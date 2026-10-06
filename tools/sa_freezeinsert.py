#!/usr/bin/env python3
"""sa_freezeinsert — create the stability a marking needs, the way Saad does.

His rule (10 Aug): a box needs 2-3 seconds of stable screen, which is why he adds small
freeze frames. When a marking must sit on a moment the recording rushes through, he
splits the video, holds a still for ~1s, and the timeline after it slides right. This
tool is that move, done programmatically:

  split the video segment at t · insert a still of frame t for D seconds ·
  shift every later segment on every track by +D · split anything straddling t.

Library use (the fix pass calls build() then writes with its own backups):
    from sa_freezeinsert import build, extract_still
    d2 = build(draft, t=12.4, dur=1.0, still_path="/abs/hold.png")

    Tools/venv/bin/python3 Tools/sa_freezeinsert.py --test

His freeze frames on one finished video measure 0.83-2.3s, median 0.93 — default DUR
follows that.
"""
import copy
import json
import os
import pathlib
import subprocess
import sys
import uuid

US = 1_000_000
DEFAULT_DUR = 1.0


def new_id():
    return str(uuid.uuid4()).upper()


def extract_still(video, t, out):
    subprocess.run(["ffmpeg", "-y", "-v", "quiet", "-ss", f"{t:.3f}", "-i", str(video),
                    "-frames:v", "1", "-update", "1", str(out)], check=True)
    return out


def _split_segment(seg, t):
    """Pure: segment straddling t -> (left, right) with source split to match.
    Assumes speed 1.0 (every training-build segment is)."""
    tr, sr = seg["target_timerange"], seg.get("source_timerange")
    off = int(t * US) - tr["start"]
    left = copy.deepcopy(seg)
    right = copy.deepcopy(seg)
    right["id"] = new_id()
    left["target_timerange"] = {"start": tr["start"], "duration": off}
    right["target_timerange"] = {"start": tr["start"] + off,
                                 "duration": tr["duration"] - off}
    if sr:
        left["source_timerange"] = {"start": sr["start"], "duration": off}
        right["source_timerange"] = {"start": sr["start"] + off,
                                     "duration": sr["duration"] - off}
    return left, right


def build(draft, t, dur, still_path, still_track="Freeze holds"):
    """Pure: draft -> draft with a dur-second freeze of frame t inserted at t.
    Everything at/after t slides right by dur; segments straddling t are split."""
    out = copy.deepcopy(draft)
    t_us, d_us = int(t * US), int(dur * US)
    for tr in out.get("tracks", []):
        segs = []
        for s in tr.get("segments", []):
            a = s["target_timerange"]["start"]
            b = a + s["target_timerange"]["duration"]
            if b <= t_us:                        # entirely before: untouched
                segs.append(s)
            elif a >= t_us:                      # entirely after: slide right
                s["target_timerange"]["start"] = a + d_us
                segs.append(s)
            elif s.get("source_timerange"):      # straddling video/audio: split at t,
                left, right = _split_segment(s, t)     # slide the right half
                right["target_timerange"]["start"] += d_us
                segs.extend([left, right])
            else:                                # straddling text/box: stretch over the
                s["target_timerange"]["duration"] += d_us    # freeze, never duplicate
                segs.append(s)
        tr["segments"] = segs
    # the still itself, top of the video stack (donor: any photo material, else video)
    vids = out["materials"].get("videos", [])
    donor = next((m for m in vids if (m.get("path") or "").endswith(".png")), vids[0])
    m = copy.deepcopy(donor)
    m.update({"id": new_id(), "path": str(still_path),
              "material_name": os.path.basename(str(still_path))})
    out["materials"]["videos"].append(m)
    donor_seg = next(s for trk in out["tracks"] if trk.get("type") == "video"
                     for s in trk["segments"])
    fs = copy.deepcopy(donor_seg)
    fs.update({"id": new_id(), "material_id": m["id"],
               "target_timerange": {"start": t_us, "duration": d_us},
               "source_timerange": {"start": 0, "duration": d_us},
               "extra_material_refs": [], "group_id": "", "template_id": ""})
    fs.setdefault("clip", {})
    if fs["clip"]:
        fs["clip"]["transform"] = {"x": 0.0, "y": 0.0}
        fs["clip"]["scale"] = {"x": 1.0, "y": 1.0}
    holds = next((trk for trk in out["tracks"] if trk.get("name") == still_track), None)
    if holds is None:
        holds = {"id": new_id(), "type": "video", "attribute": 0, "flag": 0,
                 "is_default_name": False, "name": still_track, "segments": []}
        out["tracks"].append(holds)
    holds["segments"].append(fs)
    holds["segments"].sort(key=lambda s: s["target_timerange"]["start"])
    return out


def _test():
    def seg(a, d, mid="v0", src=True):
        s = {"id": "s" + str(a), "material_id": mid,
             "target_timerange": {"start": int(a * US), "duration": int(d * US)},
             "clip": {"transform": {"x": 0, "y": 0}, "scale": {"x": 1, "y": 1}}}
        if src:
            s["source_timerange"] = {"start": int(a * US), "duration": int(d * US)}
        return s
    draft = {"materials": {"videos": [{"id": "v0", "path": "/x/PACED.mp4"},
                                      {"id": "p0", "path": "/x/01_box.png"}]},
             "tracks": [
                 {"type": "video", "name": "", "segments": [seg(0, 30)]},
                 {"type": "video", "name": "box", "segments": [seg(14, 2, "p0", src=False)]},
                 {"type": "text", "name": "Captions", "segments":
                     [seg(2, 2, "c1", src=False), seg(20, 2, "c2", src=False)]}]}
    out = build(draft, t=10.0, dur=1.0, still_path="/x/hold.png")
    main = out["tracks"][0]["segments"]
    assert len(main) == 2, "video must split into two"
    assert main[0]["target_timerange"] == {"start": 0, "duration": int(10 * US)}
    assert main[1]["target_timerange"]["start"] == int(11 * US)
    assert main[1]["source_timerange"]["start"] == int(10 * US), \
        "right half must resume the source where the left stopped"
    box = out["tracks"][1]["segments"][0]
    assert box["target_timerange"]["start"] == int(15 * US), "later box slides +1s"
    caps = out["tracks"][2]["segments"]
    assert caps[0]["target_timerange"]["start"] == int(2 * US), "earlier caption untouched"
    assert caps[1]["target_timerange"]["start"] == int(21 * US)
    holds = [t for t in out["tracks"] if t.get("name") == "Freeze holds"]
    assert len(holds) == 1 and holds[0]["segments"][0]["target_timerange"] == \
        {"start": int(10 * US), "duration": int(1 * US)}
    # two freezes stack correctly: the second (later t computed on NEW timeline) also lands
    out2 = build(out, t=21.5, dur=1.0, still_path="/x/hold2.png")
    caps2 = [s for t2 in out2["tracks"] if t2.get("name") == "Captions"
             for s in t2["segments"]]
    assert caps2[1]["target_timerange"] == {"start": int(21 * US),
                                            "duration": int(3 * US)}, \
        "a caption straddling a freeze stretches over it — never splits into duplicates"
    mains = [s for t2 in out2["tracks"] if t2.get("type") == "video"
             and not t2.get("name") for s in t2["segments"]]
    assert len(mains) == 3, "video splits again at the second freeze"
    print("sa_freezeinsert self-check: ok (split, slide, stretch-not-duplicate, stack)")


if __name__ == "__main__":
    if "--test" in sys.argv:
        _test()
        sys.exit()
    print(__doc__)
