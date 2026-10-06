#!/usr/bin/env python3
"""Adaptive outdoor photo grade, tuned per image.
  sa_photo.py <src_dir|file> [out_dir] [--n 1]

Recipe (NEVER global saturation): white-patch WB + cool bias > auto-levels/dehaze >
shadow lift + highlight recover > VIBRANCE not saturation > chroma denoise > clarity.
Reads .ARW (rawpy, camera WB) or .JPG. Writes graded JPG. Non-destructive.
"""
import os, sys, numpy as np
from PIL import Image, ImageFilter

# Neutral starting values (vibrance, cool bias on blue, target mid-luma). Tune them to an
# outdoor edit you made and approved yourself; sa_lrread.py reads your Lightroom values.
VIB = 0.20; COOL = 1.02; TARGET = 0.45

def _load(p):
    if p.lower().endswith(".arw"):
        import rawpy
        with rawpy.imread(p) as r:
            rgb = r.postprocess(use_camera_wb=True, no_auto_bright=True, output_bps=16)
        return rgb.astype(np.float32) / 65535.0
    im = Image.open(p).convert("RGB")
    return np.asarray(im, np.float32) / 255.0

def _luma(a): return a[...,0]*0.2126 + a[...,1]*0.7152 + a[...,2]*0.0722

def grade(p):
    a = _load(p)
    # 1. white-patch WB: neutralise 97th-pct highlights, then slight cool
    hi = np.percentile(a.reshape(-1,3), 97, axis=0) + 1e-4
    a = a * (hi.mean() / hi)
    a[...,2] *= COOL; a[...,0] /= (COOL**0.5)
    # 2. auto-levels (dehaze) + gamma to target midtone
    l = _luma(a); blk, wht = np.percentile(l, 0.5), np.percentile(l, 99.6)
    a = np.clip((a - blk) / (wht - blk + 1e-4), 0, 1)
    med = max(np.median(_luma(a)), 1e-3)
    a = a ** (np.log(TARGET) / np.log(med))
    # 3. shadow lift + highlight recover (luma-weighted, soft)
    l = np.clip(_luma(a), 0, 1)[...,None]
    a = a + (a*(1-a)) * (0.35*(1-l) - 0.18*l)   # lift darks, pull brights
    a = np.clip(a, 0, 1)
    # 4. VIBRANCE (not saturation): boost dull pixels more, protect saturated
    g = _luma(a)[...,None]; mx, mn = a.max(2,keepdims=True), a.min(2,keepdims=True)
    sat = (mx-mn)/(mx+1e-4)
    a = np.clip(g + (a-g)*(1 + VIB*(1-sat)), 0, 1)
    im = Image.fromarray((a*255+0.5).astype(np.uint8))
    # 5. chroma denoise: median on Cb,Cr only (keep luma sharp)
    y,cb,cr = im.convert("YCbCr").split()
    im = Image.merge("YCbCr",(y, cb.filter(ImageFilter.MedianFilter(3)),
                              cr.filter(ImageFilter.MedianFilter(3)))).convert("RGB")
    # 6. clarity: mild unsharp
    return im.filter(ImageFilter.UnsharpMask(radius=1.6, percent=85, threshold=2))

def main():
    if len(sys.argv) < 2: sys.exit("usage: sa_photo.py <src> [out_dir] [--n N]")
    src = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith("--") \
          else os.path.join(src if os.path.isdir(src) else os.path.dirname(src), "Edited")
    lim = int(sys.argv[sys.argv.index("--n")+1]) if "--n" in sys.argv else 0
    if os.path.isfile(src): files = [src]
    else:
        files = sorted(os.path.join(src,f) for f in os.listdir(src)
                       if f.lower().endswith((".arw",".jpg",".jpeg")))
    if lim: files = files[:lim]
    os.makedirs(out, exist_ok=True)
    for i,p in enumerate(files,1):
        name = os.path.splitext(os.path.basename(p))[0] + "_graded.jpg"
        try:
            grade(p).save(os.path.join(out,name), quality=95)
            print(f"[{i}/{len(files)}] {name}")
        except Exception as e: print("skip", p, e)
    print("done ->", out)

if __name__ == "__main__":
    main()
