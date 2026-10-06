#!/usr/bin/env python3
"""sa_assemble — CapCut draft writer: raw footage folder -> first-pass timeline.

Applies the pacing style Claude has learned from Saad's real finished projects
(Reference/STYLE_DNA.md, Reference/TUTORIAL_TEMPLATES.md) so the assembled draft
already looks roughly right before Saad's taste pass. No voiceover, no captions
are added unless explicitly requested — that's a standing rule (10 Jul 2026).

  python3 sa_assemble.py <footage_folder> --name "New Project" --style tribute
  python3 sa_assemble.py <footage_folder> --name "New Project" --style tutorial_a --donor "My Tutorial Project"

Styles: tutorial_a (4.0s median cut), tutorial_b (8.0s median cut), tribute (1.5s median cut).
Each style has a default donor project it copies the transition/music/outro schema from.

Safety: never touches the donor project (read-only source, whole folder copied to a
NEW project name). Still — CapCut must be closed before running, same as any draft edit.
"""
import os, sys, re, json, glob, uuid, shutil, argparse

CAPCUT_DIR = os.path.expanduser("~/Movies/CapCut/User Data/Projects/com.lveditor.draft")
FFMPEG = shutil.which("ffmpeg") or os.path.expanduser("~/.local/bin/ffmpeg")
VIDEO_EXT = (".mp4", ".mov", ".m4v", ".MP4", ".MOV")
US = 1_000_000  # microseconds per second, CapCut's time unit

STYLES = {
    "tutorial_a": {"cut": 4.0, "donor": "Tutorial Donor A", "transition": "Slow Fade"},
    "tutorial_b": {"cut": 8.0, "donor": "Tutorial Donor B", "transition": "Slow Fade"},
    # tribute cut length confirmed 10 Jul across 5 of his finished projects (Reference/EDIT_DNA.md
    # STYLE CENSUS), not just one sample — 1.8s is the median-of-medians, not a guess.
    # Keep a second tribute-style donor on file in case this one is unavailable (--donor).
    "tribute":    {"cut": 1.8, "donor": "Tribute Donor", "transition": "Slow Fade"},
}

DUR_RE = re.compile(r"Duration: (\d+):(\d+):(\d+\.?\d*)")
RES_RE = re.compile(r"Video:.*?(\d{2,5})x(\d{2,5})")


def probe(path):
    """(duration_seconds, width, height) via ffmpeg stderr — no ffprobe on this Mac."""
    r = __import__("subprocess").run([FFMPEG, "-hide_banner", "-i", path],
                                      capture_output=True, text=True)
    dur, w, h = 0.0, 1920, 1080
    m = DUR_RE.search(r.stderr)
    if m:
        hh, mm, ss = m.groups()
        dur = int(hh) * 3600 + int(mm) * 60 + float(ss)
    m = RES_RE.search(r.stderr)
    if m:
        w, h = int(m.group(1)), int(m.group(2))
    return dur, w, h


def new_id():
    return str(uuid.uuid4()).upper()


def find_main_video_track(tracks):
    """The track with the most video segments = the main cut sequence."""
    best, best_n = None, -1
    for t in tracks:
        if t.get("type") == "video":
            n = len(t.get("segments", []))
            if n > best_n:
                best, best_n = t, n
    return best


def find_outro_track(tracks):
    """Track holding the compound bridge + brand-logo outro (path/name has outro/logo/endcard)."""
    for t in tracks:
        if t.get("type") != "video":
            continue
        for s in t.get("segments", []):
            pass  # matched via materials in caller — see assemble()
    return None


def plan_cuts(clip_paths, cut_len):
    """Pure planning: durations -> (start, used_duration) per clip. No file I/O.
    Each clip is used from its own beginning, trimmed to min(cut_len, its length)."""
    plan = []
    t = 0.0
    for path, src_dur in clip_paths:
        used = min(cut_len, src_dur) if src_dur > 0 else cut_len
        plan.append({"path": path, "start": t, "duration": used, "src_duration": src_dur})
        t += used
    return plan, t


def assemble(footage_dir, project_name, style_key, donor_name=None, order="name"):
    style = STYLES[style_key]
    donor_name = donor_name or style["donor"]
    donor_dir = os.path.join(CAPCUT_DIR, donor_name)
    if not os.path.isdir(donor_dir):
        raise SystemExit(f"donor project not found: {donor_dir}")

    new_dir = os.path.join(CAPCUT_DIR, project_name)
    if os.path.exists(new_dir):
        raise SystemExit(f"a project named '{project_name}' already exists — pick another name")

    files = sorted(f for f in os.listdir(footage_dir) if f.endswith(VIDEO_EXT))
    if not files:
        raise SystemExit(f"no video files found in {footage_dir}")
    if order == "mtime":
        files.sort(key=lambda f: os.path.getmtime(os.path.join(footage_dir, f)))

    print(f"probing {len(files)} clips...")
    clip_info = []
    for f in files:
        p = os.path.join(footage_dir, f)
        dur, w, h = probe(p)
        clip_info.append((p, dur, w, h))

    plan, total_new = plan_cuts([(p, d) for p, d, w, h in clip_info], style["cut"])
    print(f"planned {len(plan)} cuts, montage length {total_new:.1f}s (style={style_key}, cut={style['cut']}s)")

    print(f"copying donor '{donor_name}' -> '{project_name}' (donor untouched)...")
    shutil.copytree(donor_dir, new_dir)

    draft_path = os.path.join(new_dir, "draft_info.json")
    d = json.load(open(draft_path, encoding="utf-8"))
    mats = d["materials"]

    main_track = find_main_video_track(d["tracks"])
    if not main_track or not main_track["segments"]:
        raise SystemExit("donor has no usable main video track to template from")
    seg_template = json.loads(json.dumps(main_track["segments"][0]))   # deep copy
    vid_template_id = seg_template["material_id"]
    vid_template = next((m for m in mats["videos"] if m["id"] == vid_template_id), None)
    if not vid_template:
        raise SystemExit("could not find donor's video material template")
    vid_template = json.loads(json.dumps(vid_template))

    # one shared speed=1.0 material for every new clip (donor's per-clip effects/animations dropped —
    # ponytail: correctness over cosmetic parity; Saad's taste pass adds flourish if wanted)
    speed_id = new_id()
    mats.setdefault("speeds", []).append({"id": speed_id, "type": "speed", "mode": 0,
                                           "speed": 1.0, "curve_speed": None})

    new_segments, new_video_materials = [], []
    for i, item in enumerate(plan):
        p, start_s, dur_s = item["path"], item["start"], item["duration"]
        _, _, w, h = clip_info[i]
        mid = new_id()
        vm = json.loads(json.dumps(vid_template))
        vm.update(id=mid, path=p, material_name=os.path.basename(p), width=w, height=h,
                  duration=int(dur_s * US), material_id="")
        new_video_materials.append(vm)

        seg = json.loads(json.dumps(seg_template))
        seg.update(id=new_id(), material_id=mid, speed=1.0,
                    source_timerange={"start": 0, "duration": int(dur_s * US)},
                    target_timerange={"start": int(start_s * US), "duration": int(dur_s * US)},
                    render_timerange={"start": 0, "duration": 0},
                    extra_material_refs=[speed_id], render_index=i + 2,
                    caption_info=None, group_id="", template_id="")
        seg["clip"] = {"scale": {"x": 1.0, "y": 1.0}, "rotation": 0.0,
                       "transform": {"x": 0.0, "y": 0.0},
                       "flip": {"vertical": False, "horizontal": False}, "alpha": 1.0}
        new_segments.append(seg)

    mats["videos"].extend(new_video_materials)
    main_track["segments"] = new_segments

    # drop OTHER overlay video tracks for v1 (multi-layer collage assembly not yet built —
    # ponytail: ship the correct simple version now, add overlay logic when a real need proves it)
    outro_track = None
    for t in d["tracks"]:
        if t is main_track or t.get("type") != "video":
            continue
        keep = any(
            any(k in (m.get("path", "") + m.get("material_name", "")).lower()
                for k in ("outro", "endcard", "logo", "compound"))
            for s in t.get("segments", [])
            for m in mats["videos"] if m["id"] == s.get("material_id")
        )
        if keep:
            outro_track = t
        else:
            t["segments"] = []

    if outro_track and outro_track["segments"]:
        old_block_start = min(s["target_timerange"]["start"] for s in outro_track["segments"])
        shift = int(total_new * US) - old_block_start
        for s in outro_track["segments"]:
            s["target_timerange"]["start"] += shift
        block_end = max(s["target_timerange"]["start"] + s["target_timerange"]["duration"]
                         for s in outro_track["segments"])
    else:
        block_end = int(total_new * US)

    # continuous music: keep first music segment, extend/trim to the new montage length,
    # drop any secondary/overlapping music segment (v1 simplification, see docstring)
    music_tracks = [t for t in d["tracks"] if t.get("type") == "audio"]
    for t in music_tracks:
        segs = t.get("segments", [])
        if not segs:
            continue
        segs.sort(key=lambda s: s["target_timerange"]["start"])
        keep_seg = segs[0]
        keep_seg["target_timerange"]["duration"] = int(total_new * US)
        t["segments"] = [keep_seg] if keep_seg["target_timerange"]["start"] == 0 else []

    d["duration"] = block_end
    json.dump(d, open(draft_path, "w", encoding="utf-8"), ensure_ascii=False)

    # Newer CapCut keeps the live timeline in Timelines/<main_timeline_id>/draft_info.json
    # and treats the root file as legacy. Writing only the root looked like success but
    # the project opened showing the DONOR's timeline (found 17 Aug on a car reel —
    # a donor's old timeline appeared instead of the montage). Mirror it.
    mirrored = []
    tl_cfg = os.path.join(new_dir, "Timelines", "project.json")
    if os.path.exists(tl_cfg):
        main_id = json.load(open(tl_cfg, encoding="utf-8")).get("main_timeline_id")
        for tl in glob.glob(os.path.join(new_dir, "Timelines", "*", "draft_info.json")):
            if main_id and os.path.basename(os.path.dirname(tl)) != main_id:
                continue
            json.dump(d, open(tl, "w", encoding="utf-8"), ensure_ascii=False)
            mirrored.append(os.path.basename(os.path.dirname(tl)))

    print(f"\nwritten: {new_dir}")
    print(f"  {len(new_segments)} clips, {total_new:.1f}s montage + outro block -> {block_end/US:.1f}s total")
    if mirrored:
        print(f"  mirrored into Timelines/{mirrored[0]}/draft_info.json (the file CapCut reads)")
    elif os.path.exists(os.path.join(new_dir, "Timelines")):
        print("  WARNING: Timelines/ exists but no main timeline was written — check before opening")
    print("  CapCut must be CLOSED before this write and reopened after — standard rule.")
    print("  No VO/captions added (standing rule 10 Jul) — Saad's taste pass next.")
    return new_dir


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("footage_dir")
    ap.add_argument("--name", required=True, help="new CapCut project name")
    ap.add_argument("--style", required=True, choices=STYLES.keys())
    ap.add_argument("--donor", help="override the style's default donor project")
    ap.add_argument("--order", choices=["name", "mtime"], default="name")
    a = ap.parse_args()
    assemble(a.footage_dir, a.name, a.style, a.donor, a.order)


def _test_plan_cuts():
    """ponytail: one runnable check for the core timing-math logic (no file I/O needed)."""
    clips = [("a.mp4", 5.0), ("b.mp4", 1.0), ("c.mp4", 3.0)]
    plan, total = plan_cuts(clips, cut_len=2.0)
    assert [round(p["duration"], 2) for p in plan] == [2.0, 1.0, 2.0], plan
    assert [round(p["start"], 2) for p in plan] == [0.0, 2.0, 3.0], plan
    assert round(total, 2) == 5.0, total
    print("plan_cuts: ok")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        _test_plan_cuts()
    else:
        main()
