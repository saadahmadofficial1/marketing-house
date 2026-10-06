#!/bin/bash
# sa_nightly — the one overnight entry point. Runs the heavy local work in the 1-6am
# window, resumes instead of restarting, and leaves a morning note.
#
# Rule (9 Aug): training-screen frames never go to generation services, and nothing in this
# nightly sends a picture anywhere. Frames are read by Ollama on localhost only. The one
# cloud step is the morning note, which sends TEXT ONLY (logs and counts, never images) to
# Claude; every other step is local.
#
# Resume-not-restart: each finished step is recorded in the ledger; a crash or a re-run
# picks up at the first unfinished step. Delete the ledger to force a full re-run.
# From Reference/HARNESS_IDEAS.md "Do now" #1 and #2.
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"   # the workspace this script lives in
PY="$ROOT/Tools/venv/bin/python3"
STATE_DIR="$ROOT/Sessions/_nightly"
TODAY=$(date +%Y-%m-%d)
LEDGER="$STATE_DIR/$TODAY.ledger"
LOG="$STATE_DIR/$TODAY.log"
mkdir -p "$STATE_DIR"
export PATH="$HOME/.local/bin:/usr/local/bin:/opt/homebrew/bin:$PATH"

note() { echo "$(date '+%H:%M:%S') $*" >> "$LOG"; }
done_step() { grep -qx "$1" "$LEDGER" 2>/dev/null; }
mark() { echo "$1" >> "$LEDGER"; }

run_step() {  # run_step <name> <command...>
  local name="$1"; shift
  if done_step "$name"; then note "skip $name (already done)"; return 0; fi
  note "start $name"
  if "$@" >> "$LOG" 2>&1; then mark "$name"; note "ok $name"
  else note "FAIL $name (exit $?) — will retry on next run"; return 1; fi
}

note "=== nightly run begins ==="

# Never write CapCut projects, and never contend with Saad editing at night. Saad usually
# leaves CapCut open, so exiting here (as this did until 8 Sep) silently skipped the WHOLE
# night — catalogue, morning note and the clean-exit marker included, which then
# tripped the 07:00 dead-man every day. Only the project-touching step is skipped now.
CAPCUT_OPEN=0
if pgrep -x CapCut >/dev/null; then
  CAPCUT_OPEN=1
  note "CapCut is open — skipping the project-reading step only; the rest still runs"
fi

# The vision check is the longest step: on a full series it once ran ~10h a night (01:22 ->
# still going at 11:13) and starved the steps after it, so the nightly never reached a clean
# exit. While a series is idle, run with BOXCHECK_PAUSED=1 to skip it. Nothing else changes.
BOXCHECK_PAUSED="${BOXCHECK_PAUSED:-0}"

# 1. Look at every call-out box in the series (local Ollama only). Reads CapCut projects.
if [ "$BOXCHECK_PAUSED" = "1" ]; then
  note "skip boxcheck (paused — unset BOXCHECK_PAUSED to resume)"
elif [ "$CAPCUT_OPEN" = "0" ]; then
  run_step boxcheck  caffeinate -im /bin/bash "$ROOT/Tools/sa_boxcheck_all.sh"
else
  note "skip boxcheck (CapCut open)"
fi

# 2. Regenerate the tool catalogue (pure local).
run_step toolindex "$PY" "$ROOT/Tools/sa_toolindex.py"

# 3. Morning note — TEXT ONLY to Claude. Counts and log tails, never a frame, never a
#    screenshot, never a file from the training-series folders. Skipped silently if claude is absent.
if ! done_step morningnote && command -v claude >/dev/null 2>&1; then
  SUMMARY=$(tail -40 "$LOG"; echo "---"; tail -12 "$ROOT/Sessions/automation_heartbeat.log" 2>/dev/null)
  echo "$SUMMARY" | claude -p --model claude-opus-5 \
    "This is the overnight automation log from Saad's video-production Mac. Write him a
     3-line plain-English morning note: what ran, what failed (if anything), and the one
     thing to look at first. British English, no jargon, no file paths." \
    > "$STATE_DIR/$TODAY.morning.md" 2>>"$LOG" && mark morningnote \
    && note "ok morningnote" || note "morningnote skipped/failed (fine)"
fi

# 4. Clean exit marker — the dead-man check at 07:00 looks for this.
date +%s > "$STATE_DIR/last_success"
note "=== nightly run complete ==="
