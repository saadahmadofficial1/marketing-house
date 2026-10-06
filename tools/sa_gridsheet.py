#!/usr/bin/env python3
"""sa_gridsheet — contact sheets with a pixel ruler, for measuring call-out boxes.

Placing a call-out means reading real coordinates off a real frame. The hard-won rule
(T03, 5 Aug): measure on the EXACT frame the render will freeze on — a neighbouring
frame can be mid-scroll and puts the box on the wrong row.

  # measure: grid overlay, coordinates in SOURCE pixels
  sa_gridsheet.py T04_PACED.mp4 -t 4.9 13.9 32.1 -o grid.png
  # verify a burned render: no grid, just look
  sa_gridsheet.py T04_MARKED.mp4 -t 4.9 13.9 --no-grid --cols 2 -o check.png

Labels above each tile are the timestamps, so what you read is what you put in the spec.
"""
import argparse
import os
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw, ImageFont

STEP = 50            # grid every STEP px on the scaled tile
PINK = (255, 0, 255)
FAINT = (255, 180, 255)


def _font(size):
    for p in (os.path.expanduser("~/Library/Fonts/Poppins-SemiBold.ttf"),
              "/System/Library/Fonts/Helvetica.ttc"):
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def grab(video, t, width, tmp):
    out = os.path.join(tmp, f"f{t:.2f}.png")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.3f}", "-i", video,
                    "-frames:v", "1", "-vf", f"scale={width}:-1", out], check=True)
    return out


def draw_grid(img, scale):
    """Grid labelled in SOURCE pixels, so numbers can be pasted straight into a spec."""
    d = ImageDraw.Draw(img)
    f = _font(13)
    for x in range(0, img.width, STEP):
        major = x % (STEP * 2) == 0
        d.line([(x, 0), (x, img.height)], fill=PINK if major else FAINT, width=1)
        if major:
            d.text((x + 2, 2), str(int(x / scale)), fill=PINK, font=f)
    for y in range(0, img.height, STEP):
        major = y % (STEP * 2) == 0
        d.line([(0, y), (img.width, y)], fill=PINK if major else FAINT, width=1)
        if major:
            d.text((2, y + 2), str(int(y / scale)), fill=PINK, font=f)
    return img


def build(video, times, out, cols=1, width=960, grid=True, labels=None):
    tmp = tempfile.mkdtemp(prefix="gridsheet_")
    src_w = int(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                                "-show_entries", "stream=width", "-of", "csv=p=0", video],
                               capture_output=True, text=True).stdout.strip())
    scale = width / src_w
    tiles = []
    for i, t in enumerate(times):
        im = Image.open(grab(video, t, width, tmp)).convert("RGB")
        if grid:
            draw_grid(im, scale)
        cap = labels[i] if labels else f"{t:.2f}s"
        tiles.append((im, cap))

    tw, th = tiles[0][0].size
    rows = (len(tiles) + cols - 1) // cols
    pad, head = 10, 30
    sheet = Image.new("RGB", (cols * tw + (cols + 1) * pad, rows * (th + head) + pad), (18, 18, 22))
    d = ImageDraw.Draw(sheet)
    f = _font(20)
    for i, (im, cap) in enumerate(tiles):
        cx = pad + (i % cols) * (tw + pad)
        cy = pad + (i // cols) * (th + head)
        d.text((cx + 2, cy + 4), cap, fill=(255, 220, 80), font=f)
        sheet.paste(im, (cx, cy + head))
    sheet.save(out)
    print(f"-> {out}  ({len(tiles)} frames, grid={'on' if grid else 'off'}, "
          f"coords in source px @ {src_w}w)")
    return out


def _test():
    im = Image.new("RGB", (960, 570), (0, 0, 0))
    draw_grid(im, 0.5)
    px = im.load()
    assert px[0, 5] == PINK, "x=0 must be a major gridline"
    assert px[STEP, 5] == FAINT, "odd multiples of STEP are minor lines"
    assert px[STEP * 2, 5] == PINK, "even multiples are major"
    print("sa_gridsheet self-check: ok (major/minor lines, source-px labelling)")


if __name__ == "__main__":
    if "--test" in sys.argv:
        _test()
        sys.exit()
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("-t", "--times", nargs="+", type=float, required=True)
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--cols", type=int, default=1)
    ap.add_argument("--width", type=int, default=960)
    ap.add_argument("--no-grid", action="store_true")
    a = ap.parse_args()
    build(a.video, a.times, a.out, a.cols, a.width, not a.no_grid)
