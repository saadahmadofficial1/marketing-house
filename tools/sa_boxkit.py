#!/usr/bin/env python3
"""sa_boxkit — a library of empty call-out boxes as transparent PNGs.

Saad marks up screen recordings in CapCut and adds his own text, so these are
deliberately EMPTY: drop one on the timeline, scale it over the button, type
the label yourself.

  Tools/venv/bin/python3 Tools/sa_boxkit.py --out ~/Downloads/SA_BoxKit
  Tools/venv/bin/python3 Tools/sa_boxkit.py --test

Everything is drawn at 4x and downsampled, so edges stay clean when scaled in
CapCut. Sizes are the intended size on a 1920x1080 timeline — scale DOWN from a
bigger one rather than up from a smaller one, or the stroke goes soft.
"""
import argparse
import os
import sys

from PIL import Image, ImageDraw

SS = 4          # supersample factor — drawn big, shrunk down, edges stay sharp
RADIUS = 12     # corner radius at final size
STROKE = 6      # stroke weight at final size

# name -> #hex. The blue matches the UI being recorded; swap in your own product's colour.
COLOURS = {
    "UI-Blue":   "#3949AB",
    "White":     "#FFFFFF",
    "Black":     "#111318",
    "Red":       "#D92D20",
    "Green":     "#12B76A",
    "Amber":     "#F79009",
}

# name -> (w, h) at final size on a 1920x1080 canvas
SIZES = {
    "XS-140x44":     (140, 44),
    "S-240x56":      (240, 56),
    "M-380x64":      (380, 64),
    "L-560x72":      (560, 72),
    "XL-820x80":     (820, 80),
    "LONG-1300x70":  (1300, 70),
    "SQ-S-120":      (120, 120),
    "SQ-L-260":      (260, 260),
}


def _rgba(hex_colour, alpha=255):
    h = hex_colour.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) + (alpha,)


def make_box(w, h, hex_colour, filled, radius=RADIUS, stroke=STROKE, sharp=False):
    """One transparent PNG. filled=True gives a solid block, False an outline."""
    W, H = w * SS, h * SS
    pad = stroke * SS          # room so the stroke is never clipped
    img = Image.new("RGBA", (W + pad * 2, H + pad * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    box = [pad, pad, pad + W, pad + H]
    r = 0 if sharp else radius * SS
    col = _rgba(hex_colour)
    if filled:
        d.rounded_rectangle(box, radius=r, fill=col)
    else:
        d.rounded_rectangle(box, radius=r, outline=col, width=stroke * SS)
    return img.resize(((W + pad * 2) // SS, (H + pad * 2) // SS), Image.LANCZOS)


def build(outdir):
    made = 0
    for cname, chex in COLOURS.items():
        for style, filled in (("stroke", False), ("fill", True)):
            for corner, sharp in (("rounded", False), ("sharp", True)):
                folder = os.path.join(outdir, cname, f"{style}-{corner}")
                os.makedirs(folder, exist_ok=True)
                for sname, (w, h) in SIZES.items():
                    img = make_box(w, h, chex, filled, sharp=sharp)
                    img.save(os.path.join(folder, f"{cname}_{style}_{corner}_{sname}.png"))
                    made += 1
    return made


def _test():
    s = make_box(240, 56, "#3949AB", filled=False)
    assert s.mode == "RGBA"
    # outline: centre must be transparent, edge must not be
    cx, cy = s.width // 2, s.height // 2
    assert s.getpixel((cx, cy))[3] == 0, "stroke box should be hollow"
    f = make_box(240, 56, "#3949AB", filled=True)
    assert f.getpixel((cx, cy))[3] > 250, "fill box should be solid"
    sq = make_box(120, 120, "#FFFFFF", filled=False, sharp=True)
    assert abs(sq.width - sq.height) < 3, "square should stay square"
    print("sa_boxkit self-check: ok (stroke hollow, fill solid, square stays square)")


if __name__ == "__main__":
    if "--test" in sys.argv:
        _test()
        sys.exit()
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.expanduser("~/Downloads/SA_BoxKit"))
    a = ap.parse_args()
    n = build(a.out)
    print(f"{n} boxes -> {a.out}")
    print(f"  {len(COLOURS)} colours x {len(SIZES)} sizes x stroke/fill x rounded/sharp")
