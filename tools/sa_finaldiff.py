#!/usr/bin/env python3
"""sa_finaldiff — measure a video Saad has finished against the build he was handed.

The single most valuable feedback available. When he signs a video off, the gap between what
was built and what he was willing to ship is a specification: every difference is something
the pipeline should have done and did not. Run it on EVERY video he finishes.

    Tools/venv/bin/python3 Tools/sa_finaldiff.py "My Project"
    Tools/venv/bin/python3 Tools/sa_finaldiff.py --all
    Tools/venv/bin/python3 Tools/sa_finaldiff.py --test

Compares his current draft against the `.pre_captions` backup — the last state that was
purely machine-built. Read-only on both.

Two traps this gets right, both found by getting them wrong on 7 Aug:

1. **CapCut stores a freeze frame as a PNG**, named `<32 hex>_<micros>-sdr709.png`. Counting
   those as call-outs turned 18 into 46 and produced the confident nonsense that he had added
   28 boxes. Filter the pattern out before comparing anything.
2. **A call-out he typed himself is a TEXT element**, not a PNG — his are Poppins Medium at
   size 5. Count PNG layers and typed labels separately or his additions vanish.
"""
import argparse
import glob
import json
import os
import pathlib
import re
import statistics
import sys

US = 1_000_000
CAPCUT = pathlib.Path("~/Movies/CapCut/User Data/Projects/com.lveditor.draft").expanduser()
FREEZE = re.compile(r"^[0-9a-f]{32}_\d+-sdr709\.png$", re.I)
# Tracks the build itself creates — text on these is MINE, so finding it in his final
# proves nothing. "Role changes" was missing until 11 Aug, and its absence made the tool
# report my own role labels as steps he had typed himself: a false learning recorded in
# VERIFIER_GAPS, which is worse than no learning at all.
CHROME = {"Captions", "Title", "Sign-off", "Sign-off VO", "Role changes",
          "New call-outs", "Freeze holds", "End hold", "Narration (aligned)",
          # 12 Aug: sa_addsource puts the original recording on every remaining project as
          # a hidden reference. It is mine. Without this line every one of the five would
          # report a track and a video Saad never added — the same false learning as above.
          "SOURCE (reference)"}


def is_freeze(name):
    """CapCut's own freeze-frame still, not a call-out anyone authored."""
    return bool(FREEZE.match(name or ""))


# The build's own stills. Named-track filtering cannot catch these: CapCut drops them on an
# UNNAMED track, so one video reported 9 call-outs against my 8 and the extra one was my own
# T01_endhold.png. Match on the filename, which the build controls.
MINE = re.compile(r"_(endhold|title|signoff)\.png$", re.I)


def is_build_still(name):
    return bool(MINE.search(name or ""))


def read(path):
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def layers(d):
    """-> (call-out PNGs {file: [(at, dur)]}, freeze stills [(at, dur)])"""
    png = {m["id"]: os.path.basename(m.get("path", "") or "")
           for m in d.get("materials", {}).get("videos", [])
           if (m.get("path") or "").lower().endswith(".png")}
    calls, freezes = {}, []
    for t in d.get("tracks", []):
        for s in t.get("segments", []):
            f = png.get(s.get("material_id"))
            if not f or is_build_still(f):      # my own end-hold is not one of his call-outs
                continue
            tr = s.get("target_timerange") or {}
            at, dur = round(tr.get("start", 0) / US, 1), round(tr.get("duration", 0) / US, 2)
            (freezes.append((at, dur)) if is_freeze(f)
             else calls.setdefault(f, []).append((at, dur)))
    return calls, freezes


# Role labels — "Sign in as the Sales Advisor", "Sign out" — are the one thing this tool
# genuinely CANNOT attribute. The build writes them, and Saad types them himself when the build
# misses one; both are Poppins Medium at size 5, so neither style nor wording separates them.
#
# 12 Aug: he regrouped the tracks while editing, the build's own label moved off the
# track named "Role changes", the CHROME name filter stopped seeing it, and the diff announced
# it as a step HE had typed — two false entries in VERIFIER_GAPS before anyone looked. The
# deeper cause is the baseline: `.pre_captions` is captured BEFORE the role-label step runs, so
# the build's labels are never in the comparison to be cancelled out.
#
# Filtering them out would hide the real ones. So they are reported SEPARATELY and never
# recorded as escaped defects — an uncertain finding presented as fact is how false learnings
# get in, and this workspace rates those as worse than no learning.
ROLE_LABEL = re.compile(r"^\s*(sign\s+in\s+as\b|sign\s+out\s*$)", re.I)


def typed(d):
    """-> [(at, dur, text, size, font)] for text he wrote himself, captions/titles excluded.

    Captions are separated by FONT WEIGHT, not by track name: the build writes captions in
    Poppins **Regular** at size 5, and Saad types his own labels in Poppins **Medium** at the
    same size. 12 Aug: he regrouped the tracks, every caption fell off the track named
    "Captions", and the diff announced twelve of his own captions as steps he had typed by
    hand. Third time a name-keyed check has accused his finished work this week — the weight
    is in the file and he never changes it.
    """
    tm = {m["id"]: m for m in d.get("materials", {}).get("texts", [])}
    out = []
    for t in d.get("tracks", []):
        if (t.get("name") or "").strip() in CHROME:
            continue
        for s in t.get("segments", []):
            m = tm.get(s.get("material_id"))
            if not m:
                continue
            try:
                c = json.loads(m.get("content") or "{}")
            except (json.JSONDecodeError, TypeError):
                continue
            st = (c.get("styles") or [{}])[0]
            font = os.path.basename((st.get("font") or {}).get("path", "") or "")
            if "Regular" in font:
                continue        # a caption the build wrote, wherever he has moved it
            tr = s.get("target_timerange") or {}
            out.append((round(tr.get("start", 0) / US, 1),
                        round(tr.get("duration", 0) / US, 2), c.get("text", ""),
                        st.get("size"),
                        os.path.basename((st.get("font") or {}).get("path", "") or "")))
    return sorted(out)


def end_of(d):
    ends = [(s["target_timerange"]["start"] + s["target_timerange"]["duration"]) / US
            for t in d.get("tracks", []) for s in t.get("segments", [])
            if s.get("target_timerange")]
    return round(max(ends), 1) if ends else 0.0


def median(xs):
    return round(statistics.median(xs), 2) if xs else None


def compare(mine, his):
    """Pure: two drafts -> the findings. Testable without CapCut."""
    mc, mf = layers(mine)
    hc, hf = layers(his)
    mt = [t for t in typed(mine) if (t[3] or 0) < 10]      # size 18 is the title, skip it
    ht = [t for t in typed(his) if (t[3] or 0) < 10]
    md = [d for v in mc.values() for _a, d in v]
    hd = [d for v in hc.values() for _a, d in v]
    return {
        "length": {"mine": end_of(mine), "his": end_of(his),
                   "delta": round(end_of(his) - end_of(mine), 1)},
        "callout_pngs": {"mine": len(mc), "his": len(hc),
                         "he_dropped": sorted(set(mc) - set(hc)),
                         "he_added": sorted(set(hc) - set(mc))},
        "typed_by_him": [{"at": a, "dur": d, "text": x, "font": f} for a, d, x, _s, f in ht
                         if (a, d, x) not in {(a2, d2, x2) for a2, d2, x2, _s2, _f2 in mt}
                         and not ROLE_LABEL.match(x)],
        # cannot be attributed either way — reported, never recorded as a defect
        "role_labels_unattributable": [
            {"at": a, "dur": d, "text": x} for a, d, x, _s, _f in ht
            if (a, d, x) not in {(a2, d2, x2) for a2, d2, x2, _s2, _f2 in mt}
            and ROLE_LABEL.match(x)],
        "freezes": {"mine": len(mf), "his": len(hf), "holds": sorted(d for _a, d in hf),
                    "median_hold": median([d for _a, d in hf])},
        "callout_on_screen": {"mine": median(md), "his": median(hd)},
        "tracks": {"mine": len(mine.get("tracks", [])), "his": len(his.get("tracks", []))},
    }


def project(name):
    p = CAPCUT / name
    cur = sorted(glob.glob(str(p / "Timelines/*/draft_info.json")))
    bak = sorted(glob.glob(str(p / "Timelines/*/*.pre_captions")))
    if not cur or not bak:
        raise SystemExit(f"{name}: need both the current draft and a .pre_captions backup")
    return compare(read(bak[0]), read(cur[0]))


def show(name, r):
    L, C, T, F, S = (r["length"], r["callout_pngs"], r["typed_by_him"],
                     r["freezes"], r["callout_on_screen"])
    print(f"\n===== {name} =====")
    print(f"  length          mine {L['mine']:7.1f}s   his {L['his']:7.1f}s   "
          f"{L['delta']:+.1f}s  ({100 * L['delta'] / max(L['mine'], 1):+.0f}%)")
    print(f"  call-out images mine {C['mine']:7d}     his {C['his']:7d}")
    print(f"  freeze frames   mine {F['mine']:7d}     his {F['his']:7d}"
          + (f"   median hold {F['median_hold']}s" if F["median_hold"] else ""))
    print(f"  box on screen   mine {str(S['mine']):>7}s   his {str(S['his']):>7}s")
    print(f"  tracks          mine {r['tracks']['mine']:7d}     his {r['tracks']['his']:7d}")
    if C["he_dropped"]:
        print("  HE DROPPED:")
        for f in C["he_dropped"]:
            print(f"     {f}")
    # 12 Aug: he_added was computed and never printed, so the summary said "nothing added
    # or dropped" on a video carrying 15 call-outs the baseline had never seen. The most
    # valuable signal this tool produces was being silently discarded.
    if C["he_added"]:
        print(f"  ADDED SINCE THE BASELINE ({len(C['he_added'])}) — mine or his, check the dates:")
        for f in C["he_added"]:
            print(f"     {f}")
    if T:
        print("  HE TYPED THESE HIMSELF — steps the build missed:")
        for t in T:
            print(f"     {t['at']:7.1f}s  {t['dur']:4.2f}s  {t['font'][:18]:18s} {t['text']!r}")
    U = r.get("role_labels_unattributable") or []
    if U:
        print("  ROLE LABELS — cannot tell whose these are, check by eye:")
        for u in U:
            print(f"     {u['at']:7.1f}s  {u['dur']:4.2f}s  {u['text']!r}")
        print("     (the build writes these too, and the baseline predates that step)")
    if not C["he_dropped"] and not C["he_added"] and not T and not U:
        print("  nothing added or dropped — the call-outs were right")


GAPS_MD = pathlib.Path(__file__).resolve().parents[1] / "Reference" / "VERIFIER_GAPS.md"
GOLDEN = pathlib.Path(__file__).resolve().parents[1] / "Sessions" / "_golden"


def moved_layers(mine, his, px=0.02):
    """Call-out PNGs Saad REPOSITIONED after verification passed them. -> [(file, dx, dy)]

    Every one is an escaped defect: the verifier said the box was right and he still had to
    move it. Pure. px is in CapCut normalised units (~0.02 = ±38px on a 1920 canvas).
    """
    def transforms(d):
        png = {m["id"]: os.path.basename(m.get("path", "") or "")
               for m in d.get("materials", {}).get("videos", [])
               if (m.get("path") or "").lower().endswith(".png")}
        out = {}
        for t in d.get("tracks", []):
            for s in t.get("segments", []):
                f = png.get(s.get("material_id"))
                if f and not is_freeze(f):
                    tr = (s.get("clip") or {}).get("transform") or {}
                    out[f] = (tr.get("x", 0.0), tr.get("y", 0.0))
        return out
    a, b = transforms(mine), transforms(his)
    out = []
    for f in set(a) & set(b):
        dx, dy = b[f][0] - a[f][0], b[f][1] - a[f][1]
        if abs(dx) > px or abs(dy) > px:
            out.append((f, round(dx, 4), round(dy, 4)))
    return sorted(out)


def learn(name, r, mine, his):
    """Record every escaped defect as a permanent case (HARNESS_IDEAS "Do now" #4).

    A verifier miss is allowed to happen ONCE. After this, the gap is written down with its
    evidence, and the rule is: a gap is closed only when a check exists that fails on it.
    """
    import datetime
    cases = []
    for f, dx, dy in moved_layers(mine, his):
        cases.append(f"box passed verification but Saad moved it "
                     f"({dx:+.3f}, {dy:+.3f}): `{f}`")
    for t in r.get("typed_by_him", []):
        cases.append(f"step missed by the build — he typed {t['text']!r} at {t['at']}s")
    if not cases:
        return 0
    GAPS_MD.parent.mkdir(parents=True, exist_ok=True)
    newfile = not GAPS_MD.exists()
    with GAPS_MD.open("a", encoding="utf-8") as fh:
        if newfile:
            fh.write("> hub: [[INDEX]] · [[PIPELINE_TRAPS]]\n\n"
                     "# Verifier gaps — defects that escaped past a passing check\n\n"
                     "Each entry escaped ONCE. It is closed only when a check exists that\n"
                     "fails on its recorded case. Never delete entries; mark them CLOSED.\n\n")
        fh.write(f"## {datetime.date.today():%d %b %Y} — {name}\n")
        for c in cases:
            fh.write(f"- OPEN: {c}\n")
        fh.write("\n")
    return len(cases)

def _test():
    def draft(pngs=(), freezes=(), texts=(), tracks=1):
        vids = [{"id": f"p{i}", "path": f"/x/{n}"} for i, n in enumerate(pngs)]
        vids += [{"id": f"f{i}", "path": f"/x/{n}"} for i, n in enumerate(freezes)]
        segs = [{"material_id": m["id"],
                 "target_timerange": {"start": 0, "duration": int(3 * US)}} for m in vids]
        tm = [{"id": f"t{i}", "content": json.dumps({"text": t,
              "styles": [{"size": 5, "font": {"path": "/f/Poppins-Medium.ttf"}}]})}
              for i, t in enumerate(texts)]
        segs += [{"material_id": m["id"],
                  "target_timerange": {"start": int(9 * US), "duration": int(2 * US)}}
                 for m in tm]
        return {"materials": {"videos": vids, "texts": tm},
                "tracks": [{"name": "", "segments": segs}] * tracks}

    assert is_freeze("0123456789abcdef0123456789abcdef_8500000-sdr709.png")
    assert not is_freeze("01_Sign_in_as_Sales_Advisor.png")
    # 12 Aug: the build's own end-hold rode an unnamed track and was counted as a call-out
    # Saad had added — a phantom +1 on every video.
    assert is_build_still("T01_endhold.png") and is_build_still("T02_ENDHOLD.PNG")
    assert not is_build_still("01_Sign_in_as_Sales_Advisor.png")
    # 12 Aug: a build role label he had merely MOVED read as a step he typed himself.
    # captions are Poppins Regular and are the build's; his own labels are Poppins Medium
    capt = {"id": "cp", "content": json.dumps({"text": "Open the record, then submit it",
            "styles": [{"size": 5.0, "font": {"path": "/f/Poppins-Regular.ttf"}}]})}
    lab = {"id": "lb", "content": json.dumps({"text": "Click Submit",
           "styles": [{"size": 5.0, "font": {"path": "/f/Poppins-Medium.ttf"}}]})}
    dd = {"materials": {"texts": [capt, lab], "videos": []}, "tracks": [{"name": "regrouped",
          "segments": [{"material_id": "cp", "target_timerange": {"start": 0, "duration": 1000000}},
                       {"material_id": "lb", "target_timerange": {"start": 0, "duration": 1000000}}]}]}
    got = [x[2] for x in typed(dd)]
    assert got == ["Click Submit"], got   # the caption must not read as his work
    assert ROLE_LABEL.match("Sign in as the Sales Advisor")
    assert ROLE_LABEL.match("  sign out ")
    assert not ROLE_LABEL.match("Click Save Changes")
    assert not ROLE_LABEL.match("Signature required")

    mine = draft(pngs=["01_a.png", "02_b.png"])
    his = draft(pngs=["01_a.png", "02_b.png"],
                freezes=["0123456789abcdef0123456789abcdef_8500000-sdr709.png"],
                texts=["Sign in as Reviewer"])
    r = compare(mine, his)
    assert r["callout_pngs"] == {"mine": 2, "his": 2, "he_dropped": [], "he_added": []}, \
        "a freeze frame must never be counted as a call-out"
    assert r["freezes"]["mine"] == 0 and r["freezes"]["his"] == 1
    # A "Sign in as ..." label cannot be attributed — the build writes them too and the
    # baseline predates that step (12 Aug). It must still be REPORTED, in the bucket
    # that says so, and must never be recorded as an escaped defect.
    assert not r["typed_by_him"], r["typed_by_him"]
    assert len(r["role_labels_unattributable"]) == 1 and \
        r["role_labels_unattributable"][0]["text"] == "Sign in as Reviewer", \
        "an unattributable role label must still be surfaced, just not as his work"
    # identical drafts report nothing
    r2 = compare(mine, mine)
    assert not r2["typed_by_him"] and not r2["callout_pngs"]["he_dropped"]
    assert not r2["role_labels_unattributable"]
    assert r2["length"]["delta"] == 0
    print("sa_finaldiff self-check: ok (freeze not a call-out, typed labels found, "
          "clean diff is silent)")


if __name__ == "__main__":
    if "--test" in sys.argv:
        _test()
        sys.exit()
    ap = argparse.ArgumentParser()
    ap.add_argument("project", nargs="?")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--learn", action="store_true",
                    help="record escaped defects as permanent cases")
    ap.add_argument("--prefix", default="Training ",
                    help="with --all: the project-name prefix of the series")
    a = ap.parse_args()
    names = ([d.name for d in sorted(CAPCUT.iterdir())
              if d.is_dir() and d.name.startswith(a.prefix)]
             if a.all else [a.project])
    if not names or not names[0]:
        ap.error("give a project name or --all")
    for n in names:
        try:
            p = CAPCUT / n
            cur = sorted(glob.glob(str(p / "Timelines/*/draft_info.json")))
            bak = sorted(glob.glob(str(p / "Timelines/*/*.pre_captions")))
            if not cur or not bak:
                raise SystemExit("need both the current draft and a .pre_captions backup")
            mine, his = read(bak[0]), read(cur[0])
            r = compare(mine, his)
            show(n, r)
            if a.learn:
                g = learn(n, r, mine, his)
                if g:
                    print(f"  -> {g} escaped defect(s) recorded in Reference/VERIFIER_GAPS.md")
        except SystemExit as e:
            print(f"\n===== {n} =====\n  skipped: {e}")
