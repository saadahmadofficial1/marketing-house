#!/usr/bin/env python3
"""
Bake a left-weighted scrim into a hero image.

The careers hero on this site lays its white headline straight onto the picture with no
overlay of its own, so the only thing keeping that text readable is darkness already in
the photograph. When the dark side of a studio gradient stops short of where the words
end, the tail of the sentence lands on a bright background - or on somebody's shoulder.

A well-built page would do this in CSS. Until it does, the image has to carry it.

The falloff is smoothstep rather than linear: a linear ramp leaves a visible edge where
it reaches zero, because the eye finds the discontinuity in the first derivative.

    sa_hero_scrim.py in.png out.png [--reach 0.46] [--depth 0.72]
    sa_hero_scrim.py --demo
"""
import sys
import numpy as np
from PIL import Image


def scrim(im, reach=0.46, depth=0.72, floor=(16, 20, 24)):
    """Darken the left of `im`, fading out by `reach` across the width.

    depth  how dark the very left edge goes, 0 = untouched, 1 = solid floor colour.
    """
    a = np.asarray(im.convert("RGB"), dtype=np.float32)
    h, w = a.shape[:2]
    x = np.linspace(0, 1, w, dtype=np.float32)
    t = np.clip(1 - x / reach, 0, 1)
    t = t * t * (3 - 2 * t)                      # smoothstep: no visible edge at the tail
    k = (t * depth)[None, :, None]
    return Image.fromarray(np.clip(a * (1 - k) + np.array(floor, np.float32) * k, 0, 255).astype(np.uint8))


def readable(im, upto=0.40, band=(0.28, 0.52), p=75):
    """The brightness a white headline would sit on: p-th percentile over the text area."""
    a = np.asarray(im.convert("L"), dtype=np.float32)
    h, w = a.shape
    region = a[int(h * band[0]):int(h * band[1]), int(w * 0.05):int(w * upto)]
    return float(np.percentile(region, p))


def demo():
    # a realistic width - the falloff is spread over the frame, so a narrow test
    # canvas compresses it and exaggerates the per-column step
    bright = Image.fromarray(np.full((400, 2000, 3), 230, np.uint8))
    out = scrim(bright, reach=0.5, depth=0.8)
    a = np.asarray(out.convert("L"), dtype=float)
    assert a[:, :40].mean() < 90, "the left edge must go genuinely dark"
    assert a[:, -40:].mean() > 225, "past the reach the picture must be untouched"
    prof = a.mean(axis=0)
    step = np.abs(np.diff(prof)).max()
    assert step < (prof.max() - prof.min()) / 100, \
        f"the falloff must be smooth; worst column step {step:.2f} over a range of {prof.max()-prof.min():.0f}"
    # and it must actually reach zero smoothly, not stop dead
    # where the scrim reaches zero it must fade out, not stop dead. 1.0 is the floor:
    # an 8-bit image cannot step by less than one level.
    tail = np.abs(np.diff(prof[int(len(prof)*0.45):int(len(prof)*0.55)])).max()
    assert tail <= 1.0, f"visible edge where the scrim ends ({tail:.2f})"
    assert readable(bright) > readable(out), "the scrim must improve headline contrast"
    print("demo ok")


if __name__ == "__main__":
    if "--demo" in sys.argv:
        demo(); sys.exit(0)
    g = lambda f, d: float(sys.argv[sys.argv.index(f) + 1]) if f in sys.argv else d
    im = Image.open(sys.argv[1]).convert("RGB")
    out = scrim(im, g("--reach", 0.46), g("--depth", 0.72))
    out.save(sys.argv[2])
    print(f"  headline background {readable(im):.0f} -> {readable(out):.0f}  (white text needs under ~140)")
