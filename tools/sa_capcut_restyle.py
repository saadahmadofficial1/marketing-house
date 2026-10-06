#!/usr/bin/env python3
"""sa_capcut_restyle — give a module's CapCut project Saad's phone look, copied from his own edit.

Requirement (24 Sep): Saad re-laid one module's phone project by hand and asked for every
other module to follow it - the same phone placement, the same glow treatment, and the same
two copy layers stacked on top of the app recording.

His look is a stack of CapCut settings: glow scaled and softened with a feathered rectangle
mask; the app scaled 0.716 and moved up; two thin masked COPIES of the app (one turned
180 deg) filling the gaps in the phone's screen hole; the phone mockup on top, darkened with
adjustments and its floor shadow masked off (numbers: a reference style JSON).
Re-deriving those numbers is how drift creeps in, so this tool does not: it copies his
visible phone/app tracks verbatim, every mask / adjustment / HSL material under fresh ids,
and re-points the media at the target's own files (app -> LAYERS/<tag>/L4_app_<tag>.mp4).

    Tools/venv/bin/python3 Tools/sa_capcut_restyle.py <reference_dir> <target_dir | project name> --tag 05_ModuleName
    Tools/venv/bin/python3 Tools/sa_capcut_restyle.py --test

The target's Background / Glow / iPhone back / App recording / iPhone frame tracks are
replaced; Markings, Voice over and Captions stay exactly as they are, above the new stack.
Refuses while CapCut is open and never writes the reference. Backs the draft up first
(.pre_restyle), writes one blob to the root and main-timeline draft_info.json (the two
copies CapCut reads), re-reads both and restores the originals if the check fails.
"""
import subprocess, argparse, copy, json, os, pathlib, re, shutil, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from sa_capcut_callouts import CAPCUT, US, capcut_open, new_id, probe  # noqa: E402

# Per-module layer renders live in LAYERS/<tag>/; set SA_LAYERS_DIR to point elsewhere.
LAYERS = pathlib.Path(os.environ.get("SA_LAYERS_DIR", "LAYERS")).expanduser()
VISUAL = re.compile(r"^L[1-5]_|mockup", re.I)        # background, glow, phone, app, mockup
VISUAL_NAMES = {"Background", "Glow", "iPhone back", "App recording (masked)", "iPhone frame",
                "App recording", "App fill strip 1", "App fill strip 2", "Phone mockup"}
ABOVE = ["Markings", "Voice over", "Captions"]        # must sit over the stack, in this order
FRAME = US // 30


def index(draft):
    """material id -> (group, material), across every materials list."""
    return {m["id"]: (k, m) for k, v in draft["materials"].items() if isinstance(v, list)
            for m in v if isinstance(m, dict) and "id" in m}


def refs(seg):
    return [seg["material_id"]] + list(seg.get("extra_material_refs") or [])


def is_visual(track, idx):
    if track.get("type") != "video" or not track.get("segments"):
        return False
    if track.get("name") in VISUAL_NAMES:
        return True
    return all(VISUAL.search(idx.get(s["material_id"], ("", {}))[1].get("material_name", ""))
               for s in track["segments"])


def strip_still(app, T, at=0.5):
    """One frame of the app (its first screen) as a video as long as the timeline, for the strips."""
    png, still = app.with_name(app.stem + "_still.png"), app.with_name(app.stem.replace("L4_app", "L4_still") + ".mp4")
    if not still.exists() or probe(still)[0] * US < T:
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{at}", "-i", str(app), "-frames:v", "1", str(png)], check=True)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-i", str(png), "-t", f"{T / US + 1:.3f}",
                        "-r", "30", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-tune", "stillimage", str(still)], check=True)
    return still


def restyle(ref, tgt, tag, freeze_strips=False):
    """Pure: reference draft + target draft -> (restyled copy of target, summary)."""
    ridx, out = index(ref), copy.deepcopy(tgt)
    tidx, T = index(out), out["duration"]
    stack = [t for t in ref["tracks"] if is_visual(t, ridx)
             and any(s.get("visible", True) for s in t["segments"])]      # his hidden tracks stay out
    if not stack:
        raise SystemExit("reference has no visible phone/app tracks")
    for t in stack:
        s = t["segments"][0]
        if len(t["segments"]) != 1 or s.get("speed", 1.0) != 1.0 or s.get("keyframe_refs") \
                or s.get("common_keyframes"):
            raise SystemExit(f"reference track {t.get('name')!r}: expected one plain full-length segment")

    own = {m["material_name"][:3]: m["path"] for k, m in tidx.values()
           if k == "videos" and re.match(r"L[1-5]_", m.get("material_name", ""))}
    app = LAYERS / tag / f"L4_app_{tag}.mp4"
    still = strip_still(app, T) if freeze_strips and app.exists() else None
    if own.get("L4_") and os.path.basename(own["L4_"]) != app.name:     # wrong --tag = wrong video
        raise SystemExit(f"--tag {tag} does not match this project's app recording "
                         f"{os.path.basename(own['L4_'])}")

    def media(m):
        n = m.get("material_name", "")
        if n.startswith("L4_"):
            dur, w, h = probe(app)
            if int(dur * US) < T - FRAME:
                raise SystemExit(f"{app.name} is {dur:.2f}s, shorter than the {T / US:.2f}s timeline")
            m.update(path=str(app), name=app.name, material_name=app.name, width=w, height=h,
                     duration=max(int(dur * US), T), unique_id="")
        elif re.match(r"L[1-5]_", n):
            p = own.get(n[:3]) or str(LAYERS / tag / n)
            m.update(path=p, name=os.path.basename(p), material_name=os.path.basename(p),
                     duration=T, unique_id="")
        else:
            m["duration"] = T                                            # the mockup keeps its PNG

    # out with the old stack, and any material only it used
    old = [t for t in out["tracks"] if is_visual(t, tidx)]
    keep = [t for t in out["tracks"] if not is_visual(t, tidx)]
    # a fresh build leaves every video track at track_render_index 0 (track order decides, and
    # that is what Saad has opened); numbering the stack 1..5 would put it OVER the Markings if
    # CapCut layers by that index. So never above the lowest index the kept tracks use.
    floor = min((s.get("track_render_index", 0) for t in keep for s in t["segments"]), default=0)
    gone = {r for t in old for s in t["segments"] for r in refs(s)} - \
           {r for t in keep for s in t["segments"] for r in refs(s)}
    for k, v in out["materials"].items():
        if isinstance(v, list):
            out["materials"][k] = [m for m in v if not (isinstance(m, dict) and m.get("id") in gone)]

    fresh, new, apps, copied = {}, [], 0, 0
    remap = lambda i: fresh.setdefault(i, new_id())
    for pos, t in enumerate(stack):
        t = copy.deepcopy(t)
        s = t["segments"][0]
        kind = ridx[s["material_id"]][1].get("material_name", "") if s["material_id"] in ridx else ""
        for rid in refs(s):
            if rid in fresh:
                continue
            if rid not in ridx:
                raise SystemExit(f"reference track {t.get('name')!r} points at a missing material {rid[:8]}")
            k, m = ridx[rid]
            m = copy.deepcopy(m)
            m["id"] = remap(rid)
            if m.get("constant_material_id"):
                m["constant_material_id"] = remap(m["constant_material_id"])
            if k == "videos":
                media(m)
            out["materials"].setdefault(k, []).append(m)
            copied += 1
        s.update(id=new_id(), material_id=fresh[s["material_id"]],
                 extra_material_refs=[fresh[r] for r in s.get("extra_material_refs") or []],
                 target_timerange={"start": 0, "duration": T},
                 source_timerange={"start": 0, "duration": T},
                 render_index=pos, track_render_index=min(pos, floor))
        if kind.startswith("L4_") and apps and still:
            # Saad's finished reference cut (24 Sep): the two fill strips are ONE frozen frame of the app
            # (its first screen) for the whole video, not moving copies - so the bands at the top
            # and bottom of the phone never flicker when the app changes page.
            vm = next(m for m in out["materials"]["videos"] if m["id"] == s["material_id"])
            fm = copy.deepcopy(vm)
            fm.update(id=new_id(), path=str(still), name=still.name, material_name=still.name, unique_id="")
            out["materials"]["videos"].append(fm)
            s["material_id"] = fm["id"]
        t["id"] = new_id()
        if not t.get("name"):                                             # his copies are unnamed
            if kind.startswith("L4_"):
                t["name"] = "App recording" if not apps else f"App fill strip {apps}"
            elif "mockup" in kind.lower():
                t["name"] = "Phone mockup"
            t["is_default_name"] = not t.get("name")
        apps += kind.startswith("L4_")
        new.append(t)
    out["tracks"] = new + keep
    return out, {"removed": [t.get("name") or tidx.get(t["segments"][0]["material_id"], ("", {}))[1]
                             .get("material_name", "?") for t in old],
                 "inserted": [t.get("name") or "?" for t in new], "materials": copied}


def ids_of(draft):
    """Every identifier the draft owns: tracks, segments, materials, constant ids."""
    got = {t["id"] for t in draft["tracks"]} | {s["id"] for t in draft["tracks"] for s in t["segments"]}
    for _, m in index(draft).values():
        got |= {m["id"], m.get("constant_material_id") or m["id"]}
    return got


def check(draft, ref):
    """What CapCut needs to open this and what Saad needs to see. [] = pass."""
    p, idx, T = [], index(draft), draft["duration"]
    mids = [m["id"] for v in draft["materials"].values() if isinstance(v, list)
            for m in v if isinstance(m, dict) and "id" in m]
    if len(mids) != len(set(mids)):
        p.append("two materials share an id")
    for t in draft["tracks"]:
        for s in t["segments"]:
            miss = [r for r in refs(s) if r not in idx]
            if miss:
                p.append(f"{t.get('name') or t['type']}: {len(miss)} dangling material ref(s)")
    stack = [t for t in draft["tracks"] if is_visual(t, idx)]
    if draft["tracks"][:len(stack)] != stack:
        p.append("phone/app stack is not at the bottom of the timeline")
    names = [t.get("name") for t in draft["tracks"][len(stack):]]
    if [n for n in names if n in ABOVE] != ABOVE:
        p.append(f"above the stack expected {' > '.join(ABOVE)}, found {names}")
    # the phone must paint UNDER the markings by either index CapCut might layer with
    lo = lambda key, ts: min((s.get(key, 0) for t in ts for s in t["segments"]), default=1 << 30)
    hi = lambda key, ts: max((s.get(key, 0) for t in ts for s in t["segments"]), default=-1)
    above = draft["tracks"][len(stack):]
    if hi("track_render_index", stack) > lo("track_render_index", above):
        p.append("stack track_render_index above the Markings (CapCut could paint the phone over them)")
    if hi("render_index", stack) >= lo("render_index", [t for t in above if t["type"] == "video"]):
        p.append("stack render_index not below the Markings")
    mine = {t["id"] for t in stack} | {s["id"] for t in stack for s in t["segments"]}
    for t in stack:
        for r in refs(t["segments"][0]):
            if r in idx:
                m = idx[r][1]
                mine |= {m["id"], m.get("constant_material_id") or m["id"]}
    if mine & ids_of(ref):
        p.append(f"{len(mine & ids_of(ref))} id(s) reused from the reference")
    for t in stack:
        s = t["segments"][0]
        tr, sr = s["target_timerange"], s["source_timerange"]
        if (tr["start"], tr["duration"], sr["start"], sr["duration"]) != (0, T, 0, T):
            p.append(f"{t.get('name')}: segment does not span the {T / US:.2f}s timeline")
        m = idx.get(s["material_id"], ("", {}))[1]
        if m.get("duration", 0) < T:
            p.append(f"{t.get('name')}: material shorter than the timeline")
        if not os.path.exists(m.get("path", "")):
            p.append(f"{t.get('name')}: missing media {m.get('path')}")
        if not s.get("visible", True):
            p.append(f"{t.get('name')}: hidden track copied")
    return p


def resolve(p):
    p = pathlib.Path(os.path.expanduser(str(p)))
    return p if p.is_dir() else CAPCUT / str(p)                 # a bare name lives in CapCut's folder


def copies(project):
    """The draft_info.json copies CapCut reads: root (legacy) and Timelines/<main timeline>/."""
    pj = project / "Timelines" / "project.json"
    main = json.loads(pj.read_text())["main_timeline_id"] if pj.exists() else None
    return [p for p in (project / "draft_info.json",
                        project / "Timelines" / str(main) / "draft_info.json") if p.exists()]


def write(ref_dir, tgt_dir, tag):
    ref_dir, tgt_dir = resolve(ref_dir), resolve(tgt_dir)
    if ref_dir.resolve() == tgt_dir.resolve() or "REFERENCE" in tgt_dir.name:
        raise SystemExit("refusing: the target is Saad's reference project")
    if capcut_open():
        raise SystemExit("CapCut is open — close it first; a write into a loaded draft is lost or corrupts it")
    paths = copies(tgt_dir)
    if not paths:
        raise SystemExit(f"no draft_info.json in {tgt_dir}")
    before = {p: p.read_bytes() for p in paths}
    if len(set(before.values())) > 1:
        print("  note: root copy differed from the main timeline; both now get the main timeline, restyled")
    ref = json.loads(copies(ref_dir)[-1].read_text(encoding="utf-8"))
    out, info = restyle(ref, json.loads(before[paths[-1]]), tag, freeze_strips=True)
    bad = check(out, ref)
    if bad:
        raise SystemExit("REFUSED, nothing written:\n  " + "\n  ".join(bad))

    blob = json.dumps(out, ensure_ascii=False)
    for p in paths:
        bak = p.with_suffix(".json.pre_restyle")
        if not bak.exists():
            shutil.copy2(p, bak)
        p.write_text(blob, encoding="utf-8")
    back = [p.read_text(encoding="utf-8") for p in paths]           # read back the way CapCut will
    bad = ([] if len(set(back)) == 1 else ["draft copies disagree after writing"]) + \
          check(json.loads(back[0]), ref)
    if bad:
        for p, b in before.items():
            p.write_bytes(b)
        raise SystemExit("read-back failed, originals restored:\n  " + "\n  ".join(bad))
    print(f"-> {tgt_dir.name}: Saad's phone look from {ref_dir.name}\n"
          f"   removed  {', '.join(info['removed'])}\n"
          f"   inserted {', '.join(info['inserted'])}  ({info['materials']} materials, fresh ids)\n"
          f"   order    {' > '.join(t.get('name') or t['type'] for t in out['tracks'])}\n"
          f"   {out['duration'] / US:.2f}s, {len(paths)} draft copies identical  [verified]  backup .pre_restyle")
    return out


def _test():
    import tempfile
    global probe, LAYERS
    tmp = pathlib.Path(tempfile.mkdtemp())
    for f in ("X/L4_app_X.mp4", "own/L1_background.png", "own/L2_glow.png"):
        (tmp / f).parent.mkdir(exist_ok=True)
        (tmp / f).write_bytes(b"")
    own = lambda n: str(tmp / "own" / n)
    here = str(pathlib.Path(__file__).resolve())
    V = lambda i, n, p=here: {"id": i, "material_name": n, "name": n, "path": p, "duration": 1, "type": "photo"}
    S = lambda i, mid, ex=(), vis=True: {"id": i, "material_id": mid, "extra_material_refs": list(ex),
                                         "visible": vis, "speed": 1.0, "render_index": 0,
                                         "target_timerange": {"start": 0, "duration": 1},
                                         "source_timerange": {"start": 0, "duration": 1}}
    Tk = lambda i, name, segs, kind="video": {"id": i, "type": kind, "name": name, "segments": segs}
    ref = {"duration": 5 * US, "materials": {
        "videos": [V("rb", "L1_background.png"), V("rg", "L2_glow.png"), V("ra", "L4_app_REF.mp4"),
                   V("rs", "L4_app_REF.mp4"), V("rm", "iPhone_mockup.png"), V("rk", "L3_iphone_back.png"),
                   V("rx", "mark_001_box.png")],
        "common_mask": [{"id": "m1", "constant_material_id": "C1"}, {"id": "m2", "constant_material_id": "C1"}],
        "effects": [{"id": "e1"}], "hsl": [{"id": "h1", "constant_material_id": "H1"}]},
        "tracks": [Tk("t0", "Background", [S("s0", "rb")]), Tk("t1", "Glow", [S("s1", "rg")]),
                   Tk("t2", "", [S("s2", "ra", ["m1"])]), Tk("t3", "", [S("s3", "rs", ["m2"])]),
                   Tk("t4", "", [S("s4", "rm", ["e1", "h1"])]),
                   Tk("t5", "iPhone back", [S("s5", "rk", vis=False)]),
                   Tk("t6", "Markings", [S("s6", "rx")])]}
    tgt = {"duration": 10 * US, "materials": {
        "videos": [V("b", "L1_background.png", own("L1_background.png")),
                   V("g", "L2_glow.png", own("L2_glow.png")),
                   V("k", "L3_iphone_back.png"), V("a", "L4_app_X.mp4", str(tmp / "X" / "L4_app_X.mp4")),
                   V("f", "L5_iphone_front.png"),
                   V("x", "mark_001_box.png")],
        "common_mask": [{"id": "tm"}], "audios": [{"id": "vo"}], "texts": [{"id": "tx"}]},
        "tracks": [Tk("T0", "Background", [S("A0", "b")]), Tk("T1", "Glow", [S("A1", "g")]),
                   Tk("T2", "iPhone back", [S("A2", "k")]),
                   Tk("T3", "App recording (masked)", [S("A3", "a", ["tm"])]),
                   Tk("T4", "iPhone frame", [S("A4", "f")]), Tk("T5", "Markings", [S("A5", "x")]),
                   Tk("T6", "Voice over", [S("A6", "vo")], "audio"),
                   Tk("T7", "Captions", [S("A7", "tx")], "text")]}
    tgt["tracks"][5]["segments"][0]["render_index"] = 6        # callouts numbers call-outs after the stack
    real = probe, LAYERS
    probe, LAYERS = (lambda p: (10.0, 1080, 1920)), tmp
    try:
        out, info = restyle(ref, tgt, "X")
        names = [t["name"] for t in out["tracks"]]
        assert names == ["Background", "Glow", "App recording", "App fill strip 1", "Phone mockup",
                         "Markings", "Voice over", "Captions"], names    # his hidden iPhone back stays out
        assert check(out, ref) == [], check(out, ref)
        idx = index(out)
        assert not {"k", "f", "tm", "a", "b", "g"} & set(idx), "old stack materials must go"
        assert {"x", "vo", "tx"} <= set(idx), "markings / voice / captions materials must stay"
        assert out["tracks"][5:] == tgt["tracks"][5:], "markings / voice / captions untouched"
        masks = [idx[r][1] for t in out["tracks"][2:4] for r in t["segments"][0]["extra_material_refs"]]
        assert masks[0]["constant_material_id"] == masks[1]["constant_material_id"] != "C1"
        m = lambda n: idx[out["tracks"][n]["segments"][0]["material_id"]][1]
        assert m(0)["path"] == own("L1_background.png"), "background / glow = the target's own files"
        assert m(2)["path"] == str(tmp / "X" / "L4_app_X.mp4")
        assert m(3)["path"] == m(2)["path"] and m(4)["path"] == here, "strips re-pointed, mockup kept"
        assert all(t["segments"][0]["target_timerange"]["duration"] == 10 * US for t in out["tracks"][:5])
        assert {t["segments"][0]["track_render_index"] for t in out["tracks"][:5]} == {0}, \
            "fresh build: Markings sit at track_render_index 0, so the stack may not rise above it"
        bad = copy.deepcopy(out)
        bad["tracks"][4]["segments"][0]["track_render_index"] = 4
        assert any("track_render_index" in x for x in check(bad, ref)), "check must catch a stack over the Markings"
        again, _ = restyle(ref, out, "X")                                  # a second run replaces, never stacks
        assert [t["name"] for t in again["tracks"]] == names, [t["name"] for t in again["tracks"]]
        assert check(again, ref) == [], check(again, ref)
        assert len(index(again)) == len(idx), "a re-run must not leave orphan materials behind"
        for tag, why in (("Y", "a --tag naming another module's app must be refused"),
                         ("X", "an app recording shorter than the timeline must be refused")):
            probe = (lambda p: (5.0, 1080, 1920)) if tag == "X" else probe
            try:
                restyle(ref, tgt, tag)
                raise AssertionError(why)
            except SystemExit:
                pass
    finally:
        probe, LAYERS = real
        shutil.rmtree(tmp, ignore_errors=True)
    print("sa_capcut_restyle self-check: ok (stack copied, hidden skipped, fresh ids, re-pointed, "
          "markings/voice/captions untouched, re-run idempotent)")


if __name__ == "__main__":
    if "--test" in sys.argv:
        _test()
        sys.exit()
    ap = argparse.ArgumentParser()
    ap.add_argument("reference")
    ap.add_argument("target")
    ap.add_argument("--tag", required=True, help="e.g. 05_ModuleName (LAYERS/<tag>/L4_app_<tag>.mp4)")
    a = ap.parse_args()
    write(a.reference, a.target, a.tag)
