"""Split each marking into two CapCut layers — the box and its heading — in Saad's layout.

    sa_capcut_split_marks.py <tag> "<CapCut project name>"    e.g. 01_Intro "Mobile App 01 Intro"
    sa_capcut_split_marks.py --test
    [--wait]  draw while CapCut is open, write once it is closed

Inputs: SA_MOBILE_DIR (the series working folder: LAYERS/, BUILD_P/) and SA_APP_STYLE (the
approved app placement exported from CapCut; without it the scale/lift below are used).

Requirement (24 Sep): markings and their heading text must be separate layers, so the boxes can
be adjusted on their own. Until now each marking was one PNG (box + heading chip). This redraws every marking
as mark_NNN_box.png (outline only) and mark_NNN_label.png (heading chip only) and puts them on two
tracks, "Markings" and "Marking headings", with the SAME timing as the project's own segments
(his hand-nudged start times are kept).

It also moves every marking into HIS layout: he scaled the app 0.7159 and lifted it 0.1148
(the approved style file), so a box drawn for the old app position sits in the wrong place and at
the wrong size. Boxes are mapped through exactly the transform CapCut applies to the app layer.

Refuses while CapCut is open; backs the project up first; validates every reference afterwards.

Build rules (24 Sep, from a QA pass against his approved reference module):
  HEADINGS NEVER ON TEXT  every marking's frames (start / middle / end) are OCR'd and the text
      boxes mapped into his layout; the pill goes in the nearest slot that overlaps none of
      them (sa_stepmark.place_heading), else the least overlap that never covers the target's
      own words. Per mark, from the module spec via _layers.json: "heading_at":
      "below|above|left|right" (that side first) or "chip_at": [x, y] (pill top-left, his layout).
  BOXES NEVER CLIP LETTERS OR CUT A NEIGHBOUR  a words-only outline gets WORDS_PAD so the stroke
      (drawn INSIDE the edge) clears the glyphs, built from the union of the OCR words and the
      detected glyph box; an edge that would run through a neighbouring text line shrinks away
      from it (MIN_AIR off the target when the gap allows, else >= 1 px of air on both sides),
      and when the gap is too small even for that it grows to take the line in (a stacked
      label / value, the QA's own fix for '90% PLAN') (fit_box). An element outline only
      ever shrinks its gap.
  The run prints "?? heading" / "?? edge" lines for anything still touching text.
"""
import copy, glob, hashlib, json, os, pathlib, re, shutil, subprocess, sys, time, uuid

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import sa_stepmark as sm                                     # noqa: E402
from PIL import Image, ImageDraw, ImageFilter                 # noqa: E402
import numpy as np                                            # noqa: E402

D = pathlib.Path(os.path.expanduser(os.environ.get("SA_MOBILE_DIR", "~/Downloads/training-series/mobile_app")))
CAP = pathlib.Path(os.path.expanduser("~/Movies/CapCut/User Data/Projects/com.lveditor.draft"))
STYLE_FILE = pathlib.Path(os.path.expanduser(os.environ.get("SA_APP_STYLE", str(D / "app_style.json"))))
APP = (json.load(open(STYLE_FILE))["layers"]["app"]["clip"] if STYLE_FILE.exists()
       else {"scale": {"x": 0.7159}, "transform": {"y": 0.1148}})   # his approved placement
S, TY = APP["scale"]["x"], APP["transform"]["y"]
W, H = 1080, 1920
SCREEN = (107, 96, 866, 1728)                                 # the app inside L4, before his transform
PAD, R, STROKE = 12, 18, 6                                    # same outline as render_step_mobile
MIN_H = 30          # his layout: most words-only boxes already are 29-30 px; small caps labels were 11-20
# The stroke is drawn INSIDE the outline's edge, so the old words-only gap (outline pad 10 x 0.716
# = 7) left 1 px between stroke and glyphs, and the glow sat on the letters ('L' of Weekly Target,
# QA 24 Sep). WORDS_PAD = stroke + 5 px of air.
WORDS_PAD = STROKE + 5
MIN_AIR = 3          # px the stroke's inner edge prefers off the glyphs when pulled in from a neighbour
EDGE_OUT = 2         # the stroke's anti-aliased outer edge
EL_MIN_PAD = STROKE - 2   # an element outline may pull in until the stroke meets the element's rim
MIN_OUTER_H = MIN_H + 2 * max(6, round(10 * S))   # the old words-only floor (30 + its 7 px gap), outer edge
GROW_MAX = 4.5       # a words box may take in neighbour lines up to this many times its own height


def to_canvas(box):
    """L4 app-layer box -> final canvas box under his app transform (scale about the centre, then lift)."""
    x, y, w, h = box
    cx, cy = W / 2 + (x - W / 2) * S, (H / 2 - TY * H / 2) + (y - H / 2) * S
    return (round(cx), round(cy), round(w * S), round(h * S))


TMP = pathlib.Path(os.environ.get("TMPDIR", "/tmp")) / f"split_marks_{os.getpid()}"


def l4_frame(tag, t):
    """The L4 app layer (1080x1920, the app at SCREEN) at timeline time t -> png path."""
    TMP.mkdir(parents=True, exist_ok=True)
    tmp = TMP / f"{tag}_{t:.3f}.png"
    if not tmp.exists():
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i",
                        str(D / "LAYERS" / tag / f"L4_app_{tag}.mp4"), "-frames:v", "1", str(tmp)], check=True)
    return tmp


def ocr_texts(png):
    """OCR text boxes (x, y, w, h, text) of an L4 frame, in L4 pixels."""
    from sa_appread import parse_elements
    out = subprocess.run([str(HERE / "bin" / "sa_ocr"), "--boxes", str(png)], capture_output=True, text=True).stdout
    return [(e["x"], e["y"], e["w"], e["h"], e["text"]) for e in parse_elements(out.partition("\t")[2].strip())
            if e.get("x") is not None and e["w"] > 0 and e["h"] > 0]


_OCR = {}


def ink_box(a, box):
    """An OCR box shrunk to the glyphs actually drawn in it (a: canvas RGB array). Vision's boxes
    carry a few px of slack, and on a tight list that slack is the whole gap between two lines.
    Background = the median of the box's rim; ink = pixels far from it. No ink -> the box."""
    x, y, w, h = box
    x0, y0 = max(0, x - 2), max(0, y - 2)
    x1, y1 = min(a.shape[1], x + w + 2), min(a.shape[0], y + h + 2)
    p = a[y0:y1, x0:x1].astype(int)
    if p.shape[0] < 3 or p.shape[1] < 3:
        return tuple(box)
    bg = np.median(np.concatenate([p[0], p[-1], p[:, 0], p[:, -1]]), axis=0)
    ys, xs = np.nonzero(np.abs(p - bg).max(axis=2) > 48)
    if ys.size < 4:
        return tuple(box)
    return (int(x0 + xs.min()), int(y0 + ys.min()), int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1))


def canvas_texts(tag, t):
    """Every OCR text box on the app at timeline time t, mapped into HIS layout (only those on
    the phone screen) and shrunk to its ink -> [(x, y, w, h, text)]."""
    key = (tag, round(t, 2))
    if key not in _OCR:
        sx0, sy0, sw, sh = SCREEN
        a = np.asarray(app_frame(tag, t))
        _OCR[key] = [ink_box(a, to_canvas((x, y, w, h))) + (txt,) for x, y, w, h, txt in ocr_texts(l4_frame(tag, t))
                     if sx0 <= x + w / 2 <= sx0 + sw and sy0 <= y + h / 2 <= sy0 + sh]
    return _OCR[key]


def app_frame(tag, t):
    """The app as it appears on HIS canvas at timeline time t (for chip placement + checks)."""
    im = Image.open(l4_frame(tag, t)).convert("RGB")
    small = im.resize((round(W * S), round(H * S)), Image.LANCZOS)
    canvas = Image.new("RGB", (W, H), (0, 0, 0))
    canvas.paste(small, (round(W / 2 - small.width / 2), round(H / 2 - TY * H / 2 - small.height / 2)))
    return canvas


def draw_box(box, colour, pad=PAD, radius=R):
    x, y, w, h = box
    return draw_rect((x - pad, y - pad, x + w + pad, y + h + pad), colour, radius)


def draw_rect(rect, colour, radius=R):
    """The outline alone, its OUTER edge at rect (x0, y0, x1, y1); the stroke lies inside it."""
    line, _soft = colour
    x0, y0, x1, y1 = rect
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    halo = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(halo).rounded_rectangle([x0 - 4, y0 - 4, x1 + 4, y1 + 4], radius=radius + 4,
                                           outline=line[:3] + (170,), width=STROKE + 6)
    img = Image.alpha_composite(img, halo.filter(ImageFilter.GaussianBlur(7)))
    ImageDraw.Draw(img).rounded_rectangle([x0, y0, x1, y1], radius=radius, outline=line, width=STROKE)
    return img


def draw_label(box, heading, colour, frame, bounds, pad=PAD, radius=R, texts=None, own=(),
               prefer=None, chip_at=None, want_chip=False):
    """The heading chip alone: render the full call-out, keep only the chip layers.
    render_step_mobile decides WHERE the chip goes (beside the box, never on it); the chip is
    drawn after the box, so rendering once with and once without the heading isolates it.
    texts = the frame's OCR boxes in his layout, (x, y, w, h[, weight]): the chip then never sits on
    text (24 Sep), and when it must, it covers the lightest (text_weights);
    prefer / chip_at = the spec's "heading_at" / "chip_at". Without them: the old placement."""
    kw = dict(frame=np.array(frame), colour=colour, bounds=bounds, pad=pad, radius=radius)
    full, chip = sm.render_step_mobile((W, H), box, heading, want_chip=True, prefer=prefer, chip_at=chip_at,
                                       obstacles=None if texts is None else
                                       [tuple(t[:4]) + ((t[4],) if len(t) > 4 and not isinstance(t[4], str) else ())
                                        for t in texts],
                                       own=[t[:4] for t in own], **kw)
    bare = sm.render_step_mobile((W, H), box, None, **kw)
    a, b = np.array(full).astype(int), np.array(bare).astype(int)
    diff = np.abs(a - b).sum(axis=2) > 6
    out = np.zeros_like(a)
    out[diff] = a[diff]
    img = Image.fromarray(out.astype("uint8"))
    return (img, chip) if want_chip else img


def _union(a, b):
    return (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))


def _xyxy(b):
    return (b[0], b[1], b[0] + b[2], b[1] + b[3])


def _hits(a, b):
    return min(a[2], b[2]) > max(a[0], b[0]) and min(a[3], b[3]) > max(a[1], b[1])


def crosses(rect, t, slack=EDGE_OUT):
    """Does the outline whose outer edge is `rect` run through text box t (x0, y0, x1, y1)?
    The stroke band is the rect's edge (plus `slack` px of anti-aliasing) down to STROKE inside
    it; text wholly inside the stroke's inner edge, or wholly outside, is untouched."""
    x0, y0, x1, y1 = rect
    outer = (x0 - slack, y0 - slack, x1 + slack, y1 + slack)
    inner = (x0 + STROKE + 1, y0 + STROKE + 1, x1 - STROKE - 1, y1 - STROKE - 1)
    inside = inner[0] <= t[0] and inner[1] <= t[1] and t[2] <= inner[2] and t[3] <= inner[3]
    return _hits(outer, t) and not inside


def own_texts(words, texts):
    """The target's own OCR text: boxes lying mostly inside its words box."""
    g = _xyxy(words)
    out = []
    for t in texts:
        r = _xyxy(t)
        a = max(1, (r[2] - r[0]) * (r[3] - r[1]))
        ov = max(0, min(r[2], g[2] + 4) - max(r[0], g[0] - 4)) * max(0, min(r[3], g[3] + 4) - max(r[1], g[1] - 4))
        if ov >= 0.5 * a:
            out.append(t)
    return out


def fit_box(words, drawn, kind, pad, texts, bounds):
    """Where the outline's OUTER edge goes -> ((x0, y0, x1, y1), taken_in, unresolved).

    words   the OCR words box (x, y, w, h), his layout
    drawn   what outline_for chose: the element, or the box hugging the glyphs (his layout)
    kind    "element" | "text" | "tab"
    pad     the element's gap (words-only outlines use WORDS_PAD instead)
    texts   OCR text boxes (x, y, w, h, ...) on the marking's frames, his layout
    bounds  the phone screen (x0, y0, x1, y1): the outline stays on it

    Words-only: the edge sits WORDS_PAD outside the union of the OCR words and the glyph box, so
    the stroke clears the letters, and is never shorter than MIN_OUTER_H. Then, for every
    neighbouring text line the stroke would run through: pull that side in - with MIN_AIR off the
    target's glyphs when the gap allows, else squeezed into the gap with at least 1 px of air on
    BOTH sides (a gap of STROKE + 2); when not even that fits, take the neighbour in - a line
    stacked on the target (label / value: the QA fix for '90% PLAN' 7 px under 'GAP - TARGET
    AT') or the rest of its row - up to GROW_MAX times the words' height, at most two lines,
    never a cascade across the screen. (Taking a line in whenever the air is short was tried and
    rejected, 24 Sep: on the real builds it swallowed greetings and names into 11 more boxes.)
    An element or tab outline only pulls its gap in (a tab's neighbours are the other tabs).
    What cannot be cleared is returned."""
    wr = _xyxy(words)
    el = kind == "element"
    mine = [t for t in own_texts(words, texts)]
    ink = _xyxy(drawn)                                        # the glyphs (or the element)
    if not el:
        for t in mine:
            ink = _union(ink, _xyxy(t))
    core = ink if el else _union(wr, ink)                     # inside the stroke, with its gap
    p = pad if el else WORDS_PAD
    R = [core[0] - p, core[1] - p, core[2] + p, core[3] + p]
    if not el and R[3] - R[1] < MIN_OUTER_H:                 # never a sliver: grow evenly
        g = MIN_OUTER_H - (R[3] - R[1])
        R[1] -= g // 2
        R[3] += g - g // 2
    need = EL_MIN_PAD if el else STROKE + MIN_AIR             # the gap a pulled-in side prefers
    others = []
    mset = {tuple(t[:4]) for t in mine}
    for t in texts:
        r = _xyxy(t)
        if tuple(t[:4]) not in mset and r not in others:
            others.append(r)
    taken, left = [], []
    h0, w0 = max(1, wr[3] - wr[1], ink[3] - ink[1]), max(1, core[2] - core[0])

    def pull(sd, t):
        """Move one side of R off neighbour t: EDGE_OUT + 1 px clear of it when the stroke then
        still keeps `need` off the target's ink, else the stroke centred in the gap when that
        leaves >= 1 px of air on both sides. -> True when done."""
        lo = {"top": t[3], "left": t[2]}.get(sd)              # neighbour's near edge
        hi = {"bottom": t[1], "right": t[0]}.get(sd)
        k = {"top": 1, "bottom": 3, "left": 0, "right": 2}[sd]
        c = ink[k]
        gap = c - lo if lo is not None else hi - c
        sgn = 1 if lo is not None else -1                    # neighbour before / after the target
        edge = lo if lo is not None else hi
        if gap - (EDGE_OUT + 1) >= need:
            R[k] = edge + sgn * (EDGE_OUT + 1)
        elif gap >= STROKE + 2:
            R[k] = edge + sgn * max(1, (gap - STROKE) // 2)
        else:
            return False
        return True

    for _ in range(16):
        cut = [t for t in others if crosses(R, t)]
        if not cut:
            break
        t = min(cut, key=lambda r: max(0, r[1] - ink[3], ink[1] - r[3]) + max(0, r[0] - ink[2], ink[0] - r[2]))
        room, sd = max((ink[1] - t[3], "top"), (t[1] - ink[3], "bottom"),
                       (ink[0] - t[2], "left"), (t[0] - ink[2], "right"))
        others.remove(t)
        if room > 0 and pull(sd, t):                          # it lies outside the target: pull away
            continue
        # no room for the stroke between them: take it in - a line stacked on the target (its
        # label / value) or the rest of its row, never a cascade across the screen
        nc = _union(ink, t)
        row = sd in ("left", "right") and min(ink[3], t[3]) - max(ink[1], t[1]) >= 0.5 * min(h0, t[3] - t[1])
        ok = (kind == "text" and len(taken) < 2 and nc[3] - nc[1] <= GROW_MAX * h0
              and nc[2] - nc[0] <= max(2.2 * w0, w0 + 180) and (sd in ("top", "bottom") or room <= 0 or row))
        if ok:
            ink, core = nc, _union(core, t)
            R = [min(R[0], t[0] - WORDS_PAD), min(R[1], t[1] - WORDS_PAD),
                 max(R[2], t[2] + WORDS_PAD), max(R[3], t[3] + WORDS_PAD)]
            if R[3] - R[1] > MIN_OUTER_H:                     # tall enough now: drop the sliver
                R[3] = max(min(R[3], core[3] + WORDS_PAD), R[1] + MIN_OUTER_H)   # floor's growth
                R[1] = min(max(R[1], core[1] - WORDS_PAD), R[3] - MIN_OUTER_H)   # (pulls stay)
            taken.append(t)
        else:
            left.append(t)
    bx0, by0, bx1, by1 = bounds
    R = (max(R[0], bx0 + 1), max(R[1], by0 + 1), min(R[2], bx1 - 1), min(R[3], by1 - 1))
    left = [t for t in left if crosses(R, t, 0)]
    return tuple(int(round(v)) for v in R), taken, left


def heading_hits(chip, texts):
    """OCR texts a drawn heading pill [x, y, w, h] overlaps -> [text]."""
    if not chip:
        return []
    c = (chip[0], chip[1], chip[0] + chip[2], chip[1] + chip[3])
    return [t[4] if len(t) > 4 else str(t[:4]) for t in texts if _hits(c, _xyxy(t))]


_w = lambda z: {x for x in re.findall(r"[a-z0-9]+", z.lower()) if len(x) >= 3 or x.isdigit()}


def text_weights(texts, spoken):
    """How bad it is for a heading to cover each text, when it must cover something: words the
    voice says in this line 4, figures 2, anything else 1 (QA 24 Sep: put it 'over the Opened
    label, which the voice does not name')."""
    said = _w(spoken)
    return [4 if _w(t[4]) & said else 2 if re.search(r"\d", t[4]) else 1 for t in texts]


def spoken_line(tag, layer):
    """The script line a marking belongs to (its layer's 'beat' -> <tag>_marks.json -> <tag>_lines.txt);
    its 'say' words when the script files are not there."""
    here = pathlib.Path(__file__).resolve().parent
    try:
        mk = json.load(open(here / f"{tag}_marks.json"))["marks"][layer["beat"] - 1]
        return (here / f"{tag}_lines.txt").read_text().strip().split("\n")[mk["line"] - 1]
    except Exception:
        return layer.get("say", "")


def marking_texts(tag, words, times):
    """The text on screen while a marking is up (his layout), from the frames at `times`. A frame
    where the target is no longer at its box (the screen moved under it) is left out and its
    time returned: its text is not what sits round the box. -> (texts, [moved times])."""
    keep, moved = [], []
    frames = [(tt, canvas_texts(tag, tt)) for tt in times]
    for tt, tx in frames:
        (keep if own_texts(words, tx) else moved).append((tt, tx))
    if not keep:                                             # OCR missed it everywhere: use all
        keep, moved = frames, []
    return _dedupe([x for _tt, tx in keep for x in tx]), [tt for tt, _tx in moved]


def _dedupe(texts):
    out = []
    for t in texts:
        if not any(abs(t[0] - u[0]) <= 3 and abs(t[1] - u[1]) <= 3 and abs(t[2] - u[2]) <= 3
                   and abs(t[3] - u[3]) <= 3 for u in out):
            out.append(t)
    return out


def colour_of(layer):
    return ((sm.ACCENT_GREEN, sm.ACCENT_GREEN_SOFT) if layer.get("colour") == "accent"
            else (sm.APP_GREEN, sm.APP_GREEN_SOFT))


def render(tag, starts, folder="layers_split"):
    """-> {NNN: (box_png, label_png, text_box, label, t, info)} for every marking, drawn in his layout
    (info: mark_one's findings - heading_on / edge_through / took_in / screen_moved_at).
    With _layers_outlines.json (sa_appbuild --add-outlines) the box outlines the whole element
    (tile, button, row), a proper shape as required on 24 Sep - scaled into his layout with it."""
    src = D / "BUILD_P" / tag / "_layers_outlines.json"
    layers = json.load(open(src if src.exists() else D / "BUILD_P" / tag / "_layers.json"))["layers"]
    out = D / "BUILD_P" / tag / folder
    out.mkdir(exist_ok=True)
    bounds = to_canvas(SCREEN)
    bounds = (bounds[0], bounds[1], bounds[0] + bounds[2], bounds[1] + bounds[3])
    done = {}
    for l in layers:
        n = re.search(r"mark_(\d+)_box", l["file"]).group(1)
        m = mark_one(tag, l, starts.get(n, l["start"]), bounds)
        bp, lp = out / f"mark_{n}_box.png", out / f"mark_{n}_label.png"
        m["box_img"].save(bp)
        m["label_img"].save(lp)
        done[n] = (bp, lp, m["words"], l["label"], m["t"], m["info"])
    return done


def mark_one(tag, l, t0, bounds):
    """One marking in his layout: its outline and heading images, and what they sit next to.
    t0 = when it starts on the timeline (his project's start when known)."""
    box = to_canvas(l["box"])                                  # the words: read-back check
    o = l.get("outline")
    ob = to_canvas(o["box"]) if o else box                     # the element, or the glyphs
    kind = o["kind"] if o else "text"
    pad, rad = (max(6, round(o["pad"] * S)), max(8, round(o["radius"] * S))) if o else (PAD, R)
    t = t0 + 0.3
    dur = float(l.get("duration") or 2.0)
    # the text on screen while the marking is up: its start, middle and end frames
    texts, moved = marking_texts(tag, box, (t, t0 + dur / 2, t0 + max(0.4, dur - 0.2)))
    rect, taken, left = fit_box(box, ob, kind, pad, texts, bounds)
    wts = text_weights(texts, spoken_line(tag, l) + " " + l.get("say", ""))
    frame = app_frame(tag, t)
    own = own_texts(box, texts) + [(r[0], r[1], r[2] - r[0], r[3] - r[1]) for r in taken]
    img, chip = draw_label((rect[0], rect[1], rect[2] - rect[0], rect[3] - rect[1]), l["heading"],
                           colour_of(l), frame, bounds, 0, rad, texts=[tx[:4] + (w,) for tx, w in zip(texts, wts)],
                           own=own, prefer=l.get("heading_at"), chip_at=l.get("chip_at"), want_chip=True)
    name = lambda r: next((x[4] for x in texts if _xyxy(x) == r), str(r))
    info = {"rect": rect, "chip": chip, "heading_on": heading_hits(chip, texts),
            "edge_through": [name(r) for r in left], "took_in": [name(r) for r in taken],
            "screen_moved_at": [round(x, 2) for x in moved], "kind": kind, "radius": rad,
            "texts": texts, "own": own}
    return {"words": box, "t": t, "info": info, "frame": frame,
            "box_img": draw_rect(rect, colour_of(l), rad), "label_img": img}


def check(tag, done):
    """Every box must still read its own element in HIS layout (local OCR, spacing-blind)."""
    ocr = str(HERE / "bin" / "sa_ocr")
    bad = []
    for n, (_bp, _lp, (x, y, w, h), label, t, *_i) in sorted(done.items()):
        fr = app_frame(tag, t)
        TMP.mkdir(parents=True, exist_ok=True)
        crop = TMP / "_c.png"
        fr.crop((max(0, x - 8), max(0, y - 8), x + w + 8, y + h + 8)).resize(
            (round((w + 16) / S), round((h + 16) / S))).save(crop)
        txt = subprocess.run([ocr, str(crop)], capture_output=True, text=True).stdout.partition("\t")[2]
        key = re.sub(r"[^a-z0-9]", "", label.lower())[:10]
        if key not in re.sub(r"[^a-z0-9]", "", txt.lower()):
            bad.append((n, label, txt.strip()[:40]))
    return bad


def new_id():
    return str(uuid.uuid4()).upper()


def patch(draft, done):
    """Markings -> box PNGs at transform 0; add a 'Marking headings' track right above it."""
    mats = {m["id"]: (k, m) for k, v in draft["materials"].items() if isinstance(v, list)
            for m in v if isinstance(m, dict) and "id" in m}
    ti = next(i for i, t in enumerate(draft["tracks"]) if t.get("name") == "Markings")
    track = draft["tracks"][ti]
    heads = {"id": new_id(), "type": track["type"], "flag": track.get("flag", 0), "attribute": 0,
             "name": "Marking headings", "is_default_name": False, "segments": []}
    top_ri = max((s.get("render_index", 0) for t in draft["tracks"] if t["type"] == "video"
                  for s in t["segments"]), default=0)
    for k, seg in enumerate(track["segments"]):
        _kk, mat = mats[seg["material_id"]]
        n = re.search(r"mark_(\d+)_box", mat["material_name"]).group(1)
        bp, lp = done[n][0], done[n][1]
        mat["path"], mat["material_name"] = str(bp), bp.name
        mat["unique_id"] = hashlib.md5(open(bp, "rb").read()).hexdigest()
        seg["clip"]["transform"] = {"x": 0.0, "y": 0.0}            # the PNG is already placed
        seg["clip"]["scale"] = {"x": 1.0, "y": 1.0}
        h = copy.deepcopy(seg)
        h["id"] = new_id()
        m2 = copy.deepcopy(mat)
        m2["id"], m2["path"], m2["material_name"] = new_id(), str(lp), lp.name
        m2["unique_id"] = hashlib.md5(open(lp, "rb").read()).hexdigest()
        draft["materials"]["videos"].append(m2)
        h["material_id"] = m2["id"]
        refs = []
        for r in seg.get("extra_material_refs", []):
            kk, em = mats[r]
            e2 = copy.deepcopy(em)
            e2["id"] = new_id()
            draft["materials"][kk].append(e2)
            refs.append(e2["id"])
        h["extra_material_refs"] = refs
        h["render_index"] = top_ri + 1 + k
        h["track_render_index"] = seg.get("track_render_index", 0) + 1
        heads["segments"].append(h)
    draft["tracks"].insert(ti + 1, heads)
    for t in draft["tracks"][ti + 2:]:                             # keep track order indices unique
        for s in t["segments"]:
            s["track_render_index"] = s.get("track_render_index", 0) + 1
    return draft


def validate(draft):
    ids = {m["id"] for v in draft["materials"].values() if isinstance(v, list)
           for m in v if isinstance(m, dict) and "id" in m}
    for t in draft["tracks"]:
        for s in t["segments"]:
            assert s["material_id"] in ids, ("missing material", t.get("name"), s["material_id"])
            for r in s.get("extra_material_refs", []):
                assert r in ids, ("missing extra ref", t.get("name"), r)
    names = [t.get("name") for t in draft["tracks"]]
    assert names.index("Marking headings") == names.index("Markings") + 1
    return len(ids)


def repoint(draft, done):
    """Already split: point both tracks at the new PNGs (same timing, same ids)."""
    mats = {m["id"]: m for v in draft["materials"].values() if isinstance(v, list)
            for m in v if isinstance(m, dict) and "id" in m}
    n_done = 0
    for t in draft["tracks"]:
        if t.get("name") not in ("Markings", "Marking headings"):
            continue
        for seg in t["segments"]:
            mat = mats[seg["material_id"]]
            m = re.search(r"mark_(\d+)_(box|label)", mat["material_name"])
            png = done[m.group(1)][0 if m.group(2) == "box" else 1]
            mat["path"], mat["material_name"] = str(png), png.name
            mat["unique_id"] = hashlib.md5(open(png, "rb").read()).hexdigest()
            seg["clip"]["transform"] = {"x": 0.0, "y": 0.0}
            seg["clip"]["scale"] = {"x": 1.0, "y": 1.0}
            n_done += 1
    return n_done


def main(tag, name, folder="layers_split", wait=False):
    """wait=True (--wait): draw everything while CapCut is open (only reads the draft), then wait for
    Saad to close CapCut and write in seconds. Never for a project he has open - the draft read at the
    start must still be current when it is written."""
    if not wait and subprocess.run(["pgrep", "-x", "CapCut"], capture_output=True).returncode == 0:
        raise SystemExit("CapCut is open - close it first (never write a draft CapCut has open)")
    proj = CAP / name
    copies = [proj / "draft_info.json"] + sorted(proj.glob("Timelines/*/draft_info.json"))
    # CapCut keeps these byte-identical; build from the main-timeline copy, write it to all
    draft = json.load(open(copies[-1]))
    segs = [s for t in draft["tracks"] if t.get("name") == "Markings" for s in t["segments"]]
    mats = {m["id"]: m for v in draft["materials"].values() if isinstance(v, list)
            for m in v if isinstance(m, dict) and "id" in m}
    starts = {re.search(r"mark_(\d+)_", mats[s["material_id"]]["material_name"]).group(1):
              s["target_timerange"]["start"] / 1e6 for s in segs}
    done = render(tag, starts, folder)
    bad = check(tag, done)
    print(f"{len(done)} markings drawn in Saad's layout ({folder}); read-back {len(done) - len(bad)}/{len(done)}")
    for b in bad:
        print("   ?? mark", b)
    heads = [(n, d[5]["heading_on"]) for n, d in sorted(done.items()) if d[5]["heading_on"]]
    edges = [(n, d[5]["edge_through"]) for n, d in sorted(done.items()) if d[5]["edge_through"]]
    print(f"headings clear of text {len(done) - len(heads)}/{len(done)}; "
          f"outlines clear of neighbours {len(done) - len(edges)}/{len(done)}")
    for n, h in heads:
        print(f"   ?? heading mark {n} on {h}")
    for n, e in edges:
        print(f"   ?? edge mark {n} through {e}")
    for n, d in sorted(done.items()):
        if d[5]["screen_moved_at"]:
            print(f"   ?? screen moves under mark {n} at {d[5]['screen_moved_at']} (target not at its box)")
    while wait and subprocess.run(["pgrep", "-x", "CapCut"], capture_output=True).returncode == 0:
        time.sleep(3)
    if subprocess.run(["pgrep", "-x", "CapCut"], capture_output=True).returncode == 0:
        raise SystemExit("CapCut was opened meanwhile - PNGs are ready, run again to write the project")
    if wait and json.load(open(copies[-1])) != draft:
        raise SystemExit("the draft changed while waiting - not written; run again")
    bak = D / "_backup_capcut" / f"{name}_before_split_{time.strftime('%H%M%S')}"
    shutil.copytree(proj, bak)
    print("backup:", bak)
    if any(t.get("name") == "Marking headings" for t in draft["tracks"]):
        print(f"  repointed {repoint(draft, done)} segments")
    else:
        draft = patch(draft, done)
    n_ids = validate(draft)
    blob = json.dumps(draft, ensure_ascii=False)
    for f in copies:
        f.write_text(blob)
    assert len({f.read_bytes() for f in copies}) == 1, "draft copies differ"
    print(f"  wrote {len(copies)} identical copies ({n_ids} materials): "
          f"{[t.get('name') or '-' for t in draft['tracks']]}")


def _test():
    assert to_canvas((540, 960, 0, 0))[:2] == (540, round(960 - TY * 960)), "the centre only lifts"
    x, y, w, h = to_canvas((107, 96, 866, 1728))
    assert abs(w - 866 * S) < 1 and abs(x - (540 - 433 * S)) < 1
    d = {"materials": {"videos": [{"id": "m1", "material_name": "mark_001_box.png", "path": "p"}],
                       "speeds": [{"id": "s1"}]},
         "tracks": [{"id": "t", "type": "video", "name": "Markings",
                     "segments": [{"id": "g", "material_id": "m1", "extra_material_refs": ["s1"],
                                   "clip": {"transform": {"x": .2, "y": .1}, "scale": {"x": 1, "y": 1}},
                                   "render_index": 6, "track_render_index": 8,
                                   "target_timerange": {"start": 0, "duration": 1}}]},
                    {"id": "c", "type": "text", "name": "Captions", "segments": [{"id": "x", "material_id": "m1",
                     "track_render_index": 9}]}]}
    tmp = pathlib.Path("/tmp/_split_test"); tmp.mkdir(exist_ok=True)
    for f in ("b.png", "l.png"):
        Image.new("RGBA", (2, 2)).save(tmp / f)
    p = patch(d, {"001": (tmp / "b.png", tmp / "l.png")})
    validate(p)
    assert p["tracks"][0]["segments"][0]["clip"]["transform"] == {"x": 0.0, "y": 0.0}
    assert p["tracks"][1]["name"] == "Marking headings" and p["tracks"][1]["segments"][0]["material_id"] != "m1"
    assert p["tracks"][2]["segments"][0]["track_render_index"] == 10
    _test_fit()
    _test_label()
    print("split_marks self-check: ok (patch, outlines clear the letters and every neighbour line, "
          "headings clear of text, heading_at / chip_at)")


def _clean(rect, texts):
    """Text boxes the stroke's pixels run through (each must be wholly inside or outside it)."""
    return [t[4] for t in texts if crosses(rect, _xyxy(t), 0)]


def _air(rect, ink):
    """px between the stroke's inner edge and the glyphs (x0, y0, x1, y1), worst side."""
    return min(ink[0] - rect[0], ink[1] - rect[1], rect[2] - ink[2], rect[3] - ink[3]) - STROKE


def _test_fit():
    """QA vs his approved reference module, 24 Sep - real geometry (his layout, ink-tight OCR boxes)."""
    bounds = (180, 150, 900, 1500)
    # 'L of Weekly Target' clipped (0:25.8): words-only, the figures 11 px below. The stroke clears
    # the letters and slips between the words and the figures without touching either.
    own = (282, 537, 117, 19, "Weekly Target")
    tx = [own, (282, 504, 340, 12, "MY DASHBOARD - TEAM"), (745, 536, 53, 19, "73%"),
          (282, 569, 297, 28, "109K of 150K this month"), (282, 644, 13, 19, "2")]
    rect, taken, left = fit_box((279, 538, 122, 20), (282, 534, 117, 24), "text", PAD, tx, bounds)
    assert not left and not taken and not _clean(rect, tx), (rect, _clean(rect, tx))
    assert _air(rect, _xyxy(own)) >= 1 and 569 - rect[3] >= 1, rect
    assert min(537 - rect[1], 282 - rect[0], rect[2] - 399) - STROKE >= WORDS_PAD - STROKE - 3, "air where there is room"
    # the same words with room round them: WORDS_PAD all round, never a sliver
    rect, taken, left = fit_box((279, 538, 122, 20), (282, 534, 117, 24), "text", PAD, [own], bounds)
    assert _air(rect, _xyxy(own)) >= WORDS_PAD - STROKE - 3 and rect[3] - rect[1] >= MIN_OUTER_H and not taken
    # '64K of 80K' 9 px under 'Item A 80%' (0:38.5): the old top edge ran through the label. Now
    # the stroke sits in the gap, >= 1 px off both lines; 'Item B 96%' / '63K of 65K' stay out.
    own = (282, 654, 79, 11, "64K of 80K")
    tx = [own, (282, 629, 102, 16, "Item A 80%"), (424, 629, 98, 16, "Item B 96%"),
          (423, 654, 79, 11, "63K of 65K"), (281, 703, 281, 16, "Gap 1440 - target at 90% plan")]
    rect, taken, left = fit_box((282, 652, 82, 14), (281, 654, 79, 11), "text", PAD, tx, bounds)
    assert not left and not taken and not _clean(rect, tx), (rect, taken)
    assert rect[1] - 645 >= 1 and _air(rect, (281, 654, 361, 665)) >= 1 and rect[2] < 423, rect
    # '90% PLAN' 7 px under 'GAP - TARGET AT' (1:21.8): no 1 px of air each side is possible, so
    # the two-line caption becomes one target (the QA's fix); '1,440' 8 px above that is too tall
    # to take in as well, so that edge squeezes between, touching neither
    own = (656, 609, 94, 11, "90% PLAN")
    tx = [own, (656, 591, 134, 11, "GAP - TARGET AT"), (657, 555, 78, 28, "1,440"),
          (282, 582, 137, 14, "ITEM A - 64K/80K"), (469, 582, 134, 14, "ITEM B - 63K/65K"),
          (256, 685, 253, 13, "MONTHLY SUMMARY")]
    rect, taken, left = fit_box((653, 608, 98, 14), (656, 609, 93, 11), "text", PAD, tx, bounds)
    assert not left and not _clean(rect, tx) and taken == [_xyxy(tx[1])], (rect, taken, left)
    assert rect[1] - 583 >= 1 and 591 - (rect[1] + STROKE) >= 1, "between '1,440' and the caption"
    assert _air(rect, (656, 591, 790, 620)) >= 1, rect
    # a word along the row is kept out (squeezed), not swallowed: 'Item B 96%' 40 px right of 'Item A 80%'
    own = (282, 629, 102, 16, "Item A 80%")
    tx = [own, (424, 629, 98, 16, "Item B 96%")]
    rect, taken, left = fit_box((282, 627, 104, 20), (282, 629, 102, 16), "text", PAD, tx, bounds)
    assert not taken and not left and not _clean(rect, tx) and rect[2] < 424, rect
    # an element outline never grows to take a neighbour in: it pulls its gap in (never inside the
    # element's rim), and what it cannot clear is reported, not hidden
    el = (260, 600, 300, 80)
    tx = [(270, 610, 200, 20, "Tile title"), (270, 690, 120, 14, "caption below the tile")]
    rect, taken, left = fit_box((270, 610, 200, 20), el, "element", 10, tx, bounds)
    assert not taken and not left and not _clean(rect, tx) and rect[3] - 680 >= EL_MIN_PAD, rect
    tx[1] = (270, 684, 120, 14, "caption 4 px under the tile")
    rect, taken, left = fit_box((270, 610, 200, 20), el, "element", 10, tx, bounds)
    assert not taken and left == [_xyxy(tx[1])], (rect, left)
    # the outline stays on the phone screen
    rect, _t, _l = fit_box((184, 160, 60, 14), (184, 160, 60, 14), "text", PAD, [], bounds)
    assert rect[0] > bounds[0] and rect[1] > bounds[1]


def _test_label():
    """The heading chip in his layout never lands on the frame's text; heading_at / chip_at obeyed."""
    frame = Image.new("RGB", (W, H), (246, 246, 246))
    bounds = (180, 150, 900, 1500)
    colour = (sm.APP_GREEN, sm.APP_GREEN_SOFT)
    rect = (270, 618, 395, 681)                                  # 'Item A 80%' + '64K of 80K'
    tx = [(282, 629, 102, 16, 1), (282, 654, 79, 11, 1), (424, 629, 98, 16, 1), (423, 654, 79, 11, 1),
          (281, 703, 281, 16, 2), (281, 560, 300, 30, 1), (700, 640, 120, 20, 4)]
    box = (rect[0], rect[1], rect[2] - rect[0], rect[3] - rect[1])
    img, chip = draw_label(box, "Own target", colour, frame, bounds, 0, 12, texts=tx, own=tx[:2], want_chip=True)
    assert chip and not heading_hits(chip, [t[:4] + ("t",) for t in tx]), chip
    a = np.array(img)
    assert a[..., 3].max() > 0 and a[chip[1]:chip[1] + chip[3], chip[0]:chip[0] + chip[2], 3].max() > 0
    ys, xs = np.nonzero(a[..., 3] > 0)                           # only the chip (and its shadow) drawn
    assert xs.min() >= chip[0] - 12 and xs.max() <= chip[0] + chip[2] + 12 and ys.max() <= chip[1] + chip[3] + 14
    cr = (chip[0], chip[1], chip[0] + chip[2], chip[1] + chip[3])
    assert not _hits(cr, rect), "never on its own box"
    _i, c2 = draw_label(box, "Own target", colour, frame, bounds, 0, 12, texts=tx, own=tx[:2], prefer="below",
                        want_chip=True)
    assert c2[1] >= rect[3] and not heading_hits(c2, [t[:4] + ("t",) for t in tx]), c2
    _i, c3 = draw_label(box, "Own target", colour, frame, bounds, 0, 12, texts=tx, chip_at=[300, 1000], want_chip=True)
    assert c3[:2] == [300, 1000], c3


if __name__ == "__main__":
    if sys.argv[1] == "--test":
        _test()
    else:
        args = [a for a in sys.argv[1:] if a != "--wait"]
        main(args[0], args[1], *args[2:3], wait="--wait" in sys.argv)
