#!/usr/bin/env python3
"""Make an EXACT .cube from a Lightroom look via an identity image (no approximation).
  sa_lut.py identity [out.png] [--size 33]   # 1) make reference image
  sa_lut.py frompng <graded.png> [out.cube]  # 3) graded reference -> .cube

Workflow: (1) make identity PNG -> (2) import to Lightroom, apply your preset,
export as PNG (sRGB, NO sharpening/resize) -> (3) frompng converts it to .cube.
Layout: width=size*size, height=size; pixel(x,y): b=x//size, r=x%size, g=y.
"""
import sys
import numpy as np
from PIL import Image

def identity(out, size=33):
    w = size*size
    a = np.zeros((size, w, 3), np.uint8)
    for b in range(size):
        for r in range(size):
            for g in range(size):
                a[g, b*size+r] = [round(r*255/(size-1)),
                                  round(g*255/(size-1)),
                                  round(b*255/(size-1))]
    Image.fromarray(a).save(out)
    print("identity ->", out, f"({w}x{size}, {size}^3)")

def frompng(src, out, size=33):
    a = np.asarray(Image.open(src).convert("RGB"))
    h, w, _ = a.shape
    if w != size*size or h != size:
        size = round((w*h)**(1/3))  # recover size if resized oddly
        if w != size*size or h != size:
            sys.exit(f"image is {w}x{h}, not a {size}^3 identity layout — re-export without resizing")
    lines = [f'TITLE "{src.split("/")[-1]}"', f"LUT_3D_SIZE {size}", ""]
    for b in range(size):
        for g in range(size):
            for r in range(size):
                px = a[g, b*size+r] / 255.0
                lines.append("%.5f %.5f %.5f" % (px[0], px[1], px[2]))
    open(out, "w").write("\n".join(lines)+"\n")
    print("wrote", out, f"({size}^3 LUT)")

def main():
    if len(sys.argv) < 2: sys.exit(__doc__)
    size = int(sys.argv[sys.argv.index("--size")+1]) if "--size" in sys.argv else 33
    cmd = sys.argv[1]
    arg = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith("--") else None
    if cmd == "identity":
        identity(arg or "identity.png", size)
    elif cmd == "frompng":
        if not arg: sys.exit("need <graded.png>")
        out = sys.argv[3] if len(sys.argv) > 3 and not sys.argv[3].startswith("--") \
              else arg.rsplit(".",1)[0]+".cube"
        frompng(arg, out, size)
    else: sys.exit(__doc__)

if __name__ == "__main__":
    main()
