#!/usr/bin/env python3
"""Step 1 of the voice refresh: cut every line's ORIGINAL audio and measure it.

The comparison that works is original-vs-fresh-takes of the SAME words (see
sa_hfcheck). So the job splits in three: this script cuts and measures the
originals, the session generates fresh takes through the API, and sa_voicepick
compares and names the winners.

Screening is one take per line, not two — a single fresh take of the same words
is enough to tell whether the original is the dull one. A second take is only
worth generating for the lines that fail, to choose between them.

    sa_voiceplan.py MOD03              # -> work list + original HF
    sa_voiceplan.py --all --skip MOD01,MOD02
"""
import argparse
import json
import os
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from sa_voicecheck import captions, resolve                 # noqa: E402
from sa_transcript import VIDEOS, DRAFTS                    # noqa: E402
from sa_outro import draft_path, US                         # noqa: E402
from sa_hfcheck import hf_ratio                             # noqa: E402

WORK = pathlib.Path(os.environ.get("TRAINING_ROOT", "~/Downloads/training-series")).expanduser() / "5 ADMIN" / "voice_work"
MIN_WORDS = 2          # "displayed." on its own is not worth a generation
MIN_DUR = 0.8


def spans_of(d, proj):
    """Timeline -> (file, source offset) for everything that carries voice."""
    auds = {m["id"]: m for m in (d["materials"].get("audios") or [])}
    vids = {m["id"]: m for m in (d["materials"].get("videos") or [])}
    out = []
    for t in d["tracks"]:
        if t.get("type") not in ("audio", "video"):
            continue
        for s in t.get("segments") or []:
            mat = auds.get(s.get("material_id")) or vids.get(s.get("material_id"))
            if not mat or s.get("volume", 1.0) <= 0.15:
                continue
            p = pathlib.Path(resolve(mat.get("path", ""), DRAFTS / proj))
            if p.suffix.lower() not in (".mp3", ".wav", ".mp4", ".mov") or not p.exists():
                continue
            g = s["target_timerange"]
            out.append((g["start"] / US, (g["start"] + g["duration"]) / US,
                        (s.get("source_timerange") or {}).get("start", 0) / US, p))
    return out


def plan_video(tag):
    entry = VIDEOS[tag]
    proj, tl = entry[0], (entry[2] if len(entry) > 2 else None)
    dp = (DRAFTS / proj / "Timelines" / tl / "draft_info.json") if tl else draft_path(proj)
    d = json.loads(dp.read_text())
    spans = spans_of(d, proj)
    orig_dir = WORK / tag / "original"
    orig_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for i, (a, b, txt) in enumerate(captions(d)):
        if len(txt.split()) < MIN_WORDS or (b - a) < MIN_DUR:
            continue
        cover = [s for s in spans if s[0] <= a + 0.05 and s[1] >= b - 0.05]
        if not cover:
            continue
        s0, _s1, src, p = cover[0]
        f = orig_dir / f"{i:03d}.mp3"
        if not f.exists():
            subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{src + (a - s0):.3f}",
                            "-t", f"{b - a:.3f}", "-i", str(p), "-ac", "1", "-ar", "44100",
                            "-b:a", "128k", "-y", str(f)], capture_output=True)
        h = hf_ratio(f) if f.exists() else None
        if h is None:
            continue
        rows.append({"i": i, "tag": tag, "t": round(a, 2), "dur": round(b - a, 2),
                     "text": txt, "orig_hf": round(h, 4), "orig": str(f)})
    (WORK / tag / "plan.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False))
    print(f"  {tag:<7} {len(rows):>3} lines to screen   (~{len(rows)*0.3:.0f} credits for one take each)")
    return rows


def demo():
    assert MIN_WORDS >= 2 and MIN_DUR >= 0.5
    print("demo ok")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("tag", nargs="?")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--skip", default="")
    if "--demo" in sys.argv:
        demo(); sys.exit()
    a = ap.parse_args()
    skip = {x.strip() for x in a.skip.split(",") if x.strip()}
    tags = [t for t in VIDEOS if t not in skip] if a.all else [a.tag]
    total = 0
    for t in tags:
        try:
            total += len(plan_video(t))
        except Exception as e:
            print(f"  {t:<7} skipped: {str(e)[:70]}")
    print(f"\n  {total} lines total  ~{total*0.3:.0f} credits to screen with one take each")
