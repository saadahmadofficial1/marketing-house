#!/usr/bin/env python3
"""System doctor — one command answers "is everything healthy?"
  python3 Tools/sa_doctor.py
Checks tools compile, brain files, backup freshness,
scheduled-task traces, git state. Writes Reference/DOCTOR.md (traffic lights).
Run weekly or whenever something feels off.
"""
import os, glob, py_compile, subprocess, time, datetime, json, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
results = []  # (ok, label, detail)

def check(ok, label, detail=""):
    results.append((ok, label, detail))
    print(("✅" if ok else "❌"), label, ("— " + detail if detail else ""))

# 1. every tool compiles
bad = []
compile_cache = os.path.join(tempfile.gettempdir(), "sa_doctor_pycache")
os.makedirs(compile_cache, exist_ok=True)
for f in glob.glob(os.path.join(HERE, "*.py")):
    try:
        py_compile.compile(
            f, cfile=os.path.join(compile_cache, os.path.basename(f) + ".pyc"),
            doraise=True,
        )
    except Exception as e: bad.append(f"{os.path.basename(f)}: {e}")
check(not bad, f"Tools compile ({len(glob.glob(os.path.join(HERE,'*.py')))} scripts)", "; ".join(bad))

# 2. brain files present + index not stale vs newest md
chroma = os.path.join(ROOT, "brain", "chroma_db")
check(os.path.isdir(chroma) and any(os.scandir(chroma)), "brain index (brain/chroma_db) exists")

# 3. backup freshness (< 3 days) — must be a VERIFIED SUCCESS, not any file mtime.
# Audit 2026-07-10: the old newest-file-anywhere check went false-green because a
# failing LaunchAgent's growing error log looked "fresh". Truth = the last
# "backup ok" line in backup.log, cross-checked against an actual snapshot tarball.
# same folder as brain/backup_brain.sh: SA_BACKUP_ROOT, else its BACKUP_ROOT, else ~/Brain_Backups
bdir = (os.environ.get("SA_BACKUP_ROOT") or os.environ.get("BACKUP_ROOT")
        or os.path.expanduser("~/Brain_Backups"))
last_ok = 0
try:
    for line in open(os.path.join(bdir, "backup.log"), encoding="utf-8"):
        if "backup ok" in line and line.startswith("["):
            ts = line[1:line.index("]")]
            last_ok = time.mktime(time.strptime(ts, "%Y-%m-%d %H:%M:%S"))
except FileNotFoundError:
    pass
snaps = glob.glob(os.path.join(bdir, "snapshots", "*.tar.gz"))
newest_snap = max((os.path.getmtime(p) for p in snaps), default=0)
verified = min(last_ok, newest_snap) if (last_ok and newest_snap) else 0
age_d = (time.time() - verified) / 86400 if verified else 999
check(age_d < 3, "brain backup fresh (verified 'backup ok' + snapshot)",
      f"{age_d:.1f} days since last verified success" if verified else "no verified successful backup found")

# 3b. NAS backup freshness (< 10 days; stamp written by Tools/backup_to_nas.command)
stamp = os.path.join(ROOT, ".last_nas_backup")
try:
    last = datetime.date.fromisoformat(open(stamp).read().strip())
    nas_age = (datetime.date.today() - last).days
    check(nas_age <= 10, "NAS backup fresh", f"{nas_age} days ago — run Tools/backup_to_nas.command" if nas_age > 10 else f"{nas_age} days ago")
except FileNotFoundError:
    check(False, "NAS backup fresh", "never run — run Tools/backup_to_nas.command")

# 4. scheduled-task traces: visual-memory line in worklog within 2 days
try:
    wl = open(os.path.join(ROOT, "SA_WORKLOG.md"), encoding="utf-8").read()
    today = datetime.date.today()
    recent = any(f"[{(today - datetime.timedelta(days=d)).isoformat()}]" in line and "visual-memory" in line
                 for line in wl.splitlines() for d in range(3))
    check(recent, "visual-memory nightly leaving traces", "no trace in last 3 days" if not recent else "")
except Exception as e:
    check(False, "worklog readable", str(e))


# 4b. trending digest freshness (< 3 days)
try:
    digs = sorted(glob.glob(os.path.join(ROOT, "Trending", "DIGEST_*.md")))
    age = 99
    if digs:
        latest = os.path.basename(digs[-1])[7:17]
        age = (datetime.date.today() - datetime.date.fromisoformat(latest)).days
    check(age <= 2, "trending digest fresh", f"latest is {age} days old" if age > 2 else "")
except Exception as e:
    check(False, "trending digest check", str(e))

# 4c. heartbeat integrity — every STARTED in the last 3 days must have a matching
# FINISHED/FAILED line (audit 2026-07-10: a run can die silently mid-way; a lone
# STARTED means exactly that). No red for zero heartbeats here — 4/4b already
# catch missing output; this catches half-dead runs.
try:
    hb_path = os.path.join(ROOT, "Sessions", "automation_heartbeat.log")
    orphans = []
    if os.path.exists(hb_path):
        lines = [l.strip() for l in open(hb_path, encoding="utf-8") if l.strip()]
        # audit 2026-07-16: judge the LAST STARTED per task, however old — a lone
        # trailing STARTED means that task's most recent run died mid-way.
        # 2h grace so a currently-running job isn't flagged.
        last_start = {}
        for i, l in enumerate(lines):
            parts = l.split()
            if len(parts) >= 3 and parts[2] == "STARTED":
                try:
                    ts = datetime.datetime.fromisoformat(parts[0].replace("Z", "+00:00"))
                except ValueError:
                    continue
                last_start[parts[1]] = (i, ts, parts[0])
        grace = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=2)
        for task, (i, ts, raw) in sorted(last_start.items()):
            if ts > grace:
                continue
            done = any(task in l2 and ("FINISHED" in l2 or "FAILED" in l2)
                       for l2 in lines[i + 1:])
            if not done:
                orphans.append(f"{task} @ {raw}")
    check(not orphans, "automation heartbeats paired (STARTED→FINISHED)",
          "died mid-run: " + "; ".join(orphans) if orphans else "")
except Exception as e:
    check(False, "heartbeat log check", str(e))

# 5. git state
try:
    dirty = subprocess.run(["git", "-C", ROOT, "status", "--porcelain"],
                           capture_output=True, text=True).stdout.strip()
    n = len(dirty.splitlines()) if dirty else 0
    check(n < 10, f"git working tree ({n} uncommitted files)",
          "commit soon" if n >= 10 else "")
except Exception as e:
    check(False, "git", str(e))

# 6. deterministic agent-loop readiness, state drift and circuit breaker
try:
    loop = subprocess.run([sys.executable,
                           os.path.join(HERE, "sa_loop.py"), "audit", "--json"],
                          capture_output=True, text=True)
    # JSON is printed after audit artifacts are written; locate its first object.
    start = loop.stdout.find("{")
    result = json.loads(loop.stdout[start:]) if start >= 0 else {}
    score = result.get("score", 0)
    check(result.get("healthy", False), f"agent loop readiness ({score}/100 {result.get('level', 'L0')})",
          "; ".join(result.get("breaker_reasons", [])) or "see Reference/SA_LOOP_AUDIT.md")
except Exception as e:
    check(False, "agent loop readiness", str(e))

# 7. pinned third-party plugin, hook and secret-permission audit
try:
    security = subprocess.run([sys.executable, os.path.join(HERE, "sa_security.py"), "audit"],
                              capture_output=True, text=True)
    detail = "; ".join(line.strip() for line in security.stdout.splitlines() if line.strip())
    check(security.returncode == 0, "third-party plugin registry and hook hashes", detail)
except Exception as e:
    check(False, "third-party plugin security", str(e))

# write report
# tool catalogue stays fresh: regenerate it every doctor run so CHECK-BEFORE-NEW always
# has a live index (HARNESS_IDEAS "Do now" #5 — a hand-maintained map goes stale)
try:
    r = subprocess.run([sys.executable, os.path.join(HERE, "sa_toolindex.py")],
                       capture_output=True, text=True, timeout=60)
    check(r.returncode == 0, "tool catalogue regenerated",
          r.stdout.strip().split("->")[-1].strip() if r.returncode == 0 else r.stderr[:80])
except Exception as e:
    check(False, "tool catalogue regenerated", str(e)[:80])

# the nightly runner left a clean exit within the last day (dead-man visibility in doctor too)
try:
    marker = os.path.join(ROOT, "Sessions", "_nightly", "last_success")
    age_h = (time.time() - os.path.getmtime(marker)) / 3600 if os.path.exists(marker) else 1e9
    check(age_h < 26, "nightly runner completed in the last 26h",
          f"{age_h:.0f}h ago" if age_h < 1e8 else "never ran")
except Exception as e:
    check(False, "nightly runner completed in the last 26h", str(e)[:80])

ok_n = sum(1 for r in results if r[0])
report = [f"# System Doctor — {datetime.date.today().isoformat()}",
          f"> {ok_n}/{len(results)} checks passing. Run: `python3 Tools/sa_doctor.py`", ""]
for ok, label, detail in results:
    report.append(f"- {'🟢' if ok else '🔴'} **{label}**" + (f" — {detail}" if detail else ""))
open(os.path.join(ROOT, "Reference", "DOCTOR.md"), "w", encoding="utf-8").write("\n".join(report) + "\n")
print(f"\n{ok_n}/{len(results)} passing -> Reference/DOCTOR.md")
raise SystemExit(0 if ok_n == len(results) else 1)
