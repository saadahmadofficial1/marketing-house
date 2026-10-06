#!/bin/bash
# Double-click this file to open the site.
# It starts a tiny local web server in this folder and opens your browser at it.
# Leave this black Terminal window open while you browse. Close it when finished.
cd "$(dirname "$0")"
PORT=4200
while lsof -i :$PORT >/dev/null 2>&1; do PORT=$((PORT+1)); done
echo ""
echo "  Offline site preview"
echo "  Opening http://127.0.0.1:$PORT/en/"
echo ""
echo "  Keep this window open while you browse."
echo "  Close it when you are done."
echo ""
python3 -m http.server $PORT >/dev/null 2>&1 &
SERVER=$!
sleep 1
open "http://127.0.0.1:$PORT/en/"
trap "kill $SERVER 2>/dev/null" EXIT
wait $SERVER
