#!/usr/bin/env python3
"""sa_tighten — rough-cut a talking-head clip: strip silences, fillers, repeated takes.

The missing piece all three reference videos (Jul 2026) converged on, built free/local:
faster-whisper word-level timestamps (no ElevenLabs key) + ffmpeg. Made for footage
like corporate interview shoots — one person to camera, multiple takes, dead air.

Review-first, like everything here: by default it writes a CUT PLAN (markdown +
JSON) for Saad to approve. --render actually produces the tightened MP4.

  python3 sa_tighten.py interview.mp4              # plan only
  python3 sa_tighten.py interview.mp4 --render     # plan + MP4
  ... [--gap 0.7] [--pad 0.15] [--model small] [--keep-fillers] [--no-retake-cut]

What gets cut:
  - silence gaps  > --gap seconds between words (tightened, not removed — a --pad
    breath is kept each side so cuts don't feel robotic)
  - filler words  standalone um/uh/erm/hmm ("like"/"you know" NOT cut — too risky)
  - repeated takes  consecutive near-duplicate sentences -> keep the LAST take
    (people re-say a line until they nail it; the last one is the keeper)

Runs whisper on CPU — one clip anytime is fine; a big folder batch is an
overnight job by the usual rule.
"""
import os, sys, json, difflib, argparse, subprocess

FFMPEG = os.path.expanduser("~/.local/bin/ffmpeg")
if not os.path.exists(FFMPEG):
    FFMPEG = "ffmpeg"

FILLERS = {"um", "uh", "erm", "uhh", "umm", "hmm", "mmm", "er", "ah"}


# ---------- pure logic (self-checked) ----------

def merge_ranges(ranges, join_gap=0.05):
    """Merge overlapping/adjacent [start,end] ranges. Pure."""
    out = []
    for s, e in sorted(ranges):
        if out and s <= out[-1][1] + join_gap:
            out[-1][1] = max(out[-1][1], e)
        else:
            out.append([s, e])
    return out


def plan_keeps(words, total_dur, gap=0.7, pad=0.15, cut_fillers=True):
    """words: [{"w": str, "start": float, "end": float}] -> keep-ranges + cut log.
    Silence between consecutive words longer than `gap` is tightened to 2*pad.
    Standalone filler words are dropped entirely. Pure function."""
    keeps, cuts = [], []
    if not words:
        return [[0.0, total_dur]], cuts

    spoken = []
    for w in words:
        token = w["w"].strip().lower().strip(".,!?…")
        if cut_fillers and token in FILLERS:
            cuts.append({"type": "filler", "at": round(w["start"], 2), "text": w["w"].strip()})
            continue
        spoken.append(w)
    if not spoken:
        return [[0.0, total_dur]], cuts

    cur_start = max(spoken[0]["start"] - pad, 0.0)
    prev_end = spoken[0]["end"]
    for w in spoken[1:]:
        if w["start"] - prev_end > gap:
            keeps.append([cur_start, prev_end + pad])
            cuts.append({"type": "silence", "at": round(prev_end, 2),
                         "dur": round(w["start"] - prev_end, 2)})
            cur_start = max(w["start"] - pad, 0.0)
        prev_end = max(prev_end, w["end"])
    keeps.append([cur_start, min(prev_end + pad, total_dur)])
    return merge_ranges(keeps), cuts


def drop_repeated_takes(segments, similarity=0.8):
    """segments: [{"text","start","end"}] -> (kept_segments, cut_log).
    Consecutive near-duplicate sentences: keep the LAST occurrence. Pure."""
    def norm(t):
        return " ".join(t.lower().strip().strip(".,!?…").split())
    kept, cuts = [], []
    i = 0
    while i < len(segments):
        j = i
        while (j + 1 < len(segments) and
               difflib.SequenceMatcher(None, norm(segments[j]["text"]),
                                        norm(segments[j + 1]["text"])).ratio() >= similarity):
            j += 1
        if j > i:
            for k in range(i, j):
                cuts.append({"type": "retake", "at": round(segments[k]["start"], 2),
                             "text": segments[k]["text"].strip()[:60]})
        kept.append(segments[j])
        i = j + 1
    return kept, cuts


def subtract_ranges(keeps, removals):
    """Remove `removals` time-ranges from `keeps` ranges. Pure."""
    out = keeps
    for rs, re_ in removals:
        nxt = []
        for s, e in out:
            if re_ <= s or rs >= e:
                nxt.append([s, e])
                continue
            if rs > s:
                nxt.append([s, rs])
            if re_ < e:
                nxt.append([re_, e])
        out = nxt
    return [r for r in out if r[1] - r[0] > 0.08]


# ---------- I/O ----------

def transcribe(path, model_name):
    from faster_whisper import WhisperModel
    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    segs, info = model.transcribe(path, word_timestamps=True)
    words, sentences = [], []
    for s in segs:
        sentences.append({"text": s.text, "start": s.start, "end": s.end})
        for w in (s.words or []):
            words.append({"w": w.word, "start": w.start, "end": w.end})
    return words, sentences, info.duration


def render(path, keeps, out_path):
    """Re-encode each keep-range, then concat. Precise (not keyframe-snapped)."""
    import tempfile, shutil
    tmp = tempfile.mkdtemp(prefix="tighten_")
    listfile = os.path.join(tmp, "list.txt")
    with open(listfile, "w") as lf:
        for i, (s, e) in enumerate(keeps):
            part = os.path.join(tmp, f"p{i:04d}.mp4")
            subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-ss", f"{s:.3f}",
                            "-to", f"{e:.3f}", "-i", path, "-c:v", "libx264",
                            "-preset", "fast", "-crf", "18", "-c:a", "aac",
                            "-b:a", "192k", part], check=True)
            lf.write(f"file '{part}'\n")
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                    "-i", listfile, "-c", "copy", out_path], check=True)
    shutil.rmtree(tmp, ignore_errors=True)
    return out_path


def write_html_timeline(base, vid, dur, kept_dur, keeps, cuts):
    """Editor-style review page: program track above, removed material drops to a bin lane."""
    from string import Template

    def pct(t):
        return "%.3f%%" % (t / dur * 100)

    def tc(t):
        return "%02d:%04.1f" % (int(t // 60), t % 60)

    retake_windows = []
    last = 0.0
    for s, e in keeps:
        if s > last:
            retake_windows.append((last, s))
        last = e
    if last < dur:
        retake_windows.append((last, dur))
    retake_starts = {round(c["at"], 1) for c in cuts if c["type"] == "retake"}

    def is_retake(gs, ge):
        return any(gs - 0.6 <= r <= ge + 0.6 for r in retake_starts)

    program, bin_lane, drops = [], [], []
    for i, (s, e) in enumerate(keeps):
        program.append(
            '<div class="k" tabindex="0" style="left:%s;width:%s" data-r="Clip %d &nbsp;·&nbsp; %s → %s &nbsp;·&nbsp; %.1fs kept"></div>'
            % (pct(s), pct(e - s), i + 1, tc(s), tc(e), e - s))
    for n, (gs, ge) in enumerate(retake_windows):
        kind = "retake" if is_retake(gs, ge) else "dead air"
        cls = "x r" if kind == "retake" else "x"
        bin_lane.append(
            '<div class="%s" tabindex="0" style="left:%s;width:%s;animation-delay:%ims" data-r="Removed %s &nbsp;·&nbsp; %s → %s &nbsp;·&nbsp; %.1fs"></div>'
            % (cls, pct(gs), pct(ge - gs), 120 + n * 35, kind, tc(gs), tc(ge), ge - gs))
        drops.append('<div class="dl" style="left:%s"></div>' % pct(gs + (ge - gs) / 2))

    rows = []
    for n, c in enumerate(cuts, 1):
        detail = c.get("text") or "%.1fs pause tightened" % c.get("dur", 0)
        badge = "retake" if c["type"] == "retake" else "silence"
        rows.append(
            "<tr><td>%03d</td><td><span class='b %s'>%s</span></td><td>%s</td><td>%s</td></tr>"
            % (n, badge, badge, tc(c["at"]), detail))

    ticks = "".join('<span style="left:%s">%s</span>' % (pct(t), tc(t))
                    for t in range(0, int(dur) + 1, max(10, round(dur / 7 / 10) * 10 or 10)))

    page = Template("""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Tighten · $name</title><style>
:root{--bg:#0A1F1B;--panel:#0D2823;--line:#17352D;--ink:#EAFFF6;--mut:#8FB7AB;
--go:#00E676;--keep:#1D9E75;--air:#F0997B;--take:#D4537E}
*{box-sizing:border-box;margin:0}
body{background:var(--bg);color:var(--ink);font-family:'Avenir Next',-apple-system,sans-serif;
max-width:960px;margin:0 auto;padding:48px 24px 64px}
.eyebrow{font-size:12px;letter-spacing:.18em;text-transform:uppercase;color:var(--go);font-weight:600}
h1{font-family:'Avenir Next Condensed','Avenir Next',sans-serif;font-weight:600;font-size:34px;margin:6px 0 2px}
.meta{color:var(--mut);font-size:14px}
.verdict{display:flex;align-items:baseline;gap:14px;margin:34px 0 10px;flex-wrap:wrap}
.verdict b{font-family:ui-monospace,'SF Mono',Menlo,monospace;font-size:52px;font-weight:600;color:var(--go);letter-spacing:-.02em}
.verdict span{color:var(--mut);font-size:15px}
.verdict .cutn{color:var(--air)}
.lane-label{font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--mut);margin:18px 0 6px}
.track{position:relative;height:64px;background:var(--panel);border:1px solid var(--line);border-radius:10px}
.k{position:absolute;top:7px;height:50px;background:var(--keep);border-radius:4px;border-top:2px solid #46E0A8;cursor:pointer}
.k:hover,.k:focus-visible{background:#27B98C;outline:2px solid var(--go);outline-offset:1px}
.bin{position:relative;height:44px;background:transparent;border:1px dashed var(--line);border-radius:10px;margin-top:26px}
.x{position:absolute;top:6px;height:32px;background:var(--air);border-radius:4px;opacity:.92;cursor:pointer;animation:drop .45s cubic-bezier(.2,.9,.3,1.2) backwards}
.x.r{background:var(--take)}
.x:hover,.x:focus-visible{outline:2px solid var(--ink);outline-offset:1px}
@keyframes drop{from{transform:translateY(-96px);opacity:0}to{transform:none;opacity:.92}}
@media (prefers-reduced-motion:reduce){.x{animation:none}}
.dl{position:absolute;top:64px;width:1px;height:26px;background:var(--line)}
.wrap{position:relative}
.ruler{position:relative;height:22px;margin-top:6px;font:11px ui-monospace,'SF Mono',Menlo,monospace;color:var(--mut)}
.ruler span{position:absolute;top:4px}
.readout{margin-top:14px;padding:10px 14px;background:var(--panel);border:1px solid var(--line);border-radius:8px;
font:13px ui-monospace,'SF Mono',Menlo,monospace;color:var(--mut);min-height:38px}
.readout em{color:var(--ink);font-style:normal}
h2{font-family:'Avenir Next Condensed','Avenir Next',sans-serif;font-weight:600;font-size:19px;margin:40px 0 10px}
table{width:100%;border-collapse:collapse;font:13px ui-monospace,'SF Mono',Menlo,monospace}
th{color:var(--mut);text-align:left;font-weight:500;font-size:11px;letter-spacing:.12em;text-transform:uppercase;
padding:8px 10px;border-bottom:1px solid var(--line)}
td{padding:8px 10px;border-bottom:1px solid var(--line);color:var(--ink);vertical-align:top}
td:first-child{color:var(--mut)}
.b{padding:2px 8px;border-radius:99px;font-size:11px;font-weight:600}
.b.silence{background:rgba(240,153,123,.16);color:var(--air)}
.b.retake{background:rgba(212,83,126,.18);color:var(--take)}
.next{margin-top:36px;padding:16px;border:1px solid var(--line);border-radius:10px;background:var(--panel)}
.next p{color:var(--mut);font-size:13px;margin-bottom:8px}
code{font:12.5px ui-monospace,'SF Mono',Menlo,monospace;color:var(--go);display:block;padding:2px 0;user-select:all}
legend,.legend{display:flex;gap:18px;font-size:12px;color:var(--mut);margin-top:10px}
.legend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:5px}
</style></head><body>
<p class="eyebrow">Tighten plan</p>
<h1>$name</h1>
<p class="meta">Whisper word-level pass · silences · fillers · repeated takes</p>
<div class="verdict"><b>$kept</b><span>survives of ${dur}s</span>
<span class="cutn">−${removed}s removed in $ncuts cuts</span></div>
<div class="wrap">
<p class="lane-label">Program — what stays</p>
<div class="track">$program $drops</div>
<div class="ruler">$ticks</div>
<p class="lane-label">Bin — what was lifted out</p>
<div class="bin">$binlane</div>
</div>
<div class="readout" id="ro">Hover or tab through any block — details appear here.</div>
<div class="legend"><span><i style="background:var(--keep)"></i>kept speech</span>
<span><i style="background:var(--air)"></i>dead air</span>
<span><i style="background:var(--take)"></i>repeated take</span></div>
<h2>Edit decision list</h2>
<table><tr><th>Event</th><th>Type</th><th>At</th><th>Detail</th></tr>$rows</table>
<div class="next"><p>Happy with the plan? Render it:</p>
<code>python3 sa_tighten.py "$src" --render</code></div>
<script>
var ro=document.getElementById('ro');
document.querySelectorAll('[data-r]').forEach(function(el){
  function show(){ro.innerHTML='<em>'+el.dataset.r+'</em>'}
  el.addEventListener('mouseenter',show);el.addEventListener('focus',show);});
</script></body></html>""")

    html = page.substitute(
        name=os.path.basename(vid), kept="%.1fs" % kept_dur, dur="%.1f" % dur,
        removed="%.1f" % (dur - kept_dur), ncuts=len(cuts),
        program="".join(program), binlane="".join(bin_lane), drops="".join(drops),
        ticks=ticks, rows="".join(rows), src=vid,
        json=base + "_tighten.json")
    open(base + "_tighten.html", "w").write(html)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--gap", type=float, default=0.7, help="silence longer than this is tightened")
    ap.add_argument("--pad", type=float, default=0.15, help="breath kept around each cut")
    ap.add_argument("--model", default="small", help="whisper model (base/small/medium)")
    ap.add_argument("--keep-fillers", action="store_true")
    ap.add_argument("--no-retake-cut", action="store_true")
    ap.add_argument("--render", action="store_true", help="produce the tightened MP4 too")
    a = ap.parse_args()

    vid = os.path.abspath(a.video)
    base = os.path.splitext(vid)[0]
    print(f"transcribing with faster-whisper ({a.model}, word timestamps)...")
    words, sentences, dur = transcribe(vid, a.model)
    print(f"  {len(words)} words, {len(sentences)} sentences, {dur:.1f}s")

    keeps, cuts = plan_keeps(words, dur, a.gap, a.pad, cut_fillers=not a.keep_fillers)

    if not a.no_retake_cut:
        kept_sents, retake_cuts = drop_repeated_takes(sentences)
        removals = []
        dropped = {(c["at"]) for c in retake_cuts}
        for s in sentences:
            if round(s["start"], 2) in dropped:
                removals.append([s["start"], s["end"]])
        keeps = subtract_ranges(keeps, removals)
        cuts += retake_cuts

    kept_dur = sum(e - s for s, e in keeps)
    plan = {"source": vid, "duration": round(dur, 2), "kept_duration": round(kept_dur, 2),
            "keeps": [[round(s, 3), round(e, 3)] for s, e in keeps], "cuts": cuts}
    json.dump(plan, open(base + "_tighten.json", "w"), indent=1)

    # Keep the transcript. Whisper has already done the expensive part and every downstream
    # step wants it — the script, the caption alignment, the step list. 12 Aug: the plan was
    # written without it and 23 minutes of audio had to be re-transcribed to get the words
    # back. Costs nothing to save; costs a CPU hour to recompute.
    json.dump({"source": vid, "duration": round(dur, 2),
               "words": [{"w": w["w"], "start": round(w["start"], 3),
                          "end": round(w["end"], 3)} for w in words],
               "sentences": sentences},
              open(base + "_transcript.json", "w"), indent=1)
    with open(base + "_transcript.txt", "w") as fh:
        for s in sentences:
            fh.write(f"[{s['start']:8.2f}] {s['text'].strip()}\n")
    print(f"  -> {os.path.basename(base)}_transcript.txt  (what he actually says, with times)")

    md = [f"# Tighten plan — {os.path.basename(vid)}",
          f"**{dur:.1f}s → {kept_dur:.1f}s** ({len(keeps)} kept ranges, {len(cuts)} cuts)\n",
          "| Cut | At | Detail |", "|---|---|---|"]
    for c in cuts:
        detail = c.get("text") or f"{c.get('dur', '')}s pause"
        md.append(f"| {c['type']} | {c['at']}s | {detail} |")
    open(base + "_tighten.md", "w").write("\n".join(md) + "\n")
    write_html_timeline(base, vid, dur, kept_dur, keeps, cuts)
    print(f"plan: {dur:.1f}s -> {kept_dur:.1f}s  ({len(cuts)} cuts)")
    print(f"  -> {base}_tighten.md (review this)")
    print(f"  -> {base}_tighten.html (visual timeline — double-click to open)")

    if a.render:
        out = base + "_tight.mp4"
        print("rendering...")
        render(vid, keeps, out)
        print(f"  -> {out}")
    else:
        print("  (--render to produce the MP4 after review)")


def _tests():
    W = lambda w, s, e: {"w": w, "start": s, "end": e}
    # silence tightening: 2s gap between words -> two keep ranges, one silence cut
    words = [W("hello", 0.2, 0.5), W("world", 0.6, 0.9), W("again", 3.0, 3.4)]
    keeps, cuts = plan_keeps(words, 4.0, gap=0.7, pad=0.1)
    assert len(keeps) == 2 and cuts[0]["type"] == "silence", (keeps, cuts)
    assert abs(keeps[0][0] - 0.1) < 1e-6 and abs(keeps[0][1] - 1.0) < 1e-6, keeps

    # filler removal
    words = [W("so", 0, 0.2), W("um", 0.3, 0.5), W("yes", 0.6, 0.8)]
    keeps, cuts = plan_keeps(words, 1.0, gap=5, pad=0.05)
    assert any(c["type"] == "filler" for c in cuts) and len(keeps) == 1

    # retake: three near-identical sentences -> keep last
    segs = [{"text": "I love good coffee.", "start": 0, "end": 2},
            {"text": "I love good coffee!", "start": 3, "end": 5},
            {"text": "I love a good coffee.", "start": 6, "end": 8},
            {"text": "Totally different line.", "start": 9, "end": 11}]
    kept, cuts = drop_repeated_takes(segs)
    assert len(kept) == 2 and kept[0]["start"] == 6 and len(cuts) == 2, (kept, cuts)

    # subtract_ranges: removing a middle chunk splits a keep
    out = subtract_ranges([[0, 10]], [[4, 6]])
    assert out == [[0, 4], [6, 10]], out

    print("sa_tighten self-checks: ok")


if __name__ == "__main__":
    if "--test" in sys.argv:
        _tests()
    else:
        main()
