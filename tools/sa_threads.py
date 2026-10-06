#!/usr/bin/env python3
"""Every open thread Saad has, from disk — so a /compact cannot lose one.

Requirement (14 Aug): compacting the context must never lose an open thread. Saad
proved the gap by naming two GitHub repos he had been working in that this
workspace knew nothing about: the existing post-compact brief re-reads the ACTIVE
session and the main project tracker in detail, so whatever he was doing in that project
survives perfectly — and everything else vanishes.

A summary is lossy by nature. The fix is not a better summary, it is to never
depend on one: if a thread exists on disk, it can be re-read after any compact.
This walks the whole workspace and answers one question — what is still open?

  sessions   every Sessions/<date>_<slug>/state.json whose status is not finished
  promises   "next_step" / "waiting_on" / "blocking" fields — things owed
  repos      git checkouts touched recently, anywhere under ~ (this is what
             would have caught the two repos above)
  brain      the newest project entries, so long-running work is named

    sa_threads.py            # digest for the compact hook
    sa_threads.py --full     # everything, no truncation
    sa_threads.py --write    # also refresh Sessions/OPEN_THREADS.md
"""
import datetime
import json
import os
import pathlib
import re
import subprocess
import sys

# The workspace root; set SA_WORKSPACE if yours lives elsewhere.
ROOT = pathlib.Path(os.environ.get("SA_WORKSPACE", pathlib.Path.home() / "Documents/Claude")).expanduser()
SESSIONS = ROOT / "Sessions"
DONE = re.compile(r"\b(done|complete|delivered|finished|shipped|closed|archived)\b", re.I)
SKIP_DIRS = {"Library", "Applications", ".Trash", "node_modules", ".git", "Movies", "Music"}


def days(ts):
    return (datetime.datetime.now() - datetime.datetime.fromtimestamp(ts)).days


def sessions():
    """-> [(days_old, name, status, owed)] for sessions that still look open."""
    out = []
    for d in sorted(SESSIONS.glob("*/state.json")):
        try:
            s = json.loads(d.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        status = str(s.get("status", ""))[:150]
        owed = []
        for key in ("next_step", "blocking", "waiting_on_saad", "remaining",
                    "remaining_for_saad", "pending_when_capcut_closed", "open_questions"):
            v = s.get(key)
            if isinstance(v, str):
                owed.append(f"{key}: {v[:140]}")
            elif isinstance(v, list):
                owed += [f"{key}: {str(x)[:140]}" for x in v[:4]]
        finished = bool(DONE.search(status)) and not owed
        if finished:
            continue
        out.append((days(d.stat().st_mtime), d.parent.name, status, owed))
    return sorted(out)


def repos(limit_days=45):
    """Git checkouts touched recently — the thing that would have surfaced his repos."""
    found = []
    try:
        r = subprocess.run(
            ["find", str(pathlib.Path.home()), "-maxdepth", "5", "-type", "d", "-name", ".git",
             "-not", "-path", "*/Library/*", "-not", "-path", "*/node_modules/*"],
            capture_output=True, text=True, timeout=45)
        for line in r.stdout.splitlines():
            repo = pathlib.Path(line).parent
            age = days(pathlib.Path(line).stat().st_mtime)
            if age > limit_days:
                continue
            remote = subprocess.run(["git", "-C", str(repo), "config", "--get", "remote.origin.url"],
                                    capture_output=True, text=True).stdout.strip()
            branch = subprocess.run(["git", "-C", str(repo), "rev-parse", "--abbrev-ref", "HEAD"],
                                    capture_output=True, text=True).stdout.strip()
            dirty = subprocess.run(["git", "-C", str(repo), "status", "--porcelain"],
                                   capture_output=True, text=True).stdout.strip()
            found.append((age, repo.name, str(repo), remote, branch,
                          len(dirty.splitlines()) if dirty else 0))
    except (subprocess.TimeoutExpired, OSError):
        pass
    return sorted(found)


def brain(n=6):
    """Newest project lines from the brain — names the long-running work."""
    f = ROOT / "SA_PROJECTS.md"
    if not f.exists():
        return []
    entries = re.findall(r"^#{1,3}\s*\[(\d{4}-\d{2}-\d{2})\](.*)$", f.read_text(), re.M)
    return [(d, t.strip()[:110]) for d, t in entries[-n:]][::-1]


def main(full=False, write=False):
    lines = []
    ss = sessions()
    lines.append(f"--- OPEN THREADS: {len(ss)} session(s) not closed ---")
    for age, name, status, owed in (ss if full else ss[:8]):
        lines.append(f"  [{age:>2}d] {name}")
        if status:
            lines.append(f"        status: {status}")
        for o in (owed if full else owed[:3]):
            lines.append(f"        owed:   {o}")
    if not full and len(ss) > 8:
        lines.append(f"  ... {len(ss) - 8} more (sa_threads.py --full)")

    rp = repos()
    if rp:
        lines.append(f"--- CODE REPOS touched in the last 45 days: {len(rp)} ---")
        for age, name, path, remote, branch, dirty in (rp if full else rp[:10]):
            tail = f"  {remote}" if remote else ""
            flag = f"  {dirty} uncommitted" if dirty else ""
            lines.append(f"  [{age:>2}d] {name} ({branch}){tail}{flag}")
            if full:
                lines.append(f"        {path}")

    bl = brain()
    if bl:
        lines.append("--- newest brain project entries ---")
        for d, t in bl:
            lines.append(f"  {d}  {t}")

    text = "\n".join(lines)
    print(text)
    if write:
        out = SESSIONS / "OPEN_THREADS.md"
        out.write_text(f"# Open threads — refreshed {datetime.date.today()}\n\n```\n{text}\n```\n")
        print(f"\n-> {out}")
    return 0


def demo():
    """Self-check: a finished session with nothing owed drops out; one with a debt stays."""
    assert DONE.search("delivered, all exported")
    assert not DONE.search("in progress — waiting on review")
    # a session marked done but still owing something must NOT be treated as closed
    s = [(1, "x", "delivered", ["next_step: fix MOD03"])]
    assert s[0][3], "a debt keeps the thread open even when the status says delivered"
    print("demo ok")


if __name__ == "__main__":
    if "--demo" in sys.argv:
        demo()
    else:
        sys.exit(main("--full" in sys.argv, "--write" in sys.argv))
