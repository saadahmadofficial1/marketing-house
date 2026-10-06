#!/usr/bin/env python3
"""Measure every video in the series against the most recently finished edit.

Saad asked for a detailed check of every video against his latest edit. That edit is
the reference because it is the one he finished LAST — it carries his current style:

    head        content starts at 5.23s (room for the intro), title text over it
    captions    size 5, y -0.89, uniform
    voice       1.00-1.07, his boost never passes 1.1
    sign-off    "Thank you for watching" audio laid OVER the outro
    outro       butted to the picture end: in 4.07s, 9.10s, muted, scale 1.082
    music       none

Read-only. Emits `5 ADMIN/final_check_data.json` — one record per video with
MEASUREMENTS, not verdicts. Judgement (does a hole matter? is a deviant caption
his deliberate choice?) belongs to the reviewer reading the record.

    Tools/venv/bin/python3 Tools/sa_videocheck.py            # every mapped video
    Tools/venv/bin/python3 Tools/sa_videocheck.py MOD01      # one
    Tools/venv/bin/python3 Tools/sa_videocheck.py --demo     # self-check
"""
import glob
import json
import os
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from sa_import import PROJECT, DRAFTS          # tag -> CapCut project folder
from sa_outro import draft_path, US, SOURCE_IN, OUTRO_LEN, OUTRO_VOL, OUTRO_SCALE

SERIES = pathlib.Path(os.environ.get("TRAINING_ROOT", "~/Downloads/training-series")).expanduser()
BUILD = SERIES / "2 BUILD"
ADMIN = SERIES / "5 ADMIN"


def build_folder(tag):
    """MOD01 -> the '2 BUILD/T01 ...' folder, if the build has one."""
    t = "T" + tag[3:]
    hits = [f for f in glob.glob(str(BUILD / f"{t} *")) + glob.glob(str(BUILD / t))
            if pathlib.Path(f).is_dir()]
    return pathlib.Path(hits[0]) if hits else None


def union(spans):
    """Merge [(a,b)] -> coverage; pure."""
    out = []
    for a, b in sorted(spans):
        if out and a <= out[-1][1] + 1e-9:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return out


def holes(spans, start, end):
    """Uncovered stretches of (start,end) given merged coverage; pure."""
    got, cur = [], start
    for a, b in spans:
        if a > cur + 0.05:
            got.append((round(cur, 2), round(min(a, end), 2)))
        cur = max(cur, b)
        if cur >= end:
            break
    if cur < end - 0.05:
        got.append((round(cur, 2), round(end, 2)))
    return [(a, b) for a, b in got if b > a]


def texts_of(d):
    """-> [(t, dur, text, size, y)] for every text segment."""
    mats = {m["id"]: m for m in (d["materials"].get("texts") or [])}
    out = []
    for tr in d["tracks"]:
        for s in tr.get("segments") or []:
            m = mats.get(s.get("material_id"))
            if not m:
                continue
            try:
                c = json.loads(m.get("content", "{}"))
            except Exception:
                c = {}
            size = 0
            for st in (c.get("styles") or []):
                size = st.get("size", size)
            txt = "".join(re.findall(r'"text":\s*"([^"]*)"', m.get("content", "")))[:80]
            g = s["target_timerange"]
            y = round((s.get("clip", {}).get("transform", {}) or {}).get("y", 0), 2)
            out.append((round(g["start"] / US, 2), round(g["duration"] / US, 2),
                        txt, round(size or 0), y))
    return sorted(out)


def check(tag):
    project = PROJECT[tag]
    dp = draft_path(project)
    d = json.loads(dp.read_text())
    vids = {m["id"]: m for m in d["materials"]["videos"]}
    auds = {m["id"]: m for m in (d["materials"].get("audios") or [])}
    name = lambda mid, pool: pathlib.Path((pool.get(mid) or {}).get("path", "")).name

    # --- picture: every mp4/mov segment that is not the outro ---
    pic, outro_seg, intro_on_tl = [], None, False
    for tr in d["tracks"]:
        if tr.get("type") != "video":
            continue
        for s in tr.get("segments") or []:
            n = name(s.get("material_id"), vids)
            if not n.lower().endswith((".mp4", ".mov")):
                continue
            if "OUTRO" in n.upper():
                outro_seg = s
                continue
            if n.upper().startswith("INTRO_"):
                intro_on_tl = True
            g = s["target_timerange"]
            pic.append((g["start"] / US, (g["start"] + g["duration"]) / US))
    cov = union(pic)
    head = round(cov[0][0], 2) if cov else None
    pic_end = round(max(b for _a, b in cov), 2) if cov else None

    # --- outro placement vs the donor constants ---
    outro = {"present": False}
    if outro_seg is not None:
        g, src = outro_seg["target_timerange"], outro_seg.get("source_timerange", {})
        sc = (outro_seg.get("clip", {}).get("scale", {}) or {}).get("x", 1.0)
        outro = {
            "present": True,
            "start": round(g["start"] / US, 2),
            "end": round((g["start"] + g["duration"]) / US, 2),
            "gap_to_picture": round(g["start"] / US - pic_end, 2) if pic_end else None,
            "source_in_ok": abs(src.get("start", 0) - SOURCE_IN) < 0.05 * US,
            "length_ok": abs(g["duration"] - OUTRO_LEN) < 0.05 * US,
            "muted_ok": abs(outro_seg.get("volume", 1.0) - OUTRO_VOL) < 1e-3,
            "scale_ok": abs(sc - OUTRO_SCALE) < 0.01,
        }

    # --- audio: sign-off, beds, volume outliers, spill past the outro ---
    signoff, beds, vol_odd, spill = None, [], [], []
    outro_end = outro.get("end")
    for tr in d["tracks"]:
        if tr.get("type") != "audio":
            continue
        for s in tr.get("segments") or []:
            n = name(s.get("material_id"), auds) or (auds.get(s.get("material_id")) or {}).get("name", "")
            g = s["target_timerange"]
            a, b = g["start"] / US, (g["start"] + g["duration"]) / US
            v = s.get("volume", 1.0)
            if "SIGNOFF" in n.upper():
                signoff = {"start": round(a, 2), "end": round(b, 2), "vol": round(v, 3)}
            elif v < 0.15:
                beds.append({"file": n[:40], "start": round(a, 2), "end": round(b, 2), "vol": round(v, 4)})
            elif not (0.9 <= v <= 1.1):
                vol_odd.append({"file": n[:40], "t": round(a, 2), "vol": round(v, 3)})
            if outro_end and b > outro_end + 1.6 and "SIGNOFF" not in n.upper():
                spill.append({"file": n[:40], "ends": round(b, 2)})

    # --- text: style vs the reference edit (size 5 @ y -0.89), banners, title head ---
    tx = texts_of(d)
    small = [x for x in tx if x[3] and x[3] < 10]
    deviants = [x for x in small if not (x[3] == 5 and abs(x[4] + 0.89) < 0.06)]
    banners = [name(s.get("material_id"), vids)
               for tr in d["tracks"] if tr.get("type") == "video"
               for s in tr.get("segments") or []
               if re.search(r"role|banner", name(s.get("material_id"), vids), re.I)]

    # --- script coverage (build-side arithmetic, if this video has a build) ---
    coverage = None
    bf = build_folder(tag)
    if bf:
        try:
            from sa_coverage import analyse
            r = analyse(str(bf))
            if r:
                coverage = {"steps": r["segments"], "callouts": r["callouts"],
                            "unmarked": [{"n": u["n"], "t": round(u["start"], 1),
                                          "text": u["text"][:90], "verbs": u["verbs"]}
                                         for u in r["unmarked"]],
                            "recut_by_s": round(r["recut_by"], 1) if r.get("recut_by") else None}
        except Exception as e:
            coverage = {"error": str(e)[:120]}

    # --- media pool: intro + line sat ready to drag ---
    meta = json.loads((DRAFTS / project / "draft_meta_info.json").read_text())
    pool = {i.get("extra_info", "") for g in meta["draft_materials"]
            if g.get("type") == 0 for i in g["value"]}

    return {
        "tag": tag, "project": project, "draft": str(dp),
        "build_folder": str(bf) if bf else None,
        "head_s": head, "picture_end_s": pic_end,
        "intro_on_timeline": intro_on_tl,
        "intro_in_pool": any(n.startswith(f"INTRO_{tag}_") for n in pool),
        "line_in_pool": f"LINE_{tag}_FINAL.mp3" in pool,
        "title_text_at_head": [x for x in tx if head and x[0] < head + 0.5 and x[3] >= 10][:4],
        "holes": holes(cov, cov[0][0], pic_end) if cov else [],
        "outro": outro, "signoff": signoff,
        "music_beds": beds, "volume_outliers": vol_odd[:12], "audio_past_outro": spill,
        "captions": {"count": len(small),
                     "deviants_from_size5_y-0.89": [{"t": x[0], "text": x[2][:60],
                                                     "size": x[3], "y": x[4]} for x in deviants[:15]],
                     "deviant_count": len(deviants)},
        "banner_segments": banners,
        "coverage": coverage,
        "all_text": [{"t": x[0], "dur": x[1], "text": x[2], "size": x[3]} for x in tx],
    }


def main(only=None):
    out = []
    for tag in PROJECT:
        if only and only != tag:
            continue
        r = check(tag)
        out.append(r)
        c = r["coverage"] or {}
        print(f"  {tag:<7} head {r['head_s']:>6} end {r['picture_end_s']:>7} "
              f"holes {len(r['holes'])} outro {'yes' if r['outro']['present'] else 'NO '} "
              f"signoff {'yes' if r['signoff'] else 'no '} "
              f"capdev {r['captions']['deviant_count']:>3} "
              f"banners {len(r['banner_segments']):>2} "
              f"unmarked {len(c.get('unmarked', [])) if isinstance(c, dict) else '?'}")
    ADMIN.mkdir(parents=True, exist_ok=True)
    (ADMIN / "final_check_data.json").write_text(json.dumps(out, indent=1))
    print(f"\n-> {ADMIN / 'final_check_data.json'}  ({len(out)} videos)")


def demo():
    assert union([(0, 5), (4, 9), (12, 14)]) == [(0, 9), (12, 14)]
    assert holes([(0, 9), (12, 14)], 0, 14) == [(9, 12)]
    assert holes([(5.23, 100)], 5.23, 100) == [], "a head gap is not a hole"
    assert holes([(0, 50), (50.02, 100)], 0, 100) == [], "0.02s butt joins are not holes"
    assert holes([(0, 50), (53, 100)], 0, 100) == [(50, 53)]
    print("demo ok (union + holes)")


if __name__ == "__main__":
    argv = [a for a in sys.argv[1:] if not a.startswith("--")]
    sys.exit(demo() if "--demo" in sys.argv else main(argv[0] if argv else None))
