#!/usr/bin/env python3
"""Write an editor-neutral timeline plan into a NEW CapCut draft.

The donor and every existing CapCut project are read-only. The writer refuses
to overwrite a project and refuses to run while CapCut is open.

  python3 Tools/sa_capcut_writer.py timeline_plan.json --name "Project v1"
  python3 Tools/sa_capcut_writer.py timeline_plan.json --name test --output-root /tmp/capcut-test
  Tools/venv/bin/python3 Tools/sa_capcut_writer.py --test
"""
import argparse
import json
import os
import pathlib
import shutil
import subprocess
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from sa_assemble import CAPCUT_DIR, US, find_main_video_track, new_id, probe
from sa_timeline import load_json, validate_plan
from sa_security import assert_writes_allowed


def capcut_is_open():
    result = subprocess.run(["pgrep", "-x", "CapCut"], capture_output=True)
    return result.returncode == 0


def find_material(materials, material_id):
    for group, rows in materials.items():
        if not isinstance(rows, list):
            continue
        for row in rows:
            if isinstance(row, dict) and row.get("id") == material_id:
                return group, row
    return None, None


def is_outro_material(material):
    text = " ".join(str(material.get(k, "")) for k in
                    ("path", "material_name", "name")).lower()
    return any(x in text for x in ("outro", "endcard"))


def donor_outro_segments(draft):
    videos = {x.get("id"): x for x in draft.get("materials", {}).get("videos", [])}
    found = []
    for track in draft.get("tracks", []):
        if track.get("type") != "video":
            continue
        segments = [s for s in track.get("segments", [])
                    if is_outro_material(videos.get(s.get("material_id"), {}))]
        if segments:
            found.append((track, segments))
    return found


def is_voice_material(material):
    text = " ".join(str(material.get(k, "")) for k in
                    ("path", "name", "type")).lower()
    return any(x in text for x in ("vo_", "subblock", "sbl-", "voice", "human.wav"))


def copy_donor_skeleton(source, target):
    """Copy metadata, not CapCut's multi-GB generated caches."""
    target.mkdir(parents=True)
    for child in source.iterdir():
        if child.is_file() and child.name != ".DS_Store":
            shutil.copy2(child, target / child.name)
    attachments = source / "common_attachment"
    if attachments.is_dir():
        shutil.copytree(attachments, target / "common_attachment")
    placeholder = source / "Resources" / "defaultPlaceholder.png"
    if placeholder.is_file():
        (target / "Resources").mkdir()
        shutil.copy2(placeholder, target / "Resources" / placeholder.name)


def write_timelines(target, blob):
    """Write the modern Timelines/ read path beside the legacy root draft_info.

    CapCut reads Timelines/<uuid>/draft_info.json (project.json names the uuid);
    a draft with only the root copy opens the DONOR's timeline (see
    Reference/CAPCUT_DRAFT_SCHEMA.md). Both copies must be byte-identical and
    every identifier freshly minted — never the donor's.
    """
    timeline_id = new_id()
    now_us = int(time.time() * US)
    tdir = target / "Timelines" / timeline_id
    tdir.mkdir(parents=True)
    (tdir / "draft_info.json").write_text(blob, encoding="utf-8")
    project = {
        "config": {"color_space": -1, "render_index_track_mode_on": False,
                   "use_float_render": False},
        "create_time": now_us,
        "id": new_id(),
        "main_timeline_id": timeline_id,
        "timelines": [{
            "create_time": now_us,
            "id": timeline_id,
            "is_marked_delete": False,
            "name": "Timeline 01",
            "update_time": now_us,
        }],
        "update_time": now_us,
        "version": 0,
    }
    (target / "Timelines" / "project.json").write_text(
        json.dumps(project, ensure_ascii=False), encoding="utf-8")
    return timeline_id


def donor_transition_id(materials, name):
    if not name:
        return None
    for row in materials.get("transitions", []):
        if (row.get("name") or "").lower() == name.lower():
            return row.get("id")
    return None


def main_video_plan(plan):
    for track in plan["tracks"]:
        if track.get("type") == "video" and track.get("clips"):
            return track["clips"]
    raise ValueError("plan has no populated video track")


def apply_plan(draft, plan):
    """Pure draft transform used by both the CLI and integration test."""
    materials = draft["materials"]
    main_track = find_main_video_track(draft.get("tracks", []))
    if not main_track or not main_track.get("segments"):
        raise ValueError("donor has no main video segment template")
    original_outros = [(track, json.loads(json.dumps(segments)))
                       for track, segments in donor_outro_segments(draft)]
    segment_template = json.loads(json.dumps(main_track["segments"][0]))
    _, donor_video = find_material(materials, segment_template.get("material_id"))
    if not donor_video:
        raise ValueError("donor video material template missing")
    donor_video = json.loads(json.dumps(donor_video))

    plan_clips = main_video_plan(plan)
    new_segments = []
    for index, clip_plan in enumerate(plan_clips):
        file_path = str(pathlib.Path(clip_plan["file"]).expanduser().resolve())
        full_duration, width, height = probe(file_path)
        material_id = new_id()
        video = json.loads(json.dumps(donor_video))
        video.update({
            "id": material_id,
            "path": file_path,
            "media_path": "",
            "material_name": os.path.basename(file_path),
            "name": os.path.basename(file_path),
            "width": width,
            "height": height,
            "duration": int(full_duration * US),
            "material_id": "",
            "category_id": "",
            "category_name": "local",
            "material_url": "",
            "request_id": "",
        })
        materials.setdefault("videos", []).append(video)

        speed = float(clip_plan.get("speed") or 1.0)
        speed_id = new_id()
        materials.setdefault("speeds", []).append({
            "id": speed_id, "type": "speed", "mode": 0,
            "speed": speed, "curve_speed": None,
        })
        refs = [speed_id]
        transition_id = donor_transition_id(materials, clip_plan.get("transition"))
        if transition_id:
            refs.append(transition_id)

        transform = clip_plan.get("transform") or {}
        segment = json.loads(json.dumps(segment_template))
        segment.update({
            "id": new_id(),
            "material_id": material_id,
            "speed": speed,
            "source_timerange": {
                "start": int(float(clip_plan.get("source_start", 0)) * US),
                "duration": int(float(clip_plan.get("source_duration",
                                                    clip_plan["timeline_duration"] * speed)) * US),
            },
            "target_timerange": {
                "start": int(float(clip_plan["timeline_start"]) * US),
                "duration": int(float(clip_plan["timeline_duration"]) * US),
            },
            "render_timerange": {"start": 0, "duration": 0},
            "extra_material_refs": refs,
            "render_index": index + 2,
            "caption_info": None,
            "group_id": "",
            "template_id": "",
            "clip": {
                "scale": {
                    "x": float(transform.get("scale_x", 1.0)),
                    "y": float(transform.get("scale_y", 1.0)),
                },
                "rotation": float(transform.get("rotation", 0.0)),
                "transform": {
                    "x": float(transform.get("x", 0.0)),
                    "y": float(transform.get("y", 0.0)),
                },
                "flip": {"vertical": False, "horizontal": False},
                "alpha": float(transform.get("alpha", 1.0)),
            },
        })
        new_segments.append(segment)
    main_track["segments"] = new_segments

    picture_end = max((s["target_timerange"]["start"] +
                       s["target_timerange"]["duration"] for s in new_segments), default=0)

    # Remove donor content that does not belong in the new plan. Keep only the
    # new main picture, one donor music bed, and an identified outro.
    outro_track_ids = {id(t) for t, _ in original_outros}
    for track in draft.get("tracks", []):
        if track is main_track:
            continue
        if id(track) in outro_track_ids:
            continue
        if track.get("type") not in ("audio",):
            track["segments"] = []

    outro_end = picture_end
    for track, outro_segments in original_outros:
        original_start = min(s["target_timerange"]["start"] for s in outro_segments)
        kept = []
        for segment in outro_segments:
            clone = json.loads(json.dumps(segment))
            clone["target_timerange"]["start"] = (
                picture_end + segment["target_timerange"]["start"] - original_start)
            kept.append(clone)
            outro_end = max(outro_end, clone["target_timerange"]["start"] +
                            clone["target_timerange"]["duration"])
        if track is main_track:
            track["segments"].extend(kept)
        else:
            track["segments"] = kept

    audio_materials = {x.get("id"): x for x in materials.get("audios", [])}
    music_choice = None
    for track in draft.get("tracks", []):
        if track.get("type") != "audio":
            continue
        for segment in track.get("segments", []):
            material = audio_materials.get(segment.get("material_id"), {})
            if material and not is_voice_material(material):
                candidate = (segment["target_timerange"]["start"], track, segment)
                if music_choice is None or candidate[0] < music_choice[0]:
                    music_choice = candidate
    for track in draft.get("tracks", []):
        if track.get("type") != "audio":
            continue
        if music_choice and track is music_choice[1]:
            segment = json.loads(json.dumps(music_choice[2]))
            segment["target_timerange"]["start"] = 0
            segment["target_timerange"]["duration"] = picture_end
            segment["source_timerange"]["start"] = 0
            segment["source_timerange"]["duration"] = picture_end
            track["segments"] = [segment]
        else:
            track["segments"] = []

    canvas = plan["canvas"]
    draft["canvas_config"].update({
        "width": int(canvas["width"]), "height": int(canvas["height"]),
    })
    draft["fps"] = float(canvas["fps"])
    draft["duration"] = outro_end
    draft["name"] = plan["project"]
    draft.setdefault("config", {})["export_range"] = {
        "start": 0, "duration": outro_end,
    }
    return draft


def write_project(plan_path, project_name, donor_name=None, output_root=None,
                  allow_open=False):
    assert_writes_allowed("CapCut project write")
    plan = load_json(plan_path)
    errors = validate_plan(plan)
    if errors:
        raise SystemExit("invalid plan: " + "; ".join(errors))
    if capcut_is_open() and not allow_open:
        raise SystemExit("CapCut is open. Close it before writing a draft.")
    donor_name = donor_name or plan["style"]["masters"][0]
    donor_dir = pathlib.Path(CAPCUT_DIR) / donor_name
    if not donor_dir.is_dir():
        raise SystemExit("donor project not found: %s" % donor_dir)
    root = pathlib.Path(output_root or CAPCUT_DIR).expanduser().resolve()
    target = root / project_name
    if target.exists():
        raise SystemExit("refusing to overwrite existing project: %s" % target)
    root.mkdir(parents=True, exist_ok=True)
    copy_donor_skeleton(donor_dir, target)
    draft_path = target / "draft_info.json"
    draft = json.loads(draft_path.read_text(encoding="utf-8"))
    plan_for_name = json.loads(json.dumps(plan))
    plan_for_name["project"] = project_name
    try:
        result = apply_plan(draft, plan_for_name)
        draft_id = new_id()
        result["id"] = draft_id
        result["name"] = project_name
        result["path"] = str(target)
        blob = json.dumps(result, ensure_ascii=False)
        draft_path.write_text(blob, encoding="utf-8")
        write_timelines(target, blob)
        meta_path = target / "draft_meta_info.json"
        if meta_path.is_file():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            now_us = int(time.time() * US)
            media_size = sum(os.path.getsize(c["file"]) for c in main_video_plan(plan_for_name)
                             if os.path.isfile(c["file"]))
            meta.update({
                "draft_name": project_name,
                "draft_fold_path": str(target),
                "draft_root_path": str(root),
                "draft_id": draft_id,
                "tm_draft_create": now_us,
                "tm_draft_modified": now_us,
                "tm_duration": result["duration"],
                "draft_timeline_materials_size_": media_size,
            })
            meta_path.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
        (target / "SA_TIMELINE_PLAN.json").write_text(
            json.dumps(plan_for_name, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    except Exception:
        shutil.rmtree(target, ignore_errors=True)
        raise
    print("new CapCut draft -> %s" % target)
    print("source projects untouched; open and perform Saad's taste pass")
    return target


def _test():
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        target = pathlib.Path(tmp) / "Test Project"
        target.mkdir()
        donor_project_id = new_id()
        donor_timeline_id = new_id()
        blob = json.dumps({"id": new_id(), "duration": 123}, ensure_ascii=False)
        timeline_id = write_timelines(target, blob)
        # checklist (CAPCUT_DRAFT_SCHEMA.md): both read paths byte-equal
        copy = (target / "Timelines" / timeline_id / "draft_info.json").read_bytes()
        assert copy == blob.encode("utf-8"), "Timelines copy must be byte-identical"
        # project.json: exactly one timeline, main_timeline_id points at it
        project = json.loads((target / "Timelines" / "project.json")
                             .read_text(encoding="utf-8"))
        assert len(project["timelines"]) == 1, "exactly ONE timeline entry"
        assert project["main_timeline_id"] == timeline_id
        assert project["timelines"][0]["id"] == timeline_id
        assert (target / "Timelines" / timeline_id).is_dir()
        # every identifier fresh — never the donor's
        assert project["id"] not in (donor_project_id, donor_timeline_id)
        assert timeline_id not in (donor_project_id, donor_timeline_id)
        # times in microseconds (any plausible seconds value fails this)
        assert project["create_time"] > 1e15 and project["update_time"] > 1e15
        assert project["timelines"][0]["name"] == "Timeline 01"
        assert project["version"] == 0
        assert project["config"] == {"color_space": -1,
                                     "render_index_track_mode_on": False,
                                     "use_float_render": False}
    print("sa_capcut_writer self-check: ok "
          "(Timelines written, byte-equal, one timeline, fresh ids)")


def main():
    if "--test" in sys.argv:
        _test()
        sys.exit()
    ap = argparse.ArgumentParser()
    ap.add_argument("plan")
    ap.add_argument("--name", required=True)
    ap.add_argument("--donor")
    ap.add_argument("--output-root")
    ap.add_argument("--allow-capcut-open", action="store_true",
                    help="test-only override when output is outside CapCut")
    args = ap.parse_args()
    write_project(args.plan, args.name, args.donor, args.output_root,
                  args.allow_capcut_open)


if __name__ == "__main__":
    main()
