# Your before-and-after

`baseline.json` — how long your regular jobs took you before, captured during setup.
`log.jsonl`    — one line per job finished since.

Ask for the report any time:

    python3 Tools/progress.py report

It only counts jobs that were logged and that have a "before" time. Anything else is left
out of the totals on purpose — a number that flatters you is worse than no number, because
you would make decisions on it. The real saving is always at least what it shows.
