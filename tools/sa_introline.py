#!/usr/bin/env python3
"""Pad an AI-presenter intro line with silence so the video model never improvises.

Requirement (13 Aug 2026): the presenter must say only the scripted line, nothing extra.

Seedance fills any audio-less stretch of the clip with invented mouth movement.
Measured on the 13 Aug take: a 3.04s line in a 5.04s video moved the mouth just as
much AFTER the words ran out (5.93) as during them (5.68). The approved T01 clip
escapes it only because its line nearly fills the clip (4.20s of 5.04s).

The fix: hand the model audio for the WHOLE duration, with the slack at the END.

    1.0s silence   →   the line   →   silence to fill the clip
    video seconds  =   round(line + 2)

Measured 13 Aug: trailing silence is what fixes it — motion after the last word fell
from 5.93 to 0.50, which was Saad's complaint (the lips kept moving after the line
ended). My metric also flagged movement during the 1s head pad and I argued for
dropping it; SAAD WATCHED BOTH AND CHOSE THE 1s-HEAD BUILD.
His eye is the reference, not the metric — the head motion he does not mind, the
trailing mouthing he does. Keep HEAD at 1.0.

    sa_introline.py line.mp3                  # report only
    sa_introline.py line.mp3 -o padded.wav    # write the padded track

Print the duration it reports as the `duration` parameter of the video generation,
and upload the padded file as the audio reference.
"""
import pathlib
import subprocess
import sys

HEAD = 1.0          # Saad approved the 1s-head build. See note below.
MIN_TAIL = 0.6      # never less than this after the last word

# Requirement (13 Aug): narration at a natural, unhurried pace so the AI presenter can
# lip-sync it. The TTS engine has no speed control, so pace it here.
# CHOOSING THE TARGET — I first used the approved T01 intro line (9 words in 4.20s =
# 2.14 w/s) and it was the wrong reference: checking 30+ other narration takes,
# the normal delivery is 2.2-2.9 w/s (e.g. 40 words in 18.0s = 2.22; 43 in 15.76 =
# 2.73). T01 is an outlier on the slow side, and targeting it stretched a real line
# to its safety floor and still missed. 2.50 w/s sits inside that natural range,
# is clearly slower than the raw short-line reads (~3.2 w/s), and needs only a gentle
# stretch. Never speed a line up.
TARGET_WPS = 2.50
MIN_TEMPO = 0.75    # below this ffmpeg's atempo starts to smear the voice


def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True).stdout.strip()
    if not out:
        sys.exit(f"cannot read duration: {path}")
    return float(out)


def plan(line_seconds):
    """-> (video_seconds, head, tail). Duration must be a whole number, 4-15."""
    want = round(line_seconds + HEAD + 1.0)   # HEAD is 0, so: line + ~1s of tail
    want = max(4, min(15, want))
    tail = want - HEAD - line_seconds
    if tail < MIN_TAIL:                 # rounding went the wrong way — give it another second
        want = min(15, want + 1)
        tail = want - HEAD - line_seconds
    return want, HEAD, round(tail, 2)


def pace(src, text, dst):
    """Slow the line to Saad's reference pace. Returns (new_path, tempo, old, new)."""
    words = len([w for w in text.split() if w.strip()])
    before = probe(src)
    if not words or before <= 0:
        return src, 1.0, before, before
    tempo = max(MIN_TEMPO, min(1.0, (words / TARGET_WPS) and TARGET_WPS / (words / before)))
    if tempo >= 0.995:
        return src, 1.0, before, before          # already at or below the target pace
    subprocess.run(["ffmpeg", "-v", "error", "-i", str(src),
                    "-filter:a", f"atempo={tempo:.4f}",   # atempo preserves pitch
                    "-y", str(dst)], check=True)
    return dst, tempo, before, probe(dst)


def pad(src, dst, head, tail):
    subprocess.run(["ffmpeg", "-v", "error", "-i", str(src),
                    "-af", f"adelay={int(head*1000)}|{int(head*1000)},"
                           f"apad=pad_dur={tail}",
                    "-ar", "44100", "-y", str(dst)], check=True)
    return probe(dst)


def main():
    argv = sys.argv[1:]
    if not argv:
        sys.exit(__doc__)
    src = pathlib.Path(argv[0])
    out = None
    if "-o" in argv:
        out = pathlib.Path(argv[argv.index("-o") + 1])

    text = None
    if "--text" in sys.argv:
        text = sys.argv[sys.argv.index("--text") + 1]
    if text:
        src, tempo, was, now = pace(src, text, src.with_name(src.stem + "_paced.mp3"))
        if tempo < 1.0:
            print(f"  paced       {tempo:.2f}x   {was:.2f}s -> {now:.2f}s "
                  f"({len(text.split())/was:.2f} -> {len(text.split())/now:.2f} words/sec)")
        else:
            print(f"  paced       not needed ({len(text.split())/was:.2f} words/sec already)")
    line = probe(src)
    secs, head, tail = plan(line)
    print(f"  line        {line:5.2f}s")
    print(f"  head pad    {head:5.2f}s   (she is still, then starts)")
    print(f"  tail pad    {tail:5.2f}s   (she finishes, then holds)")
    print(f"  VIDEO       {secs}s        <- pass this as `duration`")
    if out:
        got = pad(src, out, head, tail)
        print(f"\n  wrote {out}  ({got:.2f}s)")
        if abs(got - secs) > 0.15:
            print(f"  ! padded track is {got:.2f}s but the video is {secs}s — "
                  f"the gap is where it will improvise")
    else:
        print("\n  (no -o given, nothing written)")
    return 0


def demo():
    """Self-check: the padded track always spans the whole video, never less."""
    for line in (1.4, 2.5, 3.04, 4.2, 5.9, 7.35):
        secs, head, tail = plan(line)
        total = head + line + tail
        assert abs(total - secs) < 1e-6, f"{line}: {total} != {secs}"
        assert tail >= MIN_TAIL - 1e-9, f"{line}: tail {tail} too short"
        assert 4 <= secs <= 15
    # the real case that started this: a 3.04s line -> 4s video
    assert plan(3.04)[0] == 5, plan(3.04)
    # 3.04s line -> 5s video is the build Saad approved.
    assert plan(4.2)[0] == 6, plan(4.2)
    print("demo ok")


if __name__ == "__main__":
    sys.exit(demo() if "--demo" in sys.argv else main())
