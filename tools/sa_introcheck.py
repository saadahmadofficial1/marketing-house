#!/usr/bin/env python3
"""Download an AI-presenter intro clip and check the three things that have gone wrong.

The intro pipeline failed in three distinct ways over 13-14 Aug, and each failure
was only visible in a different place:

  1. resolution   `resolution` silently defaults to 720p. Saad's series is 1080p.
  2. burnt text   Seedance transcribed the voice-over onto the wall in one intro
                  (1 of 9). Invisible to a duration check, obvious as edge energy
                  in the empty left third: clean = 0.0000, the bad take = 0.0403.
  3. framing      She must be RIGHT of frame, never centred (Saad's rule,
                  13 Aug). Measured as where the dark suit sits.

    sa_introcheck.py <url> <output.mp4> [expected_seconds]

Exit 0 = clean, 1 = something to look at. Prints frame paths to Read afterwards.
"""
import os
import pathlib
import subprocess
import sys
import urllib.request

# Requirement (20 Aug): the approved set is consistent — measure every new clip against it.
# centre 73.2%, subject width 30.2%, left clear 58.1%. A clip outside these read to him as
# centred rather than to the side (one clip, caused by passing a second reference image).
APPROVED_CENTRE = (72.5, 74.0)
APPROVED_WIDTH  = (29.5, 31.0)

RAW = pathlib.Path(os.environ.get("TRAINING_ROOT", "~/Downloads/training-series")).expanduser() / "3 ASSETS" / "intro raw"


def probe(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True).stdout.split()
    return int(out[0]), int(out[1]), float(out[2])


def ink(png, crop):
    """Mean edge energy in a crop. Text on a blank wall lights this up."""
    out = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(png), "-vf",
         f"crop={crop},edgedetect=low=0.1:high=0.3", "-f", "rawvideo",
         "-pix_fmt", "gray", "-"], capture_output=True).stdout
    return sum(out) / len(out) / 255 if out else 0.0


def darkness(png, crop):
    """Mean darkness in a crop — the navy suit is the darkest thing in frame."""
    out = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(png), "-vf", f"crop={crop}",
         "-f", "rawvideo", "-pix_fmt", "gray", "-"], capture_output=True).stdout
    return 1 - (sum(out) / len(out) / 255) if out else 0.0


def main():
    url, dst = sys.argv[1], RAW / sys.argv[2]
    want = float(sys.argv[3]) if len(sys.argv) > 3 else None
    urllib.request.urlretrieve(url, dst)

    w, h, dur = probe(dst)
    frames = pathlib.Path("/tmp/introcheck")
    subprocess.run(["rm", "-rf", str(frames)])
    frames.mkdir(parents=True)
    subprocess.run(["ffmpeg", "-v", "error", "-i", str(dst), "-vf", "fps=1",
                    str(frames / "f%02d.png")], check=True)
    shots = sorted(frames.glob("*.png"))

    bad = []
    print(f"  {dst.name}")
    print(f"  {w}x{h}  {dur:.2f}s")
    if h < 1080:
        bad.append(f"{h}p — `resolution` defaulted again, must be 1080p")
    if want and abs(dur - want) > 0.3:
        bad.append(f"{dur:.2f}s but the padded audio is {want:.2f}s — she will improvise in the gap")

    worst = max(ink(p, "iw/3:ih:0:0") for p in shots)
    print(f"  left-third ink   {worst:.4f}   (0.0000 = blank wall, 0.04 = text burnt in)")
    if worst > 0.006:
        bad.append(f"text on the wall (ink {worst:.4f})")

    left = sum(darkness(p, "iw/2:ih:0:0") for p in shots) / len(shots)
    right = sum(darkness(p, "iw/2:ih:iw/2:0") for p in shots) / len(shots)
    side = "RIGHT" if right > left else "LEFT"
    print(f"  she is on the    {side}   (dark {left:.3f} left vs {right:.3f} right)")
    if side != "RIGHT":
        bad.append("she is not on the right of frame")

    for b in bad:
        print(f"  ! {b}")
    if not bad:
        print("  clean")
    print(f"  frames: {frames}/")
    return 1 if bad else 0


def demo():
    """Self-check on the two clips we know the answer for."""
    good = RAW / "INTRO_APPROVED_reference.mp4"
    if not good.exists():
        print("demo skipped (reference clip not on this machine)"); return
    frames = pathlib.Path("/tmp/introcheck_demo")
    subprocess.run(["rm", "-rf", str(frames)]); frames.mkdir(parents=True)
    subprocess.run(["ffmpeg", "-v", "error", "-i", str(good), "-vf", "fps=1",
                    str(frames / "f%02d.png")], check=True)
    p = sorted(frames.glob("*.png"))[0]
    assert ink(p, "iw/3:ih:0:0") < 0.006, "an approved clip must read as clean"
    assert darkness(p, "iw/2:ih:iw/2:0") > darkness(p, "iw/2:ih:0:0"), \
        "the suit must be on the right half"
    assert probe(good)[1] == 1080
    print("demo ok (approved clip reads clean, right-framed, 1080p)")


if __name__ == "__main__":
    sys.exit(demo() if "--demo" in sys.argv else main())
