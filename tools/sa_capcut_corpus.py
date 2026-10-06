#!/usr/bin/env python3
"""Inventory every CapCut project and every timeline without changing the library."""

from __future__ import annotations

import argparse
import collections
import datetime
import hashlib
import json
import pathlib

from sa_stylebrain import DRAFTS, encode_project


def read_json(path: pathlib.Path):
    try:
        raw = path.read_text(encoding="utf-8")
        if not raw.lstrip().startswith("{"):
            return None, "encrypted_or_non_json"
        return json.loads(raw), None
    except Exception as error:
        return None, f"{type(error).__name__}: {error}"


def project_timeline_index(folder: pathlib.Path) -> tuple[str | None, dict[str, str]]:
    path = folder / "Timelines" / "project.json"
    data, _error = read_json(path) if path.exists() else (None, None)
    if not data:
        return None, {}
    return data.get("main_timeline_id"), {
        row.get("id", ""): row.get("name") or ""
        for row in data.get("timelines") or [] if row.get("id")
    }


def signature(data: dict) -> str:
    rows = []
    for track in data.get("tracks") or []:
        for segment in track.get("segments") or []:
            target = segment.get("target_timerange") or {}
            source = segment.get("source_timerange") or {}
            rows.append((
                track.get("type"), segment.get("material_id"), target.get("start"),
                target.get("duration"), source.get("start"), source.get("duration"),
                round(float(segment.get("speed") or 1), 5),
            ))
    payload = json.dumps({
        "canvas": data.get("canvas_config"),
        "export": (data.get("config") or {}).get("export_range"),
        "duration": data.get("duration"),
        "segments": rows,
    }, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def timeline_paths(folder: pathlib.Path) -> list[pathlib.Path]:
    paths = sorted((folder / "Timelines").glob("*/draft_info.json"))
    if not paths and (folder / "draft_info.json").is_file():
        paths = [folder / "draft_info.json"]
    return paths


def build(root: pathlib.Path) -> dict:
    projects = []
    fingerprints = collections.defaultdict(list)
    for folder in sorted((p for p in root.iterdir() if p.is_dir()), key=lambda p: p.name.casefold()):
        main_id, names = project_timeline_index(folder)
        project = {
            "folder": folder.name,
            "path": str(folder),
            "main_timeline_id": main_id,
            "timeline_count": 0,
            "timelines": [],
        }
        for path in timeline_paths(folder):
            timeline_id = path.parent.name if path.parent.parent.name == "Timelines" else "root"
            data, error = read_json(path)
            row = {
                "id": timeline_id,
                "name": names.get(timeline_id) or ("Root timeline" if timeline_id == "root" else ""),
                "is_main": timeline_id == main_id or (timeline_id == "root" and main_id is None),
                "path": str(path),
                "file_size": path.stat().st_size,
                "readable": data is not None,
            }
            if data is None:
                row["error"] = error
            else:
                export = (data.get("config") or {}).get("export_range") or {}
                duration = int(export.get("duration", 0)) or int(data.get("duration", 0))
                row.update({
                    "draft_duration_s": round(int(data.get("duration", 0)) / 1_000_000, 4),
                    "export_start_s": round(int(export.get("start", 0)) / 1_000_000, 4),
                    "export_duration_s": round(duration / 1_000_000, 4),
                    "has_saved_export_range": bool(export.get("duration")),
                    "track_count": len(data.get("tracks") or []),
                    "segment_count": sum(len(t.get("segments") or []) for t in data.get("tracks") or []),
                    "empty": not any(t.get("segments") for t in data.get("tracks") or []),
                    "signature": signature(data),
                })
                label = f"{folder.name} — {row['name'] or timeline_id}"
                try:
                    learned = encode_project(path, name=label)
                    row["style_type"] = learned["style_type"]
                    row["confidence"] = learned["evidence"]["confidence"]
                    row["has_outro"] = learned["evidence"]["has_outro"]
                    row["has_music_or_sound"] = learned["evidence"]["has_music_or_sound"]
                    row["canvas"] = learned["canvas"]
                    row["metrics"] = learned["metrics"]
                except Exception as exc:
                    row["fingerprint_error"] = f"{type(exc).__name__}: {exc}"
                fingerprints[row["signature"]].append((folder.name, timeline_id))
            project["timelines"].append(row)
        project["timeline_count"] = len(project["timelines"])
        projects.append(project)

    duplicate_groups = [
        {"signature": key, "timelines": [{"project": p, "timeline": t} for p, t in values]}
        for key, values in fingerprints.items() if len(values) > 1
    ]
    all_rows = [t for p in projects for t in p["timelines"]]
    return {
        "schema_version": "1.0",
        "authorship": "(done by codex)",
        "generated": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "root": str(root),
        "project_count": len(projects),
        "timeline_count": len(all_rows),
        "readable_timeline_count": sum(bool(t["readable"]) for t in all_rows),
        "unreadable_timeline_count": sum(not t["readable"] for t in all_rows),
        "empty_timeline_count": sum(bool(t.get("empty")) for t in all_rows),
        "saved_export_range_count": sum(bool(t.get("has_saved_export_range")) for t in all_rows),
        "duplicate_signature_groups": duplicate_groups,
        "projects": projects,
    }


def markdown(corpus: dict) -> str:
    style_counts = collections.Counter(
        t.get("style_type", "unreadable")
        for p in corpus["projects"] for t in p["timelines"]
        if not t.get("empty")
    )
    lines = [
        "# Complete CapCut Timeline Corpus",
        "",
        "This is a read-only census of every project folder and every timeline. (done by codex)",
        "",
        f"- Projects: {corpus['project_count']}",
        f"- Timelines: {corpus['timeline_count']}",
        f"- Readable: {corpus['readable_timeline_count']}",
        f"- Unreadable or encrypted: {corpus['unreadable_timeline_count']}",
        f"- Empty: {corpus['empty_timeline_count']}",
        f"- Timelines with saved export ranges: {corpus['saved_export_range_count']}",
        f"- Exact duplicate groups: {len(corpus['duplicate_signature_groups'])}",
        "",
        "## Style-family census",
        "",
    ]
    for style, count in style_counts.most_common():
        lines.append(f"- `{style}`: {count}")
    lines += [
        "", "## Timeline inventory", "",
        "| Project | Timeline | Main | Readable | Export | Style | Confidence |",
        "|---|---|:---:|:---:|---:|---|---|",
    ]
    for project in corpus["projects"]:
        if not project["timelines"]:
            lines.append(f"| {project['folder']} | — | — | no timeline file | — | — | — |")
            continue
        for timeline in project["timelines"]:
            lines.append(
                f"| {project['folder']} | {timeline.get('name') or timeline['id']} | "
                f"{'yes' if timeline['is_main'] else ''} | "
                f"{'yes' if timeline['readable'] else 'no'} | "
                f"{timeline.get('export_duration_s', '—')} | "
                f"{timeline.get('style_type', '—')} | {timeline.get('confidence', '—')} |"
            )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(DRAFTS))
    parser.add_argument(
        "--out",
        default=str(pathlib.Path(__file__).resolve().parents[1] / "Reference"
                    / "CAPCUT_TIMELINE_CORPUS.json"),
    )
    args = parser.parse_args()
    corpus = build(pathlib.Path(args.root).expanduser().resolve())
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(corpus, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    out.with_suffix(".md").write_text(markdown(corpus), encoding="utf-8")
    print(
        f"{corpus['project_count']} projects, {corpus['timeline_count']} timelines, "
        f"{corpus['readable_timeline_count']} readable, "
        f"{corpus['unreadable_timeline_count']} unreadable"
    )
    print(f"-> {out}")


if __name__ == "__main__":
    main()
