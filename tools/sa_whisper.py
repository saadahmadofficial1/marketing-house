#!/usr/bin/env python3
"""Local speech-to-text for a recording's own narration, via faster-whisper.

Role-based training recordings are narrated demos, so the original voice track maps 1:1 to
the finalized script beats (same things, same order — a linear flow). Whispering it
gives per-segment [start,end] in RECORDING time, which sa_align_beats turns into
correct per-beat row windows. Zero model tokens; this runs locally and uploads nothing.

    sa_whisper.py "<build folder>"            # writes transcript.json (segments)
    sa_whisper.py path/to/video.mp4 out.json

Output matches what sa_align_beats expects: a list of {start, end, text}.
"""
import json
import pathlib
import subprocess
import sys


def has_audio(video):
    out = subprocess.run(["ffprobe", "-v", "quiet", "-select_streams", "a",
                          "-show_entries", "stream=index", "-of", "csv=p=0", str(video)],
                         capture_output=True, text=True).stdout.strip()
    return bool(out)


def resolve_video(folder):
    """SRC30.mp4 is the CFR re-encode and has NO audio track. When asked for a folder,
    prefer SRC30 only if it kept audio; otherwise fall back to the original the pipeline
    recorded in SOURCE.txt (same duration/timing, just with the narration)."""
    src30 = folder / "SRC30.mp4"
    if src30.exists() and has_audio(src30):
        return src30
    srctxt = folder / "SOURCE.txt"
    if srctxt.exists():
        orig = pathlib.Path(srctxt.read_text().strip().splitlines()[0])
        if orig.exists() and has_audio(orig):
            return orig
    return src30      # last resort; will error loudly if truly no audio anywhere


def transcribe(video, model="base.en"):
    from faster_whisper import WhisperModel
    wav = pathlib.Path(video).with_suffix(".whisper.wav")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(video), "-vn",
                    "-ac", "1", "-ar", "16000", str(wav)], check=True)
    m = WhisperModel(model, device="cpu", compute_type="int8")
    segs, _ = m.transcribe(str(wav), vad_filter=True)
    out = [{"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip()} for s in segs]
    wav.unlink(missing_ok=True)
    return out


if __name__ == "__main__":
    arg = sys.argv[1]
    p = pathlib.Path(arg)
    if p.is_dir():
        video = resolve_video(p)
        out = p / "transcript.json"
    else:
        video = p
        out = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else p.with_suffix(".transcript.json")
    segs = transcribe(video)
    out.write_text(json.dumps(segs, indent=1))
    print(f"{len(segs)} segments -> {out}")
    for s in segs[:3]:
        print(f"  {s['start']:.1f}-{s['end']:.1f}  {s['text'][:64]}")
