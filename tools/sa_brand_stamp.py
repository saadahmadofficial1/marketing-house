#!/usr/bin/env python3
"""
Put real brand artwork onto a generated plate, without a generative model ever
touching it.

This exists because of one measured failure: an AI image-to-image pass over a real
photograph silently changed one letter of a company name on a real badge (an O became
a D). Models redraw letters as shapes. So a plate is generated with the signage DELIBERATELY BLANK
- a bare stone band, a plain sunken disc, an unmarked bag - and the genuine artwork is
stamped in here, at pixel level, where it cannot be reinvented.

Two seats, because a mark sits differently on stone than on paper:

  engrave()  cuts the mark INTO a surface. An engraved mark is not a dark stencil: the
             rim casts a shadow INTO the cut on the side facing the light, and the far
             wall of the cut catches that light. So the shadow copy is offset TOWARD
             the sun and the highlight copy AWAY from it - the opposite of a raised
             sign, and the thing that makes it read as cut stone rather than a decal.

  stamp()    prints the mark ON a surface. The trick is the surface's own shading must
             run THROUGH the ink: the panel's luminance is multiplied over the mark, so
             folds, creases and falloff carry across it. Skip that and it reads as a
             sticker no matter how good the perspective is.

Both take the mark as white-on-transparent RGBA and place it in an ellipse or a quad,
so perspective comes from the seat measured off the plate, never from a guess.

    sa_brand_stamp.py --demo
"""
import numpy as np
from PIL import Image, ImageFilter


def _fit(mark, w, h, keep_aspect=True):
    """Place the mark in a w x h box, centred.

    keep_aspect=False STRETCHES it to fill the box. That is not a distortion: a round
    mark on a wall turned away from the camera is genuinely an ellipse on the sensor,
    so the seat's own foreshortening is what the artwork has to take.
    """
    if keep_aspect:
        s = min(w / mark.width, h / mark.height)
        size = (max(1, int(mark.width * s)), max(1, int(mark.height * s)))
    else:
        size = (max(1, w), max(1, h))
    m = mark.resize(size, Image.LANCZOS)
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    out.paste(m, ((w - m.width) // 2, (h - m.height) // 2))
    return out


def _alpha(img):
    return np.asarray(img, dtype=np.float32)[..., 3] / 255.0


def engrave(plate, mark, centre, rx, ry, sun=(1, -1), depth=0.22, relief=2.2, fill=0.90):
    """Cut `mark` into `plate` inside the ellipse at `centre`.

    sun    direction the light comes FROM, in image axes (x right, y down).
           (1,-1) is upper-right.
    depth  how much darker the cut face is than the surrounding surface.
    relief pixels of offset for the shadow/highlight pair.
    fill   fraction of the ellipse the mark occupies.
    """
    cx, cy = centre
    bw, bh = int(rx * 2 * fill), int(ry * 2 * fill)
    a = _alpha(_fit(mark, bw, bh, keep_aspect=False))   # take the seat's foreshortening

    # normalise the sun into a unit offset
    sx, sy = sun
    n = (sx * sx + sy * sy) ** 0.5 or 1.0
    ox, oy = sx / n * relief, sy / n * relief

    def shifted(arr, dx, dy):
        return np.roll(np.roll(arr, int(round(dy)), axis=0), int(round(dx)), axis=1)

    shadow = np.clip(shifted(a, ox, oy) - a, 0, 1)      # rim shadow, toward the sun
    light = np.clip(shifted(a, -ox, -oy) - a, 0, 1)     # lit far wall, away from it

    x0, y0 = int(cx - bw / 2), int(cy - bh / 2)
    region = np.asarray(plate.crop((x0, y0, x0 + bw, y0 + bh)).convert("RGB"), dtype=np.float32)

    out = region * (1 - depth * a[..., None])                       # the cut face
    out *= (1 - 0.30 * shadow[..., None])                           # shadow in the cut
    out += (255 - out) * 0.22 * light[..., None]                    # light on the far wall

    ed = Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.4))
    plate = plate.copy()
    plate.paste(ed, (x0, y0))
    return plate


def stamp(plate, mark, quad, ink=(255, 255, 255), strength=0.95, shade=0.75, fill=1.0):
    """Print `mark` onto the quad [(x,y) x4, clockwise from top-left] of `plate`.

    shade  how much of the panel's own luminance is multiplied through the ink.
           This is what stops it reading as a sticker.
    fill   fraction of the panel the mark covers. Real packaging leaves a margin;
           a mark running to the fold reads as a printing error.
    """
    xs = [p[0] for p in quad]; ys = [p[1] for p in quad]
    x0, y0, x1, y1 = int(min(xs)), int(min(ys)), int(max(xs)) + 1, int(max(ys)) + 1
    w, h = x1 - x0, y1 - y0
    inner = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    inner.paste(_fit(mark, int(w * fill), int(h * fill)),
                (int(w * (1 - fill) / 2), int(h * (1 - fill) / 2)))
    src = inner

    # map the mark's own rectangle onto the quad
    dst = [(x - x0, y - y0) for x, y in quad]
    coeffs = _perspective(dst, [(0, 0), (w, 0), (w, h), (0, h)])
    warped = src.transform((w, h), Image.PERSPECTIVE, coeffs, Image.BICUBIC)
    a = _alpha(warped) * strength

    region = np.asarray(plate.crop((x0, y0, x1, y1)).convert("RGB"), dtype=np.float32)
    lum = region.mean(axis=2, keepdims=True) / 255.0
    lum = shade * lum + (1 - shade)                     # the panel's shading, softened
    colour = np.array(ink, dtype=np.float32) * lum      # ink lit by the panel

    out = region * (1 - a[..., None]) + colour * a[..., None]
    st = Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.3))
    plate = plate.copy()
    plate.paste(st, (x0, y0))
    return plate


def _perspective(src, dst):
    """Coefficients mapping dst -> src, which is the direction PIL wants."""
    A = []
    for (x, y), (u, v) in zip(src, dst):
        A.append([u, v, 1, 0, 0, 0, -x * u, -x * v])
        A.append([0, 0, 0, u, v, 1, -y * u, -y * v])
    A = np.array(A, dtype=np.float64)
    b = np.array([c for p in src for c in p], dtype=np.float64)
    return np.linalg.solve(A, b).tolist()


def demo():
    """An engraved mark must darken the stone; a stamped one must follow its shading."""
    stone = Image.new("RGB", (240, 240), (210, 200, 185))
    mark = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
    mark.paste((255, 255, 255, 255), (20, 20, 80, 80))

    e = engrave(stone, mark, (120, 120), 70, 70)
    a0 = np.asarray(stone, float)[100:140, 100:140].mean()
    a1 = np.asarray(e, float)[100:140, 100:140].mean()
    assert a1 < a0, f"an engraved mark must sit darker than the stone ({a1:.0f} vs {a0:.0f})"

    # a gradient panel: the ink must be darker where the panel is darker
    g = np.tile(np.linspace(60, 250, 240, dtype=np.uint8), (240, 1))
    panel = Image.fromarray(np.dstack([g] * 3))
    s = stamp(panel, mark, [(40, 40), (200, 40), (200, 200), (40, 200)])
    arr = np.asarray(s, float)
    left, right = arr[110:130, 60:80].mean(), arr[110:130, 160:180].mean()
    assert left < right, "the panel's shading must run through the ink"

    # a round mark in an elliptical seat must come out elliptical, not round
    blank = Image.new("RGB", (240, 300), (210, 200, 185))
    tall = engrave(blank, mark, (120, 150), 40, 100)
    cut = np.abs(np.asarray(tall, float) - np.asarray(blank, float)).mean(axis=2) > 2
    ys, xs = np.nonzero(cut)
    assert (ys.max() - ys.min()) > (xs.max() - xs.min()) * 1.5, "the seat's foreshortening was ignored"

    # fill must keep the mark clear of the panel edge
    narrow = stamp(panel, mark, [(40, 40), (200, 40), (200, 200), (40, 200)], fill=0.5)
    d = np.abs(np.asarray(narrow, float) - np.asarray(panel, float)).mean(axis=2)
    assert d[110:130, 45:55].max() < 1, "fill=0.5 must leave the panel edge untouched"

    # the warp must be the identity when the quad IS the rectangle
    c = _perspective([(0, 0), (10, 0), (10, 10), (0, 10)], [(0, 0), (10, 0), (10, 10), (0, 10)])
    assert abs(c[0] - 1) < 1e-9 and abs(c[4] - 1) < 1e-9, c
    print("demo ok")


if __name__ == "__main__":
    demo()
