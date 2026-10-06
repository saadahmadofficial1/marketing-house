#!/usr/bin/env python3
"""sa_rawdev — technical Camera Raw develop for property RAWs, as XMP sidecars.

Measures each RAW and writes a Lightroom/Camera Raw sidecar next to it: white balance,
exposure, highlight recovery, shadow lift, noise reduction, sharpening, lens correction.
Lightroom picks the settings up on import, non-destructively, at full resolution.

    sa_rawdev.py "<folder>" --recurse            # write sidecars
    sa_rawdev.py "<folder>" --recurse --dry      # measure and print, write nothing
    sa_rawdev.py "<folder>" --preview /tmp/p     # approximate before/after JPEGs

It does TECHNICAL correction only. Vibrance, saturation, HSL, tone curve and colour
grading are deliberately left at zero - that is the grade, and the grade is Saad's.

ponytail: an XMP sidecar, not a rendered file. Lightroom is a far better raw processor
than anything written here, and the sidecar keeps every slider live for him to move.
"""
import argparse, os, sys, glob, math
import numpy as np

TARGET_LO, TARGET_HI = 0.34, 0.60     # median luma left alone inside this band
TARGET = 0.46


def measure(path):
    """Half-size camera-WB render, measured in sRGB. Half size is plenty for statistics
    and ~4x faster than full."""
    import rawpy
    with rawpy.imread(path) as r:
        rgb = r.postprocess(use_camera_wb=True, no_auto_bright=True,
                            output_bps=8, half_size=True)
        iso = 0
        try: iso = int(r.camera_whitebalance and 0) or 0
        except Exception: pass
    a = rgb.astype(np.float32) / 255.0
    lum = a[..., 0]*0.2126 + a[..., 1]*0.7152 + a[..., 2]*0.0722
    m = {}
    m["p50"] = float(np.median(lum))
    m["clip"] = float((a.max(axis=2) >= 0.988).mean() * 100)      # % blown
    m["crush"] = float((lum <= 0.02).mean() * 100)                # % blocked
    m["p01"] = float(np.percentile(lum, 1))
    # colour cast measured on midtones only, so a beige wall doesn't read as a cast
    mid = (lum > 0.25) & (lum < 0.75)
    if mid.sum() > 1000:
        mr, mg, mb = [float(a[..., i][mid].mean()) for i in range(3)]
    else:
        mr, mg, mb = [float(a[..., i].mean()) for i in range(3)]
    m["rgb"] = (mr, mg, mb)
    return m


def exif_iso(jpg):
    from PIL import Image
    try:
        return int(Image.open(jpg).getexif().get_ifd(0x8769).get(0x8827) or 0)
    except Exception:
        return 0



def find_iso(arw, root):
    """The JPG twin may sit a folder up (a RAW moved into SELECTED/), so match on the
    DSC number anywhere under the shoot root. Falls back to a mid value, and says so."""
    import re
    mm = re.search(r"(DSC\d{5})\.ARW$", arw, re.I)
    if mm:
        for c in glob.glob(os.path.join(root, "**", mm.group(1) + ".JPG"), recursive=True):
            v = exif_iso(c)
            if v: return v
        up = os.path.dirname(os.path.dirname(arw))
        for c in glob.glob(os.path.join(up, "**", mm.group(1) + ".JPG"), recursive=True):
            v = exif_iso(c)
            if v: return v
    return 0


def settings(m, iso):
    """Map measurements to Camera Raw sliders. Everything clamped - a develop that
    can't go far can't ruin a frame, and Saad still has every slider."""
    s = {}
    p50 = m["p50"]
    if p50 < TARGET_LO or p50 > TARGET_HI:
        ev = math.log2(TARGET / max(p50, 0.02))
    else:
        ev = 0.0
    # never add exposure to a frame that is already clipping - it only buries more
    # of the window. Lift the interior with Shadows instead.
    if m["clip"] > 2.0:
        ev = min(ev, 0.0)
    s["Exposure2012"] = round(max(-0.90, min(1.60, ev)), 2)
    if m["clip"] > 2.0 and m["p50"] < TARGET_LO:
        s["_shadow_bias"] = True

    s["Highlights2012"] = int(-max(0, min(100, m["clip"] * 14)))
    s["Whites2012"]     = int(-max(0, min(55,  m["clip"] * 7)))
    sh = max(0, min(70, m["crush"] * 5))
    if s.pop("_shadow_bias", False):          # dark interior behind a blown window
        sh = max(sh, min(70, (TARGET_LO - m["p50"]) * 220))
    s["Shadows2012"] = int(sh)
    # only set a black point when the frame is genuinely hazy/lifted
    s["Blacks2012"]     = int(-min(18, max(0, (m["p01"] - 0.06) * 260)))

    # NO white balance. Removed 17 Sep 2026 after it turned 87 frames of one shoot green.
    # The old heuristic read a beige wall as a red cast and cooled the frame by up to
    # -14, which on warm LED interiors lands squarely in green. Interior white balance
    # under mixed daylight and LED is a judgement, not a measurement - it belongs with
    # the grade. Camera WB as shot is the honest starting point, and one eyedropper
    # click on a white wall beats any guess made here.

    # technical crispness only - not an HDR clarity punch
    s["Texture"]   = 12
    s["Clarity2012"] = 5

    # Saad sets Sharpness to 0 on every frame and gets crispness from Clarity and
    # Dehaze instead (read from his own Lightroom edits, 17 Sep). Don't argue with his taste.
    s["Sharpness"] = 0
    # Noise follows the EFFECTIVE exposure, not the ISO dial. An ISO 100 frame pushed
    # +1.6 EV with Shadows at 70 is as noisy as ISO ~400 - dim interior corridors are exactly
    # this, shot dark in manual and rescued in post. Judging by base ISO under-treats them.
    push = (2 ** max(0.0, s["Exposure2012"])) * (1 + 0.6 * s["Shadows2012"] / 100.0)
    eff = (iso or 1600) * push
    s["LuminanceSmoothing"] = (10 if eff <= 800 else 20 if eff <= 1600 else
                               28 if eff <= 2500 else 35 if eff <= 4000 else
                               42 if eff <= 12000 else 50)
    s["LuminanceNoiseReductionDetail"] = 50
    s["ColorNoiseReduction"] = 30
    s["ColorNoiseReductionDetail"] = 50
    return s


XMP = """<x:xmpmeta xmlns:x="adobe:ns:meta/" x:xmptk="sa_rawdev">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about=""
    xmlns:crs="http://ns.adobe.com/camera-raw-settings/1.0/"
    crs:Version="15.0"
    crs:ProcessVersion="11.0"
    crs:HasSettings="True"
{fields}
    crs:Vibrance="0"
    crs:Saturation="0"
    crs:ParametricShadows="0"
    crs:ParametricDarks="0"
    crs:ParametricLights="0"
    crs:ParametricHighlights="0"
    crs:AutoLateralCA="1"
    crs:LensProfileEnable="1"
    crs:LensProfileSetup="Auto"
    crs:PerspectiveUpright="0"
    crs:ToneCurveName2012="Linear"
    crs:ConvertToGrayscale="False"/>
 </rdf:RDF>
</x:xmpmeta>
"""


def write_xmp(arw, s):
    fields = "\n".join(f'    crs:{k}="{v}"' for k, v in s.items())
    dst = os.path.splitext(arw)[0] + ".xmp"
    with open(dst, "w") as f:
        f.write(XMP.format(fields=fields))
    return dst


def approx_preview(arw, s, out_dir):
    """Rough visual of where the settings push the frame. NOT a Lightroom match -
    Lightroom's raw engine is better than this. It is here to catch a develop that
    goes the wrong way, which is exactly the mistake that made this tool necessary."""
    import rawpy, cv2
    with rawpy.imread(arw) as r:
        rgb = r.postprocess(use_camera_wb=True, no_auto_bright=True,
                            output_bps=8, half_size=True)
    a = rgb.astype(np.float32) / 255.0
    before = a.copy()
    a = np.clip(a * (2 ** s["Exposure2012"]), 0, 1)
    lum = a[..., 0]*0.2126 + a[..., 1]*0.7152 + a[..., 2]*0.0722
    if s["Highlights2012"]:
        w = np.clip((lum - 0.65) / 0.35, 0, 1)[..., None]
        a *= (1 + (s["Highlights2012"] / 100.0) * 0.55 * w)
    if s["Shadows2012"]:
        w = np.clip((0.35 - lum) / 0.35, 0, 1)[..., None]
        a *= (1 + (s["Shadows2012"] / 100.0) * 0.85 * w)
    if s["Blacks2012"]:
        a = np.clip(a + (s["Blacks2012"] / 100.0) * 0.10, 0, 1)
    temp = s.get("IncrementalTemperature", 0)       # white balance is no longer set; kept at 0
    a[..., 0] *= (1 - temp / 600.0)
    a[..., 2] *= (1 + temp / 600.0)
    a = np.clip(a, 0, 1)
    os.makedirs(out_dir, exist_ok=True)
    n = os.path.splitext(os.path.basename(arw))[0]
    both = np.hstack([before, a])
    cv2.imwrite(os.path.join(out_dir, f"{n}_approx.jpg"),
                cv2.cvtColor((both * 255).astype(np.uint8), cv2.COLOR_RGB2BGR),
                [cv2.IMWRITE_JPEG_QUALITY, 90])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--recurse", action="store_true")
    ap.add_argument("--dry", action="store_true", help="measure and print, write nothing")
    ap.add_argument("--preview", help="directory for approximate before/after JPEGs")
    a = ap.parse_args()
    root = os.path.expanduser(a.folder)
    pat = "**/*.ARW" if a.recurse else "*.ARW"
    files = sorted(glob.glob(os.path.join(root, pat), recursive=a.recurse))
    if not files:
        sys.exit("no ARW files found")
    print(f"{'file':44}{'ev':>6}{'hi':>6}{'sh':>5}{'bl':>5}{'temp':>6}{'tint':>6}{'nr':>5}{'ISO':>7}")
    for f in files:
        m = measure(f)
        iso = find_iso(f, root)
        s = settings(m, iso)
        print(f"{os.path.basename(f)[:43]:44}{s['Exposure2012']:>6.2f}"
              f"{s['Highlights2012']:>6}{s['Shadows2012']:>5}{s['Blacks2012']:>5}"
              f"{'-':>6}{'-':>6}"
              f"{s['LuminanceSmoothing']:>5}{iso:>7}")
        if not a.dry:
            write_xmp(f, s)
        if a.preview:
            approx_preview(f, s, a.preview)


def demo():
    """assert-based self-check on the settings mapping."""
    base = {"p50": 0.46, "clip": 0.0, "crush": 0.0, "p01": 0.05, "rgb": (0.5, 0.5, 0.5)}
    s = settings(base, 800)
    assert s["Exposure2012"] == 0 and s["Highlights2012"] == 0 and s["Shadows2012"] == 0
    dark = dict(base, p50=0.12, crush=9.0)
    sd = settings(dark, 4000)
    assert sd["Exposure2012"] > 0.9 and sd["Shadows2012"] > 0
    assert sd["LuminanceSmoothing"] >= 42               # ISO 4000 pushed hard -> more NR
    blown = dict(base, clip=6.0, p50=0.70)
    sb = settings(blown, 500)
    assert sb["Highlights2012"] <= -80 and sb["Exposure2012"] < 0
    assert settings(dict(base, p50=0.02), 100)["Exposure2012"] <= 1.60   # clamped
    # white balance is never touched, whatever the cast looks like
    warm = settings(dict(base, rgb=(0.60, 0.50, 0.42)), 800)
    assert "IncrementalTemperature" not in warm and "IncrementalTint" not in warm, warm
    # dark interior behind a blown window: lift with Shadows, never with Exposure
    bw = settings(dict(base, clip=5.0, p50=0.18, crush=0.0), 4000)
    assert bw["Exposure2012"] <= 0, bw
    assert bw["Shadows2012"] > 20, bw
    # NR tracks effective exposure. A pushed frame gets more than the same ISO left alone,
    # but a low-ISO frame pushed a little is still a low-noise frame - don't over-treat it.
    calm   = settings(dict(base, p50=0.46), 1600)
    pushed = settings(dict(base, p50=0.12, crush=8.0), 1600)
    assert pushed["LuminanceSmoothing"] > calm["LuminanceSmoothing"], (calm, pushed)
    assert settings(dict(base, p50=0.12, crush=8.0), 100)["LuminanceSmoothing"] <= 20
    print("sa_rawdev demo ok")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "demo": demo()
    else: main()
