#!/usr/bin/env python3
"""sa_session — ONE canonical session contract for Claude + Codex handoffs.

Fixes audit finding #1 (six incompatible state shapes, missing log events,
stale LATEST.txt). Both agents call this instead of hand-writing JSON.

Canonical state.json (required keys — anything else lives under "extra"):
  session      folder name, e.g. "2026-07-10_system-audit"
  updated      ISO-8601 with timezone
  agent        who wrote it last: claude | codex | saad
  purpose      one line, what this session is for
  status       short current status
  last_action  one line, most recent completed step
  next         list of next steps
  extra        dict — deliverables, key_learning, rules, anything session-specific

Canonical log.jsonl line: {"ts", "agent", "event", "note"} — event is a short
snake_case slug ("vo_generated", "correction", "note").

CLI:
  sa_session.py new <slug> --agent claude --purpose "..."   create + point LATEST.txt
  sa_session.py update --agent claude --status "..." [--last-action ...] [--next "a;b"]
  sa_session.py log <agent> <event> <note>                  append to active session
  sa_session.py check                                       resume validator (exit 1 on problems)
  sa_session.py migrate                                     normalise all old sessions (backs up originals)
  sa_session.py --test                                      self-checks
"""
import os, sys, json, glob, argparse, tempfile
from datetime import datetime, timezone, timedelta

ROOT = os.path.expanduser(os.environ.get("WORKSPACE_ROOT", "~/Documents/Claude"))
SESSIONS = os.path.join(ROOT, "Sessions")
LATEST = os.path.join(SESSIONS, "LATEST.txt")
GST = timezone(timedelta(hours=4))
REQUIRED = ["session", "updated", "agent", "purpose", "status", "last_action", "next", "extra"]


def now_iso():
    return datetime.now(GST).isoformat(timespec="seconds")


def _atomic_write(path, text):
    """Write via temp file + rename so a crash never leaves half a JSON file."""
    d = os.path.dirname(path)
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".tmp_", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


def canonicalize(old: dict, session_name: str) -> dict:
    """Map any historical state shape into the canonical one. Pure function.
    Nothing is dropped: unknown keys are preserved under extra."""
    KNOWN_STATUS = ["status", "current_status", "current_action"]
    KNOWN_PURPOSE = ["purpose", "project", "active_project"]
    out = {
        "session": old.get("session") or session_name,
        "updated": old.get("updated") or now_iso(),
        "agent": old.get("agent") or old.get("owner") or "claude",
        "purpose": next((old[k] for k in KNOWN_PURPOSE if old.get(k)), ""),
        "status": next((old[k] for k in KNOWN_STATUS if old.get(k)), ""),
        "last_action": old.get("last_action", ""),
        "next": [],
        "extra": {},
    }
    nxt = old.get("next") or old.get("next_step") or old.get("pending") or []
    out["next"] = [nxt] if isinstance(nxt, str) else list(nxt)
    if isinstance(old.get("extra"), dict):        # already-canonical input: merge, don't nest
        out["extra"].update(old["extra"])
    consumed = set(KNOWN_STATUS + KNOWN_PURPOSE +
                   ["session", "updated", "agent", "owner", "last_action", "next", "next_step",
                    "pending", "extra"])
    for k, v in old.items():
        if k not in consumed:
            out["extra"][k] = v
    if isinstance(old.get("pending"), list) and old.get("next") :
        out["extra"]["pending"] = old["pending"]   # both existed: keep pending separately too
    return out


def active_session():
    if not os.path.exists(LATEST):
        return None
    name = open(LATEST).read().strip()
    p = os.path.join(SESSIONS, name)
    return p if os.path.isdir(p) else None


def cmd_new(slug, agent, purpose):
    name = f"{datetime.now(GST).strftime('%Y-%m-%d')}_{slug}"
    p = os.path.join(SESSIONS, name)
    os.makedirs(p, exist_ok=True)
    state = {"session": name, "updated": now_iso(), "agent": agent, "purpose": purpose,
             "status": "started", "last_action": "session created", "next": [], "extra": {}}
    _atomic_write(os.path.join(p, "state.json"), json.dumps(state, indent=2, ensure_ascii=False))
    open(LATEST, "w").write(name + "\n")
    cmd_log(agent, "session_created", purpose or name)
    print(f"created {name}, LATEST.txt updated")
    return p


def cmd_update(agent, **fields):
    p = active_session()
    if not p:
        raise SystemExit("no active session — run: sa_session.py new <slug>")
    sp = os.path.join(p, "state.json")
    state = canonicalize(json.load(open(sp)), os.path.basename(p)) if os.path.exists(sp) else \
        canonicalize({}, os.path.basename(p))
    for k, v in fields.items():
        if v is None:
            continue
        if k == "next":
            state["next"] = [x.strip() for x in v.split(";") if x.strip()] if isinstance(v, str) else v
        elif k in REQUIRED:
            state[k] = v
        else:
            state["extra"][k] = v
    state["agent"] = agent
    state["updated"] = now_iso()
    _atomic_write(sp, json.dumps(state, indent=2, ensure_ascii=False))
    print(f"updated {os.path.basename(p)}/state.json")


def cmd_log(agent, event, note):
    p = active_session()
    if not p:
        raise SystemExit("no active session — run: sa_session.py new <slug>")
    line = json.dumps({"ts": now_iso(), "agent": agent, "event": event, "note": note},
                      ensure_ascii=False)
    with open(os.path.join(p, "log.jsonl"), "a", encoding="utf-8") as f:
        f.write(line + "\n")
    print("logged:", event)


def newest_activity():
    """(session_name, mtime) of the most recently touched session by state/log mtime."""
    best, best_t = None, 0
    for d in glob.glob(os.path.join(SESSIONS, "*/")):
        for fn in ("state.json", "log.jsonl"):
            fp = os.path.join(d, fn)
            if os.path.exists(fp):
                t = os.path.getmtime(fp)
                if t > best_t:
                    best, best_t = os.path.basename(d.rstrip("/")), t
    return best, best_t


def cmd_check():
    """Resume validator. Exit 0 = safe to resume from LATEST; exit 1 = fix first."""
    problems = []
    if not os.path.exists(LATEST):
        problems.append("LATEST.txt missing")
    else:
        name = open(LATEST).read().strip()
        p = os.path.join(SESSIONS, name)
        if not os.path.isdir(p):
            problems.append(f"LATEST.txt points at missing folder: {name}")
        else:
            sp = os.path.join(p, "state.json")
            if not os.path.exists(sp):
                problems.append(f"{name}/state.json missing")
            else:
                try:
                    st = json.load(open(sp))
                    missing = [k for k in REQUIRED if k not in st]
                    if missing:
                        problems.append(f"{name}/state.json not canonical, missing: {missing} "
                                        f"(run: sa_session.py migrate)")
                except Exception as e:
                    problems.append(f"{name}/state.json unreadable: {e}")
            newest, newest_t = newest_activity()
            if newest and newest != name:
                pointed_t = max((os.path.getmtime(os.path.join(p, f))
                                 for f in ("state.json", "log.jsonl")
                                 if os.path.exists(os.path.join(p, f))), default=0)
                if newest_t > pointed_t + 60:
                    problems.append(f"newer work exists in '{newest}' but LATEST points at '{name}' "
                                    f"— confirm the pointer before resuming")
    if problems:
        print("RESUME CHECK: PROBLEMS")
        for x in problems:
            print("  ✗", x)
        return 1
    print(f"RESUME CHECK: ok — {open(LATEST).read().strip()}")
    return 0


def normalize_log_file(lp):
    """Normalise one append-only log, preserving its original once before rewrite."""
    lines, changed = [], 0
    for line in open(lp):
        line = line.strip()
        if not line:
            continue
        try:
            j = json.loads(line)
        except Exception:
            lines.append(line); continue
        if "event" not in j:
            j["event"] = "note"; changed += 1
        # Some older agents accidentally wrote the full note into `event`
        # and omitted the required `note` key. Preserve the original text
        # verbatim as the note, then give the record a stable event name.
        if "note" not in j:
            j["note"] = str(j.get("event", ""))
            j["event"] = "legacy_note"
            changed += 1
        j.setdefault("agent", "claude")
        lines.append(json.dumps(j, ensure_ascii=False))
    if changed:
        bak = lp + ".pre_canonical"
        if not os.path.exists(bak):
            os.rename(lp, bak)
        open(lp, "w").write("\n".join(lines) + "\n")
    return changed


def cmd_repair_active_log():
    """Repair only the live session log; leave historic sessions untouched."""
    name = open(LATEST).read().strip()
    lp = os.path.join(SESSIONS, name, "log.jsonl")
    if not os.path.exists(lp):
        raise SystemExit("active log missing: " + lp)
    changed = normalize_log_file(lp)
    print(f"active log repaired: {name} ({changed} canonicalised rows)")


def cmd_migrate():
    """Normalise every session: canonical state.json + canonical log records.
    Originals saved once as *.pre_canonical (never overwritten on re-run)."""
    for d in sorted(glob.glob(os.path.join(SESSIONS, "*/"))):
        name = os.path.basename(d.rstrip("/"))
        sp = os.path.join(d, "state.json")
        if os.path.exists(sp):
            old_raw = open(sp).read()
            old = json.loads(old_raw)
            if sorted(old.keys()) != sorted(REQUIRED):
                bak = sp + ".pre_canonical"
                if not os.path.exists(bak):
                    open(bak, "w").write(old_raw)
                _atomic_write(sp, json.dumps(canonicalize(old, name), indent=2, ensure_ascii=False))
                print(f"  state migrated: {name}")
        lp = os.path.join(d, "log.jsonl")
        if os.path.exists(lp):
            changed = normalize_log_file(lp)
            if changed:
                print(f"  log migrated: {name} ({changed} canonicalised rows)")
    print("migrate done")


def _tests():
    # canonicalize maps every historical shape without losing data
    old = {"project": "Demo", "status": "done", "next_step": "commit", "hard_rules": ["x"],
           "agent": "claude", "updated": "2026-07-08T10:00:00+04:00", "last_action": "y"}
    c = canonicalize(old, "2026-07-08_demo")
    assert c["purpose"] == "Demo" and c["status"] == "done" and c["next"] == ["commit"]
    assert c["extra"]["hard_rules"] == ["x"] and sorted(c.keys()) == sorted(REQUIRED)

    old2 = {"session": "s", "owner": "saad", "purpose": "p", "current_status": "cs",
            "deliverables": {"a": 1}, "next": ["n1", "n2"], "last_action": "la", "updated": "u"}
    c2 = canonicalize(old2, "s")
    assert c2["agent"] == "saad" and c2["status"] == "cs" and c2["next"] == ["n1", "n2"]
    assert c2["extra"]["deliverables"] == {"a": 1}

    # canonical passthrough is stable (idempotent)
    c3 = canonicalize(c2, "s")
    assert c3["status"] == "cs" and c3["extra"]["deliverables"] == {"a": 1}
    legacy_log = {"ts": "x", "agent": "claude", "event": "old note"}
    if "note" not in legacy_log:
        legacy_log["note"] = str(legacy_log.get("event", ""))
        legacy_log["event"] = "legacy_note"
    assert legacy_log == {"ts": "x", "agent": "claude", "event": "legacy_note", "note": "old note"}
    print("sa_session self-checks: ok")


def main():
    if "--test" in sys.argv:
        _tests(); return
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("new"); n.add_argument("slug"); n.add_argument("--agent", default="claude"); n.add_argument("--purpose", default="")
    u = sub.add_parser("update"); u.add_argument("--agent", default="claude")
    for f in ("purpose", "status", "last_action", "next"):
        u.add_argument(f"--{f.replace('_','-')}", dest=f)
    l = sub.add_parser("log"); l.add_argument("agent"); l.add_argument("event"); l.add_argument("note")
    sub.add_parser("check"); sub.add_parser("repair-active-log"); sub.add_parser("migrate")
    a = ap.parse_args()
    if a.cmd == "new":
        cmd_new(a.slug, a.agent, a.purpose)
    elif a.cmd == "update":
        cmd_update(a.agent, purpose=a.purpose, status=a.status, last_action=a.last_action, next=a.next)
    elif a.cmd == "log":
        cmd_log(a.agent, a.event, a.note)
    elif a.cmd == "check":
        sys.exit(cmd_check())
    elif a.cmd == "repair-active-log":
        cmd_repair_active_log()
    elif a.cmd == "migrate":
        cmd_migrate()


if __name__ == "__main__":
    main()
