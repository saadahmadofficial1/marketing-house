#!/usr/bin/env python3
"""Independent verify (24 Sep, a build workflow's VERIFY stage): transcribe the REVIEW render's
audio with a DIFFERENT local model than the build used (medium.en vs the build's base/small.en),
word timestamps. This check runs locally and uploads nothing.

    python3 sa_independent_asr.py REVIEW.mp4 [OUT.json]
        -> OUT.json (default: <REVIEW>_words_medium.json next to the video)
"""
import json, pathlib, subprocess, sys, tempfile

if len(sys.argv) < 2:
    sys.exit(__doc__)
from faster_whisper import WhisperModel

REVIEW = pathlib.Path(sys.argv[1]).expanduser()
OUT = (pathlib.Path(sys.argv[2]).expanduser() if len(sys.argv) > 2
       else REVIEW.with_name(REVIEW.stem + "_words_medium.json"))
OUT.parent.mkdir(parents=True, exist_ok=True)

with tempfile.TemporaryDirectory() as tmp:
    wav = pathlib.Path(tmp) / "a.wav"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(REVIEW), "-ac", "1", "-ar", "16000", str(wav)], check=True)
    wm = WhisperModel("medium.en", device="cpu", compute_type="int8", cpu_threads=6)
    segs, _ = wm.transcribe(str(wav), word_timestamps=True, beam_size=5, vad_filter=False,
                            condition_on_previous_text=False)
    words = []
    for s in segs:
        for w in s.words:
            words.append({"w": w.word.strip(), "s": round(w.start, 3), "e": round(w.end, 3), "p": round(w.probability, 3)})
json.dump({"model": "faster-whisper medium.en int8", "video": str(REVIEW), "words": words}, open(OUT, "w"), indent=0)
print("words", len(words))
