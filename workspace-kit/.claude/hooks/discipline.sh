#!/bin/zsh
# Studio operating-discipline reminder — injected each user turn.
# Turns the recurring gaps Saad called out into standing rules.
cat <<'MSG'
[Studio DISCIPLINE — auto-injected, follow every turn]
1. LOG IN REAL TIME: the moment Saad corrects / approves / starts a project → sa_log NOW, same turn. Never batch at session end.
2. VERIFY BEFORE GENERATING: re-read the brief + check aspect ratio/continuity/prop-count/eye-line BEFORE firing any generation. No fire-then-fix.
3. CAVEMAN BY DEFAULT: terse. Pick the best option and go — don't lay out A/B/C menus unless Saad asks to choose.
4. DON'T OVER-POLL: wait smart on long jobs; don't re-check the same job 8+ times.
5. ANTICIPATE: flag the next-project reuse or the looming problem BEFORE Saad asks.
6. CHECK BEFORE NEW: before treating a request as new, sa_search the brain + scan Tools/. If already solved, SAY SO ("we did this — here's the solution/script"); Saad is human, he forgets. Don't redo solved work.
7. REUSE SCRIPTS: media glue = Tools/media_kit.py (put/grab/sheet/crop/probe) + sa_*.py. Call them, don't re-write Python each task. New repeat pattern -> add a function, don't burn tokens twice.
8. STEP SHAPE: number every multi-step task, one bounded action per step; restate state each turn ("step 3 of 5 done, next X"); end with ONE concrete next action Saad can do in under 2 minutes.
MSG

# Saad's idea, 19 Aug: checkpoint the decisions as the context fills, rather than
# relying on one lossy summary when it is already full. Prints nothing until a
# checkpoint is actually due, so the normal turn is unchanged.
WS="${CLAUDE_PROJECT_DIR:-$PWD}"          # the workspace root (Claude Code sets this for hooks)
PY="$WS/Tools/venv/bin/python3"; [ -x "$PY" ] || PY=python3
"$PY" "$WS/Tools/sa_checkpoint.py" --due 2>/dev/null
