#!/usr/bin/env python3
"""sa_voiceref — build a voice-cloning reference sample from the best takes in a folder.

Point it only at recordings you own, or are licensed to use for voice cloning with the
speaker’s consent. It reads the folder named by VOICE_REF_DIR and nothing else.

A long recording session leaves hundreds of takes. Most are good; some are dull,
band-limited “old radio” takes. A clone is only ever as good as its reference, so this
picks by measurement, not by hope:

  1. HF>5kHz ratio (sa_hfcheck)  — the dull/choppy takes measure low. Keep the top band.
  2. peak level                   — reject anything clipping (>0.985) or too quiet.
  3. duration                     — 1.8-9s chunks only; fragments and monologues both hurt.
  4. silence                      — reject takes that are mostly padding.
  5. transcription                — the shortlist is read back with faster-whisper and
                                    dropped if it stutters, doubles a phrase, or is unclear.
  6. phonetic spread              — greedy pick that maximises new letters/sounds, so the
                                    reference covers the range rather than ten similar lines.

Writes a single concatenated wav (24kHz mono, gently level-matched) plus a manifest of
exactly which takes went in and why.

    export VOICE_REF_DIR=~/Voice/my-recordings   # recordings you own or are licensed to clone
    python3 sa_voiceref.py --scan            # measure, report, write nothing
    python3 sa_voiceref.py --build -o ref.wav --seconds 90
    python3 sa_voiceref.py --test

Every step here runs locally and this script uploads nothing; whatever you later hand
ref.wav to is a separate choice: check that service’s terms, and use only recordings you
own or are licensed to clone.
"""
import argparse
import json
import os
import pathlib
import re
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from sa_hfcheck import hf_ratio

# Recordings you own or are licensed to clone. Nothing outside this folder is read.
REF_DIR = pathlib.Path(os.environ.get("VOICE_REF_DIR", "~/Voice/reference-recordings")).expanduser()
AUDIO_EXTS = {".wav", ".mp3", ".m4a", ".flac", ".aif", ".aiff"}
MIN_DUR, MAX_DUR = 1.8, 9.0
PEAK_MAX = 0.985            # above this it is clipping and will teach the clone to crackle
PEAK_MIN = 0.08             # below this there is not enough signal to learn from
SILENCE_MAX = 0.45          # fraction of the take allowed to be silence


def probe(path):
    """-> (duration, peak, silence_fraction). One ffmpeg pass, no decode to disk."""
    # -v info, NOT error: astats and silencedetect write their report at info level, so
    # "-v error" returns an empty string and every take measures as silent (caught 20 Aug).
    out = subprocess.run(
        ["ffmpeg", "-v", "info", "-i", str(path), "-af",
         "astats=metadata=1:reset=0,silencedetect=n=-40dB:d=0.25", "-f", "null", "-"],
        capture_output=True, text=True).stderr
    dur = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
         str(path)], capture_output=True, text=True).stdout.strip()
    dur = float(dur) if dur else 0.0
    peak = 0.0
    m = re.findall(r"Peak level dB:\s*(-?[\d.]+|-inf)", out)
    if m:
        vals = [float(x) for x in m if x != "-inf"]
        if vals:
            peak = 10 ** (max(vals) / 20)
    quiet = sum(float(x) for x in re.findall(r"silence_duration:\s*([\d.]+)", out))
    return dur, peak, (quiet / dur if dur else 1.0)


def sources():
    """Every audio take under VOICE_REF_DIR (your own or licensed recordings only)."""
    if not REF_DIR.is_dir():
        sys.exit(f"VOICE_REF_DIR not found: {REF_DIR} — point it at recordings you own "
                 "or are licensed to clone")
    return sorted(p for p in REF_DIR.rglob("*")
                  if p.is_file() and p.suffix.lower() in AUDIO_EXTS)


def measure(paths):
    rows = []
    for p in paths:
        dur, peak, sil = probe(p)
        if not (MIN_DUR <= dur <= MAX_DUR):
            continue
        if not (PEAK_MIN <= peak <= PEAK_MAX):
            continue
        if sil > SILENCE_MAX:
            continue
        hf = hf_ratio(p) or 0.0
        rows.append({"file": str(p), "dur": round(dur, 2), "peak": round(peak, 3),
                     "silence": round(sil, 2), "hf": round(hf, 4)})
    rows.sort(key=lambda r: -r["hf"])
    return rows


def clean_read(path, model):
    """-> (text, ok). Rejects stutters, doubled phrases and unintelligible takes."""
    segs, _ = model.transcribe(str(path))
    text = " ".join(s.text for s in segs).strip()
    words = re.sub(r"[^a-z0-9 ]", " ", text.lower()).split()
    if len(words) < 3:
        return text, False
    # a doubled take repeats a run of words back-to-back
    for n in range(3, min(9, len(words) // 2 + 1)):
        if any(words[i:i + n] == words[i + n:i + 2 * n] for i in range(len(words) - 2 * n + 1)):
            return text, False
    return text, True


def spread_pick(rows, target_seconds):
    """Greedy: take the brightest, then keep adding whichever take brings the most new
    letters, so the reference covers a wide range of sounds instead of ten similar lines."""
    chosen, seen, total = [], set(), 0.0
    pool = list(rows)
    while pool and total < target_seconds:
        best, best_gain = None, -1
        for r in pool:
            gain = len(set(re.sub(r"[^a-z]", "", r.get("text", "").lower())) - seen)
            gain = gain * 10 + r["hf"] * 100          # coverage first, brightness as tiebreak
            if gain > best_gain:
                best, best_gain = r, gain
        pool.remove(best)
        chosen.append(best)
        seen |= set(re.sub(r"[^a-z]", "", best.get("text", "").lower()))
        total += best["dur"]
    return chosen, total


def build(chosen, out_path):
    """Concatenate at a common loudness. Gentle: loudnorm only, no EQ, no compression —
    the clone must hear the speaker, not our processing."""
    tmp = pathlib.Path(out_path).with_suffix(".files.txt")
    parts = []
    for i, r in enumerate(chosen):
        seg = pathlib.Path(out_path).with_name(f"_ref_{i:03d}.wav")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", r["file"],
                        "-af", "loudnorm=I=-20:TP=-2:LRA=7", "-ar", "24000", "-ac", "1",
                        str(seg)], check=True)
        parts.append(seg)
    tmp.write_text("".join(f"file '{p}'\n" for p in parts))
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
                    "-i", str(tmp), "-ar", "24000", "-ac", "1", str(out_path)], check=True)
    for p in parts:
        p.unlink()
    tmp.unlink()
    return out_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scan", action="store_true")
    ap.add_argument("--build", action="store_true")
    ap.add_argument("-o", default="VOICE_REFERENCE.wav")
    ap.add_argument("--seconds", type=float, default=90.0)
    ap.add_argument("--shortlist", type=int, default=60)
    a = ap.parse_args()

    paths = sources()
    print(f"{len(paths)} takes on disk; measuring...")
    rows = measure(paths)
    print(f"{len(rows)} pass the level/length/silence gates")
    if not rows:
        return 1
    hi = rows[:a.shortlist]
    print(f"HF range kept: {hi[-1]['hf']:.4f} - {hi[0]['hf']:.4f}")

    from faster_whisper import WhisperModel
    model = WhisperModel("base.en", device="cpu", compute_type="int8")
    clean = []
    for r in hi:
        text, ok = clean_read(r["file"], model)
        r["text"] = text
        if ok:
            clean.append(r)
    print(f"{len(clean)} of {len(hi)} read back clean (no stutter or doubled phrase)")

    chosen, total = spread_pick(clean, a.seconds)
    letters = len(set(re.sub(r"[^a-z]", "", " ".join(c["text"].lower() for c in chosen))))
    print(f"\nreference: {len(chosen)} takes, {total:.1f}s, {letters}/26 letters covered")
    for c in chosen:
        print(f"   {c['hf']:.4f}  {c['dur']:4.1f}s  {pathlib.Path(c['file']).name[:44]}")

    if a.build:
        out = build(chosen, a.o)
        json.dump(chosen, open(pathlib.Path(a.o).with_suffix(".json"), "w"), indent=1)
        d, peak, sil = probe(out)
        print(f"\n-> {out}  ({d:.1f}s, peak {peak:.3f}, silence {sil:.0%})")
        print(f"-> {pathlib.Path(a.o).with_suffix('.json')}  (which takes went in)")
    return 0


def _test():
    rows = [{"dur": 3.0, "hf": 0.09, "text": "the quick brown fox"},
            {"dur": 3.0, "hf": 0.08, "text": "the quick brown fox"},
            {"dur": 3.0, "hf": 0.07, "text": "jumps over lazy dogs"}]
    chosen, total = spread_pick(rows, 6.5)
    assert chosen[0]["hf"] == 0.09, "brightest first"
    assert chosen[1]["text"] == "jumps over lazy dogs", \
        "second pick must add new sounds, not repeat the same words"
    words = "one two three one two three".split()
    doubled = any(words[i:i + 3] == words[i + 3:i + 6] for i in range(len(words) - 5))
    assert doubled, "the doubled-phrase detector must catch a repeated run"
    print("sa_voiceref self-check: ok (spread favours new sounds, doubling detected)")


if __name__ == "__main__":
    sys.exit(_test() if "--test" in sys.argv else main())
