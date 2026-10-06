#!/usr/bin/env python3
"""Cut the six website crops from a stills master. Ungraded — Saad grades in Lightroom.

Requirement (21 Sep): Saad grades these himself, so this is pure geometry: never touch colour.

Always cut from the NATIVE file, never an upscale. Every crop here is <= 2560px, so a 26MP
original has detail to spare; an upscale only adds its own artefacts (one web copy once turned out
to be a 2x upscale — it was recut from the Lightroom original instead).

    sa_webcrops.py <image> [<image> ...] [--out DIR]
    sa_webcrops.py --demo
"""
import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from PIL import Image


def crop(img, ratio):
    """Centre horizontally; tall crops sit 0.38 down, so horizons run high."""
    w, h = img.size
    tw, th = ratio
    want = tw / th
    if w / h > want:                      # too wide — trim the sides, keep centre
        nw = int(round(h * want)); box = ((w - nw) // 2, 0, (w - nw) // 2 + nw, h)
    else:                                 # too tall — bias upward, horizons sit high
        nh = int(round(w / want)); top = int((h - nh) * 0.38)
        box = (0, top, w, top + nh)
    return img.crop(box)


# name -> (ratio, delivered width)
SIZES = {"hero 16x9": ((16, 9), 2560), "banner 3x1": ((3, 1), 2560),
         "card 4x3": ((4, 3), 1600), "portrait 4x5": ((4, 5), 1280),
         "square 1x1": ((1, 1), 1280), "mobile 9x16": ((9, 16), 1080)}


def cut(src, outdir):
    im = Image.open(src).convert("RGB")
    outdir.mkdir(parents=True, exist_ok=True)
    for name, (ratio, w) in SIZES.items():
        c = crop(im, ratio)
        if c.width > w:
            c = c.resize((w, round(w * c.height / c.width)), Image.LANCZOS)
        p = outdir / f"{src.stem} — {name}.jpg"
        c.save(p, quality=92, subsampling=0, optimize=True)
        yield p, c.size


def demo():
    """Every crop must hit its ratio and never be upscaled past the source."""
    im = Image.new("RGB", (6240, 4160))
    for name, (ratio, w) in SIZES.items():
        c = crop(im, ratio)
        c = c.resize((w, round(w * c.height / c.width))) if c.width > w else c
        assert abs(c.width / c.height - ratio[0] / ratio[1]) < 0.01, name
        assert c.width <= w, name
    small = Image.new("RGB", (800, 600))            # a small source must not be blown up
    c = crop(small, (16, 9))
    assert c.width <= 800, c.size
    print("demo ok")


if __name__ == "__main__":
    if "--demo" in sys.argv:
        demo(); sys.exit(0)
    ap = argparse.ArgumentParser()
    ap.add_argument("images", nargs="+")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    for s in a.images:
        src = pathlib.Path(s).expanduser()
        out = pathlib.Path(a.out).expanduser() if a.out else src.parent / "web crops (ungraded)"
        print(f"{src.name}  {Image.open(src).size[0]}x{Image.open(src).size[1]}")
        for p, size in cut(src, out):
            print(f"   {p.name:<44} {size[0]}x{size[1]}")
        print(f"   -> {out}")
