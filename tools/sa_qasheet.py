#!/usr/bin/env python3
"""One composited still per call-out — the frame that plays, with the box drawn on it.

Every placement check that has ever caught a real defect came from LOOKING at the
frame (the nearest click is not the narrated action; the box was right but
covering something). This makes that cheap and repeatable instead of
hand-rolled each time.

    sa_qasheet.py "…/module_stepmarks.json" -o /tmp/module_qa
    sa_qasheet.py "…/_layers.json"       -o /tmp/module_qa --context

Accepts either manifest shape:
    stepmarks  {"video":…, "marks"|list of {t, dur, box, label, file}}
    layers     {"video":…, "layers": [{start, duration, box, chip, label, file}]}

Writes NN_<label>.jpg plus index.json. `--context` keeps the full frame (needed to
judge whether a chip is covering something); the default crops around the box with
padding so the target is legible.

The stills are made locally with ffmpeg and Pillow. If a hosted agent then reviews them,
they are processed on its provider’s servers, so use that route only for footage cleared
for it.
"""
import json
import pathlib
import subprocess
import sys

try:
    from PIL import Image, ImageDraw
except ImportError:
    sys.exit("needs pillow (pip install pillow)")

PAD = 300


def load(manifest):
    data = json.loads(pathlib.Path(manifest).read_text())
    video = pathlib.Path(data["video"])
    if "layers" in data:
        items = [{"t": l["start"], "dur": l.get("duration", 2.0), "box": l["box"],
                  "chip": l.get("chip"), "label": l.get("label", ""),
                  "file": l.get("file", "")} for l in data["layers"]]
    else:
        raw = data if isinstance(data, list) else data.get("marks", data.get("steps", []))
        items = [{"t": m["t"], "dur": m.get("dur", 2.0), "box": m["box"],
                  "chip": m.get("chip"), "label": m.get("label", ""),
                  "file": m.get("file", "")} for m in raw]
    return video, items


def render(video, item, out, context):
    # Sample once the box has settled, never its first frame (a box fades in).
    t = item["t"] + min(0.4, item["dur"] / 3)
    tmp = out.with_suffix(".src.png")
    subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", str(video),
                    "-frames:v", "1", "-y", str(tmp)], check=True)
    im = Image.open(tmp).convert("RGB")
    d = ImageDraw.Draw(im)
    x, y, w, h = (int(v) for v in item["box"])
    d.rectangle([x, y, x + w, y + h], outline=(255, 40, 40), width=5)
    if item.get("chip"):
        cx, cy, cw, ch = (int(v) for v in item["chip"])
        d.rectangle([cx, cy, cx + cw, cy + ch], outline=(255, 170, 0), width=4)
    if not context:
        im = im.crop((max(0, x - PAD), max(0, y - PAD),
                      min(im.width, x + w + PAD), min(im.height, y + h + PAD)))
    im.thumbnail((1100, 1100))
    im.save(out, quality=82)
    tmp.unlink(missing_ok=True)
    return round(t, 2)


def main():
    argv = sys.argv[1:]
    if "-o" not in argv:
        sys.exit(__doc__)
    i = argv.index("-o")
    out_dir = pathlib.Path(argv[i + 1])
    context = "--context" in argv
    args = [a for a in argv[:i] + argv[i + 2:] if not a.startswith("-")]
    if not args:
        sys.exit(__doc__)

    video, items = load(args[0])
    if not video.exists():
        sys.exit(f"missing video: {video}")
    out_dir.mkdir(parents=True, exist_ok=True)
    index = []
    for n, item in enumerate(items, 1):
        safe = "".join(c if c.isalnum() else "_" for c in item["label"])[:46] or "mark"
        out = out_dir / f"{n:02d}_{safe}.jpg"
        shot_t = render(video, item, out, context)
        index.append({"n": n, "at": shot_t, "label": item["label"],
                      "box": item["box"], "png": pathlib.Path(item["file"]).name,
                      "image": str(out)})
        print(f"  {n:>3} {shot_t:8.2f}s  {item['label'][:56]}")
    (out_dir / "index.json").write_text(json.dumps(index, indent=1))
    print(f"\n{len(index)} stills -> {out_dir}")
    return 0


def demo():
    """Self-check: both manifest shapes normalise to the same item fields."""
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        d = pathlib.Path(d)
        a = d / "s.json"
        a.write_text(json.dumps({"video": "/v.mp4", "marks": [
            {"t": 1.0, "dur": 2.0, "box": [1, 2, 3, 4], "label": "Click Save"}]}))
        b = d / "_layers.json"
        b.write_text(json.dumps({"video": "/v.mp4", "layers": [
            {"start": 1.0, "duration": 2.0, "box": [1, 2, 3, 4], "chip": [0, 0, 1, 1],
             "label": "Click Save", "file": "/x/01_Click_Save.png"}]}))
        for m in (a, b):
            video, items = load(m)
            assert str(video) == "/v.mp4" and len(items) == 1
            assert items[0]["t"] == 1.0 and items[0]["box"] == [1, 2, 3, 4]
            assert items[0]["label"] == "Click Save"
    print("demo ok")


if __name__ == "__main__":
    sys.exit(demo() if "--demo" in sys.argv else main())
