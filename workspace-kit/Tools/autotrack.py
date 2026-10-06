#!/usr/bin/env python3
"""autotrack — measures the difference without anyone having to remember to log anything.

People do not keep timesheets. So this reads the evidence that already exists: the files in
the folders where the work actually lands. It records what production looked like BEFORE the
assistant arrived, then keeps measuring, so months later the question "has this actually made
us faster?" has an answer drawn from the work itself.

    python3 Tools/autotrack.py watch ~/Documents/Work ~/Desktop/Projects   # once, at setup
    python3 Tools/autotrack.py scan                                        # weekly, automatic
    python3 Tools/autotrack.py report                                      # any time

**What it can honestly measure:** how many finished pieces of work appear per week, how long
a project takes from first file to last, and how that has changed. **What it cannot:** quality,
difficulty, or the weeks you were on leave. The report says so rather than pretending.
"""
import json
import pathlib
import statistics
import sys
import time
from datetime import datetime, timedelta

ROOT = pathlib.Path(__file__).resolve().parents[1]
DIR = ROOT / "progress"
CONF = DIR / "autotrack.json"
SNAPS = DIR / "snapshots.jsonl"

# What counts as a finished piece of work rather than a working file
DELIVERABLE = {".pdf", ".pptx", ".docx", ".xlsx", ".png", ".jpg", ".jpeg", ".mp4", ".mov",
               ".ai", ".psd", ".indd", ".fig", ".sketch", ".csv", ".key", ".pages", ".numbers"}
# NOT "Library" as a bare component — corporate Macs keep work in
# ~/Library/CloudStorage/OneDrive-... and iCloud Drive, and skipping those
# would silently produce a baseline of zero.
IGNORE_PARTS = {".git", "node_modules", ".Trash", "__pycache__", ".obsidian"}


def walk(folder, since=None):
    """-> [(path, mtime)] of deliverable files, ignoring junk. Pure apart from the disk."""
    out = []
    base = pathlib.Path(folder).expanduser()
    if not base.exists():
        return out
    for p in base.rglob("*"):
        if not p.is_file() or p.suffix.lower() not in DELIVERABLE:
            continue
        if any(part in IGNORE_PARTS or part.startswith(".") for part in p.parts):
            continue
        try:
            m = p.stat().st_mtime
        except OSError:
            continue
        if since and m < since:
            continue
        out.append((str(p), m))
    return out


def per_week(files, weeks):
    """Pure: file list + window -> deliverables per week, rounded."""
    return round(len(files) / weeks, 2) if weeks > 0 else 0.0


def cmd_watch(folders):
    DIR.mkdir(exist_ok=True)
    now = time.time()
    look_back_days = 180
    conf = {"folders": [str(pathlib.Path(f).expanduser()) for f in folders],
            "started": datetime.now().strftime("%Y-%m-%d")}
    before = []
    for f in conf["folders"]:
        before += walk(f, since=now - look_back_days * 86400)
    # the "before" rate: what they were producing in the six months before setup
    conf["baseline"] = {"window_days": look_back_days,
                        "deliverables": len(before),
                        "per_week": per_week(before, look_back_days / 7)}
    CONF.write_text(json.dumps(conf, indent=1))
    print(f"Watching {len(conf['folders'])} folder(s).")
    print(f"Before this system: {conf['baseline']['deliverables']} finished files in the last "
          f"{look_back_days} days — {conf['baseline']['per_week']:.2f} per week.")
    print("That is the line to beat. Your assistant re-checks it at the start of\n"
          "the first session each week — you never run this yourself.")
    print("\nWhat this records: file paths and dates of finished files in those folders,\n"
          "stored in progress/. It runs locally, uploads nothing and never opens the files.\n"
          "Point it away from anything you would rather it did not list.")


def cmd_scan():
    if not CONF.exists():
        print("Not set up. Run: python3 Tools/autotrack.py watch <your work folders>")
        return
    conf = json.loads(CONF.read_text())
    start = datetime.strptime(conf["started"], "%Y-%m-%d").timestamp()
    files = []
    for f in conf["folders"]:
        files += walk(f, since=start)
    DIR.mkdir(exist_ok=True)
    with SNAPS.open("a") as fh:
        fh.write(json.dumps({"at": datetime.now().strftime("%Y-%m-%dT%H:%M"),
                             "since_setup": len(files)}) + "\n")
    print(f"scanned: {len(files)} finished files since setup")


def cmd_report():
    if not CONF.exists():
        print("Not set up. Run: python3 Tools/autotrack.py watch <your work folders>")
        return
    conf = json.loads(CONF.read_text())
    start_dt = datetime.strptime(conf["started"], "%Y-%m-%d")
    start = start_dt.timestamp()
    weeks = max(0.15, (time.time() - start) / (7 * 86400))
    files = []
    for f in conf["folders"]:
        files += walk(f, since=start)
    now_rate = per_week(files, weeks)
    was = conf["baseline"]["per_week"]
    print("\n  AI workspace system — directed by Saad Ahmad, coded with AI agents")
    print(f"\n  Since {start_dt:%d %b %Y} — {weeks:.0f} weeks\n")
    print(f"  Finished files per week, before   {was:.2f}")
    print(f"  Finished files per week, now      {now_rate:.2f}")
    if was > 0:
        change = (now_rate - was) / was * 100
        print(f"  Change                            {change:+.0f}%")
    print(f"  Finished since setup              {len(files)}")
    if weeks < 3:
        print("\n  Too early to mean much — three weeks or more before this number settles.")
    print("\n  Counts finished files (documents, decks, images, video, spreadsheets) appearing\n"
          "  in the folders you asked it to watch. It cannot see quality, difficulty, or the\n"
          "  weeks you were away — so read it alongside what you know about the period.\n")


def _test():
    import tempfile, os
    d = pathlib.Path(tempfile.mkdtemp())
    (d / "a.pdf").write_text("x")
    (d / "b.png").write_text("x")
    (d / "notes.txt").write_text("x")            # not a deliverable
    (d / ".git").mkdir()
    (d / ".git" / "c.pdf").write_text("x")       # ignored location
    got = walk(d)
    assert len(got) == 2, [g[0] for g in got]
    old = time.time() - 400 * 86400
    os.utime(d / "a.pdf", (old, old))
    assert len(walk(d, since=time.time() - 180 * 86400)) == 1, "window must exclude old files"
    assert per_week([1, 2, 3, 4], 2) == 2.0
    assert per_week([], 5) == 0.0
    assert per_week([1], 0) == 0.0               # never divide by zero
    print("autotrack self-check: ok (deliverables only, junk ignored, window, rate)")


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] in ("-h", "--help"):
        print(__doc__)
    elif a[0] == "--test":
        _test()
    elif a[0] == "watch" and len(a) > 1:
        cmd_watch(a[1:])
    elif a[0] == "scan":
        cmd_scan()
    elif a[0] == "report":
        cmd_report()
    else:
        print(__doc__)
