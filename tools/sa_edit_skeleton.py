#!/usr/bin/env python3
"""Story-first editing skeletons based on Saad's approved work.

This utility never changes footage or an existing CapCut project. It creates a
reviewable chapter map plus a semantic assignment sheet; only an explicitly
reviewed assignment sheet can be compiled into an editor-neutral timeline plan.

Examples:
  python3 Tools/sa_edit_skeleton.py families
  python3 Tools/sa_edit_skeleton.py new --name "Event Recap" --family event_recap_fast --duration 45 --format story_9x16 --out Projects/Event/plan.json
  python3 Tools/sa_edit_skeleton.py validate Projects/Event/plan.json
  python3 Tools/sa_edit_skeleton.py compile Projects/Event/plan.json Projects/Event/plan.assignments.csv --donor "Review Donor" --out Projects/Event/timeline_plan.json
"""
import argparse
import csv
import json
import pathlib
import sys
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parents[1]
GRAMMAR_PATH = ROOT / "Reference" / "SAAD_EDITING_GRAMMAR.json"
EPSILON = 0.0001


def load_json(path):
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def safe_name(value):
    return "".join(c if c.isalnum() else "_" for c in value).strip("_") or "edit"


def get_family(grammar, name):
    family = grammar.get("families", {}).get(name)
    if not family:
        choices = ", ".join(sorted(grammar.get("families", {})))
        raise SystemExit("unknown family %r; choose one of: %s" % (name, choices))
    return family


def get_format(grammar, name):
    fmt = grammar.get("formats", {}).get(name)
    if not fmt:
        choices = ", ".join(sorted(grammar.get("formats", {})))
        raise SystemExit("unknown format %r; choose one of: %s" % (name, choices))
    return fmt


def as_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def bool_value(value):
    return str(value).strip().lower() in {"1", "true", "yes", "y", "approved"}


def chapter_slots(chapter, pattern, rhythm, required=True):
    duration = chapter["duration_s"]
    midpoint = sum(rhythm["median_range"]) / 2
    slot_count = max(1, round(duration / midpoint))
    slots = []
    for index in range(slot_count):
        role = pattern[index % len(pattern)] if pattern else "picture"
        slots.append({
            "id": "%s_%02d" % (chapter["id"], index + 1),
            "chapter": chapter["id"],
            "narrative_role": role,
            "target_hold_s": round(duration / slot_count, 3),
            "required": required,
            "selection_note": "Choose one non-duplicative shot that fulfils this role.",
        })
    return slots


def make_skeleton(name, family_name, duration, format_name, brief=""):
    grammar = load_json(GRAMMAR_PATH)
    family = get_family(grammar, family_name)
    fmt = get_format(grammar, format_name)
    min_duration, max_duration = family["typical_duration_s"]
    if duration <= 0:
        duration = min_duration
    chapters = []
    cursor = 0.0
    template = family["chapter_template"]
    for index, item in enumerate(template):
        if index == len(template) - 1:
            chapter_duration = round(duration - cursor, 3)
        else:
            chapter_duration = round(duration * float(item["ratio"]), 3)
        chapter = {
            "id": item["id"],
            "label": item["label"],
            "purpose": item["purpose"],
            "start_s": round(cursor, 3),
            "duration_s": chapter_duration,
            "end_s": round(cursor + chapter_duration, 3),
            "transition_in": None if index == 0 else "hard_cut",
        }
        chapters.append(chapter)
        cursor += chapter_duration
    pattern = family.get("slot_pattern", ["picture"])
    slots = []
    for chapter in chapters:
        slots.extend(chapter_slots(chapter, pattern, family["cut_rhythm_s"]))
    return {
        "schema_version": "1.0",
        "authorship": "(done by codex)",
        "project": name,
        "brief": brief,
        "family": family_name,
        "format": format_name,
        "canvas": {"width": fmt["canvas"][0], "height": fmt["canvas"][1], "fps": 30.0},
        "target_duration_s": round(duration, 3),
        "duration_guidance": {"family_range_s": [min_duration, max_duration], "outside_family_range": duration < min_duration or duration > max_duration},
        "authority": grammar["authority_order"],
        "family_guidance": {
            "description": family["description"],
            "cut_rhythm_s": family["cut_rhythm_s"],
            "speed": family["speed"],
            "transition_budget": family["transition_budget"],
            "must_check": family.get("must_check", []),
            "instruction_rules": family.get("instruction_rules", {}),
        },
        "global_rules": grammar["global_rules"],
        "chapters": chapters,
        "slots": slots,
        "review": {
            "status": "skeleton_only",
            "human_approval_required_before_compile": True,
            "notes": [
                "Assign footage by semantic role and chapter, not filename order.",
                "A generated skeleton is a first assembly guide, not a final edit.",
                "Original footage and existing CapCut projects remain read-only."
            ]
        }
    }


def assignment_rows(skeleton):
    rows = []
    chapters = {item["id"]: item for item in skeleton["chapters"]}
    for slot in skeleton["slots"]:
        chapter = chapters[slot["chapter"]]
        rows.append({
            "slot_id": slot["id"],
            "chapter": slot["chapter"],
            "chapter_label": chapter["label"],
            "narrative_role": slot["narrative_role"],
            "target_hold_s": slot["target_hold_s"],
            "required": "yes" if slot["required"] else "no",
            "file": "",
            "source_in_s": "",
            "source_out_s": "",
            "speed": "1.0",
            "transition_in": chapter["transition_in"] or "",
            "new_reason_if_repeated": "",
            "reframed_for_format": "no",
            "approved": "no",
            "notes": slot["selection_note"],
        })
    return rows


def write_assignments(path, skeleton):
    path = pathlib.Path(path)
    rows = assignment_rows(skeleton)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0]) if rows else ["slot_id"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def review_markdown(skeleton, assignment_path):
    lines = [
        "# Editing skeleton — %s" % skeleton["project"],
        "",
        "- Family: `%s`" % skeleton["family"],
        "- Format: `%s` (%sx%s)" % (skeleton["format"], skeleton["canvas"]["width"], skeleton["canvas"]["height"]),
        "- Target duration: %.2fs" % skeleton["target_duration_s"],
        "- Assignment sheet: `%s`" % pathlib.Path(assignment_path).name,
        "- Status: first-assembly guide; human approval is required before compiling.",
        "",
        "## Chapters",
        "",
        "| Start | Chapter | Purpose |",
        "|---:|---|---|",
    ]
    for chapter in skeleton["chapters"]:
        lines.append("| %.2fs | %s (%.2fs) | %s |" % (chapter["start_s"], chapter["label"], chapter["duration_s"], chapter["purpose"]))
    lines.extend(["", "## What to do", "", "1. Fill the assignment sheet in story order.", "2. Mark each chosen source `approved` only after checking the exact in/out and format reframe.", "3. Validate and compile only the approved rows into a new review timeline.", "", "## Non-negotiable checks", ""])
    for item in skeleton["global_rules"]["story_first"] + skeleton["global_rules"]["format"]:
        lines.append("- %s" % item)
    return "\n".join(lines) + "\n"


def validate_skeleton(skeleton, assignment_path=None):
    errors, warnings = [], []
    grammar = load_json(GRAMMAR_PATH)
    if skeleton.get("schema_version") != "1.0":
        errors.append("schema_version must be 1.0")
    family_name = skeleton.get("family")
    if family_name not in grammar.get("families", {}):
        errors.append("unknown family")
        return errors, warnings
    family = grammar["families"][family_name]
    chapters = skeleton.get("chapters") or []
    if not chapters:
        errors.append("at least one chapter is required")
        return errors, warnings
    expected_ids = [item["id"] for item in family["chapter_template"]]
    actual_ids = [item.get("id") for item in chapters]
    missing = [item for item in expected_ids if item not in actual_ids]
    if missing:
        errors.append("missing required chapters: %s" % ", ".join(missing))
    if abs(as_float(chapters[0].get("start_s")) - 0.0) > EPSILON:
        errors.append("first chapter must start at 0")
    previous_end = 0.0
    for chapter in chapters:
        start = as_float(chapter.get("start_s"), -1)
        duration = as_float(chapter.get("duration_s"), -1)
        if start < previous_end - EPSILON:
            errors.append("chapters overlap at %s" % chapter.get("id"))
        if duration <= 0:
            errors.append("chapter %s has non-positive duration" % chapter.get("id"))
        previous_end = max(previous_end, start + duration)
    if abs(previous_end - as_float(skeleton.get("target_duration_s"))) > grammar["validator"]["duration_tolerance_s"]:
        errors.append("chapter duration total does not match target duration")
    if not any(item.get("id") in {"resolution", "brand", "occasion_resolve", "outro", "cta", "milestone", "legacy"} for item in chapters):
        errors.append("missing a resolution chapter")
    slots = skeleton.get("slots") or []
    if not slots:
        errors.append("no semantic slots")
    if assignment_path:
        with pathlib.Path(assignment_path).open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        by_slot = {row.get("slot_id"): row for row in rows}
        used_files = Counter()
        speaker_run = 0
        transition_count = 0
        for slot in slots:
            row = by_slot.get(slot["id"])
            if not row:
                if slot.get("required"):
                    errors.append("missing assignment row for %s" % slot["id"])
                continue
            approved = bool_value(row.get("approved"))
            file_value = row.get("file", "").strip()
            if slot.get("required") and not file_value:
                warnings.append("unassigned required slot: %s" % slot["id"])
            if file_value:
                used_files[file_value] += 1
            if approved and not file_value:
                errors.append("approved slot without a file: %s" % slot["id"])
            if approved and not row.get("source_out_s", "").strip():
                errors.append("approved slot without source_out_s: %s" % slot["id"])
            if skeleton["format"] in {"story_9x16", "square_1x1"} and file_value and not bool_value(row.get("reframed_for_format")):
                warnings.append("format reframe not confirmed: %s" % slot["id"])
            if row.get("transition_in", "").strip() and row.get("transition_in", "").strip() != "hard_cut":
                transition_count += 1
            role = slot.get("narrative_role", "")
            if "speaker" in role or "interview" in role:
                speaker_run += 1
            elif "reaction" in role or "listener" in role or "supporting" in role:
                speaker_run = 0
            if skeleton["family"] == "event_recap_fast" and speaker_run > 1:
                warnings.append("speaker run without reaction/listener bridge near %s" % slot["id"])
        max_transitions = family["transition_budget"]["max_structural_transitions_per_30s"] * max(1, skeleton["target_duration_s"] / 30.0)
        if transition_count > max_transitions + EPSILON:
            warnings.append("transition count %.0f exceeds family guidance %.1f" % (transition_count, max_transitions))
        for file_value, count in used_files.items():
            if count > 1:
                duplicates = [row for row in rows if row.get("file", "").strip() == file_value]
                if any(not row.get("new_reason_if_repeated", "").strip() for row in duplicates):
                    warnings.append("repeated asset needs a new narrative reason: %s" % pathlib.Path(file_value).name)
    return errors, sorted(set(warnings))


def compile_plan(skeleton, assignment_path, donor):
    errors, warnings = validate_skeleton(skeleton, assignment_path)
    if errors:
        raise SystemExit("cannot compile:\n" + "\n".join("ERROR: " + item for item in errors))
    with pathlib.Path(assignment_path).open(newline="", encoding="utf-8") as handle:
        assignments = {row["slot_id"]: row for row in csv.DictReader(handle)}
    picture = []
    cursor = 0.0
    for slot in skeleton["slots"]:
        row = assignments.get(slot["id"])
        if not row or not bool_value(row.get("approved")) or not row.get("file", "").strip():
            continue
        source_in = as_float(row.get("source_in_s"))
        source_out = as_float(row.get("source_out_s"))
        speed = max(as_float(row.get("speed"), 1.0), 0.1)
        source_duration = source_out - source_in
        if source_duration <= 0:
            raise SystemExit("invalid source range for %s" % slot["id"])
        file_path = pathlib.Path(row["file"]).expanduser()
        if not file_path.is_file():
            raise SystemExit("approved source file is missing for %s: %s" % (slot["id"], file_path))
        timeline_duration = source_duration / speed
        picture.append({
            "file": str(file_path.resolve()),
            "role": slot["narrative_role"],
            "chapter": slot["chapter"],
            "timeline_start": round(cursor, 4),
            "timeline_duration": round(timeline_duration, 4),
            "source_start": round(source_in, 4),
            "source_duration": round(source_duration, 4),
            "speed": round(speed, 4),
            "transition": row.get("transition_in") or None,
            "transform": {},
            "needs_review": False,
            "evidence": "Human-approved semantic assignment (%s)" % slot["id"],
        })
        cursor += timeline_duration
    if not picture:
        raise SystemExit("no approved assignment rows to compile")
    return {
        "schema_version": "1.0",
        "project": skeleton["project"],
        "brief": skeleton.get("brief", ""),
        "canvas": skeleton["canvas"],
        "style": {"type": skeleton["family"], "masters": [donor], "confidence": "human-reviewed"},
        "story_skeleton": {"family": skeleton["family"], "format": skeleton["format"], "chapters": skeleton["chapters"]},
        "review": {"required": False, "reviewed_cutsheet": str(assignment_path), "warnings": warnings, "note": "Approved assignment sheet compiled; build only in a new review timeline."},
        "tracks": [{"type": "video", "name": "Main picture", "clips": picture}],
    }


def command_families(grammar):
    for name, family in sorted(grammar["families"].items()):
        lo, hi = family["typical_duration_s"]
        print("%-28s %3ss-%3ss  %s" % (name, lo, hi, family["description"]))


def self_test():
    grammar = load_json(GRAMMAR_PATH)
    skeleton = make_skeleton("Self test", "event_recap_fast", 45, "story_9x16")
    errors, warnings = validate_skeleton(skeleton)
    assert not errors, errors
    assert skeleton["chapters"][0]["start_s"] == 0
    assert abs(sum(c["duration_s"] for c in skeleton["chapters"]) - 45) < 0.01
    assert get_family(grammar, "training_tutorial")["instruction_rules"]["callout_default_hold_s"] == 2.1
    print("edit skeleton self-test: ok")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--test", action="store_true")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("families")
    new = sub.add_parser("new")
    new.add_argument("--name", required=True)
    new.add_argument("--family", required=True)
    new.add_argument("--duration", required=True, type=float)
    new.add_argument("--format", required=True)
    new.add_argument("--brief", default="")
    new.add_argument("--out", required=True)
    check = sub.add_parser("validate")
    check.add_argument("skeleton")
    check.add_argument("--assignments")
    compile_cmd = sub.add_parser("compile")
    compile_cmd.add_argument("skeleton")
    compile_cmd.add_argument("assignments")
    compile_cmd.add_argument("--donor", required=True, help="CapCut donor used only when a new review project is later written")
    compile_cmd.add_argument("--out", required=True)
    args = parser.parse_args()
    if args.test:
        self_test()
        return
    grammar = load_json(GRAMMAR_PATH)
    if args.command == "families":
        command_families(grammar)
        return
    if args.command == "new":
        skeleton = make_skeleton(args.name, args.family, args.duration, args.format, args.brief)
        errors, warnings = validate_skeleton(skeleton)
        if errors:
            raise SystemExit("invalid generated skeleton: " + "; ".join(errors))
        out = pathlib.Path(args.out)
        write_json(out, skeleton)
        assignments = out.with_name(out.stem + ".assignments.csv")
        write_assignments(assignments, skeleton)
        out.with_suffix(".md").write_text(review_markdown(skeleton, assignments), encoding="utf-8")
        print("skeleton -> %s" % out)
        print("assignment sheet -> %s" % assignments)
        print("review brief -> %s" % out.with_suffix(".md"))
        if warnings:
            print("warnings:\n" + "\n".join("- " + item for item in warnings))
        return
    if args.command == "validate":
        errors, warnings = validate_skeleton(load_json(args.skeleton), args.assignments)
        if warnings:
            print("warnings:\n" + "\n".join("- " + item for item in warnings))
        if errors:
            print("errors:\n" + "\n".join("- " + item for item in errors))
            raise SystemExit(1)
        print("editing skeleton valid")
        return
    if args.command == "compile":
        plan = compile_plan(load_json(args.skeleton), args.assignments, args.donor)
        write_json(args.out, plan)
        print("review timeline plan -> %s" % args.out)
        return
    parser.print_help()
    raise SystemExit(2)


if __name__ == "__main__":
    main()
