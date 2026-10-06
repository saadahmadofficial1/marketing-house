#!/usr/bin/env python3
"""Studio Runtime Inspector — one command showing what every agent currently sees.

  python3 Tools/sa_inspect.py            # human report
  python3 Tools/sa_inspect.py --json     # machine-readable
  python3 Tools/sa_inspect.py --test

Answers "is Claude giving Codex the same system and context?" in one shot:
instruction files, session freshness, pinned plugins/skills, policies,
local services, model runtimes — with warnings when something is stale,
missing or drifted. Inspired by grok-build's config inspection; built on
our own sa_security audit (no new registry, no new agent).
"""
import datetime
import hashlib
import json
import os
import pathlib
import subprocess
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Tools"))

WARN = []


def sha12(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()[:12]


def age_days(path):
    return round((datetime.datetime.now().timestamp() - os.path.getmtime(path)) / 86400, 1)


def instruction_files():
    rows = {}
    for label, p in {
        "workspace CLAUDE.md": ROOT / "CLAUDE.md",
        "workspace AGENTS.md": ROOT / "AGENTS.md",
        "global CLAUDE.md": pathlib.Path.home() / ".claude" / "CLAUDE.md",
    }.items():
        if p.exists():
            rows[label] = {"sha": sha12(p), "age_days": age_days(p)}
        else:
            rows[label] = None
            WARN.append("missing instruction file: %s" % label)
    both = rows.get("workspace CLAUDE.md"), rows.get("workspace AGENTS.md")
    if all(both) and abs(both[0]["age_days"] - both[1]["age_days"]) > 14:
        WARN.append("CLAUDE.md and AGENTS.md ages differ >14 days — check the older one for staleness")
    return rows


def session_state():
    latest = (ROOT / "Sessions" / "LATEST.txt")
    if not latest.exists():
        WARN.append("Sessions/LATEST.txt missing")
        return None
    name = latest.read_text().strip()
    folder = ROOT / "Sessions" / name
    out = {"session": name}
    state_p = folder / "state.json"
    log_p = folder / "log.jsonl"
    if state_p.exists():
        state = json.loads(state_p.read_text())
        out["status"] = state.get("status")
        out["next"] = (state.get("next") or "")[:90]
        out["state_updated"] = state.get("updated")
    else:
        WARN.append("active session has no state.json")
    if log_p.exists():
        lines = [l for l in log_p.read_text().splitlines() if l.strip()]
        out["log_rows"] = len(lines)
        try:
            last_ts = json.loads(lines[-1]).get("ts", "")
            out["last_log_ts"] = last_ts
            if out.get("state_updated") and last_ts and last_ts[:10] > str(out["state_updated"])[:10]:
                WARN.append("state.json older than last log entry — session state drift")
        except Exception:
            pass
    return out


def pinned_registry():
    try:
        import sa_security
        findings = sa_security.plugin_audit()
        bad = [msg for ok, msg in findings if not ok]
        for b in bad:
            WARN.append("registry: " + b)
        return {"ok": not bad, "detail": [m for _, m in findings]}
    except Exception as e:
        WARN.append("plugin audit failed: %s" % e)
        return {"ok": False, "detail": [str(e)]}


def policies():
    out = {}
    p = ROOT / "Reference" / "SA_DATA_POLICY.json"
    if p.exists():
        pol = json.loads(p.read_text())
        out["default_class"] = pol.get("default_class")
        out["requirements"] = pol.get("requirements", [])
        if not out["requirements"]:
            WARN.append("SA_DATA_POLICY has no fail-closed requirements block")
    out["loop_paused"] = (ROOT / "Reference" / "SA_LOOP_PAUSE").exists()
    return out


def http_ok(url, timeout=2):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status == 200, r.read()[:200].decode("utf-8", "replace")
    except Exception as e:
        return False, str(e)[:80]


def services():
    out = {}
    ok, _ = http_ok("http://127.0.0.1:5679/health")
    out["opencut_server"] = "up" if ok else "down (start only when needed)"
    ok, body = http_ok("http://127.0.0.1:11434/api/tags")
    if ok:
        try:
            out["ollama"] = "up (%d models)" % len(json.loads(body).get("models", []))
        except Exception:
            out["ollama"] = "up"
    else:
        out["ollama"] = "down"
    out["supertonic"] = "installed" if (pathlib.Path.home() / "ThirdParty" / "vo-engines" / ".venv").exists() else "missing"
    out["opencut_install"] = "pinned" if (pathlib.Path.home() / "ThirdParty" / "OpenCut").exists() else "missing"
    return out


def model_routing():
    # declared routing (docs) vs what is actually reachable
    return {
        "claude": "Claude app/Cowork (this session)",
        "codex": "OpenAI Codex (manual handoff)",
        "qwen_daytime": "ollama qwen3-vl:2b",
        "qwen_overnight": "ollama qwen3-vl:8b",
        "vo": "supertonic F2 (leading) + edge-tts fallback",
        "reference": "Reference/CAPABILITY_MAP.md",
    }


def report():
    data = {
        "generated": datetime.datetime.now().isoformat(timespec="seconds"),
        "instructions": instruction_files(),
        "session": session_state(),
        "registry": pinned_registry(),
        "policies": policies(),
        "services": services(),
        "model_routing": model_routing(),
    }
    data["warnings"] = list(WARN)
    return data


def main():
    data = report()
    if "--json" in sys.argv:
        print(json.dumps(data, indent=1))
        return
    print("RUNTIME INSPECTOR — %s" % data["generated"])
    for label, row in data["instructions"].items():
        print("  %-22s %s" % (label, "sha %s, %s d old" % (row["sha"], row["age_days"]) if row else "MISSING"))
    s = data["session"] or {}
    print("  session: %s [%s] log_rows=%s" % (s.get("session"), s.get("status"), s.get("log_rows")))
    print("  next: %s" % s.get("next", ""))
    print("  registry: %s" % ("OK — " + "; ".join(data["registry"]["detail"]) if data["registry"]["ok"] else "PROBLEMS"))
    print("  policies: default_class=%s, requirements=%d, paused=%s" % (
        data["policies"].get("default_class"), len(data["policies"].get("requirements", [])),
        data["policies"].get("loop_paused")))
    for k, v in data["services"].items():
        print("  %-24s %s" % (k, v))
    print("  routing: " + ", ".join("%s→%s" % (k, v) for k, v in data["model_routing"].items() if k != "reference"))
    if data["warnings"]:
        print("\n  ⚠ WARNINGS:")
        for w in data["warnings"]:
            print("   - " + w)
    else:
        print("\n  ✅ no warnings")


def self_test():
    data = report()
    for key in ("instructions", "session", "registry", "policies", "services", "model_routing", "warnings"):
        assert key in data, key
    assert isinstance(data["warnings"], list)
    print("sa_inspect self-checks: ok (%d warnings live)" % len(data["warnings"]))


if __name__ == "__main__":
    self_test() if "--test" in sys.argv else main()
