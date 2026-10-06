#!/usr/bin/env python3
"""Read the final training-series CapCut cuts and describe their construction without editing them."""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import statistics

from sa_outro import draft_path, US
from sa_transcript import DRAFTS, VIDEOS


FREEZE = re.compile(r"^[0-9a-f]{32}_\d+-sdr709\.png$", re.I)
BUILD_STILL = re.compile(r"_(?:endhold|title|signoff)\.png$", re.I)
ROLE = re.compile(r"^\s*(?:now\s+)?(?:sign\s+(?:back\s+)?in\s+as\b|sign\s+out\b)", re.I)


def parse_text(material: dict) -> dict:
    try:
        return json.loads(material.get("content") or "{}")
    except (json.JSONDecodeError, TypeError):
        return {}


def clipped(segment: dict, start: int, end: int):
    target = segment.get("target_timerange") or {}
    a = int(target.get("start", 0))
    b = a + int(target.get("duration", 0))
    if a >= end or b <= start:
        return None
    return max(a, start), min(b, end)


def seconds(value: int, export_start: int) -> float:
    return round((value - export_start) / US, 3)


def median(values: list[float]):
    return round(statistics.median(values), 3) if values else None


def audit(tag: str) -> dict:
    entry = VIDEOS[tag]
    project = entry[0]
    timeline = entry[2] if len(entry) > 2 else None
    path = (
        DRAFTS / project / "Timelines" / timeline / "draft_info.json"
        if timeline else draft_path(project)
    )
    draft = json.loads(path.read_text(encoding="utf-8"))
    export = (draft.get("config") or {}).get("export_range") or {}
    export_start = int(export.get("start", 0))
    export_duration = int(export.get("duration", 0)) or int(draft.get("duration", 0))
    export_end = export_start + export_duration

    materials = draft.get("materials") or {}
    texts = {m["id"]: m for m in materials.get("texts") or []}
    videos = {m["id"]: m for m in materials.get("videos") or []}
    audios = {m["id"]: m for m in materials.get("audios") or []}
    transitions = {m["id"]: m for m in materials.get("transitions") or []}

    caption_rows = []
    title_rows = []
    role_rows = []
    other_text = []
    callouts = []
    freezes = []
    intros = []
    outros = []
    picture_segments = []
    audio_segments = []
    transition_rows = []
    track_names = []

    for track_index, track in enumerate(draft.get("tracks") or []):
        if track.get("visible") is False:
            continue
        name = (track.get("name") or "").strip()
        track_names.append(name)
        for segment in track.get("segments") or []:
            if segment.get("visible") is False:
                continue
            bounds = clipped(segment, export_start, export_end)
            if not bounds:
                continue
            a, b = bounds
            at = seconds(a, export_start)
            dur = round((b - a) / US, 3)
            material_id = segment.get("material_id")

            if material_id in texts:
                content = parse_text(texts[material_id])
                value = (content.get("text") or "").strip()
                if not value:
                    continue
                style = (content.get("styles") or [{}])[0]
                transform = ((segment.get("clip") or {}).get("transform") or {})
                scale = ((segment.get("clip") or {}).get("scale") or {})
                font = os.path.basename(((style.get("font") or {}).get("path") or ""))
                row = {
                    "at": at, "duration": dur, "text": value,
                    "size": style.get("size"), "font": font,
                    "x": transform.get("x", 0), "y": transform.get("y", 0),
                    "scale": scale.get("x", 1), "track": name,
                }
                size = float(style.get("size") or 0)
                y = float(transform.get("y", 0))
                if size >= 10:
                    title_rows.append(row)
                elif abs(y + 0.892) < 0.06:
                    caption_rows.append(row)
                elif ROLE.match(value):
                    role_rows.append(row)
                else:
                    other_text.append(row)
                continue

            if material_id in videos:
                material = videos[material_id]
                source = material.get("path") or material.get("name") or ""
                base = os.path.basename(source)
                volume = float(segment.get("volume", 1.0))
                source_range = segment.get("source_timerange") or {}
                transform = ((segment.get("clip") or {}).get("transform") or {})
                scale = ((segment.get("clip") or {}).get("scale") or {})
                row = {
                    "at": at, "duration": dur, "file": base, "volume": round(volume, 4),
                    "source_in": round(float(source_range.get("start", 0)) / US, 3),
                    "source_duration": round(float(source_range.get("duration", 0)) / US, 3),
                    "x": transform.get("x", 0), "y": transform.get("y", 0),
                    "scale": scale.get("x", 1), "track": name, "track_index": track_index,
                }
                lower = base.casefold()
                if lower.endswith(".png"):
                    if FREEZE.match(base):
                        freezes.append(row)
                    elif not BUILD_STILL.search(base):
                        callouts.append(row)
                elif "intro_" in lower:
                    intros.append(row)
                elif "outro" in lower:
                    outros.append(row)
                elif lower.endswith((".mp4", ".mov", ".mkv", ".webm")):
                    picture_segments.append(row)

                refs = set(segment.get("extra_material_refs") or [])
                for ref in sorted(refs & transitions.keys()):
                    transition = transitions[ref]
                    transition_rows.append({
                        "at": at, "clip": base, "name": transition.get("name"),
                        "duration": round(float(transition.get("duration", 0)) / US, 3),
                    })
                continue

            if material_id in audios:
                material = audios[material_id]
                source = material.get("path") or material.get("name") or ""
                volume = float(segment.get("volume", 1.0))
                audio_segments.append({
                    "at": at, "duration": dur, "file": os.path.basename(source),
                    "volume": round(volume, 4), "track": name,
                    "kind": (
                        "signoff" if "signoff" in (source + name).casefold()
                        else "music_bed" if volume < 0.15
                        else "voice_or_program"
                    ),
                })

    callout_durations = [r["duration"] for r in callouts]
    freeze_durations = [r["duration"] for r in freezes]
    caption_styles = sorted({
        (r["size"], r["font"], round(float(r["y"]), 3), round(float(r["scale"]), 3))
        for r in caption_rows
    })
    role_phrases = [
        r["text"] for r in caption_rows
        if re.search(r"\bsign\s+(?:back\s+)?in\s+as\b|\bsign\s+out\b", r["text"], re.I)
    ]

    return {
        "tag": tag,
        "title": entry[1],
        "project": project,
        "timeline": timeline or path.parent.name,
        "draft": str(path),
        "export_start_s": round(export_start / US, 3),
        "export_duration_s": round(export_duration / US, 3),
        "canvas": [draft.get("canvas_config", {}).get("width"), draft.get("canvas_config", {}).get("height")],
        "track_count": len(draft.get("tracks") or []),
        "visible_track_names": track_names,
        "picture_segment_count": len(picture_segments),
        "picture_audio_active_count": sum(1 for r in picture_segments if r["volume"] >= 0.01),
        "picture_audio_muted_count": sum(1 for r in picture_segments if r["volume"] < 0.01),
        "intro_segments": intros,
        "outro_segments": outros,
        "transition_segments": transition_rows,
        "caption_count": len(caption_rows),
        "caption_styles": [
            {"size": s, "font": f, "y": y, "scale": scale}
            for s, f, y, scale in caption_styles
        ],
        "title_segments": title_rows,
        "role_labels": role_rows,
        "role_phrases_in_captions": role_phrases,
        "other_text": other_text,
        "callout_segment_count": len(callouts),
        "callout_unique_files": len({r["file"] for r in callouts}),
        "callout_median_hold_s": median(callout_durations),
        "callout_min_hold_s": min(callout_durations) if callout_durations else None,
        "callout_max_hold_s": max(callout_durations) if callout_durations else None,
        "callouts": callouts,
        "freeze_count": len(freezes),
        "freeze_median_hold_s": median(freeze_durations),
        "freeze_max_hold_s": max(freeze_durations) if freeze_durations else None,
        "freezes": freezes,
        "audio_segments": audio_segments,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("tags", nargs="*")
    parser.add_argument(
        "--out",
        default=str(pathlib.Path(__file__).resolve().parents[1]
                    / "Projects" / "Training_Series" / "Mastery" / "TIMELINE_AUDIT.json"),
    )
    args = parser.parse_args()
    unknown = sorted(set(args.tags) - set(VIDEOS))
    if unknown:
        parser.error(f"unknown tag(s): {', '.join(unknown)}")
    tags = args.tags or list(VIDEOS)
    rows = []
    for tag in tags:
        row = audit(tag)
        rows.append(row)
        print(
            f"{tag:<6} {row['export_duration_s']:7.2f}s  "
            f"{row['caption_count']:3d} captions  {row['callout_segment_count']:3d} call-outs  "
            f"{row['freeze_count']:2d} freezes  {len(row['role_labels']):2d} role labels"
        )
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(f"-> {out}")


if __name__ == "__main__":
    main()
