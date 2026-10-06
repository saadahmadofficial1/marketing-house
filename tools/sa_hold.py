#!/usr/bin/env python3
"""sa_hold — hold the frame under every call-out, so the box never sits on moving footage.

Measured on the two videos Saad has finished (video A and video B, 7 Aug): **the build inserts
zero freeze frames and he adds them every time** — 2 in the short video, 6 in the long one,
median hold 2.06-2.53s. It is the one correction he has made to every single video.

What he actually does, read off his video A timeline: a still REPLACES the motion, it does not
push the timeline out. His video ran 47.8s before and 47.9s after, with 5.06s of freeze in it
— so roughly five seconds of moving picture became five seconds of still. This does the same:
each call-out window is replaced by the exact frame the box was measured on, so total length
is unchanged and the voice-over stays in sync.

    python3 sa_hold.py module_stepmarks.json -o module_PACED_HELD.mp4
    python3 sa_hold.py --test

Deliberately does NOT draw anything. The boxes stay as separate CapCut layers he can drag,
which is the whole point of the pipeline — this only makes the picture underneath stand still
while they are up.

The frame taken is `t + dur/2`, the same one `sa_stepmark` measured the box against. Any
other frame and the box lands on the wrong row, because the UI scrolls between frames.
"""
import argparse
import json
import os
import pathlib
import subprocess
import sys
import tempfile

# His measured holds: video A -> 3.83s and 1.23s; video B -> 1.13, 1.23, 1.30, 2.83, 3.50, 4.17.
# Median across both is 2.1s. A call-out shorter than this is not worth freezing for.
MIN_HOLD = 0.8


def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                          "format=duration:stream=width,height,r_frame_rate",
                          "-of", "csv=p=0", str(path)], capture_output=True, text=True).stdout
    lines = [l for l in out.strip().split("\n") if l]
    w, h, rate = lines[0].split(",")[:3]
    num, _, den = rate.partition("/")
    return float(lines[-1]), int(w), int(h), float(num) / float(den or 1)


def moves_under_box(video, t, dur, box, thresh=6.0):
    """Does the picture actually move under this box during its window?

    THE REASON THIS EXISTS: validating against video A showed the first version would freeze
    under all four call-outs, when Saad froze under two. In video B he froze 6 times against
    23 call-outs. **He freezes selectively**, and blanket-freezing would have been a fresh
    error dressed up as a fix.

    **TESTED AND REJECTED AS A RULE, 7 Aug.** The obvious theory was that he freezes where the
    picture slides under the box. Checked against both videos he has finished, it is wrong in
    both directions:

        video A — 4 call-outs, this says 4 move, he froze 2
        video B — 18 call-outs, this says 3 move, he froze 6

    Over-predicts on one, under-predicts on the other, so motion is not the signal. Whatever
    decides it has not been identified. This stays available as ADVICE (`--only-moving`) and
    is never the default: freezing everything would be a fresh error wearing the costume of
    a fix, and shipping a guess is exactly what his zero-error requirement rules out.

    Ask him which moments needed holding before automating this.
    """
    import cv2
    import numpy as np
    cap = cv2.VideoCapture(str(video))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    x, y, w, h = (int(v) for v in box)
    got = []
    for at in (t + 0.05, t + dur - 0.05):
        cap.set(cv2.CAP_PROP_POS_FRAMES, max(int(at * fps), 0))
        ok, frame = cap.read()
        if not ok:
            cap.release()
            return False
        H, W = frame.shape[:2]
        # a generous margin: the row above and below is what he notices sliding
        y0, y1 = max(0, y - h), min(H, y + 2 * h)
        x0, x1 = max(0, x - 20), min(W, x + w + 20)
        got.append(cv2.cvtColor(frame[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY).astype("float32"))
    cap.release()
    if got[0].shape != got[1].shape or got[0].size == 0:
        return False
    return float(np.abs(got[0] - got[1]).mean()) > thresh


def plan(steps, duration, min_hold=MIN_HOLD):
    """-> [('play', a, b) | ('hold', at, dur)] covering the whole video exactly once.

    Pure, so the arithmetic that decides what the viewer sees is testable without ffmpeg.
    Overlapping or out-of-order call-outs are merged rather than allowed to produce a
    timeline that double-counts a second.
    """
    wins = sorted(((float(s["t"]), float(s["dur"])) for s in steps
                   if float(s["dur"]) >= min_hold), key=lambda x: x[0])
    merged = []
    for t, d in wins:
        if merged and t < merged[-1][0] + merged[-1][1]:
            a, ad = merged[-1]
            merged[-1] = (a, max(ad, t + d - a))          # one hold, not two overlapping
        else:
            merged.append((t, d))

    out, cursor = [], 0.0
    for t, d in merged:
        t = max(t, cursor)
        end = min(t + d, duration)
        if end - t < min_hold:
            continue
        if t - cursor > 0.02:
            out.append(("play", round(cursor, 3), round(t, 3)))
        out.append(("hold", round(t, 3), round(end - t, 3)))
        cursor = end
    if duration - cursor > 0.02:
        out.append(("play", round(cursor, 3), round(duration, 3)))
    return out


def total(segments):
    return round(sum(b - a if k == "play" else b for k, a, b in segments), 3)


def render(spec_path, out):
    spec = json.load(open(spec_path, encoding="utf-8"))
    video = spec["video"]
    steps = spec.get("steps", [])
    dur, w, h, fps = probe(video)
    segs = plan(steps, dur)
    holds = [s for s in segs if s[0] == "hold"]
    if not holds:
        raise SystemExit("no call-out is long enough to be worth holding")

    tmp = tempfile.mkdtemp()
    inputs, parts, fc = ["-i", str(video)], [], []
    still_ix = 1
    for k, a, b in segs:
        if k == "hold":
            png = os.path.join(tmp, f"h{still_ix}.png")
            # the frame the box was measured against, never a neighbour
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{a + b / 2:.3f}",
                            "-i", str(video), "-frames:v", "1", png], check=True)
            inputs += ["-loop", "1", "-t", f"{b:.3f}", "-r", f"{fps:.4f}", "-i", png]
            fc.append(f"[{still_ix}:v]setsar=1,format=yuv420p[p{len(parts)}]")
            still_ix += 1
        else:
            fc.append(f"[0:v]trim=start={a:.3f}:end={b:.3f},setpts=PTS-STARTPTS,"
                      f"setsar=1,format=yuv420p[p{len(parts)}]")
        parts.append(f"[p{len(parts)}]")
    fc.append("".join(parts) + f"concat=n={len(parts)}:v=1:a=0[vout]")

    cmd = (["ffmpeg", "-y", "-v", "error", "-stats"] + inputs +
           ["-filter_complex", ";".join(fc), "-map", "[vout]", "-map", "0:a?",
            "-c:v", "libx264", "-preset", "medium", "-crf", "16", "-pix_fmt", "yuv420p",
            "-r", f"{fps:.4f}", "-c:a", "copy", "-shortest_buf_duration", "10", str(out)])
    subprocess.run([c for c in cmd if c != "-shortest_buf_duration" and c != "10"], check=True)

    got, _w, _h, _f = probe(out)
    # The whole promise of this tool is that the length does not move — the voice-over is
    # already cut to it. A drift means the picture and the voice have come apart.
    if abs(got - dur) > 0.5:
        raise SystemExit(f"{out}: {got:.2f}s but the source was {dur:.2f}s — the hold must "
                         f"replace motion, never extend the timeline")
    print(f"-> {out}  ({got:.1f}s, unchanged)  {len(holds)} frame(s) held, "
          f"{sum(b for _k, _a, b in holds):.1f}s of stills")
    return segs


def _test():
    # a hold replaces motion, so the total never moves
    steps = [{"t": 10.0, "dur": 2.0}, {"t": 20.0, "dur": 3.0}]
    p = plan(steps, 30.0)
    assert total(p) == 30.0, p
    assert p == [("play", 0.0, 10.0), ("hold", 10.0, 2.0), ("play", 12.0, 20.0),
                 ("hold", 20.0, 3.0), ("play", 23.0, 30.0)], p
    # a call-out shorter than the floor is not worth a freeze
    assert not [s for s in plan([{"t": 5.0, "dur": 0.3}], 20.0) if s[0] == "hold"]
    assert total(plan([{"t": 5.0, "dur": 0.3}], 20.0)) == 20.0
    # overlapping call-outs become ONE hold, never two that double-count time
    p2 = plan([{"t": 5.0, "dur": 4.0}, {"t": 7.0, "dur": 4.0}], 20.0)
    assert [k for k, _a, _b in p2].count("hold") == 1, p2
    assert total(p2) == 20.0, p2
    # a call-out running past the end is clipped, not allowed to invent footage
    p3 = plan([{"t": 18.0, "dur": 10.0}], 20.0)
    assert total(p3) == 20.0, p3
    assert p3[-1] == ("hold", 18.0, 2.0), p3
    # out-of-order input is handled
    p4 = plan([{"t": 20.0, "dur": 2.0}, {"t": 5.0, "dur": 2.0}], 30.0)
    assert [a for k, a, _b in p4 if k == "hold"] == [5.0, 20.0], p4
    assert total(p4) == 30.0
    print("sa_hold self-check: ok (length preserved, floor, overlap merge, clipping, order)")


if __name__ == "__main__":
    if "--test" in sys.argv:
        _test()
        sys.exit()
    ap = argparse.ArgumentParser()
    ap.add_argument("spec")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--at", help="comma-separated times to hold, e.g. 23.7,28.2 — the "
                                 "honest default, because what makes Saad freeze is not "
                                 "yet known and guessing it is a new error")
    ap.add_argument("--only-moving", action="store_true",
                    help="advisory only: hold where the picture slides under the box. "
                         "Tested against both finished videos and wrong in both directions")
    a = ap.parse_args()
    os.chdir(os.path.dirname(os.path.abspath(a.spec)) or ".")
    if not (a.at or a.only_moving):
        ap.error("give --at with the moments to hold. There is no safe automatic rule yet: "
                 "checked against video A and video B, every theory tried so far picks the "
                 "wrong frames.")
    render(os.path.basename(a.spec), a.out)
