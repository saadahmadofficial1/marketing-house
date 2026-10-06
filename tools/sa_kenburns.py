#!/usr/bin/env python3
"""sa_kenburns — still photo -> 9:16 slow push/pull clip. REAL PIXELS ONLY.

Safe for jewellery and fine products: no generation, no interpolation, no grade. The camera just moves
over the photo (float affine window, so no integer-crop jitter).

  sa_kenburns.py OUT_DIR photo1.jpg photo2.jpg ... [--sec 3]
Moves cycle per photo: push-in, pull-out, push-in + drift up, push-in + drift down.
ponytail: centre-anchored moves only; add per-photo focus points if a crop misses the piece.
"""
import os, sys, subprocess
from concurrent.futures import ProcessPoolExecutor
from PIL import Image, ImageOps

FFMPEG = os.path.expanduser("~/.local/bin/ffmpeg")
if not os.path.exists(FFMPEG):
    FFMPEG = "ffmpeg"
W, H, FPS = 1080, 1920, 30
# (zoom_a, zoom_b, dy_a, dy_b) — zoom >= 1.0, dy as fraction of frame height
MOVES = [(1.00, 1.08, 0, 0), (1.08, 1.00, 0, 0), (1.04, 1.10, .02, -.02), (1.04, 1.10, -.02, .02)]


def render(job):
    src, out, move, sec = job
    im = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
    # fit-cover to 9:16 at 2x output so the window always has real pixels under it
    sw, sh = im.size
    s = max(2 * W / sw, 2 * H / sh)
    im = im.resize((round(sw * s), round(sh * s)), Image.LANCZOS)
    iw, ih = im.size
    za, zb, ya, yb = move
    n = int(sec * FPS)
    p = subprocess.Popen([FFMPEG, "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                          "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264",
                          "-crf", "14", "-preset", "slow", "-pix_fmt", "yuv420p", out],
                         stdin=subprocess.PIPE)
    for i in range(n):
        t = i / (n - 1)
        t = t * t * (3 - 2 * t)                      # ease in/out
        z = za + (zb - za) * t
        cw, ch = 2 * W / z, 2 * H / z                  # window in source px
        cx = iw / 2
        cy = ih / 2 + (ya + (yb - ya) * t) * ih
        cy = min(max(cy, ch / 2), ih - ch / 2)
        k = cw / W                                     # source px per output px
        f = im.transform((W, H), Image.AFFINE, (k, 0, cx - cw / 2, 0, k, cy - ch / 2), Image.BICUBIC)
        p.stdin.write(f.tobytes())
    p.stdin.close(); p.wait()
    return out


if __name__ == "__main__":
    a = sys.argv[1:]
    sec = 3.0
    if "--sec" in a:
        i = a.index("--sec"); sec = float(a[i + 1]); del a[i:i + 2]
    out_dir, photos = a[0], a[1:]
    assert all(m[0] >= 1 and m[1] >= 1 for m in MOVES)
    os.makedirs(out_dir, exist_ok=True)
    jobs = [(p, os.path.join(out_dir, f"KB_{os.path.splitext(os.path.basename(p))[0]}.mp4"),
             MOVES[k % len(MOVES)], sec) for k, p in enumerate(photos)]
    with ProcessPoolExecutor(4) as ex:
        for o in ex.map(render, jobs): print("ok", o)
