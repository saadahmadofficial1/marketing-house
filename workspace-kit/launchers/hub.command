#!/bin/bash
# Double-click to open the Studio Hub (drag this file to your Dock for one-click access).
# WORKSPACE = the folder that holds tools/sa_hub.py; defaults to this repo's root.
WORKSPACE="${WORKSPACE:-$(cd "$(dirname "$0")/../.." && pwd)}"
cd "$WORKSPACE" || exit 1
python3 tools/sa_hub.py
