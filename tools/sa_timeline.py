#!/usr/bin/env python3
"""Create and validate editor-neutral timeline plans from the Style Brain.

This planner is intentionally review-first. It uses learned CapCut timing,
speed, in-point and transform evidence, but marks choices that were not backed
by a reviewed cutsheet.

  python3 Tools/sa_timeline.py plan FOOTAGE --name "Project" --style luxury_event_reel
  python3 Tools/sa_timeline.py validate Projects/Project/timeline_plan.json
"""
import argparse
import json
import os
import pathlib
import statistics
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from sa_assemble import VIDEO_EXT, probe

ROOT = pathlib.Path(__file__).resolve().parents[1]
STYLE_BRAIN = ROOT / "Reference" / "CAPCUT_STYLE_BRAIN.json"

STYLE_ALIASES = {
    "tutorial_a": "tutorial_short_walkthrough",
    "tutorial_b": "training_animation",
    "tribute": "tribute_farewell",
    "event": "luxury_event_reel",
}


def load_json(path):
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def validate_plan(plan):
    errors = []
    if plan.get("schema_version") != "1.0":
        errors.append("schema_version must be 1.0")
    if not plan.get("project"):
        errors.append("project is required")
    canvas = plan.get("canvas") or {}
    for key in ("width", "height", "fps"):
        if not isinstance(canvas.get(key), (int, float)) or canvas[key] <= 0:
            errors.append("canvas.%s must be positive" % key)
    tracks = plan.get("tracks")
    if not isinstance(tracks, list) or not tracks:
        errors.append("tracks must be a non-empty list")
        return errors
    allowed = {"video", "audio", "text", "effect", "filter"}
    for ti, track in enumerate(tracks):
        if track.get("type") not in allowed:
            errors.append("tracks[%s].type is invalid" % ti)
        if not isinstance(track.get("clips"), list):
            errors.append("tracks[%s].clips must be a list" % ti)
            continue
        previous_end = 0.0
        for ci, clip in enumerate(track["clips"]):
            prefix = "tracks[%s].clips[%s]" % (ti, ci)
            start = clip.get("timeline_start")
            duration = clip.get("timeline_duration")
            if not isinstance(start, (int, float)) or start < 0:
                errors.append(prefix + ".timeline_start must be >= 0")
            if not isinstance(duration, (int, float)) or duration <= 0:
                errors.append(prefix + ".timeline_duration must be > 0")
            if track.get("type") in ("video", "audio") and not clip.get("file"):
                errors.append(prefix + ".file is required")
            if isinstance(start, (int, float)) and isinstance(duration, (int, float)):
                if track.get("type") == "video" and start < previous_end - 0.001:
                    errors.append(prefix + " overlaps the previous clip on the same video track")
                previous_end = max(previous_end, start + duration)
    return errors


def choose_master(brain, style, explicit=None):
    if explicit:
        for project in brain["projects"]:
            if project["project"].lower() == explicit.lower():
                return project
        raise SystemExit("master project not found in Style Brain: %s" % explicit)
    canonical = STYLE_ALIASES.get(style, style)
    matches = [p for p in brain["projects"] if p["style_type"] == canonical]
    if not matches:
        raise SystemExit("no Style Brain project for style: %s" % canonical)
    rank = {"high": 2, "medium": 1, "low": 0}
    matches.sort(key=lambda p: (
        rank.get(p["evidence"]["confidence"], 0),
        p["metrics"]["primary_picture_segments"]
    ), reverse=True)
    return matches[0]


def master_templates(master):
    primary = master["metrics"].get("primary_video_track")
    rows = [s for s in master["segments"]
            if s["track_type"] == "video" and s["track_index"] == primary
            and s["role"] != "outro"]
    rows.sort(key=lambda s: s["timeline_start"])
    return rows


def cutsheet_map(path):
    if not path:
        return {}
    rows = load_json(path)
    automated = isinstance(rows, dict)
    if automated:
        rows = rows.get("clips", [])
    for row in rows:
        row.setdefault("_human_reviewed", not automated)
    return {row.get("file"): row for row in rows if row.get("file") and "error" not in row}


def typical_source_ratio(master):
    value = master["metrics"].get("source_in_ratio", {}).get("median")
    return min(max(value if value is not None else 0.35, 0.0), 0.9)


def make_plan(footage, name, style, master_name=None, cutsheet=None,
              max_clips=None, target_duration=None, brief="", selected_files=None):
    brain = load_json(STYLE_BRAIN)
    master = choose_master(brain, style, master_name)
    templates = master_templates(master)
    if not templates:
        raise SystemExit("selected master has no primary picture sequence")
    folder = pathlib.Path(footage).expanduser().resolve()
    allowed = {x.lower() for x in VIDEO_EXT}
    if selected_files:
        files = [folder / name for name in selected_files]
        missing = [str(p) for p in files if not p.is_file() or p.suffix.lower() not in allowed]
        if missing:
            raise SystemExit("selected footage missing: %s" % ", ".join(missing))
    else:
        files = sorted(p for p in folder.iterdir() if p.suffix.lower() in allowed)
    if max_clips:
        files = files[:max_clips]
    if not files:
        raise SystemExit("no video files found in %s" % folder)
    reviewed = cutsheet_map(cutsheet)
    fallback_ratio = typical_source_ratio(master)
    clips = []
    timeline = 0.0
    for index, path in enumerate(files):
        if target_duration and timeline >= target_duration:
            break
        duration, width, height = probe(str(path))
        template = templates[index % len(templates)]
        row = reviewed.get(path.name)
        if row:
            source_start = float(row.get("suggested_in", 0))
            proposed_out = float(row.get("suggested_out", source_start))
            source_duration = max(proposed_out - source_start, 0.1)
            speed = float(row.get("suggested_speed") or template.get("speed") or 1.0)
            human_reviewed = bool(row.get("reviewed", row.get("_human_reviewed", False)))
            evidence = ("human-reviewed cutsheet suggestion" if human_reviewed else
                        "automatic multi-frame extraction; quality %s/100, confidence %s" %
                        (row.get("quality_score", "unknown"), row.get("confidence", "unknown")))
            needs_review = not human_reviewed
        else:
            speed = float(template.get("speed") or 1.0)
            desired_timeline = float(template.get("timeline_duration") or 3.0)
            source_duration = desired_timeline * speed
            source_start = max((duration - source_duration) * fallback_ratio, 0.0)
            evidence = "Style Brain template from %s; visual moment not reviewed" % master["project"]
            needs_review = True
        if master["style_type"] == "luxury_event_reel" and index > 0:
            minimum_hold = 1.5 if index == len(files) - 1 else 0.9
            learned_timeline = source_duration / speed
            if learned_timeline < minimum_hold:
                source_duration = minimum_hold * speed
                if not row:
                    source_start = max((duration - source_duration) * fallback_ratio, 0.0)
                evidence += "; luxury readability floor %.1fs" % minimum_hold
        if duration > 0:
            source_start = min(source_start, max(duration - 0.1, 0.0))
            source_duration = min(source_duration, max(duration - source_start, 0.1))
        timeline_duration = source_duration / speed
        if target_duration:
            timeline_duration = min(timeline_duration, target_duration - timeline)
            source_duration = timeline_duration * speed
        if timeline_duration <= 0:
            continue
        transition = (template.get("transitions") or [None])[0]
        if (not transition and master["style_type"] == "luxury_event_reel"
                and index > 0 and index % 4 == 0):
            ranked = master["metrics"].get("transitions") or {}
            transition = next(iter(ranked), None)
        role = "opener" if not clips else "picture"
        clips.append({
            "file": str(path),
            "role": role,
            "timeline_start": round(timeline, 4),
            "timeline_duration": round(timeline_duration, 4),
            "source_start": round(source_start, 4),
            "source_duration": round(source_duration, 4),
            "speed": round(speed, 4),
            "transform": dict(template.get("transform") or {}),
            "transition": transition,
            "needs_review": needs_review,
            "evidence": evidence,
            "source_dimensions": {"width": width, "height": height},
        })
        timeline += timeline_duration
    if clips:
        clips[-1]["role"] = "closer"
    canvas = master["canvas"]
    return {
        "schema_version": "1.0",
        "project": name,
        "brief": brief,
        "canvas": {
            "width": int(canvas.get("width") or 1920),
            "height": int(canvas.get("height") or 1080),
            "fps": float(canvas.get("fps") or 30),
        },
        "style": {
            "type": master["style_type"],
            "masters": [master["project"]],
            "confidence": master["evidence"]["confidence"],
        },
        "review": {
            "required": any(c["needs_review"] for c in clips),
            "reviewed_cutsheet": str(cutsheet or ""),
            "note": "Approve clip order, in-points and roles before production use.",
        },
        "tracks": [{"type": "video", "name": "Main picture", "clips": clips}],
    }


def review_markdown(plan):
    clips = plan["tracks"][0]["clips"]
    lines = [
        "# Timeline review - %s" % plan["project"], "",
        "- Style: `%s`" % plan["style"]["type"],
        "- Master: %s" % ", ".join(plan["style"]["masters"]),
        "- Review required: %s" % ("YES" if plan["review"]["required"] else "no"),
        "", "| # | Role | File | Timeline | Source | Speed | Transition | Review |",
        "|---:|---|---|---:|---:|---:|---|---|",
    ]
    for i, clip in enumerate(clips, 1):
        lines.append("| %s | %s | %s | %.2fs @ %.2fs | %.2fs-%.2fs | %.2fx | %s | %s |" % (
            i, clip["role"], pathlib.Path(clip["file"]).name,
            clip["timeline_duration"], clip["timeline_start"],
            clip["source_start"], clip["source_start"] + clip["source_duration"],
            clip["speed"], clip.get("transition") or "-",
            "CHECK" if clip["needs_review"] else "cutsheet"))
    return "\n".join(lines) + "\n"


def self_test():
    good = {
        "schema_version": "1.0", "project": "x",
        "canvas": {"width": 1080, "height": 1920, "fps": 30},
        "style": {"type": "x", "masters": ["y"]},
        "tracks": [{"type": "video", "clips": [{
            "file": "/tmp/a.mp4", "timeline_start": 0,
            "timeline_duration": 2, "source_start": 1, "source_duration": 2,
        }]}],
    }
    assert validate_plan(good) == []
    bad = json.loads(json.dumps(good))
    bad["tracks"][0]["clips"][0]["timeline_duration"] = 0
    assert validate_plan(bad)
    print("timeline validation: ok")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", action="store_true")
    sub = ap.add_subparsers(dest="command")
    make = sub.add_parser("plan")
    make.add_argument("footage")
    make.add_argument("--name", required=True)
    make.add_argument("--style", required=True)
    make.add_argument("--master")
    make.add_argument("--cutsheet")
    make.add_argument("--max-clips", type=int)
    make.add_argument("--duration", type=float)
    make.add_argument("--brief", default="")
    make.add_argument("--files", nargs="+",
                      help="selected clip filenames in intentional story order")
    make.add_argument("--out", required=True)
    check = sub.add_parser("validate")
    check.add_argument("plan")
    args = ap.parse_args()
    if args.test:
        self_test()
        return
    if args.command == "validate":
        errors = validate_plan(load_json(args.plan))
        if errors:
            print("\n".join("ERROR: " + e for e in errors))
            raise SystemExit(1)
        print("timeline plan valid")
        return
    if args.command != "plan":
        ap.print_help()
        raise SystemExit(2)
    plan = make_plan(args.footage, args.name, args.style, args.master,
                     args.cutsheet, args.max_clips, args.duration, args.brief,
                     args.files)
    errors = validate_plan(plan)
    if errors:
        raise SystemExit("invalid generated plan: " + "; ".join(errors))
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    out.with_suffix(".md").write_text(review_markdown(plan), encoding="utf-8")
    print("timeline plan -> %s" % out)
    print("review sheet -> %s" % out.with_suffix(".md"))


if __name__ == "__main__":
    main()
