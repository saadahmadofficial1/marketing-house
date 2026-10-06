#!/usr/bin/env python3
"""sa_desk — the little Claude window that floats over CapCut.

Requirement (10 Aug): be able to ask the assistant things from inside the editor, without
leaving it. CapCut is closed software with no plugin API, so nothing can live
*inside* it. This is the next best thing and it is real: a small always-on-top window
that sits beside the timeline, takes a plain-English request, and runs it against this
workspace — same tools, same guards, same memory as the terminal.

    python3 Tools/sa_desk.py            (or double-click "Ask Claude.command")

It knows what he is editing: every request carries the CapCut project he touched last,
so "the box is wrong here" needs no explaining. Answers are read-only by default —
project writes still refuse while CapCut is open, exactly as in the terminal.
"""
import glob
import os
import pathlib
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import font as tkfont

ROOT = pathlib.Path(__file__).resolve().parents[1]
CAPCUT = pathlib.Path("~/Movies/CapCut/User Data/Projects/com.lveditor.draft").expanduser()
CLAUDE = os.path.expanduser("~/.local/bin/claude")
BG, FG, ACC, DIM = "#14161a", "#e8eaed", "#4c8dff", "#8b9099"


def current_project():
    """The CapCut project he touched last — the context for anything he asks."""
    best, when = None, 0
    for f in glob.glob(str(CAPCUT / "*/draft_info.json")) + \
            glob.glob(str(CAPCUT / "*/Timelines/*/draft_info.json")):
        try:
            m = os.path.getmtime(f)
        except OSError:
            continue
        if m > when:
            when, best = m, f
    if not best:
        return None
    name = pathlib.Path(best).relative_to(CAPCUT).parts[0]
    return None if name.endswith("-copy") else name


def capcut_open():
    return subprocess.run(["pgrep", "-x", "CapCut"], capture_output=True).returncode == 0


# --- voice ------------------------------------------------------------------
# Saad would rather talk than type. Recording is ffmpeg off the built-in mic;
# transcription is the local faster-whisper in Tools/venv: it runs locally and uploads
# no audio (only the text he chooses to send goes to Claude). The heard text lands in the box so he can see it before sending, because
# a misheard instruction acted on silently is worse than no voice input at all.
MIC = ":1"                                   # avfoundation "MacBook Pro Microphone"
WAV = pathlib.Path("/tmp/sa_desk_voice.wav")
VENV_PY = ROOT / "Tools" / "venv" / "bin" / "python3"
TRANSCRIBE = """
import sys, warnings
warnings.filterwarnings("ignore")
from faster_whisper import WhisperModel
segs, _ = WhisperModel("small", device="cpu", compute_type="int8").transcribe(
    sys.argv[1], language="en")
print(" ".join(s.text.strip() for s in segs).strip())
"""


def start_recording():
    WAV.unlink(missing_ok=True)
    return subprocess.Popen(
        ["ffmpeg", "-y", "-f", "avfoundation", "-i", MIC, "-ac", "1", "-ar", "16000",
         str(WAV)], stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL)


def stop_recording(proc):
    """ffmpeg needs 'q' on stdin to close the file cleanly; killing it truncates."""
    try:
        proc.stdin.write(b"q")
        proc.stdin.flush()
        proc.wait(timeout=5)
    except Exception:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except Exception:
            proc.kill()


def transcribe():
    if not WAV.exists() or WAV.stat().st_size == 0:
        # macOS blocks the mic until the launching app is ticked in Privacy settings,
        # and ffmpeg fails silently when it is not — say so instead of "heard nothing"
        return "__NO_MIC__"
    if WAV.stat().st_size < 8000:                          # under ~0.25s of audio
        return ""
    r = subprocess.run([str(VENV_PY), "-c", TRANSCRIBE, str(WAV)],
                       capture_output=True, text=True)
    return (r.stdout or "").strip()


def ask(prompt, out_q):
    """Run the request through Claude Code in this workspace; stream lines back."""
    proj = current_project()
    context = (f"[Saad is in CapCut right now, last editing: {proj}. "
               f"CapCut is {'OPEN — never write to any project' if capcut_open() else 'closed'}.] "
               if proj else "")
    try:
        p = subprocess.Popen(
            [CLAUDE, "-p", context + prompt],
            cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1)
        for line in p.stdout:
            out_q.put(line.rstrip())
        p.wait()
    except Exception as e:                       # a dead CLI must not kill the window
        out_q.put(f"[could not reach Claude: {e}]")
    out_q.put(None)


class Desk:
    def __init__(self, root):
        self.root = root
        self.q = queue.Queue()
        self.busy = False
        root.title("Ask Claude")
        root.configure(bg=BG)
        root.geometry("420x340+40+80")
        root.attributes("-topmost", True)        # stays above CapCut
        root.minsize(340, 240)

        mono = tkfont.Font(family="SF Mono", size=12)
        ui = tkfont.Font(family="SF Pro Text", size=12)

        self.status = tk.Label(root, text="", bg=BG, fg=DIM, font=ui, anchor="w",
                               padx=10, pady=4)
        self.status.pack(fill="x")

        self.out = tk.Text(root, bg="#0f1114", fg=FG, font=mono, wrap="word",
                           relief="flat", padx=10, pady=8, insertbackground=FG,
                           highlightthickness=0)
        self.out.pack(fill="both", expand=True, padx=8)
        self.out.tag_config("me", foreground=ACC)
        self.out.tag_config("dim", foreground=DIM)
        self.out.insert("end", "Ask me anything about the video you are editing.\n"
                               "Enter to send · Shift-Enter for a new line\n\n", "dim")
        self.out.configure(state="disabled")

        self.entry = tk.Text(root, height=3, bg="#1b1e24", fg=FG, font=ui, wrap="word",
                             relief="flat", padx=8, pady=6, insertbackground=FG,
                             highlightthickness=1, highlightbackground="#2a2e36",
                             highlightcolor=ACC)
        self.entry.pack(fill="x", padx=8, pady=(8, 4))
        self.entry.bind("<Return>", self.send)
        self.entry.bind("<Shift-Return>", lambda e: None)
        self.entry.focus_set()

        bar = tk.Frame(root, bg=BG)
        bar.pack(fill="x", padx=8, pady=(0, 8))
        self.mic_btn = tk.Button(bar, text="  Talk  ", command=self.toggle_mic,
                                 bg="#1b1e24", fg=FG, font=ui, relief="flat",
                                 activebackground=ACC, activeforeground="#ffffff",
                                 highlightthickness=0, bd=0, padx=10, pady=4)
        self.mic_btn.pack(side="left")
        tk.Label(bar, text="  hold a thought, click again to stop", bg=BG, fg=DIM,
                 font=ui).pack(side="left")
        tk.Button(bar, text="  Send  ", command=self.send, bg=ACC, fg="#ffffff",
                  font=ui, relief="flat", activebackground="#3a7bef",
                  activeforeground="#ffffff", highlightthickness=0, bd=0,
                  padx=10, pady=4).pack(side="right")
        self.rec = None

        self.tick_status()
        self.drain()

    def toggle_mic(self):
        if self.rec is None:                       # start
            try:
                self.rec = start_recording()
            except Exception as e:
                self.write(f"[microphone unavailable: {e}]", "dim")
                return
            self.mic_btn.config(text="  Stop  ", bg="#8f2a2a")
            self.status.config(text="  listening…")
            return
        proc, self.rec = self.rec, None            # stop + transcribe off-thread
        self.mic_btn.config(text="  …  ", bg="#1b1e24")

        def finish():
            stop_recording(proc)
            said = transcribe()
            self.q.put(("VOICE", said))
        threading.Thread(target=finish, daemon=True).start()

    def tick_status(self):
        proj = current_project()
        state = "CapCut open" if capcut_open() else "CapCut closed"
        self.status.config(text=f"  {proj or 'no project yet'}   ·   {state}")
        self.root.after(4000, self.tick_status)

    def write(self, text, tag=None):
        self.out.configure(state="normal")
        self.out.insert("end", text + "\n", tag)
        self.out.see("end")
        self.out.configure(state="disabled")

    def send(self, event=None):
        if self.busy:
            return "break"
        prompt = self.entry.get("1.0", "end").strip()
        if not prompt:
            return "break"
        self.entry.delete("1.0", "end")
        self.write("\n> " + prompt, "me")
        self.write("thinking…", "dim")
        self.busy = True
        threading.Thread(target=ask, args=(prompt, self.q), daemon=True).start()
        return "break"

    def drain(self):
        try:
            while True:
                item = self.q.get_nowait()
                if isinstance(item, tuple) and item[0] == "VOICE":
                    said = item[1]
                    self.mic_btn.config(text="  Talk  ", bg="#1b1e24")
                    if said == "__NO_MIC__":
                        self.write("[the microphone is blocked — open System Settings › "
                                   "Privacy & Security › Microphone and switch on "
                                   "Terminal, then click Talk again]", "dim")
                    elif said:
                        self.entry.delete("1.0", "end")
                        self.entry.insert("1.0", said)   # he checks it, then Enter
                        self.entry.focus_set()
                    else:
                        self.write("[heard nothing — try again]", "dim")
                    continue
                if item is None:
                    self.busy = False
                    break
                self.write(item)
        except queue.Empty:
            pass
        self.root.after(120, self.drain)


if __name__ == "__main__":
    if "--test" in sys.argv:
        # pure bits only: no window is opened during a self-check
        assert callable(current_project) and callable(capcut_open)
        p = current_project()
        assert p is None or not p.endswith("-copy"), "the -copy project is never context"
        print(f"sa_desk self-check: ok (context project: {p or 'none'}, "
              f"CapCut {'open' if capcut_open() else 'closed'})")
        sys.exit()
    Desk(tk.Tk()).root.mainloop()
