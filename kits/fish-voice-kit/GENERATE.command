#!/bin/bash
# Double-click to speak everything in lines.txt using your cloned voice.
cd "$(dirname "$0")" || exit 1
[ -x ./.venv/bin/python3 ] || { echo "Run SETUP.command first."; read -r -p "Press return."; exit 1; }
./.venv/bin/python3 fish_voice.py "$@"
echo
read -r -p "Press return to close."
