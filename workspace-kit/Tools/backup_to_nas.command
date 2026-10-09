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

SRC="$WORKSPACE"
if [ ! -f "$SRC/CLAUDE.md" ]; then   # --delete mirrors the source: never run it from the wrong folder
  echo "❌ $SRC does not look like the workspace (no CLAUDE.md). Nothing copied, nothing deleted."
  read -p "Press Enter to close."; exit 1
fi
rsync -a --delete \
  --exclude 'Tools/venv' --exclude 'Tools/installs' --exclude 'Tools/external' \
  --exclude 'Tools/headroom' --exclude '**/__pycache__' --exclude '**/node_modules' \
  --exclude '.DS_Store' \
  "$SRC/" "$DEST/Claude/"
RC_WORKSPACE=$?

RC_BRAIN=0
BRAIN_BACKUPS="${BACKUP_ROOT:-$HOME/Brain_Backups}"   # brain/backup_brain.sh writes them; same default and override
if [ -d "$BRAIN_BACKUPS" ]; then
  rsync -a --delete "$BRAIN_BACKUPS/" "$DEST/Brain_Backups/"
  RC_BRAIN=$?
else
  echo "⚠️  No brain backups at $BRAIN_BACKUPS (run brain/backup_brain.sh, or set BACKUP_ROOT) - that part was skipped."
fi
cp "$HOME/.claude/CLAUDE.md" "$DEST/machine-wide-CLAUDE.md" 2>/dev/null

echo ""
if [ "$RC_WORKSPACE" -eq 0 ] && [ "$RC_BRAIN" -eq 0 ]; then
  date +%Y-%m-%d > "$WORKSPACE/.last_nas_backup"   # the doctor reads this stamp
  echo "✅ Backup complete: $(date '+%A %d %B %Y, %H:%M')"
else
  echo "❌ Backup FAILED (workspace rsync exit $RC_WORKSPACE, brain backups exit $RC_BRAIN)."
  echo "   Not recorded as a backup. Check the NAS connection and run it again."
fi
du -sh "$DEST" 2>/dev/null
read -p "Press Enter to close."
