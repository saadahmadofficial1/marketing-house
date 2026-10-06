#!/usr/bin/env python3
"""Describe approved-video contact strips with the local Ollama vision model only."""

from __future__ import annotations

import argparse
import base64
import json
import pathlib
import subprocess
import tempfile
import urllib.request


# Default inputs/outputs live beside the workspace Tools/ folder; override with the CLI flags.
MASTERY = pathlib.Path(__file__).resolve().parents[1] / "Projects" / "Editing_Style_Mastery"

SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "opening_strategy": {"type": "string"},
        "sequence": {"type": "array", "items": {"type": "string"}},
        "middle_progression": {"type": "string"},
        "ending_strategy": {"type": "string"},
        "scale_pattern": {"type": "array", "items": {"type": "string"}},
        "people_product_venue_balance": {"type": "string"},
        "text_and_graphics": {"type": "array", "items": {"type": "string"}},
        "colour_and_light": {"type": "string"},
        "pacing_shape": {"type": "string"},
        "emotional_shape": {"type": "string"},
        "edit_rules_evidenced": {"type": "array", "items": {"type": "string"}},
        "uncertainties": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "summary", "opening_strategy", "sequence", "middle_progression",
        "ending_strategy", "scale_pattern", "people_product_venue_balance",
        "text_and_graphics", "colour_and_light", "pacing_shape", "emotional_shape",
        "edit_rules_evidenced", "uncertainties",
    ],
}


PROMPT = """Read these contact strips as one approved edited video. Tiles are chronological,
left-to-right and top-to-bottom; a source timecode is burned at the bottom of each tile.
Describe only visible evidence. Do not identify people, infer private facts or invent unreadable
text. This is an EDITING study: recover the story progression, opening hook, ending resolution,
alternation of wide/medium/detail/reaction shots, treatment of people versus place/product,
graphic moments, pace changes and emotional build. Treat blank unused tiles at the end as
padding, not footage. A contact strip cannot prove motion transitions or sound decisions, so put
those in uncertainties instead of guessing. Keep the sequence compact: group adjacent tiles
that form one story beat and use visible timecodes where legible. Return one JSON object with
exactly these keys: summary, opening_strategy, sequence, middle_progression, ending_strategy,
scale_pattern, people_product_venue_balance, text_and_graphics, colour_and_light, pacing_shape,
emotional_shape, edit_rules_evidenced, uncertainties. sequence, scale_pattern,
text_and_graphics, edit_rules_evidenced and uncertainties must be arrays of short strings;
all other values must be strings. Return JSON only."""


def image_bytes(path: pathlib.Path, maximum: int = 2200) -> bytes:
    with tempfile.NamedTemporaryFile(suffix=".jpg") as target:
        subprocess.run(
            ["sips", "-Z", str(maximum), "-s", "format", "jpeg", "-s", "formatOptions", "88",
             str(path), "--out", target.name],
            capture_output=True, text=True, timeout=60, check=True,
        )
        return pathlib.Path(target.name).read_bytes()


def analyse(images: list[pathlib.Path], model: str) -> dict:
    payload = {
        "model": model,
        "prompt": PROMPT,
        "images": [base64.b64encode(image_bytes(path)).decode("ascii") for path in images],
        "stream": False,
        "format": "json",
        "think": False,
        "keep_alive": "15m",
        "options": {"temperature": 0, "num_predict": 3000},
    }
    request = urllib.request.Request(
        "http://localhost:11434/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    response = json.loads(urllib.request.urlopen(request, timeout=600).read())
    raw = (response.get("response") or response.get("thinking") or "{}").strip()
    result = json.loads(raw)
    missing = [key for key in SCHEMA["required"] if key not in result]
    if missing:
        raise RuntimeError(f"local visual response missing: {', '.join(missing)}")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "registry", nargs="?",
        default=str(MASTERY / "VIDEO_CORPUS.json"),
    )
    parser.add_argument(
        "--frames-root",
        default=str(MASTERY / "Frames"),
    )
    parser.add_argument(
        "--out",
        default=str(MASTERY / "Visual_Reads"),
    )
    parser.add_argument("--model", default="qwen3-vl:8b")
    parser.add_argument("--only", nargs="*")
    parser.add_argument("--redo", action="store_true")
    args = parser.parse_args()

    registry = json.loads(pathlib.Path(args.registry).read_text(encoding="utf-8"))
    requested = set(args.only or [])
    videos = [v for v in registry["videos"] if not requested or v["id"] in requested]
    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for video in videos:
        target = out / f"{video['id']}.json"
        if target.exists() and not args.redo:
            print(f"{video['id']}: existing local visual read kept", flush=True)
            continue
        strips = sorted((pathlib.Path(args.frames_root) / video["id"] / "strips").glob("*.jpg"))
        if not strips:
            raise SystemExit(f"{video['id']}: no contact strips")
        print(f"{video['id']}: reading {len(strips)} strip(s) locally", flush=True)
        result = analyse(strips, args.model)
        result["video_id"] = video["id"]
        result["model"] = args.model
        result["evidence"] = [str(path) for path in strips]
        result["authorship"] = "(done by codex)"
        target.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"{video['id']}: -> {target}", flush=True)


if __name__ == "__main__":
    main()
