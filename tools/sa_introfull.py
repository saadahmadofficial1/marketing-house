#!/usr/bin/env python3
"""Apply the intro + music recipe from Saad's finished donor module to another project.

Requirement (14 Aug): once he has finished a donor module, learn its recipe, apply it,
same music everywhere, and leave a project alone at the slightest doubt.
Every number below is measured from the donor module, not invented.

THE RECIPE (from his own edit)
  intro   INTRO_<tag> clip at 0.00, source cut at the spoken line's end,
          speed so the lips run at natural pace (1.2x undoes the 0.83x pacing
          baked into the clip; an unpaced clip stays at 1.0x), scale 1.06,
          duplicated on a second track, Slow Fade 0.53s into the content
  voice   the ORIGINAL-pace voice-over line at 0.00 (he swapped the slowed line
          back for the original)
  title   the old two-text card is DELETED; one text over the intro's empty
          left side, "line1\nline2", size 18, x -0.39 y 0, scale 0.49,
          line1 Poppins-Light, line2 Poppins-Black, 0 -> L-0.27
  shift   every existing segment moves + L  (L = source_cut / speed)
  music   Tutorial Music at volume 0.03, looped butt-joined to the outro end

SAFETY
  refuses while CapCut is open · backs up first · after writing, re-reads and
  verifies EVERY pre-existing segment moved by exactly +L and nothing else
  changed; any mismatch -> the backup is restored and the video is left alone.

    sa_introfull.py T02 --voice raw.mp3 --line-seconds 2.78 --speed 1.124
    sa_introfull.py T02 ... --apply
"""
import argparse
import copy
import json
import pathlib
import shutil
import subprocess
import sys
import uuid

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from sa_import import PROJECT, DRAFTS, ASSETS   # one shared intro-clips folder
from sa_outro import draft_path, US

DONOR = "Training 00 Donor Module"   # the finished CapCut project whose recipe is copied
MUSIC_ID = "YOUR_MUSIC_ID"    # CapCut library cache file name of the music bed
VOICE_MATCH = "intro_voice"   # substring of the donor's intro voice file name
MUSIC = pathlib.Path.home() / ("Library/Containers/com.lemon.lvoverseas/Data/Movies/"
                               "CapCut/User Data/Cache/music/" + MUSIC_ID + ".mp3")
MUSIC_LOOP = 126.10          # his loop chunk length
MUSIC_VOL = 0.03
INTRO_SCALE = 1.06           # 1140/1080 — fills his canvas
FADE_S = 0.53
TITLE_X, TITLE_Y, TITLE_SCALE = -0.39, 0.0, 0.49
TAIL_AFTER_LINE = 0.06       # his donor cut: 4.40 = 1.0 head + 3.34 paced line + 0.06


def capcut_running():
    return bool(subprocess.run(["pgrep", "-x", "CapCut"], capture_output=True).stdout.strip())


def probe_len(p):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", str(p)], capture_output=True, text=True).stdout.strip()
    return float(out)


def donor_bits():
    """The title material, fade material and intro/voice/music segment shapes from the donor."""
    d = json.loads(draft_path(DONOR).read_text())
    txts = d["materials"]["texts"]
    title = next(m for m in txts
                 if json.loads(m["content"]).get("styles", [{}])[0].get("size") == 18
                 and "\n" in json.loads(m["content"]).get("text", ""))
    fade = next(m for m in d["materials"]["transitions"]
                if m["name"] == "Slow Fade" and abs(m["duration"] / US - FADE_S) < 0.05)
    vids = {m["id"]: m for m in d["materials"]["videos"]}
    auds = {m["id"]: m for m in (d["materials"].get("audios") or [])}
    intro_mat = next(m for m in vids.values() if "INTRO_" in pathlib.Path(m.get("path", "")).name)
    music_mat = next(m for m in auds.values() if MUSIC_ID in m.get("path", ""))
    voice_mat = next(m for m in auds.values() if VOICE_MATCH in m.get("path", ""))
    segs = {"intro": None, "title": None, "music": None, "voice": None}
    for t in d["tracks"]:
        for s in t.get("segments") or []:
            mid = s.get("material_id")
            if mid == intro_mat["id"] and segs["intro"] is None:
                segs["intro"] = s
            if mid == title["id"]:
                segs["title"] = s
            if mid == music_mat["id"] and segs["music"] is None:
                segs["music"] = s
            if mid == voice_mat["id"] and segs["voice"] is None:
                segs["voice"] = s
    return title, fade, intro_mat, music_mat, voice_mat, segs


def new_id():
    return str(uuid.uuid4()).upper()


def title_lines(tag, d):
    """The two lines of this video's title, read from its OWN old title card."""
    txts = {m["id"]: m for m in (d["materials"].get("texts") or [])}
    heads = []
    for t in d["tracks"]:
        for s in t.get("segments") or []:
            m = txts.get(s.get("material_id"))
            if not m:
                continue
            c = json.loads(m.get("content", "{}"))
            if (c.get("styles") or [{}])[0].get("size") == 18:
                y = ((s.get("clip") or {}).get("transform") or {}).get("y", 0)
                heads.append((-y, m["id"], c.get("text", "")))
    heads.sort()          # top line first: it sits at y +0.07, the lower at -0.07
    return heads


def apply(tag, voice, line_seconds, speed, do_it, title_arg=None, project=None, voice_offset=0.0,
          no_music=False, timeline=None):
    project = project or PROJECT[tag]
    # A role slice is a SUB-timeline; without this the intro lands in the finished
    # parent video instead of the slice (the same trap sa_outro hit on 14 Sep).
    dp = draft_path(project, timeline)
    before = json.loads(dp.read_text())
    d = copy.deepcopy(before)

    intro_clip = sorted(ASSETS.glob(f"INTRO_{tag}_*.mp4"))
    if not intro_clip:
        return f"no intro clip for {tag}"
    intro_clip = intro_clip[0]

    src_cut = 1.0 + line_seconds + TAIL_AFTER_LINE          # head pad + PACED line + his hold
    src_cut = min(src_cut, probe_len(intro_clip))
    L = round(src_cut / speed, 2)

    # Some modules already carry a head gap he left for the intro — the intro must
    # land INTO that gap, so the shift is (L - existing_head), negative when the gap is
    # larger than the intro. Everyone else has head 0 and shifts by +L.
    vids0 = {m["id"]: m for m in before["materials"]["videos"]}
    head = None
    for t in before["tracks"]:
        for s0 in t.get("segments") or []:
            pth = (vids0.get(s0.get("material_id")) or {}).get("path", "")
            if "OUTRO" in pth.upper():
                continue
            # One module opens on a STILL with voice over it, not a video clip. Counting only
            # .mp4/.mov read its head as 7.5s, so the shift went negative and dragged the
            # still, its audio and its first caption to -1.73s. Any content counts as head.
            if pth or s0.get("material_id"):
                a = s0["target_timerange"]["start"] / US
                head = a if head is None else min(head, a)
    head = max(head or 0.0, 0.0)
    shift = round(L - head, 2)
    if shift < 0:
        return (f"{tag}: computed shift {shift:+.2f}s would push segments before 0 — "
                f"left alone (head {head:.2f}s vs intro {L:.2f}s)")

    title, donor_fade, donor_intro, donor_music, donor_voice, donor_segs = donor_bits()

    # ---- old title card out, its wording kept ----
    # Some modules never had a title card; their titles come from the build sheet,
    # split at the em dash exactly the way his other two-part cards split theirs.
    # Example entries: build tag -> (line 1, line 2).
    NO_CARD = {"T01": ("Example two-part module", "Part 1"),
               "T02": ("Example two-part module", "Part 2")}
    heads = title_lines(tag, d)
    # 14 Sep: the role-wise projects never had a title card (captions are size 5, and
    # there is no size-18 head text), so there is nothing to read the wording from. --title
    # supplies it as "line 1|line 2" instead of hardcoding another NO_CARD entry per video.
    if title_arg and not heads:
        line1, line2 = [x.strip() for x in title_arg.split("|", 1)]
        heads = []
    elif heads:
        line1 = heads[0][2].strip()
        line2 = heads[1][2].strip() if len(heads) > 1 else ""
    elif tag in NO_CARD:
        line1, line2 = NO_CARD[tag]
    else:
        return f"{tag}: no title card and no fallback — left alone"
    old_ids = {mid for _s, mid, _t in heads}
    for t in d["tracks"]:
        t["segments"] = [s for s in (t.get("segments") or []) if s.get("material_id") not in old_ids]

    # ---- shift everything that exists by the computed amount ----
    moved = 0
    for t in d["tracks"]:
        for s in t.get("segments") or []:
            s["target_timerange"]["start"] += int(shift * US)
            moved += 1

    US_L = int(shift * US)

    def seg(base, mat_id, start, dur, src, extra=None):
        s = copy.deepcopy(base)
        s["id"] = new_id()
        s["material_id"] = mat_id
        s["target_timerange"] = {"start": int(start * US), "duration": int(dur * US)}
        if s.get("source_timerange") is not None:
            s["source_timerange"] = {"start": int(src * US), "duration": int(dur * US * (s.get("speed", 1) or 1))}
        s["extra_material_refs"] = extra or []
        return s

    # ---- intro clip: main track + duplicate above, fade on the main copy ----
    imat = copy.deepcopy(donor_intro); imat["id"] = new_id()
    imat["path"] = str(intro_clip)
    imat["duration"] = int(probe_len(intro_clip) * US)
    d["materials"]["videos"].append(imat)
    fmat = copy.deepcopy(donor_fade); fmat["id"] = new_id()
    d["materials"].setdefault("transitions", []).append(fmat)

    main = seg(donor_segs["intro"], imat["id"], 0, L, 0, [fmat["id"]])
    main["speed"] = speed
    main["source_timerange"] = {"start": 0, "duration": int(src_cut * US)}
    main["clip"]["scale"] = {"x": INTRO_SCALE, "y": INTRO_SCALE}
    # the picture track is the one whose first (shifted) segment sits at L
    pic = min((t for t in d["tracks"] if t.get("type") == "video" and t.get("segments")),
              key=lambda t: min(s["target_timerange"]["start"] for s in t["segments"]))
    pic["segments"].insert(0, main)

    twin = copy.deepcopy(main); twin["id"] = new_id(); twin["extra_material_refs"] = []
    d["tracks"].append({"type": "video", "segments": [twin], "id": new_id(),
                        "attribute": 0, "flag": 0})

    # ---- merged title over the intro ----
    tmat = copy.deepcopy(title); tmat["id"] = new_id()
    c = json.loads(tmat["content"])
    text = f"{line1}\n{line2}"
    n1 = len(line1) + 1
    c["text"] = text
    st = c["styles"]
    st[0]["range"] = [0, n1]
    st[1]["range"] = [n1, len(text)]
    tmat["content"] = json.dumps(c, ensure_ascii=False)
    d["materials"]["texts"].append(tmat)
    ts = seg(donor_segs["title"], tmat["id"], 0, max(L - 0.27, 1.0), 0)
    ts["clip"]["transform"] = {"x": TITLE_X, "y": TITLE_Y}
    ts["clip"]["scale"] = {"x": TITLE_SCALE, "y": TITLE_SCALE}
    d["tracks"].append({"type": "text", "segments": [ts], "id": new_id(),
                        "attribute": 0, "flag": 0})

    # ---- original-pace voice ----
    # 14 Sep: the Seedance clip is generated against the PADDED track from sa_introline
    # (HEAD silence, then the line, then a hold), but the voice placed here is the UNPADDED
    # file. Starting it at 0.00 puts her lips HEAD seconds behind the words, and leaves that
    # much mouth movement running after the line ends — exactly what Saad had to trim off
    # one role-wise video by hand. Offsetting the voice by the head pad lines them up and
    # keeps his approved 1s of stillness before she speaks.
    vmat = copy.deepcopy(donor_voice); vmat["id"] = new_id()
    vmat["path"] = str(voice)
    vmat["name"] = pathlib.Path(voice).name
    vmat["duration"] = int(probe_len(voice) * US)
    d["materials"].setdefault("audios", []).append(vmat)
    vs = seg(donor_segs["voice"], vmat["id"], voice_offset / (speed or 1.0),
             min(probe_len(voice), L - voice_offset / (speed or 1.0)), 0)
    vtrack = {"type": "audio", "segments": [vs], "id": new_id(), "attribute": 0, "flag": 0}
    d["tracks"].append(vtrack)

    # ---- music 0 -> outro end, butt-joined loops ----
    # 15 Sep: the role-wise timelines already carry LANDED music from sa_tailkit
    # (its last segment is the music file's own ending, back-timed onto the last frame).
    # Laying this butt-joined bed on top gives two music tracks and re-introduces the
    # mid-phrase stop Saad fixed by hand on one of them. Auto-skip when music is present.
    vids = {m["id"]: m for m in d["materials"]["videos"]}
    auds_now = {m["id"]: m for m in d["materials"].get("audios", [])}
    has_music = any(MUSIC_ID in (auds_now.get(s2.get("material_id"), {}).get("path", ""))
                    for t in d["tracks"] for s2 in t.get("segments") or [])
    end = 0
    for t in d["tracks"]:
        for s in t.get("segments") or []:
            e = (s["target_timerange"]["start"] + s["target_timerange"]["duration"]) / US
            end = max(end, e)
    msegs = []
    if not (no_music or has_music):
        mmat = copy.deepcopy(donor_music); mmat["id"] = new_id()
        d["materials"]["audios"].append(mmat)
        msegs, cur = [], 0.0
        while cur < end - 0.05:
            dur = min(MUSIC_LOOP, end - cur)
            ms = seg(donor_segs["music"], mmat["id"], cur, dur, 0.03)
            ms["volume"] = MUSIC_VOL
            msegs.append(ms)
            cur += dur
        d["tracks"].append({"type": "audio", "segments": msegs, "id": new_id(),
                            "attribute": 0, "flag": 0})

    d["duration"] = int(end * US)

    # ---- verify against the before-image ----
    def snapshot(x, skip_ids=()):
        out = []
        for t in x["tracks"]:
            for s in t.get("segments") or []:
                if s.get("material_id") in skip_ids or s["id"] in skip_ids:
                    continue
                out.append((s["id"], s["target_timerange"]["start"], s["target_timerange"]["duration"]))
        return sorted(out)

    old = [(i, st0 + US_L, du) for i, st0, du in snapshot(before, old_ids)]
    new_ids = {main["id"], twin["id"], ts["id"], vs["id"]} | {m["id"] for m in msegs}
    now = [r for r in snapshot(d) if r[0] not in new_ids]
    if old != now:
        return f"VERIFY FAILED for {tag} — nothing written"

    print(f"  {tag:<7} L={L:.2f}s shift {shift:+.2f}s  speed {speed:.2f}  cut {src_cut:.2f}s  "
          f"title \"{line1} / {line2[:32]}\"  music to {end:.2f}s  "
          f"({moved} segs, verified)")
    if not do_it:
        return "dry run ok"
    if capcut_running():
        return "REFUSED: CapCut is open"
    bak = dp.with_suffix(".json.pre_full")
    shutil.copy2(dp, bak)
    blob = json.dumps(d, ensure_ascii=False)
    dp.write_text(blob)
    # 15 Sep: a single-timeline project ALSO keeps a root draft_info.json, and CapCut can
    # show that one. One video kept its old, shorter length in the root while the
    # timeline file already held the intro — the intro was written but invisible. Never
    # touch the root on a MULTI-timeline project: there it is the finished parent video,
    # not the slice.
    root = dp.parent.parent.parent / "draft_info.json"
    if root.exists() and len(list(root.parent.glob("Timelines/*/draft_info.json"))) == 1:
        shutil.copy2(root, str(root) + ".pre_rootsync")
        root.write_text(blob)
    # paranoia: re-read and re-verify from disk
    disk = json.loads(dp.read_text())
    if [r for r in snapshot(disk) if r[0] not in new_ids] != old:
        shutil.copy2(bak, dp)
        return f"POST-WRITE VERIFY FAILED for {tag} — backup restored"
    return "written"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tag")
    ap.add_argument("--voice", required=True)
    ap.add_argument("--line-seconds", type=float, required=True)
    ap.add_argument("--speed", type=float, required=True)
    ap.add_argument("--title", help='"line 1|line 2" for a project with no old title card')
    ap.add_argument("--project", help="CapCut project name, when the tag is not in PROJECT")
    ap.add_argument("--voice-offset", type=float, default=0.0,
                    help="seconds of head pad baked into the clip; delays the voice to match her lips")
    ap.add_argument("--timeline", help="sub-timeline name, for a role slice")
    ap.add_argument("--no-music", action="store_true",
                    help="never add music (auto-skipped anyway when the timeline already has it)")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    print(apply(a.tag, pathlib.Path(a.voice), a.line_seconds, a.speed, a.apply, a.title, a.project, a.voice_offset,
                a.no_music, a.timeline))


if __name__ == "__main__":
    main()
