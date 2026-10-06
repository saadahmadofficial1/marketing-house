#!/usr/bin/env python3
"""
The house treatment for real photographs on a corporate website.

ONE pipeline, identical numbers for every card, so the real-photo cards sit
together as a set. Nothing is redrawn, reshaped or invented — buildings,
structures and branding come through exactly as photographed. Only haze,
tone, colour and framing change.

    python3 sa_house_grade.py <src> <out> [--crop x0,y0,x1,y1] [--native]

The sky step is self-balancing: it targets BRIGHT, LOW-SATURATION pixels, so a
hazy white sky gets pulled back to blue while an already-deep sky is barely
touched. That is what keeps frames shot in different conditions consistent
without hand-tuning each one.
"""
import sys, pathlib
from PIL import Image, ImageEnhance, ImageFilter, ImageChops, ImageDraw

W, H = 1672, 941

# the house numbers — change here, everything re-renders the same
HAZE_CAP   = 90     # never assume a haze floor darker than this
CONTRAST   = 1.11
SATURATION = 1.14
SKY_TARGET = 104     # the blue every card's sky is driven towards (0-255 saturation)
SKY_MAX    = 1.5    # ceiling on how hard a flat white sky may be pushed
WARM_R     = 4      # highlight warmth
COOL_B     = 5      # shadow coolness
VIGNETTE   = 0.14   # light — these are bright daylight frames, not dusk
SHARPEN    = (1.8, 58, 3)



def _sky_reading(im):
    """Mean colour saturation across the sky mask — how blue this frame reads."""
    r, g, b = im.split()
    mx = ImageChops.lighter(ImageChops.lighter(r, g), b)
    mn = ImageChops.darker(ImageChops.darker(r, g), b)
    sat = ImageChops.subtract(mx, mn)
    bright = mx.point(lambda v: 255 if v > 150 else int(max(0, v - 110) * 5.6))
    mask = ImageChops.multiply(bright, sat.point(lambda v: 255 if v < 150 else 0))
    grad = Image.linear_gradient("L").resize(im.size).point(
        lambda v: 255 if v < 90 else max(0, 255 - int((v - 90) * 3.2)))
    mask = ImageChops.multiply(mask, grad).filter(ImageFilter.GaussianBlur(14))
    mp, sp = mask.load(), sat.load()
    vals = [sp[x, y] for y in range(0, im.height // 2, 5)
            for x in range(0, im.width, 5) if mp[x, y] > 120]
    return (sum(vals) / len(vals) if vals else SKY_TARGET), mask


def _vignette(im, strength):
    w, h = im.size
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).ellipse((-w*0.20, -h*0.32, w*1.20, h*1.32), fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(min(w, h)*0.17))
    return Image.composite(im, Image.blend(im, Image.new("RGB", (w, h), (0, 0, 0)), strength), mask)


def house(src, dst, crop=None, native=False):
    """native=True keeps the source dimensions — no crop, no resize. Used when
    the standing instruction is no crops, full size; Saad cuts the sizes later."""
    global W, H
    im = Image.open(src).convert("RGB")
    if native:
        W, H = im.size
    if crop:
        sw, sh = im.size
        x0, y0, x1, y1 = crop
        im = im.crop((int(sw*x0), int(sh*y0), int(sw*x1), int(sh*y1)))

    tr, sr = W/H, im.width/im.height
    if native:
        pass
    elif sr > tr:
        nw = int(im.height*tr); im = im.crop(((im.width-nw)//2, 0, (im.width+nw)//2, im.height))
    else:
        nh = int(im.width/tr); top = int((im.height-nh)*0.5)
        im = im.crop((0, top, im.width, top+nh))
    if not native:
        im = im.resize((W, H), Image.LANCZOS)

    # haze floor
    px = im.load()
    lo = min(min(px[x, y]) for y in range(0, H, 7) for x in range(0, W, 7))
    lo = min(lo, HAZE_CAP)
    if lo > 18:                                   # a real haze floor, not just a dark frame
        scale = 255.0/(255.0-lo)
        im = im.point(lambda v: max(0, min(255, int((v-lo)*scale))))

    # Adaptive strength. A fixed lift overcooks a frame that was already punchy —
    # one already-rich photo came back with orange ground and a blue-cast subject.
    # Measure how flat the frame actually is and apply only the shortfall.
    from PIL import ImageStat
    g = im.convert("L")
    spread = ImageStat.Stat(g).stddev[0]          # ~40 flat, ~70 punchy
    rr, gg, bb = im.split()
    satimg = ImageChops.subtract(ImageChops.lighter(ImageChops.lighter(rr, gg), bb),
                                 ImageChops.darker(ImageChops.darker(rr, gg), bb))
    satmean = ImageStat.Stat(satimg).mean[0]      # ~25 flat, ~60 rich

    c = 1 + (CONTRAST - 1) * max(0.0, min(1.0, (62 - spread) / 22))
    v = 1 + (SATURATION - 1) * max(0.0, min(1.0, (55 - satmean) / 30))
    print(f"    spread {spread:.0f} sat {satmean:.0f} -> contrast x{c:.3f} colour x{v:.3f}")
    im = ImageEnhance.Contrast(im).enhance(c)
    im = ImageEnhance.Color(im).enhance(v)

    # sky recovery through a blurred mask (a hard threshold speckles the gradient)
    r, g, b = im.split()
    mx = ImageChops.lighter(ImageChops.lighter(r, g), b)
    mn = ImageChops.darker(ImageChops.darker(r, g), b)
    sat = ImageChops.subtract(mx, mn)
    bright = mx.point(lambda v: 255 if v > 150 else int(max(0, v-110)*5.6))
    flat = sat.point(lambda v: 255 if v < 40 else max(0, 255-(v-40)*8))
    mask = ImageChops.multiply(bright, flat)
    # Sky lives at the TOP. Without this, a large bright neutral subject — a white
    # storage tank, a pale facade — reads as sky to the mask and gets tinted
    # blue. Fade the mask out below the upper third.
    grad = Image.linear_gradient("L").resize((W, H)).point(
        lambda v: 255 if v < 90 else max(0, 255 - int((v - 90) * 3.2)))
    mask = ImageChops.multiply(mask, grad).filter(ImageFilter.GaussianBlur(14))

    # Self-levelling: measure how blue this frame's sky already is and push only
    # as hard as needed to reach SKY_TARGET. A hazy white sky gets a strong lift,
    # an already-deep sky gets almost none — so frames shot in different
    # conditions finish on the same blue instead of needing hand-tuning.
    mpx, spx = mask.load(), sat.load()
    vals = [spx[x, y] for y in range(0, H//2, 5) for x in range(0, W, 5) if mpx[x, y] > 120]
    cur = sum(vals)/len(vals) if vals else SKY_TARGET
    sky = max(0.0, min(SKY_MAX, (SKY_TARGET - cur)/70.0))

    blue = Image.merge("RGB", (
        r.point(lambda v: int(v*(1-0.30*sky))),
        g.point(lambda v: int(v*(1-0.14*sky))),
        b.point(lambda v: min(255, int(v*(1+0.08*sky)))),
    ))
    print(f"    sky saturation {cur:.0f} -> push {sky:.2f}")
    im = Image.composite(blue, im, mask)

    r, g, b = im.split()
    r = r.point(lambda v: min(255, int(v + (v/255)*WARM_R)))
    b = b.point(lambda v: min(255, int(v + (1-v/255)*COOL_B)))
    im = Image.merge("RGB", (r, g, b))

    # Closing pass. The steps above land each frame near the target but not on
    # it, because contrast and saturation move a hazy frame and a clear one by
    # different amounts. Measure the FINISHED sky and trim once, so every card
    # converges on the same blue rather than each being hand-tuned.
    for _ in range(6):
        cur, m = _sky_reading(im)
        gap = SKY_TARGET - cur
        if abs(gap) < 6:
            break
        k = max(-0.45, min(0.45, gap / 150.0))
        rr, gg, bb = im.split()
        trim = Image.merge("RGB", (
            rr.point(lambda v: max(0, min(255, int(v * (1 - 0.30 * k))))),
            gg.point(lambda v: max(0, min(255, int(v * (1 - 0.14 * k))))),
            bb.point(lambda v: max(0, min(255, int(v * (1 + 0.08 * k))))),
        ))
        im = Image.composite(trim, im, m)
    print(f"    sky settled at {_sky_reading(im)[0]:.0f} (target {SKY_TARGET})")

    im = _vignette(im, VIGNETTE)
    im = im.filter(ImageFilter.UnsharpMask(*SHARPEN))
    im.save(dst, quality=93, subsampling=1)
    print(f"  {pathlib.Path(dst).name}  {W}x{H}  haze floor {lo}")


if __name__ == "__main__":
    a = sys.argv[1:]
    crop = tuple(float(v) for v in a[a.index("--crop")+1].split(",")) if "--crop" in a else None
    house(a[0], a[1], crop, native="--native" in a)
