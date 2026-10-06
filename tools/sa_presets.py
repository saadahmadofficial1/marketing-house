#!/usr/bin/env python3
"""sa_presets — turn Saad's real Lightroom edits into scene presets he can click.

Reads what he actually did (via sa_lrread), groups it by scene, and writes Lightroom /
Camera Raw presets. Run it again after every unit he edits and the numbers get better -
that is the whole point, it learns from him rather than guessing.

    sa_presets.py --shoot "~/Downloads/Apartment Shoot"             # build and install
    sa_presets.py --shoot "<folder>" --dry                          # show, write nothing
    sa_presets.py --shoot "<folder>" --out "~/Downloads/Presets"    # somewhere else

Lightroom CC never reads XMP sidecars, but it does import presets - that is why this
exists rather than writing develop settings onto the files.

Install: Lightroom CC -> Edit -> Presets -> ... -> Import Presets.
Photoshop's Camera Raw picks them up on its own from the Settings folder.
"""
import argparse, glob, hashlib, json, os, re, statistics as st, subprocess, sys, collections

HERE = os.path.dirname(os.path.abspath(__file__))
ACR = os.path.expanduser("~/Library/Application Support/Adobe/CameraRaw/Settings/Property")
KEYS = ("Temperature", "Tint", "Exposure2012", "Contrast2012",
        "Highlights2012", "Shadows2012", "Whites2012")

# Sliders he never varies. Read off his own edits, not invented.
BASE = {"Texture": "0", "Clarity2012": "+8", "Dehaze": "+15", "Vibrance": "+15",
        "Saturation": "+3", "Blacks2012": "+2", "Sharpness": "0",
        "LuminanceSmoothing": "0", "ColorNoiseReduction": "0"}

AGAINST_FILE = "against-the-window.txt"   # lives in the shoot folder, Saad edits it

SCENES = {
    "01a Room - away from window":   lambda r: r in ("living-room", "bedroom", "bedroom-1",
                                                     "bedroom-2", "bedroom-wardrobe"),
    "01b Room - AGAINST the window": lambda r: r in ("view",),
    "02 Kitchen":                    lambda r: "kitchen" in r,
    "03 Washroom":                   lambda r: "bath" in r or "wc" in r or "shower" in r,
    "04 Entrance - dark corridor":   lambda r: r in ("door-plate", "entrance-hall",
                                                     "inner-corridor", "building-corridor"),
}
def against(shoot):
    """The frames shot into the glass. A plain list Saad keeps, because this is the one
    call no measurement makes: bright-pixel share and largest white blob both overlap,
    and the room label does not carry it either (his own window shots are labelled
    living-room and bedroom). Starts empty; Saad adds frames as he goes."""
    p = os.path.join(shoot, AGAINST_FILE)
    if not os.path.exists(p):
        open(p, "w").write(
            "# Frames shot INTO the window - one DSC number per line.\n"
            "# These take preset 01b instead of 01a. Add to this list as you go;\n"
            "# nothing else can work it out, the glass can sit anywhere in frame.\n")
    return {l.strip() for l in open(p) if l.strip() and not l.startswith("#")}


# ponytail: 01a vs 01b cannot be detected from the pixels. Bright-pixel share and largest
# white blob both overlap - a wardrobe with a window off to one side scores the same as a
# bedroom shot into the glass. Saad assigns those two by eye; the split still earns its
# place because the two treatments differ a lot (contrast -68 vs -39, shadows +71 vs +30).

TPL = '''<x:xmpmeta xmlns:x="adobe:ns:meta/" x:xmptk="sa_presets">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about=""
    xmlns:crs="http://ns.adobe.com/camera-raw-settings/1.0/"
    crs:PresetType="Normal" crs:Cluster="" crs:UUID="{uuid}"
    crs:SupportsAmount="False" crs:SupportsColor="True" crs:SupportsMonochrome="True"
    crs:SupportsHighDynamicRange="True" crs:SupportsNormalDynamicRange="True"
    crs:SupportsSceneReferred="True" crs:SupportsOutputReferred="True"
    crs:CameraModelRestriction="" crs:Version="15.0" crs:ProcessVersion="11.0"
    crs:WhiteBalance="Custom"
{fields}
   <crs:Name><rdf:Alt><rdf:li xml:lang="x-default">{name}</rdf:li></rdf:Alt></crs:Name>
   <crs:ShortName><rdf:Alt><rdf:li xml:lang="x-default">{name}</rdf:li></rdf:Alt></crs:ShortName>
   <crs:Group><rdf:Alt><rdf:li xml:lang="x-default">Property</rdf:li></rdf:Alt></crs:Group>
  </rdf:Description>
 </rdf:RDF>
</x:xmpmeta>
'''


def read_edits(shoot):
    """Delegate to sa_lrread so there is one reader, not two."""
    out = os.path.join("/tmp", "sa_presets_edits.json")
    subprocess.run([sys.executable, os.path.join(HERE, "sa_lrread.py"),
                    "--shoot", shoot, "--json", out],
                   check=True, capture_output=True)
    return json.load(open(out))


def drop_synced(recs):
    """A setting repeated byte-for-byte across frames is one look synced, not a per-scene
    judgement. Counting it once stops a synced default from drowning the real edits -
    exactly the mistake that produced a bogus 'washroom recipe' first time round."""
    seen = collections.Counter(tuple(x.get(k) for k in KEYS) for x in recs)
    return [x for x in recs if seen[tuple(x.get(k) for k in KEYS)] == 1]


def group(recs, win=frozenset()):
    g = collections.defaultdict(list)
    for x in recs:
        if x.get("frame") in win:
            g["01b Room - AGAINST the window"].append(x); continue
        for name, match in SCENES.items():
            if match(x.get("room", "")):
                g[name].append(x); break
    return g


def medians(rows):
    out = {}
    for k in KEYS:
        v = [float(r[k]) for r in rows if r.get(k)]
        if v: out[k] = st.median(v)
    return out


def write(name, med, dirs):
    sgn = lambda v: f"{int(round(v)):+d}"
    f = {"Temperature": str(int(med["Temperature"])), "Tint": sgn(med["Tint"]),
         "Exposure2012": f'{med["Exposure2012"]:+.2f}',
         "Contrast2012": sgn(med["Contrast2012"]),
         "Highlights2012": sgn(med["Highlights2012"]),
         "Shadows2012": sgn(med["Shadows2012"]),
         "Whites2012": sgn(med["Whites2012"])}
    f.update(BASE)
    body = "\n".join(f'    crs:{k}="{v}"' for k, v in f.items())
    xml = TPL.format(uuid=hashlib.md5(name.encode()).hexdigest().upper(),
                     fields=body, name=name)
    for d in dirs:
        os.makedirs(d, exist_ok=True)
        open(os.path.join(d, name.replace("/", "-") + ".xmp"), "w").write(xml)
    return f


def assignments(shoot, win=frozenset()):
    """Which numbered frame in each SELECTED folder takes which preset."""
    out = {}
    for f in sorted(glob.glob(os.path.join(shoot, "*", "SELECTED", "*.ARW"))):
        m = re.match(r"^.+?_(\d{2})_(.+)_DSC\d+\.ARW$", os.path.basename(f))
        if not m: continue
        unit = f.split(os.sep)[-3]
        dsc = re.search(r"(DSC\d+)\.ARW$", f).group(1)
        if dsc in win:
            out.setdefault(unit, {}).setdefault("01b Room - AGAINST the window", []).append(m.group(1))
            continue
        for name, match in SCENES.items():
            if match(m.group(2)):
                out.setdefault(unit, {}).setdefault(name, []).append(m.group(1)); break
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shoot", required=True)
    ap.add_argument("--out", default="~/Downloads/Lightroom Presets")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    shoot = os.path.expanduser(a.shoot)
    win = against(shoot)
    recs = read_edits(shoot)
    indiv = drop_synced(recs)
    print(f"{len(recs)} edited frames, {len(indiv)} genuinely individual "
          f"({len(recs)-len(indiv)} were one look synced across frames)\n")
    g = group(indiv, win)
    dirs = [] if a.dry else [os.path.expanduser(a.out), ACR]
    print(f"{'preset':32}{'n':>3}{'Temp':>7}{'Tint':>6}{'Contr':>7}{'High':>6}{'Shad':>6}{'Whit':>6}")
    for name in SCENES:
        rows = g.get(name, [])
        if not rows:
            print(f"{name:32}{0:>3}   -- no edits yet, preset not written"); continue
        med = medians(rows)
        if len(med) < len(KEYS):
            print(f"{name:32}{len(rows):>3}   -- incomplete data, skipped"); continue
        f = write(name, med, dirs) if dirs else {k: str(round(v)) for k, v in med.items()}
        thin = "   <- thin, one sample" if len(rows) == 1 else ""
        print(f"{name:32}{len(rows):>3}{med['Temperature']:>7.0f}{med['Tint']:>6.0f}"
              f"{med['Contrast2012']:>7.0f}{med['Highlights2012']:>6.0f}"
              f"{med['Shadows2012']:>6.0f}{med['Whites2012']:>6.0f}{thin}")
    if not a.dry:
        print(f"\nwritten to {os.path.expanduser(a.out)}\nand to Camera Raw at {ACR}")
    print("\nwhich frame takes which preset:")
    print(f"  (01b comes from {os.path.join(shoot, AGAINST_FILE)} - {len(win)} frames listed)")
    for unit, m in sorted(assignments(shoot, win).items()):
        print(f"  {unit}")
        for name in SCENES:
            if m.get(name): print(f"    {name:32} {', '.join(m[name])}")


def demo():
    """assert-based self-check: grouping, synced-drop, medians."""
    r = lambda room, **kw: {"room": room, **{k: kw.get(k, "0") for k in KEYS}}
    recs = [r("kitchen", Contrast2012="-39"), r("kitchen", Contrast2012="-87"),
            r("ensuite-bath", Contrast2012="-27"), r("view", Contrast2012="-68"),
            r("living-room", Contrast2012="-40"), r("living-room", Contrast2012="-40"),
            r("door-plate", Contrast2012="-12")]
    kept = drop_synced(recs)
    assert len(kept) == 5, kept                      # the two identical living-rooms go
    g = group(kept)
    assert len(g["02 Kitchen"]) == 2
    assert len(g["03 Washroom"]) == 1
    assert len(g["01b Room - AGAINST the window"]) == 1
    assert "01a Room - away from window" not in g    # both were the synced pair
    # a frame on the against-the-window list overrides its room label
    k2 = [dict(x, frame="DSC00928") if x["room"] == "kitchen" else x for x in kept]
    g2 = group(k2, {"DSC00928"})
    assert len(g2["01b Room - AGAINST the window"]) >= 1, g2
    assert medians(g["02 Kitchen"])["Contrast2012"] == -63
    assert all(SCENES["03 Washroom"](x) for x in ("guest-bathroom", "ensuite-bath", "ensuite-shower"))
    assert SCENES["02 Kitchen"]("kitchen-oven") and not SCENES["02 Kitchen"]("bedroom")
    print("sa_presets demo ok")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "demo": demo()
    else: main()
