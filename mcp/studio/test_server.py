"""End-to-end checks for the studio MCP server (no pytest needed).

    uv run --directory <this folder> python test_server.py

Starts the server in memory with the FastMCP Client and calls all six tools on real local
data (a CapCut project read-only, a temporary copy of ~10 photos, the prompt
playbooks), then checks the refusal paths (overwrite, writing into a CapCut project,
writing outside the allowed folders) and edge cases on small synthetic drafts.

Everything it writes goes into one temporary folder that is deleted at the end
(set STUDIO_TEST_KEEP=1 to keep it). It verifies the CapCut project is untouched and the
photo copies are byte-for-byte unchanged afterwards. Optional settings:
  STUDIO_TEST_PROJECT  CapCut project to read (default: the most recently saved project
                       that has captions)
  STUDIO_TEST_PHOTOS   folder with 10+ .jpg photos to copy (default: the first such folder
                       found under ~/Downloads or ~/Pictures)
  STUDIO_TEST_COMPOUND_PROJECT  optional regression check: a project of yours that keeps
                       most of its call-outs inside compound clips (skipped if unset)
  STUDIO_TEST_PHONE_PROJECT     optional regression check: a phone-app tutorial narrated
                       with 'Tap ...' (skipped if unset)
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path

sys.dont_write_bytecode = True
TMP = Path(tempfile.mkdtemp(prefix="studio_test_")).resolve()
os.environ["STUDIO_OUT"] = str(TMP / "out")
os.environ["STUDIO_WRITE_ROOTS"] = str(TMP)
sys.path.insert(0, str(Path(__file__).resolve().parent))

import server  # noqa: E402
from fastmcp import Client  # noqa: E402

US = 1_000_000
RESULTS: list[tuple[str, str, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append(("PASS" if ok else "FAIL", name, "" if ok else detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + ("" if ok else f"  -- {detail}"), flush=True)


def skip(name: str, why: str) -> None:
    RESULTS.append(("SKIP", name, why))
    print(f"SKIP  {name}  -- {why}", flush=True)


async def call(c: Client, tool: str, args: dict):
    r = await c.call_tool(tool, args, raise_on_error=False)
    text = r.content[0].text if r.content else ""
    return r, (r.structured_content if not r.is_error else None), text


def fingerprint(folder: Path) -> dict:
    """Every file under the folder: size + modification time (cheap, catches any write)."""
    out = {}
    for p in folder.rglob("*"):
        try:
            st = p.lstat()
        except OSError:
            continue
        out[str(p.relative_to(folder))] = (st.st_size, st.st_mtime_ns)
    return out


def sha_all(folder: Path) -> dict:
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(folder.iterdir()) if p.is_file()}


SRT_TIME = re.compile(r"^\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}$")


def srt_ok(text: str) -> tuple[bool, str]:
    blocks = [b for b in text.strip().split("\n\n") if b.strip()]
    for i, b in enumerate(blocks, 1):
        lines = b.split("\n")
        if lines[0] != str(i):
            return False, f"block {i} numbered {lines[0]!r}"
        if not SRT_TIME.match(lines[1]):
            return False, f"bad timing line {lines[1]!r}"
        if len(lines) < 3 or not lines[2].strip():
            return False, f"block {i} has no text"
    return True, f"{len(blocks)} blocks"


# ---------------------------------------------------------------------------
# Synthetic CapCut drafts (no real names, no real media)
# ---------------------------------------------------------------------------
def text_mat(mid: str, text: str, size: float, mtype: str = "text") -> dict:
    return {"id": mid, "type": mtype,
            "content": json.dumps({"text": text, "styles": [{"size": size}]})}


def seg(mid: str, start: float, dur: float, y: float = 0.0, visible: bool = True) -> dict:
    s = {"material_id": mid, "target_timerange": {"start": int(start * US),
                                                  "duration": int(dur * US)},
         "clip": {"transform": {"x": 0.0, "y": y}}}
    if not visible:
        s["visible"] = False
    return s


def draft(tracks: list, texts: list, videos: list = (), duration: float = 60.0,
          export: tuple[float, float] | None = None) -> dict:
    d = {"duration": int(duration * US), "fps": 30.0,
         "canvas_config": {"width": 1920, "height": 1080, "ratio": "original"},
         "config": {}, "tracks": tracks,
         "materials": {"texts": texts, "videos": list(videos), "audios": []}}
    if export:
        d["config"]["export_range"] = {"start": int(export[0] * US),
                                       "duration": int(export[1] * US)}
    return d


def write_project(root: Path, name: str, timelines: dict[str, dict] | None = None,
                  main: str | None = None, root_draft=None) -> Path:
    p = root / name
    p.mkdir(parents=True)
    if timelines:
        (p / "Timelines").mkdir()
        cfg = {"main_timeline_id": main, "timelines": []}
        for tid, (tname, d) in timelines.items():
            (p / "Timelines" / tid).mkdir()
            body = d if isinstance(d, (bytes, str)) else json.dumps(d)
            mode = "wb" if isinstance(body, bytes) else "w"
            with open(p / "Timelines" / tid / "draft_info.json", mode) as fh:
                fh.write(body)
            cfg["timelines"].append({"id": tid, "name": tname, "is_marked_delete": False})
        (p / "Timelines" / "project.json").write_text(json.dumps(cfg))
    if root_draft is not None:
        (p / "draft_info.json").write_text(json.dumps(root_draft))
    return p


def pick_real_project() -> str | None:
    """Most recently saved project with a readable, captioned main timeline, skipping any
    saved in the last 2 hours (it may be open in CapCut, which would change its files)."""
    rows = []
    for name in server._project_names():
        probe = server.DRAFTS / name / "draft_settings"
        try:
            rows.append(((probe if probe.exists() else server.DRAFTS / name).stat().st_mtime, name))
        except OSError:
            continue
    recent = time.time() - 2 * 3600
    for _, name in sorted((r for r in rows if r[0] < recent), reverse=True):
        try:
            _folder, _tl, d = server._open_draft(name, None, False)
        except Exception:
            continue
        if server._caption_key(server._text_rows(d)):
            return name
    return None


def pick_main_not_first() -> tuple[str, str] | None:
    """A real project whose main timeline is not the first timeline folder on disk."""
    for name in server._project_names():
        folder = server.DRAFTS / name
        try:
            cfg = json.loads((folder / "Timelines" / "project.json").read_text())
        except (OSError, ValueError):
            continue
        on_disk = sorted(p.parent.name for p in folder.glob("Timelines/*/draft_info.json"))
        main = cfg.get("main_timeline_id")
        if len(on_disk) > 1 and main in on_disk and on_disk[0] != main:
            head = (folder / "Timelines" / main / "draft_info.json").read_bytes()[:64].lstrip()
            if head.startswith(b"{"):
                return name, main
    return None


def find_photo_folder() -> Path | None:
    """STUDIO_TEST_PHOTOS, else the first folder (3 levels deep) under ~/Downloads or
    ~/Pictures holding 10+ JPGs."""
    env = os.environ.get("STUDIO_TEST_PHOTOS")
    roots = [Path(os.path.expanduser(env))] if env else \
        [Path.home() / "Downloads", Path.home() / "Pictures"]
    for root in roots:
        if not root.is_dir():
            continue
        base = len(root.parts)
        for dp, dn, fn in os.walk(root):
            dn[:] = sorted(d for d in dn if not d.startswith("."))[:200] \
                if len(Path(dp).parts) - base < 3 else []
            if sum(1 for f in fn if f.lower().endswith(".jpg") and not f.startswith(".")) >= 10:
                return Path(dp)
            if env:
                break
    return None


async def real_capcut_tests(c: Client) -> None:
    drafts = server.DRAFTS
    if not drafts.is_dir():
        skip("real CapCut project", f"no drafts folder at {drafts}")
        return
    project = os.environ.get("STUDIO_TEST_PROJECT") or pick_real_project()
    if not project or not (drafts / project).is_dir():
        skip("real CapCut project", "no readable project with captions found "
             "(set STUDIO_TEST_PROJECT)")
        return
    print(f"      (real project: {project})", flush=True)
    folder = drafts / project
    before = fingerprint(folder)
    root_before = sorted(os.listdir(drafts))

    r, d, t = await call(c, "capcut_project_summary", {"project": project})
    check("summary: real project reads", not r.is_error, t[:300])
    if d:
        check("summary: has duration, canvas, tracks, media check",
              d["duration_s"] > 0 and d["canvas"]["width"] and d["tracks"]
              and "missing_count" in d["media"], json.dumps(d)[:300])
        check("summary: captions detected", d["text"]["captions"] > 0, str(d["text"]))

    r, d, t = await call(c, "capcut_project_summary", {"project": "list"})
    check("summary: 'list' returns recent projects",
          not r.is_error and len(d["most_recent"]) > 0, t[:200])

    r, d, t = await call(c, "capcut_project_summary", {"project": "zz no such project qq"})
    check("summary: unknown project is a clear error", r.is_error and "No CapCut project" in t, t)

    trap = pick_main_not_first()
    if trap:
        name, main_id = trap
        r, d, t = await call(c, "capcut_project_summary", {"project": name})
        check("summary: main timeline used even when it is not first on disk (real project)",
              not r.is_error and d["timeline"]["id"] == main_id, t[:200])
    else:
        skip("summary: main timeline not first on disk (real project)", "no such project here")

    # --- SRT export ---------------------------------------------------------
    r, d, t = await call(c, "capcut_export_srt", {"project": project})
    check("srt: default export writes a new file", not r.is_error, t[:300])
    first_srt = None
    if d:
        first_srt = Path(d["written"])
        body = first_srt.read_text("utf-8")
        ok, why = srt_ok(body)
        check("srt: file is valid SRT", ok, why)
        check("srt: no ',1000' timestamps", ",1000" not in body)
        check("srt: cue count matches", body.count(" --> ") == d["cues"], f"{d['cues']}")
        check("srt: written under the output folder", server._inside(first_srt, TMP / "out"),
              str(first_srt))
        r2, d2, t2 = await call(c, "capcut_export_srt", {"project": project})
        check("srt: second export gets a new name instead of overwriting",
              not r2.is_error and d2["written"] != d["written"]
              and first_srt.read_text("utf-8") == body, t2[:200])

    if first_srt:
        r, _, t = await call(c, "capcut_export_srt",
                             {"project": project, "out_path": str(first_srt)})
        check("refuse: overwrite an existing file", r.is_error and "already exists" in t, t)
    target = folder / "studio_test_should_not_exist.srt"
    r, _, t = await call(c, "capcut_export_srt", {"project": project, "out_path": str(target)})
    check("refuse: write inside a CapCut project folder",
          r.is_error and "CapCut" in t and not target.exists(), t)
    link = TMP / "sneaky_link"
    link.symlink_to(folder)
    r, _, t = await call(c, "capcut_export_srt",
                         {"project": project, "out_path": str(link / "evil.srt")})
    check("refuse: symlink that points into a CapCut project",
          r.is_error and "CapCut" in t and not (folder / "evil.srt").exists(), t)
    # The Mac's disk ignores letter case: other spellings of the same folder must be refused
    for label, variant in (
            ("lower-case 'capcut'", str(folder).replace("CapCut", "capcut")),
            ("upper-case path", str(folder).upper()),
            ("firmlink /System/Volumes/Data", "/System/Volumes/Data" + str(folder))):
        if label.startswith("firmlink") and not Path("/System/Volumes/Data/Users").is_dir():
            skip(f"refuse: CapCut project via {label}", "no firmlinked data volume here")
            continue
        r, _, t = await call(c, "capcut_export_srt",
                             {"project": project, "out_path": variant + "/zz_probe.srt"})
        check(f"refuse: CapCut project spelt another way ({label})",
              r.is_error and "CapCut" in t and not (folder / "zz_probe.srt").exists(), t)
    r, _, t = await call(c, "capcut_export_srt",
                         {"project": project, "out_path": str(TMP / "a\x00b.srt")})
    check("refuse: NUL byte in out_path is a clear refusal",
          r.is_error and "NUL" in t and "embedded null" not in t, t)
    r, _, t = await call(c, "capcut_export_srt",
                         {"project": project, "out_path": str(TMP / ("x" * 2000)) + ".srt"})
    check("refuse: over-long out_path", r.is_error and "too long" in t and len(t) < 400, t[:200])
    for outside in ("/etc/studio_test.srt", str(Path.home() / "studio_test_outside.srt")):
        r, _, t = await call(c, "capcut_export_srt", {"project": project, "out_path": outside})
        check(f"refuse: path outside allowed folders ({outside})",
              r.is_error and "outside" in t and not Path(outside).exists(), t)
    r, _, t = await call(c, "capcut_export_srt", {"project": project, "out_path": "rel.srt"})
    check("refuse: relative out_path", r.is_error and "full path" in t, t)
    r, _, t = await call(c, "capcut_export_srt",
                         {"project": project, "out_path": str(TMP / "captions.txt")})
    check("refuse: wrong file type", r.is_error and ".srt" in t, t)

    # --- call-out audit -----------------------------------------------------
    r, d, t = await call(c, "callout_audit", {"project": project})
    check("audit: real project runs", not r.is_error, t[:300])
    if d:
        check("audit: never reports a pass",
              d["status"] in ("candidates", "incomplete") and "pass" != d["status"]
              and (d["status"] != "candidates" or d["counts"]["candidates"] > 0
                   or "not a pass" in d["message"]), d["message"])
        check("audit: counts present", d["status"] == "incomplete"
              or d["counts"]["actions_checked"] >= d["counts"]["candidates"], str(d.get("counts")))

    check("real project untouched (every file same size + time)", fingerprint(folder) == before)
    check("drafts folder gained no new entries", sorted(os.listdir(drafts)) == root_before)

    # Regressions seen on real drafts (read-only; skipped unless you name the project)
    compound = os.environ.get("STUDIO_TEST_COMPOUND_PROJECT", "")
    if compound and (drafts / compound).is_dir():
        r, d, t = await call(c, "callout_audit", {"project": compound})
        check("real compound-clip project: call-outs inside compound clips are seen "
              "(no false alarms)",
              not r.is_error and d["counts"]["call_out_images_in_compound_clips"] > 0
              and d["counts"]["candidates"] <= 2, t[:300])
    else:
        skip("real compound-clip project", "set STUDIO_TEST_COMPOUND_PROJECT")
    phone = os.environ.get("STUDIO_TEST_PHONE_PROJECT", "")
    if phone and (drafts / phone).is_dir():
        r, d, t = await call(c, "callout_audit", {"project": phone})
        check("real phone-app project: 'Tap ...' narration is checked",
              not r.is_error and d["counts"]["actions_checked"] >= 10, t[:300])
    else:
        skip("real phone-app project", "set STUDIO_TEST_PHONE_PROJECT")


def vault_guard_tests() -> None:
    """The vault (STUDIO_ROOT) is never a write target, however it is spelt. Validator only:
    _new_file_path raises before anything could be created."""
    root = server.ROOT
    cases = [("vault top level", root / "zz_probe.srt"),
             ("vault Reference/", root / "Reference" / "zz_probe.srt"),
             ("vault tools/", server.TOOLS / "zz_probe.srt"),
             ("vault tools/ in another letter case",
              server.TOOLS.parent / "Tools" / "zz_probe.srt"),
             ("vault in upper case", Path(str(root / "Reference").upper()) / "zz_probe.srt")]
    for label, p in cases:
        try:
            server._new_file_path(str(p), ".srt")
            check(f"refuse: {label}", False, f"{p} was allowed")
        except server.ToolError as exc:
            check(f"refuse: {label}", "never writes inside" in str(exc) and not p.exists(),
                  str(exc))
    for label, p in (("network path /net", "/net/zz-studio-test-host/x.srt"),
                     ("network path /Network", "/Network/Servers/zz/x.srt")):
        try:
            server._check_write_location(Path(p))
            check(f"refuse: {label}", False, "allowed")
        except server.ToolError as exc:
            check(f"refuse: {label}", "network" in str(exc), str(exc))
    # spelling: case-insensitive; identity: another route (here a symlink) to the same folder
    check("write guard ignores letter case",
          server._rel_under(Path(str(TMP).upper()) / "a" / "b", TMP) == ("a", "b"),
          str(server._rel_under(Path(str(TMP).upper()) / "a" / "b", TMP)))
    real = TMP / "guard_real"
    real.mkdir()
    (TMP / "guard_alias").symlink_to(real)
    check("write guard matches folders by identity, not only by spelling",
          server._rel_under(TMP / "guard_alias" / "x.srt", real) == ("x.srt",),
          str(server._rel_under(TMP / "guard_alias" / "x.srt", real)))


async def synthetic_tests(c: Client) -> None:
    fake = TMP / "fake_drafts"
    fake.mkdir()
    # Alpha: main timeline 'BBBB' is NOT first on disk; captions are size 8 on 'Captions'
    alpha_main = draft(
        tracks=[{"type": "text", "name": "Captions", "segments": [
                    seg("c1", 1.0, 2.0, -0.68), seg("c2", 3.5, 2.0, -0.68),
                    seg("c3", 6.0, 2.0, -0.68), seg("ch", 8.0, 1.0, -0.68, visible=False)]},
                {"type": "text", "name": "", "segments": [seg("lbl", 2.0, 1.0, 0.3)]}],
        texts=[text_mat("c1", "Alpha caption one.", 8), text_mat("c2", "Alpha caption two.", 8),
               text_mat("c3", "Alpha caption three.", 8), text_mat("ch", "hidden line", 8),
               text_mat("lbl", "a label", 5)])
    side = draft(tracks=[{"type": "text", "name": "", "segments": [
                    seg("s1", 0.5, 1.0, -0.89), seg("s2", 2.0, 1.0, -0.89),
                    seg("s3", 4.0, 1.0, -0.89)]}],
                 texts=[text_mat("s1", "Side one.", 5), text_mat("s2", "Side two.", 5),
                        text_mat("s3", "Side three.", 5)])
    write_project(fake, "Alpha Test", {"AAAA-1": ("Side Slice", side),
                                       "BBBB-2": ("Alpha Main", alpha_main)}, main="BBBB-2")
    # Clip: export range 10 s + 5 s; cues straddle both edges
    clip = draft(tracks=[{"type": "text", "name": "", "segments": [
                    seg("k1", 9.0, 2.0, -0.89), seg("k2", 12.0, 1.0, -0.89),
                    seg("k3", 16.0, 1.0, -0.89)]}],
                 texts=[text_mat("k1", "Edge cue.", 5), text_mat("k2", "Middle cue.", 5),
                        text_mat("k3", "After the out point.", 5)],
                 duration=30.0, export=(10.0, 5.0))
    write_project(fake, "Clip Test", root_draft=clip)
    # Rounding: a cue at 1.9996 s must print 00:00:02,000, never 00:00:01,1000
    rnd = draft(tracks=[{"type": "text", "name": "", "segments": [
                    {"material_id": "r1", "target_timerange": {"start": 1_999_600,
                                                               "duration": 1_000_000},
                     "clip": {"transform": {"y": -0.89}}},
                    seg("r2", 4.0, 1.0, -0.89), seg("r3", 6.0, 1.0, -0.89)]}],
                texts=[text_mat("r1", "Round me.", 5), text_mat("r2", "Two.", 5),
                       text_mat("r3", "Three.", 5)])
    write_project(fake, "Round Test", root_draft=rnd)
    # Encrypted timeline (base64 text, not JSON)
    write_project(fake, "Locked Test", {"CCCC-3": ("Locked", base64.b64encode(b"x" * 300))},
                  main="CCCC-3")
    # Audit: two actions in one caption with a box nearby; a later action with only a
    # freeze frame and a hidden box nearby (neither counts)
    audit = draft(
        tracks=[{"type": "text", "name": "Captions", "segments": [
                    seg("a1", 5.6, 2.0, -0.89), seg("a2", 30.0, 2.0, -0.89),
                    seg("a3", 40.0, 2.0, -0.89)]},
                {"type": "video", "name": "", "segments": [
                    seg("box", 5.7, 1.6), seg("frz", 30.0, 2.0),
                    seg("hid", 30.0, 2.0, visible=False)]}],
        texts=[text_mat("a1", "Open the Leads List and select the lead.", 5),
               text_mat("a2", "Click Save.", 5),
               text_mat("a3", "The record is now saved.", 5)],
        videos=[{"id": "box", "type": "photo", "path": "/nowhere/01_box.png"},
                {"id": "frz", "type": "photo",
                 "path": "/nowhere/" + "a" * 32 + "_123-sdr709.png"},
                {"id": "hid", "type": "photo", "path": "/nowhere/02_box.png"}])
    write_project(fake, "Audit Test", root_draft=audit)

    # Compound clip: call-outs, a caption and a media file exist ONLY inside the compound
    # clip, which sits at 8-28 s on the timeline showing its own 5-25 s.
    sub = draft(
        tracks=[{"type": "video", "name": "", "segments": [
                    seg("p1", 7.2, 1.0), seg("p2", 18.0, 1.0),
                    seg("p3", 34.0, 1.0)]},             # 37-38 s: outside the clip window
                {"type": "text", "name": "", "segments": [seg("sc", 12.0, 2.0, -0.89)]},
                {"type": "video", "name": "", "segments": [seg("sv", 0.0, 30.0)]}],
        texts=[text_mat("sc", "Select the claim.", 5)],
        videos=[{"id": "p1", "type": "photo", "path": "/nowhere/c01_open.png"},
                {"id": "p2", "type": "photo", "path": "/nowhere/c02_approve.png"},
                {"id": "p3", "type": "photo", "path": "/nowhere/c03_late.png"},
                {"id": "sv", "type": "video", "path": "/nowhere/sub_missing.mp4"}],
        duration=40.0)
    comp_seg = seg("cc", 8.0, 20.0)
    comp_seg["source_timerange"] = {"start": 5 * US, "duration": 20 * US}
    comp_seg["extra_material_refs"] = ["SUB1"]
    comp = draft(
        tracks=[{"type": "text", "name": "Captions", "segments": [
                    seg("m1", 10.0, 2.0, -0.89), seg("m2", 20.0, 2.0, -0.89),
                    seg("m3", 40.0, 2.0, -0.89)]},
                {"type": "video", "name": "", "segments": [comp_seg]}],
        texts=[text_mat("m1", "Open the Job Card.", 5), text_mat("m2", "Click Approve.", 5),
               text_mat("m3", "Tap Save.", 5)],
        videos=[{"id": "cc", "type": "video", "path": "", "material_name": "Compound clip1"}])
    comp["materials"]["drafts"] = [{"id": "SUB1", "type": "combination", "draft": sub}]
    write_project(fake, "Compound Test", root_draft=comp)

    # Phone-app narration with no markings at all
    phone = draft(
        tracks=[{"type": "text", "name": "Captions", "segments": [
            seg("f1", 2.0, 2.0, -0.68), seg("f2", 12.0, 2.0, -0.68), seg("f3", 22.0, 2.0, -0.68)]}],
        texts=[text_mat("f1", "Tap Jobs to see them.", 8),
               text_mat("f2", "Tap the job to open it.", 8),
               text_mat("f3", "Press Scan and swipe to the next part.", 8)])
    write_project(fake, "Phone Test", root_draft=phone)
    # Narration with no instructions at all (a brand film): nothing can be checked
    lines = [f"Our brand value number {i} matters to everyone." for i in range(12)]
    brand = draft(
        tracks=[{"type": "text", "name": "Captions", "segments": [
            seg(f"b{i}", 1.0 + 3 * i, 2.5, -0.89) for i in range(12)]}],
        texts=[text_mat(f"b{i}", line, 5) for i, line in enumerate(lines)])
    write_project(fake, "Brand Test", root_draft=brand)
    # Window: a box STARTING 4.5 s after the action is too late; one ENDING 4.5 s before
    # the action still counts (the sa_actioncheck window is 5 s before, 4 s after)
    window = draft(
        tracks=[{"type": "text", "name": "Captions", "segments": [
                    seg("w1", 10.0, 2.0, -0.89), seg("w2", 30.0, 2.0, -0.89)]},
                {"type": "video", "name": "", "segments": [seg("late", 14.5, 1.0),
                                                           seg("early", 24.0, 1.5)]}],
        texts=[text_mat("w1", "Click Save.", 5), text_mat("w2", "Click Next.", 5)],
        videos=[{"id": "late", "type": "photo", "path": "/nowhere/01_late.png"},
                {"id": "early", "type": "photo", "path": "/nowhere/02_early.png"}])
    write_project(fake, "Window Test", root_draft=window)
    # Two caption tracks playing at once
    overlap = draft(
        tracks=[{"type": "text", "name": "", "segments": [
                    seg("o1", 0.0, 3.0, -0.89), seg("o2", 3.0, 3.0, -0.89)]},
                {"type": "text", "name": "", "segments": [
                    seg("o3", 3.1, 2.9, -0.89), seg("o4", 6.0, 2.0, -0.89)]}],
        texts=[text_mat("o1", "Open the", 5), text_mat("o2", "Job Card.", 5),
               text_mat("o3", "The screen shows the list.", 5),
               text_mat("o4", "Click Save.", 5)])
    write_project(fake, "Overlap Test", root_draft=overlap)
    # Media on a network share and on a drive that is not connected: never probed
    net = draft(tracks=[{"type": "text", "name": "", "segments": [seg("n1", 1.0, 1.0, -0.89)]}],
                texts=[text_mat("n1", "Hello.", 5)],
                videos=[{"id": "v1", "type": "video", "path": "/net/zz-studio-test-host/a.mp4"},
                        {"id": "v2", "type": "video",
                         "path": "/Volumes/zz_studio_no_such_drive/b.mp4"}])
    write_project(fake, "Network Test", root_draft=net)

    real_drafts = server.DRAFTS
    server.DRAFTS = fake
    try:
        r, d, t = await call(c, "callout_audit", {"project": "Compound Test"})
        cands = [x["action"] for x in (d or {}).get("candidates", [])]
        check("compound clip: call-outs inside it count, clipped-off ones don't",
              not r.is_error and cands == ["Tap Save"]
              and d["counts"]["call_out_images_in_compound_clips"] == 2, f"{cands} {t[:400]}")
        r, d, t = await call(c, "capcut_project_summary", {"project": "Compound Test"})
        check("compound clip: summary counts it and the caption inside it",
              not r.is_error and d["compound_clips"]["on_timeline"] == 1
              and d["text"]["captions"] == 4 and d["text"]["captions_inside_compound_clips"] == 1,
              t[:400])
        check("compound clip: missing media inside it is reported (stand-in is not)",
              d and "/nowhere/sub_missing.mp4" in d["media"]["missing"]
              and d["media"]["materials_without_a_path"] == 0
              and d["media"]["files_only_inside_compound_clips"] == 4, str(d and d["media"]))
        r, d, t = await call(c, "capcut_export_srt", {"project": "Compound Test"})
        body = Path(d["written"]).read_text() if d else t
        check("compound clip: its caption lands in the SRT at the timeline time",
              "00:00:15,000 --> 00:00:17,000\nSelect the claim." in body, body[:400])
        to_main = server._child_map(lambda a, b: (a, b), 50 * US, 55 * US, 0, 2.0)
        check("compound clip: speed and window applied to inner times",
              to_main(int(7.2 * US), int(8.2 * US)) == (int(53.6 * US), int(54.1 * US))
              and to_main(int(20 * US), int(21 * US)) is None, str(to_main(7_200_000, 8_200_000)))

        r, d, t = await call(c, "callout_audit", {"project": "Phone Test"})
        cands = [x["action"] for x in (d or {}).get("candidates", [])]
        check("phone narration: tap/press/swipe are actions",
              not r.is_error and d["counts"]["actions_checked"] == 4
              and cands == ["Tap Jobs to see them", "Tap the job to open it", "Press Scan"],
              f"{cands} {t[:300]}")
        r, d, t = await call(c, "callout_audit", {"project": "Brand Test"})
        check("audit: narration with no recognisable actions is 'incomplete'",
              not r.is_error and d["status"] == "incomplete"
              and d["counts"]["actions_checked"] == 0 and "not a pass" in d["message"], t[:300])
        r, d, t = await call(c, "callout_audit", {"project": "Window Test"})
        cands = [x["action"] for x in (d or {}).get("candidates", [])]
        check("audit window: 5 s before / 4 s after, and the text says so",
              not r.is_error and cands == ["Click Save"]
              and "from 5 s before to 4 s after" in d["message"], f"{cands} {t[:300]}")

        r, d, t = await call(c, "capcut_export_srt", {"project": "Overlap Test"})
        if d:
            body = Path(d["written"]).read_text()
            ok, why = srt_ok(body)
            times = [re.findall(r"(\d\d):(\d\d):(\d\d),(\d{3})", ln)
                     for ln in body.splitlines() if " --> " in ln]
            secs = [[int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000
                     for h, m, s, ms in pair] for pair in times]
            no_overlap = all(secs[i][1] <= secs[i + 1][0] for i in range(len(secs) - 1))
            long_enough = all(b - a >= 0.2 - 1e-9 for a, b in secs)
            check("overlapping caption tracks: valid SRT, no overlaps, no cue under 0.2 s",
                  ok and no_overlap and long_enough, body)
            check("overlapping caption tracks: warning lists the times",
                  any("two caption tracks" in n for n in d["notes"]), str(d["notes"]))
        else:
            check("overlapping caption tracks: valid SRT", False, t)
        joined = [s for s, _ in server._sentences([
            (0.0, 2.0, "Open the", "A"), (1.0, 3.0, "The screen shows", "B"),
            (2.5, 4.0, "Job Card.", "A"), (3.0, 5.0, "the list.", "B")])]
        check("sentences are joined per caption track, never interleaved",
              joined == ["Open the Job Card.", "The screen shows the list."], str(joined))

        t0 = time.monotonic()
        r, d, t = await call(c, "capcut_project_summary", {"project": "Network Test"})
        check("media on network / unplugged drives is not probed",
              not r.is_error and d["media"]["on_network_drives_not_checked"] == 1
              and d["media"]["on_unmounted_drives"] == {"zz_studio_no_such_drive": 1}
              and d["media"]["missing_count"] == 0 and time.monotonic() - t0 < 3, t[:400])

        # default output folders that are symlinks into CapCut must be refused
        saved_out = server.OUT
        server.OUT = TMP / "out_link"
        try:
            server.OUT.mkdir()
            (server.OUT / "SRT").symlink_to(fake / "Clip Test")
            before = sorted(os.listdir(fake / "Clip Test"))
            r, _, t = await call(c, "capcut_export_srt", {"project": "Clip Test"})
            check("refuse: default SRT folder that is a symlink into CapCut",
                  r.is_error and "CapCut" in t
                  and sorted(os.listdir(fake / "Clip Test")) == before, t)
            (server.OUT / "cull").symlink_to(fake / "Clip Test")
            pics = TMP / "link_pics"
            pics.mkdir()
            (pics / "a.jpg").write_bytes(b"\xff\xd8 not a real photo")
            r, _, t = await call(c, "photo_cull", {"folder": str(pics), "limit": 1})
            check("refuse: default cull folder that is a symlink into CapCut",
                  r.is_error and "CapCut" in t
                  and sorted(os.listdir(fake / "Clip Test")) == before, t)
        finally:
            server.OUT = saved_out

        r, d, t = await call(c, "capcut_project_summary", {"project": "Alpha"})
        check("synthetic: main_timeline_id chosen over first-on-disk",
              not r.is_error and d["timeline"]["id"] == "BBBB-2", t[:200])
        check("synthetic: size-8 captions detected (hidden one skipped)",
              d and d["text"]["captions"] == 3 and d["text"]["caption_style"]["size"] == 8,
              str(d and d["text"]))
        r, d, t = await call(c, "capcut_project_summary",
                             {"project": "Alpha Test", "timeline": "Side Slice"})
        check("synthetic: named timeline selected", not r.is_error
              and d["timeline"]["id"] == "AAAA-1" and d["text"]["caption_style"]["size"] == 5,
              t[:200])
        r, d, t = await call(c, "capcut_export_srt", {"project": "Clip Test"})
        if not r.is_error:
            body = Path(d["written"]).read_text()
            check("synthetic: export range clips and shifts cues",
                  d["cues"] == 2 and body.startswith("1\n00:00:00,000 --> 00:00:01,000\nEdge cue.")
                  and "00:00:02,000 --> 00:00:03,000\nMiddle cue." in body
                  and "After the out point" not in body, body)
        else:
            check("synthetic: export range clips and shifts cues", False, t)
        r, d, t = await call(c, "capcut_export_srt",
                             {"project": "Clip Test", "timeline_range": "full"})
        check("synthetic: full range keeps all cues", not r.is_error and d["cues"] == 3, t[:200])
        r, d, t = await call(c, "capcut_export_srt", {"project": "Round Test"})
        body = Path(d["written"]).read_text() if d else t
        check("synthetic: 1.9996 s prints as 00:00:02,000",
              "00:00:02,000 --> 00:00:03,000" in body and ",1000" not in body, body[:120])
        r, _, t = await call(c, "capcut_project_summary", {"project": "Locked Test"})
        check("synthetic: encrypted draft reported plainly", r.is_error and "encrypted" in t, t)
        saved = server.MAX_DRAFT_BYTES
        server.MAX_DRAFT_BYTES = 50
        server._DRAFT_CACHE.clear()
        try:
            r, _, t = await call(c, "capcut_project_summary", {"project": "Round Test"})
            check("synthetic: oversized draft refused without allow_large",
                  r.is_error and "allow_large" in t, t)
            r, _, t = await call(c, "capcut_project_summary",
                                 {"project": "Round Test", "allow_large": True})
            check("synthetic: allow_large reads it anyway", not r.is_error, t[:200])
        finally:
            server.MAX_DRAFT_BYTES = saved
        r, d, t = await call(c, "callout_audit", {"project": "Audit Test"})
        cands = [x["action"] for x in (d or {}).get("candidates", [])]
        check("synthetic audit: double action covered by one box; freeze/hidden box ignored",
              not r.is_error and d["counts"]["actions_checked"] == 3
              and cands == ["Click Save"], f"{cands} {t[:300]}")
        r, d, t = await call(c, "callout_audit", {"project": "Clip Test", "caption_size": 99})
        check("synthetic audit: no captions -> 'incomplete', not a pass",
              not r.is_error and d["status"] == "incomplete", t[:200])
    finally:
        server.DRAFTS = real_drafts


async def style_tests(c: Client) -> None:
    r, d, t = await call(c, "style_lookup", {"style": "training_tutorial"})
    check("style: family lookup", not r.is_error and d["family"] == "training_tutorial"
          and d["grammar"] and "chapter_template" in d["grammar"], t[:200])
    if d and not server.STYLE_BRAIN.is_file():
        skip("style: live cut stats included", f"no full style brain at {server.STYLE_BRAIN} "
             "(build one with tools/sa_stylebrain.py or set STUDIO_STYLE_BRAIN)")
    elif d:
        live = d["cut_rhythm"]["live_stats"]["styles"]
        check("style: live cut stats included", "tutorial_or_explainer" in live, str(live)[:200])
        brain = server.STYLE_BRAIN
        if brain.is_file():
            names = {str(p.get("project")) for p in json.loads(brain.read_text())["projects"]}
            leaked = [n for n in names if len(n) > 5 and n in t]
            check("style: no project names leak from the style brain", not leaked, str(leaked[:5]))
    r, d, t = await call(c, "style_lookup", {"style": "tutorial_or_explainer"})
    check("style: style-type lookup", not r.is_error and d["style_types"] == ["tutorial_or_explainer"],
          t[:200])
    r, d, t = await call(c, "style_lookup", {"style": "farewell"})
    check("style: plain words", not r.is_error and d["family"] == "tribute_farewell", t[:200])
    r, d, t = await call(c, "style_lookup", {"style": "event"})
    check("style: 'event' means the event recap family, alternatives listed",
          not r.is_error and d["family"] == "event_recap_fast"
          and "premium_product_event" in d.get("other_possible_families", []), t[:200])
    r, d, t = await call(c, "style_lookup", {"style": "list"})
    check("style: list", not r.is_error and len(d["families"]) >= 7, t[:200])
    r, _, t = await call(c, "style_lookup", {"style": "qqzz xxyy"})
    check("style: unknown style is a clear error", r.is_error and "No style matches" in t, t)
    for q, fam in (("montage", "event_recap_fast"), ("\U0001F3AC montage ✨", "event_recap_fast"),
                   ("software demo", "training_tutorial"),
                   ("luxury car launch", "premium_product_event")):
        r, d, t = await call(c, "style_lookup", {"style": q})
        check(f"style: {q!r} -> {fam}", not r.is_error and d["family"] == fam, t[:200])
    r, _, t = await call(c, "style_lookup", {"style": "x" * 210_000})
    check("style: huge input refused without echoing it", r.is_error and len(t) < 400, t[:200])


async def cap_tests(c: Client) -> None:
    r, _, t = await call(c, "prompt_search", {"query": "kling " * 200_000, "limit": 3})
    check("prompts: 1 MB query refused, short reply", r.is_error and len(t) < 400, t[:200])
    r, _, t = await call(c, "prompt_search",
                         {"query": " ".join(f"word{i}" for i in range(20)), "limit": 3})
    check("prompts: more than 12 words refused", r.is_error and "Too many words" in t, t)
    r, _, t = await call(c, "capcut_project_summary", {"project": "p" * 100_000})
    check("summary: huge project name refused, short reply", r.is_error and len(t) < 400, t[:200])
    r, _, t = await call(c, "photo_cull", {"folder": "/tmp/a\x00b"})
    check("cull: NUL byte in folder is a clear refusal", r.is_error and "NUL" in t, t)


async def photo_tests(c: Client) -> None:
    src = find_photo_folder()
    if not src:
        skip("photo_cull on real photos", "no folder with 10+ JPGs found "
             "(set STUDIO_TEST_PHOTOS)")
    elif not server.VENV_PY.is_file():
        skip("photo_cull on real photos", f"no OpenCV Python at {server.VENV_PY} "
             "(set STUDIO_CULL_PYTHON)")
    else:
        print(f"      (photos copied from: {src})", flush=True)
        copy = TMP / "photos"
        copy.mkdir()
        for p in sorted(p for p in src.iterdir()
                        if p.suffix.lower() == ".jpg" and not p.name.startswith("."))[:10]:
            shutil.copy2(p, copy / p.name)
        (copy / "note.png").write_bytes(b"not really a png")
        before = sha_all(copy)
        r, d, t = await call(c, "photo_cull", {"folder": str(copy), "limit": 8})
        check("cull: runs on 8 of 10 photos", not r.is_error and d["scored"] == 8, t[:300])
        if d:
            out = Path(d["output_folder"])
            check("cull: output is a new folder under the output root",
                  out.is_dir() and server._inside(out, TMP / "out" / "cull"), str(out))
            check("cull: report, picks list and contact sheet written",
                  len(d["files_written"]) == 3 and all(Path(f).is_file()
                                                       for f in d["files_written"]),
                  str(d["files_written"]))
            check("cull: picks returned (capped)", 0 < d["picks_count"] <= 8
                  and len(d["picks"]) <= 30, str(d["picks_count"]))
            check("cull: skipped non-JPG counted", "png" in " ".join(d["notes"]), str(d["notes"]))
        check("cull: original photos unchanged (sha256) and nothing added",
              sha_all(copy) == before)
        (r1, d1, t1), (r2, d2, t2) = await asyncio.gather(
            call(c, "photo_cull", {"folder": str(copy), "limit": 2}),
            call(c, "photo_cull", {"folder": str(copy), "limit": 2}))
        check("cull: two runs in the same second get two new folders",
              not r1.is_error and not r2.is_error
              and d1["output_folder"] != d2["output_folder"], f"{t1[:200]} | {t2[:200]}")
        check("cull: originals still unchanged after parallel runs", sha_all(copy) == before)
    await cull_cancel_test()
    r, _, t = await call(c, "photo_cull", {"folder": "relative/folder"})
    check("cull: relative folder refused", r.is_error and "full path" in t, t)
    empty = TMP / "empty_photos"
    empty.mkdir()
    r, _, t = await call(c, "photo_cull", {"folder": str(empty)})
    check("cull: folder without JPGs is a clear error", r.is_error and "No .jpg" in t, t)
    r, _, t = await call(c, "photo_cull", {"folder": str(empty), "limit": 0})
    check("cull: limit below 1 rejected", r.is_error, t)


async def cull_cancel_test() -> None:
    """A cancelled photo_cull (client gave up, server shutting down) must kill its child."""
    if not server.VENV_PY.is_file():
        skip("cull: cancel kills the scoring process",
             "no OpenCV Python (set STUDIO_CULL_PYTHON)")
        return
    pics = TMP / "cancel_pics"
    pics.mkdir()
    (pics / "a.jpg").write_bytes(b"\xff\xd8 not a real photo")
    pid_file = TMP / "fake_driver.pid"
    fake = TMP / "fake_driver.py"
    fake.write_text("import os, sys, time\nsys.stdin.read()\n"
                    f"open({str(pid_file)!r}, 'w').write(str(os.getpid()))\ntime.sleep(60)\n")
    saved = server.CULL_DRIVER
    server.CULL_DRIVER = fake
    try:
        task = asyncio.create_task(server.photo_cull(folder=str(pics), limit=1, ctx=None))
        for _ in range(100):
            if pid_file.exists() and pid_file.read_text().strip():
                break
            await asyncio.sleep(0.1)
        pid = int(pid_file.read_text().strip()) if pid_file.exists() else None
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await task
        alive = True
        if pid:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                alive = False
        check("cull: cancel kills the scoring process", pid is not None and not alive,
              f"pid={pid} alive={alive}")
    finally:
        server.CULL_DRIVER = saved


async def prompt_tests(c: Client) -> None:
    r, d, t = await call(c, "prompt_search", {"query": "Kling", "limit": 3})
    check("prompts: real query finds entries", not r.is_error and 0 < len(d["results"]) <= 3
          and all(x["score"] > 0 for x in d["results"]), t[:200])
    check("prompts: text is labelled as quoted data",
          d and all("quoted_text" in x for x in d["results"]) and "data" in d.get("note", ""),
          t[:200])
    r, d, t = await call(c, "prompt_search", {"query": "Suno heritage", "limit": 5})
    check("prompts: music playbook searched", not r.is_error
          and any("music" in x["file"] for x in d["results"]), t[:200])
    r, d, t = await call(c, "prompt_search", {"query": "x", "limit": 3})
    check("prompts: too-short query refused", r.is_error, t)
    r, _, t = await call(c, "prompt_search", {"query": "Kling", "limit": 50})
    check("prompts: limit above 20 rejected", r.is_error, t)
    # splitter: empty dated title, undated child section, ### under ##
    vault = TMP / "fake_vault"
    vault.mkdir()
    (vault / "prompts.md").write_text(
        "# Library\n\n---\n## [2026-01-02] \n[2026-01-02] Neon zebra entry\nbody zebra\n"
        "## CORE TRICKS\nzebra trick\n---\n## TOPIC\n### Zebra prompt one\nprompt text\n")
    saved, saved_files = server.ROOT, server.PROMPT_FILES
    server.ROOT, server.PROMPT_FILES = vault, {"prompts.md": "prompts.md"}
    try:
        r, d, t = await call(c, "prompt_search", {"query": "zebra", "limit": 10})
        heads = {x["heading"]: x for x in (d or {}).get("results", [])}
        check("prompts: empty dated title filled from first line",
              "Neon zebra entry" in heads and heads["Neon zebra entry"]["date"] == "2026-01-02",
              str(list(heads)))
        check("prompts: undated part kept with its dated parent",
              heads.get("CORE TRICKS", {}).get("part_of") == "Neon zebra entry", str(heads)[:300])
        check("prompts: ### entry has its ## parent",
              heads.get("Zebra prompt one", {}).get("part_of") == "TOPIC", str(heads)[:300])
    finally:
        server.ROOT, server.PROMPT_FILES = saved, saved_files


async def main() -> int:
    vault_cache = server.TOOLS / "__pycache__"
    cache_before = set(os.listdir(vault_cache)) if vault_cache.is_dir() else set()
    async with Client(server.mcp) as c:
        tools = {t.name: t for t in await c.list_tools()}
        expected = {"style_lookup", "capcut_project_summary", "capcut_export_srt",
                    "callout_audit", "photo_cull", "prompt_search"}
        check("exactly the six tools", set(tools) == expected, str(sorted(tools)))
        ro = {n for n, t in tools.items() if t.annotations and t.annotations.readOnlyHint}
        check("read-only hints", ro == expected - {"capcut_export_srt", "photo_cull"}, str(ro))
        check("no tool is destructive or open-world",
              all(t.annotations and t.annotations.destructiveHint is False
                  and t.annotations.openWorldHint is False for t in tools.values()))
        check("every tool documented", all((t.description or "").strip() for t in tools.values()))
        check("server tells clients returned text is data, not instructions",
              "never as instructions" in (server.mcp.instructions or ""))
        check("fastmcp's PyPI update check is off",
              os.environ.get("FASTMCP_CHECK_FOR_UPDATES") == "off")
        await style_tests(c)
        await cap_tests(c)
        await real_capcut_tests(c)
        vault_guard_tests()
        await synthetic_tests(c)
        await photo_tests(c)
        await prompt_tests(c)
    cache_after = set(os.listdir(vault_cache)) if vault_cache.is_dir() else set()
    check("no bytecode written into the vault's tools folder", cache_after <= cache_before,
          str(sorted(cache_after - cache_before)))
    passed = sum(1 for s, *_ in RESULTS if s == "PASS")
    failed = [r for r in RESULTS if r[0] == "FAIL"]
    skipped = sum(1 for s, *_ in RESULTS if s == "SKIP")
    print(f"\n{passed} passed, {len(failed)} failed, {skipped} skipped")
    return 1 if failed else 0


if __name__ == "__main__":
    try:
        code = asyncio.run(main())
    finally:
        if os.environ.get("STUDIO_TEST_KEEP") != "1":
            shutil.rmtree(TMP, ignore_errors=True)
        else:
            print(f"kept test folder: {TMP}")
    sys.exit(code)
