#!/usr/bin/env python3
"""Add the per-role opening line to a training-module role slice, and tidy what the slicing left behind.

Saad, 15 Sep, on one role slice: the script's opening paragraph is missing. He is right,
and the reason it is missing is structural:

    The module recording has ONE opening ("In this video, we'll learn how ..."). Only the
    first role's slice is cut from the start of the recording, so only that role has an
    opening. The per-role openings live in the SCRIPTS and were never recorded, so they
    have to be voiced and inserted.

What this does, in one backed-up write:
  1. inserts the voiced opening right after the presenter intro, over a FROZEN first content
     frame (the screen is static there anyway), and shifts everything after it
  2. writes the caption in the house chunks, cloned from the slice's own caption style
  3. deletes the stray "Sign in as <role>" label the slicing duplicated into mid-video
  4. puts the intro voice back on 1.00s — the clip carries exactly 1.0s of head silence,
     so any other value shows as lip lag

    sa_openline.py "<timeline>" --voice OPEN_ROLE.mp3 --caption "a|b|c"     # plan
    sa_openline.py "<timeline>" --voice ... --caption ... --apply
    sa_openline.py --demo

Refuses while CapCut is open.
"""
import argparse
import copy
import json
import os
import pathlib
import shutil
import subprocess
import sys
import uuid

US = 1_000_000
DRAFTS = pathlib.Path.home() / "Movies/CapCut/User Data/Projects/com.lveditor.draft"
PROJECT = os.environ.get("CAPCUT_PROJECT", "Training 01 Example")   # the CapCut project that holds the role timelines
GAP = 0.25          # breath between the intro and the opening line
HEAD_PAD = 1.00     # silence baked into every presenter intro clip


def capcut_open():
    return subprocess.run(["pgrep", "-x", "CapCut"], capture_output=True).returncode == 0


def probe(p):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", str(p)], capture_output=True, text=True).stdout.strip()
    return round(float(out), 2)


def resolve(timeline):
    p = DRAFTS / PROJECT
    cfg = json.loads((p / "Timelines/project.json").read_text())
    want = next((t["id"] for t in cfg["timelines"] if timeline.lower() in t["name"].lower()), None)
    if not want:
        sys.exit(f"no timeline matching {timeline!r}; have: "
                 + ", ".join(repr(t["name"]) for t in cfg["timelines"]))
    return p / "Timelines" / want / "draft_info.json"


def chunk_times(parts, total):
    """Share the line's length across the caption chunks by character count, so a long
    chunk stays up longer. Hand-set seconds would drift the moment the wording changes."""
    n = sum(len(p) for p in parts)
    t, out = 0.0, []
    for p in parts:
        d = round(total * len(p) / n, 2)
        out.append((round(t, 2), d))
        t += d
    return out


def plan(dp, voice, parts):
    d = json.loads(dp.read_text())
    vid = {m["id"]: m for m in d["materials"].get("videos", [])}
    txt = {m["id"]: m for m in d["materials"].get("texts", [])}
    aud = {m["id"]: m for m in d["materials"].get("audios", [])}
    intro = [s for t in d["tracks"] for s in t.get("segments", [])
             if "INTRO_" in (vid.get(s.get("material_id"), {}).get("path", ""))]
    if not intro:
        sys.exit("no presenter intro in this timeline — run sa_introfull first")
    top = max(intro, key=lambda s: s["target_timerange"]["duration"])
    # SHIFT from the instant the intro ends, not from where the voice starts. The content
    # audio begins on the intro's last frame, so a later threshold leaves it behind and it
    # talks over the new line (caught 15 Sep on one role slice before Saad saw it).
    at = (top["target_timerange"]["start"] + top["target_timerange"]["duration"]) / US
    vlen = probe(voice)
    # the stray mid-video label: a lone "Sign in as ..." text on a track of its own
    strays = []
    for t in d["tracks"]:
        segs = [s for s in t.get("segments", []) if s.get("material_id") in txt]
        if len(segs) == 1 and len(t.get("segments", [])) == 1:
            body = json.loads(txt[segs[0]["material_id"]]["content"]).get("text", "")
            if body.startswith("Sign in") and segs[0]["target_timerange"]["start"] / US > at:
                strays.append((t, segs[0], body))
    # intro voice that is not on HEAD_PAD
    bad_voice = [s for t in d["tracks"] for s in t.get("segments", [])
                 if "/intro lines" in (aud.get(s.get("material_id"), {}).get("path", ""))
                 and abs(s["target_timerange"]["start"] / US - HEAD_PAD) > 0.05]
    return d, at, vlen, strays, bad_voice


def apply(timeline, voice, parts, do_it):
    if do_it and capcut_open():
        sys.exit("REFUSING: CapCut is open.")
    dp = resolve(timeline)
    d, at, vlen, strays, bad_voice = plan(dp, voice, parts)
    old = d["duration"] / US
    shift = round(vlen + GAP, 2)
    L = [f"  {timeline}", f"    opening line {vlen:.2f}s goes in at {at + GAP:.2f}s (shift from {at:.2f}s)",
         f"    length {old:.2f}s -> {old + shift:.2f}s   everything from {at:.2f}s shifts +{shift:.2f}s",
         f"    stray labels to delete: {[s[2] for s in strays] or 'none'}",
         f"    intro voice off {HEAD_PAD}s: {[round(s['target_timerange']['start']/US,2) for s in bad_voice] or 'no'}",
         f"    caption chunks: {len(parts)}"]
    if not do_it:
        return "\n".join(L) + "\n    (plan only)"

    shutil.copy2(dp, str(dp) + ".pre_openline")
    nid = lambda: str(uuid.uuid4()).upper()
    vid = {m["id"]: m for m in d["materials"]["videos"]}
    txt = {m["id"]: m for m in d["materials"].get("texts", [])}

    for t, s, _ in strays:
        t["segments"].remove(s)
    for s in bad_voice:
        s["target_timerange"]["start"] = int(HEAD_PAD * US)

    # the content clip that is playing at `at` — freeze its first frame under the line
    body = None
    for t in d["tracks"]:
        for s in t.get("segments", []):
            p = vid.get(s.get("material_id"), {}).get("path", "")
            a = s["target_timerange"]["start"] / US
            if p.endswith((".mp4", ".mov")) and "INTRO_" not in p and a >= at - 0.6:
                if body is None or a < body[1]["target_timerange"]["start"] / US:
                    body = (t, s)
    if body is None:
        return "\n".join(L) + "\n    no content clip after the intro — nothing to freeze onto"

    for t in d["tracks"]:
        for s in t.get("segments", []):
            if s["target_timerange"]["start"] / US >= at - 0.01:
                s["target_timerange"]["start"] += int(shift * US)

    ft = copy.deepcopy(body[1])
    ft.update(id=nid(), speed=1.0, volume=0.0, extra_material_refs=[], group_id="", template_id="",
              source_timerange={"start": body[1]["source_timerange"]["start"], "duration": 40000},
              target_timerange={"start": int(at * US), "duration": int(shift * US)})
    ft["keyframe_refs"] = []; ft["common_keyframes"] = []
    body[0]["segments"].append(ft)

    donor_a = next(s for t in d["tracks"] if t.get("type") == "audio" for s in t.get("segments", []))
    am = copy.deepcopy(next(m for m in d["materials"]["audios"] if m["id"] == donor_a["material_id"]))
    am.update(id=nid(), path=str(voice), name=pathlib.Path(voice).name,
              duration=int(vlen * US), music_id="", text_id="", local_material_id="")
    d["materials"]["audios"].append(am)
    a = copy.deepcopy(donor_a)
    a.update(id=nid(), material_id=am["id"], speed=1.0, volume=1.0, visible=True,
             extra_material_refs=[], group_id="", template_id="",
             source_timerange={"start": 0, "duration": int(vlen * US)},
             target_timerange={"start": int((at + GAP) * US), "duration": int(vlen * US)})
    d["tracks"].append({"id": nid(), "type": "audio", "name": "Opening line",
                        "attribute": 0, "flag": 0, "segments": [a], "is_default_name": False})

    ct = max((t for t in d["tracks"] if any(s.get("material_id") in txt for s in t.get("segments", []))),
             key=lambda t: len(t["segments"]))
    donor_c = min((s for s in ct["segments"] if s.get("material_id") in txt),
                  key=lambda s: s["target_timerange"]["start"])
    for (off, dur), body_text in zip(chunk_times(parts, vlen), parts):
        cm = copy.deepcopy(txt[donor_c["material_id"]]); cm["id"] = nid()
        c = json.loads(cm["content"]); c["text"] = body_text
        st0 = (c.get("styles") or [{}])[0]; st0["range"] = [0, len(body_text)]
        c["styles"] = [st0]
        cm["content"] = json.dumps(c, ensure_ascii=False)
        d["materials"]["texts"].append(cm)
        cs = copy.deepcopy(donor_c); cs["id"] = nid(); cs["material_id"] = cm["id"]
        cs["target_timerange"] = {"start": int((at + GAP + off) * US), "duration": int(dur * US)}
        ct["segments"].append(cs)

    d["duration"] = int(round(old + shift, 2) * US)
    dp.write_text(json.dumps(d, ensure_ascii=False))
    L.append(f"    written — {len(parts)} captions, freeze {shift:.2f}s, new length {d['duration']/US:.2f}s")
    return "\n".join(L)


def demo():
    """Chunk timing must fill the line exactly and never run backwards."""
    parts = ["In this video, we'll follow the reviewer:",
             "taking the record the team has sent",
             "for checks,", "working through the review,",
             "and passing it back to the requester."]
    ts = chunk_times(parts, 11.25)
    assert len(ts) == len(parts)
    assert abs(sum(d for _o, d in ts) - 11.25) < 0.05, ts
    assert all(b[0] >= a[0] + a[1] - 0.02 for a, b in zip(ts, ts[1:])), ts
    assert ts[0][0] == 0.0
    longest = max(range(len(parts)), key=lambda i: len(parts[i]))
    assert ts[longest][1] == max(d for _o, d in ts), "the longest line must hold longest"
    print("demo ok")


if __name__ == "__main__":
    if "--demo" in sys.argv:
        demo(); sys.exit(0)
    ap = argparse.ArgumentParser()
    ap.add_argument("timeline")
    ap.add_argument("--voice", required=True)
    ap.add_argument("--caption", required=True, help="caption chunks separated by |")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    print(apply(a.timeline, pathlib.Path(a.voice).expanduser(), a.caption.split("|"), a.apply))
