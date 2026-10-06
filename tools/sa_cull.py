#!/usr/bin/env python3
"""sa_cull — deterministic stills culling. Zero tokens, zero Ollama.

Scores every JPG on sharpness / exposure / clipping / level, groups near-duplicate
frames (brackets + burst re-shoots of the same composition), and picks the best of
each group. Built for real-estate property shoots but nothing in it is property-specific.

    sa_cull.py "~/Downloads/Property Shoot/Unit 101" -o /tmp/unit101
    sa_cull.py "…/Property Shoot" --recurse -o /tmp/shoot      # every subfolder
    sa_cull.py … --sheet          # also write contact sheets of the picks

Writes cull.json (every frame scored) + picks.txt (the keepers) into -o.
Reads only; never moves or modifies a source file.
"""
import argparse, json, os, sys, glob
from datetime import datetime
import cv2, numpy as np
from PIL import Image, ExifTags

TAGS = {v: k for k, v in ExifTags.TAGS.items()}


def exif(path):
    try:
        e = Image.open(path).getexif()
    except Exception:
        return {}
    g = lambda n: e.get(TAGS.get(n))
    out = {"dt": g("DateTimeOriginal") or g("DateTime"), "iso": g("ISOSpeedRatings"),
           "f": g("FNumber"), "exp": g("ExposureTime"), "focal": g("FocalLength"),
           "orient": g("Orientation"), "model": g("Model")}
    for k in ("f", "exp", "focal"):
        v = out[k]
        if v is not None:
            try: out[k] = round(float(v), 4)
            except Exception: out[k] = None
    return out


def score(path):
    """Quarter-res read: 6000x4000 -> 1500x1000. Plenty for sharpness ranking."""
    img = cv2.imread(path, cv2.IMREAD_REDUCED_COLOR_4)
    if img is None:
        return None
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    lum = float(g.mean())
    # ponytail: Laplacian variance is the standard cheap focus measure. It ranks
    # frames of the SAME scene reliably, which is all grouping needs — comparing it
    # across different scenes is meaningless, so we only ever compare within a group.
    sharp = float(cv2.Laplacian(g, cv2.CV_64F).var())
    hi = float((g >= 250).mean() * 100)
    lo = float((g <= 5).mean() * 100)
    # 16x16 average hash for grouping near-identical compositions
    small = cv2.resize(g, (16, 16), interpolation=cv2.INTER_AREA)
    ah = (small > small.mean()).flatten()
    return {"sharp": round(sharp, 1), "lum": round(lum, 1),
            "clip_hi": round(hi, 2), "clip_lo": round(lo, 2), "hash": ah}


def hamming(a, b):
    return int(np.count_nonzero(a != b))


def group(frames, thresh=28):
    """Chain consecutive frames whose hashes are close — brackets and re-shoots of
    one composition land in one group. Sequential only: a corridor shot revisited
    20 frames later is a deliberate second angle, not a duplicate."""
    groups, cur = [], []
    for fr in frames:
        if cur and hamming(cur[-1]["hash"], fr["hash"]) <= thresh:
            cur.append(fr)
        else:
            if cur: groups.append(cur)
            cur = [fr]
    if cur: groups.append(cur)
    return groups


def pick(g):
    """Best of a group: sharpest, but reject anything badly clipped if a clean
    alternative exists."""
    clean = [f for f in g if f["clip_hi"] < 8 and f["clip_lo"] < 8] or g
    return max(clean, key=lambda f: f["sharp"])


def run(folder, out, sheet=False):
    jpgs = sorted(glob.glob(os.path.join(folder, "*.JPG")) +
                  glob.glob(os.path.join(folder, "*.jpg")))
    if not jpgs:
        return None
    frames = []
    for p in jpgs:
        s = score(p)
        if s is None:
            print(f"  ! unreadable {os.path.basename(p)}", file=sys.stderr); continue
        s["file"] = os.path.basename(p); s["path"] = p; s.update(exif(p))
        frames.append(s)
    groups = group(frames)
    picks = [pick(g) for g in groups]
    name = os.path.basename(folder.rstrip("/"))
    os.makedirs(out, exist_ok=True)
    rec = {"folder": folder, "unit": name, "frames": len(frames),
           "groups": len(groups),
           "picks": [{k: f[k] for k in
                      ("file", "sharp", "lum", "clip_hi", "clip_lo", "dt", "iso", "f", "exp", "focal")}
                     for f in picks],
           "all": [{k: f[k] for k in
                    ("file", "sharp", "lum", "clip_hi", "clip_lo", "dt")} for f in frames]}
    with open(os.path.join(out, f"cull_{name}.json"), "w") as fh:
        json.dump(rec, fh, indent=1)
    with open(os.path.join(out, f"picks_{name}.txt"), "w") as fh:
        fh.write("\n".join(f["path"] for f in picks) + "\n")
    if sheet:
        contact(picks, os.path.join(out, f"sheet_{name}.jpg"))
    return rec


def contact(picks, dest, cols=6, tile=400):
    rows = (len(picks) + cols - 1) // cols
    canvas = np.full((rows * tile, cols * tile, 3), 24, np.uint8)
    for i, f in enumerate(picks):
        im = cv2.imread(f["path"], cv2.IMREAD_REDUCED_COLOR_8)
        if im is None: continue
        h, w = im.shape[:2]; s = min(tile / w, tile / h)
        im = cv2.resize(im, (int(w * s), int(h * s)))
        y, x = (i // cols) * tile, (i % cols) * tile
        canvas[y:y + im.shape[0], x:x + im.shape[1]] = im
        # ponytail: label INSIDE the tile, not in the gutter below it. A cell is taller
        # than a landscape frame, so a bottom-of-cell label floats nearer the NEXT row
        # and gets read against the wrong picture. Cost a wrong frame number once.
        lab = f["file"].rsplit(".", 1)[0]
        w = int(11 * len(lab)) + 12
        cv2.rectangle(canvas, (x, y), (x + w, y + 26), (0, 0, 0), -1)
        cv2.putText(canvas, lab, (x + 6, y + 19),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 2, cv2.LINE_AA)
    cv2.imwrite(dest, canvas, [cv2.IMWRITE_JPEG_QUALITY, 88])



def walk(folder, out, per=24, cols=4, tile=600):
    """Chunked contact sheets of EVERY frame in shoot order — the walk-through.

    sa_cull ranks frames; this one just shows them all, in the order they were taken,
    big enough to read a room. Sequence IS the circulation of the unit, so keeping
    shoot order is the whole point — never sort these by score.
    """
    import glob
    jpgs = sorted(glob.glob(os.path.join(folder, "*.JPG")) +
                  glob.glob(os.path.join(folder, "*.jpg")))
    name = os.path.basename(folder.rstrip("/"))
    os.makedirs(out, exist_ok=True)
    made = []
    for n, i in enumerate(range(0, len(jpgs), per), 1):
        chunk = [{"path": f, "file": os.path.basename(f)} for f in jpgs[i:i + per]]
        dest = os.path.join(out, f"walk_{name}_{n:02d}.jpg")
        contact(chunk, dest, cols=cols, tile=tile)
        made.append(dest)
    return made


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--recurse", action="store_true", help="score each subfolder separately")
    ap.add_argument("--sheet", action="store_true")
    ap.add_argument("--walk", action="store_true", help="chunked sheets of EVERY frame in shoot order")
    ap.add_argument("--per", type=int, default=24)
    a = ap.parse_args()
    root = os.path.expanduser(a.folder); out = os.path.expanduser(a.out)
    targets = ([os.path.join(root, d) for d in sorted(os.listdir(root))
                if os.path.isdir(os.path.join(root, d))] if a.recurse else [root])
    for t in targets:
        if a.walk:
            m = walk(t, out, a.per)
            print(f"{os.path.basename(t)}: {len(m)} walk sheets")
        r = run(t, out, a.sheet)
        if r:
            print(f"{r['unit']}: {r['frames']} frames -> {r['groups']} compositions, {len(r['picks'])} picks")


def demo():
    """assert-based self-check: grouping + pick logic."""
    h = lambda bits: np.array(bits, bool)
    a = h([0] * 256); b = h([1] * 10 + [0] * 246); c = h([1] * 256)
    f = lambda n, hh, sh, hi=0: {"file": n, "hash": hh, "sharp": sh, "clip_hi": hi, "clip_lo": 0}
    gs = group([f("a", a, 10), f("b", b, 99), f("c", c, 50)])
    assert [len(g) for g in gs] == [2, 1], gs          # a+b chain, c breaks
    assert pick(gs[0])["file"] == "b"                   # sharpest wins
    blown = [f("x", a, 999, hi=50), f("y", a, 10, hi=0)]
    assert pick(blown)["file"] == "y"                   # clipped loses to clean
    assert pick([f("x", a, 999, hi=50)])["file"] == "x" # unless it's all there is
    print("sa_cull demo ok")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "demo": demo()
    else: main()
