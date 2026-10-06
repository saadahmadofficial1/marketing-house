#!/usr/bin/env python3
"""Locate where each panel/control appears in a screen recording, by OCR, so a
re-sequenced script can still point every beat at the frame that actually shows it.

Some tour scripts (a dashboard tour) name the panels in a tidy reading order that
does NOT match the order they were scrolled/clicked on screen. A straight timeline
align then puts the wrong panel under each line. This builds an OCR INDEX of the
recording once (cached), then for a needle returns the timestamp where that needle is
most prominent — near the top of the content area, largest, highest confidence — i.e.
the moment the user brought that panel into view.

    sa_panel_locate.py "<build folder>" --index         # build/refresh the cache
    sa_panel_locate.py "<build folder>" --find "Panel Alpha"
    sa_panel_locate.py --test

The per-row render in build.py is independent per row, so rows need NOT be monotonic in
recording time — a beat may point anywhere. That is what makes the non-linear assembly
safe: voice + captions play in script order, each beat's footage jumps to its panel.

Local only, zero model tokens. The scan is the slow part; run it in the background.
"""
import json
import pathlib
import subprocess
import sys

# Vision OCR helper binary (not included): prints {"rows": [{"text", "box", "confidence"}]}
OCR = pathlib.Path(__file__).with_name("ocr_bounds")
CONTENT_X = 248
STEP = 2.0          # seconds between sampled frames


def _squash(t):
    import re
    return re.sub(r"[^a-z0-9]", "", t.lower())


def build_index(folder, src="SRC30.mp4", step=STEP):
    folder = pathlib.Path(folder)
    video = folder / src
    dur = float(subprocess.run(["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                                "-of", "csv=p=0", str(video)], capture_output=True, text=True).stdout)
    tmp = folder / "_scan.png"
    index = []
    t = 0.0
    while t < dur:
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.2f}", "-i", str(video),
                        "-frames:v", "1", str(tmp)], check=True)
        j = json.loads(subprocess.run([str(OCR), str(tmp)], capture_output=True, text=True).stdout)
        rows = [{"t": r["text"], "b": [round(x) for x in r["box"]], "c": round(r["confidence"], 2)}
                for r in j["rows"] if r["confidence"] > 0.4 and r["box"][0] > CONTENT_X]
        index.append({"t": round(t, 2), "rows": rows})
        t += step
    tmp.unlink(missing_ok=True)
    (folder / "panel_index.json").write_text(json.dumps(index))
    return index


def load_index(folder):
    return json.loads((pathlib.Path(folder) / "panel_index.json").read_text())


def find(index, needle, ytop=520):
    """Best timestamp for a needle. Score rewards a match whose box sits high in the
    content (a heading the user scrolled to the top), is tall (a real heading, not a
    footnote) and confident. Returns (t, box, score) or None."""
    n = _squash(needle)
    best = None
    for fr in index:
        for r in fr["rows"]:
            if n in _squash(r["t"]):
                x, y, w, h = r["b"]
                # high on screen = better (y small); taller text = better; confident = better
                score = r["c"] * 2 + max(0, (ytop - y)) / 200 + h / 40
                if best is None or score > best[2]:
                    best = (fr["t"], r["b"], round(score, 2))
    return best


def _test():
    idx = [
        {"t": 0.0, "rows": [{"t": "Panel Alpha", "b": [300, 600, 200, 30], "c": 0.9}]},
        {"t": 2.0, "rows": [{"t": "Panel Alpha", "b": [300, 120, 240, 40], "c": 0.9},
                             {"t": "Panel Beta", "b": [300, 700, 200, 28], "c": 0.8}]},
    ]
    # "Panel Alpha" should pick t=2.0 (heading scrolled to the top, y=120 beats y=600)
    hit = find(idx, "Panel Alpha")
    assert hit[0] == 2.0, hit
    # squashed/fuzzy: OCR noise "Panelbeta" still matches "Panel Beta"
    idx2 = [{"t": 5.0, "rows": [{"t": "Panelbeta", "b": [300, 200, 210, 30], "c": 0.85}]}]
    assert find(idx2, "Panel Beta")[0] == 5.0
    # a needle nobody shows -> None
    assert find(idx, "Missing Panel") is None
    print("sa_panel_locate self-check: ok (top-of-content wins, squash match, miss=None)")


if __name__ == "__main__":
    if "--test" in sys.argv:
        _test(); sys.exit()
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    folder = args[0]
    if "--index" in sys.argv:
        idx = build_index(folder)
        print(f"indexed {len(idx)} frames -> {folder}/panel_index.json")
    elif "--find" in sys.argv:
        idx = load_index(folder)
        hit = find(idx, args[1])
        print(hit if hit else f"not found: {args[1]!r}")
