#!/usr/bin/env python3
"""Render a timeline-plan JSON (playbooks/templates/timeline_plan.schema.json) straight to a cut MP4 — no NLE needed.

  Tools/venv/bin/python3 Tools/sa_cut_render.py plan.json out.mp4 [--speed 1.0]

Cuts each clip's source window and concatenates them in timeline order.
Head/tail gaps in the plan are ignored (they're for the NLE); use --gap-black
to render them as black instead. Read-only on the source.
"""
import json, subprocess, sys, pathlib, os

def main():
    plan_p, out = sys.argv[1], sys.argv[2]
    speed = 1.0
    if "--speed" in sys.argv:
        speed = float(sys.argv[sys.argv.index("--speed") + 1])
    plan = json.load(open(plan_p))
    clips = [c for t in plan["tracks"] if t.get("type") == "video" for c in t["clips"]]
    clips.sort(key=lambda c: c["timeline_start"])
    src = clips[0]["file"]
    parts = []
    fc = []
    for i, c in enumerate(clips):
        a, d = c["source_start"], c["source_duration"]
        fc.append(f"[0:v]trim=start={a}:duration={d},setpts=PTS-STARTPTS[v{i}]")
        fc.append(f"[0:a]atrim=start={a}:duration={d},asetpts=PTS-STARTPTS[a{i}]")
        parts.append(f"[v{i}][a{i}]")
    n = len(clips)
    fc.append("".join(parts) + f"concat=n={n}:v=1:a=1[vc][ac]")
    if speed != 1.0:
        fc.append(f"[vc]setpts={1/speed}*PTS[vo]")
        fc.append(f"[ac]atempo={speed}[ao]")
        vmap, amap = "[vo]", "[ao]"
    else:
        vmap, amap = "[vc]", "[ac]"
    cmd = ["ffmpeg", "-y", "-v", "error", "-stats", "-i", src,
           "-filter_complex", ";".join(fc),
           "-map", vmap, "-map", amap,
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", out]
    subprocess.run(cmd, check=True)
    dur = subprocess.run(["ffprobe","-v","error","-show_entries","format=duration",
                          "-of","csv=p=0",out],capture_output=True,text=True).stdout.strip()
    print(f"\n-> {out}  ({float(dur):.1f}s, {n} sections)")

if __name__ == "__main__":
    main()
