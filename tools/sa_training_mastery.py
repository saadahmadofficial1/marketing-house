#!/usr/bin/env python3
"""Build a read-only evidence manifest for a finished screen-recorded training series.

The final exported MP4 is the authority.  CapCut captions are useful production data, but
they are never allowed to redefine the final runtime.  Optional local Whisper output
is written under the requested workspace folder; this check runs locally and uploads nothing.
"""

from __future__ import annotations

import argparse
import difflib
import json
import pathlib
import re
import subprocess
from typing import Iterable


# tag -> a phrase unique to that video's delivered folder name (example entries)
MODULE_HINTS = {
    "MOD01": "Example Module One",
    "MOD02": "Example Module Two",
}


def norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def locate(root: pathlib.Path, hint: str) -> pathlib.Path:
    matches = [p for p in root.iterdir() if p.is_dir() and norm(hint) in norm(p.name)]
    if len(matches) != 1:
        raise RuntimeError(f"{hint!r}: expected one delivered folder, found {matches}")
    videos = sorted(matches[0].glob("*.mp4"))
    if len(videos) != 1:
        raise RuntimeError(f"{matches[0]}: expected one final MP4, found {videos}")
    return videos[0]


def probe(path: pathlib.Path) -> dict:
    cmd = [
        "ffprobe", "-v", "error", "-show_entries",
        "format=duration:stream=index,codec_type,codec_name,width,height,r_frame_rate,sample_rate,channels",
        "-of", "json", str(path),
    ]
    data = json.loads(subprocess.check_output(cmd, text=True))
    duration = round(float(data["format"]["duration"]), 3)
    video = next((s for s in data["streams"] if s.get("codec_type") == "video"), {})
    audio = next((s for s in data["streams"] if s.get("codec_type") == "audio"), {})
    return {
        "duration_s": duration,
        "width": video.get("width"),
        "height": video.get("height"),
        "fps": video.get("r_frame_rate"),
        "video_codec": video.get("codec_name"),
        "audio_codec": audio.get("codec_name"),
        "sample_rate": int(audio["sample_rate"]) if audio.get("sample_rate") else None,
        "channels": audio.get("channels"),
    }


def stamp(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:06.3f}".replace(".", ",")


def flatten_captions(captions: Iterable[dict]) -> str:
    return " ".join(str(c.get("text", "")).strip() for c in captions).strip()


def words(value: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", value.casefold())


def similarity(a: str, b: str) -> float:
    return round(difflib.SequenceMatcher(None, words(a), words(b)).ratio(), 4)


def transcribe(path: pathlib.Path, model, language: str = "en") -> list[dict]:
    segments, _info = model.transcribe(
        str(path), language=language, vad_filter=True, word_timestamps=False
    )
    return [
        {"in": round(s.start, 3), "out": round(s.end, 3), "text": s.text.strip()}
        for s in segments
    ]


def write_audio_evidence(out: pathlib.Path, tag: str, segments: list[dict]) -> None:
    folder = out / "Actual_Audio"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{tag}.json").write_text(json.dumps(segments, indent=2), encoding="utf-8")
    (folder / f"{tag}.txt").write_text(
        " ".join(s["text"] for s in segments) + "\n", encoding="utf-8"
    )
    cues = []
    for index, segment in enumerate(segments, 1):
        cues.append(
            f"{index}\n{stamp(segment['in'])} --> {stamp(segment['out'])}\n"
            f"{segment['text']}\n"
        )
    (folder / f"{tag}.srt").write_text("\n".join(cues), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root", default="~/Downloads/Training Videos",
        help="Folder containing one sub-folder per delivered video",
    )
    parser.add_argument(
        "--out",
        default="Projects/Training_Series/Mastery",
    )
    parser.add_argument("--transcribe", action="store_true")
    parser.add_argument("--model", default="small", choices=("tiny", "base", "small", "medium"))
    args = parser.parse_args()

    root = pathlib.Path(args.root).expanduser()
    out = pathlib.Path(args.out).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    caption_file = out / "Transcripts" / "ALL_TRANSCRIPTS.json"
    captions = {row["tag"]: row for row in json.loads(caption_file.read_text(encoding="utf-8"))}

    whisper = None
    if args.transcribe:
        from faster_whisper import WhisperModel
        whisper = WhisperModel(args.model, device="cpu", compute_type="int8")

    rows = []
    for tag, hint in MODULE_HINTS.items():
        path = locate(root, hint)
        row = {"tag": tag, "file": str(path), **probe(path)}
        cap = captions[tag]
        row.update({
            "title": cap["title"],
            "timeline_runtime_s": cap["runtime_s"],
            "timeline_vs_final_s": round(cap["runtime_s"] - row["duration_s"], 3),
            "caption_count": cap["caption_count"],
            "caption_words": cap["word_count"],
            "title_card": cap.get("title_card", []),
        })

        audio_file = out / "Actual_Audio" / f"{tag}.json"
        if args.transcribe and not audio_file.exists():
            print(f"{tag}: transcribing {row['duration_s']:.1f}s", flush=True)
            write_audio_evidence(out, tag, transcribe(path, whisper))
        if audio_file.exists():
            actual = json.loads(audio_file.read_text(encoding="utf-8"))
            actual_text = flatten_captions(actual)
            expected_text = flatten_captions(cap["captions"])
            row.update({
                "actual_audio_segments": len(actual),
                "actual_audio_words": len(words(actual_text)),
                "caption_audio_similarity": similarity(expected_text, actual_text),
                "actual_speech_in_s": actual[0]["in"] if actual else None,
                "actual_speech_out_s": actual[-1]["out"] if actual else None,
            })
        rows.append(row)
        print(
            f"{tag:<6} final {row['duration_s']:7.3f}s  "
            f"timeline delta {row['timeline_vs_final_s']:+.3f}s",
            flush=True,
        )

    (out / "TRAINING_MASTER_DATA.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(f"-> {out / 'TRAINING_MASTER_DATA.json'}")


if __name__ == "__main__":
    main()
