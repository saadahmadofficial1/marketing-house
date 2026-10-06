#!/usr/bin/env python3
"""progress — proof that this is actually saving you time.

Set up on day one, add a line whenever you finish something, and in three months you can
answer "has this helped?" with hours rather than a feeling.

    python3 Tools/progress.py baseline --set "weekly report=60" --set "photo edit=15"
    python3 Tools/progress.py baseline          # same thing, asking question by question
    python3 Tools/progress.py did "weekly report" 25
    python3 Tools/progress.py report            # the after picture, any time

It only counts what you log. It says so in the report, out loud, because a number that
flatters you is worse than no number — you would make decisions on it.
"""
import json
import pathlib
import statistics
import sys
from datetime import datetime, timedelta

ROOT = pathlib.Path(__file__).resolve().parents[1]
DIR = ROOT / "progress"
BASE = DIR / "baseline.json"
LOG = DIR / "log.jsonl"


def load_log():
    if not LOG.exists():
        return []
    out = []
    for line in LOG.read_text().splitlines():
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return out


def saved(entries, baseline):
    """Pure: entries + baseline -> (minutes saved, counted, uncounted).

    A task with no 'before' time in the baseline is NOT counted as a saving. Guessing
    there is how these numbers turn into fiction."""
    before = {k.lower(): v for k, v in baseline.get("tasks", {}).items()}
    total, counted, uncounted = 0, 0, 0
    for e in entries:
        b = before.get((e.get("task") or "").lower())
        if not b:
            uncounted += 1
            continue
        gain = b - e.get("minutes", 0)
        total += gain
        counted += 1
    return total, counted, uncounted


def merge_baseline(tasks):
    """Pure-ish: add/overwrite task timings, keeping the ORIGINAL start date.
    A second run must never wipe the first — the start date is what every later
    'per week' figure is measured from."""
    DIR.mkdir(exist_ok=True)
    old = json.loads(BASE.read_text()) if BASE.exists() else {}
    merged = dict(old.get("tasks", {}))
    merged.update(tasks)
    data = {"started": old.get("started", datetime.now().strftime("%Y-%m-%d")),
            "tasks": merged}
    BASE.write_text(json.dumps(data, indent=1))
    return data


def cmd_set(pairs):
    """The assistant's entry point: no terminal needed. --set "task=minutes"."""
    tasks = {}
    for pair in pairs:
        if "=" not in pair:
            print(f"skipped {pair!r} — expected \"task name=minutes\"")
            continue
        name, mins = pair.rsplit("=", 1)
        try:
            tasks[name.strip()] = float(mins)
        except ValueError:
            print(f"skipped {pair!r} — {mins!r} is not a number")
    if not tasks:
        print("nothing to record")
        return
    data = merge_baseline(tasks)
    print(f"Before-times recorded ({len(data['tasks'])} task(s), started {data['started']}):")
    for k, v in data["tasks"].items():
        print(f"  {k}: {v:g} min")


def cmd_baseline():
    DIR.mkdir(exist_ok=True)
    if not sys.stdin.isatty():
        # Claude Code's shell has no terminal attached; asking questions here would die
        # with EOFError and write nothing at all — which is exactly how the promised
        # measurement silently never happens.
        print("This asks questions, so it needs a real terminal.\n"
              "Assistant: ask the timings in conversation, then record them with\n"
              '  python3 Tools/progress.py baseline --set "weekly report=60" --set "photo edit=15"')
        return
    print("The before picture. Name the jobs you do regularly and how long each takes you\n"
          "TODAY, without AI help. Be honest and generous — a made-up 'before' makes every\n"
          "later number meaningless. Blank line to finish.\n")
    tasks = {}
    while True:
        name = input("  task name (blank to finish): ").strip()
        if not name:
            break
        try:
            mins = float(input(f"  minutes it takes you now, per '{name}': ").strip())
        except ValueError:
            print("  needs a number — skipped")
            continue
        tasks[name] = mins
        print()
    data = merge_baseline(tasks)
    print(f"Saved {len(data['tasks'])} tasks to {BASE.relative_to(ROOT)}.\n"
          f"From now on: python3 Tools/progress.py did \"<task name>\" <minutes it took>")


def cmd_did(task, minutes):
    DIR.mkdir(exist_ok=True)
    with LOG.open("a") as f:
        f.write(json.dumps({"at": datetime.now().strftime("%Y-%m-%dT%H:%M"),
                            "task": task, "minutes": float(minutes)}) + "\n")
    base = json.loads(BASE.read_text()) if BASE.exists() else {"tasks": {}}
    b = {k.lower(): v for k, v in base.get("tasks", {}).items()}.get(task.lower())
    if b:
        print(f"logged: {task} in {minutes} min (was {b:g}) — {b - float(minutes):+.0f} min")
    else:
        print(f"logged: {task} in {minutes} min — no 'before' time recorded for this task, "
              f"so it will not count towards hours saved. Add one in the baseline if you want it to.")


def cmd_report():
    if not BASE.exists():
        print("No baseline yet — run: python3 Tools/progress.py baseline")
        return
    base = json.loads(BASE.read_text())
    entries = load_log()
    if not entries:
        print("Nothing logged yet. Log a finished job with:\n"
              "  python3 Tools/progress.py did \"weekly report\" 25")
        return
    mins, counted, uncounted = saved(entries, base)
    start = datetime.strptime(base.get("started", entries[0]["at"][:10]), "%Y-%m-%d")
    weeks = max(1, (datetime.now() - start).days / 7)
    recent = [e for e in entries
              if datetime.strptime(e["at"][:10], "%Y-%m-%d") > datetime.now() - timedelta(days=30)]
    r_mins, _, _ = saved(recent, base)
    print("\n  AI workspace system — designed by Saad Ahmad, code written by AI agents")
    print(f"\n  Since {start:%d %b %Y} — {int(weeks)} weeks\n")
    print(f"  Jobs logged            {len(entries)}")
    print(f"  Time saved (total)     {mins/60:.1f} hours")
    print(f"  Time saved (30 days)   {r_mins/60:.1f} hours")
    print(f"  Per week, on average   {mins/60/weeks:.1f} hours")
    by = {}
    for e in entries:
        by.setdefault(e["task"].lower(), []).append(e.get("minutes", 0))
    before = {k.lower(): v for k, v in base.get("tasks", {}).items()}
    rows = []
    for task, times in by.items():
        b = before.get(task)
        if not b:
            continue
        now = statistics.median(times)
        rows.append((b - now, task, b, now, len(times)))
    if rows:
        print("\n  Where the time went\n")
        print(f"  {'task':26s} {'before':>7s} {'now':>7s} {'done':>5s} {'saved each':>11s}")
        for gain, task, b, now, n in sorted(rows, reverse=True):
            print(f"  {task[:26]:26s} {b:6.0f}m {now:6.0f}m {n:5d} {gain:10.0f}m")
    if uncounted:
        print(f"\n  {uncounted} logged job(s) had no 'before' time and are NOT in these totals.")
    print("\n  This counts only what you logged. Anything you did not log is missing from it —\n"
          "  the real saving is almost certainly larger, and this number is the floor.\n")


def _test():
    base = {"tasks": {"weekly report": 60, "photo edit": 30}}
    entries = [{"task": "weekly report", "minutes": 20},
               {"task": "Photo Edit", "minutes": 10},
               {"task": "something new", "minutes": 5}]
    mins, counted, uncounted = saved(entries, base)
    assert mins == 60, mins                       # 40 + 20, the unknown task contributes 0
    assert counted == 2 and uncounted == 1, "a task with no baseline must never be counted"
    assert saved([], base) == (0, 0, 0)
    # a job that took LONGER than before must reduce the total, not be ignored
    worse, _, _ = saved([{"task": "weekly report", "minutes": 90}], base)
    assert worse == -30, worse
    # a second baseline run must not wipe the first
    import tempfile, shutil
    global DIR, BASE
    keep_dir, keep_base = DIR, BASE
    DIR = pathlib.Path(tempfile.mkdtemp()); BASE = DIR / "baseline.json"
    merge_baseline({"a": 10})
    first_start = json.loads(BASE.read_text())["started"]
    merge_baseline({"b": 20})
    d2 = json.loads(BASE.read_text())
    assert set(d2["tasks"]) == {"a", "b"}, "a second run must merge, never replace"
    assert d2["started"] == first_start, "the original start date must survive"
    shutil.rmtree(DIR, ignore_errors=True)
    DIR, BASE = keep_dir, keep_base
    print("progress self-check: ok (unknown tasks excluded, case-insensitive, losses count, "
          "baseline merges)")


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] in ("-h", "--help"):
        print(__doc__)
    elif a[0] == "--test":
        _test()
    elif a[0] == "baseline":
        sets = [a[i + 1] for i, x in enumerate(a) if x == "--set" and i + 1 < len(a)]
        cmd_set(sets) if sets else cmd_baseline()
    elif a[0] == "did" and len(a) >= 3:
        cmd_did(a[1], a[2])
    elif a[0] == "report":
        cmd_report()
    else:
        print(__doc__)
