"""A separate CapCut copy of a mobile video whose app picture is recoloured teal -> the desktop app's navy
(sa_hue_remap_lut.py). The original project is only read. (Requirement, 25 Sep: experiment on a copy of an
approved module, never on the original.)

    sa_capcut_colour_copy.py "<project>" <tag> [suffix]   -> "<project> - <suffix>" (default COLOUR TEST; e.g.
                                                             BLUE for a roll-out copy)
    sa_capcut_colour_copy.py --externalise-stills "<project>" <tag>
    sa_capcut_colour_copy.py --fix-freezes "<project>" <tag>
    SA_MOBILE_DIR = the series working folder (LAYERS/<tag>/...)

Copy gets its own identity (draft_id, timeline id, project.json - the sa_capcut_callouts recipe: a copy that
keeps the donor's ids makes both claim one project). Every reference to the app picture - the app video (also
inside his compound clip), his freeze frames (made self-contained: absolute paths into the copy, recoloured
there), the intro phone PNG - points at a recoloured file. Everything else (background, glow, mockup, markings,
captions, voice, music, outro) is untouched.
"""
import json, os, pathlib, re, shutil, subprocess, sys, time, uuid
S = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(S))
import sa_hue_remap_lut as TN                                               # noqa: E402

CAP = pathlib.Path.home() / "Movies/CapCut/User Data/Projects/com.lveditor.draft"
D = pathlib.Path(os.path.expanduser(os.environ.get("SA_MOBILE_DIR", "~/Downloads/training-series/mobile_app")))


def nid():
    return str(uuid.uuid4()).upper()


def _frames(video, t0, n):
    import numpy as np
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t0:.4f}", "-i", str(video), "-frames:v", str(n), "-vf",
                          "scale=in_color_matrix=bt709:in_range=full:out_range=full,format=rgb24", "-f", "rawvideo", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, 1920, 1080, 3)


def sync_side_files(P):
    """Keep CapCut's side copies in step with draft_info.json (review 27 Sep): template.json mirrors, each compound's
    own subdraft file (its nested draft), and timeline_layout.json naming the project's own timeline."""
    P = pathlib.Path(P)
    blob = (P / "draft_info.json").read_text(); d = json.loads(blob)
    tl = json.loads((P / "Timelines" / "project.json").read_text()).get("main_timeline_id", "")
    for f in [P / "Timelines" / tl / "draft_info.json", P / "template.json", P / "Timelines" / tl / "template.json"]:
        if f.exists():
            f.write_text(blob)
    for x in d["materials"].get("drafts", []):
        f = pathlib.Path(x.get("draft_file_path") or "")
        if x.get("draft") and f.exists() and str(f).startswith(str(P)):
            j = json.loads(f.read_text())
            for y in j.get("materials", {}).get("drafts", []):
                if y.get("id") == x["id"]:
                    y["draft"] = x["draft"]
            f.write_text(json.dumps(j, ensure_ascii=False))
    lay = P / "timeline_layout.json"
    if lay.exists() and tl:
        j = json.loads(lay.read_text())
        for it in j.get("dockItems", []):
            if "timelineIds" in it:
                it["timelineIds"] = [tl]
            if "timelineNames" in it:
                it["timelineNames"] = [json.loads((P / "draft_meta_info.json").read_text()).get("draft_name", P.name)]
        lay.write_text(json.dumps(j, ensure_ascii=False))


def still_at(name):
    """The app second a still shows: his CapCut freeze (<md5>_<microseconds>...) or our hold_<s>.png (add_marks.frozen_at)."""
    m = re.match(r"[0-9a-f]{32}_(\d+)", name)
    if m:
        return int(m.group(1)) / 1e6
    m = re.match(r"hold_(\d+\.\d+)(_\d+)?\.png$", name)
    return float(m.group(1)) if m else None


def recut(pairs, ref_png, out_png, tol=2.5):
    """A still of the app (his freeze, our hold_) re-cut from the recoloured video at the same frame, so a patch or
    hold made from it is pixel-identical to the video around it. Recolouring the PNG on its own left the top-notch
    patch 2-3 levels off the video (25 Sep: the colours did not merge). pairs = [(teal video, navy video)]; the
    frame is found by matching the PNG against the teal video around its second. None if no video has that frame."""
    import numpy as np
    from PIL import Image
    t = still_at(pathlib.Path(ref_png).name)
    if t is None:
        return None
    ref = Image.open(ref_png); a = np.asarray(ref.convert("RGBA"))
    best = None
    for teal, navy in pairs:
        ft = _frames(teal, max(0.0, t - 2 / 30), 5)
        if not len(ft):
            continue
        d = [np.abs(f.astype(int) - a[..., :3]).mean() for f in ft]
        i = int(np.argmin(d))
        if best is None or d[i] < best[0]:
            best = (d[i], i, teal, navy)
    if best is None or best[0] > tol:          # wrong frame reads 4+; same frame, other colour maths ~0.1-2
        return None
    f = _frames(best[3], max(0.0, t - 2 / 30), 5)[best[1]]
    Image.fromarray(np.dstack([f, a[..., 3]]) if ref.mode == "RGBA" else f).save(out_png)
    return best[2]


def freeze_from_video(teal, navy, ref_png, out_png):
    return recut([(teal, navy)], ref_png, out_png) is not None


def externalise_stills(project, tag):
    """Move a copy's CapCut freeze stills (<hash>_<us>...sdr709.png, kept in the project folder) out to
    LAYERS/<tag>/COLOUR_TEST/freezes/ and point every reference at that absolute path.
    Why (26 Sep, a module's top notch still teal in CapCut): CapCut stores in-project files as
    ##_draftpath_placeholder_<id>_##/<name> with the ORIGINAL project's id, and on opening the copy it loaded the
    ORIGINAL folder's teal still of the same name (its media list then named the original folder). Outside any
    project folder, with an absolute path, there is nothing for it to resolve."""
    import shutil
    if subprocess.run(["pgrep", "-x", "CapCut"], capture_output=True).returncode == 0:
        raise SystemExit("CapCut is open - close it first")
    P = CAP / project
    T = D / "LAYERS" / tag / "COLOUR_TEST" / "freezes"; T.mkdir(parents=True, exist_ok=True)
    roots = [P / "draft_info.json"] + sorted(P.glob("Timelines/*/draft_info.json"))
    if len({f.read_bytes() for f in roots}) != 1:
        raise SystemExit("draft copies differ - open and close the project in CapCut once, then retry")
    files = roots + sorted(P.glob("subdraft/*/draft_content.json"))
    names = sorted(f.name for f in P.glob("*sdr709.png"))
    bk = D / "_backup_capcut" / f"{project}_before_external_stills_{time.strftime('%H%M%S')}"
    for f in files:
        b = bk / f.relative_to(P); b.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(f, b)
    n = 0
    for f in files:
        t = f.read_text()
        for nm in names:
            shutil.copy2(P / nm, T / nm)
            t, k = re.subn(r'"[^"]*/' + re.escape(nm) + '"', json.dumps(str(T / nm)), t); n += k
        json.loads(t)
        f.write_text(t)
    assert len({f.read_bytes() for f in roots}) == 1
    left = sum(len(re.findall(r'"[^"]*/[^"/]*sdr709\.png"', f.read_text())) - f.read_text().count(str(T) + "/") for f in files)
    sync_side_files(P)
    print(f"-> {project}: {len(names)} stills moved to {T.relative_to(D)}, {n} references repointed; in-project references left {left}")


def fix_freezes(project, tag):
    """Repair an existing COLOUR TEST copy: freezes re-cut from the navy video; colour sliders someone left on a
    freeze patch (only there - the app video under it has none) removed, as in the original project."""
    if subprocess.run(["pgrep", "-x", "CapCut"], capture_output=True).returncode == 0:
        raise SystemExit("CapCut is open - close it first")
    P, src = CAP / project, CAP / project.replace(" - COLOUR TEST", "")
    app, app_n = D / "LAYERS" / tag / f"L4_app_{tag}.mp4", D / "LAYERS" / tag / "COLOUR_TEST" / f"L4_app_{tag}_NAVY.mp4"
    copies = [P / "draft_info.json"] + sorted(P.glob("Timelines/*/draft_info.json"))
    blobs = {f.read_text() for f in copies}
    if len(blobs) != 1:
        raise SystemExit("draft copies differ - open and close the project in CapCut once, then retry")
    shutil.copytree(P, D / "_backup_capcut" / f"{project}_before_freezefix_{time.strftime('%H%M%S')}")
    for f in sorted(P.glob("*-sdr*.png")):
        ok = freeze_from_video(app, app_n, src / f.name, f)
        print(f"   {f.name}: {'re-cut from the navy video' if ok else 'NOT a frame of the app video - left as is'}")
    d = json.loads(blobs.pop()); dropped, gone = 0, set()

    def walk(dd):
        nonlocal dropped
        mats = {m["id"]: (k, m) for k, v in dd["materials"].items() if isinstance(v, list) for m in v if isinstance(m, dict) and "id" in m}
        for t in dd["tracks"]:
            for s in t["segments"]:
                if "-sdr" not in mats.get(s["material_id"], ("", {}))[1].get("path", ""):
                    continue
                h = [r for r in s.get("extra_material_refs", []) if mats.get(r, ("",))[0] == "hsl"]
                if any(mats[r][1].get(x) for r in h for x in ("hue", "saturation", "lightness")):
                    s["extra_material_refs"] = [r for r in s["extra_material_refs"] if r not in h]
                    s["enable_hsl"] = False; dropped += 1; gone.update(h)
        if gone and "hsl" in dd["materials"]:
            dd["materials"]["hsl"] = [m for m in dd["materials"]["hsl"] if m["id"] not in gone]
        for cd in dd["materials"].get("drafts", []):
            if cd.get("draft"):
                walk(cd["draft"])
    walk(d)
    blob = json.dumps(d, ensure_ascii=False)
    for f in copies:
        f.write_text(blob)
    assert len({f.read_bytes() for f in copies}) == 1
    print(f"-> {project}: freeze frames re-cut; colour sliders removed from {dropped} freeze patch segment(s)")


APP_PIC = re.compile(r"L4_(app|still)_.*\.mp4$")


def main(project, tag, suffix="COLOUR TEST"):
    if subprocess.run(["pgrep", "-x", "CapCut"], capture_output=True).returncode == 0:
        raise SystemExit("CapCut is open - close it first")
    src, name = CAP / project, f"{project} - {suffix}"
    dst = CAP / name
    if dst.exists():
        raise SystemExit(f"already exists: {dst}")
    roots = [src / "draft_info.json"] + sorted(src.glob("Timelines/*/draft_info.json"))
    if len({f.read_bytes() for f in roots}) != 1:
        raise SystemExit("draft copies differ - open and close the project in CapCut once, then retry")
    T = D / "LAYERS" / tag / "COLOUR_TEST"; T.mkdir(parents=True, exist_ok=True)
    lut = T / "app_teal_to_navy.cube"
    if not lut.exists():
        TN.write_lut(lut)
    paths = set(re.findall(r'"path":\s*"([^"]+)"', roots[0].read_text()))
    swap, pairs = {}, []
    # every video of the app picture (L4_app / L4_still, also his own copies elsewhere) -> its own navy copy
    for v in sorted(p for p in paths if APP_PIC.search(pathlib.Path(p).name) and pathlib.Path(p).exists()):
        vp = pathlib.Path(v)
        extra = "" if vp.parent == D / "LAYERS" / tag else "_" + vp.parent.parent.name
        out = T / f"{vp.stem}{extra}_NAVY.mp4"
        if not out.exists():
            TN.video(v, out, lut)
        swap[v] = str(out); pairs.append((v, out))
    for ph in sorted(p for p in paths if re.match(r"INTRO_.*_phone\.png$", pathlib.Path(p).name) and pathlib.Path(p).exists()):
        ph_n = T / f"{pathlib.Path(ph).stem}_NAVY.png"
        if not ph_n.exists():
            TN.png(ph, ph_n)
        swap[ph] = str(ph_n)
    # our hold_ stills of the app (add_marks) live outside the project: navy copies, re-cut like his freezes
    stats = {"re-cut": 0, "recoloured": 0}
    for h in sorted(p for p in paths if re.match(r"hold_.*\.png$", pathlib.Path(p).name) and pathlib.Path(p).exists()):
        out = T / "holds" / pathlib.Path(h).name; out.parent.mkdir(exist_ok=True)
        if recut(pairs, h, out):
            stats["re-cut"] += 1
        else:
            TN.png(h, out); stats["recoloured"] += 1
        swap[h] = str(out)

    shutil.copytree(src, dst)
    for junk in ("draft_info.json.bak", "template-2.tmp"):
        (dst / junk).unlink(missing_ok=True)
    # his freeze frames live in the project folder behind a placeholder: make them the copy's own, re-cut from the
    # navy video (recolouring the PNG itself leaves a patch a few levels off the video around it)
    for f in dst.glob("*-sdr*.png"):
        if recut(pairs, f, f):
            stats["re-cut"] += 1
        else:
            TN.png(f, f); stats["recoloured"] += 1
    main_id = json.loads((dst / "Timelines" / "project.json").read_text()).get("main_timeline_id", "")
    old_tl = dst / "Timelines" / main_id
    if not main_id or not old_tl.is_dir():
        old_tl = next(p for p in (dst / "Timelines").iterdir() if p.is_dir() and (p / "draft_info.json").read_bytes() == roots[0].read_bytes())
    tl_id, draft_id = nid(), nid()
    old_tl.rename(dst / "Timelines" / tl_id)
    for extra in (dst / "Timelines").iterdir():
        if extra.is_dir() and extra.name != tl_id:
            shutil.rmtree(extra)

    blob = (dst / "Timelines" / tl_id / "draft_info.json").read_text()
    d = json.loads(blob)
    n_swaps = 0

    def fix(o):
        nonlocal n_swaps
        if isinstance(o, dict):
            for k, v in list(o.items()):
                if isinstance(v, str):
                    if v in swap:
                        o[k] = swap[v]; n_swaps += 1
                    elif v.startswith("##_draftpath_placeholder_"):
                        o[k] = str(dst / v.split("_##/", 1)[1]); n_swaps += 1
                    elif v.startswith(str(src) + "/"):             # absolute paths into the source project (review 27 Sep)
                        o[k] = str(dst) + v[len(str(src)):]; n_swaps += 1
                else:
                    fix(v)
        elif isinstance(o, list):
            for v in o:
                fix(v)
    fix(d["materials"])
    d["id"] = tl_id
    out = json.dumps(d, ensure_ascii=False)
    for f in (dst / "draft_info.json", dst / "Timelines" / tl_id / "draft_info.json"):
        f.write_text(out)
    now = int(time.time() * 1_000_000)
    for meta in (dst / "draft_meta_info.json", dst / "Timelines" / tl_id / "draft_meta_info.json"):
        if meta.exists():
            m = json.loads(meta.read_text())
            m.update(draft_id=draft_id, draft_name=name, draft_fold_path=str(dst))
            m.pop("draft_timeline_materials_size_", None)
            for k in ("tm_draft_create", "tm_draft_modified"):
                if k in m:
                    m[k] = now
            meta.write_text(json.dumps(m, ensure_ascii=False))
    pj = dst / "Timelines" / "project.json"
    if pj.exists():
        p = json.loads(pj.read_text())
        p.update(id=nid(), main_timeline_id=tl_id, create_time=now, update_time=now,
                 timelines=[{"create_time": now, "id": tl_id, "is_marked_delete": False, "name": name, "update_time": now}])
        pj.write_text(json.dumps(p, ensure_ascii=False))
    (dst / "Timelines" / "project.json.bak").unlink(missing_ok=True)
    sync_side_files(dst)

    # verify: both read paths agree, every file there, nothing still pointing at the un-recoloured app
    copies = [dst / "draft_info.json", dst / "Timelines" / tl_id / "draft_info.json"]
    assert len({f.read_bytes() for f in copies}) == 1
    paths = re.findall(r'"path":\s*"([^"]+)"', out)
    missing = [p for p in paths if p and not p.startswith("##") and "/" in p and not pathlib.Path(p).exists()]
    old = [p for p in paths if p in swap or "placeholder" in p]
    print(f"-> {name}: {n_swaps} picture references swapped to navy ({len(pairs)} app videos; stills {stats}); "
          f"missing files {len(missing)}; left on teal {len(old)}")
    if missing:
        print("   missing:", missing[:5])


if __name__ == "__main__":
    if sys.argv[1] == "--externalise-stills":
        externalise_stills(sys.argv[2], sys.argv[3])
    elif sys.argv[1] == "--fix-freezes":
        fix_freezes(sys.argv[2], sys.argv[3])
    else:
        main(*sys.argv[1:4])
