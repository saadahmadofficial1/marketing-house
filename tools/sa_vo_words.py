#!/usr/bin/env python3
"""Word timestamps + durations for one module's VO clips -> vo/<mod>_words.json.

    python3 sa_vo_words.py m1 [project_dir]    # project_dir defaults to the current folder

The HyperFrames build reads this so each on-screen word lands on its spoken beat
(rule: every on-screen word lands on its VO beat)."""
import json
import pathlib
import subprocess
import sys

from faster_whisper import WhisperModel

mod = sys.argv[1]
here = pathlib.Path(sys.argv[2]).expanduser() if len(sys.argv) > 2 else pathlib.Path.cwd()
clips = sorted((here / "vo" / mod).glob("[0-9][0-9]_*.mp3"))
lines = (here / "vo" / f"{mod}_lines.txt").read_text().strip().splitlines()
assert len(clips) == len(lines), f"{len(clips)} clips vs {len(lines)} script lines"

m = WhisperModel("small.en", compute_type="int8")
out = []
for clip, text in zip(clips, lines):
    dur = float(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(clip)],
        capture_output=True, text=True, check=True).stdout)
    segs, _ = m.transcribe(str(clip), word_timestamps=True)
    words = [{"w": w.word.strip(), "s": round(w.start, 2), "e": round(w.end, 2)}
             for s in segs for w in s.words]
    out.append({"file": f"vo/{mod}/{clip.name}", "text": text, "dur": round(dur, 3), "words": words})
    print(f"{clip.name}  {dur:5.2f}s  {len(words)} words")

(here / "vo" / f"{mod}_words.json").write_text(json.dumps(out, indent=1))
