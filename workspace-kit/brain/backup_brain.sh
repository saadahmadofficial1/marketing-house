#!/bin/bash
#
# Brain — local backup (durability layer).
#
# Closes the single biggest gap in the brain: it lived in exactly one place.
# This script keeps THREE independent local copies of the brain *knowledge*
# (the .md files) + the server code, none of them inside the vault —
# so one `rm -rf` or disk-folder mistake on the source can't take the backups
# with it.
#
#   1. VERSIONED GIT VAULT  — full history of every brain edit (what changed,
#                             when). `git log` / `git diff` to inspect or revert.
#   2. ROTATING TARBALLS     — last 30 timestamped .tar.gz snapshots. Recovers
#                             even if the vault git repo is ever corrupted.
#   3. LOG                   — one line per run appended to backup.log.
#
# Data stays LOCAL (honours the standing rule). To add true off-disk
# redundancy, point BACKUP_ROOT at an external drive — nothing else changes.
#
# Note: the Chroma vector DB is deliberately NOT backed up — it's fully
# rebuildable from the .md via `sa_reindex()`, so backing up the source
# markdown backs up everything that matters, tiny and fast.

set -euo pipefail

# --- config -----------------------------------------------------------------
CODE="$(cd "$(dirname "$0")" && pwd)"     # this brain/ folder
SRC="${BRAIN_DIR:-$(dirname "$CODE")}"    # the vault that contains it
BACKUP_ROOT="${BACKUP_ROOT:-$HOME/Brain_Backups}"   # OUTSIDE the source tree
VAULT="$BACKUP_ROOT/vault"
SNAPS="$BACKUP_ROOT/snapshots"
LOG="$BACKUP_ROOT/backup.log"
KEEP=30                                                      # tarballs to retain
STAMP="$(date '+%Y%m%d_%H%M%S')"

# Files that ARE the brain knowledge + the code that serves it.
BRAIN_GLOBS=( "$SRC"/*.md )                # includes CLAUDE.md
# All hand-written code in brain/ — INCLUDING this backup script and the
# eval harness, so a wipe of the source folder loses nothing recoverable.
CODE_FILES=( rag.py server.py pyproject.toml uv.lock .gitignore \
             backup_brain.sh evals.py eval_set.json )

# --- setup ------------------------------------------------------------------
mkdir -p "$BACKUP_ROOT" "$VAULT" "$SNAPS"
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }

# --- single-run lock --------------------------------------------------------
# Two backups at once (e.g. the daily launchd run + a manual run) collide on
# git's index.lock and one fails. `mkdir` is atomic, so it's a safe mutex:
# whoever creates the dir first wins; the other exits cleanly. Stale locks
# older than 10 min are reclaimed (a previous run that was killed mid-way).
LOCK="$BACKUP_ROOT/.backup.lock"
if ! mkdir "$LOCK" 2>/dev/null; then
  if [ -d "$LOCK" ] && [ "$(find "$LOCK" -maxdepth 0 -mmin +10 2>/dev/null)" ]; then
    rmdir "$LOCK" 2>/dev/null || true
    mkdir "$LOCK" 2>/dev/null || { echo "another backup is running — skipping"; exit 0; }
  else
    echo "another backup is running — skipping"; exit 0
  fi
fi
trap 'rmdir "$LOCK" 2>/dev/null || true' EXIT

# --- 1. copy current state into the vault -----------------------------------
mkdir -p "$VAULT/brain" "$VAULT/code"
copied=0
for f in "${BRAIN_GLOBS[@]}"; do
  [ -e "$f" ] && cp -p "$f" "$VAULT/brain/" && copied=$((copied+1))
done
for f in "${CODE_FILES[@]}"; do
  [ -e "$CODE/$f" ] && cp -p "$CODE/$f" "$VAULT/code/"
done

# --- 2. commit the vault (versioned history) --------------------------------
if [ ! -d "$VAULT/.git" ]; then
  git -C "$VAULT" init -q
  git -C "$VAULT" config user.email "yourteam@yourcompany.com"
  git -C "$VAULT" config user.name "Brain Backup"
fi
git -C "$VAULT" add -A
if git -C "$VAULT" diff --cached --quiet; then
  vault_msg="no change"
else
  git -C "$VAULT" commit -q -m "brain snapshot $STAMP"
  vault_msg="committed"
fi

# --- 3. rotating tarball snapshot -------------------------------------------
TARBALL="$SNAPS/brain_$STAMP.tar.gz"
tar -czf "$TARBALL" -C "$VAULT" brain code
# prune to the most recent $KEEP tarballs
ls -1t "$SNAPS"/brain_*.tar.gz 2>/dev/null | tail -n +$((KEEP+1)) | while read -r old; do
  rm -f "$old"
done

size="$(du -h "$TARBALL" | cut -f1)"
nsnaps="$(ls -1 "$SNAPS"/brain_*.tar.gz 2>/dev/null | wc -l | tr -d ' ')"
log "backup ok — $copied brain files, vault $vault_msg, tarball $size, $nsnaps snapshots retained"

echo ""
echo "✅ brain backed up"
echo "   Vault (history): $VAULT   ($vault_msg)"
echo "   Snapshot:        $TARBALL   ($size)"
echo "   Retained:        $nsnaps / $KEEP tarballs"
