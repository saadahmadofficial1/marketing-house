#!/usr/bin/env python3
"""Build Saad's structured editing Style Brain from local CapCut projects.

The raw CapCut JSON stays read-only. This encoder extracts compact, factual
editing fingerprints from the approved export range of every readable draft.

  python3 Tools/sa_stylebrain.py
  python3 Tools/sa_stylebrain.py --test
"""
import argparse
import collections
import datetime
import json
import os
import pathlib
import statistics

US = 1_000_000
ROOT = pathlib.Path(__file__).resolve().parents[1]
DRAFTS = pathlib.Path(os.path.expanduser(
    "~/Movies/CapCut/User Data/Projects/com.lveditor.draft"))
DEFAULT_JSON = ROOT / "Reference" / "CAPCUT_STYLE_BRAIN.json"
DEFAULT_MD = ROOT / "Reference" / "CAPCUT_STYLE_BRAIN.md"

# Example project-name overrides (project name -> style family).
KNOWN_TYPES = {
    "Product Walkthrough": "tutorial_short_walkthrough",
    "Gala Night Highlights": "luxury_event_reel",
}

# User-confirmed final timelines that outrank the project's root/main draft.
# Keep this list deliberately small: a timeline is added only after Saad names it as approved.
APPROVED_TIMELINES = [
    {
        "project": "Event Edit",
        "timeline": "Timeline 02",
        "id": "00000000-0000-0000-0000-000000000002",
        "label": "Event Edit - Timeline 02 (approved Story)",
        "format": "story_9x16",
    },
    {
        "project": "Event Edit",
        "timeline": "Timeline 03",
        "id": "00000000-0000-0000-0000-000000000003",
        "label": "Event Edit - Timeline 03 (approved Square)",
        "format": "square_1x1",
    },
]


def sec(value):
    return round((value or 0) / US, 4)


def overlap(start, duration, lo, hi):
    end = start + duration
    return max(0, min(end, hi) - max(start, lo))


def plain_text(material):
    content = material.get("content", "")
    if not isinstance(content, str):
        return ""
    try:
        parsed = json.loads(content)
        return (parsed.get("text") or "").strip()
    except Exception:
        return content.strip()


def material_maps(materials):
    by_id = {}
    kind = {}
    for group, rows in materials.items():
        if not isinstance(rows, list):
            continue
        for row in rows:
            if isinstance(row, dict) and row.get("id"):
                by_id[row["id"]] = row
                kind[row["id"]] = group
    return by_id, kind


def role_for(track_type, group, material):
    name = " ".join(str(material.get(k, "")) for k in
                    ("name", "material_name", "path", "type")).lower()
    if any(x in name for x in ("outro", "endcard")):
        return "outro"
    if track_type == "text":
        return "caption" if material.get("type") == "subtitle" else "title_or_overlay"
    if track_type == "audio":
        if any(x in name for x in ("vo_", "subblock", "sbl-", "voice", "human.wav")):
            return "voiceover"
        return "music_or_sound"
    if track_type == "video":
        if any(x in name for x in ("screen", "recording", "powtoon", "without music")):
            return "base_or_screen"
        return "picture"
    if track_type in ("filter", "effect"):
        return track_type
    return group or track_type


def normalized_segment(segment, track_type, track_index, export_lo, export_hi,
                       by_id, kinds):
    tr = segment.get("target_timerange") or {}
    target_start = tr.get("start", 0)
    target_dur = tr.get("duration", 0)
    used = overlap(target_start, target_dur, export_lo, export_hi)
    if used <= 0:
        return None
    clipped_start = max(target_start, export_lo)
    left_trim = clipped_start - target_start
    material_id = segment.get("material_id", "")
    material = by_id.get(material_id, {})
    group = kinds.get(material_id, "")
    source = segment.get("source_timerange") or {}
    speed = float(segment.get("speed") or 1.0)
    source_start = source.get("start", 0) + int(left_trim * speed)
    source_dur = int(used * speed) if source else 0
    clip = segment.get("clip") or {}
    transform = clip.get("transform") or {}
    scale = clip.get("scale") or {}
    transition_names = []
    for ref in segment.get("extra_material_refs") or []:
        ref_mat = by_id.get(ref, {})
        if kinds.get(ref) == "transitions" or ref_mat.get("type") == "transition":
            transition_names.append(ref_mat.get("name") or ref_mat.get("effect_id") or "unknown")

    item = {
        "track_type": track_type,
        "track_index": track_index,
        "timeline_start": sec(clipped_start - export_lo),
        "timeline_duration": sec(used),
        "source_start": sec(source_start),
        "source_duration": sec(source_dur),
        "speed": round(speed, 4),
        "role": role_for(track_type, group, material),
        "material": {
            "group": group,
            "name": material.get("name") or material.get("material_name") or "",
            "file": os.path.basename(material.get("path", "")),
            "type": material.get("type", ""),
        },
        "transform": {
            "scale_x": round(float(scale.get("x", 1.0)), 4),
            "scale_y": round(float(scale.get("y", 1.0)), 4),
            "x": round(float(transform.get("x", 0.0)), 4),
            "y": round(float(transform.get("y", 0.0)), 4),
            "rotation": round(float(clip.get("rotation", 0.0)), 4),
            "alpha": round(float(clip.get("alpha", 1.0)), 4),
        },
        "transitions": transition_names,
    }
    if track_type == "text":
        item["text"] = {
            "content": plain_text(material),
            "font": os.path.basename(material.get("font_path", "")),
            "font_size": material.get("font_size"),
            "colour": material.get("text_color", ""),
            "alignment": material.get("alignment"),
        }
    return item


def quantiles(values):
    if not values:
        return {"min": None, "median": None, "max": None}
    return {
        "min": round(min(values), 3),
        "median": round(statistics.median(values), 3),
        "max": round(max(values), 3),
    }


def infer_type(name, fingerprint):
    if name in KNOWN_TYPES:
        return KNOWN_TYPES[name]
    canvas = fingerprint["canvas"]
    texts = fingerprint["metrics"]["text_segments"]
    median = fingerprint["metrics"]["primary_picture_duration"]["median"]
    lower = name.lower()
    if "event edit" in lower:
        return "event_highlight_square" if canvas["width"] == canvas["height"] else "vertical_event_montage"
    if "gala" in lower:
        return "luxury_event_reel"
    if "farewell" in lower:
        return "tribute_farewell"
    if canvas["height"] > canvas["width"] and texts == 0:
        return "vertical_event_montage"
    if texts > 20 and median and median <= 6:
        return "tutorial_or_explainer"
    if texts == 0 and median and median <= 2.5:
        return "fast_montage"
    return "other_or_mixed"


def encode_project(path, name=None, approval=None):
    name = name or path.parent.name
    data = json.load(open(path, encoding="utf-8"))
    materials = data.get("materials") or {}
    by_id, kinds = material_maps(materials)
    export = (data.get("config") or {}).get("export_range") or {}
    export_lo = int(export.get("start", 0))
    export_dur = int(export.get("duration", 0))
    if export_dur <= 0:
        export_dur = int(data.get("duration", 0))
    export_hi = export_lo + export_dur

    segments = []
    track_counts = collections.Counter()
    for ti, track in enumerate(data.get("tracks") or []):
        track_type = track.get("type", "unknown")
        for segment in track.get("segments") or []:
            item = normalized_segment(segment, track_type, ti, export_lo, export_hi,
                                      by_id, kinds)
            if item:
                segments.append(item)
                track_counts[track_type] += 1

    video_tracks = collections.defaultdict(list)
    for item in segments:
        if item["track_type"] == "video" and item["role"] != "outro":
            video_tracks[item["track_index"]].append(item)
    primary_index = max(video_tracks, key=lambda k: (
        sum(x["timeline_duration"] for x in video_tracks[k]), len(video_tracks[k])
    ), default=None)
    primary = sorted(video_tracks.get(primary_index, []),
                     key=lambda x: x["timeline_start"])
    picture_durations = [x["timeline_duration"] for x in primary]
    picture_speeds = [x["speed"] for x in primary]
    source_in_ratios = []
    for item in primary:
        mat = next((m for m in materials.get("videos", [])
                    if (m.get("name") or m.get("material_name") or "") == item["material"]["name"]
                    and os.path.basename(m.get("path", "")) == item["material"]["file"]), None)
        if mat and mat.get("duration"):
            source_in_ratios.append(item["source_start"] / sec(mat["duration"]))

    all_transitions = collections.Counter(
        t for item in segments for t in item.get("transitions", []))
    transforms = [x["transform"] for x in primary]
    canvas = data.get("canvas_config") or {}
    outro = any(x["role"] == "outro" for x in segments)
    music = any(x["track_type"] == "audio" and x["role"] == "music_or_sound"
                for x in segments)
    has_saved_export = bool(export.get("duration"))
    confidence = "high" if has_saved_export and (outro or music) else (
        "medium" if has_saved_export else "low")

    result = {
        "project": name,
        "source": "CapCut draft_info.json",
        "evidence": {
            "approved_range_source": "saved_export_range" if has_saved_export else "whole_draft_fallback",
            "confidence": confidence,
            "has_outro": outro,
            "has_music_or_sound": music,
            "approval": approval or "not_recorded",
        },
        "canvas": {
            "width": canvas.get("width"),
            "height": canvas.get("height"),
            "ratio": canvas.get("ratio"),
            "fps": data.get("fps"),
        },
        "approved_range": {"start": sec(export_lo), "duration": sec(export_dur)},
        "metrics": {
            "segments_by_type": dict(track_counts),
            "primary_video_track": primary_index,
            "primary_picture_segments": len(primary),
            "primary_picture_duration": quantiles(picture_durations),
            "speed": quantiles(picture_speeds),
            "source_in_ratio": quantiles(source_in_ratios),
            "reframed_ratio": round(sum(
                1 for t in transforms if t["scale_x"] != 1 or t["scale_y"] != 1
                or t["x"] != 0 or t["y"] != 0 or t["rotation"] != 0
            ) / len(transforms), 3) if transforms else 0,
            "text_segments": track_counts.get("text", 0),
            "audio_segments": track_counts.get("audio", 0),
            "transitions": dict(all_transitions.most_common()),
        },
        "segments": sorted(segments, key=lambda x: (
            x["timeline_start"], x["track_index"], x["track_type"])),
    }
    result["style_type"] = infer_type(name, result)
    return result


def build_style_brain(drafts=DRAFTS):
    projects, errors = [], []
    projects_with_approved_timelines = {row["project"] for row in APPROVED_TIMELINES}
    for path in sorted(drafts.glob("*/draft_info.json")):
        if path.parent.name in projects_with_approved_timelines:
            continue
        try:
            projects.append(encode_project(path))
        except Exception as exc:
            errors.append({"project": path.parent.name, "error": str(exc)})
    for row in APPROVED_TIMELINES:
        path = drafts / row["project"] / "Timelines" / row["id"] / "draft_info.json"
        try:
            project = encode_project(path, name=row["label"], approval="user_confirmed")
            project["timeline"] = {
                "project": row["project"],
                "name": row["timeline"],
                "id": row["id"],
                "format": row["format"],
            }
            projects.append(project)
        except Exception as exc:
            errors.append({"project": row["label"], "error": str(exc)})
    return {
        "schema_version": "1.0",
        "generated": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "principle": "Approved export-range evidence outranks whole-draft census data.",
        "project_count": len(projects),
        "errors": errors,
        "projects": projects,
    }


def markdown_summary(brain):
    high = sum(p["evidence"]["confidence"] == "high" for p in brain["projects"])
    types = collections.Counter(p["style_type"] for p in brain["projects"])
    lines = [
        "# CapCut Style Brain",
        "",
        "> Machine-readable source: `Reference/CAPCUT_STYLE_BRAIN.json`.",
        "> Raw CapCut projects remain read-only. Approved export ranges outrank whole drafts.",
        "",
        "## Coverage",
        "",
        "- Projects encoded: %s" % brain["project_count"],
        "- High-confidence finished ranges: %s" % high,
        "- Unreadable projects: %s" % len(brain["errors"]),
        "",
        "## Style Families",
        "",
    ]
    for label, count in types.most_common():
        lines.append("- `%s`: %s" % (label, count))
    lines += ["", "## Project Fingerprints", "",
              "| Project | Style | Confidence | Range | Primary pace | Reframed |",
              "|---|---|---|---:|---:|---:|"]
    for p in brain["projects"]:
        m = p["metrics"]
        lines.append("| %s | `%s` | %s | %.1fs | %s | %.0f%% |" % (
            p["project"].replace("|", "-"), p["style_type"],
            p["evidence"]["confidence"], p["approved_range"]["duration"],
            str(m["primary_picture_duration"]["median"] or "-"),
            m["reframed_ratio"] * 100))
    lines += [
        "", "## Usage Rule", "",
        "A new brief selects the closest style family and one or more high-confidence master projects. "
        "The Timeline Planner then uses their approved-range pacing, in-point, speed, transform, text, audio, transition, and outro evidence. "
        "Saad's final correction pass is compared with the generated draft and becomes new evidence.",
    ]
    if brain["errors"]:
        lines += ["", "## Read Errors", ""]
        for row in brain["errors"]:
            lines.append("- %s: %s" % (row["project"], row["error"]))
    return "\n".join(lines) + "\n"


def self_test():
    fixture = {
        "content": json.dumps({"text": "Hello"}), "font_path": "/a/F.otf",
        "font_size": 10, "text_color": "#fff", "alignment": 1, "type": "subtitle"
    }
    assert plain_text(fixture) == "Hello"
    assert overlap(10, 10, 15, 30) == 5
    assert quantiles([1, 2, 9])["median"] == 2
    print("stylebrain core: ok")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=str(DEFAULT_JSON))
    ap.add_argument("--markdown", default=str(DEFAULT_MD))
    ap.add_argument("--test", action="store_true")
    args = ap.parse_args()
    if args.test:
        self_test()
        return
    brain = build_style_brain()
    pathlib.Path(args.json).write_text(json.dumps(brain, indent=2, ensure_ascii=False) + "\n",
                                      encoding="utf-8")
    pathlib.Path(args.markdown).write_text(markdown_summary(brain), encoding="utf-8")
    print("encoded %s projects -> %s" % (brain["project_count"], args.json))
    print("summary -> %s" % args.markdown)
    if brain["errors"]:
        print("read errors: %s" % len(brain["errors"]))


if __name__ == "__main__":
    main()
