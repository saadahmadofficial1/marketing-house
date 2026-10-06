#!/usr/bin/env python3
"""Add the brand outro to a CapCut draft exactly the way Saad places it himself.

Requirement (13 Aug): learn how he places the outro against the music in his own edit,
and add it the same way to every video.

Every value below was MEASURED from his own edit — the series master, Timeline 02 — not
guessed. The donor is that timeline, so the outro this writes is indistinguishable
from the one he placed by hand:

  clip        the approved outro (OUTRO_NAME, in ~/Downloads), an 80.07s file
  source in   4.07s, for 9.10s   <- he does NOT start at the beginning of the file
  position    butted onto the END of the picture track, no gap
  volume      0.001 — the outro's own audio is muted
  scale       1.082 — he sizes it up 8.2%
  transition  "Slow Fade", 0.60s, is_overlap true, attached to the clip BEFORE the
              outro, never to the outro segment itself

The music in his edit runs at bed level (volume ~0.01-0.03) and STOPS DEAD on the
outro's last frame — no fade-out. This tool reports on music but does not touch it:
the bed differs per project and most of the T-series has none.

    sa_outro.py "Example Module"           # dry run, says what it would do
    sa_outro.py "Example Module" --apply

Refuses while CapCut is open — a write into a loaded draft can corrupt it.
"""
import copy
import json
import os
import pathlib
import shutil
import subprocess
import sys
import uuid

US = 1_000_000
DRAFTS = pathlib.Path.home() / "Movies/CapCut/User Data/Projects/com.lveditor.draft"
SERIES_PREFIX = os.environ.get("SERIES_PREFIX", "Training ")   # CapCut project names in the series
OUTRO_NAME = os.environ.get("OUTRO_NAME", "OUTRO")             # part of the approved outro's file name


def _donor():
    """The donor holding his outro segment. Resolved, never hardcoded — Saad renamed
    the master project once (found 19 Aug) and the literal path broke."""
    # the approved series uses one specific outro file; other outros in the drafts must
    # never be substituted (20 Aug), so set OUTRO_NAME to that file's name.
    for folder in sorted(DRAFTS.glob(SERIES_PREFIX + "*")):
        hits = sorted(folder.glob("Timelines/*/draft_info.json"))
        for h in hits:
            if OUTRO_NAME.upper() in h.read_text(errors="ignore").upper():
                return h
        if hits:
            return hits[0]
    return DRAFTS / (SERIES_PREFIX + "Master/Timelines/x/draft_info.json")   # reports missing


DONOR = _donor()

SOURCE_IN = int(4.07 * US)      # his in-point into the 80s outro file
OUTRO_LEN = int(9.10 * US)
OUTRO_VOL = 0.0010000000474974513
OUTRO_SCALE = 1.0820344112721776


def capcut_running():
    return bool(subprocess.run(["pgrep", "-x", "CapCut"], capture_output=True).stdout.strip())


def draft_path(project, timeline=None):
    """timeline: name of a SUB-timeline (e.g. a role slice inside a parent project). Without it this
    returns the project's MAIN timeline — which on a multi-timeline project is the finished
    parent video, not the slice you meant (14 Sep: nearly wrote an outro into the parent video itself)."""
    p = DRAFTS / project
    timelines = sorted(p.glob("Timelines/*/draft_info.json"))
    if timeline:
        cfg = json.loads((p / "Timelines/project.json").read_text())
        want = next((t["id"] for t in cfg["timelines"] if t["name"] == timeline), None)
        if not want:
            raise SystemExit(f"no timeline named {timeline!r} in {project}; have: "
                             + ", ".join(repr(t["name"]) for t in cfg["timelines"]))
        return p / "Timelines" / want / "draft_info.json"
    if timelines:
        # the main timeline, per Timelines/project.json
        cfg = p / "Timelines/project.json"
        if cfg.exists():
            main = json.loads(cfg.read_text()).get("main_timeline_id")
            for t in timelines:
                if t.parent.name == main:
                    return t
        return timelines[0]
    return p / "draft_info.json"


def donor_parts():
    d = json.loads(DONOR.read_text())
    vids = {m["id"]: m for m in d["materials"]["videos"]}
    outro_mat = next(m for m in vids.values()
                     if OUTRO_NAME.upper() in pathlib.Path(m.get("path", "")).name.upper())
    trans = next(t for t in d["materials"]["transitions"] if t.get("name") == "Slow Fade")
    seg = None
    for t in d["tracks"]:
        for s in t.get("segments") or []:
            if s.get("material_id") == outro_mat["id"]:
                seg = s
    return outro_mat, trans, seg


def picture_track(d, mats):
    """The track carrying the paced video — the one the outro goes after."""
    best, best_end = None, -1
    for t in d["tracks"]:
        if t.get("type") != "video":
            continue
        for s in t.get("segments") or []:
            path = (mats.get(s.get("material_id")) or {}).get("path") or ""
            if not path.lower().endswith((".mp4", ".mov")):
                continue
            tr = s.get("target_timerange") or {}
            end = tr.get("start", 0) + tr.get("duration", 0)
            if end > best_end:
                best, best_end = t, end
    if best is not None:   # 8 Sep: a Freeze still (photo) he lays at the end of the picture track counts as picture
        best_end = max(s["target_timerange"]["start"] + s["target_timerange"]["duration"]
                       for s in best["segments"] if s.get("target_timerange"))
    return best, best_end


def plan(project, timeline=None):
    dp = draft_path(project, timeline)
    if not dp.exists():
        sys.exit(f"no draft for {project!r}")
    d = json.loads(dp.read_text())
    mats = {m["id"]: m for m in (d.get("materials", {}).get("videos") or [])}
    track, end = picture_track(d, mats)
    if track is None:
        sys.exit("no picture track found")
    already = any(OUTRO_NAME.upper() in pathlib.Path((mats.get(s.get("material_id")) or {}).get("path", "")).name.upper()
                  for t in d["tracks"] for s in (t.get("segments") or []))
    music = []
    for t in d["tracks"]:
        if t.get("type") != "audio":
            continue
        for s in t.get("segments") or []:
            a = {m["id"]: m for m in (d["materials"].get("audios") or [])}.get(s.get("material_id"), {})
            vol = s.get("volume", 1.0)
            if vol < 0.15:                       # bed level, not voice-over
                tr = s["target_timerange"]
                music.append((pathlib.Path(a.get("path", "") or a.get("name", "")).name,
                              tr["start"] / US, (tr["start"] + tr["duration"]) / US, vol))
    return dp, d, track, end, already, music


def apply(dp, d, track, end):
    outro_mat, trans, donor_seg = donor_parts()
    mat = copy.deepcopy(outro_mat)
    mat["id"] = str(uuid.uuid4()).upper()
    d["materials"]["videos"].append(mat)

    tr_mat = copy.deepcopy(trans)
    tr_mat["id"] = str(uuid.uuid4()).upper()
    d["materials"].setdefault("transitions", []).append(tr_mat)

    seg = copy.deepcopy(donor_seg)
    seg["id"] = str(uuid.uuid4()).upper()
    seg["material_id"] = mat["id"]
    seg["target_timerange"] = {"start": int(end), "duration": OUTRO_LEN}
    seg["source_timerange"] = {"start": SOURCE_IN, "duration": OUTRO_LEN}
    seg["volume"] = OUTRO_VOL
    seg["extra_material_refs"] = [r for r in seg.get("extra_material_refs", [])
                                  if r != trans["id"]]
    seg.setdefault("clip", {})["scale"] = {"x": OUTRO_SCALE, "y": OUTRO_SCALE}

    # the Slow Fade belongs to the clip BEFORE the outro
    prev = max(track["segments"], key=lambda s: s["target_timerange"]["start"])
    prev.setdefault("extra_material_refs", []).append(tr_mat["id"])

    track["segments"].append(seg)
    d["duration"] = max(d.get("duration", 0), int(end) + OUTRO_LEN)
    return d


def main():
    argv = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not argv:
        sys.exit(__doc__)
    project = argv[0]
    do_it = "--apply" in sys.argv
    timeline = None
    if "--timeline" in sys.argv:
        timeline = sys.argv[sys.argv.index("--timeline") + 1]

    dp, d, track, end, already, music = plan(project, timeline)
    print(f"  {project}" + (f"  ->  timeline {timeline!r}" if timeline else ""))
    print(f"  picture ends at {end / US:.2f}s")
    if already:
        print("  ALREADY HAS AN OUTRO — nothing to do.")
        return 0
    print(f"  outro would run {end / US:.2f} -> {(end + OUTRO_LEN) / US:.2f}s "
          f"(source in 4.07s, muted, scale 1.082)")
    print(f"  Slow Fade 0.60s onto the clip before it")
    if music:
        print("  music beds present — his style is that they STOP with the outro:")
        for n, a, b, v in music:
            flag = "" if abs(b - (end + OUTRO_LEN) / US) < 0.5 else "   <-- ends early, extend to the outro"
            print(f"    {n[:38]:<38} {a:7.2f}-{b:7.2f}  vol {v:.3f}{flag}")
    else:
        print("  no music bed in this project (most of the T-series has none)")

    if not do_it:
        print("\n  dry run — nothing written. Add --apply to commit.")
        return 0
    if capcut_running():
        print("\n  REFUSING: CapCut is open. Close it first.")
        return 1
    shutil.copy2(dp, dp.with_suffix(".json.pre_outro"))
    dp.write_text(json.dumps(apply(dp, d, track, end), ensure_ascii=False))
    print(f"\n  written. backup: {dp.name}.pre_outro")
    return 0


def demo():
    """Self-check: the measured constants, and that the donor still parses."""
    assert abs(SOURCE_IN / US - 4.07) < 0.01
    assert abs(OUTRO_LEN / US - 9.10) < 0.01
    assert 0 < OUTRO_VOL < 0.01, "the outro is muted, not audible"
    assert 1.08 < OUTRO_SCALE < 1.09
    if DONOR.exists():
        mat, trans, seg = donor_parts()
        assert OUTRO_NAME.upper() in pathlib.Path(mat["path"]).name.upper()
        assert trans["name"] == "Slow Fade" and trans["duration"] == 600000
        assert trans["is_overlap"] is True
        assert abs(seg["volume"] - OUTRO_VOL) < 1e-9
        print("demo ok (donor matches the measured constants)")
    else:
        print("demo ok (constants only — donor timeline not on this machine)")


if __name__ == "__main__":
    sys.exit(demo() if "--demo" in sys.argv else main())
