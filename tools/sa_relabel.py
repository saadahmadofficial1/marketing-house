#!/usr/bin/env python3
"""sa_relabel — correct the words on a call-out without disturbing Saad's edit.

The 7 Aug terminology pass changed 16 call-out labels ("Sign in as Admin" ->
"Sign in as Administrator"). Re-running sa_stepmark --layers would rebuild them, but it
names each PNG after its label, so the corrected one lands at a NEW filename — and the CapCut
project still points at the old name. Every corrected call-out would open as missing media,
and any repositioning Saad had done would be lost.

So this redraws the PNG **in place**: same file, same path, new words inside. CapCut reloads
the pixels and knows nothing happened. Where he has dragged a box to a better spot, his
transform is on the CapCut layer, not in the file, so it survives untouched.

    Tools/venv/bin/python3 Tools/sa_relabel.py --check
    Tools/venv/bin/python3 Tools/sa_relabel.py --fix
    Tools/venv/bin/python3 Tools/sa_relabel.py --test

Pairs the stepmarks file (corrected labels) against the layers manifest (what was drawn), by
position, and redraws only the ones whose words have changed.
"""
import argparse
import glob
import json
import os
import pathlib
import shutil
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
SERIES = pathlib.Path(os.environ.get("TRAINING_ROOT", "~/Downloads/training-series")).expanduser()
BUILD = SERIES / "2 BUILD"


def pairs(folder):
    """-> [(layer dict, corrected label)] for one build folder, matched by index.

    Matched by position, not by name: the name is exactly what changed. The stepmarks file
    and the layers manifest are written from the same list in the same order, so index n in
    one is index n in the other — asserted below rather than assumed.
    """
    sm = glob.glob(os.path.join(folder, "*_stepmarks.json"))
    lm = glob.glob(os.path.join(folder, "*_LAYERS", "_layers.json"))
    if not sm or not lm:
        return None, []
    steps = json.load(open(sm[0], encoding="utf-8"))
    steps = steps.get("steps", steps if isinstance(steps, list) else [])
    man = json.load(open(lm[0], encoding="utf-8"))
    layers = man.get("layers", [])
    if len(steps) != len(layers):
        print(f"  ! {os.path.basename(folder)}: {len(steps)} steps vs {len(layers)} layers "
              f"— skipping rather than guessing which is which")
        return lm[0], []
    out = []
    for s, L in zip(steps, layers):
        if s.get("label") != L.get("label"):
            out.append((L, s["label"], s))
    return lm[0], out


def redraw(layer, label, step, canvas):
    """Rewrite one PNG at its existing path with the corrected words."""
    import sa_stepmark
    img = sa_stepmark.render_step(tuple(canvas), tuple(step["box"]), label)
    path = layer["file"]
    if not os.path.exists(path):
        raise SystemExit(f"the layer file has moved: {path}")
    if not os.path.exists(path + ".pre_relabel"):
        shutil.copy2(path, path + ".pre_relabel")
    img.save(path)                       # same name, same place — CapCut never notices
    return path


def run(apply_it):
    total = 0
    for folder in sorted(glob.glob(str(BUILD / "*"))):
        if not os.path.isdir(folder):
            continue
        man_path, changed = pairs(folder)
        if not changed:
            continue
        canvas = json.load(open(man_path, encoding="utf-8")).get("canvas", [1920, 1140])
        for layer, label, step in changed:
            print(f"  {os.path.basename(folder)[:26]:26s} \"{layer['label']}\" -> \"{label}\"")
            print(f"       {os.path.basename(layer['file'])}  (filename kept)")
            if apply_it:
                redraw(layer, label, step, canvas)
                layer["label"] = label
            total += 1
        if apply_it:
            man = json.load(open(man_path, encoding="utf-8"))
            for L, (layer, label, _s) in zip(
                    [m for m in man["layers"] if m["file"] in {c[0]["file"] for c in changed}],
                    changed):
                L["label"] = label
            json.dump(man, open(man_path, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(f"\n{total} call-out image(s) {'redrawn' if apply_it else 'would be redrawn'}, "
          f"0 filenames changed")
    return total


def _test():
    # the guarantee that matters: the path never changes, so CapCut never loses the layer
    import tempfile
    from PIL import Image
    d = tempfile.mkdtemp()
    p = os.path.join(d, "08_Sign_in_as_Admin.png")
    Image.new("RGBA", (40, 20)).save(p)
    before = os.path.realpath(p)
    import sa_stepmark
    img = sa_stepmark.render_step((400, 300), (10, 10, 80, 30), "Sign in as Administrator")
    shutil.copy2(p, p + ".pre_relabel")
    img.save(p)
    assert os.path.realpath(p) == before, "the PNG must keep its exact path"
    assert os.path.exists(p + ".pre_relabel"), "the original is kept, so this is reversible"
    assert Image.open(p).size == (400, 300), "and it is redrawn full-canvas"
    # a folder whose two files disagree in length is skipped, never guessed at
    empty = tempfile.mkdtemp()
    json.dump({"steps": [{"label": "a"}]}, open(os.path.join(empty, "x_stepmarks.json"), "w"))
    os.makedirs(os.path.join(empty, "x_LAYERS"))
    json.dump({"layers": []}, open(os.path.join(empty, "x_LAYERS", "_layers.json"), "w"))
    assert pairs(empty)[1] == [], "mismatched counts must yield nothing to change"
    print("sa_relabel self-check: ok (path preserved, backup kept, mismatch refused)")


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
