#!/usr/bin/env python3
"""sa_capcut_captions — put an SRT into a CapCut draft as editable text segments.

Saad wants a project he can open, check, tweak and export without leaving CapCut, so the
captions have to be real text layers he can retype — not burned pixels and not a sidecar
file he has to import.

The text style is cloned from a text material already in his own draft (Poppins Medium,
white, soft shadow), so new captions look identical to the ones he typed by hand.

  Tools/venv/bin/python3 Tools/sa_capcut_captions.py "Module 04 Approval" T04.srt
  Tools/venv/bin/python3 Tools/sa_capcut_captions.py --test

Additive and reversible: it only appends one text track, backs the draft up first, and
refuses to run while CapCut is open.
"""
import argparse
import copy
import glob
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import uuid

US = 1_000_000
CAPCUT = pathlib.Path("~/Movies/CapCut/User Data/Projects/com.lveditor.draft").expanduser()
def _donor():
    # The donor project has been renamed before — match its name as a prefix, don't
    # assume the exact name. Set CAPCUT_DONOR to your own approved template project.
    name = os.environ.get("CAPCUT_DONOR", "Donor Project")
    hits = [p.name for p in sorted(CAPCUT.glob(name + "*")) if (p / "Timelines").exists()]
    return hits[0] if hits else name


DONOR = _donor()                # borrow the text style he already approved
TRACK_NAME = "Captions"


def new_id():
    return str(uuid.uuid4()).upper()


def capcut_open():
    return subprocess.run(["pgrep", "-x", "CapCut"], capture_output=True).returncode == 0


def parse_srt(path):
    """-> [(start_seconds, end_seconds, text)]. Blank-line separated, 3+ lines a block."""
    raw = pathlib.Path(path).read_text(encoding="utf-8-sig").strip()
    out = []
    for block in re.split(r"\n\s*\n", raw):
        lines = [l for l in block.strip().splitlines() if l.strip()]
        if len(lines) < 2:
            continue
        stamp = next((l for l in lines if "-->" in l), None)
        if not stamp:
            continue
        a, b = [s.strip() for s in stamp.split("-->")]

        def secs(x):
            x = x.replace(",", ".")
            h, m, s = x.split(":")
            return int(h) * 3600 + int(m) * 60 + float(s)

        text = " ".join(lines[lines.index(stamp) + 1:]).strip()
        if text:
            out.append((secs(a), secs(b), text))
    return out


CAPCUT_FONTS = pathlib.Path(
    "~/Library/Containers/com.lemon.lvoverseas/Data/Library/Fonts").expanduser()
CAPTION_FONT = CAPCUT_FONTS / "Poppins-Regular.ttf"
TITLE_LIGHT = CAPCUT_FONTS / "Poppins-Light.ttf"
TITLE_FONT = CAPCUT_FONTS / "Poppins-Regular.ttf"

# Saad's exact numbers, 6 Aug. CapCut's position readout is normalised x1000 — verified
# against the text layers he placed by hand (his y -716 reads as transform -0.7163).
UI = 1000.0

CAPTION = dict(font_size=5.0, scale=0.75, x=0.0, y=-892 / UI,
               shadow_alpha=0.50, shadow_smoothing=0.15,
               shadow_distance=5.0, shadow_angle=-45.0)

TITLE_TOP = dict(font_size=18.0, scale=0.49, x=-747 / UI, y=0.0, font=TITLE_LIGHT,
                 shadow_alpha=0.55, shadow_smoothing=0.15,
                 shadow_distance=5.0, shadow_angle=-45.0)
TITLE_BOTTOM = dict(font_size=18.0, scale=0.49, x=-747 / UI, y=0.0, font=TITLE_FONT,
                    shadow_alpha=0.55, shadow_smoothing=0.15,
                    shadow_distance=5.0, shadow_angle=-45.0)


def styled(m, spec, font):
    """Stamp one text material with Saad's spec. Shadow values are his UI numbers /100."""
    m["font_path"] = str(font)
    m["font_size"] = spec["font_size"]
    m["has_shadow"] = True
    m["shadow_alpha"] = spec["shadow_alpha"]
    m["shadow_smoothing"] = spec["shadow_smoothing"]
    m["shadow_distance"] = spec["shadow_distance"]
    m["shadow_angle"] = spec["shadow_angle"]
    m["shadow_color"] = "#000000"
    m["line_max_width"] = 0.98        # captions are ONE LINE — never let CapCut wrap
    m["line_feed"] = 0
    content = json.loads(m["content"])
    for st in content.get("styles", []):
        st.setdefault("font", {})["path"] = str(font)
        st["size"] = spec["font_size"]
        for sh in st.get("shadows", []):
            sh["alpha"] = spec["shadow_alpha"]
            sh["distance"] = spec["shadow_distance"]
            sh["angle"] = spec["shadow_angle"]
            sh["diffuse"] = spec["shadow_smoothing"]
    m["content"] = json.dumps(content, ensure_ascii=False)
    return m


def placed(seg, spec):
    seg["clip"] = {"scale": {"x": spec["scale"], "y": spec["scale"]}, "rotation": 0.0,
                   "transform": {"x": spec["x"], "y": spec["y"]},
                   "flip": {"vertical": False, "horizontal": False}, "alpha": 1.0}
    return seg


def text_material(template, text):
    """Clone the approved style, swap only the words, and pin the weight.

    The donor carries several style RANGES (it styled different words differently).
    Widening each to cover the new string leaves N styles stacked on the same text,
    and each one paints its own shadow — which is exactly why Saad saw a shadow far
    heavier than the 50% he asked for (6 Aug). Keep ONE style, spanning the text.
    """
    m = copy.deepcopy(template)
    content = json.loads(m["content"])
    content["text"] = text
    styles = content.get("styles") or [{}]
    one = copy.deepcopy(styles[0])
    one["range"] = [0, len(text)]
    shadows = one.get("shadows") or []
    if shadows:
        one["shadows"] = [shadows[0]]       # one shadow, never a stack
    content["styles"] = [one]
    m["id"] = new_id()
    m["content"] = json.dumps(content, ensure_ascii=False)
    m["base_content"] = ""
    return m


def caption_segment(template, material_id, start, duration, index):
    s = copy.deepcopy(template)
    s.update({
        "id": new_id(), "material_id": material_id,
        "source_timerange": None,
        "target_timerange": {"start": int(start * US), "duration": int(duration * US)},
        "render_index": 20000 + index,      # above the picture and the call-outs
        "extra_material_refs": [], "caption_info": None,
        "group_id": "", "template_id": "", "visible": True,
    })
    return s


def build(draft, donor_text, donor_seg, cues, canvas_h=1140):
    """Pure: draft + cues -> draft with one appended caption track."""
    out = copy.deepcopy(draft)
    out["materials"].setdefault("texts", [])
    segs = []
    for i, (a, b, text) in enumerate(cues):
        dur = max(b - a, 0.3)
        m = styled(text_material(donor_text, text), CAPTION, CAPTION_FONT)
        out["materials"]["texts"].append(m)
        segs.append(placed(caption_segment(donor_seg, m["id"], a, dur, i), CAPTION))
    out["tracks"].append({
        "id": new_id(), "type": "text", "attribute": 0, "flag": 0,
        "is_default_name": False, "name": TRACK_NAME, "segments": segs,
    })
    return out


TITLE_TRACK = "Title"
TITLE_DUR = 4.4          # Timeline 01 held its title 0.00-4.40s


def add_title(draft, donor_text, donor_seg, line1, line2, dur=TITLE_DUR):
    """Two stacked text elements at the head of the video, to Saad's spec.

    Line 2 sits a little under line 1; everything else is his numbers verbatim.
    """
    out = copy.deepcopy(draft)
    out["materials"].setdefault("texts", [])
    out["tracks"] = [t for t in out.get("tracks", [])
                     if not (t.get("type") == "text" and t.get("name") == TITLE_TRACK)]
    segs = []
    for i, (text, spec) in enumerate(((line1, TITLE_TOP), (line2, TITLE_BOTTOM))):
        m = styled(text_material(donor_text, text), spec, spec["font"])
        out["materials"]["texts"].append(m)
        seg = caption_segment(donor_seg, m["id"], 0.0, dur, 900 + i)
        placed(seg, spec)
        # line 1 above, line 2 below, around the y he gave for the pair
        seg["clip"]["transform"]["y"] = spec["y"] + (0.075 if i == 0 else -0.075)
        segs.append(seg)
    out["tracks"].append({
        "id": new_id(), "type": "text", "attribute": 0, "flag": 0,
        "is_default_name": False, "name": TITLE_TRACK, "segments": segs,
    })
    return out


def apply_title(project, line1, line2):
    from sa_guard import preflight
    preflight("capcut_write", project=project)
    if capcut_open():
        raise SystemExit("CapCut is open — close it first")
    target = CAPCUT / project
    drafts = [target / "draft_info.json"] + \
             [pathlib.Path(p) for p in glob.glob(str(target / "Timelines/*/draft_info.json"))]
    drafts = [p for p in drafts if p.exists()]
    if not drafts:
        raise SystemExit(f"no draft found for {project}")
    dt, ds = donor_templates()
    for p in drafts:
        bak = p.with_suffix(".json.pre_captions")
        if not bak.exists():
            shutil.copy2(p, bak)
        d = json.loads(p.read_text(encoding="utf-8"))
        p.write_text(json.dumps(add_title(d, dt, ds, line1, line2), ensure_ascii=False),
                     encoding="utf-8")
    print(f'-> {project}: title "{line1} / {line2}"')


def donor_templates():
    root = CAPCUT / DONOR / "Timelines"
    for p in sorted(root.glob("*/draft_info.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        texts = d["materials"].get("texts") or []
        for tr in d.get("tracks", []):
            if tr.get("type") == "text" and tr.get("segments") and texts:
                return copy.deepcopy(texts[0]), copy.deepcopy(tr["segments"][0])
    raise SystemExit("no text style found in the donor project")


def apply(project, srt):
    from sa_guard import preflight
    preflight("capcut_write", project=project)
    if capcut_open():
        raise SystemExit("CapCut is open — close it first")
    target = CAPCUT / project
    drafts = [target / "draft_info.json"] + \
             [pathlib.Path(p) for p in glob.glob(str(target / "Timelines/*/draft_info.json"))]
    drafts = [p for p in drafts if p.exists()]
    if not drafts:
        raise SystemExit(f"no draft found for {project}")

    cues = parse_srt(srt)
    if not cues:
        raise SystemExit(f"no cues parsed from {srt}")
    dt, ds = donor_templates()

    built = {}      # input blob -> output blob, so identical root/Timelines copies
    for p in drafts:  # stay identical instead of diverging on freshly minted UUIDs (19 Aug)
        bak = p.with_suffix(".json.pre_captions")
        if not bak.exists():
            shutil.copy2(p, bak)            # reversible, once
        raw = p.read_text(encoding="utf-8")
        if raw not in built:
            d = json.loads(raw)
            d["tracks"] = [t for t in d.get("tracks", [])
                           if not (t.get("type") == "text" and t.get("name") == TRACK_NAME)]
            built[raw] = json.dumps(build(d, dt, ds, cues), ensure_ascii=False)
        p.write_text(built[raw], encoding="utf-8")

    last = cues[-1][1]
    dur = json.loads(drafts[0].read_text(encoding="utf-8")).get("duration", 0) / US
    warn = "  ! last cue runs past the end of the video" if last > dur + 0.5 else ""
    print(f"-> {project}: {len(cues)} caption segments, ends {last:.1f}s of {dur:.1f}s{warn}")
    return len(cues)


def _test():
    srt = ("1\n00:00:01,000 --> 00:00:02,500\nIn this video,\n\n"
           "2\n00:00:02,500 --> 00:00:04,000\nwe'll sign in as the Sales Manager\n")
    p = pathlib.Path("/tmp/_sa_cap_test.srt")
    p.write_text(srt)
    cues = parse_srt(p)
    assert len(cues) == 2, cues
    assert abs(cues[0][0] - 1.0) < 1e-9 and abs(cues[0][1] - 2.5) < 1e-9
    assert cues[1][2] == "we'll sign in as the Sales Manager"

    donor_text = {"id": "x", "content": json.dumps(
        {"text": "old", "styles": [{"range": [0, 3], "size": 5}]})}
    donor_seg = {"id": "s", "material_id": "x", "clip": {}, "render_index": 1,
                 "target_timerange": {"start": 0, "duration": 0}}
    draft = {"materials": {"texts": []}, "tracks": []}
    out = build(draft, donor_text, donor_seg, cues)
    track = out["tracks"][-1]
    assert track["type"] == "text" and track["name"] == TRACK_NAME
    assert len(track["segments"]) == 2 and len(out["materials"]["texts"]) == 2
    got = json.loads(out["materials"]["texts"][1]["content"])
    assert got["text"] == cues[1][2]
    seg0 = track["segments"][0]
    assert abs(seg0["clip"]["transform"]["y"] - (-0.892)) < 1e-9, "caption y must be -892/1000"
    assert abs(seg0["clip"]["scale"]["x"] - 0.75) < 1e-9, "caption scale must be 75%"
    mat = out["materials"]["texts"][0]
    assert mat["font_size"] == 5.0 and mat["shadow_alpha"] == 0.50
    assert mat["shadow_smoothing"] == 0.15 and mat["shadow_distance"] == 5.0
    assert mat["shadow_angle"] == -45.0 and mat["has_shadow"]
    assert all("\n" not in c[2] for c in cues), "captions are one line"
    # a stacked style paints its shadow once per range — 50% opacity thrice is not 50%
    stacked = {"id": "x", "content": json.dumps({"text": "old", "styles": [
        {"range": [0, 3], "size": 5, "shadows": [{"alpha": 0.5}]},
        {"range": [0, 3], "size": 5, "shadows": [{"alpha": 0.5}]},
        {"range": [0, 3], "size": 5, "shadows": [{"alpha": 0.5}]}]})}
    got = json.loads(text_material(stacked, "some caption text")["content"])
    assert len(got["styles"]) == 1, "donor style ranges must collapse to one"
    assert len(got["styles"][0]["shadows"]) == 1, "exactly one shadow, never a stack"
    assert got["styles"][0]["range"] == [0, len("some caption text")], \
        "style must span the new text"
    assert track["segments"][0]["target_timerange"]["start"] == 1_000_000
    assert track["segments"][0]["target_timerange"]["duration"] == 1_500_000
    assert track["segments"][1]["render_index"] > track["segments"][0]["render_index"]
    print("sa_capcut_captions self-check: ok (srt parse, style span, timings, layering)")


if __name__ == "__main__":
    if "--test" in sys.argv:
        _test()
        sys.exit()
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("srt", nargs="?")
    ap.add_argument("--title", nargs=2, metavar=("LINE1", "LINE2"))
    a = ap.parse_args()
    if a.title:
        apply_title(a.project, *a.title)
    else:
        apply(a.project, a.srt)
