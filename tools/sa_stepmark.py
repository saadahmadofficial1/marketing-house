#!/usr/bin/env python3
"""sa_stepmark — house-style step call-outs for software training videos.

Draws a blue (BOX_BLUE) rounded box around the UI element being clicked, plus a labelled
chip saying what's happening. Same look on every topic, so a long video series
feels like one product.

  python3 sa_stepmark.py steps.json --overlay   # transparent MOV for an overlay track
  python3 sa_stepmark.py steps.json --burn      # flattened MP4 preview
  python3 sa_stepmark.py --test

steps.json:
  {"video": "/path/in.mp4",
   "steps": [{"t": 5.0, "dur": 2.5, "box": [1200,180,120,32], "label": "Click Save"}]}

--overlay is the one to use: it renders ProRes 4444 with real alpha, for an overlay
track above the footage, so each call-out can still be moved, trimmed or deleted.
Nothing is baked into the source.
"""
import argparse
import json
import os
import pathlib
import subprocess
import sys
import tempfile

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

# ---- house style (keep identical across the whole series) ----
BOX_BLUE = (57, 73, 171, 255)     # #3949AB — set this to the software's own accent colour
BOX_SOFT = (57, 73, 171, 80)      # glow

# 23 Sep 2026, a MOBILE app. Same method as the blue above: sample the app's
# own UI (the colour of its Approve button and completion chips). Placeholders below.
# Requirement (23 Sep): the box takes the app's own green, matching its UI style.
# CAUTION, and the reason ACCENT exists: in this app green MEANS approved/done. A green
# box drawn on the Approve button or a completion chip disappears into it, and on a
# neutral element it can read as "this is already done". Use APP_GREEN as the default
# and ACCENT_GREEN for any target that is itself green.
APP_GREEN = (46, 125, 50, 255)     # #2E7D32 placeholder: sample your app's own accent colour
APP_GREEN_SOFT = (46, 125, 50, 80)
ACCENT_GREEN = (102, 187, 106, 255)  # #66BB6A placeholder: same hue, lifted, for green-on-green
ACCENT_GREEN_SOFT = (102, 187, 106, 80)
INK = (255, 255, 255, 255)       # chip text
STROKE = 4                        # box line width
RADIUS = 8                        # box corner radius
PAD = 10                          # breathing room around the element
CHIP_H = 46
CHIP_PAD = 18
CHIP_GAP = 22                     # gap between box and chip
FADE = 0.25                       # seconds in/out


def _font(size):
    """Poppins by default; swap in the target software's UI typeface so call-outs
    read as part of it."""
    home = os.path.expanduser("~")
    for p in (f"{home}/Library/Fonts/Poppins-SemiBold.ttf",
              f"{home}/Library/Fonts/Poppins-Medium.ttf",
              f"{home}/Library/Fonts/Poppins-Bold.ttf",
              "/Library/Fonts/Poppins-SemiBold.ttf"):
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    raise SystemExit("Poppins not found — install it (Google Fonts) into ~/Library/Fonts")


def _busyness(frame, x, y, w, h):
    """How much detail sits in this rectangle. Low = empty space = safe for a label."""
    H, W = frame.shape[:2]
    x0, y0 = max(0, int(x)), max(0, int(y))
    x1, y1 = min(W, int(x + w)), min(H, int(y + h))
    if x1 - x0 < 8 or y1 - y0 < 8:
        return 1e9                       # off-screen: never choose it
    patch = frame[y0:y1, x0:x1]
    return float(cv2.Canny(cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY), 60, 160).mean())


def place_chip(canvas, box, cw, frame):
    """Pick the emptiest spot around the element so the label never sits on top of UI."""
    W, H = canvas
    x, y, w, h = box
    x0, y0, x1, y1 = x - PAD, y - PAD, x + w + PAD, y + h + PAD
    cands = []
    for g in (CHIP_GAP, CHIP_GAP * 3, CHIP_GAP * 5):  # search farther out until clear space
        cands += [
            (x0, y0 - g - CHIP_H),                    # above, left-aligned
            (x0, y1 + g),                             # below, left-aligned
            (x1 + g, y0 + (h - CHIP_H) // 2),         # right
            (x0 - g - cw, y0 + (h - CHIP_H) // 2),    # left
            (x1 - cw, y0 - g - CHIP_H),               # above, right-aligned
            (x1 - cw, y1 + g),                        # below, right-aligned
        ]
    best, best_score = None, None
    for cx, cy in cands:
        if cx < 8 or cy < 8 or cx + cw > W - 8 or cy + CHIP_H > H - 8:
            continue                                   # must fit fully on screen
        score = _busyness(frame, cx, cy, cw, CHIP_H) if frame is not None else 0
        if best_score is None or score < best_score:
            best, best_score = (int(cx), int(cy)), score
    if best is None:                                   # nothing fits — clamp above
        best = (max(8, min(W - 8 - cw, x0)), max(8, y0 - CHIP_GAP - CHIP_H))
    return best


def render_step(canvas, box, label, frame=None, want_chip=False, colour=None):
    """One transparent PNG: rounded box around `box` + label chip in nearby empty space.

    `colour` is (rgba, rgba_glow); omit it and the default blue is used exactly as before,
    so every existing desktop build renders unchanged."""
    W, H = canvas
    line, glow = colour if colour else (BOX_BLUE, BOX_SOFT)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    x, y, w, h = box
    x0, y0, x1, y1 = x - PAD, y - PAD, x + w + PAD, y + h + PAD

    # soft glow, then the crisp box
    d.rounded_rectangle([x0 - 3, y0 - 3, x1 + 3, y1 + 3], radius=RADIUS + 3,
                        outline=glow, width=STROKE + 5)
    d.rounded_rectangle([x0, y0, x1, y1], radius=RADIUS, outline=line, width=STROKE)

    chip = None
    if label:
        f = _font(26)
        tw = d.textlength(label, font=f)
        cw = int(tw) + CHIP_PAD * 2
        cx, cy = place_chip(canvas, box, cw, frame)
        d.rounded_rectangle([cx, cy, cx + cw, cy + CHIP_H], radius=7, fill=line)
        d.text((cx + CHIP_PAD, cy + CHIP_H / 2), label, font=f, fill=INK, anchor="lm")
        chip = [int(cx), int(cy), int(cw), CHIP_H]
    return (img, chip) if want_chip else img


HEAD_H, HEAD_PAD, HEAD_FONT = 56, 22, 30     # the mobile heading pill
HEAD_CLEAR = 10       # px between the pill and the box's outer edge (the glow reaches ~8)
TEXT_AIR = 4          # px the pill keeps off any text box
PER_PX = 1 / 300      # heading fallback: 300 px further from its box = hiding one more (weight-1) word


def _rect_gap(a, b):
    """Distance between two (x0, y0, x1, y1) rects, 0 when they touch or overlap."""
    dx = max(0, b[0] - a[2], a[0] - b[2])
    dy = max(0, b[1] - a[3], a[1] - b[3])
    return (dx * dx + dy * dy) ** 0.5


def _inter(a, b):
    return max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))


def heading_slots(outer, cw, ch, bounds):
    """Every place a heading pill may go round a box -> [(side, x, y)], inside `bounds`
    (6 px in) and never on the box: beside it on the same row first, then above / below at
    growing gaps, sliding along the box and then across the screen."""
    x0, y0, x1, y1 = outer
    bx0, by0, bx1, by1 = bounds
    mid = (y0 + y1 - ch) // 2
    out = []
    for g in (HEAD_CLEAR + 6, HEAD_CLEAR + 18, HEAD_CLEAR + 34):
        for vy in (mid, y0, y1 - ch, mid - ch // 2 - 6, mid + ch // 2 + 6):
            out += [("right", x1 + g, vy), ("left", x0 - g - cw, vy)]
    xs = [x0, x1 - cw, (x0 + x1 - cw) // 2]
    xs += list(range(int(bx0 + 6), int(bx1 - cw - 6) + 1, 24))
    for g in (HEAD_CLEAR + 4, HEAD_CLEAR + 16, 30, 44, 60, 80, 104, 132, 164, 200):
        for cx in xs:
            out += [("above", cx, y0 - g - ch), ("below", cx, y1 + g)]
    keep, seen = [], set()
    for side, cx, cy in out:
        cx = int(max(bx0 + 6, min(cx, bx1 - cw - 6)))
        cy = int(cy)
        if cy < by0 + 6 or cy + ch > by1 - 6 or (side, cx, cy) in seen:
            continue
        if _rect_gap((cx, cy, cx + cw, cy + ch), outer) < HEAD_CLEAR:
            continue                                  # never on (or touching) its own box
        seen.add((side, cx, cy))
        keep.append((side, cx, cy))
    return keep


def place_heading(outer, cw, ch, bounds, obstacles, own=(), prefer=None, frame=None):
    """Where the heading pill goes when the frame's TEXT is known (24 Sep, QA against the approved edit: a pill
    covering the 7 of '70%' made it read '0%').

    outer      the drawn box's outer edge (x0, y0, x1, y1)
    obstacles  OCR text boxes (x, y, w, h[, weight]) on the frame(s) the marking is shown on;
               weight = how bad covering it is when something must be covered (default 1)
    own        the target's own text boxes - the pill never covers these, even as a last resort
    prefer     'right' | 'left' | 'above' | 'below': that side first (a spec's "heading_at")
    -> ((x, y), overlap) - never on the target's own text, and in this order:
      1. the NEAREST slot that overlaps no text, nor the TEXT_AIR round it;
      2. else one that only grazes that air (or shades a word with its drop shadow): least
         grazed + nearest (PER_PX: each px of distance costs as much as 1/300 of a word);
      3. else the one hiding the least text - each word box weighted by the share the pill
         covers, so half a long label beats all of '87%' - traded against distance the same
         way, so a pill does not jump 200 px away to hide 1 % less of a word.
    overlap = the weighted share incl. air and shadow (0 = clear)."""
    slots = heading_slots(outer, cw, ch, bounds)
    obs = [(o[0] - TEXT_AIR, o[1] - TEXT_AIR, o[0] + o[2] + TEXT_AIR, o[1] + o[3] + TEXT_AIR,
            o[4] if len(o) > 4 else 1.0) for o in obstacles]
    mine = [(x - TEXT_AIR, y - TEXT_AIR, x + w + TEXT_AIR, y + h + TEXT_AIR) for x, y, w, h in own]
    best = None
    for side, cx, cy in slots:
        r = (cx, cy, cx + cw, cy + ch + 4)            # + the pill's drop shadow
        if any(_inter(r, m) for m in mine):
            continue
        # how much TEXT it hides: each word box counts by the share of it covered, so half a
        # long label is better than all of '87%'
        hit = round(sum(o[4] * _inter(r, o) / max(1, (o[2] - o[0]) * (o[3] - o[1])) for o in obs), 3)
        pill = (cx, cy, cx + cw, cy + ch)             # ... and how much it hides of the words themselves
        raw = round(sum(o[4] * _inter(pill, (o[0] + TEXT_AIR, o[1] + TEXT_AIR, o[2] - TEXT_AIR, o[3] - TEXT_AIR))
                        / max(1, (o[2] - o[0] - 2 * TEXT_AIR) * (o[3] - o[1] - 2 * TEXT_AIR)) for o in obs), 3) \
            if hit else 0.0
        # nearest = closest to the box, and lined up with it (a pill slid far along a row
        # stops reading as this box's label)
        span = max(0, outer[0] - r[2], r[0] - outer[2]) if side in ("above", "below") else \
            max(0, outer[1] - r[3], r[1] - outer[3])
        dist = _rect_gap(r, outer) + 0.35 * span
        busy = _busyness(frame, cx, cy, cw, ch) if frame is not None and hit == 0 else 0
        pref = 0 if (prefer is None or side == prefer) else 1
        key = ((pref, 0, round(dist / 4), busy) if hit == 0 else
               (pref, 1, round(hit + dist * PER_PX, 3)) if raw == 0 else
               (pref, 2, round(raw + 0.25 * hit + dist * PER_PX, 3)))
        if best is None or key < best[0]:
            best = (key, (cx, cy), hit)
    if best is None:
        return None, None
    return best[1], best[2]


def render_step_mobile(canvas, box, heading, frame=None, colour=None, bounds=None, pad=12, radius=18,
                       obstacles=None, own=(), prefer=None, chip_at=None, want_chip=False):
    """The mobile call-out: the desktop box-plus-heading, sized for a phone screen.

    Requirement (23 Sep): the markings should look more attractive and carry a small
    heading again, as earlier versions did. So the heading chip is back, but it names the ACTION
    ("Tap Save") instead of repeating the button's own words, which is why it was
    dropped. Thicker stroke, rounder corners, a soft blurred glow and a pill heading with
    a light shadow. `bounds` keeps the heading inside the phone screen.
    `pad`/`radius` come from sa_appbuild.outline_for when the box is a whole element (24 Sep:
    the outline hugs the tile/button at an even gap, corners concentric with its own).

    Heading placement (24 Sep, QA against the approved edit: pills hid a percentage, a stage name and a price):
      obstacles=[(x, y, w, h)]  the frame's OCR text boxes -> place_heading: nearest slot with
                                zero text overlap, else least overlap, never on `own` text
      prefer='below'|...        that side first (spec "heading_at"); works with or without obstacles
      chip_at=(x, y)            the pill's top-left, as given (spec "chip_at"), kept inside bounds
      want_chip=True            -> (img, [x, y, w, h] of the pill or None)
    With none of these the placement is exactly the old one (emptiest nearby slot)."""
    from PIL import ImageFilter
    W, H = canvas
    line, glow = colour if colour else (BOX_BLUE, BOX_SOFT)
    PADm, Rm, Sm = pad, radius, 6
    x, y, w, h = box
    x0, y0, x1, y1 = x - PADm, y - PADm, x + w + PADm, y + h + PADm
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    halo = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(halo).rounded_rectangle([x0 - 4, y0 - 4, x1 + 4, y1 + 4], radius=Rm + 4,
                                           outline=line[:3] + (170,), width=Sm + 6)
    img = Image.alpha_composite(img, halo.filter(ImageFilter.GaussianBlur(7)))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([x0, y0, x1, y1], radius=Rm, outline=line, width=Sm)

    chip = None
    if heading:
        f = _font(HEAD_FONT)
        ch, cpad = HEAD_H, HEAD_PAD
        cw = int(d.textlength(heading, font=f)) + cpad * 2
        bx0, by0, bx1, by1 = bounds if bounds else (8, 8, W - 8, H - 8)
        placed = None
        if chip_at is not None:
            placed = (int(max(bx0 + 6, min(chip_at[0], bx1 - cw - 6))),
                      int(max(by0 + 6, min(chip_at[1], by1 - ch - 6))))
        elif obstacles is not None or prefer is not None:
            placed, _hit = place_heading((x0, y0, x1, y1), cw, ch, (bx0, by0, bx1, by1),
                                         obstacles or [], own, prefer,
                                         frame if obstacles is None else None)
        if placed is None:
            placed = _old_heading_slot(x0, y0, x1, y1, cw, ch, (bx0, by0, bx1, by1), frame)
        cx, cy = placed
        chip = [int(cx), int(cy), int(cw), int(ch)]
        sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(sh).rounded_rectangle([cx, cy + 4, cx + cw, cy + ch + 4], radius=ch // 2,
                                             fill=(0, 0, 0, 95))
        img = Image.alpha_composite(img, sh.filter(ImageFilter.GaussianBlur(6)))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([cx, cy, cx + cw, cy + ch], radius=ch // 2, fill=line)
        lum = (0.2126 * line[0] + 0.7152 * line[1] + 0.0722 * line[2]) / 255
        ink = (6, 32, 25, 255) if lum > 0.55 else (255, 255, 255, 255)
        d.text((cx + cpad, cy + ch / 2 + 1), heading, font=f, fill=ink, anchor="lm")
    return (img, chip) if want_chip else img


def _old_heading_slot(x0, y0, x1, y1, cw, ch, bounds, frame):
    """The pre-24 Sep placement (no text known): the emptiest nearby slot, by edge density."""
    bx0, by0, bx1, by1 = bounds
    # beside the box first: in a list the empty space is on the same row, and above
    # or below lands on the neighbouring row (it hid a job code on the next row, 23 Sep)
    mid = (y0 + y1 - ch) // 2
    cands = [(x1 + 16, mid), (x0 - 16 - cw, mid)]
    for g in (14, 40, 72):
        cands += [(x0, y0 - g - ch), (x1 - cw, y0 - g - ch), (x0, y1 + g),
                  (x1 - cw, y1 + g), ((x0 + x1 - cw) // 2, y0 - g - ch),
                  ((x0 + x1 - cw) // 2, y1 + g)]
    best, score = None, None
    for k, (cx, cy) in enumerate(cands):
        if k < 2 and (cx < bx0 + 6 or cx + cw > bx1 - 6):
            continue                              # a side slot that doesn't fit is skipped, not clamped onto the box
        cx = max(bx0 + 6, min(cx, bx1 - cw - 6))
        if cy < by0 + 6 or cy + ch > by1 - 6:
            continue
        if not (cx + cw < x0 or cx > x1 or cy + ch < y0 or cy > y1):
            continue                              # never on top of the thing it labels
        sc = _busyness(frame, cx, cy, cw, ch) if frame is not None else 0
        if score is None or sc < score:
            best, score = (int(cx), int(cy)), sc
    if best is None:
        best = (int(max(bx0 + 6, min(x0, bx1 - cw - 6))), int(max(by0 + 6, y0 - 14 - ch)))
    return best


MIN_DUR = 1.3        # below this a call-out is unreadable; better to drop it

# The editor's number, not the tool's. Measured 11 Aug across nine finished videos
# (Tools/sa_learncurve.py): the first drafts used 3.1s holds, the editor settled at a 2.10s median in
# 9 of 9 — every single video. A default that gets corrected every time is not taste,
# it is a wrong default. Anything authoring a call-out uses this unless told otherwise.
HOLD = 2.1
# He also inserts freezes wherever the screen will not hold still under a marking.
# Building without them hands him work.
#
# TWO MEASUREMENTS, both real — the later one supersedes because it is the whole corpus:
#   2.2s  median of 24 freezes across 9 videos — the earlier subset, measured 11 Aug while
#         the series was still in progress. Correct for what it saw, but partial.
#   3.0s  median of 120 freezes across every finished module — the full final corpus,
#         audited by an AI coding agent. This is the baseline.
# Framing note: this is not a preference overriding a measurement,
# it is a bigger sample superseding a smaller one. Say it that way.
HIS_FREEZE = 3.0
# Dense screens need longer — a screen carrying many fields or values wants 6s+ so the
# learner can actually read it before the picture moves.
DENSE_FREEZE = 6.0


def space_windows(steps):
    """Stop call-out windows overlapping — two freezes can't share a moment.

    Each window runs t-FADE .. t+dur+FADE. When they overlap, the later freeze
    overrides the earlier one mid-window and the picture visibly jumps (caught by
    --check as "background moves", 6 Aug). Trim the earlier one to fit; if it
    can't fit, say so rather than shipping a jump.
    """
    steps = sorted(steps, key=lambda s: s["t"])
    for a, b in zip(steps, steps[1:]):
        room = (b["t"] - FADE) - (a["t"] + FADE)
        if a["dur"] > room:
            if room < MIN_DUR:
                print(f"  ! '{a.get('label','')}' @{a['t']}s and '{b.get('label','')}' "
                      f"@{b['t']}s are too close ({room:.1f}s) — move one apart")
            a["dur"] = max(MIN_DUR, room)
    return steps


def probe_canvas(video):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "json", video],
        capture_output=True, text=True, check=True).stdout
    s = json.loads(out)["streams"][0]
    return int(s["width"]), int(s["height"])


def build(spec_path, mode):
    spec = json.load(open(spec_path))
    video = spec["video"]
    canvas = tuple(spec.get("canvas") or probe_canvas(video))
    steps = space_windows(spec["steps"])
    if not steps:
        raise SystemExit("no steps in spec")

    tmp = tempfile.mkdtemp(prefix="stepmark_")
    cap = cv2.VideoCapture(video)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    freeze = mode == "burn" and not spec.get("no_freeze")
    inputs, filters, labels = [], [], []
    chips = []
    for i, st in enumerate(steps):
        png = os.path.join(tmp, f"s{i}.png")
        # the call-out's reference frame; with --burn it is ALSO shown frozen for the
        # whole window, so the box can never detach from a scrolling UI (Saad, 5 Aug)
        cap.set(cv2.CAP_PROP_POS_FRAMES, int((st["t"] + st["dur"] / 2) * fps))
        ok, frame = cap.read()
        img, chip = render_step(canvas, st["box"], st.get("label", ""),
                                frame if ok else None, want_chip=True)
        img.save(png)
        chips.append(chip)
        inputs += ["-loop", "1", "-t", str(st["dur"] + FADE * 2), "-i", png]
        if freeze and ok:
            fpng = os.path.join(tmp, f"f{i}.png")
            cv2.imwrite(fpng, frame)
            inputs += ["-loop", "1", "-t", str(st["dur"] + FADE * 2), "-i", fpng]

    base = pathlib.Path(video)
    if mode == "overlay":
        # transparent base -> ProRes 4444 with alpha, for an overlay track
        dur = float(subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", video], capture_output=True, text=True).stdout.strip())
        cmd = ["ffmpeg", "-y", "-v", "error", "-stats",
               "-f", "lavfi", "-t", str(dur),
               "-i", f"color=c=black@0.0:s={canvas[0]}x{canvas[1]}:r=60,format=rgba"]
        out = str(base.with_name(base.stem + "_STEPMARKS.mov"))
        codec = ["-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le"]
    else:
        cmd = ["ffmpeg", "-y", "-v", "error", "-stats", "-i", video]
        out = str(base.with_name(base.stem + "_MARKED.mp4"))
        codec = ["-c:v", "libx264", "-preset", "medium", "-crf", "18",
                 "-pix_fmt", "yuv420p", "-c:a", "copy"]

    cmd += inputs
    prev = "[0:v]"
    per = 2 if freeze else 1          # inputs per step: call-out png (+ freeze frame)
    tag = 0
    for i, st in enumerate(steps):
        t0 = st["t"]
        t1 = t0 + st["dur"]
        ws, we = max(0, t0 - FADE), t1 + FADE
        idx = 1 + i * per
        if freeze:
            # the reference frame held for the whole window: the UI cannot move
            # under the box, and the scroll it hides is skipped, not shown
            filters.append(f"[{idx+1}:v]setpts=PTS-STARTPTS+{ws}/TB[z{i}]")
            filters.append(f"{prev}[z{i}]overlay=0:0:enable='between(t,{ws},{we})'[w{i}]")
            prev = f"[w{i}]"
        a = (f"[{idx}:v]format=rgba,fade=t=in:st=0:d={FADE}:alpha=1,"
             f"fade=t=out:st={st['dur']+FADE}:d={FADE}:alpha=1,"
             f"setpts=PTS-STARTPTS+{ws}/TB[m{i}]")
        filters.append(a)
        nxt = f"[v{i}]" if i < len(steps) - 1 else "[vout]"
        filters.append(f"{prev}[m{i}]overlay=0:0:enable='between(t,{ws},{we})'{nxt}")
        prev = f"[v{i}]"

    cmd += ["-filter_complex", ";".join(filters), "-map", "[vout]"]
    if mode != "overlay":
        cmd += ["-map", "0:a?"]
    cap.release()
    cmd += codec + [out]
    subprocess.run(cmd, check=True)
    side = {"video": out, "freeze": freeze,
            "steps": [dict(st, chip=chips[i]) for i, st in enumerate(steps)]}
    json.dump(side, open(str(base.with_name(base.stem + "_MARKED.chips.json")), "w"), indent=1)
    print(f"\n-> {out}  ({len(steps)} call-outs{', frozen windows' if freeze else ''})")
    return out


def build_layers(spec_path):
    """One FULL-CANVAS transparent PNG per call-out, plus a manifest.

    Full canvas on purpose (Saad, 6 Aug): dropped into CapCut at scale 1 /
    offset 0 the box lands exactly where it was authored — no coordinate
    convention to get wrong — and he can still drag, resize, retime or delete
    each call-out independently, which a burned-in render never allowed.
    """
    spec = json.load(open(spec_path))
    video = spec["video"]
    canvas = tuple(spec.get("canvas") or probe_canvas(video))
    steps = space_windows(spec["steps"])
    base = pathlib.Path(video)
    outdir = base.with_name(base.stem + "_LAYERS")
    outdir.mkdir(exist_ok=True)
    cap = cv2.VideoCapture(video)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    rows = []
    for i, st in enumerate(steps, 1):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int((st["t"] + st["dur"] / 2) * fps))
        ok, frame = cap.read()
        img, chip = render_step(canvas, st["box"], st.get("label", ""),
                               frame if ok else None, want_chip=True)
        slug = "".join(c if c.isalnum() else "_" for c in st.get("label", f"step{i}"))[:44]
        png = outdir / f"{i:02d}_{slug}.png"
        img.save(png)
        # absolute: CapCut stores the path verbatim and resolves it from nowhere useful
        rows.append({"file": os.path.abspath(png), "start": round(max(0.0, st["t"] - FADE), 3),
                     "duration": round(st["dur"] + FADE * 2, 3),
                     "label": st.get("label", ""), "box": st["box"], "chip": chip})
    cap.release()
    manifest = outdir / "_layers.json"
    json.dump({"video": os.path.abspath(video), "canvas": list(canvas), "layers": rows},
              open(manifest, "w"), indent=1)
    print(f"-> {outdir}  ({len(rows)} full-canvas call-out layers)")
    return manifest


def build_clips(spec_path):
    """One short transparent MOV per call-out.

    Beats a single long overlay: the editor can drag, trim or delete any one call-out
    in the timeline without razoring anything or disturbing the others.
    """
    spec = json.load(open(spec_path))
    video = spec["video"]
    canvas = tuple(spec.get("canvas") or probe_canvas(video))
    base = pathlib.Path(video)
    outdir = base.with_name(base.stem + "_CALLOUTS")
    outdir.mkdir(exist_ok=True)
    cap = cv2.VideoCapture(video)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    tmp = tempfile.mkdtemp(prefix="stepclip_")
    made = []
    for i, st in enumerate(spec["steps"], 1):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int((st["t"] + st["dur"] / 2) * fps))
        ok, frame = cap.read()
        png = os.path.join(tmp, f"c{i}.png")
        render_step(canvas, st["box"], st.get("label", ""), frame if ok else None).save(png)
        slug = "".join(ch if ch.isalnum() else "_" for ch in st.get("label", f"step{i}"))[:40]
        out = str(outdir / f"{i:02d}_{slug}.mov")
        total = st["dur"] + FADE * 2
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-loop", "1", "-t", str(total), "-i", png,
             "-filter_complex",
             f"[0:v]format=rgba,fade=t=in:st=0:d={FADE}:alpha=1,"
             f"fade=t=out:st={st['dur']+FADE}:d={FADE}:alpha=1[v]",
             "-map", "[v]", "-r", "60",
             "-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le", out],
            check=True)
        made.append((out, round(max(0.0, st["t"] - FADE), 2), round(total, 2), st.get("label", "")))
        print(f"  {i:02d}  {st['t']:6.1f}s  {st.get('label','')}")
    cap.release()
    json.dump([{"file": f, "start": s0, "dur": d, "label": l} for f, s0, d, l in made],
              open(outdir / "_clips.json", "w"), indent=1)
    print(f"\n-> {outdir}  ({len(made)} independent call-out clips)")
    return made


def check(chips_path):
    """Frame-by-frame QA on a burned render (requirement, 5 Aug: verify the WHOLE window).

    Per call-out: background must be STATIC across the window (the freeze), and the
    chip must sit on clear space in the shown frame. Writes a start|end contact
    sheet next to the video and prints one OK/FLAG line per call-out.
    """
    side = json.load(open(chips_path))
    video = side["video"]
    cap = cv2.VideoCapture(video)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    sheets = []
    flags = 0
    for i, st in enumerate(side["steps"]):
        ws = max(0, st["t"] - FADE) + 0.15
        we = st["t"] + st["dur"] + FADE - 0.15
        frames = []
        for at in (ws, we):
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(at * fps))
            ok, f = cap.read()
            frames.append(f if ok else None)
        a, b = frames
        msgs = []
        if a is None or b is None:
            msgs.append("frame read failed")
        else:
            diff = cv2.absdiff(a, b)
            # ignore the call-out's own fade region: mask box+chip (+glow margin)
            for r in [st["box"]] + ([st["chip"]] if st.get("chip") else []):
                x, y, w, h = r
                x0, y0 = max(0, x - PAD - 8), max(0, y - PAD - 8)
                diff[y0:y + h + PAD + 8, x0:x + w + PAD + 8] = 0
            moved = float((diff.max(axis=2) > 24).mean())
            if moved > 0.002:
                msgs.append(f"background moves ({moved:.1%} px)")
        ok_line = "OK  " if not msgs else "FLAG"
        if msgs:
            flags += 1
        print(f"  {ok_line} {i:02d} @{st['t']:6.1f}s  {st.get('label','')}"
              + (f"  <- {'; '.join(msgs)}" if msgs else ""))
        if a is not None and b is not None:
            h = 300
            sc = h / a.shape[0]
            pair = np.hstack([cv2.resize(a, None, fx=sc, fy=sc),
                              cv2.resize(b, None, fx=sc, fy=sc)])
            sheets.append(pair)
    cap.release()
    if sheets:
        out = str(pathlib.Path(video).with_name(pathlib.Path(video).stem + "_QA.png"))
        cv2.imwrite(out, np.vstack(sheets))
        print(f"\n-> {out}  (start|end of every window)  {flags} flagged")
    return flags


def _test():
    img = render_step((1920, 1020), [1200, 180, 120, 32], "Click Save")
    assert img.size == (1920, 1020) and img.mode == "RGBA"
    assert img.getpixel((1200, 180))[3] > 0 or img.getpixel((1194, 174))[3] > 0, "box not drawn"
    # label chip must stay on screen even for a far-right element
    img2 = render_step((1920, 1020), [1890, 20, 20, 20], "A very long label indeed")
    assert img2.size == (1920, 1020)
    # overlapping freeze windows are the one defect --check can't distinguish from
    # a genuinely moving UI, so they must be impossible by construction
    s = space_windows([{"t": 6.2, "dur": 2.6, "label": "b"}, {"t": 3.2, "dur": 2.6, "label": "a"}])
    assert [x["label"] for x in s] == ["a", "b"], "steps must be sorted by time"
    assert s[0]["t"] + s[0]["dur"] + FADE <= s[1]["t"] - FADE + 1e-9, "windows still overlap"
    far = space_windows([{"t": 0, "dur": 3.0}, {"t": 30, "dur": 3.0}])
    assert far[0]["dur"] == 3.0, "well-spaced call-outs must not be trimmed"
    _test_heading()
    print("sa_stepmark self-check: ok (box drawn, chip clamped, windows spaced, "
          "heading never on text, heading_at / chip_at, old placement unchanged)")


def _test_heading():
    """24 Sep, QA against the approved edit: the pill covered the 7 of '70%' ('Chance of closing')."""
    cv = (1080, 1920)
    bounds = (180, 150, 900, 1400)
    # the old call (no text given) is byte-for-byte the old picture
    frame = np.full((1920, 1080, 3), 246, np.uint8)
    a = render_step_mobile(cv, (300, 700, 200, 30), "Chance of closing", frame=frame, bounds=bounds)
    b, chip = render_step_mobile(cv, (300, 700, 200, 30), "Chance of closing", frame=frame, bounds=bounds,
                                 want_chip=True)
    assert a.tobytes() == b.tobytes() and chip is not None
    old = _old_heading_slot(288, 688, 512, 742, chip[2], chip[3], bounds, frame)
    assert tuple(chip[:2]) == old, "no obstacles, no preference -> the old slot"
    # the Win probability row: label boxed, '70%' at the right end of the same row, the
    # 'Stage' row above and the 'Opened' row below. The right-hand slot would cover 70%.
    box = (300, 700, 200, 30)                       # 'Win probability' (the words)
    texts = [(300, 700, 200, 30), (748, 702, 50, 26),                   # own words, '70%'
             (300, 640, 90, 26), (620, 640, 170, 26),                   # Stage | Quotation
             (300, 770, 90, 26)]                                        # Opened
    _img, chip = render_step_mobile(cv, box, "Chance of closing", bounds=bounds, pad=12,
                                    obstacles=texts, own=[texts[0]], want_chip=True)
    cr = (chip[0], chip[1], chip[0] + chip[2], chip[1] + chip[3])
    assert all(_inter(cr, (x - 1, y - 1, x + w + 1, y + h + 1)) == 0 for x, y, w, h in texts), chip
    assert _rect_gap(cr, (288, 688, 512, 742)) >= HEAD_CLEAR, "never on its own box"
    assert bounds[0] + 6 <= cr[0] and cr[2] <= bounds[2] - 6 and bounds[1] + 6 <= cr[1] and cr[3] <= bounds[3] - 6
    # the same case the old way puts the pill on the row's value (the fault)
    _i, oldchip = render_step_mobile(cv, box, "Chance of closing", bounds=bounds, pad=12, want_chip=True)
    oc = (oldchip[0], oldchip[1], oldchip[0] + oldchip[2], oldchip[1] + oldchip[3])
    assert _inter(oc, (748, 702, 798, 728)) > 0, "(old placement covered '70%')"
    # nothing clear anywhere: least overlap, but never the target's own text
    wall = [(bounds[0], y, bounds[2] - bounds[0], 20) for y in range(150, 1400, 30)]
    own = [(300, 670, 200, 20), (300, 760, 200, 20)]
    (cx, cy), hit = place_heading((288, 688, 512, 742), 300, 56, bounds, wall + own, own)
    assert hit > 0 and all(_inter((cx, cy, cx + 300, cy + 60), (x - 3, y - 3, x + w + 3, y + h + 3)) == 0
                           for x, y, w, h in own)
    # nothing fully clear: a pill that only grazes the air round a word beats one that covers
    # part of a word, however small (a real case: a heading hid 3 px of a short word)
    bnd, outer = (290, 606, 520, 906), (300, 700, 500, 742)
    tall = (296, 612, 220, 20, 1.0)                 # above: a long line the top slots would clip
    said = (300, 818, 40, 14, 4.0)                  # below: a short spoken word, 6 px under the pill
    (cx, cy), hit = place_heading(outer, 200, 56, bnd, [tall, said])
    assert hit > 0 and cy > outer[3] and all(_inter((cx, cy, cx + 200, cy + 56), (x, y, x + w, y + h)) == 0
                                              for x, y, w, h, _w in (tall, said)), (cx, cy, hit)
    # heading_at: the named side, nearest clear slot on it
    _i, c2 = render_step_mobile(cv, box, "Chance of closing", bounds=bounds, pad=12, obstacles=texts,
                                own=[texts[0]], prefer="above", want_chip=True)
    assert c2[1] + c2[3] <= 688 - HEAD_CLEAR, c2
    _i, c3 = render_step_mobile(cv, box, "Chance of closing", bounds=bounds, pad=12, prefer="below",
                                want_chip=True)
    assert c3[1] >= 742 + HEAD_CLEAR, c3
    # chip_at: exactly there (kept inside the screen)
    _i, c4 = render_step_mobile(cv, box, "Chance of closing", bounds=bounds, chip_at=(400, 900), want_chip=True)
    assert c4[:2] == [400, 900]
    _i, c5 = render_step_mobile(cv, box, "Chance of closing", bounds=bounds, chip_at=(2000, 900), want_chip=True)
    assert c5[0] + c5[2] <= bounds[2] - 6


if __name__ == "__main__":
    if "--test" in sys.argv:
        _test()
        sys.exit()
    ap = argparse.ArgumentParser()
    ap.add_argument("spec")
    ap.add_argument("--overlay", action="store_true", help="transparent MOV for an overlay track")
    ap.add_argument("--burn", action="store_true", help="flattened MP4 preview")
    ap.add_argument("--clips", action="store_true",
                    help="one short MOV per call-out, so each stays independently draggable")
    ap.add_argument("--check", action="store_true",
                    help="QA a burned render: pass the _MARKED.chips.json sidecar as spec")
    ap.add_argument("--layers", action="store_true",
                    help="full-canvas PNG per call-out + manifest, for a CapCut draft")
    a = ap.parse_args()
    if a.check:
        check(a.spec)
    elif a.layers:
        build_layers(a.spec)
    elif a.clips:
        build_clips(a.spec)
    else:
        build(a.spec, "overlay" if a.overlay else "burn")
