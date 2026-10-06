#!/usr/bin/env python3
"""Finish a video's tail the way Saad does it: music that LANDS, then the two-part sign-off.

Written after he fixed one video by hand on 14 Sep and asked for the method to be kept:

  MUSIC — mine butt-joined 126.10s loops and truncated the last one wherever the video
  happened to end, so it stopped mid-phrase. His final segment is the END of the music
  file, back-timed so the track's own ending falls on the last frame:
        start = video_end - tail_length     (e.g. 300.00 - 60.00 = 240.00)
  Loops before it overlap by ~1.2s rather than butting. Volume stays 0.03, no fade-out —
  it ends because the music ends.

  SIGN-OFF — every finished video closes on two lines cut from ONE 4.80s file,
  `3 ASSETS/Voice-over/T01 sign-off/T01_SIGNOFF_Thank you for watching.mp3`:
        source 0.00-1.80  "Thank you for watching."      WITH a caption
        source 1.80-4.80  the brand tagline              NO caption
  Measured from a finished video: piece 1 on the outro's first frame, piece 2 at outro+2.43s,
  leaving a 3.67s music-only tail. Never regenerate this voice — reuse the file.

    sa_tailkit.py "<project>" [--timeline "<name>"]            # plan, writes nothing
    sa_tailkit.py "<project>" --timeline "<name>" --apply
    sa_tailkit.py --demo

Refuses while CapCut is open. Backs up before writing. Skips whatever is already there.
"""
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
ASSETS = pathlib.Path(os.environ.get("TRAINING_ROOT", "~/Downloads/training-series")).expanduser() / "3 ASSETS"
SIGNOFF = ASSETS / "Voice-over/T01 sign-off/T01_SIGNOFF_Thank you for watching.mp3"
MUSIC = pathlib.Path.home() / "Music/music_bed.mp3"   # your own licensed music bed
MUSIC_VOL = 0.03
LOOP_OVERLAP = 1.23          # his crossfade between loops, measured on his finished edit
SIGN_GAP = 2.43              # outro -> the tagline, measured on three finished videos
SIGN_A, SIGN_B = (0.00, 1.80), (1.80, 3.00)
CAPTION_LEN = 1.37


def probe(p):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", str(p)], capture_output=True, text=True).stdout.strip()
    return round(float(out), 2)


def music_plan(total, src_len, loop_len=None):
    """Where each music segment goes. The LAST one is always the file's own ending.

    Returns [(target_start, source_start, duration), ...]. Short videos get a single
    segment lifted from the tail of the file, which is why a 33s slice still finishes
    on the music's real last note instead of a cut.
    """
    loop_len = loop_len or src_len
    if total <= src_len:
        return [(0.0, round(src_len - total, 2), total)]
    out, t = [], 0.0
    stride = loop_len - LOOP_OVERLAP
    while t + loop_len < total - loop_len:
        out.append((round(t, 2), 0.0, loop_len))
        t = round(t + stride, 2)
    out.append((round(t, 2), 0.0, loop_len))
    tail = round(total - (t + stride), 2)
    tail = min(tail if tail > 0 else total - t, src_len)
    out.append((round(total - tail, 2), round(src_len - tail, 2), tail))
    return out


def capcut_open():
    return subprocess.run(["pgrep", "-x", "CapCut"], capture_output=True).returncode == 0


def resolve(project, timeline):
    p = DRAFTS / project
    if timeline:
        cfg = json.loads((p / "Timelines/project.json").read_text())
        want = next((t["id"] for t in cfg["timelines"] if t["name"] == timeline), None)
        if not want:
            sys.exit(f"no timeline {timeline!r}; have: "
                     + ", ".join(repr(t['name']) for t in cfg['timelines']))
        return p / "Timelines" / want / "draft_info.json"
    tls = sorted(p.glob("Timelines/*/draft_info.json"))
    return tls[0] if tls else p / "draft_info.json"


def apply(project, timeline, do_it):
    if do_it and capcut_open():
        sys.exit("REFUSING: CapCut is open.")
    dp = resolve(project, timeline)
    d = json.loads(dp.read_text())
    total = d["duration"] / US
    aud = {m["id"]: m for m in d["materials"].get("audios", [])}
    vid = {m["id"]: m for m in d["materials"].get("videos", [])}
    txt = {m["id"]: m for m in d["materials"].get("texts", [])}
    outro = [s["target_timerange"]["start"] / US for t in d["tracks"] for s in t.get("segments", [])
             if "OUTRO" in (vid.get(s.get("material_id"), {}).get("path", "")).upper()]
    if not outro:
        return f"  {timeline or project}: NO OUTRO CLIP — run sa_outro first, skipped"
    outro = outro[0]
    has_sign = any("SIGNOFF" in (aud.get(s.get("material_id"), {}).get("path", "")).upper()
                   for t in d["tracks"] for s in t.get("segments", []))
    music_segs = [(t, s) for t in d["tracks"] for s in t.get("segments", [])
                  if MUSIC.name in (aud.get(s.get("material_id"), {}).get("path", ""))]
    src_len = probe(MUSIC)
    plan_m = music_plan(total, src_len)
    lands = abs((plan_m[-1][0] + plan_m[-1][2]) - total) < 0.05

    lines = [f"  {timeline or project}   {total:.2f}s, outro at {outro:.2f}s",
             f"    music: {len(music_segs)} existing -> {len(plan_m)} segment(s), "
             f"last = source {plan_m[-1][1]:.2f}-{plan_m[-1][1]+plan_m[-1][2]:.2f} "
             f"at {plan_m[-1][0]:.2f}s (lands on the final frame: {lands})",
             f"    sign-off: {'already present, skipping' if has_sign else 'add both lines + caption on the first'}"]
    if not do_it:
        return "\n".join(lines) + "\n    (plan only)"

    shutil.copy2(dp, str(dp) + ".pre_tailkit")
    nid = lambda: str(uuid.uuid4()).upper()

    # ---- music: drop the inherited fragments, lay the landed bed ----
    for t, s in music_segs:
        t["segments"].remove(s)
    donor_a = next((s for t in d["tracks"] if t.get("type") == "audio"
                    for s in t.get("segments", [])), None)
    if donor_a is None:
        return "  no audio segment to clone a shape from — skipped"
    mm = copy.deepcopy(aud[donor_a["material_id"]])
    mm.update(id=nid(), path=str(MUSIC), name=MUSIC.name, duration=int(src_len * US),
              music_id="", text_id="", local_material_id="")
    d["materials"]["audios"].append(mm)
    msegs = []
    for st, ss, du in plan_m:
        s = copy.deepcopy(donor_a)
        s.update(id=nid(), material_id=mm["id"], speed=1.0, volume=MUSIC_VOL, visible=True,
                 extra_material_refs=[], group_id="", template_id="",
                 source_timerange={"start": int(ss * US), "duration": int(du * US)},
                 target_timerange={"start": int(st * US), "duration": int(du * US)})
        msegs.append(s)
    d["tracks"].append({"id": nid(), "type": "audio", "name": "Music",
                        "attribute": 0, "flag": 0, "segments": msegs, "is_default_name": False})

    # ---- sign-off ----
    if not has_sign:
        vt = max((t for t in d["tracks"] if t.get("type") == "audio" and t is not d["tracks"][-1]),
                 key=lambda t: len(t.get("segments", [])), default=None)
        if vt is None:
            vt = {"id": nid(), "type": "audio", "segments": [], "attribute": 0, "flag": 0}
            d["tracks"].append(vt)
        sm = copy.deepcopy(aud[donor_a["material_id"]])
        sm.update(id=nid(), path=str(SIGNOFF), name=SIGNOFF.name, duration=int(4.80 * US),
                  music_id="", text_id="", local_material_id="")
        d["materials"]["audios"].append(sm)
        for start, (ss, du) in ((outro, SIGN_A), (outro + SIGN_GAP, SIGN_B)):
            s = copy.deepcopy(donor_a)
            s.update(id=nid(), material_id=sm["id"], speed=1.0, volume=1.0, visible=True,
                     extra_material_refs=[], group_id="", template_id="",
                     source_timerange={"start": int(ss * US), "duration": int(du * US)},
                     target_timerange={"start": int(start * US), "duration": int(du * US)})
            vt["segments"].append(s)
        # caption on the thank-you only, cloned from this timeline's own caption style
        ct = next((t for t in d["tracks"] if t.get("name") == "Captions" and t.get("segments")), None)
        if ct:
            donor_c = ct["segments"][-1]
            cm = copy.deepcopy(txt[donor_c["material_id"]]); cm["id"] = nid()
            c = json.loads(cm["content"]); c["text"] = "Thank you for watching."
            st0 = (c.get("styles") or [{}])[0]; st0["range"] = [0, len(c["text"])]
            c["styles"] = [st0]
            cm["content"] = json.dumps(c, ensure_ascii=False)
            d["materials"]["texts"].append(cm)
            cs = copy.deepcopy(donor_c); cs["id"] = nid(); cs["material_id"] = cm["id"]
            cs["target_timerange"] = {"start": int(outro * US), "duration": int(CAPTION_LEN * US)}
            ct["segments"].append(cs)

    blob = json.dumps(d, ensure_ascii=False)
    dp.write_text(blob)
    root = dp.parent.parent.parent / "draft_info.json"
    if root.exists() and not timeline:
        root.write_text(blob)
    return "\n".join(lines) + "\n    written."


def demo():
    """The music must always finish on the video's last frame — that is the whole point."""
    # short slice: one segment lifted from the END of the file
    p = music_plan(33.0, 126.14)
    assert len(p) == 1 and p[0][0] == 0.0, p
    assert abs(p[0][1] - (126.14 - 33.0)) < 0.01, p
    assert abs((p[0][0] + p[0][2]) - 33.0) < 0.01, p
    # long video: loops, then the file's tail back-timed onto the end
    p = music_plan(300.0, 126.14)
    assert len(p) >= 2, p
    assert abs((p[-1][0] + p[-1][2]) - 300.0) < 0.05, p[-1]
    assert abs((p[-1][1] + p[-1][2]) - 126.14) < 0.05, p[-1]   # ends ON the file's ending
    for st, ss, du in p:
        assert st >= 0 and du > 0 and ss >= 0
    print("demo ok")


if __name__ == "__main__":
    if "--demo" in sys.argv:
        demo(); sys.exit(0)
    argv = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not argv:
        sys.exit(__doc__)
    tl = sys.argv[sys.argv.index("--timeline") + 1] if "--timeline" in sys.argv else None
    print(apply(argv[0], tl, "--apply" in sys.argv))
