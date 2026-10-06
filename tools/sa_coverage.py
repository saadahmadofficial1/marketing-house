#!/usr/bin/env python3
"""sa_coverage — which steps in the script never got a call-out.

The vision model's `--gaps` mode returned 130 "worth highlighting" moments across the series
and most were noise. It was the wrong instrument: it guesses at a picture, when the answer is
already written down. **Every script segment states what the trainee must do.** If a segment
tells them to click, select, open, enter or sign in, and no call-out is on screen while that
line is being spoken, that step is unmarked. That is arithmetic, not judgement.

    Tools/venv/bin/python3 Tools/sa_coverage.py                      # whole series
    Tools/venv/bin/python3 Tools/sa_coverage.py "T01 Sign In and Navigation"
    Tools/venv/bin/python3 Tools/sa_coverage.py --json out.json
    Tools/venv/bin/python3 Tools/sa_coverage.py --test

Reads `<T>_captions.plan.json` (the locked script, per segment), `<T>_PACED.timing.json`
(when each segment starts) and `<T>_PACED_LAYERS/_layers.json` (the call-outs and their times).
Read-only.
"""
import argparse
import glob
import json
import os
import pathlib
import re
import sys

BUILD = pathlib.Path("~/Downloads/training-series/2 BUILD").expanduser()

# Verbs that mean "the trainee has to do something here". A segment carrying one of these and
# no call-out is a step nobody was pointed at.
ACTIONS = re.compile(
    r"\b(click|select|choose|open|enter|type|search|sign in|sign out|sign back in|tick|"
    r"upload|scroll to|press|set the|add the|mark|submit|generate|record|confirm|"
    r"schedule|raise|assign|approve|save|clock in|clock out|complete the|fill)\b", re.I)

# A role change is a navigation landmark — the trainee becomes a different person. Saad had to
# add these by hand in one video; across the series 17 of 30 had nothing on screen.
ROLE = re.compile(r"\bsign (in|out|back in)\b", re.I)


def segments(folder, tag):
    """-> [{n, start, end, text}] from the locked script plus the paced timing."""
    plan = os.path.join(folder, f"{tag}_captions.plan.json")
    timing = os.path.join(folder, f"{tag}_PACED.timing.json")
    if not (os.path.exists(plan) and os.path.exists(timing)):
        return []
    texts = {s["n"]: s.get("text", "") for s in json.load(open(plan))["segments"]}
    out = []
    for s in json.load(open(timing))["segments"]:
        if s["n"] not in texts:
            continue
        out.append({"n": s["n"], "start": s["start"],
                    "end": s["start"] + s.get("picture_dur", 0), "text": texts[s["n"]]})
    return sorted(out, key=lambda s: s["start"])


# build tag -> CapCut project name (example entries; one per video in the series)
PROJECT_OF = {
    "T01": "Training 01 Sign In and Navigation",
    "T02": "Training 02 Create a Record",
}


def his_labels(tag):
    """Call-outs Saad typed himself in CapCut. -> [(start, end, text)]

    He does not always wait for a rebuild — in one video he typed five labels straight into the
    project ("Sign in as the Manager", "Click Submit"). Those are call-outs and
    they cover their step. Counting only the generated PNGs reported eleven steps as unmarked
    in a video where he had already marked five of them by hand, which would have sent him to
    redo his own work.
    """
    name = PROJECT_OF.get(tag)
    if not name:
        return []
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from sa_finaldiff import typed, read, CAPCUT
        cur = sorted(glob.glob(str(CAPCUT / name / "Timelines/*/draft_info.json")))
        if not cur:
            return []
        # size 18 is the title card, not a call-out
        return [(a, a + d, t) for a, d, t, sz, _f in typed(read(cur[0])) if (sz or 0) < 10]
    except Exception:
        return []


def callouts(folder, tag):
    """-> [(start, end, label)] — the generated images AND anything he typed himself."""
    man = glob.glob(os.path.join(folder, f"{tag}_PACED_LAYERS", "_layers.json"))
    built = [(L["start"], L["start"] + L["duration"], L["label"])
             for L in json.load(open(man[0]))["layers"]] if man else []

    # Two modules keep their step call-outs in <T>_stepmarks.json and leave only the
    # role banners in _layers.json (4 and 8, against 41 and 74 real marks). Reading the
    # layers plan alone reported nearly every step as unmarked and put a false "missing"
    # count on Saad's dashboard. Merge the stepmarks in, de-duplicated by time+label.
    for sm in glob.glob(os.path.join(folder, f"{tag}_stepmarks.json")):
        try:
            data = json.load(open(sm))
        except (json.JSONDecodeError, OSError):
            continue
        marks = data if isinstance(data, list) else data.get("marks", data.get("steps", []))
        seen = {(round(a, 2), l) for a, _b, l in built}
        for m in marks:
            key = (round(m["t"], 2), m.get("label", ""))
            if key in seen:
                continue
            built.append((m["t"], m["t"] + m.get("dur", 2.1), m.get("label", "")))
    return sorted(built + his_labels(tag))


def covered(seg, calls, slack=0.5):
    """Is any call-out on screen while this segment plays? Pure."""
    return any(a < seg["end"] + slack and b > seg["start"] - slack for a, b, _l in calls)


def gaps(segs, calls):
    """-> segments that ask the trainee to act and have no call-out. Pure, so testable."""
    out = []
    for s in segs:
        if covered(s, calls):
            continue
        verbs = sorted({m.group(0).lower() for m in ACTIONS.finditer(s["text"])})
        if not verbs:
            continue
        out.append({**s, "verbs": verbs, "role_change": bool(ROLE.search(s["text"]))})
    return out


def recut_by(tag, my_total):
    """How far his timeline has drifted from the build, in seconds. -> float or None.

    Once he ripple-deletes, everything after the cut moves. The segment times here come from
    the BUILD, so on a video he has re-cut they no longer line up with his project and the
    coverage numbers are approximate. Say so rather than show false precision — one video
    ended up 38s shorter than the build it came from.
    """
    name = PROJECT_OF.get(tag)
    if not name:
        return None
    try:
        from sa_finaldiff import read, CAPCUT, end_of
        cur = sorted(glob.glob(str(CAPCUT / name / "Timelines/*/draft_info.json")))
        if not cur:
            return None
        d = end_of(read(cur[0])) - my_total
        return d if abs(d) > 3.0 else None
    except Exception:
        return None


def analyse(folder):
    tag = os.path.basename(folder).split()[0]
    segs, calls = segments(folder, tag), callouts(folder, tag)
    if not segs:
        return None
    g = gaps(segs, calls)
    return {"video": os.path.basename(folder), "tag": tag,
            "segments": len(segs), "callouts": len(calls),
            "unmarked": g,
            "recut_by": recut_by(tag, segs[-1]["end"]),
            "role_changes": sum(1 for s in segs if ROLE.search(s["text"])),
            "role_changes_marked": sum(1 for s in segs if ROLE.search(s["text"])
                                       and covered(s, calls))}


def main(only, out_json):
    rows = []
    for folder in sorted(glob.glob(str(BUILD / "T*"))):
        if not os.path.isdir(folder) or (only and only not in os.path.basename(folder)):
            continue
        r = analyse(folder)
        if r:
            rows.append(r)
    print(f"{'video':40s} {'steps':>6s} {'boxes':>6s} {'UNMARKED':>9s} {'roles':>7s}")
    for r in rows:
        roles = f"{r['role_changes_marked']}/{r['role_changes']}"
        flag = "  <--" if r["unmarked"] else ""
        print(f"{r['video'][:40]:40s} {r['segments']:6d} {r['callouts']:6d} "
              f"{len(r['unmarked']):9d} {roles:>7s}{flag}")
    tot = sum(len(r["unmarked"]) for r in rows)
    rc = sum(r["role_changes"] for r in rows)
    rm = sum(r["role_changes_marked"] for r in rows)
    print(f"\n{tot} step(s) across the series ask the trainee to act with no call-out on screen")
    print(f"{rc - rm} of {rc} role changes are unmarked")
    if out_json:
        json.dump(rows, open(out_json, "w"), indent=1)
        print(f"-> {out_json}")
    return rows


def _test():
    segs = [{"n": 1, "start": 0.0, "end": 10.0, "text": "In this video, we'll learn the flow."},
            {"n": 2, "start": 10.0, "end": 20.0, "text": "Click New Lead to begin."},
            {"n": 3, "start": 20.0, "end": 30.0, "text": "Sign in as the Cashier."},
            {"n": 4, "start": 30.0, "end": 40.0, "text": "The status updates automatically."}]
    calls = [(11.0, 14.0, "Click New Lead")]
    g = gaps(segs, calls)
    ns = [x["n"] for x in g]
    assert 2 not in ns, "a segment with a call-out on screen is covered"
    assert 1 not in ns, "an intro that asks nothing is not a gap"
    assert 4 not in ns, "a segment that only describes is not a gap"
    assert ns == [3], f"only the unmarked action segment is a gap, got {ns}"
    assert g[0]["role_change"] is True, "and a sign-in is flagged as a role change"
    # a call-out that merely overlaps the edge still counts as covering
    assert not gaps([segs[1]], [(19.9, 25.0, "x")]), "overlap at the boundary counts"
    # no call-outs at all: every action segment is a gap
    assert len(gaps(segs, [])) == 2
    print("sa_coverage self-check: ok (covered, action verbs, role change, boundaries)")


if __name__ == "__main__":
    if "--test" in sys.argv:
        _test()
        sys.exit()
    ap = argparse.ArgumentParser()
    ap.add_argument("video", nargs="?")
    ap.add_argument("--json")
    a = ap.parse_args()
    main(a.video, a.json)
