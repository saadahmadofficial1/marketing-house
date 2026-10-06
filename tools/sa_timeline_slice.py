#!/usr/bin/env python3
"""Cut a role-sized timeline out of a finished CapCut timeline, in the same project.

Requirement (13 Sep): each role cut should be a new timeline inside the same CapCut
project, not a separate project, so every job gets its own timeline.

He proved the method by hand on one module — his role timeline there is two chunks lifted
out of the finished video with the original markings, captions and voice reused. This does
the same cut automatically, for a span he names.

Why slice the FINISHED timeline rather than rebuild from the recording: the markings in it are
already approved and the pacing already reads well. Rebuilding would re-open every problem the
12 Sep session spent the day fixing.

What it does, per span:
  - deep-copies the source timeline (all materials, all tracks)
  - keeps every segment overlapping [a, b), clipping the head/tail of ones that straddle
  - shifts everything back so the new timeline starts at 0
  - gives it a fresh UUID and registers it in timeline_layout.json so CapCut shows the tab

It NEVER touches the timelines already in the project. CapCut must be closed — a write into a
loaded draft can corrupt it.

    sa_timeline_slice.py "<project>" --from <timeline-id> --name "Reviewer" --span 230.0 294.7
    sa_timeline_slice.py "<project>" --list
"""
import copy
import json
import pathlib
import subprocess
import sys
import uuid

US = 1_000_000


def capcut_running():
    return subprocess.run(["pgrep", "-x", "CapCut"], capture_output=True).returncode == 0


def load(project, tid):
    p = pathlib.Path(project) / "Timelines" / tid / "draft_info.json"
    return json.loads(p.read_text()), p


def slice_timeline(d, a_s, b_s):
    """Keep [a_s, b_s) of timeline d, shifted to start at 0. Returns a new dict."""
    a, b = int(a_s * US), int(b_s * US)
    out = copy.deepcopy(d)
    new_id = str(uuid.uuid4()).upper()
    out["id"] = new_id
    out["duration"] = b - a
    kept_total = 0
    for tr in out.get("tracks", []):
        keep = []
        for s in tr.get("segments", []):
            t = s.get("target_timerange") or {}
            ts, td = t.get("start", 0), t.get("duration", 0)
            te = ts + td
            if te <= a or ts >= b:          # entirely outside the span
                continue
            head = max(0, a - ts)           # how much of the head to cut
            tail = max(0, te - b)           # how much of the tail to cut
            new_dur = td - head - tail
            if new_dur <= 0:
                continue
            # a clipped head must advance the SOURCE too, or the picture jumps
            src = s.get("source_timerange")
            if src and head:
                speed = (src.get("duration") or td) / td if td else 1.0
                src["start"] = int(src.get("start", 0) + head * speed)
                src["duration"] = int(new_dur * speed)
            elif src and tail:
                speed = (src.get("duration") or td) / td if td else 1.0
                src["duration"] = int(new_dur * speed)
            s["target_timerange"] = {"start": int(ts + head - a), "duration": int(new_dur)}
            keep.append(s)
        tr["segments"] = keep
        kept_total += len(keep)
    out["tracks"] = [tr for tr in out["tracks"] if tr.get("segments")]
    return out, new_id, kept_total


def scaffold(project, src_tid, new_tid, new_doc):
    """A timeline folder needs more than draft_info.json, and CapCut's real registry is
    Timelines/project.json — writing only timeline_layout.json leaves the tab invisible
    (found 13 Sep: the three slices existed on disk but CapCut showed nothing)."""
    import shutil, time
    base = pathlib.Path(project) / "Timelines"
    src, dst = base / src_tid, base / new_tid
    dst.mkdir(parents=True, exist_ok=True)
    (dst / "draft_info.json").write_text(json.dumps(new_doc, ensure_ascii=False))
    # template.json is CapCut's cached render copy of the same timeline
    (dst / "template.json").write_text(json.dumps(new_doc, ensure_ascii=False))
    for aux in ("attachment_editing.json", "attachment_pc_common.json", "draft.extra", "common_attachment"):
        f = src / aux
        if not f.exists():
            continue
        if f.is_dir():
            shutil.copytree(f, dst / aux, dirs_exist_ok=True)   # common_attachment is a folder
        else:
            shutil.copy2(f, dst / aux)
    # the registry CapCut actually reads
    pj = base / "project.json"
    reg = json.loads(pj.read_text())
    if not any(t["id"] == new_tid for t in reg["timelines"]):
        now = int(time.time() * 1_000_000)
        reg["timelines"].append({"create_time": now, "id": new_tid,
                                 "is_marked_delete": False, "name": NAME_HOLDER[0],
                                 "update_time": now})
        pj.write_text(json.dumps(reg, indent=1))


NAME_HOLDER = [""]


def register(project, tid, name):
    p = pathlib.Path(project) / "timeline_layout.json"
    lay = json.loads(p.read_text())
    for dock in lay.get("dockItems", []):
        if tid in dock.get("timelineIds", []):
            return  # already there
    dock = lay["dockItems"][0]
    dock["timelineIds"].append(tid)
    dock["timelineNames"].append(name)
    p.write_text(json.dumps(lay, indent=1))


def main():
    argv = sys.argv[1:]
    if not argv:
        sys.exit(__doc__)
    project = argv[0]
    if "--list" in argv:
        lay = json.loads((pathlib.Path(project) / "timeline_layout.json").read_text())
        for dock in lay["dockItems"]:
            for i, n in zip(dock["timelineIds"], dock["timelineNames"]):
                d, _ = load(project, i)
                print(f"  {i}  {d['duration']/US:7.1f}s  {n}")
        return 0
    src = argv[argv.index("--from") + 1]
    name = argv[argv.index("--name") + 1]
    i = argv.index("--span")
    a, b = float(argv[i + 1]), float(argv[i + 2])

    if capcut_running():
        print("REFUSING: CapCut is open. Close it first.")
        return 1

    d, _ = load(project, src)
    new, tid, n = slice_timeline(d, a, b)
    NAME_HOLDER[0] = name
    scaffold(project, src, tid, new)
    register(project, tid, name)
    print(f"  {name}: {a:.1f}-{b:.1f}s ({b-a:.1f}s), {n} segments, {len(new['tracks'])} tracks")
    print(f"  -> {tid}")
    return 0


def demo():
    """Self-check: a segment straddling the start keeps picture and source in step."""
    d = {"id": "x", "duration": 100 * US, "tracks": [{"segments": [
        {"target_timerange": {"start": 0, "duration": 20 * US},
         "source_timerange": {"start": 5 * US, "duration": 20 * US}},
        {"target_timerange": {"start": 50 * US, "duration": 10 * US},
         "source_timerange": {"start": 0, "duration": 10 * US}},
    ]}]}
    out, _, n = slice_timeline(d, 10.0, 55.0)
    segs = out["tracks"][0]["segments"]
    assert n == 2, n
    # head-clipped by 10s: starts at 0 in the new timeline, source advanced 5 -> 15
    assert segs[0]["target_timerange"] == {"start": 0, "duration": 10 * US}, segs[0]
    assert segs[0]["source_timerange"]["start"] == 15 * US, segs[0]
    # tail-clipped: 50-55 becomes 40-45, source duration halved
    assert segs[1]["target_timerange"] == {"start": 40 * US, "duration": 5 * US}, segs[1]
    assert segs[1]["source_timerange"]["duration"] == 5 * US, segs[1]
    print("demo ok")


if __name__ == "__main__":
    if "--demo" in sys.argv:
        demo()
    else:
        sys.exit(main())
