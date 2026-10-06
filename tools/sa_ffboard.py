#!/usr/bin/env python3
"""Build FFMPEG_MATCH.html — did the ffmpeg renders reach Saad's style?

Pairs the arithmetic (5 ADMIN/ffmpeg_match_report.json) with real frames pulled
from each render, so Saad can judge the look in one scroll rather than opening every
file. Frames are embedded as data URIs, so the page is one self-contained local
file; building it runs locally and uploads nothing.

    sa_ffboard.py --renders /tmp/ffall
"""
import argparse
import base64
import json
import os
import pathlib
import subprocess
import sys

ADMIN = pathlib.Path(os.environ.get("TRAINING_ROOT", "~/Downloads/training-series")).expanduser() / "5 ADMIN"
# build tag -> display name shown on each card (example entries; one per video in the series)
NAME = {"T01": "Sign In and Navigation", "T02": "Create a Record"}


def frame(video, t, width=760):
    """One frame as a data URI, or None."""
    r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", str(video),
                        "-frames:v", "1", "-vf", f"scale={width}:-2", "-f", "image2pipe",
                        "-vcodec", "mjpeg", "-q:v", "4", "-"], capture_output=True)
    if not r.stdout:
        return None
    return "data:image/jpeg;base64," + base64.b64encode(r.stdout).decode()


def card(r):
    tag = r["tag"]
    if "error" in r:
        return (f'<div class="card"><div class="h bad"><b>{tag}</b> — did not render</div>'
                f'<pre>{r["error"][:400]}</pre></div>')
    f = pathlib.Path(r["file"])
    # a caption moment (a quarter in) and the outro
    shots = [s for s in (frame(f, r["render_s"] * 0.25), frame(f, r["render_s"] - 4.0)) if s]
    imgs = "".join(f'<img src="{s}">' for s in shots)
    ok = r["duration_ok"] and r["captions_visible"] == r["captions_sampled"]
    return f"""
<div class="card">
  <div class="h {'good' if ok else 'warn'}">
    <b>{tag}</b> <span class="nm">{NAME.get(tag,'')}</span>
    <span class="r">{r['render_s']:.2f}s / timeline {r['timeline_s']:.2f}s</span>
  </div>
  <div class="m">
    <span class="{'y' if r['duration_ok'] else 'n'}">duration {'exact' if r['duration_ok'] else 'off'}</span>
    <span class="{'y' if r['captions_visible']==r['captions_sampled'] else 'n'}">captions {r['captions_visible']}/{r['captions_sampled']}</span>
    <span class="{'y' if r['outro_dark'] else 'n'}">outro {'present' if r['outro_dark'] else 'not seen'}</span>
    <span class="y">voice {r['voice_db']} dB</span>
    <span class="g">{r['callouts']} call-outs · {r['texts']} text</span>
  </div>
  <div class="shots">{imgs}</div>
</div>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--renders", default="/tmp/ffall")
    a = ap.parse_args()
    rows = json.loads((ADMIN / "ffmpeg_match_report.json").read_text())
    ok = sum(1 for r in rows if r.get("duration_ok"))
    cards = "".join(card(r) for r in rows)
    page = f"""<!doctype html><html><head><meta charset="utf-8">
<title>ffmpeg vs your CapCut style</title><style>
body{{background:#101114;color:#e8e9ec;font:15px/1.55 -apple-system,system-ui;margin:0;padding:26px 18px 70px;max-width:900px;margin-inline:auto}}
h1{{font-size:21px;margin:0}} .sub{{color:#8b8d98;margin:6px 0 20px}}
.card{{background:#17181c;border:1px solid #24262c;border-radius:12px;margin:14px 0;overflow:hidden}}
.h{{padding:11px 15px;background:#1b1d22;border-left:6px solid #30a46c}}
.h.warn{{border-left-color:#f5a623}} .h.bad{{border-left-color:#e5484d}}
.nm{{color:#a9abb4;margin-left:6px}} .r{{float:right;color:#8b8d98;font-variant-numeric:tabular-nums}}
.m{{padding:10px 15px;display:flex;flex-wrap:wrap;gap:8px;font-size:12.5px}}
.m span{{border:1px solid #2a2c33;border-radius:20px;padding:2px 10px}}
.y{{color:#30a46c;border-color:#30a46c!important}} .n{{color:#e5484d;border-color:#e5484d!important}}
.g{{color:#8b8d98}}
.shots{{display:flex;gap:8px;padding:0 15px 14px;overflow-x:auto}} .shots img{{width:48%;border-radius:6px;flex:none}}
pre{{margin:10px 15px;color:#e5484d;font-size:12px;white-space:pre-wrap}}
</style></head><body>
<h1>ffmpeg rendering of your timelines</h1>
<div class="sub">Overnight experiment · each video re-rendered straight from its CapCut
timeline with ffmpeg — no CapCut involved, and nothing in your projects touched.
<b>{ok} of {len(rows)}</b> match the timeline length exactly. Frames below are from the ffmpeg renders.</div>
{cards}
</body></html>"""
    out = ADMIN / "FFMPEG_MATCH.html"
    out.write_text(page)
    print(f"-> {out}  ({len(page)//1024} KB)")


if __name__ == "__main__":
    main()
