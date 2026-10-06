#!/usr/bin/env python3
"""sa_mobile_style — a phone-app composite in Saad's own CapCut layout (24 Sep 2026).

Saad re-laid one module's project by hand: glow scaled and masked, the app shrunk and lifted, two
thin masked COPIES of the app filling the gaps at the top and bottom of the phone's screen
hole, and the stock phone mockup (darkened) on top; our drawn iPhone back and frame hidden.
His settings are a JSON of his CapCut clip numbers (path: SA_MOBILE_STYLE).

This renders the same picture locally. It matters beyond looks: the markings are placed by
OCR on this composite, so the app has to sit exactly where CapCut puts it. Everything is
derived from his clip numbers with CapCut's own rules, checked against CapCut's renders of
his project - the full-size cover it saved at 09:54 (draft_cover.jpg, final state) and the
player captures of 09:35-09:38. Against the cover: app screen edges within 0.5 px, phone
outline within 0.3 px, glow within 1 level of 255, OCR word boxes identical (median 0 px).
  * a clip's picture fits the canvas at scale 1 (contain), then scales about the canvas
    centre; transform x*540 px right, y*960 px UP.
  * a mask lives in the clip's own picture: width/height are fractions of the picture,
    centre in half-sizes (y up), roundCorner a fraction of half the shorter side.
  * feather, measured: CapCut ramps a smoothstep over the box distance
    max(|x|/a, |y|/b) - 1, from -F to +F half-sizes, F = FEATHER_K * feather. That is why his
    glow is a soft diamond with faint diagonal creases, not a round blur.

    Tools/venv/bin/python3 Tools/sa_mobile_style.py LAYER_DIR TAG out.mp4
    Tools/venv/bin/python3 Tools/sa_mobile_style.py LAYER_DIR TAG out.png --at 12.5
    Tools/venv/bin/python3 Tools/sa_mobile_style.py paced.mp4 --layers LAYER_DIR --name TAG
    Tools/venv/bin/python3 Tools/sa_mobile_style.py --test

--layers is the drop-in for sa_phoneframe --layers: same files and layers.json keys, the
composite in Saad's style. Keys that mean something different on the CapCut side:
  mask   his app mask (square corners, a touch larger than the screen), not mask_config()
  back / front  still written, but hidden in his style (the stock mockup replaces them)
  + mockup, style   the noshadow stock PNG and the style JSON, for the CapCut restyle step
"""
import argparse, json, math, os, pathlib, subprocess, sys

FFMPEG = os.path.expanduser("~/.local/bin/ffmpeg")
if not os.path.exists(FFMPEG):
    FFMPEG = "ffmpeg"
HERE = pathlib.Path(__file__).resolve().parent
# your own style JSON and phone-mockup PNG; override with SA_MOBILE_STYLE / SA_PHONE_MOCKUP
STYLE = pathlib.Path(os.environ.get("SA_MOBILE_STYLE", str(HERE.parent / "Projects" / "mobile_style.json"))).expanduser()
MOCKUP = pathlib.Path(os.environ.get("SA_PHONE_MOCKUP", str(HERE.parent / "Projects" / "phone_mockup_noshadow.png"))).expanduser()
CANVAS = (1080, 1920)
APP_SCREEN = (107, 96, 866, 1728)   # where sa_phoneframe puts the app inside the L4 layer
# Saad's clip is the full stock PNG (2207x4564, floor shadow masked off). The noshadow PNG is
# exactly its pixels [39:2170, 0:4297] - checked pixel-identical - so it is placed there.
MOCKUP_FULL = (2207, 4564)
NOSHADOW_AT = (39, 0)
FEATHER_K = 5.05     # fitted on a glow-only capture (09:35), confirmed on the final cover
# CapCut's adjustments on the mockup (brightness -0.94, white +0.77, black -0.08, tone -1,
# an HSL tweak) as one curve per channel, out = k * (in - x0) ** g, fitted to its render of
# the frame; on the full-size cover the body is within 2 levels of 255 on average.
MOCKUP_TONE = ((2.176, 63.9, 0.796), (1.854, 51.6, 0.834), (1.881, 61.8, 0.825))
_ST = None


def style():
    global _ST
    if _ST is None:
        _ST = json.loads(STYLE.read_text())["layers"]
    return _ST


def place(clip, size):
    """CapCut clip -> (kx, ky, cx, cy, rot): picture px scale and its centre on the canvas."""
    W, H = CANVAS
    s0 = min(W / size[0], H / size[1])
    return (s0 * clip["scale"]["x"], s0 * clip["scale"]["y"],
            W / 2 + clip["transform"]["x"] * W / 2, H / 2 - clip["transform"]["y"] * H / 2,
            clip.get("rotation", 0.0) % 360)


def to_canvas(clip, size, u, v):
    kx, ky, cx, cy, rot = place(clip, size)
    dx, dy = (u - size[0] / 2) * kx, (v - size[1] / 2) * ky
    c, s = math.cos(math.radians(rot)), math.sin(math.radians(rot))
    return cx + dx * c - dy * s, cy + dx * s + dy * c


def mask_rect(mask, size):
    """A CapCut mask in picture px: (x0, y0, x1, y1, corner radius)."""
    w, h = mask["width"] * size[0], mask["height"] * size[1]
    mx = size[0] / 2 + mask["centerX"] * size[0] / 2
    my = size[1] / 2 - mask["centerY"] * size[1] / 2
    return (mx - w / 2, my - h / 2, mx + w / 2, my + h / 2,
            mask.get("roundCorner", 0) * min(w, h) / 2)


def app_to_canvas(x, y, st=None):
    """A point in the L4 app layer (= old canvas px) -> where CapCut shows it."""
    return to_canvas((st or style())["app"]["clip"], CANVAS, x, y)


def box_to_canvas(box, st=None):
    """[x, y, w, h] in the L4 app layer -> [x, y, w, h] on Saad's canvas (uniform scale)."""
    x0, y0 = app_to_canvas(box[0], box[1], st)
    x1, y1 = app_to_canvas(box[0] + box[2], box[1] + box[3], st)
    return [round(x0, 1), round(y0, 1), round(x1 - x0, 1), round(y1 - y0, 1)]


def screen_rect(st=None):
    """The app's screen on the final canvas, (x, y, w, h) - for markings and checks."""
    return tuple(box_to_canvas(APP_SCREEN, st))


def _warp(im, kx, ky, cx, cy):
    """Place a picture on the canvas at sub-pixel accuracy: centre (cx, cy), scale (kx, ky).
    Premultiplied, so transparent edges do not fringe; LANCZOS with a float box, so a
    shrink is properly filtered."""
    from PIL import Image
    W, H = CANVAS
    mw, mh = im.size
    u0, u1 = mw / 2 - cx / kx, mw / 2 + (W - cx) / kx
    v0, v1 = mh / 2 - cy / ky, mh / 2 + (H - cy) / ky
    ox, oy = math.floor(u0) - 3, math.floor(v0) - 3
    big = im.convert("RGBa").crop((ox, oy, math.ceil(u1) + 3, math.ceil(v1) + 3))
    return big.resize(CANVAS, Image.LANCZOS, box=(u0 - ox, v0 - oy, u1 - ox, v1 - oy)).convert("RGBA")


def feather_alpha(mask, size, kx, ky, cx, cy):
    """CapCut's feathered rectangle mask, rendered on the canvas as 0..1 (numpy)."""
    import numpy as np
    x0, y0, x1, y1, _ = mask_rect(mask, size)
    mcx, mcy = cx + ((x0 + x1) / 2 - size[0] / 2) * kx, cy + ((y0 + y1) / 2 - size[1] / 2) * ky
    a, b = (x1 - x0) / 2 * kx, (y1 - y0) / 2 * ky
    Y, X = np.mgrid[0:CANVAS[1], 0:CANVAS[0]].astype(np.float32) + 0.5
    d = np.maximum(np.abs(X - mcx) / a, np.abs(Y - mcy) / b) - 1
    F = max(FEATHER_K * mask.get("feather", 0), 1e-3)
    t = np.clip(0.5 - d / (2 * F), 0, 1)
    return t * t * (3 - 2 * t)


def glow_layer(glow_png, st=None):
    """L2 with Saad's transform and feathered mask, as a canvas RGBA (numpy float 0..1)."""
    import numpy as np
    from PIL import Image
    L = (st or style())["glow"]
    im = Image.open(glow_png)
    kx, ky, cx, cy, _ = place(L["clip"], im.size)
    g = np.asarray(_warp(im, kx, ky, cx, cy), dtype=np.float32) / 255
    g[..., 3] *= feather_alpha(L["mask"], im.size, kx, ky, cx, cy) * L["clip"].get("alpha", 1.0)
    return g


def _curve(k, x0, g):
    import numpy as np
    return (k * np.clip(np.arange(256.0) - x0, 0, None) ** g).clip(0, 255).round().astype(np.uint8)


def mockup_layer(st=None, png=MOCKUP):
    """The stock mockup as Saad placed it, CapCut's darkening approximated by a curve."""
    import numpy as np
    from PIL import Image
    L = (st or style())["mockup"]
    im = Image.open(png).convert("RGBA")
    kx, ky, cx, cy, _ = place(L["clip"], MOCKUP_FULL)
    # where the noshadow crop's centre lands, in the full picture's frame
    ncx = cx + (NOSHADOW_AT[0] + im.size[0] / 2 - MOCKUP_FULL[0] / 2) * kx
    ncy = cy + (NOSHADOW_AT[1] + im.size[1] / 2 - MOCKUP_FULL[1] / 2) * ky
    a = np.asarray(im).copy()
    for i, tone in enumerate(MOCKUP_TONE):
        a[..., i] = _curve(*tone)[a[..., i]]
    return _warp(Image.fromarray(a), kx, ky, ncx, ncy)


def pill(size, rect, r, path, ss=4):
    """White rounded rectangle at a sub-pixel rect (the strip masks), drawn 4x and shrunk."""
    from PIL import Image, ImageDraw
    m = Image.new("L", (size[0] * ss, size[1] * ss), 0)
    ImageDraw.Draw(m).rounded_rectangle([v * ss for v in rect], radius=r * ss, fill=255)
    m.resize(size, Image.LANCZOS).save(path)


def _snap(lo, hi, f, n):
    """Integer crop [a, b) covering [lo, hi] whose ends land nearest whole canvas px under f.
    ffmpeg places and sizes in whole pixels; this keeps that rounding under 0.15 px."""
    err = lambda u: abs(f(u) - round(f(u)))
    a = min(range(max(0, math.floor(lo) - 4), math.floor(lo) + 1), key=err)
    b = min(range(math.ceil(hi), min(n, math.ceil(hi) + 4) + 1), key=err)
    return a, b


def _strip(name, st, tmp):
    """One app picture as an ffmpeg chain: crop round its mask in L4 px, turn, scale, place."""
    L = st[name]
    x0, y0, x1, y1, r = mask_rect(L["mask"], CANVAS)
    rot = place(L["clip"], CANVAS)[4]
    ua, ub = _snap(x0, x1, lambda u: to_canvas(L["clip"], CANVAS, u, 960)[0], CANVAS[0])
    va, vb = _snap(y0, y1, lambda v: to_canvas(L["clip"], CANVAS, 540, v)[1], CANVAS[1])
    corners = [to_canvas(L["clip"], CANVAS, u, v) for u in (ua, ub) for v in (va, vb)]
    X0, Y0 = round(min(p[0] for p in corners)), round(min(p[1] for p in corners))
    ow, oh = round(max(p[0] for p in corners)) - X0, round(max(p[1] for p in corners)) - Y0
    turn = {0: "", 180: ",hflip,vflip"}[round(rot) % 360]
    chain = f"crop={ub - ua}:{vb - va}:{ua}:{va}{turn},scale={ow}:{oh}:flags=lanczos"
    mk = None
    if r > 0.5:
        from PIL import Image
        mk = pathlib.Path(tmp) / f"{name}.mask.png"
        pill((ub - ua, vb - va), (x0 - ua, y0 - va, x1 - ua, y1 - va), r, mk)  # picture px ...
        m = Image.open(mk)
        if turn:
            m = m.rotate(180)
        m.resize((ow, oh), Image.LANCZOS).save(mk)                            # ... then scaled
    return chain, (X0, Y0), mk


def _graph(layer_dir, tag, tmp, st):
    """Stills flattened once (background + glow; mockup cropped to its box), the three app
    pictures overlaid per frame - the sa_phoneframe.composite recipe."""
    import numpy as np
    from PIL import Image
    layer_dir, tmp = pathlib.Path(layer_dir), pathlib.Path(tmp)
    bg = np.asarray(Image.open(layer_dir / "L1_background.png").convert("RGB"), dtype=np.float32) / 255
    g = glow_layer(layer_dir / "L2_glow.png", st)
    under = bg * (1 - g[..., 3:]) + g[..., :3] * g[..., 3:]
    Image.fromarray((under * 255 + 0.5).astype(np.uint8)).save(tmp / "under.png")
    mk = mockup_layer(st)
    bb = mk.getbbox()
    mk.crop(bb).save(tmp / "mockup.png")
    inputs = [tmp / "under.png", layer_dir / f"L4_app_{tag}.mp4", tmp / "mockup.png"]
    hold = "loop=loop=-1:size=1:start=0,setpts=N/30/TB"
    # overlays run in RGB: in YUV ffmpeg rounds an overlay's x and y DOWN to even (the chroma
    # grid) - that alone put the app 1 px left and 1 px high of CapCut on the first try.
    fc = [f"[0:v]format=rgb24,{hold}[u]", "[1:v]setpts=PTS-STARTPTS,format=rgb24,split=3[a0][a1][a2]"]
    app, (ax, ay), _ = _strip("app", st, tmp)            # square corners: no alpha needed
    fc += [f"[a0]{app}[app]", f"[u][app]overlay={ax}:{ay}:shortest=1:format=rgb[c0]"]
    last = "c0"
    for i, name in enumerate(("app_fill_strip_A", "app_fill_strip_B"), 1):
        chain, (x, y), m = _strip(name, st, tmp)
        inputs.append(m)
        n = len(inputs) - 1
        fc += [f"[a{i}]{chain},format=rgba[s{i}]", f"[{n}:v]format=gray,{hold}[m{i}]",
               f"[s{i}][m{i}]alphamerge[f{i}]", f"[{last}][f{i}]overlay={x}:{y}:format=rgb[c{i}]"]
        last = f"c{i}"
    fc += [f"[2:v]format=rgba,{hold}[mk]", f"[{last}][mk]overlay={bb[0]}:{bb[1]}:format=rgb,format=yuv420p[v]"]
    return inputs, ";".join(fc)


def _run(layer_dir, tag, out, st, at=None):
    import tempfile
    st = st or style()
    with tempfile.TemporaryDirectory() as tmp:
        inputs, fc = _graph(layer_dir, tag, tmp, st)
        dur = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                              "csv=p=0", str(inputs[1])], capture_output=True, text=True).stdout.strip()
        if at is not None:
            # at or past the last frame the seek yields no app frame, and the looped stills then
            # run forever (hung 2+ min on 02 at its duration, 24 Sep): hold the last frame instead
            at = max(0.0, min(at, float(dur) - 1.5 / 30))
        cmd = [FFMPEG, "-y", "-v", "error"]
        for i, p in enumerate(inputs):
            if i == 1 and at is not None:
                cmd += ["-ss", f"{at:.4f}"]
            cmd += ["-i", str(p)]
        cmd += ["-filter_complex", fc, "-map", "[v]"]
        if at is not None:
            cmd += ["-frames:v", "1", "-update", "1", str(out)]
        else:
            cmd += ["-t", dur, "-c:v", "libx264", "-crf", "18", "-preset", "veryfast", "-r", "30",
                    str(out)]
        subprocess.run(cmd, check=True, timeout=120 if at is not None else None)
    return str(out)


def composite(layer_dir, tag, out_mp4, st=None):
    """The whole module in Saad's style, silent, for OCR marking placement and the preview."""
    return _run(layer_dir, tag, out_mp4, st)


def render_frame(layer_dir, tag, t, out_png, st=None):
    """One frame at t seconds, through the same graph as composite()."""
    return _run(layer_dir, tag, out_png, st, at=t)


def layers(src, outdir, name):
    """Drop-in for sa_phoneframe.layers(): same layer files and keys, Saad's composite."""
    sys.path.insert(0, str(HERE))
    import sa_phoneframe as pf
    outdir = pathlib.Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    P = {"background": outdir / "L1_background.png", "glow": outdir / "L2_glow.png",
         "back": outdir / "L3_iphone_back.png", "screen": outdir / f"L4_app_{name}.mp4",
         "front": outdir / "L5_iphone_front.png"}
    pf.layer_background(P["background"]); pf.layer_glow(P["glow"])
    pf.layer_back(P["back"]); pf.layer_frame(P["front"])
    pf.layer_screen(src, P["screen"])
    P = {k: str(v) for k, v in P.items()}
    comp = outdir / f"COMPOSITE_{name}.mp4"
    composite(outdir, name, comp)
    P.update(composite=str(comp), mask=style()["app"]["mask"], mockup=str(MOCKUP),
             style=str(STYLE), screen_rect=screen_rect())
    (outdir / "layers.json").write_text(json.dumps(P, indent=1))
    return P


def _test():
    import tempfile
    st = style()
    # CapCut maths alone, on Saad's numbers: the app fills the width of the phone's hole ...
    ax0, ay0 = to_canvas(st["app"]["clip"], CANVAS, APP_SCREEN[0], APP_SCREEN[1])
    ax1, ay1 = to_canvas(st["app"]["clip"], CANVAS, APP_SCREEN[0] + APP_SCREEN[2], APP_SCREEN[1] + APP_SCREEN[3])
    assert abs((ax0 + ax1) / 2 - 540) < 0.01 and abs((ax1 - ax0) / (ay1 - ay0) - 866 / 1728) < 1e-6
    kx, ky, cx, cy, _ = place(st["mockup"]["clip"], MOCKUP_FULL)
    hole = (159, 101, 2049, 4195)                    # measured in the stock PNG
    hx0, hy0 = cx + (hole[0] - MOCKUP_FULL[0] / 2) * kx, cy + (hole[1] - MOCKUP_FULL[1] / 2) * ky
    hx1, hy1 = cx + (hole[2] - MOCKUP_FULL[0] / 2) * kx, cy + (hole[3] - MOCKUP_FULL[1] / 2) * ky
    assert abs(ax0 - hx0) < 1 and abs(ax1 - hx1) < 1, (ax0, ax1, hx0, hx1)
    # ... and his two copies close the gaps above and below it, inside the hole
    for name, lo, hi in (("app_fill_strip_B", hy0, ay0), ("app_fill_strip_A", ay1, hy1)):
        x0, y0, x1, y1, _ = mask_rect(st[name]["mask"], CANVAS)
        ys = sorted(to_canvas(st[name]["clip"], CANVAS, u, v)[1] for u in (x0, x1) for v in (y0, y1))
        assert ys[0] <= lo + 0.5 and ys[-1] >= hi - 0.5, (name, ys, lo, hi)
    # markings maths: box_to_canvas is exactly the app transform
    x, y, w, h = screen_rect()
    assert abs(x - ax0) < 0.06 and abs(y - ay0) < 0.06 and abs(x + w - ax1) < 0.1
    # ffmpeg places whole pixels: the snapped crops keep every edge within 0.15 px
    with tempfile.TemporaryDirectory() as tmp:
        for name in ("app", "app_fill_strip_A", "app_fill_strip_B"):
            chain, (X0, Y0), _ = _strip(name, st, tmp)
            cw, ch, ua, va = (int(v) for v in chain.split(",")[0][5:].split(":"))
            ex = [to_canvas(st[name]["clip"], CANVAS, u, v) for u in (ua, ua + cw) for v in (va, va + ch)]
            assert abs(min(p[0] for p in ex) - X0) < 0.15 and abs(min(p[1] for p in ex) - Y0) < 0.15, name
    # feather: a hard mask is 1 inside and 0 outside; his glow is a partial soft diamond
    fa = feather_alpha(st["app"]["mask"], CANVAS, 1, 1, 540, 960)
    assert fa[960, 540] == 1 and fa[10, 10] == 0
    ga = feather_alpha(st["glow"]["mask"], CANVAS, *place(st["glow"]["clip"], CANVAS)[:4])
    assert 0.6 < ga.max() < 0.75 and ga[1910, 540] < 0.01
    # the real ffmpeg graph on a 0.2 s app: red outside his app mask, white inside. A frame past
    # the end must still come back (it used to hang), with no red showing round the phone
    if MOCKUP.exists():
        import numpy as np
        from PIL import Image
        with tempfile.TemporaryDirectory() as tmp:
            Image.new("RGB", CANVAS, (4, 40, 36)).save(f"{tmp}/L1_background.png")
            Image.new("RGBA", CANVAS, (60, 200, 120, 160)).save(f"{tmp}/L2_glow.png")
            mx0, my0, mx1, my1, _ = mask_rect(st["app"]["mask"], CANVAS)
            a = np.zeros((CANVAS[1], CANVAS[0], 3), np.uint8); a[...] = (255, 0, 0)
            a[math.ceil(my0):math.floor(my1), math.ceil(mx0):math.floor(mx1)] = 255
            Image.fromarray(a).save(f"{tmp}/l4.png")
            subprocess.run([FFMPEG, "-v", "error", "-loop", "1", "-i", f"{tmp}/l4.png", "-t", "0.2", "-r", "30",
                            "-pix_fmt", "yuvj420p", "-c:v", "libx264", "-crf", "0", f"{tmp}/L4_app_t.mp4"], check=True)
            o = np.asarray(Image.open(render_frame(tmp, "t", 5.0, f"{tmp}/o.png")).convert("RGB")).astype(int)
            assert not ((o[..., 0] > 90) & (o[..., 1] < o[..., 0] - 60)).any(), "app shows past its mask"
            assert (o[round(y + h / 2), round(x + w / 2)] > 240).all()
    print(f"ok - app screen ({x:.1f}, {y:.1f}, {w:.1f}x{h:.1f}) in hole x {hx0:.1f}-{hx1:.1f} "
          f"y {hy0:.1f}-{hy1:.1f}; glow peak {ga.max():.2f}")


if __name__ == "__main__":
    a = argparse.ArgumentParser()
    a.add_argument("args", nargs="*")
    a.add_argument("--at", type=float, help="render one frame at this time (s) to a PNG")
    a.add_argument("--layers", help="write the CapCut layers + Saad-style composite here")
    a.add_argument("--name", default="app")
    a.add_argument("--test", action="store_true")
    n = a.parse_args()
    if n.test:
        _test()
    elif n.layers and len(n.args) == 1:
        print(json.dumps(layers(n.args[0], n.layers, n.name), indent=1))
    elif len(n.args) == 3 and n.at is not None:
        print(render_frame(*n.args[:2], n.at, n.args[2]))
    elif len(n.args) == 3:
        print(composite(*n.args))
    else:
        a.error("need LAYER_DIR TAG out.mp4 [--at t], or src --layers DIR --name TAG, or --test")
