#!/usr/bin/env python3
"""CapCut Eyes — one safe control point for watching and learning.

This never edits a CapCut project. While active it launches two local readers:

* ``sa_editwatch.py`` reads every saved CapCut timeline and records exact diffs.
* ``sa_screenwatch.py`` captures changed frames from CapCut windows only.

Each run gets its own evidence folder under ``Sessions/_eyes``. ``finish`` stops both
watchers and preserves the frames, timeline events and drafts for a Claude review pass.
Capture runs locally and uploads nothing, and frames never go to generation services; the
Claude review pass that ``finish`` hands them to is the only reader. The older fully local route (``legacy_local_finish``: a local vision join after
CapCut is closed, the durable learning, then deleting only the frames proven to have been
read) is kept for compatibility.
"""
import argparse
import datetime
import json
import os
import pathlib
import signal
import subprocess
import sys
import tempfile
import time


TOOLS = pathlib.Path(__file__).resolve().parent      # the folder this tool and its siblings live in
ROOT = TOOLS.parent
EYES = ROOT / "Sessions" / "_eyes"
ACTIVE = EYES / "ACTIVE.txt"
PY = TOOLS / "venv" / "bin" / "python3"
if not PY.exists():
    PY = pathlib.Path(sys.executable)


def now():
    return datetime.datetime.now(datetime.timezone.utc).astimezone().isoformat(
        timespec="milliseconds")


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def pid_alive(pid, expected=None):
    if not isinstance(pid, int) or pid <= 1:
        return False
    try:
        os.kill(pid, 0)
    except (ProcessLookupError, PermissionError):
        return False
    # kill(pid, 0) also succeeds for a zombie until its parent reaps it. A truthful UI
    # must never show that dead process as live.
    result = subprocess.run(["ps", "-p", str(pid), "-o", "stat=", "-o", "command="],
                            capture_output=True, text=True)
    value = result.stdout.strip()
    if result.returncode != 0 or not value:
        return False
    state, _space, command = value.partition(" ")
    return (not state.startswith("Z") and
            (expected is None or expected in command))


def capcut_open():
    return subprocess.run(["pgrep", "-x", "CapCut"], capture_output=True).returncode == 0


def active_dir(required=False):
    if ACTIVE.exists():
        sid = ACTIVE.read_text(encoding="utf-8").strip()
        path = EYES / sid
        if path.exists():
            return path
    if required:
        raise SystemExit("no active CapCut Eyes session")
    return None


def manifest(path):
    p = path / "manifest.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def save_manifest(path, data):
    data["updated_at"] = now()
    atomic_json(path / "manifest.json", data)


def counts(path):
    events = path / "timeline_events.jsonl"
    frame_index = path / "frames" / "frame_index.jsonl"
    event_n = sum(1 for x in events.read_text(encoding="utf-8").splitlines() if x.strip()) \
        if events.exists() else 0
    frame_n = sum(1 for x in frame_index.read_text(encoding="utf-8").splitlines() if x.strip()) \
        if frame_index.exists() else 0
    frame_bytes = sum(p.stat().st_size for p in (path / "frames").glob("*.png")) \
        if (path / "frames").exists() else 0
    return event_n, frame_n, frame_bytes


def session_running(data):
    pids = data.get("pids") or {}
    return any(pid_alive(v, f"sa_{k}.py") for k, v in pids.items())


def start(interval=3.0, owner_pid=None):
    EYES.mkdir(parents=True, exist_ok=True)
    existing = active_dir()
    resuming = False
    if existing:
        old = manifest(existing)
        if session_running(old):
            print_status(existing)
            return existing
        if old.get("status") not in {"learned_and_frames_purged", "learned_frames_kept"}:
            path, data, resuming = existing, old, True
            data.setdefault("resumed_at", []).append(now())
            data["status"] = "restarting"
            data["ended_at"] = None
        else:
            existing = None
    if not existing or not resuming:
        sid = datetime.datetime.now().astimezone().strftime("%Y-%m-%dT%H%M%S%z")
        path = EYES / sid
        path.mkdir(parents=True, exist_ok=False)
        data = {
            "schema": "sa-capcut-eyes-session-v1",
            "session_id": sid,
            "status": "starting",
            "started_at": now(),
            "ended_at": None,
            "timeline_scope": "all CapCut projects and all timeline draft_info.json files",
            "visual_scope": "CapCut windows only; never desktop, mail, messages, or browser",
            "data_route": ("capture runs locally and uploads nothing; frames go only to the "
                           "Claude review pass, never to generation services"),
            "project_mutation": "none; timeline reader is read-only",
            "learning_policy": "observations first; only final-surviving changes can become candidates",
            "cleanup_policy": "delete session PNGs only after checksum-backed observation coverage",
            "pids": {},
        }
    if owner_pid:
        data["visible_owner_pid"] = owner_pid
    save_manifest(path, data)
    ACTIVE.write_text(path.name + "\n", encoding="utf-8")

    edit_log = (path / "editwatch.log").open("a", encoding="utf-8")
    screen_log = (path / "screenwatch.log").open("a", encoding="utf-8")
    edit_cmd = [str(PY), "-u", str(TOOLS / "sa_editwatch.py"),
                "--interval", "1.0", "--session-dir", str(path)]
    screen_cmd = [str(PY), "-u", str(TOOLS / "sa_screenwatch.py"),
                  "--interval", str(interval), "--session-dir", str(path)]
    if owner_pid:
        edit_cmd.extend(["--owner-pid", str(owner_pid)])
        screen_cmd.extend(["--owner-pid", str(owner_pid)])
    edit = subprocess.Popen(edit_cmd, stdout=edit_log, stderr=subprocess.STDOUT,
                            start_new_session=True)
    screen = subprocess.Popen(screen_cmd, stdout=screen_log, stderr=subprocess.STDOUT,
                              start_new_session=True)
    edit_log.close()
    screen_log.close()
    data["pids"] = {"editwatch": edit.pid, "screenwatch": screen.pid}
    data["status"] = "watching_or_waiting_for_capcut"
    save_manifest(path, data)
    time.sleep(0.4)
    print_status(path)
    return path


def stop(path=None):
    path = path or active_dir(required=True)
    data = manifest(path)
    for pid in (data.get("pids") or {}).values():
        if pid_alive(pid):
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
    deadline = time.time() + 6
    while session_running(data) and time.time() < deadline:
        time.sleep(0.2)
    data["status"] = "stopped" if not session_running(data) else "stop_requested"
    data["ended_at"] = data.get("ended_at") or now()
    save_manifest(path, data)
    print_status(path)
    return path


def handoff_to_claude(path=None):
    """Stop capture and preserve every artifact for Claude's visual learning pass."""
    path = stop(path)
    data = manifest(path)
    data["status"] = "stopped_pending_claude_learning"
    data["learning_owner"] = "claude"
    data["claude_handoff_at"] = now()
    data["frame_disposition"] = "preserve until Claude confirms visual learning coverage"
    save_manifest(path, data)
    print_status(path)
    return path


def legacy_local_finish(path=None, keep_frames=False, wait_for_capcut=False):
    """Retained for forensic compatibility; normal Finish no longer calls this route."""
    path = stop(path)
    if capcut_open():
        data = manifest(path)
        data["status"] = "stopped_waiting_for_capcut_to_close_before_learning"
        save_manifest(path, data)
        if not wait_for_capcut:
            raise SystemExit("watching stopped safely. Close CapCut, then run `sa_eyes.py finish`; "
                             "the local vision pass must not slow an active edit")
        print("watching stopped; waiting for CapCut to close before local learning...")
        while capcut_open():
            time.sleep(5)
    analyse = subprocess.run([str(PY), str(TOOLS / "sa_learn.py"), "--analyse",
                              "--session-dir", str(path)])
    if analyse.returncode:
        raise SystemExit(analyse.returncode)
    if not keep_frames:
        purge = subprocess.run([str(PY), str(TOOLS / "sa_learn.py"), "--purge",
                                "--session-dir", str(path)])
        if purge.returncode:
            raise SystemExit(purge.returncode)
    data = manifest(path)
    data["status"] = "learned_frames_kept" if keep_frames else "learned_and_frames_purged"
    data["learned_at"] = now()
    save_manifest(path, data)
    if ACTIVE.exists() and ACTIVE.read_text(encoding="utf-8").strip() == path.name:
        ACTIVE.unlink()
    print_status(path)
    return path


def finish(path=None, keep_frames=False, wait_for_capcut=False):
    """Compatibility alias: Saad assigned all CapCut Eyes learning to Claude."""
    return handoff_to_claude(path)


def print_status(path=None):
    path = path or active_dir()
    if not path:
        print("CapCut Eyes: OFF")
        return
    data = manifest(path)
    e, f, b = counts(path)
    processes = {k: pid_alive(v, f"sa_{k}.py")
                 for k, v in (data.get("pids") or {}).items()}
    print(f"CapCut Eyes: {data.get('status', 'unknown')}")
    print(f"session: {path.name}")
    print(f"timeline events: {e} | CapCut frames: {f} | frame storage: {b / 1048576:.1f} MB")
    print("processes: " + ", ".join(f"{k}={'live' if v else 'stopped'}"
                                     for k, v in processes.items()))
    print(f"CapCut: {'open' if capcut_open() else 'closed or not visible to this process'}")


def _test():
    global EYES, ACTIVE
    with tempfile.TemporaryDirectory() as d:
        EYES = pathlib.Path(d) / "eyes"
        ACTIVE = EYES / "ACTIVE.txt"
        s = EYES / "s1"
        (s / "frames").mkdir(parents=True)
        ACTIVE.write_text("s1\n", encoding="utf-8")
        atomic_json(s / "manifest.json", {"pids": {}, "status": "stopped"})
        (s / "timeline_events.jsonl").write_text("{}\n{}\n", encoding="utf-8")
        (s / "frames" / "frame_index.jsonl").write_text("{}\n", encoding="utf-8")
        (s / "frames" / "x.png").write_bytes(b"1234")
        assert active_dir() == s
        assert counts(s) == (2, 1, 4)
        assert not session_running(manifest(s))
        handoff_to_claude(s)
        handed = manifest(s)
        assert handed["status"] == "stopped_pending_claude_learning"
        assert handed["learning_owner"] == "claude"
        assert (s / "frames" / "x.png").exists(), "handoff must preserve screenshots"
    print("sa_eyes self-check: ok (session isolation, evidence counts, PID state)")


def main():
    ap = argparse.ArgumentParser(description="local, read-only live eyes for CapCut")
    sub = ap.add_subparsers(dest="command", required=True)
    p = sub.add_parser("start")
    p.add_argument("--interval", type=float, default=3.0)
    p.add_argument("--owner-pid", type=int,
                   help="visible pad PID; watchers stop if this process disappears")
    sub.add_parser("status")
    sub.add_parser("stop")
    sub.add_parser("handoff", help="stop and preserve the session for Claude to learn")
    f = sub.add_parser("finish", help="stop and preserve for Claude (compatibility alias)")
    f.add_argument("--keep-frames", action="store_true")
    f.add_argument("--wait-for-capcut", action="store_true")
    sub.add_parser("test")
    a = ap.parse_args()
    if a.command == "start":
        start(a.interval, a.owner_pid)
    elif a.command == "status":
        print_status()
    elif a.command == "stop":
        stop()
    elif a.command == "handoff":
        handoff_to_claude()
    elif a.command == "finish":
        finish(keep_frames=a.keep_frames, wait_for_capcut=a.wait_for_capcut)
    else:
        _test()


if __name__ == "__main__":
    main()
