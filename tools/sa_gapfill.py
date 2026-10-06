#!/usr/bin/env python3
"""sa_gapfill — propose a call-out for each step the script asks for and nobody marked.

`sa_coverage` says WHICH steps have no call-out. This says WHERE the box should go, and
throws away its own bad guesses before anyone sees them.

    python3 sa_gapfill.py "T03"
    python3 sa_gapfill.py --all -o proposals.json
    python3 sa_gapfill.py --test

Two stages, because neither is good enough alone:

**Find** — `sa_clickdetect` (Saad's method, 4 Aug): on a static UI the only thing that moves
is the cursor, so a screen change means the cursor's last position was clicked. On one module it
found 109 clicks and matched 13 of the 16 unmarked steps.

**Verify** — each candidate is rendered with its box and put to the local vision model with
one question: is a clickable control inside this rectangle, or is it empty space? Measured on
that module: 13 candidates in, 8 kept, 5 rejected — two toasts, two blank areas, one wrong table cell.
Its rejections matched what the eye saw on a contact sheet. **Without this stage roughly half
the boxes land on nothing**, which is exactly the fault Saad has been reporting.

The click time also fixes a subtler error: a step's frame is NOT the middle of the spoken line.
One segment says "click Add Item"; the line runs 17.1-27.8s and by its midpoint the page
has already navigated. Use the click.
"""
import argparse
import glob
import json
import os
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))

VERIFY = """A green rectangle is drawn on this screenshot of a web application.

Reply strict JSON only:
{"on_control": true or false,
 "what_is_inside": "the exact button, field, dropdown or link inside the rectangle - or 'empty space' if there is no control inside it"}

on_control is TRUE only if a clickable control (button, dropdown, input, link, table row) is
inside the rectangle. If the rectangle is on blank background, on whitespace, on a toast or
success message, or on only part of a paragraph, on_control is FALSE."""


def clicks_for(tag, cache):
    """Detected clicks for one video, computed once and cached on disk."""
    p = pathlib.Path(cache) / f"{tag}_clicks.json"
    if p.exists():
        return json.load(open(p))["steps"]
    return []


def candidates(folder, cache, slack=0.5):
    """-> [{n, t, box, text, label_hint}] one per unmarked step that has a click. Pure-ish."""
    import sa_coverage as C
    r = C.analyse(folder)
    if not r:
        return []
    clicks = clicks_for(r["tag"], cache)
    out = []
    for g in r["unmarked"]:
        if g["role_change"]:
            continue                      # no login screen on these frames — different job
        inside = [c for c in clicks if g["start"] - slack <= c["t"] <= g["end"] + slack]
        if not inside:
            continue
        c = inside[0]
        out.append({"n": g["n"], "t": round(c["t"], 2), "box": list(c["box"]),
                    "text": g["text"], "verbs": g["verbs"]})
    return out


def label_from(text, verbs):
    """A short imperative label from the script line. Pure.

    Saad's labels are imperative and short — "Click Save", "Select the Model". Take the
    clause containing the action verb, not the whole sentence.
    """
    import re
    for clause in re.split(r"[.,;]", text):
        for v in verbs:
            m = re.search(rf"\b{re.escape(v)}\b", clause, re.I)
            if m:
                s = clause[m.start():].strip()
                s = re.sub(r"\s+", " ", s)
                if len(s) > 42:
                    s = s[:42].rsplit(" ", 1)[0]
                return s[0].upper() + s[1:]
    return (text[:40].rsplit(" ", 1)[0] + "").strip()


def verify(video, cands, work):
    """Drop the candidates whose box is not on a control. -> (kept, rejected)."""
    import sa_boxcheck as B
    os.makedirs(work, exist_ok=True)
    kept, dropped = [], []
    for c in cands:
        img = B.frame_with_box(video, c["t"], c["box"], [1920, 1032],
                               os.path.join(work, f"gf_{c['n']}.jpg"))
        r = B.ask(img, VERIFY) or {}
        c["saw"] = r.get("what_is_inside", "")
        (kept if r.get("on_control") else dropped).append(c)
    return kept, dropped


def run(only, out_json, cache):
    import sa_coverage as C
    allk, alld = [], []
    for folder in sorted(glob.glob(str(C.BUILD / "T*"))):
        name = os.path.basename(folder)
        if only and only not in name:
            continue
        cands = candidates(folder, cache)
        if not cands:
            continue
        tag = name.split()[0]
        video = os.path.join(folder, f"{tag}_PACED.mp4")
        if not os.path.exists(video):
            continue
        kept, dropped = verify(video, cands, os.path.join(cache, "gapfill"))
        print(f"\n=== {name} ===  {len(cands)} candidate(s) -> "
              f"{len(kept)} kept, {len(dropped)} rejected")
        for c in kept:
            print(f"  KEEP  seg {c['n']:2d} {c['t']:7.1f}s  {c['saw'][:30]:30s} "
                  f"label: {label_from(c['text'], c['verbs'])!r}")
        for c in dropped:
            print(f"  drop  seg {c['n']:2d} {c['t']:7.1f}s  {c['saw'][:30]}")
        for c in kept:
            c["video"] = name
            c["label"] = label_from(c["text"], c["verbs"])
        allk += kept
        alld += dropped
    print(f"\nTOTAL: {len(allk)} verified proposal(s), {len(alld)} rejected")
    if out_json:
        json.dump(allk, open(out_json, "w"), indent=1)
        print(f"-> {out_json}")
    return allk


def _test():
    assert label_from("When the form opens, click Add Item in the top right corner.",
                      ["click"]) == "Click Add Item in the top right corner"
    assert label_from("Here we'll select Express Delivery. Add any notes.",
                      ["select"]) == "Select Express Delivery"
    # long clauses are cut at a word boundary, never mid-word
    long = label_from("Then select the Shipping Address the order should be sent to "
                      "before confirming anything at all.", ["select"])
    assert len(long) <= 42 and not long.endswith(" ") and " " in long
    assert long.startswith("Select the Shipping")
    # a step whose verb is not in the text still yields something usable
    assert label_from("The status updates automatically.", ["click"])
    print("sa_gapfill self-check: ok (imperative label, clause pick, word-boundary cut)")


if __name__ == "__main__":
    if "--test" in sys.argv:
        _test()
        sys.exit()
    ap = argparse.ArgumentParser()
    ap.add_argument("video", nargs="?")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("-o", "--out")
    ap.add_argument("--cache", default="_gapfill_cache",
                    help="folder holding <tag>_clicks.json from sa_clickdetect")
    a = ap.parse_args()
    if not (a.video or a.all):
        ap.error("give a video name or --all")
    run(a.video, a.out, a.cache)
