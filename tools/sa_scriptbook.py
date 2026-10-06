#!/usr/bin/env python3
"""sa_scriptbook — one accurate script file per training video, straight from CapCut.

Why: a course team builds lessons from these scripts, so no line can be wrong. Some videos
were revised and re-exported elsewhere, so the MP4 on this Mac can be stale — the CapCut
project is the only truth.

The trap this tool exists to avoid: a project is longer than the video exported from it
(parked recordings, INSERT tracks, older versions). Dumping every caption would put lines
in the script that nobody ever sees. So the region is decided per project:

  1. `config.export_range` — what CapCut actually rendered. Trusted when it is a strict
     subset (e.g. 41.3-91.0s of a 91s project, or 920-1265s of a 1265s one — the
     editor's own exported section, to the frame).
  2. Otherwise the whole timeline.
  Cues outside the region are still written out, under "not in this export", so nothing
  is silently lost.

    Tools/venv/bin/python3 Tools/sa_scriptbook.py            # all of them
    Tools/venv/bin/python3 Tools/sa_scriptbook.py --test

Read-only on the projects. Writes to ./SCRIPTS/ (set SA_SCRIPTBOOK_OUT to change it).
"""
import argparse, html, json, os, pathlib, re, sys

US = 1_000_000
CAPCUT = pathlib.Path("~/Movies/CapCut/User Data/Projects/com.lveditor.draft").expanduser()
OUT = pathlib.Path(os.environ.get("SA_SCRIPTBOOK_OUT", "SCRIPTS")).expanduser()


def cue_text(mat):
    """CapCut stores caption text as JSON with styling; pull the words out."""
    raw = mat.get("content") or ""
    if raw.startswith("{"):
        try:
            raw = json.loads(raw).get("text", "")
        except Exception:
            pass
    raw = re.sub(r"<[^>]+>", "", html.unescape(raw))
    return re.sub(r"\s+", " ", raw).strip()


def cues(project, timeline=None):
    """Every caption cue in the project (or one of its timelines), in time order."""
    d = CAPCUT / project
    src = d / "draft_info.json"
    if timeline:
        cands = sorted(d.glob("Timelines/*/draft_info.json"))
        src = next((c for c in cands if c.parent.name.startswith(timeline)), src)
    j = json.load(open(src))
    mats = {m["id"]: m for m in j["materials"].get("texts", [])}
    out = []
    for t in j["tracks"]:
        if t["type"] != "text":
            continue
        for s in t.get("segments", []):
            if not s.get("visible", True):
                continue
            txt = cue_text(mats.get(s["material_id"], {}))
            if not txt:
                continue
            a = s["target_timerange"]["start"] / US
            out.append({"t": round(a, 2), "end": round(a + s["target_timerange"]["duration"] / US, 2),
                        "track": t.get("name") or "", "track_id": str(t.get("id") or id(t)), "text": txt})
    out.sort(key=lambda c: c["t"])
    # A text track is not always narration: call-out labels and titles live on text tracks
    # too (a call-out such as "The record is saved" is never spoken). The
    # caption track is the dense one; sparse tracks are labels, reported separately.
    counts = {}
    for c in out:
        counts[c["track_id"]] = counts.get(c["track_id"], 0) + 1
    top = max(counts.values()) if counts else 0
    dense = {k for k, n in counts.items() if n >= max(6, top * 0.25)}
    # A sparse track is only USUALLY labels. In these projects the narration is split across
    # several text tracks, so a continuation of a sentence can sit on a 3-cue track (e.g.
    # "is processed once the reviewer has"). Dropping it silently ate the opening of three
    # scripts. So test the flow instead: a cue is a label only if the sentence reads correctly
    # without it — the cue before it ends mid-sentence and the cue after it carries that
    # sentence on. If the cue itself is what carries the sentence on, it is narration.
    for i, c in enumerate(out):
        if c["track_id"] in dense:
            c["spoken"] = True; continue
        prev = next((o for o in reversed(out[:i]) if o["track_id"] in dense), None)
        nxt = next((o for o in out[i + 1:] if o["track_id"] in dense), None)
        p_open = bool(prev) and not prev["text"].rstrip().endswith((".", "!", "?", ":"))
        n_cont = bool(nxt) and nxt["text"][:1].islower()
        c_cont = c["text"][:1].islower()
        if p_open and c_cont:
            c["spoken"] = True            # this cue carries the sentence on
        elif p_open and n_cont:
            c["spoken"] = False           # the sentence closes without it: an on-screen label
        else:
            c["spoken"] = not (prev is None and c["t"] - out[0]["t"] < 3.0)   # a card at the top is the title
    cfg = j.get("config") or {}
    er = cfg.get("export_range") or {}
    rng = None
    if er.get("duration"):
        a, b = er["start"] / US, (er["start"] + er["duration"]) / US
        if b - a < j["duration"] / US - 1:          # a strict subset: he exported a section
            rng = (round(a, 2), round(b, 2))
    return out, rng, round(j["duration"] / US, 2)


def title_cue(cs, t0=0.0):
    """The title card: a cue at the very start of the video that is not part of the narration.

    It must be first, within the first 3 seconds, not spoken, and must not read as the opening
    of a sentence ("In this video, we'll..."), which is narration and belongs in the body.
    """
    if not cs:
        return None
    c = cs[0]
    if c.get("t", 99) - t0 > 3.0:
        return None
    t = c["text"].strip()
    # A title card carries no closing punctuation. The spoken flag is unreliable for a video
    # exported from the middle of a timeline (one starts at 920s), so judge the text too.
    if c.get("spoken", True) and t.rstrip().endswith((".", "!", "?")):
        return None
    if len(t.split()) < 3 or t.lower().startswith(("in this video", "we'll", "we will", "today")):
        return None
    return t


def prose(cs, t0=0.0):
    """Cues -> readable sentences. A caption is a fragment; the script is the sentences."""
    t = title_cue(cs, t0)
    if t: cs = [c for c in cs if c["text"] != t]
    words = " ".join(c["text"] for c in cs)
    words = re.sub(r"\s+", " ", words).strip()
    parts, cur = [], ""
    for tok in words.split():
        cur = f"{cur} {tok}".strip()
        if tok.endswith((".", "!", "?")):
            parts.append(cur); cur = ""
    if cur:
        parts.append(cur)
    # drop an exact repeat (a cue kept on two tracks)
    dedup = [p for i, p in enumerate(parts) if i == 0 or p != parts[i - 1]]
    return dedup


def write(num, title, project, note="", timeline=None, regions=None):
    cs, rng, dur = cues(project, timeline)
    if regions:                      # explicit regions win over export_range
        rng = (regions[0][1], regions[-1][2])
        inside = [c for c in cs if any(a - 0.01 <= c["t"] <= b + 0.01 for _, a, b in regions)]
    else:
        inside = [c for c in cs if rng is None or (rng[0] - 0.01 <= c["t"] <= rng[1] + 0.01)]
    outside = [c for c in cs if c not in inside]
    tc0 = title_cue(inside, rng[0] if rng else 0.0)
    onscreen = [c for c in inside if not c.get("spoken", True) and c["text"] != tc0]
    inside = [c for c in inside if c.get("spoken", True)]
    body = prose(inside, rng[0] if rng else 0.0)
    stamp = f"{rng[0]:.1f}s to {rng[1]:.1f}s of the timeline" if rng else f"whole timeline ({dur:.0f}s)"
    lines = [title.upper(), "=" * len(title), "",
             f"Video {num} of {len(BOOK)}.  Source: CapCut project \"{project}\" — caption track, {stamp}.",
             f"Spoken length about {(rng[1]-rng[0]) if rng else dur:.0f} seconds.  Read {TODAY}."]
    if note:
        lines.append(f"NOTE: {note}")
    lines += ["", ""]
    tc = tc0          # taken before the spoken filter — the title card is never "spoken"
    if tc:
        lines += [f"On-screen title: {tc}", ""]
    if regions and len(regions) > 1:
        for label, a, b in regions:
            part = prose([c for c in cs if a - 0.01 <= c["t"] <= b + 0.01])
            lines += [f"--- {label} ({a:.0f}s to {b:.0f}s) ---", ""]
            buf, m = [], 0
            for s2 in part:
                buf.append(s2); m += len(s2)
                if m > 320: lines += [" ".join(buf), ""]; buf, m = [], 0
            if buf: lines += [" ".join(buf), ""]
            lines.append("")
        body = []
    para, n = [], 0
    for s in body:
        para.append(s); n += len(s)
        if n > 320:
            lines.append(" ".join(para)); lines.append(""); para, n = [], 0
    if para:
        lines.append(" ".join(para))
    if onscreen:
        lines += ["", "", "-" * 70,
                  "ON-SCREEN TEXT — shown in the video but NOT spoken",
                  "(call-out labels and titles; keep these out of the narration):", ""]
        lines += [f"  [{c['t']:7.1f}s] {c['text']}" for c in onscreen]
    if outside:
        lines += ["", "", "-" * 70,
                  f"NOT IN THIS EXPORT — {len(outside)} caption(s) elsewhere in the same project",
                  "(kept here so nothing is lost; they are not spoken in this video):", ""]
        lines += [f"  [{c['t']:7.1f}s] {c['text']}" for c in outside]
    p = OUT / f"{num:02d}_{re.sub(r'[^A-Za-z0-9]+', '_', title).strip('_')}.txt"
    p.write_text("\n".join(lines) + "\n")
    return p, len(body), len(inside), len(outside), rng


import datetime as _dt
_d = _dt.date.today()
TODAY = f"{_d.day} {_d:%B %Y}"

# The exported video on this Mac, where it exists and is current. Used by --verify to check the
# script against the audio the viewer actually hears — a video revised and re-exported elsewhere
# has a stale local copy, so it is deliberately absent here.
FIN = pathlib.Path(os.environ.get("TRAINING_ROOT", "~/Downloads/training-series")).expanduser() / "4 FINAL VIDEOS"
EXPORTS = {
    1: "Module 01 - Example.mp4",
    2: "Module 02 - Example.mp4",
}


def verify(num, path):
    """Compare the written script with what is actually spoken in the exported video.

    Local transcription only. A caption can survive in the project after the export was
    trimmed (e.g. an export that renders 27s of a 41s timeline), so a line can be in the caption track
    and never reach the viewer's ears. Those get marked in the file rather than deleted.
    """
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    import sa_finalcheck as fc
    body_lines, head = [], []
    txt = path[1].read_text().split("\n")
    for l in txt:
        if l.startswith(("  [", "---", "NOT IN", "ON-SCREEN", "(kept", "(call-out", "Video ", "Spoken", "NOTE", "=", "On-screen")) or l == txt[0]:
            continue
        body_lines.append(l)
    tr = fc.transcribe(path[0]); hay = fc.norm(tr).split()
    sents = fc.sentences("\n".join(body_lines))
    scored = [(sn, fc.best_match(sn, hay)[0]) for sn in sents]
    unheard = [sn for sn, r in scored if r < 0.6]
    mean = sum(r for _, r in scored) / max(1, len(scored))
    out = []
    for l in txt:
        for sn in unheard:
            if sn in l:
                l = l.replace(sn, sn + "  [ON SCREEN ONLY — not spoken in the exported video]")
        out.append(l)
        if l.startswith("Spoken length"):
            out.append(f"Checked against the exported video's own audio: {len(sents)-len(unheard)} of "
                       f"{len(sents)} sentences heard, average match {mean:.2f}.")
    path[1].write_text("\n".join(out))
    return len(sents) - len(unheard), len(sents), round(mean, 2)

TL = {2: "ABC123"}                 # several modules share one project: pick the timeline by id prefix
REGIONS = {1: [("The published video", 0.0, 290.0),
               ("The revised section exported later", 297.8, 499.5)]}

# video number -> (title, capcut project, note). Example entries; list your own series here.
BOOK = [
    (1, "How to approve a request", "Module 01 Example", "Revised version."),
    (2, "How to create a record", "Module 02 Example", "Shares its project with another module; this video is the first timeline."),
]


def self_test():
    assert cue_text({"content": '{"text":"Open the <b>Records List</b>."}'}) == "Open the Records List."
    assert cue_text({"content": "Plain &amp; simple"}) == "Plain & simple"
    p = prose([{"text": "Open the list."}, {"text": "Select the"}, {"text": "record."}])
    assert p == ["Open the list.", "Select the record."], p
    # the title card is lifted out, not glued onto the first spoken sentence
    cs = [{"t": 0.0, "spoken": False, "text": "How to complete the Review"},
          {"t": 4.0, "spoken": True, "text": "Open the checklist."}]
    assert title_cue(cs) == "How to complete the Review"
    assert prose(cs) == ["Open the checklist."], prose(cs)
    # 9 Sep, found by Saad: the opening of the narration is NOT a title card, and taking it as
    # one beheaded three scripts ("In this video, we'll learn how a record" became the title
    # and the body then started mid-sentence)
    opener = [{"t": 4.9, "spoken": True, "text": "In this video, we'll learn how a record"},
              {"t": 7.2, "spoken": True, "text": "is processed once the reviewer has"},
              {"t": 9.7, "spoken": True, "text": "completed the check."}]
    assert title_cue(opener) is None, title_cue(opener)
    assert prose(opener)[0].startswith("In this video"), prose(opener)
    print("self-test ok")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", action="store_true")
    ap.add_argument("--verify", action="store_true", help="check each script against its exported video's audio")
    ap.add_argument("--clean", action="store_true",
                    help="also write forwarding copies: title, title card, narration — no working notes")
    a = ap.parse_args()
    if a.test:
        return self_test()
    OUT.mkdir(parents=True, exist_ok=True)
    for num, title, project, note in BOOK:
        if not (CAPCUT / project).exists():
            print(f"  {num:2d}  MISSING PROJECT: {project}"); continue
        p, sents, cin, cout, rng = write(num, title, project, note, TL.get(num), REGIONS.get(num))
        where = f"{rng[0]:.0f}-{rng[1]:.0f}s" if rng else "whole"
        print(f"  {num:2d}  {sents:3d} sentences  {cin:3d} cues ({where}){f' · {cout} outside' if cout else ''}  {p.name}")
    if a.clean:
        # What a course team receives should be the words and nothing else. The provenance —
        # source, region, audio check, on-screen labels, captions from elsewhere in the project —
        # stays in the working copy, which is where it is useful if a step is ever questioned.
        import textwrap
        cd = OUT.parent / (OUT.name + "_CLEAN"); cd.mkdir(exist_ok=True)
        for f in sorted(OUT.glob("*.txt")):
            lines = f.read_text().split("\n")
            title, rule = lines[0], lines[1]
            card = next((l[len("On-screen title: "):] for l in lines if l.startswith("On-screen title:")), None)
            body, i = [], 2
            for j, l in enumerate(lines[2:], 2):
                if l.startswith(("-" * 10, "ON-SCREEN TEXT", "NOT IN THIS EXPORT")):
                    break
                if l.startswith(("Video ", "Spoken length", "Checked against", "NOTE:", "On-screen title:",
                                 "(call-out", "(kept", "  [", "--- ")):
                    continue
                body.append(l)
            paras = [" ".join(x.split()) for x in "\n".join(body).split("\n\n") if x.strip()]
            out = [title, rule, ""]
            if card: out += [f"Title card: {card}", ""]
            out += ["\n\n".join(textwrap.fill(x, width=96) for x in paras), ""]
            (cd / f.name).write_text("\n".join(out))
        print(f"\nclean forwarding copies -> {cd}")

    if a.verify:
        print("\nchecking against the exported audio (local transcription):")
        for num, rel in sorted(EXPORTS.items()):
            mp = FIN / rel
            f = next(iter(OUT.glob(f"{num:02d}_*.txt")), None)
            if not mp.exists() or not f:
                print(f"  {num:2d}  no export on this Mac"); continue
            good, tot, mean = verify(num, (mp, f))
            print(f"  {num:2d}  {good}/{tot} sentences heard   mean {mean:.2f}   {f.name}")
    print(f"\n{len(BOOK)} scripts -> {OUT}")


if __name__ == "__main__":
    main()
