#!/usr/bin/env python3
"""sa_clonevo — speak a line in a cloned narrator voice, locally and free.

Requirement (20 Aug 2026): generate narration lines locally, with no per-line cost and
no upload.

Chatterbox (Resemble AI, MIT — the licence matters, XTTS-v2 and F5-TTS ship non-commercial
weights we cannot use for commercial training material) does zero-shot cloning from a
reference sample you have the rights to: your own voice, or a voice actor who has licensed
their voice for cloning. The engine's licence does not cover the voice — the reference
audio must be licensed for this use. `sa_voiceref.py` picks the brightest, cleanest takes
from that material — a clone is only ever as good as what it listens to.

    Tools/venvs/chatterbox/bin/python3 Tools/sa_clonevo.py "Click Save Changes." -o out.wav
    ... --lines lines.json --outdir vo/        # a whole video in one go
    ... --test

Runs locally (Apple Silicon GPU) and uploads nothing.

WHERE NOT TO USE IT: a clone sounds close but not identical. Do not mix it with other
recordings of the same voice inside one video; the switch is heard as a "voice suddenly
changes" fault.
"""
import argparse
import json
import os
import pathlib
import sys

# ONE CONTINUOUS TAKE (7-15 s), never a splice: a montage of many takes is good audio but
# a bad reference, because the model learns every take's different acoustic start and
# stop. Source: one continuous take from your own (or licensed) recording. To replace
# it, find the new best with sa_voiceref.py --scan and copy that ONE file here.
REF = (pathlib.Path(os.environ.get("TRAINING_ROOT", "~/Downloads/training-series")).expanduser()
       / "3 ASSETS" / "voice clone" / "REF_SINGLE.wav")

# Settled on a measured, calm read with no theatrics.
# exaggeration 0.5 = neutral delivery (higher gets dramatic, which the reference never is)
#
# cfg_weight 0.20 — Saad's ear, 21 Aug: the clone rushed its ending, while the reference
# finishes at a normal pace. Measured it and he was exactly right: the reference STARTS
# fast and DECELERATES into the ending (11.6 -> 6.6 peaks/sec, a 43% slowdown) and
# finishes clean with ~0.1s of tail.
# At cfg 0.5 the clone held a flat rate to the end (6.4 -> 6.7, i.e. NO slowdown) and then
# stopped abruptly, leaving 0.3-0.6s of dead air — which reads as rushing the last words.
# Sweeping cfg: 0.5 = no slowdown; 0.3 = decelerates but long tails and rougher;
# 0.2 = slows 17-18% with the tightest tail (0.18s) AND the smoothest output. 0.2 it is.
EXAGGERATION = 0.5
CFG_WEIGHT = 0.2
TAIL_SILENCE = 0.15         # the reference finishes with 0.05-0.17s; trim the clone's to match

# Review note (21 Aug): the clone lacked the reference's energy. Measured: the clone projects
# ~30% weaker at the peaks (0.095 vs the reference's 0.133) and comes out of the engine at
# -22.1 LUFS against the reference files' -17.5 LUFS. I was also delivering at a generic -20,
# flattening it further. Match the REFERENCE files, not a broadcast default.
REF_LUFS = -17.5
REF_PEAK = -3.2


def load(device=None):
    import torch
    from chatterbox.tts import ChatterboxTTS
    if device is None:
        device = "mps" if torch.backends.mps.is_available() else "cpu"
    return ChatterboxTTS.from_pretrained(device=device), device


def say(model, text, out_path, ref=REF, exaggeration=EXAGGERATION, cfg=CFG_WEIGHT):
    """One line -> one wav. 'R&D' is spoken 'R and D' — the engine reads '&' as 'and'
    inconsistently, and the narration should say it in full."""
    import torchaudio
    text = text.replace("R&D", "R and D").replace("&", " and ")
    wav = model.generate(text, audio_prompt_path=str(ref),
                         exaggeration=exaggeration, cfg_weight=cfg)
    torchaudio.save(str(out_path), wav, model.sr)
    trim_tail(out_path, model.sr)
    match_level(out_path)
    return out_path


def match_level(path, lufs=REF_LUFS, peak=REF_PEAK):
    """Lift the clone to the loudness the reference takes sit at, so a swapped line does not
    sound weaker than its neighbours. Loudness only — no compression, no EQ."""
    import subprocess
    import pathlib as _p
    path = _p.Path(path)
    tmp = path.with_name(path.stem + "_lvl.wav")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(path),
                    "-af", f"loudnorm=I={lufs}:TP={peak}:LRA=9",
                    "-ar", "24000", "-ac", "1", str(tmp)], check=True)
    tmp.replace(path)
    return path


def trim_tail(path, sr, keep=TAIL_SILENCE):
    """Cut dead air off the end so the line finishes like the reference does.

    The engine tends to stop speaking then leave 0.3-0.6s of silence; the reference takes
    end 0.05-0.17s after the last word. That gap is part of what Saad heard as the clone
    'rushing' the ending — the words stop early and then nothing happens.
    """
    import numpy as np
    import soundfile as sf
    x, got = sf.read(str(path))
    if x.ndim > 1:
        x = x.mean(axis=1)
    win = max(1, int(got * 0.01))
    env = np.array([np.sqrt((x[i:i + win] ** 2).mean())
                    for i in range(0, max(1, len(x) - win), win)])
    if not len(env) or env.max() <= 0:
        return path
    voiced = np.where(env > env.max() * 0.06)[0]
    if not len(voiced):
        return path
    end = min(len(x), int((voiced[-1] + 1) * win + keep * got))
    sf.write(str(path), x[:end], got)
    return path


def choppiness(path):
    """How abruptly the spectrum jumps between frames, 95th percentile over voiced frames.

    Built 21 Aug because HF>5kHz could NOT hear what Saad calls choppy — the clone he
    rejected and the line he called clear measured the same brightness (0.055 vs 0.057).
    This does separate them: his clear line 0.119, his choppy line 0.145. Like HF it is a
    shortlist, not a verdict — one line he disliked measures clean. Rank with it, then let
    him listen.
    """
    import subprocess
    import tempfile
    import numpy as np
    import soundfile as sf
    w = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(path),
                    "-ar", "24000", "-ac", "1", w], check=True)
    x, _ = sf.read(w)
    n, hop = 1024, 256
    fr = np.array([x[i:i + n] * np.hanning(n) for i in range(0, len(x) - n, hop)])
    if len(fr) < 4:
        return 9.9
    S = np.abs(np.fft.rfft(fr, axis=1)) + 1e-9
    S /= S.sum(axis=1, keepdims=True)
    f = np.sqrt(((np.diff(S, axis=0)) ** 2).sum(axis=1))
    env = np.sqrt((fr ** 2).mean(axis=1))
    voiced = env > env.max() * 0.06
    return float(np.percentile(f[voiced[:len(f)]], 95))


def best_of(model, text, out_path, takes=3, ref=REF, whisper=None, **kw):
    """Chatterbox is inconsistent — in one measured batch, 3 of 6 varied lines came out
    rougher than the rest; some takes come out rougher than others. Locally that costs nothing to fix: speak the line a few
    times, drop any take that says the wrong words, keep the smoothest. This is what makes
    an inconsistent engine usable in production.
    """
    import re
    import difflib
    import pathlib as _p
    out_path = _p.Path(out_path)
    want = re.sub(r"[^a-z0-9 ]", " ", text.lower().replace("&", " and ")).split()
    scored = []
    for i in range(takes):
        tmp = out_path.with_name(f"_{out_path.stem}_take{i}.wav")
        say(model, text, tmp, ref, **kw)
        ok = True
        if whisper is not None:
            heard = " ".join(s.text for s in whisper.transcribe(str(tmp))[0])
            got = re.sub(r"[^a-z0-9 ]", " ", heard.lower().replace("&", " and ")).split()
            ok = difflib.SequenceMatcher(None, want, got).ratio() >= 0.95
        scored.append((not ok, choppiness(tmp), tmp))     # wrong words sink to the bottom
    scored.sort()
    keep = scored[0][2]
    keep.replace(out_path)
    for _, _, p in scored[1:]:
        p.unlink(missing_ok=True)
    return out_path, scored[0][1], sum(1 for bad, _, _ in scored if bad)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("text", nargs="?")
    ap.add_argument("-o", default="clone_out.wav")
    ap.add_argument("--lines", help="JSON list of {n, text} to speak in one run")
    ap.add_argument("--outdir", default=".")
    ap.add_argument("--ref", default=str(REF))
    ap.add_argument("--exaggeration", type=float, default=EXAGGERATION)
    ap.add_argument("--cfg", type=float, default=CFG_WEIGHT)
    ap.add_argument("--takes", type=int, default=3,
                    help="speak each line N times and keep the smoothest (free, local)")
    a = ap.parse_args()

    ref = pathlib.Path(a.ref)
    if not ref.exists():
        raise SystemExit(f"no reference sample at {ref}\n"
                         f"build one first: Tools/sa_voiceref.py --build")

    model, device = load()
    print(f"chatterbox on {device}, reference {ref.name}")

    if a.lines:
        rows = json.loads(pathlib.Path(a.lines).read_text())
        outdir = pathlib.Path(a.outdir)
        outdir.mkdir(parents=True, exist_ok=True)
        whisper = None
        if a.takes > 1:
            from faster_whisper import WhisperModel
            whisper = WhisperModel("base.en", device="cpu", compute_type="int8")
        for r in rows:
            p = outdir / f"{int(r['n']):02d}.wav"
            if a.takes > 1:
                p, chop, wrong = best_of(model, r["text"], p, a.takes, ref, whisper,
                                         exaggeration=a.exaggeration, cfg=a.cfg)
                note = f"  chop {chop:.4f}" + (f", {wrong} take(s) misread" if wrong else "")
            else:
                say(model, r["text"], p, ref, a.exaggeration, a.cfg); note = ""
            print(f"  {p.name}  {r['text'][:46]}{note}")
        return 0

    if not a.text:
        raise SystemExit("give a line to speak, or --lines a JSON file")
    say(model, a.text, a.o, ref, a.exaggeration, a.cfg)
    print(f"-> {a.o}")
    return 0


def _test():
    """Self-check the text handling without loading the model (which is slow)."""
    t = "The R&D desk opens at nine."
    fixed = t.replace("R&D", "R and D").replace("&", " and ")
    assert fixed == "The R and D desk opens at nine.", fixed
    assert "&" not in fixed, "ampersand must never reach the engine"
    assert REF.name.endswith(".wav")
    print("sa_clonevo self-check: ok (R&D spoken in full, reference path set)")


if __name__ == "__main__":
    sys.exit(_test() if "--test" in sys.argv else main())
