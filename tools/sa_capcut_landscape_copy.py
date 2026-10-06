"""16:9 landscape copy of an approved 9:16 mobile training video, for desktop / laptop viewing (requirement,
26 Sep: an approved sketch with the phone in the middle, captions on the right, the step list on the left, a progress bar).

    sa_capcut_landscape_copy.py "<blue 9:16 project>" <tag> [--dry]      -> "<project> - 16x9"

Layout on 1920x1080 (the reel is never touched; the copy gets its own identity):
  centre  every 9:16 picture layer (compound with app/stills/glow/mockup, iPhone back/front, markings, headings,
          intro phone). CapCut fits a 1080x1920 layer to the canvas height before clip.scale, so these shrink
          together by 0.5625 and stay aligned; only their x offsets need rescaling (FX).
  back    the navy background, scaled to cover the full width.
  outro   the series outro (file name contains OUTRO_TAG) is already 1920x1080: full frame, its reel mask removed.
  right   captions, centred in the right panel, wrapping inside it.
  left    the intro title during the intro; afterwards the role label, "Step n of N" and a 5-line step list
          (current step white, neighbours dim) from the visible marking headings, words taken from the build's
          marks json (checked against every drawn heading by OCR, 26 Sep: 53/53); a mark whose heading Saad hid but
          whose box shows still counts, from the box.
  bottom  a thin progress bar that fills one step at a time.
Text sizes: CapCut draws text at ~4.4 px of em per (style size x clip scale) on a 1080-wide canvas and in
proportion to canvas WIDTH (measured on a reel export, 26 Sep: 4.28 / 4.43 / 4.44; Saad's 75 % desktop vs
137 % reel captions only both look right under a width rule), so on 1920 wide it is 4.4 x 1920/1080 per unit.
Refuses while CapCut is open.
"""
import copy, hashlib, json, pathlib, re, shutil, subprocess, sys, time
import numpy as np
from PIL import Image, ImageDraw, ImageFont
S = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(S))
from sa_capcut_colour_copy import CAP, D, nid                                  # noqa: E402

W, H = 1920, 1080
OUTRO_TAG = "SERIES OUTRO"                # file-name marker of the series' own 16:9 outro clip
SERIES_LABEL = "TRAINING SERIES"         # shown after the role on the left panel
FX = (540 * 1080 / 1920) / 960            # a 9:16 layer's x offset after the fit, in 16:9 half-widths
UNIT = 4.4 * W / 1080                     # px of em per (size x scale) on this canvas
FONTS = pathlib.Path.home() / "Library/Containers/com.lemon.lvoverseas/Data/Library/Fonts"
X0 = 150                                  # left panel: left edge of the list
LEFT_MAX = 540                            # widest the left text may run (phone body starts ~720)
RIGHT_C, RIGHT_W = 1560, 560              # right panel: centre and wrap width of the captions
PHONE_K = 1.17                            # v2 (requirement 26 Sep: a slightly bigger phone): phone group scale
PHONE_R = 480                             # v2 intro: phone centre this many px right of centre while the title shows
MOVE = (2_900_000, 3_833_333)             # v3 intro: the move to the middle, lands before the live phone (3.87 s)
MOVE_STEPS = 14                           # v3: smoothstep ease drawn with linear keys - his FreeCurve (0.63,0)-(1,1)
                                          # accelerates into a dead stop, which read as a shake on the wide move
TITLE_END = 3_300_000                     # v3: the title's fade-out is done before the phone reaches its lines
TITLE_X0 = 140                            # v2 intro title: left edge; lines (text, em, py, colour)
TITLE = {1: (26, 350, [143 / 255, 160 / 255, 1.0]), 2: (64, 432, [1.0, 1.0, 1.0]), 3: (112, 548, [1.0, 1.0, 1.0]), 4: (80, 668, None)}
GLOW_RGB, GLOW_A, GLOW_SX, GLOW_SY = (90, 112, 254), 0.40, 517, 411   # v3 wide glow (v2 at 0.246 read as "no glow")
HALO_A, HALO_S, HALO_R = 0.30, 70, 60     # v3 halo hugging the phone, as the reel's masked glow does
GLOW_OVER = 2                             # glow placed at scale 2 over a canvas-sized PNG: no edge ever on screen,
                                          # and a quarter of the pixels of a 2x PNG (a soft glow needs no detail)
PHONE_CY = 523                            # the visible phone's centre: middle of the space above the progress bar

NAVY_DIM, LIGHT = [0.42, 0.455, 0.588], [143 / 255, 160 / 255, 1.0]
ROWS = {"prev2": 408, "prev1": 458, "cur": 526, "next1": 594, "next2": 644}   # list rows (py), current in the middle


def tx(px):
    return (px - W / 2) / (W / 2)


def ty(py):
    return (H / 2 - py) / (H / 2)


def em_width(text, weight, em):
    return ImageFont.truetype(str(FONTS / f"Poppins-{weight}.ttf"), 200).getlength(text) / 200 * em


def clone(src, name):
    """A self-contained copy with its own identity (the sa_capcut_colour_copy recipe)."""
    s, dst = CAP / src, CAP / name
    if dst.exists():
        raise SystemExit(f"already exists: {dst}")
    roots = [s / "draft_info.json"] + sorted(s.glob("Timelines/*/draft_info.json"))
    if len({f.read_bytes() for f in roots}) != 1:
        raise SystemExit("draft copies differ - open and close the project in CapCut once, then retry")
    shutil.copytree(s, dst)
    for junk in ("draft_info.json.bak", "template-2.tmp"):
        (dst / junk).unlink(missing_ok=True)
    main_id = json.loads((dst / "Timelines" / "project.json").read_text()).get("main_timeline_id", "")
    old_tl = dst / "Timelines" / main_id
    tl_id, draft_id = nid(), nid()
    old_tl.rename(dst / "Timelines" / tl_id)
    for extra in (dst / "Timelines").iterdir():
        if extra.is_dir() and extra.name != tl_id:
            shutil.rmtree(extra)
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
    p = json.loads(pj.read_text())
    p.update(id=nid(), main_timeline_id=tl_id, create_time=now, update_time=now,
             timelines=[{"create_time": now, "id": tl_id, "is_marked_delete": False, "name": name, "update_time": now}])
    pj.write_text(json.dumps(p, ensure_ascii=False))
    (dst / "Timelines" / "project.json.bak").unlink(missing_ok=True)
    # no stale 9:16 state left for crash recovery / fallback to bring back (review 26 Sep)
    for f in [*(dst / "Timelines" / tl_id).glob("*.bak"), *(dst / "Timelines" / tl_id).glob("*.tmp"),
              dst / "Timelines" / tl_id / "attachment" / "patch" / "mini_draft.json"]:
        f.unlink(missing_ok=True)
    pf = dst / "Timelines" / tl_id / "attachment" / "patch" / "patch.json"
    if pf.exists():
        pf.write_text('{"patch_data":[]}\n')
    lay = dst / "timeline_layout.json"
    if lay.exists():
        t = lay.read_text().replace(main_id, tl_id)
        lay.write_text(re.sub(r'("timelineNames"\s*:\s*\[)[^\]]*\]', lambda m_: m_.group(1) + json.dumps(name) + "]", t))
    return dst, tl_id


def overlay(path, draw):
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); draw(ImageDraw.Draw(im)); im.save(path)


def main(project, tag, dry=False, suffix="16x9"):
    if not dry and subprocess.run(["pgrep", "-x", "CapCut"], capture_output=True).returncode == 0:
        raise SystemExit("CapCut is open - close it first")
    src_d = json.loads((CAP / project / "draft_info.json").read_text())
    marks = json.load(open(S / f"{tag}_marks.json"))["marks"]
    role = tag.split("_", 1)[1]
    role = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", role).replace("and", " and ").replace("  ", " ").strip()

    # --- the step list, from the visible heading segments of the approved timeline
    M = {m["id"]: m for v in src_d["materials"].values() if isinstance(v, list) for m in v if isinstance(m, dict) and "id" in m}
    seen = {}                                   # mark stem -> {"label": [starts], "box": [starts]}
    for t in src_d["tracks"]:
        for s in t["segments"]:
            p = M.get(s["material_id"], {}).get("path") or ""
            m_ = re.search(r"(mark_\w+?)_(label|box)\.png$", p)
            if m_ and s.get("visible", True):
                seen.setdefault(m_.group(1), {"label": [], "box": []})[m_.group(2)].append(s["target_timerange"]["start"])
    steps = []
    for stem, v in seen.items():
        n = re.match(r"mark_(\d+)$", stem)
        words = marks[int(n.group(1)) - 1]["heading"] if n else stem.split("_", 2)[-1].replace("_", " ").capitalize()
        steps.append((min(v["label"] or v["box"]), words))
    steps.sort()
    voice = [s for t in src_d["tracks"] if t.get("name") == "Voice over" for s in t["segments"]]
    list_end = max(s["target_timerange"]["start"] + s["target_timerange"]["duration"] for s in voice)
    first = min(s["target_timerange"]["start"] for s in voice)
    N = len(steps)

    # --- sizes: fit every left-panel line inside LEFT_MAX
    def fit(text, weight, em):
        w = em_width(text, weight, em)
        return (em * LEFT_MAX / w, LEFT_MAX) if w > LEFT_MAX else (em, w)
    report = {"steps": N, "longest_step": max(steps, key=lambda s: len(s[1]))[1] if steps else "", "shrunk": []}
    for _, h in steps:
        e, _w = fit(h, "SemiBold", 40)
        if e < 40:
            report["shrunk"].append((h, round(e, 1)))
    if dry:
        print(json.dumps(report, indent=1)); return

    name = f"{project} - {suffix}"
    dst, tl_id = clone(project, name)
    L = D / "LAYERS" / tag / "LANDSCAPE" / re.sub(r"[^A-Za-z0-9]+", "_", suffix); L.mkdir(parents=True, exist_ok=True)
    d = json.loads((dst / "draft_info.json").read_text())
    d["id"] = tl_id
    d["canvas_config"].update(width=W, height=H, ratio="16:9")
    mats = {m["id"]: (k, m) for k, v in d["materials"].items() if isinstance(v, list) for m in v if isinstance(m, dict) and "id" in m}

    # placeholders -> absolute paths inside the copy (never let CapCut resolve them to the source project)
    def unplace(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if isinstance(v, str) and v.startswith("##_draftpath_placeholder_"):
                    o[k] = str(dst / v.split("_##/", 1)[1])
                else:
                    unplace(v)
        elif isinstance(o, list):
            for v in o:
                unplace(v)
    unplace(d["materials"])

    # one caption line, as in the reel: the widest caption decides the size (review 26 Sep: wrapping left orphans)
    widest = max(em_width(json.loads(mats[s["material_id"]][1]["content"])["text"], "Medium", 1.0)
                 for t in d["tracks"] if t.get("name") == "Captions" for s in t["segments"])
    CAP_EM = min(38.0, 0.97 * RIGHT_W / widest)
    captions, cap_tmpl, bg_last, bg_segs, intro_phone = [], None, None, {}, None
    # the phone group's vertical centre on the 16:9 canvas (from the mockup inside the compound), so the bigger
    # phone can be re-centred: TY moves it back to the middle after scaling by PHONE_K about the canvas centre
    sub = d["materials"]["drafts"][0]["draft"] if d["materials"].get("drafts") else None
    mock_y = next((s_["clip"]["transform"]["y"] for t_ in (sub or {"tracks": []})["tracks"] for s_ in t_["segments"]
                   if "iPhone_mockup" in (next((m_.get("path", "") for v_ in sub["materials"].values() if isinstance(v_, list)
                                                for m_ in v_ if isinstance(m_, dict) and m_.get("id") == s_["material_id"]), ""))), 0.0)
    phone_up = mock_y * 960 * 1080 / 1920                 # px above the 16:9 centre before the group scale
    TY = -PHONE_K * phone_up / (H / 2)                    # mockup box centred on the canvas ...
    mock = next((m_ for v_ in (sub or {"materials": {}})["materials"].values() if isinstance(v_, list) for m_ in v_
                 if isinstance(m_, dict) and "iPhone_mockup" in (m_.get("path") or "")), None)
    if mock and pathlib.Path(mock["path"]).exists():      # ... then the VISIBLE body (its PNG rows until the first gap)
        al = np.asarray(Image.open(mock["path"]).convert("RGBA"))[..., 3].max(1) > 0
        gap = np.flatnonzero(~al[1:] & al[:-1]); vis_end = int(gap[0]) + 1 if len(gap) else len(al)
        sy = next(s_["clip"]["scale"]["y"] for t_ in sub["tracks"] for s_ in t_["segments"] if s_["material_id"] == mock["id"])
        px_row = 1920 / len(al) * sy * (1080 / 1920) * PHONE_K
        d_vis = (len(al) / 2 - vis_end / 2) * px_row      # visible centre sits this far above the box centre
        TY -= ((PHONE_CY + d_vis) - H / 2) / (H / 2)
        VIS_CY = PHONE_CY
        sx = next(s_["clip"]["scale"]["x"] for t_ in sub["tracks"] for s_ in t_["segments"] if s_["material_id"] == mock["id"])
        VIS_HW = Image.open(mock["path"]).size[0] * px_row / sy * sx / 2                 # frame is scaled 0.782 x 0.757
        VIS_HH = vis_end * px_row / 2
    else:
        VIS_CY, VIS_HW, VIS_HH = H / 2, 240, 450
    for t in d["tracks"]:
        for s in t["segments"]:
            k, m = mats.get(s["material_id"], ("?", {}))
            path, c = m.get("path") or "", s.get("clip")
            if t["type"] == "video" and c:
                if "L1_background" in path:
                    c["scale"] = {"x": 3.2, "y": 3.2}; c["transform"] = {"x": 0.0, "y": 0.0}      # covers 1920 with overscan
                    bg_last = max(bg_last, (s["target_timerange"]["start"], id(s)), key=lambda x: x[0]) if bg_last else (s["target_timerange"]["start"], id(s))
                    bg_segs[id(s)] = s
                elif OUTRO_TAG in path:
                    c["scale"] = {"x": 1.0, "y": 1.0}; c["transform"] = {"x": 0.0, "y": 0.0}
                    s["extra_material_refs"] = [r for r in s["extra_material_refs"] if mats.get(r, ("",))[0] not in ("common_mask", "masks")]
                elif "L2_glow" in path:
                    s["visible"] = False                   # replaced by one wide glow (v2)
                else:
                    c["transform"]["x"] = PHONE_K * c["transform"]["x"] * FX
                    c["transform"]["y"] = PHONE_K * c["transform"]["y"] + TY
                    c["scale"] = {"x": c["scale"]["x"] * PHONE_K, "y": c["scale"]["y"] * PHONE_K}
                    for g in s.get("common_keyframes", []):
                        pt = g.get("property_type")
                        for kf in g["keyframe_list"]:
                            if pt == "KFTypePositionX":
                                kf["values"] = [PHONE_K * v * FX for v in kf["values"]]
                            elif pt == "KFTypePositionY":
                                kf["values"] = [PHONE_K * v + TY for v in kf["values"]]
                            elif pt in ("KFTypeScaleX", "KFTypeScaleY", "KFTypeScale"):
                                kf["values"] = [v * PHONE_K for v in kf["values"]]
                    if "INTRO_" in path and "_phone" in path:
                        intro_phone = s
            elif t["type"] == "text":
                cc = json.loads(m["content"]); st0 = cc["styles"][0]; size = st0.get("size", 5)
                if t.get("name") == "Captions":
                    em = CAP_EM
                    c["scale"] = {"x": em / (size * UNIT), "y": em / (size * UNIT)}; c["transform"] = {"x": tx(RIGHT_C), "y": 0.0}
                    m["alignment"] = 1; m["line_max_width"] = 0.98; m["force_apply_line_max_width"] = False
                    captions.append(s); cap_tmpl = cap_tmpl or (copy.deepcopy(s), copy.deepcopy(m))
                elif t.get("name") == "Sign-off":
                    em = 30
                    c["scale"] = {"x": em / (size * UNIT), "y": em / (size * UNIT)}; c["transform"] = {"x": 0.0, "y": ty(1012)}
                elif t.get("name", "").startswith("Intro text"):
                    i = int(t["name"][-1])
                    em, py, col = TITLE[i]
                    weight = pathlib.Path(st0["font"]["path"]).stem.split("-")[1]
                    w = em_width(cc["text"], weight, em)
                    if w > 1000 - TITLE_X0:
                        em *= (1000 - TITLE_X0) / w; w = em_width(cc["text"], weight, em)
                    if col:
                        for st_ in cc["styles"]:
                            st_["fill"]["content"]["solid"]["color"] = col
                        m["content"] = json.dumps(cc, ensure_ascii=False)
                    m["alignment"] = 0
                    c["scale"] = {"x": em / (size * UNIT), "y": em / (size * UNIT)}; c["transform"] = {"x": tx(TITLE_X0 + w / 2), "y": ty(py)}
                    s["target_timerange"]["duration"] = max(600_000, min(s["target_timerange"]["duration"], TITLE_END - s["target_timerange"]["start"]))

    # v2 intro: the phone fades in on the right (no slide-up), holds, then eases to the middle as the title fades
    def kf_group(tmpl, prop, keys):
        g = copy.deepcopy(tmpl); g["id"] = nid(); g["property_type"] = prop; kl = []
        for (t_, v, curve, rc) in keys:
            k_ = copy.deepcopy(tmpl["keyframe_list"][0]); k_.update(id=nid(), time_offset=t_, values=[v], curveType=curve,
                                                                    left_control={"x": 0.0, "y": 0.0}, right_control={"x": rc, "y": 0.0})
            kl.append(k_)
        g["keyframe_list"] = kl
        return g
    def move_keys(right, mid):
        ks = [(0, right, "Line", 0.0)]
        for i in range(MOVE_STEPS + 1):
            u = i / MOVE_STEPS; e = u * u * (3 - 2 * u)            # smoothstep: gentle start, gentle landing
            ks.append((int(MOVE[0] + (MOVE[1] - MOVE[0]) * u), right + (mid - right) * e, "Line", 0.0))
        return ks
    kf_tmpl = None
    if intro_phone:
        kf_tmpl = copy.deepcopy(intro_phone["common_keyframes"][0]) if intro_phone.get("common_keyframes") else None
        ic = intro_phone["clip"]; mid_x = ic["transform"]["x"]
        ic["transform"]["y"] = TY
        intro_phone["common_keyframes"] = [kf_group(kf_tmpl, "KFTypePositionX", move_keys(mid_x + PHONE_R / (W / 2), mid_x))] if kf_tmpl else []
    if sub:                                               # the glow inside the compound, in the embedded copy and its file
        smats = {m_["id"]: m_ for v_ in sub["materials"].values() if isinstance(v_, list) for m_ in v_ if isinstance(m_, dict) and "id" in m_}
        gids = {s_["id"] for t_ in sub["tracks"] for s_ in t_["segments"] if "L2_glow" in (smats.get(s_["material_id"], {}).get("path") or "")}
        def hide(o):
            if isinstance(o, dict):
                if o.get("id") in gids and "target_timerange" in o:
                    o["visible"] = False
                for v_ in o.values():
                    hide(v_)
            elif isinstance(o, list):
                for v_ in o:
                    hide(v_)
        hide(sub)
        fp = d["materials"]["drafts"][0].get("draft_file_path") or ""
        if fp and pathlib.Path(fp).exists():
            sj = json.loads(pathlib.Path(fp).read_text()); hide(sj); pathlib.Path(fp).write_text(json.dumps(sj, ensure_ascii=False))
    glow_png = L / "L_glow_wide.png"
    GW, GH = W, H                                          # fitted to the canvas, then scale GLOW_OVER: 1 PNG px = 2 screen px
    yy, xx = np.mgrid[0:GH, 0:GW]
    X_, Y_ = (xx - GW / 2) * GLOW_OVER, (yy - GH / 2) * GLOW_OVER          # screen px from the glow centre
    wide = GLOW_A * np.exp(-(X_ ** 2 / (2 * GLOW_SX ** 2) + Y_ ** 2 / (2 * GLOW_SY ** 2)))
    qx, qy = np.maximum(np.abs(X_) - (VIS_HW - HALO_R), 0), np.maximum(np.abs(Y_) - (VIS_HH - HALO_R), 0)
    dist = np.maximum(np.hypot(qx, qy) - HALO_R, 0)                          # px outside the phone's rounded body
    halo = HALO_A * np.exp(-dist ** 2 / (2 * HALO_S ** 2))
    a_ = 1 - (1 - wide) * (1 - halo)
    Image.fromarray(np.dstack([np.full((GH, GW), c_, np.uint8) for c_ in GLOW_RGB] + [np.round(a_ * 255).astype(np.uint8)])).save(glow_png)

    # the outro is full frame now: keep the background under it (it fades in over ~0.7 s)
    if bg_last:
        s = bg_segs[bg_last[1]]; end = d["duration"]
        s["target_timerange"]["duration"] = end - s["target_timerange"]["start"]
        if s.get("source_timerange"):
            s["source_timerange"]["duration"] = s["target_timerange"]["duration"]

    # --- new left panel texts + overlays
    ts, tm = cap_tmpl
    ri = []
    def text_seg(txt, weight, em, colour, px_left, py, start, end, track):
        m = copy.deepcopy(tm); m["id"] = nid()
        cc = json.loads(m["content"]); st = copy.deepcopy(cc["styles"][0])
        fp = str(FONTS / f"Poppins-{weight}.ttf")
        st["font"] = {"path": fp, "id": ""}; st["size"] = 5.0; st["fill"]["content"]["solid"]["color"] = colour; st["range"] = [0, len(txt)]
        cc.update(text=txt, styles=[st]); m["content"] = json.dumps(cc, ensure_ascii=False)
        m.update(font_path=fp, alignment=0, line_max_width=0.98, force_apply_line_max_width=False, font_size=5.0)
        d["materials"]["texts"].append(m)
        s = copy.deepcopy(ts); s["id"] = nid(); s["material_id"] = m["id"]; s["extra_material_refs"] = []
        s["target_timerange"] = {"start": int(start), "duration": int(end - start)}
        s["source_timerange"] = None
        s["render_index"] = 21000 + len(ri); ri.append(1)
        sc = em / (5.0 * UNIT); w = em_width(txt, weight, em)
        s["clip"]["scale"] = {"x": sc, "y": sc}; s["clip"]["transform"] = {"x": tx(px_left + w / 2), "y": ty(py)}
        track["segments"].append(s)

    ct = next(t for t in d["tracks"] if t.get("name") == "Captions")
    new = {k: {**{kk: copy.deepcopy(v) for kk, v in ct.items() if kk not in ("segments", "id", "name")},
               "segments": [], "id": nid(), "name": f"Steps - {k}"} for k in ("label", "count", "prev2", "prev1", "cur", "next1", "next2")}
    t_intro_end = min(s["target_timerange"]["start"] for s in captions)
    label = f"{role.upper()}  ·  {SERIES_LABEL}"
    text_seg(label, "Medium", 22, LIGHT, X0, 190, t_intro_end, list_end, new["label"])
    for i, (st, h) in enumerate(steps):
        end = steps[i + 1][0] if i + 1 < N else list_end
        text_seg(f"Step {i + 1} of {N}", "Regular", 22, NAVY_DIM, X0, 330, st, end, new["count"])
        for key, j in (("prev2", i - 2), ("prev1", i - 1), ("next1", i + 1), ("next2", i + 2)):
            if 0 <= j < N:
                e, _ = fit(steps[j][1], "Regular", 26)
                text_seg(steps[j][1], "Regular", e, NAVY_DIM, X0, ROWS[key], st, end, new[key])
        e, _ = fit(h, "SemiBold", 40)
        text_seg(h, "SemiBold", e, [1.0, 1.0, 1.0], X0, ROWS["cur"], st, end, new["cur"])

    bar = L / "L_step_bar.png"
    overlay(bar, lambda g: g.rounded_rectangle([X0 - 24, ROWS["cur"] - 24, X0 - 18, ROWS["cur"] + 24], radius=3, fill=(84, 106, 252, 255)))
    prog = []
    for i in range(N):
        pth = L / f"L_progress_{i + 1:03d}.png"
        frac = (i + 1) / N
        overlay(pth, lambda g, f=frac: (g.rectangle([120, 1046, 1800, 1049], fill=(28, 36, 64, 255)),
                                        g.rectangle([120, 1046, 120 + int(1680 * f), 1049], fill=(84, 106, 252, 255))))
        prog.append(pth)

    vid_tmpl = next(s for t in d["tracks"] if t.get("name") == "Markings" for s in t["segments"])
    vid_mat = mats[vid_tmpl["material_id"]][1]
    def png_seg(path, start, end, track):
        m = copy.deepcopy(vid_mat); m.update(id=nid(), path=str(path), material_name=path.name, width=W, height=H,
                                             duration=10_800_000_000, unique_id=hashlib.md5(path.read_bytes()).hexdigest())
        d["materials"]["videos"].append(m)
        refs = []
        for r in vid_tmpl.get("extra_material_refs", []):
            k_, em_ = mats.get(r, (None, None))
            if k_ and k_ not in ("material_animations", "common_mask", "masks", "transitions"):
                em_ = copy.deepcopy(em_); em_["id"] = nid(); d["materials"][k_].append(em_); refs.append(em_["id"])
        s = copy.deepcopy(vid_tmpl); s.update(id=nid(), material_id=m["id"], extra_material_refs=refs, common_keyframes=[])
        s["render_index"] = 900 + len(ri); ri.append(1)
        s["target_timerange"] = {"start": int(start), "duration": int(end - start)}
        s["source_timerange"] = {"start": 0, "duration": int(end - start)}
        s["clip"] = {"scale": {"x": 1.0, "y": 1.0}, "rotation": 0.0, "transform": {"x": 0.0, "y": 0.0},
                     "flip": {"vertical": False, "horizontal": False}, "alpha": 1.0}
        track["segments"].append(s)
    vt = next(t for t in d["tracks"] if t.get("name") == "Markings")
    track_like = lambda donor, nm: {**{k: copy.deepcopy(v) for k, v in donor.items() if k not in ("segments", "id", "name")},
                                    "segments": [], "id": nid(), "name": nm}
    bar_t, prog_t = track_like(vt, "Steps - bar"), track_like(vt, "Progress")
    if steps:
        png_seg(bar, steps[0][0], list_end, bar_t)
        for i, (st, _) in enumerate(steps):
            png_seg(prog[i], st, steps[i + 1][0] if i + 1 < N else list_end, prog_t)
    glow_t = track_like(vt, "Glow - wide")
    png_seg(glow_png, 0, d["duration"], glow_t)
    gs = glow_t["segments"][0]
    gm = mats_new = next(m_ for m_ in d["materials"]["videos"] if m_["id"] == gs["material_id"]); gm.update(width=GW, height=GH)
    gs["clip"]["scale"] = {"x": float(GLOW_OVER), "y": float(GLOW_OVER)}
    gs["clip"]["transform"]["y"] = ty(VIS_CY)
    gs["render_index"] = 1
    if kf_tmpl:
        gs["common_keyframes"] = [kf_group(kf_tmpl, "KFTypePositionX", move_keys(PHONE_R / (W / 2), 0.0))]
    old_glow = intro_phone                                 # fade in together with the phone (its own Fade In)
    if old_glow:
        for r in old_glow["extra_material_refs"]:
            if mats.get(r, ("",))[0] == "material_animations":
                a2 = copy.deepcopy(mats[r][1]); a2["id"] = nid(); d["materials"]["material_animations"].append(a2); gs["extra_material_refs"].append(a2["id"])
    bg_i = next(i for i, t in enumerate(d["tracks"]) if t.get("name") == "Background")
    d["tracks"].insert(bg_i + 1, glow_t)
    d["tracks"] += [bar_t, prog_t] + list(new.values())
    for i, t in enumerate(d["tracks"]):
        for s in t["segments"]:
            if "track_render_index" in s:
                s["track_render_index"] = i

    # --- checks, then write both copies
    ids = {m["id"] for v in d["materials"].values() if isinstance(v, list) for m in v if isinstance(m, dict) and "id" in m}
    bad = [r for t in d["tracks"] for s in t["segments"] for r in [s["material_id"]] + s.get("extra_material_refs", []) if r not in ids]
    assert not bad, f"{len(bad)} broken references"
    for t in d["tracks"]:
        segs = sorted(t["segments"], key=lambda s: s["target_timerange"]["start"])
        for a, b in zip(segs, segs[1:]):
            assert a["target_timerange"]["start"] + a["target_timerange"]["duration"] <= b["target_timerange"]["start"] + 1, f"overlap on {t.get('name')}"
    blob = json.dumps(d, ensure_ascii=False)
    for f in [dst / "draft_info.json", dst / "Timelines" / tl_id / "draft_info.json"]:
        f.write_text(blob)
    for f in [dst / "template.json", dst / "Timelines" / tl_id / "template.json"]:
        if f.exists():
            f.write_text(blob)
    print(f"-> {name}: canvas 1920x1080; {N} steps; captions {len(captions)} to the right panel at em {CAP_EM:.1f} (one line); "
          f"{sum(len(t['segments']) for t in new.values())} list texts; shrunk to fit {len(report['shrunk'])}; overlays in {L.relative_to(D)}")


if __name__ == "__main__":
    sfx = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--suffix=")), "16x9")
    main(sys.argv[1], sys.argv[2], "--dry" in sys.argv, sfx)
