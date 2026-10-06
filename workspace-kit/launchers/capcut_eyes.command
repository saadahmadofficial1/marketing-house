#!/bin/zsh
# Double-click launcher for the CapCut Eyes control pad (sa_eyes_pad.py).
# WORKSPACE defaults to the repo root (two folders above this launcher); export
# WORKSPACE to point at your own workspace instead.
export TK_SILENCE_DEPRECATION=1
WORKSPACE="${WORKSPACE:-${0:A:h:h:h}}"
cd "$WORKSPACE" || exit 1
PAD="$WORKSPACE/Tools/sa_eyes_pad.py"
[[ -f "$PAD" ]] || PAD="$WORKSPACE/tools/sa_eyes_pad.py"
PY="$WORKSPACE/Tools/venv/bin/python3"
[[ -x "$PY" ]] || PY="$(command -v python3)"
exec "$PY" "$PAD"
