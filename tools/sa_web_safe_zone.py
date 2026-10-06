#!/usr/bin/env python3
"""
Slide a picture sideways so something that overran the card's crop lands back inside it.

A site's image cards often show only the middle of the file - object-fit: cover cuts a
slice off each side (CARD_CROP per side). A sign or a face that ends near the edge of
the file (say at 89% of the width, with 16.5% cut per side) gets sliced in half.

Cropping cannot fix that. The crop is symmetric, so taking L pixels off the left also
takes CARD_CROP x L off the surviving right edge; for a detail that far out the crop
can eat close to half the picture.

So the whole frame is translated instead, and the strip left bare at the trailing edge is
rebuilt by mirroring its neighbour. Translating keeps every internal relationship exactly
as rendered - spacing, distances, where each person stands. Nothing is retouched.
And the rebuilt strip lands OUTSIDE the card's visible window, so on the page it is never
seen at all.

    sa_web_safe_zone.py in.jpg <px> out.jpg
    sa_web_safe_zone.py --demo
"""
import sys
import numpy as np
from PIL import Image

CARD_CROP = 0.165          # per side; measure it off your own live site


def safe_zone(width, margin=0.0):
    """The x range of a file that actually reaches the screen."""
    return width * (CARD_CROP + margin), width * (1 - CARD_CROP - margin)


def shift_left(im, px, feather=24):
    """Move the content left by `px` and rebuild the bare strip at the right edge.

    CHECK BEFORE USING: the strip is mirrored from its own neighbour, so anything
    distinctive sitting within `2*px` of the original right edge gets DUPLICATED there.
    Plain repeating material - glass bays, stone, water - mirrors invisibly; a sign or a
    face does not. mirror_source_is_clear() answers this, and the demo asserts it.
    """
    w, h = im.size
    out = Image.new("RGB", (w, h))
    out.paste(im.crop((px, 0, w, h)), (0, 0))

    # mirror the strip that now sits just inside the gap, so edges meet like for like
    gap = px
    src = out.crop((w - gap * 2, 0, w - gap, h)).transpose(Image.FLIP_LEFT_RIGHT)
    out.paste(src, (w - gap, 0))

    # feather across the join so the mirrored seam does not read as a hard line
    if feather:
        a = np.asarray(out, dtype=np.float32)
        x0 = w - gap
        for i in range(min(feather, gap)):
            t = i / feather
            a[:, x0 + i] = a[:, x0 - 1] * (1 - t) + a[:, x0 + i] * t
        out = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    return out


def mirror_source_is_clear(im, px, tol=14.0):
    """True when the strip about to be mirrored is plain enough to duplicate unnoticed."""
    w, h = im.size
    strip = np.asarray(im.crop((w - px * 2, 0, w, h)).convert("L"), dtype=np.float32)
    # the WORST column, not the average - one strong feature is enough to give a
    # mirrored duplicate away, and averaging hides it among its plain neighbours
    return float(np.percentile(strip.std(axis=0), 98)) < tol


def demo():
    w, h = 1000, 400
    im = Image.new("RGB", (w, h), (30, 30, 30))
    im.paste((240, 40, 40), (880, 150, 930, 250))       # a mark out past the card's edge
    lo, hi = safe_zone(w)
    assert 930 > hi, "the fixture must start outside the card"

    out = shift_left(im, 120)
    a = np.asarray(out, dtype=int)
    red = (a[:, :, 0] > 200) & (a[:, :, 1] < 100)
    xs = np.nonzero(red)[1]
    assert xs.min() >= 880 - 120 - 2, "the mark must move by the amount asked, not more"
    assert 760 <= xs.min() and (xs[(xs < hi)]).size > 0, "the mark must land inside the card"
    assert out.size == im.size, "the file must keep the exact size the slot serves"

    # and the hazard the mirror creates, asserted rather than hoped for:
    # this fixture's mark IS within 2*px of the edge, so it must be reported as unsafe
    assert not mirror_source_is_clear(im, 120), "a mark near the trailing edge must fail the check"
    plain = Image.new("RGB", (w, h), (30, 30, 30))
    assert mirror_source_is_clear(plain, 120), "featureless material must pass the check"
    print("demo ok")


if __name__ == "__main__":
    if "--demo" in sys.argv:
        demo(); sys.exit(0)
    src, px = sys.argv[1], int(sys.argv[2])
    im = Image.open(src).convert("RGB")
    shift_left(im, px).save(sys.argv[3], quality=96, subsampling=0)
    print(f"  shifted {px}px -> {sys.argv[3]}")
