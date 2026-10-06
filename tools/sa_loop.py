#!/usr/bin/env python3
"""Agent-loop readiness, drift detection, run ledger and circuit breaker.

Adapts useful Loop Engineering patterns to the workspace's existing JSON session
system. It does not create another memory format or invoke an LLM.

  python3 Tools/sa_loop.py audit
  python3 Tools/sa_loop.py start --goal "Build Creative Console"
  python3 Tools/sa_loop.py attempt --action "write CapCut draft" --outcome failure --error "CapCut was open"
  python3 Tools/sa_loop.py check
  python3 Tools/sa_loop.py finish --outcome success --evidence file:/path --evidence test:sa_extract
"""
import argparse
import datetime
import hashlib
import json
import os
import pathlib
import re
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "Reference"
SESSIONS = ROOT / "Sessions"
CONSTRAINTS = REFERENCE / "SA_LOOP_CONSTRAINTS.json"
LEDGER = SESSIONS / "SA_LOOP_LEDGER.json"
PAUSE = REFERENCE / "SA_LOOP_PAUSE"
REQUIRED_STATE = {"session", "updated", "agent", "purpose", "status", "last_action", "next", "extra"}


def now():
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=".sa_loop_", suffix=".json", dir=str(path.parent))
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    os.replace(temp, path)


def empty_ledger(goal=""):
    return {"schema_version": "1.0", "run_id": now(), "goal": goal,
            "started_at": now(), "status": "active", "attempts": [],
            "completion_evidence": [], "finished_at": None}


def load_ledger():
    return read_json(LEDGER) if LEDGER.exists() else empty_ledger()


def error_signature(error):
    normalized = re.sub(r"\d+", "#", (error or "").strip().lower())
    return hashlib.sha256(normalized.encode()).hexdigest()[:12] if normalized else ""


def breaker_reasons(ledger, constraints):
    attempts = ledger.get("attempts", [])
    config = constraints["circuit_breaker"]
    reasons = []
    if PAUSE.exists():
        reasons.append("global kill switch active: Reference/SA_LOOP_PAUSE")
    if not attempts:
        return reasons
    latest_action = attempts[-1].get("action")
    action_attempts = [row for row in attempts if row.get("action") == latest_action]
    if len(action_attempts) >= config["max_attempts_per_action"] and action_attempts[-1].get("outcome") != "success":
        reasons.append("max attempts reached for action: %s" % latest_action)
    failures = []
    for row in reversed(attempts):
        if row.get("outcome") == "success":
            break
        if row.get("outcome") == "failure":
            failures.append(row)
    if len(failures) >= config["consecutive_failure_threshold"]:
        reasons.append("consecutive failure threshold reached")
    signatures = [row.get("error_signature") for row in failures if row.get("error_signature")]
    threshold = config["same_error_threshold"]
    if len(signatures) >= threshold and len(set(signatures[:threshold])) == 1:
        reasons.append("same error repeated %s times" % threshold)
    return reasons


def current_state_findings():
    findings = []
    latest = SESSIONS / "LATEST.txt"
    if not latest.exists():
        return [("fail", "LATEST.txt missing")]
    name = latest.read_text(encoding="utf-8").strip()
    folder = SESSIONS / name
    state_path, log_path = folder / "state.json", folder / "log.jsonl"
    if not folder.is_dir():
        return [("fail", "LATEST points to missing session: %s" % name)]
    if not state_path.exists():
        findings.append(("fail", "%s/state.json missing" % name))
    else:
        try:
            state = read_json(state_path)
            missing = REQUIRED_STATE - set(state)
            findings.append(("ok" if not missing else "fail",
                             "canonical active state" if not missing else "state missing keys: %s" % sorted(missing)))
            updated = datetime.datetime.fromisoformat(state["updated"])
            age = datetime.datetime.now(updated.tzinfo) - updated
            age_hours = age.total_seconds() / 3600
            if age_hours < -0.1:
                findings.append(("fail", "active state timestamp is %.1f hours in the future" % abs(age_hours)))
            else:
                findings.append(("ok" if age_hours < 48 else "warn",
                                 "active state age %.1f hours" % age_hours))
        except Exception as error:
            findings.append(("fail", "state unreadable: %s" % error))
    if not log_path.exists():
        findings.append(("fail", "%s/log.jsonl missing" % name))
    else:
        invalid = 0
        for line in log_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
                if not {"ts", "agent", "event", "note"}.issubset(row):
                    invalid += 1
            except Exception:
                invalid += 1
        findings.append(("ok" if invalid == 0 else "fail", "active log valid" if invalid == 0 else "%s invalid log rows" % invalid))
    return findings


def documented_path_findings():
    findings = []
    files = [ROOT / "AGENTS.md", ROOT / "SA_MEMORY.md", REFERENCE / "STYLE_BRAIN_WORKFLOW.md"]
    missing = set()
    pattern = re.compile(r"`(" + re.escape(str(ROOT)) + r"/[^`]+)`")
    for source in files:
        if not source.exists():
            findings.append(("fail", "required documentation missing: %s" % source.name))
            continue
        for raw in pattern.findall(source.read_text(encoding="utf-8", errors="ignore")):
            path = pathlib.Path(raw.rstrip(".,:;"))
            if not path.exists():
                missing.add(str(path))
    if missing:
        examples = "; ".join(sorted(missing)[:4])
        findings.append(("warn", "%s documented paths missing: %s" % (len(missing), examples)))
    else:
        findings.append(("ok", "documented absolute paths resolve"))
    return findings


def audit_result():
    findings = []
    required = [ROOT / "AGENTS.md", ROOT / "SA_MEMORY.md", ROOT / "SA_PROJECTS.md",
                CONSTRAINTS, ROOT / "Tools" / "sa_session.py", ROOT / "Tools" / "sa_doctor.py"]
    for path in required:
        findings.append(("ok" if path.exists() else "fail", "%s %s" % (path.relative_to(ROOT), "present" if path.exists() else "missing")))
    try:
        constraints = read_json(CONSTRAINTS)
        findings.append(("ok" if constraints.get("schema_version") == "1.0" else "fail", "constraints schema valid"))
    except Exception as error:
        constraints = {"circuit_breaker": {"max_attempts_per_action": 3, "same_error_threshold": 3, "consecutive_failure_threshold": 5}}
        findings.append(("fail", "constraints unreadable: %s" % error))
    findings.extend(current_state_findings())
    findings.extend(documented_path_findings())
    ledger = load_ledger()
    reasons = breaker_reasons(ledger, constraints)
    findings.append(("fail" if reasons else "ok", "circuit breaker: %s" % ("; ".join(reasons) if reasons else "clear")))
    weights = {"ok": 1.0, "warn": 0.5, "fail": 0.0}
    score = round(sum(weights[level] for level, _ in findings) / max(len(findings), 1) * 100)
    level = "L3" if score >= 90 and not any(x[0] == "fail" for x in findings) else ("L2" if score >= 70 else ("L1" if score >= 45 else "L0"))
    return {"schema_version": "1.0", "generated_at": now(), "score": score,
            "level": level, "healthy": not any(x[0] == "fail" for x in findings),
            "findings": [{"level": level_, "message": message} for level_, message in findings],
            "breaker_reasons": reasons}


def write_audit(result):
    atomic_json(REFERENCE / "SA_LOOP_AUDIT.json", result)
    lines = ["# Loop Audit", "", "**Readiness: %s/100 (%s)**" % (result["score"], result["level"]), ""]
    icons = {"ok": "PASS", "warn": "WARN", "fail": "FAIL"}
    lines += ["- **%s** %s" % (icons[row["level"]], row["message"]) for row in result["findings"]]
    (REFERENCE / "SA_LOOP_AUDIT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def cmd_start(goal):
    ledger = empty_ledger(goal)
    atomic_json(LEDGER, ledger)
    print("loop started:", goal)


def cmd_attempt(action, outcome, error="", evidence=None):
    ledger, constraints = load_ledger(), read_json(CONSTRAINTS)
    if ledger.get("status") != "active":
        raise SystemExit("no active loop; run sa_loop.py start")
    reasons = breaker_reasons(ledger, constraints)
    if reasons:
        raise SystemExit("CIRCUIT OPEN: " + "; ".join(reasons))
    ledger["attempts"].append({"iteration": len(ledger["attempts"]) + 1, "timestamp": now(),
                               "action": action, "outcome": outcome, "error": error,
                               "error_signature": error_signature(error), "evidence": evidence or []})
    atomic_json(LEDGER, ledger)
    after = breaker_reasons(ledger, constraints)
    print("attempt logged:", outcome, action)
    if after:
        print("CIRCUIT TRIPPED:", "; ".join(after))
        return 2
    return 0


def cmd_finish(outcome, evidence):
    ledger = load_ledger()
    if outcome == "success" and not evidence:
        raise SystemExit("success requires completion evidence")
    ledger["status"] = "complete" if outcome == "success" else "failed"
    ledger["finished_at"] = now()
    ledger["completion_evidence"] = evidence
    atomic_json(LEDGER, ledger)
    print("loop finished:", outcome)


def self_test():
    constraints = read_json(CONSTRAINTS)
    ledger = empty_ledger("test")
    for index in range(3):
        ledger["attempts"].append({"action": "x", "outcome": "failure",
                                   "error_signature": error_signature("Error 123")})
    reasons = breaker_reasons(ledger, constraints)
    assert any("max attempts" in row for row in reasons)
    assert any("same error" in row for row in reasons)
    assert error_signature("Error 123") == error_signature("Error 456")
    result = audit_result()
    assert 0 <= result["score"] <= 100 and result["level"] in {"L0", "L1", "L2", "L3"}
    print("sa_loop self-checks: ok")


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("test")  # runs the built-in self-test (was unreachable before)
    audit = sub.add_parser("audit"); audit.add_argument("--json", action="store_true")
    start = sub.add_parser("start"); start.add_argument("--goal", required=True)
    attempt = sub.add_parser("attempt"); attempt.add_argument("--action", required=True); attempt.add_argument("--outcome", choices=["success", "failure", "noop"], required=True); attempt.add_argument("--error", default=""); attempt.add_argument("--evidence", action="append", default=[])
    sub.add_parser("check")
    finish = sub.add_parser("finish"); finish.add_argument("--outcome", choices=["success", "failure"], required=True); finish.add_argument("--evidence", action="append", default=[])
    args = parser.parse_args()
    if args.command == "audit":
        result = audit_result(); write_audit(result)
        if args.json: print(json.dumps(result, indent=2))
        else: print("Loop readiness: %s/100 %s" % (result["score"], result["level"])); [print("%s: %s" % (row["level"].upper(), row["message"])) for row in result["findings"]]
        raise SystemExit(0 if result["healthy"] else 1)
    if args.command == "start": cmd_start(args.goal)
    elif args.command == "attempt": raise SystemExit(cmd_attempt(args.action, args.outcome, args.error, args.evidence))
    elif args.command == "check":
        reasons = breaker_reasons(load_ledger(), read_json(CONSTRAINTS)); print("CIRCUIT OPEN: " + "; ".join(reasons) if reasons else "CIRCUIT: clear"); raise SystemExit(2 if reasons else 0)
    elif args.command == "finish": cmd_finish(args.outcome, args.evidence)
    else: self_test()


if __name__ == "__main__":
    main()
