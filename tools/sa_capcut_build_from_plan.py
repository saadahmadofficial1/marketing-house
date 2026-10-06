#!/usr/bin/env python3
"""Build a NEW CapCut review draft for one module of a brand tutorial series (3D style B).

The CapCut hand-off of the HyperFrames brand-tutorial template: the rendered picture, the
voice-over and the captions land in an editable CapCut timeline for the editor's review.
Driven by each module's <m>_edit_plan.json (vo_placement, captions.cues, music) and
<m>_timing.json (scenes, used for the M3 music restart).

Tracks, in order:
  Picture (silent render) / End frame (swap for the brand outro) / Voice-over (one detached
  clip per line at its vo_placement start) / Music (the plan's music bed, vol 0.03; M3 restarts
  the bed at the nearest scene boundary so it runs to the end) / Captions (plan cues ->
  SRT -> sa_capcut_captions: Poppins Regular 5, y -0.892, 75%, no background).

Safety: CapCut closed before EVERY write (re-checked each time,
stops if it opens); the target name must be free; backup manifest of the whole projects
folder (listing + mtimes/sizes of every project's draft files + donor sha256) and a copy
of the donor's JSON; donor read-only and hash-verified after; no existing project touched;
both draft_info copies byte-equal; donor draft_agency_info.json list cleared.

  python3 sa_capcut_build_from_plan.py m2            # build + 13 checks
  python3 sa_capcut_build_from_plan.py m2 --verify   # re-run the 13 checks

All media is referenced from SA_TUTORIAL_MEDIA (default ~/Movies/Brand_Tutorials/, a stable
folder), never the build folder; the music path comes from the edit plan (keep a backup copy
of the bed next to the module's media).
"""
import copy
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import sa_capcut_callouts as cc      # noqa: E402
import sa_capcut_captions as cap     # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
ROOT = pathlib.Path(os.environ.get("SA_TUTORIAL_MEDIA", "~/Movies/Brand_Tutorials")).expanduser()
US = 1_000_000

MODULES = {
    "m1": dict(name="Acme M1 - Welcome (3D v2)", folder="M1",
               picture="M1/final_B/m1_B_picture_silent.mp4",
               end_frame="M1/final_B/m1_B_end_frame.mp4", vo="M1/vo",
               picture_s=141.9, total_s=148.2, music_restart_near_s=None),
    "m2": dict(name="Acme M2 - Our Identity (3D v1)", folder="M2",
               picture="M2/final_B/m2_B_picture_silent.mp4",
               end_frame="M2/final_B/m2_B_end_frame.mp4", vo="M2/final_B/vo",
               picture_s=165.2, total_s=171.5, music_restart_near_s=None),
    "m3": dict(name="Acme M3 - Everyday Use (3D v1)", folder="M3",
               picture="M3/final_B/m3_B_picture_silent.mp4",
               end_frame="M3/final_B/m3_B_end_frame.mp4", vo="M3/final_B/vo",
               picture_s=242.2, total_s=248.5,
               # bed is 215s: restart it at the "final layer" orbit scene (~2:23)
               music_restart_near_s=143.0, music_restart_scene="layer"),
    "m4": dict(name="Acme M4 - Scenarios (3D v1)", folder="M4",
               picture="M4/final_B/m4_B_picture_silent.mp4",
               end_frame="M4/final_B/m4_B_end_frame.mp4", vo="M4/final_B/vo",
               picture_s=288.2, total_s=294.5,
               # bed is 215s: restart it where scenario 4 begins (134.3s)
               music_restart_near_s=134.3, music_restart_scene="s4"),
    "m5": dict(name="Acme M5 - Recap (3D v1)", folder="M5",
               picture="M5/final_B/m5_B_picture_silent.mp4",
               end_frame="M5/final_B/m5_B_end_frame.mp4", vo="M5/final_B/vo",
               picture_s=178.533, total_s=184.82, music_restart_near_s=None),
}
SIBLING_NAMES = {c["name"] for c in MODULES.values()}

if len(sys.argv) < 2 or sys.argv[1] not in MODULES:
    raise SystemExit(f"usage: sa_capcut_build_from_plan.py <{'|'.join(MODULES)}> [--verify]")
MOD = sys.argv[1]
CFG = MODULES[MOD]
PLAN = json.loads((HERE / f"{MOD}_edit_plan.json").read_text(encoding="utf-8"))
TIMING = json.loads((HERE / f"{MOD}_timing.json").read_text(encoding="utf-8"))
LINES_TXT = HERE / "vo" / f"{MOD}_lines.txt"
NAME = CFG["name"]
CANVAS = PLAN["capcut_review_draft"]["canvas"]

PICTURE = ROOT / CFG["picture"]
END_FRAME = ROOT / CFG["end_frame"]
VO_DIR = ROOT / CFG["vo"]
MUSIC = pathlib.Path(os.path.expanduser(PLAN["music"]["file"]))
MUSIC_VOL = float(PLAN["music"]["volume"])
CUES = PLAN["captions"]["cues"]

TAG = re.sub(r"[^a-z0-9]+", "_", NAME[NAME.rfind("(") + 1:].strip(")").lower()).strip("_")
WORK = PICTURE.parent / f"capcut_{TAG}"          # e.g. M3/final_B/capcut_3d_v1
SRT = WORK / f"{MOD}.srt"
SCAFFOLD = WORK / "scaffold_manifest.json"
BACKUP_MANIFEST = WORK / "capcut_backup_manifest.json"

DRAFTS = cc.CAPCUT
DONOR = cc.DONOR                             # resolved by glob inside the tool
cap.DONOR = DONOR
TARGET = DRAFTS / NAME


def guard(what=""):
    """Re-checked before EVERY write: if CapCut opens, stop at once."""
    if cc.capcut_open():
        raise SystemExit(f"STOPPED: CapCut is open{' (before ' + what + ')' if what else ''}. "
                         f"Nothing further written.")


def wtext(path, text):
    guard(f"write {pathlib.Path(path).name}")
    pathlib.Path(path).write_text(text, encoding="utf-8")


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


_DUR = {}


def ffdur(p):
    p = str(p)
    if p not in _DUR:
        out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                              "-of", "csv=p=0", p], capture_output=True, text=True).stdout
        _DUR[p] = float(out.strip())
    return _DUR[p]


def us(t):
    return int(round(t * US))


def vo_files():
    return [(p, VO_DIR / pathlib.Path(p["file"]).name) for p in PLAN["vo_placement"]]


def words(s):
    s = s.replace("’", "'").replace("‘", "'").replace("—", " ").replace("–", " ")
    return re.findall(r"[a-z0-9&']+", s.lower())


def music_plan(total_us):
    """-> [(timeline_start_us, source_start_us, duration_us)], back to back, 0 -> total."""
    near = CFG.get("music_restart_near_s")
    if near is None:
        return [(0, 0, total_us)], None
    starts = sorted(v[0] for k, v in TIMING["scenes"].items() if v[0] > 0)
    t = min(starts, key=lambda s: abs(s - near))
    scene = next(k for k, v in TIMING["scenes"].items() if v[0] == t)
    t_us = us(t)
    return [(0, 0, t_us), (t_us, 0, total_us - t_us)], (scene, t)


# ---------------------------------------------------------------- snapshot / backup
def donor_files():
    root = DRAFTS / DONOR
    files = [root / "draft_info.json", root / "draft_meta_info.json",
             root / "Timelines" / "project.json"]
    files += sorted((root / "Timelines").glob("*/draft_info.json"))
    return [f for f in files if f.exists()]


def snapshot():
    """ls of the drafts folder + mtime/size of every project's draft files + donor hashes."""
    projects = {}
    for p in sorted(DRAFTS.iterdir()):
        if not p.is_dir():
            continue
        files = {}
        for f in [p / "draft_info.json", p / "draft_meta_info.json",
                  p / "Timelines" / "project.json"] + sorted(p.glob("Timelines/*/draft_info.json")):
            if f.exists():
                st = f.stat()
                files[str(f.relative_to(p))] = [st.st_mtime_ns, st.st_size]
        projects[p.name] = files
    return {"taken": time.strftime("%Y-%m-%d %H:%M:%S"), "module": MOD, "target": NAME,
            "drafts_root": str(DRAFTS), "listing": sorted(os.listdir(DRAFTS)),
            "projects": projects, "donor": DONOR,
            "donor_sha256": {str(f.relative_to(DRAFTS / DONOR)): sha(f) for f in donor_files()}}


# ---------------------------------------------------------------- preflight
def preflight():
    guard("preflight")
    if TARGET.exists():
        raise SystemExit(f"REFUSED: project already exists: {TARGET}")
    if not (DRAFTS / DONOR / "Timelines").exists():
        raise SystemExit(f"donor not found: {DRAFTS / DONOR}")
    media = [PICTURE, END_FRAME, MUSIC] + [f for _, f in vo_files()]
    missing = [str(f) for f in media if not f.exists()]
    if missing:
        raise SystemExit("missing media: " + ", ".join(missing))
    bad = [str(f) for f in media if f != MUSIC and not str(f).startswith(str(ROOT) + "/")]
    if bad:
        raise SystemExit(f"media outside {ROOT}: " + ", ".join(bad))
    lines = [l for l in LINES_TXT.read_text(encoding="utf-8").splitlines() if l.strip()]
    on_disk = sorted(p.name for p in VO_DIR.glob("*.mp3"))
    planned = [f.name for _, f in vo_files()]
    assert len(planned) == len(lines) == len(on_disk), (len(planned), len(lines), len(on_disk))
    assert planned == on_disk, "plan VO files differ from the VO folder"
    assert len(CUES) == int(PLAN["captions"]["count"]), "caption count mismatch"
    assert words(" ".join(c["text"] for c in CUES)) == words(" ".join(lines)), \
        "caption words are not the script words"
    assert [round(p["start"], 3) for p, _ in vo_files()] == \
        [round(s, 3) for s in TIMING["vo_starts"]], "plan and timing VO starts differ"
    pic, end = ffdur(PICTURE), ffdur(END_FRAME)
    assert abs(pic - CFG["picture_s"]) < 0.05, f"picture is {pic}s, expected {CFG['picture_s']}"
    assert abs(end - 6.3) < 0.05, f"end frame is {end}s"
    assert abs(pic + end - CFG["total_s"]) < 0.05, f"total {pic + end} vs {CFG['total_s']}"
    prev = -1.0
    for p, f in vo_files():
        assert p["start"] >= prev - 1e-6, f"VO overlap at line {p['line']}"
        prev = p["start"] + ffdur(f)
    assert prev <= pic, f"last VO ends {prev}s, after the picture ({pic}s)"
    for c in CUES:
        assert len(c["text"]) <= 46 and "\n" not in c["text"], c["text"]
    for a, b in zip(CUES, CUES[1:]):
        assert b["start"] >= a["end"] - 1e-9 and a["end"] - a["start"] >= 0.3, (a, b)
    segs, _ = music_plan(us(pic + end))
    for _, _, d in segs:
        assert d <= us(ffdur(MUSIC)), "music segment longer than the bed"


# ---------------------------------------------------------------- srt
def write_srt():
    def stamp(t):
        ms = int(round(t * 1000))
        h, ms = divmod(ms, 3_600_000)
        m, ms = divmod(ms, 60_000)
        s, ms = divmod(ms, 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
    blocks = [f"{i}\n{stamp(c['start'])} --> {stamp(c['end'])}\n{c['text']}\n"
              for i, c in enumerate(CUES, 1)]
    wtext(SRT, "\n".join(blocks))


# ---------------------------------------------------------------- build
def audio_shape():
    donor = cc.donor_draft()
    auds = {m["id"]: m for m in donor["materials"].get("audios", [])}
    for tr in donor["tracks"]:
        for s in tr.get("segments", []):
            if tr.get("type") == "audio" and s.get("material_id") in auds:
                return copy.deepcopy(auds[s["material_id"]]), copy.deepcopy(s)
    raise SystemExit("donor has no audio shape to clone")


def audio_clip(am, sg, path, mat_dur_us, start_us, clip_us, vol, src_start_us=0):
    m = copy.deepcopy(am)
    m.update({"id": cc.new_id(), "path": str(path), "name": path.name,
              "duration": mat_dur_us, "music_id": "", "text_id": "",
              "tone_type": "", "local_material_id": "", "wave_points": []})
    s = copy.deepcopy(sg)
    s.update({"id": cc.new_id(), "material_id": m["id"],
              "source_timerange": {"start": src_start_us, "duration": clip_us},
              "target_timerange": {"start": start_us, "duration": clip_us},
              "speed": 1.0, "volume": vol, "last_nonzero_volume": vol, "visible": True,
              "extra_material_refs": [], "keyframe_refs": [], "common_keyframes": [],
              "group_id": "", "template_id": "", "raw_segment_id": ""})
    return m, s


def referenced_ids(d):
    ids = set()
    for t in d["tracks"]:
        for s in t.get("segments", []):
            ids.add(s["material_id"])
            ids.update(s.get("extra_material_refs") or [])
    return ids


def clean_agency(target):
    """draft_agency_info.json is CapCut's proxy-converter list — the donor's holds its own
    source paths (screen clips, freeze PNGs, outros). None are in this project."""
    f = target / "draft_agency_info.json"
    if f.exists():
        a = json.loads(f.read_text(encoding="utf-8"))
        a["marterial"] = []                    # CapCut's own spelling
        wtext(f, json.dumps(a, ensure_ascii=False))


def post_process(target):
    tls = list((target / "Timelines").glob("*/draft_info.json"))
    assert len(tls) == 1, tls
    tl = tls[0]
    d = json.loads(tl.read_text(encoding="utf-8"))
    media = [(PICTURE, "video"), (END_FRAME, "video")] + \
            [(f, "music") for _, f in vo_files()] + [(MUSIC, "music")]
    pool_id = {str(f): cc.new_id().lower() for f, _ in media}

    # picture + end frame: exact ffprobe µs, end frame at the picture's real end
    pic_us, end_us = us(ffdur(PICTURE)), us(ffdur(END_FRAME))
    total_us = pic_us + end_us
    mats = {m["id"]: m for m in d["materials"]["videos"]}
    for t in d["tracks"]:
        for s in t["segments"]:
            s["keyframe_refs"] = []
            s["common_keyframes"] = []
            m = mats.get(s["material_id"])
            if t["type"] != "video" or not m:
                continue
            if m["path"] == str(PICTURE):
                m["duration"] = pic_us
                s["source_timerange"] = {"start": 0, "duration": pic_us}
                s["target_timerange"] = {"start": 0, "duration": pic_us}
            elif m["path"] == str(END_FRAME):
                m["type"] = "video"                     # callouts writes "photo"
                m["duration"] = end_us
                s["source_timerange"] = {"start": 0, "duration": end_us}
                s["target_timerange"] = {"start": pic_us, "duration": end_us}
    d["tracks"][0]["name"] = "Picture"
    d["tracks"][0]["is_default_name"] = False

    # voice-over: one detached clip per line at the planned start, real durations
    am, sg = audio_shape()
    d["materials"]["audios"] = []
    vo = []
    for p, f in vo_files():
        dur = us(ffdur(f))
        m, s = audio_clip(am, sg, f, dur, us(p["start"]), dur, 1.0)
        d["materials"]["audios"].append(m)
        vo.append(s)
    d["tracks"].append({"id": cc.new_id(), "type": "audio", "attribute": 0, "flag": 0,
                        "is_default_name": False, "name": "Voice-over", "segments": vo})

    # music: source 0, vol 0.03, back-to-back segments to the end (M3: restart)
    mu = []
    for start, src, dur in music_plan(total_us)[0]:
        m, s = audio_clip(am, sg, MUSIC, us(ffdur(MUSIC)), start, dur, MUSIC_VOL, src)
        d["materials"]["audios"].append(m)
        mu.append(s)
    d["tracks"].append({"id": cc.new_id(), "type": "audio", "attribute": 0, "flag": 0,
                        "is_default_name": False, "name": "Music", "segments": mu})

    # drop every donor material no segment references (transitions, canvases, keyframes…)
    keep = referenced_ids(d)
    for k, v in list(d["materials"].items()):
        if isinstance(v, list):
            d["materials"][k] = [x for x in v if not isinstance(x, dict) or x.get("id") in keep]
    if isinstance(d.get("keyframes"), dict):
        for k, v in d["keyframes"].items():
            if isinstance(v, list):
                d["keyframes"][k] = []

    end = max(s["target_timerange"]["start"] + s["target_timerange"]["duration"]
              for t in d["tracks"] for s in t["segments"])
    assert end == total_us, (end, total_us)
    d["duration"] = total_us
    d["fps"] = 30.0
    d.setdefault("config", {})["export_range"] = {"start": 0, "duration": total_us}

    for g in ("videos", "audios"):              # link timeline materials to our pool rows
        for m in d["materials"][g]:
            m["local_material_id"] = pool_id[m["path"]]

    blob = json.dumps(d, ensure_ascii=False)
    wtext(tl, blob)
    wtext(target / "draft_info.json", blob)

    tl_dir = tl.parent
    tid = tl_dir.name

    # donor sidecars that carry its identity or content
    for f in list(tl_dir.glob("draft_info.json.*")) + [tl_dir / "template-2.tmp",
                                                         tl_dir / "template.json",
                                                         tl_dir / "draft_cover.jpg"]:
        if f.exists():
            guard(f"remove {f.name}")
            f.unlink()
    for f in list(target.glob("*.prelink")) + list(target.glob("crypto_key_store.dat.bak")):
        guard(f"remove {f.name}")
        f.unlink()
    for sub in (target / "subdraft").glob("*"):
        if sub.is_dir():
            guard("remove subdraft")
            shutil.rmtree(sub)
    for f in (target / "Resources" / "combination").glob("*"):
        guard("remove combination audio")
        f.unlink()
    clean_agency(target)
    wtext(target / "timeline_layout.json", json.dumps(
        {"dockItems": [{"dockIndex": 0, "ratio": 1, "timelineIds": [tid],
                        "timelineNames": ["Timeline 01"]}], "layoutOrientation": 1}))
    pj = target / "Timelines" / "project.json"
    p = json.loads(pj.read_text(encoding="utf-8"))
    p["timelines"][0]["name"] = "Timeline 01"
    wtext(pj, json.dumps(p, ensure_ascii=False))

    # media pool: our files only
    now_us = int(time.time() * US)
    for meta_path in (target / "draft_meta_info.json", tl_dir / "draft_meta_info.json"):
        if not meta_path.exists():
            continue
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        rows = [r for g in meta["draft_materials"] for r in g["value"]]
        vt = copy.deepcopy(next(r for r in rows if r.get("metetype") == "video"))
        mt = copy.deepcopy(next(r for r in rows if r.get("metetype") == "music"))
        pool = []
        for f, kind in media:
            r = copy.deepcopy(vt if kind == "video" else mt)
            dur = us(ffdur(f))
            w, h = cc.probe(f)[1:] if kind == "video" else (0, 0)
            r.update({"id": pool_id[str(f)], "file_Path": str(f), "extra_info": f.name,
                      "duration": dur, "width": w, "height": h, "metetype": kind, "type": 0,
                      "create_time": -1, "import_time": -1, "import_time_ms": -1,
                      "item_source": 1, "md5": "",
                      "roughcut_time_range": {"start": 0, "duration": dur},
                      "sub_time_range": {"start": -1, "duration": -1}})
            pool.append(r)
        for g in meta["draft_materials"]:
            g["value"] = pool if g["type"] == 0 else []
        meta["draft_segment_extra_info"] = []
        meta["draft_materials_copied_info"] = []
        meta["tm_duration"] = total_us
        meta["tm_draft_modified"] = now_us
        meta["draft_timeline_materials_size_"] = sum(
            pathlib.Path(r["file_Path"]).stat().st_size for r in pool)
        meta["draft_root_path"] = str(DRAFTS)
        meta["draft_fold_path"] = str(target)
        meta["draft_name"] = NAME
        wtext(meta_path, json.dumps(meta, ensure_ascii=False))
    return tl


# ---------------------------------------------------------------- verify
def donor_ids():
    """Every uuid-looking id in the donor's timelines/meta — to prove none leaked."""
    ids = set()
    root = DRAFTS / DONOR
    for f in donor_files():
        d = json.loads(f.read_text(encoding="utf-8"))
        stack = [d]
        while stack:
            x = stack.pop()
            if isinstance(x, dict):
                for k, v in x.items():
                    if k in ("id", "draft_id", "main_timeline_id", "material_id") and \
                            isinstance(v, str) and len(v) == 36:
                        ids.add(v.upper())
                    stack.append(v)
            elif isinstance(x, list):
                stack.extend(x)
    ids.update(p.name.upper() for p in (root / "Timelines").glob("*") if p.is_dir())
    return ids


def verify(snap, built_now):
    R = []

    def check(label, ok, detail=""):
        R.append((label, bool(ok), detail))

    t = TARGET
    pic_us, end_us = us(ffdur(PICTURE)), us(ffdur(END_FRAME))
    total_us = pic_us + end_us
    root_blob = (t / "draft_info.json").read_bytes()
    tls = [p for p in (t / "Timelines").glob("*") if p.is_dir()]
    tl_blob = (tls[0] / "draft_info.json").read_bytes() if len(tls) == 1 else b""
    check("both draft_info copies byte-equal", root_blob == tl_blob and len(tls) == 1,
          f"{len(root_blob)} bytes, {len(tls)} timeline folder(s)")
    d = json.loads(root_blob)
    pj = json.loads((t / "Timelines" / "project.json").read_text(encoding="utf-8"))
    lay = json.loads((t / "timeline_layout.json").read_text(encoding="utf-8"))
    ids = {d["id"], tls[0].name, pj["main_timeline_id"],
           *[x["id"] for x in pj["timelines"]], *lay["dockItems"][0]["timelineIds"]}
    check("one timeline id matches (draft_info/folder/project.json/layout)",
          len(ids) == 1 and len(pj["timelines"]) == 1,
          next(iter(ids)) if len(ids) == 1 else str(ids))

    meta = json.loads((t / "draft_meta_info.json").read_text(encoding="utf-8"))
    dmeta = json.loads((DRAFTS / DONOR / "draft_meta_info.json").read_text(encoding="utf-8"))
    check("draft_id fresh, draft_name = folder",
          meta["draft_id"] != dmeta["draft_id"] and meta["draft_name"] == t.name)

    paths = [m["path"] for g in ("videos", "audios") for m in d["materials"][g]]
    paths += [r["file_Path"] for g in meta["draft_materials"] for r in g["value"]]
    fonts = [m.get("font_path") for m in d["materials"]["texts"]]
    miss = [p for p in paths + fonts if not os.path.exists(p)]
    check("every media path exists", not miss and paths,
          f"{len(paths)} media refs + {len(fonts)} font refs"
          + (f"; missing {miss[:3]}" if miss else ""))

    overl = []
    for tr in d["tracks"]:
        segs = sorted((s["target_timerange"]["start"],
                       s["target_timerange"]["start"] + s["target_timerange"]["duration"])
                      for s in tr["segments"])
        for (a0, a1), (b0, b1) in zip(segs, segs[1:]):
            if b0 < a1:
                overl.append((tr.get("name"), a1 / US, b0 / US))
    check("no overlaps per track", not overl,
          f"{len(d['tracks'])} tracks: " + ", ".join(f"{tr.get('name')}={len(tr['segments'])}"
                                                      for tr in d["tracks"]))

    end = max(s["target_timerange"]["start"] + s["target_timerange"]["duration"]
              for tr in d["tracks"] for s in tr["segments"])
    check(f"header duration = picture+end frame ({total_us / US:.3f}s) = content end = export_range",
          d["duration"] == total_us and end == total_us
          and d.get("config", {}).get("export_range", {}).get("duration") == total_us
          and meta.get("tm_duration") == total_us, f"{d['duration'] / US:.3f}s")

    auds = {m["id"]: m for m in d["materials"]["audios"]}
    vo_tr = [tr for tr in d["tracks"] if tr["type"] == "audio" and tr.get("name") == "Voice-over"]
    n_vo = len(vo_files())
    bad = []
    if len(vo_tr) == 1 and len(vo_tr[0]["segments"]) == n_vo:
        segs = sorted(vo_tr[0]["segments"], key=lambda s: s["target_timerange"]["start"])
        for (p, f), s in zip(vo_files(), segs):
            real = ffdur(f)
            st = s["target_timerange"]["start"] / US
            m = auds[s["material_id"]]
            if abs(st - p["start"]) > 0.01 or m["path"] != str(f) or \
                    abs(s["target_timerange"]["duration"] / US - real) > 0.001 or \
                    abs(m["duration"] / US - real) > 0.001 or s["volume"] != 1.0 or \
                    m["type"] != "extract_music" or s["source_timerange"]["start"] != 0:
                bad.append(p["line"])
    else:
        bad.append("track/segment count")
    vp = PLAN["vo_placement"]
    check(f"{n_vo} VO segments at planned starts ±0.01s, real ffprobe durations", not bad,
          f"bad={bad}" if bad else
          f"{vp[0]['line']:02d} {vp[0]['start']:.2f}s … {vp[-1]['line']:02d} {vp[-1]['start']:.2f}s, vol 1.0")

    expect, restart = music_plan(total_us)
    mu = [tr for tr in d["tracks"] if tr["type"] == "audio" and tr.get("name") == "Music"]
    ok = len(mu) == 1 and len(mu[0]["segments"]) == len(expect)
    if ok:
        segs = sorted(mu[0]["segments"], key=lambda s: s["target_timerange"]["start"])
        for s, (start, src, dur) in zip(segs, expect):
            ok = ok and (abs(s["volume"] - MUSIC_VOL) < 1e-9
                         and s["target_timerange"] == {"start": start, "duration": dur}
                         and s["source_timerange"] == {"start": src, "duration": dur}
                         and auds[s["material_id"]]["path"] == str(MUSIC)
                         and dur <= auds[s["material_id"]]["duration"])
    rs = (f"; restarts at {restart[1]:.2f}s (scene '{restart[0]}')" if restart else "")
    if restart and restart[0] != CFG.get("music_restart_scene"):
        ok = False
        rs += f" — expected scene '{CFG.get('music_restart_scene')}'"
    check(f"music vol {MUSIC_VOL}, source 0, 0→{total_us / US:.3f}s in {len(expect)} segment(s)",
          ok, MUSIC.name + rs)

    texts = {m["id"]: m for m in d["materials"]["texts"]}
    cap_tr = [tr for tr in d["tracks"] if tr["type"] == "text"]
    C = cap.CAPTION
    cbad = []
    n = 0
    for tr in cap_tr:
        for s in tr["segments"]:
            n += 1
            m = texts[s["material_id"]]
            c = json.loads(m["content"])
            txt = c["text"]
            if len(txt) > 46 or "\n" in txt or m["font_size"] != 5.0 or \
                    abs(s["clip"]["transform"]["y"] + 0.892) > 1e-6 or \
                    abs(s["clip"]["transform"]["x"]) > 1e-6 or \
                    abs(s["clip"]["scale"]["x"] - 0.75) > 1e-6 or \
                    "Poppins-Regular" not in m["font_path"] or \
                    m.get("background_style", 0) != 0 or m.get("background_color", "") != "" or \
                    abs(m.get("shadow_alpha", 0) - C["shadow_alpha"]) > 1e-6 or \
                    abs(m.get("shadow_smoothing", 0) - C["shadow_smoothing"]) > 1e-6 or \
                    abs(m.get("shadow_distance", 0) - C["shadow_distance"]) > 1e-6 or \
                    abs(m.get("shadow_angle", 0) - C["shadow_angle"]) > 1e-6 or \
                    len(c["styles"]) != 1 or s["render_index"] < 20000:
                cbad.append(txt)
    got = [(s["target_timerange"]["start"], json.loads(texts[s["material_id"]]["content"])["text"])
           for tr in cap_tr for s in sorted(tr["segments"], key=lambda s: s["target_timerange"]["start"])]
    want = [(us(c["start"]), c["text"]) for c in CUES]
    timed = len(got) == len(want) and all(g[1] == w[1] and abs(g[0] - w[0]) <= 2000
                                          for g, w in zip(got, want))   # SRT is ms-precise
    script = [l for l in LINES_TXT.read_text(encoding="utf-8").splitlines() if l.strip()]
    same_words = words(" ".join(x[1] for x in got)) == words(" ".join(script))
    check(f"{len(CUES)} captions = script words, ≤46 chars, one line, Poppins Regular 5 / "
          f"y −0.892 / 75% / shadow 50-15-5-−45, no bg",
          n == len(CUES) and not cbad and timed and same_words and len(cap_tr) == 1,
          f"{n} cues, max {max(len(x[1]) for x in got) if got else 0} chars, "
          f"words match {LINES_TXT.name}: {same_words}" + (f"; bad {cbad[:2]}" if cbad else ""))

    ef = [m for m in d["materials"]["videos"] if m["path"] == str(END_FRAME)]
    efs = [s for tr in d["tracks"] for s in tr["segments"] if ef and s["material_id"] == ef[0]["id"]]
    check(f"end-frame material type 'video' at the picture's real end ({pic_us / US:.3f}s)",
          len(ef) == 1 and ef[0]["type"] == "video" and len(efs) == 1 and
          efs[0]["target_timerange"] == {"start": pic_us, "duration": end_us}, "")

    ours = {str(PICTURE), str(END_FRAME), str(MUSIC)} | {str(f) for _, f in vo_files()}
    leaks = []
    for f in t.rglob("*.json"):
        txt = f.read_text(encoding="utf-8", errors="ignore")
        for frag in ("training-series", "Downloads/", "Training_Series", "sdr709", "subdraft/",
                     "/Cache/effect/", "/.claude/worktrees/"):
            if frag in txt:
                leaks.append(f"{f.relative_to(t)}:{frag}")
    leaks += [p for p in set(paths) if p not in ours]
    leaks += [p for p in set(paths) if p != str(MUSIC) and not p.startswith(str(ROOT) + "/")]
    did = donor_ids()
    blob_up = "\n".join(f.read_text(encoding="utf-8", errors="ignore") for f in
                        [t / "draft_info.json", t / "draft_meta_info.json",
                         t / "Timelines" / "project.json", t / "timeline_layout.json"]).upper()
    uuid_hits = [i for i in did if i in blob_up]
    check("no donor-only media or donor ids left referenced; media from ~/Movies only",
          not leaks and not uuid_hits,
          f"leaks={leaks[:4]} donor_ids={uuid_hits[:4]}" if (leaks or uuid_hits) else
          f"{len(did)} donor ids checked, 0 hits; media refs = our {len(ours)} files only")

    now = {str(f.relative_to(DRAFTS / DONOR)): sha(f) for f in donor_files()}
    check("donor untouched (sha256)", now == snap["donor_sha256"],
          f"{len(now)} donor files hashed")

    after = snapshot()
    changed = [p for p, files in snap["projects"].items() if after["projects"].get(p) != files]
    new = sorted(set(after["listing"]) - set(snap["listing"]))
    gone = sorted(set(snap["listing"]) - set(after["listing"]))
    # right after a build: the only new entry is this draft. On a later --verify, sibling
    # module drafts built since by this script are allowed too (they are new, not changed).
    ok_new = (new == [NAME]) if built_now else (NAME in new and set(new) <= SIBLING_NAMES)
    check("no other project changed; only new entry is this one" +
          ("" if built_now else " (+ sibling module drafts)"),
          not changed and ok_new and not gone, f"changed={changed} new={new} gone={gone}")
    return R


def main():
    built_now = "--verify" not in sys.argv
    if not built_now:
        snap = json.loads(BACKUP_MANIFEST.read_text(encoding="utf-8"))
    else:
        preflight()
        guard("backup")
        WORK.mkdir(parents=True, exist_ok=True)
        snap = snapshot()
        wtext(BACKUP_MANIFEST, json.dumps(snap, indent=1, ensure_ascii=False))
        bdir = WORK / f"_donor_backup_{time.strftime('%Y%m%d_%H%M%S')}"
        for f in donor_files():
            dst = bdir / f.relative_to(DRAFTS / DONOR)
            dst.parent.mkdir(parents=True, exist_ok=True)
            guard("donor backup copy")
            shutil.copy2(f, dst)
        print(f"backup manifest -> {BACKUP_MANIFEST}\ndonor JSON copy -> {bdir}")

        write_srt()
        manifest = {"canvas": CANVAS, "video": str(PICTURE),
                    "layers": [{"file": str(END_FRAME), "start": ffdur(PICTURE),
                                "duration": round(ffdur(END_FRAME), 3),
                                "label": "End frame (swap for the brand outro)"}]}
        wtext(SCAFFOLD, json.dumps(manifest, indent=1))
        guard("scaffold")
        target = cc.write(SCAFFOLD, NAME)
        assert target == TARGET
        post_process(target)
        guard("captions")
        cap.apply(NAME, str(SRT))

    results = verify(snap, built_now)
    width = max(len(r[0]) for r in results)
    for label, ok, detail in results:
        print(f"{'PASS' if ok else 'FAIL'}  {label.ljust(width)}  {detail}")
    failed = [r for r in results if not r[1]]
    print(f"\n{len(results) - len(failed)}/{len(results)} passed -> {TARGET}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
