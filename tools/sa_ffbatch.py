#!/usr/bin/env python3
"""Render every mapped project with ffmpeg and check each one against its timeline.

The overnight experiment Saad asked for on 14 Aug: match the house style with ffmpeg
and compare, without touching any CapCut project. Read-only on his drafts; output
goes to --out.

The comparison is arithmetic, not opinion. For each video it asks:
  duration   does the render last exactly as long as the timeline says?
  captions   at the midpoint of each caption, is there ink in the caption band?
  outro      is the last second dark, the way his outro ends?
  voice      does the audio carry speech at his level (-1.1 to -30 dB)?

    sa_ffbatch.py --out /tmp/ffall
    sa_ffbatch.py --out /tmp/ffall --only MOD01
"""
import argparse
import json
import os
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from sa_ffrender import read_spec, render
from sa_import import PROJECT

ADMIN = pathlib.Path(os.environ.get("TRAINING_ROOT", "~/Downloads/training-series")).expanduser() / "5 ADMIN"


def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", str(path)], capture_output=True, text=True).stdout.strip()
    return float(out) if out else 0.0


def band_ink(video, t, H):
    """Edge energy in the caption band at time t — captions live near the bottom."""
    r = subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", str(video), "-frames:v", "1",
         "-vf", f"crop=iw:{round(H*0.12)}:0:{round(H*0.86)},edgedetect=low=0.1:high=0.3",
         "-f", "rawvideo", "-pix_fmt", "gray", "-"], capture_output=True).stdout
    return sum(r) / len(r) / 255 if r else 0.0


def mean_grey(video, t):
    r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", str(video),
                        "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                       capture_output=True).stdout
    return sum(r) / len(r) if r else 0.0


def voice_db(video):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(video), "-af", "volumedetect",
                        "-f", "null", "-"], capture_output=True, text=True).stderr
    for line in r.splitlines():
        if "mean_volume" in line:
            return float(line.split(":")[-1].replace("dB", "").strip())
    return None


def check(spec, out_path):
    """-> dict of measured agreement between the render and the timeline."""
    want = spec["end"] + (spec["outro"]["dur"] if spec["outro"] else 0)
    got = probe(out_path)
    H = spec["H"]
    # Pick captions by POSITION, not size: a title line is 28px too, and picking by px
    # sampled one video's title card and then looked for it in the caption band, where it
    # was never going to be. Captions are the ones sitting on the y -0.892 line.
    caps = [t for t in spec["texts"] if abs(t["y"] + 0.892) < 0.06 and t["text"].strip()]
    step = max(1, len(caps) // 8)
    sampled = caps[::step][:8]
    # A one-word caption ("customer.", "stage.") lays down a fraction of the ink of a full
    # line, so a flat threshold called four correct renders a miss. Scale it with length.
    def seen(c):
        floor = 0.004 * min(1.0, len(c["text"]) / 24)
        return band_ink(out_path, c["t"] + c["dur"] / 2, H) > max(floor, 0.0012)
    hits = sum(1 for c in sampled if seen(c))
    return {
        "timeline_s": round(want, 2), "render_s": round(got, 2),
        "duration_ok": abs(got - want) < 0.1,
        "captions_sampled": len(sampled), "captions_visible": hits,
        "outro_dark": (mean_grey(out_path, want - 1.0) < 60) if spec["outro"] else None,
        "voice_db": voice_db(out_path),
        "callouts": len(spec["overlays"]), "texts": len(spec["texts"]),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="/tmp/ffall")
    ap.add_argument("--only")
    ap.add_argument("--check-only", action="store_true",
                    help="re-verify existing renders without re-rendering")
    a = ap.parse_args()
    rows = []
    for tag, project in PROJECT.items():
        if a.only and a.only != tag:
            continue
        try:
            spec = read_spec(project)
            if a.check_only:
                out = pathlib.Path(a.out) / f"{project.replace(' ', '_')}_ffmpeg.mp4"
                if not out.exists():
                    print(f"  {tag:<7} no render"); continue
            else:
                out = render(spec, a.out)
            res = check(spec, out)
            res["tag"] = tag
            res["file"] = str(out)
            rows.append(res)
            print(f"  {tag:<7} {res['render_s']:>7.2f}s vs {res['timeline_s']:>7.2f}s "
                  f"{'ok ' if res['duration_ok'] else 'OFF'}  "
                  f"captions {res['captions_visible']}/{res['captions_sampled']}  "
                  f"outro {'dark' if res['outro_dark'] else '-'}  "
                  f"voice {res['voice_db']}dB")
        except Exception as e:
            rows.append({"tag": tag, "error": str(e)[:300]})
            print(f"  {tag:<7} ERROR {str(e)[:80]}")
    ADMIN.mkdir(exist_ok=True)
    (ADMIN / "ffmpeg_match_report.json").write_text(json.dumps(rows, indent=1))
    ok = sum(1 for r in rows if r.get("duration_ok"))
    print(f"\n{ok}/{len(rows)} match the timeline duration exactly")
    print(f"-> {ADMIN / 'ffmpeg_match_report.json'}")


if __name__ == "__main__":
    main()
