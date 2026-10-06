#!/usr/bin/env python3
"""Cut every spoken line out to its own clip and build a listening sheet.

Why this and not a detector: six ways of finding the drifted lines automatically
were measured on 18 Aug against the five bad lines Saad already knew about in
one video. Five acoustic tests (spectral flatness, pitch, bandwidth collapse,
rolloff, MFCC timbre) separated nothing — every ratio sat between 0.90x and
1.09x. Transcription mismatch was the only one with signal, and calibrating it
across the whole series showed the trade is hopeless: tight enough to be
trustworthy it catches 1 line in 5; loose enough to catch 3 in 5 it flags 72% of
the series. A shortlist that flags three-quarters of the audio is not a
shortlist.

So: stop pretending to detect, and make Saad's ear fast instead. Every spoken
segment becomes a short clip he can play in one click, with the script beside it,
ordered so the weakest-scoring ones come first. 165 segments across a series is
about twenty minutes of clicking rather than scrubbing every timeline — and
whatever he ticks is the truth, which is what it always was.

Reads VOICE_CHECK.json (from sa_voicecheck.py). It runs locally and uploads nothing.

    sa_voiceclips.py            # all videos
    sa_voiceclips.py MOD01           # one
    sa_voiceclips.py MOD01,MOD02     # several
"""
import html
import json
import os
import pathlib
import subprocess
import sys

ADMIN = pathlib.Path(os.environ.get("TRAINING_ROOT", "~/Downloads/training-series")).expanduser() / "5 ADMIN"
CLIPS = ADMIN / "voice_clips"


def mmss(t):
    return f"{int(t//60)}:{int(t%60):02d}"


def cut(row, dst):
    """Extract exactly the stretch that plays in the video."""
    if dst.exists():
        return True
    r = subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", f"{row['src']:.3f}", "-t", f"{row['dur']:.3f}",
         "-i", row["path"], "-ac", "1", "-ar", "44100", "-b:a", "128k", "-y", str(dst)],
        capture_output=True)
    return r.returncode == 0 and dst.exists()


def build(only=None):
    rows = json.loads((ADMIN / "VOICE_CHECK.json").read_text())
    if only:
        want = {x.strip() for x in only.split(",")}
        rows = [r for r in rows if r["tag"] in want]
    CLIPS.mkdir(parents=True, exist_ok=True)
    # weakest first: a real mismatch outranks low confidence, but neither is trusted
    rows.sort(key=lambda r: (-r["wer"], r["logprob"]))
    out, made = [], 0
    for i, r in enumerate(rows):
        name = f"{r['tag']}_{int(r['t']//60):02d}m{int(r['t']%60):02d}s_{i:03d}.mp3"
        if not cut(r, CLIPS / name):
            continue
        made += 1
        out.append((name, r))
    esc = lambda s: html.escape(str(s or ""))
    body = "".join(f"""
<div class=r>
  <div class=hd><b>{esc(r['tag'])}</b> <span class=t>{mmss(r['t'])}</span>
    <span class=d>{r['dur']:.1f}s</span>
    <span class=sc>wer {r['wer']:.2f} · conf {r['logprob']:.2f}</span></div>
  <audio controls preload=none src="voice_clips/{esc(n)}"></audio>
  <div class=sx>{esc(r['intended'])[:300]}</div>
</div>""" for n, r in out)
    page = f"""<!doctype html><meta charset=utf-8><title>Voice listening sheet</title><style>
body{{background:#101114;color:#e8e9ec;font:14px/1.55 -apple-system,system-ui;margin:0;padding:24px;max-width:1000px;margin-inline:auto}}
h1{{font-size:20px;margin:0}} .w{{background:#2a1e12;border:1px solid #f5a623;border-radius:8px;padding:12px 14px;margin:14px 0;color:#f5c07a}}
.r{{border-bottom:1px solid #1d1f25;padding:12px 0}} .hd{{display:flex;gap:12px;align-items:baseline}}
.t{{color:#8b8d98;font-variant-numeric:tabular-nums}} .d{{color:#8b8d98;font-size:12px}}
.sc{{margin-left:auto;color:#6b6d78;font-size:12px;font-variant-numeric:tabular-nums}}
audio{{width:100%;margin:8px 0;height:32px}} .sx{{color:#a9abb4;font-size:13px}}
</style>
<h1>Voice listening sheet — {made} lines</h1>
<div class=w><b>There is no reliable automatic test for this.</b> Six methods were measured
against the five bad lines you already found in one video: five acoustic ones separated nothing,
and transcription either catches 1 in 5 or flags 72% of everything. So this is not a list of
faults — it is every spoken line, cut out and ordered weakest-first, so you can hear them
quickly. Tick the ones that drift and I will regenerate exactly those.</div>
{body}"""
    (ADMIN / "VOICE_LISTEN.html").write_text(page)
    print(f"  {made} clips -> {CLIPS}")
    print(f"  sheet      -> {ADMIN/'VOICE_LISTEN.html'}")


if __name__ == "__main__":
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    build(a[0] if a else None)
