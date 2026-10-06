#!/usr/bin/env python3
"""Pull the spoken transcript of each training video straight from its CapCut timeline.

Requirement (14 Aug, after exporting the series): a transcript for every video, by
name, covering only the in/out selection of each timeline.

In/out selection = only what is actually inside the finished cut. The captions ARE
the script, and every caption sitting on his caption line (y -0.892) is on screen
in the export — anything he ripple-deleted took its caption with it. So reading the
caption track gives the delivered wording, in order, with the times it appears.

Read-only. Writes plain .txt (one per video, plus a combined file) into 5 ADMIN/Transcripts/.

Requirement (14 Aug, second pass): no .md files and no timestamps, plain prose only,
because a course designer works from it. So the output is plain prose in .txt — the spoken script
only, ready to hand to whoever builds the course.

    sa_transcript.py            # all videos
    sa_transcript.py MOD03
"""
import argparse
import json
import os
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from sa_outro import draft_path, US

DRAFTS = pathlib.Path.home() / "Movies/CapCut/User Data/Projects/com.lveditor.draft"
SERIES = pathlib.Path(os.environ.get("TRAINING_ROOT", "~/Downloads/training-series")).expanduser()
OUT = SERIES / "5 ADMIN" / "Transcripts"

# tag -> (CapCut project folder, delivered title). A third element pins the timeline,
# because one project may hold several modules as separate timelines. Example entries;
# list your own series.
VIDEOS = {
 "MOD01": ("Example Pair", "Example Module One", "00000000-0000-0000-0000-000000000001"),
 "MOD02": ("Example Pair", "Example Module Two",
           "00000000-0000-0000-0000-000000000002"),
 "MOD03": ("MOD 03 Example", "Example Module Three"),
}
CAPTION_Y = -0.892


def mmss(t):
    return f"{int(t // 60)}:{int(t % 60):02d}"


def read(project, timeline=None):
    """-> (captions, title_lines, total_s). Only what is inside the cut."""
    dp = (DRAFTS / project / "Timelines" / timeline / "draft_info.json") if timeline else draft_path(project)
    d = json.loads(dp.read_text())
    txts = {m["id"]: m for m in (d.get("materials", {}).get("texts") or [])}
    export = (d.get("config") or {}).get("export_range") or {}
    export_start = int(export.get("start", 0))
    export_duration = int(export.get("duration", 0))
    if export_duration <= 0:
        export_duration = int(d.get("duration", 0))
    export_end = export_start + export_duration
    caps, titles = [], []
    for t in d["tracks"]:
        if t.get("visible") is False:
            continue
        for s in t.get("segments") or []:
            if s.get("visible") is False:
                continue
            g = s["target_timerange"]
            segment_start = int(g["start"])
            segment_end = segment_start + int(g["duration"])
            if segment_start >= export_end or segment_end <= export_start:
                continue
            clipped_start = max(segment_start, export_start)
            clipped_end = min(segment_end, export_end)
            m = txts.get(s.get("material_id"))
            if not m:
                continue
            try:
                c = json.loads(m.get("content", "{}"))
            except json.JSONDecodeError:
                continue
            text = (c.get("text") or "").strip()
            if not text:
                continue
            size = (c.get("styles") or [{}])[0].get("size") or 0
            y = ((s.get("clip") or {}).get("transform") or {}).get("y", 0)
            row = ((clipped_start - export_start) / US,
                   (clipped_end - export_start) / US, text)
            if size >= 10:
                titles.append(row)
            elif abs(y - CAPTION_Y) < 0.06:
                caps.append(row)
    return dedupe(sorted(caps)), sorted(titles), export_duration / US


def norm(t):
    return re.sub(r"[^a-z0-9 ]", "", t.lower()).strip()


def dedupe(caps):
    """Drop leftover auto-caption layers.

    One module carried an old auto-caption track ("first sign in with your username")
    on the same line as the real subtitles ("First, sign in with your username."),
    so every line came out twice. Where two captions overlap in time and one text
    contains the other, keep the properly punctuated one.
    """
    kept = []
    for a, b, text in caps:
        n = norm(text)
        replaced = False
        for i, (ka, kb, ktext) in enumerate(kept):
            if min(b, kb) - max(a, ka) <= 0:          # no time overlap
                continue
            kn = norm(ktext)
            if not (n in kn or kn in n):
                continue
            better = text if (text[:1].isupper() or text.rstrip()[-1:] in ".,!?") else ktext
            kept[i] = (min(a, ka), max(b, kb), better if len(better) >= len(ktext) else ktext)
            replaced = True
            break
        if not replaced:
            kept.append((a, b, text))
    return sorted(kept)


def paragraphs(caps, gap=1.1):
    """Join caption fragments into readable sentences; a real pause starts a new one."""
    out, cur, start = [], [], None
    prev_end = None
    for a, b, text in caps:
        if start is None:
            start = a
        elif prev_end is not None and a - prev_end > gap and cur:
            out.append((start, prev_end, " ".join(cur)))
            cur, start = [], a
        cur.append(text)
        prev_end = b
        joined = " ".join(cur)
        if re.search(r"[.!?]$", text) and len(joined) > 90:
            out.append((start, b, joined))
            cur, start, prev_end = [], None, None
    if cur:
        out.append((start, prev_end, " ".join(cur)))
    return out


def build(tag):
    entry = VIDEOS[tag]
    project, title = entry[0], entry[1]
    timeline = entry[2] if len(entry) > 2 else None
    caps, titles, end = read(project, timeline)
    paras = paragraphs(caps)
    words = sum(len(t.split()) for _a, _b, t in caps)
    lines = [title.upper(), "=" * len(title), ""]
    for _a, _b, text in paras:
        lines.append(text)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n", {
        "tag": tag, "title": title, "project": project,
        "runtime_s": round(end, 2), "caption_count": len(caps), "word_count": words,
        "speech_in_s": round(caps[0][0], 2) if caps else None,
        "speech_out_s": round(caps[-1][1], 2) if caps else None,
        "title_card": [t for _a, _b, t in titles],
        "captions": [{"in": round(a, 2), "out": round(b, 2), "text": t} for a, b, t in caps],
        "paragraphs": [{"in": round(a, 2), "out": round(b, 2), "text": t} for a, b, t in paras],
    }


def main(only=None, out_dir=OUT):
    out_dir = pathlib.Path(out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*.md"):
        old.unlink()
    allmd, alljson = ["TRAINING VIDEO SCRIPTS", "", ""], []
    for tag in VIDEOS:
        if only and only != tag:
            continue
        try:
            md, data = build(tag)
        except FileNotFoundError:
            print(f"  {tag:<7} project folder not found"); continue
        (out_dir / f"{tag}.txt").write_text(md)
        allmd.append(md); allmd.append("\n")
        alljson.append(data)
        print(f"  {tag:<7} {data['word_count']:>5} words  {mmss(data['runtime_s'])}  -> {tag}.txt")
    (out_dir / "ALL_SCRIPTS.txt").write_text("\n".join(allmd))
    (out_dir / "ALL_TRANSCRIPTS.json").write_text(json.dumps(alljson, indent=1, ensure_ascii=False))
    print(f"\n-> {out_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("only", nargs="?", choices=VIDEOS.keys())
    parser.add_argument("--out", default=str(OUT), help="output directory")
    args = parser.parse_args()
    main(args.only, args.out)
