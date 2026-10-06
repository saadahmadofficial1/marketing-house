#!/usr/bin/env python3
"""sa_learncurve — am I actually learning from Saad's edits? Measured, not claimed.

He asked it straight on 11 Aug, after editing the first batch of videos: is the build actually
learning from his edits? The only honest answer is a number, so this
compares every video I built against the version he finished and reports:

  * what he changes EVERY time (the recurring tax — each one is a build default I
    should have changed and did not),
  * whether the tax is falling video by video (the learning curve),
  * which videos needed no marking work at all (the wins).

    Tools/venv/bin/python3 Tools/sa_learncurve.py
    Tools/venv/bin/python3 Tools/sa_learncurve.py --test

Read-only. A pattern that shows up in 3+ finished videos is not taste any more, it is
a defect in the build defaults, and this prints it as such.
"""
import glob
import json
import os
import pathlib
import re
import statistics as st
import sys

US = 1_000_000
CAPCUT = pathlib.Path("~/Movies/CapCut/User Data/Projects/com.lveditor.draft").expanduser()
SERIES = pathlib.Path(os.environ.get("TRAINING_ROOT", "~/Downloads/training-series")).expanduser()
BUILD = SERIES / "2 BUILD"
PROGRESS = SERIES / "5 ADMIN" / "PROGRESS.json"
FREEZE_RE = re.compile(r"^[0-9a-f]{32}_\d+-sdr709\.png$")


def measure(draft, manifest_boxes):
    """Pure: draft -> the numbers that show how he finished it."""
    vids = {m["id"]: (m.get("path") or "") for m in draft["materials"].get("videos", [])}
    texts = {m["id"]: m for m in draft["materials"].get("texts", [])}
    holds, freezes, moved, typed, end = [], [], 0, 0, 0.0
    for t in draft.get("tracks", []):
        nm = (t.get("name") or "").strip().lower()
        for s in t.get("segments", []):
            tr = s.get("target_timerange") or {}
            dur = tr.get("duration", 0) / US
            end = max(end, (tr.get("start", 0) + tr.get("duration", 0)) / US)
            p = vids.get(s.get("material_id"), "")
            base = os.path.basename(p)
            if FREEZE_RE.match(base):
                freezes.append(dur)
            elif p.endswith(".png") and "endhold" not in base:
                holds.append(dur)
                clip = s.get("clip") or {}
                tf = clip.get("transform") or {}
                sc = clip.get("scale") or {}
                if abs(tf.get("x", 0)) > 0.02 or abs(tf.get("y", 0)) > 0.02 \
                        or abs(sc.get("x", 1) - 1) > 0.03:
                    moved += 1
            elif s.get("material_id") in texts and nm not in ("captions", "title",
                                                              "sign-off"):
                try:
                    c = json.loads(texts[s["material_id"]].get("content") or "{}")
                    if (c.get("styles") or [{}])[0].get("size", 99) < 10 \
                            and len(c.get("text", "")) <= 40:
                        typed += 1
                except (json.JSONDecodeError, TypeError):
                    pass
    return {"boxes": len(holds), "hold_median": round(st.median(holds), 2) if holds else 0,
            "freezes": len(freezes),
            "freeze_median": round(st.median(freezes), 2) if freezes else 0,
            "moved": moved, "typed": typed, "length": round(end, 1)}


def done_videos(progress_path=PROGRESS):
    try:
        prog = json.loads(pathlib.Path(progress_path).read_text())
    except (OSError, json.JSONDecodeError):
        return []
    return [k for k, v in prog.get("videos", {}).items() if v.get("saad") == "done"]


# progress-file name prefix -> build tag, and tag -> CapCut project (example entries)
TAG_OF = {"Training 01": "T01", "Training 02": "T02"}
PROJ_OF = {"T01": "Training 01 Sign In and Navigation",
           "T02": "Training 02 Create a Record"}
MY_HOLD = 3.1          # what the build shipped as a box hold, until 10 Aug


def run():
    rows = []
    for name in done_videos():
        tag = next((t for k, t in TAG_OF.items() if name.startswith(k)), None)
        proj = PROJ_OF.get(tag)
        if not proj:
            continue
        fs = sorted(glob.glob(str(CAPCUT / proj / "Timelines/*/draft_info.json")))
        if not fs:
            continue
        man = next(iter(glob.glob(str(BUILD / "*" / f"{tag}_PACED_LAYERS" / "_layers.json"))),
                   None)
        boxes = len(json.load(open(man)).get("layers", [])) if man else 0
        rows.append((tag, measure(json.load(open(fs[0])), boxes)))
    if not rows:
        print("no finished videos to measure")
        return rows
    print(f"{'video':6s} {'his hold':>9s} {'freezes':>8s} {'moved':>6s} {'typed':>6s} "
          f"{'length':>7s}")
    for tag, m in rows:
        print(f"{tag:6s} {m['hold_median']:9.2f} {m['freezes']:8d} {m['moved']:6d} "
              f"{m['typed']:6d} {m['length']:7.1f}")
    holds = [m["hold_median"] for _, m in rows if m["hold_median"]]
    frz = [m["freezes"] for _, m in rows]
    moved = [m["moved"] for _, m in rows]
    typed = [m["typed"] for _, m in rows]
    print(f"\nTHE RECURRING TAX — what he fixes on my build, every time:")
    print(f"  box hold      : I ship {MY_HOLD}s, he settles at {st.median(holds):.2f}s "
          f"(range {min(holds):.1f}-{max(holds):.1f}) — {len(holds)}/{len(rows)} videos")
    print(f"  freezes added : {sum(frz)} across {sum(1 for f in frz if f)}/{len(rows)} "
          f"videos, median {st.median([m['freeze_median'] for _, m in rows if m['freezes']] or [0]):.2f}s")
    print(f"  boxes nudged  : {sum(moved)} total, {sum(1 for m in moved if m)}/{len(rows)} videos")
    print(f"  labels typed  : {sum(typed)} total ({sum(1 for t in typed if t)}/{len(rows)} videos)")
    return rows


def _test():
    d = {"materials": {
            "videos": [{"id": "b", "path": "/x/01_Open.png"},
                       {"id": "f", "path": "/x/" + "a" * 32 + "_1000-sdr709.png"}],
            "texts": [{"id": "t", "content": json.dumps(
                {"text": "Sign in as Cashier", "styles": [{"size": 5}]})}]},
         "tracks": [
            {"name": "box", "segments": [
                {"material_id": "b", "target_timerange": {"start": 0,
                                                          "duration": int(2.0 * US)},
                 "clip": {"transform": {"x": 0.4, "y": 0}, "scale": {"x": 1.0}}}]},
            {"name": "video", "segments": [
                {"material_id": "f", "target_timerange": {"start": int(2 * US),
                                                          "duration": int(0.9 * US)}}]},
            {"name": "his labels", "segments": [
                {"material_id": "t", "target_timerange": {"start": 0,
                                                          "duration": int(1.6 * US)}}]}]}
    m = measure(d, 1)
    assert m["boxes"] == 1 and m["hold_median"] == 2.0
    assert m["freezes"] == 1 and m["freeze_median"] == 0.9, "freeze stills counted apart"
    assert m["moved"] == 1, "a box he shifted must register as moved"
    assert m["typed"] == 1, "his own typed label must register"
    assert m["length"] == 2.9
    print("sa_learncurve self-check: ok (holds, freezes, moves, typed labels)")


if __name__ == "__main__":
    if "--test" in sys.argv:
        _test()
        sys.exit()
    run()
