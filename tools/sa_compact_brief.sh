#!/bin/bash
# sa_compact_brief — fired by the SessionStart:compact hook, the instant a /compact happens.
#
# Requirement (9 Aug 2026): after every compact, recover the maximum information and
# forget nothing.
#
# A compact summarises the conversation, and a summary can drop details. This makes that
# survivable: the moment the compacted session starts, the GROUND TRUTH is re-read from disk
# and injected into context — the active session state, his per-video progress, system
# health, open defects, and the standing pointers. The summary becomes a convenience, not a
# single point of failure, because everything that matters was logged to files in real time.
#
# Output is budgeted (~90 lines) — a briefing, not a dump. Anything deeper is one
# sa_search away, and the pointers say exactly where.
set -u
ROOT="${WORKSPACE_ROOT:-$HOME/Documents/Claude}"
ADMIN="${TRAINING_ROOT:-$HOME/Downloads/training-series}/5 ADMIN"

echo "=== POST-COMPACT GROUND TRUTH (from disk, just now — trust this over the summary) ==="

# 1. the active session and its live state
LATEST=$(cat "$ROOT/Sessions/LATEST.txt" 2>/dev/null)
echo "--- active session: ${LATEST:-none} ---"
if [ -n "${LATEST:-}" ] && [ -f "$ROOT/Sessions/$LATEST/state.json" ]; then
  head -c 1800 "$ROOT/Sessions/$LATEST/state.json"; echo
  echo "--- last 3 log entries ---"
  tail -3 "$ROOT/Sessions/$LATEST/log.jsonl" 2>/dev/null | cut -c1-260
fi

# 2. per-video progress, if the project keeps a PROGRESS.json tracker (optional)
if [ -f "$ADMIN/PROGRESS.json" ]; then
  echo "--- his progress (PROGRESS.json) ---"
  python3 -c "
import json
d=json.load(open('$ADMIN/PROGRESS.json'))
vs=d.get('videos',{})
done=[k for k,v in vs.items() if v.get('saad')=='done']
todo=[k for k,v in vs.items() if v.get('saad')!='done']
print(f'{len(done)} done: ' + ', '.join(k.split()[0]+' '+k.split()[1] if len(k.split())>1 else k for k in done))
print(f'{len(todo)} not done: ' + ', '.join(k.split()[0]+' '+k.split()[1] if len(k.split())>1 else k for k in todo))
" 2>/dev/null
fi

# 2b. EVERY open thread, not just the active one.
# Requirement (14 Aug): compacting must never lose an open thread. He proved the gap by
# naming two repos this workspace had never heard of.
# Sections 1-2 recover the ACTIVE session in detail and lose everything else, so a
# compact mid-series silently drops every other commitment. This lists them all.
"$ROOT/Tools/venv/bin/python3" "$ROOT/Tools/sa_threads.py" 2>/dev/null | head -46

# 2c. checkpoints written DURING this session, before the context filled.
# Saad's idea, 19 Aug: a summary written at 100k still sees detail that a summary
# written at 1M has lost. The compaction summary and these checkpoints are two
# different views of the session — read both, and prefer the checkpoint where they
# disagree, because it was written while the detail was still in front of me.
CKPT="$ROOT/Sessions/${LATEST:-none}/checkpoints"
if [ -d "$CKPT" ] && ls "$CKPT"/[0-9]*.md >/dev/null 2>&1; then
  echo "--- CHECKPOINTS written during this session (fuller than the summary) ---"
  for f in "$CKPT"/[0-9]*.md; do
    echo "=== $(basename "$f")"
    head -c 2200 "$f"; echo
  done
fi

# 3. system health, one line per red light only
echo "--- doctor (red lights only) ---"
DOCTOR_PY="$ROOT/Tools/venv/bin/python3"; [ -x "$DOCTOR_PY" ] || DOCTOR_PY=python3
if [ -f "$ROOT/Tools/sa_doctor.py" ]; then
  DOC_OUT=$("$DOCTOR_PY" "$ROOT/Tools/sa_doctor.py" 2>/dev/null); DOC_RC=$?
  if [ "$DOC_RC" -eq 0 ]; then
    echo "all green"
  elif ! printf '%s\n' "$DOC_OUT" | grep "❌"; then
    # a crash or a missing dependency is not a pass: say UNKNOWN, never "all green"
    echo "doctor could not run (exit $DOC_RC) - health UNKNOWN, run Tools/sa_doctor.py by hand"
  fi
else
  echo "doctor not installed (Tools/sa_doctor.py missing) - health UNKNOWN"
fi

# 4. anything the overnight watchdog flagged
[ -f "$ROOT/Sessions/_nightly/attention.md" ] && { echo "--- NIGHTLY NEEDS ATTENTION ---"; tail -3 "$ROOT/Sessions/_nightly/attention.md"; }

# 5. open escaped defects
[ -f "$ROOT/Reference/VERIFIER_GAPS.md" ] && \
  echo "--- open verifier gaps: $(grep -c 'OPEN:' "$ROOT/Reference/VERIFIER_GAPS.md" 2>/dev/null) (Reference/VERIFIER_GAPS.md) ---"

# 6. the standing pointers — where full recall lives
cat <<'EOF'
--- standing recall (read on demand, do not reload wholesale) ---
SAAD_METHOD.md                     how he judges, talks, decides — read before creative work
Reference/MISTAKE_PATTERNS.md      76 mistakes, 16 patterns — check before repeating history
Reference/DEBUG_PLAYBOOK.md        the 10 diagnosis rules + recall table
Reference/TOOLS_CATALOG.md         the private tool catalogue — CHECK BEFORE BUILDING ANYTHING
Reference/PIPELINE_TRAPS.md        every video-pipeline trap and its guard
5 ADMIN/GAPS.html                  Saad's one progress dashboard
sa_search("<topic>")              the brain — every correction since May, superseded demoted
--- if the summary and this briefing disagree, THIS wins; and if something is not
--- here at all, say "I don't have that" rather than reconstructing it from memory
--- hard rules that survive any summary ---
screen frames never go to generation services; routine checks run locally and upload
nothing, and only large one-off verification passes use an AI coding agent (text-only
prompts are fine) · never write while CapCut
is open · never touch a video Saad declared done · backups before every write · three-outcome
verification (ok/wrong/UNKNOWN) · log corrections to the brain the same turn · British
English · his intros/outros are his own task
EOF
