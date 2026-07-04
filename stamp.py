#!/usr/bin/env python3
"""stamp.py - dev helper. WRITES index.html.

Recomputes the two self-referential numbers to a fixpoint:
  - the byte-count badge  [ N,NNN bytes ]   == the file's own size
  - "fits in it N.NN times"                 == floor(65536 / bytes, 2 dp)

Run this after editing any copy, then run ./check.sh to confirm.
This is NOT part of deploy - the served page is pre-stamped and static;
check.sh (verify-only) is what guards the deploy.
"""
import re, sys, pathlib
import cspsum

FILE = pathlib.Path(__file__).parent / "public" / "index.html"
BADGE = re.compile(r"\[ [\d,]+ bytes \]")
# Scoped to the hover overlay so it never touches the 0x… contract addresses
# elsewhere on the page.
HEX = re.compile(r'<span class="x" aria-hidden="true">\[ 0x[0-9A-Fa-f]+ bytes \]</span>')
RATIO = re.compile(r"fits in it \d+\.\d{2} times")

text = FILE.read_text(encoding="utf-8")
if not BADGE.search(text) or not HEX.search(text) or not RATIO.search(text):
    sys.exit("stamp.py: could not find badge, hex, or ratio pattern in index.html")

# Replace with tokens so the length is stable while we solve.
tmpl = RATIO.sub("fits in it \x00R\x00 times",
       HEX.sub('<span class="x" aria-hidden="true">[ \x00H\x00 bytes ]</span>',
       BADGE.sub("[ \x00B\x00 bytes ]", text)))

guess = len(tmpl.encode("utf-8"))
for _ in range(100):
    b = f"{guess:,}"
    h = f"0x{guess:04X}"
    # Floor to 2 dp so "fits in it N.NN times" is a truthful lower bound -
    # rounding to nearest could round up and overstate how many times it fits.
    hundredths = 65536 * 100 // guess
    ratio = f"{hundredths // 100}.{hundredths % 100:02d}"
    out = tmpl.replace("\x00B\x00", b).replace("\x00H\x00", h).replace("\x00R\x00", ratio)
    actual = len(out.encode("utf-8"))
    if actual == guess:
        FILE.write_text(out, encoding="utf-8")
        print(f"stamped: {b} bytes ({h}), fits {ratio}x (65536/{guess}={65536/guess:.4f})")
        h = cspsum.write_vercel()
        print(f"csp pinned: {len(h['script'])} script + {len(h['style'])} style hash(es)")
        sys.exit(0)
    guess = actual
sys.exit("stamp.py: did not converge")
