#!/usr/bin/env python3
"""Is the call-out covering something the viewer needs to read?

The gap the 12 Aug residue study found: of 53 call-outs Saad repositioned, 42 were
already on the right element. `sa_boxcheck --verify` passes all of those, because it
only ever asks "is the box on the named element?". Twenty-seven of the moves existed
to UNCOVER something — the box's own border struck through a line of text, or the
label chip was parked on live content (a grand total, a KPI row, a value
recorded one step earlier).

Two tests, both on the frame that actually plays, both local (no vision model):

  stroke   the 4 border bands of the box. Ink there means the border is laid across
           glyphs — he fixes these with a 10-26px nudge.
  chip     the label chip's rect. Ink under it means it is sitting on content rather
           than on empty panel background.

"Ink" = pixels that differ sharply from their own local background, which is what text
and icons are on these flat dashboard screens. No OCR, no model, ~1s per call-out.

THIS IS A SCREEN, NOT A VERDICT — measured, 12 Aug. On one video it flagged 13 of the 14
call-outs Saad actually moved, without knowing his edits: every case the residue study
named by hand (grand total struck, chip on the KPI row, border through the green tick).
On another the same thresholds flagged 43 of 76, and looking at the twelve worst, only
about four were real — these dashboards put dense text within a few px of every button,
so the band catches content the border never touches. Always composite and LOOK before
changing anything. Auto-nudging on this score would have damaged a good build.

    sa_occlude.py "…/T01_PACED_LAYERS/_layers.json"
    sa_occlude.py "…/_layers.json" --json out.json --top 20

Reads only. Never touches a draft.
"""
import json
import pathlib
import subprocess
import sys
import tempfile

try:
    import numpy as np
    from PIL import Image
except ImportError:
    sys.exit("needs pillow + numpy (Tools/venv/bin/python3)")

STROKE = 6          # the build's border weight
BAND = STROKE + 6   # how far either side of the border a glyph still reads as struck


def frame_at(video, t, out):
    subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", str(video),
                    "-frames:v", "1", "-y", str(out)], check=True)
    return np.asarray(Image.open(out).convert("L"), dtype=np.int16)


def ink(gray, rect):
    """Fraction of pixels in rect that are strong local departures from background.

    Dashboard screens are flat colour, so a pixel far from its row's median is a
    glyph, an icon edge or a control border — i.e. something a viewer is reading.
    """
    x, y, w, h = (int(v) for v in rect)
    x, y = max(x, 0), max(y, 0)
    patch = gray[y:y + h, x:x + w]
    if patch.size < 40:
        return 0.0
    bg = np.median(patch)
    return float((np.abs(patch - bg) > 40).mean())


def stroke_bands(box):
    x, y, w, h = (int(v) for v in box)
    return {
        "top": (x, y - BAND // 2, w, BAND),
        "bottom": (x, y + h - BAND // 2, w, BAND),
        "left": (x - BAND // 2, y, BAND, h),
        "right": (x + w - BAND // 2, y, BAND, h),
    }


def check(layers_path, top=None):
    layers_path = pathlib.Path(layers_path)
    plan = json.loads(layers_path.read_text())
    video = pathlib.Path(plan["video"])
    if not video.exists():
        sys.exit(f"missing paced video: {video}")
    rows = []
    with tempfile.TemporaryDirectory() as tmp:
        shot = pathlib.Path(tmp) / "f.png"
        for layer in plan["layers"]:
            # Sample where the box is settled, not on its first frame.
            t = layer["start"] + min(0.4, layer.get("duration", 1) / 3)
            gray = frame_at(video, t, shot)
            bands = {k: ink(gray, r) for k, r in stroke_bands(layer["box"]).items()}
            worst_band = max(bands, key=bands.get)
            rows.append({
                "png": pathlib.Path(layer["file"]).name,
                "at": round(t, 2),
                "chip_ink": round(ink(gray, layer["chip"]), 4) if layer.get("chip") else None,
                "stroke_ink": round(bands[worst_band], 4),
                "stroke_edge": worst_band,
            })
    rows.sort(key=lambda r: -(max(r["chip_ink"] or 0, r["stroke_ink"])))
    return rows[:top] if top else rows


def report(rows):
    # Calibrated against the moves he actually made: a clean chip on empty panel
    # background sits near 0.00; the ones he rescued were an order of magnitude up.
    chip_bad = [r for r in rows if (r["chip_ink"] or 0) > 0.06]
    stroke_bad = [r for r in rows if r["stroke_ink"] > 0.10]
    print(f"{len(rows)} call-outs checked\n")
    print(f"  CHIP on content   {len(chip_bad):>3}   label parked over text/numbers")
    print(f"  BORDER on glyphs  {len(stroke_bad):>3}   box edge struck through a line\n")
    flagged = {r["png"]: r for r in chip_bad + stroke_bad}
    for r in sorted(flagged.values(), key=lambda r: -(max(r["chip_ink"] or 0, r["stroke_ink"]))):
        bits = []
        if (r["chip_ink"] or 0) > 0.06:
            bits.append(f"chip {r['chip_ink']:.2f}")
        if r["stroke_ink"] > 0.10:
            bits.append(f"{r['stroke_edge']} border {r['stroke_ink']:.2f}")
        print(f"    {r['at']:7.2f}s  {r['png'][:46]:<46} {' · '.join(bits)}")
    if not flagged:
        print("    nothing over threshold — no call-out is covering content")
    return flagged


def demo():
    """Self-check: ink() fires on text-like contrast, not on flat panel background."""
    flat = np.full((60, 200), 240, dtype=np.int16)
    assert ink(flat, (0, 0, 200, 60)) == 0.0, "flat background must read as clean"
    texty = flat.copy()
    texty[20:40, 10:150] = 30           # a dark line of glyphs
    assert ink(texty, (0, 0, 200, 60)) > 0.15, "a line of text must read as ink"
    b = stroke_bands((100, 100, 50, 40))
    assert b["bottom"][1] == 134 and b["left"][2] == BAND
    print("demo ok")


def main():
    argv = sys.argv[1:]
    out_path = None
    if "--json" in argv:
        i = argv.index("--json")
        out_path = pathlib.Path(argv[i + 1])
        argv = argv[:i] + argv[i + 2:]
    top = None
    if "--top" in argv:
        i = argv.index("--top")
        top = int(argv[i + 1])
        argv = argv[:i] + argv[i + 2:]
    args = [a for a in argv if not a.startswith("--")]
    if not args:
        sys.exit(__doc__)
    rows = check(args[0], top)
    if out_path:
        out_path.write_text(json.dumps(rows, indent=1))
        print(f"wrote {out_path}\n")
    report(rows)
    return 0


if __name__ == "__main__":
    sys.exit(demo() if "--demo" in sys.argv else main())
