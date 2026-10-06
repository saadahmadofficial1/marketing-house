#!/usr/bin/env python3
"""sa_phoneframe — put a phone screen-recording inside a phone, on a branded background.

Requirement (23 Sep 2026): the whole video sits inside an iPhone mockup.

The reference he sent is an app advert: the screen sits inside a phone body on a glowing
background, with room above and below for a title and captions. That format also solves
the vertical problem — a raw 1206x2622 recording is taller than 9:16, so bare it leaves
dead bars; inside a phone the surround becomes the design instead of waste.

Colours are NOT taken from the reference. STYLE_DNA forbids purple gradients and says
never invent a colour — derive from the brand palette (neutral placeholders here: #1B3A4B
and #2E7D32; set your own). The ground is the app's own panel colour and sits with its
accent colour, so the frame, the ground and the call-out boxes agree.

    Tools/venv/bin/python3 Tools/sa_phoneframe.py in.mp4 out.mp4
    Tools/venv/bin/python3 Tools/sa_phoneframe.py --plate plate.png   # just the backdrop
    Tools/venv/bin/python3 Tools/sa_phoneframe.py --test

Prints the screen rectangle, which is what any marking tool needs to stay in register.
"""
import argparse, json, os, pathlib, subprocess, sys

FFMPEG = os.path.expanduser("~/.local/bin/ffmpeg")
if not os.path.exists(FFMPEG):
    FFMPEG = "ffmpeg"

CANVAS = (1080, 1920)
SRC = (1206, 2403)          # the recording already cropped of iOS chrome
# Requirement (23 Sep): a darker ground, and a larger phone and app on screen. His
# reference phone video fills 91% of the frame height on a light ground, so match that rather than my earlier
# cautious margins - the app inside is the thing being taught and it has to be read.
TOP = 92                    # clear space above the phone
BOTTOM = 92                 # clear space below

# MEASURED OFF SAAD'S OWN EARLIER PHONE-APP VIDEO (23 Sep 2026), so the device matches
# his approved style. His device there is 487x980 with a 466x974 screen: a side bezel of only
# 10-11px (2.1% of device width) and a 3px hairline top and bottom. It is a rim, not a
# frame - my first attempt used a 20px band all round and read as a toy.
BEZEL_X_PCT = 0.021         # side bezel as a fraction of device width
BEZEL_Y = 4                 # hairline top and bottom
RIM = (169, 155, 166)       # the pale metallic band, sampled from his frame
DEEP = (27, 58, 75)         # #1B3A4B (placeholder brand dark)
GLOW = (46, 125, 50)        # #2E7D32 (placeholder brand green)
# Requirement (23 Sep): the same green style behind the phone, but dark, matched to the
# app interface. So the ground is not a brand guess and not a
# light plate - it is the app's OWN panel colour, sampled across four modules:
# the most common colour by pixel count, far ahead of anything else. The values below
# are neutral placeholders: sample your own app's panel colours.
APP_DARK = (38, 50, 56)      # #263238 - the app's header and card panels
APP_DARKER = (28, 38, 43)    # #1C262B - its shadowed edge, for the gradient


def geometry():
    dh = CANVAS[1] - TOP - BOTTOM
    sh = dh - 2 * BEZEL_Y
    sw = round(sh * SRC[0] / SRC[1])
    if sw % 2:
        sw -= 1
    bez = round(sw * BEZEL_X_PCT / (1 - 2 * BEZEL_X_PCT))
    dw = sw + 2 * bez
    dx = (CANVAS[0] - dw) // 2
    return {"screen": (dx + bez, TOP + BEZEL_Y, sw, sh),
            "body": (dx, TOP, dw, dh), "bezel": bez, "scale": sw / SRC[0]}


def plate(path):
    """The app's own dark green as the ground, with the device large on it.

    Matching the interface rather than inventing a backdrop means the frame never fights
    the screen inside it — the phone reads as a window onto the same product."""
    from PIL import Image, ImageDraw, ImageFilter
    g = geometry()
    W, H = CANVAS
    bx, by, bw, bh = g["body"]

    # vertical gradient: the app panel colour, deepening towards both edges
    col = Image.new("RGB", (1, H))
    for y in range(H):
        t = abs(y / (H - 1) - 0.42) / 0.58            # 0 at the phone's centre, 1 at an edge
        col.putpixel((0, y), tuple(round(APP_DARK[i] + (APP_DARKER[i] - APP_DARK[i]) * t)
                                   for i in range(3)))
    im = col.resize((W, H))

    # a low lift behind the device so the ground is not a flat field
    m = Image.new("L", (W, H), 0)
    ImageDraw.Draw(m).rounded_rectangle([bx - 200, by - 160, bx + bw + 200, by + bh + 200],
                                        radius=270, fill=52)
    im = Image.composite(Image.new("RGB", (W, H), GLOW), im,
                         m.filter(ImageFilter.GaussianBlur(180)))

    # contact shadow under the device
    sh_m = Image.new("L", (W, H), 0)
    ImageDraw.Draw(sh_m).rounded_rectangle([bx - 16, by + 14, bx + bw + 16, by + bh + 30],
                                           radius=110, fill=150)
    im = Image.composite(Image.new("RGB", (W, H), (1, 12, 10)), im,
                         sh_m.filter(ImageFilter.GaussianBlur(42)))

    d = ImageDraw.Draw(im)
    R = round(bw * 0.105)
    d.rounded_rectangle([bx, by, bx + bw, by + bh], radius=R, fill=RIM)
    d.rounded_rectangle([bx + 3, by + 3, bx + bw - 3, by + bh - 3], radius=R - 3,
                        fill=(14, 12, 14))
    sx, sy, sw, sh = g["screen"]
    d.rounded_rectangle([sx, sy, sx + sw, sy + sh], radius=R - g["bezel"], fill=(0, 0, 0))
    d.rounded_rectangle([bx - 5, by + round(bh * 0.20), bx - 1, by + round(bh * 0.28)],
                        radius=3, fill=RIM)
    im.save(path)
    return g


def sheen(path, w, h, radius):
    """A soft diagonal highlight laid over the screen, so it reads as glass and not a
    hole cut in the plate. Kept very low — it must never fight the app underneath."""
    from PIL import Image, ImageDraw, ImageFilter
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    band = Image.new("L", (w, h), 0)
    dd = ImageDraw.Draw(band)
    dd.polygon([(-w, h * 0.42), (w * 0.72, -h * 0.06), (w * 1.5, h * 0.10), (-w, h * 0.70)],
               fill=34)
    band = band.filter(ImageFilter.GaussianBlur(46))
    keep = Image.new("L", (w, h), 0)
    ImageDraw.Draw(keep).rounded_rectangle([0, 0, w - 1, h - 1], radius=radius, fill=255)
    band = Image.composite(band, Image.new("L", (w, h), 0), keep)
    im.putalpha(band)
    im.paste((255, 255, 255), (0, 0, w, h), None)
    im.putalpha(band)
    im.save(path)


def corner_mask(path, w, h, radius):
    """White rounded rectangle on black — the screen's alpha, drawn once."""
    from PIL import Image, ImageDraw
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, w - 1, h - 1], radius=radius, fill=255)
    m.convert("RGB").save(path)


def render(src, out):
    g = geometry()
    sx, sy, sw, sh = g["screen"]
    out = pathlib.Path(out)
    plate_png = out.with_suffix(".plate.png")
    mask_png = out.with_suffix(".mask.png")
    plate(plate_png)
    R = round(g["body"][2] * 0.105) - g["bezel"]
    corner_mask(mask_png, sw, sh, R)
    sheen_png = out.with_suffix(".sheen.png")
    sheen(sheen_png, sw, sh, R)
    # alphamerge, not geq: geq evaluates an expression per pixel per frame and made a
    # 7-minute recording take minutes to composite. The mask is drawn once instead.
    vf = (f"[1:v]scale={sw}:{sh}:flags=lanczos,format=rgba[s];"
          f"[2:v]format=gray[m];[s][m]alphamerge[sa];"
          f"[0:v][sa]overlay={sx}:{sy}:format=auto[base];"
          f"[base][3:v]overlay={sx}:{sy}:format=auto[v]")
    subprocess.run([FFMPEG, "-y", "-v", "error",
                    "-loop", "1", "-i", str(plate_png),
                    "-i", str(src),
                    "-loop", "1", "-i", str(mask_png),
                    "-loop", "1", "-i", str(sheen_png),
                    "-filter_complex", vf, "-map", "[v]", "-map", "1:a?",
                    "-c:v", "libx264", "-crf", "18", "-preset", "veryfast",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
                    "-shortest", str(out)], check=True)
    mask_png.unlink(missing_ok=True)
    sheen_png.unlink(missing_ok=True)
    return g


def oklch_lift(rgb, dL):
    """Raise a colour's OKLCH lightness by dL, keeping its hue and chroma.
    STYLE_DNA: never invent a colour - derive it from the brand palette."""
    import math
    def lin(c):
        c /= 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    def gam(c):
        c = max(0.0, min(1.0, c))
        return round(255 * (12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055))
    r, g, b = (lin(v) for v in rgb)
    l = (0.4122214708 * r + 0.5363325363 * g + 0.05144599290 * b) ** (1 / 3)
    m = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3)
    s_ = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3)
    L = 0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s_
    A = 1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s_
    B = 0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s_
    L = min(1.0, L + dL)
    l2 = (L + 0.3963377774 * A + 0.2158037573 * B) ** 3
    m2 = (L - 0.1055613458 * A - 0.0638541728 * B) ** 3
    s2 = (L - 0.0894841775 * A - 1.2914855480 * B) ** 3
    return (gam(4.0767416621 * l2 - 3.3077115913 * m2 + 0.2309699292 * s2),
            gam(-1.2684380046 * l2 + 2.6097574011 * m2 - 0.3413193965 * s2),
            gam(-0.0041960863 * l2 - 0.7034186147 * m2 + 1.7076147010 * s2))


GLOW_COLOUR = oklch_lift(GLOW, 0.12)    # #2E7D32 lifted, so it reads as light, not paint


def layer_background(path):
    """Layer 1: the ground on its own - APP_DARK falling to APP_DARKER."""
    from PIL import Image
    W, H = CANVAS
    col = Image.new("RGB", (1, H))
    for y in range(H):
        t = abs(y / (H - 1) - 0.45) / 0.55
        col.putpixel((0, y), tuple(round(APP_DARK[i] + (APP_DARKER[i] - APP_DARK[i]) * t)
                                   for i in range(3)))
    col.resize((W, H)).save(path)


def layer_glow(path):
    """Layer 2: the halo alone, transparent everywhere else.

    Modelled on the app advert Saad sent: the light hugs the device - brightest right
    at the edge, gone within a couple of hundred pixels - rather than a wide soft wash.
    Three falloffs stacked: a tight core, a body, and a faint far reach."""
    from PIL import Image, ImageDraw, ImageFilter, ImageChops
    g = geometry()
    W, H = CANVAS
    bx, by, bw, bh = g["body"]
    R = round(bw * 0.105)
    alpha = Image.new("L", (W, H), 0)
    # 23 Sep: the first cut read as a hairline plus haze; Saad's reference holds strong
    # light for a couple of hundred pixels. Wider body, higher peaks.
    for grow, blur, peak in ((8, 16, 255), (34, 72, 235), (80, 170, 160)):
        m = Image.new("L", (W, H), 0)
        ImageDraw.Draw(m).rounded_rectangle([bx - grow, by - grow, bx + bw + grow, by + bh + grow],
                                            radius=R + grow, fill=peak)
        alpha = ImageChops.lighter(alpha, m.filter(ImageFilter.GaussianBlur(blur)))
    im = Image.new("RGBA", (W, H), GLOW_COLOUR + (0,))
    im.putalpha(alpha)
    im.save(path)


def layer_frame(path):
    """Layer 4: the iPhone itself - rim, bezel, island, button - with a transparent screen
    and transparent surroundings, so it sits over the app recording and over anything
    Saad puts behind it."""
    from PIL import Image, ImageDraw
    g = geometry()
    W, H = CANVAS
    bx, by, bw, bh = g["body"]
    sx, sy, sw, sh = g["screen"]
    R = round(bw * 0.105)
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([bx, by, bx + bw, by + bh], radius=R, fill=RIM + (255,))
    d.rounded_rectangle([bx + 3, by + 3, bx + bw - 3, by + bh - 3], radius=R - 3,
                        fill=(14, 12, 14, 255))
    d.rounded_rectangle([bx - 5, by + round(bh * 0.20), bx - 1, by + round(bh * 0.28)],
                        radius=3, fill=RIM + (255,))
    # punch the screen out
    hole = Image.new("L", (W, H), 0)
    ImageDraw.Draw(hole).rounded_rectangle([sx, sy, sx + sw, sy + sh], radius=R - g["bezel"],
                                           fill=255)
    a = im.getchannel("A")
    a.paste(0, mask=hole)
    im.putalpha(a)
    # Dynamic Island, drawn over the top of the screen as on a real device
    # Shorter and higher than a real island: with the status bar cropped, the app's own
    # header rides up under where the island sits, and a true-size one hid the app's logo.
    iw, ih = round(sw * 0.21), round(sh * 0.020)
    ImageDraw.Draw(im).rounded_rectangle([sx + (sw - iw) // 2, sy + 3,
                                          sx + (sw + iw) // 2, sy + 3 + ih],
                                         radius=ih // 2, fill=(6, 8, 8, 255))
    im.save(path)


ISLAND_TRIM = 20   # rows of the recording's own Dynamic Island left under the 130px crop


def layer_back(path):
    """Layer 3: the phone's body, solid - sits UNDER the app recording.
    If the CapCut mask ever rounds the recording a little too much, this is what shows in
    the corners, and it looks like bezel rather than a hole."""
    from PIL import Image, ImageDraw
    g = geometry()
    bx, by, bw, bh = g["body"]
    im = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle([bx, by, bx + bw, by + bh], radius=round(bw * 0.105),
                                         fill=(10, 10, 12, 255))
    im.save(path)


def layer_screen(src, path):
    """Layer 4: the app recording on a FULL-CANVAS MP4, sitting in the screen position.

    Not a transparent video: QuickTime Animation grew to 22.9 GB in ten minutes because
    compression noise changes every pixel on every frame. Instead the corners are rounded
    by CapCut's own rectangle mask - the method Saad used on his earlier phone video, and a slider he can
    move himself. Full canvas at scale 1 means no placement maths in CapCut at all.

    The top ISLAND_TRIM rows are dropped: iOS expands the Dynamic Island with the
    recording indicator and it reaches below the 130px status-bar crop."""
    g = geometry()
    sx, sy, sw, sh = g["screen"]
    W, H = CANVAS
    vf = (f"[0:v]crop=iw:ih-{ISLAND_TRIM}:0:{ISLAND_TRIM},scale={sw}:{sh}:flags=lanczos,"
          f"pad={W}:{H}:{sx}:{sy}:black,format=yuv420p[v]")
    subprocess.run([FFMPEG, "-y", "-v", "error", "-i", str(src), "-filter_complex", vf,
                    "-map", "[v]", "-an", "-c:v", "libx264", "-crf", "16", "-preset", "medium",
                    "-r", "30", str(path)], check=True)


def mask_config():
    """The CapCut rectangle mask for layer 4, in the units of Saad's own CapCut masks:
    width/height as fractions of the media, centre in half-sizes (0,0 = middle),
    roundCorner 0-1 of half the shorter side."""
    g = geometry()
    sx, sy, sw, sh = g["screen"]
    W, H = CANVAS
    r = round(g["body"][2] * 0.105) - g["bezel"]
    return {"width": sw / W, "height": sh / H,
            "centerX": (sx + sw / 2 - W / 2) / (W / 2), "centerY": (H / 2 - (sy + sh / 2)) / (H / 2),
            "rotation": 0.0, "feather": 0.0, "expansion": 0.0,
            "roundCorner": round(r / (min(sw, sh) / 2), 4), "invert": False, "aspectRatio": 1.0}


def composite(layer_paths, out):
    """What CapCut will show, rendered locally - for marking placement and the preview.

    Speed matters here: with five `-loop 1` stills ffmpeg re-decodes every PNG on every
    frame, and a 2-minute module crawled at a few frames a second (23 Sep). So the three
    layers below the recording are flattened ONCE into a single plate, and each still
    is decoded a single time and held with the `loop` filter."""
    from PIL import Image, ImageDraw
    g = geometry()
    sx, sy, sw, sh = g["screen"]
    r = round(g["body"][2] * 0.105) - g["bezel"]
    out = pathlib.Path(out)
    L = layer_paths
    under = Image.open(L["background"]).convert("RGBA")
    for k in ("glow", "back"):
        under = Image.alpha_composite(under, Image.open(L[k]).convert("RGBA"))
    under_png = out.with_suffix(".under.png"); under.convert("RGB").save(under_png)
    mask_png = out.with_suffix(".mask.png")
    m = Image.new("L", CANVAS, 0)
    ImageDraw.Draw(m).rounded_rectangle([sx, sy, sx + sw, sy + sh], radius=r, fill=255)
    m.save(mask_png)
    dur = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", L["screen"]], capture_output=True, text=True).stdout.strip()
    hold = "loop=loop=-1:size=1:start=0,setpts=N/30/TB"
    fc = (f"[0:v]{hold}[u];[1:v]format=rgba,{hold}[f];[2:v]format=gray,{hold}[mk];"
          f"[3:v]format=rgba[s0];[s0][mk]alphamerge[s];"
          f"[u][s]overlay=0:0:shortest=1[c];[c][f]overlay=0:0,format=yuv420p[v]")
    subprocess.run([FFMPEG, "-y", "-v", "error",
                    "-i", str(under_png), "-i", L["front"], "-i", str(mask_png), "-i", L["screen"],
                    "-filter_complex", fc, "-map", "[v]", "-t", dur,
                    "-c:v", "libx264", "-crf", "18", "-preset", "veryfast", "-r", "30", str(out)],
                   check=True)
    under_png.unlink(missing_ok=True); mask_png.unlink(missing_ok=True)


def layers(src, outdir, name):
    """Write the separate CapCut layers for one module, plus a local composite."""
    outdir = pathlib.Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    P = {"background": outdir / "L1_background.png", "glow": outdir / "L2_glow.png",
         "back": outdir / "L3_iphone_back.png", "screen": outdir / f"L4_app_{name}.mp4",
         "front": outdir / "L5_iphone_front.png"}
    layer_background(P["background"]); layer_glow(P["glow"])
    layer_back(P["back"]); layer_frame(P["front"])
    layer_screen(src, P["screen"])
    P = {k: str(v) for k, v in P.items()}
    comp = outdir / f"COMPOSITE_{name}.mp4"
    composite(P, comp)
    P["composite"] = str(comp)
    P["mask"] = mask_config()
    (outdir / "layers.json").write_text(json.dumps(P, indent=1))
    return P


def _test():
    g = geometry()
    sx, sy, sw, sh = g["screen"]
    bx, by, bw, bh = g["body"]
    assert sh == CANVAS[1] - TOP - BOTTOM - 2 * BEZEL_Y, sh
    # the rim must match what was measured off his reference video, not a guess
    assert abs(g["bezel"] / (sw + 2 * g["bezel"]) - BEZEL_X_PCT) < 0.002, g["bezel"]
    assert abs(sw / sh - SRC[0] / SRC[1]) < 0.002, "screen must keep the recording's shape"
    assert bx >= 0 and bx + bw <= CANVAS[0], "phone body must fit the canvas"
    assert by + bh <= CANVAS[1] - BOTTOM + 1, "phone must leave the caption band clear"
    assert 0.70 < g["scale"] < 0.80, g["scale"]   # the app must be big enough to read
    assert g["body"][0] > 0 and g["body"][0] + g["body"][2] <= CANVAS[0]
    print(f"ok - screen {sw}x{sh} at ({sx},{sy}), app at {g['scale']:.3f} of source")


if __name__ == "__main__":
    a = argparse.ArgumentParser()
    a.add_argument("src", nargs="?"); a.add_argument("out", nargs="?")
    a.add_argument("--plate"); a.add_argument("--test", action="store_true")
    a.add_argument("--layers", help="write separate CapCut layers into this folder")
    a.add_argument("--name", default="app")
    n = a.parse_args()
    if n.test:
        _test()
    elif n.layers and n.src:
        print(json.dumps(layers(n.src, n.layers, n.name), indent=1))
    elif n.plate:
        print(plate(n.plate))
    elif n.src and n.out:
        print(render(n.src, n.out))
    else:
        a.error("need src and out, or --plate, or --test")
