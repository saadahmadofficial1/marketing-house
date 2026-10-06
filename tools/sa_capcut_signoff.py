#!/usr/bin/env python3
"""sa_capcut_signoff — put the series sign-off on the tail of a CapCut project.

The "In the next video…" closer was dropped on 6 Aug; Saad's replacement is one
line, identical on every video in the series, so the ending is a brand beat rather
than a trailer:

    "Thank you for watching.  <brand tagline>"

Set SIGNOFF_TAGLINE to your own tagline. Left empty, only the thank-you caption is
written.

The voice-over already exists (rendered for the first video), so this reuses that one file
everywhere — same read, same pace, same loudness on every video.

    python3 sa_capcut_signoff.py "Training 01 Example"
    python3 sa_capcut_signoff.py --all
    python3 sa_capcut_signoff.py --test

It ADDS two tracks at the very end of the timeline and touches nothing else — the
picture, the call-outs and the captions Saad has already approved are left exactly
as they are. The 4.8s the sign-off occupies is left black on purpose: that is the
slot he drops the product logo card into. Both tracks are named, so he can drag them.

Re-running replaces the sign-off rather than stacking a second copy.
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
import uuid

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from sa_capcut_captions import (US, CAPCUT, CAPTION, CAPTION_FONT, capcut_open,
                                 donor_templates, styled, text_material,
                                 caption_segment, placed)

VO = (pathlib.Path(os.environ.get("TRAINING_ROOT", "~/Downloads/training-series")).expanduser()
      / "3 ASSETS" / "voice-over" / "signoff_thank_you_for_watching.mp3")

AUDIO_TRACK = "Sign-off VO"
SERIES_PREFIX = os.environ.get("SERIES_PREFIX", "Training ")   # CapCut project names in the series
TEXT_TRACK = "Sign-off"
LEAD = 0.10                      # start the caption a touch before the word lands

# Cue times measured from the sign-off voice-over, not guessed: "Thank you for watching."
# runs 0.00-1.02 and the tagline 1.78-4.54. Re-measure if the recorded line changes.
TAGLINE = os.environ.get("SIGNOFF_TAGLINE", "").strip()   # your brand tagline, if any
CUES = [(0.00, 1.35, "Thank you for watching.")] + \
       ([(1.70, 4.60, TAGLINE)] if TAGLINE else [])


def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    return float(out.stdout.strip())


def _donor_audio():
    """An audio material + segment shape from any project that has one."""
    for folder in sorted(CAPCUT.glob(SERIES_PREFIX + "*")):
        for p in sorted(folder.glob("Timelines/*/draft_info.json")):
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                continue
            auds = d["materials"].get("audios") or []
            ids = {a["id"] for a in auds}
            for tr in d.get("tracks", []):
                if tr.get("type") == "audio":
                    for s in tr.get("segments", []):
                        if s.get("material_id") in ids:
                            mat = next(a for a in auds if a["id"] == s["material_id"])
                            return copy.deepcopy(mat), copy.deepcopy(s)
    return None, None


def audio_templates(draft):
    """Clone this project's own audio material and segment.

    Authoring CapCut's audio schema from scratch is how you get a project that
    opens with a silent, undraggable clip. The project already contains the narrator's
    voice-over — copy its shape and change only what must change.
    """
    auds = draft["materials"].get("audios") or []
    if not auds:
        # Some videos carry no audio track at all — the voice is embedded in the paced
        # picture (seen on two modules). Borrow the shape from a donor that has
        # one; the schema is what we need, not its content. (Found 20 Aug.)
        return _donor_audio()
    ids = {a["id"] for a in auds}
    for tr in draft.get("tracks", []):
        if tr.get("type") == "audio":
            for s in tr.get("segments", []):
                if s.get("material_id") in ids:
                    return copy.deepcopy(auds[0]), copy.deepcopy(s)
    return copy.deepcopy(auds[0]), None


def content_end(draft):
    """Where the last frame of actual content sits, in seconds."""
    ends = [(s["target_timerange"]["start"] + s["target_timerange"]["duration"]) / US
            for t in draft.get("tracks", []) for s in t.get("segments", [])
            if s.get("target_timerange")]
    return max(ends) if ends else 0.0


def strip(draft):
    """Remove a previous sign-off so re-running never stacks two.

    Shrinks `duration` back to the content as well. Leaving it inflated is not cosmetic —
    CapCut exports the header length, so every video would have ended on 4.8s of black
    (caught 7 Aug, after the sign-off turned out to be a duplicate).
    """
    gone = {s["material_id"]
            for t in draft.get("tracks", []) if t.get("name") in (AUDIO_TRACK, TEXT_TRACK)
            for s in t.get("segments", []) if s.get("material_id")}
    draft["tracks"] = [t for t in draft.get("tracks", [])
                       if t.get("name") not in (AUDIO_TRACK, TEXT_TRACK)]
    for kind in ("audios", "texts"):
        draft["materials"][kind] = [m for m in draft["materials"].get(kind, [])
                                    if m["id"] not in gone]
    draft["duration"] = int(content_end(draft) * US)
    return draft


def build(draft, donor_text, donor_seg, vo_path, vo_dur, start=None):
    """Pure: draft -> draft with the sign-off audio and captions appended.

    start defaults to the end of the existing timeline, so the sign-off lands
    after the last frame rather than over the final step.
    """
    out = strip(copy.deepcopy(draft))
    end = start if start is not None else max(
        [(s["target_timerange"]["start"] + s["target_timerange"]["duration"]) / US
         for t in out.get("tracks", []) for s in t.get("segments", [])] or [0.0])

    amat, aseg = audio_templates(out)
    if amat is None:
        raise SystemExit("project has no audio material to copy the shape from")
    amat.update({"id": str(uuid.uuid4()).upper(), "path": str(vo_path),
                 "name": vo_path.name, "duration": int(vo_dur * US),
                 "music_id": "", "text_id": "", "tone_type": "", "local_material_id": ""})
    out["materials"].setdefault("audios", []).append(amat)

    seg = copy.deepcopy(aseg) if aseg else {"clip": None, "speed": 1.0, "volume": 1.0,
                                            "visible": True, "extra_material_refs": []}
    seg.update({"id": str(uuid.uuid4()).upper(), "material_id": amat["id"],
                "source_timerange": {"start": 0, "duration": int(vo_dur * US)},
                "target_timerange": {"start": int(end * US), "duration": int(vo_dur * US)},
                "speed": 1.0, "volume": 1.0, "visible": True,
                "group_id": "", "template_id": ""})
    out["tracks"].append({"id": str(uuid.uuid4()).upper(), "type": "audio",
                          "attribute": 0, "flag": 0, "is_default_name": False,
                          "name": AUDIO_TRACK, "segments": [seg]})

    segs = []
    for i, (a, b, text) in enumerate(CUES):
        m = styled(text_material(donor_text, text), CAPTION, CAPTION_FONT)
        out["materials"].setdefault("texts", []).append(m)
        segs.append(placed(caption_segment(donor_seg, m["id"],
                                           end + max(a - LEAD, 0.0), b - a, 950 + i),
                           CAPTION))
    out["tracks"].append({"id": str(uuid.uuid4()).upper(), "type": "text",
                          "attribute": 0, "flag": 0, "is_default_name": False,
                          "name": TEXT_TRACK, "segments": segs})

    out["duration"] = max(out.get("duration", 0), int((end + vo_dur) * US))
    return out


def spoken_already(video, model="small", tail=11.0):
    """Does the recorded voice-over already end with the sign-off?

    Checked the hard way — decode the last few seconds and listen — because nearly every
    video turned out to close with it and nothing in the project files said so. Adding a
    second one on top made every video thank the viewer twice (7 Aug). Call this BEFORE
    apply(), always.
    """
    import subprocess
    import tempfile
    from faster_whisper import WhisperModel
    dur = probe(video)
    wav = os.path.join(tempfile.mkdtemp(), "tail.wav")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{max(0, dur - tail):.3f}",
                    "-i", str(video), "-vn", "-ac", "1", "-ar", "16000", wav], check=True)
    segs, _ = WhisperModel(model, device="cpu", compute_type="int8").transcribe(wav, language="en")
    heard = " ".join(s.text for s in segs).lower()
    return "thank you for watching" in heard


def remove(project):
    """Take the sign-off back out, leaving everything else untouched."""
    from sa_guard import preflight
    preflight("capcut_write", project=project)
    if capcut_open():
        raise SystemExit("CapCut is open — close it first")
    n = 0
    for p in drafts_of(project):
        d = json.loads(p.read_text(encoding="utf-8"))
        before, was_dur = len(d.get("tracks", [])), d.get("duration")
        d = strip(d)
        n += before - len(d["tracks"])
        # write when EITHER changed: a second run has no tracks left to drop but may still
        # be carrying an inflated duration from the first
        if len(d["tracks"]) != before or d.get("duration") != was_dur:
            p.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    left = [t.get("name") for t in
            json.loads(drafts_of(project)[0].read_text(encoding="utf-8"))["tracks"]]
    if AUDIO_TRACK in left or TEXT_TRACK in left:
        raise SystemExit(f"{project}: sign-off track survived removal")
    print(f"-> {project}: {n} sign-off track(s) removed")
    return n


def drafts_of(project):
    t = CAPCUT / project
    paths = [t / "draft_info.json"] + \
            [pathlib.Path(p) for p in glob.glob(str(t / "Timelines/*/draft_info.json"))]
    return [p for p in paths if p.exists()]


def apply(project, vo=VO):
    from sa_guard import preflight
    preflight("capcut_write", project=project)
    if capcut_open():
        raise SystemExit("CapCut is open — close it first")
    if not vo.exists():
        raise SystemExit(f"sign-off voice-over missing: {vo}")
    paths = drafts_of(project)
    if not paths:
        raise SystemExit(f"no draft found for {project}")
    dur = probe(vo)
    dt, ds = donor_templates()
    for p in paths:
        bak = p.with_suffix(".json.pre_signoff")
        if not bak.exists():
            shutil.copy2(p, bak)
        d = json.loads(p.read_text(encoding="utf-8"))
        p.write_text(json.dumps(build(d, dt, ds, vo, dur), ensure_ascii=False),
                     encoding="utf-8")

    # Re-read the way CapCut will: the sign-off must be there, once, and audible.
    d = json.loads(paths[0].read_text(encoding="utf-8"))
    tracks = [t for t in d["tracks"] if t.get("name") in (AUDIO_TRACK, TEXT_TRACK)]
    paths_ok = all(pathlib.Path(m["path"]).exists()
                   for m in d["materials"]["audios"] if m.get("path"))
    if len(tracks) != 2 or not paths_ok:
        raise SystemExit(f"{project}: sign-off did not land ({len(tracks)} track(s), "
                         f"media ok={paths_ok})")
    at = next(t for t in tracks if t["name"] == AUDIO_TRACK)
    start = at["segments"][0]["target_timerange"]["start"] / US
    print(f"-> {project}: sign-off at {start:.1f}s, runs to {start + dur:.1f}s")
    return start


def _test():
    draft = {
        "duration": int(10 * US),
        "materials": {"audios": [{"id": "A", "path": "/old.mp3", "duration": 1,
                                  "name": "old"}], "texts": []},
        "tracks": [{"type": "audio", "name": "vo", "segments": [
            {"id": "s", "material_id": "A", "volume": 1.0,
             "source_timerange": {"start": 0, "duration": int(10 * US)},
             "target_timerange": {"start": 0, "duration": int(10 * US)}}]}],
    }
    dt = {"id": "T", "content": json.dumps({"text": "x", "styles": [{"range": [0, 1]}]})}
    ds = {"id": "S", "clip": {"transform": {"x": 0, "y": 0}, "scale": {"x": 1, "y": 1}},
          "target_timerange": {"start": 0, "duration": 1}}
    out = build(draft, dt, ds, pathlib.Path("/new.mp3"), 4.8)
    names = [t.get("name") for t in out["tracks"]]
    assert names.count(AUDIO_TRACK) == 1 and names.count(TEXT_TRACK) == 1
    a = next(t for t in out["tracks"] if t["name"] == AUDIO_TRACK)
    assert a["segments"][0]["target_timerange"]["start"] == int(10 * US), \
        "the sign-off starts after the last frame, never over the final step"
    assert out["duration"] == int(14.8 * US), "the timeline grows to hold it"
    assert len(out["materials"]["audios"]) == 2, "the original voice-over is untouched"
    again = build(out, dt, ds, pathlib.Path("/new.mp3"), 4.8)
    n = [t.get("name") for t in again["tracks"]]
    assert n.count(AUDIO_TRACK) == 1, "re-running replaces the sign-off, never stacks it"
    assert len(again["materials"]["audios"]) == 2, "and cleans up the material it replaced"
    assert len(again["materials"]["texts"]) == len(CUES), "one set of caption cues, never two"
    # taking it back out must also shrink the timeline, or the export ends on black
    back = strip(copy.deepcopy(out))
    assert back["duration"] == int(10 * US), \
        f"duration must return to the content length, got {back['duration'] / US}"
    assert not [t for t in back["tracks"] if t.get("name") in (AUDIO_TRACK, TEXT_TRACK)]
    print("sa_capcut_signoff self-check: ok (placement, growth, idempotence, no stacking)")


if __name__ == "__main__":
    if "--test" in sys.argv:
        _test()
        sys.exit()
    ap = argparse.ArgumentParser()
    ap.add_argument("project", nargs="?")
    ap.add_argument("--all", action="store_true", help="every project in the series")
    ap.add_argument("--remove", action="store_true",
                    help="take the sign-off back out (the voice-over may already have one)")
    a = ap.parse_args()
    if a.remove:
        if not a.project:
            ap.error("--remove needs a project name")
        remove(a.project)
        sys.exit()
    if a.all:
        names = sorted(p.name for p in CAPCUT.iterdir()
                       if p.is_dir() and p.name.startswith(SERIES_PREFIX))
        for n in names:
            try:
                apply(n)
            except SystemExit as e:
                print(f"!! {n}: {e}")
    elif a.project:
        apply(a.project)
    else:
        ap.error("give a project name or --all")
