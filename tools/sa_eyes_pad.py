#!/usr/bin/env python3
"""Small movable, always-on-top control pad for CapCut Live Eyes.

The pad is intentionally separate from the menu bar. Drag its header anywhere, including
another monitor. It reports the watcher processes and real evidence counts, then delegates
all lifecycle work to sa_eyes.py.
"""
import argparse
import glob
import json
import os
import pathlib
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import font as tkfont

import sa_eyes


ROOT = pathlib.Path(__file__).resolve().parents[1]
CAPCUT = pathlib.Path("~/Movies/CapCut/User Data/Projects/com.lveditor.draft").expanduser()
PY = pathlib.Path(__file__).resolve().parent / "venv" / "bin" / "python3"
if not PY.exists():
    PY = pathlib.Path(sys.executable)
EYES_TOOL = pathlib.Path(__file__).resolve().parent / "sa_eyes.py"
POSITION = ROOT / "Sessions" / "_eyes" / "pad_position.json"
PAD_PID = ROOT / "Sessions" / "_eyes" / "pad.pid"

BG = "#111613"
SURFACE = "#1a211d"
TEXT = "#f3f7f4"
MUTED = "#93a29a"
GREEN = "#20b568"
ORANGE = "#f59e0b"
YELLOW = "#eab308"
PURPLE = "#7656d6"
BORDER = "#2d3932"


def current_project():
    best, when = None, 0.0
    patterns = [str(CAPCUT / "*/draft_info.json"),
                str(CAPCUT / "*/Timelines/*/draft_info.json")]
    for pattern in patterns:
        for value in glob.glob(pattern):
            try:
                modified = os.path.getmtime(value)
            except OSError:
                continue
            if modified > when:
                when, best = modified, value
    return pathlib.Path(best).relative_to(CAPCUT).parts[0] if best else "No project yet"


def position():
    try:
        data = json.loads(POSITION.read_text(encoding="utf-8"))
        return int(data["x"]), int(data["y"])
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        return 56, 96


def geometry_position(x, y):
    """Tk geometry coordinates that also work on monitors left/above the main display."""
    return f"{int(x):+d}{int(y):+d}"


def claim_single_instance():
    PAD_PID.parent.mkdir(parents=True, exist_ok=True)
    try:
        prior = int(PAD_PID.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        prior = 0
    if prior and prior != os.getpid() and sa_eyes.pid_alive(prior, "sa_eyes_pad.py"):
        raise SystemExit("CapCut Eyes pad is already open")
    PAD_PID.write_text(str(os.getpid()) + "\n", encoding="utf-8")


def snapshot():
    path = sa_eyes.active_dir()
    if not path:
        return {"state": "off", "title": "Eyes paused", "detail": "Ready when you are",
                "color": MUTED, "events": 0, "frames": 0, "path": None}
    data = sa_eyes.manifest(path)
    events, frames, _bytes = sa_eyes.counts(path)
    pids = data.get("pids") or {}
    edit_live = sa_eyes.pid_alive(pids.get("editwatch"), "sa_editwatch.py")
    screen_live = sa_eyes.pid_alive(pids.get("screenwatch"), "sa_screenwatch.py")
    status = data.get("status", "")
    if status == "stopped_pending_claude_learning":
        return {"state": "claude_wait", "title": "Ready for Claude",
                "detail": "Recording stopped; evidence preserved", "color": PURPLE,
                "events": events, "frames": frames, "path": path}
    if "waiting_for_capcut" in status:
        return {"state": "learning_wait", "title": "Waiting to learn",
                "detail": "Close CapCut; learning starts automatically", "color": PURPLE,
                "events": events, "frames": frames, "path": path}
    if status.startswith("learned"):
        return {"state": "learned", "title": "Learning saved",
                "detail": "Screenshots cleaned after verification", "color": GREEN,
                "events": events, "frames": frames, "path": path}
    if edit_live and screen_live:
        capcut = sa_eyes.capcut_open()
        return {"state": "live", "title": "Eyes live" if capcut else "Eyes ready",
                "detail": "Timeline + CapCut window" if capcut else "Waiting for CapCut",
                "color": ORANGE if capcut else GREEN,
                "events": events, "frames": frames, "path": path}
    if edit_live or screen_live:
        working = "Timeline only" if edit_live else "Picture only"
        missing = "picture unavailable" if edit_live else "timeline unavailable"
        return {"state": "degraded", "title": working,
                "detail": f"Degraded · {missing}", "color": YELLOW,
                "events": events, "frames": frames, "path": path}
    return {"state": "paused", "title": "Eyes paused", "detail": "Session kept safely",
            "color": MUTED, "events": events, "frames": frames, "path": path}


class EyesPad:
    def __init__(self, root):
        self.root = root
        self.busy = False
        self.drag_x = self.drag_y = 0
        self.compact = False
        root.title("CapCut Eyes")
        root.configure(bg=BG)
        x, y = position()
        root.geometry(f"306x176{geometry_position(x, y)}")
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        root.protocol("WM_DELETE_WINDOW", self.close)
        try:
            root.attributes("-alpha", 0.97)
        except tk.TclError:
            pass

        ui = tkfont.Font(family="SF Pro Text", size=11)
        strong = tkfont.Font(family="SF Pro Display", size=12, weight="bold")
        tiny = tkfont.Font(family="SF Pro Text", size=9)

        self.header = tk.Frame(root, bg=SURFACE, height=42,
                               highlightbackground=BORDER, highlightthickness=1)
        self.header.pack(fill="x")
        self.header.pack_propagate(False)
        self.dot = tk.Label(self.header, text="●", bg=SURFACE, fg=MUTED,
                            font=tkfont.Font(size=13))
        self.dot.pack(side="left", padx=(10, 6))
        self.heading = tk.Label(self.header, text="CAPCUT EYES", bg=SURFACE, fg=TEXT,
                                font=strong)
        self.heading.pack(side="left")
        self.collapse_btn = tk.Button(self.header, text="—", command=self.toggle_compact,
                                      bg=SURFACE, fg=MUTED, font=ui, relief="flat", bd=0,
                                      activebackground=SURFACE, activeforeground=TEXT)
        self.collapse_btn.pack(side="right", padx=(0, 4))
        self.close_btn = tk.Button(self.header, text="×", command=self.close,
                                   bg=SURFACE, fg=MUTED, font=strong, relief="flat", bd=0,
                                   activebackground=SURFACE, activeforeground=TEXT)
        self.close_btn.pack(side="right", padx=(2, 8))
        for widget in (self.header, self.dot, self.heading):
            widget.bind("<ButtonPress-1>", self.drag_start)
            widget.bind("<B1-Motion>", self.drag_move)
            widget.bind("<ButtonRelease-1>", self.drag_end)

        self.body = tk.Frame(root, bg=BG, highlightbackground=BORDER, highlightthickness=1)
        self.body.pack(fill="both", expand=True)
        self.title_label = tk.Label(self.body, text="Eyes paused", bg=BG, fg=TEXT,
                                    font=strong, anchor="w")
        self.title_label.pack(fill="x", padx=12, pady=(10, 0))
        self.detail_label = tk.Label(self.body, text="Ready when you are", bg=BG, fg=MUTED,
                                     font=tiny, anchor="w")
        self.detail_label.pack(fill="x", padx=12, pady=(1, 0))
        self.project_label = tk.Label(self.body, text="", bg=BG, fg=MUTED, font=tiny,
                                      anchor="w")
        self.project_label.pack(fill="x", padx=12, pady=(3, 8))

        controls = tk.Frame(self.body, bg=BG)
        controls.pack(fill="x", padx=10)
        self.resume_btn = self.button(controls, "Resume", self.resume, GREEN, ui)
        self.resume_btn.pack(side="left", fill="x", expand=True, padx=(0, 4))
        self.pause_btn = self.button(controls, "Pause", self.pause, SURFACE, ui)
        self.pause_btn.pack(side="left", fill="x", expand=True, padx=4)
        self.finish_btn = self.button(controls, "Finish for Claude", self.finish, PURPLE, ui)
        self.finish_btn.pack(side="left", fill="x", expand=True, padx=(4, 0))
        self.refresh()

    @staticmethod
    def button(parent, text, command, bg, font):
        return tk.Button(parent, text=text, command=command, bg=bg, fg="#ffffff",
                         activebackground=bg, activeforeground="#ffffff", font=font,
                         relief="flat", bd=0, padx=7, pady=7, highlightthickness=0)

    def drag_start(self, event):
        self.drag_x = event.x_root - self.root.winfo_x()
        self.drag_y = event.y_root - self.root.winfo_y()

    def drag_move(self, event):
        x, y = event.x_root - self.drag_x, event.y_root - self.drag_y
        self.root.geometry(geometry_position(x, y))

    def drag_end(self, _event=None):
        POSITION.parent.mkdir(parents=True, exist_ok=True)
        POSITION.write_text(json.dumps({"x": self.root.winfo_x(),
                                        "y": self.root.winfo_y()}) + "\n",
                            encoding="utf-8")

    def run(self, command):
        if self.busy:
            return
        self.busy = True
        self.detail_label.config(text="Working…")

        def worker():
            log_path = sa_eyes.active_dir()
            if command == "handoff" and log_path:
                log_file = log_path / "finish.log"
            else:
                log_file = ROOT / "Sessions" / "_eyes" / "pad.log"
            log_file.parent.mkdir(parents=True, exist_ok=True)
            with log_file.open("a", encoding="utf-8") as out:
                args = [str(PY), str(EYES_TOOL), command]
                if command == "start":
                    args.extend(["--owner-pid", str(os.getpid())])
                subprocess.run(args, stdout=out, stderr=subprocess.STDOUT)
            self.busy = False
        threading.Thread(target=worker, daemon=True).start()

    def resume(self):
        self.run("start")

    def pause(self):
        self.run("stop")

    def finish(self):
        self.run("handoff")

    def toggle_compact(self):
        self.compact = not self.compact
        if self.compact:
            self.body.pack_forget()
            self.root.geometry(f"250x42{geometry_position(self.root.winfo_x(), self.root.winfo_y())}")
            self.collapse_btn.config(text="+")
        else:
            self.body.pack(fill="both", expand=True)
            self.root.geometry(f"306x176{geometry_position(self.root.winfo_x(), self.root.winfo_y())}")
            self.collapse_btn.config(text="—")

    def refresh(self):
        state = snapshot()
        self.dot.config(fg=state["color"])
        self.title_label.config(text=state["title"])
        if not self.busy:
            self.detail_label.config(text=state["detail"])
        project = current_project()
        if len(project) > 29:
            project = project[:27] + "…"
        self.project_label.config(
            text=f"{project}  ·  {state['events']} saves  ·  {state['frames']} frames")
        live = state["state"] in {"live", "degraded"}
        self.resume_btn.config(state="disabled" if live or self.busy else "normal")
        self.pause_btn.config(state="normal" if live and not self.busy else "disabled")
        self.finish_btn.config(state="normal" if state["path"] and not self.busy else "disabled")
        self.root.lift()
        self.root.after(1000, self.refresh)

    def close(self):
        self.drag_end()
        # Closing the visible control must never leave invisible recording behind.
        subprocess.Popen([str(PY), str(EYES_TOOL), "stop"], stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
        try:
            if PAD_PID.read_text(encoding="utf-8").strip() == str(os.getpid()):
                PAD_PID.unlink()
        except OSError:
            pass
        self.root.destroy()


def _test():
    x, y = position()
    assert isinstance(x, int) and isinstance(y, int)
    assert geometry_position(-1920, 96) == "-1920+96"
    state = snapshot()
    assert state["state"] in {"off", "paused", "live", "degraded", "claude_wait",
                              "learning_wait", "learned"}
    project = current_project()
    assert isinstance(project, str) and project
    print(f"sa_eyes_pad self-check: ok (state={state['state']}, project={project})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", action="store_true")
    if ap.parse_args().test:
        _test()
    else:
        claim_single_instance()
        EyesPad(tk.Tk()).root.mainloop()
