#!/usr/bin/env python3
"""sa_rolemark — mark every role change with a label in Saad's own style.

Across the series the script tells the trainee to become a different person 30 times and
only 13 had anything on screen. In one module Saad fixed two himself by typing a label —
"Sign in as the Manager" — in Poppins Medium size 5, centred, ~1.9s. That element IS the
spec: this tool clones his own text material verbatim (font, size, no shadow, position,
scale) and changes only the words, so the new labels are indistinguishable from his.

    Tools/venv/bin/python3 Tools/sa_rolemark.py --check
    Tools/venv/bin/python3 Tools/sa_rolemark.py --fix
    Tools/venv/bin/python3 Tools/sa_rolemark.py --test

No freezes are inserted: a freeze lengthens the timeline and shifts every caption after it.
Freezing is Saad's editing move; the label lands where the role's screen is already showing.

All labels go on ONE track named "Role changes" — he consolidated my one-track-per-call-out
build onto single lanes, so nineteen lanes is a mistake we do not repeat. Re-running
replaces the track, never stacks it. Only the tags in PROJECT_OF are touched — never a
video he has declared done.
"""
import argparse
import copy
import glob
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import uuid

US = 1_000_000
CAPCUT = pathlib.Path("~/Movies/CapCut/User Data/Projects/com.lveditor.draft").expanduser()
DONOR_PROJECT = "Donor Module"
DONOR_TEXT = "Sign in as Cashier"          # his most recent hand-typed role label
TRACK = "Role changes"
DUR = 1.9                                  # his labels ran 1.60-1.97s
PROJECT_OF = {"T01": "Module 01 Example Process",   # tag -> CapCut project name
              "T02": "Module 02 Example Process",
              "T03": "Module 03 Example Process"}

# The list above is a hardcoded snapshot and goes stale the moment Saad finishes a video —
# on 13 Aug it would have written into two videos he had declared done the day before.
# His progress file is the only live truth, so ask it every run.
SERIES = pathlib.Path(os.environ.get("TRAINING_ROOT", "~/Downloads/training-series")).expanduser()
PROGRESS = str(SERIES / "5 ADMIN" / "PROGRESS.json")


def declared_done():
    """Tags Saad has marked done — never write into these, whatever the allow-list says."""
    import json as _json
    import os as _os
    import re as _re
    if not _os.path.exists(PROGRESS):
        return set()                       # cannot prove it is safe -> caller keeps its list
    videos = _json.load(open(PROGRESS)).get("videos", {})
    done = set()
    for name, row in videos.items():
        if str(row.get("saad", "")).lower() != "done":
            continue
        m = _re.search(r"\b(\d{2})\b", name)       # the module number in its name
        if m:
            done.add("T" + m.group(1))
        m2 = _re.match(r"\s*(T\d{2}[a-z]?)\b", name)
        if m2:
            done.add(m2.group(1))
    return done

ROLE_RE = re.compile(r"[Ss]ign (?:in|back in)(?: as (the )?([A-Z][\w ]*?))?(?=[,.]| and| to)")


def label_for(script):
    """-> "Sign in as the Approver", from the script line. Pure."""
    m = ROLE_RE.search(script)
    if m and m.group(2):
        role = m.group(2).strip()
        # the script may carry an unlocked role name ("Review user"); the LABEL must
        # use the locked one — exactly what an 8 Aug audit flagged
        from sa_terms import fix_label
        return fix_label(f"Sign in as {'the ' if m.group(1) else ''}{role}")
    if re.search(r"[Ss]ign out", script):
        return "Sign out"
    return None


def capcut_open():
    return subprocess.run(["pgrep", "-x", "CapCut"], capture_output=True).returncode == 0


def donor():
    """His own typed label: (text material, its segment), deep-copied."""
    p = CAPCUT / DONOR_PROJECT
    for f in glob.glob(str(p / "Timelines/*/draft_info.json")):
        d = json.load(open(f))
        tm = {m["id"]: m for m in d["materials"].get("texts", [])}
        for t in d.get("tracks", []):
            for s in t.get("segments", []):
                m = tm.get(s.get("material_id"))
                if not m:
                    continue
                try:
                    if json.loads(m.get("content") or "{}").get("text") == DONOR_TEXT:
                        return copy.deepcopy(m), copy.deepcopy(s)
                except (json.JSONDecodeError, TypeError):
                    pass
    raise SystemExit(f"donor label {DONOR_TEXT!r} not found in {DONOR_PROJECT}")


def build(draft, dm, ds, marks):
    """Pure: draft + [(t, label)] -> draft with one replaced 'Role changes' track."""
    out = copy.deepcopy(draft)
    gone = {s.get("material_id")
            for t in out.get("tracks", []) if t.get("name") == TRACK
            for s in t.get("segments", [])}
    out["tracks"] = [t for t in out.get("tracks", []) if t.get("name") != TRACK]
    out["materials"]["texts"] = [m for m in out["materials"].get("texts", [])
                                 if m["id"] not in gone]
    segs = []
    for i, (t, label) in enumerate(sorted(marks)):
        m = copy.deepcopy(dm)
        m["id"] = str(uuid.uuid4()).upper()
        c = json.loads(m["content"])
        c["text"] = label
        # his element has exactly one style; widen its range to the new text
        for st in (c.get("styles") or []):
            st["range"] = [0, len(label)]
        m["content"] = json.dumps(c, ensure_ascii=False)
        m["base_content"] = ""
        out["materials"].setdefault("texts", []).append(m)
        s = copy.deepcopy(ds)
        s.update({"id": str(uuid.uuid4()).upper(), "material_id": m["id"],
                  "target_timerange": {"start": int(t * US), "duration": int(DUR * US)},
                  "source_timerange": None, "render_index": 21000 + i,
                  "extra_material_refs": [], "group_id": "", "template_id": ""})
        segs.append(s)
    out["tracks"].append({"id": str(uuid.uuid4()).upper(), "type": "text",
                          "attribute": 0, "flag": 0, "is_default_name": False,
                          "name": TRACK, "segments": segs})
    return out


def already_marked(tag, when, label, window=8.0):
    """Is there already a call-out naming this role at about this moment?

    One module had 6 of its 10 role changes covered by ordinary call-outs ("Sign in as the
    Team Leader" etc). Writing a text label for those too would double the marker.
    """
    import json as _json
    import glob as _glob
    role = label.lower().replace("sign in as the", "").replace("sign in as", "").strip()
    words = {w for w in role.split() if len(w) > 3}
    if not words:
        return False
    for f in _glob.glob(str(SERIES / "2 BUILD") + f"/*/{tag}_PACED_LAYERS/_layers.json"):
        for lay in _json.load(open(f)).get("layers", []):
            if abs(lay.get("start", -999) - when) > window:
                continue
            have = lay.get("label", "").lower()
            if words and all(w in have for w in words):
                return True
    return False


def run(items, apply_it):
    by = {}
    for it in items:
        lab = label_for(it["script"])
        if not lab:
            print(f"  ! {it['tag']} seg {it['seg']}: no role found in the line — skipped")
            continue
        t = (it["click_times"][0] if it["click_times"] else it["win"][0] + 1.0)
        if already_marked(it["tag"], t, lab):
            print(f"  - {it['tag']} {t:7.1f}s {lab!r} — already has a call-out, skipped")
            continue
        by.setdefault(it["tag"], []).append((round(t, 2), lab))
    dm, ds = donor()
    finished = declared_done()
    total = 0
    for tag, marks in sorted(by.items()):
        if tag in finished:
            print(f"  {tag}: SKIPPED — Saad has declared this one done "
                  f"({len(marks)} label(s) not written)")
            continue
        proj = PROJECT_OF[tag]
        for lbl_t, lbl in marks:
            print(f"  {tag}  {lbl_t:7.1f}s  {lbl!r}")
        total += len(marks)
        if not apply_it:
            continue
        from sa_guard import preflight
        preflight("capcut_write", project=proj)
        p = CAPCUT / proj
        for f in [pathlib.Path(x) for x in
                  glob.glob(str(p / "Timelines/*/draft_info.json"))] + \
                 ([p / "draft_info.json"] if (p / "draft_info.json").exists() else []):
            bak = f.with_suffix(".json.pre_roles")
            if not bak.exists():
                shutil.copy2(f, bak)
            d = json.loads(f.read_text(encoding="utf-8"))
            f.write_text(json.dumps(build(d, dm, ds, marks), ensure_ascii=False),
                         encoding="utf-8")
        # re-read the way CapCut will
        chk = json.load(open(glob.glob(str(p / "Timelines/*/draft_info.json"))[0]))
        got = [t for t in chk["tracks"] if t.get("name") == TRACK]
        assert len(got) == 1 and len(got[0]["segments"]) == len(marks), \
            f"{proj}: expected {len(marks)} role labels, found " \
            f"{len(got[0]['segments']) if got else 0}"
        print(f"  -> {proj}: {len(marks)} label(s) on one '{TRACK}' track, verified")
    print(f"\n{total} role label(s) {'written' if apply_it else 'would be written'}")
    return total


def _test():
    assert label_for("Sign in as the Approver. The queue shows…") == \
        "Sign in as the Approver"
    assert label_for("Sign in as the Editor and open the task list.") == \
        "Sign in as the Editor"
    assert label_for("Now sign out, and sign in as the Support Team.") in \
        ("Sign in as the Support Team", "Sign out")
    assert label_for("Sign in as the Review user. Open the review queue.") == \
        "Sign in as the Reviewer", "unlocked role names must be corrected in the label"
    assert label_for("The status updates automatically.") is None
    dm = {"id": "D", "content": json.dumps(
        {"text": "Sign in as Cashier", "styles": [{"size": 5, "range": [0, 18]}]})}
    ds = {"id": "S", "material_id": "D", "clip": {"transform": {"x": 0, "y": -0.061}},
          "target_timerange": {"start": 0, "duration": 1}}
    draft = {"materials": {"texts": [dm]}, "tracks": [
        {"name": "Captions", "type": "text", "segments": []}]}
    out = build(draft, dm, ds, [(10.0, "Sign in as the Reviewer"),
                                (40.0, "Sign in as the Requester")])
    tr = [t for t in out["tracks"] if t.get("name") == "Role changes"]
    assert len(tr) == 1 and len(tr[0]["segments"]) == 2
    m0 = [m for m in out["materials"]["texts"] if m["id"] != "D"]
    c = json.loads(m0[0]["content"])
    assert c["text"].startswith("Sign in as the")
    assert c["styles"][0]["range"] == [0, len(c["text"])], \
        "the style range must cover the new words, or the styling silently stops mid-label"
    assert tr[0]["segments"][0]["target_timerange"]["start"] == int(10.0 * US)
    # re-running replaces, never stacks
    again = build(out, dm, ds, [(10.0, "Sign in as the Reviewer")])
    tr2 = [t for t in again["tracks"] if t.get("name") == "Role changes"]
    assert len(tr2) == 1 and len(tr2[0]["segments"]) == 1
    assert len([m for m in again["materials"]["texts"] if m["id"] != "D"]) == 1, \
        "replaced labels must not leave orphan materials behind"
    print("sa_rolemark self-check: ok (role extraction, his style cloned, range widened, "
          "idempotent)")


if __name__ == "__main__":
    if "--test" in sys.argv:
        _test()
        sys.exit()
    ap = argparse.ArgumentParser()
    ap.add_argument("--fix", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--items", default="role_items.json",
                    help="JSON list of role-change items (tag, seg, script, click_times, win)")
    a = ap.parse_args()
    if not (a.fix or a.check):
        ap.error("give --check or --fix")
    if a.fix and capcut_open():
        raise SystemExit("CapCut is open — close it first")
    items = json.load(open(a.items))
    run(items, a.fix)
