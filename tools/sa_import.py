#!/usr/bin/env python3
"""Put media into a CapCut project's media pool WITHOUT touching the timeline.

Requirement (13 Aug): new intro media goes into the same CapCut project as the video it
belongs to. Every finished video starts its content at 0.00s, so inserting an
intro into the timeline would shift captions, call-outs and everything else on a
video he has already signed off. He builds his own head himself — one video already
has a 5.23s gap left at the start, and another has its presenter clip
at 3.77s, not 0.

So this only registers the file in `draft_meta_info.json` → `draft_materials`
(type 0). The clip appears in the project's media panel ready to drag; not one
segment moves.

    sa_import.py "Training 01 Sign In and Navigation" clip.mp4 line.mp3
    sa_import.py --plan            # show the whole intro mapping, write nothing

Refuses while CapCut is open.
"""
import json
import os
import pathlib
import shutil
import subprocess
import sys
import uuid

US = 1_000_000
DRAFTS = pathlib.Path.home() / "Movies/CapCut/User Data/Projects/com.lveditor.draft"
ASSETS = pathlib.Path(os.environ.get("TRAINING_ROOT", "~/Downloads/training-series")).expanduser() / "3 ASSETS" / "intro raw"

# intro tag -> CapCut project. Names must match the drafts folder exactly, and the keys
# must match the clip filenames (INTRO_<tag>_*.mp4). Example entries; one per video.
PROJECT = {
    "T01": "Training 01 Sign In and Navigation",
    "T02": "Training 02 Create a Record",
}


def capcut_running():
    return bool(subprocess.run(["pgrep", "-x", "CapCut"], capture_output=True).stdout.strip())


def probe(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height:format=duration",
         "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True).stdout.split()
    w = h = 0
    dur = 0.0
    nums = [float(x) for x in out if x.replace(".", "").isdigit()]
    if len(nums) == 3:
        w, h, dur = int(nums[0]), int(nums[1]), nums[2]
    elif nums:
        dur = nums[-1]
    return w, h, dur


def entry(path):
    path = pathlib.Path(path)
    w, h, dur = probe(path)
    kind = "video" if path.suffix.lower() in (".mp4", ".mov") else "music"
    return {
        "ai_group_type": "", "create_time": -1, "duration": int(dur * US),
        "enter_from": 0, "extra_info": path.name, "file_Path": str(path),
        "height": h, "id": str(uuid.uuid4()).upper(),
        "import_time": -1, "import_time_ms": -1, "item_source": 1,
        "material_color_tag": "", "md5": "", "metetype": kind,
        "roughcut_time_range": {"duration": int(dur * US), "start": 0},
        "sub_time_range": {"duration": -1, "start": -1},
        "type": 0, "width": w,
    }


def add(project, files):
    meta = DRAFTS / project / "draft_meta_info.json"
    if not meta.exists():
        return f"no draft_meta_info.json for {project!r}"
    d = json.loads(meta.read_text())
    group = next((g for g in d["draft_materials"] if g.get("type") == 0), None)
    if group is None:
        group = {"type": 0, "value": []}
        d["draft_materials"].append(group)
    have = {i.get("file_Path") for i in group["value"]}
    added = []
    for f in files:
        if str(f) in have:
            continue
        group["value"].append(entry(f))
        added.append(pathlib.Path(f).name)
    if added:
        shutil.copy2(meta, meta.with_suffix(".json.pre_import"))
        meta.write_text(json.dumps(d, ensure_ascii=False))
    return added


def pairs():
    """-> [(tag, project, [clip, line])] for every intro that exists on disk."""
    out = []
    for tag, project in PROJECT.items():
        clip = sorted(ASSETS.glob(f"INTRO_{tag}_*.mp4"))
        line = sorted(ASSETS.glob(f"LINE_{tag}_FINAL.mp3"))
        if clip:
            out.append((tag, project, [clip[0]] + ([line[0]] if line else [])))
    return out


def main():
    argv = [a for a in sys.argv[1:] if not a.startswith("--")]
    if "--plan" in sys.argv or not argv:
        for tag, project, files in pairs():
            exists = "   " if (DRAFTS / project).exists() else " ! "
            print(f"{exists}{tag:<7} -> {project[:44]:<44} {len(files)} file(s)")
            for f in files:
                print(f"          {f.name}")
        if not argv:
            print("\n  --plan only. Give a project name and files to write.")
        return 0
    if capcut_running():
        print("REFUSING: CapCut is open."); return 1
    print(add(argv[0], [pathlib.Path(a) for a in argv[1:]]))
    return 0


def demo():
    """Self-check: an entry has the fields CapCut's media pool needs."""
    e = entry(pathlib.Path("/nonexistent.mp4"))
    for k in ("file_Path", "extra_info", "duration", "metetype", "type",
              "roughcut_time_range", "id", "width", "height"):
        assert k in e, k
    assert e["type"] == 0 and e["metetype"] == "video"
    assert entry(pathlib.Path("/x.mp3"))["metetype"] == "music"
    # every mapped project name should be a real folder, or the mapping is stale
    missing = [p for p in PROJECT.values() if not (DRAFTS / p).exists()]
    if missing:
        print(f"note: mapping points at folders not on this machine: {missing}")
    print(f"demo ok ({len(PROJECT)} projects mapped)")


if __name__ == "__main__":
    sys.exit(demo() if "--demo" in sys.argv else main())
