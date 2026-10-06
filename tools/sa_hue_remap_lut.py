"""sa_hue_remap_lut — recolour a mobile app's dark teal to a desktop web app's navy, so a phone-app
training series matches the colour of the desktop one.

Requirement (25 Sep): match the phone-app videos to the desktop training videos' colour, and try it
first on a copy of one module.

Measured: mobile app dark teal #052927 (hue 177), desktop web navy #151D31 / #263B5E / active #2D3A88 (hue 220-230).
Only teal-ish pixels move: hue 155-195 fully, fading out to 140 and 210, and only if they carry colour
(saturation above ~0.15). Hue goes to 225, saturation is capped at 0.62 (the web navy's), brightness is kept -
so white text, greys, reds, ambers and bright status greens stay exactly as they were.

    sa_hue_remap_lut.py --lut out.cube            # a 33-point 3D LUT (ffmpeg lut3d, or CapCut Adjust > LUT)
    sa_hue_remap_lut.py --png in.png out.png      # a still, alpha kept
    sa_hue_remap_lut.py --video in.mp4 out.mp4    # through the LUT
    sa_hue_remap_lut.py --test
"""
import subprocess, sys
import numpy as np

HUE_TO, SAT_CAP = 225.0, 0.62


def rgb_to_hsv(rgb):
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    mx, mn = rgb.max(-1), rgb.min(-1); df = mx - mn
    h = np.zeros_like(mx)
    m = df > 1e-9
    rm, gm, bm = m & (mx == r), m & (mx == g) & (mx != r), m & (mx == b) & (mx != r) & (mx != g)
    h[rm] = ((g - b)[rm] / df[rm]) % 6
    h[gm] = (b - r)[gm] / df[gm] + 2
    h[bm] = (r - g)[bm] / df[bm] + 4
    s = np.where(mx > 1e-9, df / np.maximum(mx, 1e-9), 0)
    return h * 60.0, s, mx


def hsv_to_rgb(h, s, v):
    h = (h % 360) / 60.0; i = np.floor(h).astype(int) % 6; f = h - np.floor(h)
    p, q, t = v * (1 - s), v * (1 - s * f), v * (1 - s * (1 - f))
    out = np.stack([np.choose(i, [v, q, p, p, t, v]), np.choose(i, [t, v, v, q, p, p]), np.choose(i, [p, p, t, v, v, q])], -1)
    return out


def weight(h, s):
    wh = np.clip((h - 140) / 15, 0, 1) * np.clip((210 - h) / 15, 0, 1)
    ws = np.clip((s - 0.10) / 0.12, 0, 1)
    return wh * ws


def remap(rgb):
    """rgb float 0..1 (..., 3) -> recoloured rgb."""
    h, s, v = rgb_to_hsv(rgb)
    w = weight(h, s)
    dh = ((HUE_TO - h + 180) % 360) - 180
    h2 = h + w * dh
    s2 = s * (1 - w) + w * np.minimum(s, SAT_CAP)
    return rgb * (1 - w[..., None]) + hsv_to_rgb(h2, s2, v) * w[..., None]


def write_lut(path, n=33):
    g = np.linspace(0, 1, n)
    b, gg, r = np.meshgrid(g, g, g, indexing="ij")               # .cube order: red fastest
    rgb = np.stack([r, gg, b], -1).reshape(-1, 3)
    out = remap(rgb)
    with open(path, "w") as f:
        f.write(f'TITLE "teal to navy"\nLUT_3D_SIZE {n}\n')
        for x in out:
            f.write("%.6f %.6f %.6f\n" % tuple(np.clip(x, 0, 1)))
    return path


def png(src, dst):
    from PIL import Image
    im = Image.open(src); a = np.asarray(im.convert("RGBA")).astype(np.float64) / 255
    a[..., :3] = remap(a[..., :3])
    Image.fromarray((np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8), "RGBA").save(dst)


def video(src, dst, lut):
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-threads", "4", "-i", str(src), "-vf", f"lut3d=file='{lut}':interp=tetrahedral",
                    "-c:v", "libx264", "-crf", "15", "-preset", "medium", "-pix_fmt", "yuv420p", "-an", str(dst)], check=True)


def _test():
    c = lambda hx: np.array([[int(hx[i:i + 2], 16) / 255 for i in (1, 3, 5)]])
    hx = lambda a: "#%02X%02X%02X" % tuple(int(round(x * 255)) for x in a[0])
    teal = remap(c("#052927")); h, s, v = rgb_to_hsv(teal)
    assert 215 < h[0] < 235 and abs(v[0] - 0.16) < 0.02, (hx(teal), h, v)
    for keep in ("#FFFFFF", "#FCFCFC", "#3D3D3D", "#D83838", "#B4843C", "#45C269"):     # white, grey, red, amber, status green
        assert np.abs(remap(c(keep)) - c(keep)).max() < 0.02, keep
    print("sa_hue_remap_lut self-check: ok (#052927 ->", hx(teal) + "; white, grey, red, amber, status green unchanged)")


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "--test": _test()
    elif a[0] == "--lut": print(write_lut(a[1]))
    elif a[0] == "--png": png(a[1], a[2])
    elif a[0] == "--video": video(a[1], a[2], a[3] if len(a) > 3 else write_lut("/tmp/teal2navy.cube"))
