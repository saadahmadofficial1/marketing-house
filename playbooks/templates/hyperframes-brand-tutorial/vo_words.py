#!/usr/bin/env python3
"""Word timestamps and durations for a module's voice-over clips -> words.json.

    python3 vo_words.py --clips vo/acme_m1 --lines lines.txt --out words.json [--model small.en]

One clip per script line, named so that sorting puts them in order (01_..., 02_...).
build_module.py reads the result so every on-screen word lands on its spoken beat, and
the captions are cut on real word times rather than guessed ones.

Runs locally with faster-whisper (pip install faster-whisper) and uploads nothing.
A recogniser can split or merge a word; build_module.py reports those and places them
between their neighbours, and a cue word that is not heard at all stops the build.
Generalised from ../../../tools/sa_vo_words.py.
"""
import argparse
import json
import pathlib
import subprocess


def duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", str(path)], capture_output=True, text=True, check=True)
    return round(float(out.stdout.strip()), 3)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--clips", required=True, help="folder of voice-over clips, one per line")
    ap.add_argument("--lines", required=True, help="the script, one line per clip")
    ap.add_argument("--out", required=True)
    ap.add_argument("--model", default="small.en", help="faster-whisper model name")
    ap.add_argument("--glob", default="[0-9][0-9]_*.mp3")
    a = ap.parse_args()

    from faster_whisper import WhisperModel  # imported here so --help works without it

    clips = sorted(pathlib.Path(a.clips).glob(a.glob))
    lines = [s.strip() for s in pathlib.Path(a.lines).read_text(encoding="utf-8").splitlines()
             if s.strip() and not s.strip().startswith("#")]
    if len(clips) != len(lines):
        raise SystemExit(f"{len(clips)} clips vs {len(lines)} script lines: one clip per line")
    model = WhisperModel(a.model, device="cpu", compute_type="int8")
    out = []
    for clip, text in zip(clips, lines):
        segs, _ = model.transcribe(str(clip), word_timestamps=True)
        words = [{"w": w.word.strip(), "s": round(w.start, 2), "e": round(w.end, 2)}
                 for s in segs for w in s.words]
        out.append({"file": str(clip), "text": text, "dur": duration(clip), "words": words})
        print(f"{clip.name}  {out[-1]['dur']:6.2f}s  {len(words)} words")
    pathlib.Path(a.out).write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    print(f"-> {a.out}")


if __name__ == "__main__":
    main()
