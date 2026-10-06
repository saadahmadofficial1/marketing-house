#!/usr/bin/env python3
"""sa_capcut_flatten — collapse a call-out project down to the five tracks Saad works with.

Requirement (9 Sep), from Saad opening one project: put every marking on a single
track with the marking names on the track above it, so a project carries five tracks
rather than one per marking — one each for captions, markings, marking names, video
and voice-over. That keeps the edit smooth and fast.

He is right. The builder writes every call-out PNG as its own track, so a 55-marking module
arrives as 111 video tracks and CapCut becomes unusable. The markings never overlap in time
(checked before every flatten), so they all fit on two tracks: the boxes on one, the name
chips on the one above it.

    Tools/venv/bin/python3 Tools/sa_capcut_flatten.py "My Project"
    Tools/venv/bin/python3 Tools/sa_capcut_flatten.py --test

Refuses while CapCut is open, backs the draft up first (.pre_flatten), and refuses to touch a
project whose call-outs DO overlap — there the extra tracks are doing real work.
"""
import argparse, json, pathlib, shutil, subprocess, sys

CAPCUT = pathlib.Path("~/Movies/CapCut/User Data/Projects/com.lveditor.draft").expanduser()
US = 1_000_000


def capcut_open():
    return subprocess.run(["pgrep", "-x", "CapCut"], capture_output=True).returncode == 0


def _name(mats, mid):
    for lst in mats.values():
        if isinstance(lst, list):
            for m in lst:
                if isinstance(m, dict) and m.get("id") == mid:
                    return m.get("material_name") or m.get("name") or ""
    return ""


def plan(draft):
    """Which video tracks are call-outs, and do their segments overlap?"""
    mats = draft["materials"]
    boxes, labels, keep = [], [], []
    for t in draft["tracks"]:
        if t["type"] != "video":
            keep.append(t); continue
        names = [_name(mats, s["material_id"]) for s in t.get("segments", [])]
        if names and all(n.endswith("_box.png") for n in names):
            boxes += t["segments"]
        elif names and all(n.endswith("_label.png") for n in names):
            labels += t["segments"]
        else:
            keep.append(t)
    def spans(segs):
        return sorted((s["target_timerange"]["start"],
                       s["target_timerange"]["start"] + s["target_timerange"]["duration"]) for s in segs)
    clash = []
    for group, tag in ((boxes, "box"), (labels, "label")):
        for a, b in zip(spans(group), spans(group)[1:]):
            if b[0] < a[1]:
                clash.append((tag, round(a[1] / US, 2), round(b[0] / US, 2)))
    return keep, boxes, labels, clash


def flatten(project, apply=False):
    d = CAPCUT / project
    root = d / "draft_info.json"
    if not root.exists():
        sys.exit(f"no such project: {project}")
    draft = json.load(open(root))
    keep, boxes, labels, clash = plan(draft)
    before = len([t for t in draft["tracks"] if t["type"] == "video"])
    kept_v = len([t for t in keep if t["type"] == "video"])
    print(f"{project}\n  video tracks {before} -> {kept_v + (1 if boxes else 0) + (1 if labels else 0)}"
          f"   ({len(boxes)} box + {len(labels)} label segments)")
    if clash:
        print("  REFUSED: call-outs overlap in time, so the separate tracks are doing real work:")
        for tag, a, b in clash[:5]:
            print(f"    {tag}: one ends {a}s, the next starts {b}s")
        return False
    if not boxes and not labels:
        print("  nothing to flatten"); return True
    if not apply:
        print("  (dry run — pass --apply to write)"); return True
    if capcut_open():
        sys.exit("CapCut is open — close it first; a write into a loaded draft is lost or corrupts it")

    order = lambda segs: sorted(segs, key=lambda s: s["target_timerange"]["start"])
    tracks = list(keep)
    for segs, name in ((boxes, "Markings"), (labels, "Marking names")):
        if not segs:
            continue
        tracks.append({"id": segs[0]["id"][:32].upper().ljust(32, "0"), "type": "video",
                       "name": name, "attribute": 0, "flag": 0,
                       "is_default_name": False, "segments": order(segs)})
    draft["tracks"] = tracks + [t for t in draft["tracks"] if t["type"] in ("audio", "text")
                                and t not in tracks]
    # keep every non-video track exactly as it was, once
    seen, final = set(), []
    for t in tracks + [t for t in json.load(open(root))["tracks"] if t["type"] != "video"]:
        k = id(t) if t["type"] == "video" else (t["type"], t.get("name"), len(t.get("segments", [])))
        if k in seen: continue
        seen.add(k); final.append(t)
    draft["tracks"] = final

    for target in [root] + list(d.glob("Timelines/*/draft_info.json")):
        bak = target.with_suffix(".json.pre_flatten")
        if not bak.exists():
            shutil.copy2(target, bak)
        json.dump(draft, open(target, "w"))
    v = len([t for t in draft["tracks"] if t["type"] == "video"])
    a = len([t for t in draft["tracks"] if t["type"] == "audio"])
    x = len([t for t in draft["tracks"] if t["type"] == "text"])
    print(f"  written: {v} video + {a} audio + {x} text = {v+a+x} tracks   (backup .pre_flatten)")
    return True


def self_test():
    mk = lambda mid, a, b: {"id": "S" * 32, "material_id": mid,
                            "target_timerange": {"start": int(a * US), "duration": int((b - a) * US)}}
    draft = {"materials": {"videos": [{"id": "m1", "material_name": "PACED.mp4"},
                                      {"id": "b1", "material_name": "x_box.png"},
                                      {"id": "b2", "material_name": "y_box.png"},
                                      {"id": "l1", "material_name": "x_label.png"}]},
             "tracks": [{"type": "video", "segments": [mk("m1", 0, 60)]},
                        {"type": "video", "segments": [mk("b1", 1, 3)]},
                        {"type": "video", "segments": [mk("b2", 5, 7)]},
                        {"type": "video", "segments": [mk("l1", 1, 3)]},
                        {"type": "audio", "segments": []}]}
    keep, boxes, labels, clash = plan(draft)
    assert len(keep) == 2 and len(boxes) == 2 and len(labels) == 1 and not clash, (len(keep), len(boxes), clash)
    draft["tracks"][2]["segments"] = [mk("b2", 2, 7)]          # now it overlaps the first box
    assert plan(draft)[3], "overlapping call-outs must be refused"
    print("self-test ok")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project", nargs="?")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--test", action="store_true")
    a = ap.parse_args()
    if a.test:
        return self_test()
    if not a.project:
        sys.exit("name a CapCut project")
    flatten(a.project, a.apply)


if __name__ == "__main__":
    main()
