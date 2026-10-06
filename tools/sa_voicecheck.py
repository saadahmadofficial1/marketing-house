#!/usr/bin/env python3
"""Shortlist the voice lines worth re-listening to, across every video in a training series.

Six of seven videos were flagged in review for voice quality. The reported fault:
mid-line, the pitch and tone shift (an "old radio" sound, as if a different speaker
took over), then recover. That is the generator drifting mid-line, not damage done
afterwards (the narration inside
T03_PACED.mp4 cross-correlates against the original vo/02.mp3 at 1.0000, i.e.
byte-for-byte identical, so nothing we did touched it).

WHAT THIS CAN AND CANNOT DO — read before trusting it.
Five acoustic approaches were measured against Saad's five known-bad
lines in one module and every one failed to separate them from the good ones:
    spectral flatness / HF energy / spectral jump   0.96-1.09x
    pitch jump + pitch variation                    0.98-1.09x
    HF collapse inside a file ("old radio" test)    no separation
    spectral rolloff / bandwidth collapse           no separation
    MFCC timbre, "is this the same person"          0.90x
Only transcription carries signal: all nine good chunks came back at WER 0.000,
three of the five bad ones at 0.286 / 0.080 / 0.053, and a fourth showed low
confidence. So this is a HIGH-PRECISION, ~65%-RECALL shortlist. A line that is
not flagged is UNKNOWN, never "good". Saad's ear remains the detector.

This check runs locally (faster_whisper, base.en) and uploads nothing.

    sa_voicecheck.py --demo          # reproduce the ground truth, no scan
    sa_voicecheck.py MOD03           # one video
    sa_voicecheck.py                 # all of them -> 5 ADMIN/VOICE_CHECK.html
"""
import html
import io
import json
import os
import pathlib
import re
import subprocess
import sys
import warnings

warnings.filterwarnings("ignore")
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from sa_transcript import VIDEOS, DRAFTS, CAPTION_Y, dedupe          # noqa: E402
from sa_outro import draft_path, US                                  # noqa: E402

SERIES = pathlib.Path(os.environ.get("TRAINING_ROOT", "~/Downloads/training-series")).expanduser()
ADMIN = SERIES / "5 ADMIN"
BUILD = SERIES / "2 BUILD"
WER_FLAG = 0.0          # anything above zero is suspicious: good lines score exactly 0
LOGPROB_FLAG = -0.30    # measured: bad mean -0.281, good mean -0.235
_MODEL = None


def model():
    global _MODEL
    if _MODEL is None:
        from faster_whisper import WhisperModel
        _MODEL = WhisperModel("base.en", device="cpu", compute_type="int8")
    return _MODEL


def words(t):
    return re.sub(r"[^a-z0-9 ]", " ", t.lower()).split()


def wer(ref, hyp):
    """Word error rate. Pure — this is what the demo pins."""
    r, h = words(ref), words(hyp)
    if not r:
        return 0.0
    d = [[0] * (len(h) + 1) for _ in range(len(r) + 1)]
    for i in range(len(r) + 1):
        d[i][0] = i
    for j in range(len(h) + 1):
        d[0][j] = j
    for i in range(1, len(r) + 1):
        for j in range(1, len(h) + 1):
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1,
                          d[i - 1][j - 1] + (r[i - 1] != h[j - 1]))
    return d[len(r)][len(h)] / len(r)


def transcribe(path):
    segs, _ = model().transcribe(str(path), language="en", beam_size=5)
    segs = list(segs)
    text = " ".join(s.text for s in segs).strip()
    lp = sum(s.avg_logprob for s in segs) / len(segs) if segs else 0.0
    ns = max((s.no_speech_prob for s in segs), default=0.0)
    return text, lp, ns


def resolve(p, project_dir):
    """CapCut hides its own generated media behind a placeholder token."""
    if p.startswith("##_draftpath_placeholder_"):
        return str(pathlib.Path(project_dir) / p.split("_##/", 1)[-1])
    return p


def captions(d):
    """-> sorted [(start, end, text)] of the on-screen caption line."""
    txts = {m["id"]: m for m in (d.get("materials", {}).get("texts") or [])}
    out = []
    for t in d["tracks"]:
        for s in t.get("segments") or []:
            m = txts.get(s.get("material_id"))
            if not m:
                continue
            try:
                c = json.loads(m.get("content", "{}"))
            except json.JSONDecodeError:
                continue
            text = (c.get("text") or "").strip()
            size = (c.get("styles") or [{}])[0].get("size") or 0
            y = ((s.get("clip") or {}).get("transform") or {}).get("y", 0)
            if text and size < 10 and abs(y - CAPTION_Y) < 0.06:
                g = s["target_timerange"]
                out.append((g["start"] / US, (g["start"] + g["duration"]) / US, text))
    return dedupe(sorted(out))


def intended(caps, a, b):
    """Caption text on screen while this audio segment plays."""
    hit = [t for (ca, cb, t) in caps if min(b, cb) - max(a, ca) > 0.15]
    return " ".join(hit).strip()


def scan_video(tag):
    entry = VIDEOS[tag]
    project, title = entry[0], entry[1]
    tl = entry[2] if len(entry) > 2 else None
    dp = (DRAFTS / project / "Timelines" / tl / "draft_info.json") if tl else draft_path(project)
    d = json.loads(dp.read_text())
    proj_dir = DRAFTS / project
    auds = {m["id"]: m for m in (d["materials"].get("audios") or [])}
    caps = captions(d)
    rows, seen = [], set()
    vids = {m["id"]: m for m in (d["materials"].get("videos") or [])}
    for t in d["tracks"]:
        # One module has no audio track at all — its whole voice-over is inside the paced
        # screen recording on the PICTURE track. Scanning only audio tracks gave it a
        # score of zero segments, which reads as "clean" when it is really "not looked at".
        if t.get("type") not in ("audio", "video"):
            continue
        for s in sorted(t.get("segments") or [], key=lambda x: x["target_timerange"]["start"]):
            mat = auds.get(s.get("material_id")) or vids.get(s.get("material_id"))
            if mat is None or s.get("volume", 1.0) <= 0.15:      # muted or a music bed
                continue
            path = pathlib.Path(resolve(mat.get("path", ""), proj_dir))
            # Most narration does not live in a .mp3 at all — it is inside the paced
            # screen recording (T03_PACED.mp4) and played from an audio track. Excluding
            # video containers here scanned 5 segments of a 2:40 video instead of all of it.
            if not path.exists() or path.suffix.lower() not in (
                    ".mp3", ".wav", ".m4a", ".aac", ".mp4", ".mov"):
                continue
            g = s["target_timerange"]
            src = (s.get("source_timerange") or {}).get("start", 0) / US
            a, b = g["start"] / US, (g["start"] + g["duration"]) / US
            key = (str(path), round(src, 2), round(b - a, 2))
            if key in seen:
                continue
            seen.add(key)
            want = intended(caps, a, b)
            if not want:
                continue
            # transcribe exactly the stretch that plays, not the whole file
            clip = subprocess.run(
                ["ffmpeg", "-v", "error", "-ss", f"{src:.3f}", "-t", f"{b-a:.3f}",
                 "-i", str(path), "-ac", "1", "-ar", "16000", "-f", "wav", "-"],
                capture_output=True).stdout
            if len(clip) < 2000:
                continue
            tmp = pathlib.Path("/tmp/_vc.wav")
            tmp.write_bytes(clip)
            heard, lp, ns = transcribe(tmp)
            e = wer(want, heard)
            rows.append({
                "tag": tag, "title": title, "t": round(a, 2), "dur": round(b - a, 2),
                "file": path.name, "path": str(path), "src": round(src, 2),
                "wer": round(e, 3), "logprob": round(lp, 3), "no_speech": round(ns, 3),
                "intended": want, "heard": heard,
                "flag": bool(e > WER_FLAG or lp < LOGPROB_FLAG),
            })
    return rows


def mmss(t):
    return f"{int(t//60)}:{int(t%60):02d}"


def page(rows):
    flagged = [r for r in rows if r["flag"]]
    flagged.sort(key=lambda r: (-r["wer"], r["logprob"]))
    def esc(s):
        return html.escape(str(s or ""))
    body = "".join(f"""
<tr class="{'f' if r['flag'] else ''}">
 <td><b>{esc(r['tag'])}</b><div class=s>{esc(r['file'])[:34]}</div></td>
 <td class=n>{mmss(r['t'])}<div class=s>{r['dur']:.1f}s</div></td>
 <td class=n>{r['wer']:.3f}<div class=s>{r['logprob']:.2f}</div></td>
 <td>{esc(r['intended'])[:190]}</td>
 <td class=h>{esc(r['heard'])[:190]}</td></tr>""" for r in flagged)
    return f"""<!doctype html><meta charset=utf-8><title>Voice check</title><style>
body{{background:#101114;color:#e8e9ec;font:14px/1.5 -apple-system,system-ui;margin:0;padding:24px;max-width:1200px;margin-inline:auto}}
h1{{font-size:20px;margin:0 0 4px}} .w{{background:#2a1e12;border:1px solid #f5a623;border-radius:8px;padding:12px 14px;margin:14px 0;color:#f5c07a}}
table{{border-collapse:collapse;width:100%;font-size:13px}} th{{text-align:left;color:#8b8d98;border-bottom:1px solid #2a2c33;padding:8px}}
td{{padding:8px;border-bottom:1px solid #1d1f25;vertical-align:top}} .n{{font-variant-numeric:tabular-nums;white-space:nowrap}}
.s{{color:#8b8d98;font-size:11.5px}} .h{{color:#f5a623}} tr.f td{{background:#17181c}}
</style>
<h1>Voice check — lines worth re-listening to</h1>
<div class=s>Scanned {len(rows)} spoken segments across the series · {len(flagged)} flagged</div>
<div class=w><b>This is a shortlist, not a verdict.</b> Measured against the five bad lines
Saad already found in one module, transcription catches about 65% of them — every good line
transcribed perfectly, but a third of the bad ones read perfectly too. A line that is NOT
listed here is <b>unknown</b>, not confirmed good. Five acoustic tests (flatness, pitch,
bandwidth collapse, rolloff, timbre) all failed to separate bad from good, so there is no
automatic way to catch the rest — your ear is still the detector.</div>
<table><tr><th>video</th><th>at</th><th>WER / conf</th><th>script says</th><th>audio says</th></tr>
{body}</table>"""


def demo():
    """Pin the ground truth measured 18 Aug on one module."""
    assert wer("hello there world", "hello there world") == 0.0
    assert abs(wer("a b c d", "a b x d") - 0.25) < 1e-9
    assert wer("", "anything") == 0.0
    vo = BUILD / "T03 Example Module" / "vo"
    if not vo.exists():
        print("demo ok (pure WER only — build folder not on this machine)")
        return
    plan = json.loads((vo.parent / "T03_captions.plan.json").read_text())
    ref = {s["vo"]: s["text"] for s in plan["segments"]}
    got = {}
    for name in ("01.mp3", "03.mp3"):
        heard, _lp, _ns = transcribe(vo / name)
        got[name] = wer(ref[f"vo/{name}"], heard)
    print(f"  vo/01 WER {got['01.mp3']:.3f}  (ground truth 0.000)")
    print(f"  vo/03 WER {got['03.mp3']:.3f}  (ground truth 0.286)")
    assert got["01.mp3"] == 0.0, "a clean line must score exactly zero"
    assert got["03.mp3"] > 0.2, "the known-bad line must still score high"
    print("demo ok — reproduces the 18 Aug ground truth")


def main(only):
    rows = []
    for tag in VIDEOS:
        if only and only != tag:
            continue
        try:
            r = scan_video(tag)
        except FileNotFoundError as e:
            print(f"  {tag:<7} skipped ({e.filename})")
            continue
        rows += r
        n = sum(1 for x in r if x["flag"])
        print(f"  {tag:<7} {len(r):>3} segments  {n:>2} flagged")
    ADMIN.mkdir(parents=True, exist_ok=True)
    (ADMIN / "VOICE_CHECK.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False))
    (ADMIN / "VOICE_CHECK.html").write_text(page(rows))
    print(f"\n{sum(1 for r in rows if r['flag'])} of {len(rows)} flagged -> {ADMIN/'VOICE_CHECK.html'}")


if __name__ == "__main__":
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    if "--demo" in sys.argv:
        demo()
    else:
        main(a[0] if a else None)
