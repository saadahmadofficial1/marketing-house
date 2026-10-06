#!/usr/bin/env python3
"""Read approved-video audio locally from a corpus registry; originals stay untouched."""

from __future__ import annotations

import argparse
import json
import os
import pathlib


def stamp(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:06.3f}".replace(".", ",")


def write_outputs(folder: pathlib.Path, video_id: str, segments: list[dict]) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{video_id}.json").write_text(json.dumps(segments, indent=2), encoding="utf-8")
    (folder / f"{video_id}.txt").write_text(
        " ".join(row["text"] for row in segments).strip() + "\n", encoding="utf-8"
    )
    cues = []
    for index, row in enumerate(segments, 1):
        cues.append(
            f"{index}\n{stamp(row['in'])} --> {stamp(row['out'])}\n{row['text']}\n"
        )
    (folder / f"{video_id}.srt").write_text("\n".join(cues), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "registry",
        nargs="?",
        default=os.environ.get("SA_VIDEO_CORPUS", "VIDEO_CORPUS.json"),
        help="corpus registry: {\"videos\": [{\"id\", \"final\", \"duration_s\"}, ...]}",
    )
    parser.add_argument(
        "--out",
        default=os.environ.get("SA_VIDEO_CORPUS_AUDIO", "Audio"),
    )
    parser.add_argument("--model", default="small", choices=("tiny", "base", "small", "medium"))
    parser.add_argument("--only", nargs="*")
    parser.add_argument("--redo", action="store_true")
    args = parser.parse_args()

    from faster_whisper import WhisperModel

    registry = json.loads(pathlib.Path(args.registry).read_text(encoding="utf-8"))
    requested = set(args.only or [])
    videos = [v for v in registry["videos"] if not requested or v["id"] in requested]
    missing = requested - {v["id"] for v in videos}
    if missing:
        parser.error(f"unknown id(s): {', '.join(sorted(missing))}")

    model = WhisperModel(args.model, device="cpu", compute_type="int8")
    out = pathlib.Path(args.out)
    for video in videos:
        target = out / f"{video['id']}.json"
        if target.exists() and not args.redo:
            print(f"{video['id']}: existing local transcript kept", flush=True)
            continue
        source = pathlib.Path(video["final"])
        print(f"{video['id']}: reading {video['duration_s']:.1f}s", flush=True)
        stream, info = model.transcribe(
            str(source), vad_filter=True, word_timestamps=False, beam_size=5
        )
        segments = [
            {"in": round(s.start, 3), "out": round(s.end, 3), "text": s.text.strip()}
            for s in stream
        ]
        write_outputs(out, video["id"], segments)
        print(
            f"{video['id']}: {len(segments)} segment(s), detected {info.language} "
            f"({info.language_probability:.2f})",
            flush=True,
        )


if __name__ == "__main__":
    main()
