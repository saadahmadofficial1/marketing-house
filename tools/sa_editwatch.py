#!/usr/bin/env python3
"""sa_editwatch — watch Saad edit in CapCut, live, and write down what he does.

The brief: watch a live editing session and log what changes, like a screen recording
but readable, and live.

Screen recording would be the worse answer. CapCut saves the whole timeline to JSON every few
seconds while he works, so his edits can be read as numbers instead of guessed from pixels —
which box he dragged and exactly where to, how many frames he froze, which word he retyped.
No screen capture, no permissions, no pixels: it runs locally and uploads nothing.

This is the live front end for machinery that already exists: sa_stylebrain.py encodes his
finished projects and sa_style_delta.py compares a generated plan against his re-cut. Those
run after the fact. This one runs WHILE he edits, so nothing is lost if he never saves a
separate version — and it catches the small corrections he makes and forgets.

    Tools/venv/bin/python3 Tools/sa_editwatch.py                  # every CapCut project
    Tools/venv/bin/python3 Tools/sa_editwatch.py "My Project"
    Tools/venv/bin/python3 Tools/sa_editwatch.py --summary        # what has been learned
    Tools/venv/bin/python3 Tools/sa_editwatch.py --test

Read-only on the drafts. It never writes to a CapCut project — one process writing a draft
while CapCut has it open is how you lose an afternoon's work.
"""
import argparse
import datetime
import glob
import hashlib
import json
import os
import pathlib
import signal
import sys
import time

US = 1_000_000
CAPCUT = pathlib.Path("~/Movies/CapCut/User Data/Projects/com.lveditor.draft").expanduser()
ROOT = pathlib.Path(__file__).resolve().parents[1]
SNAPS = ROOT / "Sessions" / "_editwatch"
# where the running log goes; override with SA_EDITWATCH_LOG
LOG = pathlib.Path(os.environ.get("SA_EDITWATCH_LOG", str(SNAPS / "EDIT_WATCH.md"))).expanduser()
EYES_ROOT = ROOT / "Sessions" / "_eyes"
UI = 1000.0                     # CapCut's position readout is the normalised value x1000


def segments(draft):
    """-> {segment id: flat facts}, keyed so the same clip can be followed across saves."""
    out = {}
    for track_index, tr in enumerate(draft.get("tracks", [])):
        name = (tr.get("name") or "").strip() or tr.get("type", "?")
        for segment_index, s in enumerate(tr.get("segments", [])):
            t = s.get("target_timerange") or {}
            src = s.get("source_timerange") or {}
            clip = s.get("clip") or {}
            tf = clip.get("transform") or {}
            sc = clip.get("scale") or {}
            out[s.get("id")] = {
                "track": name,
                "track_type": tr.get("type", "?"),
                "track_index": track_index,
                "segment_index": segment_index,
                "start": round(t.get("start", 0) / US, 3),
                "dur": round(t.get("duration", 0) / US, 3),
                "src_start": round(src.get("start", 0) / US, 3),
                "src_dur": round(src.get("duration", 0) / US, 3),
                "speed": round(s.get("speed", 1.0), 3),
                "volume": round(s.get("volume", 1.0), 3),
                "x": round(tf.get("x", 0.0) * UI),
                "y": round(tf.get("y", 0.0) * UI),
                "scale": round(sc.get("x", 1.0), 3),
                "rotation": round(clip.get("rotation", 0.0), 3),
                "alpha": round(clip.get("alpha", 1.0), 3),
                "visible": bool(s.get("visible", True)),
                "keyframes": len(s.get("common_keyframes") or []),
                "material": s.get("material_id"),
            }
    return out


def texts(draft):
    """-> {material id: the words on screen}."""
    out = {}
    for m in draft.get("materials", {}).get("texts", []) or []:
        try:
            out[m["id"]] = json.loads(m.get("content") or "{}").get("text", "")
        except (json.JSONDecodeError, TypeError):
            pass
    return out


def track_order(draft):
    """Stable track identities in stack order, used once per save instead of per clip.

    CapCut inserts a new lane by shifting every lane below it. Segment track indexes then
    all change even though Saad did not move those clips, so indexes are presentation
    evidence—not individual edit evidence.
    """
    out = []
    unnamed_seen = {}
    for index, track in enumerate(draft.get("tracks", [])):
        label = (track.get("name") or "").strip() or track.get("type", "?")
        if track.get("id"):
            key = f"id:{track['id']}"
        else:
            # Some saves omit the type on an otherwise unchanged named lane. The visible
            # name is the least noisy fallback; occurrence keeps repeated names distinct.
            base = f"fallback:{label}"
            occurrence = unnamed_seen.get(base, 0) + 1
            unnamed_seen[base] = occurrence
            key = f"{base}:{occurrence}"
        out.append({"key": key, "label": label, "index": index})
    return out


def describe(before, after):
    """-> list of plain-English sentences for what changed between two saves.

    Pure: two draft dicts in, sentences out. The whole point of the tool is this function,
    so it is the part that gets tested.
    """
    sb, sa = segments(before), segments(after)
    tb, ta = texts(before), texts(after)
    said = []

    # Describe a lane-stack change once. Never report every unchanged segment below an
    # inserted lane as having moved tracks—that is CapCut renumbering, not Saad's action.
    before_tracks, after_tracks = track_order(before), track_order(after)
    before_keys = {track["key"] for track in before_tracks}
    after_keys = {track["key"] for track in after_tracks}
    for track in after_tracks:
        if track["key"] not in before_keys:
            said.append(f"added track \"{track['label']}\" at layer {track['index'] + 1}")
    for track in before_tracks:
        if track["key"] not in after_keys:
            said.append(f"removed track \"{track['label']}\" from layer {track['index'] + 1}")
    if before_keys == after_keys and [t["key"] for t in before_tracks] != [
            t["key"] for t in after_tracks]:
        said.append("reordered the track stack")

    # From the track list, not from the segments: a track he emptied still exists, and
    # refilling it is not a new call-out.
    old_tracks = {(t.get("name") or "").strip() or t.get("type", "?")
                  for t in before.get("tracks", [])}
    for sid in sa.keys() - sb.keys():
        s = sa[sid]
        if s["track"] not in old_tracks:
            # A track name that did not exist before is a NEW CALL-OUT he has added by hand.
            # This is the most valuable line in the whole log: it names a moment the build
            # failed to highlight, at the exact second he thinks it should have been.
            # Hand-added boxes fill in highlights the build skipped. Never let this read
            # as an ordinary clip insert.
            said.append(f"** ADDED A NEW CALL-OUT: \"{s['track']}\" at {s['start']:.1f}s "
                        f"for {s['dur']:.1f}s — a step the build missed **")
        else:
            said.append(f"added a clip on \"{s['track']}\" at {s['start']:.1f}s "
                        f"lasting {s['dur']:.1f}s")
    for sid in sb.keys() - sa.keys():
        s = sb[sid]
        said.append(f"deleted the clip on \"{s['track']}\" that ran "
                    f"{s['start']:.1f}-{s['start'] + s['dur']:.1f}s")

    for sid in sb.keys() & sa.keys():
        a, b = sb[sid], sa[sid]
        who = f"\"{b['track']}\""
        if abs(a["x"] - b["x"]) > 2 or abs(a["y"] - b["y"]) > 2:
            dx, dy = b["x"] - a["x"], b["y"] - a["y"]
            way = []
            if dy:
                way.append(f"{abs(dy)} {'up' if dy > 0 else 'down'}")
            if dx:
                way.append(f"{abs(dx)} {'right' if dx > 0 else 'left'}")
            said.append(f"moved {who} {' and '.join(way)} "
                        f"(now {b['x']}, {b['y']})")
        if abs(a["scale"] - b["scale"]) > 0.005:
            said.append(f"resized {who} from {a['scale']:.0%} to {b['scale']:.0%}")
        if abs(a["dur"] - b["dur"]) > 0.05:
            d = b["dur"] - a["dur"]
            said.append(f"{'held' if d > 0 else 'shortened'} {who} by {abs(d):.2f}s "
                        f"({a['dur']:.2f} -> {b['dur']:.2f}s)")
        if abs(a["start"] - b["start"]) > 0.05:
            said.append(f"slid {who} {abs(b['start'] - a['start']):.2f}s "
                        f"{'later' if b['start'] > a['start'] else 'earlier'}")
        if abs(a["speed"] - b["speed"]) > 0.02:
            said.append(f"changed the speed of {who} from {a['speed']:.2f}x to {b['speed']:.2f}x")
        if abs(a["volume"] - b["volume"]) > 0.02:
            said.append(f"set the volume of {who} from {a['volume']:.0%} to {b['volume']:.0%}")
        if abs(a["src_start"] - b["src_start"]) > 0.05:
            said.append(f"trimmed the source of {who} from {a['src_start']:.2f}s "
                        f"to {b['src_start']:.2f}s")
        if abs(a["rotation"] - b["rotation"]) > 0.05:
            said.append(f"rotated {who} from {a['rotation']:.1f}° to {b['rotation']:.1f}°")
        if abs(a["alpha"] - b["alpha"]) > 0.01:
            said.append(f"changed opacity of {who} from {a['alpha']:.0%} to {b['alpha']:.0%}")
        if a["keyframes"] != b["keyframes"]:
            said.append(f"changed keyframes on {who} from {a['keyframes']} to {b['keyframes']}")

    for mid in tb.keys() & ta.keys():
        if tb[mid] != ta[mid]:
            said.append(f"retyped \"{tb[mid][:44]}\" as \"{ta[mid][:44]}\"")
    return said


def draft_paths(project):
    p = CAPCUT / project
    return sorted(glob.glob(str(p / "Timelines/*/draft_info.json")))


def series_projects(prefix="Training "):
    """Projects that belong to one numbered series, by name prefix."""
    return sorted(d.name for d in CAPCUT.iterdir()
                  if d.is_dir() and d.name.startswith(prefix))


def all_projects():
    """Every readable CapCut project, including projects created after the watcher starts."""
    if not CAPCUT.exists():
        return []
    return sorted(d.name for d in CAPCUT.iterdir() if d.is_dir() and draft_paths(d.name))


def load(path):
    """CapCut writes the file in place, so a read can land mid-write. -> dict or None."""
    try:
        return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return None


def saad_is_editing():
    """Is a change to a draft right now HIS work, or a script's?

    He can only edit while CapCut is open, and every tool here refuses to write a draft
    unless CapCut is closed. So the running process is a clean discriminator, with no
    lock files or coordination to forget. Without this the log filled with 1,393 of the
    agent's own caption writes in one minute (7 Aug) — which would have taught the system
    that Saad's editing style is "changes 1,393 things at 09:54".
    """
    import subprocess
    result = subprocess.run(["pgrep", "-x", "CapCut"], capture_output=True, text=True)
    if result.returncode == 0:
        return True
    if result.returncode == 1 and not result.stderr.strip():
        return False
    # Some sandboxed/menu-bar launches cannot inspect the process table. Unknown must not
    # silently erase a real timeline change; record it with reduced authorship confidence.
    return None


def snap_path(path):
    key = hashlib.sha1(path.encode()).hexdigest()[:12]
    return SNAPS / f"{key}.json"


def _sha(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":"))
                          .encode("utf-8")).hexdigest()


def _atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def _owner_alive(pid):
    if not pid:
        return True
    try:
        os.kill(int(pid), 0)
        return True
    except (OSError, ValueError):
        return False


def _timeline_key(path):
    p = pathlib.Path(path)
    rel = p.relative_to(CAPCUT)
    project = rel.parts[0]
    timeline = rel.parts[2] if len(rel.parts) > 3 and rel.parts[1] == "Timelines" else "root"
    key = hashlib.sha1(str(rel).encode()).hexdigest()[:12]
    return project, timeline, str(rel), key


def note(project, timeline, relpath, lines, before, after, session_dir=None,
         capcut_state=True):
    stamp = datetime.datetime.now().strftime("%d %b %H:%M:%S")
    target = (pathlib.Path(session_dir) / "timeline_changes.md") if session_dir else LOG
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_text("# What Saad actually did\n\n"
                          "Read live from CapCut's saved timeline while he edits. Each event "
                          "also has exact machine evidence in `timeline_events.jsonl`.\n\n",
                          encoding="utf-8")
    with target.open("a", encoding="utf-8") as f:
        f.write(f"**{stamp} · {project} · {timeline}**\n\n")
        for l in lines:
            f.write(f"- {l}\n")
        f.write("\n")
    if session_dir:
        session_dir = pathlib.Path(session_dir)
        _project, _timeline, _rel, key = _timeline_key(CAPCUT / relpath)
        before_path = session_dir / "timeline_before" / f"{key}.json"
        final_path = session_dir / "timeline_final" / f"{key}.json"
        if not before_path.exists():
            _atomic_json(before_path, before)
        _atomic_json(final_path, after)
        now = datetime.datetime.now(datetime.timezone.utc).astimezone().isoformat(timespec="milliseconds")
        event = {
            "schema": "sa-capcut-eyes-event-v1",
            "event_id": hashlib.sha1(f"{now}:{relpath}:{_sha(after)}".encode()).hexdigest()[:16],
            "at": now,
            "project": project,
            "timeline_id": timeline,
            "draft_path": relpath,
            "before_sha256": _sha(before),
            "after_sha256": _sha(after),
            "changes": lines,
            "source": "capcut_saved_timeline",
            "authorship": ("Saad_editing_CapCut_open" if capcut_state is True else
                           "timeline_change_recorded_process_visibility_unknown"),
            "interpretation": "observation_only_until_final_state_and_review",
        }
        with (session_dir / "timeline_events.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
    for l in lines:
        print(f"  {l}")


def watch(projects=None, interval=4.0, once=False, session_dir=None, owner_pid=None):
    SNAPS.mkdir(parents=True, exist_ok=True)
    dynamic = projects is None
    projects = all_projects() if dynamic else projects
    paths = [(p, d) for p in projects for d in draft_paths(p)]
    if not paths:
        raise SystemExit("no CapCut projects found to watch")
    print(f"watching {len(paths)} timeline(s) across {len(projects)} project(s); "
          f"ctrl-C to stop\n-> "
          f"{pathlib.Path(session_dir) / 'timeline_changes.md' if session_dir else LOG}")
    seen = {}
    for proj, d in paths:                     # baseline first, so the first diff is real work
        cur = load(d)
        if cur is not None:
            seen[d] = cur
            snap_path(d).write_text(json.dumps(cur), encoding="utf-8")
    changes = 0
    stopping = False

    def _stop(_signum, _frame):
        nonlocal stopping
        stopping = True

    old_term = signal.signal(signal.SIGTERM, _stop)
    old_int = signal.signal(signal.SIGINT, _stop)
    try:
        while True:
            if not _owner_alive(owner_pid):
                print("owner pad closed; stopping timeline observation")
                break
            if dynamic:
                current = [(p, d) for p in all_projects() for d in draft_paths(p)]
                known = {d for _p, d in paths}
                for proj, d in current:
                    if d not in known:
                        paths.append((proj, d))
                        cur = load(d)
                        if cur is not None:
                            seen[d] = cur
            for proj, d in paths:
                cur = load(d)
                if cur is None or d not in seen:
                    if cur is not None:
                        seen[d] = cur
                    continue
                lines = describe(seen[d], cur)
                if lines:
                    edit_state = saad_is_editing()
                    if edit_state is not False:
                        changes += len(lines)
                        project, timeline, relpath, _key = _timeline_key(d)
                        note(project, timeline, relpath, lines, seen[d], cur, session_dir,
                             edit_state)
                    # either way, re-baseline: a script's change is the new starting point,
                    # it must not resurface as "his" the next time he opens the project
                    seen[d] = cur
                    snap_path(d).write_text(json.dumps(cur), encoding="utf-8")
            if once or stopping:
                break
            time.sleep(interval)
    except KeyboardInterrupt:
        pass
    finally:
        signal.signal(signal.SIGTERM, old_term)
        signal.signal(signal.SIGINT, old_int)
    print(f"\n{changes} change(s) recorded -> "
          f"{pathlib.Path(session_dir) / 'timeline_changes.md' if session_dir else LOG}")
    return changes


def summary():
    """What the watching has taught, as counts he can sanity-check."""
    if not LOG.exists():
        raise SystemExit(f"nothing recorded yet: {LOG}")
    import re
    text = LOG.read_text(encoding="utf-8")
    moves = re.findall(r"moved .*?\(now (-?\d+), (-?\d+)\)", text)
    holds = [float(x) for x in re.findall(r"held .*? by ([\d.]+)s", text)]
    trims = [float(x) for x in re.findall(r"shortened .*? by ([\d.]+)s", text)]
    retypes = re.findall(r'retyped "(.*?)" as "(.*?)"', text)
    print(f"boxes repositioned : {len(moves)}")
    print(f"frames held        : {len(holds)}"
          + (f"   median {sorted(holds)[len(holds) // 2]:.2f}s, "
             f"range {min(holds):.2f}-{max(holds):.2f}s" if holds else ""))
    print(f"clips shortened    : {len(trims)}"
          + (f"   median {sorted(trims)[len(trims) // 2]:.2f}s" if trims else ""))
    print(f"words changed      : {len(retypes)}")
    for a, b in retypes[:12]:
        print(f'   "{a}" -> "{b}"')
    if holds:
        print(f"\nHis hold is the number that matters: he is telling you how long a screen "
              f"needs to sit.\nmedian {sorted(holds)[len(holds) // 2]:.2f}s — "
              f"sa_dubcut DEFAULT_GAP should not sit below it.")


def _test():
    def draft(x=0.0, y=0.0, dur=2.0, start=1.0, text="Click Save", speed=1.0, sid="s1"):
        return {"materials": {"texts": [{"id": "m1",
                                         "content": json.dumps({"text": text})}]},
                "tracks": [{"name": "Click Save", "type": "text", "segments": [
                    {"id": sid, "material_id": "m1", "speed": speed, "volume": 1.0,
                     "clip": {"transform": {"x": x, "y": y}, "scale": {"x": 1.0}},
                     "target_timerange": {"start": int(start * US), "int": 0,
                                          "duration": int(dur * US)},
                     "source_timerange": {"start": 0, "duration": int(dur * US)}}]}]}

    assert describe(draft(), draft()) == [], "an untouched project reports nothing"
    # he drags a box up: y goes positive in CapCut's readout
    d = describe(draft(y=0.0), draft(y=0.074))
    assert len(d) == 1 and "74 up" in d[0] and "now 0, 74" in d[0], d
    # he freezes a frame — the clip gets longer
    d = describe(draft(dur=2.0), draft(dur=3.9))
    assert "held" in d[0] and "1.90s" in d[0], d
    # he shortens one
    assert "shortened" in describe(draft(dur=4.0), draft(dur=2.0))[0]
    # he fixes a word
    d = describe(draft(text="Clik Save"), draft(text="Click Save"))
    assert d == ['retyped "Clik Save" as "Click Save"'], d
    # he deletes the clip, then adds a different one
    empty = {"materials": {"texts": []}, "tracks": [{"name": "Click Save", "segments": []}]}
    assert "deleted" in describe(draft(), empty)[0]
    # the track already existed, so this is an ordinary insert, not a new call-out
    d = describe(empty, draft())[0]
    assert "added a clip" in d and "NEW CALL-OUT" not in d, d
    # a track name that never existed before IS a new call-out, and must shout about it
    before = {"materials": {"texts": []}, "tracks": [{"name": "video", "segments": [
        {"id": "v", "target_timerange": {"start": 0, "duration": int(9 * US)},
         "source_timerange": {"start": 0, "duration": int(9 * US)}}]}]}
    after = json.loads(json.dumps(before))
    after["tracks"].append({"name": "Click Generate Invoice", "segments": [
        {"id": "n1", "target_timerange": {"start": int(42.5 * US),
                                          "duration": int(3 * US)},
         "source_timerange": {"start": 0, "duration": int(3 * US)}}]})
    d = describe(before, after)
    assert len(d) == 2 and "added track" in d[0] and "NEW CALL-OUT" in d[1], d
    assert "Click Generate Invoice" in d[1] and "42.5s" in d[1], d
    # Inserting a lane shifts every later track index. That must be logged once as a lane
    # addition, never as one fake move per unchanged clip.
    stable_before = {"materials": {"texts": []}, "tracks": [
        {"id": "t-video", "name": "video", "segments": [
            {"id": "v1", "target_timerange": {"start": 0, "duration": int(2 * US)},
             "source_timerange": {"start": 0, "duration": int(2 * US)}}]},
        {"id": "t-text", "name": "existing caption", "segments": [
            {"id": "c1", "target_timerange": {"start": 0, "duration": int(2 * US)},
             "source_timerange": {"start": 0, "duration": int(2 * US)}}]},
    ]}
    stable_after = json.loads(json.dumps(stable_before))
    stable_after["tracks"].insert(1, {"id": "t-new", "name": "new lane", "segments": []})
    d = describe(stable_before, stable_after)
    assert d == ['added track "new lane" at layer 2'], d
    assert not any("from track" in line for line in d), d
    # sub-frame noise from CapCut re-saving must not become a "change"
    assert describe(draft(dur=2.0), draft(dur=2.02)) == [], \
        "rounding noise is not an edit — it would flood the log"
    print("sa_editwatch self-check: ok (move, hold, trim, retype, add/delete, track shifts, noise floor)")


if __name__ == "__main__":
    if "--test" in sys.argv:
        _test()
        sys.exit()
    ap = argparse.ArgumentParser()
    ap.add_argument("project", nargs="?", help="default: every CapCut project")
    ap.add_argument("--interval", type=float, default=4.0)
    ap.add_argument("--once", action="store_true", help="one pass, for cron or a quick check")
    ap.add_argument("--summary", action="store_true", help="what has been learned so far")
    ap.add_argument("--session-dir", help="write exact events/evidence into an eyes session")
    ap.add_argument("--owner-pid", type=int,
                    help="stop automatically if the visible control pad closes")
    a = ap.parse_args()
    if a.summary:
        summary()
    else:
        watch([a.project] if a.project else None, a.interval, a.once, a.session_dir,
              a.owner_pid)
