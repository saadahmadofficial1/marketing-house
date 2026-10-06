#!/bin/bash
# Double-click this once. It installs what the kit needs and opens the two boxes to fill.
cd "$(dirname "$0")" || exit 1
echo "Fish Voice Kit — setup"
echo "======================"
echo

# --- ffmpeg (does the audio tidying) -----------------------------------------
if command -v ffmpeg >/dev/null 2>&1; then
  echo "[1/4] ffmpeg .......... already installed"
elif command -v brew >/dev/null 2>&1; then
  echo "[1/4] ffmpeg .......... installing, this takes a few minutes..."
  brew install ffmpeg
else
  echo "[1/4] ffmpeg .......... MISSING, and Homebrew is not installed."
  echo "      Install Homebrew first from https://brew.sh, then run this again."
  echo
  read -r -p "Press return to close."
  exit 1
fi

# --- a private Python just for this kit --------------------------------------
echo "[2/4] Python packages . setting up"
if [ ! -d ".venv" ]; then python3 -m venv .venv || exit 1; fi
./.venv/bin/pip install --quiet --upgrade pip requests || exit 1

# --- the two boxes to fill ---------------------------------------------------
if [ ! -f fish_key.txt ]; then
  cat > fish_key.txt <<'EOF'
# Paste your Fish Audio API key below, then save (Cmd+S).
# Get it from fish.audio -> Developer -> API Keys. It starts with sk-fish-
# Only you can read this file, and the key is sent only to Fish Audio.
#
# Several keys are fine — one per team member or language. Put each key on its own
# line and give it a label, like:
#
#     arabic: sk-fish-PASTE-KEY
#     english: sk-fish-PASTE-KEY
#
# One key? Just paste it on a line by itself. The labels are only there to tell the
# keys apart when the kit asks which voice you want.

EOF
fi
chmod 600 fish_key.txt
echo "[3/4] Settings files .. ready"

echo "[4/4] Opening them for you now"
open -e fish_key.txt
echo
echo "Paste your API key into that window and save it (Cmd+S)."
echo "Then type your script into lines.txt and double-click GENERATE.command —"
echo "it will show your own voices and let you pick one."
echo "Clone only your own voice, or one you have explicit permission to use."
echo
read -r -p "Press return to close."
