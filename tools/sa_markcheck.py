#!/usr/bin/env python3
"""sa_markcheck — deterministic, zero-token pre-flight on a training module's markings.

NOT a replacement for sa_boxcheck.py, which is the VISION check (qwen3-vl via Ollama:
"is this box on the element its label names?"). This one never looks at a picture — it
checks what arithmetic and OCR alone can prove, and prints a shortlist of the beats that
still need eyes. Run this first, then sa_boxcheck on what it flags.

Question (11 Sep): would a small local model (qwen) for background jobs use fewer tokens
and give better results? The honest answer is that the cheapest model is no model.
Roughly three quarters of what the box-authoring subagents did on 10/11 Sep was
mechanical and deterministic — this does that part locally, and prints a SHORTLIST
of the beats that genuinely need a model's judgement.

What it checks (all local, all deterministic):

  coverage    how many narration lines carry a marking, vs the approved reference
              (the approved reference module = 57 boxes for 57 lines = 100%)
  needle      every `find` string is actually present in that beat's frame OCR, using
              the same exact -> squashed -> fuzzy ladder the module builder's locate() uses
  geometry    no box off-canvas, degenerate, absurdly tall, or crossing the sidebar
              guard at x=248 (Saad's rule, measured 9 Sep)
  house style is there a `label`, a `cue`, and `pad` — the three things every entry in
              the approved reference file has and two later modules' files did not
  cue        every `cue` is a verbatim substring of a real caption chunk for its line

What it CANNOT check, and why a model is still needed for the shortlist:
  whether the frame is the RIGHT SCREEN for the narration (pre-action vs post-action),
  and whether the box landed on the intended element rather than another instance of
  the same words. Both bugs shipped on 10 Sep reporting `ok`:
    module A, approve beat  "Approve" matched the page subtitle, not the button
    module B, approve beat  "Approve" matched the sidebar "My Approvals", box at x=-10

    sa_markcheck.py "<module folder>"           # report
    sa_markcheck.py "<module folder>" --shortlist   # only the beats needing a human/model
"""
import difflib
import json
import pathlib
import re
import subprocess
import sys

REFERENCE_COVERAGE = 1.00      # the approved reference: 57 boxes / 57 lines
# The sidebar border. 248 is right for the full-scale renders, but one
# module was recorded at a smaller browser scale and its content starts at x~206.
# Page headings also start near x=161 in another, so a blanket guard cries wolf on every
# h1. Default is OFF; pass --guard=N per module only when you have measured it.
LEFT_GUARD = 0    # OFF by default: see note above — pass --guard=N deliberately
MAX_BOX_H = 700                # taller than this is almost always a container blow-out


def squash(t):
    return re.sub(r"[^a-z0-9]", "", t.lower())


def ocr(binary, png):
    out = subprocess.run([str(binary), str(png)], capture_output=True, text=True)
    if out.returncode != 0 or not out.stdout.strip():
        return None
    return [r for r in json.loads(out.stdout)["rows"] if r["confidence"] > 0.3]


def find_needle(rows, needle):
    """Mirrors the module builder's locate(): exact, then squashed, then fuzzy >= 0.82."""
    n = needle.lower()
    for r in rows:
        if n in r["text"].lower():
            return "exact", r
    sn = squash(needle)
    for r in rows:
        if sn and sn in squash(r["text"]):
            return "squashed", r
    best, score = None, 0.0
    for r in rows:
        s = difflib.SequenceMatcher(None, sn, squash(r["text"])).ratio()
        if s > score:
            best, score = r, s
    if best and score >= 0.82:
        return f"fuzzy {score:.2f}", best
    return None, None


def check(root, guard=LEFT_GUARD):
    root = pathlib.Path(root)
    boxes = json.loads((root / "boxes.json").read_text())
    lines = [l.strip() for l in (root / "lines.txt").read_text().splitlines() if l.strip()]
    binary = root / "ocr_bounds_local"
    caps = json.loads((root / "captions.json").read_text()) if (root / "captions.json").exists() else []
    timing = {}
    if (root / "callout_timing.json").exists():
        timing = json.loads((root / "callout_timing.json").read_text())

    problems, shortlist = [], []

    cov = len(boxes) / len(lines)
    if cov < 0.80:
        problems.append(f"COVERAGE {len(boxes)}/{len(lines)} = {cov:.0%} — reference is {REFERENCE_COVERAGE:.0%}")

    for name, sp in sorted(boxes.items()):
        # --- house style -------------------------------------------------------
        for key in ("label", "cue"):
            if not sp.get(key):
                problems.append(f"{name}: no {key}")
        if "pad" not in sp and not sp.get("manual") and sp.get("mode") != "manual":
            # NOTE, not a problem. 11 Sep: adding pad:12 to one dropdown beat widened the box
            # and pushed its chip onto the modal's Brand dropdown — the very control the
            # narration points at. Unions often sit on the default pad deliberately.
            shortlist.append(f"{name}: no pad — check the chip still clears the content before adding one")

        # --- cue must exist in a real caption chunk ----------------------------
        if caps and sp.get("cue"):
            hit = any(c["line"] == sp["line"] and sp["cue"].lower() in c["text"].lower() for c in caps)
            if not hit:
                problems.append(f"{name}: cue {sp['cue']!r} is not in any caption chunk for line {sp['line']}")

        # --- geometry from the last build -------------------------------------
        t = timing.get(name)
        if t:
            x, y, w, h = t["box"]
            if x < 0 or y < 0:
                problems.append(f"{name}: box off-canvas at ({x},{y})")
            elif guard and x < guard < x + w:
                # Saad's rule is that nothing may CROSS the sidebar border. A box wholly
                # inside the sidebar is correct and required — it marks the nav item being
                # selected. Only a box straddling the border is wrong.
                problems.append(f"{name}: box x={x}..{x+w} CROSSES the sidebar guard at {guard}")
            if w < 20 or h < 10:
                problems.append(f"{name}: box degenerate {w}x{h}")
            if h > MAX_BOX_H:
                problems.append(f"{name}: box {h}px tall — container blow-out?")
            cx, cy, cw, ch = t["chip"]
            if cx < 0 or cy < 0:
                problems.append(f"{name}: chip off-canvas at ({cx},{cy})")

        # --- needle actually on the frame -------------------------------------
        png = root / "frames" / f"{name}.png"
        needle = sp.get("find")
        if needle == "__manual__" or sp.get("mode") == "manual":
            continue
        if not png.exists() or not binary.exists():
            continue
        rows = ocr(binary, png)
        if rows is None:
            problems.append(f"{name}: OCR failed on its frame")
            continue
        nds = needle if isinstance(needle, list) else [needle]
        missing = []
        for nd in nds:
            how, hit = find_needle(rows, nd)
            if how is None:
                missing.append(nd)
            elif how.startswith("fuzzy"):
                shortlist.append(f"{name}: {nd!r} only matched {how} -> {hit['text'][:40]!r}")
        # the module builder's union mode needs only SOME members present, so a partial miss is a
        # note, not a failure. A single-needle miss is fatal.
        if missing and len(missing) == len(nds):
            problems.append(f"{name}: needle(s) {missing!r} NOT on its frame")
        elif missing:
            shortlist.append(f"{name}: union missing {missing!r} — box is built from the rest")

        # --- the class of bug a needle check cannot catch ----------------------
        # If the same needle appears more than once on the frame, which instance the
        # builder picked is a judgement call. This is exactly how both Approve bugs
        # shipped while reporting ok.
        for nd in (needle if isinstance(needle, list) else [needle]):
            n = nd.lower()
            hits = [r for r in rows if n in r["text"].lower()]
            if len(hits) > 1 and not sp.get("pick") and not sp.get("word"):
                where = ", ".join(f"({r['box'][0]},{r['box'][1]})" for r in hits[:4])
                shortlist.append(f"{name}: {nd!r} appears {len(hits)}x on the frame [{where}] "
                                 f"and no pick/word set — which one did it take?")

    return problems, shortlist, cov, len(boxes), len(lines)


def main():
    argv = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not argv:
        sys.exit(__doc__)
    root = pathlib.Path(argv[0])
    only_short = "--shortlist" in sys.argv
    guard = LEFT_GUARD
    for a in sys.argv:
        if a.startswith("--guard="):
            guard = int(a.split("=", 1)[1])
    problems, shortlist, cov, nb, nl = check(root, guard)

    print(f"\n  {root.name}")
    print(f"  coverage {nb}/{nl} = {cov:.0%}")
    if not only_short:
        print(f"\n  HARD PROBLEMS ({len(problems)}) — fix these, no model needed:")
        for p in problems:
            print(f"    {p}")
        if not problems:
            print("    none")
    print(f"\n  NEEDS JUDGEMENT ({len(shortlist)}) — send only these to a model:")
    for s in shortlist:
        print(f"    {s}")
    if not shortlist:
        print("    none")
    print(f"\n  A model still has to confirm the SCREEN is right for the narration —")
    print(f"  that is the one thing this cannot see.\n")
    return 1 if problems else 0


def demo():
    """Self-check: the needle ladder behaves the way the module builder's locate() does."""
    rows = [{"text": "Exchange Rate *", "confidence": 1, "box": [0, 0, 10, 10]},
            {"text": "© Approvi", "confidence": 1, "box": [1758, 39, 59, 14]}]
    assert find_needle(rows, "Exchange Rate")[0] == "exact"
    assert find_needle(rows, "ExchangeRate")[0] == "squashed"
    assert find_needle(rows, "Approve")[0].startswith("fuzzy"), "the © Approvi case must fuzzy-match"
    assert find_needle(rows, "Nonexistent Panel")[0] is None
    print("demo ok")


if __name__ == "__main__":
    if "--demo" in sys.argv:
        demo()
    else:
        sys.exit(main())
