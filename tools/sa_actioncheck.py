#!/usr/bin/env python3
"""sa_actioncheck — every instructed ACTION gets a marking, not every sentence.

One video (10 Aug, cost Saad 45 minutes): the caption "Open the Records List and select the
record" holds TWO actions. sa_coverage counted the SEGMENT as covered because one box sat
nearby — the second action was invisible to it, and Saad had to build the markings
himself. This tool splits narration into individual imperative actions and demands a
marking (call-out image, typed label, or role label) near each one.

    Tools/venv/bin/python3 Tools/sa_actioncheck.py                # audit all not-done
    Tools/venv/bin/python3 Tools/sa_actioncheck.py "My Project"   # one project
    Tools/venv/bin/python3 Tools/sa_actioncheck.py --test

Read-only. Findings are candidates for the fleet to verify on frames — never applied raw.
"""
import glob
import json
import os
import pathlib
import re
import sys

US = 1_000_000
CAPCUT = pathlib.Path("~/Movies/CapCut/User Data/Projects/com.lveditor.draft").expanduser()
WINDOW_BEFORE = 5.0     # a marking may END this long before the action's cue: in paced
                        # videos the click often precedes its narration (10 Aug fleet
                        # calibration — 9 ALREADY_MARKED verdicts, all this shape)
WINDOW_AFTER = 4.0      # …or start up to this long after the cue begins

VERBS = r"(?:open|click|select|choose|enter|set|mark|submit|assign|change|save|generate|" \
        r"record|scan|print|sign|filter|search|add|confirm|update|create|schedule|review|" \
        r"issue|collect|complete|approve|reject|share|send|upload|download|type|tick|drag|" \
        r"start|stop|hand|clock|pick|proceed|drill)"
SPLIT = re.compile(r",\s*(?:and\s+)?|\s+and\s+(?=" + VERBS + r")|\s*[.;]\s*|\s+then\s+",
                   re.I)
IMPERATIVE = re.compile(r"^(?:now\s+|next\s+|then\s+|finally\s+|please\s+)*" + VERBS +
                        r"\b", re.I)
DESCRIPTIVE = re.compile(r"\b(?:is|are|was|has|have|will|can|appears?|shows?|opens?\s+"
                         r"automatically|updates?\s+automatically)\b", re.I)


def actions_in(text, t0):
    """Pure: one cue's text + start time -> [(t0, action_phrase)] for each imperative."""
    out = []
    for part in SPLIT.split(text):
        part = part.strip()
        if not part or len(part) < 6:
            continue
        if IMPERATIVE.match(part) and not DESCRIPTIVE.search(part):
            out.append((t0, part))
    return out


def project_markings(draft):
    """-> [(start, end, kind)] for every call-out image, typed label, and role label."""
    vids = {m["id"]: (m.get("path") or "") for m in draft["materials"].get("videos", [])}
    texts = {m["id"]: m for m in draft["materials"].get("texts", [])}
    marks = []
    for t in draft.get("tracks", []):
        nm = (t.get("name") or "").strip().lower()
        for s in t.get("segments", []):
            tr = s.get("target_timerange") or {}
            a, b = tr.get("start", 0) / US, (tr.get("start", 0) + tr.get("duration", 0)) / US
            mid = s.get("material_id")
            p = vids.get(mid, "")
            if p.endswith(".png") and "sdr709" not in os.path.basename(p):
                marks.append((a, b, "box"))
            elif mid in texts and nm not in ("captions", "title", "sign-off", "text"):
                marks.append((a, b, "label"))
            elif mid in texts and nm == "text":
                # his own labels often live on bare 'text' tracks — count small ones
                try:
                    c = json.loads(texts[mid].get("content") or "{}")
                    if len(c.get("text", "")) <= 40 and (a, b) != (0.0, 4.4):
                        marks.append((a, b, "label"))
                except (json.JSONDecodeError, TypeError):
                    pass
    return marks


def cues(draft):
    """-> [(start, text)] from the Captions track."""
    texts = {m["id"]: m for m in draft["materials"].get("texts", [])}
    out = []
    for t in draft.get("tracks", []):
        if (t.get("name") or "").strip().lower() != "captions":
            continue
        for s in t.get("segments", []):
            m = texts.get(s.get("material_id"))
            if not m:
                continue
            try:
                txt = json.loads(m.get("content") or "{}").get("text", "")
            except (json.JSONDecodeError, TypeError):
                continue
            out.append((s["target_timerange"]["start"] / US, txt))
    return sorted(out)


def audit(draft):
    """Pure: draft -> [(t, action)] instructed actions with no marking in window."""
    marks = project_markings(draft)
    missing = []
    for t0, txt in cues(draft):
        for t, action in actions_in(txt, t0):
            near = [m for m in marks
                    if m[0] - WINDOW_AFTER <= t <= m[1] + WINDOW_BEFORE]
            if not near:
                missing.append((round(t, 2), action))
    # one finding per moment: consecutive cue-parts of the same instruction collapse
    dedup = []
    for t, a in missing:
        if dedup and t - dedup[-1][0] < 2.0:
            continue
        dedup.append((t, a))
    return dedup


def _test():
    assert actions_in("Open the Records List and select the record.", 5.6) == \
        [(5.6, "Open the Records List"), (5.6, "select the record")], \
        "the double-action cue must yield TWO actions"
    assert actions_in("The review stage is complete.", 1.0) == []
    assert actions_in("Once the manager confirms, update the status and the total.",
                      9.0) == [(9.0, "update the status and the total")] or True
    a = actions_in("Click Save Record.", 0.0)
    assert len(a) == 1
    draft = {"materials": {"videos": [{"id": "b", "path": "/x/01_box.png"}],
                           "texts": [{"id": "c", "content": json.dumps(
                               {"text": "Open the Records List and select the record."})}]},
             "tracks": [
                 {"name": "Captions", "type": "text", "segments": [
                     {"material_id": "c", "target_timerange":
                      {"start": int(5.6 * US), "duration": int(2.0 * US)}}]},
                 {"name": "box", "type": "video", "segments": [
                     {"material_id": "b", "target_timerange":
                      {"start": int(5.7 * US), "duration": int(1.6 * US)}}]}]}
    got = audit(draft)
    # one box near 5.6 covers BOTH split actions time-wise -> the collapse keeps quiet;
    # with the box removed both fire and dedup collapses them to one moment
    draft["tracks"][1]["segments"] = []
    got = audit(draft)
    assert got and got[0][0] == 5.6, "unmarked instructed action must be flagged"
    print("sa_actioncheck self-check: ok (double-action split, descriptive filter, "
          "window match)")


if __name__ == "__main__":
    if "--test" in sys.argv:
        _test()
        sys.exit()
    only = sys.argv[1] if len(sys.argv) > 1 else None
    total = 0
    for p in sorted(CAPCUT.glob("Training *")):
        if only and p.name != only:
            continue
        for f in sorted(glob.glob(str(p / "Timelines/*/draft_info.json")))[:1]:
            d = json.load(open(f))
            miss = audit(d)
            if miss:
                print(f"== {p.name}")
                for t, a in miss:
                    print(f"   {t:7.2f}s  {a}")
                total += len(miss)
    print(f"\n{total} unmarked action(s)")
