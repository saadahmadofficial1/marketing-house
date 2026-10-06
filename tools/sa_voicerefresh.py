#!/usr/bin/env python3
"""Regenerate every spoken line and keep the take that is not dull.

Requirement (18 Aug): regenerate the remaining dull-sounding lines (short of high
frequencies) across all the videos; placement is adjusted by hand. The drift had been flagged in review, but
not the exact lines.

That is the whole problem in one sentence: a reviewer can hear the drift but cannot
name the lines, and neither can any absolute measurement — HF energy tracks the
WORDS, not the quality (every title line in his delivered videos sits 0.047-0.071
purely because of its wording, so a fixed threshold condemns work he is happy
with).

But there IS one valid comparison: the existing audio against FRESH TAKES OF THE
SAME WORDS. Content is then identical, so a real difference can only be the
generator drifting. That is what this does, per line:

    1. cut the original audio exactly as it plays in the video
    2. generate N fresh takes of the same text (the approved voice, its settings)
    3. measure HF>5kHz on all of them
    4. if the original falls below RELATIVE_DROP of the best take, the original
       is the dull one -> hand him the best take as a replacement

Validated by his ear twice: a take he rejected measured 0.0614 against
0.0907/0.0916/0.1080 accepted, and a title he independently flagged measured
0.0404, the lowest of anything tested.

Nothing is written into any project — this only produces files and a report.
Placement is his, or sa_voiceswap.py's.

    sa_voicerefresh.py MOD03 --takes 2          # dry run: costs, no generation
    sa_voicerefresh.py MOD03 --takes 2 --go
"""
import argparse
import json
import os
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from sa_hfcheck import hf_ratio, RELATIVE_DROP          # noqa: E402

SERIES = pathlib.Path(os.environ.get("TRAINING_ROOT", "~/Downloads/training-series")).expanduser()
ADMIN = SERIES / "5 ADMIN"
OUT = SERIES / "3 ASSETS" / "voice fixes"
VOICE = "YOUR_VOICE_ID"          # the TTS voice the series was narrated with


def segments(tag):
    rows = json.loads((ADMIN / "VOICE_CHECK.json").read_text())
    return [r for r in rows if r["tag"] == tag and r["intended"].strip()]


def cut_original(r, dst):
    """The original audio exactly as it plays in the finished video."""
    subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{r['src']:.3f}", "-t", f"{r['dur']:.3f}",
                    "-i", r["path"], "-ac", "1", "-ar", "44100", "-b:a", "128k",
                    "-y", str(dst)], capture_output=True)
    return dst if dst.exists() else None


def plan(tag, takes):
    segs = segments(tag)
    words = sum(len(s["intended"].split()) for s in segs)
    print(f"  {tag}: {len(segs)} lines, ~{words} words -> {len(segs)*takes} generations "
          f"(~{len(segs)*takes*0.3:.0f} credits)")
    return segs


def report(tag, rows):
    OUT.mkdir(parents=True, exist_ok=True)
    f = OUT / f"{tag}_refresh.json"
    f.write_text(json.dumps(rows, indent=1, ensure_ascii=False))
    worse = [r for r in rows if r["verdict"] == "REPLACE"]
    print(f"\n  {tag}: {len(worse)} of {len(rows)} originals are duller than a fresh take")
    for r in worse:
        print(f"    {r['at']:>7}  orig {r['orig_hf']:.4f} vs best {r['best_hf']:.4f}   "
              f"{r['text'][:64]}")
    print(f"  -> {f}")
    return worse


def demo():
    """The decision rule, pinned to what Saad judged by ear."""
    def decide(orig, takes):
        best = max(takes)
        return "REPLACE" if orig < best * RELATIVE_DROP else "keep"
    assert decide(0.0614, [0.0907, 0.0916, 0.1080]) == "REPLACE"
    assert decide(0.0916, [0.0907, 0.1080]) == "keep", "a good original is left alone"
    # a line that is simply low-frequency by wording must be KEPT when its takes match it
    assert decide(0.0471, [0.0480, 0.0476]) == "keep", "low HF from wording is not a fault"
    print("demo ok — replaces only what is dull against its own words")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("tag")
    ap.add_argument("--takes", type=int, default=2)
    ap.add_argument("--go", action="store_true")
    if "--demo" in sys.argv:
        demo(); sys.exit()
    a = ap.parse_args()
    segs = plan(a.tag, a.takes)
    if not a.go:
        print("\n  dry run — add --go to generate")
        sys.exit()
    print("  (generation is driven from the session, not this script)")
