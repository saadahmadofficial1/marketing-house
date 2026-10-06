#!/usr/bin/env python3
"""sa_appbuild — turn a read phone-app recording into a CapCut review project.

Built for a phone-app training series. It joins three things that already
exist: the verified action map (what is taught, and when), the boxed OCR read from
sa_appread (WHERE each element sits, in source pixels), and sa_stepmark's renderer.

The rule it enforces, which is the whole point: a call-out is only placed when the OCR
proves its target was on screen at that moment. Anything unproven is SKIPPED and listed,
never nudged to a plausible spot. Saad's markings have been wrong before by being placed
from the sentence instead of the screen.

    Tools/venv/bin/python3 Tools/sa_appbuild.py --id 0001 \
        --map  <maps dir>/0001_map.json \
        --read <boxed screens dir>/0001/screens.json \
        --video "<vertical dir>/06_RoleName_0001_V.mp4" \
        --out   <build dir> --title "Role Name"
    Tools/venv/bin/python3 Tools/sa_appbuild.py --add-outlines <build>/_layers.json   # 24 Sep shape, no rebuild
    Tools/venv/bin/python3 Tools/sa_appbuild.py --test
    (--text-box on any build = the old strip round the OCR words instead of the element)

Geometry: source is 1206x2622; the vertical picture is cropped top CROP_TOP, bottom
CROP_BOT and scaled to 1080 wide, so every source box must be mapped the same way or the
marking lands somewhere else entirely.
"""
import argparse, json, os, pathlib, re, subprocess, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import sa_stepmark as sm
from sa_appread import find_element, parse_elements

FFMPEG = os.path.expanduser("~/.local/bin/ffmpeg")
if not os.path.exists(FFMPEG):
    FFMPEG = "ffmpeg"

OCR_BIN = pathlib.Path(__file__).resolve().parent / "bin" / "sa_ocr"
SRC_W, SRC_H = 1206, 2622
CROP_TOP, CROP_BOT = 130, 89          # iOS status bar / below the tab bar — measured
CANVAS = (1080, 2152)          # default; build() overrides it from the video itself
SCALE = CANVAS[0] / SRC_W             # 0.895522
HOLD = 2.10                           # Saad's measured median hold, via sa_stepmark
GREEN_REF = (46, 125, 50)             # #2E7D32 placeholder: sample the app's own green


HEADINGS = None      # {normalised element text: heading} - set by --headings
SCREEN = None        # (x0, y0, x1, y1) of the phone screen - headings stay inside it


def heading_for(el):
    """The heading chip: what the viewer should DO or what this MEANS. Never a copy of
    the button's own words - that duplication is why the chip was first removed."""
    key = " ".join("".join(c if (c.isalnum() or c == " ") else " "
                           for c in label_for(el).lower()).split())
    return (HEADINGS or {}).get(key, label_for(el))


def to_canvas(el):
    """Source element box -> vertical-picture box. None if it lives in trimmed chrome."""
    x, y, w, h = el["x"], el["y"], el["w"], el["h"]
    if y < CROP_TOP or y + h > SRC_H - CROP_BOT:
        return None
    return (round(x * SCALE), round((y - CROP_TOP) * SCALE),
            round(w * SCALE), round(h * SCALE))


def screen_at(screens, t):
    for s in screens:
        if s["t"] <= t < s["t_end"]:
            return s
    return None


def grab(video, t, path):
    subprocess.run([FFMPEG, "-y", "-v", "error", "-ss", f"{t:.2f}", "-i", str(video),
                    "-frames:v", "1", str(path)], check=True)
    return path


def is_pale(frame_png, box):
    """Is the ring the box will draw sitting on a pale surface? Then the dark app green
    has the better contrast; anywhere else the bright one does. Measured on the RING,
    not the element, because that is the only place the stroke is actually drawn."""
    from PIL import Image
    import numpy as np
    a = np.array(Image.open(frame_png).convert("RGB")).astype(int)
    x, y, w, h = box
    pad = sm.PAD + sm.STROKE
    y0, y1 = max(0, y - pad), min(a.shape[0], y + h + pad)
    x0, x1 = max(0, x - pad), min(a.shape[1], x + w + pad)
    ring = a[y0:y1, x0:x1]
    if ring.size == 0:
        return True
    border = np.concatenate([ring[:3].reshape(-1, 3), ring[-3:].reshape(-1, 3),
                             ring[:, :3].reshape(-1, 3), ring[:, -3:].reshape(-1, 3)])
    return bool(border.mean() > 150)


# ---- the SHAPE of a marking (requirement, 24 Sep: some markings were too small and others
# did not follow the shape of the thing they mark). OCR gives the box of the WORDS; the viewer taps the THING:
# the 'Approvals' tile, not a strip round its caption. So the outline follows the element
# the words sit on, found by growing that element's own colour out from just around the text.
# Every size is a fraction of the phone screen, never pixels, because the app layer gets
# rescaled (his 24 Sep layout is 0.716) and the rules must survive that.
SHAPE = "element"      # "text" = the old strip round the OCR words (--text-box)
EL_TOL = 5             # per channel: card #FDFFFD vs page #F6F6F2 differ by 7-11, video noise ~2
EL_MAX_AREA = 0.12     # of the screen - a panel or the page is not "the thing to tap"
EL_MAX_GROWTH = 60     # element area / text area - a tile with a one-word label is ~50; a card of rows is 70+
EL_MIN_FILL = 0.80     # rounded rect >=0.88 (0.81 with the FAB over a corner); a leak is far lower
MIN_H, MIN_W = 0.024, 0.11   # fallback floor (before the gap), of screen h / w - no marking is tiny


def element_box(frame, text_box, bounds=None):
    """The UI element that the OCR'd text belongs to -> (box, radius, kind, why).

    kind "element": the tile / pill / button / row the text sits on - `box` is its edge and
    `radius` its own corner radius. Otherwise `why` names the guard that refused it and
    `box` hugs the actual glyphs (the OCR box can sit 10px off them), grown towards a floor
    size but only into empty space, so it never crosses the line above or below:
    kind "tab" is a bottom-bar label with its icon, "text" the words alone.
    Tried and dropped 24 Sep: pulling in any nearby "ink" as icon+label - it merged the
    neighbouring text line far more often than an icon, so only the tab bar does that.
    Only the drawn outline changes: hold checks keep reading the ORIGINAL text box."""
    import cv2
    import numpy as np
    a = np.asarray(frame)[..., :3].astype(np.int16)
    bx0, by0, bx1, by1 = bounds or (0, 0, a.shape[1], a.shape[0])
    sw, sh = bx1 - bx0, by1 - by0
    x, y, w, h = (int(v) for v in text_box)
    scr = a[by0:by1, bx0:bx1]
    tx0, ty0, tx1, ty1 = x - bx0, y - by0, x + w - bx0, y + h - by0
    gap = max(3, round(0.004 * sw))               # just clear of the glyphs' anti-aliasing
    band = max(3, round(0.006 * sw))
    ring = np.zeros(scr.shape[:2], bool)
    ring[max(0, ty0 - gap - band):ty1 + gap + band, max(0, tx0 - gap - band):tx1 + gap + band] = True
    ring[max(0, ty0 - gap):ty1 + gap, max(0, tx0 - gap):tx1 + gap] = False

    def fallback(why, seed=None, kind="text"):
        # grow to the minimum size, evenly on both sides, but only into EMPTY space: a floor
        # that pushed the outline across the figure above a caption would be a new fault
        l, t, r, b = tx0, ty0, tx1, ty1
        if seed is not None:
            ink = np.abs(scr - seed).max(axis=2) > 40
            # the OCR box can sit 10px off the glyphs: pad round what is actually drawn
            oy, ox = max(0, t - gap), max(0, l - gap)
            ys, xs = np.nonzero(ink[oy:b + gap, ox:r + gap])
            if ys.size:
                l, t, r, b = ox + xs.min(), oy + ys.min(), ox + xs.max() + 1, oy + ys.max() + 1
                for _ in range(max(3, h // 2)):                # glyphs running past the box
                    up, dn = t > 0 and ink[t - 1, l:r].any(), b < sh and ink[b, l:r].any()
                    if not (up or dn):
                        break
                    t, b = t - up, b + dn
                if kind == "tab":        # a tab's label takes the icon just above it
                    col, k = ink[:t, l:r].any(axis=1)[::-1], 0
                    while k < min(len(col), 2 * h) and not col[k]:
                        k += 1
                    k0 = k
                    while k < len(col) and col[k] and k - k0 < 3 * h:
                        k += 1
                    t -= k if k > k0 else 0
        gx = (max(0, round(MIN_W * sw) - (r - l)) + 1) // 2
        gy = (max(0, round(MIN_H * sh) - (b - t)) + 1) // 2
        if seed is not None:
            c = max(6, round(0.012 * sw)) + 5               # the outline's gap + stroke + air

            def free(strip):                                # empty lines next to the glyphs
                hit = np.nonzero(strip)[0]
                return hit[0] if hit.size else len(strip)
            per_row = ink[:, max(0, l - c - gx):r + c + gx].any(axis=1)
            per_col = ink[t:b].any(axis=0)
            gy = max(0, min(gy, free(per_row[max(0, t - c - gy):t][::-1]) - c,
                            free(per_row[b:b + c + gy]) - c))
            gx = max(0, min(gx, free(per_col[max(0, l - c - gx):l][::-1]) - c,
                            free(per_col[r:r + c + gx]) - c))
        fw, fh = r - l + 2 * gx, b - t + 2 * gy
        fx, fy = max(0, min(l - gx, sw - fw)), max(0, min(t - gy, sh - fh))
        return (int(fx + bx0), int(fy + by0), int(fw), int(fh)), round(0.009 * sw), kind, why

    px = scr[ring]
    if px.size == 0:
        return fallback("text outside the screen")
    seed = np.median(px, axis=0)
    if (np.abs(px - seed).max(axis=1) <= EL_TOL).mean() < 0.55:
        return fallback("text on a busy background")
    mask = (np.abs(scr - seed).max(axis=2) <= EL_TOL).astype(np.uint8)
    mask[max(0, ty0 + 2):ty1 - 2, max(0, tx0 + 2):tx1 - 2] = 1     # the words are part of it
    _, lab = cv2.connectedComponents(mask, connectivity=4)
    k = lab[min(max(0, (ty0 + ty1) // 2), sh - 1), min(max(0, (tx0 + tx1) // 2), sw - 1)]
    comp = (lab == k).astype(np.uint8)
    ys, xs = np.nonzero(comp)
    ex0, ey0, ex1, ey1 = xs.min(), ys.min(), xs.max() + 1, ys.max() + 1
    ew, eh = ex1 - ex0, ey1 - ey0
    if ex0 <= 1 or ey0 <= 1 or ex1 >= sw - 1 or ey1 >= sh - 1:
        if ey1 >= sh - 1 and eh < 0.1 * sh:
            # the tab bar: nothing in it but tabs, so the label takes the icon above it
            return fallback("a tab in the bottom bar", seed, "tab")
        return fallback("colour runs to the screen edge (page background)", seed)
    if ex0 > tx0 + 2 or ey0 > ty0 + 2 or ex1 < tx1 - 2 or ey1 < ty1 - 2:
        return fallback("text spills out of the element", seed)
    if ew * eh > EL_MAX_AREA * sw * sh:
        return fallback("element is a panel, not a control", seed)
    if ew * eh > EL_MAX_GROWTH * max(1, w * h):
        return fallback("text is one line in a much bigger card", seed)
    if max(ew / eh, eh / ew * 4) > 14:
        return fallback("element is a bar or strip", seed)
    cs, _ = cv2.findContours(comp[ey0:ey1, ex0:ex1].copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    solid = np.zeros((eh, ew), np.uint8)
    cv2.drawContours(solid, cs, -1, 1, -1)
    if solid.mean() < EL_MIN_FILL:
        return fallback("element is not a rectangle", seed)
    # Its TRUE edge. The grown colour stops inside the anti-aliased rim, and on a dark or
    # gradient fill video noise leaves it ragged: 01_033's ~25px corner read 44 and the
    # outline cut through the tile's corners (verified 24 Sep). So re-find the edge where a
    # pixel turns nearer the surrounding colour than the element's own, each side the median
    # of its middle half (a FAB over a corner cannot move it). Skipped when the element is
    # its surroundings' colour (a row inside its card): there the grown edge is all there is.
    M = gap + 2 * band
    X0, Y0, X1, Y1 = max(0, ex0 - M), max(0, ey0 - M), min(sw, ex1 + M), min(sh, ey1 + M)
    win = scr[Y0:Y1, X0:X1]
    inner = np.zeros(win.shape[:2], bool)
    inner[max(0, ey0 - Y0 - gap - band):ey1 - Y0 + gap + band, max(0, ex0 - X0 - gap - band):ex1 - X0 + gap + band] = True
    page = np.median(win[~inner], axis=0) if (~inner).any() else seed
    if np.abs(seed - page).max() > 2 * EL_TOL:
        body = np.zeros(win.shape[:2], np.uint8)
        body[ey0 - Y0:ey1 - Y0, ex0 - X0:ex1 - X0] = solid
        body |= (inner & (np.abs(win - seed).sum(axis=2) < np.abs(win - page).sum(axis=2))).astype(np.uint8)
        cs, _ = cv2.findContours(body, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        mid = (float((tx0 + tx1) // 2 - X0), float((ty0 + ty1) // 2 - Y0))
        body[:] = 0
        cv2.drawContours(body, [c for c in cs if cv2.pointPolygonTest(c, mid, False) >= 0] or cs, -1, 1, -1)
        H, W = body.shape
        mc, mr = body[:, W // 4:3 * W // 4] > 0, body[H // 4:3 * H // 4] > 0
        t, b = round(np.median(mc.argmax(0))), H - round(np.median(mc[::-1].argmax(0)))
        l, r = round(np.median(mr.argmax(1))), W - round(np.median(mr[:, ::-1].argmax(1)))
        if b - t > eh // 2 and r - l > ew // 2:
            ex0, ey0, ex1, ey1, solid = X0 + l, Y0 + t, X0 + r, Y0 + b, body[t:b, l:r]
            ew, eh = ex1 - ex0, ey1 - ey0
    # its corner radius, from the area a rounded corner cuts off: (1 - pi/4) r^2. Counting
    # pixels is steadier than any one edge; the median ignores a corner a FAB sits on.
    m = min(ew, eh) // 2
    cut = sorted(m * m - int(solid[sy, sx].sum()) for sy in (slice(0, m), slice(eh - m, eh))
                 for sx in (slice(0, m), slice(ew - m, ew)))
    rad = min(round(((cut[1] + cut[2]) / 2 / 0.2146) ** 0.5), m)
    return (int(ex0 + bx0), int(ey0 + by0), int(ew), int(eh)), int(rad), "element", None


def outline_for(frame, text_box, bounds=None):
    """What render_step_mobile draws: (box, pad, radius, kind, why). Even gap outside the
    element, corners concentric with the element's own. SHAPE "text" = the old strip."""
    if SHAPE == "text":
        return tuple(text_box), 12, 18, "text", "old style (--text-box)"
    box, rad, kind, why = element_box(frame, text_box, bounds)
    bx0, by0, bx1, by1 = bounds or (0, 0, len(frame[0]), len(frame))
    pad = max(6, round(0.012 * (bx1 - bx0)))
    # never past the screen onto the phone frame: a bottom tab sits ~7px above the edge and
    # its outline overhung it by 10 (03_016, 04_016); pull that side of the box in instead
    x, y, w, h = box
    x0, y0 = max(x, bx0 + pad), max(y, by0 + pad)
    x1, y1 = min(x + w, bx1 - pad - 1), min(y + h, by1 - pad - 1)     # PIL draws x1/y1 inclusive
    if x1 > x0 and y1 > y0:
        box = (x0, y0, x1 - x0, y1 - y0)
    return box, pad, rad + pad, kind, why


def colour_for(frame_png, box, outline):
    """Dark app green, or the bright accent where the dark one would vanish: on a dark
    surface where the stroke is drawn (the outline's ring) OR on a target that is itself
    dark/green (sampled round its words, inside it) - an outline hugging the green Approve
    button 4px out reads as the button's own border (sa_stepmark's ACCENT rule)."""
    pale = is_pale(frame_png, outline) and is_pale(frame_png, box)
    return (sm.APP_GREEN, sm.APP_GREEN_SOFT) if pale else (sm.ACCENT_GREEN, sm.ACCENT_GREEN_SOFT)


def candidates(target):
    """Ordered guesses at the literal on-screen text inside a stated mark_target.

    The maps write targets like: the 'READY FOR REVIEW — REF-1001 • Item K8 55 DELUXE' card.
    Taking the longest WORD out of that picks "DELUXE", which is on three cards at once —
    that is how a marking ended up on a K6 when the beat was about a K8. So: try the
    quoted phrase first, then its segments, and only then single words."""
    out = []
    for q in re.findall(r"['\"\u201c\u201d]([^'\"\u201c\u201d]{2,60})['\"\u201c\u201d]", target):
        out.append(q)
    for q in list(out) + [target]:
        for seg in re.split(r"[\u2014\u2013\u2022\u00b7/|]", q):
            seg = seg.strip(" .:\u2014\u2013\u2022\u00b7")
            if 2 <= len(seg) <= 40:
                out.append(seg)
    # NO bare-word fallback. A word like "Floor" or "DELUXE" is on several rows at once,
    # and falling back to it is how a marking lands on the wrong card. If the map did not
    # quote the literal on-screen text, the target is unproven and the marking is skipped.
    out.insert(0, target)            # the whole stated target first - most specific
    seen, res = set(), []
    for c in out:
        k = " ".join(c.lower().split())
        if k and k not in seen:
            seen.add(k)
            res.append(c)
    return res


def _pn(z):
    return " ".join("".join(c if (c.isalnum() or c == " ") else " " for c in z.lower()).split())


def matches(screen, needle):
    n = _pn(needle)
    return [e for e in screen.get("elements", [])
            if e.get("x") is not None and n and n in _pn(e["text"])]


def locate(screen, target):
    """The element a stated target means, or (None, why). UNIQUE MATCH OR NOTHING —
    a marking on the wrong row is worse than a marking that is missing, and this
    series has been bitten by exactly that."""
    ambiguous = False
    for c in candidates(target):
        hits = matches(screen, c)
        if len(hits) == 1:
            return hits[0], None
        if len(hits) > 1:
            ambiguous = True
    return None, ("ambiguous - the stated target matches several elements"
                  if ambiguous else "not on screen per OCR")


def label_for(el):
    """The label IS the element's own on-screen text — so a marking can never disagree
    with the thing it points at. Requirement (23 Sep): markings and titles must match."""
    t = " ".join(el["text"].split())
    for junk in ("›", "»", "•", "❯"):
        t = t.replace(junk, "")
    # OCR often prefixes an icon it read as a stray glyph or lone digit ("1 I'm Here")
    t = re.sub(r"^[^A-Za-z0-9]{0,2}\d?[^A-Za-z0-9]{0,2}\s+(?=[A-Za-z])", "", t.strip())
    # a lone leading character is an icon the OCR tried to read ("D Messages", "E F1-028")
    bits = t.split()
    if len(bits) > 1 and len(bits[0]) == 1 and bits[0].lower() not in ("a", "i"):
        t = " ".join(bits[1:])
    t = t.strip(" .:-")
    return t[:28]


def ocr_frame(video, t, tmp):
    """OCR the exact frame the marking will sit on.

    The sampled screens say WHAT is taught and WHEN. They must not be trusted for WHERE:
    a screen entry spans a window and the list can scroll inside it. Saad's very first
    correction on this series was a box sitting over footage that moved underneath it.
    So geometry always comes from the frame itself."""
    f = grab(video, t, tmp / "probe.png")
    out = subprocess.run([str(OCR_BIN), "--boxes", str(f)],
                         capture_output=True, text=True).stdout
    return {"elements": parse_elements(out.partition("\t")[2].strip())}, f


def reads(video, t, box, label, tmp):
    """Does the box region at time t read back its own label? OCR, not pixels."""
    from PIL import Image
    im = Image.open(grab(video, t, tmp / "h.png")).convert("RGB")
    x, y, w, h = box
    im.crop((max(0, x - 10), max(0, y - 10), min(im.width, x + w + 10),
             min(im.height, y + h + 10))).save(tmp / "hc.png")
    out = subprocess.run([str(OCR_BIN), str(tmp / "hc.png")], capture_output=True, text=True).stdout
    norm = lambda z: " ".join("".join(c if (c.isalnum() or c == " ") else " "
                                      for c in z.lower()).split())
    key = norm(label).replace(" ", "")[:12]    # spacing is OCR noise: "XX 1 23456" reads back "XX 123456"
    return bool(key) and key in norm(out.partition("\t")[2]).replace(" ", "")


def stable(video, t, dur, box, tmp, label=None, step=0.25):
    """How long does the element REALLY stay under the box? Returns seconds, or 0.

    The 23 Sep final review found 9 of 23 markings in one module drifting mid-hold - two ended
    on a different button - because this used to compare mean pixel difference inside
    the box, and a transition onto a similar white panel never trips that. Now the box
    is read back every quarter-second and the marking ends when its label leaves."""
    if not label:
        return dur
    held, k, misses = 0.0, 0, 0
    while k * step <= dur:
        if reads(video, t + k * step, box, label, tmp):
            held, misses = k * step, 0      # end ON the last verified frame, not a step past it
        else:
            misses += 1
            if misses >= 2:                 # one miss is OCR noise; two is the element gone
                break
        k += 1
    held = min(held, dur)
    return round(held, 2) if held >= sm.MIN_DUR else 0.0


def probe_size(video):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                          "-show_entries", "stream=width,height", "-of", "csv=p=0", str(video)],
                         capture_output=True, text=True).stdout.strip()
    w, h = (int(v) for v in out.split(",")[:2])
    return (w, h)


def build(mapping, screens, video, out, title):
    from PIL import Image
    import numpy as np
    global CANVAS
    CANVAS = probe_size(video)     # the picture may be a bare crop or a phone mockup
    out = pathlib.Path(out)
    (out / "layers").mkdir(parents=True, exist_ok=True)
    tmp = out / "_frames"
    tmp.mkdir(exist_ok=True)
    layers, skipped = [], []
    for n, beat in enumerate(mapping.get("beats", []), start=1):
        target = (beat.get("mark_target") or "").strip()
        if not target:
            continue
        t = float(beat["t_start"])
        # 1. is the target on screen anywhere in the search window? unique match or nothing
        near = [sc for sc in screens if sc["t_end"] > t - 3.0 and sc["t"] < t + 1.5]
        if not near:
            skipped.append({"beat": n, "t": t, "target": target, "why": "no OCR screen at this time"})
            continue
        whys = [locate(sc, target)[1] for sc in near]
        if all(w is not None for w in whys):
            skipped.append({"beat": n, "t": t, "target": target, "why": whys[0]})
            continue
        # 2. geometry from the exact frame the viewer will see
        # A tap marking maps to the last instant before its screen changes, where it can
        # never hold. Look back first (the ~2s while the line says "tap X" is the right
        # place), then slightly forward, and keep the first moment that holds in full.
        best = None
        for off in (0.0, -0.5, -1.0, -1.5, -2.0, -2.5, -3.0, 0.5, 1.0, 1.5):
            c = t + off
            if c < 0:
                continue
            live, frame = ocr_frame(video, c + 0.3, tmp)
            el, why = locate(live, target)
            if el is None:
                continue
            box_c = (el["x"], el["y"], el["w"], el["h"])
            d = stable(video, c + 0.3, HOLD, box_c, tmp, label=label_for(el))
            if d and (best is None or d > best[0]):
                best = (d, c, el, frame)
            if d >= HOLD - 0.01:
                break
        if best is None:
            skipped.append({"beat": n, "t": t, "target": target,
                            "why": "no moment within 3s where the element holds 1.3s under the box"})
            continue
        dur, t, el, _ = best
        frame = grab(video, t + 0.3, tmp / "chosen.png")   # the frame actually chosen
        why = None
        if el is None:
            skipped.append({"beat": n, "t": t, "target": target,
                            "why": "on the sampled screen but not on this exact frame "
                                   "(the view moved) - needs a hand-placed marking"})
            continue
        box = (el["x"], el["y"], el["w"], el["h"])   # already in vertical-frame pixels
        if box[1] < 0 or box[1] + box[3] > CANVAS[1] or box[0] + box[2] > CANVAS[0]:
            skipped.append({"beat": n, "t": t, "target": target, "why": "outside the vertical frame"})
            continue
        pix = np.array(Image.open(frame).convert("RGB"))
        ob, opad, orad, okind, _ = (outline_for(pix, box, SCREEN) if HEADINGS is not None   # `box` stays the words
                                    else (box, sm.PAD, sm.RADIUS, "text", None))
        colour = colour_for(frame, box, ob)
        # MUST end _box.png: sa_capcut_flatten identifies call-out tracks by this
        # suffix, and Saad's 9 Sep rule is one markings track, not one per call-out.
        png = out / "layers" / f"mark_{n:03d}_box.png"
        # No chip. On desktop the chip named a small toolbar icon; here the box already
        # surrounds legible text, so a chip just prints the same words twice (proved on
        # one module's sheet, 23 Sep). The label still names the CapCut track, so every
        # marking stays findable and matches what it points at.
        if HEADINGS is not None:
            # mobile call-out: box + a heading that says what to DO (requirement, 23 Sep:
            # markings carry their small heading again, as before)
            sm.render_step_mobile(CANVAS, ob, heading_for(el), frame=pix, colour=colour,
                                  bounds=SCREEN, pad=opad, radius=orad).save(png)
        else:
            sm.render_step(CANVAS, box, "",
                           frame=np.array(Image.open(frame).convert("RGB")),
                           colour=colour).save(png)
        # dur was measured on this exact box during the search above
        # start where the hold was VERIFIED (t+0.3), not 0.3s before it - the 23 Sep
        # start/mid/end check caught two markings appearing before their button arrived
        layers.append({"file": str(png), "start": round(t + 0.3, 2), "duration": round(dur, 2),
                       "label": label_for(el), "beat": n,
                       "heading": heading_for(el) if HEADINGS is not None else "",
                       "colour": "accent" if colour[0] == sm.ACCENT_GREEN else "app",
                       "box": list(box),
                       "outline": {"box": list(ob), "pad": opad, "radius": orad, "kind": okind}})
    layers.sort(key=lambda l: l["start"])
    clean = []
    for l in layers:
        if clean and l["start"] < clean[-1]["start"] + clean[-1]["duration"]:
            clean[-1]["duration"] = round(max(sm.MIN_DUR, l["start"] - clean[-1]["start"] - 0.05), 2)
            if l["start"] < clean[-1]["start"] + clean[-1]["duration"]:
                skipped.append({"beat": l["beat"], "t": l["start"], "target": l["label"],
                                "why": "overlaps the previous marking"})
                continue
        clean.append(l)
    man = {"video": str(video), "canvas": list(CANVAS), "title": title, "layers": clean}
    (out / "_layers.json").write_text(json.dumps(man, indent=1))
    (out / "_skipped.json").write_text(json.dumps(skipped, indent=1))
    if HEADINGS is not None:
        # a marking with no written heading falls back to its button's own words - the
        # duplication Saad objected to. List them so they get a real heading.
        miss = sorted({l["label"] for l in clean if l.get("heading") == l["label"]})
        (out / "_missing_headings.json").write_text(json.dumps(miss, indent=1))
        if miss:
            print(f"   {len(miss)} marking(s) need a heading written: {miss}")
    for f in tmp.glob("*.png"):
        f.unlink()
    tmp.rmdir()
    return man, skipped


def line_word_times(lines, plan, timing):
    """Absolute time of every SCRIPT word: whisper word timestamps on each voice clip,
    aligned back to the written words, offset by the segment's start in the paced cut.
    Checked 23 Sep against the waveform: line starts land within 20-100 ms."""
    import difflib
    from faster_whisper import WhisperModel
    model = WhisperModel("small", device="cpu", compute_type="int8")
    vo = {sg["n"]: sg["vo"] for sg in plan["segments"]}
    out = []
    for seg, text in zip(timing["segments"], lines):
        S, D = seg["start"], seg["vo_dur"]
        segs, _ = model.transcribe(vo[seg["n"]], word_timestamps=True)
        heard = [(w.word, w.start) for sg in segs for w in sg.words]
        words = text.split()
        sm2 = difflib.SequenceMatcher(None, [_pn(w) for w in words], [_pn(h[0]) for h in heard])
        t = [None] * len(words)
        for a, b, n in sm2.get_matching_blocks():
            for k in range(n):
                t[a + k] = heard[b + k][1]
        for i in range(len(words)):
            if t[i] is None:
                t[i] = D * i / max(1, len(words))
        out.append([(w, S + ti) for w, ti in zip(words, t)])
    return out


def phrase_time(line_words, say):
    """When the first word of `say` is spoken in this line, or None."""
    want = _pn(say).split()
    toks = [(tk, t) for w, t in line_words for tk in _pn(w).split()]   # "I'm" -> "i", "m"
    for i in range(len(toks) - len(want) + 1):
        if [x[0] for x in toks[i:i + len(want)]] == want:
            return toks[i][1]
    return None


HEADING_KEYS = ("heading_at", "chip_at")


def heading_opts(mk):
    """A mark's heading placement from the module spec -> {key: value} for its layer.
    "heading_at": below|above|left|right (that side first); "chip_at": [x, y], the heading's
    top-left in Saad's layout. Anything else is refused: a typo must not silently do nothing."""
    out = {k: mk[k] for k in HEADING_KEYS if mk.get(k) is not None}
    if out.get("heading_at") not in (None, "below", "above", "left", "right"):
        raise SystemExit(f"heading_at must be below|above|left|right, not {out['heading_at']!r} ({mk.get('say')})")
    c = out.get("chip_at")
    if c is not None and not (isinstance(c, (list, tuple)) and len(c) == 2
                              and all(isinstance(v, (int, float)) for v in c)):
        raise SystemExit(f"chip_at must be [x, y] in Saad's layout, not {c!r} ({mk.get('say')})")
    return out


def build_voice(spec, lines, plan, timing, video, out, title):
    """Markings driven by the SCRIPT: each box goes up on the words that name it.

    23 Sep: placed from the old narrator map, 11 of 21 markings in one module were up to 4 s off
    the narrator's words. Here the trigger is the spoken phrase; the box sits on the element that
    OCR finds at that moment (unique match or nothing) and holds only while its text reads
    back from inside the box.

    Per mark (spec["marks"][i]): line, say, target, heading; optional "pick": "top" (the first of
    several identical buttons) or "bottom" (the lowest: a tab-bar button whose tile twin is
    above it), "heading_at": "below|above|left|right" and "chip_at": [x, y] (the
    heading's top-left in Saad's layout) - both carried into _layers.json for split_marks."""
    from PIL import Image
    import numpy as np
    global CANVAS
    for mk in spec["marks"]:
        heading_opts(mk)                          # refuse a bad heading_at / chip_at before any work
    CANVAS = probe_size(video)
    out = pathlib.Path(out)
    (out / "layers").mkdir(parents=True, exist_ok=True)
    tmp = out / "_frames"
    tmp.mkdir(exist_ok=True)
    words = line_word_times(lines, plan, timing)
    layers, skipped = [], []
    for n, mk in enumerate(spec["marks"], start=1):
        trig = phrase_time(words[mk["line"] - 1], mk["say"])
        if trig is None:
            skipped.append({"beat": n, "t": None, "target": mk["target"], "why": f"'{mk['say']}' not in line {mk['line']}"})
            continue
        best, seen_once, ambiguous, exact_seen = None, False, False, False
        # nearest to the word first; reaching back 2 s, because a "tap X" target is
        # usually tapped right after the word and only holds BEFORE it
        for off in (0.0, 0.25, -0.25, 0.5, -0.5, 0.75, -0.75, 1.0, -1.0, -1.5, 1.5, -2.0):
            c = trig - 0.15 + off
            if c < 0:
                continue
            live, _ = ocr_frame(video, c, tmp)
            hits = matches(live, mk["target"])       # the STATED target only - no partial
            # the element that IS the target, icon glyph aside ("V Handover" is the button)
            sq = lambda z: _pn(z).replace(" ", "")
            raw = [e for e in hits if sq(e["text"]) == sq(mk["target"])]
            exact = raw or [e for e in hits if sq(label_for(e)) == sq(mk["target"])]
            exact_seen = exact_seen or bool(exact)
            if len(hits) > 1:
                # "Parked" is also inside "3 parked now"; "XX 1 23456" also inside the header
                # line that repeats the plate. The element that IS the target wins - its raw
                # OCR text first (icon glyph included), then its text with the glyph stripped.
                if len(exact) == 1:
                    hits = exact
                elif mk.get("pick") == "top" and len(exact or hits) > 1:
                    hits = [min(exact or hits, key=lambda e: e["y"])]   # the same button on every card: the first card's
                elif mk.get("pick") == "bottom" and len(exact or hits) > 1:
                    hits = [max(exact or hits, key=lambda e: e["y"])]   # the tab-bar button (a Scan button, 25 Sep): its tile twin is above
                else:
                    ambiguous = True
            elif exact_seen and not exact:
                continue      # once the real element has shown up, never settle for a look-alike
            if len(hits) != 1:
                continue
            el = hits[0]
            seen_once = True
            box = (el["x"], el["y"], el["w"], el["h"])
            d = stable(video, c, HOLD, box, tmp, label=label_for(el))
            if d:
                best = (d, c, el, box)
                break                     # nearest workable moment to the word wins
        if best is None:
            why = ("target never uniquely on screen near the word" + (" (matches several elements)" if ambiguous else "")
                   if not seen_once else "target on screen but never held 1.3 s within -2..+1.5 s of the word")
            skipped.append({"beat": n, "t": round(trig, 2), "target": mk["target"], "why": why})
            continue
        dur, c, el, box = best
        frame = grab(video, c, tmp / "chosen.png")
        pix = np.array(Image.open(frame).convert("RGB"))
        # the outline follows the tile/button the words sit on (Saad, 24 Sep); `box` stays
        # the words, so every hold / read-back check keeps testing exactly what it did
        ob, opad, orad, okind, _ = outline_for(pix, box, SCREEN)
        colour = colour_for(frame, box, ob)
        png = out / "layers" / f"mark_{n:03d}_box.png"
        sm.render_step_mobile(CANVAS, ob, mk["heading"], frame=pix, colour=colour,
                              bounds=SCREEN, pad=opad, radius=orad, prefer=mk.get("heading_at")).save(png)
        layers.append({"file": str(png), "start": round(c, 2), "duration": round(dur, 2),
                       "label": label_for(el), "heading": mk["heading"], "beat": n,
                       "say": mk["say"], "said_at": round(trig, 2),
                       "colour": "accent" if colour[0] == sm.ACCENT_GREEN else "app",
                       "box": list(box),
                       "outline": {"box": list(ob), "pad": opad, "radius": orad, "kind": okind}})
        # per-mark heading placement from the module spec, used when split_marks draws the
        # heading in Saad's layout: "heading_at" = below|above|left|right, "chip_at" = [x, y]
        layers[-1].update(heading_opts(mk))
    layers.sort(key=lambda l: l["start"])
    clean = []
    for l in layers:                       # one markings track: no two boxes at once
        if clean and l["start"] < clean[-1]["start"] + clean[-1]["duration"]:
            clean[-1]["duration"] = round(l["start"] - clean[-1]["start"] - 0.05, 2)
            if clean[-1]["duration"] < sm.MIN_DUR:
                skipped.append({"beat": clean[-1]["beat"], "t": clean[-1]["start"],
                                "target": clean[-1]["label"], "why": "squeezed below 1.3 s by the next marking"})
                clean.pop()
        clean.append(l)
    man = {"video": str(video), "canvas": list(CANVAS), "title": title, "layers": clean}
    (out / "_layers.json").write_text(json.dumps(man, indent=1))
    (out / "_skipped.json").write_text(json.dumps(skipped, indent=1))
    for f in tmp.glob("*.png"):
        f.unlink()
    tmp.rmdir()
    return man, skipped


def add_outlines(manifest_path, out_path):
    """Give an already-built _layers.json the 24 Sep marking shape without rebuilding it:
    each marking's `outline` from the frame it starts on. `box` and timings are untouched."""
    import tempfile
    from PIL import Image
    import numpy as np
    man = json.loads(pathlib.Path(manifest_path).read_text())
    kinds = {}
    with tempfile.TemporaryDirectory() as td:
        for l in man["layers"]:
            pix = np.array(Image.open(grab(man["video"], l["start"], pathlib.Path(td) / "f.png")).convert("RGB"))
            ob, opad, orad, okind, _ = outline_for(pix, l["box"], SCREEN)
            l["outline"] = {"box": list(ob), "pad": opad, "radius": orad, "kind": okind}
            kinds[okind] = kinds.get(okind, 0) + 1
    pathlib.Path(out_path).write_text(json.dumps(man, indent=1))
    return kinds


def verify(manifest, video, ocr_bin):
    """Read back what is actually inside each drawn box, and fail the ones that do not
    contain their own label. This is the check that catches a box on the wrong row —
    the fault Saad has corrected on this series before."""
    import tempfile
    from PIL import Image
    bad = []
    with tempfile.TemporaryDirectory() as td:
        td = pathlib.Path(td)
        for l in manifest["layers"]:
            box = l["box"]
            f = grab(video, l["start"] + 0.3, td / "f.png")
            im = Image.open(f).convert("RGB")
            x, y, w, h = box
            pad = sm.PAD
            im.crop((max(0, x - pad), max(0, y - pad),
                     min(im.width, x + w + pad), min(im.height, y + h + pad))).save(td / "c.png")
            out = subprocess.run([str(ocr_bin), str(td / "c.png")],
                                 capture_output=True, text=True).stdout
            inside = " ".join(out.partition("\t")[2].split()).lower()
            norm = lambda z: " ".join("".join(c if (c.isalnum() or c == " ") else " "
                                                for c in z.lower()).split())
            key, inside = norm(l["label"])[:14], norm(inside)
            if key and key not in inside:
                bad.append({"start": l["start"], "label": l["label"], "read_inside": inside[:70]})
    return bad


def time_map(plan, timing):
    """Source-recording time -> time in an sa_dubcut paced cut.

    Inside a line's window: linear at that segment's speed. Before or after the window
    but inside its zone the recording is frozen (plan_pacing guarantees it), so the
    moment is the same frame as the window's edge and maps there."""
    keeps = plan.get("keeps")

    def tight(u):                     # original source time -> time in the fault-cut source
        if not keeps:
            return u
        acc = 0.0
        for a, b in keeps:
            if u < a:
                return acc
            if u <= b:
                return acc + (u - a)
            acc += b - a
        return acc

    T = {x["n"]: x for x in timing["segments"]}
    segs = []
    for sg in plan["segments"]:
        ts = T[sg["n"]]
        za, zb = sg.get("zone", sg["src"])
        segs.append((za, zb, sg["src"][0], sg["src"][1], ts["start"], ts["speed"], ts["picture_dur"]))

    def f(t):
        for i, (za, zb, w0, w1, S, k, P) in enumerate(segs):
            if za <= t < zb or (i == len(segs) - 1 and t >= zb):
                te = min(max(t, w0), w1)
                return round(S + min((tight(te) - tight(w0)) / k, P - 0.05), 3)
        return round(segs[0][4], 3)
    return f


def remap(mapping, screens, f):
    """Move a map's beats and a screen read into paced time."""
    m2 = dict(mapping)
    m2["beats"] = [dict(b, t_start=f(b["t_start"]), t_end=f(b.get("t_end", b["t_start"])))
                   for b in mapping.get("beats", [])]
    s2 = []
    for sc in screens:
        a, b = f(sc["t"]), f(sc["t_end"] - 0.001)
        if b > a:
            s2.append(dict(sc, t=a, t_end=b + 0.001))
    return m2, s2


def _test():
    assert to_canvas({"x": 0, "y": 130, "w": 1206, "h": 100}) == (0, 0, 1080, 90)
    assert to_canvas({"x": 100, "y": 50, "w": 10, "h": 10}) is None, "status bar must be refused"
    assert to_canvas({"x": 0, "y": 2500, "w": 10, "h": 60}) is None, "below the trim must be refused"
    mid = to_canvas({"x": 791, "y": 1820, "w": 229, "h": 45})
    assert mid == (708, 1513, 205, 40), mid   # (1820-130)*0.895522 = 1513.4
    scr = [{"t": 0.0, "t_end": 3.0}, {"t": 3.0, "t_end": 9.0}]
    assert screen_at(scr, 4.0)["t_end"] == 9.0 and screen_at(scr, 99) is None
    assert label_for({"text": "View team breakdown ›"}) == "View team breakdown"
    assert label_for({"text": "1 I'm Here"}) == "I'm Here", label_for({"text": "1 I'm Here"})
    assert label_for({"text": "Add Photo"}) == "Add Photo"
    lw = [("Tap", 1.0), ("the", 1.2), ("job", 1.4), ("you", 1.6)]
    assert phrase_time(lw, "the job") == 1.2 and phrase_time(lw, "tap I'm") is None
    assert phrase_time([("tap", 5.0), ("I'm", 5.2), ("Here.", 5.5)], "tap I'm Here") == 5.0
    scr3 = {"elements": [{"text": "Collect \u2022 Bay F1-030", "x": 1, "y": 9, "w": 5, "h": 5},
                         {"text": "Main Car Park \u00b7 1st Floor \u00b7 Bay F1-030", "x": 1, "y": 50, "w": 5, "h": 5}]}
    assert locate(scr3, "Collect \u00b7 Bay F1-030")[0]["y"] == 9, "punctuation-blind, full target first"
    scr2 = {"elements": [
        {"text": "REF-1001 Item K8 55 DELUXE", "x": 1, "y": 200, "w": 5, "h": 5},
        {"text": "REF-1002 Item K6 45 DELUXE", "x": 1, "y": 400, "w": 5, "h": 5}]}
    hit, _ = locate(scr2, "the 'READY FOR REVIEW — REF-1001 • Item K8 55 DELUXE' card")
    assert hit and hit["y"] == 200, "quoted phrase must pick the right card"
    miss, why = locate(scr2, "the DELUXE card")
    assert miss is None and why, "an unquoted generic word must be refused, not guessed"
    miss2, why2 = locate(scr2, "the 'F1-028' row")
    assert miss2 is None and "not on screen" in why2, why2
    plan = {"segments": [{"n": 1, "src": [0.0, 4.0], "zone": [0.0, 10.0]},
                         {"n": 2, "src": [12.0, 16.0], "zone": [10.0, 20.0]}]}
    timing = {"segments": [{"n": 1, "start": 0.0, "speed": 1.0, "picture_dur": 5.0},
                           {"n": 2, "start": 5.0, "speed": 2.0, "picture_dur": 3.0}]}
    f = time_map(plan, timing)
    assert f(2.0) == 2.0, f(2.0)        # inside window 1, speed 1
    assert f(8.0) == 4.0, f(8.0)        # frozen tail of zone 1 -> window 1 end
    assert f(11.0) == 5.0, f(11.0)      # frozen head of zone 2 -> window 2's start
    assert f(14.0) == 6.0, f(14.0)      # inside window 2 at 2x
    plan["keeps"] = [[0.0, 2.0], [3.0, 20.0]]  # a 1s fault cut out at 2-3s
    f = time_map(plan, timing)
    assert f(1.0) == 1.0 and f(3.5) == 2.5, (f(1.0), f(3.5))  # after the cut, 1s earlier
    _test_shape()
    print("ok")


def _test_shape():
    """element_box on a drawn screen: the app's own page / card / border colours."""
    from PIL import Image, ImageDraw
    import numpy as np
    im = Image.new("RGB", (600, 1200), (246, 246, 242))
    d = ImageDraw.Draw(im)

    def words(x, y, w, h):                        # glyph-like bars, inside their box
        for i in range(x, x + w - 5, 9):
            d.rectangle([i, y, i + 5, y + h - 1], fill=(20, 20, 20))
    d.rounded_rectangle([40, 100, 290, 260], radius=20, fill=(253, 255, 253), outline=(223, 223, 219), width=2)
    words(60, 220, 100, 16)                                   # a tile's caption
    words(60, 400, 140, 14)                                   # a heading on the page
    words(60, 578, 140, 14); words(60, 600, 140, 14)          # two lines 8px apart
    d.rounded_rectangle([40, 700, 560, 1000], radius=20, fill=(253, 255, 253), outline=(223, 223, 219), width=2)
    words(60, 720, 120, 14)                                   # one line in a big card
    d.rectangle([0, 1110, 599, 1199], fill=(253, 255, 253))   # the tab bar
    d.rectangle([282, 1122, 308, 1148], fill=(90, 90, 90)); words(270, 1162, 50, 14)
    a = np.array(im)
    box, rad, kind, _ = element_box(a, (60, 220, 100, 16))
    assert kind == "element" and all(abs(p - q) <= 3 for p, q in zip(box, (42, 102, 247, 157))), (box, kind)
    assert 14 <= rad <= 24, rad                               # its own corners, not a default
    box, _, kind, why = element_box(a, (60, 400, 140, 14))
    assert kind == "text" and "edge" in why and box[3] >= round(MIN_H * 1200), (box, why)
    box, _, kind, _ = element_box(a, (60, 600, 140, 14))
    assert kind == "text" and box[1] >= 594, box              # never grows over the line above
    box, _, kind, why = element_box(a, (60, 720, 120, 14))
    assert kind == "text" and "panel" in why, why             # a card of rows is not the target
    box, _, kind, _ = element_box(a, (270, 1162, 50, 14))
    assert kind == "tab" and box[1] <= 1122 < 1162 <= box[1] + box[3], box   # label + its icon
    # sizes are fractions of the screen: the same screen at his 0.716 layout finds the same tile
    s = 0.716
    small = np.array(im.resize((round(600 * s), round(1200 * s)), Image.LANCZOS))
    box, _, kind, _ = element_box(small, tuple(round(v * s) for v in (60, 220, 100, 16)))
    assert kind == "element" and all(abs(p - q * s) <= 4 for p, q in zip(box, (42, 102, 247, 157))), box
    # a bottom tab's outline stays on the screen, not over the phone frame (03_016 / 04_016)
    words(400, 1185, 60, 12)
    a = np.array(im)
    box, pad, _, kind, _ = outline_for(a, (400, 1185, 60, 12), (0, 0, 600, 1200))
    assert box[1] + box[3] + pad <= 1200 and box[0] >= pad, (box, pad)
    # a dark button on video noise: the grown colour goes ragged, and read its 22px corners
    # as 34, so the outline cut them (Approve, 01_033 - verified 24 Sep); its TRUE edge counts
    big = Image.new("RGB", (2400, 1600), (246, 246, 242))
    ImageDraw.Draw(big).rounded_rectangle([800, 400, 1919, 759], radius=88, fill=(46, 125, 50))
    b = np.array(big.resize((600, 400), Image.BOX)).astype(float)
    b = np.clip(b + np.random.default_rng(1).normal(0, 3.5, b.shape), 0, 255).astype(np.uint8)
    for i in range(265, 400, 9):
        b[135:151, i:i + 5] = 250                                  # its white label
    box, rad, kind, _ = element_box(b, (265, 135, 135, 16))
    assert kind == "element" and all(abs(p - q) <= 2 for p, q in zip(box, (200, 100, 280, 90))), box
    assert 18 <= rad <= 26, rad
    # colour: the outline sits on the pale page, but the target is itself green -> accent
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        pb, pa = pathlib.Path(td) / "b.png", pathlib.Path(td) / "a.png"
        Image.fromarray(b).save(pb); im.save(pa)
        assert colour_for(pb, (265, 135, 135, 16), box)[0] == sm.ACCENT_GREEN
        tile = outline_for(a, (60, 220, 100, 16))[0]
        assert colour_for(pa, (60, 220, 100, 16), tile)[0] == sm.APP_GREEN
    global SHAPE
    SHAPE, old = "text", SHAPE
    assert outline_for(a, (60, 220, 100, 16))[:3] == ((60, 220, 100, 16), 12, 18), "--text-box = old strip"
    SHAPE = old
    # per-mark heading placement is carried into the layer; nothing added when absent; typos refused
    assert heading_opts({"say": "x"}) == {}
    assert heading_opts({"say": "x", "heading_at": "below", "chip_at": [300, 900]}) == \
        {"heading_at": "below", "chip_at": [300, 900]}
    for bad in ({"heading_at": "under"}, {"chip_at": [1]}, {"chip_at": "300,900"}):
        try:
            heading_opts(dict(bad, say="x"))
            raise AssertionError(f"accepted {bad}")
        except SystemExit:
            pass


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--id"); p.add_argument("--map"); p.add_argument("--read")
    p.add_argument("--video"); p.add_argument("--out"); p.add_argument("--title", default="")
    p.add_argument("--plan"); p.add_argument("--timing")
    p.add_argument("--marks", help="voice-anchored marking spec json (needs --lines, --plan, --timing)")
    p.add_argument("--lines", help="the written script, one line per voice clip")
    p.add_argument("--headings", help="json of element text -> heading; turns on the mobile call-out")
    p.add_argument("--text-box", action="store_true",
                   help="old marking shape: a strip round the OCR words, not the element")
    p.add_argument("--add-outlines", metavar="LAYERS_JSON",
                   help="write the element outline into a built _layers.json (to --out, else in place)")
    p.add_argument("--test", action="store_true")
    a = p.parse_args()
    if a.text_box:
        SHAPE = "text"
    if a.test:
        _test()
    elif a.add_outlines:
        import sa_phoneframe as _pf
        _g = _pf.geometry()["screen"]
        SCREEN = (_g[0], _g[1], _g[0] + _g[2], _g[1] + _g[3])
        print(add_outlines(a.add_outlines, a.out or a.add_outlines))
    else:
        if a.marks:
            import sa_phoneframe as _pf
            _g = _pf.geometry()["screen"]
            SCREEN = (_g[0], _g[1], _g[0] + _g[2], _g[1] + _g[3])
            man, skipped = build_voice(json.loads(pathlib.Path(a.marks).read_text()),
                                       pathlib.Path(a.lines).read_text().strip().split("\n"),
                                       json.loads(pathlib.Path(a.plan).read_text()),
                                       json.loads(pathlib.Path(os.path.expanduser(a.timing)).read_text()),
                                       os.path.expanduser(a.video), a.out, a.title)
            print(f"{a.id}: {len(man['layers'])} voice-anchored markings, {len(skipped)} skipped -> {a.out}")
            raise SystemExit(0)
        mapping = json.loads(pathlib.Path(a.map).read_text())
        if a.headings:
            HEADINGS = {k: v for k, v in json.loads(pathlib.Path(a.headings).read_text()).items()
                        if not k.startswith("_")}
            import sa_phoneframe as _pf
            _g = _pf.geometry()["screen"]
            SCREEN = (_g[0], _g[1], _g[0] + _g[2], _g[1] + _g[3])
        screens = json.loads(pathlib.Path(a.read).read_text())["screens"]
        if a.plan and a.timing:
            f = time_map(json.loads(pathlib.Path(a.plan).read_text()),
                         json.loads(pathlib.Path(os.path.expanduser(a.timing)).read_text()))
            mapping, screens = remap(mapping, screens, f)
        man, skipped = build(mapping, screens, os.path.expanduser(a.video), a.out, a.title)
        print(f"{a.id}: {len(man['layers'])} markings placed, {len(skipped)} skipped -> {a.out}")
