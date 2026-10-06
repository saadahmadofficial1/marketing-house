#!/usr/bin/env python3
"""Narrated slide explainer -> MP4.

Re-runnable: edit SCENES, run again, get a new video. Details change, so nothing
here is hand-made in an editor.

  python3 sa_explainer_build.py

Pipeline: SCENES -> script.srt -> sa_vo (edge-tts, en-GB) -> Pillow slides ->
ffmpeg segments -> concat -> explainer.mp4

ponytail: slides drawn with Pillow, not a headless browser — a text-only layout
does not need a render engine.
"""
import os, re, subprocess, sys, shutil
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
# the folder holding sa_vo.py; override with SA_TOOLS
TOOLS = os.path.expanduser(os.environ.get("SA_TOOLS", HERE))
PY = sys.executable
FFMPEG = os.path.expanduser("~/.local/bin/ffmpeg")
VOICE = "en-GB-RyanNeural"
GAP = 0.55                      # silence held after each line
W, H, FPS = 1920, 1080, 30
PAD = 170

GREEN = (27, 58, 75)            # deep slate #1B3A4B — set your own palette here
IVORY = (244, 241, 234)
SAND  = (184, 155, 94)
MUTED = (176, 189, 184)         # ivory at ~70% over the green

SERIF = ["/System/Library/Fonts/Supplemental/Georgia.ttf"]
SANS  = ["/System/Library/Fonts/Supplemental/Arial.ttf"]

# (kicker, headline — "|" is a line break, supporting line, voiceover)
SCENES = [
    ("Example explainer",
     "One idea|per slide",
     "Edit SCENES, run the script again, get a new video",
     "Each slide carries one idea. Edit the list, run the script again, and you get a new video."),

    ("How it is built",
     "Script. Voice.|Slides. Cut.",
     "script.srt · edge-tts voice-over · Pillow slides · ffmpeg segments · one concat",
     "The scenes become a subtitle file, the subtitle file becomes a voice-over, and each line gets its own slide, timed to its own voice."),

    ("Why it is re-runnable",
     "Nothing made|by hand",
     "When the details change, change one line and rebuild — the voice-over is only re-cut if the words changed",
     "Nothing is hand-made in an editor. When the details change, you change one line and build it again."),

    ("Your turn",
     "Replace|these scenes",
     "Kicker, headline, supporting line, voice-over: four strings per slide",
     "Replace these scenes with your own, and run it again."),
]


def typo(s):
    """Straight quotes and hyphens are a giveaway on a screen. Fix on the way in."""
    s = s.replace("'", "\u2019")
    return re.sub(r"(\d)\s*-\s*(\d)", "\\1\u2013\\2", s)


def font(paths, size):
    for p in paths:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    sys.exit(f"no font found in {paths}")


def wrap(draw, text, fnt, max_w):
    words, lines, cur = text.split(), [], ""
    for word in words:
        trial = f"{cur} {word}".strip()
        if draw.textlength(trial, font=fnt) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def tracked(draw, xy, text, fnt, fill, spacing):
    """Draw text with letter-spacing — Pillow has no tracking of its own."""
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=fnt, fill=fill)
        x += draw.textlength(ch, font=fnt) + spacing
    return x


def draw_slide(path, kicker, headline, small, n, total):
    kicker, headline, small = typo(kicker), typo(headline), typo(small)
    img = Image.new("RGB", (W, H), GREEN)
    d = ImageDraw.Draw(img)

    head_lines = headline.split("|")
    longest = max(len(l) for l in head_lines)
    size = 172 if longest <= 12 else (132 if longest <= 26 else 106)
    f_head = font(SERIF, size)
    f_kick = font(SANS, 25)
    f_small = font(SANS, 30)
    f_foot = font(SANS, 19)

    lead = int(size * 1.08)
    # breathing room under the headline has to scale with it — a fixed gap
    # leaves a 172px line almost touching the line below
    gap_after_head = int(size * 0.42)
    small_lines = wrap(d, small, f_small, W - PAD * 2 - 560)

    block = (3 + 44 + 32 + 40 + len(head_lines) * lead - (lead - size)
             + gap_after_head + len(small_lines) * 48)
    y = (H - block) // 2

    d.rectangle([PAD, y, PAD + 70, y + 3], fill=SAND)
    y += 3 + 44
    tracked(d, (PAD, y), kicker.upper(), f_kick, SAND, 5.2)
    y += 32 + 40

    for line in head_lines:
        d.text((PAD, y), line, font=f_head, fill=IVORY)
        y += lead
    y += gap_after_head - (lead - size)

    for line in small_lines:
        d.text((PAD, y), line, font=f_small, fill=MUTED)
        y += 48

    d.text((PAD, H - 100), f"{n:02d} / {total:02d}", font=f_foot, fill=SAND)
    mark = "YOUR BRAND"
    d.text((W - PAD - d.textlength(mark, font=f_foot) - 24, H - 100),
           mark, font=f_foot, fill=(96, 122, 116))
    img.save(path)


def sh(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"FAILED: {' '.join(cmd[:4])}\n{r.stderr[-1500:]}")
    return r


def srt_ts(sec):
    ms = int(round(sec * 1000))
    return f"{ms//3600000:02d}:{ms//60000%60:02d}:{ms//1000%60:02d},{ms%1000:03d}"


def dur(p):
    out = subprocess.run([FFMPEG, "-i", p], capture_output=True, text=True).stderr
    h, m, s = re.search(r"Duration: (\d+):(\d+):(\d+\.?\d*)", out).groups()
    return int(h) * 3600 + int(m) * 60 + float(s)


def main():
    vo_dir, png_dir, seg_dir = (os.path.join(HERE, x) for x in ("VO", "slides", "segments"))
    for x in (png_dir, seg_dir):
        shutil.rmtree(x, ignore_errors=True)
        os.makedirs(x)

    srt = os.path.join(HERE, "script.srt")
    open(srt, "w").write("\n\n".join(
        f"{i}\n{srt_ts(i*5)} --> {srt_ts(i*5+4)}\n{s[3]}"
        for i, s in enumerate(SCENES, 1)) + "\n")

    # ponytail: only re-cut VO when the script changed — slide tweaks are the
    # common case and edge-tts is the slow step
    stamp = f"{vo_dir}/.script"
    have = os.path.exists(stamp) and all(
        os.path.exists(f"{vo_dir}/{i:02d}.mp3") for i in range(1, len(SCENES) + 1))
    if have and open(srt).read() == open(stamp).read():
        print("voiceover… unchanged, reusing")
    else:
        print("voiceover…")
        shutil.rmtree(vo_dir, ignore_errors=True)
        sh([PY, f"{TOOLS}/sa_vo.py", srt, vo_dir, "--voice", VOICE, "--gap", str(GAP)])
        open(f"{vo_dir}/.script", "w").write(open(srt).read())

    print("slides…")
    for i, (kicker, head, small, _) in enumerate(SCENES, 1):
        draw_slide(f"{png_dir}/{i:02d}.png", kicker, head, small, i, len(SCENES))

    print("segments…")
    listing = []
    for i in range(1, len(SCENES) + 1):
        mp3 = f"{vo_dir}/{i:02d}.mp3"
        d = dur(mp3) + GAP
        seg = f"{seg_dir}/{i:02d}.mp4"
        sh([FFMPEG, "-y", "-loop", "1", "-framerate", str(FPS),
            "-i", f"{png_dir}/{i:02d}.png", "-i", mp3, "-t", f"{d:.3f}",
            "-vf", f"fade=t=in:st=0:d=0.4,fade=t=out:st={d-0.4:.3f}:d=0.4,format=yuv420p",
            "-af", f"apad,atrim=0:{d:.3f}",
            "-c:v", "libx264", "-preset", "medium", "-crf", "19",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-r", str(FPS), seg])
        # ponytail: basenames only — a project path may contain an apostrophe
        # ("Team's") and the concat demuxer would choke on it
        listing.append(f"file '{i:02d}.mp4'")
        print(f"  {i:02d}  {d:5.1f}s")

    open(os.path.join(seg_dir, "list.txt"), "w").write("\n".join(listing) + "\n")
    out = os.path.join(HERE, "explainer.mp4")
    r = subprocess.run([FFMPEG, "-y", "-f", "concat", "-safe", "0",
                        "-i", "list.txt", "-c", "copy", out],
                       capture_output=True, text=True, cwd=seg_dir)
    if r.returncode:
        sys.exit(f"concat failed:\n{r.stderr[-1500:]}")
    print(f"\n{out}   {dur(out):.0f}s")


if __name__ == "__main__":
    main()
