#!/usr/bin/env python3
"""
Pull every card in an image set toward the look of the ones Saad approved.

Consistency in a set is measurable, not a matter of taste: the approved reference
cards define the target, and each other card is nudged toward it on
brightness and saturation. Adjustments are capped so a card is corrected, never
rebuilt — the picture stays the picture.

    python3 sa_match_set.py <folder> --ref a,b            # measure only
    python3 sa_match_set.py <folder> --ref a,b --write

Every <name>.jpg in <folder> is a card; --ref names the approved ones (never touched).
"""
import sys, pathlib
from PIL import Image, ImageChops, ImageStat, ImageEnhance

IMG = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else ".")
REFERENCE = sys.argv[sys.argv.index("--ref") + 1].split(",") if "--ref" in sys.argv else []
ORDER = sorted(p.stem for p in IMG.glob("*.jpg"))   # every card in the set

CAP_BRIGHT = 0.22      # never move brightness more than this
# 21 Sep: colour was capped at 0.30 and three cards pinned to it, which is how the
# set ended up looking uniform. Mean saturation is set by the SUBJECT — a glass
# office is bound to read flatter than a turquoise aerial — so colour only gets a
# nudge now. Brightness is what makes a set look like one family; colour is not.
CAP_COLOUR = 0.15


def measure(im):
    r, g, b = im.split()
    mx = ImageChops.lighter(ImageChops.lighter(r, g), b)
    mn = ImageChops.darker(ImageChops.darker(r, g), b)
    sat = ImageStat.Stat(ImageChops.subtract(mx, mn)).mean[0]
    return ImageStat.Stat(im.convert("L")).mean[0], sat


def main(write):
    if not REFERENCE or not all(n in ORDER for n in REFERENCE):
        sys.exit(__doc__)
    stats = {n: measure(Image.open(IMG / f"{n}.jpg").convert("RGB")) for n in ORDER}
    tb = sum(stats[n][0] for n in REFERENCE) / len(REFERENCE)
    ts = sum(stats[n][1] for n in REFERENCE) / len(REFERENCE)
    print(f"  target from {' + '.join(REFERENCE)}:  brightness {tb:.0f}   saturation {ts:.0f}\n")

    for n in ORDER:
        b, s = stats[n]
        if n in REFERENCE:
            print(f"  {n:<14} {b:5.0f} {s:5.0f}   reference, untouched")
            continue
        kb = max(1 - CAP_BRIGHT, min(1 + CAP_BRIGHT, tb / b))
        ks = max(1 - CAP_COLOUR, min(1 + CAP_COLOUR, ts / s))
        if abs(kb - 1) < 0.02 and abs(ks - 1) < 0.02:
            print(f"  {n:<14} {b:5.0f} {s:5.0f}   already within tolerance")
            continue
        print(f"  {n:<14} {b:5.0f} {s:5.0f}   brightness x{kb:.2f}  colour x{ks:.2f}", end="")
        if write:
            f = IMG / f"{n}.jpg"
            im = Image.open(f).convert("RGB")
            im = ImageEnhance.Brightness(im).enhance(kb)
            im = ImageEnhance.Color(im).enhance(ks)
            im.save(f, quality=88, subsampling=1, optimize=True)
            nb, ns = measure(im)
            print(f"  ->  {nb:.0f} {ns:.0f}")
        else:
            print()


if __name__ == "__main__":
    main("--write" in sys.argv)
