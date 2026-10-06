#!/usr/bin/env python3
"""Studio consistency gate - read-only preflight for Spec Kit and Claude timing work."""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from pathlib import Path
from typing import Any


DEFAULT_ROOT = Path(__file__).resolve().parents[1]

PLACEHOLDER_PATTERNS = [
    re.compile(r"\[FEATURE NAME\]"),
    re.compile(r"\[DATE\]"),
    re.compile(r"\[NEEDS CLARIFICATION[^\]]*\]"),
    re.compile(r"\[PRINCIPLE_[^\]]+\]"),
    re.compile(r"\[###-[^\]]+\]"),
    re.compile(r"\[PROJECT_NAME\]"),
    re.compile(r"\[COMMAND_NAME\]"),
    re.compile(r"\[ENTITY[^\]]*\]"),
    re.compile(r"\[USER_ACTION\]"),
    re.compile(r"\bTBD\b"),
    re.compile(r"TODO\("),
    re.compile(r"TODO:"),
]


def add_issue(
    issues: list[dict[str, str]],
    level: str,
    code: str,
    message: str,
    path: Path | None = None,
) -> None:
    issue = {"level": level, "code": code, "message": message}
    if path is not None:
        issue["path"] = str(path)
    issues.append(issue)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def count_jsonl(path: Path) -> int | None:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        return sum(1 for line in handle if line.strip())


def relative_or_absolute(root: Path, value: str) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    return root / path


def pilot_paths(root: Path) -> dict[str, Path]:
    pilot = root / "Projects" / "SA_SpecKit_Pilot"
    feature = pilot / "specs" / "001-claude-consistency-gates"
    return {
        "pilot": pilot,
        "constitution": pilot / ".specify" / "memory" / "constitution.md",
        "overlay": pilot
        / ".specify"
        / "workflows"
        / "overlays"
        / "speckit"
        / "sa-consistency-gates.yml",
        "spec": feature / "spec.md",
        "research": feature / "research.md",
        "plan": feature / "plan.md",
        "data_model": feature / "data-model.md",
        "contract": feature / "contracts" / "sa-consistency-gate.md",
        "quickstart": feature / "quickstart.md",
        "tasks": feature / "tasks.md",
    }


def required_docs(root: Path) -> list[Path]:
    paths = pilot_paths(root)
    return [
        root / "AGENTS.md",
        root / "SA_MEMORY.md",
        root / "SA_FEEDBACK.md",
        root / "Reference" / "SA_LOOP_CONSTRAINTS.json",
        root / "Reference" / "SAAD_EDITING_STYLE.md",
        root / "Reference" / "CAPCUT_LIVE_EYES.md",
        root / "Reference" / "TRAINING_REVISION_PROTOCOL.md",
        root / "Reference" / "SA_SPEC_KIT_PILOT.md",
        root / "Reference" / "CLAUDE_CONSISTENCY_GATES.md",
        *paths.values(),
    ]


def scan_placeholder_files(root: Path) -> list[Path]:
    paths = pilot_paths(root)
    return [
        root / "Reference" / "SA_SPEC_KIT_PILOT.md",
        root / "Reference" / "CLAUDE_CONSISTENCY_GATES.md",
        paths["constitution"],
        paths["overlay"],
        paths["spec"],
        paths["research"],
        paths["plan"],
        paths["data_model"],
        paths["contract"],
        paths["quickstart"],
        paths["tasks"],
    ]


def check_required_docs(root: Path, issues: list[dict[str, str]]) -> None:
    missing = []
    for path in required_docs(root):
        if not path.exists():
            missing.append(path)

    if missing:
        for path in missing:
            add_issue(issues, "FAIL", "missing_required_doc", "Required Studio/Spec Kit reference is missing.", path)
        return

    add_issue(issues, "PASS", "required_docs_present", "Required Studio and Spec Kit pilot references are present.")

    for path in scan_placeholder_files(root):
        if not path.exists():
            continue
        text = read_text(path)
        for pattern in PLACEHOLDER_PATTERNS:
            if pattern.search(text):
                add_issue(
                    issues,
                    "FAIL",
                    "unresolved_placeholder",
                    f"Unresolved template placeholder matched {pattern.pattern}.",
                    path,
                )
                break


def check_active_session(root: Path, issues: list[dict[str, str]]) -> None:
    latest = root / "Sessions" / "LATEST.txt"
    if not latest.exists():
        add_issue(issues, "FAIL", "latest_session_missing", "Sessions/LATEST.txt is missing.", latest)
        return

    latest_value = read_text(latest).strip()
    if not latest_value:
        add_issue(issues, "FAIL", "latest_session_empty", "Sessions/LATEST.txt is empty.", latest)
        return

    session_dir = relative_or_absolute(root / "Sessions", latest_value)
    if not session_dir.exists():
        add_issue(issues, "FAIL", "active_session_missing", "Active session folder is missing.", session_dir)
        return

    state_path = session_dir / "state.json"
    log_path = session_dir / "log.jsonl"
    if not state_path.exists():
        add_issue(issues, "FAIL", "active_session_state_missing", "Active session state.json is missing.", state_path)
        return
    if not log_path.exists():
        add_issue(issues, "FAIL", "active_session_log_missing", "Active session log.jsonl is missing.", log_path)
        return

    try:
        state = read_json(state_path)
    except Exception as exc:  # noqa: BLE001 - validator should report parse failures cleanly
        add_issue(issues, "FAIL", "active_session_state_invalid", f"state.json could not be parsed: {exc}", state_path)
        return

    log_lines = count_jsonl(log_path) or 0
    if log_lines == 0:
        add_issue(issues, "FAIL", "active_session_log_empty", "Active session log.jsonl has no entries.", log_path)
    else:
        add_issue(
            issues,
            "PASS",
            "active_session_loaded",
            f"Active session loaded with {log_lines} log entries.",
            session_dir,
        )

    if isinstance(state, dict) and not state.get("status"):
        add_issue(issues, "WARN", "active_session_status_missing", "Active session has no status field.", state_path)


def check_pilot_safety(root: Path, issues: list[dict[str, str]]) -> None:
    paths = pilot_paths(root)
    if (root / ".specify").exists():
        add_issue(
            issues,
            "WARN",
            "root_specify_present",
            "Root workspace has .specify; confirm this was intentional and done from a clean baseline.",
            root / ".specify",
        )
    else:
        add_issue(issues, "PASS", "root_specify_absent", "Root workspace is not initialized with Spec Kit.")

    if (paths["pilot"] / ".specify").exists():
        add_issue(issues, "PASS", "pilot_specify_present", "Isolated Studio Spec Kit pilot exists.", paths["pilot"])
    else:
        add_issue(issues, "FAIL", "pilot_specify_missing", "Studio Spec Kit pilot .specify folder is missing.", paths["pilot"])

    gitignore = root / ".gitignore"
    if gitignore.exists():
        text = read_text(gitignore)
        if "Projects/SA_SpecKit_Pilot/.agents/" in text or "Projects/SA_SpecKit_Pilot/.agents" in text:
            add_issue(issues, "PASS", "pilot_agents_ignored", "Pilot .agents folder is ignored by root git.", gitignore)
        else:
            add_issue(
                issues,
                "WARN",
                "pilot_agents_not_ignored",
                "Spec Kit warned .agents can contain local credentials; add the pilot .agents folder to .gitignore.",
                gitignore,
            )
    else:
        add_issue(issues, "WARN", "gitignore_missing", "Root .gitignore is missing; pilot .agents safety could not be checked.")


def newest_eyes_dir(root: Path) -> Path | None:
    eyes_root = root / "Sessions" / "_eyes"
    if not eyes_root.exists():
        return None
    candidates = [path for path in eyes_root.iterdir() if path.is_dir() and (path / "manifest.json").exists()]
    if not candidates:
        return None
    return max(candidates, key=lambda path: (path / "manifest.json").stat().st_mtime)


def nested_ints(value: Any, keys: set[str]) -> dict[str, int]:
    found: dict[str, int] = {}
    if isinstance(value, dict):
        for key, item in value.items():
            if key in keys and isinstance(item, int):
                found[key] = max(found.get(key, 0), item)
            nested = nested_ints(item, keys)
            for nested_key, nested_value in nested.items():
                found[nested_key] = max(found.get(nested_key, 0), nested_value)
    elif isinstance(value, list):
        for item in value:
            nested = nested_ints(item, keys)
            for nested_key, nested_value in nested.items():
                found[nested_key] = max(found.get(nested_key, 0), nested_value)
    return found


def nested_contains(value: Any, needle: str) -> bool:
    if isinstance(value, str):
        return needle in value
    if isinstance(value, dict):
        return any(nested_contains(item, needle) for item in value.values())
    if isinstance(value, list):
        return any(nested_contains(item, needle) for item in value)
    return False


def frame_index_path(eyes_dir: Path) -> Path:
    nested = eyes_dir / "frames" / "frame_index.jsonl"
    if nested.exists():
        return nested
    return eyes_dir / "frame_index.jsonl"


def check_eyes_session(
    root: Path,
    issues: list[dict[str, str]],
    eyes_dir: Path | None,
    explicit: bool,
) -> None:
    selected = eyes_dir or newest_eyes_dir(root)
    if selected is None:
        level = "FAIL" if explicit else "WARN"
        add_issue(issues, level, "eyes_session_missing", "No CapCut Eyes manifest folder found.")
        return

    manifest_path = selected / "manifest.json"
    timeline_path = selected / "timeline_events.jsonl"
    frame_path = frame_index_path(selected)
    learning_path = selected / "learning.md"
    observations_path = selected / "observations.json"

    if not manifest_path.exists():
        level = "FAIL" if explicit else "WARN"
        add_issue(issues, level, "eyes_manifest_missing", "Selected Eyes folder has no manifest.", manifest_path)
        return

    try:
        manifest = read_json(manifest_path)
    except Exception as exc:  # noqa: BLE001
        add_issue(issues, "FAIL", "eyes_manifest_invalid", f"manifest.json could not be parsed: {exc}", manifest_path)
        return

    status = str(manifest.get("status", "unknown"))
    if status == "stopped_pending_claude_learning":
        add_issue(
            issues,
            "FAIL",
            "eyes_learning_pending",
            "Eyes session stopped before Claude learning was recorded.",
            manifest_path,
        )
    elif status == "claude_learning_recorded":
        add_issue(issues, "PASS", "eyes_learning_recorded", "Eyes session manifest says Claude learning was recorded.", manifest_path)
    else:
        add_issue(issues, "WARN", "eyes_status_unknown", f"Eyes session status is {status}.", manifest_path)

    event_count = count_jsonl(timeline_path)
    frame_count = count_jsonl(frame_path)

    if event_count is None:
        add_issue(issues, "FAIL" if explicit else "WARN", "timeline_events_missing", "timeline_events.jsonl is missing.", timeline_path)
    else:
        add_issue(issues, "PASS", "timeline_events_counted", f"Timeline events counted: {event_count}.", timeline_path)

    if frame_count is None:
        add_issue(issues, "FAIL" if explicit else "WARN", "frame_index_missing", "Frame index is missing.", frame_path)
    else:
        add_issue(issues, "PASS", "frame_index_counted", f"Frame index counted: {frame_count}.", frame_path)

    frames_reviewed = manifest.get("frames_reviewed")
    if isinstance(frames_reviewed, dict) and frame_count is not None:
        total = frames_reviewed.get("of") or frames_reviewed.get("total")
        viewed = frames_reviewed.get("viewed")
        if isinstance(total, int) and total != frame_count:
            add_issue(
                issues,
                "WARN",
                "manifest_frame_count_mismatch",
                f"Manifest frame total {total} differs from frame index count {frame_count}.",
                manifest_path,
            )
        if isinstance(viewed, int) and isinstance(total, int) and viewed < total:
            add_issue(
                issues,
                "WARN",
                "sampled_visual_review",
                f"Claude reviewed {viewed} of {total} frames; do not claim every frame was visually inspected.",
                manifest_path,
            )

    if learning_path.exists() and event_count is not None and frame_count is not None:
        learning = read_text(learning_path)
        if str(event_count) in learning and str(frame_count) in learning:
            add_issue(
                issues,
                "PASS",
                "learning_counts_reference_current_files",
                "learning.md mentions the current event and frame counts.",
                learning_path,
            )
        else:
            add_issue(
                issues,
                "WARN",
                "learning_counts_not_explicit",
                "learning.md does not explicitly mention both current event and frame counts.",
                learning_path,
            )
    elif not learning_path.exists():
        add_issue(issues, "WARN", "learning_md_missing", "learning.md is missing from the Eyes folder.", learning_path)

    if observations_path.exists() and event_count is not None and frame_count is not None:
        try:
            observations = read_json(observations_path)
        except Exception as exc:  # noqa: BLE001
            add_issue(issues, "WARN", "observations_invalid", f"observations.json could not be parsed: {exc}", observations_path)
            return

        obs_numbers = nested_ints(
            observations,
            {
                "frame_count",
                "frames_count",
                "total_frames",
                "event_count",
                "events_count",
                "timeline_event_count",
            },
        )
        obs_frame = max(
            [obs_numbers.get(key, 0) for key in ("frame_count", "frames_count", "total_frames")],
            default=0,
        )
        obs_event = max(
            [obs_numbers.get(key, 0) for key in ("event_count", "events_count", "timeline_event_count")],
            default=0,
        )
        stale_by_count = (obs_frame and obs_frame < frame_count) or (obs_event and obs_event < event_count)
        stale_by_status = nested_contains(observations, "vision_failed")
        if stale_by_count or stale_by_status:
            add_issue(
                issues,
                "WARN",
                "stale_observations_json",
                (
                    "observations.json appears stale or failed; prefer manifest, timeline events, "
                    "frame index, and learning.md for current claims."
                ),
                observations_path,
            )


def run_checks(root: Path, eyes_dir: Path | None = None, eyes_explicit: bool = False) -> dict[str, Any]:
    root = root.resolve()
    issues: list[dict[str, str]] = []
    selected_eyes = eyes_dir.resolve() if eyes_dir else None

    check_required_docs(root, issues)
    check_active_session(root, issues)
    check_pilot_safety(root, issues)
    check_eyes_session(root, issues, selected_eyes, eyes_explicit)

    failures = sum(1 for issue in issues if issue["level"] == "FAIL")
    warnings = sum(1 for issue in issues if issue["level"] == "WARN")
    passes = sum(1 for issue in issues if issue["level"] == "PASS")
    status = "fail" if failures else "warn" if warnings else "pass"
    return {
        "status": status,
        "root": str(root),
        "issues": issues,
        "summary": {"passes": passes, "warnings": warnings, "failures": failures},
    }


def print_human(result: dict[str, Any]) -> None:
    print(f"Studio consistency gate: {result['status'].upper()}")
    summary = result["summary"]
    print(f"Passes: {summary['passes']}  Warnings: {summary['warnings']}  Failures: {summary['failures']}")
    for issue in result["issues"]:
        location = f" ({issue['path']})" if "path" in issue else ""
        print(f"[{issue['level']}] {issue['code']}: {issue['message']}{location}")


def write_fixture_file(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_test_root(root: Path) -> Path:
    content = "Fixture content for Studio consistency gate self-test. (done by codex)\n"
    paths = pilot_paths(root)
    for path in required_docs(root):
        if path == paths["pilot"]:
            path.mkdir(parents=True, exist_ok=True)
        else:
            write_fixture_file(path, content)

    write_fixture_file(root / ".gitignore", "Projects/SA_SpecKit_Pilot/.agents/\n")
    write_fixture_file(root / "Sessions" / "LATEST.txt", "2026-09-05_test\n")
    write_fixture_file(
        root / "Sessions" / "2026-09-05_test" / "state.json",
        json.dumps({"status": "testing Studio consistency gate (done by codex)"}, indent=2),
    )
    write_fixture_file(
        root / "Sessions" / "2026-09-05_test" / "log.jsonl",
        json.dumps({"agent": "codex", "event": "test", "note": "(done by codex)"}) + "\n",
    )

    eyes = root / "Sessions" / "_eyes" / "2026-09-05T000000+0400"
    write_fixture_file(
        eyes / "manifest.json",
        json.dumps({"status": "claude_learning_recorded", "frames_reviewed": {"viewed": 2, "of": 4}}, indent=2),
    )
    write_fixture_file(eyes / "timeline_events.jsonl", "{}\n{}\n{}\n")
    write_fixture_file(eyes / "frames" / "frame_index.jsonl", "{}\n{}\n{}\n{}\n")
    write_fixture_file(eyes / "learning.md", "Current learning uses 3 timeline events and 4 frames. (done by codex)\n")
    write_fixture_file(eyes / "observations.json", json.dumps({"frame_count": 1, "event_count": 1, "status": "vision_failed"}))
    return eyes


def run_self_tests() -> int:
    with tempfile.TemporaryDirectory(prefix="sa-consistency-gate-") as tmp:
        root = Path(tmp)
        eyes = build_test_root(root)

        result = run_checks(root, eyes, eyes_explicit=True)
        codes = {issue["code"] for issue in result["issues"]}
        if result["summary"]["failures"] != 0:
            print(json.dumps(result, indent=2), file=sys.stderr)
            print("Expected no failures in valid fixture.", file=sys.stderr)
            return 2
        if "stale_observations_json" not in codes:
            print(json.dumps(result, indent=2), file=sys.stderr)
            print("Expected stale observations warning.", file=sys.stderr)
            return 2

        write_fixture_file(pilot_paths(root)["spec"], "[FEATURE NAME]\n")
        failed = run_checks(root, eyes, eyes_explicit=True)
        failed_codes = {issue["code"] for issue in failed["issues"]}
        if "unresolved_placeholder" not in failed_codes or failed["summary"]["failures"] == 0:
            print(json.dumps(failed, indent=2), file=sys.stderr)
            print("Expected unresolved placeholder failure.", file=sys.stderr)
            return 2

    print("sa_consistency_gate self-tests passed")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Studio read-only consistency preflight checks.")
    parser.add_argument("--root", default=str(DEFAULT_ROOT), help="Studio root folder to inspect.")
    parser.add_argument("--eyes-dir", help="Specific Sessions/_eyes folder to inspect.")
    parser.add_argument("--json", action="store_true", help="Emit JSON.")
    parser.add_argument("--test", action="store_true", help="Run self-tests and exit.")
    args = parser.parse_args()

    if args.test:
        return run_self_tests()

    root = Path(args.root).expanduser()
    eyes_dir = relative_or_absolute(root, args.eyes_dir) if args.eyes_dir else None

    try:
        result = run_checks(root, eyes_dir, eyes_explicit=bool(args.eyes_dir))
    except Exception as exc:  # noqa: BLE001
        result = {
            "status": "fail",
            "root": str(root),
            "issues": [
                {
                    "level": "FAIL",
                    "code": "validator_error",
                    "message": f"Validator failed unexpectedly: {exc}",
                }
            ],
            "summary": {"passes": 0, "warnings": 0, "failures": 1},
        }
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print_human(result)
        return 2

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print_human(result)

    return 1 if result["summary"]["failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
