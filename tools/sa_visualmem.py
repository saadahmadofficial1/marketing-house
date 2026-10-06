#!/usr/bin/env python3
"""Low-impact, local visual memory for image libraries.

Examples:
  python3 Tools/sa_visualmem.py
  python3 Tools/sa_visualmem.py "/path/to/images" --limit 20
  python3 Tools/sa_visualmem.py "/path/to/images" --profile overnight

The background profile uses a small VLM and resized temporary copies. The
overnight profile keeps the 8B model for a slower, higher-quality pass.
Original media is read-only; this runs locally and uploads nothing.
"""
import argparse
import base64
import datetime
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
PROJECTS = ROOT / "Projects"
MEMORY_MD = PROJECTS / "VISUAL_MEMORY.md"
MEMORY_JSONL = PROJECTS / "VISUAL_MEMORY.jsonl"
STATE = PROJECTS / "VISUAL_MEMORY.state.json"
PAUSE = ROOT / "Reference" / "SA_LOOP_PAUSE"
OLLAMA = "http://localhost:11434/api/generate"
EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".heic"}
SKIP_PARTS = {"_seen", "frames", "assets", ".bak"}
BUSY_APPS = ("Adobe Premiere Pro", "Adobe After Effects", "CapCut", "DaVinci Resolve")

PROFILES = {
    "background": {
        "model": "qwen3-vl:2b", "limit": 20, "max_dimension": 1024,
        # timeout was 90s: a cold model takes ~50s to load and this reply needs ~30s to
        # generate, so a single image could exceed it. keep_alive was 20s, shorter than
        # a pause_for_apps wait, so the model unloaded and paid the load cost again.
        "sleep": 4.0, "timeout": 240, "keep_alive": "2m", "pause_for_apps": True,
    },
    "overnight": {
        "model": "qwen3-vl:8b", "limit": 150, "max_dimension": 1600,
        "sleep": 1.0, "timeout": 300, "keep_alive": "1m", "pause_for_apps": False,
    },
}

ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "subjects": {"type": "array", "items": {"type": "string"}},
        "setting": {"type": "string"},
        "composition": {"type": "string"},
        "visual_style": {"type": "string"},
        "lighting": {"type": "string"},
        "dominant_colors": {"type": "array", "items": {"type": "string"}},
        "readable_text": {"type": "array", "items": {"type": "string"}},
        "useful_for": {"type": "array", "items": {"type": "string"}},
        "tags": {"type": "array", "items": {"type": "string"}},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "warnings": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "summary", "subjects", "setting", "composition", "visual_style",
        "lighting", "dominant_colors", "readable_text", "useful_for", "tags",
        "confidence", "warnings",
    ],
}

PROMPT = """Analyse this image as factual production metadata for a local visual memory.
Describe only visible evidence. Do not identify people by name, infer confidential facts, or invent unreadable text.
readable_text must contain exact characters only when clearly legible at this resolution; otherwise return an empty list. Symbols and guessed labels are not readable text. LIMIT readable_text TO AT MOST 12 ENTRIES — the headings, titles and button labels a person would notice first. Never transcribe a document, a table, a chat log or body copy; on a text-dense screenshot list only the main headings and say so in summary. Keep every string under 100 characters and the whole reply under 2000.
For useful_for, suggest editing roles such as establishing-shot, detail-shot, interior, tutorial, product, transition, or avoid.
Warnings should mention blur, poor exposure, obstruction, duplicate-like framing, uncertain text, or sensitive visible information.
Return only JSON matching this schema: %s""" % json.dumps(ANALYSIS_SCHEMA, separators=(",", ":"))


def data_class(path):
    try:
        from sa_security import classify
        return classify(str(path))
    except (ImportError, FileNotFoundError, json.JSONDecodeError):
        return "INTERNAL"


def active_creative_apps():
    try:
        result = subprocess.run(
            ["ps", "-axo", "comm="], capture_output=True, text=True, timeout=5, check=True
        )
    except (OSError, subprocess.SubprocessError):
        return []
    process_text = result.stdout.lower()
    return [app for app in BUSY_APPS if app.lower() in process_text]


def load_state():
    if not STATE.exists():
        return {}
    try:
        value = json.loads(STATE.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_state(state):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=STATE.name, dir=STATE.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(state, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temporary, STATE)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def atomic_text(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name, dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def image_bytes(path, max_dimension):
    """Create a small temporary JPEG in memory; never alter source media."""
    fd, output = tempfile.mkstemp(suffix=".jpg")
    os.close(fd)
    try:
        subprocess.run(
            ["sips", "-Z", str(max_dimension), "-s", "format", "jpeg",
             "-s", "formatOptions", "82", str(path), "--out", output],
            capture_output=True, text=True, timeout=45, check=True,
        )
        return pathlib.Path(output).read_bytes()
    finally:
        pathlib.Path(output).unlink(missing_ok=True)


def validate_analysis(value):
    if not isinstance(value, dict):
        raise ValueError("analysis is not a JSON object")
    for key in ANALYSIS_SCHEMA["required"]:
        if key not in value:
            raise ValueError("analysis missing field: %s" % key)
    for key in ("subjects", "dominant_colors", "readable_text", "useful_for", "tags", "warnings"):
        if not isinstance(value[key], list):
            raise ValueError("analysis field is not a list: %s" % key)
        cleaned = []
        for item in value[key]:
            item = str(item).strip()
            if item and item not in cleaned:
                cleaned.append(item)
        value[key] = cleaned
    # VLM confidence is not statistically calibrated; keep it visibly conservative.
    value["confidence"] = max(0.0, min(0.85, float(value["confidence"])))
    return value


def analyse(path, config):
    pixels = image_bytes(path, config["max_dimension"])
    payload = {
        "model": config["model"],
        "prompt": PROMPT,
        "images": [base64.b64encode(pixels).decode("ascii")],
        "stream": False,
        "format": ANALYSIS_SCHEMA,
        "think": False,
        "keep_alive": config["keep_alive"],
        # num_predict must be GENEROUS, not absent, and not tight.
        #   420  (original) -> the reply was cut off mid-string; the same 3 images failed
        #                      every night because the thinking counts against this budget.
        #   none (8 Aug fix) -> removed the truncation and introduced a worse failure: on
        #                      dense text-heavy screenshots the model never stops and the
        #                      request times out after 4 minutes. Three images, 12 minutes.
        # A normal reply needs ~800. 2000 clears every image measured and still bounds the
        # pathological ones so one bad file cannot eat the whole nightly window.
        # NEVER set num_ctx on a vision call — it truncates the image itself.
        "options": {"temperature": 0, "num_predict": 2000},
    }
    request = urllib.request.Request(
        OLLAMA, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    started = time.monotonic()
    response = json.loads(urllib.request.urlopen(request, timeout=config["timeout"]).read())
    raw = (response.get("response") or response.get("thinking") or "").strip()
    analysis = validate_analysis(json.loads(raw))
    metrics = {
        "wall_seconds": round(time.monotonic() - started, 2),
        "load_seconds": round(response.get("load_duration", 0) / 1e9, 2),
        "prompt_eval_seconds": round(response.get("prompt_eval_duration", 0) / 1e9, 2),
        "eval_seconds": round(response.get("eval_duration", 0) / 1e9, 2),
    }
    return analysis, metrics


def ask(path, model=None):
    """Compatibility entry point used by sa_peek and older local tools."""
    config = dict(PROFILES["background"])
    if model:
        config["model"] = model
    analysis, _ = analyse(pathlib.Path(path), config)
    return json.dumps(analysis, ensure_ascii=True, indent=2)


def unload(model):
    request = urllib.request.Request(
        OLLAMA,
        data=json.dumps({"model": model, "keep_alive": 0}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        urllib.request.urlopen(request, timeout=20).read()
    except (OSError, urllib.error.URLError):
        pass


def file_key(path):
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def already_done(state, path, target_model):
    key = file_key(path)
    current = path.stat().st_mtime_ns
    old = state.get(key)
    if isinstance(old, dict):
        if old.get("mtime_ns") != current:
            return False
        previous_model = old.get("model")
        if previous_model == target_model:
            return True
        # A completed deep pass also satisfies the lightweight background pass.
        return previous_model == "qwen3-vl:8b" and target_model == "qwen3-vl:2b"
    if isinstance(old, (int, float)):
        return abs(float(old) - path.stat().st_mtime) < 0.001
    return False


def find_images(roots, state, target_model, reanalyse=False):
    found = []
    for root in roots:
        root = pathlib.Path(root).expanduser().resolve()
        paths = [root] if root.is_file() else root.rglob("*") if root.exists() else []
        for path in paths:
            if not path.is_file() or path.suffix.lower() not in EXTENSIONS:
                continue
            if any(part in SKIP_PARTS for part in path.parts):
                continue
            if not reanalyse and already_done(state, path, target_model):
                continue
            found.append(path)
    return sorted(set(found), key=lambda item: str(item).lower())


def append_record(record):
    MEMORY_JSONL.parent.mkdir(parents=True, exist_ok=True)
    records = []
    if MEMORY_JSONL.exists():
        for line in MEMORY_JSONL.read_text(encoding="utf-8").splitlines():
            try:
                old = json.loads(line)
            except json.JSONDecodeError:
                continue
            if old.get("path") != record["path"]:
                records.append(old)
    records.append(record)
    atomic_text(
        MEMORY_JSONL,
        "".join(json.dumps(row, ensure_ascii=True, separators=(",", ":")) + "\n" for row in records),
    )
    if not MEMORY_MD.exists():
        MEMORY_MD.write_text(
            "# VISUAL MEMORY\n\nLocal, auto-generated image descriptions. JSON source: VISUAL_MEMORY.jsonl.\n",
            encoding="utf-8",
        )
    analysis = record["analysis"]
    text = (
        "\n## {path}\n({date}; {model}; {data_class}; confidence {confidence:.0%}) "
        "{summary}\n\nTags: {tags}\n"
    ).format(
        path=record["path"], date=record["analysed_at"][:10], model=record["model"],
        data_class=record["data_class"], confidence=analysis["confidence"],
        summary=analysis["summary"], tags=", ".join(analysis["tags"]),
    )
    existing = MEMORY_MD.read_text(encoding="utf-8")
    section = re.compile(r"\n## %s\n.*?(?=\n## |\Z)" % re.escape(record["path"]), re.DOTALL)
    existing = section.sub("", existing).rstrip() + "\n"
    atomic_text(MEMORY_MD, existing + text)


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_worklog_trace(successes, failures, model):
    if not successes:
        return
    path = ROOT / "SA_WORKLOG.md"
    if not path.exists():
        return
    today = datetime.date.today().isoformat()
    entry = (
        "\n## [%s] visual-memory local batch\n"
        "Indexed %s image(s) with `%s`; %s failed. Sources stayed local; model unloaded after completion.\n"
        % (today, successes, model, failures)
    )
    current = path.read_text(encoding="utf-8")
    marker = "\n---\n"
    if marker in current:
        current = current.replace(marker, marker + entry, 1)
    else:
        current = entry.lstrip() + "\n" + current
    atomic_text(path, current)


def self_test():
    sample = {key: ([] if ANALYSIS_SCHEMA["properties"][key]["type"] == "array" else "ok")
              for key in ANALYSIS_SCHEMA["required"]}
    sample["confidence"] = 0.75
    assert validate_analysis(sample)["confidence"] == 0.75
    assert PROFILES["background"]["model"] == "qwen3-vl:2b"
    assert PROFILES["background"]["max_dimension"] <= 1024
    print("sa_visualmem self-checks: ok")


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("roots", nargs="*", default=[str(PROJECTS)], help="image files or folders")
    parser.add_argument("--profile", choices=sorted(PROFILES), default="background")
    parser.add_argument("--model", help="override the profile model")
    parser.add_argument("--limit", type=int, help="maximum images this run")
    parser.add_argument("--max-dimension", type=int, help="temporary analysis copy size")
    parser.add_argument("--sleep", type=float, help="seconds between images")
    parser.add_argument("--force", action="store_true", help="run even if a creative app is open")
    parser.add_argument("--keep-loaded", action="store_true", help="leave model loaded after the run")
    parser.add_argument("--reanalyse", action="store_true", help="analyse even when the source is unchanged")
    parser.add_argument("--dry-run", action="store_true", help="analyse and print JSON without saving memory")
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    if args.self_test:
        self_test()
        return
    if PAUSE.exists():
        raise SystemExit("LOOP PAUSED: visual memory did not run")

    config = dict(PROFILES[args.profile])
    for name in ("model", "limit", "max_dimension", "sleep"):
        value = getattr(args, name)
        if value is not None:
            config[name] = value
    if args.profile == "background":
        try:
            os.nice(10)
        except OSError:
            pass

    busy = active_creative_apps() if config["pause_for_apps"] and not args.force else []
    if busy:
        print("Visual memory paused: creative app open (%s). Nothing changed." % ", ".join(busy))
        return

    state = load_state()
    todo = find_images(args.roots, state, config["model"], args.reanalyse)[:max(0, config["limit"])]
    if not todo:
        print("Visual memory up to date: nothing new")
        return

    print("Local-only visual memory: %s image(s), %s, max %spx" %
          (len(todo), config["model"], config["max_dimension"]))
    successes = failures = 0
    try:
        for index, path in enumerate(todo, 1):
            if PAUSE.exists():
                print("Paused by SA_LOOP_PAUSE after %s image(s)" % successes)
                break
            if config["pause_for_apps"] and not args.force:
                busy = active_creative_apps()
                if busy:
                    print("Paused before next image: %s opened" % ", ".join(busy))
                    break
            try:
                analysis, metrics = analyse(path, config)
                stat = path.stat()
                record = {
                    "schema_version": 1,
                    "path": file_key(path),
                    "source_name": path.name,
                    "content_sha256": sha256_file(path),
                    "source_bytes": stat.st_size,
                    "source_mtime_ns": stat.st_mtime_ns,
                    "analysed_at": datetime.datetime.now(datetime.timezone.utc).astimezone().isoformat(),
                    "model": config["model"],
                    "profile": args.profile,
                    "analysis_max_dimension": config["max_dimension"],
                    "data_class": data_class(path),
                    "analysis": analysis,
                    "metrics": metrics,
                }
                if args.dry_run:
                    print(json.dumps(record, indent=2, ensure_ascii=True))
                else:
                    append_record(record)
                    state[file_key(path)] = {
                        "mtime_ns": stat.st_mtime_ns,
                        "model": config["model"],
                        "analysed_at": record["analysed_at"],
                    }
                    save_state(state)
                successes += 1
                print("[%s/%s] indexed %s (%.1fs)" %
                      (index, len(todo), path.name, metrics["wall_seconds"]))
            except Exception as error:
                failures += 1
                print("[%s/%s] failed %s: %s" % (index, len(todo), path.name, error))
            if index < len(todo) and config["sleep"]:
                time.sleep(config["sleep"])
    finally:
        if not args.keep_loaded:
            unload(config["model"])

    print("Indexed %s; failed %s. JSON: %s" %
          (successes, failures, MEMORY_JSONL.relative_to(ROOT)))
    if not args.dry_run:
        write_worklog_trace(successes, failures, config["model"])
    if failures and not successes:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
