#!/usr/bin/env python3
"""Photo-library routine: inventory -> de-duplicate -> quality-flag -> upscale only what needs it
-> write Lightroom grade sidecars -> contact-sheet dashboard.

  sa_photolib.py scan   <library>                    # what have I got? (no changes)
  sa_photolib.py build  <library> <out> [--upscale]   # produce a graded, deduped delivery
  sa_photolib.py sheet  <folder> <out.jpg>           # numbered contact sheet of a folder

WHY THIS EXISTS (Aug 2026): a "photo enhancement" pass run through generative image
models re-draws at ~1536x1024, so delivered files can come back SMALLER than their 24 MP
originals. Generative enhance is NOT upscaling. This routine only ever enlarges
frames that are genuinely low-resolution, and does it locally with Real-ESRGAN.

Grade: writes a .xmp sidecar next to each image so Lightroom applies the approved look on
import. Indoor vs outdoor is chosen per image (sky in the top third + ISO), because using one
preset across both is a common grading mistake.
"""
import os, sys, re, json, shutil, subprocess, collections
from PIL import Image, ImageFilter, ExifTags
import numpy as np

HERE     = os.path.dirname(os.path.abspath(__file__))
PRESETS  = os.path.join(HERE, "presets")
ESRGAN   = os.path.join(HERE, "external", "realesrgan", "realesrgan-ncnn-vulkan")
MODELS   = os.path.join(HERE, "external", "realesrgan", "models")
IMG_EXT  = (".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp")
EXIF_T   = {v: k for k, v in ExifTags.TAGS.items()}

LOWRES_MP   = 3.0    # below this, a frame is a genuine upscale candidate
NEAR_DUP    = 6      # dHash hamming distance treated as "same scene"
SOFT, BLOWN, DARK = 600, 6.0, 70    # sharpness var, % clipped highlights, mean luma

# ── inventory ────────────────────────────────────────────────────────────────
def _dhash(gray):
    a = np.asarray(gray, dtype=np.int16)
    return "".join("1" if x else "0" for x in (a[:, 1:] > a[:, :-1]).flatten())

def profile(path):
    """dims, sharpness, exposure, perceptual hash, EXIF — header-cheap, no full decode."""
    r = {"path": path, "bytes": os.path.getsize(path)}
    try:
        im = Image.open(path)
        r["w"], r["h"] = im.size
        r["mp"] = round(im.size[0] * im.size[1] / 1e6, 1)
        try:
            ex = im.getexif(); ifd = ex.get_ifd(0x8769)
            for tag in ("DateTimeOriginal", "Model", "LensModel", "ISOSpeedRatings", "FNumber"):
                t = EXIF_T.get(tag)
                if t and (ifd.get(t) is not None or ex.get(t) is not None):
                    r[tag] = str(ifd.get(t) if ifd.get(t) is not None else ex.get(t))
        except Exception:
            pass
        im.draft("L", (400, 400))                     # JPEG DCT downscale, very fast
        g = im.convert("L"); g.thumbnail((256, 256), Image.BILINEAR)
        a = np.asarray(g, dtype=np.float32)
        r["luma"]     = round(float(a.mean()), 1)
        r["clip_hi"]  = round(float((a > 250).mean() * 100), 2)
        r["clip_lo"]  = round(float((a < 5).mean() * 100), 2)
        r["sharp"]    = round(float(np.abs(np.asarray(
            g.filter(ImageFilter.FIND_EDGES), dtype=np.float32)).var()), 1)
        h = g.copy(); h.thumbnail((9, 8), Image.BILINEAR); h = h.resize((9, 8), Image.BILINEAR)
        r["dhash"] = _dhash(h)
    except Exception as e:
        r["error"] = str(e)[:120]
    return r

def walk(root):
    out = []
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if not d.startswith(".")]
        out += [os.path.join(dp, f) for f in fn
                if f.lower().endswith(IMG_EXT) and not f.startswith(".")]
    return sorted(out)

# ── grouping and scoring ─────────────────────────────────────────────────────
def _ham(a, b): return sum(x != y for x, y in zip(a, b))

def dedupe(items):
    """Cluster near-identical frames; return one best-of per cluster, plus the rejects."""
    clusters = []
    for x in sorted(items, key=lambda i: -i.get("mp", 0)):
        for c in clusters:
            if _ham(x["dhash"], c[0]["dhash"]) <= NEAR_DUP:
                c.append(x); break
        else:
            clusters.append([x])
    keep = [max(c, key=score) for c in clusters]
    kept = {id(k) for k in keep}
    return sorted(keep, key=score, reverse=True), [i for i in items if id(i) not in kept]

def score(x):
    s  = x.get("sharp", 0) / 1000 + x.get("mp", 0) / 8
    s -= max(0, x.get("clip_hi", 0) - 1) * 0.4
    s -= max(0, x.get("clip_lo", 0) - 3) * 0.15
    s -= abs(x.get("luma", 140) - 140) / 90
    return s

def flags(x):
    f = []
    if x.get("mp", 99) < LOWRES_MP:   f.append("lowres")
    if x.get("sharp", 999) < SOFT:    f.append("soft")
    if x.get("clip_hi", 0) > BLOWN:   f.append("blown")
    if x.get("luma", 140) < DARK:     f.append("dark")
    return f

# ── grade ────────────────────────────────────────────────────────────────────
_DROP = {"PresetType","Cluster","UUID","ShowInPresets","ShowInQuickActions","CameraModelRestriction",
         "Copyright","ContactInfo","Name","SortName","Group","Description","SupportsAmount",
         "SupportsAmount2","SupportsColor","SupportsMonochrome","SupportsHighDynamicRange",
         "SupportsNormalDynamicRange","SupportsSceneReferred","SupportsOutputReferred",
         "RequiresRGBTables","HasSettings"}

def load_preset(name):
    t = open(os.path.join(PRESETS, name), encoding="utf-8").read()
    return dict(re.findall(r'crs:([A-Za-z0-9_]+)="([^"]*)"', t))

def write_sidecar(dest_img, vals):
    at = "\n".join(f'   crs:{k}="{v}"' for k, v in vals.items() if k not in _DROP)
    xml = ('<x:xmpmeta xmlns:x="adobe:ns:meta/" x:xmptk="sa_photolib">\n'
           ' <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">\n'
           '  <rdf:Description rdf:about=""\n'
           '    xmlns:crs="http://ns.adobe.com/camera-raw-settings/1.0/"\n'
           f'   crs:RawFileName="{os.path.basename(dest_img)}"\n{at}>\n'
           '  </rdf:Description>\n </rdf:RDF>\n</x:xmpmeta>\n')
    open(os.path.splitext(dest_img)[0] + ".xmp", "w").write(xml)

def is_outdoor(path, iso=None):
    """Sky in the top third, or low ISO with some sky. Indoor != outdoor is the grade that
    gets fumbled most often, so it is decided per image rather than per folder."""
    try:
        im = Image.open(path); im.draft("RGB", (200, 200)); im = im.convert("RGB")
        im.thumbnail((160, 160))
        a = np.asarray(im, dtype=np.float32)[: max(1, im.size[1] // 3)]
        r, g, b = a[..., 0], a[..., 1], a[..., 2]
        frac = float((((b > r + 8) & (b > 110)) | ((r > 235) & (g > 235) & (b > 235))).mean())
        iso = int(iso) if iso and str(iso).isdigit() else None
        return frac > 0.30 or (frac > 0.15 and (iso is None or iso <= 400))
    except Exception:
        return False

# ── upscale (local, free, non-destructive) ───────────────────────────────────
def upscale(src, dest_jpg, scale=4):
    """Real-ESRGAN on-device. Only ever called on genuinely low-res frames — never as a
    substitute for a proper capture, and never on a file that is already high resolution."""
    tmp = dest_jpg + ".tmp.png"
    subprocess.run([ESRGAN, "-i", src, "-o", tmp, "-s", str(scale),
                    "-n", "realesrgan-x4plus", "-m", MODELS], capture_output=True, text=True)
    if not os.path.exists(tmp):
        return False
    Image.open(tmp).convert("RGB").save(dest_jpg, quality=92, subsampling=0)
    os.remove(tmp)
    return True

# ── contact sheet ────────────────────────────────────────────────────────────
def sheet(paths, out, cols=6, tw=300, th=200):
    from PIL import ImageDraw
    import math
    rows = math.ceil(len(paths) / cols)
    s = Image.new("RGB", (cols * tw, rows * (th + 18)), (20, 20, 20))
    d = ImageDraw.Draw(s)
    for i, p in enumerate(paths):
        try:
            im = Image.open(p); im.draft("RGB", (tw * 2, th * 2)); im = im.convert("RGB")
            im.thumbnail((tw - 6, th - 6))
            x, y = (i % cols) * tw, (i // cols) * (th + 18)
            s.paste(im, (x + (tw - im.width) // 2, y + (th - im.height) // 2))
            d.text((x + 5, y + th + 3), f"{i}  {os.path.basename(p)[:26]}", fill=(200, 200, 200))
        except Exception:
            pass
    s.save(out, quality=82)
    return out

# ── commands ─────────────────────────────────────────────────────────────────
def cmd_scan(root):
    files = walk(root)
    print(f"{len(files)} images under {root}\n")
    by = collections.defaultdict(list)
    for f in files:
        by[os.path.relpath(os.path.dirname(f), root)].append(profile(f))
    print(f"{'folder':<44}{'n':>5}{'medMP':>8}{'minMP':>8}{'lowres':>8}{'dupes':>7}")
    for k in sorted(by):
        v = [x for x in by[k] if "mp" in x]
        if not v: continue
        keep, cut = dedupe(v)
        mps = sorted(x["mp"] for x in v)
        low = sum(1 for x in v if x["mp"] < LOWRES_MP)
        print(f"{k[:44]:<44}{len(v):>5}{mps[len(mps)//2]:>8.1f}{mps[0]:>8.1f}{low:>8}{len(cut):>7}")
    return by

def cmd_build(root, out, do_upscale=False):
    # your own Lightroom presets, exported as .xmp into Tools/presets/
    indoor, outdoor = load_preset("INDOOR.xmp"), load_preset("OUTDOOR.xmp")
    files = walk(root)
    by = collections.defaultdict(list)
    for f in files:
        by[os.path.relpath(os.path.dirname(f), root)].append(profile(f))
    total = up = 0
    for folder, items in sorted(by.items()):
        items = [x for x in items if "mp" in x]
        if not items: continue
        keep, _cut = dedupe(items)
        dest = os.path.join(out, folder); os.makedirs(dest, exist_ok=True)
        rank = 0
        for x in keep:
            bad = flags(x)
            sub = os.path.join(dest, "_REVIEW") if (bad and "lowres" not in bad) else dest
            os.makedirs(sub, exist_ok=True)
            stem = os.path.splitext(os.path.basename(x["path"]))[0].replace(" ", "_")
            if "lowres" in bad and do_upscale:
                rank += 1
                d = os.path.join(sub, f"{rank:02d}_{stem}_4x.jpg")
                if upscale(x["path"], d): up += 1
                else: shutil.copy2(x["path"], d)
            else:
                if sub == dest: rank += 1
                name = (f"{rank:02d}_{stem}" if sub == dest else stem) + os.path.splitext(x["path"])[1]
                d = os.path.join(sub, name)
                shutil.copy2(x["path"], d)
            write_sidecar(d, outdoor if is_outdoor(x["path"], x.get("ISOSpeedRatings")) else indoor)
            total += 1
        print(f"  {folder or '.'}: {rank} ready, {len(keep)-rank} review")
    print(f"\n{total} files written to {out}" + (f" ({up} upscaled)" if do_upscale else ""))

def main():
    if len(sys.argv) < 3: sys.exit(__doc__)
    c = sys.argv[1]
    if c == "scan":
        cmd_scan(os.path.expanduser(sys.argv[2]))
    elif c == "build":
        cmd_build(os.path.expanduser(sys.argv[2]), os.path.expanduser(sys.argv[3]),
                  "--upscale" in sys.argv)
    elif c == "sheet":
        print(sheet(walk(os.path.expanduser(sys.argv[2])), os.path.expanduser(sys.argv[3])))
    else:
        sys.exit(__doc__)

if __name__ == "__main__":
    main()
