#!/usr/bin/env python3
"""sa_lrread — read Saad's actual Lightroom CC edits back out of the catalogue.

Lightroom CC never writes XMP sidecars, so the only way to learn what he did is to
read its own store. This extracts the develop settings and masks per frame and joins
them to the original files by capture time.

    sa_lrread.py                          # every edited frame it can match
    sa_lrread.py --shoot "<folder>"       # only frames from this shoot
    sa_lrread.py --shoot "<f>" --json out.json

Where it lives:
  ~/Pictures/Lightroom Library.lrlibrary/<uuid>/Managed Catalog.mcat   (SQLite doc store)
    revs.content is msgpack; it carries captureDate and an xmpCameraRaw sha256
  ~/Pictures/Lightroom Library.lrlibrary/<uuid>/settings/<sha256>      (plain crs XMP)

ponytail: regex over the msgpack rather than decoding it properly. The two fields needed
are plain ASCII inside the blob, and a real decoder would be a lot of code to learn
nothing more. If Adobe changes the layout this breaks loudly, which is the right failure.
"""
import argparse, glob, json, os, re, sqlite3, shutil, sys, tempfile

LIB = os.path.expanduser("~/Pictures/Lightroom Library.lrlibrary")
SLIDERS = ["Temperature", "Tint", "Exposure2012", "Contrast2012", "Highlights2012",
           "Shadows2012", "Whites2012", "Blacks2012", "Texture", "Clarity2012",
           "Dehaze", "Vibrance", "Saturation", "Sharpness", "LuminanceSmoothing"]
LOCALS = ["LocalExposure2012", "LocalContrast2012", "LocalHighlights2012",
          "LocalShadows2012", "LocalWhites2012", "LocalBlacks2012",
          "LocalTemperature", "LocalTint", "LocalClarity2012", "LocalTexture",
          "LocalDehaze", "LocalSaturation"]


def catalogs():
    return sorted(glob.glob(os.path.join(LIB, "*", "Managed Catalog.mcat")))


def capture_to_sha(mcat):
    """Newest revision wins, so a re-edit replaces the earlier one."""
    tmp = os.path.join(tempfile.mkdtemp(), "cat.mcat")
    shutil.copy(mcat, tmp)
    for ext in ("-wal", "-shm"):
        if os.path.exists(mcat + ext):
            shutil.copy(mcat + ext, tmp + ext)
    con = sqlite3.connect(tmp); con.text_factory = bytes
    out = {}
    for _, b in con.execute("SELECT sequence,content FROM revs WHERE content IS NOT NULL"
                            " ORDER BY sequence"):
        s = bytes(b).decode("utf8", "ignore")
        if "xmpCameraRaw" not in s:
            continue
        cap = re.search(r"captureDate(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)", s)
        sha = re.search(r"xmpCameraRaw\D{0,4}sha256@([0-9a-f]{64})", s)
        if cap and sha:
            out[cap.group(1)] = sha.group(1)
    return out


def read_settings(sha, mcat):
    p = os.path.join(os.path.dirname(mcat), "settings", sha)
    if not os.path.exists(p):
        return None
    x = open(p, encoding="utf8", errors="ignore").read()
    g = lambda k: (re.search(f'crs:{k}="([+-]?[\\d.]+)"', x) or [None, None])[1]
    rec = {k: g(k) for k in SLIDERS}
    rec["WhiteBalance"] = (re.search(r'crs:WhiteBalance="([^"]+)"', x) or [None, None])[1]
    masks = []
    for blk in re.split(r"(?=crs:MaskName=)", x)[1:]:
        m = {"name": (re.search(r'crs:MaskName="([^"]+)"', blk) or [None, None])[1],
             "at": (re.search(r'crs:ReferencePoint="([^"]+)"', blk) or [None, None])[1]}
        for k in LOCALS:
            v = re.search(f'crs:{k}="([+-]?[\\d.]+)"', blk)
            if v and float(v.group(1)) != 0:
                m[k[5:]] = v.group(1)
        masks.append(m)
    if not masks and "Paint" in x:
        masks = [{"name": "Paint", "at": None}]
    rec["masks"] = masks
    return rec


def shoot_times(folder):
    from PIL import Image
    t = {}
    for f in glob.glob(os.path.join(folder, "**", "*.JPG"), recursive=True):
        try:
            d = Image.open(f).getexif().get_ifd(0x8769).get(0x9003)
        except Exception:
            continue
        if d:
            t[d.replace(":", "-", 2).replace(" ", "T")] = os.path.basename(f)[:-4]
    return t


def rooms(folder):
    r = {}
    for f in glob.glob(os.path.join(folder, "*", "SELECTED", "*.ARW")):
        n = re.search(r"(DSC\d+)\.ARW$", f)
        m = re.match(r"^.+?_\d{2}_(.+)_DSC\d+\.ARW$", os.path.basename(f))
        if n and m:
            r[n.group(1)] = m.group(1)
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shoot", help="shoot folder, to name frames and rooms")
    ap.add_argument("--json", help="write the full record here")
    a = ap.parse_args()
    cats = catalogs()
    if not cats:
        sys.exit(f"no Lightroom catalogue under {LIB}")
    t2n = shoot_times(a.shoot) if a.shoot else {}
    rm = rooms(a.shoot) if a.shoot else {}
    recs = []
    for mcat in cats:
        for cap, sha in capture_to_sha(mcat).items():
            name = t2n.get(cap)
            if a.shoot and not name:
                continue
            s = read_settings(sha, mcat)
            if not s:
                continue
            if all(v in (None, "0", "0.00", "+0.00") for k, v in s.items()
                   if k in ("Exposure2012", "Contrast2012", "Highlights2012")):
                continue                       # untouched, still at Lightroom defaults
            s["frame"] = name or cap
            s["room"] = rm.get(name, "?")
            recs.append(s)
    recs.sort(key=lambda r: r["frame"])
    print(f"{'frame':10}{'room':20}{'temp':>7}{'tint':>6}{'exp':>7}{'contr':>7}"
          f"{'high':>7}{'shad':>7}{'whit':>7}  masks")
    for r in recs:
        print(f"{r['frame'][:9]:10}{r['room'][:19]:20}"
              + "".join(f"{(r.get(k) or '-'):>7}" for k in
                        ("Temperature", "Tint", "Exposure2012", "Contrast2012",
                         "Highlights2012", "Shadows2012", "Whites2012"))
              + f"  {len(r['masks'])}")
    print(f"\n{len(recs)} edited frames")
    if a.json:
        json.dump(recs, open(a.json, "w"), indent=1)
        print("written:", a.json)


def demo():
    """assert-based self-check on the parsing, no catalogue needed."""
    x = ('crs:Temperature="5449" crs:Tint="+52" crs:Exposure2012="+0.72" '
         'crs:Sharpness="0" crs:MaskName="Object" crs:ReferencePoint="0.5 0.4" '
         'crs:LocalHighlights2012="-0.82" crs:LocalShadows2012="0" '
         'crs:LocalContrast2012="-0.90"')
    d = tempfile.mkdtemp(); os.makedirs(os.path.join(d, "settings"))
    open(os.path.join(d, "settings", "abc"), "w").write(x)
    r = read_settings("abc", os.path.join(d, "Managed Catalog.mcat"))
    assert r["Temperature"] == "5449" and r["Tint"] == "+52", r
    assert r["Sharpness"] == "0"
    assert len(r["masks"]) == 1 and r["masks"][0]["name"] == "Object", r["masks"]
    assert r["masks"][0]["Highlights2012"] == "-0.82"
    assert "Shadows2012" not in r["masks"][0], "zero local values must be dropped"
    assert read_settings("nope", os.path.join(d, "Managed Catalog.mcat")) is None
    print("sa_lrread demo ok")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "demo": demo()
    else: main()
