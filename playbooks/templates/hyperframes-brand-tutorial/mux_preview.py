#!/usr/bin/env python3
"""Review preview: the silent render + each voice-over clip at its planned start + a music bed.

    python3 mux_preview.py build/acme_m1_timing.json renders/acme_m1.mp4 preview.mp4 \
        [--music bed.mp3] [--music-volume 0.16] [--vo-root .]

The picture stays silent and the voice stays detached, exactly as they will sit in the
editable CapCut review draft, so what the reviewer hears is what the editor will get.
A music volume of 0.16 measured about 14 dB under the voice (around -32 LUFS against
-18 LUFS) on the module this was built for; measure your own bed rather than trusting it.
The audio is padded to the picture's full length (apad=whole_dur), never cut with
-shortest. Generalised from a production preview tool that is not published; this
template version is the published one.
"""
import argparse
import json
import pathlib
import subprocess


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("timing")
    ap.add_argument("video")
    ap.add_argument("out")
    ap.add_argument("--music")
    ap.add_argument("--music-volume", type=float, default=0.16)
    ap.add_argument("--vo-root", default=".", help="folder the timing file's vo_files are relative to")
    a = ap.parse_args()

    t = json.loads(pathlib.Path(a.timing).read_text(encoding="utf-8"))
    total = float(t["total"])
    inputs, filt, labels = ["-i", a.video], [], []
    for i, (f, s) in enumerate(zip(t["vo_files"], t["vo_starts"])):
        p = pathlib.Path(a.vo_root) / f
        if not p.exists():
            raise SystemExit(f"missing voice-over clip: {p}")
        ms = int(round(float(s) * 1000))
        inputs += ["-i", str(p)]
        filt.append(f"[{i + 1}:a]adelay={ms}|{ms},aformat=channel_layouts=stereo[v{i}]")
        labels.append(f"[v{i}]")
    n = len(labels)
    if a.music:
        inputs += ["-i", a.music]
        filt.append(f"[{n + 1}:a]atrim=0:{total},volume={a.music_volume},"
                    f"afade=t=out:st={max(total - 3, 0)}:d=3,aformat=channel_layouts=stereo[m]")
        labels.append("[m]")
    filt.append("".join(labels) + f"amix=inputs={len(labels)}:normalize=0,apad=whole_dur={total}[a]")
    subprocess.run(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", ";".join(filt),
                    "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", a.out],
                   check=True)
    print(a.out)


if __name__ == "__main__":
    main()
