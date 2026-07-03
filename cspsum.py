#!/usr/bin/env python3
"""cspsum.py - CSP sha256 hashes of every inline <script>/<style> the site serves.

The site ships a strict Content-Security-Policy with NO 'unsafe-inline'. The CSP
applies to ALL routes (source "/(.*)"), so EVERY served HTML page's inline blocks
must be pinned by hash in vercel.json (index.html AND 404.html), or the browser
blocks them - that's how a strict CSP left the 404 unstyled once.

The JSON-LD <script type="application/ld+json"> is a data block, never executed,
so CSP doesn't touch it and it needs no hash.

Shared by:
  - stamp.py  : after stamping, pins the current hashes into vercel.json (--write)
  - check.sh  : refuses to deploy if vercel.json's hashes drift (--verify)

  python3 cspsum.py           # print every inline hash across the site
  python3 cspsum.py --write   # pin them into public/vercel.json
  python3 cspsum.py --verify  # exit 0 if vercel.json matches the pages, else 1
"""
import re, sys, base64, hashlib, pathlib

ROOT = pathlib.Path(__file__).parent
VJSON = ROOT / "public" / "vercel.json"
HTML = ["public/index.html", "public/404.html"]   # every HTML page the CSP covers


def _sha256(content):
    return "sha256-" + base64.b64encode(hashlib.sha256(content.encode("utf-8")).digest()).decode()


def hashes():
    """Sorted, de-duped {'script':[...], 'style':[...]} across all served HTML pages."""
    scripts, styles = set(), set()
    for f in HTML:
        html = (ROOT / f).read_text(encoding="utf-8")
        for m in re.finditer(r"<script>(.*?)</script>", html, re.S):   # bare <script>; skips ld+json
            scripts.add(_sha256(m.group(1)))
        for m in re.finditer(r"<style>(.*?)</style>", html, re.S):
            styles.add(_sha256(m.group(1)))
    return {"script": sorted(scripts), "style": sorted(styles)}


def _fmt(hs):
    return " ".join("'%s'" % h for h in hs)


def write_vercel(h=None):
    """Pin the current hashes into vercel.json's script-src / style-src."""
    h = h or hashes()
    v = VJSON.read_text(encoding="utf-8")
    v = re.sub(r"script-src [^;]*;", lambda m: "script-src %s;" % _fmt(h["script"]), v)
    v = re.sub(r"style-src [^;]*;", lambda m: "style-src %s;" % _fmt(h["style"]), v)
    VJSON.write_text(v, encoding="utf-8")
    return h


def read_vercel():
    """The sorted {'script':[...], 'style':[...]} hashes currently pinned in vercel.json."""
    v = VJSON.read_text(encoding="utf-8")
    def pull(d):
        m = re.search(d + r"-src ([^;]*);", v)
        return sorted(re.findall(r"'(sha256-[^']+)'", m.group(1))) if m else []
    return {"script": pull("script"), "style": pull("style")}


if __name__ == "__main__":
    if "--write" in sys.argv:
        h = write_vercel()
        print("pinned %d script + %d style hash(es)" % (len(h["script"]), len(h["style"])))
    elif "--verify" in sys.argv:
        want, have = hashes(), read_vercel()
        for k in ("script", "style"):
            tag = "ok  " if want[k] == have[k] else "FAIL"
            print("  %s csp %-6s %d hash(es)" % (tag, k, len(have[k])))
        sys.exit(0 if want == have else 1)
    else:
        h = hashes()
        for k in ("script", "style"):
            for v in h[k]:
                print("%s: %s" % (k, v))
