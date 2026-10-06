#!/usr/bin/env python3
"""sa_guard — the pre-flight gate. Lessons stop being prose and start refusing.

The 9 Aug post-mortem (Reference/MISTAKE_PATTERNS.md) found 76 mistakes since May and one
clean conclusion: **no written rule has ever stopped a repeat — only code has.** This module
is the keystone guard (missing guard #1) plus the approved-freeze list (missing guard #4):

  assert_not_frozen(project)   a video Saad declared done can NOT be written, ever.
                               Source of truth: 5 ADMIN/PROGRESS.json ("saad": "done") —
                               the same file the dashboard reads, updated as he reports.
  preflight("capcut_write")    CapCut must be closed; refuses otherwise.
  preflight("ollama_batch")    no second Ollama batch may start; refuses while one runs.
  check_not_already_built(x)   greps the generated tool catalogue before a new tool is
                               written; near-misses are printed and must be overridden.

    Tools/venv/bin/python3 Tools/sa_guard.py --test
    Tools/venv/bin/python3 Tools/sa_guard.py --status     # what is frozen right now

Wired into every tool that writes a CapCut project. A new write-tool must call
`guard.preflight("capcut_write", project=...)` before its first write — the doctor's
tool-hygiene list is where missing wiring shows up.

Instances this would have caught: an approved photo set auto-graded (23 Jun), approved
print masters regraded (24 Jun), the near-edit of a finished training module (9 Aug), the double Ollama run that
faked a fix failure (8 Aug), the clickdetect near-rebuild (9 Aug).
"""
import json
import os
import pathlib
import re
import subprocess
import sys

# The same file the dashboard and the other series tools read; TRAINING_ROOT moves the series.
PROGRESS = (pathlib.Path(os.environ.get("TRAINING_ROOT", "~/Downloads/training-series"))
            .expanduser() / "5 ADMIN" / "PROGRESS.json")
CATALOG = pathlib.Path(__file__).resolve().parents[1] / "Reference" / "TOOLS_CATALOG.md"

# PROGRESS.json keys -> CapCut project names. Explicit, because the two naming schemes
# diverge exactly where it is most dangerous (MOD 02 lives in "Renamed Example").
# Example entries; map your own series here.
PROJECT_OF = {
    "MOD 01": "MOD 01 Example A",
    "MOD 02": "Renamed Example",                # a project renamed without its number
    "MOD 03": "MOD 03 Example C",
    # one PROGRESS entry, two projects — a value may be a list
    "T04": ["MOD 04a Part One", "MOD 04b Part Two"],
}


class Frozen(SystemExit):
    """Raised when a write would touch work Saad has declared done."""


def frozen_projects(progress_path=PROGRESS):
    """-> set of CapCut project names Saad has finished. Read fresh every call —
    he reports progress mid-session and a cached list would unfreeze nothing."""
    try:
        prog = json.loads(pathlib.Path(progress_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    out = set()
    for name, st in prog.get("videos", {}).items():
        if st.get("saad") != "done":
            continue
        for prefix, proj in PROJECT_OF.items():
            if name.startswith(prefix):
                out.update([proj] if isinstance(proj, str) else proj)
                break
    return out


def assert_not_frozen(project, progress_path=PROGRESS):
    """Refuse any write to a project on the frozen list. The rule this enforces is
    Saad's oldest standing correction: never 'improve' what he has approved."""
    if project in frozen_projects(progress_path):
        raise Frozen(
            f"REFUSED: '{project}' is on Saad's done list (PROGRESS.json). His finished "
            f"work is never written by a tool. If he has genuinely asked for this exact "
            f"change, set his entry back to 'to edit' first — that decision is his, not "
            f"the tool's.")


def ancestors(pid=None):
    """-> {pid, parent, grandparent, … , 1}. The WHOLE chain, deliberately.

    Counting levels was always going to break; walk to init instead so the next
    wrapper someone adds cannot reintroduce a self-match."""
    import os
    pid = os.getpid() if pid is None else pid
    seen = set()
    while pid and pid > 1 and pid not in seen:
        seen.add(pid)
        out = subprocess.run(["ps", "-o", "ppid=", "-p", str(pid)],
                             capture_output=True, text=True).stdout.strip()
        try:
            pid = int(out)
        except ValueError:
            break
    return seen


def ollama_busy():
    """A second vision batch corrupts the first's timings and fakes failures (8 Aug).

    Match the WORKER (…​.py), never the harness. 12 Aug: the pattern was the bare name
    'sa_boxcheck', so it matched `caffeinate -im /bin/bash sa_boxcheck_all.sh` — the
    nightly's own wrapper, which is NOT in the ancestor chain (caffeinate sits beside
    the shell, not above it). All 17 sections refused inside one second and the run
    still logged 'ok'. Excluding ancestors alone does not save you from that; only the
    worker process actually loads the model, so only the worker counts.

    Excludes this process and every ancestor too: boxcheck calling this from inside
    itself matched its OWN pid and refused — which the 10 Aug nightly recorded as
    'clean'. A guard that can see itself is a guard that lies twice."""
    mine = ancestors()
    for pat in ("sa_boxcheck.py", "sa_visualmem.py", "sa_learn.py --analyse"):
        out = subprocess.run(["pgrep", "-f", pat], capture_output=True, text=True).stdout
        others = {int(p) for p in out.split()} - mine
        # 10 Sep: pgrep -f also matches the shell WRAPPER whose command line merely
        # contains the script path (the Bash tool runs `zsh -c "…eval '…sa_boxcheck.py…'"`),
        # so a lone invocation refused itself. Only the python WORKER actually loads the
        # model — keep pids whose argv[0] is python.
        real = []
        for pid in others:
            cmd = subprocess.run(["ps","-o","command=","-p",str(pid)],
                                 capture_output=True, text=True).stdout.lower()
            if "python" in cmd.split(" ",1)[0] or "/python" in cmd[:cmd.find(pat.split()[0])+1]:
                real.append(pid)
        if real:
            return pat
    return None


def preflight(task, project=None, progress_path=PROGRESS):
    """The gate. Call before starting; it raises rather than warns."""
    if task == "capcut_write":
        if subprocess.run(["pgrep", "-x", "CapCut"], capture_output=True).returncode == 0:
            raise SystemExit("REFUSED: CapCut is open. A draft written now is overwritten "
                             "when it saves — close it first.")
        if project:
            assert_not_frozen(project, progress_path)
    elif task == "ollama_batch":
        busy = ollama_busy()
        if busy:
            raise SystemExit(f"REFUSED: an Ollama batch is already running ({busy}). Two "
                             f"at once produced timeouts that read as a failed fix on "
                             f"8 Aug. Wait or stop it.")
    else:
        raise SystemExit(f"unknown preflight task {task!r} — add it, don't skip it")
    return True


def check_not_already_built(purpose, catalog_path=CATALOG):
    """-> [] if nothing similar exists, else the catalogue lines that look like it.

    Pattern 16: a capability was rebuilt while the tool sat on disk. Call with a few
    keywords before writing any new tool; a non-empty return means READ those first.
    """
    try:
        text = pathlib.Path(catalog_path).read_text(encoding="utf-8")
    except OSError:
        return []
    words = [w.lower() for w in re.findall(r"[a-z]{4,}", purpose.lower())]
    hits = []
    for line in text.splitlines():
        if not line.startswith("| `sa_"):
            continue
        score = sum(1 for w in words if w in line.lower())
        if score >= 2:
            hits.append(line.strip())
    return hits


def _test():
    import tempfile, os
    p = pathlib.Path(tempfile.mkdtemp()) / "PROGRESS.json"
    p.write_text(json.dumps({"videos": {
        "MOD 01  Example A": {"saad": "done"},
        "MOD 02  Example B (renamed)": {"saad": "done"},
        "MOD 03  Example C": {"saad": "to edit"},
        "T04  Parts One & Two": {"saad": "done"},
    }}))
    fz = frozen_projects(p)
    assert "MOD 01 Example A" in fz
    assert "Renamed Example" in fz, \
        "MOD 02 must map to its real project name — the dangerous divergence"
    assert "MOD 03 Example C" not in fz
    assert {"MOD 04a Part One", "MOD 04b Part Two"} <= fz, \
        "one T04 progress entry must freeze BOTH 04a and 04b"
    try:
        assert_not_frozen("MOD 01 Example A", p)
        raise AssertionError("a frozen project must refuse")
    except Frozen:
        pass
    assert_not_frozen("MOD 03 Example C", p)     # not frozen: passes silently
    # a missing progress file freezes nothing (fail-open on reads, fail-closed on writes
    # is wrong here: with no list there is nothing declared done)
    assert frozen_projects(pathlib.Path("/nope.json")) == set()
    # catalogue lookup finds the wheel before it is reinvented
    cat = pathlib.Path(tempfile.mkdtemp()) / "cat.md"
    cat.write_text("| `sa_clickdetect.py` | find the click moments in a screen-recording, "
                   "automatically. | yes |\n| `sa_beats.py` | beat grid for music. | yes |\n")
    hits = check_not_already_built("detect where clicks happen in a screen recording", cat)
    assert hits and "clickdetect" in hits[0]
    assert check_not_already_built("generate pptx slides from markdown", cat) == []
    # The guard must not see its own harness. This reproduces the exact nightly chain —
    # caffeinate -im /bin/bash sa_boxcheck_all.sh -> subshell -> python — which on
    # 12 Aug made every section refuse. caffeinate is NOT an ancestor, so this fails
    # unless the pattern matches the worker rather than the wrapper.
    chain = ancestors()
    assert os.getpid() in chain and os.getppid() in chain
    assert len(chain) >= 2, "ancestor walk stopped at self"
    d = pathlib.Path(tempfile.mkdtemp())
    w = d / "sa_boxcheck_all.sh"        # a wrapper whose NAME contains the tool name
    w.write_text('#!/bin/bash\nls | while read x; do "$1" "$2" --busy; done | cat\n')
    out = subprocess.run(["caffeinate", "-im", "/bin/bash", str(w), sys.executable, __file__],
                         capture_output=True, text=True, cwd=d).stdout
    assert out.strip().splitlines()[0] == "idle", \
        f"guard saw its own harness: {out.strip()!r}"
    print("sa_guard self-check: ok (freeze list, renamed-project mapping, refusal, catalogue, "
          "no self-detection through the real caffeinate+wrapper chain)")


if __name__ == "__main__":
    if "--test" in sys.argv:
        _test()
        sys.exit()
    if "--busy" in sys.argv:          # used by the self-check, from inside a wrapper chain
        print(ollama_busy() or "idle")
        sys.exit()
    if "--status" in sys.argv:
        fz = sorted(frozen_projects())
        print(f"{len(fz)} project(s) frozen (Saad has declared them done):")
        for f in fz:
            print(f"   {f}")
        busy = ollama_busy()
        print(f"ollama batch running: {busy or 'no'}")
        sys.exit()
    print(__doc__)
