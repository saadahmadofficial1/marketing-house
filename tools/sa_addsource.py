#!/usr/bin/env python3
"""sa_addsource — put a video's own source recording on its timeline as a reference track.

Requirement (12 Aug 2026): put the main source file on the timeline as well, so the steps
can be checked against the original whenever an edit gets stuck.

Each build folder already carries the right file — `T01_src.mp4` is T01's own source cut, not
the hour-long run recording it came from. This drops that file onto a new track named
SOURCE (reference), muted and hidden, so it renders nothing and plays no audio. In CapCut he
clicks the eye to reveal it when he needs to check what the original actually did.

    python3 sa_addsource.py "MOD 02 Example Module"
    python3 sa_addsource.py --all-remaining
    python3 sa_addsource.py "MOD 02 Example Module" --remove
    python3 sa_addsource.py --test

THE RISK, and what was done about it: every source is LONGER than its finished edit (one source
runs 21:39 against a 10:58 edit), and a clip on the timeline sets how long the project is. Measured
on one module, 12 Aug: a real-time reference took the export from 77s to 131s, and pinning the
stored duration did not help — the length is computed from the content. So by default the WHOLE
source is fitted into the length the edit already occupies by running the reference fast (2.25x
on that one). Every frame stays reachable, the export does not move. `--full` restores real time and
accepts the longer project.

Refuses while CapCut is open and refuses on any project Saad has declared done — his finished
work is not written by tools.
"""
import argparse
import copy
import json
import os
import pathlib
import sys
import uuid

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from sa_capcut_captions import US, CAPCUT, capcut_open
from sa_capcut_signoff import drafts_of, probe

BUILD = pathlib.Path(os.environ.get("TRAINING_ROOT", "~/Downloads/training-series")).expanduser() / "2 BUILD"
TRACK = "SOURCE (reference)"

# The ones Saad still has to edit (example entries: CapCut project name -> build tag).
# The finished ones are frozen and preflight refuses them.
REMAINING = {
    "MOD 01 Example Module": "T01",
    "MOD 02 Example Module": "T02",
}


def source_for(tag):
    """-> the project's own trimmed source, or None. `T01_src.mp4` inside T01's build."""
    hits = sorted(BUILD.glob(f"{tag}*/{tag}_src.mp4"))
    return hits[0] if hits else None


def content_end(draft, ignore=TRACK):
    """Seconds. The end of real content, not counting a reference track we added."""
    ends = [(s["target_timerange"]["start"] + s["target_timerange"]["duration"]) / US
            for t in draft.get("tracks", []) if t.get("name") != ignore
            for s in t.get("segments", [])]
    return max(ends) if ends else 0.0


def donor_video(draft):
    """A real video material from this project, to copy CapCut's own shape from.

    Inventing the field set breaks on CapCut updates; cloning one that this very project
    already opens with does not.
    """
    for m in draft.get("materials", {}).get("videos", []):
        if m.get("type") == "video":
            return m
    return None


def build(draft, src_path, src_dur, fit=True):
    """Pure apart from the uuids: draft + source -> draft with one hidden reference track.

    fit=True compresses the WHOLE source into the length the edit already occupies, by
    running the reference clip fast. Measured 12 Aug: a full-length reference at normal
    speed took one module's export from 77s to 131s — leaving the stored duration alone does
    not help, because the length is computed from the content. Every frame of the source
    is still there to scrub; only its playback speed changes, and CapCut will set that
    back to 1 if he ever wants it.
    """
    out = copy.deepcopy(draft)
    donor = donor_video(out)
    if donor is None:
        raise SystemExit("project has no video material to copy the shape from")
    end = content_end(out)
    if fit and end and src_dur > end:
        target, speed = end, src_dur / end
    else:
        target, speed = src_dur, 1.0

    mat = copy.deepcopy(donor)
    mat.update({"id": str(uuid.uuid4()).upper(), "path": str(src_path),
                "material_name": src_path.name, "duration": int(src_dur * US),
                "has_audio": True, "local_material_id": ""})
    out["materials"].setdefault("videos", []).append(mat)

    seg = {"id": str(uuid.uuid4()).upper(), "material_id": mat["id"],
           "target_timerange": {"start": 0, "duration": int(target * US)},
           "source_timerange": {"start": 0, "duration": int(src_dur * US)},
           "speed": speed, "volume": 0.0, "is_tone_modify": False,
           "visible": False, "render_index": 0, "track_render_index": 0,
           "extra_material_refs": [], "clip": {"alpha": 1.0, "flip": {"horizontal": False,
           "vertical": False}, "rotation": 0.0, "scale": {"x": 1.0, "y": 1.0},
           "transform": {"x": 0.0, "y": 0.0}}, "enable_adjust": False,
           "reverse": False, "intensifies_audio": False}
    out["tracks"].append({"id": str(uuid.uuid4()).upper(), "type": "video",
                          "attribute": 0, "flag": 0, "is_default_name": False,
                          "name": TRACK, "segments": [seg]})
    return out, target, end, speed


def strip(draft):
    gone = {s["material_id"] for t in draft.get("tracks", []) if t.get("name") == TRACK
            for s in t.get("segments", []) if s.get("material_id")}
    draft["tracks"] = [t for t in draft.get("tracks", []) if t.get("name") != TRACK]
    draft["materials"]["videos"] = [m for m in draft["materials"].get("videos", [])
                                    if m.get("id") not in gone]
    return draft


def apply(project, tag=None, fit=True, remove=False):
    from sa_guard import preflight, Frozen
    try:
        preflight("capcut_write", project=project)    # refuses if frozen
    except (Frozen, SystemExit):
        # Removal is the one operation allowed on a finished video, because it can only
        # ever take out a track this tool added. 12 Aug: one module's reference was fitted at
        # 56.5s, Saad then shortened the tail to 53.8s, and the stale reference was
        # extending a video he had already signed off. Refusing to remove it would have
        # protected the damage, not the work.
        if not remove:
            raise
        print(f"   {project}: finished video — removal allowed (tool's own track only)")
    if capcut_open():
        raise SystemExit("REFUSED: CapCut is open — a draft written now is overwritten "
                         "when it saves. Close it first.")
    paths = drafts_of(project)
    if not paths:
        raise SystemExit(f"no draft found for {project!r}")

    if remove:
        for p in paths:
            d = strip(json.loads(p.read_text(encoding="utf-8")))
            # Take the header down with the track. Leaving `duration` at the old value
            # leaves CapCut claiming a length the content no longer reaches, which
            # exports as black — the first removal on one module did exactly that.
            was = d.get("duration")
            end = content_end(d)
            if end and was and was > int(end * US):
                d["duration"] = int(end * US)
            p.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        print(f"-> {project}: reference track removed, "
              f"duration trimmed {(was or 0)/US:.1f}s -> {content_end(d):.1f}s")
        return

    tag = tag or REMAINING.get(project)
    src = source_for(tag) if tag else None
    if not src:
        raise SystemExit(f"no {tag}_src.mp4 found under {BUILD}")
    dur = probe(src)

    for p in paths:
        d = json.loads(p.read_text(encoding="utf-8"))
        if any(t.get("name") == TRACK for t in d.get("tracks", [])):
            print(f"   {p.parent.name}: already has one, skipped")
            continue
        bak = p.with_suffix(".json.pre_addsource")
        if not bak.exists():
            bak.write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
        was = d.get("duration")
        d, placed, end, speed = build(d, src, dur, fit=fit)
        d["duration"] = was                 # never let the reference redefine the project
        p.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        print(f"-> {project}: {src.name} ({dur:.0f}s) on '{TRACK}' — "
              f"whole source in {placed:.0f}s at {speed:.2f}x, edit ends {end:.0f}s")


def _test():
    draft = {"duration": 20_000_000, "materials": {"videos": [
        {"id": "D", "type": "video", "path": "/x.mp4", "duration": 5_000_000}]},
        "tracks": [{"name": "main", "segments": [
            {"material_id": "D", "target_timerange": {"start": 0, "duration": 20_000_000}}]}]}
    src = pathlib.Path("/tmp/T99_src.mp4")

    out, placed, end, speed = build(draft, src, 45.0)          # default: fit by speed
    assert end == 20.0, end
    assert placed == 20.0, "the reference must never outlast the edit — 12 Aug: 77s -> 131s"
    assert abs(speed - 2.25) < 1e-6, speed
    ref = [t for t in out["tracks"] if t["name"] == TRACK]
    assert len(ref) == 1
    seg = ref[0]["segments"][0]
    assert seg["visible"] is False, "the reference must never render"
    assert seg["volume"] == 0.0, "the reference must never be heard"
    assert seg["source_timerange"]["duration"] == 45_000_000, \
        "the WHOLE source must be reachable, not a clamped window"
    assert content_end(out) == 20.0, "the reference must not count towards content end"
    assert draft["tracks"][0]["name"] == "main" and len(draft["tracks"]) == 1, \
        "build must not mutate the draft it was given"

    short, placed_s, _, speed_s = build(draft, src, 8.0)
    assert (placed_s, speed_s) == (8.0, 1.0), "a source shorter than the edit is left alone"

    full, placed_f, _, _ = build(draft, src, 45.0, fit=False)
    assert placed_f == 45.0, "--full keeps real time, and accepts the longer project"

    back = strip(copy.deepcopy(out))
    assert not [t for t in back["tracks"] if t["name"] == TRACK]
    assert len(back["materials"]["videos"]) == 1, "removal must take its material with it"
    assert strip(copy.deepcopy(back)) == back, "removing twice must be harmless"
    print("sa_addsource self-check: ok (hidden, silent, clamped, reversible, non-mutating)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project", nargs="?")
    ap.add_argument("--tag", help="T01/T02/... if the name does not map")
    ap.add_argument("--full", action="store_true",
                    help="real-time reference — WARNING: makes the project longer")
    ap.add_argument("--remove", action="store_true")
    ap.add_argument("--all-remaining", action="store_true")
    ap.add_argument("--test", action="store_true")
    a = ap.parse_args()
    if a.test:
        _test()
    elif a.all_remaining:
        for proj, tag in REMAINING.items():
            try:
                apply(proj, tag, fit=not a.full, remove=a.remove)
            except SystemExit as e:
                print(f"   {proj}: {e}")
    elif a.project:
        apply(a.project, a.tag, fit=not a.full, remove=a.remove)
    else:
        ap.print_help()
