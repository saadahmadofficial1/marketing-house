# Sessions — how continuity works

Each task gets a folder: `Sessions/<YYYY-MM-DD>_<short-slug>/` containing:

- **`state.json`** — the live truth. Edit in place as things change. Shape:
  ```json
  {
    "session": "2026-01-15_campaign-deck",
    "updated": "2026-01-15T10:30:00Z",
    "agent": "claude",
    "purpose": "one line: what this session is for",
    "status": "in_progress",
    "last_action": "the most recent completed step",
    "next": ["the very next action", "the one after"],
    "extra": {}
  }
  ```
  Keep exactly these eight keys, so every agent reads the file the same way. `agent` is whoever wrote it last (`claude`, `codex` or you); `updated` is an ISO 8601 timestamp with time zone; anything session-specific (deliverables, rules, learnings) goes under `extra`.
- **`log.jsonl`** — append-only. One line per change: `{"ts":"...","agent":"claude","event":"correction","note":"what happened"}`. `event` is a short slug such as `correction`, `decision` or `note`.

`LATEST.txt` (in this folder) holds the name of the active session folder. Update it when you start a new task.

**That's the whole magic:** any time your Claude reopens this folder, it reads `LATEST.txt` → `state.json` → knows exactly where you left off and continues. Works across restarts, across machines, across days.
