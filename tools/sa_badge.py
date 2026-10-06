#!/usr/bin/env python3
"""Pin a logo badge to the AI presenter's blazer and track it so it moves with her.

Requirement (14 Sep): the approved placement is tracked.
The badge was placed by hand on one video and the tracking never made it into a
tool, so it had to be redone from scratch on 15 Sep. This is that tool.

WHY IT CANNOT BE COPIED BETWEEN CLIPS
Each intro is a separate Seedance generation, so her chest drifts differently in
every one. The keyframes are fitted to ONE clip's motion; pasted onto another they
slide off the lapel. Re-track per clip. What IS shared is the anchor: every intro
starts from the same PRESENTER_START.png, so the badge begins in the same place.

THE CANVAS TRICK (why there is no scale maths here)
`3 ASSETS/BADGE_canvas.png` is a full-canvas 1920x1086 transparent PNG with the
50x15 mark already sitting at the centre. Dropping it in at scale 1.0 puts the mark
dead centre; the only thing to animate is position. Do not rescale it.

ANCHOR — from Saad's approved placement on one video (transform x 0.32591, y -0.14221),
converted back to pixels: (1273, 617). Same character, same framing, same side
(her hair falls on the other one). Keep it unless he moves it.

    sa_badge.py "<project>" --clip INTRO_x.mp4            # track + report, writes nothing
    sa_badge.py "<project>" --clip INTRO_x.mp4 --apply
    sa_badge.py "<project>" --timeline "<name>" --clip ... --apply
    sa_badge.py --demo

Refuses while CapCut is open. Backs up first. Skips if a badge is already there.
"""
import argparse
import copy
import json
import os
import pathlib
import shutil
import subprocess
import sys
import uuid

import cv2
import numpy as np

US = 1_000_000
DRAFTS = pathlib.Path.home() / "Movies/CapCut/User Data/Projects/com.lveditor.draft"
BADGE = pathlib.Path(os.environ.get("TRAINING_ROOT", "~/Downloads/training-series")).expanduser() / "3 ASSETS" / "BADGE_canvas.png"

# Saad's approved placement, kept in CANVAS pixels because that is what it was
# measured from (transform x 0.32591, y -0.14221 on a 1920x1086 canvas).
ANCHOR_CANVAS = (1272.9, 620.2)
# The intro clip is laid in at scale 1.06 (sa_introfull's INTRO_SCALE) to fill his canvas,
# so a pixel of movement in the CLIP is 1.06 canvas pixels. Getting this wrong makes the
# badge drift against her chest instead of with it. The real scale is read off the segment.
INTRO_SCALE = 1.06
PATCH = 150              # template half-size: big enough to be unique, small enough to stay rigid
SEARCH = 60              # how far the chest can drift between a frame and frame 0
SMOOTH = 9               # frames; kills per-frame jitter that reads as the badge buzzing
FPS = 25
MAX_KF = 30              # keyframes per axis — more than this and CapCut's editor crawls
MIN_CONF = 0.80          # below this the match is not trustworthy; report and refuse


def capcut_open():
    return subprocess.run(["pgrep", "-x", "CapCut"], capture_output=True).returncode == 0


def video_anchor(scale=INTRO_SCALE):
    """Where the approved canvas point lands in the clip's own 1920x1080 pixels."""
    cx, cy = ANCHOR_CANVAS
    return (round(960 + (cx - 960) / scale), round(540 + (cy - 543) / scale))


def track(clip, anchor):
    """Follow the chest patch across the clip. Returns (times, dx, dy, confidence)."""
    cap = cv2.VideoCapture(str(clip))
    frames = []
    while True:
        ok, f = cap.read()
        if not ok:
            break
        frames.append(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY))
    cap.release()
    if len(frames) < 2:
        raise SystemExit(f"{clip}: could not read frames")
    ax, ay = anchor
    h, w = frames[0].shape
    tpl = frames[0][max(0, ay - PATCH):ay + PATCH, max(0, ax - PATCH):ax + PATCH]
    xs, ys, confs = [], [], []
    for f in frames:
        y0, y1 = max(0, ay - PATCH - SEARCH), min(h, ay + PATCH + SEARCH)
        x0, x1 = max(0, ax - PATCH - SEARCH), min(w, ax + PATCH + SEARCH)
        res = cv2.matchTemplate(f[y0:y1, x0:x1], tpl, cv2.TM_CCOEFF_NORMED)
        _, conf, _, loc = cv2.minMaxLoc(res)
        xs.append(x0 + loc[0] + PATCH - ax)
        ys.append(y0 + loc[1] + PATCH - ay)
        confs.append(conf)
    return smooth(xs), smooth(ys), confs, len(frames)


def smooth(v, n=SMOOTH):
    """Moving average with edge padding — a raw match jitters by a pixel or two."""
    a = np.asarray(v, dtype=float)
    pad = np.pad(a, (n // 2, n // 2), mode="edge")
    return np.convolve(pad, np.ones(n) / n, mode="valid")[:len(a)]


def norm(px, py, W=1920, H=1086):
    """CapCut canvas coordinates. y is inverted."""
    return (px - W / 2) / (W / 2), -(py - H / 2) / (H / 2)


def parse_args_anchor(text):
    return tuple(float(v) for v in text.split(",")) if text else None


def resolve(project, timeline):
    p = DRAFTS / project
    if timeline:
        cfg = json.loads((p / "Timelines/project.json").read_text())
        want = next((t["id"] for t in cfg["timelines"] if t["name"] == timeline), None)
        if not want:
            sys.exit(f"no timeline {timeline!r}; have: "
                     + ", ".join(repr(t["name"]) for t in cfg["timelines"]))
        return p / "Timelines" / want / "draft_info.json"
    tls = sorted(p.glob("Timelines/*/draft_info.json"))
    return tls[0] if tls else p / "draft_info.json"


def apply(project, timeline, clip, do_it, anchor_canvas=ANCHOR_CANVAS):
    if do_it and capcut_open():
        sys.exit("REFUSING: CapCut is open.")
    dp = resolve(project, timeline)
    d = json.loads(dp.read_text())
    vid = {m["id"]: m for m in d["materials"].get("videos", [])}

    if any("BADGE" in (vid.get(s.get("material_id"), {}).get("path", "")).upper()
           for t in d["tracks"] for s in t.get("segments", [])):
        return f"  {timeline or project}: badge already present, skipped"

    # sa_introfull lays the intro TWICE: the full clip on top (source 0, the one you see)
    # and a shorter cut underneath that skips the 1s head pad for the Slow Fade. Picking the
    # wrong one pins the badge to a segment that is a second out of step with the picture,
    # so take the longest, and carry its source offset into the frame maths.
    intro = [s for t in d["tracks"] for s in t.get("segments", [])
             if "INTRO_" in (vid.get(s.get("material_id"), {}).get("path", ""))]
    if not intro:
        return f"  {timeline or project}: NO INTRO CLIP in the timeline — run sa_introfull first"
    seg_intro = max(intro, key=lambda s: s["target_timerange"]["duration"])
    start = seg_intro["target_timerange"]["start"] / US
    dur = seg_intro["target_timerange"]["duration"] / US
    src0 = seg_intro["source_timerange"]["start"] / US

    scale = float((seg_intro.get("clip") or {}).get("scale", {}).get("x") or INTRO_SCALE)
    anc_v = video_anchor(scale)
    dx, dy, confs, nframes = track(clip, anc_v)
    lo = min(confs)
    lines = [f"  {timeline or project}",
             f"    clip {pathlib.Path(clip).name}  {nframes} frames, badge at {start:.2f}s for {dur:.2f}s"
             f"  (of {len(intro)} intro segments; source starts {src0:.2f}s)",
             f"    match confidence {lo:.3f} min / {sum(confs)/len(confs):.3f} mean",
             f"    intro scale {scale:.3f}   anchor canvas {anchor_canvas} -> clip px {anc_v}",
             f"    drift  x {dx.min():+.1f} to {dx.max():+.1f} px   y {dy.min():+.1f} to {dy.max():+.1f} px (in clip px)"]
    if lo < MIN_CONF:
        return "\n".join(lines) + f"\n    REFUSING: confidence below {MIN_CONF} — the patch was lost, check the anchor"
    if not do_it:
        return "\n".join(lines) + "\n    (plan only)"

    shutil.copy2(dp, str(dp) + ".pre_badge15")
    nid = lambda: str(uuid.uuid4()).upper()

    # step the keyframes so the editor stays responsive; always keep the last frame
    idx = sorted(set(list(range(0, nframes, max(1, nframes // MAX_KF))) + [nframes - 1]))
    kx, ky = [], []
    for i in idx:
        t = i / FPS - src0            # clip time -> time within the segment
        if t < 0 or t > dur:
            continue
        t = min(t, dur)
        nx, ny = norm(anchor_canvas[0] + dx[i] * scale, anchor_canvas[1] + dy[i] * scale)
        kx.append({"id": nid(), "time_offset": int(t * US), "values": [nx],
                   "curveType": "Line", "graphID": "", "left_control": {"x": 0.0, "y": 0.0},
                   "right_control": {"x": 0.0, "y": 0.0}})
        ky.append({"id": nid(), "time_offset": int(t * US), "values": [ny],
                   "curveType": "Line", "graphID": "", "left_control": {"x": 0.0, "y": 0.0},
                   "right_control": {"x": 0.0, "y": 0.0}})

    bm = copy.deepcopy(vid[seg_intro["material_id"]])
    bm.update(id=nid(), path=str(BADGE), name=BADGE.name, type="photo",
              material_name=BADGE.name, duration=int(dur * US), has_audio=False)
    d["materials"]["videos"].append(bm)

    s = copy.deepcopy(seg_intro)
    s.update(id=nid(), material_id=bm["id"], speed=1.0, volume=0.0, visible=True,
             extra_material_refs=[], group_id="", template_id="", render_index=20000,
             source_timerange={"start": 0, "duration": int(dur * US)},
             target_timerange={"start": int(start * US), "duration": int(dur * US)})
    s["clip"] = {"scale": {"x": 1.0, "y": 1.0}, "rotation": 0.0,
                 "transform": {"x": kx[0]["values"][0], "y": ky[0]["values"][0]},
                 "flip": {"vertical": False, "horizontal": False}, "alpha": 1.0}
    s["uniform_scale"] = {"on": True, "value": 1.0}
    s["keyframe_refs"] = []
    s["common_keyframes"] = [
        {"id": nid(), "property_type": "KFTypePositionX", "keyframe_list": kx},
        {"id": nid(), "property_type": "KFTypePositionY", "keyframe_list": ky},
    ]
    d["tracks"].append({"id": nid(), "type": "video", "name": "Logo badge",
                        "attribute": 0, "flag": 0, "segments": [s], "is_default_name": False})

    dp.write_text(json.dumps(d, ensure_ascii=False))
    lines.append(f"    written — {len(kx)} keyframes per axis on a new 'Logo badge' track")
    return "\n".join(lines)


def demo():
    """The canvas trick and the coordinate maths are the two things that can silently break."""
    from PIL import Image
    im = Image.open(BADGE)
    assert im.size == (1920, 1086), im.size
    bb = im.getchannel("A").getbbox()
    cx, cy = (bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2
    assert abs(cx - 960) < 2 and abs(cy - 543) < 2, f"mark not centred: {cx},{cy}"
    # Saad's approved transform must round-trip to the anchor
    nx, ny = norm(*ANCHOR_CANVAS)
    assert abs(nx - 0.32591) < 0.002, nx
    assert abs(ny - (-0.14221)) < 0.002, ny
    # and the canvas point must map back into the clip's own pixels through the 1.06 scale
    vx, vy = video_anchor()
    assert 1240 < vx < 1270 and 600 < vy < 625, (vx, vy)
    # smoothing must not shift the series or change its length
    v = [0, 10, 0, 10, 0, 10, 0, 10, 0, 10, 0]
    s = smooth(v)
    assert len(s) == len(v) and 3 < s.mean() < 7, (len(s), s.mean())
    print("demo ok")


if __name__ == "__main__":
    if "--demo" in sys.argv:
        demo(); sys.exit(0)
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--timeline")
    ap.add_argument("--clip", required=True)
    ap.add_argument("--anchor", help="x,y in CANVAS pixels; defaults to Saad's approved position")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    anc = parse_args_anchor(a.anchor) or ANCHOR_CANVAS
    print(apply(a.project, a.timeline, pathlib.Path(a.clip).expanduser(), a.apply, anc))
