#!/usr/bin/env python3
"""sa_applyboxes — take measured-and-verified call-out boxes and put them everywhere they live.

Input: the verified results of the measuring fleet (box, time, label per gap). For each one:

  1. Find the stable window around the measured frame — the box must never sit over footage
     that scrolls underneath it. That was Saad's very first correction on this series
     (a highlight bar that moved with the page). The call-out is trimmed to the span where the
     pixels inside the box actually hold still, capped at his observed on-screen time (~2s).
  2. Render the full-canvas transparent PNG with sa_stepmark.render_step — same box style,
     same chip, same font as the existing call-outs.
  3. Register it in the build folder: the PNG in *_PACED_LAYERS/, an entry in _layers.json
     and in *_stepmarks.json, so every later tool sees one truth.
  4. Add it to the CapCut project on ONE track named "New call-outs" — he consolidated my
     one-track-per-call-out layout, so we do not repeat that. The donor material shape is
     cloned from an existing call-out PNG in the same project.

    Tools/venv/bin/python3 Tools/sa_applyboxes.py results.json --check
    Tools/venv/bin/python3 Tools/sa_applyboxes.py results.json --fix
    Tools/venv/bin/python3 Tools/sa_applyboxes.py --test

Idempotent: re-running replaces the "New call-outs" track and re-renders the PNGs in place.
Backups (.pre_newboxes) on first touch. Refuses while CapCut is open.
"""
import argparse
import copy
import glob
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import uuid

US = 1_000_000
BUILD = pathlib.Path("~/Downloads/training-series/2 BUILD").expanduser()
CAPCUT = pathlib.Path("~/Movies/CapCut/User Data/Projects/com.lveditor.draft").expanduser()
TRACK = "New call-outs"
# build tag -> CapCut project name (example entries; one per video in the series)
PROJECT_OF = {"T01": "Training 01 Sign In and Navigation",
              "T02": "Training 02 Create a Record"}
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from sa_stepmark import HOLD as MAX_DUR      # 2.1s — his measured median, one source
MIN_DUR = 1.2


def frame_crop(video, t, box, out):
    x, y, w, h = (int(v) for v in box)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{max(t, 0):.3f}",
                    "-i", str(video), "-frames:v", "1",
                    "-vf", f"crop={w}:{h}:{x}:{y},scale=160:-2", str(out)],
                   capture_output=True)
    return os.path.exists(out)


def region_diff(a, b):
    """Mean absolute pixel difference between two crops. 0 = identical."""
    from PIL import Image
    ia = Image.open(a).convert("L").resize((80, 40))
    ib = Image.open(b).convert("L").resize((80, 40))
    da, db = list(ia.getdata()), list(ib.getdata())
    return sum(abs(p - q) for p, q in zip(da, db)) / len(da)


def stable_window(video, t, box, work, thresh=6.0):
    """-> (start, dur): the span around t where the box region holds still.

    Probes ±1.5s in 0.5s steps and keeps extending while the region matches the frame at t.
    The whole point of the series' freeze technique is that a box must not ride on a
    scrolling UI; when the surroundings move, the call-out simply gets shorter.
    """
    os.makedirs(work, exist_ok=True)
    ref = os.path.join(work, "ref.png")
    if not frame_crop(video, t, box, ref):
        return max(0.0, t - MIN_DUR / 2), MIN_DUR
    lo = hi = t
    for step in (0.5, 1.0, 1.5):
        p = os.path.join(work, f"m{step}.png")
        if frame_crop(video, t - step, box, p) and region_diff(ref, p) < thresh:
            lo = t - step
        else:
            break
    for step in (0.5, 1.0, 1.5):
        p = os.path.join(work, f"p{step}.png")
        if frame_crop(video, t + step, box, p) and region_diff(ref, p) < thresh:
            hi = t + step
        else:
            break
    start, end = clamp_window(t, lo, hi)
    return start, end - start


def clamp_window(t, lo, hi):
    """Pure: centre the call-out on t inside [lo, hi], within MIN/MAX duration."""
    lo, hi = min(lo, t), max(hi, t)
    if hi - lo < MIN_DUR:
        half = MIN_DUR / 2
        return max(0.0, t - half), max(0.0, t - half) + MIN_DUR
    start = max(lo, min(t - MAX_DUR / 2, hi - MAX_DUR))
    end = min(hi, start + MAX_DUR)
    return start, end


def next_index(manifest):
    ns = [int(os.path.basename(L["file"]).split("_")[0])
          for L in manifest.get("layers", []) if
          os.path.basename(L.get("file", "")).split("_")[0].isdigit()]
    return (max(ns) + 1) if ns else 1


def _local_donor(draft):
    vids = {m["id"]: m for m in draft["materials"].get("videos", [])
            if (m.get("path") or "").lower().endswith(".png")
            and "sdr709" not in os.path.basename(m.get("path") or "")}
    for t in draft.get("tracks", []):
        for s in t.get("segments", []):
            if s.get("material_id") in vids:
                return copy.deepcopy(vids[s["material_id"]]), copy.deepcopy(s)
    return None, None


def photo_donor(draft):
    """An existing call-out PNG material + segment in this project, deep-copied.
    A fresh project (built with zero layers) has none — fall back to
    a donor from any sibling project in the series so first boxes can land."""
    dm, ds = _local_donor(draft)
    if dm is not None:
        return dm, ds
    for sib in sorted(CAPCUT.glob("Training */Timelines/*/draft_info.json")):
        try:
            dm, ds = _local_donor(json.loads(sib.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
        if dm is not None:
            return dm, ds
    return None, None


def add_track(draft, dm, ds, layers):
    """Pure: draft + [(png_path, start, dur, label)] -> draft with one replaced track."""
    out = copy.deepcopy(draft)
    gone = {s.get("material_id")
            for t in out.get("tracks", []) if t.get("name") == TRACK
            for s in t.get("segments", [])}
    out["tracks"] = [t for t in out.get("tracks", []) if t.get("name") != TRACK]
    out["materials"]["videos"] = [m for m in out["materials"].get("videos", [])
                                  if m["id"] not in gone]
    segs = []
    for i, (png, start, dur, label) in enumerate(sorted(layers, key=lambda x: x[1])):
        m = copy.deepcopy(dm)
        m.update({"id": str(uuid.uuid4()).upper(), "path": str(png),
                  "material_name": os.path.basename(png)})
        out["materials"]["videos"].append(m)
        s = copy.deepcopy(ds)
        s.update({"id": str(uuid.uuid4()).upper(), "material_id": m["id"],
                  "source_timerange": {"start": 0, "duration": int(dur * US)},
                  "target_timerange": {"start": int(start * US),
                                       "duration": int(dur * US)},
                  "render_index": 22000 + i, "extra_material_refs": [],
                  "group_id": "", "template_id": "", "visible": True})
        # full-canvas layer: identity placement, exactly like the existing call-outs
        if s.get("clip"):
            s["clip"]["transform"] = {"x": 0.0, "y": 0.0}
            s["clip"]["scale"] = {"x": 1.0, "y": 1.0}
        segs.append(s)
    out["tracks"].append({"id": str(uuid.uuid4()).upper(), "type": "video",
                          "attribute": 0, "flag": 0, "is_default_name": False,
                          "name": TRACK, "segments": segs})
    return out


def run(results, apply_it):
    sys.path.insert(0, str(pathlib.Path(__file__).parent))
    import sa_stepmark
    work = pathlib.Path(tempfile.gettempdir()) / "applyboxes"
    by = {}
    for r in results:
        by.setdefault(r["tag"], []).append(r)
    total = 0
    for tag, rows in sorted(by.items()):
        folder = BUILD / rows[0]["video_name"]
        man_p = folder / f"{tag}_PACED_LAYERS" / "_layers.json"
        man = json.load(open(man_p))
        video, canvas = man["video"], man.get("canvas", [1920, 1140])
        idx = next_index(man)
        planned = []
        for r in rows:
            start, dur = stable_window(video, r["t"], r["box"],
                                       work / f"{tag}_{r['seg']}")
            safe = "".join(c if c.isalnum() else "_" for c in r["label"])[:44]
            png = man_p.parent / f"{idx:02d}_{safe}.png"
            planned.append((r, png, start, dur))
            print(f"  {tag} seg {r['seg']:2d}  {start:7.2f}s +{dur:.2f}s  "
                  f"box {r['box']}  {r['label']!r}")
            idx += 1
        total += len(planned)
        if not apply_it:
            continue
        from sa_guard import preflight
        preflight("capcut_write", project=PROJECT_OF[tag])
        # 1+2: render PNGs and register in the build folder
        for r, png, start, dur in planned:
            img = sa_stepmark.render_step(tuple(canvas), tuple(int(v) for v in r["box"]),
                                           r["label"])
            img.save(png)
            man["layers"].append({"file": str(png), "start": round(start, 2),
                                  "duration": round(dur, 2), "label": r["label"],
                                  "box": [int(v) for v in r["box"]]})
        bak = str(man_p) + ".pre_newboxes"
        if not os.path.exists(bak):
            shutil.copy2(man_p, bak)
        json.dump(man, open(man_p, "w"), indent=1, ensure_ascii=False)
        sm = glob.glob(str(folder / f"{tag}_stepmarks.json"))
        if sm:
            d = json.load(open(sm[0]))
            steps = d.get("steps", d if isinstance(d, list) else [])
            for r, png, start, dur in planned:
                steps.append({"t": round(start, 2), "dur": round(dur, 2),
                              "box": [int(v) for v in r["box"]], "label": r["label"]})
            if not os.path.exists(sm[0] + ".pre_newboxes"):
                shutil.copy2(sm[0], sm[0] + ".pre_newboxes")
            json.dump(d, open(sm[0], "w"), indent=1, ensure_ascii=False)
        # 3: CapCut
        proj = CAPCUT / PROJECT_OF[tag]
        for f in [pathlib.Path(x) for x in
                  glob.glob(str(proj / "Timelines/*/draft_info.json"))] + \
                 ([proj / "draft_info.json"]
                  if (proj / "draft_info.json").exists() else []):
            d = json.loads(f.read_text(encoding="utf-8"))
            dm, ds = photo_donor(d)
            if dm is None:
                print(f"  ! {PROJECT_OF[tag]}: no PNG donor in draft — skipped")
                continue
            b = f.with_suffix(".json.pre_newboxes")
            if not b.exists():
                shutil.copy2(f, b)
            # The track is rebuilt from the FULL manifest, never from this run's new
            # boxes alone: on 10 Aug an incremental 1-box run replaced one project's track
            # and silently destroyed the other 15 layers (the assert only counted the
            # new ones). The manifest is the record; the track mirrors it entirely.
            layers = [(L["file"], L["start"], L["duration"], L.get("label", ""))
                      for L in man["layers"]]
            f.write_text(json.dumps(add_track(d, dm, ds, layers), ensure_ascii=False),
                         encoding="utf-8")
        chk = json.load(open(glob.glob(str(proj / "Timelines/*/draft_info.json"))[0]))
        got = [t for t in chk["tracks"] if t.get("name") == TRACK]
        n = len(got[0]["segments"]) if got else 0
        missing = [m["path"] for m in chk["materials"]["videos"]
                   if m.get("path") and not os.path.exists(m["path"])]
        # verify against the MANIFEST count, not this run's: counting only the new
        # boxes is exactly how that destruction passed verification
        assert len(got) == 1 and n == len(man["layers"]) and not missing, \
            f"{PROJECT_OF[tag]}: track={len(got)} segs={n} " \
            f"expected={len(man['layers'])} missing={len(missing)}"
        print(f"  -> {PROJECT_OF[tag]}: {n} layer(s) on one '{TRACK}' track "
              f"(full manifest), 0 missing media, verified")
    print(f"\n{total} call-out(s) {'applied' if apply_it else 'planned'}")
    return total


def _test():
    # window clamping: centred on t, bounded by stability and his on-screen norms
    s, e = clamp_window(10.0, 8.5, 11.5)
    assert e - s <= MAX_DUR + 1e-9 and s <= 10.0 <= e
    s, e = clamp_window(10.0, 9.9, 10.1)
    assert abs((e - s) - MIN_DUR) < 1e-9, "a jittery region still gets a visible minimum"
    s, e = clamp_window(0.3, 0.0, 3.0)
    assert s >= 0.0
    # add_track: replaces, never stacks; strips its own old materials
    dm = {"id": "P", "path": "/x/01_a.png", "type": "photo"}
    ds = {"id": "S", "material_id": "P", "clip": {"transform": {"x": 0.5, "y": 0.5},
          "scale": {"x": 2.0, "y": 2.0}},
          "target_timerange": {"start": 0, "duration": 1}}
    draft = {"materials": {"videos": [dm]}, "tracks": [
        {"type": "video", "name": "video", "segments": [
            {"id": "v", "material_id": "P",
             "target_timerange": {"start": 0, "duration": int(9 * US)}}]}]}
    out = add_track(draft, dm, ds, [("/x/07_new.png", 5.0, 2.0, "New")])
    tr = [t for t in out["tracks"] if t.get("name") == TRACK]
    assert len(tr) == 1 and len(tr[0]["segments"]) == 1
    seg = tr[0]["segments"][0]
    assert seg["clip"]["transform"] == {"x": 0.0, "y": 0.0}, \
        "a full-canvas layer must sit at identity, not inherit the donor's transform"
    assert seg["clip"]["scale"] == {"x": 1.0, "y": 1.0}
    again = add_track(out, dm, ds, [("/x/07_new.png", 5.0, 2.0, "New")])
    tr2 = [t for t in again["tracks"] if t.get("name") == TRACK]
    assert len(tr2) == 1 and len(tr2[0]["segments"]) == 1
    pngs = [m for m in again["materials"]["videos"] if m["path"].endswith("07_new.png")]
    assert len(pngs) == 1, "re-running must not leave orphan materials"
    assert next_index({"layers": [{"file": "/x/03_a.png"}, {"file": "/x/11_b.png"}]}) == 12
    assert next_index({"layers": []}) == 1
    print("sa_applyboxes self-check: ok (window clamp, identity placement, idempotent, "
          "numbering)")


if __name__ == "__main__":
    if "--test" in sys.argv:
        _test()
        sys.exit()
    ap = argparse.ArgumentParser()
    ap.add_argument("results", nargs="?")
    ap.add_argument("--fix", action="store_true")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    if not a.results:
        ap.error("give the verified results json")
    if a.fix and subprocess.run(["pgrep", "-x", "CapCut"],
                                capture_output=True).returncode == 0:
        raise SystemExit("CapCut is open — close it first")
    run(json.load(open(a.results)), a.fix)
