#!/usr/bin/env python3
"""Audit external plugins/hooks and enforce your data boundaries before anything leaves the machine."""
import argparse
import hashlib
import json
import os
import pathlib
import re
import stat
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "Reference" / "PLUGIN_SECURITY.json"
DATA_POLICY = ROOT / "Reference" / "DATA_POLICY.json"
INSTALLED = pathlib.Path.home() / ".claude" / "plugins" / "installed_plugins.json"
PAUSE = ROOT / "Reference" / "PAUSE"


def assert_writes_allowed(operation="write"):
    if PAUSE.exists():
        raise SystemExit("PAUSED: refusing %s while %s exists" % (operation, PAUSE))


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def plugin_audit():
    registry = load(REGISTRY)
    installed = load(INSTALLED).get("plugins", {}) if INSTALLED.exists() else {}
    findings = []
    registered = registry.get("plugins", {})
    for name in sorted(set(installed) - set(registered)):
        findings.append((False, "unregistered installed plugin: %s" % name))
    for name, spec in registered.items():
        rows = installed.get(name, [])
        if not rows:
            findings.append((False, "registered plugin missing: %s" % name))
            continue
        row = rows[-1]
        if row.get("version") != spec.get("version"):
            findings.append((False, "%s version drift: %s != %s" % (name, row.get("version"), spec.get("version"))))
        if row.get("gitCommitSha") != spec.get("commit"):
            findings.append((False, "%s commit drift" % name))
        base = pathlib.Path(row["installPath"])
        for relative, expected in spec.get("hooks", {}).items():
            path = base / relative
            if not path.exists():
                findings.append((False, "%s hook missing: %s" % (name, relative)))
            elif digest(path) != expected:
                findings.append((False, "%s hook changed: %s" % (name, relative)))
        for raw in spec.get("secret_files", []):
            path = pathlib.Path(os.path.expanduser(raw))
            if path.exists():
                perms = stat.S_IMODE(path.stat().st_mode)
                if perms not in (0o600, 0o400):
                    findings.append((False, "unsafe secret permissions %o: %s" % (perms, path)))
                if not spec.get("credentials_allowed", False):
                    text = path.read_text(encoding="utf-8", errors="ignore")
                    if any(re.match(r"\s*(?:GROQ_API_KEY|OPENAI_API_KEY)\s*=\s*\S+", line)
                           for line in text.splitlines()):
                        findings.append((False, "%s has prohibited cloud Whisper credentials" % name))
        if not spec.get("credentials_allowed", False):
            for key in ("GROQ_API_KEY", "OPENAI_API_KEY"):
                if os.environ.get(key):
                    findings.append((False, "%s exposed to %s despite credential prohibition" % (key, name)))
    for name, spec in registry.get("skills", {}).items():
        path = pathlib.Path.home() / ".agents" / "skills" / name / "SKILL.md"
        if not path.exists():
            findings.append((False, "registered skill missing: %s" % name))
        elif digest(path) != spec.get("skill_hash"):
            findings.append((False, "skill changed: %s" % name))
    if not findings:
        findings.append((True, "%s plugins and %s skills match pinned registry" % (len(registered), len(registry.get("skills", {})))))
    return findings


def classify(path, explicit=None):
    policy = load(DATA_POLICY)
    if explicit:
        return explicit
    text = str(path).lower()
    for class_name in ("CLIENT_RESTRICTED", "CONFIDENTIAL"):
        if any(word in text for word in policy.get("path_hints", {}).get(class_name, [])):
            return class_name
    return policy["default_class"]


def gate(path, service, explicit=None, written_approval=False):
    data_class = classify(path, explicit)
    policy = load(DATA_POLICY)
    external = service.lower() not in {"local", "ollama", "ffmpeg", "opencv", "photoshop", "illustrator",
                                  "indesign", "figma-local", "excel", "word"}
    allowed = not PAUSE.exists()
    reason = "allowed"
    if PAUSE.exists():
        allowed, reason = False, "global pause is active"
    elif external and not policy["external_processing"].get(data_class, False) and not written_approval:
        allowed, reason = False, "%s media is local-only without written approval" % data_class
    return {"allowed": allowed, "data_class": data_class, "service": service,
            "external": external, "reason": reason}


def self_test():
    assert classify("/x/client contract/video.mp4") == "CLIENT_RESTRICTED"
    assert classify("/x/interview.mov") == "CONFIDENTIAL"
    assert classify("/x/general.mp4") == "INTERNAL"
    # The default class (no path hint) is the most common case — assert it blocks
    # external services and stays INTERNAL, and that a local service passes.
    r = gate("/x/general.mp4", "elevenlabs")
    assert not r["allowed"] and r["data_class"] == "INTERNAL"
    assert gate("/x/general.mp4", "ollama")["allowed"]
    assert gate("/x/public.mp4", "elevenlabs", "PUBLIC")["allowed"]
    print("security_gate self-checks: ok")


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("test")  # runs the built-in self-test (was unreachable before)
    sub.add_parser("audit")
    check = sub.add_parser("gate"); check.add_argument("path"); check.add_argument("--service", required=True); check.add_argument("--class", dest="data_class", choices=["PUBLIC", "INTERNAL", "CONFIDENTIAL", "CLIENT_RESTRICTED"]); check.add_argument("--written-approval", action="store_true"); check.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.command == "audit":
        findings = plugin_audit()
        for ok, message in findings: print(("PASS" if ok else "FAIL") + ": " + message)
        if not all(row[0] for row in findings):
            print("\nA FAIL on a plugin you knowingly installed is fixed by registering it:"
                  "\nadd its name, version and commit to Reference/PLUGIN_SECURITY.json,"
                  "\nthen re-run this audit. A FAIL you don't recognise is worth investigating.")
        raise SystemExit(0 if all(row[0] for row in findings) else 1)
    if args.command == "gate":
        result = gate(args.path, args.service, args.data_class, args.written_approval)
        print(json.dumps(result, indent=2) if args.json else ("ALLOW" if result["allowed"] else "BLOCK") + ": " + result["reason"] + " [%s]" % result["data_class"])
        raise SystemExit(0 if result["allowed"] else 2)
    self_test()


if __name__ == "__main__":
    main()
