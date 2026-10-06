"""The three sync checks needed when a reviewer reports markings or captions out of sync with the voice,
run on a finished module.
  1. markings vs voice: each box's start against the moment its words are spoken
  2. markings held: the element reads back from inside the box at start, middle AND end
  3. captions vs voice: each line's first caption against the speech onset on the WAVEFORM
    sa_check_sync.py COMPOSITE.mp4 PREVIEW.mp4 _layers.json captions.srt timing.json
OCR is the on-device bin/sa_ocr helper next to this file (built from sa_ocr.swift)."""
import json, os, subprocess, sys, tempfile, pathlib, wave
import numpy as np
from PIL import Image
FF = os.path.expanduser("~/.local/bin/ffmpeg")
if not os.path.exists(FF):
    FF = "ffmpeg"
OCR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bin", "sa_ocr")
norm = lambda z: " ".join("".join(c if c.isalnum() or c == " " else " " for c in z.lower()).split())
def sec(x):
    h, m, s = x.replace(",", ".").split(":"); return int(h) * 3600 + int(m) * 60 + float(s)

def main(comp, prev, layers, srt, timing):
    L = json.load(open(layers))["layers"]; T = json.load(open(timing))
    offs = [l["start"] - l["said_at"] for l in L if "said_at" in l]
    worst = max(offs, key=abs) if offs else 0
    print(f"1. MARKINGS vs VOICE: {len(offs)} markings, worst {worst:+.2f}s from the word "
          f"({sum(abs(o) > 1.0 for o in offs)} more than 1s off)")
    td = pathlib.Path(tempfile.mkdtemp()); clean = 0; fails = []
    for l in L:
        x, y, w, h = l["box"]; s, d = l["start"], l["duration"]; ok = True
        for tag, t in (("start", s + 0.05), ("mid", s + d / 2), ("end", s + d - 0.08)):
            subprocess.run([FF, "-y", "-v", "error", "-ss", f"{t:.2f}", "-i", comp, "-frames:v", "1", str(td / "c.png")], check=True)
            im = Image.open(td / "c.png").convert("RGB")
            im.crop((max(0, x - 10), max(0, y - 10), min(im.width, x + w + 10), min(im.height, y + h + 10))).save(td / "k.png")
            txt = subprocess.run([OCR, str(td / "k.png")], capture_output=True, text=True).stdout.partition("\t")[2]
            if norm(l["label"]).replace(" ", "")[:12] not in norm(txt).replace(" ", ""): ok = False; fails.append((s, l["label"], tag))  # OCR spacing is noise
        clean += ok
    print(f"2. MARKINGS HELD: {clean}/{len(L)} clean at start, middle AND end" + "".join(f"\n   !! {f[0]:.2f}s '{f[1]}' at {f[2]}" for f in fails))
    subprocess.run([FF, "-y", "-v", "error", "-i", prev, "-vn", "-ac", "1", "-ar", "16000", str(td / "a.wav")], check=True)
    wv = wave.open(str(td / "a.wav")); sr = wv.getframerate()
    a = np.frombuffer(wv.readframes(wv.getnframes()), dtype=np.int16).astype(float)
    rms = np.sqrt(np.convolve(a * a, np.ones(int(sr * 0.01)) / int(sr * 0.01), mode="same")); thr = rms.max() * 0.06
    starts = [sec(b.split("\n")[1].split("-->")[0].strip()) for b in open(srt).read().strip().split("\n\n")]
    errs = []
    for sg in T["segments"]:
        i0 = int(sg["start"] * sr); idx = np.where(rms[i0:i0 + int(1.5 * sr)] > thr)[0]
        if len(idx):
            on = sg["start"] + idx[0] / sr; errs.append(min(starts, key=lambda t: abs(t - on)) - on)
    print(f"3. CAPTIONS vs VOICE: worst line start {max(errs, key=abs)*1000:+.0f} ms from the waveform onset")

if __name__ == "__main__":
    main(*[os.path.expanduser(a) for a in sys.argv[1:6]])
