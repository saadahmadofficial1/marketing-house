#!/bin/bash
# Double-click to list the voices on your Fish Audio account, with their ids.
cd "$(dirname "$0")" || exit 1
[ -x ./.venv/bin/python3 ] || { echo "Run SETUP.command first."; read -r -p "Press return."; exit 1; }
./.venv/bin/python3 fish_voice.py --list
echo
read -r -p "Press return to close."
