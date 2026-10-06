"""Kokoro with REAL punctuation pauses: synth per phrase, insert silence.
usage: sa_kokoro_say.py "text" voice speed out.wav
(kokoro-v1.0.onnx and voices-v1.0.bin sit beside this script)"""
import re
import sys

import numpy as np
import soundfile as sf
from kokoro_onnx import Kokoro

BASE = __file__.rsplit("/", 1)[0]
text, voice, speed, out = sys.argv[1], sys.argv[2], float(sys.argv[3]), sys.argv[4]

k = Kokoro(f"{BASE}/kokoro-v1.0.onnx", f"{BASE}/voices-v1.0.bin")
# split keeping the delimiter so we know which pause to insert
parts = re.split(r"(?<=[,.;:!?…])\s+", text.strip())
chunks, sr = [], 24000
for p in parts:
    p = p.strip()
    if not p:
        continue
    samples, sr = k.create(p, voice=voice, speed=speed, lang="en-gb")
    chunks.append(samples)
    pause = 0.45 if p[-1] in ".!?…" else 0.22   # full stop vs comma
    chunks.append(np.zeros(int(sr * pause), dtype=samples.dtype))
sf.write(out, np.concatenate(chunks[:-1]), sr)  # drop trailing pause
print("ok")
