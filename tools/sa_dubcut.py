#!/usr/bin/env python3
"""sa_dubcut — pace a screen recording to a replacement voice-over, segment by segment.

The training-video problem: the trainer narrates the recording himself, then we
replace him with a studio TTS voice-over. The new voice says the same thing in fewer words, so the
picture always runs long and every call-out drifts off its click.

Fix: cut the picture to the voice, not the voice to the picture. Each script segment
owns a source window; that window is stretched or squeezed so it lasts exactly as long
as its VO clip (plus a breath). A UI screen recording takes a 1.3x nudge invisibly —
nothing moves on screen except the cursor.

  Tools/venv/bin/python3 Tools/sa_dubcut.py plan.json -o out.mp4
  Tools/venv/bin/python3 Tools/sa_dubcut.py --test

plan.json:
  {"source": "tight.mp4",
   "keeps": [[2.26,8.92], ...],        # optional: sa_tighten keeps, so "src" times
   "gap": 0.45,                        #   can be quoted in ORIGINAL source time
   "segments": [{"n":1, "src":[2.32,19.73], "vo":"vo/01.mp3"}, ...]}

Writes out.mp4 (picture + VO muxed) and out.timing.json — the segment start times in
FINAL time, which is what sa_stepmark call-outs must be authored against.

VOICE ANCHORS. Saad's own finished cut of one module: where a voice outlasts
its picture the old rule plays the window at the 0.70 floor and then HOLDS THE LAST FRAME,
so a tap or scroll lands before the voice has talked about it. He fixed it by hand with
freeze frames BEFORE the transitions. A segment may now carry
   "anchors": [{"at": 4.2, "src": 401.5}, ...]
= "4.2 s into this line's voice clip the picture must be showing ORIGINAL source second
401.5". The segment becomes pieces through (0, window start) -> anchors -> (end, window
end); each piece plays at its own speed inside [SPEED_MIN, SPEED_MAX], and spare time is a
freeze of the frame at the START of that piece (hold the screen, then play the motion so it
arrives on time). An anchor out of reach even at SPEED_MAX is met late; anchors out of
order are dropped. Plans with no anchors render exactly as before (byte-identical); a plan
with anchors is built frame-exact on the 30 fps grid, and its timing.json gains per-segment
"pieces": [[t0, s0, t1, s1, speed | "hold"], ...] (t in this cut, s in plan["source"]).
"""
import argparse
import json
import math
import os
import subprocess
import sys

# Saad re-cut one module by hand on 6 Aug because the pace felt too fast. Five of his six
# inserted freezes landed on segments running at the old 2.20x cap — he never let 2.20x
# stand. 1.60 is the ceiling he accepts.
SPEED_MIN, SPEED_MAX = 0.70, 1.60
# Breath between steps. His holds ran 0.84-4.67s (median ~1.7s); 0.9 is the floor that
# lets a screen settle before the next line starts.
DEFAULT_GAP = 0.9
TAIL_HOLD = 2.5                     # the closing screen needs to land, not snap away
FPS = 30                            # the cut is written at -r 30; anchored cuts are exact on it


def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", path], capture_output=True, text=True).stdout
    return float(out.strip())


def to_tight(t, keeps):
    """Map a time in the ORIGINAL source to its time in the tightened cut."""
    if not keeps:
        return t
    acc = 0.0
    for a, b in keeps:
        if t < a:
            return acc                      # t fell in a removed gap: snap to next keep
        if t <= b:
            return acc + (t - a)
        acc += b - a
    return acc


def from_tight(u, keeps):
    """Inverse of to_tight: a time in the tightened cut -> the ORIGINAL source time.
    A time exactly on a join belongs to the keep that ends there."""
    if not keeps:
        return u
    acc = 0.0
    for a, b in keeps:
        if u <= acc + (b - a) + 1e-9:
            return a + max(0.0, u - acc)
        acc += b - a
    return keeps[-1][1]


def _in_order(points):
    """Largest set of (at, src) anchors that moves forward in both voice and picture time:
    the picture can never run backwards, so an anchor that would need it is dropped."""
    n = len(points)
    best, prev = [1] * n, [-1] * n
    for j in range(n):
        for i in range(j):
            if (points[i][0] < points[j][0] - 1e-9 and points[i][1] <= points[j][1] + 1e-9
                    and best[i] + 1 > best[j]):
                best[j], prev[j] = best[i] + 1, i
    if not n:
        return [], []
    k = max(range(n), key=lambda j: (best[j], -j))
    keep = []
    while k >= 0:
        keep.append(k)
        k = prev[k]
    keep = set(keep)
    return ([p for i, p in enumerate(points) if i in keep],
            [p for i, p in enumerate(points) if i not in keep])


def plan_pieces(ta, span, target, anchors=None, keeps=None):
    """One segment's picture as pieces. Pure, so it can be tested.

    -> (pieces, picture_dur, used, dropped, late)
    pieces: [(t0, s0, t1, s1, speed)] with t from the segment start and s in the RENDERED
    source (tight when keeps are used); speed None = a freeze of frame s0.
    used / dropped: [(at, tight src, index into anchors)]; late: [(index, seconds late)].
    picture_dur exceeds target only when an anchor was met late and the rest of the window
    cannot fit even at SPEED_MAX — the picture is never cut to make it fit.
    With no anchors this is today's map: play at the clamped speed, hold the last frame.
    With anchors, spare time in a piece is a freeze at the piece's START — the screen the
    voice is talking about stays up and the tap that leaves it comes after (Saad's hand fix).
    """
    end = ta + span
    if not anchors:
        speed = min(max(span / target, SPEED_MIN), SPEED_MAX)
        d = span / speed
        pieces = [(0.0, ta, d, end, speed)]
        if target - d > 0.02:
            pieces.append((d, end, target, end, None))
        return pieces, target, [], [], []
    pts = []
    for k, an in enumerate(anchors):
        at = min(max(float(an["at"]), 0.0), target)
        src = min(max(to_tight(float(an["src"]), keeps), ta), end)
        pts.append((at, src, k))
    pts.sort(key=lambda p: (p[0], p[2]))
    used, dropped = _in_order(pts)
    pieces, late = [], []
    tc, sc = 0.0, ta
    for ti, si, k in used + [(target, end, None)]:
        ds, dt = si - sc, ti - tc
        if ds <= 1e-6:                          # same frame: hold it for whatever time there is
            if dt > 1e-6:
                pieces.append((tc, sc, ti, sc, None))
                tc = ti
            continue
        if dt <= 1e-6 or ds / dt > SPEED_MAX:   # out of reach: full speed, arrive late
            d = ds / SPEED_MAX
            pieces.append((tc, sc, tc + d, si, SPEED_MAX))
            if k is not None:
                late.append((k, round(tc + d - ti, 3)))
            tc, sc = tc + d, si
            continue
        sp = ds / dt
        if sp < SPEED_MIN:                      # spare time: freeze FIRST, then play the motion
            play = ds / SPEED_MIN
            pieces.append((tc, sc, ti - play, sc, None))
            pieces.append((ti - play, sc, ti, si, SPEED_MIN))
        else:
            pieces.append((tc, sc, ti, si, sp))
        tc, sc = ti, si
    return pieces, max(target, tc), used, dropped, late


def src_at(seg, t):
    """Rendered-source time on screen at cut time t, for a timing segment with pieces."""
    ps = seg["pieces"]
    for t0, s0, t1, s1, sp in ps:
        if t <= t1 + 1e-9:
            return s0 if sp == "hold" else min(s1, s0 + max(0.0, t - t0) * sp)
    return ps[-1][3]


def _holds(seg):
    """Held frames of a timing segment as [(t0, t1, s)], back-to-back holds of one frame merged."""
    out = []
    for t0, s0, t1, s1, sp in seg["pieces"]:
        if sp == "hold" and t1 > t0:
            if out and abs(out[-1][2] - s0) <= 1e-6 and abs(out[-1][1] - t0) <= 1e-3:
                out[-1] = (out[-1][0], t1, s0)
            else:
                out.append((t0, t1, s0))
    return out


def hold_frac(seg, t):
    """How far through a held frame cut time t is (0..1), or None when the picture moves."""
    for t0, t1, _s in _holds(seg):
        if t0 - 1e-9 <= t <= t1 + 1e-9:
            return min(1.0, max(0.0, (t - t0) / (t1 - t0)))
    return None


def time_at(seg, s, frac=0.5):
    """Cut time at which rendered-source time s is on screen, for a timing segment with
    pieces. A held frame is on screen for a while: `frac` picks the point in that hold
    (default its middle), so a call-out inside one hold lands at the same point of the other."""
    for t0, t1, s0 in _holds(seg):
        if abs(s - s0) <= 1e-6:
            return t0 + (t1 - t0) * frac
    ps = seg["pieces"]
    for t0, s0, t1, s1, sp in ps:
        if sp != "hold" and s0 - 1e-6 <= s <= s1 + 1e-6:
            return t0 + max(0.0, s - s0) / sp
    return ps[-1][2] if s > ps[-1][3] else ps[0][0]


def _frame(x):
    return int(math.floor(x * FPS + 0.5))


def build(plan):
    """-> list of (src_start, src_dur, speed, vo_path, vo_dur, picture_dur).

    picture_dur is what the segment occupies on the timeline: the voice plus a breath,
    or longer when the screen needs more room. Pure, so it can be tested.
    """
    keeps = plan.get("keeps")
    gap = plan.get("gap", DEFAULT_GAP)
    rows = []
    for seg in plan["segments"]:
        a, b = seg["src"]
        ta, tb = to_tight(a, keeps), to_tight(b, keeps)
        vo_dur = probe(seg["vo"]) if os.path.exists(seg["vo"]) else seg["vo_dur"]
        span = max(tb - ta, 0.1)
        # A segment gets AT LEAST as long as its voice, and as much longer as it needs to
        # show everything at a comfortable speed. Trimming to fit the voice is what
        # silently dropped 3.7 min from one module and made another feel rushed — the
        # picture is allowed to outrun the narration and simply play on without it.
        target = max(vo_dur + gap, span / SPEED_MAX)
        speed = min(max(span / target, SPEED_MIN), SPEED_MAX)
        rows.append((ta, span, speed, seg["vo"], vo_dur, target))
    return rows


def _voice_mix(plan, rows, holds, speeds):
    """VO laid end to end with the same breath the picture was cut to.
    -> (ffmpeg inputs, audio filters, timing rows, total). Shared by both renderers, so an
    anchored cut can never mix the voice differently from a plain one."""
    gap = plan.get("gap", DEFAULT_GAP)
    inputs, aparts, timing, t = [], [], [], 0.0
    for i, (_a, d, _sp, vo, vd, target) in enumerate(rows):
        inputs += ["-i", vo]
        aparts.append(f"[{i+1}:a]adelay={int(t*1000)}|{int(t*1000)},apad=whole_dur={t+vd+gap:.3f}[a{i}]")
        hold = holds[i]
        timing.append({"n": plan["segments"][i]["n"], "start": round(t, 3),
                       "vo_dur": round(vd, 3), "picture_dur": round(hold, 3),
                       "speed": round(speeds[i], 3)})
        t += hold
    # Pad the mix to the full picture length. With segments now free to run longer than
    # their voice, the audio ends first — and "-shortest" then chopped the tail off all
    # videos in a batch. The video is the master; the audio pads to meet it.
    aparts.append("".join(f"[a{i}]" for i in range(len(rows))) +
                  f"amix=inputs={len(rows)}:normalize=0[amix]")
    aparts.append(f"[amix]apad=whole_dur={t:.3f}[aout]")
    return inputs, aparts, timing, t


def _encode(src, inputs, fc, out, t, meta, nseg):
    cmd = (["ffmpeg", "-y", "-v", "error", "-stats", "-i", src] + inputs +
           ["-filter_complex", ";".join(fc), "-map", "[vout]", "-map", "[aout]",
            "-c:v", "libx264", "-preset", "medium", "-crf", "16", "-pix_fmt", "yuv420p",
            "-r", "30", "-c:a", "aac", "-b:a", "192k", out])
    subprocess.run(cmd, check=True)

    # Asymmetric on purpose: a cut that ran SHORT lost content and must never ship.
    # Running a little long is just frame rounding accumulating across segments.
    actual = probe(out)
    if actual < t - 0.5:
        raise SystemExit(f"{out}: rendered {actual:.1f}s but planned {t:.1f}s — "
                         f"{t - actual:.1f}s of the cut is missing, refusing to report success")

    tpath = os.path.splitext(out)[0] + ".timing.json"
    json.dump(meta, open(tpath, "w"), indent=1)
    print(f"\n-> {out}  ({probe(out):.1f}s, {nseg} segments)")
    print(f"-> {tpath}  (author call-outs against these times)")


def render(plan, out):
    if any(seg.get("anchors") for seg in plan["segments"]):
        return render_anchored(plan, out)
    rows = build(plan)
    src = plan["source"]
    fc, vparts = [], []
    for i, (a, d, sp, _vo, vd, target) in enumerate(rows):
        chain = f"[0:v]trim=start={a:.3f}:duration={d:.3f},setpts=(PTS-STARTPTS)/{sp:.5f}"
        if i == len(rows) - 1:
            target += TAIL_HOLD          # closing screen lands instead of snapping away
        short = target - d / sp
        if short > 0.02:   # picture ran out before the voice: hold the last frame
            chain += f",tpad=stop_mode=clone:stop_duration={short:.3f}"
        fc.append(chain + f"[v{i}]")
        vparts.append(f"[v{i}]")
    fc.append("".join(vparts) + f"concat=n={len(rows)}:v=1:a=0[vout]")

    holds = [r[5] + (TAIL_HOLD if i == len(rows) - 1 else 0.0) for i, r in enumerate(rows)]
    inputs, aparts, timing, t = _voice_mix(plan, rows, holds, [r[2] for r in rows])
    fc += aparts
    _encode(src, inputs, fc, out, t,
            {"video": os.path.abspath(out), "total": round(t, 3), "segments": timing}, len(rows))


def anchored_layout(plan, rows=None):
    """Every segment of an anchored plan as pieces -> (per-segment dicts, holds, speeds).
    Segments without anchors keep today's map (play, then hold the last frame)."""
    rows = rows if rows is not None else build(plan)
    keeps = plan.get("keeps")
    out, holds, speeds = [], [], []
    for i, ((ta, span, sp, _vo, _vd, target), seg) in enumerate(zip(rows, plan["segments"])):
        anchors = seg.get("anchors") or []
        pieces, pdur, used, dropped, late = plan_pieces(ta, span, target, anchors, keeps)
        hold = pdur
        if i == len(rows) - 1:            # closing screen lands instead of snapping away
            pieces.append((pdur, ta + span, pdur + TAIL_HOLD, ta + span, None))
            hold = pdur + TAIL_HOLD
        holds.append(hold)
        # one number for tools that still read "speed" linearly: source per second of picture
        speeds.append(span / pdur if anchors else sp)
        out.append({"pieces": pieces, "picture_dur": pdur, "target": target,
                    "used": [(at, anchors[k]) for at, _s, k in used],
                    "dropped": [anchors[k] for _a, _s, k in dropped],
                    "late": [(anchors[k], secs) for k, secs in late]})
    return out, holds, speeds


def render_anchored(plan, out):
    """Voice-anchored cut. Every piece is cut to a whole number of frames on the absolute
    30 fps grid, so picture and voice cannot drift apart over a long module (the plain
    renderer runs ~0.5 s long by the end of a 5-minute module from frame rounding)."""
    rows = build(plan)
    src = plan["source"]
    lay, holds, speeds = anchored_layout(plan, rows)
    fc, vparts, S, k = [], [], 0.0, 0
    for i, L in enumerate(lay):
        for t0, s0, t1, s1, sp in L["pieces"]:
            n = _frame(S + t1) - _frame(S + t0)
            if n <= 0:
                continue
            if sp is None or s1 - s0 < 2.0 / FPS:
                # a held frame: the one ON SCREEN at s0 (last frame at or before it), so a
                # hold at the very end of the source still finds a frame
                fc.append(f"[0:v]trim=start={max(0.0, s0 - 0.25):.4f}:end={s0 + 0.0005:.4f},"
                          f"setpts=PTS-STARTPTS,reverse,trim=end_frame=1,"
                          f"tpad=stop_mode=clone:stop={n - 1},setpts=N/({FPS}*TB)[p{k}]")
            else:
                fc.append(f"[0:v]trim=start={s0:.4f}:end={s1:.4f},setpts=(PTS-STARTPTS)/{sp:.5f},"
                          f"fps={FPS},tpad=stop_mode=clone:stop={n},trim=end_frame={n}[p{k}]")
            vparts.append(f"[p{k}]")
            k += 1
        S += holds[i]
    fc.append("".join(vparts) + f"concat=n={len(vparts)}:v=1:a=0[vout]")
    inputs, aparts, timing, t = _voice_mix(plan, rows, holds, speeds)
    fc += aparts
    for row, L, seg in zip(timing, lay, plan["segments"]):
        S0 = row["start"]
        row["pieces"] = [[round(S0 + t0, 3), round(s0, 3), round(S0 + t1, 3), round(s1, 3),
                          "hold" if sp is None else round(sp, 4)] for t0, s0, t1, s1, sp in L["pieces"]]
        if seg.get("anchors"):
            row["anchors"] = [[round(a["at"], 3), a["src"]] for _at, a in L["used"]]
            if L["dropped"]:
                row["anchors_dropped"] = [[a["at"], a["src"]] for a in L["dropped"]]
            if L["late"]:
                row["anchors_late"] = [[a["at"], a["src"], s] for a, s in L["late"]]
            if L["picture_dur"] > L["target"] + 1e-6:
                row["extended"] = round(L["picture_dur"] - L["target"], 3)
                print(f"  segment {row['n']}: anchors met late - picture runs "
                      f"{row['extended']:.2f}s past voice+gap (nothing cut)")
    _encode(src, inputs, fc, out, t,
            {"video": os.path.abspath(out), "total": round(t, 3), "anchored": True,
             "pieces_note": "[t0, s0, t1, s1, speed|'hold']: t = seconds in this cut, "
                            "s = seconds in plan['source'] (the fault-cut source when keeps are used)",
             "segments": timing}, len(rows))


def retime(spec, old_timing, new_timing):
    """Move call-outs from one paced cut to another, keeping the same source frame.

    Re-pacing changes every segment's start and speed, so a call-out authored against
    the old cut points at the wrong moment in the new one. Each call-out is mapped
    through SOURCE time — the frame it was measured on — so the box stays correct.
    Mapping the window CENTRE matters: that is the frame sa_stepmark freezes on.
    A timing segment with "pieces" (an anchored cut) is mapped through its pieces, so
    holds and per-piece speeds are honoured in either direction.
    """
    old = {s["n"]: s for s in old_timing["segments"]}
    new = {s["n"]: s for s in new_timing["segments"]}
    order = sorted(old.values(), key=lambda s: s["start"])

    def to_source(t):
        seg = None
        for s in order:                       # last segment starting at or before t
            if s["start"] <= t + 1e-9:
                seg = s
            else:
                break
        if seg is None:
            seg = order[0]
        if seg.get("pieces"):
            return seg["n"], src_at(seg, t) - seg["pieces"][0][1], hold_frac(seg, t)
        return seg["n"], (t - seg["start"]) * seg["speed"], None

    moved = []
    for st in spec["steps"]:
        centre = st["t"] + st["dur"] / 2
        n, offset, frac = to_source(centre)
        if n not in new:
            moved.append(dict(st))
            continue
        ns = new[n]
        if ns.get("pieces"):
            new_centre = time_at(ns, ns["pieces"][0][1] + offset, 0.5 if frac is None else frac)
        else:
            new_centre = ns["start"] + offset / ns["speed"]
        # never let a call-out run past the segment it belongs to
        new_centre = min(new_centre, ns["start"] + ns["picture_dur"] - st["dur"] / 2)
        moved.append(dict(st, t=round(max(0.0, new_centre - st["dur"] / 2), 3)))
    moved.sort(key=lambda s: s["t"])
    return dict(spec, steps=moved)


def _test():
    keeps = [[0, 10], [20, 30]]
    assert to_tight(5, keeps) == 5
    assert to_tight(25, keeps) == 15, "time after a cut shifts back by the removed gap"
    assert to_tight(15, keeps) == 10, "time inside a cut snaps to the next keep"
    plan = {"source": "x.mp4", "keeps": keeps, "gap": 0.5,
            "segments": [{"n": 1, "src": [0, 10], "vo": "no.mp3", "vo_dur": 4.0}]}
    (a, d, sp, _, vd, target), = build(plan)
    assert a == 0 and abs(vd - 4.0) < 1e-9
    assert abs(d - 10.0) < 1e-9, "no source may be dropped to make the voice fit"
    assert sp <= SPEED_MAX + 1e-9, "speed never exceeds the comfortable ceiling"
    assert abs(target - 10.0 / SPEED_MAX) < 1e-6, \
        "a dense segment runs longer than its voice instead of being trimmed"
    slow = {"source": "x.mp4", "gap": 0.5,
            "segments": [{"n": 1, "src": [0, 2.0], "vo": "no.mp3", "vo_dur": 6.0}]}
    (_a, _d, sp2, _v, _vd, tgt2), = build(slow)
    assert abs(tgt2 - 6.5) < 1e-9, "a short segment still waits for its voice"
    assert sp2 >= SPEED_MIN
    # retiming: a call-out must land on the same SOURCE frame after re-pacing
    oldt = {"segments": [{"n": 1, "start": 0.0, "picture_dur": 10.0, "speed": 2.0},
                         {"n": 2, "start": 10.0, "picture_dur": 10.0, "speed": 2.0}]}
    newt = {"segments": [{"n": 1, "start": 0.0, "picture_dur": 20.0, "speed": 1.0},
                         {"n": 2, "start": 20.0, "picture_dur": 20.0, "speed": 1.0}]}
    spec = {"steps": [{"t": 4.0, "dur": 2.0, "box": [0, 0, 1, 1], "label": "a"},
                      {"t": 14.0, "dur": 2.0, "box": [0, 0, 1, 1], "label": "b"}]}
    out = retime(spec, oldt, newt)["steps"]
    # centre 5.0 is 10s into segment 1 at 2x -> 10s in at 1x = new centre 10.0
    assert abs(out[0]["t"] - 9.0) < 1e-6, out[0]
    # centre 15.0 is 10s into segment 2 -> new centre 20+10 = 30.0
    assert abs(out[1]["t"] - 29.0) < 1e-6, out[1]
    assert [s["label"] for s in out] == ["a", "b"], "order preserved"
    _test_anchors()
    print("sa_dubcut self-check: ok (keep mapping, speed fit, clamp, retime, "
          "default command unchanged, anchors: hold-before-transition, late, order, "
          "extension, retime through pieces, frame-exact render)")


def _test_anchors():
    import tempfile
    for u in (0.0, 3.0, 10.0, 12.5, 20.0):
        assert abs(to_tight(from_tight(u, [[0, 10], [20, 30]]), [[0, 10], [20, 30]]) - u) < 1e-9
    assert from_tight(12.5, [[0, 10], [20, 30]]) == 22.5

    # 1. no anchors = today's map exactly (play at the clamp, then hold the last frame)
    ps, pd, *_ = plan_pieces(0.0, 2.0, 6.5)
    assert pd == 6.5 and ps[0][4] == SPEED_MIN and ps[-1][4] is None and ps[-1][2] == 6.5
    assert abs(ps[0][2] - 2.0 / SPEED_MIN) < 1e-9, "the hold is at the END, as before"

    # 2. the hand-fixed fault: 4 s of source, the tap at 3.0, an 8 s voice line. The voice names
    # the button at 5.0 - the picture must still show it (src 2.5) then, so the spare time
    # becomes a freeze BEFORE the tap, not after it.
    ps, pd, used, dropped, late = plan_pieces(0.0, 4.0, 8.0, [{"at": 5.0, "src": 2.5}])
    seg = {"pieces": [[t0, s0, t1, s1, "hold" if sp is None else sp] for t0, s0, t1, s1, sp in ps]}
    assert abs(src_at(seg, 5.0) - 2.5) < 1e-9 and pd == 8.0 and not late and not dropped
    assert src_at(seg, 5.0 + 1.3) < 3.0, "the button is still up 1.3 s after it is named"
    assert ps[0][4] is None and ps[0][1] == 0.0, "spare time freezes the START of the piece"
    assert all(sp is None or SPEED_MIN - 1e-9 <= sp <= SPEED_MAX + 1e-9 for *_x, sp in ps)
    assert abs(ps[-1][2] - 8.0) < 1e-9 and ps[-1][3] == 4.0, "the window still ends on time"
    old_seg = {"pieces": [[t0, s0, t1, s1, "hold" if sp is None else sp]
                          for t0, s0, t1, s1, sp in plan_pieces(0.0, 4.0, 8.0)[0]]}
    assert src_at(old_seg, 5.0) > 3.0, "(the old map had already tapped past the button)"

    # 3. out of reach even at SPEED_MAX: arrive late and carry on, never jump
    ps, pd, used, dropped, late = plan_pieces(0.0, 10.0, 10.0, [{"at": 1.0, "src": 8.0}])
    assert late and abs(late[0][1] - (8.0 / SPEED_MAX - 1.0)) < 1e-6 and pd == 10.0
    assert ps[0] == (0.0, 0.0, 8.0 / SPEED_MAX, 8.0, SPEED_MAX)

    # 4. an anchor that would run the picture backwards is dropped
    ps, pd, used, dropped, late = plan_pieces(0.0, 10.0, 10.0, [{"at": 2, "src": 5}, {"at": 3, "src": 1},
                                                                 {"at": 4, "src": 6}])
    assert [u[2] for u in used] == [0, 2] and [d[2] for d in dropped] == [1]

    # 5. met so late the rest cannot fit: the segment runs longer, nothing is cut
    ps, pd, *_ = plan_pieces(0.0, 10.0, 10.0, [{"at": 9.5, "src": 1.0}])
    assert abs(pd - (9.5 + 9.0 / SPEED_MAX)) < 1e-9 and ps[-1][3] == 10.0

    # 6. anchors quote ORIGINAL source time; the render trims the fault-cut source
    ps, *_ = plan_pieces(to_tight(20, [[0, 10], [20, 30]]), 5.0, 8.0, [{"at": 4.0, "src": 22.0}],
                         [[0, 10], [20, 30]])
    seg = {"pieces": [[t0, s0, t1, s1, "hold" if sp is None else sp] for t0, s0, t1, s1, sp in ps]}
    assert abs(src_at(seg, 4.0) - 12.0) < 1e-9

    # 7. retime through pieces: same source frame, old cut -> anchored cut and back
    plain = {"segments": [{"n": 1, "start": 0.0, "picture_dur": 8.0, "speed": 0.7,
                           "pieces": old_seg["pieces"]}]}
    anch = {"segments": [{"n": 1, "start": 0.0, "picture_dur": 8.0, "speed": 0.5,
                          "pieces": [[t0, s0, t1, s1, "hold" if sp is None else sp] for t0, s0, t1, s1, sp in
                                     plan_pieces(0.0, 4.0, 8.0, [{"at": 5.0, "src": 2.5}])[0]]}]}
    step = {"steps": [{"t": 2.571 - 0.5, "dur": 1.0, "label": "x"}]}     # centre = src 1.8 (0.7x)
    there = retime(step, plain, anch)["steps"][0]
    back = retime({"steps": [there]}, anch, plain)["steps"][0]
    assert abs(src_at(anch["segments"][0], there["t"] + 0.5) - 1.8) < 1e-3, there
    assert abs(back["t"] - step["steps"][0]["t"]) < 1e-3, back
    inside = {"steps": [{"t": 0.3, "dur": 0.4, "label": "h"}]}           # centre in the first hold
    assert abs(retime(inside, anch, anch)["steps"][0]["t"] - 0.3) < 1e-9, "same cut -> same time"
    # a plain old timing (no pieces) still retimes exactly as before
    assert abs(retime({"steps": [{"t": 4.0, "dur": 2.0}]},
                      {"segments": [{"n": 1, "start": 0.0, "picture_dur": 10.0, "speed": 2.0}]},
                      {"segments": [{"n": 1, "start": 0.0, "picture_dur": 20.0, "speed": 1.0}]}
                      )["steps"][0]["t"] - 9.0) < 1e-9

    # 8. no anchors anywhere -> the ffmpeg command is byte-for-byte the pre-anchor one
    global probe
    real_run, real_probe, cap = subprocess.run, probe, []

    class _R:
        stdout = "1.0"
    try:
        subprocess.run = lambda cmd, **kw: cap.append(cmd) or _R()
        probe = lambda p: 99.0
        with tempfile.TemporaryDirectory() as d:
            import contextlib, io
            with contextlib.redirect_stdout(io.StringIO()):
                render({"source": "s.mp4", "keeps": [[0, 10], [20, 30]], "gap": 0.5,
                        "segments": [{"n": 1, "src": [0, 10], "vo": "a.mp3", "vo_dur": 4.0},
                                     {"n": 2, "src": [22, 24], "vo": "b.mp3", "vo_dur": 3.0}]},
                       os.path.join(d, "o.mp4"))
            tim = json.load(open(os.path.join(d, "o.timing.json")))
    finally:
        subprocess.run, probe = real_run, real_probe
    golden = ("[0:v]trim=start=0.000:duration=10.000,setpts=(PTS-STARTPTS)/1.60000[v0];"
              "[0:v]trim=start=12.000:duration=2.000,setpts=(PTS-STARTPTS)/0.70000,"
              "tpad=stop_mode=clone:stop_duration=3.143[v1];[v0][v1]concat=n=2:v=1:a=0[vout];"
              "[1:a]adelay=0|0,apad=whole_dur=4.500[a0];[2:a]adelay=6250|6250,apad=whole_dur=9.750[a1];"
              "[a0][a1]amix=inputs=2:normalize=0[amix];[amix]apad=whole_dur=12.250[aout]")
    fc = cap[0][cap[0].index("-filter_complex") + 1]
    assert fc == golden, "a plan with no anchors must build the pre-anchor command:\n" + fc
    assert tim["segments"] == [{"n": 1, "start": 0.0, "vo_dur": 4.0, "picture_dur": 6.25, "speed": 1.6},
                               {"n": 2, "start": 6.25, "vo_dur": 3.0, "picture_dur": 6.0, "speed": 0.7}]
    assert list(tim) == ["video", "total", "segments"]

    # 9. a real render: every output frame shows the source frame the pieces promise, the
    # cut is exact on the frame grid, and the voice mix is placed as before
    import shutil
    ff = shutil.which("ffmpeg")
    if not ff:
        print("  (ffmpeg not found - render check skipped)")
        return
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, "src.mp4")       # frame N is painted grey level 16 + 3N
        subprocess.run([ff, "-v", "error", "-y", "-f", "lavfi", "-i",
                        "color=c=black:s=64x64:r=30:d=2.4,format=gray,geq=lum='16+3*N'",
                        "-c:v", "libx264", "-crf", "0", "-pix_fmt", "yuv420p", "-r", "30", src], check=True)
        for name, dur in (("v1.mp3", 1.0), ("v2.mp3", 1.5)):
            subprocess.run([ff, "-v", "error", "-y", "-f", "lavfi", "-i", f"sine=f=440:d={dur}",
                            os.path.join(d, name)], check=True)
        plan = {"source": src, "gap": 0.5, "segments": [
            {"n": 1, "src": [0, 1.0], "vo": os.path.join(d, "v1.mp3"), "anchors": [{"at": 1.0, "src": 0.3}]},
            {"n": 2, "src": [1.0, 2.4], "vo": os.path.join(d, "v2.mp3")}]}
        out = os.path.join(d, "out.mp4")
        import contextlib, io
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            render(plan, out)
        tim = json.load(open(os.path.join(d, "out.timing.json")))
        raw = subprocess.run([ff, "-v", "error", "-i", out, "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                             capture_output=True).stdout
        frames = [(sum(raw[i * 4096:(i + 1) * 4096]) / 4096 - 16) / 3 for i in range(len(raw) // 4096)]
        assert len(frames) == _frame(tim["total"]) == 180, (len(frames), tim["total"])
        segs = tim["segments"]
        for j, got in enumerate(frames):
            t = j / FPS
            sg = [s for s in segs if s["start"] <= t + 1e-9][-1]
            want = src_at(sg, t) * FPS
            assert abs(got - want) <= 1.6, (j, got, want)
        assert abs(frames[30] - 9) <= 1, "at voice time 1.0 the picture shows source 0.3 s"
        assert all(abs(f) <= 0.6 for f in frames[:17]), "the spare time is a freeze of the first frame"
        assert [s["start"] for s in segs] == [0.0, 1.5] and segs[0]["anchors"] == [[1.0, 0.3]]


if __name__ == "__main__":
    if "--test" in sys.argv:
        _test()
        sys.exit()
    ap = argparse.ArgumentParser()
    ap.add_argument("plan")
    ap.add_argument("-o", "--out", required=True)
    a = ap.parse_args()
    render(json.load(open(a.plan)), a.out)
