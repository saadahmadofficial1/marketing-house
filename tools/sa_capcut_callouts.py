#!/usr/bin/env python3
"""sa_capcut_callouts — build a CapCut draft where every call-out is its own layer.

Why this exists (Saad, 6 Aug 2026): a burned-in MP4 is not a deliverable he can work
with. He needs to nudge a box, resize it, retime it or delete it himself. So the draft
is the artefact and the flat render is only a preview.

Shape of the draft, matching how he already edits (his approved template project):
  track 0  picture  — the paced MP4 (voice-over already inside it)
  track 1+ overlay  — ONE full-canvas transparent PNG per call-out

Each call-out PNG is full-canvas and goes in at scale 1 / offset 0, so it lands exactly
where it was authored. Dragging the layer moves the box; scaling resizes it. That keeps
the maths out of it — there is no coordinate convention left to get wrong.

  Tools/venv/bin/python3 Tools/sa_capcut_callouts.py T01/T01_PACED_LAYERS/_layers.json \
      --name "Training 01 Example"
  Tools/venv/bin/python3 Tools/sa_capcut_callouts.py --test

Refuses to run while CapCut is open, and refuses to overwrite an existing project.
"""
import argparse
import copy
import json
import os
import pathlib
import shutil
import subprocess
import sys
import time
import uuid

US = 1_000_000
CAPCUT = pathlib.Path("~/Movies/CapCut/User Data/Projects/com.lveditor.draft").expanduser()
def _donor():
    # The donor project has been renamed before — match its name as a prefix, don't
    # assume the exact name. Set CAPCUT_DONOR to your own approved template project.
    name = os.environ.get("CAPCUT_DONOR", "Donor Project")
    hits = [p.name for p in sorted(CAPCUT.glob(name + "*")) if (p / "Timelines").exists()]
    return hits[0] if hits else name


DONOR = _donor()                # Saad's own approved project — used only as a template


def new_id():
    return str(uuid.uuid4()).upper()


def capcut_open():
    return subprocess.run(["pgrep", "-x", "CapCut"], capture_output=True).returncode == 0


def probe(path):
    # one -show_entries only: a second flag silently replaces the first
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "format=duration:stream=width,height",
         "-of", "json", str(path)], capture_output=True, text=True).stdout
    d = json.loads(out or "{}")
    s = (d.get("streams") or [{}])[0]
    dur = float((d.get("format") or {}).get("duration") or 0.0)   # stills have no duration
    return (dur, int(s.get("width", 0)), int(s.get("height", 0)))


def donor_draft():
    """Any draft_info.json from the donor project — we only borrow its schema."""
    root = CAPCUT / DONOR / "Timelines"
    for p in sorted(root.glob("*/draft_info.json")):
        return json.loads(p.read_text(encoding="utf-8"))
    raise SystemExit(f"donor project not found: {root}")


# CapCut's rectangle mask, exactly as it appears in one of Saad's own projects -
# the method he used to round the recording into the phone (found 23 Sep). Only the id
# and config change per use. The path is CapCut's cached effect on this Mac.
MASK_TEMPLATE = {
    "type": "mask", "category": "video", "category_name": "", "category_id": "", "panel": "",
    "is_old_version": False, "resource_id": "7374021450748924432",
    "name": "Rectangle", "resource_type": "rectangle",
    "path": os.path.expanduser("~/Library/Containers/com.lemon.lvoverseas/Data/Movies/CapCut/User Data/Cache/effect/1068046531/02b8999168d121538a98ea59127483ef"),
    "position_info": "",
    "text_config": {"content": "", "font_name": "", "font_path": "", "font_resource_id": "",
                    "font_size": 15.0, "bold_width": 0.0, "italic_degree": 0,
                    "has_underline": False, "line_gap": 0.0, "char_spacing": 0.0,
                    "align_type": 15, "scale": 1.0},
    "platform": "all", "loader_work_space": "", "track_segment": "", "contour_path": None,
    "source_platform": 0,
}


def mask_material(config):
    m = copy.deepcopy(MASK_TEMPLATE)
    m.update({"id": new_id(), "constant_material_id": new_id(), "config": dict(config)})
    return m


def video_material(template, path, width, height, duration):
    m = copy.deepcopy(template)
    m.update({
        "id": new_id(), "path": str(path), "media_path": "",
        "material_name": os.path.basename(path), "name": os.path.basename(path),
        "width": width, "height": height, "duration": int(duration * US),
        "material_id": "", "category_id": "", "category_name": "local",
        "material_url": "", "request_id": "", "type": "video",
    })
    return m


def segment(template, material_id, start, duration, render_index, source_start=0.0):
    s = copy.deepcopy(template)
    s.update({
        "id": new_id(), "material_id": material_id, "speed": 1.0,
        "source_timerange": {"start": int(source_start * US), "duration": int(duration * US)},
        "target_timerange": {"start": int(start * US), "duration": int(duration * US)},
        "render_timerange": {"start": 0, "duration": 0},
        "extra_material_refs": [], "render_index": render_index,
        "caption_info": None, "group_id": "", "template_id": "",
        "clip": {"scale": {"x": 1.0, "y": 1.0}, "rotation": 0.0,
                 "transform": {"x": 0.0, "y": 0.0},
                 "flip": {"vertical": False, "horizontal": False}, "alpha": 1.0},
        "visible": True,
    })
    return s


def build(manifest, draft, name, root=None):
    """Pure: donor draft + manifest -> new draft dict. Separated so it can be tested.

    Every media path is made absolute against `root` (the manifest's own folder).
    CapCut stores paths verbatim, so a relative one becomes missing media the moment
    the draft is opened from anywhere else.
    """
    root = pathlib.Path(root or ".")

    def fix(p):
        p = pathlib.Path(p)
        return str(p if p.is_absolute() else (root / p)).replace("/./", "/")

    canvas = manifest["canvas"]
    video = fix(manifest["video"])
    vdur, vw, vh = probe(video)

    vids = draft["materials"].get("videos", [])
    vtemplate = copy.deepcopy(next((m for m in vids if m.get("type") == "video"), vids[0]))
    main = next(t for t in draft.get("tracks", []) if t.get("type") == "video"
                and t.get("segments"))
    stemplate = copy.deepcopy(main["segments"][0])

    out = copy.deepcopy(draft)
    out["id"] = new_id()
    out["canvas_config"] = {"ratio": "original", "width": canvas[0], "height": canvas[1],
                            "background": None}
    out["materials"]["videos"] = []
    out["materials"]["texts"] = []
    for key in ("audios", "speeds", "transitions", "stickers"):
        out["materials"].setdefault(key, [])
    out["tracks"] = []

    # Full-canvas stills that sit UNDER the picture (background, glow, phone back) and
    # OVER it (phone frame), each its own named track so Saad can restyle any of them.
    # Added 23 Sep for a phone-app series; a manifest without them builds as before.
    idx = [0]

    def still_track(item):
        f = fix(item["file"])
        _, pw, ph = probe(f)
        m = video_material(vtemplate, f, pw or canvas[0], ph or canvas[1], vdur)
        m["type"] = "photo"
        out["materials"]["videos"].append(m)
        out["tracks"].append({"id": new_id(), "type": "video", "attribute": 0, "flag": 0,
                              "is_default_name": False, "name": item.get("name", "")[:40],
                              "segments": [segment(stemplate, m["id"], 0.0, vdur, idx[0])]})
        idx[0] += 1

    for item in manifest.get("under", []):
        still_track(item)

    # picture (the voice-over is already inside this file, unless muted below)
    pic = video_material(vtemplate, video, vw, vh, vdur)
    out["materials"]["videos"].append(pic)
    pseg = segment(stemplate, pic["id"], 0.0, vdur, idx[0])
    idx[0] += 1
    if manifest.get("picture_muted"):
        pseg["volume"] = 0.0
    if manifest.get("mask"):
        mm = mask_material(manifest["mask"])
        out["materials"].setdefault("common_mask", []).append(mm)
        pseg["extra_material_refs"] = pseg.get("extra_material_refs", []) + [mm["id"]]
    out["tracks"].append({
        "id": new_id(), "type": "video", "attribute": 0, "flag": 0,
        "is_default_name": not manifest.get("picture_name"), "name": manifest.get("picture_name", ""),
        "segments": [pseg],
    })

    for item in manifest.get("over", []):
        still_track(item)

    # one track per call-out, so none of them can fight for the same lane
    for i, layer in enumerate(manifest["layers"], start=1):
        lf = fix(layer["file"])
        _, pw, ph = probe(lf)
        m = video_material(vtemplate, lf, pw or canvas[0], ph or canvas[1],
                           max(layer["duration"], 0.1))
        m["type"] = "photo"
        out["materials"]["videos"].append(m)
        out["tracks"].append({
            "id": new_id(), "type": "video", "attribute": 0, "flag": 0,
            "is_default_name": False, "name": layer["label"][:40] or f"call-out {i}",
            "segments": [segment(stemplate, m["id"], layer["start"], layer["duration"], idx[0] + i)],
        })

    total = int(vdur * US)
    out["duration"] = total
    for key in ("create_time", "update_time"):
        if key in out:
            out[key] = int(time.time())
    return out


def write(manifest_path, name):
    if capcut_open():
        raise SystemExit("CapCut is open — close it first, the draft would be overwritten")
    manifest = json.loads(pathlib.Path(manifest_path).read_text(encoding="utf-8"))
    target = CAPCUT / name
    if target.exists():
        raise SystemExit(f"project already exists, refusing to overwrite: {target}")

    donor_root = CAPCUT / DONOR
    src_tl = next((CAPCUT / DONOR / "Timelines").glob("*/draft_info.json")).parent
    shutil.copytree(donor_root, target)                 # take the donor's asset scaffolding

    # Strip the donor's baggage. The ROOT draft_info.json is the legacy
    # single-timeline copy of Saad's Timeline 01 — leaving it is what made all 15
    # projects open at 402.7s showing his main timeline (6 Aug). It gets rewritten
    # with the new content below rather than deleted, since older CapCut reads it.
    for junk in ("draft_info.json.bak", "template-2.tmp", "draft_cover.jpg"):
        (target / junk).unlink(missing_ok=True)
    for cached in list(target.glob("*-sdr*.png")) + list(target.glob("template*.tmp")):
        cached.unlink(missing_ok=True)

    # Every identifier has to be regenerated. CapCut indexes projects by draft_id
    # and timeline id; leaving the donor's means 16 projects claim one identity and
    # none of them open (6 Aug — this is exactly what went wrong the first time).
    tl_id = new_id()
    tl = target / "Timelines" / tl_id
    src_tl.parent.joinpath(src_tl.name)                 # (donor untouched, read only)
    (target / "Timelines" / src_tl.name).rename(tl)
    for extra in (target / "Timelines").glob("*"):      # drop every other donor timeline
        if extra.is_dir() and extra.name != tl_id:
            shutil.rmtree(extra)

    out = build(manifest, json.loads((tl / "draft_info.json").read_text(encoding="utf-8")),
                name, root=pathlib.Path(manifest_path).resolve().parent)
    out["id"] = tl_id
    blob = json.dumps(out, ensure_ascii=False)
    (tl / "draft_info.json").write_text(blob, encoding="utf-8")
    (target / "draft_info.json").write_text(blob, encoding="utf-8")   # both read paths agree

    draft_id = new_id()
    now = int(time.time() * 1_000_000)
    for meta in (tl / "draft_meta_info.json", target / "draft_meta_info.json"):
        if meta.exists():
            d = json.loads(meta.read_text(encoding="utf-8"))
            d["draft_id"] = draft_id
            d["draft_name"] = name
            d["draft_fold_path"] = str(target)
            for k in ("draft_timeline_materials_size_",):
                d.pop(k, None)                          # stale byte count from the donor
            for k in ("tm_draft_create", "tm_draft_modified"):
                if k in d:
                    d[k] = now
            meta.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")

    pj = target / "Timelines" / "project.json"
    if pj.exists():
        d = json.loads(pj.read_text(encoding="utf-8"))
        d["id"] = new_id()
        d["main_timeline_id"] = tl_id
        d["create_time"] = d["update_time"] = now
        d["timelines"] = [{"create_time": now, "id": tl_id, "is_marked_delete": False,
                           "name": name, "update_time": now}]
        pj.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    (target / "Timelines" / "project.json.bak").unlink(missing_ok=True)

    extra = len(manifest.get("under", [])) + len(manifest.get("over", []))
    problems = verify(target, expect_layers=len(manifest["layers"]) + extra)
    if problems:
        raise SystemExit(f"{name}: draft written but failed verification -> " + "; ".join(problems))
    print(f"-> {target}\n   picture + {len(manifest['layers'])} independent call-out layers  [verified]")
    return target


def verify(target, expect_layers):
    """Read the project back the way CapCut does, and prove it is the right one.

    Written after all 15 first builds opened as Saad's 402.7s main timeline: a
    "wrote successfully" message proves nothing, so this re-opens every read path,
    checks they agree, and confirms every referenced file is on disk.
    """
    target = pathlib.Path(target)
    out = []
    pj_path = target / "Timelines" / "project.json"
    if not pj_path.exists():
        return ["Timelines/project.json missing"]
    pj = json.loads(pj_path.read_text(encoding="utf-8"))
    ids = [t["id"] for t in pj.get("timelines", [])]
    if len(ids) != 1:
        out.append(f"project.json lists {len(ids)} timelines, expected exactly 1")
    if pj.get("main_timeline_id") not in ids:
        out.append("main_timeline_id does not point at a listed timeline")

    dirs = [p for p in (target / "Timelines").glob("*") if p.is_dir()]
    if len(dirs) != 1:
        out.append(f"{len(dirs)} timeline folders on disk, expected 1")
    for tid in ids:
        if not (target / "Timelines" / tid / "draft_info.json").exists():
            out.append(f"timeline {tid[:8]} has no draft_info.json")

    drafts = [target / "draft_info.json"] + [target / "Timelines" / i / "draft_info.json"
                                             for i in ids]
    durs = set()
    for p in drafts:
        if not p.exists():
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        durs.add(round(d.get("duration", 0) / US, 1))
        layers = len([t for t in d.get("tracks", []) if t.get("type") == "video"]) - 1
        if layers != expect_layers:
            out.append(f"{p.name} has {layers} call-out tracks, expected {expect_layers}")
        for m in d.get("materials", {}).get("videos", []):
            if m.get("path") and not os.path.exists(m["path"]):
                out.append(f"missing media: {os.path.basename(m['path'])}")
                break
    if len(durs) > 1:
        out.append(f"read paths disagree on duration: {sorted(durs)}")

    meta = target / "draft_meta_info.json"
    if meta.exists():
        m = json.loads(meta.read_text(encoding="utf-8"))
        if m.get("draft_name") != target.name:
            out.append("draft_meta_info draft_name does not match the folder")
        donor_meta = CAPCUT / DONOR / "draft_meta_info.json"
        if donor_meta.exists():
            if m.get("draft_id") == json.loads(
                    donor_meta.read_text(encoding="utf-8")).get("draft_id"):
                out.append("draft_id still identical to the donor — CapCut will not list it")
    return out


def _test():
    donor = {
        "id": "x", "duration": 0, "canvas_config": {},
        "materials": {"videos": [{"id": "v0", "type": "video", "path": "/old.mp4"}]},
        "tracks": [{"type": "video", "segments": [{"id": "s0", "material_id": "v0",
                                                   "clip": {}, "render_index": 0}]}],
    }
    man = {"video": __file__, "canvas": [1920, 1140],
           "layers": [{"file": __file__, "start": 3.0, "duration": 2.5, "label": "Click Save"},
                      {"file": __file__, "start": 9.0, "duration": 2.0, "label": "Click Next"}]}
    global probe
    real, probe = probe, lambda p: (120.0, 1920, 1140)
    try:
        out = build(man, donor, "T")
    finally:
        probe = real
    assert len(out["tracks"]) == 3, "one picture track plus one track per call-out"
    assert out["canvas_config"]["width"] == 1920
    names = [t["name"] for t in out["tracks"][1:]]
    assert names == ["Click Save", "Click Next"], "tracks are named so they're findable"
    for t in out["tracks"][1:]:
        c = t["segments"][0]["clip"]
        assert c["scale"] == {"x": 1.0, "y": 1.0} and c["transform"] == {"x": 0.0, "y": 0.0}, \
            "full-canvas layers must go in untransformed or the box moves"
    assert out["tracks"][1]["segments"][0]["target_timerange"]["start"] == 3_000_000
    assert out["tracks"][0]["segments"][0]["target_timerange"]["duration"] == 120_000_000
    for t in out["tracks"]:
        path = next(m["path"] for m in out["materials"]["videos"]
                    if m["id"] == t["segments"][0]["material_id"])
        assert os.path.isabs(path), "relative paths become missing media in CapCut"
    print("sa_capcut_callouts self-check: ok (track per call-out, untransformed, timings)")


if __name__ == "__main__":
    if "--test" in sys.argv:
        _test()
        sys.exit()
    ap = argparse.ArgumentParser()
    ap.add_argument("manifest")
    ap.add_argument("--name", required=True)
    a = ap.parse_args()
    write(a.manifest, a.name)
