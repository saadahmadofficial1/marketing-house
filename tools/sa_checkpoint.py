#!/usr/bin/env python3
"""Checkpoint the decisions in a long session, before the context fills.

Requirement (19 Aug 2026, Saad's idea): checkpoint decisions every ~100k tokens of
context, then combine the checkpoints. The principle holds — a summary written at
100k can see detail that a summary written at 1M has already lost. Ten honest
checkpoints beat one desperate compaction.

WHY NOT AN OFF-THE-SHELF TOOL. Three were reviewed the same day:
  claude-mem        checkpoints on lifecycle events, not context growth; has an
                    optional cloud sync to a third-party server
  claude-remember   does fire mid-session, but on TOOL OUTPUT volume, and posts
                    content to an external API to compress it
  memsearch         a retrieval index, not a checkpointer
None trigger on context growth, and two send content to a third-party server, which
the workspace data policy does not allow. Measured on this very session: 70% of
the transcript is tool output (ffmpeg logs, job ids, JSON) and only 10% is Saad's
own words. So a tool that triggers on tool-output volume checkpoints hardest on the
noise, and can sail straight past a conversation where he corrects a rule in two
plain sentences with no tool call at all. That is the opposite of what is wanted.

WHAT THIS DOES INSTEAD. It watches the session transcript on disk — its size is
a usable proxy for context consumed — and when it has grown past a threshold
since the last checkpoint, it asks for one. Nothing is summarised automatically
and nothing is sent anywhere: the request lands in context, and the assistant
writes the checkpoint itself, while the detail is still in front of it.

    sa_checkpoint.py --due          # is one due? (used by the hook)
    sa_checkpoint.py --mark         # record that one was just written
    sa_checkpoint.py --list         # checkpoints for the active session
"""
import argparse
import datetime
import json
import os
import pathlib
import sys

ROOT = pathlib.Path(os.path.expanduser(os.environ.get("WORKSPACE_ROOT", "~/Documents/Claude")))
# Claude Code stores a project's transcripts under its path with "/" turned into "-"
PROJECTS = pathlib.Path.home() / ".claude/projects" / str(ROOT).replace("/", "-")
# 84 MB of transcript covered roughly one full context plus a compact on 18 Aug,
# so ~8 MB is about a tenth of the window: one checkpoint per ~100k tokens of a 1M window.
STEP_MB = 8.0


def active_session():
    latest = ROOT / "Sessions/LATEST.txt"
    if latest.exists():
        name = latest.read_text().strip()
        if name and (ROOT / "Sessions" / name).is_dir():
            return ROOT / "Sessions" / name
    dirs = [p for p in (ROOT / "Sessions").glob("2*_*") if p.is_dir()]
    return max(dirs, key=lambda p: p.stat().st_mtime) if dirs else None


def transcript():
    """The .jsonl this session is being written to — newest wins."""
    files = list(PROJECTS.glob("*.jsonl")) if PROJECTS.is_dir() else []
    return max(files, key=lambda p: p.stat().st_mtime) if files else None


def state_path(sess):
    return sess / "checkpoints" / "_state.json"


def read_state(sess):
    p = state_path(sess)
    if p.exists():
        try:
            return json.loads(p.read_text())
        except json.JSONDecodeError:
            pass
    return {"last_mb": 0.0, "count": 0}


def due(sess, t):
    """-> (is_due, grown_mb, state). Pure enough to test."""
    st = read_state(sess)
    mb = t.stat().st_size / 1048576 if t else 0.0
    grown = mb - st.get("last_mb", 0.0)
    return grown >= STEP_MB, grown, st


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--due", action="store_true")
    ap.add_argument("--mark", action="store_true")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()

    sess, t = active_session(), transcript()
    if sess is None or t is None:
        return 0

    if a.list:
        d = sess / "checkpoints"
        for f in sorted(d.glob("[0-9]*.md")) if d.is_dir() else []:
            first = f.read_text().splitlines()[0] if f.stat().st_size else ""
            print(f"  {f.name}  {first[:90]}")
        return 0

    if a.mark:
        d = sess / "checkpoints"
        d.mkdir(parents=True, exist_ok=True)
        st = read_state(sess)
        st["last_mb"] = t.stat().st_size / 1048576
        st["count"] = st.get("count", 0) + 1
        st["marked"] = datetime.datetime.now().isoformat(timespec="seconds")
        state_path(sess).write_text(json.dumps(st, indent=1))
        print(f"checkpoint {st['count']} marked at {st['last_mb']:.1f} MB")
        return 0

    if a.due:
        is_due, grown, st = due(sess, t)
        if not is_due:
            return 0
        n = st.get("count", 0) + 1
        print(f"""
[CHECKPOINT DUE — {grown:.0f} MB of transcript since the last one]
Write {sess.name}/checkpoints/{n:02d}.md now, while the detail is still in context.
Capture ONLY what would be lost in a compaction — not a narrative of the session:
  · decisions Saad made, and any rule or preference he stated
  · corrections to me, and what the correct behaviour is
  · things measured, with their numbers
  · what was delivered, and what is still owed to him
Skip tool output, file listings and anything re-readable from disk.
Then run: Tools/venv/bin/python3 Tools/sa_checkpoint.py --mark
Also log anything durable to sa-brain — a checkpoint is for this session, the
brain is forever.""")
    return 0


def demo():
    """The trigger arithmetic, without touching any real session."""
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        sess = pathlib.Path(d) / "2026-08-19_test"
        (sess / "checkpoints").mkdir(parents=True)
        t = pathlib.Path(d) / "t.jsonl"
        t.write_bytes(b"x" * int(3 * 1048576))
        assert due(sess, t)[0] is False, "3 MB is not yet a checkpoint"
        t.write_bytes(b"x" * int(9 * 1048576))
        ok, grown, _ = due(sess, t)
        assert ok and 8.9 < grown < 9.1, f"9 MB should be due, got {grown}"
        # after marking at 9 MB, another 8 must accumulate before the next one
        state_path(sess).write_text(json.dumps({"last_mb": 9.0, "count": 1}))
        assert due(sess, t)[0] is False, "must not re-fire immediately after a mark"
        t.write_bytes(b"x" * int(18 * 1048576))
        assert due(sess, t)[0] is True, "another 9 MB should be due again"
    print("demo ok — fires every ~8 MB, never twice for the same growth")


if __name__ == "__main__":
    sys.exit(demo() if "--demo" in sys.argv else main())
