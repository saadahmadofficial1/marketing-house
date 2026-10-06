#!/usr/bin/env python3
"""What is finished and what is still owed, for a role-by-role training series.

Requirement (15 Sep): log which videos are done and what is left, so the editor can verify it.

Two sources, deliberately kept apart:
  DISK   — read fresh every run: does the timeline exist, how long is it, is the presenter
           intro actually on a track, is the root draft in sync with the timeline file.
           Never hand-typed, so it cannot drift.
  SAAD   — `5 ADMIN/delivered.json`: what HE has reviewed and exported. Nothing on this
           Mac can prove an export that went to OneDrive, so it is recorded from his word
           and labelled as such. Never guess it; never mark something delivered he has
           not said is delivered.

    sa_delivery.py                      the sheet
    sa_delivery.py --done "Module 8"    mark one exported (matches on the name)
    sa_delivery.py --write              also save 5 ADMIN/DELIVERY_STATUS.md
    sa_delivery.py --demo
"""
import datetime
import json
import os
import pathlib
import sys

DRAFTS = pathlib.Path.home() / "Movies/CapCut/User Data/Projects/com.lveditor.draft"
SERIES = pathlib.Path(os.environ.get("TRAINING_ROOT", "~/Downloads/training-series")).expanduser()
STATE = SERIES / "5 ADMIN" / "delivered.json"
SHEET = SERIES / "5 ADMIN" / "DELIVERY_STATUS.md"
# one project that holds several module timelines (listed one row per timeline)
MULTI = os.environ.get("SA_MULTI_TIMELINE_PROJECT", "15 Example")
# CapCut project-name prefix shared by the series (one project per module)
PREFIX = os.environ.get("SA_SERIES_PREFIX", "Module ")


def has_intro(d):
    """A material is not a segment — a slice inherits the parent's material list, so only
    a clip actually ON a track counts (a material-only check once gave a false yes)."""
    vid = {m["id"]: m for m in d["materials"].get("videos", [])}
    return any("INTRO_" in (vid.get(s.get("material_id"), {}).get("path", ""))
               for t in d["tracks"] for s in t.get("segments", []))


def root_synced(project_dir, tl_path, d):
    """A single-timeline project also keeps a root draft_info.json and CapCut can show THAT
    one. One video's root sat at its pre-intro length while the timeline file was
    correct. Multi-timeline projects are exempt — there the root is the parent video."""
    root = project_dir / "draft_info.json"
    if not root.exists() or len(list(project_dir.glob("Timelines/*/draft_info.json"))) != 1:
        return None
    try:
        return abs(json.loads(root.read_text())["duration"] - d["duration"]) < 1000
    except Exception:
        return False


def rows():
    out = []
    if not DRAFTS.exists():
        return out
    for p in sorted(x for x in DRAFTS.iterdir()
                    if x.is_dir() and x.name.startswith(PREFIX) and "PILOT" not in x.name):
        tls = sorted(p.glob("Timelines/*/draft_info.json"))
        if not tls:
            continue
        d = json.loads(tls[0].read_text())
        out.append({"name": p.name.split(" 2026")[0], "secs": d["duration"] / 1e6,
                    "intro": has_intro(d), "sync": root_synced(p, tls[0], d)})
    sl = [x for x in DRAFTS.iterdir() if x.is_dir() and MULTI and MULTI in x.name]
    if sl:
        reg = json.loads((sl[0] / "Timelines/project.json").read_text())
        for t in reg["timelines"]:
            d = json.loads((sl[0] / "Timelines" / t["id"] / "draft_info.json").read_text())
            out.append({"name": "MOD15 · " + t["name"], "secs": d["duration"] / 1e6,
                        "intro": has_intro(d), "sync": None})
    return out


def load():
    try:
        return json.loads(STATE.read_text())
    except Exception:
        return {}


def mark(name):
    s = load()
    hit = [r["name"] for r in rows() if name.lower() in r["name"].lower()]
    if len(hit) != 1:
        sys.exit(f"{name!r} matched {len(hit)}: " + ", ".join(hit) if hit else f"no match for {name!r}")
    s[hit[0]] = datetime.date.today().isoformat()
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(s, indent=1))
    return hit[0]


def sheet(rs, done):
    mm = lambda x: f"{int(x // 60)}:{int(x % 60):02d}"
    L = ["# Role-wise training series — delivery status", "",
         f"_Disk read {datetime.datetime.now():%d %b %Y %H:%M}. "
         f"'Exported' comes from Saad, not from this Mac._", "",
         "| video | length | intro | CapCut in sync | exported |", "|---|---|---|---|---|"]
    notes = done.get("_notes", {})
    for r in rs:
        sync = "—" if r["sync"] is None else ("yes" if r["sync"] else "**STALE**")
        if any(k in r["name"] for k in notes):
            r = dict(r, intro="flag")
        mark_i = "**see note**" if r["intro"] == "flag" else ("yes" if r["intro"] else "**no**")
        L.append(f"| {r['name']} | {mm(r['secs'])} | {mark_i} "
                 f"| {sync} | {done.get(r['name'], '')} |")
    notes = done.get("_notes", {})
    if notes:
        L += ["", "**Watch out for:**"] + [f"- **{k}** — {v}" for k, v in notes.items()]
    left = [r["name"] for r in rs if r["name"] not in done and not r["name"].startswith("_")]
    L += ["", f"**{len(rs) - len(left)} of {len(rs)} exported.**", ""]
    if left:
        L.append("Still to export:")
        L += [f"- {n}" + ("" if next(r["intro"] for r in rs if r["name"] == n)
                          else "  — intro not in the timeline yet") for n in left]
    return "\n".join(L)


def demo():
    """A video Saad has not named must never show as exported."""
    rs = [{"name": "Module A - Role One", "secs": 315.35, "intro": True, "sync": True},
          {"name": "Module B - Role Two", "secs": 405.0, "intro": False, "sync": None}]
    s = sheet(rs, {"Module A - Role One": "2026-01-15",
                   "_notes": {"Module B": "old intro still in place"}})
    assert "1 of 2 exported" in s
    assert "see note" in s and "old intro still in place" in s
    assert "Module B - Role Two" in s.split("Still to export:")[1]
    assert "intro not in the timeline yet" in s
    assert "5:15" in s and "**STALE**" not in s
    print("demo ok")


if __name__ == "__main__":
    if "--demo" in sys.argv:
        demo(); sys.exit(0)
    if "--done" in sys.argv:
        print("marked exported:", mark(sys.argv[sys.argv.index("--done") + 1]))
    rs = rows()
    out = sheet(rs, load())
    print(out)
    if "--write" in sys.argv:
        SHEET.parent.mkdir(parents=True, exist_ok=True)
        SHEET.write_text(out + "\n")
        print("\nwritten: " + str(SHEET))
