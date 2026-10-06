#!/usr/bin/env python3
"""Build one brand tutorial module as a HyperFrames/GSAP composition, timed to its voice-over.

    python3 build_module.py example/module.json --brand brand.example.json \
        --words example/words.example.json --out build/acme_m1
    python3 build_module.py example/module.json --brand brand.example.json \
        --words example/words.example.json --check
    python3 build_module.py example/module.json --brand brand.example.json \
        --synthetic --write-words example/words.example.json      # lay out before any voice exists

Inputs
  module.json  script lines, scene plan, on-screen copy and the spoken word each item lands on
  brand.json   name, colours, fonts (installed PostScript names), optional logo, type tokens
  words.json   per voice-over clip: file, text, dur and word timestamps (vo_words.py makes it)

Outputs (with --out build/<id>)
  build/<id>/index.html, hyperframes.json, package.json   the composition, rendered by HyperFrames
  build/<id>_timing.json     total, vo_starts, scene windows, vo_files   (mux_preview.py reads it)
  build/<id>_edit_plan.json  vo_placement, captions.cues, music, runtime  (the CapCut hand-off)
  build/<id>.srt             captions: one line each, never longer than the brand's max_chars

The method this encodes (playbooks/hyperframes-brand-tutorials.md):
  * A FIXED TIMING CORE. Title, gap, hold, tail and end-frame constants, or voice-over starts
    taken from an editor's edit plan, decide every scene window and the total. Picture
    variants share the core, so any of them drops into the same CapCut review draft.
  * ONE CONTINUOUS 3D DEPTH WORLD. A backdrop of line shards at several depths; the camera
    pushes through it at every scene change (a camera move, not a cut). Items arrive from
    depth, and readable text always lands FLAT at z = 0, facing the camera.
  * EVERY ON-SCREEN WORD ON ITS SPOKEN BEAT. Items are cued to word timestamps, never to
    guessed seconds; a cue word the voice does not say is an error, not a fallback.
  * ONE MOVEMENT PER BEAT. No spring wobbles; text arrives after the motion settles.
  * The 3D z-sort trap is designed out: a child never animates from negative z inside a
    preserve-3d parent that has its own background (it sorts behind the face, the fade is
    invisible, and the DOM still reports opacity rising). Card text moves on y only.

Production tools these were generalised from (written by AI coding agents under the
author's direction): ../../../tools/sa_vo_words.py, ../../../tools/sa_verify_fonts.py
and ../../../tools/sa_capcut_build_from_plan.py; the preview muxer is published only
as mux_preview.py in this folder.
Standard library only. GSAP is referenced from its CDN, not vendored.
"""
import argparse
import html
import json
import pathlib
import re
import shutil
import sys

# ---------------------------------------------------------------- the fixed timing core
TITLE = 5.0        # title card before the first line
LEAD = 0.2         # the first line starts this long after the title card
GAP = 0.9          # default air between voice-over lines (a screen has to settle)
TAIL = 2.5         # hold after the last line, before the end frame
END = 6.3          # end frame; the CapCut builder expects this length
SCENE_LEAD = 0.3   # a scene opens this long before its first line is spoken
EXIT = 0.35        # each scene's rig rushes past camera in its last EXIT seconds
CUE_OFFSET = -0.15 # items land just before their word, like a call-out box
FPS = 30
W, H = 1920, 1080
CAPTION_TOP = 960  # keep picture text above this line; captions live below it
GSAP_CDN = "https://cdn.jsdelivr.net/npm/gsap@3.12.5/dist/gsap.min.js"
HF_VERSION = "0.8.91"  # the HyperFrames CLI version this template was used with (needs Node 22+)
SMALL_WORDS = {"in", "the", "of", "to", "a", "an", "and", "on", "for", "at", "is", "your", "with"}


def r2(x):
    return round(float(x) + 1e-9, 2)


def norm(w):
    return re.sub(r"[^a-z0-9]", "", w.lower().replace("&", "and"))


def slug(text, n=28):
    return re.sub(r"[^a-z0-9]+", "_", text.lower())[:n].strip("_") or "line"


def esc(s):
    return html.escape(str(s), quote=True)


# ---------------------------------------------------------------- inputs
def load_json(path):
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def synthetic_words(module, wps=2.7):
    """Evenly spaced words at `wps` words per second: lets you lay out and preview a module
    before any voice exists. Loudly marked; never render a final from it."""
    out = []
    for i, text in enumerate(module["lines"], 1):
        toks = text.split()
        step = 1.0 / wps
        words = [{"w": t, "s": r2(k * step), "e": r2(k * step + step * 0.85)} for k, t in enumerate(toks)]
        out.append({"file": f"vo/{module['id']}/{i:02d}_{slug(text)}.mp3", "text": text,
                    "dur": r2(len(toks) * step + 0.25), "words": words, "synthetic": True})
    return out


# ---------------------------------------------------------------- timing
class Timing:
    def __init__(self, module, words):
        self.module, self.words = module, words
        n = len(module["lines"])
        if len(words) != n:
            raise SystemExit(f"{len(words)} voice-over clips vs {n} script lines")
        if module.get("vo_starts"):                      # locked by an editor's edit plan
            self.starts = [r2(s) for s in module["vo_starts"]]
            if len(self.starts) != n:
                raise SystemExit("vo_starts must have one entry per line")
            self.from_plan = True
        else:
            holds = {int(k): float(v) for k, v in module.get("holds", {}).items()}
            t, self.starts = TITLE + LEAD, []
            for i, w in enumerate(words, 1):
                self.starts.append(r2(t))
                t += float(w["dur"]) + GAP + holds.get(i, 0.0)
            self.from_plan = False
        self.body_end = r2(self.starts[-1] + float(words[-1]["dur"]) + TAIL)
        self.total = r2(self.body_end + END)
        self.warnings = []
        self.scenes = self._scenes()

    def vo(self, line):
        return self.starts[line - 1]

    def _scenes(self):
        sc = self.module["scenes"]
        firsts = [self.vo(s["lines"][0]) - SCENE_LEAD for s in sc]
        out = {"open": (0.0, r2(firsts[0]))}
        for k, s in enumerate(sc):
            a = firsts[k]
            b = firsts[k + 1] if k + 1 < len(sc) else self.body_end
            out[s["id"]] = (r2(a), r2(b - a))
        out["end"] = (self.body_end, r2(END))
        for name, (a, d) in out.items():
            if d <= 0.5:
                raise SystemExit(f"scene '{name}' is {d}s long: reorder scenes or lines")
        return out

    def start(self, sid):
        return self.scenes[sid][0]

    def stop(self, sid):
        a, d = self.scenes[sid]
        return r2(a + d)

    def cue(self, spec):
        """A cue spec -> timeline seconds. {"line": n, "word": "w", "nth": 1, "offset": -0.15}
        or {"line": n, "at": "start" | "end"}. A word the voice does not say is an ERROR."""
        line = int(spec["line"])
        base = self.vo(line)
        off = float(spec.get("offset", CUE_OFFSET))
        if spec.get("at") == "start":
            return r2(base + max(off, 0.0))
        if spec.get("at") == "end":
            return r2(base + float(self.words[line - 1]["dur"]) + off)
        want, nth, seen = norm(spec["word"]), int(spec.get("nth", 1)), 0
        for w in self.words[line - 1]["words"]:
            if norm(w["w"]).startswith(want):
                seen += 1
                if seen == nth:
                    return r2(base + float(w["s"]) + off)
        raise KeyError(f"cue word '{spec['word']}' #{nth} is not heard in line {line}")

    def word_beats(self, line, text):
        """Each word of `text` -> the time it is spoken in `line`, matched in order. Words the
        recogniser split or merged are interpolated between their neighbours and reported."""
        heard = [(norm(w["w"]), float(w["s"])) for w in self.words[line - 1]["words"]]
        base, ptr, out = self.vo(line), 0, []
        for tok in text.split():
            n, hit = norm(tok), None
            for j in range(ptr, len(heard)):
                if n and (heard[j][0] == n or heard[j][0].startswith(n) or n.startswith(heard[j][0] or "#")):
                    hit = j
                    break
            if hit is None:
                out.append((tok, None))
            else:
                out.append((tok, r2(base + heard[hit][1])))
                ptr = hit + 1
        known = [t for _, t in out if t is not None]
        if not known:
            raise KeyError(f"none of '{text}' is heard in line {line}")
        for i, (tok, t) in enumerate(out):                 # fill gaps from the neighbours
            if t is None:
                prev = next((out[k][1] for k in range(i - 1, -1, -1) if out[k][1] is not None), known[0])
                nxt = next((out[k][1] for k in range(i + 1, len(out)) if out[k][1] is not None), prev + 0.4)
                out[i] = (tok, r2((prev + nxt) / 2))
                self.warnings.append(f"line {line}: '{tok}' not heard, placed between its neighbours")
        return out


# ---------------------------------------------------------------- captions
def caption_cues(timing, max_chars):
    """Phrases cut on the words: break at punctuation, never over max_chars, never end a
    phrase on a small word ('role in' / 'the ...'); each cue holds until the next starts."""
    cues = []
    for i, (text, w) in enumerate(zip(timing.module["lines"], timing.words), 1):
        toks, ws = text.split(), w["words"]
        if not ws:
            raise SystemExit(f"line {i} has no word timestamps")
        ws = ws[:len(toks)] + [ws[-1]] * max(0, len(toks) - len(ws))
        phrases, cur = [], []
        for tok, wd in zip(toks, ws):
            if cur and len(" ".join(t for t, _ in cur + [(tok, None)])) > max_chars:
                phrases.append(cur)
                cur = []
            cur.append((tok, wd))
            if tok.endswith((",", ".", ":", ";", "?", "!")) and len(" ".join(t for t, _ in cur)) > 12:
                phrases.append(cur)
                cur = []
        if cur:
            phrases.append(cur)
        for k in range(len(phrases) - 1):                  # a trailing small word moves on
            while len(phrases[k]) > 1 and phrases[k][-1][0].lower().strip(",.") in SMALL_WORDS \
                    and not phrases[k][-1][0].endswith((",", ".")):
                phrases[k + 1].insert(0, phrases[k].pop())
        base = timing.vo(i)
        nxt_line = timing.vo(i + 1) if i < len(timing.starts) else timing.body_end
        for k, ph in enumerate(phrases):
            start = r2(base + float(ph[0][1]["s"]))
            if k + 1 < len(phrases):
                end = r2(base + float(phrases[k + 1][0][1]["s"]) - 1.0 / FPS)   # no blink between phrases
            else:
                end = r2(min(base + float(ph[-1][1]["e"]) + 0.3, nxt_line - 0.05))
            cues.append({"start": start, "end": max(end, r2(start + 0.3)),
                         "text": " ".join(t for t, _ in ph)})
    return cues


def srt(cues):
    def stamp(t):
        ms = int(round(t * 1000))
        h, ms = divmod(ms, 3_600_000)
        m, ms = divmod(ms, 60_000)
        s, ms = divmod(ms, 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
    return "\n".join(f"{i}\n{stamp(c['start'])} --> {stamp(c['end'])}\n{c['text']}\n"
                     for i, c in enumerate(cues, 1))


# ---------------------------------------------------------------- the composition
def tw(method, sel, *objs, at):
    """One GSAP tween as a JS line; json.dumps keeps braces and quoting correct."""
    return f"tl.{method}({json.dumps(sel)}, {', '.join(json.dumps(o) for o in objs)}, {r2(at)});"


SHARDS = [  # left, top, width, height, z, opacity
    (-900, -700, 3700, 2500, -1500, .45), (-160, 60, 760, 300, -900, .9),
    (1350, 80, 700, 380, -600, .8), (-120, 700, 640, 420, -350, .7),
    (1400, 720, 760, 300, -1100, .9), (620, -260, 820, 240, -1250, .8),
    (560, 1010, 900, 260, -800, .7), (1700, 380, 420, 520, -250, .55),
]


class Composer:
    def __init__(self, module, brand, timing):
        self.m, self.b, self.t = module, brand, timing
        self.js, self.uid = [], 0

    def nid(self, p):
        self.uid += 1
        return f"{p}{self.uid}"

    # ---- items: each returns HTML and appends its tweens
    def item(self, it, sid):
        kind = it["type"]
        if kind == "kicker":
            i = self.nid("k")
            self.js.append(tw("fromTo", f"#{i}", {"opacity": 0, "y": 18}, {"opacity": 1, "y": 0, "duration": .6, "ease": "power3.out"}, at=self.t.cue(it["cue"])))
            return f'<div class="kicker t-small" id="{i}">{esc(it["text"])}</div>'
        if kind == "headline":
            i = self.nid("h")
            self.js.append(tw("fromTo", f"#{i}", {"yPercent": 110}, {"yPercent": 0, "duration": .8, "ease": "expo.out"}, at=self.t.cue(it["cue"])))
            return f'<div class="mask"><span class="h-l" id="{i}">{esc(it["text"])}</span></div>'
        if kind == "sub":
            i = self.nid("s")
            self.js.append(tw("fromTo", f"#{i}", {"opacity": 0, "y": 24}, {"opacity": 1, "y": 0, "duration": .6, "ease": "power3.out"}, at=self.t.cue(it["cue"])))
            return f'<div class="sub t-mid" id="{i}">{esc(it["text"])}</div>'
        if kind == "words":                                   # every word on its spoken beat
            spans = []
            for tok, at in self.t.word_beats(int(it["line"]), it["text"]):
                i = self.nid("w")
                self.js.append(tw("fromTo", f"#{i}", {"opacity": 0, "y": 14}, {"opacity": 1, "y": 0, "duration": .35, "ease": "power2.out"}, at=at - 0.05))
                spans.append(f'<span class="w" id="{i}">{esc(tok)}</span>')
            return f'<p class="vo-words t-mid">{" ".join(spans)}</p>'
        if kind == "chips":                                   # flat parent with no background: z is safe
            out = []
            for c in it["items"]:
                i = self.nid("c")
                self.js.append(tw("fromTo", f"#{i}", {"opacity": 0, "z": -500}, {"opacity": 1, "z": 0, "duration": .7, "ease": "power3.out"}, at=self.t.cue(c["cue"])))
                out.append(f'<span class="chip t-small" id="{i}">{esc(c["text"])}</span>')
            return f'<div class="chips">{"".join(out)}</div>'
        if kind == "cards":                                   # the card moves in z; its text on y only
            out = []
            for c in it["items"]:
                i = self.nid("card")
                at = self.t.cue(c["cue"])
                self.js.append(tw("fromTo", f"#{i}", {"opacity": 0, "z": -1400, "rotationY": -28}, {"opacity": 1, "z": 0, "rotationY": 0, "duration": .8, "ease": "power3.out"}, at=at))
                self.js.append(tw("fromTo", f"#{i} .card-in", {"opacity": 0, "y": 16}, {"opacity": 1, "y": 0, "duration": .45, "ease": "power2.out"}, at=at + 0.6))
                out.append(f'<div class="card" id="{i}"><div class="card-in"><div class="card-t">{esc(c["title"])}</div>'
                           f'<div class="card-b t-small">{esc(c.get("body", ""))}</div></div></div>')
            return f'<div class="cards">{"".join(out)}</div>'
        if kind == "stamp":
            i = self.nid("st")
            self.js.append(tw("fromTo", f"#{i}", {"opacity": 0, "scale": 1.25}, {"opacity": 1, "scale": 1, "duration": .5, "ease": "back.out(1.6)"}, at=self.t.cue(it["cue"])))
            return f'<div class="stamp" id="{i}">{esc(it["text"])}</div>'
        raise SystemExit(f"scene {sid}: unknown item type '{kind}'")

    def backdrop(self):
        ids = [s["id"] for s in self.m["scenes"]] + ["end"]
        ry = [0, 4, -4, 3, -3, 4, -4, 0, 3, 0] * 4
        keys = [(0.0, -260, 0)]
        for k, sid in enumerate(ids):
            b = self.t.start(sid)
            keys.append((r2(b - 0.4), 0, ry[k]))
            keys.append((r2(b + 1.0), 340, ry[k + 1]))
        keys.append((self.t.total, 120, 0))
        for i, s in enumerate(SHARDS):
            self.js.append(tw("set", f"#sh{i}", {"z": s[4]}, at=0))
        for (t0, z0, y0), (t1, z1, y1) in zip(keys, keys[1:]):
            push = z1 > z0
            self.js.append(tw("fromTo", "#bgcam", {"z": z0, "rotationY": y0},
                              {"z": z1, "rotationY": y1, "duration": r2(max(t1 - t0, .05)),
                               "ease": "power3.inOut" if push else "sine.inOut", "immediateRender": False}, at=t0))
        # background colour per scene: deep / paper / void, cross-faded just before the push
        bgs = {s["id"]: s.get("bg", "deep") for s in self.m["scenes"]}
        bgs["end"] = "paper"
        self.js.append(tw("set", "#bgpaper, #bgvoid", {"opacity": 0}, at=0))
        prev = "deep"
        for sid in ids:
            cur = bgs[sid]
            if cur != prev:
                at = self.t.start(sid) - 0.35
                for layer, name in (("#bgpaper", "paper"), ("#bgvoid", "void")):
                    self.js.append(tw("fromTo", layer, {"opacity": 1 if prev == name else 0},
                                      {"opacity": 1 if cur == name else 0, "duration": .6, "ease": "power2.inOut", "immediateRender": False}, at=at))
                ink = self.b["colours"]["ink" if cur == "paper" else "paper"]
                self.js.append(tw("to", "#mark", {"color": ink, "duration": .4}, at=at))
            prev = cur
        return "".join(f'<div class="shard" id="sh{i}" style="left:{l}px;top:{t}px;width:{w}px;height:{h}px;opacity:{o}"></div>'
                       for i, (l, t, w, h, _, o) in enumerate(SHARDS))

    def section(self, sid, inner, bg):
        a, d = self.t.scenes[sid]
        return (f'<section id="sc-{sid}" class="clip on-{bg}" data-start="{a}" data-duration="{d}">'
                f'<div class="rig"><div class="stack">{inner}</div></div></section>')

    def exit(self, sid):
        self.js.append(tw("to", f"#sc-{sid} .rig", {"z": 620, "opacity": 0, "duration": EXIT, "ease": "power2.in"}, at=self.t.stop(sid) - EXIT))

    def build(self):
        shards = self.backdrop()
        parts = []
        # open: the title card
        self.js.append(tw("fromTo", "#t-title", {"yPercent": 110}, {"yPercent": 0, "duration": 1.0, "ease": "expo.out"}, at=0.5))
        self.js.append(tw("fromTo", "#t-rule", {"scaleX": 0}, {"scaleX": 1, "duration": .8, "ease": "power3.inOut"}, at=1.2))
        self.js.append(tw("fromTo", "#t-sub", {"opacity": 0, "y": 24}, {"opacity": 1, "y": 0, "duration": .8, "ease": "power3.out"}, at=1.6))
        self.exit("open")
        parts.append(self.section("open", f'<div class="mask"><h1 class="h-xl" id="t-title">{esc(self.m["title"])}</h1></div>'
                                  f'<div class="rule" id="t-rule"></div><div class="sub t-mid" id="t-sub">{esc(self.m.get("subtitle", ""))}</div>', "deep"))
        for s in self.m["scenes"]:
            inner = "".join(self.item(it, s["id"]) for it in s["items"])
            parts.append(self.section(s["id"], inner, s.get("bg", "deep")))
            self.exit(s["id"])
        # end frame: the wordmark (or logo) lands from depth, then the completion line
        ea = self.t.start("end")
        self.js.append(tw("to", "#mark", {"opacity": 0, "duration": .3}, at=ea - 0.2))
        self.js.append(tw("fromTo", "#end-mark", {"opacity": 0, "z": -900}, {"opacity": 1, "z": 0, "duration": 1.2, "ease": "power3.out"}, at=ea + 0.2))
        self.js.append(tw("fromTo", "#end-txt", {"opacity": 0, "y": 24}, {"opacity": 1, "y": 0, "duration": .7, "ease": "power3.out"}, at=ea + 1.1))
        mark = self.mark_html("end-mark", "end-mark")
        parts.append(self.section("end", f'{mark}<div class="sub t-mid" id="end-txt">{esc(self.m.get("end_text", ""))}</div>', "paper"))
        return shards, "\n".join(parts)

    def mark_html(self, el_id, cls):
        logo = self.b.get("logo")
        if logo:
            return f'<img id="{el_id}" class="{cls}" src="assets/{esc(pathlib.Path(logo).name)}" alt="{esc(self.b["name"])}" />'
        return f'<div id="{el_id}" class="{cls} wordmark">{esc(self.b.get("wordmark", self.b["name"]))}</div>'


def font_faces(brand):
    rules = []
    for role in ("display", "text"):
        f = brand["fonts"][role]
        for weight, ps in sorted(f["faces"].items()):
            rules.append(f'@font-face {{ font-family: "{f["family"]}"; src: local("{ps}"); '
                         f'font-weight: {weight}; font-style: normal; }}')
    return "\n".join(rules)


CSS = """
$faces
:root { --deep:$deep; --void:$void; --paper:$paper; --ink:$ink; --accent:$accent; --mist:$mist; }
* { margin:0; padding:0; box-sizing:border-box; }
html, body { width:${W}px; height:${H}px; overflow:hidden; background:var(--deep); }
#root { position:relative; width:${W}px; height:${H}px; overflow:hidden; color:var(--paper);
  font-family:"$text", $fallback; font-synthesis:none; font-kerning:normal;
  background:radial-gradient(120% 90% at 50% 45%, var(--deep) 0%, var(--void) 100%);
  /* type tokens: custom properties inherit UNRESOLVED, so each element resolves the em
     against its own size. (word-spacing:.08em set on #root would resolve ONCE, against
     #root's 16px, and every child would inherit ~1.3px.) */
  --ls:$base_ls; --ws:$base_ws; }
:where(#root *:not(svg, svg *)) { letter-spacing:var(--ls); word-spacing:var(--ws); }
.t-small { --ls:$small_ls; --ws:$small_ws; }   /* text at or under ~26px */
.t-mid { --ls:$mid_ls; --ws:$mid_ws; }         /* 38-54px lines at z = 0 */
#bgpaper { position:absolute; inset:0; background:var(--paper); opacity:0; }
#bgvoid { position:absolute; inset:0; background:var(--void); opacity:0; }
#bgw { position:absolute; inset:0; perspective:1600px; }
#bgcam { position:absolute; inset:0; transform-style:preserve-3d; }
.shard { position:absolute; background:repeating-linear-gradient(${angle}deg, transparent 0 22px, color-mix(in srgb, var(--accent) 22%, transparent) 22px 25px); }
#vig { position:absolute; inset:0; background:radial-gradient(75% 70% at 50% 48%, transparent 55%, rgba(0,0,0,.35) 100%); }
.clip { position:absolute; inset:0; overflow:hidden; perspective:1600px; perspective-origin:50% 50%; }
.rig { position:absolute; inset:0; transform-style:preserve-3d; }
/* the safe area: >=160px side padding, nothing below the caption line */
.stack { position:absolute; left:160px; right:160px; top:120px; bottom:${stack_bottom}px; display:flex; flex-direction:column;
  align-items:center; justify-content:center; gap:30px; text-align:center; transform-style:preserve-3d; }
.on-paper { color:var(--ink); }
.mask { overflow:hidden; display:inline-block; padding-bottom:.1em; }
.mask > * { display:inline-block; }
.h-xl, .h-l, .stamp, .card-t, .wordmark { font-family:"$display", $fallback; --ls:$head_ls; --ws:$head_ws; }
.h-xl { font-weight:700; font-size:112px; line-height:1.02; }
.h-l { font-weight:700; font-size:88px; line-height:1.05; }
.sub { font-weight:400; font-size:40px; line-height:1.3; color:var(--mist); }
.on-paper .sub { color:color-mix(in srgb, var(--ink) 70%, transparent); }
.rule { width:180px; height:4px; background:var(--accent); border-radius:2px; transform-origin:50% 50%; }
/* uppercase kicker: the trailing tracking is taken back so centring stays true */
.kicker { font-weight:500; font-size:26px; text-transform:uppercase; --ls:$kick_ls; margin-right:calc(-1 * $kick_ls); color:var(--accent); }
.vo-words { font-weight:400; font-size:48px; line-height:1.25; max-width:1400px; }
.vo-words .w { display:inline-block; }
.chips { display:flex; flex-wrap:wrap; gap:18px; justify-content:center; transform-style:preserve-3d; }
.chip { display:inline-flex; font-weight:500; font-size:26px; padding:14px 28px; border-radius:40px;
  border:2px solid color-mix(in srgb, var(--accent) 60%, transparent); }
.cards { display:flex; gap:40px; justify-content:center; transform-style:preserve-3d; }
.card { width:440px; padding:44px 40px; border-radius:22px; background:#fff; color:var(--ink); text-align:left;
  box-shadow:0 50px 90px -40px rgba(0,0,0,.45); }
.card-t { font-weight:700; font-size:56px; line-height:1.05; color:var(--accent); }
.card-b { font-weight:500; font-size:26px; margin-top:14px; }
.stamp { font-weight:700; font-size:96px; padding:10px 40px; border:6px solid var(--accent); border-radius:18px; color:var(--paper); }
#mark { position:absolute; top:56px; right:72px; z-index:50; font-size:30px; }
.wordmark { font-weight:700; }
.end-mark.wordmark { font-size:120px; color:var(--ink); }
img.end-mark { width:300px; }
"""


def page(module, brand, timing):
    comp = Composer(module, brand, timing)
    shards, sections = comp.build()
    c, f, ty = brand["colours"], brand["fonts"], brand.get("type", {})
    tok = lambda k, sub, d: ty.get(k, {}).get(sub, d)          # noqa: E731
    from string import Template
    css = Template(CSS).substitute(
        faces=font_faces(brand), W=W, H=H, angle=brand.get("motif_angle", 135),
        deep=c["deep"], void=c["void"], paper=c["paper"], ink=c["ink"], accent=c["accent"], mist=c["mist"],
        text=f["text"]["family"], display=f["display"]["family"], fallback=f.get("fallback", "Georgia, serif"),
        base_ls=tok("base", "ls", ".015em"), base_ws=tok("base", "ws", ".07em"),
        small_ls=tok("small", "ls", ".025em"), small_ws=tok("small", "ws", ".08em"),
        mid_ls=tok("mid", "ls", ".008em"), mid_ws=tok("mid", "ws", ".05em"),
        head_ls=tok("headline", "ls", "-.012em"), head_ws=tok("headline", "ws", ".045em"),
        kick_ls=tok("kicker", "ls", ".12em"), stack_bottom=H - CAPTION_TOP + 20)
    mark = comp.mark_html("mark", "mark")
    js = "\n".join(comp.js)
    return f"""<!doctype html>
<html lang="en" data-resolution="landscape">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width={W}, height={H}" />
<title>{esc(module['title'])}</title>
<script src="{GSAP_CDN}"></script>
<style>{css}</style>
</head>
<body>
<div id="root" data-composition-id="main" data-start="0" data-duration="{timing.total}" data-width="{W}" data-height="{H}">
<div id="bgpaper"></div><div id="bgvoid"></div>
<div id="bgw"><div id="bgcam">{shards}</div></div>
<div id="vig"></div>
{mark}
{sections}
</div>
<script>
const tl = gsap.timeline({{ paused: true }});
{js}
window.__timelines = window.__timelines || {{}};
window.__timelines["main"] = tl;
</script>
</body>
</html>
"""


# ---------------------------------------------------------------- checks
def check(module, timing, cues, max_chars, quiz):
    """Everything a reviewer would otherwise find by watching. Returns a list of errors."""
    errs = []
    for k in range(1, len(timing.starts)):                     # no voice over voice
        prev_end = timing.starts[k - 1] + float(timing.words[k - 1]["dur"])
        if timing.starts[k] < prev_end - 1e-6:
            errs.append(f"line {k + 1} starts {timing.starts[k]}s, before line {k} ends ({r2(prev_end)}s)")
    if timing.starts[-1] + float(timing.words[-1]["dur"]) > timing.body_end:
        errs.append("last line runs into the end frame")
    words = lambda s: [norm(w) for w in s.split() if norm(w)]  # noqa: E731
    if words(" ".join(c["text"] for c in cues)) != words(" ".join(module["lines"])):
        errs.append("caption words are not the script words")
    for c in cues:
        if len(c["text"]) > max_chars or "\n" in c["text"]:
            errs.append(f"caption over {max_chars} chars or wrapped: {c['text']!r}")
    for a, b in zip(cues, cues[1:]):
        if b["start"] < a["end"] - 1e-6:
            errs.append(f"captions overlap at {b['start']}s")
    for i, (text, w) in enumerate(zip(module["lines"], timing.words), 1):
        if words(text) != words(w.get("text", text)):
            errs.append(f"line {i}: words.json text differs from the script")
    for q in (quiz or {}).get("questions", []):                # every answer taught in the module
        t = q.get("taught_in")
        if not t:
            errs.append(f"quiz: '{q['q']}' has no taught_in")
            continue
        heard = " ".join(norm(x["w"]) for x in timing.words[int(t["line"]) - 1]["words"])
        if " ".join(norm(x) for x in t["words"].split()) not in heard:
            errs.append(f"quiz: '{t['words']}' is not heard in line {t['line']}")
    return errs


# ---------------------------------------------------------------- main
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("module")
    ap.add_argument("--brand", required=True)
    ap.add_argument("--words", help="words.json from vo_words.py")
    ap.add_argument("--synthetic", action="store_true", help="no voice yet: evenly spaced words")
    ap.add_argument("--wps", type=float, default=2.7, help="words per second for --synthetic")
    ap.add_argument("--write-words", help="with --synthetic: save the synthetic words.json here")
    ap.add_argument("--out", help="output folder for the HyperFrames project, e.g. build/acme_m1")
    ap.add_argument("--check", action="store_true", help="validate only; write nothing")
    a = ap.parse_args(argv)

    mpath = pathlib.Path(a.module)
    module, brand = load_json(mpath), load_json(a.brand)
    if a.words:
        words = load_json(a.words)
        if any(w.get("synthetic") for w in words):
            print("!! these words are SYNTHETIC: for layout only, never for a final render")
    elif a.synthetic:
        words = synthetic_words(module, a.wps)
        print(f"!! SYNTHETIC timing at {a.wps} words/s: for layout only, never for a final render")
        if a.write_words:
            pathlib.Path(a.write_words).write_text(json.dumps(words, indent=1) + "\n", encoding="utf-8")
    else:
        raise SystemExit("give --words words.json (from vo_words.py) or --synthetic")
    quiz = load_json(mpath.parent / module["quiz"]) if module.get("quiz") else None
    max_chars = int(brand.get("captions", {}).get("max_chars", 46))

    timing = Timing(module, words)
    try:
        html_page = page(module, brand, timing)
    except KeyError as e:
        raise SystemExit(f"CUE ERROR: {e.args[0]}")
    cues = caption_cues(timing, max_chars)
    errs = check(module, timing, cues, max_chars, quiz)

    print(f"{module['id']}: total {timing.total}s  ({len(module['lines'])} lines, "
          f"{len(module['scenes'])} scenes, {len(cues)} captions, starts {'from plan' if timing.from_plan else 'computed'})")
    for sid, (s, d) in timing.scenes.items():
        print(f"  {sid:12s} {s:7.2f} +{d:.2f}")
    for w in timing.warnings:
        print("  ~", w)
    for e in errs:
        print("  !!", e)
    if errs:
        raise SystemExit(1)
    if a.check or not a.out:
        print("checks: PASS" + ("" if a.check else "  (give --out to write the project)"))
        return

    out = pathlib.Path(a.out)
    (out / "assets").mkdir(parents=True, exist_ok=True)
    if brand.get("logo"):
        shutil.copy2(pathlib.Path(a.brand).parent / brand["logo"], out / "assets" / pathlib.Path(brand["logo"]).name)
    (out / "index.html").write_text(html_page, encoding="utf-8")
    (out / "hyperframes.json").write_text(json.dumps({
        "$schema": "https://hyperframes.heygen.com/schema/hyperframes.json",
        "paths": {"blocks": "compositions", "components": "compositions/components", "assets": "assets"},
    }, indent=2) + "\n", encoding="utf-8")
    hf = f"npx --yes hyperframes@{HF_VERSION}"
    (out / "package.json").write_text(json.dumps({
        "name": module["id"], "private": True, "type": "module",
        "scripts": {"dev": f"{hf} preview", "check": f"{hf} check", "lint": f"{hf} lint", "render": f"{hf} render"},
    }, indent=2) + "\n", encoding="utf-8")

    vo_files = [w["file"] for w in words]
    stem = out.parent / out.name
    timing_json = {"total": timing.total, "vo_starts": timing.starts,
                   "scenes": {k: list(v) for k, v in timing.scenes.items()},
                   "vo_files": vo_files, "from_plan": timing.from_plan}
    pathlib.Path(f"{stem}_timing.json").write_text(json.dumps(timing_json, indent=1) + "\n", encoding="utf-8")
    music = brand.get("music", {})
    plan = {
        "module": module["id"], "title": module["title"],
        "canvas": {"width": W, "height": H, "fps": FPS},
        "timing_rules_applied": {"title_s": TITLE, "default_gap_s": GAP, "tail_hold_s": TAIL,
                                 "end_frame_s": END, "holds": module.get("holds", {})},
        "vo_placement": [{"line": i, "file": f, "start": s, "dur": float(w["dur"]),
                          "end": r2(s + float(w["dur"])),
                          "gap_before": r2(s - (timing.starts[i - 2] + float(words[i - 2]["dur"]) if i > 1 else 0))}
                         for i, (f, s, w) in enumerate(zip(vo_files, timing.starts, words), 1)],
        "captions": {"count": len(cues), "max_chars": max_chars, "cues": cues},
        "music": {"file": music.get("file"), "volume": music.get("draft_volume", 0.03)},
        "ending": {"start": timing.body_end},
        "runtime": {"total_s": timing.total, "mmss": f"{int(timing.total // 60)}:{int(round(timing.total % 60)):02d}"},
        "capcut_review_draft": {"canvas": [W, H], "fps": FPS, "duration_s": timing.total},
        "synthetic_timing": any(w.get("synthetic") for w in words),
    }
    pathlib.Path(f"{stem}_edit_plan.json").write_text(json.dumps(plan, indent=1) + "\n", encoding="utf-8")
    pathlib.Path(f"{stem}.srt").write_text(srt(cues), encoding="utf-8")
    print(f"wrote {out}/index.html, {stem}_timing.json, {stem}_edit_plan.json, {stem}.srt")


if __name__ == "__main__":
    main(sys.argv[1:])
