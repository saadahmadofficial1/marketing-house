#!/usr/bin/env python3
"""Measure the approved final MP4s themselves; never rely on timeline metadata alone."""

from __future__ import annotations

import argparse
import datetime
import json
import pathlib
import statistics

from scenedetect import ContentDetector, SceneManager, open_video


def detect(path: pathlib.Path, threshold: float) -> list[tuple[float, float]]:
    video = open_video(str(path))
    manager = SceneManager()
    manager.auto_downscale = True
    manager.add_detector(ContentDetector(threshold=threshold, min_scene_len=8))
    manager.detect_scenes(video, show_progress=False)
    return [(round(a.get_seconds(), 3), round(b.get_seconds(), 3))
            for a, b in manager.get_scene_list(start_in_scene=True)]


def quantiles(values: list[float]) -> dict:
    if not values:
        return {"min": None, "median": None, "max": None}
    return {
        "min": round(min(values), 3),
        "median": round(statistics.median(values), 3),
        "max": round(max(values), 3),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "registry", nargs="?",
        default="VIDEO_CORPUS.json",
        help="corpus JSON: {videos: [{id, family, final, duration_s}]}",
    )
    parser.add_argument(
        "--out",
        default="FINAL_VIDEO_AUDIT.json",
    )
    parser.add_argument("--threshold", type=float, default=24.0)
    parser.add_argument("--only", nargs="*")
    args = parser.parse_args()
    corpus = json.loads(pathlib.Path(args.registry).read_text(encoding="utf-8"))
    requested = set(args.only or [])
    rows = []
    for video in corpus["videos"]:
        if requested and video["id"] not in requested:
            continue
        print(f"{video['id']}: reading approved final", flush=True)
        scenes = detect(pathlib.Path(video["final"]), args.threshold)
        durations = [round(b - a, 3) for a, b in scenes]
        rows.append({
            "id": video["id"],
            "family": video["family"],
            "final": video["final"],
            "duration_s": video["duration_s"],
            "scene_threshold": args.threshold,
            "detected_scene_count": len(scenes),
            "detected_scene_duration": quantiles(durations),
            "scenes": [{"in": a, "out": b, "duration": round(b - a, 3)} for a, b in scenes],
        })
        print(
            f"{video['id']}: {len(scenes)} visual scenes, "
            f"median {quantiles(durations)['median']}s",
            flush=True,
        )
    result = {
        "authorship": "(done by codex)",
        "generated": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "note": "Scene detection is supporting evidence; CapCut cut boundaries and visual review outrank it.",
        "videos": rows,
    }
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"-> {out}")


if __name__ == "__main__":
    main()
