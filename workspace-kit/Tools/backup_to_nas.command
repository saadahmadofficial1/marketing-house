#!/bin/bash
# Double-click to back up the whole AI workspace to the NAS (weekly).
# Settings (override in the environment): NAS_URL = the SMB share, NAS_SHARE = where macOS
# mounts it, NAS_FOLDER = the folder inside it, WORKSPACE = the workspace root.
NAS_URL="${NAS_URL:-smb://nas.local/Share}"
SHARE="${NAS_SHARE:-/Volumes/Share}"
DEST="$SHARE/${NAS_FOLDER:-AI workspace backup}"

cd "$(dirname "$0")"
WORKSPACE="${WORKSPACE:-$(cd .. && pwd)}"
# auto-mount the share if needed (first time macOS asks for the NAS login — tick "Remember")
if [ ! -d "$SHARE" ]; then
  echo "Connecting to NAS..."
  osascript -e "mount volume \"$NAS_URL\"" >/dev/null 2>&1
  for i in $(seq 1 15); do [ -d "$SHARE" ] && break; sleep 1; done
fi
if [ ! -d "$SHARE" ]; then
  echo "❌ Could not reach the NAS ($NAS_URL). Are you on the same network?"
  read -p "Press Enter to close."; exit 1
fi

mkdir -p "$DEST"
echo "Backing up to: $DEST"
echo "(first run copies everything — can take a while; later runs copy only changes)"

rsync -a --delete \
  --exclude 'Tools/venv' --exclude 'Tools/installs' --exclude 'Tools/external' \
  --exclude 'Tools/headroom' --exclude '**/__pycache__' --exclude '**/node_modules' \
  --exclude '.DS_Store' \
  "$WORKSPACE/" "$DEST/Claude/"

# the brain backups (brain/backup_brain.sh writes them; same default and override)
BRAIN_BACKUPS="${BACKUP_ROOT:-$HOME/Brain_Backups}"
MISSING=""
if [ -d "$BRAIN_BACKUPS" ]; then
  rsync -a --delete "$BRAIN_BACKUPS/" "$DEST/Brain_Backups/"
else
  MISSING=1
  echo "WARNING: no brain backups at $BRAIN_BACKUPS (run brain/backup_brain.sh, or set BACKUP_ROOT) - not copied."
fi
cp "$HOME/.claude/CLAUDE.md" "$DEST/machine-wide-CLAUDE.md" 2>/dev/null

date +%Y-%m-%d > "$WORKSPACE/.last_nas_backup"
echo ""
if [ -n "$MISSING" ]; then
  echo "⚠️  Backup finished WITHOUT the brain backups (see the warning above): $(date '+%A %d %B %Y, %H:%M')"
else
  echo "✅ Backup complete: $(date '+%A %d %B %Y, %H:%M')"
fi
du -sh "$DEST" 2>/dev/null
read -p "Press Enter to close."
