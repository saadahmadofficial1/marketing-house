"""Voice anchors: pin each marking's screen to the words that name it.

Saad, 24 Sep, on one finished role video: where the voice is longer than the
picture (the 0.70 floor), the picture finished its motion early and sat on its LAST frame,
so a tap or a scroll happened before the voice had talked about it and markings were
squeezed or skipped. He fixed it by hand in CapCut with freeze frames BEFORE the
transitions. This writes that rule into the plan, so sa_dubcut does it on every module:

  for every marking   at  = when its words are said in that line's voice clip - 0.3 s
                      src = a steady moment of the recording (ORIGINAL seconds) where its
                            target is on screen, inside that line's zone
  -> plan["segments"][line-1]["anchors"] = [{"at", "src", ...}]; sa_dubcut then freezes
     the current screen at the start of each piece and plays the motion to arrive on time.

How src is chosen (OCR proves it, never the sentence):
  - runs      = where the boxed OCR reads resolve the target to ONE element at one place, by
                sa_appbuild's rule (exact text wins over a longer look-alike; once the exact
                element has been seen, a look-alike never counts). A read inside a freeze
                stretch (the prep's freezedetect list) stands for the whole stretch.
  - candidates= the moment the picture would show anyway ("already on screen"), or that moment
                pulled forward to the start of a steady (frozen) stretch of the target, or held
                back so the target still has KEEP s of screen time after 'at' even at SPEED_MAX
                - so a "tap X" anchor always lands BEFORE the tap.
  - choice    = least added lateness, with penalties for a moving screen, for a moment that
                needs a keep pin, and for arriving too late for the placer; then least change.
  - keep pin  = a second anchor, added only when the target would otherwise leave within KEEP s.
  - frame check = the CLI then reads the frames the cut will show (plan["source"], every STEP s
                from 'at') and pins the last frame that still shows the target if it leaves too
                soon - screens.json only knows element positions at the first read of a merged
                entry, so a slow scroll can hide a departure (one module's marking 12, verifier 24 Sep).

SPEC OVERRIDES (24 Sep, QA against his own edit) - optional keys of the module spec, copied by build_module into
<tag>_marks.json next to "marks"; "line" is the spec line's "n", like a mark's:
  "anchor_overrides": [{"line": 12, "say": "Tap Closed", "src": 211.4}]
        replaces (or adds) the anchor for the words `say` in that line: when they are said (minus
        LEAD, or the entry's own "lead") the picture shows ORIGINAL source second `src`. A mark with
        the same say keeps its box and gets this src instead of the OCR choice; with no such mark the
        anchor is added on its own (kind "override"). Other markings in the line are anchored round
        it in order; the voice never moves (the anchor only redistributes the line's picture time).
  "holds": [{"line": 13, "src": 243.0, "secs": 0.5}]
        a still: when the picture reaches ORIGINAL source second `src` inside that line, it stays on
        that frame `secs` longer than it would have (two anchors, kind "hold"), so the transition
        after it comes later. The time is taken back from the motion after it (up to SPEED_MAX); an
        anchor inside the hold that wants a later frame is dropped and reported. Only a hold that
        cannot be paid back lengthens the line.
  Reports (<out>_report.json, and printed): "late_or_longer" = seconds a later marking in the line
  now arrives late (or the line runs longer); "moves_voice" = seconds the line runs past its voice,
  i.e. every later line of voice moves by that much - never silent.
  "exclude" (build_module) and "marks" (incl. "pick": "top" | "bottom", "heading_at", "chip_at") work as before.

    APP_SERIES_DIR=<series folder> sa_voice_anchors.py 01_RoleA SCRIPTS/01_RoleA_plan.json   -> ..._plan_anchored.json
        [--screens boxed/<id>/screens.json] [--freezes PREP/<tag>_<id>_freezes.txt]
        [--id <recording id>] [--video VERTICAL/<base>_V.mp4  (freezes when PREP has none)]
        [--lines ..._lines.txt] [--marks ..._marks.json] [--out path]
    The series folder (APP_SERIES_DIR, default: the current folder) holds PREP/, READ/ and
    SCRIPTS/ (<tag>_lines.txt, <tag>_marks.json). Boxed screens are looked for in
    READ/boxed/<id>.json first, then $BOXED_DIR/<id>/screens.json (default <series>/boxed).
    sa_voice_anchors.py --test
"""
import argparse, glob, hashlib, json, os, pathlib, sys

HERE = pathlib.Path(__file__).resolve().parent
# the series folder: PREP/ (freeze lists), READ/boxed/ (OCR screens), SCRIPTS/ (lines, marks)
SERIES = pathlib.Path(os.environ.get("APP_SERIES_DIR", ".")).expanduser().resolve()
SCRIPTS = SERIES / "SCRIPTS"
sys.path.insert(0, str(HERE))      # sa_dubcut, sa_appbuild, sa_appread, sa_plan_pacing sit beside it
import sa_dubcut as dc                                              # noqa: E402
from sa_appbuild import matches, label_for, _pn, OCR_BIN, FFMPEG   # noqa: E402

LEAD = 0.3        # the screen is already steady this long before its words
# The placer (sa_appbuild.build_voice) starts a box 0.15 s before the word and drops it if
# its target does not stay 1.3 s (sa_stepmark.MIN_DUR). From 'at' (= word - LEAD) that is
# LEAD - 0.15 + 1.3 = 1.45 s; KEEP adds a frame or two of margin. (Spec floor: >= 1.3 s.)
KEEP = 1.6
KEEP_FULL = LEAD - 0.15 + 2.1 + 0.05   # the full 2.1 s HOLD, asked for only when it costs nothing
SETTLE = 0.05     # inside a freeze, never on its first/last frame
# A moment that needs a keep pin (the screen moves on within KEEP s) is worth up to this much
# lateness to avoid: a settled screen a beat late beats a pinned one about to scroll (one
# role video, line 5, 24 Sep). But the placer only looks up to 1.35 s after the word, so a target that arrives
# more than LATE_LIMIT late is as good as missing and costs LATE_PENALTY more.
SHORT_PENALTY = 0.9
LATE_LIMIT, LATE_PENALTY = 1.2, 2.0
# Likewise a moment where the screen is still moving (mid-transition, typing): the spec is a
# STEADY moment, so one is only chosen when every steady one costs more than this in lateness.
MOVING_PENALTY = 0.5
# Frame check spacing (cut seconds). screens.json keeps the element boxes of the FIRST read of a
# merged entry only (sa_appread merges reads whose words barely differ), so a slow scroll inside
# an entry is invisible to runs(): one module's heading was claimed on screen 131.5-135.0
# but scrolls off at 132.1 (verifier, 24 Sep). The keep window is therefore read on the real frames.
STEP = 0.25
MAX_PIN_COST = 0.35   # seconds of lateness (or segment length) a frame-check pin may add
# where the boxed OCR reads live (screens.json with element boxes, SOURCE seconds)
BOXED = [SERIES / "READ" / "boxed" / "{id}.json",
         pathlib.Path(os.environ.get("BOXED_DIR", str(SERIES / "boxed"))).expanduser() / "{id}" / "screens.json"]


def load_freezes(path_or_list):
    if not isinstance(path_or_list, (str, pathlib.Path)):
        return sorted(tuple(map(float, f)) for f in path_or_list)
    out = []
    for ln in pathlib.Path(path_or_list).read_text().split():
        a, _, b = ln.partition("-")
        out.append((float(a), float(b)))
    return sorted(out)


def resolve(screen, mk, exact_only=False):
    """The ONE element a marking means on this screen, or None - sa_appbuild.build_voice's
    rule: a substring match, the element whose own text IS the target winning a tie."""
    hits = matches(screen, mk["target"])
    sq = lambda z: _pn(z).replace(" ", "")
    raw = [e for e in hits if sq(e["text"]) == sq(mk["target"])]
    exact = raw or [e for e in hits if sq(label_for(e)) == sq(mk["target"])]
    if exact_only and not exact:
        return None
    if len(hits) > 1:
        if len(exact) == 1:
            hits = exact
        elif mk.get("pick") == "top" and len(exact or hits) > 1:
            hits = [min(exact or hits, key=lambda e: e["y"])]
        elif mk.get("pick") == "bottom" and len(exact or hits) > 1:   # a tab-bar button whose
            hits = [max(exact or hits, key=lambda e: e["y"])]         # tile twin sits above it
    return hits[0] if len(hits) == 1 else None


def _clip(a, b, keeps):
    """[a, b] intersected with the kept (not fault-cut) parts of the recording."""
    if not keeps:
        return [(a, b)] if b > a else []
    return [(max(a, x), min(b, y)) for x, y in keeps if min(b, y) > max(a, x)]


def _merge(iv):
    out = []
    for a, b in sorted(iv):
        if out and a <= out[-1][1] + 0.05:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return out


def runs(mk, screens, zone, keeps, freezes, every=1.0):
    """Where the target sits still on screen inside the zone -> [run], ORIGINAL seconds.

    A run is consecutive OCR reads that resolve the target to ONE element at the same place
    (a scroll that moves it starts a new run). OCR reads once a second and sometimes misses a
    word, so each edge is taken from the freeze list: a read inside a freeze stretch means the
    target is there for the WHOLE stretch (the frames are identical); otherwise a run starts
    at its first read and ends half-way to the next different read.
    run = {"a", "b", "steady": [freezes in it]}."""
    za, zb = zone
    # sa_appread samples with ffmpeg fps=1/every, which keeps the LAST frame before t + every/2:
    # the read labelled t is really the picture at t + every/2 - 1 frame (measured 24 Sep on a
    # frame-numbered clip: labels 0, 1, 2 s held frames 0.47, 1.50, 2.47 s)
    lag = 0.5 * every - 1 / 30
    screens = [dict(s, t=s["t"] + lag, t_end=s["t_end"] + lag) for s in screens]
    inz = sorted((s for s in screens if s["t"] < zb and s["t_end"] > za), key=lambda s: s["t"])
    exact_seen = any(resolve(s, mk, exact_only=True) is not None for s in inz)
    raw, reads = [], []                         # reads: (time, place) of every read that finds it
    same = lambda p, q: abs(p[0] - q[0]) <= 12 and abs(p[1] - q[1]) <= 12
    for s in inz:
        el = resolve(s, mk, exact_only=exact_seen)
        if el is not None:
            first, last, pos = s["t"], max(s["t"], s["t_end"] - every), (el["x"], el["y"])
            reads += [(first + k * every, pos) for k in range(int(round((last - first) / every)) + 1)]
            if raw and same(pos, raw[-1][3]) and first <= raw[-1][2] + every + 1e-6:
                raw[-1] = (raw[-1][0], last, s["t_end"], raw[-1][3])
            else:
                raw.append((first, last, s["t_end"], pos))
    edges = []
    for first, last, nxt, pos in raw:
        # a freeze stands for its whole stretch - unless a read in it saw the target ELSEWHERE
        # (the one-second reads and the freeze edges can disagree by a fraction of a second)
        a = first
        fz = next(((fa, fb) for fa, fb in freezes if fa <= first <= fb), None)
        if fz and not any(fz[0] <= t < first and not same(p, pos) for t, p in reads):
            a = fz[0]
        # no freeze: it was seen at `last` and gone by `nxt` - assume it left half-way
        b = min(nxt, last + 0.5 * every)
        fz = next(((fa, fb) for fa, fb in freezes if fa <= last <= fb), None)
        if fz:
            contra = [t for t, p in reads if last < t <= fz[1] and not same(p, pos)]
            b = min(contra) if contra else fz[1]
        if edges and edges[-1][1] > a:          # it left its old place when the new one settled
            edges[-1][1] = a
        edges.append([a, b])
    out = []
    for a, b in edges:
        for x, y in _clip(max(a, za), min(b, zb), keeps):
            st = [(max(fa, x), min(fb, y)) for fa, fb in freezes if min(fb, y) - max(fa, x) > 2 * SETTLE]
            out.append({"a": x, "b": y, "steady": st})
    return out


def candidates(rs, cur, prev_src, window):
    """Moments the anchor could pin -> [(src, run, why, short, steady)]. A run that reaches the
    window end keeps the target until the line ends (the picture holds its last frame), so it
    has room; otherwise the target must stay KEEP s after 'at' even at SPEED_MAX, and a moment
    without that room is `short` (it will need a keep pin). Everything is clamped into the
    window: outside it, inside the zone, the recording is frozen on the window's edge frame.
    `steady` = the moment sits inside a freeze stretch (nothing on screen is moving)."""
    w0, w1 = window
    out = []
    for r in rs:
        open_end = r["b"] >= w1 - 0.05
        room = float("inf") if open_end else r["b"] - SETTLE - KEEP * dc.SPEED_MAX
        still = lambda c: any(fa + SETTLE - 1e-6 <= c <= fb - SETTLE + 1e-6 for fa, fb in r["steady"])
        if r["a"] <= cur <= min(r["b"] - SETTLE, room):
            out.append((cur, r, "already on screen", False, still(cur)))
        for fa, fb in r["steady"] + [(r["a"], r["b"])]:
            c = min(max(cur, fa + SETTLE), max(fa + SETTLE, min(fb - SETTLE, room)))
            c = min(max(c, w0), w1)
            out.append((c, r, "pulled forward to the steady screen" if c > cur + 0.02 else
                        "held back before it leaves" if c < cur - 0.02 else "already on screen",
                        c > room + 1e-6, still(c)))
    return [c for c in out if prev_src is None or c[0] >= prev_src - 1e-6]


def word_times(lines, plan, cache_path=None):
    """Whisper word times per voice clip, clip-relative - sa_appbuild.line_word_times with
    every segment starting at 0. Cached by clip bytes + line text (whisper is the slow part)."""
    from sa_appbuild import line_word_times
    cache = {}
    if cache_path and os.path.exists(cache_path):
        cache = json.load(open(cache_path))
    keys = [hashlib.sha1(open(s["vo"], "rb").read() + t.encode()).hexdigest()
            for s, t in zip(plan["segments"], lines)]
    need = [i for i, k in enumerate(keys) if k not in cache]
    if need:
        sub = {"segments": [plan["segments"][i] for i in need]}
        tim = {"segments": [{"n": s["n"], "start": 0.0, "vo_dur": dc.probe(s["vo"])} for s in sub["segments"]]}
        for i, w in zip(need, line_word_times([lines[i] for i in need], sub, tim)):
            cache[keys[i]] = w
        if cache_path:
            json.dump(cache, open(cache_path, "w"))
    return [[tuple(x) for x in cache[k]] for k in keys]


def source_frames(video):
    """-> read([rendered-source seconds]) -> [screen]: OCR of the frames the cut will show, from
    plan["source"] (the fault-cut source sa_dubcut renders from). Cached per frame."""
    import subprocess, tempfile
    from concurrent.futures import ThreadPoolExecutor
    from sa_appread import parse_elements
    tmp, cache = tempfile.mkdtemp(prefix="anchors_frames_"), {}

    def burst(fs):
        """Frames fs (sorted, within a few seconds) from ONE seek and decode, OCR'd in one call."""
        d = os.path.join(tmp, str(fs[0]))
        os.makedirs(d, exist_ok=True)
        sel = "+".join(f"eq(n\\,{f - fs[0]})" for f in fs)
        # seek half a frame early: the first frame at or after the seek point is then exactly fs[0]
        subprocess.run([FFMPEG, "-y", "-v", "error", "-ss", f"{max(0.0, (fs[0] - 0.5) / dc.FPS):.4f}", "-i", video,
                        "-frames:v", str(len(fs)), "-vf", f"select='{sel}'", "-fps_mode", "passthrough",
                        os.path.join(d, "%04d.png")], check=True)
        pngs = [os.path.join(d, f"{k + 1:04d}.png") for k in range(len(fs))]
        got = {}
        for ln in subprocess.run([str(OCR_BIN), "--boxes"] + pngs, capture_output=True, text=True).stdout.splitlines():
            path, _, payload = ln.partition("\t")
            got[path] = {"elements": parse_elements(payload.strip())}
        for p in pngs:
            os.unlink(p)
        os.rmdir(d)
        return [got.get(p, {"elements": []}) for p in pngs]

    def read(ts):
        idx = [int(t * dc.FPS + 1e-6) for t in ts]          # the frame on screen at t
        need, groups = sorted(set(idx) - set(cache)), []
        for f in need:
            if groups and f - groups[-1][0] <= 3 * dc.FPS:
                groups[-1].append(f)
            else:
                groups.append([f])
        with ThreadPoolExecutor(4) as ex:
            for fs, scr in zip(groups, ex.map(burst, groups)):
                cache.update(zip(fs, scr))
        return [cache[i] for i in idx]
    return read


def _core(z):
    """Text without an icon glyph the OCR read as a lone letter at either end: a toast reads
    "Approved v" on one frame and "Approved" on the next - the same toast, not a departure."""
    b = _pn(z).split()
    if len(b) > 1 and len(b[-1]) == 1 and b[-1] not in ("a", "i"):
        b = b[:-1]
    if len(b) > 1 and len(b[0]) == 1 and b[0] not in ("a", "i"):
        b = b[1:]
    return "".join(b)


def _samples(out, i, layout, target):
    """Cut times from arrive anchor out[i]'s 'at' to its keep horizon (never past the next
    marking's words), and the rendered-source second the cut shows at each -> (ts, srcs, H).
    The horizon allows for an arrival up to LATE_LIMIT late: the hold counts from the arrival."""
    an = out[i]
    nxt = next((o["at"] for o in out[i + 1:] if o["kind"] != "keep"), None)
    H = min(an["at"] + KEEP_FULL + LATE_LIMIT, target - 0.05, (nxt - 0.05) if nxt is not None else 1e9)
    ts = [an["at"] + k * STEP for k in range(int(max(0.0, H - an["at"]) / STEP + 1e-6) + 1)]
    if ts[-1] < H - 1e-6:
        ts.append(H)
    tseg = layout(out)[0]
    return ts, [dc.src_at(tseg, t) for t in ts], H


def frame_check(out, layout, frames, marks_by_k, reports, target, keeps):
    """Closed loop on the real frames, in place on `out` (one line's anchors, in order). For each
    'arrive' anchor, read what the cut will show every STEP s from 'at' to the keep horizon (never
    past the next marking's words). If the target arrives and then leaves (or slides out of its
    box) too soon, pin the last frame that still shows it in place - KEEP s from its arrival
    always, the full hold only when that costs no lateness (the same rule as the keep pins).
    -> number of pins added or tightened."""
    pins, i = 0, 0
    while i < len(out):
        an = out[i]
        if an["kind"] != "arrive":
            i += 1
            continue
        mk, r = marks_by_k[an["mark"]], reports[an["mark"]]
        (ts, srcs, H), cost = _samples(out, i, layout, target), layout(out)[1]
        scr = frames(srcs)
        exact = any(resolve(s, mk, exact_only=True) is not None for s in scr)

        def find(s):
            el = resolve(s, mk, exact_only=exact)
            core = [e for e in s["elements"] if e.get("x") is not None and _core(e["text"]) == _core(mk["target"])]
            return el or (core[0] if len(core) == 1 else None)
        els = [find(s) for s in scr]
        i += 1
        # judge from the anchor frame on: before it (a late arrival) the screen is still coming in
        s_an = dc.to_tight(an["src"], keeps)
        k_an = next((k for k, s in enumerate(srcs) if s >= s_an - 1e-3), len(srcs))
        a0 = next((k for k in range(k_an, len(els)) if els[k]), None)
        if a0 is None:
            r["frames"] = "".join("y" if e else "." for e in els)
            r["frame_check"] = "target not read on the frames from its anchor on"
            continue
        # the placer needs the box to keep reading back, so the target must stay PUT: its middle
        # within 12 px up/down (a scroll), 40 px sideways (a glyph read or not shifts centred text)
        mid = lambda e: (e["x"] + e.get("w", 0) / 2, e["y"] + e.get("h", 0) / 2)
        put = lambda e: (e is not None and abs(mid(e)[1] - mid(els[a0])[1]) <= 12
                         and abs(mid(e)[0] - mid(els[a0])[0]) <= 40)
        # the box goes up when the target arrives (a late anchor arrives after 'at'), so the
        # KEEP / full-hold windows count from that sample
        R, F = min(ts[a0] + KEEP, H), min(ts[a0] + KEEP_FULL, H)
        ok = [k >= a0 and put(e) for k, e in enumerate(els)]
        r["frames"] = "".join("Y" if x else "." for x, t in zip(ok, ts) if t <= F + 1e-6)
        # the placer's rule (sa_appbuild.stable): one missed read is OCR noise, two in a row is gone
        leave = next((k for k in range(a0 + 1, len(ok)) if not ok[k] and ts[k] <= F + 1e-6
                      and (k + 1 >= len(ok) or not ok[k + 1])), None)
        if leave is None or R < ts[a0] + KEEP - 1e-6:
            continue                                  # stays, or the next words come first anyway
        s_ok = srcs[leave - 1]
        if s_ok < dc.to_tight(an["src"], keeps) - 1e-6:
            r["frame_check"] = "target leaves before its anchor frame"
            continue
        pin_at = R if ts[leave] <= R + 1e-6 else F
        fixed = next((o for o in out[i:] if o["kind"] != "keep"), None)
        if fixed is not None and fixed.get("override") and dc.to_tight(fixed["src"], keeps) < s_ok - 1e-6:
            r["frame_check"] = "a pin would run past the next spec override"
            continue
        rest = [o for o in out[i:] if not (o["kind"] == "keep" and o["mark"] == an["mark"])]
        pin = {"at": round(pin_at, 3), "src": round(dc.from_tight(s_ok, keeps), 3), "mark": an["mark"],
               "kind": "keep", "target": an["target"]}
        trial = out[:i] + [pin] + rest
        added = layout(trial)[1] - cost
        if pin_at > R + 1e-6 and added > 0.01:
            continue                                  # the full hold would make it late
        if added > MAX_PIN_COST:
            # never buy one marking's hold with the next one's timing (or a longer segment, which
            # would move every later line of voice): one role video, line 10, verifier 24 Sep
            r["frame_check"] = f"leaves {ts[leave] - ts[a0]:.2f} s after it arrives; a pin would cost {added:.2f} s"
            continue
        out[:] = trial
        r["keep"], r["frame_pin"] = pin["src"], True
        pins += 1
        i += 1                                        # past the pin
    return pins


def _layout_fn(ta, span, target, keeps):
    """-> layout(anchor_list) -> (timing-style segment with pieces, seconds late or longer)."""
    def layout(anchor_list):
        pcs, pdur, _u, _d, late = dc.plan_pieces(ta, span, target, anchor_list, keeps)
        return ({"pieces": [[t0, s0, t1, s1, "hold" if sp is None else sp] for t0, s0, t1, s1, sp in pcs]},
                sum(x for _k, x in late) + (pdur - target))
    return layout


def anchors(tag, spec_lines, marks, plan, vo_dir, screens_json, freezes, words=None, cache=None,
            frames=None, overrides=None, holds=None):
    """Write plan["segments"][i]["anchors"] for every marking it can prove. -> (plan, report).

    tag          module tag, for the report only
    spec_lines   the written script lines (one per plan segment)
    marks        [{"line", "say", "target", ...}] as in <tag>_marks.json (1-based lines)
    plan         plan_pacing's plan (dict; returned as a copy with anchors)
    vo_dir       voice clips, used when a segment's "vo" path is missing
    screens_json boxed OCR (path or loaded dict), SOURCE-recording seconds
    freezes      freeze stretches (path to "a-b" lines, or a list)
    words        optional precomputed clip-relative word times per line (tests)
    frames       optional read([rendered-source s]) -> [screen] (source_frames(plan["source"]));
                 given, every anchor's keep window is checked on the real frames (frame_check)
    overrides    spec "anchor_overrides" [{"line", "say", "src"[, "lead"]}] (1-based lines)
    holds        spec "holds" [{"line", "src", "secs"}] (1-based lines)
    """
    from sa_appbuild import phrase_time
    plan = json.loads(json.dumps(plan))
    clips = sorted(glob.glob(os.path.join(os.path.expanduser(vo_dir or ""), "*.mp3")))
    for i, s in enumerate(plan["segments"]):
        if not os.path.exists(s["vo"]) and i < len(clips):
            s["vo"] = clips[i]
    scr = screens_json if isinstance(screens_json, dict) else json.load(open(screens_json))
    screens = scr["screens"]
    F = load_freezes(freezes)
    keeps = plan.get("keeps")
    rows = dc.build(plan)
    if words is None:
        words = word_times(spec_lines, plan, cache)
    report = []
    by_line, checks = {}, []
    for k, mk in enumerate(marks, start=1):
        by_line.setdefault(mk["line"], []).append((k, mk))
    for li, seg in enumerate(plan["segments"], start=1):
        seg.pop("anchors", None)
        ta, span, _sp, _vo, _vd, target = rows[li - 1]
        zone = seg.get("zone", seg["src"])
        todo, forced = [], {}
        for ov in [o for o in (overrides or []) if o["line"] == li]:
            said = phrase_time(words[li - 1], ov["say"])
            k = next((k for k, mk in by_line.get(li, []) if _pn(mk["say"]) == _pn(ov["say"])), None)
            if said is None:
                report.append({"override": True, "line": li, "say": ov["say"], "src": ov["src"],
                               "skip": f"'{ov['say']}' not heard in line {li}"})
                continue
            at = max(0.0, said - float(ov.get("lead", LEAD)))
            if k is not None:
                forced[k] = (float(ov["src"]), at)
            else:
                r = {"override": True, "line": li, "say": ov["say"], "said": round(said, 2)}
                report.append(r)
                todo.append((at, None, ov, r))
        for k, mk in by_line.get(li, []):
            said = phrase_time(words[li - 1], mk["say"])
            r = {"mark": k, "line": li, "say": mk["say"], "target": mk["target"],
                 "said": None if said is None else round(said, 2),
                 "tap": _pn(mk["say"]).startswith("tap")}
            report.append(r)
            if k in forced:
                todo.append((forced[k][1], k, mk, r))
                continue
            if said is None:
                r["skip"] = f"'{mk['say']}' not heard in line {li}"
                continue
            todo.append((max(0.0, said - LEAD), k, mk, r))
        todo.sort(key=lambda x: x[0])
        # the spec's fixed moments: every OCR-chosen anchor must fit between them, in order
        fixed = [(at, forced[k][0] if k is not None else float(mk["src"]))
                 for at, k, mk, _r in todo if k is None or k in forced]
        out, prev_src, prev_at, pinfo = [], None, -1.0, []
        win_end = dc.from_tight(ta + span, keeps)

        layout = _layout_fn(ta, span, target, keeps)
        for at, k, mk, r in todo:
            if k is None or k in forced:                   # a spec override: its src, as given
                src = forced[k][0] if k is not None else float(mk["src"])
                if at <= prev_at + 1e-3:
                    at = prev_at + 0.02                    # the picture needs a moment between them
                if prev_src is not None and src < prev_src - 1e-6:
                    r["skip"] = f"override src {src} is before the previous anchor's {prev_src}"
                    continue
                w0 = seg["src"][0]
                if not (w0 - 1e-6 <= src <= win_end + 1e-6):
                    r["warn"] = f"src {src} is outside line {li}'s window {w0}-{round(win_end, 2)}: clamped"
                if keeps and not any(a - 1e-6 <= src <= b + 1e-6 for a, b in keeps):
                    r["warn"] = f"src {src} is inside a removed part of the recording: snapped to the next kept frame"
                tseg, cost0 = layout(out)
                r.update(at=round(at, 2), was=round(dc.from_tight(dc.src_at(tseg, at), keeps), 2),
                         src=round(src, 2), why="spec override")
                r["moved"] = round(dc.to_tight(src, keeps) - dc.to_tight(r["was"], keeps), 2)
                _t, late = layout(out + [{"at": at, "src": src}])
                if late - cost0 > 0.05:
                    r["late_or_longer"] = round(late - cost0, 2)
                out.append({"at": round(at, 3), "src": round(src, 3), "mark": k,
                            "kind": "arrive" if k is not None else "override", "override": True,
                            "target": mk["target"] if k is not None else mk["say"]})
                prev_src, prev_at = src, at
                continue
            rs = runs(mk, screens, zone, keeps, F, scr.get("every", 1.0))
            if not rs:
                r["skip"] = "target not on screen in its zone (OCR)"
                continue
            if at <= prev_at + 0.05:
                r["skip"] = "said at the same moment as the previous marking"
                continue
            tseg, cost0 = layout(out)
            cur = dc.from_tight(dc.src_at(tseg, at), keeps)
            r.update(at=round(at, 2), was=round(cur, 2),
                     visible=[[round(x["a"], 2), round(x["b"], 2)] for x in rs[:3]])
            best = None
            cap = min((fs for fa, fs in fixed if fa > at + 1e-6), default=None)   # the next fixed moment
            for c, run, why, short, still in candidates(rs, cur, prev_src, (seg["src"][0], win_end)):
                if cap is not None and c > cap + 1e-6:
                    continue
                _t, cost = layout(out + [{"at": at, "src": c}])
                late = cost - cost0
                key = (round(late + (LATE_PENALTY if late > LATE_LIMIT else 0.0) +
                             (SHORT_PENALTY if short else 0.0) + (0.0 if still else MOVING_PENALTY), 2),
                       abs(dc.to_tight(c, keeps) - dc.to_tight(cur, keeps)))
                if best is None or key < best[0]:
                    best = (key, c, run, why)
            if best is None:
                r["skip"] = "out of order with the previous marking"
                continue
            (cost, shift), src, run, why = best
            r.update(src=round(src, 2), moved=round(dc.to_tight(src, keeps) - dc.to_tight(cur, keeps), 2), why=why)
            _t, late = layout(out + [{"at": at, "src": src}])
            if late - cost0 > 0.05:
                r["late_or_longer"] = round(late - cost0, 2)
            out.append({"at": round(at, 3), "src": round(src, 3), "mark": k, "kind": "arrive",
                        "target": mk["target"]})
            pinfo.append((len(out) - 1, run, win_end, r))
            prev_src, prev_at = src, at
        # Keep pins, only where needed: a target that would leave within KEEP s of its words
        # (a tap too soon after "tap X") is pinned on its last frame until then. Where it costs
        # no lateness the pin reaches for the full HOLD, so the box is not cut short either.
        for i in range(len(pinfo) - 1, -1, -1):
            j, run, we, r = pinfo[i]
            an = out[j]
            nxt = next((o["at"] for o in out[j + 1:] if o["kind"] != "keep"), None)
            if run["b"] >= we - 0.05:
                continue                                   # it stays until the line ends
            last_ok = max(run["b"] - SETTLE, an["src"])     # never behind its own arrival
            nfix = next((o for o in out[j + 1:] if o["kind"] != "keep"), None)
            if nfix is not None and nfix.get("override"):
                last_ok = min(last_ok, nfix["src"])        # never past the spec's next moment
            tseg, cost_now = layout(out)
            for want in (KEEP_FULL, KEEP):
                tk = min(an["at"] + want, target - 0.05, (nxt - 0.05) if nxt is not None else 1e9)
                if tk < an["at"] + KEEP:
                    break                                  # the next words come first anyway
                if dc.src_at(tseg, tk) <= dc.to_tight(last_ok, keeps) + 1e-3:
                    break                                  # already stays long enough
                pin = {"at": round(tk, 3), "src": round(last_ok, 3), "mark": an["mark"],
                       "kind": "keep", "target": an["target"]}
                if want == KEEP_FULL and layout(out[:j + 1] + [pin] + out[j + 1:])[1] > cost_now + 0.01:
                    continue                               # the full hold would make it late
                out.insert(j + 1, pin)
                r["keep"] = round(last_ok, 2)
                break
        if out:
            seg["anchors"] = out                    # the same list: frame_check edits it in place
            checks.append((out, layout, {k: mk for k, mk in by_line.get(li, [])},
                           {r["mark"]: r for r in report if r["line"] == li and "mark" in r}, target))
    if frames is not None and checks:
        frames([s for out, lay, _m, _r, tg in checks                   # read them all at once
                for i in range(len(out)) if out[i]["kind"] == "arrive" for s in _samples(out, i, lay, tg)[1]])
        for out, lay, mm, rr, tg in checks:
            frame_check(out, lay, frames, mm, rr, tg, keeps)
    apply_holds(plan, holds or [], rows, report)
    # a spec override / hold whose line now runs past its voice (+ breath) moves every later line
    # of voice by that much: say so on its report ("moves_voice", seconds)
    for r in report:
        if (r.get("override") or r.get("hold") or r.get("why") == "spec override") and "skip" not in r:
            ta, span, _sp, _vo, _vd, target = rows[r["line"] - 1]
            pdur = dc.plan_pieces(ta, span, target, plan["segments"][r["line"] - 1].get("anchors"), keeps)[1]
            if pdur - target > 0.05:
                r["moves_voice"] = round(pdur - target, 2)
    return plan, report


def _arrival(tseg, s):
    """First cut time (segment-relative) at which rendered-source time s is on screen, and how
    long that frame is then held -> (t, dwell)."""
    for t0, s0, t1, s1, sp in tseg["pieces"]:
        if sp == "hold":
            if abs(s0 - s) <= 1e-4:
                dwell = sum(b - a for a, b, h in dc._holds(tseg) if abs(h - s) <= 1e-4 and a >= t0 - 1e-6)
                return t0, dwell
        elif s0 - 1e-6 <= s <= s1 + 1e-6:
            t = t0 + max(0.0, s - s0) / sp
            nxt = [(a, b) for a, b, h in dc._holds(tseg) if abs(h - s) <= 1e-4 and abs(a - t) <= 1e-3]
            return t, (nxt[0][1] - nxt[0][0]) if nxt else 0.0
    ps = tseg["pieces"]
    return (0.0, 0.0) if s <= ps[0][1] else (ps[-1][2], 0.0)


def apply_holds(plan, holds, rows, report):
    """The spec's "holds" (see the module docstring), in place on plan["segments"][line-1]["anchors"]."""
    keeps = plan.get("keeps")
    for h in holds:
        li, src, secs = int(h["line"]), float(h["src"]), float(h["secs"])
        r = {"hold": True, "line": li, "src": src, "secs": secs}
        report.append(r)
        if not 1 <= li <= len(plan["segments"]) or secs <= 0:
            r["skip"] = "no such line, or secs <= 0"
            continue
        seg = plan["segments"][li - 1]
        ta, span, _sp, _vo, _vd, target = rows[li - 1]
        s_t = dc.to_tight(src, keeps)
        if not ta - 1e-6 <= s_t <= ta + span + 1e-6:
            r["skip"] = f"src {src} is outside line {li}'s window"
            continue
        if keeps and not any(a - 1e-6 <= src <= b + 1e-6 for a, b in keeps):
            r["warn"] = f"src {src} is inside a removed part of the recording: snapped to the next kept frame"
        layout = _layout_fn(ta, span, target, keeps)
        out = list(seg.get("anchors") or [])
        tseg, cost0 = layout(out)
        t_arr, dwell = _arrival(tseg, s_t)
        t_end = t_arr + dwell + secs
        clash = [o for o in out if t_arr + 1e-3 < o["at"] < t_end - 1e-3 and dc.to_tight(o["src"], keeps) > s_t + 1e-3]
        if clash:
            r["dropped"] = [o.get("target") or o["kind"] for o in clash]
            out = [o for o in out if o not in clash]
        new = [{"at": round(t_end, 3), "src": round(src, 3), "kind": "hold", "secs": secs}]
        if not any(abs(o["at"] - t_arr) <= 1e-3 and abs(dc.to_tight(o["src"], keeps) - s_t) <= 1e-3 for o in out):
            new.insert(0, {"at": round(t_arr, 3), "src": round(src, 3), "kind": "hold"})
        out = sorted(out + new, key=lambda o: o["at"])
        _t, cost = layout(out)
        r.update(at=round(t_arr, 2), until=round(t_end, 2), was_held=round(dwell, 2))
        if cost - cost0 > 0.05:
            r["late_or_longer"] = round(cost - cost0, 2)
        seg["anchors"] = out


def _paths(tag, plan_path, a):
    """Inputs by series convention; each one can be overridden on the command line."""
    S = SCRIPTS
    fz = a.freezes or next(iter(sorted(glob.glob(str(SERIES / "PREP" / f"{tag}_*_freezes.txt")))), None)
    rid = a.id or (pathlib.Path(fz).name[len(tag) + 1:].split("_")[0] if fz else None)
    if not fz:
        if not a.video:
            raise SystemExit(f"no freezes for {tag} in PREP/ - pass --freezes, or --video to detect them")
        import sa_plan_pacing as plan_pacing                # the same freezedetect the plan was cut with
        fz = plan_pacing.freezes(os.path.expanduser(a.video))
    if not rid:
        raise SystemExit("recording id unknown - pass --id")
    scr = a.screens or next((str(p).format(id=rid) for p in BOXED if os.path.exists(str(p).format(id=rid))), None)
    if not scr:
        raise SystemExit(f"no boxed OCR screens for {rid} - pass --screens")
    return (a.lines or str(S / f"{tag}_lines.txt"), a.marks or str(S / f"{tag}_marks.json"), scr, fz,
            a.out or str(pathlib.Path(plan_path).with_name(pathlib.Path(plan_path).stem + "_anchored.json")))


def _test():
    import sa_dubcut
    # a line: static list 0-4 s (the button on it), tap at 4.0, new screen 4.2-6 s
    scr = {"screens": [
        {"t": 0.0, "t_end": 4.0, "elements": [{"text": "View team →", "x": 1, "y": 5, "w": 5, "h": 5},
                                              {"text": "DEALS CLOSED", "x": 1, "y": 9, "w": 5, "h": 5}]},
        {"t": 4.0, "t_end": 6.0, "elements": [{"text": "SEPTEMBER TARGET", "x": 1, "y": 5, "w": 5, "h": 5}]}]}
    F = [(0.3, 4.0), (4.2, 6.0)]
    plan = {"source": "x.mp4", "gap": 1.7, "segments": [
        {"n": 1, "src": [0.0, 6.0], "zone": [0.0, 6.0], "vo": "no.mp3", "vo_dur": 7.0}]}
    marks = [{"line": 1, "say": "deals closed", "target": "DEALS CLOSED"},
             {"line": 1, "say": "Tap it", "target": "View team →"}]
    words = [[("Each", 0.2), ("card", 0.5), ("has", 0.8), ("deals", 1.0), ("closed.", 1.3),
              ("Tap", 5.0), ("it", 5.2)]]
    p, rep = anchors("t", ["x"], marks, plan, None, scr, F, words=words)
    an = p["segments"][0]["anchors"]
    tap = [a for a in an if a["mark"] == 2 and a["kind"] == "arrive"][0]
    assert abs(tap["at"] - 4.7) < 1e-9, tap
    assert tap["src"] <= 4.0 - KEEP * sa_dubcut.SPEED_MAX, "a tap anchor lands BEFORE the tap, with room"
    rows = sa_dubcut.build(p)
    pcs, pd, used, dropped, late = sa_dubcut.plan_pieces(*rows[0][:2], rows[0][5], an, None)
    seg = {"pieces": [[t0, s0, t1, s1, "hold" if sp is None else sp] for t0, s0, t1, s1, sp in pcs]}
    for t in (4.7, 5.35, 6.0):
        assert sa_dubcut.src_at(seg, t) < 4.0, f"the button is still there at voice {t}"
    assert not dropped and not late and pd == rows[0][5], "nothing dropped, late or lengthened"
    old = {"pieces": [[t0, s0, t1, s1, "hold" if sp is None else sp]
                      for t0, s0, t1, s1, sp in sa_dubcut.plan_pieces(*rows[0][:2], rows[0][5])[0]]}
    assert sa_dubcut.src_at(old, 6.0) > 4.0, "(without anchors it had tapped away by then)"
    # runs: exact text beats a look-alike, and a look-alike never counts once seen
    mk = {"target": "Leads"}
    s2 = [{"t": 0, "t_end": 2, "elements": [{"text": "Open Leads", "x": 1, "y": 1, "w": 1, "h": 1}]},
          {"t": 2, "t_end": 4, "elements": [{"text": "Open Leads", "x": 1, "y": 1, "w": 1, "h": 1},
                                            {"text": "Leads", "x": 1, "y": 9, "w": 1, "h": 1}]}]
    rs = runs(mk, s2, (0, 4), None, [(0.0, 1.9), (2.1, 4.0)])
    # (reads are labelled half a second early - see runs(): the read "2" is the frame at 2.47)
    assert [(r["a"], r["b"], r["steady"]) for r in rs] == [(2.1, 4.0, [(2.1, 4.0)])], rs
    # a fault cut splits a run; nothing inside the cut is ever offered
    rs = runs(mk, s2, (0, 4), [[0, 3], [3.5, 9]], [(2.1, 4.0)])
    assert [(r["a"], r["b"]) for r in rs] == [(2.1, 3), (3.5, 4.0)], rs
    # the target scrolling to a new place starts a new run
    s3 = [{"t": 0, "t_end": 2, "elements": [{"text": "Leads", "x": 1, "y": 9, "w": 1, "h": 1}]},
          {"t": 2, "t_end": 4, "elements": [{"text": "Leads", "x": 1, "y": 300, "w": 1, "h": 1}]}]
    assert len(runs(mk, s3, (0, 4), None, [])) == 2
    # a read inside a freeze stands for the whole freeze (identical frames; OCR misses words)
    s5 = [{"t": 9, "t_end": 10, "elements": [{"text": "Leads", "x": 1, "y": 9, "w": 1, "h": 1}]}]
    rs = runs(mk, s5, (0, 12), None, [(2.0, 10.5)])
    assert [(r["a"], r["b"]) for r in rs] == [(2.0, 10.5)], rs
    # the "Win probability" case, 24 Sep: read at y1765 at "215" and "216", at y800 at "217";
    # the freeze 215.87-217.27 holds the first place - reads are the picture half a second later
    s6 = [{"t": 215, "t_end": 217, "elements": [{"text": "Win probability", "x": 1, "y": 1765, "w": 1, "h": 1}]},
          {"t": 217, "t_end": 218, "elements": [{"text": "Win probability", "x": 1, "y": 800, "w": 1, "h": 1}]}]
    rs6 = runs({"target": "Win probability"}, s6, (214.5, 219.8), None, [(215.87, 217.27)])
    assert [(round(r["a"], 2), round(r["b"], 2)) for r in rs6] == [(215.47, 217.27), (217.47, 217.97)], rs6
    assert [(round(x[0], 2), x[4]) for x in candidates(rs6[:1], 215.1, None, (214.5, 219.8))] == \
        [(215.92, True), (215.52, False)], \
        "only the moment inside the freeze counts as steady"
    # a read that saw the target ELSEWHERE inside a freeze beats the freeze (a tiny scroll can
    # stay under freezedetect's noise floor)
    s7 = [{"t": 0, "t_end": 2, "elements": [{"text": "Leads", "x": 1, "y": 9, "w": 1, "h": 1}]},
          {"t": 2, "t_end": 3, "elements": [{"text": "Leads", "x": 1, "y": 300, "w": 1, "h": 1}]}]
    rs7 = runs(mk, s7, (0, 5), None, [(0.0, 5.0)])
    assert [(round(r["a"], 2), round(r["b"], 2)) for r in rs7] == [(0.0, 2.47), (2.47, 5.0)], rs7
    # outside the window (inside the zone) the recording is frozen on the window's edge
    assert all(3.0 <= x[0] <= 6.0 for x in candidates(rs, 1.0, None, (3.0, 6.0)))
    # candidates: early -> the steady screen's start; out of order -> nothing to offer;
    # a run that lasts to the window end keeps the target, so 'already on screen' stands
    run = {"a": 2.0, "b": 3.0, "steady": [(2.0, 3.0)]}
    c = candidates([run], 0.5, None, (0.0, 10.0))
    assert c and all(abs(x[0] - (2.0 + SETTLE)) < 1e-9 for x in c) and "pulled forward" in c[0][2]
    assert candidates([run], 0.5, 5.0, (0.0, 10.0)) == []
    c = candidates([{"a": 2.0, "b": 10.0, "steady": [(2.0, 4.0)]}], 8.0, None, (0.0, 10.0))
    assert (8.0, "already on screen") in [(x[0], x[2]) for x in c]
    # a keep pin appears only when the target would otherwise leave within KEEP s: the tap
    # is 0.5 s after the steady screen starts and the voice names it right at the start
    scr4 = {"screens": [{"t": 0.0, "t_end": 1.0, "elements": [{"text": "Send", "x": 1, "y": 5, "w": 5, "h": 5}]},
                        {"t": 1.0, "t_end": 6.0, "elements": [{"text": "Sent", "x": 1, "y": 5, "w": 5, "h": 5}]}]}
    p4 = {"source": "x.mp4", "gap": 1.7, "segments": [
        {"n": 1, "src": [0.0, 6.0], "zone": [0.0, 6.0], "vo": "no.mp3", "vo_dur": 2.0}]}
    p4, _r = anchors("t", ["x"], [{"line": 1, "say": "tap Send", "target": "Send"}], p4, None, scr4,
                     [(0.0, 0.8), (1.2, 6.0)], words=[[("tap", 0.4), ("Send", 0.6)]])
    kinds = [x["kind"] for x in p4["segments"][0]["anchors"]]
    assert kinds == ["arrive", "keep"], p4["segments"][0]["anchors"]
    rows = sa_dubcut.build(p4)
    pcs = sa_dubcut.plan_pieces(*rows[0][:2], rows[0][5], p4["segments"][0]["anchors"], None)[0]
    seg = {"pieces": [[t0, s0, t1, s1, "hold" if sp is None else sp] for t0, s0, t1, s1, sp in pcs]}
    assert sa_dubcut.src_at(seg, 0.1 + KEEP) <= 0.8, "Send still on screen KEEP s after it is named"
    # frame check (one module's marking 12, 24 Sep): screens.json says "Total" is up for the whole 0-6 s entry (a
    # merged read keeps its first read's boxes), but on the real frames it scrolls off at 0.6 s.
    # The keep window is read on the frames and the last frame that shows it is pinned.
    scr5 = {"screens": [{"t": 0.0, "t_end": 6.0, "elements": [{"text": "Total", "x": 1, "y": 5, "w": 5, "h": 5}]}]}
    p5 = {"source": "x.mp4", "gap": 1.7, "segments": [
        {"n": 1, "src": [0.0, 6.0], "zone": [0.0, 6.0], "vo": "no.mp3", "vo_dur": 7.0}]}
    real = lambda ts: [{"elements": ([{"text": "Total", "x": 1, "y": 5, "w": 5, "h": 5}] if t < 0.6 else
                                     [{"text": "Other", "x": 1, "y": 5, "w": 5, "h": 5}])} for t in ts]
    mk5 = [{"line": 1, "say": "the total", "target": "Total"}]
    w5 = [[("the", 0.5), ("total", 0.7)]]
    blind, _r = anchors("t", ["x"], mk5, p5, None, scr5, [(0.0, 6.0)], words=w5)
    seen, r5 = anchors("t", ["x"], mk5, p5, None, scr5, [(0.0, 6.0)], words=w5, frames=real)
    rows = sa_dubcut.build(p5)
    lay = lambda an: {"pieces": [[t0, s0, t1, s1, "hold" if sp is None else sp] for t0, s0, t1, s1, sp in
                                 sa_dubcut.plan_pieces(*rows[0][:2], rows[0][5], an, None)[0]]}
    at = seen["segments"][0]["anchors"][0]["at"]
    assert sa_dubcut.src_at(lay(blind["segments"][0]["anchors"]), at + KEEP) >= 0.6, "(blind: it had scrolled off)"
    an5 = seen["segments"][0]["anchors"]
    assert [x["kind"] for x in an5] == ["arrive", "keep"] and r5[0]["frame_pin"], an5
    for k in range(int(KEEP / 0.1) + 1):
        assert sa_dubcut.src_at(lay(an5), at + 0.1 * k) < 0.6, f"Total still on the frames at +{0.1 * k:.1f} s"
    # ...but an icon glyph flickering in and out of the OCR ("Approved v" / "Approved") is the
    # same element staying put: no pin
    assert _core("Approved v") == _core("Approved") == "approved" and _core("V Handover") == "handover"
    flick = lambda ts: [{"elements": [{"text": "Total v" if t < 0.6 else "Total", "x": 1, "y": 5, "w": 5, "h": 5}]}
                        for t in ts]
    scr6 = {"screens": [{"t": 0.0, "t_end": 6.0, "elements": [{"text": "Total v", "x": 1, "y": 5, "w": 5, "h": 5}]}]}
    p6, r6 = anchors("t", ["x"], [dict(mk5[0], target="Total v")], p5, None, scr6, [(0.0, 6.0)], words=w5,
                     frames=flick)
    assert [x["kind"] for x in p6["segments"][0]["anchors"]] == ["arrive"] and set(r6[0]["frames"]) == {"Y"}, r6
    # ...and a target that SLIDES (still on screen, 40 px lower) has left its box: pinned too
    slide = lambda ts: [{"elements": [{"text": "Total", "x": 1, "y": 5 if t < 0.6 else 45, "w": 5, "h": 5}]} for t in ts]
    p7, r7 = anchors("t", ["x"], mk5, p5, None, scr5, [(0.0, 6.0)], words=w5, frames=slide)
    assert [x["kind"] for x in p7["segments"][0]["anchors"]] == ["arrive", "keep"] and r7[0]["frame_pin"], r7
    # a LATE anchor (named in the line's first word, the screen still arriving): the 1.3 s the
    # placer needs count from the arrival, not from 'at' (that marking stayed skipped otherwise)
    scr8 = {"screens": [{"t": 0.6, "t_end": 6.0, "elements": [{"text": "Total", "x": 1, "y": 5, "w": 5, "h": 5}]}]}
    late = lambda ts: [{"elements": [{"text": "Total", "x": 1, "y": 5, "w": 5, "h": 5}] if 1.0 <= t < 1.3 else []}
                       for t in ts]
    p8, r8 = anchors("t", ["x"], [dict(mk5[0], say="Total")], p5, None, scr8, [(1.0, 6.0)],
                     words=[[("Total", 0.0), ("x", 0.5)]], frames=late)
    an8 = p8["segments"][0]["anchors"]
    arr = next(t / 100 for t in range(0, 300) if sa_dubcut.src_at(lay(an8), t / 100) >= 1.0)
    assert r8[0]["frame_pin"] and arr > 0.3, (an8, arr)
    assert sa_dubcut.src_at(lay(an8), arr + 1.45) < 1.3, "still on screen 1.45 s after it ARRIVES"
    # one missed read is OCR noise / a bounce (the placer tolerates it too): no pin
    bounce = lambda ts: [{"elements": [{"text": "Total", "x": 1, "y": 45 if 0.7 <= t < 0.8 else 5, "w": 5, "h": 5}]}
                         for t in ts]
    p9, r9 = anchors("t", ["x"], mk5, p5, None, scr5, [(0.0, 6.0)], words=w5, frames=bounce)
    assert [x["kind"] for x in p9["segments"][0]["anchors"]] == ["arrive"] and r9[0]["frames"].count(".") == 1, r9
    # a pin that would push the line past its voice (and every later line with it) is refused
    p10 = {"source": "x.mp4", "gap": 1.7, "segments": [
        {"n": 1, "src": [0.0, 6.0], "zone": [0.0, 6.0], "vo": "no.mp3", "vo_dur": 2.0}]}
    gone = lambda ts: [{"elements": [{"text": "Total", "x": 1, "y": 5, "w": 5, "h": 5}] if t < 0.5 else []}
                       for t in ts]
    p10, r10 = anchors("t", ["x"], mk5, p10, None, scr5, [(0.0, 6.0)], words=w5, frames=gone)
    assert [x["kind"] for x in p10["segments"][0]["anchors"]] == ["arrive"] and "would cost" in r10[0]["frame_check"]
    _test_overrides()
    print("anchors self-check: ok (tap lands before the tap, held 1.3 s, exact-match rule, "
          "fault cuts, scroll = new run, open-ended runs, keep pin only when needed, order, "
          "frame check pins what the frames show, spec overrides + holds move the picture not the voice)")


def _test_overrides():
    """Spec "anchor_overrides" and "holds" (QA against his own edit, 24 Sep): the picture moves as asked, the
    voice does not - every line of voice starts where it did."""
    import sa_dubcut
    # two lines. Line 1: the Open list 0-4 s ('Closed' tab on it), the tap at 4.0, the Closed list
    # 4.2-8 s. Its voice is 8 s: "... Tap Closed ... then Open".
    scr = {"screens": [
        {"t": 0.0, "t_end": 4.0, "elements": [{"text": "Closed", "x": 1, "y": 5, "w": 5, "h": 5},
                                              {"text": "Customer A", "x": 1, "y": 50, "w": 5, "h": 5}]},
        {"t": 4.0, "t_end": 8.0, "elements": [{"text": "Closed", "x": 1, "y": 5, "w": 5, "h": 5},
                                              {"text": "Deal closed 1 Sep", "x": 1, "y": 50, "w": 5, "h": 5}]},
        {"t": 8.0, "t_end": 12.0, "elements": [{"text": "Stage", "x": 1, "y": 5, "w": 5, "h": 5}]}]}
    F = [(0.3, 4.0), (4.2, 8.0), (8.2, 12.0)]
    plan = {"source": "x.mp4", "gap": 1.7, "segments": [
        {"n": 1, "src": [0.0, 8.0], "zone": [0.0, 8.0], "vo": "no1.mp3", "vo_dur": 8.3},
        {"n": 2, "src": [8.0, 12.0], "zone": [8.0, 12.0], "vo": "no2.mp3", "vo_dur": 4.0}]}
    words = [[("The", 0.2), ("deals", 0.5), ("list.", 0.8), ("Tap", 3.0), ("Closed", 3.3), ("for", 3.8),
              ("history,", 4.1), ("then", 6.6), ("Open.", 6.9)],
             [("Stage", 0.5), ("shows", 0.9)]]
    marks = [{"line": 1, "say": "Tap Closed", "target": "Closed"},
             {"line": 2, "say": "Stage", "target": "Stage"}]

    def lay(p, i=0):
        rows = sa_dubcut.build(p)
        return {"pieces": [[t0, s0, t1, s1, "hold" if sp is None else sp] for t0, s0, t1, s1, sp in
                           sa_dubcut.plan_pieces(*rows[i][:2], rows[i][5], p["segments"][i].get("anchors"), None)[0]]}

    def voice_starts(p):
        _l, holds, _s = sa_dubcut.anchored_layout(p)
        return [round(sum(holds[:i]), 6) for i in range(len(holds))]

    base, _r = anchors("t", ["x", "y"], marks, plan, None, scr, F, words=words)
    # (a) override an existing mark: 'Tap Closed' must show source 1.5 (the Open list, well before
    # the tap), not the moment OCR chose
    ov = [{"line": 1, "say": "Tap Closed", "src": 1.5}]
    got, rep = anchors("t", ["x", "y"], marks, plan, None, scr, F, words=words, overrides=ov)
    at = 3.0 - LEAD
    a1 = [a for a in got["segments"][0]["anchors"] if a.get("mark") == 1 and a["kind"] == "arrive"][0]
    assert a1["src"] == 1.5 and a1["override"] and abs(a1["at"] - at) < 1e-9, a1
    assert abs(sa_dubcut.src_at(lay(got), at) - 1.5) < 1e-6, "the picture shows the override's frame"
    assert abs(sa_dubcut.src_at(lay(base), at) - 1.5) > 0.2, "(without it the picture was elsewhere)"
    assert next(r for r in rep if r.get("mark") == 1)["why"] == "spec override"
    assert voice_starts(got) == voice_starts(base) == voice_starts(plan), "the voice never moves"
    # (b) an override with no mark: 'then Open' shows source 6.5 when it is said; the mark before
    # it is anchored in order round it
    ov2 = ov + [{"line": 1, "say": "then Open", "src": 6.5}]
    got2, rep2 = anchors("t", ["x", "y"], marks, plan, None, scr, F, words=words, overrides=ov2)
    an = got2["segments"][0]["anchors"]
    o2 = [a for a in an if a["kind"] == "override"][0]
    assert o2["src"] == 6.5 and abs(o2["at"] - (6.6 - LEAD)) < 1e-9 and o2["mark"] is None, an
    assert abs(sa_dubcut.src_at(lay(got2), 6.6 - LEAD) - 6.5) < 1e-6
    assert not any("late_or_longer" in r for r in rep2), rep2
    # one out of reach even at SPEED_MAX (1.5 -> 7.5 in 3.6 s) is met late and SAYS so
    _g, rep2b = anchors("t", ["x", "y"], marks, plan, None, scr, F, words=words,
                        overrides=ov + [{"line": 1, "say": "then Open", "src": 7.5}])
    assert next(r for r in rep2b if r.get("override"))["late_or_longer"] > 0
    assert [a["at"] for a in an] == sorted(a["at"] for a in an) and \
        [a["src"] for a in an] == sorted(a["src"] for a in an), "in order in voice and picture"
    rows = sa_dubcut.build(got2)
    assert not sa_dubcut.plan_pieces(*rows[0][:2], rows[0][5], an, None)[3], "no anchor dropped by sa_dubcut"
    assert voice_starts(got2) == voice_starts(plan)
    # words that are never said: reported, nothing applied
    _g, rep3 = anchors("t", ["x", "y"], marks, plan, None, scr, F, words=words,
                       overrides=[{"line": 1, "say": "not in the line", "src": 2.0}])
    assert any(r.get("override") and "skip" in r for r in rep3)
    # (c) a hold: stay on source 3.9 (the Open list just before the tap) 1.2 s longer; the tap then
    # comes 1.2 s later, the time is taken back from the motion after it, and the voice stays put
    hd = [{"line": 1, "src": 3.9, "secs": 1.2}]
    got3, rep4 = anchors("t", ["x", "y"], marks, plan, None, scr, F, words=words, overrides=ov, holds=hd)
    r4 = next(r for r in rep4 if r.get("hold"))
    assert "skip" not in r4 and "late_or_longer" not in r4, r4
    t_arr, until = [a["at"] for a in got3["segments"][0]["anchors"] if a["kind"] == "hold"]
    assert abs(until - t_arr - r4["was_held"] - 1.2) < 1e-6 and abs(r4["at"] - t_arr) < 0.01
    L3, L1 = lay(got3), lay(got)
    for k in range(13):
        t = t_arr + k * (until - t_arr) / 12
        assert abs(sa_dubcut.src_at(L3, t) - 3.9) < 1e-3, f"held on 3.9 at {t:.2f}"
    after = next(t / 100 for t in range(int(until * 100), 2000) if sa_dubcut.src_at(L3, t / 100) > 3.95)
    before = next(t / 100 for t in range(int(t_arr * 100), 2000) if sa_dubcut.src_at(L1, t / 100) > 3.95)
    assert after >= before + 1.0, ("the transition after the still comes later", before, after)
    assert abs(sa_dubcut.src_at(L3, at) - 1.5) < 1e-6, "the override before it still holds"
    assert voice_starts(got3) == voice_starts(plan), "the voice never moves"
    assert [a["kind"] for a in got3["segments"][0]["anchors"]].count("hold") == 2
    assert "moves_voice" not in r4, "paid back inside the line: no later voice moves"
    # one that cannot be paid back (5 s on 3.9 in a 10 s line that must still show 3.9 -> 8.0)
    # lengthens its line; every later line of voice moves by exactly that, and the report says so
    got6, rep6 = anchors("t", ["x", "y"], marks, plan, None, scr, F, words=words, holds=[{"line": 1, "src": 3.9, "secs": 5.0}])
    r6 = next(r for r in rep6 if r.get("hold"))
    assert r6.get("moves_voice", 0) > 0.5, r6
    assert abs(voice_starts(got6)[1] - voice_starts(plan)[1] - r6["moves_voice"]) < 0.02, (voice_starts(got6), r6)
    # a hold outside the line's window is refused, not clamped onto another screen
    _g, rep5 = anchors("t", ["x", "y"], marks, plan, None, scr, F, words=words,
                       holds=[{"line": 1, "src": 9.0, "secs": 1.0}])
    assert "skip" in next(r for r in rep5 if r.get("hold"))
    # (d) end to end: sa_dubcut renders the overridden plan - the frame on screen when the words are
    # said is the override's source frame, and every line of voice starts where it did
    import shutil, subprocess, tempfile, contextlib, io
    ff = shutil.which("ffmpeg")
    if not ff:
        print("  (ffmpeg not found - render check skipped)")
        return
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, "src.mp4")              # frame N is painted grey level 16 + N
        subprocess.run([ff, "-v", "error", "-y", "-f", "lavfi", "-i",
                        "color=c=black:s=32x32:r=30:d=12,format=gray,geq=lum='16+N/2'",
                        "-c:v", "libx264", "-crf", "0", "-pix_fmt", "yuv420p", "-r", "30", src], check=True)
        for name, dur in (("no1.mp3", 8.3), ("no2.mp3", 4.0)):
            subprocess.run([ff, "-v", "error", "-y", "-f", "lavfi", "-i", f"sine=f=440:d={dur}",
                            os.path.join(d, name)], check=True)
        timings = []
        for p in (base, got3):
            q = json.loads(json.dumps(p))
            q["source"] = src
            for sg in q["segments"]:
                sg["vo"] = os.path.join(d, sg["vo"])
            out = os.path.join(d, "out.mp4")
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                sa_dubcut.render(q, out)
            timings.append(json.load(open(os.path.join(d, "out.timing.json"))))
        raw = subprocess.run([ff, "-v", "error", "-i", out, "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                             capture_output=True).stdout
        fr = [(sum(raw[i * 1024:(i + 1) * 1024]) / 1024 - 16) * 2 / 30 for i in range(len(raw) // 1024)]
        k = int(round(at * 30))
        assert abs(fr[k] - 1.5) <= 0.07, ("the cut shows source 1.5 s when 'Tap Closed' is said", fr[k])
        k = int(round((t_arr + until) / 2 * 30))
        assert abs(fr[k] - 3.9) <= 0.07, ("the still", fr[k])
        assert [s["start"] for s in timings[0]["segments"]] == [s["start"] for s in timings[1]["segments"]], \
            "voice lines start at the same times in the rendered cut"
        assert timings[1]["segments"][0]["anchors"][0][1] == 1.5



if __name__ == "__main__":
    if "--test" in sys.argv:
        _test()
        sys.exit()
    ap = argparse.ArgumentParser()
    ap.add_argument("tag"); ap.add_argument("plan")
    ap.add_argument("--screens"); ap.add_argument("--freezes"); ap.add_argument("--lines")
    ap.add_argument("--marks"); ap.add_argument("--out"); ap.add_argument("--id")
    ap.add_argument("--video", help="the VERTICAL recording, to detect freezes when PREP has none")
    a = ap.parse_args()
    lines_p, marks_p, scr, fz, out = _paths(a.tag, a.plan, a)
    plan = json.load(open(a.plan))
    lines = pathlib.Path(lines_p).read_text().strip().split("\n")
    mspec = json.load(open(marks_p))
    marks = mspec["marks"]
    vo_dir = os.path.dirname(plan["segments"][0]["vo"])
    if not os.path.exists(plan["source"]):
        raise SystemExit(f"{plan['source']} missing - the anchors are checked on its frames")
    p, rep = anchors(a.tag, lines, marks, plan, vo_dir, scr, fz,
                     cache=os.path.splitext(out)[0] + "_words.json", frames=source_frames(plan["source"]),
                     overrides=mspec.get("anchor_overrides"), holds=mspec.get("holds"))
    json.dump(p, open(out, "w"), indent=1)
    n_an = sum(1 for r in rep if "src" in r and "mark" in r)
    for r in rep:
        who = (f"hold  line {r['line']:2d} src {r['src']} +{r['secs']} s" if r.get("hold") else
               f"override line {r['line']:2d} '{r['say']}'" if "mark" not in r else
               f"mark {r['mark']:2d} line {r['line']:2d} '{r['say']}'")
        if "skip" in r:
            print(f"  {who}: not applied - {r['skip']}")
        elif "frame_check" in r:
            print(f"  {who}: {r['frame_check']}")
        for k in ("warn", "dropped", "late_or_longer", "moves_voice"):
            if k in r and (r.get("hold") or r.get("why") == "spec override" or r.get("override")):
                print(f"  {who}: {k} {r[k]}")
    rep_m = [r for r in rep if "mark" in r]
    moved = [r for r in rep_m if "src" in r and abs(r["moved"]) >= 0.05]
    n_ov = sum(1 for r in rep if r.get("why") == "spec override" or (r.get("override") and "skip" not in r))
    n_h = sum(1 for r in rep if r.get("hold") and "skip" not in r)
    print(f"{a.tag}: {n_an}/{len(rep_m)} markings anchored ({len(moved)} moved the picture, "
          f"{sum(1 for r in rep_m if 'keep' in r)} with a keep pin, "
          f"{sum(1 for r in rep_m if r.get('frame_pin'))} set by the frame check"
          + (f", {n_ov} spec override(s), {n_h} hold(s)" if n_ov or n_h else "") + f") -> {out}")
    json.dump(rep, open(os.path.splitext(out)[0] + "_report.json", "w"), indent=1)
