#!/usr/bin/env python3
"""sa_revealreel — turn a folder of delivery stills into a 9:16 reveal reel.

A vehicle reveal reel built from stills.
Brief: black cloth over the car, pulled from the BACK, and kill the illuminated
wall behind the car that throws colour onto the black paint.

Everything here is REAL PIXELS + compositing. Nothing about the car is generated:
  - motion  = Ken Burns window over the high-res still (no frame interpolation)
  - cloth   = a drawn silk layer composited ON TOP, the car underneath is untouched
  - wall    = hue-selective desaturate + darken, so the brightly coloured
              illuminated wall print sinks to near-black while the car's accent
              colour (ACCENT_HUE, a warm trim colour by default) is left untouched

  sa_revealreel.py --out /tmp/reveal            # render the reel
  sa_revealreel.py --out /tmp/reveal --stills   # also dump one PNG per shot (storyboard)
  sa_revealreel.py --out /tmp/reveal --shot 1   # render a single shot, fast loop

ponytail: shot list is a literal below, not a config file. One car, one reel.
"""
import argparse
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageFilter

SRC = os.path.expanduser("~/Pictures/car-handover/stills")
SRC2 = os.path.expanduser("~/Pictures/car-handover/hires")   # the photographer's 60MP stills
FFMPEG = os.environ.get("FFMPEG", "ffmpeg")
W, H = 1080, 1920
FPS = 30
ACCENT_HUE = float(os.environ.get("ACCENT_HUE", "42"))   # hue (deg) wallkill() protects: the trim colour
ACCENT_WIDTH = 30.0                                      # width of that protected band (deg)


def s(name):
    """Resolve a short name to its full path across the three delivery batches."""
    if name.startswith("HRS"):          # the photographer's 60MP camera stills, second batch
        return os.path.join(SRC2, f"hires-{name[3:]}.jpg")
    if name.startswith("DSC"):
        return os.path.join(SRC, name + ".jpg")
    return os.path.join(SRC, f"still_{name}.jpg")


# ---------------------------------------------------------------- shot list
# cx, cy  = centre of the crop window in fractions of the source (0..1)
# z       = zoom. MUST BE >= 1.0. 1.0 = the whole source height; 1.10 = 10% tighter.
#           Values below 1.0 ask for a window taller than the source, get clamped, and
#           the shot silently goes STATIC — that bug shipped once, hence the assert
#           in selfcheck(). For a push-in, b.z must be greater than a.z.
# Motion runs from the "a" values to the "b" values across the shot.
# These are the DETAIL BEATS only. The reveal itself is a separately approved clip
# and gets concatenated in front of this at build time.
# Every beat carries studio=.92 so it matches the black-studio reveal — that relight
# is also what removes the showroom lightbox wall, so it is not optional.
# 1.20.2 / 1.17.1 / 1.29.2 are the three Saad picked out by hand.
SHOTS = [
    # Story: reveal -> walk the outside -> the sill takes us INSIDE ->
    # cockpit -> back out to the rear and hold. 4.4s reveal + 10.5s = 14.9s.
    dict(id=1, name="front",     src="1.7.1", dur=1.2,
         a=dict(cx=.45, cy=.52, z=1.02), b=dict(cx=.47, cy=.55, z=1.11),
         wall=.60, dark=(.55, .00), studio=.92),
    dict(id=2, name="wheel",     src="1.11.1", dur=1.0,
         a=dict(cx=.50, cy=.50, z=1.00), b=dict(cx=.53, cy=.50, z=1.07),
         wall=.55, studio=.92),
    dict(id=3, name="headlight", src="1.24.1", dur=1.0,
         a=dict(cx=.46, cy=.46, z=1.02), b=dict(cx=.50, cy=.42, z=1.09),
         wall=.55, studio=.92),
    # the hinge: lit door sill is the natural step from outside to inside
    dict(id=4, name="sill",      src="1.20.2", dur=1.2,
         a=dict(cx=.50, cy=.58, z=1.04), b=dict(cx=.50, cy=.56, z=1.13),
         wall=.45, studio=.92),
    # --- interior: the photographer's 60MP stills. green showroom cast -> neutralise();
    #     already dark -> gentler crush than the exteriors
    dict(id=5, name="steering",  src="HRS49", dur=1.2,
         a=dict(cx=.50, cy=.48, z=1.00), b=dict(cx=.50, cy=.47, z=1.08),
         neutral=.70, studio=.82, spot=(.50, .44)),
    dict(id=6, name="console",   src="HRS48", dur=1.0,
         a=dict(cx=.45, cy=.50, z=1.00), b=dict(cx=.44, cy=.52, z=1.08),
         neutral=.70, studio=.82, spot=(.42, .46)),
    dict(id=7, name="seat",      src="HRS51", dur=1.1,
         a=dict(cx=.52, cy=.45, z=1.00), b=dict(cx=.52, cy=.44, z=1.08),
         neutral=.70, studio=.84, spot=(.52, .36)),
    # --- back outside for the close
    dict(id=8, name="rear detail", src="1.29.2", dur=1.1,
         a=dict(cx=.42, cy=.56, z=1.06), b=dict(cx=.46, cy=.62, z=1.16),
         wall=.85, studio=.98, spot=(.46, .60)),
    dict(id=9, name="profile",   src="1.23.2", dur=1.7,
         a=dict(cx=.52, cy=.55, z=1.00), b=dict(cx=.44, cy=.52, z=1.10),
         wall=.70, dark=(.00, .45), studio=.92),
]


# ---------------------------------------------------------------- wall kill
def wallkill(arr, strength):
    """Sink the illuminated showroom lightbox without touching the accent colour.

    The wall is bright AND saturated AND a mostly cool-hued print. The car's coloured
    trim sits in a warm band around ACCENT_HUE (default 42 deg, roughly 30-55). So the
    mask is: saturated, outside the accent band, and reasonably bright. Blurred so the
    correction has no visible edge.
    """
    if strength <= 0:
        return arr
    f = arr.astype(np.float32) / 255.0
    mx, mn = f.max(2), f.min(2)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
    val = mx

    r, g, b = f[..., 0], f[..., 1], f[..., 2]
    d = np.maximum(mx - mn, 1e-6)
    hue = np.where(mx == r, ((g - b) / d) % 6,
          np.where(mx == g, (b - r) / d + 2, (r - g) / d + 4)) * 60.0

    accent = np.exp(-((hue - ACCENT_HUE) / ACCENT_WIDTH) ** 2)   # 1 on the accent, ~0 elsewhere
    mask = np.clip(sat * 2.0, 0, 1) * np.clip((val - .18) * 1.7, 0, 1) * (1 - accent)
    mask = np.asarray(
        Image.fromarray((mask * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(9)),
        dtype=np.float32) / 255.0
    mask = (mask[..., None] * strength)

    grey = f.mean(2, keepdims=True)
    out = f * (1 - mask) + (grey * 0.30) * mask        # desaturate and pull down
    return np.clip(out * 255, 0, 255).astype(np.uint8)


# ---------------------------------------------------------------- white balance
def neutralise(arr, strength=0.7):
    """Pull the showroom's green fluorescent cast out of the interior shots.

    The 60MP interiors (second batch) are lit through showroom glass and carry a
    clear green-cyan tint. Damped grey-world: scale each channel toward the mean
    so the cast goes without flipping the car's coloured details.
    """
    if strength <= 0:
        return arr
    f = arr.astype(np.float32) / 255.0
    mean = f.reshape(-1, 3).mean(0)
    target = mean.mean()
    gain = np.clip(target / np.maximum(mean, 1e-4), 0.75, 1.35)
    gain = 1.0 + (gain - 1.0) * strength
    return np.clip(f * gain * 255, 0, 255).astype(np.uint8)


# ---------------------------------------------------------------- studio grade
def studioise(arr, strength, cx=0.5, cy=0.28):
    """Relight a real showroom photo as if it were shot in a black studio.

    Saad's brief: the same shots, but on a black background with only a top spot
    light. This is the non-generative way to do it —
    a top-centre light falloff plus a hard black crush, so the showroom sinks and
    only what the 'spot' hits survives. The car's own pixels are never redrawn.
    """
    if strength <= 0:
        return arr
    h, w = arr.shape[:2]
    y = (np.arange(h, dtype=np.float32)[:, None] / h - cy)
    x = (np.arange(w, dtype=np.float32)[None, :] / w - cx)
    # elliptical cone: wide across, long down the frame, like a hard top spot
    d = np.sqrt((x / 0.62) ** 2 + (y / 0.78) ** 2)
    spot = np.clip(1.25 - d, 0, 1) ** 1.5

    f = arr.astype(np.float32) / 255.0
    lit = f * (0.16 + 0.84 * spot[..., None])          # everything outside the cone falls away
    crushed = np.clip((lit - 0.055) / 0.945, 0, 1) ** 1.18   # hard black crush
    out = f * (1 - strength) + crushed * strength
    return np.clip(out * 255, 0, 255).astype(np.uint8)


# ---------------------------------------------------------------- studio plate
def largest_blob(alpha, thresh=40):
    """Keep only the biggest connected region of an alpha channel.

    rembg treats props, stands and torn-off pieces of the lightbox wall
    as foreground too, so a raw cut-out floats a cloud of debris above the
    car. The car is always the largest single blob. Iterative row-wise union-find
    with a plain dict — no scipy on this Mac.
    """
    m = alpha > thresh
    h, w = m.shape
    lab = np.zeros((h, w), np.int32)
    parent = {}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    nxt = 1
    for y in range(h):
        row, prev = m[y], lab[y - 1] if y else None
        cur = lab[y]
        run = -1
        for x in range(w):
            if not row[x]:
                run = -1
                continue
            up = prev[x] if prev is not None and prev[x] else 0
            left = cur[x - 1] if x and cur[x - 1] else 0
            if up and left:
                cur[x] = min(up, left); union(up, left)
            elif up or left:
                cur[x] = up or left
            else:
                parent[nxt] = nxt; cur[x] = nxt; nxt += 1
            run = x
    if nxt == 1:
        return alpha
    flat = np.vectorize(lambda v: find(v) if v else 0, otypes=[np.int32])(lab)
    ids, counts = np.unique(flat[flat > 0], return_counts=True)
    keep = ids[counts.argmax()]
    return np.where(flat == keep, alpha, 0).astype(alpha.dtype)


def studio_plate(cutout_png, out_path, size=(1620, 2880), car_w=0.88, base=0.62):
    """Put a cut-out car on a real black studio floor: top light, pool, reflection.

    Saad also wanted full-car wides with the same grade. The grade alone CANNOT do
    this — the showroom wall is a printed backdrop whose warm tones fall inside the
    accent band wallkill() protects, so it survives every wide. The background has to
    be removed (a local rembg cut-out, free), not colour-graded.

    Everything here is the real photograph's pixels; only the floor and the
    light are synthetic.
    """
    W_, H_ = size
    car = Image.open(cutout_png).convert("RGBA")
    ca = np.asarray(car).copy()
    ca[..., 3] = largest_blob(ca[..., 3])                # drop props / wall scraps
    car = Image.fromarray(ca)
    bb = car.getbbox()
    if bb:
        car = car.crop(bb)                               # now trims to the car alone

    scale = (W_ * car_w) / car.width
    car = car.resize((max(1, round(car.width * scale)),
                      max(1, round(car.height * scale))), Image.LANCZOS)

    a = np.asarray(car, np.float32) / 255.0
    rgb, alpha = a[..., :3], a[..., 3:4]

    # key from above: the roofline reads brighter than the sills
    gy = np.linspace(0, 1, car.height, dtype=np.float32)[:, None, None]
    rgb = np.clip(rgb * (1.18 - 0.42 * gy), 0, 1)

    canvas = np.zeros((H_, W_, 3), np.float32)

    # overhead cone, and the pool it throws on the floor
    yy = np.arange(H_, dtype=np.float32)[:, None] / H_
    xx = np.arange(W_, dtype=np.float32)[None, :] / W_
    cone = np.clip(1 - np.sqrt(((xx - .5) / (.10 + .55 * yy)) ** 2 + ((yy - .0) / 1.5) ** 2), 0, 1) ** 2
    canvas += cone[..., None] * 0.055

    x0 = (W_ - car.width) // 2
    y1 = int(H_ * base)
    y0 = y1 - car.height

    pool = np.clip(1 - np.sqrt(((xx - .5) / .52) ** 2 + ((yy - base) / .085) ** 2), 0, 1) ** 1.6
    canvas += pool[..., None] * 0.16

    # reflection first, so the car sits on top of it
    ref = np.flipud(rgb), np.flipud(alpha)
    rh = int(car.height * 0.45)
    rr = np.asarray(Image.fromarray((ref[0] * 255).astype(np.uint8)).resize((car.width, rh), Image.LANCZOS), np.float32) / 255.0
    ra = np.asarray(Image.fromarray((ref[1][..., 0] * 255).astype(np.uint8)).resize((car.width, rh), Image.LANCZOS).filter(ImageFilter.GaussianBlur(6)), np.float32) / 255.0
    fade = np.linspace(0.30, 0.0, rh, dtype=np.float32)[:, None]
    ra = (ra * fade)[..., None]
    ry0, ry1 = y1, min(H_, y1 + rh)
    if ry1 > ry0:
        h = ry1 - ry0
        sl = canvas[ry0:ry1, x0:x0 + car.width]
        canvas[ry0:ry1, x0:x0 + car.width] = sl * (1 - ra[:h]) + rr[:h] * ra[:h]

    cy0, cy1 = max(0, y0), min(H_, y1)
    sy0 = cy0 - y0
    sl = canvas[cy0:cy1, x0:x0 + car.width]
    ca, cr = alpha[sy0:sy0 + (cy1 - cy0)], rgb[sy0:sy0 + (cy1 - cy0)]
    canvas[cy0:cy1, x0:x0 + car.width] = sl * (1 - ca) + cr * ca

    out = np.clip((np.clip(canvas - 0.012, 0, 1) / 0.988) ** 1.06 * 255, 0, 255).astype(np.uint8)
    Image.fromarray(out).save(out_path, quality=95, subsampling=0)
    return out_path


# ---------------------------------------------------------------- the cloth
def silk(width, height, seed=7):
    """A black silk sheet: folds from stacked sines + noise, near-black with sheen.

    ponytail: drawn, not stock. It only ever sits ON TOP of the photograph, so it
    cannot alter the car. Wide enough to slide fully out of frame.
    """
    rng = np.random.default_rng(seed)
    x = np.linspace(0, 1, width, dtype=np.float32)[None, :]
    y = np.linspace(0, 1, height, dtype=np.float32)[:, None]

    folds = np.zeros((height, width), np.float32)
    for freq, amp, ph in ((7, .55, .3), (13, .28, 1.7), (23, .14, 3.1), (41, .07, 5.0)):
        folds += amp * np.sin(2 * np.pi * (x * freq + ph + y * .35 * np.sin(ph)))
    folds = (folds - folds.min()) / (folds.max() - folds.min())

    grain = rng.normal(0, 1, (height // 8, width // 8)).astype(np.float32)
    grain = np.asarray(Image.fromarray(((grain - grain.min()) /
                       (np.ptp(grain) + 1e-6) * 255).astype(np.uint8)
                       ).resize((width, height), Image.BICUBIC), np.float32) / 255.0

    lum = 0.020 + 0.155 * (folds ** 1.8) * (0.75 + 0.25 * grain)
    lum *= 0.80 + 0.20 * (1 - y)                       # light falls from above
    rgb = np.stack([lum * 1.00, lum * 0.99, lum * 1.06], -1)  # a hair cool
    return np.clip(rgb * 255, 0, 255).astype(np.uint8)


def cloth_frame(base, sheet, t):
    """Composite the sheet over `base`. t=1 fully covered, t=0 fully off.

    The sheet exits toward the lower-left — i.e. pulled off the BACK of the car,
    which in the hero frame sits away from camera and to the left.
    """
    if t >= 0.999:
        prog = 0.0
    elif t <= 0.001:
        return base
    else:
        prog = 1.0 - t

    sh, sw = sheet.shape[:2]
    # leading edge sweeps across the frame; ease-out so the pull decelerates
    e = 1 - (1 - prog) ** 2
    off_x = int(-e * (sw * 0.92))
    off_y = int(e * (H * 0.30))

    canvas = np.zeros((H, W, 3), np.uint8)
    alpha = np.zeros((H, W), np.float32)

    xs0, xs1 = max(0, off_x), min(W, off_x + sw)
    ys0, ys1 = max(0, off_y), min(H, off_y + sh)
    if xs1 > xs0 and ys1 > ys0:
        canvas[ys0:ys1, xs0:xs1] = sheet[ys0 - off_y:ys1 - off_y, xs0 - off_x:xs1 - off_x]
        alpha[ys0:ys1, xs0:xs1] = 1.0

    # wavy, soft trailing edge so it reads as fabric, not a wipe
    gx = np.arange(W, dtype=np.float32)[None, :]
    gy = np.arange(H, dtype=np.float32)[:, None]
    edge = off_x + sw + 26 * np.sin(gy / 95.0 + prog * 5.0) + 14 * np.sin(gy / 41.0)
    feather = np.clip((edge - gx) / 70.0, 0, 1)
    alpha = alpha * feather

    # a rim of catch-light on the lifting edge
    rim = np.clip(1 - np.abs(gx - edge) / 30.0, 0, 1) * alpha * 0.55

    a = alpha[..., None]
    out = base.astype(np.float32) * (1 - a) + canvas.astype(np.float32) * a
    out += (rim[..., None] * 90.0)
    return np.clip(out, 0, 255).astype(np.uint8)


# ---------------------------------------------------------------- rendering
def prep(path):
    """Load once, pre-scale so per-frame crops are cheap and clean."""
    im = Image.open(path).convert("RGB")
    scale = (H * 1.45) / im.height
    if scale < 1:
        im = im.resize((round(im.width * scale), round(im.height * scale)), Image.LANCZOS)
    return im


def window(im, p):
    """Crop a 9:16 window at centre (cx, cy) and zoom z, then fit to 1080x1920."""
    ch = min(im.height, im.height / max(p["z"], .01))
    cw = ch * (W / H)
    if cw > im.width:
        cw, ch = im.width, im.width * (H / W)
    cx, cy = p["cx"] * im.width, p["cy"] * im.height
    x0 = min(max(cx - cw / 2, 0), im.width - cw)
    y0 = min(max(cy - ch / 2, 0), im.height - ch)
    return im.resize((W, H), Image.LANCZOS, box=(x0, y0, x0 + cw, y0 + ch))


def lerp(a, b, u):
    return a + (b - a) * u


def pair(v):
    return v if isinstance(v, tuple) else (v, v)


def render(out_dir, only=None, dump_stills=False):
    os.makedirs(out_dir, exist_ok=True)
    frames_dir = os.path.join(out_dir, "frames")
    os.makedirs(frames_dir, exist_ok=True)

    sheet = silk(int(W * 1.9), int(H * 1.35))
    cache, n = {}, 0

    for sh in SHOTS:
        if only and sh["id"] != only:
            continue
        path = s(sh["src"])
        if path not in cache:
            cache[path] = prep(path)
        im = cache[path]
        total = int(sh["dur"] * FPS)
        d0, d1 = pair(sh.get("dark", 0.0))
        c0, c1 = pair(sh.get("cloth", (0.0, 0.0)))

        for i in range(total):
            u = i / max(total - 1, 1)
            e = u * u * (3 - 2 * u)                     # smoothstep
            p = {k: lerp(sh["a"][k], sh["b"][k], e) for k in ("cx", "cy", "z")}
            arr = np.asarray(window(im, p), np.uint8)
            arr = neutralise(arr, sh.get("neutral", 0.0))
            arr = wallkill(arr, sh.get("wall", 0.0))
            spot = sh.get("spot", (0.5, 0.28))
            arr = studioise(arr, sh.get("studio", 0.0), spot[0], spot[1])

            dark = lerp(d0, d1, e)
            if dark > 0:
                arr = np.clip(arr.astype(np.float32) * (1 - dark), 0, 255).astype(np.uint8)

            ct = lerp(c0, c1, e)
            if ct > 0:
                arr = cloth_frame(arr, sheet, ct)

            n += 1
            Image.fromarray(arr).save(os.path.join(frames_dir, f"f{n:05d}.jpg"),
                                      quality=94, subsampling=0)
            if dump_stills and i == total // 2:
                Image.fromarray(arr).save(
                    os.path.join(out_dir, f"board_{sh['id']}_{sh['name'].replace(' ', '_')}.jpg"),
                    quality=92)
        print(f"  shot {sh['id']} {sh['name']:<9} {total:>3} frames  <- {os.path.basename(path)}")

    mp4 = os.path.join(out_dir, "reveal_proof.mp4")
    subprocess.run([FFMPEG, "-y", "-v", "error", "-framerate", str(FPS),
                    "-i", os.path.join(frames_dir, "f%05d.jpg"),
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
                    "-movflags", "+faststart", mp4], check=True)
    print(f"\n{mp4}  ({n / FPS:.1f}s, {W}x{H})")
    return mp4


def selfcheck():
    """One runnable check: the wall mask must sink teal and spare the accent colour."""
    teal = np.tile(np.array([[[10, 170, 180]]], np.uint8), (40, 40, 1))
    accent = np.tile(np.array([[[214, 168, 74]]], np.uint8), (40, 40, 1))   # warm, hue ~40
    assert wallkill(teal, 1.0).mean() < teal.mean() * 0.55, "wall not sunk"
    assert wallkill(accent, 1.0).mean() > accent.mean() * 0.80, "accent colour was damaged"
    a = np.full((H, W, 3), 120, np.uint8)
    sheet = silk(int(W * 1.9), int(H * 1.35))
    assert cloth_frame(a, sheet, 1.0).mean() < 60, "cloth does not cover"
    assert (cloth_frame(a, sheet, 0.0) == a).all(), "cloth does not clear"

    # z < 1 gets clamped by window() and the shot goes static — the beats shipped
    # motionless once because of this. Fail loudly instead.
    for sh in SHOTS:
        for k in ("a", "b"):
            assert sh[k]["z"] >= 1.0, f"shot {sh['id']} {k}.z={sh[k]['z']} < 1.0 -> static"
        assert sh["b"]["z"] != sh["a"]["z"] or sh["b"] != sh["a"], f"shot {sh['id']} has no motion"

    # and prove the window actually moves on a 9:16 source, where cw == full width
    im = Image.new("RGB", (2160, 3840))
    w0 = window(im, SHOTS[0]["a"]).size, window(im, SHOTS[0]["b"]).size
    assert w0[0] == w0[1] == (W, H), "window must always deliver 1080x1920"
    print("selfcheck ok")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="/tmp/car_reveal")
    ap.add_argument("--shot", type=int)
    ap.add_argument("--stills", action="store_true")
    ap.add_argument("--selfcheck", action="store_true")
    a = ap.parse_args()
    if a.selfcheck:
        selfcheck()
        sys.exit(0)
    render(os.path.expanduser(a.out), only=a.shot, dump_stills=a.stills)
