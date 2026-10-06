#!/usr/bin/env python3
"""Studio auto-SRT — generate synced .srt captions from any audio/video.
Local + offline (faster-whisper / CTranslate2, no torch, no cloud).
Auto-applies Studio British-English spelling. Usage:
    sa_srt.py <file_or_folder> [--model small|medium] [--burn]
Outputs <name>.srt next to each input. --burn also writes <name>_subbed.mp4.
"""
import sys, os, re, subprocess
from faster_whisper import WhisperModel

FFMPEG = os.path.expanduser("~/.local/bin/ffmpeg")
MEDIA = (".mp3",".wav",".m4a",".aac",".flac",".mp4",".mov",".mkv",".webm")

# Studio standing rule: British English. Fix common Americanisms Whisper emits.
BRIT = {
    r"\borganiz": "organis", r"\bcolor": "colour", r"\bpersonaliz": "personalis",
    r"\bcenter": "centre", r"\brealiz": "realis", r"\boptimiz": "optimis",
    r"\bfavorite": "favourite", r"\bcatalog\b": "catalogue", r"\bprogram\b": "programme",
    r"\bdefense": "defence", r"\btraveler": "traveller", r"\bfiber": "fibre",
    r"\banalyz": "analys", r"\bcanceled": "cancelled", r"\blicense\b": "licence",
}
def britishise(t):
    for a, b in BRIT.items():
        t = re.sub(a, b, t, flags=re.IGNORECASE)
    return t

def ts(s):
    h = int(s//3600); m = int((s%3600)//60); sec = s%60
    return f"{h:02d}:{m:02d}:{sec:06.3f}".replace(".", ",")

def srt_for(path, model):
    print(f"  transcribing {os.path.basename(path)} ...")
    segs, info = model.transcribe(path, language="en", vad_filter=True,
                                  word_timestamps=False)
    lines = []
    for i, s in enumerate(segs, 1):
        txt = britishise(s.text.strip())
        lines.append(f"{i}\n{ts(s.start)} --> {ts(s.end)}\n{txt}\n")
    out = os.path.splitext(path)[0] + ".srt"
    with open(out, "w") as f:
        f.write("\n".join(lines))
    print(f"  -> {out}  ({len(lines)} cues)")
    return out

def burn(video, srt):
    out = os.path.splitext(video)[0] + "_subbed.mp4"
    subprocess.run([FFMPEG, "-y", "-i", video, "-vf",
        f"subtitles={srt}:force_style='FontName=Avenir Next,FontSize=20,"
        f"PrimaryColour=&Hffffff&,OutlineColour=&H80000000&,BorderStyle=3'",
        "-c:a", "copy", out], check=True)
    print(f"  burned -> {out}")

def main():
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    target = os.path.expanduser(sys.argv[1])
    size = "small"
    if "--model" in sys.argv: size = sys.argv[sys.argv.index("--model")+1]
    do_burn = "--burn" in sys.argv
    files = []
    if os.path.isdir(target):
        files = [os.path.join(target,f) for f in sorted(os.listdir(target))
                 if f.lower().endswith(MEDIA)]
    else:
        files = [target]
    print(f"loading whisper '{size}' (first run downloads model once)...")
    model = WhisperModel(size, device="cpu", compute_type="int8")
    for fp in files:
        srt = srt_for(fp, model)
        if do_burn and fp.lower().endswith((".mp4",".mov",".mkv",".webm")):
            burn(fp, srt)
    print(f"done — {len(files)} file(s).")

if __name__ == "__main__":
    main()
