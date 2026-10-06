#!/usr/bin/env python3
"""
Render a web page's image cards exactly as the page shows them.

Two things are easy to forget when judging a file flat, and both change the verdict:
the site crops the picture to about 1.14:1 from the centre, and it lays its label
gradient over the bottom third - linear-gradient(#10182000, #101820e0), read off the
live stylesheet, not guessed. A story that lives in the bottom of the frame is gone.

    CARD_IMAGES=path/to/card/images python3 sa_card_preview.py [out.jpg]

One card per image, in file-name order, three to a row; the label comes from the
file name ("02-our-services.jpg" -> "02  Our Services").
"""
import os, sys, pathlib
from PIL import Image, ImageDraw, ImageFont

IMG = pathlib.Path(os.environ.get("CARD_IMAGES", "public/images/cards")).expanduser()
COLS = 3
RATIO, LABEL_FRAC, LABEL_ALPHA, LABEL_RGB = 1.14, 0.32, 0xE0, (0x10, 0x18, 0x20)


def render(path, w=420):
    im = Image.open(path).convert("RGB")
    W, H = im.size
    nw = round(H * RATIO)
    im = im.crop(((W - nw) // 2, 0, (W - nw) // 2 + nw, H))
    h = round(w / RATIO)
    card = im.resize((w, h), Image.LANCZOS).convert("RGBA")
    lh = int(h * LABEL_FRAC)
    ov = Image.new("RGBA", (w, lh), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    for y in range(lh):
        d.line([(0, y), (w, y)], fill=LABEL_RGB + (int(LABEL_ALPHA * y / (lh - 1)),))
    card.alpha_composite(ov, (0, h - lh))
    return card.convert("RGB")


def label(path):
    """'02-our-services.jpg' -> '02  Our Services'."""
    num, _, rest = path.stem.partition("-")
    words = rest.replace("-", " ").replace("_", " ").title()
    return f"{num}  {words}" if num.isdigit() and words else path.stem.replace("-", " ").title()


def main(out):
    try:
        f = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 17)
    except OSError:
        f = ImageFont.load_default()
    files = sorted(p for p in IMG.iterdir()
                   if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")) if IMG.is_dir() else []
    if not files:
        sys.exit(f"no card images in {IMG} (set CARD_IMAGES)")
    cards = [(render(p), label(p)) for p in files]
    cw, ch = cards[0][0].size
    gap, rows = 12, -(-len(cards) // COLS)
    sheet = Image.new("RGB", (cw * COLS + gap * (COLS + 1), ch * rows + gap * (rows + 1)), (250, 250, 248))
    for i, (c, title) in enumerate(cards):
        x, y = gap + (i % COLS) * (cw + gap), gap + (i // COLS) * (ch + gap)
        sheet.paste(c, (x, y))
        ImageDraw.Draw(sheet).text((x + 14, y + ch - 30), title, fill=(255, 255, 255), font=f)
    sheet.save(out, quality=90)
    print(f"  {out}   {sheet.size[0]}x{sheet.size[1]}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "card_preview.jpg")
