#!/usr/bin/env python3
"""Compare a generated timeline plan with Saad's finished CapCut edit.

This is the learning loop: removed/reordered clips and changes to in-points,
duration, speed and transform become explicit evidence for the next build.

  python3 Tools/sa_style_delta.py "/path/to/CapCut Project" --out style_learning/name
"""
import argparse
import collections
import json
import os
import pathlib
import statistics

US = 1_000_000


def basename(value):
    return os.path.basename(value or "")


def actual_clips(draft):
    materials = {x.get("id"): x for x in draft.get("materials", {}).get("videos", [])}
    tracks = [t for t in draft.get("tracks", [])
              if t.get("type") == "video" and t.get("segments")]
    if not tracks:
        return []
    main = max(tracks, key=lambda t: len(t["segments"]))
    export = (draft.get("config") or {}).get("export_range") or {}
    export_start = export.get("start", 0)
    export_end = export_start + export.get("duration", draft.get("duration", 0))
    rows = []
    for segment in main["segments"]:
        target = segment.get("target_timerange") or {}
        start = target.get("start", 0)
        duration = target.get("duration", 0)
        if start >= export_end or start + duration <= export_start:
            continue
        material = materials.get(segment.get("material_id"), {})
        name = basename(material.get("path") or material.get("material_name"))
        if not name or any(x in name.lower() for x in ("outro", "endcard")):
            continue
        source = segment.get("source_timerange") or {}
        clip = segment.get("clip") or {}
        scale = clip.get("scale") or {}
        transform = clip.get("transform") or {}
        rows.append({
            "file": name,
            "timeline_start": round((start - export_start) / US, 4),
            "timeline_duration": round(duration / US, 4),
            "source_start": round(source.get("start", 0) / US, 4),
            "source_duration": round(source.get("duration", 0) / US, 4),
            "speed": round(float(segment.get("speed") or 1.0), 4),
            "transform": {
                "scale_x": round(float(scale.get("x", 1.0)), 4),
                "scale_y": round(float(scale.get("y", 1.0)), 4),
                "x": round(float(transform.get("x", 0.0)), 4),
                "y": round(float(transform.get("y", 0.0)), 4),
                "rotation": round(float(clip.get("rotation", 0.0)), 4),
                "alpha": round(float(clip.get("alpha", 1.0)), 4),
            },
        })
    return sorted(rows, key=lambda x: x["timeline_start"])


def planned_clips(plan):
    for track in plan.get("tracks", []):
        if track.get("type") == "video":
            return [{**clip, "file": basename(clip.get("file"))}
                    for clip in track.get("clips", [])]
    return []


def occurrence_keys(rows):
    counts = collections.Counter()
    result = []
    for row in rows:
        counts[row["file"]] += 1
        result.append((row["file"], counts[row["file"]], row))
    return result


def delta(plan, draft):
    planned = occurrence_keys(planned_clips(plan))
    actual = occurrence_keys(actual_clips(draft))
    pmap = {(f, n): row for f, n, row in planned}
    amap = {(f, n): row for f, n, row in actual}
    shared = [key for key in pmap if key in amap]
    changes = []
    for key in shared:
        before, after = pmap[key], amap[key]
        transform_before = before.get("transform") or {}
        transform_after = after.get("transform") or {}
        changes.append({
            "file": key[0], "occurrence": key[1],
            "source_start_delta": round(after["source_start"] - before.get("source_start", 0), 4),
            "timeline_duration_delta": round(after["timeline_duration"] - before["timeline_duration"], 4),
            "speed_delta": round(after["speed"] - before.get("speed", 1.0), 4),
            "transform_changed": transform_before != transform_after,
            "before": before,
            "after": after,
        })
    planned_order = [key[:2] for key in planned if key[:2] in amap]
    actual_order = [key[:2] for key in actual if key[:2] in pmap]
    return {
        "schema_version": "1.0",
        "project": plan.get("project", ""),
        "style": plan.get("style", {}),
        "summary": {
            "planned_clips": len(planned),
            "final_clips": len(actual),
            "removed": len([k for k in pmap if k not in amap]),
            "added": len([k for k in amap if k not in pmap]),
            "reordered": planned_order != actual_order,
            "in_points_changed": sum(abs(x["source_start_delta"]) > 0.05 for x in changes),
            "durations_changed": sum(abs(x["timeline_duration_delta"]) > 0.05 for x in changes),
            "speeds_changed": sum(abs(x["speed_delta"]) > 0.01 for x in changes),
            "transforms_changed": sum(x["transform_changed"] for x in changes),
        },
        "removed": [pmap[k] for k in pmap if k not in amap],
        "added": [amap[k] for k in amap if k not in pmap],
        "changes": changes,
    }


def markdown(report):
    s = report["summary"]
    lines = [
        "# Style learning delta - %s" % report["project"], "",
        "This records Saad's taste pass against the generated timeline.", "",
        "- Planned/final clips: %s / %s" % (s["planned_clips"], s["final_clips"]),
        "- Removed/added: %s / %s" % (s["removed"], s["added"]),
        "- Reordered: %s" % ("yes" if s["reordered"] else "no"),
        "- In-points changed: %s" % s["in_points_changed"],
        "- Durations changed: %s" % s["durations_changed"],
        "- Speeds changed: %s" % s["speeds_changed"],
        "- Reframes changed: %s" % s["transforms_changed"],
        "", "| Clip | In-point delta | Duration delta | Speed delta | Reframed |",
        "|---|---:|---:|---:|---|",
    ]
    for row in report["changes"]:
        lines.append("| %s | %+.2fs | %+.2fs | %+.2fx | %s |" % (
            row["file"], row["source_start_delta"], row["timeline_duration_delta"],
            row["speed_delta"], "yes" if row["transform_changed"] else "no"))
    return "\n".join(lines) + "\n"


def self_test():
    plan = {"project": "x", "style": {}, "tracks": [{"type": "video", "clips": [
        {"file": "/a/A.mp4", "timeline_start": 0, "timeline_duration": 2,
         "source_start": 1, "source_duration": 2, "speed": 1, "transform": {}}
    ]}]}
    draft = {"duration": 3 * US, "config": {"export_range": {"start": 0, "duration": 3 * US}},
             "materials": {"videos": [{"id": "m", "path": "/a/A.mp4"}]},
             "tracks": [{"type": "video", "segments": [{"material_id": "m", "speed": 0.8,
                 "target_timerange": {"start": 0, "duration": 2500000},
                 "source_timerange": {"start": 1500000, "duration": 2000000},
                 "clip": {}}]}]}
    report = delta(plan, draft)
    assert report["summary"]["in_points_changed"] == 1
    assert report["summary"]["speeds_changed"] == 1
    print("style delta: ok")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project_dir", nargs="?")
    ap.add_argument("--plan")
    ap.add_argument("--out")
    ap.add_argument("--test", action="store_true")
    args = ap.parse_args()
    if args.test:
        self_test()
        return
    if not args.project_dir or not args.out:
        ap.error("project_dir and --out are required")
    project = pathlib.Path(args.project_dir).expanduser().resolve()
    plan_path = pathlib.Path(args.plan) if args.plan else project / "SA_TIMELINE_PLAN.json"
    draft_path = project / "draft_info.json"
    report = delta(json.loads(plan_path.read_text(encoding="utf-8")),
                   json.loads(draft_path.read_text(encoding="utf-8")))
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.with_suffix(".json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                                        encoding="utf-8")
    out.with_suffix(".md").write_text(markdown(report), encoding="utf-8")
    print("style learning -> %s" % out.with_suffix(".json"))


if __name__ == "__main__":
    main()
