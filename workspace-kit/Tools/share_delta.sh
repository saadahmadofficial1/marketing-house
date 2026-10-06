#!/bin/bash
# Share what you have LEARNT with a colleague — prose only, never your memory or your tools.
# Deliberately excludes memory/ (who you are, what must stay local), Projects/, Sessions/,
# progress/ and DATA_POLICY.json (which lists client and brand names).
set -euo pipefail
SRC="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-$HOME/Desktop/workspace_share_$(date +%Y-%m-%d)}"
DAYS="${2:-30}"

FILES=$(find "$SRC/Reference" "$SRC/charters" -name "*.md" -mtime -"$DAYS" 2>/dev/null | sort)
[ -z "$FILES" ] && { echo "Nothing changed in the last $DAYS days."; exit 0; }

echo "About to copy these files to $OUT:"
echo "$FILES" | sed "s|$SRC/|  |"
printf "Proceed? [y/N] "
read -r ANSWER
[ "$ANSWER" = "y" ] || { echo "Cancelled."; exit 0; }

mkdir -p "$OUT"
echo "$FILES" | while read -r f; do cp "$f" "$OUT/"; done
echo "Copied $(echo "$FILES" | wc -l | tr -d ' ') file(s) to $OUT"
echo
echo "Hand over prose only. Never swap Tools/ or CLAUDE.md between people — those carry"
echo "standing instructions and code, and merging them unreviewed is how a mistake spreads."
