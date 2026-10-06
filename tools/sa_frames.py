#!/usr/bin/env python3
"""Explode a video into timestamped frames + contact strips — so an agent can
read the whole motion flow of a clip image by image before planning an edit.

  python3 Tools/sa_frames.py "clip.mp4"                       # every 0.5s
  python3 Tools/sa_frames.py "clip.mp4" --interval 0.25       # denser
  python3 Tools/sa_frames.py "clip.mp4" --start 2 --end 7     # a window
  python3 Tools/sa_frames.py --test

Output (default under the session scratchpad, or --out DIR):
  <name>_frames/frames/f_0001.jpg ...   individual frames, source timecode burned in
  <name>_frames/strips/s_001.jpg ...    8x3 contact strips (24 frames each) for fast reading
  <name>_frames/index.json              frame -> approx source time map

Extraction is pure local ffmpeg; this script uploads nothing. If a hosted agent then reads
the frames, they are processed on its provider's servers, so use it only on footage cleared
for that, and never pass the frames to a generation service.
"""
import glob
import json
import os
import pathlib
import subprocess
import sys
import tempfile

FFMPEG = os.path.expanduser("~/.local/bin/ffmpeg")
if not os.path.exists(FFMPEG):
    FFMPEG = "ffmpeg"
FONT = "/System/Library/Fonts/Menlo.ttc"
SCRATCH_DEFAULT = os.environ.get("SA_FRAMES_OUT") or tempfile.gettempdir()


def explode(video, out_dir, interval=0.5, width=400, start=None, end=None, per_strip=(8, 3)):
    video = pathlib.Path(video).expanduser().resolve()
    out = pathlib.Path(out_dir)
    frames_dir, strips_dir = out / "frames", out / "strips"
    frames_dir.mkdir(parents=True, exist_ok=True)
    strips_dir.mkdir(parents=True, exist_ok=True)
    for old in list(frames_dir.glob("*.jpg")) + list(strips_dir.glob("*.jpg")):
        old.unlink()

    seek = ["-ss", str(start)] if start is not None else []
    to = ["-to", str(end)] if end is not None else []
    tc = ("drawtext=fontfile=%s:text='%%{pts\\:hms}':x=8:y=h-26:fontsize=18:"
          "fontcolor=white:box=1:boxcolor=black@0.55" % FONT)
    vf = ("%s,select='isnan(prev_selected_t)+gte(t-prev_selected_t\\,%s)',scale=%d:-2"
          % (tc, interval, width))
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", *seek, *to, "-i", str(video),
                    "-vf", vf, "-vsync", "vfr", "-q:v", "4",
                    str(frames_dir / "f_%04d.jpg")], check=True)

    frames = sorted(frames_dir.glob("f_*.jpg"))
    cols, rows = per_strip
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-pattern_type", "glob",
                    "-i", str(frames_dir / "f_*.jpg"),
                    "-vf", "tile=%dx%d" % (cols, rows), "-vsync", "vfr", "-q:v", "4",
                    str(strips_dir / "s_%03d.jpg")], check=True)

    base_t = float(start or 0)
    index = {"video": str(video), "interval": interval, "width": width,
             "frame_count": len(frames), "strips": len(list(strips_dir.glob("s_*.jpg"))),
             "frames": [{"file": f.name, "approx_t": round(base_t + i * interval, 2)}
                        for i, f in enumerate(frames)]}
    (out / "index.json").write_text(json.dumps(index, indent=1), encoding="utf-8")
    return index


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        raise SystemExit(__doc__)
    video = pathlib.Path(args[0]).expanduser()
    if not video.exists():
        raise SystemExit("no such file: %s" % video)

    def opt(name, cast, default):
        return cast(sys.argv[sys.argv.index(name) + 1]) if name in sys.argv else default

    out = opt("--out", str, os.path.join(SCRATCH_DEFAULT, video.stem + "_frames"))
    index = explode(video, out,
                    interval=opt("--interval", float, 0.5),
                    width=opt("--width", int, 400),
                    start=opt("--start", float, None),
                    end=opt("--end", float, None))
    print("%d frames -> %s" % (index["frame_count"], out))
    print("%d contact strips (24 frames each) -> %s/strips/" % (index["strips"], out))
    print("read strips first for flow; open frames/ for exact moments (timecode burned in)")


def self_test():
    with tempfile.TemporaryDirectory() as tmp:
        test_clip = os.path.join(tmp, "t.mp4")
        subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-f", "lavfi",
                        "-i", "testsrc=duration=4:size=320x180:rate=25",
                        test_clip], check=True)
        index = explode(test_clip, os.path.join(tmp, "out"), interval=0.5, width=200)
        assert 7 <= index["frame_count"] <= 9, index["frame_count"]
        assert index["strips"] >= 1
        assert index["frames"][2]["approx_t"] == 1.0
    print("sa_frames self-checks: ok")


if __name__ == "__main__":
    self_test() if "--test" in sys.argv else main()
