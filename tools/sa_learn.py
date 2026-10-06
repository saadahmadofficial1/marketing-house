#!/usr/bin/env python3
"""sa_learn — turn a session of watching Saad edit into technique I can actually use.

Requirement (7 Aug 2026): learn the editing technique in enough detail to edit unaided in
future, then delete the screenshots once the learning is written down.

The two watchers produce two halves of the story. `sa_editwatch` records WHAT changed, in
exact numbers, from the project file. `sa_screenwatch` records the screen, which is the only
place the HOW lives — which panel he opened, what was selected, whether he was inspecting or
authoring. This joins them by the clock and writes the result somewhere permanent.

    Tools/venv/bin/python3 Tools/sa_learn.py --analyse    # after he closes CapCut
    Tools/venv/bin/python3 Tools/sa_learn.py --purge      # delete the frames, once learnt
    Tools/venv/bin/python3 Tools/sa_learn.py --test

Two rules built into this on purpose:

1. **It will not run while CapCut is open.** The vision pass makes the Mac stutter, and a
   session that is still going is not a session to draw conclusions from.
2. **--purge refuses unless the observations exist and cover the frames.** He asked for the
   images to be deleted after learning; deleting them *before* would throw away evidence
   that cannot be recreated. The frames are the proof behind every claim.

An action seen once is an observation, not a habit. This writes counts and examples and
leaves the conclusions to a reader who can ask him — the 7 Aug zoom was read as a style rule
when he was only magnifying the preview to look at it.
"""
import argparse
import collections
import datetime
import hashlib
import json
import os
import pathlib
import subprocess
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).parent))

SERIES = pathlib.Path(os.environ.get("TRAINING_ROOT", "~/Downloads/training-series")).expanduser()
FRAMES = SERIES / "5 ADMIN" / "_screenwatch"
EDITLOG = SERIES / "5 ADMIN" / "EDIT_WATCH.md"
OBS = FRAMES / "observations.json"
NOTES = pathlib.Path(__file__).resolve().parents[1] / "Reference" / "SAAD_EDITING_TECHNIQUE.md"

PROMPT = """This is the CapCut video editor, mid-edit. Describe only what you can see.

Reply with strict JSON, no prose:
{"panel": "timeline | preview | text panel | effects | export | media library | dialog | other",
 "doing": "what is happening on screen, in a few words",
 "selected": "the label or name of whatever is selected, if readable, else empty string",
 "dialog": "the title of any open dialog or panel, else empty string",
 "playhead": "visible CapCut playhead time if readable, else empty string",
 "tool": "visible editing tool or property being used, else empty string",
 "confidence": 0.0}"""


def _iso(value):
    return datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))


def _jsonl(path):
    if not path.exists():
        return []
    rows = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise SystemExit(f"invalid JSONL at {path}:{n}: {exc}")
    return rows


def assign_events_to_frames(frames, events, max_seconds=5.0):
    """Attach each exact timeline save to its nearest captured CapCut frame.

    This replaces the old minute-level join, which could attach one edit to twenty unrelated
    screenshots. Each event gets at most one visual neighbour and records the actual offset.
    """
    out = {f["file"]: [] for f in frames}
    dated = [(f, _iso(f["at"])) for f in frames if f.get("at")]
    for event in events:
        if not event.get("at") or not dated:
            continue
        when = _iso(event["at"])
        frame, frame_at = min(dated, key=lambda item: abs((item[1] - when).total_seconds()))
        delta = (frame_at - when).total_seconds()
        if abs(delta) <= max_seconds:
            out[frame["file"]].append({
                "event_id": event.get("event_id"),
                "project": event.get("project"),
                "timeline_id": event.get("timeline_id"),
                "changes": event.get("changes") or [],
                "frame_offset_seconds": round(delta, 3),
            })
    return out


def _net_changes(session_dir):
    """Final-surviving timeline delta for every touched timeline."""
    from sa_editwatch import describe
    before_dir = session_dir / "timeline_before"
    final_dir = session_dir / "timeline_final"
    rows = []
    for before_path in sorted(before_dir.glob("*.json")) if before_dir.exists() else []:
        final_path = final_dir / before_path.name
        if not final_path.exists():
            continue
        before = json.loads(before_path.read_text(encoding="utf-8"))
        final = json.loads(final_path.read_text(encoding="utf-8"))
        rows.append({"timeline_key": before_path.stem,
                     "changes_that_survived": describe(before, final)})
    return rows


def _write_session_report(session_dir, rows, events, net):
    panels, doing, _acts = summarise([
        {"panel": r.get("panel", ""), "doing": r.get("doing", ""),
         "selected": r.get("selected", ""), "dialog": r.get("dialog", ""),
         "edits_that_minute": [c for e in r.get("timeline_events", [])
                               for c in e.get("changes", [])]}
        for r in rows
    ])
    matched = sum(1 for r in rows if r.get("timeline_events"))
    stable = [change for item in net for change in item["changes_that_survived"]]
    report = [
        f"# CapCut Eyes learning — {session_dir.name}", "",
        "Local evidence only. Screenshots came from CapCut windows; timeline changes came "
        "from CapCut's own saved project JSON. This local pass uploaded no pixels.", "",
        f"- Frames read locally: {len(rows)}",
        f"- Exact timeline-save events: {len(events)}",
        f"- Frames paired to a timeline event within 5 seconds: {matched}",
        f"- Final-surviving timeline changes: {len(stable)}", "",
        "## What remained in the final saved timeline", "",
    ]
    if stable:
        report.extend(f"- {x}" for x in stable)
    else:
        report.append("- No net change survived, or no timeline edit was recorded.")
    report.extend(["", "## Where the editing time was visible", ""])
    report.extend(f"- {k}: {v} frame(s)" for k, v in panels.most_common(8))
    report.extend(["", "## Repeated visible actions (observations, not style rules)", ""])
    report.extend(f"- {k}: {v}" for k, v in doing.most_common(10))
    report.extend(["", "## Interpretation guard", "",
                   "Temporary or reverted actions are inspection/process evidence. Only "
                   "changes that survived into the final saved timeline are candidates for "
                   "an editing habit, and repeated sessions or Saad's confirmation are still "
                   "required before promoting a candidate into the editing grammar.", ""])
    text = "\n".join(report)
    (session_dir / "learning.md").write_text(text, encoding="utf-8")

    marker = f"## Eyes session {session_dir.name}"
    existing = NOTES.read_text(encoding="utf-8") if NOTES.exists() else ""
    if marker not in existing:
        NOTES.parent.mkdir(parents=True, exist_ok=True)
        with NOTES.open("a", encoding="utf-8") as f:
            if not existing:
                f.write("> hub: [[INDEX]] · [[SAAD_METHOD]] · [[EDITING_CONTRACT]]\n\n"
                        "# How Saad edits — observed, not assumed\n\n")
            f.write(f"\n---\n\n{marker}\n\n")
            f.write(f"{len(rows)} CapCut-window frames read locally; {len(events)} exact "
                    f"timeline saves; {len(stable)} final-surviving changes. Full evidence: "
                    f"`{session_dir / 'learning.md'}`.\n\n")
            if stable:
                f.write("**Final-surviving observations:**\n\n")
                for x in stable[:30]:
                    f.write(f"- {x}\n")
                f.write("\n")
            f.write("These are observations, not automatic style rules. Reverted changes "
                    "remain process/inspection evidence only.\n")
    return text


def analyse_session(session_dir, model=None, limit=None):
    if capcut_open():
        raise SystemExit("CapCut is still open — stop/close it before the local learning pass")
    session_dir = pathlib.Path(session_dir).expanduser().resolve()
    frames_dir = session_dir / "frames"
    index = _jsonl(frames_dir / "frame_index.jsonl")
    events = _jsonl(session_dir / "timeline_events.jsonl")
    if limit:
        index = index[:limit]
    if not index and not events:
        raise SystemExit(f"no frame or timeline evidence in {session_dir}")
    pairs = assign_events_to_frames(index, events)
    import sa_boxcheck
    if model:
        sa_boxcheck.VLM = model

    rows, unread = [], []
    for i, entry in enumerate(index, 1):
        path = frames_dir / entry["file"]
        if not path.exists():
            unread.append({"file": entry["file"], "reason": "missing_before_learning"})
            continue
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if entry.get("sha256") and actual != entry["sha256"]:
            unread.append({"file": entry["file"], "reason": "checksum_changed"})
            continue
        answer = {}
        for _attempt in range(2):
            answer = sa_boxcheck.ask(str(path), PROMPT) or {}
            if answer:
                break
        status = "read" if answer else "vision_failed"
        row = {"frame": entry["file"], "at": entry.get("at"),
               "sha256": actual, "vision_status": status,
               "panel": answer.get("panel", ""), "doing": answer.get("doing", ""),
               "selected": answer.get("selected", ""), "dialog": answer.get("dialog", ""),
               "playhead": answer.get("playhead", ""), "tool": answer.get("tool", ""),
               "confidence": answer.get("confidence", 0.0),
               "timeline_events": pairs.get(entry["file"], [])}
        rows.append(row)
        if status != "read":
            unread.append({"file": entry["file"], "reason": status})
        print(f"  {i:4d}/{len(index)} {str(entry.get('at', ''))[11:23]} "
              f"{row['panel'][:15]:15s} {row['doing'][:48]}")

    net = _net_changes(session_dir)
    record = {"schema": "sa-capcut-eyes-learning-v1", "session": session_dir.name,
              "analysed_at": datetime.datetime.now(datetime.timezone.utc).astimezone()
              .isoformat(timespec="milliseconds"),
              "local_only": True, "frame_count": len(index), "event_count": len(events),
              "unread": unread, "net_timeline_changes": net, "observations": rows}
    (session_dir / "observations.json").write_text(
        json.dumps(record, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_session_report(session_dir, rows, events, net)
    if unread:
        raise SystemExit(f"{len(unread)} frame(s) were not safely read; observations kept, "
                         "screenshots will not be deleted")
    print(f"\n{len(rows)} frame(s) read locally -> {session_dir / 'observations.json'}")
    print(f"durable learning -> {session_dir / 'learning.md'} and {NOTES}")
    return rows


def purge_session(session_dir):
    session_dir = pathlib.Path(session_dir).expanduser().resolve()
    frames_dir = session_dir / "frames"
    obs_path = session_dir / "observations.json"
    if not obs_path.exists():
        raise SystemExit("nothing has been learnt yet; refusing to delete screenshots")
    record = json.loads(obs_path.read_text(encoding="utf-8"))
    if record.get("unread"):
        raise SystemExit("some screenshots were not read successfully; refusing to delete")
    indexed = {x["file"]: x for x in _jsonl(frames_dir / "frame_index.jsonl")}
    observed = {x["frame"]: x for x in record.get("observations", [])
                if x.get("vision_status") == "read"}
    on_disk = {p.name for p in frames_dir.glob("*.png")}
    if on_disk != set(indexed) or on_disk != set(observed):
        raise SystemExit("frame/index/observation coverage differs; refusing to delete")
    receipt = []
    for name in sorted(on_disk):
        path = frames_dir / name
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != indexed[name].get("sha256") or actual != observed[name].get("sha256"):
            raise SystemExit(f"checksum mismatch for {name}; refusing to delete any frame")
        receipt.append({"file": name, "sha256": actual, "bytes": path.stat().st_size})
    # Every validation happens before the first unlink, making partial evidence loss much
    # less likely. The receipt preserves exactly what was removed after durable learning.
    for name in sorted(on_disk):
        (frames_dir / name).unlink()
    (session_dir / "purge_receipt.json").write_text(json.dumps({
        "schema": "sa-capcut-eyes-purge-v1",
        "purged_at": datetime.datetime.now(datetime.timezone.utc).astimezone()
        .isoformat(timespec="milliseconds"),
        "count": len(receipt), "files": receipt,
        "learning": str(session_dir / "learning.md")}, indent=1) + "\n", encoding="utf-8")
    print(f"{len(receipt)} learned screenshot(s) deleted; evidence and learning retained")
    return len(receipt)


def capcut_open():
    return subprocess.run(["pgrep", "-x", "CapCut"], capture_output=True).returncode == 0


def stamp_from_name(name, today=None):
    """"103417_w0.png" -> "…T10:34:17". Pure, so the join can be tested.

    The screenshot filename carries the clock, which makes the pairing independent of
    index.json — a file the watcher only writes on exit.
    """
    m = __import__("re").match(r"(\d{2})(\d{2})(\d{2})", name)
    if not m:
        return ""
    d = today or datetime.date.today().isoformat()
    return f"{d}T{m.group(1)}:{m.group(2)}:{m.group(3)}"


def edits_by_minute(text):
    """-> {'HH:MM': [line, ...]} from the edit log. Pure, so the join is testable."""
    out = collections.defaultdict(list)
    stamp = None
    for line in text.splitlines():
        if line.startswith("**") and " · " in line:
            parts = line.strip("* ").split(" · ")[0].split()
            stamp = parts[-1][:5] if parts else None
        elif line.startswith("- ") and stamp:
            out[stamp].append(line[2:])
    return dict(out)


def analyse(model=None, limit=None):
    if capcut_open():
        raise SystemExit("CapCut is still open — learn from a finished session, not a "
                         "half-done one, and don't slow the Mac while he works")
    if not FRAMES.exists():
        raise SystemExit(f"no frames to learn from: {FRAMES}")
    import sa_boxcheck
    if model:
        sa_boxcheck.VLM = model

    idx_file = FRAMES / "index.json"
    idx = json.loads(idx_file.read_text()) if idx_file.exists() else []
    idx = [e for e in idx if (FRAMES / e["file"]).exists()]
    known = {e["file"] for e in idx}
    # The filename IS the clock — "HHMMSS_w0.png". index.json is only written when the
    # watcher exits, so a session that is still running (or was killed) leaves every frame
    # with no timestamp, and the join to the edit log silently matched nothing: 0 of 203
    # frames paired (7 Aug). Read the time off the name and never depend on the index.
    for p in sorted(FRAMES.glob("*.png")):
        if p.name not in known:
            idx.append({"file": p.name, "at": stamp_from_name(p.name)})
    idx = [e for e in idx if e.get("at")]
    idx.sort(key=lambda e: e["at"])
    if limit:
        idx = idx[:limit]
    if not idx:
        raise SystemExit("no frames on disk")

    edits = edits_by_minute(EDITLOG.read_text(encoding="utf-8")) if EDITLOG.exists() else {}
    rows = []
    for i, e in enumerate(idx, 1):
        r = sa_boxcheck.ask(str(FRAMES / e["file"]), PROMPT) or {}
        minute = (e.get("at") or "")[11:16]
        rows.append({"frame": e["file"], "at": e.get("at", ""),
                     "panel": r.get("panel", ""), "doing": r.get("doing", ""),
                     "selected": r.get("selected", ""), "dialog": r.get("dialog", ""),
                     "edits_that_minute": edits.get(minute, [])})
        print(f"  {i:3d}/{len(idx)}  {minute or '--:--'}  {r.get('panel',''):14s} "
              f"{r.get('doing','')[:46]}")
    OBS.write_text(json.dumps(rows, indent=1), encoding="utf-8")
    write_notes(rows)
    print(f"\n{len(rows)} frame(s) read -> {OBS}\n-> {NOTES}")
    print("frames kept until you have read the notes; then: sa_learn.py --purge")
    return rows


def summarise(rows):
    """-> counts a person can check. Pure."""
    panels = collections.Counter(r["panel"] for r in rows if r["panel"])
    doing = collections.Counter(r["doing"].lower() for r in rows if r["doing"])
    acts = collections.Counter()
    for r in rows:
        for line in r["edits_that_minute"]:
            acts[line.split()[0]] += 1
    return panels, doing, acts


def write_notes(rows):
    panels, doing, acts = summarise(rows)
    stamp = datetime.datetime.now().strftime("%d %b %Y %H:%M")
    NOTES.parent.mkdir(parents=True, exist_ok=True)
    new = not NOTES.exists()
    with NOTES.open("a", encoding="utf-8") as f:
        if new:
            f.write("> hub: [[INDEX]] · [[SAAD_METHOD]] · [[EDITING_CONTRACT]]\n\n"
                    "# How Saad edits — observed, not assumed\n\n"
                    "Built by watching real sessions: the CapCut project file for what "
                    "changed, the screen for how. Counts and examples only.\n\n"
                    "**An action seen once is an observation, not a habit.** Ask him what "
                    "it was for before turning any of this into a rule — on 7 Aug a zoom to "
                    "248% was read as a style choice when he was magnifying the preview to "
                    "inspect it with his own eyes.\n\n---\n\n")
        f.write(f"## Session {stamp} — {len(rows)} frames\n\n")
        f.write("**Where he spent the time:** "
                + ", ".join(f"{k} ×{v}" for k, v in panels.most_common(6)) + "\n\n")
        if acts:
            f.write("**What he changed:** "
                    + ", ".join(f"{k} ×{v}" for k, v in acts.most_common()) + "\n\n")
        if doing:
            f.write("**Most repeated on-screen action:**\n")
            for k, v in doing.most_common(6):
                f.write(f"- {k} (×{v})\n")
            f.write("\n")
        withedit = [r for r in rows if r["edits_that_minute"]]
        if withedit:
            f.write("**Screen and project file together — the moments worth reading:**\n\n")
            for r in withedit[:12]:
                f.write(f"- `{r['at'][11:]}` {r['panel']}: {r['doing']}"
                        + (f" (selected: {r['selected']})" if r["selected"] else "") + "\n")
                for line in r["edits_that_minute"][:3]:
                    f.write(f"    - {line}\n")
            f.write("\n")
        f.write("---\n\n")


def purge(force=False):
    """Delete the frames, but only once the learning is safely written."""
    if not OBS.exists():
        raise SystemExit("nothing has been learnt yet — run --analyse first. Deleting the "
                         "frames now would throw away evidence that cannot be recreated.")
    rows = json.loads(OBS.read_text())
    seen = {r["frame"] for r in rows}
    on_disk = {p.name for p in FRAMES.glob("*.png")}
    unread = on_disk - seen
    if unread and not force:
        raise SystemExit(f"{len(unread)} frame(s) were never read — run --analyse again, "
                         f"or --purge --force to bin them unread")
    if not NOTES.exists():
        raise SystemExit(f"the notes file is missing: {NOTES}")
    n = 0
    for p in FRAMES.glob("*.png"):
        p.unlink()
        n += 1
    (FRAMES / "index.json").unlink(missing_ok=True)
    print(f"{n} screenshot(s) deleted. The learning is kept in:\n  {NOTES}\n  {OBS}")
    return n


def _test():
    log = ("**07 Aug 10:07:29 · Demo 01**\n\n- moved \"video\" 2 down\n- resized \"video\"\n\n"
           "**07 Aug 10:12:01 · Demo 01**\n\n- held \"Click Save\" by 1.90s\n")
    by = edits_by_minute(log)
    assert by["10:07"] == ['moved "video" 2 down', 'resized "video"'], by
    assert by["10:12"] == ['held "Click Save" by 1.90s']
    assert "10:99" not in by
    rows = [{"panel": "timeline", "doing": "dragging a clip", "selected": "", "dialog": "",
             "edits_that_minute": ['moved "video" 2 down']},
            {"panel": "timeline", "doing": "dragging a clip", "selected": "", "dialog": "",
             "edits_that_minute": []},
            {"panel": "preview", "doing": "scrubbing", "selected": "", "dialog": "",
             "edits_that_minute": ['held "x" by 1.90s']}]
    panels, doing, acts = summarise(rows)
    assert panels["timeline"] == 2 and panels["preview"] == 1
    assert doing["dragging a clip"] == 2
    assert acts["moved"] == 1 and acts["held"] == 1
    # the filename is the clock — this is what makes the join work without index.json
    assert stamp_from_name("103417_w0.png", "2026-08-07") == "2026-08-07T10:34:17"
    assert stamp_from_name("100540.png", "2026-08-07")[11:16] == "10:05"
    assert stamp_from_name("observations.json") == "", "non-frame files carry no time"
    # and the minute it yields must be the key edits_by_minute uses
    assert stamp_from_name("101718_w1.png", "2026-08-07")[11:16] in edits_by_minute(
        "**07 Aug 10:17:18 · X**\n\n- slid \"Captions\" 6.10s earlier\n")
    frames = [{"file": "a.png", "at": "2026-09-04T10:00:00+04:00"},
              {"file": "b.png", "at": "2026-09-04T10:00:04+04:00"}]
    events = [{"event_id": "e1", "at": "2026-09-04T10:00:03.400+04:00",
               "project": "P", "timeline_id": "T", "changes": ["trimmed clip"]}]
    paired = assign_events_to_frames(frames, events)
    assert not paired["a.png"] and paired["b.png"][0]["event_id"] == "e1"
    assert paired["b.png"][0]["frame_offset_seconds"] == 0.6
    with tempfile.TemporaryDirectory() as d:
        session = pathlib.Path(d)
        frame_dir = session / "frames"
        frame_dir.mkdir()
        frame = frame_dir / "proof.png"
        frame.write_bytes(b"proof")
        digest = hashlib.sha256(b"proof").hexdigest()
        (frame_dir / "frame_index.jsonl").write_text(json.dumps({
            "file": frame.name, "sha256": digest}) + "\n", encoding="utf-8")
        (session / "learning.md").write_text("learnt", encoding="utf-8")
        (session / "observations.json").write_text(json.dumps({
            "unread": [], "observations": [{"frame": frame.name, "sha256": digest,
                                               "vision_status": "read"}]}), encoding="utf-8")
        assert purge_session(session) == 1 and not frame.exists()
        assert (session / "purge_receipt.json").exists()
    print("sa_learn self-check: ok (exact frame join and checksum-gated purge)")


if __name__ == "__main__":
    if "--test" in sys.argv:
        _test()
        sys.exit()
    ap = argparse.ArgumentParser()
    ap.add_argument("--analyse", action="store_true")
    ap.add_argument("--purge", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--model")
    ap.add_argument("--session-dir", help="isolated Sessions/_eyes run")
    a = ap.parse_args()
    if a.analyse:
        analyse_session(a.session_dir, a.model, a.limit) if a.session_dir else \
            analyse(a.model, a.limit)
    elif a.purge:
        purge_session(a.session_dir) if a.session_dir else purge(a.force)
    else:
        ap.error("give --analyse or --purge")
