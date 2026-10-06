#!/usr/bin/env python3
"""Plan a surgical training-video revision without touching an approved CapCut project.

This tool is for a later IT workflow change: a new button, renamed control,
inserted procedure, removed step, or reordered section. It records a stable
before/after anchor, fingerprints the currently approved source draft, and
produces a versioned revision card for a NEW duplicate project. It never
writes to CapCut, source media, or a delivered export.

  python3 Tools/sa_training_revision.py new-request --out IT_CHANGE_REQUEST.json
  python3 Tools/sa_training_revision.py modules
  python3 Tools/sa_training_revision.py inspect MOD03
  python3 Tools/sa_training_revision.py plan IT_CHANGE_REQUEST.json --out IT_CHANGE_PLAN.json
  python3 Tools/sa_training_revision.py validate IT_CHANGE_REQUEST.json

The module list comes from the timeline audit JSON (default ./TIMELINE_AUDIT.json;
set SA_TIMELINE_AUDIT to point elsewhere).
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
AUDIT = pathlib.Path(os.environ.get("SA_TIMELINE_AUDIT", "TIMELINE_AUDIT.json")).expanduser()
REQUEST_SCHEMA = "1.0"
CHANGE_TYPES = {
    "text_or_label_update",
    "button_or_visual_update",
    "insert_procedure",
    "replace_procedure",
    "remove_procedure",
    "reorder_procedure",
}
STRUCTURAL_TYPES = {"insert_procedure", "replace_procedure", "remove_procedure", "reorder_procedure"}


def now():
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def load_json(path):
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def sha256(path):
    digest = hashlib.sha256()
    with pathlib.Path(path).open("rb") as handle:
        while True:
            block = handle.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def modules():
    return {row["tag"].upper(): row for row in load_json(AUDIT)}


def module_info(tag):
    row = modules().get(tag.upper())
    if not row:
        raise ValueError("unknown training module %r" % tag)
    return row


def source_baseline(tag):
    row = module_info(tag)
    draft = pathlib.Path(row["draft"])
    baseline = {
        "tag": row["tag"],
        "title": row["title"],
        "source_draft": str(draft),
        "source_exists": draft.is_file(),
        "source_sha256": sha256(draft) if draft.is_file() else None,
        "approved_export_range_s": {"start": row["export_start_s"], "duration": row["export_duration_s"]},
        "canvas": row["canvas"],
        "picture_segments": row["picture_segment_count"],
        "captions": row["caption_count"],
        "callouts": row["callout_segment_count"],
        "freezes": row["freeze_count"],
        "outro": row["outro_segments"],
    }
    return baseline


def request_template():
    return {
        "schema_version": REQUEST_SCHEMA,
        "authorship": "(done by codex)",
        "request_id": "IT-YYYY-NNN",
        "requested_by": "IT team",
        "requested_on": "YYYY-MM-DD",
        "system_release": "Version or deployment date being documented",
        "changes": [
            {
                "tag": "MODXX",
                "change_type": "insert_procedure",
                "description": "State exactly what the learner must now do and why the existing module is incomplete.",
                "it_workflow_verified": False,
                "anchor": {
                    "before": "Exact visible/spoken step immediately before the change",
                    "after": "Exact visible/spoken step immediately after the change",
                    "approximate_time_s": None
                },
                "screen_capture": {
                    "path": "",
                    "capture_notes": "Record the current production system, including a clean before state, the new action, and its confirmed result.",
                    "start_state": "",
                    "end_state": ""
                },
                "voice_lines": [
                    {"text": "", "audio_path": ""}
                ],
                "callouts": [
                    {"target": "Exact on-screen control", "label": "", "screenshot_path": ""}
                ],
                "caption_reviewed": False,
                "it_approval_contact": ""
            }
        ],
        "notes": "Each change must use a stable before/after anchor. A timestamp helps orientation but is never the only anchor because earlier inserts shift downstream time."
    }


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def existing_path(value):
    return nonempty(value) and pathlib.Path(value).expanduser().is_file()


def strategy_for(change_type):
    if change_type == "text_or_label_update":
        return "in_place_replacement"
    if change_type == "button_or_visual_update":
        return "micro_section_replacement"
    if change_type == "insert_procedure":
        return "local_insert_between_anchors"
    return "bounded_section_replacement"


def required_inputs(change):
    missing = []
    if not nonempty(change.get("description")):
        missing.append("plain-language description")
    if not change.get("it_workflow_verified"):
        missing.append("IT workflow verification")
    anchor = change.get("anchor") or {}
    if not nonempty(anchor.get("before")):
        missing.append("before anchor")
    if not nonempty(anchor.get("after")):
        missing.append("after anchor")
    if not nonempty(change.get("it_approval_contact")):
        missing.append("IT approval contact")
    if change.get("change_type") in STRUCTURAL_TYPES | {"button_or_visual_update"}:
        capture = (change.get("screen_capture") or {}).get("path", "")
        if not existing_path(capture):
            missing.append("current-system screen recording")
        lines = change.get("voice_lines") or []
        if not lines or any(not nonempty(line.get("text")) or not existing_path(line.get("audio_path", "")) for line in lines):
            missing.append("approved per-line voice assets")
        callouts = change.get("callouts") or []
        if not callouts or any(not nonempty(item.get("target")) or not nonempty(item.get("label")) or not existing_path(item.get("screenshot_path", "")) for item in callouts):
            missing.append("call-out target/label/frame evidence")
        if not change.get("caption_reviewed"):
            missing.append("caption review")
    return missing


def validate_request(request):
    errors, warnings = [], []
    if request.get("schema_version") != REQUEST_SCHEMA:
        errors.append("schema_version must be %s" % REQUEST_SCHEMA)
    if not nonempty(request.get("request_id")):
        errors.append("request_id is required")
    changes = request.get("changes")
    if not isinstance(changes, list) or not changes:
        errors.append("at least one change is required")
        return errors, warnings
    known = modules()
    for index, change in enumerate(changes, 1):
        prefix = "changes[%s]" % index
        tag = str(change.get("tag", "")).upper()
        if tag not in known:
            errors.append("%s has unknown module tag %r" % (prefix, tag))
        if change.get("change_type") not in CHANGE_TYPES:
            errors.append("%s has invalid change_type" % prefix)
        anchor = change.get("anchor") or {}
        if not nonempty(anchor.get("before")) or not nonempty(anchor.get("after")):
            warnings.append("%s needs two stable anchors before a duplicate is opened" % prefix)
        if anchor.get("approximate_time_s") is not None and not isinstance(anchor.get("approximate_time_s"), (int, float)):
            errors.append("%s anchor.approximate_time_s must be numeric or null" % prefix)
        if change.get("change_type") in STRUCTURAL_TYPES and anchor.get("approximate_time_s") is not None:
            warnings.append("%s has a timestamp, but structural changes must still be located by before/after anchors" % prefix)
    return errors, warnings


def make_plan(request):
    errors, warnings = validate_request(request)
    if errors:
        raise ValueError("; ".join(errors))
    revisions = []
    for change in request["changes"]:
        tag = str(change["tag"]).upper()
        missing = required_inputs(change)
        strategy = strategy_for(change["change_type"])
        revisions.append({
            "tag": tag,
            "title": module_info(tag)["title"],
            "change_type": change["change_type"],
            "strategy": strategy,
            "readiness": "ready_to_duplicate" if not missing else "intake_incomplete",
            "missing_inputs": missing,
            "source_baseline": source_baseline(tag),
            "anchors": change.get("anchor"),
            "protected_invariants": [
                "Original CapCut project, delivered export, and source media remain read-only.",
                "Duplicate the approved project before any timeline action; include the request ID and V01 in the duplicate name.",
                "Preserve all pre-anchor timing and all post-anchor picture/audio/caption/call-out relationships unless the approved change explicitly replaces them.",
                "Never rebuild a hand-adjusted draft from an old manifest after a freeze insert; patch the duplicate surgically.",
                "Use before/after anchors and rendered frames, not a timestamp alone, to find and verify the edit point.",
                "Do not alter title, role, caption, call-out or outro rules outside the affected section.",
            ],
            "execution_order": [
                "Copy the approved project to a new revision project while CapCut is closed; record this source SHA-256 in the revision log.",
                "Import new screen, per-line audio, captions and call-out assets into the duplicate's media pool only.",
                "Locate and lock the two anchors in the duplicate. Export pre-change and post-change reference frames.",
                "Apply the selected strategy only inside the anchored section. Structural inserts move downstream tracks together in the duplicate; they never overwrite the original.",
                "Rebuild/retime captions, call-outs, freeze stills and detached audio only for the affected span, then verify the immediate joins on both sides.",
                "Run the revision QA list and render a review export. Saad approves the change before any delivery replaces a published version.",
            ],
            "qa": [
                "Source draft SHA-256 still matches the recorded baseline; if it does not, stop and establish a new approved base.",
                "Before anchor is unchanged; after anchor is present and semantically correct.",
                "No duplicated unmuted picture/audio layer, echo patch, black hole, caption drift, stranded item past outro or broken freeze alignment.",
                "New call-outs cover the actual target at their in/mid/out frames and do not obscure readable UI.",
                "Freeze starts at about 3.0s; use 6s+ for dense UI only when learner reading requires it. Call-outs default to about 2.1s.",
                "Outro stays intact and is moved as a complete final unit only when an approved structural change increases duration.",
                "Compare the revision export against the plan; report changed runtime and every changed range, never claim an unverified patch is final.",
            ],
            "change": change,
        })
    return {
        "schema_version": "1.0",
        "authorship": "(done by codex)",
        "created_at": now(),
        "request_id": request["request_id"],
        "system_release": request.get("system_release", ""),
        "status": "ready_for_duplicate" if all(item["readiness"] == "ready_to_duplicate" for item in revisions) else "blocked_pending_it_inputs",
        "warnings": warnings,
        "revisions": revisions,
        "limitations": [
            "This plan intentionally does not alter a CapCut project. A live duplicate-and-render verification is required for each real IT change.",
            "New or changed procedures require current-system screen evidence and IT-approved wording; automation cannot infer a changed business workflow from an old recording.",
            "A revision is a new version. It is not safe to claim the original export was updated until the duplicate is rendered, reviewed and approved."
        ]
    }


def markdown(plan):
    lines = [
        "# Training-video revision plan — %s" % plan["request_id"],
        "",
        "- Status: **%s**" % plan["status"],
        "- System release: %s" % (plan.get("system_release") or "not supplied"),
        "- This is a surgical duplicate workflow; no original project is changed.",
    ]
    for revision in plan["revisions"]:
        base = revision["source_baseline"]
        lines.extend([
            "", "## %s — %s" % (revision["tag"], revision["title"]),
            "", "- Change: `%s` → `%s`" % (revision["change_type"], revision["strategy"]),
            "- Readiness: **%s**" % revision["readiness"],
            "- Approved base duration: %.3fs" % base["approved_export_range_s"]["duration"],
            "- Before anchor: %s" % revision["anchors"].get("before"),
            "- After anchor: %s" % revision["anchors"].get("after"),
            "- Base fingerprint: `%s`" % (base["source_sha256"] or "UNAVAILABLE"),
        ])
        if revision["missing_inputs"]:
            lines.append("- Missing before editing: %s" % ", ".join(revision["missing_inputs"]))
        lines.extend(["", "### Required edit order", ""])
        lines.extend("%s. %s" % (index, item) for index, item in enumerate(revision["execution_order"], 1))
        lines.extend(["", "### QA before Saad reviews it", ""])
        lines.extend("- %s" % item for item in revision["qa"])
    lines.extend(["", "## Limits", ""])
    lines.extend("- %s" % item for item in plan["limitations"])
    return "\n".join(lines) + "\n"


def self_test():
    """Runs against a throwaway audit file, so it needs nothing from your own projects."""
    import tempfile
    global AUDIT
    keep = AUDIT
    with tempfile.TemporaryDirectory() as tmp:
        AUDIT = pathlib.Path(tmp) / "TIMELINE_AUDIT.json"
        write_json(AUDIT, [{
            "tag": "MOD03", "title": "Example module", "draft": __file__,
            "export_start_s": 0.0, "export_duration_s": 120.0,
            "canvas": {"width": 1920, "height": 1080},
            "picture_segment_count": 10, "caption_count": 24, "callout_segment_count": 12,
            "freeze_count": 3, "outro_segments": 1}])
        try:
            _self_test()
        finally:
            AUDIT = keep


def _self_test():
    request = request_template()
    request.update({"request_id": "TEST-001", "requested_by": "IT", "requested_on": "2026-09-01"})
    change = request["changes"][0]
    change.update({
        "tag": "MOD03",
        "description": "Add a required confirmation action.",
        "it_workflow_verified": True,
        "it_approval_contact": "test@example.invalid",
        "anchor": {"before": "Open the record", "after": "Save the record", "approximate_time_s": 30.0},
        "screen_capture": {"path": __file__, "capture_notes": "test", "start_state": "a", "end_state": "b"},
        "voice_lines": [{"text": "Select Confirm.", "audio_path": __file__}],
        "callouts": [{"target": "Confirm", "label": "Select Confirm", "screenshot_path": __file__}],
        "caption_reviewed": True,
    })
    errors, _warnings = validate_request(request)
    assert not errors, errors
    plan = make_plan(request)
    assert plan["status"] == "ready_for_duplicate"
    assert plan["revisions"][0]["strategy"] == "local_insert_between_anchors"
    assert "Original CapCut project" in plan["revisions"][0]["protected_invariants"][0]
    print("training revision self-test: ok")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--test", action="store_true")
    sub = parser.add_subparsers(dest="command")
    new = sub.add_parser("new-request")
    new.add_argument("--out", required=True)
    sub.add_parser("modules")
    inspect = sub.add_parser("inspect")
    inspect.add_argument("tag")
    validate = sub.add_parser("validate")
    validate.add_argument("request")
    plan = sub.add_parser("plan")
    plan.add_argument("request")
    plan.add_argument("--out", required=True)
    args = parser.parse_args()
    if args.test:
        self_test()
        return
    if args.command == "new-request":
        write_json(args.out, request_template())
        print("IT change request template -> %s" % args.out)
        return
    if args.command == "modules":
        for tag, row in sorted(modules().items()):
            print("%-7s %7.3fs  %s" % (tag, row["export_duration_s"], row["title"]))
        return
    if args.command == "inspect":
        print(json.dumps(source_baseline(args.tag), indent=2, ensure_ascii=False))
        return
    if args.command == "validate":
        errors, warnings = validate_request(load_json(args.request))
        for item in warnings:
            print("WARNING: " + item)
        if errors:
            for item in errors:
                print("ERROR: " + item)
            raise SystemExit(1)
        print("request structure valid")
        return
    if args.command == "plan":
        result = make_plan(load_json(args.request))
        out = pathlib.Path(args.out)
        write_json(out, result)
        out.with_suffix(".md").write_text(markdown(result), encoding="utf-8")
        print("revision plan -> %s" % out)
        print("revision review brief -> %s" % out.with_suffix(".md"))
        return
    parser.print_help()
    raise SystemExit(2)


if __name__ == "__main__":
    main()
