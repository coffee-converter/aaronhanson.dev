#!/usr/bin/env python3
"""make-og.py - regenerate public/og.png.

A long-exposure of the page's own n-body sim (same physics, same CCW orbits):
orange planetary trails around a white star, with the wordmark. Dev tool; lives
at the repo root so it is never deployed. Deterministic per --seed, so the card
is stable across regenerations.

  python3 make-og.py                      # default seed -> public/og.png
  python3 make-og.py --seed 12 --out x.png
"""
import argparse, math, pathlib
import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H = 1200, 630
PAPER = np.array([18, 20, 22])       # #121416  page dark background
ORANGE = np.array([255, 106, 43])    # #ff6a2b  dark-mode accent
STAR = np.array([245, 246, 248])     # near-white central body
INK = (214, 216, 218)                # #d6d8da  dark-mode ink
TAG = (198, 202, 207)                # tagline gray (secondary to the wordmark)
DIM = (131, 136, 142)                # #83888e  dark-mode dim
SW, SH = 640, 200                    # native sim field
CX, CY = SW / 2, SH / 2
G, SOFT = 900.0, 40.0


def font(sz, weight="Regular"):
    # SF Mono, to match what the site renders via `ui-monospace` on macOS
    try:
        f = ImageFont.truetype("/System/Library/Fonts/SFNSMono.ttf", sz)
        try: f.set_variation_by_name(weight)
        except Exception: pass
        return f
    except Exception:
        return ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", sz,
                                  index=1 if weight in ("Bold", "Semibold", "Heavy") else 0)


def simulate(seed, frames=2200):
    """Run the n-body sim; return per-frame positions [[(x,y) x9], ...] (body 0 = star)."""
    rng = np.random.default_rng(seed)
    bodies = [dict(x=CX, y=CY, vx=0.0, vy=0.0, m=32.0)]
    for _ in range(8):
        a = rng.uniform(0, 6.283); d = rng.uniform(34, 92)
        v = math.sqrt(G * 32 / d) / d * rng.uniform(.85, 1.1)
        bodies.append(dict(x=CX + math.cos(a) * d, y=CY + math.sin(a) * d,
                           vx=math.sin(a) * v * d, vy=-math.cos(a) * v * d,  # CCW
                           m=rng.uniform(.4, 1.6)))
    mx = my = M = 0.0
    for p in bodies: mx += p['vx'] * p['m']; my += p['vy'] * p['m']; M += p['m']
    for p in bodies: p['vx'] -= mx / M; p['vy'] -= my / M

    traj = []
    for f in range(frames):
        for _ in range(3):
            dt = .016
            for i, pi in enumerate(bodies):
                ax = ay = 0.0
                for j, pj in enumerate(bodies):
                    if i == j: continue
                    dx = pj['x'] - pi['x']; dy = pj['y'] - pi['y']
                    r2 = dx * dx + dy * dy + SOFT; r = math.sqrt(r2); ff = G * pj['m'] / (r2 * r)
                    ax += dx * ff; ay += dy * ff
                pi['vx'] += ax * dt; pi['vy'] += ay * dt
            for p in bodies: p['x'] += p['vx'] * .016; p['y'] += p['vy'] * .016
        P0 = bodies[0]
        for i, p in enumerate(bodies):
            if i and (p['x'] < -40 or p['x'] > SW + 40 or p['y'] < -40 or p['y'] > SH + 40):
                a = rng.uniform(0, 6.283); d = rng.uniform(40, 90); v = math.sqrt(G * 32 / d) / d
                p['x'] = P0['x'] + math.cos(a) * d; p['y'] = P0['y'] + math.sin(a) * d
                p['vx'] = P0['vx'] + math.sin(a) * v * d; p['vy'] = P0['vy'] - math.cos(a) * v * d
        cx = cy = ux = uy = m = 0.0
        for p in bodies: cx += p['x'] * p['m']; cy += p['y'] * p['m']; ux += p['vx'] * p['m']; uy += p['vy'] * p['m']; m += p['m']
        cx = cx / m - CX; cy = cy / m - CY; ux /= m; uy /= m
        for p in bodies: p['x'] -= cx * .03; p['y'] -= cy * .03; p['vx'] -= ux; p['vy'] -= uy
        traj.append([(p['x'], p['y']) for p in bodies])
    return traj


def render(seed, out, frames=2200, tagline=True):
    traj = simulate(seed, frames)
    scale = W / SW
    y_off = (H - SH * scale) / 2
    accO = np.zeros((H, W))

    def splat(cx, cy, amt, rad):
        x0, x1 = max(0, int(cx - rad)), min(W, int(cx + rad) + 1)
        y0, y1 = max(0, int(cy - rad)), min(H, int(cy + rad) + 1)
        if x0 >= x1 or y0 >= y1: return
        ys, xs = np.mgrid[y0:y1, x0:x1]
        accO[y0:y1, x0:x1] += amt * np.exp(-((xs - cx) ** 2 + (ys - cy) ** 2) / (2 * (rad / 2.5) ** 2))

    for frame in traj:
        for i, (x, y) in enumerate(frame):
            if i: splat(x * scale, y * scale + y_off, 0.14, 3.0)

    satO = 1.0 - np.exp(-accO * 1.2)
    img = PAPER[None, None, :] + (ORANGE - PAPER)[None, None, :] * satO[:, :, None]
    yy, xx = np.mgrid[0:H, 0:W]
    r2 = (xx - W / 2) ** 2 + (yy - H / 2) ** 2
    glow = np.clip(0.85 * np.exp(-r2 / (2 * 11 ** 2)) + np.exp(-r2 / (2 * 4.5 ** 2)), 0, 1)
    img = img * (1 - glow[:, :, None]) + STAR[None, None, :] * glow[:, :, None]
    # soft bottom scrim so the lower text separates cleanly from the trails
    ramp = np.clip((yy - H * 0.60) / (H * 0.40), 0, 1) * 0.82
    img = img * (1 - ramp[:, :, None]) + PAPER[None, None, :] * ramp[:, :, None]
    im = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8), 'RGB')

    d = ImageDraw.Draw(im)

    def draw_centered(text, fnt, fill, y, track):
        total = sum(d.textlength(c, font=fnt) + track for c in text) - track
        x = (W - total) / 2
        for c in text:
            d.text((x, y), c, font=fnt, fill=fill)
            x += d.textlength(c, font=fnt) + track

    draw_centered("AARON HANSON", font(66, "Bold"), INK, 60, 12)
    if tagline:
        draw_centered("my stack starts at the antenna", font(27, "Regular"), TAG, 486, 1)
        draw_centered("aaronhanson.dev", font(20, "Regular"), DIM, 556, 2)

    im.save(out, optimize=True)
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--seed', type=int, default=7)
    ap.add_argument('--out', default=str(pathlib.Path(__file__).parent / "public" / "og.png"))
    ap.add_argument('--frames', type=int, default=2200)
    a = ap.parse_args()
    out = render(a.seed, a.out, a.frames)
    print(f"wrote {out} ({pathlib.Path(out).stat().st_size} bytes, seed {a.seed})")
