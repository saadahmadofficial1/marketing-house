#!/usr/bin/env python3
"""sa_addvo — put a generated voice-over into a CapCut draft as ONE track, and mute the
original narration underneath it.

Requirement (23 Sep 2026): the first phone-app builds arrived without the generated voice-over.
The voice decision was already taken; this is the tool that carries it out. It obeys his
9 Sep track rule — one voice-over track, not one per line — while still keeping every
line its own segment so he can drag a single line without touching the rest.

    Tools/venv/bin/python3 Tools/sa_addvo.py "Mobile 06 Example" vo.json
    Tools/venv/bin/python3 Tools/sa_addvo.py --test

vo.json: {"lines": [{"file": "01.mp3", "start": 0.11}, ...]}

Refuses while CapCut is open, backs the draft up first (.pre_vo), and refuses to stack two
lines on top of each other — overlapping voice is the one fault nobody can edit around.
"""
import argparse, copy, json, os, pathlib, shutil, subprocess, sys

CAPCUT = pathlib.Path("~/Movies/CapCut/User Data/Projects/com.lveditor.draft").expanduser()
DONOR = os.environ.get("CAPCUT_DONOR", "Training-copy")   # any CapCut project with an audio track: its JSON shapes are reused
US = 1_000_000


def capcut_open():
    return subprocess.run(["pgrep", "-x", "CapCut"], capture_output=True).returncode == 0


def nid():
    import uuid
    return str(uuid.uuid4()).upper()


def dur_of(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", str(path)], capture_output=True, text=True).stdout
    return float(out.strip())


def clashes(lines):
    """Lines must not overlap. Returns the offending pairs."""
    out = []
    s = sorted(lines, key=lambda l: l["start"])
    for a, b in zip(s, s[1:]):
        if b["start"] < a["start"] + a["duration"] - 0.01:
            out.append((round(a["start"], 2), round(a["start"] + a["duration"], 2),
                        round(b["start"], 2)))
    return out


def add(draft, donor, lines, mute_picture=True):
    """Pure: draft + donor shapes + lines -> draft with one voice-over track."""
    am0 = copy.deepcopy(donor["audio_material"])
    as0 = copy.deepcopy(donor["audio_segment"])
    segs = []
    draft["materials"].setdefault("audios", [])
    for l in sorted(lines, key=lambda x: x["start"]):
        m = copy.deepcopy(am0)
        m.update(id=nid(), path=str(l["file"]), name=pathlib.Path(l["file"]).name,
                 duration=int(l["duration"] * US), music_id="", text_id="",
                 local_material_id="")
        draft["materials"]["audios"].append(m)
        s = copy.deepcopy(as0)
        s.update(id=nid(), material_id=m["id"], speed=1.0, volume=1.0, visible=True,
                 extra_material_refs=[], group_id="", template_id="",
                 source_timerange={"start": 0, "duration": int(l["duration"] * US)},
                 target_timerange={"start": int(l["start"] * US),
                                   "duration": int(l["duration"] * US)})
        s["common_keyframes"] = []
        s["keyframe_refs"] = []
        segs.append(s)
    draft["tracks"].append({"id": nid(), "type": "audio", "name": "Voice over",
                            "attribute": 0, "flag": 0, "is_default_name": False,
                            "segments": segs})
    if mute_picture:
        # the recording carries the presenter's live narration; the generated voice replaces it
        for t in draft["tracks"]:
            if t["type"] == "video":
                for s in t["segments"]:
                    s["volume"] = 0.0
    return draft


def write(project, vo_path):
    if capcut_open():
        raise SystemExit("CapCut is open — close it first")
    target = CAPCUT / project
    tl = next((target / "Timelines").glob("*/draft_info.json"))
    spec = json.loads(pathlib.Path(vo_path).read_text())
    lines = []
    for l in spec["lines"]:
        f = os.path.expanduser(l["file"])
        if not os.path.exists(f):
            raise SystemExit(f"missing voice file: {f}")
        lines.append({"file": f, "start": float(l["start"]), "duration": dur_of(f)})
    bad = clashes(lines)
    if bad:
        raise SystemExit(f"voice lines overlap, refusing: {bad[:3]}")

    dd = json.loads(next((CAPCUT / DONOR / "Timelines").glob("*/draft_info.json")).read_text())
    da = next(s for t in dd["tracks"] if t.get("type") == "audio" for s in t.get("segments", []))
    dm = next(m for m in dd["materials"]["audios"] if m["id"] == da["material_id"])

    bak = tl.with_suffix(".json.pre_vo")
    if not bak.exists():
        shutil.copy2(tl, bak)
    d = json.loads(tl.read_text())
    d = add(d, {"audio_material": dm, "audio_segment": da}, lines)
    end = max(l["start"] + l["duration"] for l in lines)
    d["duration"] = max(d.get("duration", 0), int(end * US))
    tl.write_text(json.dumps(d))
    (target / "draft_info.json").write_text(json.dumps(d))
    tracks = {}
    for t in d["tracks"]:
        tracks[t["type"]] = tracks.get(t["type"], 0) + 1
    print(f"-> {project}: {len(lines)} voice lines on ONE track; "
          f"tracks now {dict(tracks)}; original narration muted")


def _test():
    donor = {"audio_material": {"id": "m0", "path": "/old.mp3", "duration": 1},
             "audio_segment": {"id": "s0", "material_id": "m0", "volume": 1.0,
                               "source_timerange": {}, "target_timerange": {}}}
    draft = {"materials": {"audios": []},
             "tracks": [{"type": "video", "segments": [{"volume": 1.0}]}]}
    out = add(draft, donor, [{"file": "/a.mp3", "start": 5.0, "duration": 2.0},
                             {"file": "/b.mp3", "start": 0.0, "duration": 3.0}])
    at = [t for t in out["tracks"] if t["type"] == "audio"]
    assert len(at) == 1, "one voice-over track, never one per line"
    assert len(at[0]["segments"]) == 2
    starts = [s["target_timerange"]["start"] for s in at[0]["segments"]]
    assert starts == sorted(starts), "segments must be written in time order"
    assert out["tracks"][0]["segments"][0]["volume"] == 0.0, "original narration must be muted"
    assert clashes([{"start": 0, "duration": 3}, {"start": 2, "duration": 1}])
    assert not clashes([{"start": 0, "duration": 2}, {"start": 2, "duration": 1}])
    print("ok")


if __name__ == "__main__":
    a = argparse.ArgumentParser()
    a.add_argument("project", nargs="?"); a.add_argument("vo", nargs="?")
    a.add_argument("--test", action="store_true")
    n = a.parse_args()
    if n.test:
        _test()
    elif n.project and n.vo:
        write(n.project, n.vo)
    else:
        a.error("need project and vo.json, or --test")
