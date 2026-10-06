"""Give a module's captions (and its sign-off caption) the look Saad set by hand on one
reference module.

    sa_capcut_caption_style.py "<target CapCut project>" --from "<reference CapCut project>"
    sa_capcut_caption_style.py --test

Requirement (24 Sep): every module's captions were to take the style and position Saad had
set by hand on the reference module. On his finished
reference every caption sits higher (y -0.677), is bigger (size 8), Poppins Medium, with a softer shadow
(material smoothing 0.45, shadow diffuse 0.025, alpha 0.55). sa_capcut_captions writes one value
for both smoothing and diffuse, so the look is copied from his own caption instead of re-typed.
Only style + position change; every caption keeps its words and timing. Refuses while CapCut
is open; backs up; writes the same data to every draft copy.
"""
import json, os, pathlib, shutil, subprocess, sys, time

CAP = pathlib.Path(os.path.expanduser("~/Movies/CapCut/User Data/Projects/com.lveditor.draft"))
BAK = pathlib.Path(os.path.expanduser(os.environ.get("SA_CAPCUT_BACKUP", "~/Movies/CapCut/_backup_capcut")))
KEYS = ("shadow_alpha", "shadow_smoothing", "font_size", "font_path", "shadow_color",
        "shadow_distance", "text_size", "border_width", "line_spacing")


def look(src):
    """His caption: (clip, material style fields, content style) from the source project."""
    d = json.load(open(CAP / src / "draft_info.json"))
    t = next(t for t in d["tracks"] if t.get("name") == "Captions")
    s = t["segments"][0]
    m = next(m for m in d["materials"]["texts"] if m["id"] == s["material_id"])
    return s["clip"], {k: m[k] for k in KEYS if k in m}, json.loads(m["content"])["styles"][0]


def restyle(d, clip, fields, style):
    M = {m["id"]: m for m in d["materials"].get("texts", [])}
    n = 0
    for t in d["tracks"]:
        if t.get("name") not in ("Captions", "Sign-off"):
            continue
        for s in t["segments"]:
            s["clip"]["transform"]["y"] = clip["transform"]["y"]
            s["clip"]["scale"] = dict(clip["scale"])
            m = M[s["material_id"]]
            m.update(fields)
            c = json.loads(m["content"])
            for st in c["styles"]:
                st["size"], st["font"] = style["size"], dict(style["font"])
                st["shadows"] = json.loads(json.dumps(style["shadows"]))
            m["content"] = json.dumps(c, ensure_ascii=False)
            n += 1
    return n


def main(target, src=None):
    if not src:
        raise SystemExit('name the reference project: --from "<reference CapCut project>"')
    if subprocess.run(["pgrep", "-x", "CapCut"], capture_output=True).returncode == 0:
        raise SystemExit("CapCut is open - close it first")
    clip, fields, style = look(src)
    P = CAP / target
    copies = [P / "draft_info.json"] + sorted(P.glob("Timelines/*/draft_info.json"))
    shutil.copytree(P, BAK / f"{target}_before_captions_{time.strftime('%H%M%S')}")
    d = json.load(open(copies[-1]))
    n = restyle(d, clip, fields, style)
    blob = json.dumps(d, ensure_ascii=False)
    for f in copies:
        f.write_text(blob)
    print(f"{n} captions in the {src} look (y {clip['transform']['y']:.4f}, size {style['size']}, "
          f"{os.path.basename(style['font']['path'])})")


def _test():
    d = {"materials": {"texts": [{"id": "m", "font_size": 5, "content": json.dumps(
        {"text": "Hi", "styles": [{"range": [0, 2], "size": 5, "font": {"path": "R"}, "shadows": []}]})}]},
         "tracks": [{"name": "Captions", "segments": [{"material_id": "m",
                     "clip": {"transform": {"x": 0, "y": -0.95}, "scale": {"x": 1, "y": 1}}}]}]}
    n = restyle(d, {"transform": {"y": -0.677}, "scale": {"x": 1.375, "y": 1.375}}, {"font_size": 8},
                {"size": 8, "font": {"path": "M"}, "shadows": [{"alpha": .55}]})
    c = json.loads(d["materials"]["texts"][0]["content"])
    assert n == 1 and c["text"] == "Hi" and c["styles"][0]["size"] == 8 and c["styles"][0]["range"] == [0, 2]
    assert d["tracks"][0]["segments"][0]["clip"]["transform"] == {"x": 0, "y": -0.677}
    print("caption_style self-check: ok")


if __name__ == "__main__":
    if sys.argv[1] == "--test":
        _test()
    else:
        main(sys.argv[1], *(sys.argv[sys.argv.index("--from") + 1:][:1] if "--from" in sys.argv else []))
