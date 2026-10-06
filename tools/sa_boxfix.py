#!/usr/bin/env python3
"""sa_boxfix — re-centre a sidebar call-out on the row that is actually selected.

Six call-outs across the series sat exactly one row too high on the left-hand navigation
menu: each "Open <item>" box landed on the menu item above the one being taught. Confirmed by
eye 8 Aug.

Why it happens: the element detector reads the plain-text menu item, and the one the trainee
is being sent to is the row *below* — the highlighted, currently-active one. On the app's sidebar
that row is a saturated navy band, so it can be found by colour and the box moved onto it.

    Tools/venv/bin/python3 Tools/sa_boxfix.py --check       # what it would move
    Tools/venv/bin/python3 Tools/sa_boxfix.py --fix
    Tools/venv/bin/python3 Tools/sa_boxfix.py --test

Only the confirmed call-outs listed in TARGETS are touched, and only their `box` in the stepmarks plus the
PNG redrawn in place by sa_relabel's method — filename unchanged, so a layer Saad has already
positioned in CapCut does not move.
"""
import argparse
import glob
import json
import os
import pathlib
import shutil
import subprocess
import sys

BUILD = pathlib.Path(os.environ.get("TRAINING_ROOT", "~/Downloads/training-series")).expanduser() / "2 BUILD"
WORK = pathlib.Path(os.environ.get("TMPDIR", "/tmp")) / "sa_boxfix"

# (build folder, 1-based layer number, what it should be on). Example entries: list the
# call-outs you have confirmed by eye, here or as JSON triples in SA_BOXFIX_TARGETS.
TARGETS = [tuple(t) for t in json.loads(os.environ.get("SA_BOXFIX_TARGETS", "[]"))] or [
    ("T01 Example Module", 2, "Menu item A"),
    ("T01 Example Module", 15, "Menu item A"),
    ("T02 Example Module", 5, "Menu item B"),
]

SIDEBAR_X = (20, 340)       # the app's left menu, in source pixels
MIN_ROW_H = 16


def ink_rows(png, x_range=SIDEBAR_X):
    """-> [(y0, y1)] of every menu row in the sidebar, top to bottom.

    A row is a horizontal band containing ink — the icon and its label — separated from its
    neighbours by blank background. Works whether or not the row is highlighted.

    An earlier version looked for the highlighted navy row instead. That finds the page the
    user is currently ON, which is only the target AFTER they have clicked it. On one call-out it
    proposed moving the box onto the page already open (8 Aug). The reliable rule, confirmed on the
    frames, is that the right item is the row DIRECTLY BELOW the one the box landed on.
    """
    from PIL import Image
    im = Image.open(png).convert("RGB")
    W, H = im.size
    px = im.load()
    x0, x1 = max(0, x_range[0]), min(W, x_range[1])
    counts = []
    for y in range(H):
        n = 0
        for x in range(x0, x1, 3):
            r, g, b = px[x, y]
            if r + g + b < 560:                 # anything not near-white background
                n += 1
        counts.append(n)
    rows, start = [], None
    for y, n in enumerate(counts):
        if n >= 3 and start is None:
            start = y
        elif n < 3 and start is not None:
            if y - start >= 8:
                rows.append((start, y))
            start = None
    if start is not None and H - start >= 8:
        rows.append((start, H))
    return rows


def row_pitch(rows, lo=18, hi=40):
    """Distance between one menu row and the next. -> float or None.

    Taking "the next detected band" was wrong: an icon and its label can land in separate
    bands, and a tall band can swallow two rows, so the shift came out as +82 or +55 where a
    row is about 26px (9 Aug). The pitch is stable even when individual bands are not — take
    the median gap between row starts, ignoring gaps too small or too large to be one row.
    """
    starts = [a for a, _b in rows]
    gaps = sorted(b - a for a, b in zip(starts, starts[1:]) if lo <= b - a <= hi)
    if len(gaps) < 3:
        return None
    return gaps[len(gaps) // 2]


def shift_one_row(box, pitch):
    """Move the box down by exactly one menu row, keeping its size. Pure."""
    x, y, w, h = box
    return [x, int(round(y + pitch)), w, h]


def recentre(box, band, pad=7):
    """Put the box over the band, keeping its x and width. Pure."""
    x, _y, w, _h = box
    a, b = band
    return [x, max(0, int(a - pad)), w, int(b - a + 2 * pad)]


def frame(video, t, out):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", str(video),
                    "-frames:v", "1", str(out)], check=True)
    return out


def run(apply_it):
    sys.path.insert(0, str(pathlib.Path(__file__).parent))
    import sa_stepmark
    work = WORK
    work.mkdir(parents=True, exist_ok=True)
    moved = 0
    for folder, n, should_be in TARGETS:
        tag = folder.split()[0]
        man_p = BUILD / folder / f"{tag}_PACED_LAYERS" / "_layers.json"
        if not man_p.exists():
            print(f"  ! {tag} #{n}: no manifest")
            continue
        man = json.load(open(man_p))
        L = man["layers"][n - 1]
        t = L["start"] + L["duration"] / 2
        shot = frame(man["video"], t, work / f"{tag}_{n}.png")
        pitch = row_pitch(ink_rows(shot))
        if not pitch:
            print(f"  ! {tag} #{n}: could not measure the row pitch — leaving alone")
            continue
        new = shift_one_row(L["box"], pitch)
        dy = new[1] - L["box"][1]
        print(f"  {tag} #{n:2d} '{L['label'][:26]:26s}' -> {should_be:14s} "
              f"y {L['box'][1]} -> {new[1]}  ({dy:+d}px)")
        if not apply_it:
            continue
        # redraw the PNG at its existing path so CapCut keeps the layer
        img = sa_stepmark.render_step(tuple(man.get("canvas", [1920, 1140])),
                                       tuple(new), L["label"])
        p = L["file"]
        if not os.path.exists(p + ".pre_boxfix"):
            shutil.copy2(p, p + ".pre_boxfix")
        img.save(p)
        L["box"] = new
        json.dump(man, open(man_p, "w"), indent=1, ensure_ascii=False)
        # keep the stepmarks source in step so a rebuild does not undo it
        sm = glob.glob(str(BUILD / folder / f"{tag}_stepmarks.json"))
        if sm:
            d = json.load(open(sm[0]))
            steps = d.get("steps", d if isinstance(d, list) else [])
            if n - 1 < len(steps) and isinstance(steps[n - 1], dict):
                if not os.path.exists(sm[0] + ".pre_boxfix"):
                    shutil.copy2(sm[0], sm[0] + ".pre_boxfix")
                steps[n - 1]["box"] = new
                json.dump(d, open(sm[0], "w"), indent=1, ensure_ascii=False)
        moved += 1
    print(f"\n{moved} box(es) {'moved' if apply_it else 'would move'}, 0 filenames changed")
    return moved


def _test():
    # one row down, size untouched
    assert shift_one_row([15, 400, 210, 42], 26) == [15, 426, 210, 42]
    assert shift_one_row([15, 400, 210, 42], 26.4)[1] == 426
    # pitch is the median gap, immune to a band that swallowed two rows or split one
    rows = [(100, 120), (126, 146), (152, 172), (178, 198), (204, 224)]
    assert row_pitch(rows) == 26
    noisy = rows + [(230, 236)]          # a stray thin band does not move the median
    assert row_pitch(noisy) == 26
    assert row_pitch([(0, 10), (200, 210)]) is None, "too few rows to measure a pitch"
    assert row_pitch([(0, 5), (3, 8), (6, 11)]) is None, "gaps below a real row are ignored"
    # ink_rows finds the menu rows on a synthetic sidebar
    from PIL import Image
    im = Image.new("RGB", (400, 300), (250, 250, 252))
    for k in range(5):
        top = 60 + k * 26
        for yy in range(top, top + 14):
            for xx in range(24, 240):
                im.putpixel((xx, yy), (40, 44, 60))
    q = str(WORK / "_bf.png")
    os.makedirs(os.path.dirname(q), exist_ok=True)
    im.save(q)
    rr = ink_rows(q, (20, 340))
    assert len(rr) == 5, f"expected 5 menu rows, found {len(rr)}"
    assert row_pitch(rr) == 26, row_pitch(rr)
    # a blank sidebar yields no pitch, so the caller leaves the box alone
    Image.new("RGB", (400, 300), (250, 250, 252)).save(q)
    assert row_pitch(ink_rows(q, (20, 340))) is None
    print("sa_boxfix self-check: ok (one-row shift, median pitch, row detection, "
          "refuses when it cannot measure)")


if __name__ == "__main__":
    if "--test" in sys.argv:
        _test()
        sys.exit()
    ap = argparse.ArgumentParser()
    ap.add_argument("--fix", action="store_true")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    if not (a.fix or a.check):
        ap.error("give --check or --fix")
    run(a.fix)
