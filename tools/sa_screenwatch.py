#!/usr/bin/env python3
"""sa_screenwatch — capture the CapCut window while Saad edits, to learn HOW he works.

Goal (7 Aug 2026): see how Saad uses the tools to fix things in the moment, not only what
changed in the project file, so the assistant can do it better too.

sa_editwatch reads the project file and tells you WHAT changed — the box moved 74 up. It
cannot tell you HOW: which panel he opened, whether he nudged with the keyboard or dragged,
which menu he went through, how long he hesitated. That is on the screen, so this watches the
screen.

Scoped on purpose: it captures the CapCut window ONLY, never the whole desktop, so his mail,
messages and everything else stay out of it. Frames are written to this Mac, and the
local --analyse pass uploads nothing. The optional Claude review pass that sa_eyes.py sets
up is the only route off the machine, and frames never go to a generation service.

    Tools/venv/bin/python3 Tools/sa_screenwatch.py                 # capture while he edits
    Tools/venv/bin/python3 Tools/sa_screenwatch.py --analyse       # overnight: what happened
    Tools/venv/bin/python3 Tools/sa_screenwatch.py --test

NEEDS ONE PERMISSION, once: System Settings -> Privacy & Security -> Screen & System Audio
Recording -> turn on Claude. Without it macOS returns "could not create image from display"
and this refuses to run rather than silently writing black frames.

Capture is cheap (a PNG every few seconds, no CPU). The vision pass in --analyse is not, so
it belongs in the 1-6am window like every other Ollama batch.
"""
import argparse
import datetime
import hashlib
import json
import os
import pathlib
import signal
import subprocess
import sys
import time

OUT = pathlib.Path(os.environ.get("TRAINING_ROOT", "~/Downloads/training-series")).expanduser() / "5 ADMIN" / "_screenwatch"
MIN_GAP = 3.0                # a frame every few seconds is plenty to follow a hand at work
NEAR_SAME = 6                # ignore frames whose thumbprint barely moved (idle screen)
MAX_WINDOWS = 2              # the two document windows — one per screen when he uses both


def capcut_windows():
    """-> [(window id, w, h)] for every substantial CapCut window, biggest first.

    ALL of them, not just the largest. Saad works across two screens — the timeline on one,
    the preview on the other — and capturing only the biggest window recorded one screen and
    silently missed the other (7 Aug). Whichever one he is looking at, it gets captured.

    Lists off-screen windows too: when he switches to another app CapCut drops out of the
    on-screen list, and the first version of this quit on the spot. macOS still captures a
    window that is behind something else.
    """
    from Quartz import (CGWindowListCopyWindowInfo, kCGWindowListOptionAll, kCGNullWindowID)
    found = []
    # Quartz can return None when the caller lacks current WindowServer permission.
    # Treat that as "no visible CapCut window"; the capture probe will give the user the
    # precise permission message once a window becomes available.
    for w in (CGWindowListCopyWindowInfo(kCGWindowListOptionAll, kCGNullWindowID) or []):
        if "capcut" not in (w.get("kCGWindowOwnerName") or "").lower():
            continue
        b = w.get("kCGWindowBounds") or {}
        ww, hh = int(b.get("Width", 0)), int(b.get("Height", 0))
        if ww * hh > 300_000:
            # 24 Sep: an untitled, never-shown CapCut surface (1728x1059, flat grey) outranked the
            # real main window on the laptop, so the TIMELINE went unrecorded. Named windows
            # ("CapCut" = timeline, "player") first, then on-screen, then size.
            named = bool((w.get("kCGWindowName") or "").strip())
            shown = bool(w.get("kCGWindowIsOnscreen"))
            found.append(((named, shown, ww * hh), w.get("kCGWindowNumber"), ww, hh))
    # Two, not seven. CapCut also reports panels, overlays and toolbars above the size
    # floor; the two best-ranked are the document windows, one per screen when he has both up.
    return [(i, w, h) for _a, i, w, h in sorted(found, reverse=True)[:MAX_WINDOWS]]


def capcut_window():
    """The main window, for callers that only want one."""
    ws = capcut_windows()
    return ws[0] if ws else None


def _owner_alive(pid):
    if not pid:
        return True
    try:
        os.kill(int(pid), 0)
        return True
    except (OSError, ValueError):
        return False


def wait_for_capcut(poll=5.0, owner_pid=None):
    """Block until CapCut has a real window. Runs all day; never exits because he
    alt-tabbed away or had not opened the project yet."""
    said = False
    while True:
        if not _owner_alive(owner_pid):
            raise SystemExit("owner pad closed; stopping visual observation")
        win = capcut_window()
        if win:
            return win
        if not said:
            print("waiting for CapCut...")
            said = True
        time.sleep(poll)


def grab(win_id, path, why=None):
    """-> True if a real image landed.

    `screencapture` REFUSES ANY FILENAME BEGINNING WITH A DOT — it exits 0 and writes
    nothing, saying only "cannot write file to intended destination". The probe here was
    called ".probe.png" and the failure was misread as a missing Screen Recording
    permission for an hour (7 Aug). Never hand it a hidden filename, and always read stderr
    before blaming permissions.
    """
    if path.name.startswith("."):
        raise ValueError(f"screencapture cannot write a hidden file: {path.name}")
    r = subprocess.run(["screencapture", "-x", "-o", f"-l{win_id}", str(path)],
                       capture_output=True, text=True)
    if why is not None and r.stderr.strip():
        why.append(r.stderr.strip())
    return path.exists() and path.stat().st_size > 4000


def thumbprint(path):
    """Tiny greyscale fingerprint, so an idle screen does not fill the disk."""
    from PIL import Image
    im = Image.open(path).convert("L").resize((16, 16))
    px = list(im.getdata())
    avg = sum(px) / len(px)
    return "".join("1" if p > avg else "0" for p in px)


def drift(a, b):
    """How many of the 256 cells changed. Pure, so the noise floor is testable."""
    return sum(1 for x, y in zip(a, b) if x != y)


def watch(interval=MIN_GAP, limit=None, owner_pid=None):
    wait_for_capcut(owner_pid=owner_pid)
    OUT.mkdir(parents=True, exist_ok=True)
    wins = capcut_windows()
    probe, why = OUT / "probe_check.png", []
    if not grab(wins[0][0], probe, why):
        raise SystemExit(
            "the capture produced nothing.\n"
            + (f"  screencapture said: {why[0]}\n" if why else "")
            + "  If that mentions permission: System Settings -> Privacy & Security ->\n"
              "  Screen & System Audio Recording -> turn on Claude, then restart Claude.\n"
            "Refusing to run rather than fill a folder with black frames.")
    probe.unlink(missing_ok=True)
    print(f"capturing {len(wins)} CapCut window(s), "
          f"{', '.join(f'{w}x{h}' for _i, w, h in wins)}; ctrl-C to stop\n-> {OUT}")

    index, last, kept = [], {}, 0
    index_log = OUT / "frame_index.jsonl"
    stopping = False

    def _stop(_signum, _frame):
        nonlocal stopping
        stopping = True

    old_term = signal.signal(signal.SIGTERM, _stop)
    old_int = signal.signal(signal.SIGINT, _stop)
    try:
        while (limit is None or kept < limit) and not stopping:
            if not _owner_alive(owner_pid):
                print("owner pad closed; stopping visual observation")
                break
            stamp = datetime.datetime.now(datetime.timezone.utc).astimezone()
            wins = capcut_windows()
            if not wins:
                # Do not enter the separate blocking waiter here: SIGTERM must be able
                # to finish an already-started observation session after CapCut closes.
                time.sleep(min(5.0, interval))
                continue
            for n, (wid, _w, _h) in enumerate(wins):
                p = OUT / f"{stamp:%Y%m%dT%H%M%S_%f}_w{n}_{wid}.png"
                if not grab(wid, p):
                    p.unlink(missing_ok=True)
                    continue
                tp = thumbprint(p)
                if last.get(n) and drift(last[n], tp) < NEAR_SAME:
                    p.unlink(missing_ok=True)         # nothing moved on this one, drop it
                else:
                    entry = {"schema": "sa-capcut-eyes-frame-v1",
                             "file": p.name, "window": n, "window_id": wid,
                             "width": _w, "height": _h,
                             "at": stamp.isoformat(timespec="milliseconds"),
                             "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                             "bytes": p.stat().st_size,
                             "scope": "capcut_window_only",
                             "upload_allowed": False}
                    index.append(entry)
                    # Crash-safe: each kept frame is indexed immediately, not only when
                    # the watcher exits. A killed process must not leave unowned pixels.
                    with index_log.open("a", encoding="utf-8") as f:
                        f.write(json.dumps(entry) + "\n")
                    kept += 1
                    last[n] = tp
            time.sleep(interval)
    except KeyboardInterrupt:
        pass
    finally:
        signal.signal(signal.SIGTERM, old_term)
        signal.signal(signal.SIGINT, old_int)
    (OUT / "index.json").write_text(json.dumps(index, indent=1), encoding="utf-8")
    print(f"\n{kept} frame(s) kept -> {OUT}")
    return kept


ANALYSE_PROMPT = """This is a screenshot of the CapCut video editor, taken while an editor works.

Reply with strict JSON, no prose:
{"panel": "which part of CapCut is in focus - timeline, preview, text panel, effects, export dialog, media library, or other",
 "doing": "what the editor appears to be doing right now, in a few words",
 "selected": "what is selected or being edited, if you can read a label, else empty string",
 "notable": "anything a person learning this editor's habits should notice, else empty string"}"""


def analyse(model=None):
    """Pair the captured frames with the edits sa_editwatch recorded at the same minute."""
    sys.path.insert(0, str(pathlib.Path(__file__).parent))
    import sa_boxcheck
    if model:
        sa_boxcheck.VLM = model
    idx = json.loads((OUT / "index.json").read_text(encoding="utf-8"))
    log = OUT.parent / "EDIT_WATCH.md"
    edits = log.read_text(encoding="utf-8") if log.exists() else ""
    rows = []
    for e in idx:
        p = OUT / e["file"]
        if not p.exists():
            continue
        r = sa_boxcheck.ask(str(p), ANALYSE_PROMPT) or {}
        minute = e["at"][11:16]
        rows.append({"at": e["at"], "panel": r.get("panel", ""), "doing": r.get("doing", ""),
                     "selected": r.get("selected", ""), "notable": r.get("notable", ""),
                     "file_change": minute in edits})
        print(f"  {e['at'][11:]}  {r.get('panel',''):18s} {r.get('doing','')[:52]}")
    out = OUT / "analysis.json"
    out.write_text(json.dumps(rows, indent=1), encoding="utf-8")
    print(f"\n{len(rows)} frame(s) read -> {out}")
    return rows


def _test():
    a = "0" * 256
    assert drift(a, a) == 0, "an unchanged screen has zero drift"
    b = "1" * 8 + "0" * 248
    assert drift(a, b) == 8
    assert drift(a, b) >= NEAR_SAME, "a real edit must clear the noise floor"
    assert drift(a, "1" * 3 + "0" * 253) < NEAR_SAME, \
        "a cursor blink must not be kept as a new frame"
    print("sa_screenwatch self-check: ok (drift, noise floor)")


if __name__ == "__main__":
    if "--test" in sys.argv:
        _test()
        sys.exit()
    ap = argparse.ArgumentParser()
    ap.add_argument("--interval", type=float, default=MIN_GAP)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--analyse", action="store_true", help="read the captured frames (heavy)")
    ap.add_argument("--model", help="override the vision model")
    ap.add_argument("--session-dir", help="eyes session; frames are stored below it")
    ap.add_argument("--owner-pid", type=int,
                    help="stop automatically if the visible control pad closes")
    a = ap.parse_args()
    if a.session_dir:
        OUT = pathlib.Path(a.session_dir).expanduser().resolve() / "frames"
    analyse(a.model) if a.analyse else watch(a.interval, a.limit, a.owner_pid)
