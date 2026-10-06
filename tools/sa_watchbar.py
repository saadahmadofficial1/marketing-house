#!/usr/bin/env python3
"""sa_watchbar — a light in Saad's menu bar so he can see he is being watched.

Requirement (7 Aug 2026): a visible on-screen sign, such as a menu-bar icon or an orange
indicator, whenever the watchers are running.

Fair. Two background processes quietly reading his project and his screen, with nothing on
screen to show for it, is not something anyone should have to take on trust. This puts a live
indicator in the menu bar and lets him switch the whole thing off with one click.

    🔴 12 · 47      recording — 12 edits noticed, 47 screenshots taken
    ⚪️ idle          CapCut is closed, nothing is being captured
    ⏸ paused        he turned it off

    Tools/venv/bin/python3 Tools/sa_watchbar.py
    Tools/venv/bin/python3 Tools/sa_watchbar.py --test

The counters are read off the real outputs — the edit log and the frame folder — so the
number in the menu bar is the number of things actually written to disk, not a claim.
Stop from the menu and both watchers really do stop; it does not just hide the icon.
"""
import argparse
import json
import os
import pathlib
import re
import subprocess
import sys

TOOLS = pathlib.Path(__file__).resolve().parent
ROOT = TOOLS.parent
EYES_TOOL = TOOLS / "sa_eyes.py"
EYES_ROOT = ROOT / "Sessions" / "_eyes"
ACTIVE = EYES_ROOT / "ACTIVE.txt"
PY = TOOLS / "venv" / "bin" / "python3"
if not PY.exists():
    PY = pathlib.Path(sys.executable)


def running(name):
    return subprocess.run(["pgrep", "-f", name], capture_output=True).returncode == 0


def counts():
    """-> (edits, frames, capcut open). Read from disk, never remembered.

    edits and frames come back as None when the folder cannot be read — they are the
    nice-to-have, and they must never take the state down with them.

    12 Aug: macOS blocks this app from reading ~/Downloads unless it has been granted
    access. The PermissionError raised here escaped through title() into the rumps timer,
    the timer died, and the menu bar froze on the last thing it drew — the word "paused" —
    while both watchers were in fact running. Saad reasonably reported the pause button as
    broken. A frozen indicator is worse than an ugly one: it reports a state that was true
    once and presents it as now.
    """
    edits = frames = None
    path = current_session()
    log = path / "timeline_events.jsonl" if path else None
    frame_index = path / "frames" / "frame_index.jsonl" if path else None
    try:
        edits = sum(1 for x in log.read_text(encoding="utf-8").splitlines() if x.strip()) \
            if log and log.exists() else 0
    except OSError:
        pass
    try:
        frames = sum(1 for x in frame_index.read_text(encoding="utf-8").splitlines()
                     if x.strip()) if frame_index and frame_index.exists() else 0
    except OSError:
        pass
    return edits, frames, running("^CapCut$")


def current_session():
    try:
        sid = ACTIVE.read_text(encoding="utf-8").strip()
        path = EYES_ROOT / sid
        return path if path.exists() else None
    except OSError:
        return None


def current_status():
    path = current_session()
    try:
        return json.loads((path / "manifest.json").read_text(encoding="utf-8")).get("status") \
            if path else None
    except (OSError, json.JSONDecodeError):
        return None


def title(paused=False):
    """The menu-bar string. Pure, so the states are testable without a menu bar.

    Orange while it is actually recording, as requested. The first version used a white
    dot when idle that he could not pick out of the icon cluster on his second screen.
    The eye says "watching but nothing to capture".
    """
    if paused:
        return "⏸ paused"
    edits, frames, capcut = counts()
    edit_live = running("sa_editwatch")
    screen_live = running("sa_screenwatch")
    if not (edit_live or screen_live):
        return "⚠️ OFF"
    # "?" means watching is live but the counters cannot be read — the state is still true
    e = "?" if edits is None else edits
    if not capcut:
        return f"👁 {e}"
    if edit_live and screen_live:
        return f"🟠 REC {e}·{'?' if frames is None else frames}"
    return f"🟡 {'LOG' if edit_live else 'PIC'} {e}·{'?' if frames is None else frames}"


def start():
    subprocess.run([str(PY), str(EYES_TOOL), "start", "--owner-pid", str(os.getpid())],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def stop():
    subprocess.run([str(PY), str(EYES_TOOL), "stop"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main():
    import rumps

    class Bar(rumps.App):
        def __init__(self):
            super().__init__("⚪️", quit_button=None)
            # A completed recording waiting for Claude must stay stopped across menu-bar
            # restarts. Resume remains an explicit click by Saad.
            self.paused = current_status() == "stopped_pending_claude_learning"
            self.toggle_item = rumps.MenuItem(
                "Resume watching" if self.paused else "Pause watching", callback=self.toggle)
            self.menu = ["What this is watching", None,
                         self.toggle_item,
                         rumps.MenuItem("Open the edit log", callback=self.open_log),
                         rumps.MenuItem("Open the screenshots", callback=self.open_frames),
                         rumps.MenuItem("Finish recording for Claude to learn",
                                        callback=self.finish_for_claude),
                         None, rumps.MenuItem("Quit", callback=self.bye)]
            self.menu["What this is watching"].set_callback(None)
            if not self.paused:
                start()

        @rumps.timer(3)
        def tick(self, _):
            try:
                self.title = title(self.paused)
                edits, frames, capcut = counts()
                line = (f"{'?' if edits is None else edits} edits · "
                        f"{'?' if frames is None else frames} screenshots · "
                        f"CapCut {'open' if capcut else 'closed'}")
                if edits is None or frames is None:
                    line += "  — cannot read the training folder, counts unavailable"
                self.menu["What this is watching"].title = line
            except Exception as exc:
                # Never leave the last title standing: it would be read as current.
                self.title = "⚠️ error"
                self.menu["What this is watching"].title = f"error: {type(exc).__name__}"

        def toggle(self, sender):
            self.paused = not self.paused
            if self.paused:
                stop()
                sender.title = "Resume watching"
            else:
                # Label first. If start() raises, the menu must not still read "Resume
                # watching" while self.paused is already False — that mismatch is how the
                # 12 Aug fault looked from the outside.
                sender.title = "Pause watching"
                start()

        def open_log(self, _):
            path = current_session()
            if path:
                log = path / "timeline_changes.md"
                subprocess.run(["open", "-R", str(log)] if log.exists() else
                               ["open", str(path)])

        def open_frames(self, _):
            path = current_session()
            if path:
                frames = path / "frames"
                frames.mkdir(parents=True, exist_ok=True)
                subprocess.run(["open", str(frames)])

        def finish_for_claude(self, _):
            self.paused = True
            self.toggle_item.title = "Resume watching"
            path = current_session()
            if not path:
                rumps.notification("CapCut Eyes", "Nothing to finish", "No active session")
                return
            out = (path / "finish.log").open("a", encoding="utf-8")
            subprocess.run([str(PY), str(EYES_TOOL), "handoff"], stdout=out,
                           stderr=subprocess.STDOUT)
            out.close()
            rumps.notification("CapCut Eyes", "Recording finished",
                               "Evidence is preserved for Claude. Nothing was deleted.")

        def bye(self, _):
            stop()
            rumps.quit_application()

    Bar().run()


def _test():
    assert title(paused=True) == "⏸ paused"
    e, f, c = counts()
    assert (e is None or isinstance(e, int)) and (f is None or isinstance(f, int))
    assert isinstance(c, bool)
    assert current_status() is None or isinstance(current_status(), str)

    live = title(False)
    # every state must be recognisable at a glance from the other side of the desk
    assert live.startswith(("🟠", "👁", "⚠️")), live
    assert live != title(paused=True), "paused and live must never look the same"
    assert "REC" in live or not c, "while CapCut is open it must say REC, in orange"
    print(f"sa_watchbar self-check: ok (states distinct; right now it reads \"{live}\")")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", action="store_true")
    if ap.parse_args().test:
        _test()
    else:
        main()
