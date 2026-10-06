#!/usr/bin/env python3
"""sa_srtexport — pull subtitles and a clean transcript OUT of a CapCut project.

CapCut would not export an SRT on this setup (found 10 Aug), and a course is being
written from these videos, so the words have to come out of the draft itself — the
live state he has edited, not the build-time SRT, which no longer matches.

    Tools/venv/bin/python3 Tools/sa_srtexport.py                 # every training project
    Tools/venv/bin/python3 Tools/sa_srtexport.py "Training 01 Example"
    Tools/venv/bin/python3 Tools/sa_srtexport.py --test

Writes <project>.srt and <project> (transcript).txt into 5 ADMIN/Captions/.
Read-only on the projects. Hidden cues are skipped — they are not in the video, and a
course written from a hidden line would describe something the viewer never sees.
"""
import argparse
import glob
import json
import os
import pathlib
import re
import sys

US = 1_000_000
CAPCUT = pathlib.Path("~/Movies/CapCut/User Data/Projects/com.lveditor.draft").expanduser()
OUT = pathlib.Path(os.environ.get("TRAINING_ROOT", "~/Downloads/training-series")).expanduser() / "5 ADMIN" / "Captions"
SERIES_PREFIX = os.environ.get("SERIES_PREFIX", "Training ")   # CapCut project names in the series
CAPTION_SIZE = 5          # his locked caption size; titles are 18, labels vary


def cues_of(draft, caption_size=CAPTION_SIZE):
    """Pure: draft -> [(start, end, text)] of the VISIBLE caption cues, in order."""
    texts = {m["id"]: m for m in draft["materials"].get("texts", [])}
    out = []
    for t in draft.get("tracks", []):
        for s in t.get("segments", []):
            if s.get("visible") is False:
                continue
            m = texts.get(s.get("material_id"))
            if not m:
                continue
            try:
                c = json.loads(m.get("content") or "{}")
            except (json.JSONDecodeError, TypeError):
                continue
            styles = c.get("styles") or [{}]
            if styles[0].get("size") != caption_size:
                continue
            txt = (c.get("text") or "").strip()
            if not txt:
                continue
            tr = s["target_timerange"]
            out.append((tr["start"] / US, (tr["start"] + tr["duration"]) / US, txt))
    return sorted(out)


def stamp(x):
    h, rem = divmod(x, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int(round((s - int(s)) * 1000)):03d}"


def srt_text(cues):
    """Pure: cues -> SRT. Overlaps are trimmed so no two subtitles show at once."""
    fixed = []
    for i, (a, b, t) in enumerate(cues):
        if i + 1 < len(cues) and b > cues[i + 1][0]:
            b = cues[i + 1][0]
        if b - a < 0.2:                     # a cue too short to read is still shown
            b = a + 0.2
        fixed.append((a, b, t))
    return "\n".join(f"{i}\n{stamp(a)} --> {stamp(b)}\n{t}\n"
                     for i, (a, b, t) in enumerate(fixed, 1))


def transcript_text(cues, title=""):
    """Pure: cues -> paragraphs, joined at sentence ends (the course-writer's view)."""
    paras, buf = [], ""
    for _, _, t in cues:
        buf = (buf + " " + t).strip()
        if t.rstrip().endswith((".", "!", "?")):
            paras.append(buf)
            buf = ""
    if buf:
        paras.append(buf)
    head = f"{title}\n\n" if title else ""
    return head + "\n\n".join(paras) + "\n"


def project_title(draft):
    """The on-screen title lines (size 18 at the very start), as one string."""
    texts = {m["id"]: m for m in draft["materials"].get("texts", [])}
    bits = []
    for t in draft.get("tracks", []):
        for s in t.get("segments", []):
            m = texts.get(s.get("material_id"))
            if not m or s["target_timerange"]["start"] != 0:
                continue
            try:
                c = json.loads(m.get("content") or "{}")
            except (json.JSONDecodeError, TypeError):
                continue
            if any(st.get("size") == 18 for st in (c.get("styles") or [])):
                bits.append((c.get("text") or "").strip())
    return " ".join(b for b in bits if b)


def export(project, outdir=OUT):
    outdir.mkdir(parents=True, exist_ok=True)
    made = []
    drafts = sorted(glob.glob(str(CAPCUT / project / "Timelines/*/draft_info.json"))) or \
        [str(CAPCUT / project / "draft_info.json")]
    for i, f in enumerate(drafts):
        if not os.path.exists(f):
            continue
        d = json.load(open(f))
        cues = cues_of(d)
        if not cues:
            continue
        title = project_title(d)
        name = project if len(drafts) == 1 else f"{project} - timeline {i + 1:02d}"
        safe = re.sub(r"[^\w \-&()]", "", name)
        (outdir / f"{safe}.srt").write_text(srt_text(cues), encoding="utf-8")
        (outdir / f"{safe} (transcript).txt").write_text(
            transcript_text(cues, title), encoding="utf-8")
        words = len(" ".join(c[2] for c in cues).split())
        made.append((safe, len(cues), cues[-1][1], words, title))
    return made


def _test():
    d = {"materials": {"texts": [
            {"id": "a", "content": json.dumps({"text": "Open the records list",
                                               "styles": [{"size": 5}]})},
            {"id": "b", "content": json.dumps({"text": "and search for it.",
                                               "styles": [{"size": 5}]})},
            {"id": "h", "content": json.dumps({"text": "leftover",
                                               "styles": [{"size": 5}]})},
            {"id": "t", "content": json.dumps({"text": "How to do it",
                                               "styles": [{"size": 18}]})}]},
         "tracks": [{"segments": [
            {"material_id": "t", "target_timerange": {"start": 0,
                                                      "duration": int(4.4 * US)}},
            {"material_id": "a", "target_timerange": {"start": int(1.0 * US),
                                                      "duration": int(2.0 * US)}},
            {"material_id": "h", "visible": False,
             "target_timerange": {"start": int(1.5 * US), "duration": int(1.0 * US)}},
            {"material_id": "b", "target_timerange": {"start": int(2.5 * US),
                                                      "duration": int(2.0 * US)}}]}]}
    cues = cues_of(d)
    assert [c[2] for c in cues] == ["Open the records list", "and search for it."], \
        "hidden cues must never reach a course transcript; titles are not captions"
    s = srt_text(cues)
    assert s.startswith("1\n00:00:01,000 --> 00:00:02,500\nOpen the records list"), s[:60]
    assert "00:00:02,500 --> 00:00:04,500" in s, "overlap must be trimmed at the next cue"
    assert transcript_text(cues, project_title(d)).startswith(
        "How to do it\n\nOpen the records list and search for it."), "sentences join across cues"
    assert stamp(3661.5) == "01:01:01,500"
    print("sa_srtexport self-check: ok (visible only, overlap trim, sentence join)")


if __name__ == "__main__":
    if "--test" in sys.argv:
        _test()
        sys.exit()
    ap = argparse.ArgumentParser()
    ap.add_argument("project", nargs="?")
    a = ap.parse_args()
    projects = [a.project] if a.project else \
        sorted(p.name for p in CAPCUT.glob("*")
               if p.name.startswith(SERIES_PREFIX))
    total = 0
    for proj in projects:
        for safe, n, end, words, title in export(proj):
            print(f"  {safe[:52]:52s} {n:3d} cues  {end/60:5.1f} min  {words:5d} words"
                  f"  {title[:34]}")
            total += 1
    print(f"\n{total} file pair(s) -> {OUT}")
