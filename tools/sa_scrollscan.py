#!/usr/bin/env python3
"""sa_scrollscan — flag FAST scrolling in a screen recording and propose Saad's stepped scroll.

Requirement (25 Sep 2026): recordings made by other people often scroll fast (his own scroll slowly).
At intake, raise every fast scroll with him before building, then pace it as a STEPPED
scroll the way he records: start at the top of the page and stop each time the NEXT section
(card / row / block) has become fully readable (section 1 readable, pause; scroll until
section 2 is fully visible, pause; then section 3), in order, every section seen whole once, never resting on
a half-visible section. Steps are built as HELD FRAMES (module spec "holds" /
"anchor_overrides"), never by slowing footage. Extends the 4 Sep pacing law (busy scrolling
~1.0-1.2x; freeze rather than speed up). Rule text: playbooks/training-video-production.md.

    Tools/venv/bin/python3 Tools/sa_scrollscan.py <video> [--from S] [--to S] [--fps 10]
                                                 [--hold 1.5] [--json out.json] [--ocr|--no-ocr]
    Tools/venv/bin/python3 Tools/sa_scrollscan.py --test [--mutate partial|nohold]

REPORT ONLY: reads the video, writes nothing but the optional --json (plus temporary OCR
crops, deleted). Pixels are measured numerically; text comes from Tools/bin/sa_ocr (Apple
Vision, on-device). This check runs locally and uploads nothing; no vision model ever
looks at a frame.
ffmpeg runs with -threads 2 and the process lowers its own priority (nice 10), because
Saad is usually editing in CapCut on the same laptop.

Output per scroll EPISODE (times = seconds in the given video; give it the ORIGINAL source
recording and "src" in the proposed holds is directly the module spec's source second):
  start, end, direction, distance_px, peak/mean speed in px/s AND viewport-heights/s
  (viewport = the measured scrolling band), fast, why, and for fast ones the proposed
  STEPS [{t, hold, section_index, sections, fully_visible}] plus a ready "spec_holds" list
  [{"line": null, "src": t, "secs": hold}] — fill in "line" from the module's script.

METHOD
 1 Every frame is decoded (ffmpeg, -threads 2, grey, long side 960 px) WITH its real time
   (showinfo), and samples are taken here at --fps: each reported step time is a real
   frame's own -ss second. (ffmpeg's fps filter was measured taking the frame AFTER the
   tick.) VFR (iPhone: no frames while the screen is still): a tick inside a gap is a HOLD
   sample of the frame still on screen, so rests exist, episodes start when motion starts,
   and two flings with a rest between stay two. Columns are averaged in blocks of 4.
   Consecutive samples differing in >0.3 % of cells open an activity window; 0.6 s of
   stillness (= the read time) closes it. Cursor, caret, clock, spinner stay below.
 2 Per sample pair the changed rows give a region; the FFT computes the overlap-normalised
   SSD for every vertical shift at once (overlap >= 35 %), its local minima (plus "no move")
   are re-scored by a TRIMMED per-row cost (best 85 % of rows, sub-pixel), so a clock ticking
   or a fixed bar at the region's edge cannot outvote the rows that moved. A pair whose best
   trimmed SSD > 0.15*var+6 is not a translation (page change, modal) and splits segments.
 3 SCROLLING BAND per segment, by translation evidence: a row counts as scrolling where the
   shift explains its change better than staying put, and as FIXED only where it did not
   change at all. Both directions (F vs shifted R, R vs shifted F) reach both band edges;
   columns are then judged inside those rows (a fixed sidebar is excluded). A header,
   status bar or tab bar can never be band.
 4 Offsets are DRIFT-FREE: each sample is registered against a reference frame (re-anchored
   below 60 % overlap), predicted by the consecutive-pair shift; near-tied minima (look-alike
   list rows) take the candidate nearest the current velocity. A window holding a fast or
   unsure episode, or a break right next to motion (a fling can outrun 10 fps sampling),
   is re-measured WHOLE at 30 fps; ffmpeg decodes every frame either way.
 5 SECTIONS: the band is stitched into one content strip — the MEDIAN over the distinct
   scroll positions, so what stays put on screen (a floating "+" button, the iOS scroll
   indicator, a scrollbar thumb) drops out instead of smearing over the gaps. The PAGE
   colour is the colour of the flat full-width rows with the most separate gaps (inside an
   inset card no row is flat), else the plain margins' commonest colour; rows that are all
   page colour (within 4 levels) separate content runs; hairlines (list dividers) are
   dividers; LINE-sized runs (<= 6 % of the viewport) merge across the smaller of two
   clearly different gap sizes (Otsu on log gaps) to rebuild text blocks, never beyond 0.8
   viewport and never card with card; anything taller is cut at its quietest rows (a list
   with no page between items must still be seen piece by piece). Pixel runs keep card
   borders, icons and charts that OCR misses, so "whole" means the whole card. OCR lines are
   mapped into the same coordinates to label sections, and replace them when pixels give
   nothing.

NOT A PAGE SCROLL (counted under "not_scrolls", never flagged). Calibrated on phone
source 1, where they were the only false flags:
  - scrolling area < 25 % of the screen height: toasts, alerts, pickers (source 1: 17-24 %)
  - move < 0.1 viewport (and < 40 px): an alert settling, a nudge
  - the whole frame, status bar included, sliding for <= 0.3 s: a system transition
  - OCR reads a phone keypad (ABC/DEF/GHI...) or a keyboard row: a keyboard sliding in
    (needs OCR, which runs on every fast episode unless --no-ocr)
  - the changed rows' top (or bottom) edge travels >= 15 % of the screen against the
    content: a full-screen cover / sheet presented or dismissed (skeptic test, 25 Sep)

THRESHOLDS (and why)
  FAST = a section is SKIPPED, or a FLYBY happens.
  SKIPPED: a section that was not yet scrolled past at the start is scrolled past (top cut
    or gone, for a down-scroll) by the end, and between the rest before and the rest after
    it was never whole while moving <= 0.2 VH/s for >= 0.6 s. That is Saad's rule stated
    directly: every section seen whole, at rest, once. 0.2 VH/s is slow enough to read
    moving text (a screen takes 5 s to pass). Rests shorter than 0.6 s do not separate
    episodes.
  FLYBY: > 0.6 VH/s sustained >= 0.5 s while >= 1 viewport passes — a whole screen gone at
    unreadable speed; the backstop when sections are unreliable.
  A stepped scroll like Saad's (short move, then a >= 0.6 s pause with the next section
  whole) is never fast, however quick each move is: speed alone never makes it fast.
  "Scrolled past" is judged per LEG (a reversal of >= 0.5 viewport starts one): a fling
  down and straight back judges what went by on the way; a small jiggle keeps its net.

CALIBRATION (25 Sep 2026). No recording made by Saad himself was found: the desktop sources
were captured by other people, and the phone sources are the ones he says scroll fast.
  Read time 0.6 s comes from Saad's own verdict of 4 Sep: another recorder's desktop
  scrolling was fine at 1.0-1.2x and too fast at 1.51x (his feedback log). The same measured
  scrolls (desktop source A 150-300 s, 17 scrolls >= 0.25 viewport) re-judged per read time:
      read time    0.4   0.5   0.6   0.7   0.8   1.0 s
      at 1.0x        2     4     5     5     7     9   flagged of 17
      at 1.2x        3     3     5     5     7    10
      at 1.5x        4     4     7     7     8     9
  0.6 s is the shortest read time at which the speed he rejected (1.5x) flags more than
  the speeds he accepted, and it keeps accepted footage mostly unflagged (1.0 s would flag
  9 of 17 scrolls he had passed). His own freeze holds (1.13-4.17 s, sa_hold.py) set the
  default --hold 1.5 s, not the read time.
  Full tool on everything (scrolls moving >= 0.25 viewport):
      phone, 8 mobile-app sources      35 fast scrolls + 1 instant jump of 136  (26 %)
        source 1 17/47 · 2 2/21 · 3 6+1/14 · 4 4/17 · 5 4/16 · 6 0/6 · 7 3/14 ·
        an aborted take of source 7 0/1
      desktop, 4 desktop-app sources   14 fast scrolls + 6 instant jumps of 79  (18 %)
        source A 8/47 · source B (0-7 min) 4+6/24 · source C (0-7 min) 2/8 · source D 0/0
  Flags read by their OCR text were real content (lists, record pages, forms); the only
  false flags found (source 1) were overlays, now filtered: see NOT A PAGE SCROLL.
  RE-RUN AFTER THE SKEPTIC FIXES (25 Sep: VFR holds, card-level sections, median strip,
  sheet filter, legs, 0.6 s window gap). The table and totals above are the builder's
  pre-fix numbers; only these were re-run:
      Source A 150-300 s re-encoded at 960 px, all episodes:  1.0x 3 · 1.2x 3 · 1.5x 5
      (pre-fix code on the same files: 5 · 7 · 10) — 0.6 s still separates the speed he
      rejected from the two he accepted, more cleanly than before.
      Source A full res 5 -> 4 of 29 · phone source 2: 2 -> 5 of 33 · phone source 1: 17 -> 15.
  Gained: fling down a long list and straight back up (net ~0 px; the old net-
  direction test passed nothing). Lost: 3 sheets/covers sliding (not scrolls) and 2
  scrolls whose earlier 1.3-3 s of readable stillness a 0.4 s window gap had cut off.
  INSTANT JUMPS (the whole move within 2 frames: scroll-into-view, anchors, a panel
  collapsing) are reported apart: nothing between was ever on screen, so the remedy is a
  hold before/after the jump, not steps.

STEPS for fast episodes (Saad's rule, 25 Sep): in content order, each section's step frame
is the first 30 fps sample OF THIS EPISODE (up to where the next one starts) where it is
fully inside the band with a 4 px margin; within the
next 0.1 s the sample with the most clearance is taken, so a hold one source frame early is
still whole. Sections taller than the band get a top-aligned step. A start step covers what
is already whole before the scroll. Steps < 0.3 s apart merge only if every merged section
is whole in the later frame. Each step holds --hold s; a step that already rests (start or
end of the scroll) is only topped up to --hold. Times are floored to the millisecond so
ffmpeg -ss lands on the same frame. On VFR the start step's time is the REAL frame being
held, which can be seconds before the episode's start (same picture; -ss needs a real frame).

LIMITS (do not read the output as gospel)
  - Vertical scrolling only; horizontal carousels, zoom and parallax are not measured.
  - Sticky elements that appear mid-scroll, collapsing headers and pull-to-refresh can
    split an episode or shave the band; a floating button over the list can shave the band
    above it (steps then wait a little longer: still whole, never early). A sheet whose
    backdrop scales or blurs (iOS page sheet) is a break, not a scroll; a plain cover or
    dimmed-backdrop sheet is filtered (NOT A PAGE SCROLL).
  - A page with NO fixed header or tab bar (content under the status bar) that is flicked
    and stops dead within 0.3 s reads as a system slide and is dropped. A normal iOS flick
    decelerates for ~1 s and is kept (skeptic test).
  - A full-bleed list whose rows are the page colour (white rows, white page) gives one
    section per ROW; one whose cards fill the whole width over a different page colour with
    blank rows inside can still give one section per text block.
  - Content that is one uniform texture (no background rows) gives no pixel sections; OCR
    is then the only section source, and a screen with neither gives flyby-only judgement.
  - Sections cut by the first/last frame of the stitched strip (their other edge never
    appeared) are not judged and never get a step.
  - OCR misreads small UI text; the section text is a label for a human, not a transcript.
  - A list with no plain page between its items is cut at its quietest rows into pieces
    <= 0.8 viewport; a cut can fall inside an item, and a step then shows it in two parts.
  - "Rest" is stillness of the whole picture: a click, hover highlight or menu opening just
    before a scroll shortens the rest that counts, so content that was on screen long before
    the click can still be judged unread (seen on desktop: rests of 0.1 s before a jump).
  - A panel collapsing or content inserted near the band top can pass as a scroll (the
    rows below move as one); those are usually single-frame and reported as instant jumps.
  - The read time is calibrated on Saad's verdict about other people's desktop recordings,
    not on a recording of his own (none found); revisit with one of his when available.
  - A fling that bounces (iOS rubber-band) is measured as it moved; the verdict follows
    what was on screen at rest, so a fast but "rest -> jump -> rest" fling whose both
    resting screens show everything is NOT fast (nothing was skipped).
"""
import argparse
import json
import math
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import threading
import queue
import warnings

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
OCR_BIN = HERE / "bin" / "sa_ocr"
FFMPEG = os.path.expanduser("~/.local/bin/ffmpeg")
if not os.path.exists(FFMPEG):
    FFMPEG = shutil.which("ffmpeg") or "ffmpeg"
FFPROBE = os.path.expanduser("~/.local/bin/ffprobe")
if not os.path.exists(FFPROBE):
    FFPROBE = shutil.which("ffprobe") or "ffprobe"
THREADS = "2"                 # Saad edits in CapCut on this laptop

# ---- measurement --------------------------------------------------------------------------
ANALYSIS_LONG = 960           # analysis frame long side, px
COL_BLOCK = 4                 # columns averaged per descriptor cell
CHANGE_LEVEL = 12             # grey levels: a descriptor cell changed
CHANGE_FRAC = 0.003           # >0.3 % of cells changed = activity (cursor/clock/caret stay below)
WINDOW_GAP = 0.6              # s of stillness that closes an activity window: = MIN_READ, so a
                              # rest too short to separate episodes never splits them (0.4 did:
                              # a nudge 0.5 s before a scroll cut off the 1.5 s the page had
                              # already been readable — skeptic re-run, phone source 2 at 269.8 s)
MAX_WINDOW = 30.0             # s: a window is force-closed after this (bounded memory)
ROW_CHANGE = 1.5              # mean |diff| for a row to count as changed in a pair
MIN_BAND = 0.10               # changed rows must span >= 10 % of the frame to be a scroll
MIN_OVERLAP = 0.35            # shift search keeps >= 35 % overlap
REF_OVERLAP = 0.60            # re-anchor the reference frame below 60 % overlap
FIT_REL, FIT_ABS = 0.15, 6.0  # a translation leaves SSD <= 0.15*var + 6
EVIDENCE = 2.0                # grey levels: row/column translation evidence
FINE_FPS = 30.0               # re-measure fast/ambiguous episodes at this rate
# ---- not a page scroll (calibrated on phone source 1, 25 Sep) ----------------
MIN_REGION = 0.25             # a scrolling area under 25 % of the screen height is a toast,
                              # alert or picker sliding (source 1: toasts 18 %, alerts 17-24 %)
MIN_MOVE_VH = 0.10            # a move under 0.1 viewport is a nudge / alert settling
MIN_MOVE_PX = 40.0
WHOLE_SCREEN_S = 0.3          # the whole frame (status bar too) sliding for <= 0.3 s is a
                              # system transition (source 1 at 248.9 s: 1362 px in 0.1 s)
KEY_TOKENS = {"ABC", "DEF", "GHI", "JKL", "MNO", "PQRS", "TUV", "WXYZ"}
SHEET_EDGE = 0.15             # a changed-row edge travelling >= 15 % of the screen against the
                              # content offset = a sheet / cover sliding, not a scroll

# ---- judgement (see THRESHOLDS in the docstring) ------------------------------------------
MOVE_VH = 0.03                # VH/s: a pair moving faster than this is motion
MIN_READ = 0.6                # s: whole at readable speed this long = read. Calibrated on
                              # Saad's 4 Sep verdict (another recorder's desktop scrolling fine at
                              # 1.0-1.2x, too fast at 1.51x) — see CALIBRATION
READ_VH = 0.2                 # VH/s: readable speed
FAST_VH = 0.6                 # VH/s sustained ...
FLYBY_S = 0.5                 # ... for at least this long ...
FLYBY_VH = 1.0                # ... while this many viewports pass = flyby
MARGIN_PX = 4                 # section must clear the band edges by this much (orig px)
BG_TOL = 4                    # grey levels from the page colour that still count as page
STEP_MERGE = 0.3              # s
LINE_VH = 0.06                # a content run this short (of the viewport) is a line of text
LEG_VH = 0.5                  # a direction reversal this big (of the viewport) starts a new leg
JUMP_S = 0.07                 # s: a move this short is an instant jump, not a scroll
STEP_SETTLE = 0.10            # s after first full visibility to look for the clearest frame
MAX_OCR_FRAMES = 40
_MUT = None                   # self-test only: "nohold" re-breaks the VFR fix (must FAIL)


# =========================================================================== video i/o
def probe(video):
    out = subprocess.run([FFPROBE, "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height,avg_frame_rate,r_frame_rate:"
                          "stream_side_data=rotation:format=duration", "-of", "json",
                          str(video)], capture_output=True, text=True)
    if out.returncode != 0:
        raise SystemExit(f"ffprobe could not read {video}: {out.stderr.strip()[:200]}")
    d = json.loads(out.stdout)
    st = d["streams"][0]
    w, h = int(st["width"]), int(st["height"])
    rot = 0
    for sd in st.get("side_data_list", []) or []:
        if "rotation" in sd:
            rot = int(sd["rotation"])
    if abs(rot) % 180 == 90:
        w, h = h, w

    def rate(s):
        a, _, b = (s or "0/1").partition("/")
        try:
            return float(a) / float(b or 1)
        except (ValueError, ZeroDivisionError):
            return 0.0
    fps = rate(st.get("avg_frame_rate")) or rate(st.get("r_frame_rate")) or 30.0
    dur = float(d.get("format", {}).get("duration") or 0)
    s = min(1.0, ANALYSIS_LONG / max(w, h))
    wa, ha = max(8, int(round(w * s))), max(8, int(round(h * s)))
    wa -= wa % COL_BLOCK
    return {"W": w, "H": h, "fps": fps, "dur": dur, "Wa": wa, "Ha": ha,
            "sy": ha / h, "sx": wa / w}


def frames(video, t0, dur, fps, size, src_fps, hold_gaps=True):
    """Yield (n, t, grey uint8 frame, rt) sampled at ~fps from t0 for dur seconds.

    Every frame is decoded with its real timestamp (showinfo) and the sampling is done here:
    for each tick t0 + k/fps the first frame at or after it is taken, and t is THAT FRAME'S
    OWN time in ffmpeg -ss seconds. (ffmpeg's fps filter was measured picking the frame one
    source frame after the tick — 3n+1 at 10-from-30 fps — which would put a held frame on
    the wrong picture during a fling.) Same inputs -> same frames, for any size.

    VFR (iPhone screen recordings: 60 fps grid, ~34 fps average, NO frames while the screen
    is still — gaps of 1.6 s measured): a tick that falls in such a gap is the PREVIOUS frame
    still on screen, so it is yielded as a HOLD sample (t = the tick, rt = the held frame's
    own time). Without this a rest had no samples at all: two flings 1.6 s apart merged into
    one episode starting 1.5 s before the first moved (skeptic test, 25 Sep). rt is always a
    real frame's own time — the one to hand to ffmpeg -ss; t is when the picture was on
    screen. For CFR sources (no gaps) t == rt."""
    ss = max(0.0, t0 - 0.25 / src_fps)                 # a quarter frame early: t0's frame is first
    vf = (f"scale={size[0]}:{size[1]}:flags=area," if size else "") + "format=gray,showinfo"
    cmd = [FFMPEG, "-hide_banner", "-nostats", "-loglevel", "info", "-nostdin",
           "-threads", THREADS, "-ss", f"{ss:.6f}", "-t", f"{dur + 0.5 / src_fps:.6f}",
           "-i", str(video), "-filter_threads", "1", "-vf", vf, "-fps_mode", "passthrough",
           "-threads", THREADS,
           "-f", "rawvideo", "-pix_fmt", "gray", "-"]
    w, h = size if size else (probe(video)["W"], probe(video)["H"])
    nbytes = w * h
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    q = queue.Queue()

    def pump():
        for line in iter(p.stderr.readline, b""):
            i = line.find(b"pts_time:")
            if i >= 0 and b"showinfo" in line:
                try:
                    q.put(float(line[i + 9:].split()[0]))
                except ValueError:
                    pass
        q.put(None)
    threading.Thread(target=pump, daemon=True).start()
    tol = 0.5 / src_fps
    n = k = 0
    end = t0 + dur + 1e-6
    last = None                                        # (rt, frame) last frame decoded
    try:
        while True:
            buf = p.stdout.read(nbytes)
            if len(buf) < nbytes:
                break
            pt = q.get(timeout=120)
            if pt is None:
                break
            t = ss + pt
            if t > end:
                break
            fr = np.frombuffer(buf, np.uint8).reshape(h, w)
            if hold_gaps and last is not None and _MUT != "nohold":
                while t0 + k / fps < t - tol:          # tick inside a VFR gap: last on screen
                    yield n, t0 + k / fps, last[1], last[0]
                    n += 1
                    k += 1
            if t + tol >= t0 + k / fps:
                yield n, t, fr, t
                n += 1
                while t0 + k / fps <= t + tol:
                    k += 1
            last = (t, fr)
    finally:
        p.stdout.close()
        p.kill()
        p.wait()


def snap(t, geom):
    """Put a time on the source frame grid, so every decode of it starts on a real frame
    and ffmpeg's fps filter never has to break a tie between two frames."""
    return round(t * geom["fps"]) / geom["fps"]


def describe(fr):
    h, w = fr.shape
    c = w // COL_BLOCK
    return np.round(fr[:, :c * COL_BLOCK].reshape(h, c, COL_BLOCK).mean(2)).astype(np.uint8)


def activity_windows(video, geom, t0, t1, fps):
    """Yield windows {ts, rt, D, pre_still, post_still}: consecutive samples around activity.
    ts = when each sample was on screen, rt = its real frame's -ss time (they differ only on
    VFR hold samples, see frames). pre_still = how long the first frame had already been on
    screen; post_still = how long the last frame stays on screen afterwards (until the next
    change / end of range)."""
    size = (geom["Wa"], geom["Ha"])
    cur, pending, closed = None, [], None
    prev = prev_t = prev_rt = None
    last_active = t0
    for k, t, fr, rt in frames(video, t0, t1 - t0, fps, size, geom["fps"]):
        d = describe(fr)
        if prev is None:
            prev, prev_t, prev_rt = d, t, rt
            continue
        active = (np.abs(d.astype(np.int16) - prev.astype(np.int16)) > CHANGE_LEVEL).mean() \
            > CHANGE_FRAC
        if active:
            if cur is None:
                if closed is not None:           # previous window now knows its tail
                    closed["post_still"] = t - closed["ts"][-1]
                    yield closed
                    closed = None
                cur = {"ts": [prev_t], "rt": [prev_rt], "D": [prev],
                       "pre_still": max(0.0, prev_t - last_active)}
            else:
                for pt, prt, pd in pending:
                    cur["ts"].append(pt)
                    cur["rt"].append(prt)
                    cur["D"].append(pd)
            pending = []
            cur["ts"].append(t)
            cur["rt"].append(rt)
            cur["D"].append(d)
            last_active = t
            if cur["ts"][-1] - cur["ts"][0] > MAX_WINDOW:
                closed, cur = cur, None          # bounded memory; next change reopens
        elif cur is not None:
            pending.append((t, rt, d))
            if t - last_active >= WINDOW_GAP:
                cur["ts"].append(pending[0][0])
                cur["rt"].append(pending[0][1])
                cur["D"].append(pending[0][2])
                pending = []
                if closed is not None:
                    closed["post_still"] = cur["ts"][0] - closed["ts"][-1]
                    yield closed
                closed, cur = cur, None
        prev, prev_t, prev_rt = d, t, rt
    # the last frame stays on screen to the end of the range (VFR: no frames while still)
    end_t = max(prev_t, t1 - 1.0 / fps) if prev_t is not None else t1
    if cur is not None:
        if pending:
            cur["ts"].append(pending[0][0])
            cur["rt"].append(pending[0][1])
            cur["D"].append(pending[0][2])
        if closed is not None:
            closed["post_still"] = cur["ts"][0] - closed["ts"][-1]
            yield closed
        closed = cur
    if closed is not None:
        closed["post_still"] = max(0.0, end_t - closed["ts"][-1]) + 1.0 / fps
        yield closed


# ====================================================================== shift estimation
def ssd_curve(R, F):
    """Mean squared difference between F and R for every vertical shift d, where d > 0 means
    the content moved UP by d rows (F[y] ~ R[y+d]). Only the overlap counts; returned with
    the overlap fraction so tiny overlaps can be refused."""
    R = np.asarray(R, np.float64) - 128.0
    F = np.asarray(F, np.float64) - 128.0
    h, c = R.shape
    n = 1 << int(math.ceil(math.log2(2 * h)))
    cross = np.fft.irfft(np.conj(np.fft.rfft(F, n, axis=0)) * np.fft.rfft(R, n, axis=0),
                         n, axis=0).sum(1)
    ds = np.arange(-(h - 1), h)
    a = np.abs(ds)
    eF = np.concatenate([[0.0], np.cumsum((F * F).sum(1))])
    eR = np.concatenate([[0.0], np.cumsum((R * R).sum(1))])
    pos = ds >= 0
    EF = np.where(pos, eF[h - a], eF[h] - eF[a])
    ER = np.where(pos, eR[h] - eR[a], eR[h - a])
    ov = h - a
    cost = np.maximum(EF + ER - 2.0 * cross[ds % n], 0.0) / (ov * c)
    return ds, cost, ov / h


def _subpix(ds, cost, i):
    if 0 < i < len(ds) - 1:
        c0, c1, c2 = cost[i - 1], cost[i], cost[i + 1]
        den = c0 - 2 * c1 + c2
        if den > 1e-9:
            return float(ds[i] + max(-0.5, min(0.5, 0.5 * (c0 - c2) / den)))
    return float(ds[i])


def candidates(ds, cost, ovf, lo=None, hi=None):
    """Local minima [(d, cost)] best first, restricted to enough overlap (and [lo, hi])."""
    ok = ovf >= MIN_OVERLAP
    if lo is not None:
        ok &= (ds >= math.floor(lo)) & (ds <= math.ceil(hi))
    idx = np.flatnonzero(ok)
    if not len(idx):
        return []
    c = cost[idx]
    left = np.concatenate([[np.inf], c[:-1]])
    right = np.concatenate([c[1:], [np.inf]])
    loc = idx[(c <= left) & (c <= right)]
    loc = loc[np.argsort(cost[loc])][:6]
    return [(_subpix(ds, cost, i), float(cost[i])) for i in loc]


def trimmed_cost(R, F, d):
    """Mean squared difference after shifting R by (sub-pixel) d, over the best 85 % of the
    overlap rows — so a ticking clock, a scroll indicator or a fixed bar caught at the edge
    of the region cannot outvote the rows that really moved."""
    h = R.shape[0]
    di = int(math.floor(d))
    f = d - di
    ya = np.arange(max(0, -di), min(h, h - di - 1))
    if len(ya) < MIN_OVERLAP * h:
        return float("inf")
    Rs = (1 - f) * R[ya + di] + f * R[ya + di + 1]
    res = np.sort(((F[ya] - Rs) ** 2).mean(1))
    return float(res[:max(1, int(0.85 * len(res)))].mean())


def fits(R, F, d):
    """Does shifting R by d explain F (trimmed SSD <= 0.15*var + 6)? A page change, modal
    or sheet fails; a real scroll with a clock ticking in it passes."""
    return trimmed_cost(R, F, d) <= FIT_REL * float(F.var()) + FIT_ABS


def best_shift(R, F, prior=None, lo=None, hi=None):
    """(d, trimmed cost, ambiguous) for F against R. The FFT curve proposes its local minima
    (plus 'no move'); the trimmed per-row cost picks among them. Near-ties (a list of look-
    alike rows) go to the candidate nearest `prior`, the current velocity."""
    ds, cost, ovf = ssd_curve(R, F)
    cand = [c[0] for c in candidates(ds, cost, ovf, lo, hi)]
    if lo is None or lo <= 0 <= hi:
        cand.append(0.0)
    scored = sorted((trimmed_cost(R, F, d), d) for d in set(round(c, 3) for c in cand))
    scored = [x for x in scored if x[0] < float("inf")]
    if not scored:
        return None, float("inf"), False
    best_c, best_d = scored[0]
    close = [x for x in scored[1:3] if x[0] <= 1.10 * best_c + 1.0 and abs(x[1] - best_d) > 3]
    if close and prior is not None:
        best_c, best_d = min([scored[0]] + close, key=lambda x: abs(x[1] - prior))
    return best_d, best_c, bool(close)


def pair_info(R8, F8):
    R = R8.astype(np.float32)
    F = F8.astype(np.float32)
    diff = np.abs(F - R)
    h = R.shape[0]
    rows = np.flatnonzero(diff.mean(1) > ROW_CHANGE)
    if len(rows) < MIN_BAND * h or rows[-1] + 1 - rows[0] < MIN_BAND * h:
        return {"kind": "still", "d": 0.0}
    y0, y1 = int(rows[0]), int(rows[-1]) + 1
    cols = np.flatnonzero(diff[y0:y1].mean(0) > ROW_CHANGE * 0.5)
    x0, x1 = (int(cols[0]), int(cols[-1]) + 1) if len(cols) else (0, R.shape[1])
    Rc, Fc = R[y0:y1, x0:x1], F[y0:y1, x0:x1]
    d, c, _ = best_shift(Rc, Fc)
    if d is None or c > FIT_REL * float(Fc.var()) + FIT_ABS:
        return {"kind": "break", "d": 0.0, "y0": y0, "y1": y1, "x0": x0, "x1": x1}
    return {"kind": "move" if abs(d) >= 0.5 else "still", "d": d,
            "y0": y0, "y1": y1, "x0": x0, "x1": x1}


def _largest_run(mask, close):
    """(start, end) of the largest run of True after closing gaps <= close; None if empty."""
    idx = np.flatnonzero(mask)
    if not len(idx):
        return None
    runs, s, e = [], idx[0], idx[0]
    for i in idx[1:]:
        if i - e - 1 <= close:
            e = i
        else:
            runs.append((s, e))
            s = e = i
    runs.append((s, e))
    s, e = max(runs, key=lambda r: r[1] - r[0])
    return int(s), int(e) + 1


def _evidence(D, pairs, a, b, rows=None):
    """Translation evidence per row (and per column, within `rows`) over the segment's move
    pairs: +1 'moving' where the measured shift explains the change better than staying put,
    +1 'fixed' where the row did NOT change and the shift would not explain it. Both
    directions (F vs shifted R, R vs shifted F) so rows at either band edge get judged; a
    band row whose shifted partner falls in a fixed bar is simply not judged."""
    h, c = D[a].shape
    mv, fx = np.zeros(h), np.zeros(h)
    mvc, fxc = np.zeros(c), np.zeros(c)
    for k in range(a, b):
        p = pairs[k]
        if p["kind"] != "move":
            continue
        di = int(round(p["d"]))
        if abs(di) >= h:
            continue
        R = D[k].astype(np.float32)
        F = D[k + 1].astype(np.float32)
        x0, x1 = p["x0"], p["x1"]
        for A, B, s in ((F, R, di), (R, F, -di)):      # A[y] ~ B[y + s]
            ya = slice(max(0, -s), min(h, h - s))
            yb = slice(max(0, s), min(h, h + s))
            e_id = np.abs(A[ya] - B[ya])
            e_sh = np.abs(A[ya] - B[yb])
            if rows is None:
                rid, rsh = e_id[:, x0:x1].mean(1), e_sh[:, x0:x1].mean(1)
                r = np.arange(h)[ya]
                mv[r] += rsh + EVIDENCE < rid
                fx[r] += (rid < EVIDENCE) & (rid + EVIDENCE < rsh)   # fixed = did not change
            else:
                # columns: rows inside the band whose partner row is inside it too, so a band
                # row is never compared with a fixed bar
                lo = max(ya.start, rows[0], rows[0] - s)
                hi = min(ya.stop, rows[1], rows[1] - s)
                if hi - lo > 4:
                    cid = e_id[lo - ya.start:hi - ya.start].mean(0)
                    csh = e_sh[lo - ya.start:hi - ya.start].mean(0)
                    mvc += csh + EVIDENCE < cid
                    fxc += (cid < EVIDENCE) & (cid + EVIDENCE < csh)
    return mv, fx, mvc, fxc


def segment_band(D, pairs, a, b):
    """Scrolling band (y0, y1, x0, x1, xa, xb): rows and columns by translation evidence;
    xa..xb widens x0..x1 through the page's plain margins (no evidence either way) up to
    anything fixed such as a sidebar — the strip uses those margins to read the page colour."""
    h, c = D[a].shape
    mv, fx, _, _ = _evidence(D, pairs, a, b)
    floor_r = max(1.0, 0.1 * float(np.percentile(mv, 90)))
    rows = _largest_run((mv >= floor_r) & (mv > fx), int(0.25 * h))
    if rows is None or rows[1] - rows[0] < MIN_BAND * h:
        return None
    _, _, mvc, fxc = _evidence(D, pairs, a, b, rows)
    floor_c = max(1.0, 0.1 * float(np.percentile(mvc, 90)))
    cols = _largest_run((mvc >= floor_c) & (mvc > fxc), int(0.25 * c))
    if cols is None or cols[1] - cols[0] < 4:
        cols = (0, c)
    xa, xb = cols
    while xa > 0 and fxc[xa - 1] <= mvc[xa - 1]:
        xa -= 1
    while xb < c and fxc[xb] <= mvc[xb]:
        xb += 1
    return rows[0], rows[1], cols[0], cols[1], xa, xb


def register(D, pairs, a, b, band):
    """Drift-free offsets (analysis rows; first sample = 0) for samples a..b."""
    y0, y1, x0, x1 = band[:4]
    bh = y1 - y0

    def cut(k):
        return D[k][y0:y1, x0:x1].astype(np.float64)

    o = np.zeros(b - a + 1)
    amb = 0
    big = 0.0
    ref, oref = a, 0.0
    refF = prevF = cut(a)
    vprev = 0.0
    for k in range(a + 1, b + 1):
        F = cut(k)
        thr = FIT_REL * float(F.var()) + FIT_ABS
        d, c, was_amb = best_shift(prevF, F, prior=vprev)
        if d is None or c > thr:
            d = pairs[k - 1]["d"]                 # local change inside the band: trust pair
        amb += was_amb
        big = max(big, abs(d) / bh)
        pred = o[k - 1 - a] + d
        ok = pred
        if ref != k - 1:
            rel = pred - oref
            r = max(3.0, 0.03 * bh)
            d2, c2, _ = best_shift(refF, F, prior=rel, lo=rel - r, hi=rel + r)
            if d2 is not None and abs(d2 - rel) < r - 0.5 and c2 <= thr:
                ok = oref + d2
        o[k - a] = ok
        vprev = ok - o[k - 1 - a]
        if bh - abs(ok - oref) < REF_OVERLAP * bh:
            ref, oref, refF = k, ok, F
        prevF = F
    return o, amb, big


# ============================================================================== sections
def _otsu_split(vals):
    """Threshold splitting 1-D values into two classes, or None when not clearly bimodal."""
    v = np.sort(np.asarray(vals, float))
    if len(v) < 3:
        return None
    best, th = -1.0, None
    for i in range(1, len(v)):
        lo, hi = v[:i], v[i:]
        w0, w1 = len(lo) / len(v), len(hi) / len(v)
        between = w0 * w1 * (lo.mean() - hi.mean()) ** 2
        if between > best:
            best, th = between, (lo[-1] + hi[0]) / 2
    lo, hi = v[v <= th], v[v > th]
    if not len(lo) or not len(hi) or hi.mean() - lo.mean() < math.log(1.8):
        return None
    return th


def group_runs(runs, max_h):
    """Merge content runs [(top, bot)] across the small gaps (Otsu on log gap size, only
    when the gaps are clearly two populations), never making a section taller than max_h.
    Equal gaps (a list of equal cards) stay separate sections. Only LINE-LIKE runs merge
    (both sides no taller than LINE_VH of the viewport, max_h = 0.8 viewport): the
    merge exists to rebuild a text block from its lines, and one big gap on the page (a
    footer, a section title's spacing) must not glue a list of cards into 0.8-viewport
    chunks — skeptic test 25 Sep: 3 cards per 'section', so a step waited for all three."""
    runs = [list(r) for r in runs]
    if len(runs) < 2:
        return [tuple(r) for r in runs]
    gaps = [runs[i + 1][0] - runs[i][1] for i in range(len(runs) - 1)]
    th = _otsu_split(np.log(np.maximum(gaps, 0) + 1.0))
    small = set()
    for i, g in enumerate(gaps):
        if th is not None and math.log(max(g, 0) + 1.0) <= th:
            small.add(i)
    line_h = LINE_VH * max_h / 0.8
    groups = [runs[0]]
    for i in range(len(gaps)):
        nxt = runs[i + 1]
        line_like = max(runs[i][1] - runs[i][0], nxt[1] - nxt[0]) <= line_h
        if i in small and line_like and nxt[1] - groups[-1][0] <= max_h:
            groups[-1][1] = nxt[1]
        else:
            groups.append(list(nxt))
    return [tuple(g) for g in groups]


def page_colour(q, margin_cols=None):
    """The PAGE colour of a stitched strip q (good rows x descriptor cols, ints).

    The page is what shows in the GAPS between cards: rows that are one flat colour across
    the whole strip (<= 3 % of columns may differ, each alone: a thin rule; two adjacent
    columns off — a narrow page margin beside a panel — make the row NOT flat, else a
    desktop form's white panel won over the grey page: skeptic re-run on desktop source A).
    The colour with the most such separate gaps wins. Inside an inset card a row is never
    flat (page margin + card fill), so the card fill cannot win; on a plain page the blank
    rows between text are the page itself. (25 Sep skeptic test: the old rule — commonest
    colour of the columns beside the text — read the WHITE CARD FILL as the page on an iOS
    grouped layout, grey page / white cards / text on the left, so every text LINE became a
    section and steps held on half-visible cards.) Falls back to the commonest colour of
    the plain margins beside the content, then of the whole strip."""
    med = np.median(q, 1)
    off = np.abs(q - med[:, None]) > BG_TOL
    pair = off[:, 1:] & off[:, :-1]              # two adjacent columns off = a real margin
    flat = (off.mean(1) <= 0.03) & ~pair.any(1)
    gaps = {}
    i, n = 0, len(flat)
    while i < n:
        if not flat[i]:
            i += 1
            continue
        j = i
        while j + 1 < n and flat[j + 1] and abs(med[j + 1] - med[i]) <= BG_TOL:
            j += 1
        c = int(round(float(np.median(med[i:j + 1]))))
        key = next((k for k in gaps if abs(k - c) <= BG_TOL), c)
        runs, rows = gaps.get(key, (0, 0))
        gaps[key] = (runs + 1, rows + j - i + 1)
        i = j + 1
    if gaps:
        key, (runs, _) = max(gaps.items(), key=lambda kv: kv[1])
        if runs >= 2:
            return key
    src = q[:, margin_cols] if margin_cols is not None and len(margin_cols) else q
    return int(np.bincount(src.ravel(), minlength=256).argmax())


def pixel_sections(M, bh, sy, margin_cols=None):
    """Content runs of the stitched strip M (rows x descriptor cols), analysis rows.

    Separators are rows that are entirely PAGE BACKGROUND (see page_colour)."""
    good = ~np.isnan(M).any(1)
    Mv = np.where(np.isnan(M), 0, M)
    q = np.clip(np.round(Mv[good]), 0, 255).astype(np.int64)
    if not q.size:
        return []
    bg = page_colour(q, margin_cols)
    # 4 levels: the strip is an average of many frames, so noise is ~1 level, and app
    # designs separate cards from the page by as little as ~9 levels (a mobile app: 245 vs 254)
    dev = np.abs(Mv - bg) > BG_TOL
    # a column that is never page (a rule line, an accent bar down every row) would join
    # everything into one run: ignore it — unless it is most of the width, which is card
    # fill over a page that only shows in thin gaps (dense cards: 12 px gaps, 95 % card)
    persistent = dev[good].mean(0) > 0.9
    if persistent.mean() > 0.25:
        persistent[:] = False
    keep = ~persistent
    if keep.sum() < 3:
        keep[:] = True
    frac = dev[:, keep].mean(1)
    content = (frac > 0.005) & good
    runs, start = [], None
    for i, cflag in enumerate(content):
        if cflag and start is None:
            start = i
        elif not cflag and start is not None:
            runs.append((start, i))
            start = None
    if start is not None:
        runs.append((start, len(content)))
    # hairlines (a list's row dividers: 1-3 source px, smeared over <= 2 analysis rows by
    # the area scaler) separate rows; kept as content they glued a whole list together
    hair = max(2, int(round(4 * sy)))
    runs = [r for r in runs if r[1] - r[0] > hair]
    return split_tall(group_runs(runs, 0.8 * bh), frac, 0.8 * bh)


def split_tall(runs, frac, max_h):
    """A run taller than max_h (a list with no plain page between its items) is cut at its
    quietest rows into pieces <= max_h, so every part of it still has to be seen whole —
    otherwise one giant 'section' would hide a fast scroll through the whole list."""
    out = []
    for a, b in runs:
        while b - a > max_h:
            lo, hi = a + int(0.3 * max_h), a + int(max_h)
            cut = lo + int(np.argmin(frac[lo:hi]))
            out.append((a, cut))
            a = cut + 1
        out.append((a, b))
    return out


# ============================================================================== segments
class Segment:
    """One stretch of samples with a single content space (no page change inside)."""

    def __init__(self, ts, D, a, b, band, o_an, amb, big, geom, pre_ext, post_ext, nominal,
                 rts=None, edges=None):
        self.a, self.b = a, b
        self.band_an = band
        self.D = D
        self.geom = geom
        sy = geom["sy"]
        self.t = np.array(ts[a:b + 1], float)             # when each picture was on screen
        # its real frame's own time — what a hold's "src" / ffmpeg -ss must be (VFR holds)
        self.rt = np.array((rts if rts is not None else ts)[a:b + 1], float)
        self.o_an = o_an
        self.o = o_an / sy                                    # orig px, first sample = 0
        self.bh = (band[1] - band[0]) / sy
        self.band_px = [int(round(band[0] / sy)), int(round(band[1] / sy)),
                        int(round(band[2] * COL_BLOCK / geom["sx"])),
                        int(round(band[3] * COL_BLOCK / geom["sx"]))]
        # columns of the stitched strip (band + plain margins), orig px: OCR reads only these,
        # never a fixed sidebar beside the scrolling page
        self.strip_x = (int(band[4] * COL_BLOCK / geom["sx"]),
                        min(geom["W"], int(math.ceil(band[5] * COL_BLOCK / geom["sx"]))))
        self.amb, self.big = amb, big
        self.m = max(MARGIN_PX, 0.005 * self.bh)
        n = len(self.t)
        # each sample is on screen until the next one; the window's first frame had already
        # been still for pre_ext, and its last frame stays until the next change (post_ext)
        self.pre_ext = float(pre_ext or 0.0)
        self.w = np.append(np.diff(self.t), nominal) if n > 1 else np.array([nominal])
        if post_ext is not None:
            self.w[-1] = max(nominal, post_ext)
        # speed WHILE each sample is displayed (0 for the final, still frame)
        self.vf = np.append(np.abs(np.diff(self.o)) / np.maximum(np.diff(self.t), 1e-6), 0.0)
        k = max(1, int(round(0.1 / nominal)))
        idx = np.arange(n)
        lo, hi = np.maximum(0, idx - k), np.minimum(n - 1, idx + k)
        self.v = np.abs(self.o[hi] - self.o[lo]) / np.maximum(self.t[hi] - self.t[lo], 1e-6)
        self.whole_screen = band[0] <= 0.01 * geom["Ha"] and band[1] >= 0.99 * geom["Ha"]
        # changed-row edges (y0, y1, analysis rows) of each sample pair a..b-1, or None
        self.edges = edges
        self.ignored = {}
        self.sections = []
        self._build_sections()
        self.episodes = self._episodes()

    # --- geometry helpers (content coords, orig px) ---
    def full(self, s, k):
        return s["top"] >= self.o[k] + self.m and s["bot"] <= self.o[k] + self.bh - self.m

    def partial(self, s, k):
        return s["bot"] > self.o[k] and s["top"] < self.o[k] + self.bh

    def clearance(self, s, k):
        return min(s["top"] - self.o[k], self.o[k] + self.bh - s["bot"])

    def tall(self, s):
        return s["bot"] - s["top"] > self.bh - 2 * self.m

    def _build_sections(self, runs_orig=None):
        y0, y1, x0, x1, xa, xb = self.band_an
        bh_an = y1 - y0
        omin = self.o_an.min()
        rows = int(math.ceil(self.o_an.max() - omin)) + bh_an + 1
        # MEDIAN over the distinct scroll positions covering each content row, not the mean:
        # whatever stays put on SCREEN while the page moves (a floating "+" button, the iOS
        # scroll indicator, a desktop scrollbar thumb) crosses any one content row in few of
        # those positions and drops out; with the mean it smeared over every gap between
        # cards and glued the list into 0.8-viewport chunks (skeptic test, 25 Sep). One
        # sample per position, so a long rest does not outvote the scroll.
        pos, last = [], None
        for i in range(len(self.t)):
            r = int(round(self.o_an[i] - omin))
            if r != last:
                pos.append((r, self.a + i))
                last = r
        M = np.full((rows, xb - xa), np.nan)
        CH = 64
        for R in range(0, rows, CH):
            hit = [(r, i) for r, i in pos if r < R + CH and r + bh_an > R]
            if not hit:
                continue
            if len(hit) > 48:
                hit = [hit[j] for j in np.linspace(0, len(hit) - 1, 48).round().astype(int)]
            n_r = min(CH, rows - R)
            st = np.full((len(hit), n_r, xb - xa), np.nan, np.float32)
            for j, (r, i) in enumerate(hit):
                a0, a1 = max(R, r), min(R + n_r, r + bh_an)
                st[j, a0 - R:a1 - R] = self.D[i][y0 + a0 - r:y0 + a1 - r, xa:xb]
            with warnings.catch_warnings():              # all-NaN rows: no coverage
                warnings.simplefilter("ignore", RuntimeWarning)
                M[R:R + n_r] = np.nanmedian(st, axis=0)
        self.strip_rows = rows
        sy = self.geom["sy"]
        margins = [j for j in range(xb - xa) if j < x0 - xa or j >= x1 - xa]
        if runs_orig is None:
            runs = pixel_sections(M, bh_an, sy, margins)
            runs_orig = [((r0 + omin) / sy, (r1 + omin) / sy) for r0, r1 in runs]
        lo_edge, hi_edge = omin / sy, (omin + rows - 1) / sy
        self.sections = []
        for i, (t0, t1) in enumerate(runs_orig):
            self.sections.append({"i": i + 1, "top": float(t0), "bot": float(t1),
                                  "edge": bool(t0 <= lo_edge + 1.0 / sy
                                               or t1 >= hi_edge - 1.0 / sy),
                                  "text": []})
        self.section_source = "pixels"

    def _episodes(self):
        n = len(self.t)
        if n < 2:
            return []
        pv = np.abs(np.diff(self.o)) / np.maximum(np.diff(self.t), 1e-6)
        moving = pv > MOVE_VH * self.bh
        runs, i = [], 0
        while i < len(moving):
            if moving[i]:
                j = i
                while j + 1 < len(moving) and moving[j + 1]:
                    j += 1
                runs.append([i, j + 1])
                i = j + 1
            else:
                i += 1
        merged = []
        for r in runs:
            if merged and self.t[r[0]] - self.t[merged[-1][1]] < MIN_READ:
                merged[-1][1] = r[1]
            else:
                merged.append(r)
        eps = []
        for ks, ke in merged:
            path = float(np.abs(np.diff(self.o[ks:ke + 1])).sum())
            if path < max(MIN_MOVE_VH * self.bh, MIN_MOVE_PX):
                self.ignored["tiny_move"] = self.ignored.get("tiny_move", 0) + 1
                continue
            if self.whole_screen and self.t[ke] - self.t[ks] <= WHOLE_SCREEN_S:
                self.ignored["whole_screen_slide"] = self.ignored.get("whole_screen_slide", 0) + 1
                continue
            if self._sheet_slide(ks, ke):
                self.ignored["sheet_slide"] = self.ignored.get("sheet_slide", 0) + 1
                continue
            eps.append({"ks": ks, "ke": ke, "path": path})
        for j, e in enumerate(eps):
            e["kprev"] = eps[j - 1]["ke"] if j else 0
            e["knext"] = eps[j + 1]["ks"] if j + 1 < len(eps) else n - 1
        return eps

    def _sheet_slide(self, ks, ke):
        """A full-screen cover / sheet presented or dismissed over a still page is a block
        translating vertically — like a scroll — but its leading EDGE travels with it: the
        changed rows start at the sheet's top (or end at a drop-down's bottom), which moves
        against the content offset, while a scroll's changed rows stay put in a fixed band.
        (Skeptic test 25 Sep: a full-screen cover sliding up in 0.45 s was a FAST scroll.)"""
        if not self.edges:
            return False
        ys, os_ = [], []
        for k in range(ks, ke):
            ed = self.edges[k] if k < len(self.edges) else None
            if ed is not None:
                ys.append(ed)
                os_.append(self.o_an[k + 1])
        if len(ys) < 3:
            return False
        ys = np.asarray(ys, float)
        os_ = np.asarray(os_, float)
        path = float(np.ptp(os_))
        if path <= 0:
            return False
        for col in (0, 1):                         # top edge (sheet) or bottom (drop-down)
            y = ys[:, col]
            span = float(np.ptp(y))
            if span < SHEET_EDGE * self.geom["Ha"] or span < 0.5 * path or np.std(y) == 0:
                continue
            if np.corrcoef(y, os_)[0, 1] <= -0.8:
                return True
        return False

    # --- per-episode measures ---
    def rest_before(self, e):
        """Seconds the picture was still before this episode began."""
        pre = self.pre_ext if e["kprev"] == 0 else 0.0
        return pre + float(self.t[e["ks"]] - self.t[e["kprev"]])

    def rest_after(self, e):
        """Seconds the picture stays still after this episode ends."""
        n = len(self.t)
        tail = float(self.w[-1]) if e["knext"] == n - 1 else 0.0
        return float(self.t[e["knext"]] - self.t[e["ke"]]) + tail

    def read_time(self, s, lo, hi):
        """Longest stretch (s) in samples lo..hi where section s is whole and moving at a
        readable speed; the still time before the window counts when lo is its first frame."""
        best = run = 0.0
        if lo == 0 and self.pre_ext > 0 and self.full(s, 0):
            run = best = self.pre_ext
        for k in range(lo, hi + 1):
            if self.full(s, k) and self.vf[k] <= READ_VH * self.bh:
                run += self.w[k]
                best = max(best, run)
            else:
                run = 0.0
        return best

    def metrics(self, e):
        ks, ke = e["ks"], e["ke"]
        t, o, bh = self.t, self.o, self.bh
        dur = max(t[ke] - t[ks], 1e-6)
        net = o[ke] - o[ks]
        pos = float(np.clip(np.diff(o[ks:ke + 1]), 0, None).sum())
        neg = float(-np.clip(np.diff(o[ks:ke + 1]), None, 0).sum())
        direction = "down" if net >= 0 else "up"
        if min(pos, neg) >= 0.2 * (pos + neg):
            direction = "mixed"
        peak = 0.0
        for i in range(ks, ke + 1):
            j = i
            while j < ke and t[j] - t[i] < 0.2 - 1e-6:
                j += 1
            if j > i:
                peak = max(peak, abs(o[j] - o[i]) / (t[j] - t[i]))
        mean = e["path"] / dur
        return {"start": fl3(t[ks]), "end": fl3(t[ke]),
                "direction": direction, "distance_px": round(float(abs(net)), 1),
                "path_px": round(e["path"], 1),
                "peak_speed_px_s": round(peak, 1), "mean_speed_px_s": round(mean, 1),
                "peak_speed_vh_s": round(peak / bh, 3), "mean_speed_vh_s": round(mean / bh, 3),
                "viewport_px": round(bh, 1)}

    def legs(self, e):
        """The episode split at direction reversals that go back at least LEG_VH of the
        viewport: [(k_start, k_end)]. A smaller jiggle stays one leg (judged by its net
        direction): content that only peeked in and out during a nudge is not "scrolled
        past" (desktop source A 177 s: a 0.14-viewport jiggle was flagged by 0.1-viewport legs)."""
        o, ks, ke = self.o, e["ks"], e["ke"]
        tol = max(LEG_VH * self.bh, MIN_MOVE_PX)
        out, a, ext, sgn = [], ks, ks, 0
        for k in range(ks + 1, ke + 1):
            d = o[k] - o[ext]
            if sgn == 0:
                if abs(d) >= 1.0:
                    sgn, ext = (1 if d > 0 else -1), k
            elif d * sgn > 0:
                ext = k                                      # further the same way
            elif abs(d) >= tol:                              # clearly turned back
                out.append((a, ext))
                a, sgn, ext = ext, -sgn, k
        out.append((a, ke))
        return out

    def passes(self, s, e):
        """(not yet scrolled past at the start, scrolled past by the end) for section s, in
        ANY leg of the episode: down then back up must still judge what went by in between
        (the net-direction test saw a 2172 px fling down and straight back as passing
        nothing; skeptic re-run, phone source 2 at 250 s)."""
        o, bh, m = self.o, self.bh, self.m
        first = None
        for a, b in self.legs(e):
            if o[b] >= o[a]:                                 # down: leaves over the top
                r = (s["top"] >= o[a] + m, s["top"] < o[b] + m)
            else:
                r = (s["bot"] <= o[a] + bh - m, s["bot"] > o[b] + bh - m)
            if r[0] and r[1]:
                return r
            first = first or r
        return first

    def judge(self, e):
        """(fast, why, skipped sections, flyby) — see THRESHOLDS."""
        ks, ke = e["ks"], e["ke"]
        o, t, bh, m = self.o, self.t, self.bh, self.m
        skipped = []
        lo, hi = e["kprev"], e["knext"]
        for s in self.sections:
            if s["edge"] or self.tall(s):
                continue
            pre_ok, passed = self.passes(s, e)
            if not (pre_ok and passed):
                continue
            if self.read_time(s, lo, hi) < MIN_READ:
                skipped.append(s)
        flyby = None
        fastk = self.v > FAST_VH * bh
        k = ks
        while k <= ke:
            if fastk[k]:
                j = k
                while j + 1 <= ke and fastk[j + 1]:
                    j += 1
                if t[j] - t[k] >= FLYBY_S - 1e-6 and abs(o[j] - o[k]) >= FLYBY_VH * bh:
                    flyby = (float(t[k]), float(t[j]), float(abs(o[j] - o[k]) / bh))
                k = j + 1
            else:
                k += 1
        why = []
        if skipped:
            ids = ", ".join(f"#{s['i']}" for s in skipped[:12])
            why.append(f"{len(skipped)} section(s) scrolled past without ever being whole at a "
                       f"readable pause (>= {MIN_READ} s, <= {READ_VH} VH/s): {ids}")
        if flyby:
            why.append(f"{flyby[2]:.1f} viewports flew by at > {FAST_VH} VH/s for "
                       f"{flyby[1] - flyby[0]:.2f} s")
        if not why:
            why.append("every section it passes was whole at a readable pause")
        return bool(skipped or flyby), "; ".join(why), skipped, flyby

    def steps(self, e, hold, pre_rest, post_rest, mutate=None):
        """Saad's stepped scroll for this episode (see STEPS in the docstring)."""
        ks, ke = e["ks"], e["ke"]
        # only this episode's frames: up to where the NEXT episode starts. (Searching to the
        # segment's end gave episode 1 steps inside episode 2 when both share a segment — on
        # VFR sources every rest between flings does; skeptic test, 25 Sep.)
        n = e["knext"] + 1
        t = self.t
        secs = [s for s in self.sections if not s["edge"]]
        initial = [s for s in secs if self.full(s, ks)]
        raw = []
        if initial:
            raw.append({"k": ks, "new": initial, "start": True})
        never = []
        for s in secs:
            if s in initial:
                continue
            if self.tall(s):
                cand = [k for k in range(ks, n)
                        if self.o[k] + self.m <= s["top"] <= self.o[k] + 0.25 * self.bh]
            elif mutate == "partial":
                cand = [k for k in range(ks, n) if self.partial(s, k)]
            else:
                cand = [k for k in range(ks, n) if self.full(s, k)]
            if not cand:
                pre_ok, passed = self.passes(s, e)
                if pre_ok and passed:
                    never.append(s)          # it crossed the band but no frame shows it whole
                continue
            k1 = cand[0]
            if mutate != "partial" and not self.tall(s):
                win = [k1]
                for k in cand[1:]:
                    if k == win[-1] + 1 and t[k] - t[k1] <= STEP_SETTLE + 1e-6:
                        win.append(k)
                    else:
                        break
                k1 = max(win, key=lambda k: (round(self.clearance(s, k), 1), -k))
            raw.append({"k": k1, "new": [s], "start": False})
        raw.sort(key=lambda r: (t[r["k"]], r["new"][0]["top"]))
        merged = []
        for r in raw:
            if merged and not merged[-1]["start"] and not any(self.tall(s) for s in r["new"]) \
                    and t[r["k"]] - t[merged[-1]["k"]] <= STEP_MERGE + 1e-6 \
                    and all(self.full(s, r["k"]) for s in merged[-1]["new"]) \
                    and not any(self.tall(s) for s in merged[-1]["new"]):
                merged[-1]["k"] = r["k"]
                merged[-1]["new"] += r["new"]
            else:
                merged.append(dict(r, new=list(r["new"])))
        out = []
        for r in merged:
            k = r["k"]
            if r["start"] and k == ks:
                h = max(0.0, hold - pre_rest)
            elif k >= ke:
                h = max(0.0, hold - post_rest)
            else:
                h = hold
            vis = [s for s in secs if self.full(s, k)]
            out.append({"t": fl3(self.rt[k]), "k": k, "hold": round(h, 2),
                        "section_index": r["new"][0]["i"],
                        "sections": [s["i"] for s in r["new"]],
                        "fully_visible": [label(s) for s in vis]})
        return out, never


def label(s):
    txt = " / ".join(s["text"])[:80]
    return f"#{s['i']}" + (f" {txt}" if txt else "")


def analyze_window(ts, D, pre_still, post_still, geom, fps, ignored=None, breaks=None,
                   rts=None):
    """-> [Segment] for one activity window. `ignored` (dict) counts what was not a scroll;
    `breaks` (list) receives the times of pairs that were not a translation."""
    ignored = {} if ignored is None else ignored
    n = len(ts)
    if n < 2:
        return []
    pairs = [pair_info(D[k], D[k + 1]) for k in range(n - 1)]
    if breaks is not None:
        breaks.extend(ts[k] for k, p in enumerate(pairs) if p["kind"] == "break")
    spans, a = [], 0
    for k, p in enumerate(pairs):
        if p["kind"] == "break":
            if k > a:
                spans.append((a, k))
            a = k + 1
    if n - 1 > a:
        spans.append((a, n - 1))
    nominal = 1.0 / fps
    segs = []
    for a, b in spans:
        if not any(pairs[k]["kind"] == "move" for k in range(a, b)):
            continue
        band = segment_band(D, pairs, a, b)
        if band is None:
            continue
        if band[1] - band[0] < MIN_REGION * geom["Ha"]:
            ignored["small_region"] = ignored.get("small_region", 0) + 1
            continue
        o, amb, big = register(D, pairs, a, b, band)
        edges = [(pairs[k]["y0"], pairs[k]["y1"]) if pairs[k]["kind"] == "move" else None
                 for k in range(a, b)]
        sg = Segment(ts, D, a, b, band, o, amb, big, geom, pre_still if a == 0 else 0.0,
                     post_still if b == n - 1 else None, nominal, rts, edges)
        for key, v in sg.ignored.items():
            ignored[key] = ignored.get(key, 0) + v
        segs.append(sg)
    return segs


def keyboard_like(seg):
    """An on-screen keyboard / passcode keypad sliding in reads like a scroll. Its OCR gives
    it away: phone-pad letter groups (ABC, DEF, ...) or a row of single capital letters."""
    toks = []
    for s in seg.sections:
        for tx in s["text"]:
            toks += tx.replace(" ", "").upper().split("/") + tx.upper().split()
    pad = sum(1 for t in set(toks) if t in KEY_TOKENS)
    letters = sum(1 for t in set(toks) if len(t) == 1 and t.isalpha())
    return pad >= 3 or letters >= 10


# =================================================================================== OCR
def ocr_segment(video, seg, extra_k=()):
    """Read text into seg.sections via Tools/bin/sa_ocr on full-size band crops of the very
    frames that were measured (matched by exact frame time). Returns number of OCR frames."""
    if not OCR_BIN.exists():
        return 0
    try:
        from sa_appread import parse_elements
    except ImportError:
        sys.path.insert(0, str(HERE))
        from sa_appread import parse_elements
    n = len(seg.t)
    want = [0]
    for k in range(1, n):
        if abs(seg.o[k] - seg.o[want[-1]]) >= 0.45 * seg.bh:
            want.append(k)
    want.append(n - 1)
    want = sorted(set(want) | set(k for k in extra_k if 0 <= k < n))
    if len(want) > MAX_OCR_FRAMES:
        keep = np.linspace(0, len(want) - 1, MAX_OCR_FRAMES).round().astype(int)
        want = sorted(set(want[i] for i in keep) | set(extra_k))
    g = seg.geom
    y0, y1 = seg.band_px[0], seg.band_px[1]
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="sa_scrollscan_ocr_"))
    try:
        from PIL import Image
        paths = {}
        want_t, seen_rt = [], set()
        for k in want:                                   # VFR holds share their frame
            rt = round(float(seg.rt[k]), 6)
            if rt not in seen_rt:
                seen_rt.add(rt)
                want_t.append((float(seg.rt[k]), k))
        want_t.sort()
        tol = 0.25 / g["fps"]
        runs = [[want_t[0]]]                             # decode nearby wants in one pass
        for wt in want_t[1:]:
            if wt[0] - runs[-1][-1][0] < 1.0:
                runs[-1].append(wt)
            else:
                runs.append([wt])
        for run in runs:
            i = 0
            for _, t, fr, _ in frames(video, run[0][0], run[-1][0] - run[0][0], g["fps"],
                                      None, g["fps"], hold_gaps=False):
                while i < len(run) and run[i][0] < t - tol:
                    i += 1                               # (never happens on a clean decode)
                if i >= len(run):
                    break
                if abs(t - run[i][0]) <= tol:            # the very frame that was measured
                    k = run[i][1]
                    p = tmp / f"k{k:05d}.png"
                    xa, xb = seg.strip_x
                    Image.fromarray(np.ascontiguousarray(fr[y0:y1, xa:xb])).save(p)
                    paths[str(p)] = k
                    i += 1
        if not paths:
            return 0
        out = subprocess.run([str(OCR_BIN), "--boxes", *paths.keys()],
                             capture_output=True, text=True, timeout=600).stdout
        lines = []
        for row in out.splitlines():
            path, _, payload = row.partition("\t")
            if path not in paths or payload.startswith("!!"):
                continue
            k = paths[path]
            ch = y1 - y0
            for el in parse_elements(payload):
                if el["y"] is None or el["y"] < 1 or el["y"] + el["h"] > ch - 1:
                    continue               # cut by the band edge: a partial read
                txt = el["text"].strip()
                if not txt:
                    continue
                lines.append({"text": txt, "top": el["y"] + seg.o[k],
                              "bot": el["y"] + el["h"] + seg.o[k]})
        _attach_text(seg, lines)
        return len(paths)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _attach_text(seg, lines):
    """Label sections with OCR lines (content coords). If the pixels gave no usable
    structure but OCR has several lines, cluster the lines by gap instead."""
    uniq = []
    for ln in sorted(lines, key=lambda x: x["top"]):
        key = "".join(ch for ch in ln["text"].lower() if ch.isalnum())
        if not key:
            continue
        if any(u["key"] == key and abs(u["top"] - ln["top"]) < 12 for u in uniq):
            continue
        uniq.append(dict(ln, key=key))
    judged = [s for s in seg.sections if not s["edge"]]
    degenerate = not judged or (len(judged) <= 1 and any(
        s["bot"] - s["top"] > 1.2 * seg.bh for s in seg.sections))
    if degenerate and len(uniq) >= 3:
        runs = [(u["top"], u["bot"]) for u in uniq]
        runs.sort()
        joined = []
        for r in runs:                      # overlapping boxes on one line become one run
            if joined and r[0] <= joined[-1][1]:
                joined[-1] = (joined[-1][0], max(joined[-1][1], r[1]))
            else:
                joined.append(r)
        pad = 6.0
        grouped = group_runs(joined, 0.8 * seg.bh)
        seg._build_sections([(a - pad, b + pad) for a, b in grouped])
        seg.section_source = "ocr"
    for u in uniq:
        c = (u["top"] + u["bot"]) / 2
        for s in seg.sections:
            if s["top"] - 2 <= c <= s["bot"] + 2:
                if u["text"] not in s["text"]:
                    s["text"].append(u["text"])
                break


# ================================================================================== scan
def _episode_record(seg, e, hold):
    rec = seg.metrics(e)
    fast, why, skipped, flyby = seg.judge(e)
    # an INSTANT JUMP (the move fits in <= 2 frames at 30 fps: scroll-into-view, anchor,
    # layout collapse) is not someone scrolling fast: what lay between was never on screen,
    # so no step can show it — only a hold before / after the jump helps
    rec["jump"] = bool(seg.t[e["ke"]] - seg.t[e["ks"]] <= JUMP_S)
    if fast and rec["jump"]:
        why = "INSTANT JUMP (<= 2 frames) — hold before/after it; " + why
    rec.update({"fast": fast, "why": why,
                "pre_rest_s": round(seg.rest_before(e), 2),
                "post_rest_s": round(seg.rest_after(e), 2),
                "band_px": seg.band_px, "ambiguous_pairs": seg.amb,
                "skipped_sections": [s["i"] for s in skipped]})
    return rec, fast


def scan(video, t0=None, t1=None, fps=10.0, hold=1.5, ocr="fast", mutate=None, log=None):
    video = pathlib.Path(video).expanduser()
    geom = probe(video)
    t0 = snap(max(0.0, t0 or 0.0), geom)
    t1 = min(geom["dur"], t1) if t1 else geom["dur"]
    fps = min(fps, geom["fps"])
    fine = min(geom["fps"], max(FINE_FPS, fps))
    episodes = []
    ignored = {}
    for win in activity_windows(video, geom, t0, t1, fps):
        seen, breaks = {}, []
        segs = analyze_window(win["ts"], win["D"], win["pre_still"], win["post_still"],
                              geom, fps, seen, breaks, win["rt"])
        use_fps = fps
        # Re-measure the WHOLE window at 30 fps when anything in it is fast or unsure: a
        # fling can move more than the band between 10 fps samples (read as a break), and
        # steps need frame-exact times. ffmpeg decodes every frame either way.
        need = False
        for seg in segs:
            for e in seg.episodes:
                t_a, t_b = seg.t[e["ks"]], seg.t[e["ke"]]
                if seg.judge(e)[0] or seg.amb or seg.big > 0.35 or \
                        any(t_a - 0.5 <= b <= t_b + 0.5 for b in breaks):
                    need = True
        if need and fine > fps + 1e-6:
            fts, fD, frt = [], [], []
            # start at the first sample's REAL frame: on VFR it can be a hold, and a decode
            # starting at the hold's tick would never see the frame being held
            f0 = win["rt"][0]
            for _, tt, fr, rt in frames(video, f0, win["ts"][-1] - f0, fine,
                                        (geom["Wa"], geom["Ha"]), geom["fps"]):
                fts.append(tt)
                fD.append(describe(fr))
                frt.append(rt)
            seen = {}
            segs = analyze_window(fts, fD, max(0.0, win["pre_still"] - (win["ts"][0] - f0)),
                                  win["post_still"], geom, fine, seen, None, frt)
            use_fps = fine
        for key, v in seen.items():
            ignored[key] = ignored.get(key, 0) + v
        for seg in segs:
            for e in seg.episodes:
                rec, fast = _episode_record(seg, e, hold)
                rec["measured_at_fps"] = use_fps
                steps, never = [], []
                if fast:
                    steps, never = seg.steps(e, hold, rec["pre_rest_s"], rec["post_rest_s"],
                                             mutate)
                n_ocr = 0
                if ocr == "all" or (ocr == "fast" and fast):
                    n_ocr = ocr_segment(video, seg, extra_k=[st["k"] for st in steps])
                    if n_ocr and keyboard_like(seg):
                        ignored["keyboard"] = ignored.get("keyboard", 0) + 1
                        continue
                    if n_ocr and fast:        # sections may have been rebuilt from OCR
                        steps, never = seg.steps(e, hold, rec["pre_rest_s"],
                                                 rec["post_rest_s"], mutate)
                        _, why, skipped, _ = seg.judge(e)
                        rec["why"], rec["skipped_sections"] = why, [x["i"] for x in skipped]
                for st in steps:
                    st.pop("k", None)
                rec["ocr_frames"] = n_ocr
                rec["section_source"] = seg.section_source
                rec["sections"] = [{"i": x["i"], "top_px": round(x["top"], 1),
                                    "bot_px": round(x["bot"], 1), "edge": bool(x["edge"]),
                                    "tall": bool(seg.tall(x)),
                                    "text": " / ".join(x["text"])[:120]}
                                   for x in seg.sections]
                if fast:
                    rec["steps"] = steps
                    rec["never_fully_visible"] = [label(x) for x in never]
                    rec["spec_holds"] = [{"line": None, "src": st["t"], "secs": st["hold"]}
                                         for st in steps if st["hold"] > 0]
                ks, ke = e["ks"], e["ke"]
                lo, hi = max(0, ks - 3), min(len(seg.t) - 1, ke + 3)
                rec["track"] = [[fl3(seg.t[k]), round(float(seg.o[k]), 1)]
                                for k in range(lo, hi + 1)]
                episodes.append(rec)
                if log:
                    log(rec)
        win.clear()
    episodes.sort(key=lambda r: r["start"])
    for i, r in enumerate(episodes, 1):
        r["i"] = i
    fast = [r for r in episodes if r["fast"]]
    scrolls = [r for r in fast if not r["jump"]]
    jumps = [r for r in fast if r["jump"]]
    parts = []
    if scrolls:
        parts.append(f"This recording has {len(scrolls)} fast scroll"
                     f"{'s' if len(scrolls) > 1 else ''} (at "
                     f"{', '.join(tc(r['start']) for r in scrolls)}). I'll pace "
                     f"{'each' if len(scrolls) > 1 else 'it'} as a stepped scroll with held "
                     f"frames, the way you record: stop each time the next section is fully "
                     f"readable.")
    if jumps:
        parts.append(f"{'Also ' if scrolls else ''}{len(jumps)} instant page jump"
                     f"{'s' if len(jumps) > 1 else ''} (at "
                     f"{', '.join(tc(r['start']) for r in jumps)}) — nothing to step there, "
                     f"I'd hold the frame before the jump.")
    saad = " ".join(parts) or "No fast scrolling found in this recording."
    return {"video": str(video), "size": [geom["W"], geom["H"]], "src_fps": round(geom["fps"], 3),
            "range": [round(t0, 3), round(t1, 3)], "fps": fps, "hold": hold,
            "thresholds": {"READ_VH": READ_VH, "MIN_READ_S": MIN_READ, "FAST_VH": FAST_VH,
                           "FLYBY_S": FLYBY_S, "FLYBY_VH": FLYBY_VH, "MOVE_VH": MOVE_VH,
                           "MARGIN_PX": MARGIN_PX, "BG_TOL": BG_TOL,
                           "STEP_MERGE_S": STEP_MERGE},
            "episodes": episodes, "fast_count": len(fast), "fast_scrolls": len(scrolls),
            "instant_jumps": len(jumps), "not_scrolls": ignored,
            "tell_saad": saad}


def _jsonable(x):
    if isinstance(x, np.generic):
        return x.item()
    raise TypeError(type(x).__name__)


def fl3(t):
    """Seconds for output, rounded DOWN to the millisecond: ffmpeg -ss takes the first frame
    at or after the time, so a rounded-up time would hold the NEXT frame."""
    return math.floor(float(t) * 1000 + 0.01) / 1000          # 0.01 ms: float noise only


def tc(t):
    m, s = divmod(max(0.0, t), 60)
    return f"{int(m)}:{s:04.1f}"


def print_report(res, out=sys.stdout):
    w = out.write
    w(f"sa_scrollscan: {pathlib.Path(res['video']).name}  ({res['size'][0]}x{res['size'][1]} "
      f"@ {res['src_fps']} fps, {res['range'][0]}-{res['range'][1]} s, sampled {res['fps']} fps)\n")
    w(f"scroll episodes: {len(res['episodes'])} · FAST: {res['fast_count']}"
      + (f"  (ignored as not page scrolls: {res['not_scrolls']})" if res.get("not_scrolls") else "")
      + "\n")
    for r in res["episodes"]:
        tag = ("FAST JUMP" if r["jump"] else "FAST") if r["fast"] else "ok"
        w(f"  #{r['i']:<3} {r['start']:8.2f}-{r['end']:<8.2f} {r['direction']:<5} "
          f"{r['distance_px']:7.0f} px  peak {r['peak_speed_vh_s']:.2f} VH/s "
          f"({r['peak_speed_px_s']:.0f} px/s)  mean {r['mean_speed_vh_s']:.2f} VH/s  "
          f"[viewport {r['viewport_px']:.0f} px]  {tag}\n")
        w(f"        {r['why']}\n")
        for st in r.get("steps", []):
            vis = "; ".join(st["fully_visible"])[:150]
            w(f"        step {st['t']:8.2f} s  hold +{st['hold']:.2f} s  new {st['sections']}  "
              f"whole: {vis}\n")
        if r.get("never_fully_visible"):
            w(f"        never fully visible (cannot be held whole): "
              f"{', '.join(r['never_fully_visible'])}\n")
    w(f"Tell Saad: {res['tell_saad']}\n")


# ================================================================================== test
def _font(size):
    from PIL import ImageFont
    for f in ("/System/Library/Fonts/Helvetica.ttc", "/System/Library/Fonts/Supplemental/Arial.ttf",
              "/Library/Fonts/Arial.ttf"):
        if os.path.exists(f):
            try:
                return ImageFont.truetype(f, size)
            except OSError:
                pass
    return ImageFont.load_default(size=size)


W_T, H_T, HEAD, FOOT = 540, 960, 120, 860       # synthetic phone: band rows 120..860
BLOCK_H, GAP, TOP = 260, 40, 40


def _synthetic_page():
    from PIL import Image, ImageDraw
    blocks = [(TOP + i * (BLOCK_H + GAP), TOP + i * (BLOCK_H + GAP) + BLOCK_H) for i in range(10)]
    page = Image.new("L", (W_T, blocks[-1][1] + TOP), 255)
    d = ImageDraw.Draw(page)
    big, small = _font(44), _font(24)
    for i, (a, b) in enumerate(blocks):
        d.rounded_rectangle([24, a, W_T - 24, b], radius=14, fill=236, outline=150, width=2)
        d.text((52, a + 28), f"Block {i + 1}", font=big, fill=20)
        d.text((52, a + 110), f"Amount {1250 + 37 * i} AED", font=small, fill=60)
        d.text((52, a + 150), f"Status: step {i + 1} of 10", font=small, fill=60)
        d.rectangle([W_T - 150, a + 30, W_T - 52, a + 90], fill=90)
    return np.asarray(page), blocks


def _render(path, offsets, fps=30, clock=True, blink=False):
    """Encode a synthetic recording: fixed header (clock) + fixed tab bar + scrolling band."""
    from PIL import Image, ImageDraw
    page, _ = _synthetic_page()
    font = _font(30)
    cmd = [FFMPEG, "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "gray", "-s",
           f"{W_T}x{H_T}", "-r", str(fps), "-i", "-", "-c:v", "libx264", "-preset", "veryfast",
           "-crf", "16", "-pix_fmt", "yuv420p", "-threads", THREADS, str(path)]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for k, off in enumerate(offsets):
        fr = Image.new("L", (W_T, H_T), 255)
        d = ImageDraw.Draw(fr)
        d.rectangle([0, 0, W_T, HEAD - 1], fill=40)
        d.text((24, 40), "Deals", font=font, fill=235)
        if clock:
            d.text((W_T - 150, 40), f"09:{41 + (k // 15) % 10:02d}", font=font, fill=235)
        d.rectangle([0, FOOT, W_T, H_T], fill=70)
        for j, lab in enumerate(("Home", "Deals", "More")):
            if blink and (k // 21) % 2 == j % 2:
                d.rectangle([j * 180, FOOT, j * 180 + 179, H_T], fill=120)
            d.text((j * 180 + 40, FOOT + 32), lab, font=font, fill=230)
        arr = np.array(fr)
        o = int(off)
        arr[HEAD:FOOT] = page[o:o + (FOOT - HEAD)]
        p.stdin.write(arr.tobytes())
    p.stdin.close()
    p.wait()
    if p.returncode:
        raise RuntimeError("ffmpeg could not encode the synthetic recording")


def _ease(u):
    return 0.5 - 0.5 * math.cos(math.pi * min(1.0, max(0.0, u)))


def _fast_profile(fps=30):
    total = 3040 - (FOOT - HEAD)                 # 2300 px: top to bottom in 2 s
    out = []
    for k in range(int(4.0 * fps) + 1):
        t = k / fps
        out.append(int(round(total * _ease((t - 1.0) / 2.0))))
    return out


def _stepped_profile(fps=30):
    """Saad's way: rest at the top, then scroll until the next block is whole, pause."""
    _, blocks = _synthetic_page()
    bh = FOOT - HEAD
    targets = [min(b + 24 - bh, 3040 - bh) for a, b in blocks if b + 24 - bh > 0]
    keys = [(0.0, 0)]
    t = 1.2
    cur = 0
    for tg in targets:
        if tg <= cur:
            continue
        keys.append((t, cur))
        keys.append((t + 0.7, tg))
        cur = tg
        t += 0.7 + 1.2
    keys.append((t, cur))
    out = []
    for k in range(int(t * fps) + 1):
        tt = k / fps
        o = cur
        for (ta, oa), (tb, ob) in zip(keys, keys[1:]):
            if ta <= tt <= tb:
                o = oa + (ob - oa) * (_ease((tt - ta) / (tb - ta)) if tb > ta else 1)
                break
        out.append(int(round(o)))
    return out


# independent second synthetic (skeptic, 25 Sep): what the role-based phone recordings really are —
# iOS grouped layout (grey page, WHITE cards inset 16 px, 12 px gaps, text on the left), a
# floating "+" button and the scroll indicator over the list, 604x1312 (analysis scaling),
# VFR 60 fps with no frames while still
W_G, H_G, HEAD_G, FOOT_G = 604, 1312, 150, 1202


def _grouped_page():
    from PIL import Image, ImageDraw
    heights = [220, 160, 300, 180, 260, 140, 320, 200, 240, 180, 280, 160, 220, 300, 180, 200,
               240, 180, 260, 200]
    cards, y = [], 16
    for h in heights:
        cards.append((y, y + h))
        y += h + 12
    page = Image.new("L", (W_G, y + 1200), 242)
    d = ImageDraw.Draw(page)
    f1, f3 = _font(30), _font(20)
    for i, (a, b) in enumerate(cards):
        d.rounded_rectangle([16, a, W_G - 16, b], radius=14, fill=255)
        d.text((36, a + 14), f"Deal {1040 + i}", font=f1, fill=20)
        yy = a + 58
        while yy + 26 < b - 10:
            d.text((36, yy), f"Amount {1000 + 37 * i + yy % 97} AED", font=f3, fill=100)
            yy += 34
    return np.asarray(page), cards


def _render_grouped(path, frame_fn, n, vfr=True):
    cmd = [FFMPEG, "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "gray", "-s",
           f"{W_G}x{H_G}", "-r", "60", "-i", "-"]
    if vfr:                                      # drop repeated frames, keep real timestamps
        cmd += ["-vf", "mpdecimate=hi=64:lo=32:frac=0.33", "-fps_mode", "vfr"]
    cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-pix_fmt", "yuv420p",
            "-threads", THREADS, str(path)]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for k in range(n):
        p.stdin.write(np.ascontiguousarray(frame_fn(k), np.uint8).tobytes())
    p.stdin.close()
    if p.wait():
        raise RuntimeError("ffmpeg could not encode the synthetic recording")


def _grouped_chrome():
    from PIL import Image, ImageDraw
    fr = Image.new("L", (W_G, H_G), 248)
    d = ImageDraw.Draw(fr)
    d.text((24, 82), "Deals", font=_font(40), fill=0)
    d.line([0, HEAD_G - 1, W_G, HEAD_G - 1], fill=210)
    d.line([0, FOOT_G, W_G, FOOT_G], fill=210)
    for j, lab in enumerate(("Home", "Deals", "Tasks", "More")):
        d.text((40 + j * 150, FOOT_G + 58), lab, font=_font(18), fill=60)
    return np.array(fr)


def _decel(t, t1, dist, tau=0.3, dur=2.0):
    if t <= t1:
        return 0.0
    return dist * (1 - math.exp(-min(t - t1, dur) / tau)) / (1 - math.exp(-dur / tau))


def self_test(mutate=None):
    if mutate:
        print(f"MUTATION '{mutate}': a rule the test guards is deliberately broken — this test "
              f"must FAIL")
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="sa_scrollscan_test_"))
    fails = []

    def check(cond, msg):
        print(("  ok   " if cond else "  FAIL ") + msg)
        if not cond:
            fails.append(msg)

    try:
        _, blocks = _synthetic_page()
        band_t = FOOT - HEAD

        def truth_block(sec_top, sec_bot, t_ref, truth, off_ref):
            """Which block a section is, by ground truth (content -> page coords)."""
            base = truth[int(round(t_ref * 30))] - off_ref
            a, b = sec_top + base, sec_bot + base
            ov = [max(0, min(b, bb) - max(a, ba)) for ba, bb in blocks]
            j = int(np.argmax(ov))
            return j + 1 if ov[j] > 0.6 * (b - a) else None

        # (a) FAST: whole page in 2 s -------------------------------------------------------
        fast = _fast_profile()
        pa = tmp / "fast.mp4"
        _render(pa, fast)
        res = scan(pa, fps=10, hold=1.5, ocr="fast", mutate=mutate)
        print("(a) fast fling, 2300 px in 2 s:")
        check(len(res["episodes"]) == 1, f"exactly one episode (got {len(res['episodes'])})")
        if res["episodes"]:
            r = res["episodes"][0]
            check(r["fast"] is True, f"flagged fast ({r['why']})")
            check(abs(r["band_px"][0] - HEAD) <= 6 and abs(r["band_px"][1] - FOOT) <= 6,
                  f"band = rows {r['band_px'][0]}-{r['band_px'][1]} (truth {HEAD}-{FOOT}): fixed "
                  f"header/tab bar excluded")
            t_ref, off_ref = r["track"][0]
            base = fast[int(round(t_ref * 30))]
            err = max(abs(off - (fast[int(round(t * 30))] - base)) for t, off in r["track"])
            check(err <= 4.0, f"integrated offset within 4 px of truth (max err {err:.2f} px, "
                              f"{len(r['track'])} samples at {r['measured_at_fps']} fps)")
            check(abs(r["distance_px"] - 2300) <= 4, f"distance {r['distance_px']} px (truth 2300)")
            secs = {s["i"]: s for s in r["sections"]}
            seq, all_whole = [], True
            mism = 0
            for st in r.get("steps", []):
                o_true = fast[int(round(st["t"] * 30))]
                for si in st["sections"]:
                    s = secs[si]
                    b = truth_block(s["top_px"], s["bot_px"], t_ref, fast, off_ref)
                    seq.append(b)
                    if b is None:
                        all_whole = False
                        continue
                    ya, yb = blocks[b - 1][0] - o_true + HEAD, blocks[b - 1][1] - o_true + HEAD
                    if not (ya >= HEAD and yb <= FOOT):
                        all_whole = False
                        print(f"         step {st['t']} s: block {b} on screen rows {ya}-{yb}, "
                              f"band {HEAD}-{FOOT} -> NOT fully visible")
                    if s["text"] and f"block {b}" not in s["text"].lower():
                        mism += 1
            print(f"         steps: {[(st['t'], st['sections'], st['hold']) for st in r.get('steps', [])]}")
            print(f"         blocks in step order: {seq}")
            check(seq and seq == sorted(seq) and len(set(seq)) == len(seq) and None not in seq,
                  "steps strictly in page order, one per block")
            check(set(seq) == set(range(1, 11)) or set(seq) == set(range(min(seq or [1]), 11)),
                  f"every block 1..10 gets its step (from the first not already whole)")
            check(all_whole, "at every step frame each named block is fully inside the band "
                             "(ground truth)")
            if OCR_BIN.exists():
                labelled = sum(1 for s in r["sections"] if s["text"])
                check(labelled >= 8 and mism == 0,
                      f"OCR labels {labelled}/10 sections, none mislabelled ({mism})")

        # (b) SLOW, stepped like Saad -------------------------------------------------------
        slow = _stepped_profile()
        pb = tmp / "stepped.mp4"
        _render(pb, slow)
        res = scan(pb, fps=10, hold=1.5, ocr="off", mutate=mutate)
        print("(b) Saad-style stepped scroll (move until the next block is whole, pause 1.2 s):")
        check(len(res["episodes"]) >= 7, f"each move is its own episode ({len(res['episodes'])})")
        check(res["fast_count"] == 0,
              f"not flagged fast ({res['fast_count']} of {len(res['episodes'])})"
              + "".join(f"; {r['why']}" for r in res["episodes"] if r["fast"]))
        err = 0.0
        for r in res["episodes"]:
            t_ref, off_ref = r["track"][0]
            base = slow[int(round(t_ref * 30))] - off_ref
            err = max(err, max(abs(off + base - slow[int(round(t * 30))]) for t, off in r["track"]))
        check(err <= 4.0, f"offsets within 4 px of truth on every stepped move (max {err:.2f})")

        # (c) FIXED header/footer changing, page still ---------------------------------------
        pc = tmp / "static.mp4"
        _render(pc, [500] * 90, clock=True, blink=True)
        res = scan(pc, fps=10, ocr="off")
        print("(c) still page, header clock ticking + tab bar highlight blinking:")
        check(len(res["episodes"]) == 0,
              f"no fake motion from fixed bars (episodes: {len(res['episodes'])})")

        # (d) iOS grouped cards, two flings 2.3 s apart, VFR, "+" button + scroll indicator --
        gp, gcards = _grouped_page()
        ch = _grouped_chrome()
        bhg = FOOT_G - HEAD_G
        def _eased(t, t1, dist, dur=1.3):
            u = min(1.0, max(0.0, (t - t1) / dur))
            return dist * (0.5 - 0.5 * math.cos(math.pi * u))
        prof = [int(round(_decel(k / 60, 1.2, 1500) + _eased(k / 60, 4.0, 2600)))
                for k in range(int(6.5 * 60) + 1)]
        moving = np.array([0] + [prof[k] != prof[k - 1] for k in range(1, len(prof))])
        shown = np.convolve(moving, np.ones(30), "full")[:len(prof)] > 0   # + 0.5 s fade

        def gframe(k):
            fr = ch.copy()
            fr[HEAD_G:FOOT_G] = gp[prof[k]:prof[k] + bhg]
            if shown[k]:                                         # iOS scroll indicator
                L = bhg * bhg // gp.shape[0]
                y = HEAD_G + 3 + int((bhg - L - 6) * prof[k] / (gp.shape[0] - bhg))
                fr[y:y + L, W_G - 9:W_G - 4] = 110
            yy, xx = np.ogrid[:H_G, :W_G]                        # floating "+" button
            fr[(yy - (FOOT_G - 80)) ** 2 + (xx - (W_G - 80)) ** 2 < 50 ** 2] = 90
            return fr
        pd_ = tmp / "grouped_vfr.mp4"
        _render_grouped(pd_, gframe, len(prof))
        res = scan(pd_, fps=10, hold=1.5, ocr="off", mutate=mutate)
        print("(d) iOS grouped cards (grey page, white cards), two flings 2.3 s apart, VFR 60 fps, "
              "'+' button and scroll indicator over the list:")
        eps = res["episodes"]
        check(len(eps) == 2 and all(r["fast"] for r in eps),
              f"two fast episodes, the rest between them kept (got {len(eps)}: "
              f"{[(r['start'], r['end'], r['fast']) for r in eps]})")
        check(all(abs(r["start"] - t_) <= 0.12 for r, t_ in zip(eps, (1.2, 4.0))),
              f"episode starts at the real motion (1.2, 4.0 s): {[r['start'] for r in eps]}")
        cardlike = total = 0
        bad = []
        for r in eps:
            t_ref, off_ref = r["track"][0]
            base = prof[int(math.ceil(t_ref * 60 - 1e-6))] - off_ref + r["band_px"][0] - HEAD_G
            for sc in r["sections"]:
                if sc["edge"]:
                    continue
                a, b = sc["top_px"] + base, sc["bot_px"] + base
                iou = max(max(0, min(b, cb) - max(a, ca)) / (max(b, cb) - min(a, ca))
                          for ca, cb in gcards)
                total += 1
                cardlike += iou >= 0.8
            secs = {sc["i"]: sc for sc in r["sections"]}
            for st in r.get("steps", []):
                if not (r["start"] - r["pre_rest_s"] - 0.05 <= st["t"] <= r["end"] + 0.05):
                    bad.append(f"step {st['t']} outside episode {r['start']}-{r['end']}")
                o_t = prof[int(math.ceil(st["t"] * 60 - 1e-6))]
                for si in st["sections"]:
                    a = secs[si]["top_px"] + base
                    b = secs[si]["bot_px"] + base
                    ov = [max(0, min(b, cb) - max(a, ca)) for ca, cb in gcards]
                    j = int(np.argmax(ov))
                    ca, cb = gcards[j] if ov[j] > 0.5 * (b - a) else (a, b)
                    if not (ca >= o_t - 1 and cb <= o_t + bhg + 1):
                        bad.append(f"step {st['t']}: card {j + 1} not whole")
        check(total and cardlike >= 0.8 * total,
              f"sections are whole cards, not text lines or card chunks ({cardlike}/{total})")
        check(not bad, f"every step inside its episode and its cards whole (ground truth) "
                       f"{bad[:3]}")

        # (e) full-screen cover presented and dismissed over a still page: not a scroll ------
        still = ch.copy()
        still[HEAD_G:FOOT_G] = gp[:bhg]
        cover = np.full((H_G, W_G), 250, np.uint8)
        cover[60:] = gp[800:800 + H_G - 60]

        def eframe(k):
            t = k / 60
            u = min(1.0, max(0.0, (t - 1.0) / 0.45)) if t < 3.0 else \
                1.0 - min(1.0, max(0.0, (t - 3.0) / 0.4))
            u = 0.5 - 0.5 * math.cos(math.pi * u)
            fr = still.copy()
            y = int(round(H_G - (H_G - 60) * u))
            if y < H_G:
                fr[y:] = cover[60:60 + H_G - y]
            return fr
        pe = tmp / "cover.mp4"
        _render_grouped(pe, eframe, int(4.5 * 60), vfr=False)
        res = scan(pe, fps=10, ocr="off")
        print("(e) full-screen cover slides up over a still page, then is dismissed:")
        check(len(res["episodes"]) == 0,
              f"not reported as a scroll (episodes: {[(r['start'], r['distance_px'], r['fast']) for r in res['episodes']]}; ignored {res['not_scrolls']})")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if fails:
        print(f"sa_scrollscan self-test: FAILED ({len(fails)})")
        return 1
    print("sa_scrollscan self-test: ok")
    return 0


# ================================================================================== main
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video", nargs="?")
    ap.add_argument("--from", dest="t0", type=float, default=None)
    ap.add_argument("--to", dest="t1", type=float, default=None)
    ap.add_argument("--fps", type=float, default=10.0, help="sample rate for detection")
    ap.add_argument("--hold", type=float, default=1.5, help="seconds held per step")
    ap.add_argument("--json", default=None, help="also write the full report here")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--ocr", action="store_true", help="OCR every episode (default: fast ones)")
    g.add_argument("--no-ocr", action="store_true", help="never OCR")
    ap.add_argument("--test", action="store_true")
    ap.add_argument("--mutate", choices=["partial", "nohold"], default=None,
                    help=argparse.SUPPRESS)          # proves the test bites: step on first sight,
                                                     # no VFR hold samples
    a = ap.parse_args(argv)
    try:
        os.nice(10)                                   # Saad is editing on this machine
    except (OSError, AttributeError):
        pass
    if a.test:
        global _MUT
        _MUT = a.mutate
        return self_test(a.mutate)
    if not a.video:
        ap.error("give a video, or --test")
    res = scan(a.video, a.t0, a.t1, a.fps, a.hold,
               "off" if a.no_ocr else ("all" if a.ocr else "fast"), a.mutate)
    print_report(res)
    if a.json:
        pathlib.Path(a.json).write_text(json.dumps(res, indent=1, default=_jsonable))
        print(f"json: {a.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
