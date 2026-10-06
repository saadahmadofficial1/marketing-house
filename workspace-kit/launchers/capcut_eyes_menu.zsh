#!/bin/zsh
# CapCut Eyes menu-bar indicator: starts the watch bar (sa_watchbar.py) once; never a second copy.
# WORKSPACE = the folder that receives Sessions/_eyes/ (default: the repo root, three folders
# above this launcher); TOOLS_DIR = the folder with sa_watchbar.py (default: tools/ there, or
# Tools/ in your own workspace); PYTHON can be overridden too. apps/capcut-eyes/make_apps.sh
# bakes them into "CapCut Eyes Menu.app".
if [ -z "${WORKSPACE:-}" ]; then WORKSPACE="${0:A:h:h:h}"; fi
if [ -z "${TOOLS_DIR:-}" ]; then
  if [ -f "$WORKSPACE/tools/sa_watchbar.py" ]; then TOOLS_DIR="$WORKSPACE/tools"; else TOOLS_DIR="$WORKSPACE/Tools"; fi
fi
if [ -z "${PYTHON:-}" ]; then PYTHON="$TOOLS_DIR/venv/bin/python3"; [ -x "$PYTHON" ] || PYTHON=python3; fi
if [ ! -f "$TOOLS_DIR/sa_watchbar.py" ]; then
  echo "CapCut Eyes menu: $TOOLS_DIR/sa_watchbar.py not found - set WORKSPACE or TOOLS_DIR" >&2
  exit 1
fi
cd "$WORKSPACE" || exit 1
if pgrep -f "$TOOLS_DIR/sa_watchbar.py" >/dev/null 2>&1; then
  exit 0
fi
mkdir -p "$WORKSPACE/Sessions/_eyes"
nohup "$PYTHON" "$TOOLS_DIR/sa_watchbar.py" \
  >>"$WORKSPACE/Sessions/_eyes/menu.log" 2>&1 </dev/null &
exit 0
