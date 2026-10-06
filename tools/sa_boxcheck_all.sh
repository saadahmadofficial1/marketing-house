#!/bin/bash
# Look at every call-out in the training series and report the ones sitting on the wrong thing,
# plus the important steps that never got a call-out at all. Saad's two complaints, 7 Aug.
#
# Runs local-only (Ollama): this check runs locally and uploads nothing. Roughly 3 hours for the
# whole series, which is why it belongs in the 1-6am window — it makes the Mac stutter.
#
#   bash Tools/sa_boxcheck_all.sh        (BOX_ROOT / BOX_OUT override the folders)
#
# Findings land in each build folder as _boxcheck/findings.json, and a combined summary at
# 5 ADMIN/BOX_REVIEW.md.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="${BOX_ROOT:-${TRAINING_ROOT:-$HOME/Downloads/training-series}/2 BUILD}"
PY="${PY:-$HERE/venv/bin/python3}"
TOOL="$HERE/sa_boxcheck.py"
OUT="${BOX_OUT:-${TRAINING_ROOT:-$HOME/Downloads/training-series}/5 ADMIN/BOX_REVIEW.md}"

echo "# Call-out review — every box looked at, not just measured" > "$OUT"
echo "" >> "$OUT"
echo "Run $(date '+%d %b %Y %H:%M'). Local vision model; ran locally, uploaded nothing." >> "$OUT"
echo "" >> "$OUT"

CHECKED=0
UNKNOWN=0
# Loop in THIS shell (process substitution), not a pipeline subshell, so the counts
# below survive it — the whole point is being able to exit non-zero.
while IFS= read -r -d '' M; do
  DIR=$(dirname "$(dirname "$M")")
  NAME="$(basename "$DIR") / $(basename "$(dirname "$M")")"
  echo "===== $NAME ====="
  "$PY" "$TOOL" "$M" --verify --gaps --every 12 -o "$(dirname "$M")/findings.json" 2>&1 | tee /tmp/bc.$$
  RC=${PIPESTATUS[0]}
  {
    echo "## $NAME"
    echo '```'
    # Three outcomes, never two: a check that did not run is UNKNOWN, not clean.
    # The 10 Aug nightly recorded a REFUSED run as 'clean' — that lie is why this
    # branch exists.
    if [ "$RC" -ne 0 ] || grep -qE "REFUSED|Traceback|ERROR" /tmp/bc.$$; then
      echo "UNKNOWN — check did not run (exit $RC):"
      tail -3 /tmp/bc.$$
    else
      grep -E "WRONG|MISSED|call-outs checked|worth a call-out" /tmp/bc.$$ || echo "clean"
    fi
    echo '```'
    echo ""
  } >> "$OUT"
  if [ "$RC" -ne 0 ] || grep -qE "REFUSED|Traceback|ERROR" /tmp/bc.$$; then
    UNKNOWN=$((UNKNOWN + 1))
  else
    CHECKED=$((CHECKED + 1))
  fi
  rm -f /tmp/bc.$$
done < <(find "$ROOT" -name "_layers.json" -print0 | sort -z)

echo ""
echo "sections checked: $CHECKED, unknown: $UNKNOWN"
echo "-> $OUT"

# A run that checked nothing is a failed run, whatever its exit code says. On 12 Aug
# all 17 sections refused in one second and the nightly recorded 'ok boxcheck' — the
# ledger then carried a green tick for work nobody did.
if [ "$CHECKED" -eq 0 ]; then
  echo "FAILED: no section was actually checked — not marking this step done."
  exit 1
fi
