#!/usr/bin/env python3
"""cull_driver: runs tools/sa_cull.py on a chosen list of photos (used by photo_cull).

Runs inside the Python named by STUDIO_CULL_PYTHON (one with OpenCV, numpy and Pillow;
tested on Python 3.9), because the studio server's own Python has none of those. Keep
this file Python 3.9-compatible.

Input (JSON on stdin): {"cull": "<path to sa_cull.py>", "files": [...],
                        "out": "<new, empty folder>", "name": "<folder name>"}
Output: progress lines "PROGRESS i n" on stderr, one JSON summary line on stdout.

Reads the photos only. Writes only into "out", and only new files (mode 'x').
"""
import importlib.util
import json
import os
import sys

sys.dont_write_bytecode = True

KEEP = ("file", "sharp", "lum", "clip_hi", "clip_lo", "dt", "iso", "f", "exp", "focal")


def main():
    job = json.load(sys.stdin)
    spec = importlib.util.spec_from_file_location("sa_cull", job["cull"])
    cull = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cull)

    out, name, files = job["out"], job["name"], job["files"]
    if not os.path.isdir(out) or os.listdir(out):
        raise SystemExit("output folder must exist and be empty: %s" % out)

    frames, unreadable = [], []
    for i, path in enumerate(files, 1):
        s = cull.score(path)
        if s is None:
            unreadable.append(os.path.basename(path))
        else:
            s["file"] = os.path.basename(path)
            s["path"] = path
            s.update(cull.exif(path))
            frames.append(s)
        print("PROGRESS %d %d" % (i, len(files)), file=sys.stderr, flush=True)

    groups = cull.group(frames)
    picks = [cull.pick(g) for g in groups]
    record = {
        "folder": os.path.dirname(files[0]) if files else "",
        "unit": name, "frames": len(frames), "groups": len(groups),
        "picks": [{k: f.get(k) for k in KEEP} for f in picks],
        "all": [{k: f.get(k) for k in ("file", "sharp", "lum", "clip_hi", "clip_lo", "dt")}
                for f in frames],
        "unreadable": unreadable,
    }
    written = []
    report = os.path.join(out, "cull_%s.json" % name)
    with open(report, "x") as fh:
        json.dump(record, fh, indent=1, default=str)
    written.append(report)
    picks_txt = os.path.join(out, "picks_%s.txt" % name)
    with open(picks_txt, "x") as fh:
        fh.write("\n".join(f["path"] for f in picks) + "\n")
    written.append(picks_txt)
    if picks:
        sheet = os.path.join(out, "sheet_%s.jpg" % name)
        cull.contact(picks, sheet)
        if os.path.exists(sheet):
            written.append(sheet)

    print(json.dumps({"frames": len(frames), "groups": len(groups), "unreadable": unreadable,
                      "picks": record["picks"], "written": written}, default=str))


if __name__ == "__main__":
    main()
