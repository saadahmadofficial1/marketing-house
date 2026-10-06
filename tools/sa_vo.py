#!/usr/bin/env python3
"""Voiceover kit: SRT script -> per-line MP3 clips + SRT re-timed to real audio.
  sa_vo.py script.srt [outdir] [--voice en-GB-RyanNeural] [--gap 0.4]
Reads each SRT block's text, renders it with edge-tts (free, but
it sends the text to Microsoft’s online Edge read-aloud service, so keep confidential
scripts out), probes real durations, writes clips 01.mp3.. + final.srt
whose timings match the audio. Drop clips + final.srt into CapCut.
"""
import os, re, subprocess, sys

import shutil
# resolve tools portably: local known spots first, then PATH (works on any machine)
_EDGE_LOCAL = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "installs/ppt-master/.venv/bin/edge-tts")
EDGE = _EDGE_LOCAL if os.path.exists(_EDGE_LOCAL) else (shutil.which("edge-tts") or "edge-tts")
_FF_LOCAL = os.path.expanduser("~/.local/bin/ffmpeg")
FFMPEG = _FF_LOCAL if os.path.exists(_FF_LOCAL) else (shutil.which("ffmpeg") or "ffmpeg")
# no ffprobe on this Mac — durations parsed from ffmpeg -i stderr instead

def parse_srt(path):
    blocks = re.split(r"\n\s*\n", open(path, encoding="utf-8").read().strip())
    out = []
    for b in blocks:
        lines = b.strip().splitlines()
        if len(lines) >= 3:
            out.append(" ".join(lines[2:]).strip())
    return out

def dur(path):  # seconds, parsed from ffmpeg -i stderr (Duration: 00:00:07.87)
    r = subprocess.run([FFMPEG, "-i", path], capture_output=True, text=True)
    m = re.search(r"Duration: (\d+):(\d+):(\d+\.?\d*)", r.stderr)
    if not m:
        raise RuntimeError(f"no duration in ffmpeg output for {path}")
    h, mn, s = m.groups()
    return int(h) * 3600 + int(mn) * 60 + float(s)

def ts(sec):
    ms = int(round(sec * 1000))
    return f"{ms//3600000:02d}:{ms//60000%60:02d}:{ms//1000%60:02d},{ms%1000:03d}"

def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    srt = args[0]
    outdir = args[1] if len(args) > 1 else os.path.join(os.path.dirname(os.path.abspath(srt)), "VO")
    voice = sys.argv[sys.argv.index("--voice") + 1] if "--voice" in sys.argv else "en-GB-RyanNeural"
    gap = float(sys.argv[sys.argv.index("--gap") + 1]) if "--gap" in sys.argv else 0.4
    os.makedirs(outdir, exist_ok=True)

    lines = parse_srt(srt)
    t, blocks = 0.0, []
    for i, text in enumerate(lines, 1):
        mp3 = os.path.join(outdir, f"{i:02d}.mp3")
        subprocess.run([EDGE, "--voice", voice, "--text", text, "--write-media", mp3],
                       check=True, capture_output=True)
        d = dur(mp3)
        blocks.append(f"{i}\n{ts(t)} --> {ts(t + d)}\n{text}")
        print(f"{i:02d}.mp3  {d:5.1f}s  {text[:60]}")
        t += d + gap
    final = os.path.join(outdir, "final.srt")
    open(final, "w", encoding="utf-8").write("\n\n".join(blocks) + "\n")
    print(f"\n{len(lines)} clips -> {outdir}  |  re-timed SRT -> {final}  |  total ~{t:.0f}s")

if __name__ == "__main__":
    main()
