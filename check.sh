#!/usr/bin/env bash
# check.sh - VERIFY ONLY. Never writes to index.html.
# Confirms the page's self-referential claims still hold, so a stale badge
# or a blown size budget fails the deploy instead of shipping.
#
#   1. the byte-count badge equals index.html's actual size
#   2. "fits in it N.NN times" equals floor(65536 / bytes) to 2 decimals
#   3. the brotli-compressed page fits one round trip (< 14 KiB initcwnd)
#
# Usage: ./check.sh   (exit 0 = all claims hold, non-zero = mismatch)
set -euo pipefail
cd "$(dirname "$0")"

FILE=public/index.html
fail=0
note(){ printf '  %s\n' "$1"; }
warn(){ printf '  %s\n' "$1" >&2; }   # stderr: visible even when stdout is piped to /dev/null

# actual size on disk
actual=$(wc -c < "$FILE" | tr -d ' ')

# 1. badge:  [ 8,990 bytes ]
badge=$(grep -oE '\[ [0-9,]+ bytes \]' "$FILE" | grep -oE '[0-9,]+' | tr -d ',')
if [ "$badge" = "$actual" ]; then
  note "ok   byte badge: $badge = actual $actual"
else
  note "FAIL byte badge: says $badge, file is $actual"; fail=1
fi

# 2. ratio:  fits in it 7.29 times   (floor(65536 / bytes) to 2 decimals, so
#    the "fits" claim is a truthful lower bound and never rounds up)
stated=$(grep -oE 'fits in it [0-9]+\.[0-9]{2} times' "$FILE" | grep -oE '[0-9]+\.[0-9]{2}')
want=$(python3 -c "h=65536*100//$actual; print(f'{h//100}.{h%100:02d}')")
if [ "$stated" = "$want" ]; then
  note "ok   64KB ratio: $stated = 65536/$actual"
else
  note "FAIL 64KB ratio: says $stated, should be $want"; fail=1
fi

# 3. one round trip: brotli payload under the ~14 KiB initcwnd budget
budget=14336
br=$(brotli -c -q 11 "$FILE" | wc -c | tr -d ' ')
if [ "$br" -lt "$budget" ]; then
  note "ok   round trip: brotli $br bytes < $budget budget"
else
  note "FAIL round trip: brotli $br bytes >= $budget budget"; fail=1
fi

# 4. CSP integrity: the sha256 hashes pinned in vercel.json must match the page's
#    inline <script>/<style>, or the strict (no-unsafe-inline) CSP would block them
#    in production.  Hard fail - a drift here ships a broken page.
if [ -f public/vercel.json ]; then
  if cspout=$(python3 cspsum.py --verify 2>&1); then
    note "ok   csp hashes: vercel.json matches inline <script>/<style>"
  else
    note "FAIL csp hashes: vercel.json out of sync with the page - run ./stamp.py"; fail=1
    printf '%s\n' "$cspout" >&2
  fi
fi

# 5. security.txt expiry: advisory reminder to bump Expires before it lapses.
#    Warns to stderr (never blocks the deploy - only the claims above do that).
sec=public/.well-known/security.txt
if [ -f "$sec" ]; then
  exp=$(grep -iE '^Expires:' "$sec" | head -1 | sed -E 's/^[Ee]xpires:[[:space:]]*//' | tr -d '\r' || true)
  days=$(SECEXP="$exp" python3 -c "
import os, datetime
try:
    e = datetime.datetime.fromisoformat(os.environ['SECEXP'].replace('Z', '+00:00'))
    n = datetime.datetime.now(datetime.timezone.utc)
    print(int((e - n).total_seconds() // 86400))
except Exception:
    print('ERR')
" 2>/dev/null || echo ERR)
  if [ "$days" = "ERR" ] || [ -z "$days" ]; then
    warn "warn security.txt: could not parse Expires ('$exp')"
  elif [ "$days" -lt 0 ]; then
    warn "WARN security.txt EXPIRED $(( -days )) days ago - bump Expires in $sec"
  elif [ "$days" -lt 30 ]; then
    warn "warn security.txt expires in $days days - bump Expires in $sec soon"
  else
    note "ok   security.txt: Expires in $days days"
  fi
fi

if [ "$fail" -eq 0 ]; then
  echo "check.sh: all claims hold."
else
  echo "check.sh: mismatch - do not deploy." >&2
fi
exit $fail
