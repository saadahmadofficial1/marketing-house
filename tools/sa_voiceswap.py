#!/usr/bin/env python3
"""Surgically replace or silence a stretch of voice in a CapCut draft.

RETIRED FOR VOICE PLACEMENT — 18 Aug, after this tool placed 11 lines into one
module, Saad ruled it out: only the markings and timestamps were useful. The splits and mute-pieces read to him as
silent gaps and clutter in HIS timeline. The standing workflow is now
DELIVERABLES ONLY: hand him files named USE_<nn>_<timestamp>s_<slug>.mp3 and he
places them himself. Do not run this against his projects again unless he
explicitly asks for an in-place swap on a named video.

The machinery below stays because it is correct and hard-won (span-preserving
splits, transitions kept on the LAST piece, five-way verification) — the
mistake was using it uninvited, not how it worked.

Original brief it was built for, same day: new voice lines replace the old ones at
the right spots, as a straight swap that disturbs nothing else. Everything
here is designed so that not one existing element moves — captions, call-outs,
intro, outro and the outro's music all stay exactly where he put them.

Two operations, both time-preserving:

  mute   <tag> <from> <to>          silence a stretch of an existing audio
                                    segment by splitting it and setting the
                                    middle piece to volume 0 (reversible — the
                                    audio is still there, just turned down)
  place  <tag> <at> <file>          drop a new voice file in at an exact time,
                                    on its own track, over whatever is beneath

A split keeps the three pieces butt-joined across exactly the original span, so
the timeline length and every later segment are untouched.

Follows the house safety pattern (sa_outro.py, sa_introfull.py): refuse while
CapCut is open, back up first, write, then re-read from disk and verify that
every pre-existing segment still starts where it did — restore the backup if not.

    sa_voiceswap.py mute MOD03 33.95 36.73
    sa_voiceswap.py place MOD02 49.67 /path/to/line.mp3 --apply
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
from sa_transcript import VIDEOS, DRAFTS                     # noqa: E402
from sa_outro import draft_path, US                          # noqa: E402


def capcut_running():
    return bool(subprocess.run(["pgrep", "-x", "CapCut"], capture_output=True).stdout.strip())


def probe(p):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", str(p)], capture_output=True, text=True).stdout.strip()
    return float(out) if out else 0.0


def draft_for(tag):
    entry = VIDEOS[tag]
    tl = entry[2] if len(entry) > 2 else None
    return (DRAFTS / entry[0] / "Timelines" / tl / "draft_info.json") if tl else draft_path(entry[0])


def snapshot(d):
    """(id, start, duration) for every segment — the thing that must not change."""
    return sorted((s["id"], s["target_timerange"]["start"], s["target_timerange"]["duration"])
                  for t in d["tracks"] for s in (t.get("segments") or []))


def split_and_mute(d, a_us, b_us):
    """Silence timeline [a,b) inside whichever audio segments cover it. -> list of notes."""
    notes = []
    # A transition material duplicated onto every piece of a split would fire three times.
    trans = {m["id"] for m in ((d.get("materials") or {}).get("transitions") or [])}
    for t in d["tracks"]:
        # Narration often lives on the PICTURE track (one module's whole voice-over is inside
        # its T<nn>_PACED.mp4 on a video track). Splitting a video segment into butt-joined
        # pieces of the same source is exactly what CapCut's own Split does — the picture
        # plays through seamlessly — so it is safe, and it is the only way to mute a
        # stretch of embedded narration.
        if t.get("type") not in ("audio", "video"):
            continue
        out = []
        for s in (t.get("segments") or []):
            g = s["target_timerange"]
            s0, s1 = g["start"], g["start"] + g["duration"]
            if s1 <= a_us or s0 >= b_us or s.get("volume", 1.0) <= 0.15:
                out.append(s)
                continue
            src0 = (s.get("source_timerange") or {}).get("start", 0)
            speed = s.get("speed", 1.0) or 1.0

            def piece(t_from, t_to, vol):
                q = copy.deepcopy(s)
                q["id"] = str(uuid.uuid4()).upper()
                q["target_timerange"] = {"start": int(t_from), "duration": int(t_to - t_from)}
                if q.get("source_timerange") is not None:
                    q["source_timerange"] = {"start": int(src0 + (t_from - s0) * speed),
                                             "duration": int((t_to - t_from) * speed)}
                q["volume"] = vol
                # A transition attaches to a segment's END in CapCut (the Slow Fade into
                # the outro rides the last content segment). So after a split it must stay
                # on the LAST piece — leaving it on the first would fire the fade mid-video.
                # One module's 19.80-269.67s segment was exactly this case.
                if t_to < s1:
                    q["extra_material_refs"] = [r for r in (q.get("extra_material_refs") or [])
                                                if r not in trans]
                return q

            lo, hi = max(s0, a_us), min(s1, b_us)
            if s0 < lo:
                out.append(piece(s0, lo, s.get("volume", 1.0)))
            out.append(piece(lo, hi, 0.0))
            if hi < s1:
                out.append(piece(hi, s1, s.get("volume", 1.0)))
            notes.append(f"{s0/US:.2f}-{s1/US:.2f} -> muted {lo/US:.2f}-{hi/US:.2f}")
        t["segments"] = out
    return notes


def place(d, at_us, audio_path, donor_hint=None):
    """Add a voice file on its own audio track at an exact time."""
    auds = d["materials"].setdefault("audios", [])
    donor = None
    for m in auds:
        if m.get("type") in ("extract_music", "music", None) and m.get("path"):
            donor = m
            if donor_hint and donor_hint in m.get("path", ""):
                break
    mat = copy.deepcopy(donor) if donor else {"type": "extract_music"}
    mat["id"] = str(uuid.uuid4()).upper()
    mat["path"] = str(audio_path)
    mat["name"] = pathlib.Path(audio_path).name
    dur = int(probe(audio_path) * US)
    mat["duration"] = dur
    auds.append(mat)

    donor_seg = None
    for t in d["tracks"]:
        if t.get("type") == "audio" and (t.get("segments") or []):
            donor_seg = t["segments"][0]
            break
    seg = copy.deepcopy(donor_seg) if donor_seg else {}
    seg["id"] = str(uuid.uuid4()).upper()
    seg["material_id"] = mat["id"]
    seg["target_timerange"] = {"start": int(at_us), "duration": dur}
    seg["source_timerange"] = {"start": 0, "duration": dur}
    seg["volume"] = 1.0
    seg["speed"] = 1.0
    seg["extra_material_refs"] = []
    d["tracks"].append({"type": "audio", "segments": [seg], "id": str(uuid.uuid4()).upper(),
                        "attribute": 0, "flag": 0})
    return dur / US


def run(tag, op, a, b_or_file, do_it):
    dp = draft_for(tag)
    before = json.loads(dp.read_text())
    d = copy.deepcopy(before)
    protected = {i for i, _s, _u in snapshot(before)}

    if op == "mute":
        notes = split_and_mute(d, int(float(a) * US), int(float(b_or_file) * US))
        if not notes:
            return f"{tag}: nothing to mute between {a}s and {b_or_file}s"
        print(f"  {tag}  " + " | ".join(notes))
    else:
        secs = place(d, int(float(a) * US), pathlib.Path(b_or_file))
        print(f"  {tag}  placed {pathlib.Path(b_or_file).name} at {float(a):.2f}s ({secs:.2f}s)")

    # every segment that existed before must still start and last exactly the same,
    # unless it was one we deliberately split
    after = {i: (s, u) for i, s, u in snapshot(d)}
    moved = [i for i, s, u in snapshot(before) if i in after and after[i] != (s, u)]
    if moved:
        return f"{tag}: REFUSING — {len(moved)} existing segment(s) would move"
    lost = [i for i in protected if i not in after]
    if op == "place" and lost:
        return f"{tag}: REFUSING — placing must not remove segments"

    end_b = max(s + u for _i, s, u in snapshot(before))
    end_a = max(s + u for _i, s, u in snapshot(d))
    if abs(end_a - end_b) > 1000:
        return f"{tag}: REFUSING — timeline length would change ({end_b/US:.2f} -> {end_a/US:.2f})"

    if not do_it:
        return "dry run ok — nothing written"
    if capcut_running():
        return "REFUSED: CapCut is open"
    bak = dp.with_suffix(".json.pre_voice")
    if not bak.exists():
        shutil.copy2(dp, bak)
    dp.write_text(json.dumps(d, ensure_ascii=False))
    disk = json.loads(dp.read_text())
    after2 = {i: (s, u) for i, s, u in snapshot(disk)}
    if [i for i, s, u in snapshot(before) if i in after2 and after2[i] != (s, u)]:
        shutil.copy2(bak, dp)
        return f"{tag}: POST-WRITE VERIFY FAILED — backup restored"
    return "written"


def demo():
    """Split arithmetic must preserve the span exactly."""
    d = {"tracks": [{"type": "audio", "segments": [{
        "id": "X", "target_timerange": {"start": 0, "duration": 10 * US},
        "source_timerange": {"start": 0, "duration": 10 * US}, "volume": 1.0}]}]}
    split_and_mute(d, 3 * US, 5 * US)
    segs = d["tracks"][0]["segments"]
    assert len(segs) == 3, segs
    spans = [(s["target_timerange"]["start"], s["target_timerange"]["duration"]) for s in segs]
    assert spans[0] == (0, 3 * US) and spans[1] == (3 * US, 2 * US) and spans[2] == (5 * US, 5 * US)
    assert segs[1]["volume"] == 0.0 and segs[0]["volume"] == 1.0
    assert sum(u for _s, u in spans) == 10 * US, "the three pieces must fill the original span"
    # source offsets must follow the timeline cuts
    assert segs[2]["source_timerange"]["start"] == 5 * US
    print("demo ok — split preserves the span, middle muted, sources aligned")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("op", nargs="?", choices=["mute", "place"])
    ap.add_argument("tag", nargs="?")
    ap.add_argument("a", nargs="?")
    ap.add_argument("b", nargs="?")
    ap.add_argument("--apply", action="store_true")
    if "--demo" in sys.argv:
        demo()
        sys.exit()
    args = ap.parse_args()
    print(run(args.tag, args.op, args.a, args.b, args.apply))
