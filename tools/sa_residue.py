#!/usr/bin/env python3
"""Which call-outs did Saad MOVE, and had the verifier already rated them correct?

Requirement (12 Aug): measure the residue — boxes rated correct that he still moves.

A box he moves after a WRONG rating is the verifier working. A box he moves after a
CORRECT rating is the residue: either the verifier is wrong, or the placement was
defensible and he simply prefers it elsewhere. Only the residue tells us whether
auto-placement is worth trusting at all.

Two halves, joined on the overlay PNG name:

  his move   overlay segment in the finished CapCut draft whose clip.transform is
             no longer 0,0 — the PNG is authored full-canvas, so any transform is
             him dragging it. Reported in pixels against that project's canvas.
  my rating  sa_boxcheck --verify output (ok / wrong / unknown), if present.

    sa_residue.py                 every done project
    sa_residue.py "Training 03 Example"
    sa_residue.py --json out.json

Reads only. Never opens a draft for writing, so it is safe with CapCut running.
"""
import json
import os
import pathlib
import statistics
import sys

DRAFTS = pathlib.Path.home() / "Movies/CapCut/User Data/Projects/com.lveditor.draft"
BUILD = pathlib.Path(os.environ.get("TRAINING_ROOT", "~/Downloads/training-series")).expanduser() / "2 BUILD"   # where the module builds live
# CapCut stores clip.transform as a fraction of HALF the canvas: -1 = left edge.
HALF = 2.0


def draft_json(project):
    for candidate in (project / "draft_info.json",
                      *sorted(project.glob("Timelines/*/draft_info.json"))):
        if candidate.exists():
            try:
                return json.loads(candidate.read_text())
            except json.JSONDecodeError:
                continue
    return None


def canvas(draft):
    c = draft.get("canvas_config") or {}
    return float(c.get("width") or 1920), float(c.get("height") or 1080)


def plan_counts(build_folder):
    """How many times MY build used each overlay PNG."""
    counts = {}
    for f in build_folder.glob("*_LAYERS/_layers.json"):
        try:
            plan = json.loads(f.read_text())
        except json.JSONDecodeError:
            continue
        for layer in plan.get("layers", []):
            name = pathlib.Path(layer.get("file", "")).name
            if name:
                counts[name] = counts.get(name, 0) + 1
    return counts


def moved_boxes(draft):
    """Overlay PNG segments the user dragged off their authored position."""
    mats = {m.get("id"): m for m in (draft.get("materials", {}).get("videos") or [])}
    w, h = canvas(draft)
    out = []
    for track in draft.get("tracks", []):
        if track.get("type") != "video":
            continue
        for seg in track.get("segments") or []:
            mat = mats.get(seg.get("material_id")) or {}
            path = mat.get("path") or ""
            if "_LAYERS/" not in path or not path.lower().endswith(".png"):
                continue
            t = (seg.get("clip") or {}).get("transform") or {}
            dx, dy = float(t.get("x", 0.0)), float(t.get("y", 0.0))
            if abs(dx) < 1e-6 and abs(dy) < 1e-6:
                continue
            tr = seg.get("target_timerange") or {}
            start = tr.get("start", 0) / 1_000_000
            out.append({
                "png": pathlib.Path(path).name,
                # CapCut y is up-positive; screen y is down-positive.
                "dx_px": round(dx * w / HALF, 1),
                "dy_px": round(-dy * h / HALF, 1),
                "at": round(start, 2),
                "until": round(start + tr.get("duration", 0) / 1_000_000, 2),
            })
    return out


def ratings(build_folder):
    """sa_boxcheck --verify results, if the project has been checked."""
    for name in ("_boxcheck.json", "_verify.json"):
        for f in build_folder.glob(f"*_LAYERS/{name}"):
            try:
                data = json.loads(f.read_text())
            except json.JSONDecodeError:
                continue
            rows = data if isinstance(data, list) else data.get("results", [])
            table = {}
            for r in rows:
                png = pathlib.Path(r.get("file") or r.get("png") or "").name
                verdict = (r.get("verdict") or r.get("result") or "").lower()
                if png:
                    table[png] = verdict
            if table:
                return table
    return {}


def build_folder_for(png_name, cache={}):
    if not cache:
        for f in BUILD.glob("*/*_LAYERS/*.png"):
            cache.setdefault(f.name, f.parent.parent)
    return cache.get(png_name)


STOP = {"the", "and", "a", "an", "to", "of", "for", "on", "in", "is", "it", "you",
        "your", "this", "that", "then", "here", "with", "from", "need", "each",
        "any", "all", "click", "open", "select", "set", "add", "enter", "choose"}


def label_tokens(png_name):
    """Distinctive words in the baked-in label — '10_Back.png' -> {'back'}."""
    stem = pathlib.Path(png_name).stem
    parts = stem.split("_")
    if parts and parts[0].isdigit():
        parts = parts[1:]
    return {p.lower() for p in parts if len(p) >= 3 and p.lower() not in STOP}


def captions_at(draft):
    """(start, end, text) for every text segment — his own captions."""
    texts = {t["id"]: t for t in (draft.get("materials", {}).get("texts") or [])}
    out = []
    for track in draft.get("tracks", []):
        for seg in track.get("segments") or []:
            mat = texts.get(seg.get("material_id"))
            if not mat:
                continue
            try:
                content = json.loads(mat.get("content", "{}")).get("text", "")
            except (json.JSONDecodeError, TypeError):
                content = ""
            tr = seg.get("target_timerange") or {}
            start = tr.get("start", 0) / 1_000_000
            out.append((start, start + tr.get("duration", 0) / 1_000_000, content.lower()))
    return sorted(out)


def spoken_around(caps, start, end):
    return " ".join(t for s, e, t in caps if e > start and s < end)


def used_counts(draft):
    """How many times HIS finished draft uses each overlay PNG."""
    mats = {m.get("id"): m for m in (draft.get("materials", {}).get("videos") or [])}
    counts = {}
    for track in draft.get("tracks", []):
        if track.get("type") != "video":
            continue
        for seg in track.get("segments") or []:
            path = (mats.get(seg.get("material_id")) or {}).get("path") or ""
            if "_LAYERS/" in path and path.lower().endswith(".png"):
                name = pathlib.Path(path).name
                counts[name] = counts.get(name, 0) + 1
    return counts


def report(projects):
    rows = []
    for project in projects:
        draft = draft_json(project)
        if not draft:
            continue
        moves = moved_boxes(draft)
        if not moves:
            continue
        folder = build_folder_for(moves[0]["png"])
        rated = ratings(folder) if folder else {}
        mine = plan_counts(folder) if folder else {}
        his = used_counts(draft)
        caps = captions_at(draft)
        for m in moves:
            png = m["png"]
            extra = his.get(png, 0) - mine.get(png, 0)
            # Does the narration at that moment still mention what the chip says?
            spoken = spoken_around(caps, m["at"], m["until"])
            tokens = label_tokens(png)
            m["label_matches_narration"] = (
                None if not spoken or not tokens
                else any(tok in spoken for tok in tokens))
            # He duplicated the layer: the surplus copies are call-outs I never
            # built, carrying a label that still names the ORIGINAL element.
            m["kind"] = "duplicated" if extra > 0 else "repositioned"
            m["extra_copies"] = max(extra, 0)
            m["project"] = project.name
            m["rating"] = rated.get(png, "unrated")
            rows.append(m)
    return rows


def summarise(rows):
    if not rows:
        print("no moved call-outs found in any finished draft")
        return
    print(f"{len(rows)} call-outs moved across "
          f"{len(set(r['project'] for r in rows))} finished videos\n")
    dup = [r for r in rows if r["kind"] == "duplicated"]
    rep = [r for r in rows if r["kind"] == "repositioned"]
    print(f"  DUPLICATED  {len(dup):>3}  he copied my layer onto another element — "
          f"a call-out my build never made.")
    print(f"              the baked-in label still names the ORIGINAL element, so these "
          f"read WRONG on screen.")
    print(f"  REPOSITIONED{len(rep):>3}  same layer, he disagreed with where I put it.\n")
    suspect = [r for r in rows if r["label_matches_narration"] is False]
    checked = [r for r in rows if r["label_matches_narration"] is not None]
    if checked:
        print(f"  LABEL vs NARRATION: {len(suspect)} of {len(checked)} moved call-outs show a "
              f"chip whose words the narration never says at that moment.")
        for r in sorted(suspect, key=lambda r: (r["project"], r["at"]))[:12]:
            print(f"    {r['project'][:32]:<32} {r['at']:7.2f}s  {r['png'][:40]}")
        if len(suspect) > 12:
            print(f"    … and {len(suspect) - 12} more (see --json)")
        print()
    buckets = {}
    for r in rows:
        buckets.setdefault(r["rating"], []).append(r)
    for rating, group in sorted(buckets.items(), key=lambda kv: -len(kv[1])):
        dys = [r["dy_px"] for r in group]
        dxs = [r["dx_px"] for r in group]
        print(f"  rated {rating:<8} {len(group):>3}   "
              f"median dx {statistics.median(dxs):+7.1f}px   "
              f"median dy {statistics.median(dys):+7.1f}px")
    residue = buckets.get("ok", []) + buckets.get("correct", [])
    graded = [r for r in rows if r["rating"] not in ("unrated",)]
    if graded:
        print(f"\n  RESIDUE: {len(residue)} of {len(graded)} graded moves were on boxes "
              f"the verifier had passed ({100*len(residue)/len(graded):.0f}%)")
    else:
        print("\n  RESIDUE: not computable — no sa_boxcheck --verify results on disk.")
        print("  Run: Tools/sa_boxcheck.py '<…>_LAYERS/_layers.json' --verify  (1-6am, local vision)")
    print("\n  by video:")
    for name in sorted(set(r["project"] for r in rows)):
        g = [r for r in rows if r["project"] == name]
        print(f"    {len(g):>3}  {name}")


def demo():
    """Self-check: a transform of 0 is not a move; a real one converts to pixels."""
    draft = {
        "canvas_config": {"width": 1920, "height": 1080},
        "materials": {"videos": [
            {"id": "a", "path": "/x/T01_PACED_LAYERS/01_Click_Save.png"},
            {"id": "b", "path": "/x/T01_PACED_LAYERS/02_Click_Next.png"},
            {"id": "c", "path": "/x/T01_PACED.mp4"}]},
        "tracks": [{"type": "video", "segments": [
            {"material_id": "a", "clip": {"transform": {"x": 0.0, "y": 0.0}}},
            {"material_id": "b", "clip": {"transform": {"x": 0.0, "y": -0.2}}},
            {"material_id": "c", "clip": {"transform": {"x": 0.5, "y": 0.5}}}]}]}
    got = moved_boxes(draft)
    assert len(got) == 1, f"only the dragged PNG counts, got {got}"
    assert got[0]["png"] == "02_Click_Next.png"
    # y is up-positive in CapCut: -0.2 means he dragged it DOWN the screen.
    assert got[0]["dy_px"] == 108.0, got[0]
    print("demo ok")


def main():
    argv = sys.argv[1:]
    out_path = None
    if "--json" in argv:
        i = argv.index("--json")
        out_path = pathlib.Path(argv[i + 1])
        argv = argv[:i] + argv[i + 2:]          # ponytail: the value is not a project name
    args = [a for a in argv if not a.startswith("--")]
    if args:
        projects = [DRAFTS / a for a in args]
    else:
        projects = sorted(p for p in DRAFTS.glob("*") if p.is_dir())
    rows = report(projects)
    if out_path:
        out_path.write_text(json.dumps(rows, indent=1))
        print(f"wrote {out_path} ({len(rows)} rows)")
    summarise(rows)
    return 0


if __name__ == "__main__":
    sys.exit(demo() if "--demo" in sys.argv else main())
