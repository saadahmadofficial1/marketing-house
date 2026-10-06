#!/usr/bin/env python3
"""sa_clickdetect — find the click moments in a software screen-recording, automatically.

The idea (Saad's, 4 Aug 2026): on a static software UI the ONLY thing that moves
is the mouse cursor, and a big screen change means something was triggered.
So: track the cursor by frame-differencing, watch for a screen change, and the
cursor's last position before that change IS the thing that was clicked.

  Tools/venv/bin/python3 Tools/sa_clickdetect.py video.mp4 -o steps.json
  Tools/venv/bin/python3 Tools/sa_clickdetect.py video.mp4 --debug   # annotated frames
  Tools/venv/bin/python3 Tools/sa_clickdetect.py --test

Output is an sa_stepmark spec, ready to render:
  {"video":..., "steps":[{"t","dur","box":[x,y,w,h],"label":"Step 1"}]}

Labels come out as placeholders — a human (or the transcript) names them.
"""
import argparse
import json
import os
import sys

import cv2
import numpy as np

SCALE = 0.5          # process at half res for speed
CURSOR_MAX_AREA = 4000   # px^2 at full res — bigger than this isn't a cursor
TRANSITION_PCT = 0.055   # fraction of pixels changed => screen changed
CURSOR_PCT_MAX = 0.02    # above this it's not just the cursor moving
MIN_GAP = 1.0            # seconds between accepted events
LOOKBACK = 0.10          # use where the cursor was just before the change
BOX_W, BOX_H = 150, 44   # default call-out box around the click point


def element_bounds(frame, x, y, W, H):
    """Bounds of the UI element under (x,y).

    Buttons here are solid blocks of colour, so flood-fill from just under the
    cursor tip and take the filled region. Falls back to a default box when the
    fill runs away (e.g. a white field on a white page).
    """
    for dy in (6, 12, 2, 18):          # cursor hotspot is the tip; look just below it
        sy = min(H - 2, y + dy)
        sx = min(W - 2, max(1, x + 4))
        mask = np.zeros((H + 2, W + 2), np.uint8)
        try:
            cv2.floodFill(frame.copy(), mask, (sx, sy), 255,
                          (12, 12, 12), (12, 12, 12),
                          4 | cv2.FLOODFILL_MASK_ONLY | (255 << 8))
        except Exception:
            continue
        ys, xs = np.where(mask[1:-1, 1:-1] > 0)
        if len(xs) < 60:
            continue
        bx, by = int(xs.min()), int(ys.min())
        bw, bh = int(xs.max() - bx), int(ys.max() - by)
        area = bw * bh
        if (18 <= bh <= 90 and 40 <= bw <= 700 and area < 0.10 * W * H):
            return [bx, by, bw, bh]
    return None


def detect(video, debug_dir=None):
    cap = cv2.VideoCapture(video)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    step = max(1, int(round(fps / 15.0)))   # sample ~15fps

    prev = None
    hist = []                   # (t, x, y) cursor track
    events = []                 # (t, x, y, frame_before)
    recent = None               # last frame before a change
    idx = 0
    while True:
        ok = cap.grab()
        if not ok:
            break
        if idx % step:
            idx += 1
            continue
        ok, frame = cap.retrieve()
        if not ok:
            break
        small = cv2.resize(frame, None, fx=SCALE, fy=SCALE)
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        t = idx / fps

        if prev is not None:
            d = cv2.absdiff(gray, prev)
            _, th = cv2.threshold(d, 25, 255, cv2.THRESH_BINARY)
            pct = float(th.mean()) / 255.0

            if pct >= TRANSITION_PCT:
                # screen changed -> something was triggered. Use where the cursor
                # was just BEFORE the change; by the time the screen repaints the
                # user has often already moved on.
                cand = [h for h in hist if h[0] <= t - LOOKBACK] or hist
                if cand and (not events or t - events[-1][0] >= MIN_GAP):
                    events.append((t, cand[-1][1], cand[-1][2], recent))
            elif 0 < pct <= CURSOR_PCT_MAX:
                # only small movement -> almost certainly the cursor
                n, _, stats, cents = cv2.connectedComponentsWithStats(th, 8)
                best, best_a = None, 0
                for i in range(1, n):
                    a = stats[i, cv2.CC_STAT_AREA] / (SCALE * SCALE)
                    if a <= CURSOR_MAX_AREA and a > best_a:
                        best_a, best = a, cents[i]
                if best is not None:
                    hist.append((t, int(best[0] / SCALE), int(best[1] / SCALE)))
                    hist[:] = hist[-400:]
        prev = gray
        recent = frame
        idx += 1
    cap.release()

    steps = []
    for i, (t, x, y, fr) in enumerate(events, 1):
        box = element_bounds(fr, x, y, W, H) if fr is not None else None
        if box is None:                      # couldn't read the element — sane default
            box = [max(0, min(W - BOX_W, x - BOX_W // 2)),
                   max(0, min(H - BOX_H, y - BOX_H // 2)), BOX_W, BOX_H]
        steps.append({"t": round(max(0.0, t - 1.6), 2), "dur": 2.6,
                      "box": box, "label": f"Step {i}"})
    return {"video": os.path.abspath(video), "canvas": [W, H], "steps": steps}


def _test():
    # synthetic: static grey screen, a small white "cursor" moves, then the
    # whole screen flips -> exactly one event, located at the last cursor spot.
    import tempfile
    p = os.path.join(tempfile.mkdtemp(), "t.mp4")
    fw = cv2.VideoWriter(p, cv2.VideoWriter_fourcc(*"mp4v"), 30, (640, 360))
    for i in range(60):                      # cursor walks right
        f = np.full((360, 640, 3), 200, np.uint8)
        cv2.rectangle(f, (100 + i * 4, 180), (112 + i * 4, 198), (255, 255, 255), -1)
        fw.write(f)
    for _ in range(30):                      # screen flips = trigger
        fw.write(np.full((360, 640, 3), 40, np.uint8))
    fw.release()
    out = detect(p)
    assert len(out["steps"]) == 1, f"expected 1 event, got {len(out['steps'])}"
    bx, by, _, _ = out["steps"][0]["box"]
    assert 200 < bx + BOX_W // 2 < 420, f"click x off: {bx}"
    print("sa_clickdetect self-check: ok (1 event, cursor located before the screen change)")


if __name__ == "__main__":
    if "--test" in sys.argv:
        _test()
        sys.exit()
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("-o", "--out")
    a = ap.parse_args()
    spec = detect(a.video)
    out = a.out or os.path.splitext(a.video)[0] + "_steps.json"
    json.dump(spec, open(out, "w"), indent=1)
    print(f"{len(spec['steps'])} click events -> {out}")
    for s in spec["steps"]:
        print(f"   {s['t']:7.2f}s  box {s['box']}")
