#!/usr/bin/env python3
"""sa_markrules — Saad's editing rules, measured from his own cuts, in one place.

Every screen-recorded training build imports this instead of re-deriving the numbers.
Sources: three of his own finished cuts, Aug-Sep (on one module he cut my build by
almost a quarter). The detail and the evidence live in a private editing-technique note.

    import sa_markrules as R
    R.split_cues(line)                       # captions his way
    R.fit_box("button", (x,y,w,h))           # box margins per control type
    R.chip_rect(box, label_w, is_blank)      # chip beside the control, not over content
    R.pace(rows, voice_spans)                # row targets under the 8 Sep pacing law

Run it directly for the self-check:  python3 sa_markrules.py   (numpy + Pillow)
"""

# ---- pacing (8 Sep, measured on his ripple deletes) ------------------------------------------
GAP_SETTLED = 0.5     # after a line, screen already settled: he leaves 0.3-0.6s
GAP_ACTION = 2.3      # an action between two lines: 1-3.5s, click + state change only
GAP_RESULT = 4.5      # a result moment (toast, success modal) is held
SILENT_KEEP = 2.5     # silent rows <= this he leaves alone; longer ones get cut
VOICE_IN = 0.2        # voice starts this far into its row
VOICE_TAIL = 0.3      # margin after the words before the row can end

# ---- marking geometry (px on the 1920x1140 canvas) -------------------------------------------
MARGIN = {"button": 12, "row": 4, "field": 8, "login": 0, "tile": 8, "text": 10}
CHIP_GAP = 22         # blank space between chip and box
CHIP_H = 46

# a marking must not outlive the screen it describes (Saad, 9 Sep)
SCREEN_DIFF = 0.006        # fraction of pixels that must change to count as a new screen.
                           # 0.055, then 0.018, were both too slack. Measured 9 Sep on the review-cut
                           # verification: a dropdown opening over the form changes 1.5-2.3% of
                           # the frame, so markings sat across a menu open->close and the viewer
                           # saw the box beside the WRONG list. A cursor move is ~0.05% and a
                           # hover tint is under the 18-grey-level gate, so 0.6% is still noise-free.
SCREEN_STEP = 0.1          # sampling step in seconds


def pace(rows, spans):
    """rows = [(src_a, src_b, line_idx|None, kind)], spans = voice length per line.

    kind: "line" (paced to the words), "action" (click -> state change), "result" (held),
    "demo" (silent footage that illustrates the line playing under it, kept whole).
    Returns (targets, rowstart, starts, end) — the same shape the module build scripts expect.

    The law: a line row lasts its voice + a breath; a silent row is capped at what he keeps.
    My old rule (max(voice, source) + pad) is what left the frozen tails he cut.
    """
    targets, rowstart, starts, t = [], [], {}, 0.0
    for a, b, li, kind in rows:
        src = b - a
        if kind == "still":                        # closing freeze: silence, sign-off, tail
            tg = closing_still(spans[li])[0]
        elif li is not None:
            tg = spans[li] + VOICE_TAIL + GAP_SETTLED
        elif kind == "result":
            tg = min(src, GAP_RESULT)
        elif kind == "demo":
            tg = src
        else:
            tg = min(src, GAP_ACTION if src > SILENT_KEEP else src)
        tg = round(tg, 2)
        targets.append(tg); rowstart.append(round(t, 2))
        if li is not None:
            starts[li] = round(t + (STILL_LEAD if kind == "still" else VOICE_IN), 2)
        t = round(t + tg, 2)
    return targets, rowstart, starts, round(t, 2)


def fit_box(kind, bbox, container=None):
    """Box around a control. button = air; row = the card/modal container edge, never the
    table width and never across the sidebar; login = the whole list-item rectangle."""
    x, y, w, h = bbox
    m = MARGIN.get(kind, 10)
    if kind in ("row", "login") and container:
        cx, cy, cw, ch = container
        return (cx + m, y - m, cw - 2 * m, h + 2 * m)
    return (x - m, y - m, w + 2 * m, h + 2 * m)


def chip_rect(box, label_w, is_blank, W=1920, H=1140, chip_h=CHIP_H, gap=CHIP_GAP, cost=None):
    """Chip beside the control, level with it, over empty space.

    His fallback order (8 Sep, 4 instances): above-left, then RIGHT of the box level with it,
    then LEFT level with it, then below with the left edges aligned. is_blank(rect) -> bool
    decides whether a candidate covers content; the first blank candidate wins, so the chip
    stays near its box instead of flying to the emptiest corner.
    """
    bx, by, bw, bh = box
    cy_level = int(by + bh / 2 - chip_h / 2)
    cands = []
    for g in (gap, gap + 44, gap + 110):         # widen the gap before giving up on a side
        cands += [
            (bx, by - g - chip_h),               # above, left edges aligned (default)
            (bx + bw + g, cy_level),             # right, level
            (bx - g - label_w, cy_level),        # left, level
            (bx, by + bh + g),                   # below, left edges aligned
            (bx + bw - label_w, by - g - chip_h),
        ]
        # 9 Sep: the four fixed corners were not enough — on dense data-entry forms every one of them
        # landed inside a neighbouring input and blanked its value (an ID-number chip inside the
        # Phone field, End time chip inside Start time). Slide along the box's own top and bottom
        # edges before widening the gap, so the chip stays attached to its box but finds a gap.
        for dx in (bw // 2, bw + 40, -label_w - 40, bw + 160, -label_w - 160):
            cands += [(bx + dx, by - g - chip_h), (bx + dx, by + bh + g)]
        # 9 Sep round 3: on a dense form even those slots are all inside some other field, so the
        # chip kept landing on a neighbour's value ("End time" across the start time). Sweep the
        # rows above and below the box, and the columns beside it, before settling for least-bad.
        for dx in range(-520, 561, 60):
            cands += [(bx + dx, by - g - chip_h), (bx + dx, by + bh + g)]
        for dy in range(-260, 261, 52):
            cands += [(bx + bw + g, cy_level + dy), (bx - g - label_w, cy_level + dy)]
    fits = [(cx, cy) for cx, cy in cands
            if cx >= 8 and cy >= 6 and cx + label_w <= W - 8 and cy + chip_h <= H - 6]
    for cx, cy in fits:
        if is_blank((cx, cy, label_w, chip_h)):
            return (cx, cy)
    # Nothing is clean. Falling back to the FIRST candidate is how "End time" ended up printed
    # across the Start time value on a dense form (9 Sep round 2). Take the least-bad instead:
    # `cost` returns how much readable content a rectangle would bury.
    if cost and fits:
        return min(fits, key=lambda c: cost((c[0], c[1], label_w, chip_h)))
    cx, cy = fits[0] if fits else cands[0]
    return (max(8, min(cx, W - 8 - label_w)), max(6, cy))


def split_cues(text, target=46, hard=54):
    """Captions the way he re-flowed mine (8 Sep).

    46 chars is the target for STARTING a new cue, not a cap: overshoot to `hard` to keep a
    phrase whole. Break at punctuation (. : ? ! > ,) when it lands near the greedy cut; never
    end a cue on the opening words of a new sentence; never end on a bare "and"/"or"; never
    tear a capitalised name or UI string ("New Request Needs Approval.").
    """
    words = text.split()
    if not words: return []
    def capped(w): return w[:1].isupper()
    out, cur = [], []
    def flush():
        if cur: out.append(" ".join(cur)); cur.clear()
    i = 0
    while i < len(words):
        w = words[i]
        trial = len(" ".join(cur + [w]))
        if cur and trial > hard:
            # too long: back off to the last punctuation, else break here
            cut = next((k for k in range(len(cur) - 1, 0, -1)
                        if cur[k].endswith((".", ":", "?", "!", ",")) and len(" ".join(cur[:k + 1])) >= target - 12), None)
            if cut is not None:
                tail = cur[cut + 1:]; del cur[cut + 1:]; flush(); cur.extend(tail)
            else:
                flush()
            continue
        cur.append(w); i += 1
        line = " ".join(cur)
        if len(line) < target:
            continue
        # a break is allowed here — but not through a capitalised run, and not on a bare and/or
        nxt = words[i] if i < len(words) else None
        if cur[-1].endswith(("and", "or")) and not cur[-1].endswith((",", ".")):
            continue
        if nxt and capped(cur[-1].strip(".,:;")) and capped(nxt) and not cur[-1].endswith((".", ":", "!", "?")):
            continue                                   # inside a capitalised UI string
        if line.endswith((".", ":", "!", "?")):
            flush(); continue
        if nxt and words[i - 1].endswith(","):
            flush(); continue
        if len(line) >= hard - 4:
            flush()
    flush()
    # a cue must not be left holding only the first word or two of a new sentence
    for k in range(len(out) - 1):
        if out[k].endswith((".", "!", "?")):
            continue
        if len(out[k]) + len(out[k + 1]) + 1 <= hard and len(out[k + 1].split()) <= 2:
            out[k] = f"{out[k]} {out[k + 1]}"; out[k + 1] = ""
    return [c for c in out if c]


# ---- ending recipe (8 Sep) --------------------------------------------------------------------
STILL_LEAD = 2.2      # silent still before the sign-off
STILL_TAIL = 0.6      # after the sign-off, before the outro


def closing_still(signoff_len):
    """Cut at the last click; the still IS the result. Returns (still_len, signoff_start)."""
    return round(STILL_LEAD + signoff_len + STILL_TAIL, 2), STILL_LEAD


def _self_test():
    # pacing: a line row is its voice plus a breath, not the source length
    tg, rs, st, end = pace([(0, 12.0, 0, "line"), (12.0, 20.0, None, "action"), (20.0, 30.0, None, "result")], [3.0])
    assert tg[0] == round(3.0 + VOICE_TAIL + GAP_SETTLED, 2), tg
    assert tg[1] == GAP_ACTION and tg[2] == GAP_RESULT, tg
    assert st[0] == VOICE_IN and end == round(sum(tg), 2)
    # boxes
    assert fit_box("button", (100, 100, 80, 30)) == (88, 88, 104, 54)
    assert fit_box("row", (140, 400, 1740, 50), container=(256, 380, 1615, 90)) == (260, 396, 1607, 58)
    # chip: default above; when above is busy it goes right, level with the box
    assert chip_rect((300, 400, 200, 44), 180, lambda r: True)[1] == 400 - CHIP_GAP - CHIP_H
    right = chip_rect((300, 400, 200, 44), 180, lambda r: r[0] > 400)
    assert right == (300 + 200 + CHIP_GAP, 400 + 22 - 23), right
    # captions: keeps a UI string whole, breaks on the sentence, never ends on a bare "and"
    c = split_cues("When a new request arrives, a notification appears under the bell: New Request Needs Approval.")
    assert all(len(x) <= 54 for x in c), c
    assert not any(x.rstrip().endswith(" and") for x in c), c
    assert any("New Request Needs Approval." in x for x in c), c
    c2 = split_cues("Open requests are counted at the top. Click Open Requests to see them.")
    assert c2[0].endswith("top."), c2
    assert closing_still(1.23) == (4.03, 2.2)
    # a marking must not outlive its screen: on a still picture the hold is the full limit,
    # and a cut to a different picture ends it (checked for real in the build, not here)
    assert SCREEN_DIFF < 0.2 and SCREEN_STEP <= 0.2
    # the closing still: silence first, then the goodbye — his ending, not a fixed 4.5s hold
    tg2, rs2, st2, end2 = pace([(0, 6.0, 0, "line"), (6.0, 6.1, 1, "still")], [3.0, 1.23])
    assert tg2[1] == 4.03 and st2[1] == rs2[1] + 2.2, (tg2, st2, rs2)
    _self_test_containers()
    print("sa_markrules self-test ok")
    for x in c + c2: print(f"  {len(x):2d}  {x}")


# ---- containers on the frame (9 Sep — measured, replaces the guesswork below it) --------------
#
# WHAT THIS MEASURES AND WHY IT IS A LOCAL DIFFERENCE, NOT A THRESHOLD.
# No brightness threshold can separate card from page on these screens. Measured on frame A:
# the dashboard's header card is gradient-filled, its own interior running 239.0 -> 251.0 across
# its width, while the page ground immediately below it is 248.7 and immediately right of it
# 243.3 — a card interior is ~10 levels DARKER than the page ground in the same frame. (That is
# exactly what broke the old card_bounds: with ground=251 almost every pixel counts as ground,
# so its run test fired within 3px of the seed.) The ground level is not even constant between
# frames: it is ~248 on frame A and ~242 on frame B.
#
# A LOCAL difference is immune to all of that. Inside one card the fill drifts ~0.008 levels/px,
# while a real container boundary is a 10-38 level event inside 1-2px:
#     card -> drop shadow under it     255 -> 217..237  (band 27px, uniform across the width)
#     card -> gutter to the next card  255 -> 234..240  (gutter 13px: frame B x1068..1080)
#     card top -> page ground above    255 -> 244       (~11)
# Signal to within-card drift is over 100:1. The test at position p is
#     median(outside 10px) < median(inside 10px) - 3.5   AND   median(inside 10px) > 200
# the medians killing 1px chart gridlines and table rules (a mean would read a 1px rule as a
# 17-level step), and the light test refusing an edge whose inside is ink rather than a surface.
# What actually stops a chart bar or a text row from becoming a card edge is the coverage rule:
# an edge only counts if it runs across 70% of the opposite span. Measured coverage along true
# container edges 0.95-1.00; along gridlines, table rules and text rows 0.00.
#
# KNOWN BLIND SPOT, kept honest rather than fudged: a borderless nested tile. The gap between
# the KPI tiles in frame A is 255 -> 251/253 -> 255, i.e. 2-4 levels, at or below h264 noise, and
# a 1px border hairline is invisible to a 10px median by construction. Those boxes fall back to
# the text cluster clipped to the parent card and are reported confident=False — per the
# workflow rule, an unverifiable check is incomplete, not a pass.
EDGE_WIN = 10         # median window (px): wide enough to erase 1px rules and 2-4px AA fringes,
                      # narrow enough that its median still lands inside the narrowest real
                      # gutter (13px measured, frame B x1068..1080)
EDGE_DROP = 3.5       # grey levels: real boundaries give 10-38, within-card drift gives <0.2
EDGE_LIGHT = 200.0    # the inside surface has to be a surface, not ink
EDGE_COVER = 0.70     # fraction of the opposite span that must show the edge
CONTENT_X = 248       # measured on one product UI: sidebar white ends x=232, border 233,
                      # cards start 248
CONTENT_R = 1900      # measured: cards end x=1900
SIDEBAR_X = 233       # the sidebar border — no box ever crosses it, in either direction
TIGHT_KINDS = ("button", "tile", "field", "text")   # want the control, not its card
LEVEL_BY_KIND = {"button": 0, "tile": 0, "field": 0, "text": 0,
                 "row": 0, "login": 0, "card": 0, "section": 1}


def _numpy():
    try:
        import numpy as np
    except ImportError as exc:                      # pixel work only; the rest of the module is pure
        raise ImportError("sa_markrules container detection needs numpy — "
                          "pip install numpy pillow") from exc
    return np


def luma(frame):
    """frame: image path, PIL image, or a 2-D/3-D array -> float 2-D luma."""
    np = _numpy()
    if isinstance(frame, str):
        from PIL import Image
        frame = Image.open(frame)
    if hasattr(frame, "convert"):
        frame = frame.convert("RGB")
    a = np.asarray(frame, dtype="float32")
    return a.mean(2) if a.ndim == 3 else a


def edge_maps(L, win=EDGE_WIN, drop=EDGE_DROP, light=EDGE_LIGHT):
    """Per-pixel "a surface ends here" maps, one per side. See the block comment above."""
    np = _numpy()
    L = np.asarray(L, dtype="float32")
    H, W = L.shape
    view = np.lib.stride_tricks.sliding_window_view
    E = {k: np.zeros((H, W), bool) for k in ("L", "R", "T", "B")}
    if H < 2 * win + 3 or W < 2 * win + 3:                 # a crop too small to measure
        return E
    Mx = np.median(view(L, win, axis=1), axis=-1)          # Mx[:, i] = median L[:, i:i+win]
    xs = np.arange(win, W - win - 1)
    for key, out, ins in (("L", Mx[:, xs - win], Mx[:, xs + 1]),
                          ("R", Mx[:, xs + 1], Mx[:, xs - win])):
        A = np.zeros((H, W), bool); A[:, xs] = (out < ins - drop) & (ins > light); E[key] = A
    My = np.median(view(L, win, axis=0), axis=-1)          # My[i, :] = median L[i:i+win, :]
    ys = np.arange(win, H - win - 1)
    for key, out, ins in (("T", My[ys - win, :], My[ys + 1, :]),
                          ("B", My[ys + 1, :], My[ys - win, :])):
        A = np.zeros((H, W), bool); A[ys, :] = (out < ins - drop) & (ins > light); E[key] = A
    return E


def prep(frame):
    """Luma + edge maps, computed once and reused by every box on that frame (~0.2s)."""
    L = luma(frame)
    return {"L": L, "E": edge_maps(L)}


def _runs(mask):
    out, s = [], None
    for i, v in enumerate(mask):
        if v and s is None: s = i
        elif not v and s is not None: out.append((s, i - 1)); s = None
    if s is not None: out.append((s, len(mask) - 1))
    return out


def _snap(profile, band, rising, lo, hi):
    """Put a detected band on the exact pixel where the surface changes.

    The 10px medians spread a boundary into a band of about +/-5px around it; the strongest
    step in the span's own median profile IS the boundary (frame B: lands on x=1067, the
    last white pixel of the card, with the 13px gutter starting at 1068).
    """
    s, e = band
    best, at = None, (s + e) // 2
    for p in range(max(lo + 1, s - 3), min(hi - 2, e + 3) + 1):
        d = profile[p] - profile[p - 1] if rising else profile[p] - profile[p + 1]
        if best is None or d > best:
            best, at = d, p
    return at


def input_box(frame, seed, thr=242, maxh=170, maxw=1780, run=0.75):
    """The input control the seed sits in, found from the input's OWN hairline border.

    9 Sep: containers() returns the CARD for these fields, not the input — a form input is white
    on a white card with a ~#E8E8EA 1 px border, about 23 grey levels of contrast, which the edge
    map treats as noise. So walk out from the seed instead: the first row above and below where a
    horizontal hairline runs across the seed, then the first column left and right where a vertical
    hairline runs down that height. Returns (x, y, w, h) or None when the field has no drawn border.
    """
    np = _numpy()
    F = frame if isinstance(frame, dict) and "L" in frame else prep(frame)
    L = F["L"]
    H, W = L.shape
    sx, sy = int(seed[0] + seed[2] / 2), int(seed[1] + seed[3] / 2)
    if not (0 < sx < W and 0 < sy < H): return None

    def hline(r):                                    # a horizontal border under/over the seed
        # the window runs RIGHT from the seed, never straddling it: a seed 24 px inside a field
        # with a symmetric window is half outside the control, and the hairline never clears `run`.
        a, b = sx, min(W, sx + 90)
        return (L[r, a:b] <= thr).mean() >= run
    def vline(c, top, bot):                          # a vertical border down the field's height
        return (L[top + 3:bot - 3, c] <= thr).mean() >= run

    top = next((r for r in range(sy - 4, max(0, sy - maxh), -1) if hline(r)), None)
    bot = next((r for r in range(sy + 4, min(H, sy + maxh)) if hline(r)), None)
    if top is None or bot is None or bot - top < 24: return None
    left = next((c for c in range(sx - 4, max(0, sx - maxw), -1) if vline(c, top, bot)), None)
    right = next((c for c in range(sx + 4, min(W, sx + maxw)) if vline(c, top, bot)), None)
    if left is None or right is None or right - left < 60: return None
    return (left, top, right - left, bot - top)


def containers(frame, seed, levels=2, thr=EDGE_COVER, minsep=6, detail=False):
    """The real containers around `seed` (x, y, w, h), innermost first, as (x, y, w, h).

    Each side is the nearest column/row whose edge coverage over the opposite span clears
    `thr`, snapped to the pixel of the step. Every scan looks outward from the SEED, never from
    the previous pass's rectangle: anchoring on the result makes the fixed point walk out one
    container per pass until it swallows the whole viewport. Where a side has no qualifying
    edge the measured page limits stand in — content runs x=248..1900, and nothing ever crosses
    the sidebar border at x=233 (a sidebar box stays in the sidebar, a content box stays out).

    frame: an image path, an array, or the dict from prep(). detail=True returns per-side
    coverage and a confidence flag instead of bare rectangles.
    """
    np = _numpy()
    F = frame if isinstance(frame, dict) and "E" in frame else prep(frame)
    L, E = F["L"], F["E"]
    H, W = L.shape
    sx, sy, sw, sh = [int(v) for v in seed]
    if sx >= SIDEBAR_X:                                    # a content box
        xlo, xhi = max(EDGE_WIN, SIDEBAR_X + 1), min(W - EDGE_WIN - 2, CONTENT_R + EDGE_WIN)
        clamp = (CONTENT_X, CONTENT_R)
    else:                                                  # a sidebar box
        xlo, xhi = EDGE_WIN, min(W - EDGE_WIN - 2, SIDEBAR_X)
        clamp = (0, SIDEBAR_X - 1)
    ylo, yhi = EDGE_WIN, H - EDGE_WIN - 2
    ax0, ay0 = min(max(xlo, sx), xhi - 1), min(max(ylo, sy), yhi - 1)
    ax1, ay1 = max(ax0, min(xhi - 1, sx + sw - 1)), max(ay0, min(yhi - 1, sy + sh - 1))
    x0, y0, x1, y1 = ax0, ay0, ax1, ay1
    out, last = [], None
    for _ in range(max(1, levels)):
        prev, cov, found = None, {}, {}
        for _ in range(6):
            ys0 = min(max(0, y0), H - 1)
            ys1 = max(ys0 + 1, min(H, y1 + 1))
            colL = E["L"][ys0:ys1, xlo:xhi].mean(0)
            colR = E["R"][ys0:ys1, xlo:xhi].mean(0)
            px = np.median(L[ys0:ys1, :], axis=0)
            l, cov["L"], found["L"] = xlo, 0.0, False
            for s, e in reversed(_runs(colL > thr)):
                if xlo + e < ax0 - minsep:
                    l = _snap(px, (xlo + s, xlo + e), True, 1, W - 1)
                    cov["L"], found["L"] = float(colL[s:e + 1].max()), True
                    break
            r, cov["R"], found["R"] = xhi - 1, 0.0, False
            for s, e in _runs(colR > thr):
                if xlo + s > ax1 + minsep:
                    r = _snap(px, (xlo + s, xlo + e), False, 1, W - 1)
                    cov["R"], found["R"] = float(colR[s:e + 1].max()), True
                    break
            xs0 = min(max(0, l + 4), W - 2)
            xs1 = max(xs0 + 1, min(r - 2, W))
            rowT = E["T"][ylo:yhi, xs0:xs1].mean(1)
            rowB = E["B"][ylo:yhi, xs0:xs1].mean(1)
            py = np.median(L[:, xs0:xs1], axis=1)
            t, cov["T"], found["T"] = ylo, 0.0, False
            for s, e in reversed(_runs(rowT > thr)):
                if ylo + e < ay0 - minsep:
                    t = _snap(py, (ylo + s, ylo + e), True, 1, H - 1)
                    cov["T"], found["T"] = float(rowT[s:e + 1].max()), True
                    break
            b, cov["B"], found["B"] = yhi - 1, 0.0, False
            for s, e in _runs(rowB > thr):
                if ylo + s > ay1 + minsep:
                    b = _snap(py, (ylo + s, ylo + e), False, 1, H - 1)
                    cov["B"], found["B"] = float(rowB[s:e + 1].max()), True
                    break
            if (l, t, r, b) == prev:
                break
            prev = (l, t, r, b)
            x0, y0, x1, y1 = min(l, ax0), min(t, ay0), max(r, ax1), max(b, ay1)
        bx0, bx1 = max(x0, clamp[0]), min(x1, clamp[1])    # the hard, measured page limits
        box = (bx0, y0, max(1, bx1 - bx0 + 1), max(1, y1 - y0 + 1))
        if box == last:                                    # no outer container left to find
            break
        last = box
        out.append({"box": box, "cover": dict(cov), "found": dict(found),
                    "confident": all(found.values())})
        ax0 = max(xlo, x0 - EDGE_WIN - 4)                  # next level: anchor one card out
        ay0 = max(ylo, y0 - EDGE_WIN - 4)
        ax1 = min(xhi - 1, x1 + EDGE_WIN + 4)
        ay1 = min(yhi - 1, y1 + EDGE_WIN + 4)
        x0, y0, x1, y1 = ax0, ay0, ax1, ay1
    return out if detail else [d["box"] for d in out]


def box_shift(frame_a, frame_b, seed):
    """Largest edge move of the same container between two frames, in px.

    Geometry and movement are different faults. Frame C draws one correct rectangle but the
    page scrolls ~372px inside the box's on-screen window, so by the end frame it sits on the
    wrong card; frame D shifts 127px and the end frame is the post-click page. Run this on
    the first and last frame of every box's window: anything over a few px means shorten the
    window to the still segment or key the box to follow — it is not a detector error.
    """
    a = containers(frame_a, seed, levels=1)
    b = containers(frame_b, seed, levels=1)
    if not a or not b:
        return 10 ** 6
    (ax, ay, aw, ah), (bx, by, bw, bh) = a[0], b[0]
    return max(abs(ax - bx), abs(ay - by), abs(ax + aw - bx - bw), abs(ay + ah - by - bh))


def _text_cluster(rows, seed, down=210, side=80, gap=36, bound=None):
    """Group the OCR rows that read as one thing with the control. Inclusive (x0,y0,x1,y1).

    Fixed 9 Sep, three ways. Growth is SYMMETRIC — the old `by < y0 - 6: skip` was downward
    only, so a box seeded on the captions METRIC 1 / METRIC 2 could never reach the
    numbers sitting above them (frame A). Horizontal proximity is measured from the SEED, not
    from the growing box — measuring it from the box let a chart's title -> y-axis -> month
    labels chain sideways into the neighbouring card (frame B). And `gap` is the measured
    gutter (13-27px), not 130px, which is what let a cluster jump a card boundary entirely.
    `bound` is the detected container: nothing outside it may join, ever.
    """
    sx, sy, sw, sh = [int(v) for v in seed]
    x0, y0, x1, y1 = sx, sy, sx + sw - 1, sy + sh - 1
    bx0, by0, bx1, by1 = bound if bound else (-10 ** 6, -10 ** 6, 10 ** 6, 10 ** 6)
    changed = True
    while changed:
        changed = False
        for _, b in rows:
            rx, ry, rw, rh = [int(v) for v in b]
            rx1, ry1 = rx + rw - 1, ry + rh - 1
            if rx < bx0 or rx1 > bx1 or ry < by0 or ry1 > by1:
                continue                                   # outside the card: never
            if rx1 < sx - side or rx > sx + sw + side:
                continue                                   # anchored on the seed, not the box
            if ry1 < sy - down or ry > sy + down:
                continue                                   # travel budget, both directions
            if ry1 < y0 - gap or ry > y1 + gap:
                continue                                   # the gutter to the next card
            n = (min(x0, rx), min(y0, ry), max(x1, rx1), max(y1, ry1))
            if n != (x0, y0, x1, y1):
                x0, y0, x1, y1 = n
                changed = True
    return x0, y0, x1, y1


def content_block(rows, seed, down=210, side=80, pad=14, content_x=CONTENT_X, gap=36,
                  frame=None, kind=None, level=None, detail=False):
    """The container a control belongs to — his rule: the card's OWN edges.

    Pass `frame` (an image path, an array, or a prep() dict) and the card comes off the pixels
    via containers(): it starts at the card's real top, not at its title strip, stops at the
    real gutter instead of overshooting into the neighbour, and never crosses the sidebar. The
    OCR `rows` then only group controls INSIDE that card. `kind` picks the level — a button or
    a tile wants the control, a row or a card wants the container, a section wants the card
    around it (LEVEL_BY_KIND), or pass `level` directly.

    Without `frame` it falls back to text clustering. That path is now fixed (see
    _text_cluster) but it is still a guess: it is reported confident=False.

    Returns (x, y, w, h), or None. detail=True returns (box, info) with the confidence.
    """
    sx, sy, sw, sh = [int(v) for v in seed]
    lv = level if level is not None else LEVEL_BY_KIND.get(kind, 0)
    info = {"source": "text", "confident": False, "level": 0, "cover": {}}
    if frame is None:
        x0, y0, x1, y1 = _text_cluster(rows, seed, down, side, gap)
        if x1 - x0 < sw + 20 and y1 - y0 < sh + 20:
            return (None, info) if detail else None
        lo = max(0, x0 - pad)
        hi = x1 + pad
        if sx >= SIDEBAR_X:                    # a content box starts at the content edge...
            lo = max(lo, content_x if sx >= content_x else SIDEBAR_X + 1)
            hi = min(hi, CONTENT_R)
        else:                                  # ...and a sidebar box stays in the sidebar
            hi = min(hi, SIDEBAR_X - 1)
        box = (lo, max(0, y0 - pad), hi - lo + 1, (y1 - y0) + 2 * pad + 1)
        return (box, info) if detail else box

    stack = containers(frame, seed, levels=max(1, lv + 1), detail=True)
    if not stack:
        return (None, info) if detail else None
    node = stack[min(lv, len(stack) - 1)]
    cx, cy, cw, ch = node["box"]
    info.update(source="pixels", confident=node["confident"],
                level=min(lv, len(stack) - 1), cover=node["cover"])
    box = node["box"]
    if kind in TIGHT_KINDS:
        # the control, not its card — but a borderless tile has no edge to find (frame A's KPI
        # pair is 2-4 levels apart), so use the cluster clipped to the card and say so.
        x0, y0, x1, y1 = _text_cluster(rows, seed, down, side, gap,
                                       bound=(cx, cy, cx + cw - 1, cy + ch - 1))
        tight = (x0 - cx <= 2 * pad and cx + cw - 1 - x1 <= 2 * pad
                 and y0 - cy <= 2 * pad and cy + ch - 1 - y1 <= 2 * pad)
        if not tight:
            box = (max(cx, x0 - pad), max(cy, y0 - pad),
                   min(cx + cw - 1, x1 + pad) - max(cx, x0 - pad) + 1,
                   min(cy + ch - 1, y1 + pad) - max(cy, y0 - pad) + 1)
            info["source"] = "pixels+text"
            info["confident"] = False          # no tile boundary in the pixels: verify by eye
    return (box, info) if detail else box


def card_bounds(gray, seed, pad=0, ground=None, min_run=40):
    """Kept as a name only — the old ground-run version is gone.

    It thresholded at ground=251, which on these screens marks almost every pixel as ground, so
    its run test fired within 3px of the seed. Deleted rather than tuned: no global threshold
    can work when a card interior (239-251) is darker than the page ground beside it (248.7).
    This now returns the innermost real container. `ground` is ignored.
    """
    box = containers(gray, seed, levels=1)
    if not box:
        return None
    x, y, w, h = box[0]
    if w < min_run or h < 20:
        return None
    return (max(0, x - pad), max(0, y - pad), w + 2 * pad, h + 2 * pad)


def _demo_frame():
    """A stand-in for the product UI these constants were measured on (1920x1140), built from the
    signatures so the self-test exercises exactly what broke: a gradient card DARKER than the
    page ground beside it, a 13px gutter between two cards, a 27px drop shadow, a card whose
    left edge is invisible, a borderless nested tile only 3 levels apart, and the furniture a
    card carries that must NOT read as an edge (a 1px table rule, a part-height chart bar)."""
    np = _numpy()
    L = np.full((1140, 1920), 248.0, "float32")            # page ground (it is ~242 on frame B)
    L[:, 0:233] = 255.0                                    # sidebar white ends x=232
    L[:, 233] = 231.0                                      # its border
    grad = np.linspace(239.0, 251.0, 1900 - 248 + 1, dtype="float32")
    L[120:413, 248:1901] = grad                            # section card: interior 239 -> 251
    L[413:440, 248:1901] = 230.0                           # drop shadow, 27px, uniform
    L[200:391, 313:718] = 255.0                            # two white KPI tiles on that card
    L[200:391, 737:1142] = 255.0
    L[460:849, 252:1068] = 255.0                           # card 2 (frame B geometry)
    L[460:849, 1068:1081] = 237.0                          # the 13px gutter
    L[460:849, 1081:1901] = 255.0                          # card 3
    L[849:876, 252:1901] = 230.0                           # shadow under both
    L[460:849, 651:670] = 252.0                            # borderless split in card 2: 3 levels
    L[600:821, 480:541] = 60.0                             # a chart bar: ink, 57% of the height
    L[750, 260:1061] = 86.0                                # a 1px table rule across the card
    L[940:1111, 234:248] = 254.0                           # card 6's left edge, only 1 level
    L[950:1101, 248:1901] = 255.0
    return L


def _self_test_containers():
    try:
        _numpy()
    except ImportError:
        raise SystemExit("container self-test needs numpy: pip install numpy pillow")
    F = prep(_demo_frame())

    def edges(box):
        x, y, w, h = box
        return x, y, x + w - 1, y + h - 1

    # card 2 from a seed high in it: the real card, not the text
    # to the pixel: the card starts at 252/460 and its white ends at 1067 (the 13px gutter is
    # 1068..1080) and at 848 (the shadow starts 849) — snapped, not the middle of the band
    x0, y0, x1, y1 = edges(containers(F, (300, 500, 120, 20))[0])
    assert (x0, y0) == (252, 460), (x0, y0)                        # grows UP past the seed
    assert x1 == 1067 and x1 < 1081, x1                            # stops at the gutter
    assert y1 == 848, y1                                           # no 210px travel budget
    # ...and none of the card's own furniture counts as an edge: not the 1px table rule (the
    # medians erase it — a mean would see a 17-level step), not the chart bar (57% of the
    # height, under the 0.70 coverage bar), not the borderless 3-level split at x=651

    # a tile on the gradient card: its surroundings are DARKER than the page ground beside them
    t0, u0, t1, u1 = edges(containers(F, (400, 300, 120, 20))[0])
    assert (t0, t1) == (313, 717) and (u0, u1) == (200, 390), (t0, u0, t1, u1)
    # invisible left edge -> the measured content edge (248, not the old 240, not the page edge)
    c0, _, _, _ = edges(containers(F, (600, 1000, 120, 20))[0])
    assert c0 == 248 == CONTENT_X, c0
    # a sidebar box stays in the sidebar; a content box never crosses back into it
    s0, _, s1, _ = edges(containers(F, (60, 300, 100, 20))[0])
    assert s0 >= 0 and s1 <= SIDEBAR_X - 1, (s0, s1)

    # content_block: a row box is its own card even when text carries on in the next one
    rows = [("Panel A", [276, 486, 240, 26]), ("Jan", [300, 800, 40, 20]),
            ("Dec", [966, 800, 40, 20]), ("Panel B", [1112, 486, 250, 26]),
            ("Panel C", [276, 900, 320, 28])]
    box, info = content_block(rows, (300, 500, 120, 20), frame=F, kind="row", detail=True)
    b0, b1, b2, b3 = edges(box)
    assert info["source"] == "pixels" and info["confident"], info
    assert b2 < 1081 and b3 < 876, box                     # not the neighbour, not the next section
    assert abs(b0 - 252) <= 2 and abs(b1 - 460) <= 2, box
    # ...and the far side of a card is the card, not wherever its text happens to stop
    rbox = content_block([("Panel B", [1112, 486, 250, 26])],
                         (1112, 486, 250, 26), frame=F, kind="row")
    assert edges(rbox)[2] == CONTENT_R, rbox
    # a borderless tile has no edge to find: clipped to its card AND reported low confidence
    trows = [("Left half", [300, 600, 200, 24]), ("Right half", [700, 600, 200, 24])]
    tbox, tinfo = content_block(trows, (300, 600, 200, 24), frame=F, kind="tile", detail=True)
    assert tinfo["confident"] is False and tinfo["source"] == "pixels+text", tinfo
    e0, _, e2, _ = edges(tbox)
    assert e0 >= 252 and e2 <= 1067 and (e2 - e0) < 700, tbox
    # movement is a window fault, not a geometry fault: same seed, page scrolled under it
    np = _numpy()
    assert box_shift(F, np.roll(F["L"], 60, axis=0), (300, 500, 120, 20)) >= 50
    assert box_shift(F, F, (300, 500, 120, 20)) == 0

    # no frame: the text fallback still has to grow upward (frame A's numbers sit above their
    # captions) and still must not start inside the sidebar
    krows = [("2", [313, 306, 40, 60]), ("METRIC 1", [313, 372, 200, 24]),
             ("1", [737, 306, 40, 60]), ("METRIC 2", [737, 372, 200, 24])]
    fb = content_block(krows, (313, 372, 200, 24))
    assert fb is not None and fb[1] <= 306, fb
    # ...must not jump the gutter into the next section (the old 130px tolerance was 5-10x the
    # measured 13-27px gutters), and must not chain sideways into the neighbouring card
    jump = content_block([("row in this card", [276, 800, 200, 24]),
                          ("Panel C", [276, 900, 320, 28])], (276, 800, 200, 24))
    assert jump is None or jump[1] + jump[3] < 880, jump
    chain = content_block([("Panel A", [276, 486, 240, 26]),
                           ("axis", [560, 520, 200, 20]), ("months", [800, 520, 200, 20]),
                           ("Panel B", [1060, 520, 250, 26])], (276, 486, 240, 26))
    assert chain[0] + chain[2] < 800, chain
    wide = content_block([("a", [250, 500, 900, 24]), ("b", [250, 540, 900, 24])],
                         (250, 500, 900, 24))
    assert wide[0] >= CONTENT_X, wide
    # card_bounds is the same detector now, not a 251 threshold that fires 3px from the seed
    cb = card_bounds(F["L"], (300, 500, 120, 20))
    assert cb and cb[2] > 700 and cb[3] > 350, cb

    # input_box: a synthetic form field — white card, 1 px #E8E8EA hairline round the input.
    # The point of the test is that the FAINT border is found; a threshold tuned for real edges
    # returns the card and the box swallows its neighbours (what shipped in two review cuts before 9 Sep).
    np = _numpy()
    card = np.full((300, 900), 255, dtype=np.uint8)
    card[80:140, 100:700] = 255
    card[80, 100:700] = card[139, 100:700] = 232          # top / bottom hairline
    card[80:140, 100] = card[80:140, 699] = 232           # left / right hairline
    card[100:120, 140:300:3] = 90                         # the value typed in it — glyph strokes,
    card[100:120, 141:300:3] = 90                         # not a solid bar, so it never reads as a
                                                          # border line the way a filled block would
    ib = input_box({"L": card.astype(int)}, (150, 105, 24, 8))
    assert ib == (100, 80, 599, 59), ib


if __name__ == "__main__":
    _self_test()


# ---- how long a screen actually stays put (9 Sep) ---------------------------------------------
# Review feedback on two cuts: markings stayed up after the screen they described had gone,
# so the viewer still saw the previous screen's marking. A box that survives the screen
# it describes is the single most visible fault in these videos, and no amount of box-geometry
# work fixes it. So measure the screen instead of trusting the plan: hold the marking only while
# the picture under it is still the same picture.


def screen_hold(video, t0, limit=6.0, diff=SCREEN_DIFF, step=SCREEN_STEP, _cache={}):
    """Seconds from t0 until the picture changes. Returns `limit` if it never does.

    A scroll, a click that loads a page, a dropdown opening and a modal appearing all move a
    large fraction of the pixels, which is exactly what should end a marking.
    """
    import subprocess, tempfile, pathlib
    np = _numpy()
    key = (str(video), round(t0, 2), round(limit, 2))
    if key in _cache:
        return _cache[key]
    tmp = pathlib.Path(tempfile.mkdtemp())

    def grab(t):
        p = tmp / f"{t:.2f}.png"
        for k in range(2):
            r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t + k * 0.034:.3f}",
                                "-i", str(video), "-frames:v", "1", "-vf", "scale=480:-1", str(p)])
            if r.returncode == 0 and p.exists():
                from PIL import Image
                return np.asarray(Image.open(p).convert("L"), dtype=np.int16)
        return None

    base = grab(t0)
    if base is None:
        _cache[key] = limit
        return limit
    t = round(t0 + step, 2)
    while t <= t0 + limit:
        cur = grab(t)
        if cur is not None and cur.shape == base.shape:
            moved = float((np.abs(cur - base) > 18).mean())
            if moved > diff:
                _cache[key] = round(t - t0, 2)
                return _cache[key]
        t = round(t + step, 2)
    _cache[key] = limit
    return limit
