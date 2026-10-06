#!/usr/bin/env python3
"""Apply measured call-out corrections to a build, safely.

Written after fixing 38 call-outs by hand across three modules on 12-13 Aug. The
method that worked, in order:

  1. VALIDATE every box against the canvas. Trap 35: a box written x1,y1,x2,y2 into
     an x,y,w,h field drew 1895px wide off the screen and nothing noticed.
  2. DETECT COLLISIONS. Corrections are measured by independent agents that cannot
     see each other, so two of them retimed onto the SAME row 0.05s apart. Anything
     that ends up overlapping in time on a similar box is reported, never applied.
  3. Update the manifest, then re-render the PNG at the NEW time so the label chip is
     placed against the frame it will actually sit on.
  4. Only retimes need the CapCut draft touched (Trap 36) — a box change is picked up
     automatically because the PNGs are full-canvas at scale 1 / offset 0.

    sa_applyfix.py <manifest> <corrections.json> --dry-run
    sa_applyfix.py <manifest> <corrections.json> --apply --draft "<project>"

corrections.json: [{n, decision, new_t, dur, box, new_label, confidence}, …] where n
indexes the manifest in order (1-based), matching Tools/sa_qasheet.py output.
"""
import datetime
import json
import pathlib
import shutil
import sys

US = 1_000_000
SKIP = {"leave", "drop"}


def load_manifest(path):
    data = json.loads(pathlib.Path(path).read_text())
    if "layers" in data:
        return data, data["layers"], "layers"
    items = data if isinstance(data, list) else data.get("marks", data.get("steps"))
    return data, items, "marks"


def get_t(item, kind):
    return item["start"] if kind == "layers" else item["t"]


def set_t(item, kind, t, dur):
    if kind == "layers":
        item["start"], item["duration"] = t, dur
    else:
        item["t"], item["dur"] = t, dur


def validate(box, canvas):
    x, y, w, h = box
    W, H = canvas
    problems = []
    if w <= 0 or h <= 0:
        problems.append("non-positive w/h")
    if x < 0 or y < 0:
        problems.append("negative origin")
    if x + w > W:
        problems.append(f"{x + w - W}px past the right edge")
    if y + h > H:
        problems.append(f"{y + h - H}px past the bottom")
    return problems


def overlaps(a, b):
    """Do two (t, dur, box) land on top of each other in time AND space?"""
    (t1, d1, b1), (t2, d2, b2) = a, b
    if t1 + d1 <= t2 or t2 + d2 <= t1:
        return False
    # centres within 60px in both axes = effectively the same target
    c1 = (b1[0] + b1[2] / 2, b1[1] + b1[3] / 2)
    c2 = (b2[0] + b2[2] / 2, b2[1] + b2[3] / 2)
    return abs(c1[0] - c2[0]) < 60 and abs(c1[1] - c2[1]) < 60


def plan(manifest_path, corrections, canvas):
    data, items, kind = load_manifest(manifest_path)
    fixes, blocked = [], []
    for c in corrections:
        if c["decision"] in SKIP:
            blocked.append((c, f"decision={c['decision']}"))
            continue
        idx = c["n"] - 1
        if not 0 <= idx < len(items):
            blocked.append((c, f"n={c['n']} outside manifest (1..{len(items)})"))
            continue
        bad = validate(c["box"], canvas)
        if bad:
            blocked.append((c, "; ".join(bad)))
            continue
        fixes.append((idx, c))

    # collision check across the POST-fix state of every item
    final = []
    fixed_idx = {i for i, _ in fixes}
    for i, item in enumerate(items):
        if i in fixed_idx:
            c = next(c for j, c in fixes if j == i)
            final.append((i, c["new_t"], c["dur"], c["box"]))
        else:
            final.append((i, get_t(item, kind),
                          item.get("duration", item.get("dur", 2.1)), item["box"]))
    clashes = []
    for a in range(len(final)):
        for b in range(a + 1, len(final)):
            if a not in fixed_idx and b not in fixed_idx:
                continue                      # pre-existing overlaps are not ours
            if overlaps(final[a][1:], final[b][1:]):
                clashes.append((final[a][0], final[b][0]))
    return data, items, kind, fixes, blocked, clashes


def main():
    argv = sys.argv[1:]
    if len(argv) < 2:
        sys.exit(__doc__)
    manifest_path, corr_path = argv[0], argv[1]
    apply_it = "--apply" in argv
    draft = None
    if "--draft" in argv:
        draft = argv[argv.index("--draft") + 1]

    corrections = json.loads(pathlib.Path(corr_path).read_text())
    if isinstance(corrections, dict):
        corrections = corrections.get("corrections", [])

    data, items, kind, fixes, blocked, clashes = plan(
        manifest_path, corrections, (1920, 1032))

    print(f"{len(fixes)} applicable · {len(blocked)} blocked · {len(clashes)} collisions\n")
    for c, why in blocked:
        print(f"  BLOCKED n={c['n']:<3} {why}")
    for a, b in clashes:
        ta = get_t(items[a], kind)
        tb = get_t(items[b], kind)
        print(f"  COLLISION items {a + 1} and {b + 1} "
              f"({items[a].get('label', '')[:28]} @{ta:.2f} / "
              f"{items[b].get('label', '')[:28]} @{tb:.2f}) — same target, overlapping time")
    if clashes:
        print("\n  resolve collisions before applying: drop one, or separate them in time")
    if not apply_it:
        print("\n  dry run — nothing written. Add --apply to commit.")
        return 1 if (blocked or clashes) else 0
    if clashes:
        print("\n  refusing to apply while collisions stand.")
        return 1

    sys.path.insert(0, str(pathlib.Path(__file__).parent))
    import cv2
    import sa_stepmark
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    mp = pathlib.Path(manifest_path)
    shutil.copy2(mp, mp.with_suffix(mp.suffix + f".bak_{stamp}"))
    video = pathlib.Path(data["video"])
    cap = cv2.VideoCapture(str(video))
    canvas = (int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))
    retimed = []
    for idx, c in fixes:
        item = items[idx]
        old_t = get_t(item, kind)
        item["box"] = c["box"]
        if c.get("new_label"):
            item["label"] = c["new_label"]
        set_t(item, kind, c["new_t"], c["dur"])
        cap.set(cv2.CAP_PROP_POS_MSEC, (c["new_t"] + 0.4) * 1000)
        ok, frame = cap.read()
        img, chip = sa_stepmark.render_step(canvas, tuple(int(v) for v in c["box"]),
                                             item["label"], frame=frame if ok else None,
                                             want_chip=True)
        png = pathlib.Path(item["file"])
        png = png if png.is_absolute() else mp.parent / png
        shutil.copy2(png, png.with_suffix(f".png.bak_{stamp}"))
        img.save(png)
        item["chip"] = chip
        if abs(c["new_t"] - old_t) > 0.01:
            retimed.append((png.name, old_t, c["new_t"], c["dur"]))
        print(f"  n={c['n']:<3} {item['label'][:38]:<38} t {old_t:7.2f}->{c['new_t']:7.2f} box={c['box']}")
    cap.release()
    mp.write_text(json.dumps(data, indent=1))

    if retimed and draft:
        dpath = pathlib.Path.home() / "Movies/CapCut/User Data/Projects/com.lveditor.draft" / draft / "draft_info.json"
        dd = json.loads(dpath.read_text())
        shutil.copy2(dpath, dpath.parent / f"draft_info.json.bak_{stamp}")
        mats = {m["id"]: m for m in dd["materials"]["videos"]}
        hits = 0
        for name, old_t, new_t, dur in retimed:
            # A draft that has already been hand-retimed no longer matches the manifest's
            # times (one module had 13 boxes retimed earlier, so 8 of 15 missed on an
            # exact match). The draft is the truth for timing, so match by PNG and take
            # the segment nearest either time — but only within 3s, so a PNG reused
            # elsewhere in the timeline can never be grabbed by mistake.
            cands = []
            for track in dd["tracks"]:
                for s in track.get("segments") or []:
                    p = (mats.get(s.get("material_id")) or {}).get("path") or ""
                    if pathlib.Path(p).name != name:
                        continue
                    start = (s.get("target_timerange") or {}).get("start", 0) / US
                    gap = min(abs(start - old_t), abs(start - new_t))
                    if gap < 3.0:
                        cands.append((gap, start, s))
            if not cands:
                print(f"    no draft segment within 3s for {name} — left alone")
                continue
            best = min(c[0] for c in cands)
            for gap, start, s in cands:
                if gap > best + 0.01:
                    continue                  # duplicates at the same instant both move
                tr = s["target_timerange"]
                if abs(start - old_t) > 0.06:
                    print(f"    note: {name} sat at {start:.2f}s in the draft, "
                          f"not the manifest's {old_t:.2f}s — draft had diverged")
                tr["start"] = int(round(new_t * US))
                tr["duration"] = int(round(dur * US))
                sr = s.get("source_timerange")
                if sr:
                    sr["start"], sr["duration"] = 0, int(round(dur * US))
                hits += 1
        dpath.write_text(json.dumps(dd))
        print(f"\n  draft '{draft}': {hits}/{len(retimed)} segments retimed")
    elif retimed:
        print(f"\n  {len(retimed)} retimes need a draft edit — rerun with --draft \"<project>\"")
    print(f"\n  backups: *_{stamp}")
    return 0


def demo():
    """Self-check: an off-canvas box is blocked, and two fixes on one target collide."""
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        d = pathlib.Path(d)
        m = d / "_layers.json"
        m.write_text(json.dumps({"video": "/v.mp4", "canvas": [1920, 1032], "layers": [
            {"start": 10.0, "duration": 2.0, "box": [100, 100, 50, 20], "label": "A", "file": "a.png"},
            {"start": 30.0, "duration": 2.0, "box": [800, 100, 50, 20], "label": "B", "file": "b.png"},
            {"start": 50.0, "duration": 2.0, "box": [900, 900, 50, 20], "label": "C", "file": "c.png"}]}))
        corr = [{"n": 1, "decision": "rebox", "new_t": 10.0, "dur": 2.0,
                 "box": [1777, 113, 1895, 143], "new_label": "", "confidence": "high"},
                {"n": 2, "decision": "retime", "new_t": 50.1, "dur": 2.0,
                 "box": [905, 905, 50, 20], "new_label": "", "confidence": "high"}]
        _, items, kind, fixes, blocked, clashes = plan(m, corr, (1920, 1032))
        assert len(blocked) == 1 and "past the right edge" in blocked[0][1], blocked
        assert len(fixes) == 1, fixes
        assert clashes, "fix 2 lands on item 3's target at the same time — must collide"
    print("demo ok")


if __name__ == "__main__":
    sys.exit(demo() if "--demo" in sys.argv else main())
