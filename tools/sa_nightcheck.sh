#!/bin/bash
# sa_nightcheck — the 07:00 dead-man switch. A suspended 3am job looks identical to a
# finished one unless something checks. This does: if last night's runner did not write a
# clean-exit marker in the last 10 hours, you get a notification and the day's session
# folder gets a note that auto-resume will read.
set -u
ROOT="${WORKSPACE_ROOT:-$HOME/Documents/Claude}"
STATE="$ROOT/Sessions/_nightly"
NOW=$(date +%s)
LAST=$(cat "$STATE/last_success" 2>/dev/null || echo 0)
AGE=$(( (NOW - LAST) / 3600 ))
if [ "$AGE" -lt 10 ]; then
  exit 0    # ran cleanly overnight — say nothing
fi
osascript -e 'display notification "Last night'"'"'s automation did not finish — check Sessions/_nightly" with title "Nightly run did not complete"' 2>/dev/null
TODAY=$(date +%Y-%m-%d)
mkdir -p "$ROOT/Sessions/_nightly"
echo "$(date '+%H:%M') DEAD-MAN: nightly run has no clean exit in ${AGE}h — check $STATE/$TODAY.log" \
  >> "$STATE/attention.md"
