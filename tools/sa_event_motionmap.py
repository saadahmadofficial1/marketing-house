#!/usr/bin/env python3
"""Frame-level motion map for every clip of an event shoot (Saad: analyse frame by frame BEFORE planning).

  CLIPS_DIR=/path/to/clips python3 sa_event_motionmap.py OUTDIR CLIP1 [CLIP2 ...]   -> OUTDIR/<clip>.json
  python3 sa_event_motionmap.py --relabel _ OUTDIR/*.json   # re-label stored scans
  python3 sa_event_motionmap.py --test
Clips are read from $CLIPS_DIR/<clip>.MP4 (camera file names, without the extension).
Samples 10 fps at 480x270 grey. Per step: similarity fit (scale, rotation, tx, ty) from tracked
corners, fit residual, sharpness (Laplacian var), mean luma. Labels per 0.5s bin:
  lens_zoom  scale changing AND the similarity fit is clean (optical zoom: no parallax)  -> REJECT
  push       scale changing with parallax (walking in / out)                           -> usable move
  whip       fast pan (>~45% frame width per second)                                   -> cut point only
  shake      jerky high-frequency motion                                               -> REJECT
  focus_hunt sharpness dips >45% under its local median while the camera is near-still  -> REJECT
  exposure   mean luma jumps >18 levels in 0.5s while near-still (iris/AE)              -> REJECT
  stable     none of the above
ponytail: thresholds are calibrated by eye on this shoot, not universal; retune per camera.
"""
import json, os, subprocess, sys
import numpy as np

FPS, W, H = 10, 480, 270
ZOOM_RATE = 0.035      # |d ln(scale)/dt| per second that counts as zooming
CLEAN_FIT = 0.9        # median residual px: below = rigid zoom (lens), above = parallax (moving camera)


def frames(path):
    cmd = ["ffmpeg", "-v", "error", "-hwaccel", "videotoolbox", "-skip_frame", os.environ.get("MOTIONMAP_SKIP", "default"), "-i", path, "-vf",
           "fps=%d,scale=%d:%d,format=gray" % (FPS, W, H), "-f", "rawvideo", "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    n = W * H
    while True:
        b = p.stdout.read(n)
        if len(b) < n:
            break
        yield np.frombuffer(b, np.uint8).reshape(H, W)
    p.wait()


def step(prev, cur, cv2):
    pts = cv2.goodFeaturesToTrack(prev, 300, 0.01, 8)
    if pts is None or len(pts) < 12:
        return None
    nxt, st, _ = cv2.calcOpticalFlowPyrLK(prev, cur, pts, None, winSize=(21, 21), maxLevel=3)
    good = st.ravel() == 1
    a, b = pts[good].reshape(-1, 2), nxt[good].reshape(-1, 2)
    if len(a) < 12:
        return None
    M, inl = cv2.estimateAffinePartial2D(a, b, method=cv2.RANSAC, ransacReprojThreshold=2.0)
    if M is None:
        return None
    s = float(np.hypot(M[0, 0], M[1, 0])); rot = float(np.degrees(np.arctan2(M[1, 0], M[0, 0])))
    pred = a @ M[:, :2].T + M[:, 2]
    resid = float(np.median(np.linalg.norm(pred - b, axis=1)))
    return dict(scale=s, rot=rot, tx=float(M[0, 2]), ty=float(M[1, 2]), resid=resid)


def analyse(path):
    import cv2
    rows, prev = [], None
    for i, g in enumerate(frames(path)):
        sharp = float(cv2.Laplacian(g, cv2.CV_64F).var()); luma = float(g.mean())
        m = step(prev, g, cv2) if prev is not None else None
        rows.append(dict(t=round(i / FPS, 2), sharp=round(sharp, 1), luma=round(luma, 1), **({k: round(v, 5) for k, v in m.items()} if m else {})))
        prev = g
    return rows


def label_bins(rows):
    """0.5s bins -> labels. Pure function, tested in --test."""
    if not rows:
        return []
    sharp = np.array([r["sharp"] for r in rows]); luma = np.array([r["luma"] for r in rows])
    out = []
    per = FPS // 2
    for b0 in range(0, len(rows), per):
        seg = [r for r in rows[b0:b0 + per] if "scale" in r]
        t = rows[b0]["t"]
        if not seg:
            out.append(dict(t=t, label="unknown")); continue
        zr = float(np.mean([np.log(r["scale"]) for r in seg])) * FPS          # zoom rate per second
        pan = float(np.mean([abs(r["tx"]) for r in seg])) * FPS / W             # frame widths per second
        tx = np.array([r["tx"] for r in seg]); ty = np.array([r["ty"] for r in seg])
        jerk = float(np.mean(np.abs(np.diff(tx))) + np.mean(np.abs(np.diff(ty)))) if len(seg) > 2 else 0.0
        resid = float(np.median([r["resid"] for r in seg]))
        lo, hi = max(0, b0 - 3 * FPS), min(len(rows), b0 + 3 * FPS)
        local = float(np.median(sharp[lo:hi])); here = float(np.median(sharp[b0:b0 + per]))
        dl = float(abs(luma[min(b0 + per, len(luma) - 1)] - luma[b0]))
        still = pan < 0.08 and abs(zr) < ZOOM_RATE
        labels = []
        if abs(zr) >= ZOOM_RATE:
            labels.append("zoomish" if resid < CLEAN_FIT else "push")      # resolved to lens_zoom / blip below
        if pan >= 0.45:
            labels.append("whip")
        if jerk >= 8.0:
            labels.append("shake")                                         # calibrated: handheld sway is 1-6 here
        elif jerk >= 5.0:
            labels.append("handheld")
        if still and local > 0 and here < 0.55 * local:
            labels.append("focus_hunt")
        if still and dl > 18:
            labels.append("exposure")
        out.append(dict(t=t, label="+".join(labels) or "stable", zoom_rate=round(zr, 3), pan=round(pan, 3),
                        jerk=round(jerk, 2), resid=round(resid, 2), sharp=round(here, 1)))
    # optical zoom = sustained (>=2 consecutive 0.5s bins at >=0.045/s) or very fast (>=0.12/s);
    # a lone slower bin is people moving / sway in a static shot (seen on two locked-off shots) -> 'blip', usable.
    def zr(i):
        return abs(out[i].get("zoom_rate", 0)) if 0 <= i < len(out) and "zoomish" in out[i]["label"] else 0.0
    real = [zr(i) >= 0.12 or (zr(i) >= 0.045 and (zr(i - 1) >= 0.045 or zr(i + 1) >= 0.045)) for i in range(len(out))]
    for b, r in zip(out, real):                      # decide all first, then relabel (neighbours read old labels)
        b["label"] = b["label"].replace("zoomish", "lens_zoom" if r else "blip")
    return out


GOOD = ("stable", "push", "blip", "handheld", "blip+handheld", "push+handheld")


def windows(bins, good=GOOD):
    """Merge consecutive usable bins into clean windows (start, end)."""
    res, start = [], None
    for b in bins + [dict(t=None, label="END")]:
        ok = b["label"] in good
        if ok and start is None:
            start = b["t"]
        if not ok and start is not None:
            end = b["t"] if b["t"] is not None else bins[-1]["t"] + 0.5
            if end - start >= 0.8:
                res.append([start, round(end, 2)])
            start = None
    return res


def test():
    mk = lambda t, s=1.0, tx=0.0, r=0.3, sh=100.0, l=120.0: dict(t=t, scale=s, rot=0.0, tx=tx, ty=0.0, resid=r, sharp=sh, luma=l)
    rows = [mk(i / FPS) for i in range(10)] + [mk(1 + i / FPS, s=1.01) for i in range(10)] + \
           [mk(2 + i / FPS, s=1.01, r=2.5, tx=1.0) for i in range(10)] + [mk(3 + i / FPS, tx=30.0, r=2.0) for i in range(10)]
    labs = [b["label"] for b in label_bins(rows)]
    assert labs[:2] == ["stable", "stable"], labs
    assert labs[2] == "lens_zoom" and labs[4] == "push" and "whip" in labs[6], labs   # 1.01/step = 0.1/s sustained 1s
    assert windows(label_bins(rows)) == [[0.0, 1.0], [2.0, 3.0]], windows(label_bins(rows))
    print("ok")


if __name__ == "__main__":
    if sys.argv[1] == "--test":
        test(); sys.exit()
    if sys.argv[1] == "--relabel":                 # re-label stored scans after a threshold change
        for f in sys.argv[3:]:
            d = json.load(open(f)); d["bins"] = label_bins(d["raw"]); d["clean_windows"] = windows(d["bins"])
            json.dump(d, open(f, "w"))
        sys.exit()
    outdir = sys.argv[1]; os.makedirs(outdir, exist_ok=True)
    for clip in sys.argv[2:]:
        rows = analyse(os.path.join(os.path.expanduser(os.environ.get("CLIPS_DIR", "~/Movies/event-shoot")), clip + ".MP4"))
        bins = label_bins(rows)
        json.dump(dict(clip=clip, fps=FPS, bins=bins, clean_windows=windows(bins), raw=rows),
                  open(os.path.join(outdir, clip + ".json"), "w"))
        print(clip, len(rows), "frames,", sum(b["label"] != "stable" for b in bins), "flagged bins"); sys.stdout.flush()
