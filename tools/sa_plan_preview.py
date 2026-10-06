#!/usr/bin/env python3
"""Render a silent review MP4 from an editor-neutral timeline plan."""
import argparse
import json
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from sa_assemble import FFMPEG
from sa_timeline import validate_plan


def video_clips(plan):
    for track in plan["tracks"]:
        if track.get("type") == "video" and track.get("clips"):
            return track["clips"]
    return []


def render(plan_path, output):
    plan = json.loads(pathlib.Path(plan_path).read_text(encoding="utf-8"))
    errors = validate_plan(plan)
    if errors:
        raise SystemExit("invalid plan: " + "; ".join(errors))
    clips = video_clips(plan)
    if not clips:
        raise SystemExit("plan has no video clips")
    width, height = int(plan["canvas"]["width"]), int(plan["canvas"]["height"])
    fps = float(plan["canvas"]["fps"])
    cmd = [FFMPEG, "-y", "-loglevel", "error"]
    filters = []
    labels = []
    for index, clip in enumerate(clips):
        cmd += ["-ss", str(clip.get("source_start", 0)),
                "-t", str(clip.get("source_duration", clip["timeline_duration"])),
                "-i", clip["file"]]
        speed = float(clip.get("speed") or 1.0)
        label = "v%s" % index
        filters.append(
            "[%s:v]setpts=(PTS-STARTPTS)/%s,"
            "scale=%s:%s:force_original_aspect_ratio=increase,"
            "crop=%s:%s,fps=%s,setsar=1,format=yuv420p[%s]" %
            (index, speed, width, height, width, height, fps, label))
        labels.append("[%s]" % label)
    filters.append("%sconcat=n=%s:v=1:a=0[outv]" % ("".join(labels), len(labels)))
    cmd += ["-filter_complex", ";".join(filters), "-map", "[outv]",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-movflags", "+faststart", str(output)]
    pathlib.Path(output).parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(cmd, check=True)
    print("preview -> %s" % output)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("plan")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    render(args.plan, args.out)


if __name__ == "__main__":
    main()
