#!/usr/bin/env python3
"""sa_refmap — "who uses this file?" across every editing app on the Mac.

Every editor stores its media as a verbatim absolute path. Move a file and the
project reopens with media missing — CapCut as missing-media placeholders,
Premiere as offline clips, After Effects as colour bars. So before a single file
is reorganised, this maps every reference, and afterwards it proves nothing was
orphaned.

    sa_refmap.py build                     # scan everything -> refmap.json
    sa_refmap.py check <file>...           # which projects reference these files?
    sa_refmap.py users <dir>               # referenced files under dir, + their projects
    sa_refmap.py missing                   # references whose target no longer exists
    sa_refmap.py free <dir>                # files under dir referenced by NOTHING (safe to move)
    sa_refmap.py --test

Formats, and the trap in each:

  CapCut   JSON. A draft keeps the timeline in TWO places (Timelines/<uuid>/ and
           the legacy root draft_info.json) plus draft_meta_info.json. All must
           agree or CapCut shows stale media. See sa_capcut_relink.py.
  Premiere .prproj is gzipped XML; paths live in <ActualMediaFilePath> and friends
           and may be percent-encoded file:// URLs.
  AE       .aep is RIFX binary. Paths sit in embedded JSON alias blobs as
           "fullpath". Windows-authored templates carry C:\\ paths and resolve
           footage RELATIVE to the .aep — such a project survives a move only if
           its whole folder moves together. Reported as 'relative_ok', not broken.

macOS stores filenames in NFD; Python string literals and JSON are usually NFC.
Every path is normalised before comparison or the same file looks like two.
"""
import argparse
import glob
import gzip
import json
import os
import re
import sys
import unicodedata
from urllib.parse import unquote

HOME = os.path.expanduser("~")
CAPCUT_DRAFTS = os.path.join(HOME, "Movies/CapCut/User Data/Projects/com.lveditor.draft")
# Index location; override with REFMAP_INDEX. Default sits beside the workspace Tools/ folder.
DEFAULT_OUT = os.environ.get("REFMAP_INDEX") or os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Projects", "Mac Organisation", "refmap.json")

# Where project files are hunted for. Library/caches are deliberately excluded.
SCAN_ROOTS = [os.path.join(HOME, d) for d in ("Desktop", "Downloads", "Documents", "Movies")]

PROJECT_EXT = {".prproj": "premiere", ".aep": "after_effects", ".fcpxml": "fcp",
               ".wfp": "filmora", ".drp": "resolve"}

MEDIA_EXT = {".mp4", ".mov", ".m4v", ".avi", ".mxf", ".mkv", ".webm",
             ".png", ".jpg", ".jpeg", ".heic", ".tif", ".tiff", ".gif", ".webp",
             ".psd", ".ai", ".arw", ".dng", ".raw", ".svg",
             ".mp3", ".wav", ".aac", ".m4a", ".aiff", ".flac",
             ".srt", ".ass", ".vtt", ".ttf", ".otf", ".cube"}

# CapCut records the draft's own home here; rewriting these moves the project itself.
SKIP_KEYS = {"draft_fold_path", "draft_root_path", "draft_removable_storage_device",
             "draft_cover", "draft_json_file"}

SKIP_DIRS = {"node_modules", ".git", "venv", "__pycache__", "Adobe Premiere Pro Auto-Save",
             "Adobe After Effects Auto-Save", ".Trash"}


def norm(p):
    """NFC-normalise so an NFD filename off the disk matches an NFC one from JSON."""
    return unicodedata.normalize("NFC", p)


def is_media_path(s):
    """A string worth indexing: absolute POSIX path with a media extension."""
    if not isinstance(s, str) or len(s) < 4 or not s.startswith("/"):
        return False
    return os.path.splitext(s)[1].lower() in MEDIA_EXT


# ---------------------------------------------------------------- scanners

def scan_json_paths(path):
    """Every absolute media path inside a JSON file (CapCut drafts, pipeline sidecars)."""
    out = []
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            data = json.load(fh)
    except Exception:
        return out

    def walk(obj, key=None):
        if isinstance(obj, dict):
            for k, v in obj.items():
                walk(v, k)
        elif isinstance(obj, list):
            for v in obj:
                walk(v, key)
        elif key not in SKIP_KEYS and is_media_path(obj):
            out.append(norm(obj))

    walk(data)
    return out


PRPROJ_TAGS = re.compile(
    r"<(ActualMediaFilePath|FilePath|PeakFilePath|ConformedAudioPath)>([^<]*)</\1>")


def scan_prproj(path):
    """Premiere: gzipped XML (occasionally stored uncompressed)."""
    try:
        with gzip.open(path, "rb") as fh:
            raw = fh.read()
    except Exception:
        try:
            with open(path, "rb") as fh:
                raw = fh.read()
        except Exception:
            return []
    xml = raw.decode("utf-8", errors="replace")
    out = []
    for _tag, val in PRPROJ_TAGS.findall(xml):
        v = unquote(val)
        if v.startswith("file://"):
            v = v[7:]
        if is_media_path(v):
            out.append(norm(v))
    return out


AEP_FULLPATH = re.compile(rb'"fullpath"\s*:\s*"((?:[^"\\]|\\.)*)"')


def scan_aep(path):
    """After Effects: RIFX binary carrying JSON alias blobs with a "fullpath" key.

    Windows-authored templates hold C:\\ paths; AE still opens them because it
    falls back to resolving footage relative to the .aep. Those are returned so
    the caller can see them, but they are not POSIX paths and never match a file
    on this Mac — classify(), not this function, decides they are 'relative_ok'.
    """
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
    except Exception:
        return []
    out = []
    for m in AEP_FULLPATH.findall(raw):
        try:
            v = json.loads('"' + m.decode("utf-8", errors="replace") + '"')
        except Exception:
            continue
        out.append(norm(v))
    return out


def scan_project(path):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".prproj":
        return scan_prproj(path)
    if ext == ".aep":
        return scan_aep(path)
    if ext in (".fcpxml", ".wfp", ".drp"):
        return scan_json_paths(path) or scan_prproj(path)
    return []


# ---------------------------------------------------------------- discovery

def find_project_files():
    """(project_file, kind, project_name) for every editor project on the Mac."""
    found = []

    for proj in sorted(glob.glob(os.path.join(CAPCUT_DRAFTS, "*"))):
        if not os.path.isdir(proj):
            continue
        name = os.path.basename(proj)
        for pat in ("Timelines/*/draft_info.json", "draft_info.json", "draft_meta_info.json"):
            for f in sorted(glob.glob(os.path.join(proj, pat))):
                found.append((f, "capcut", name))

    for root in SCAN_ROOTS:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
            for fn in filenames:
                ext = os.path.splitext(fn)[1].lower()
                full = os.path.join(dirpath, fn)
                if ext in PROJECT_EXT:
                    found.append((full, PROJECT_EXT[ext], os.path.splitext(fn)[0]))
                elif fn.endswith("_layers.json") or fn.endswith(".timing.json"):
                    found.append((full, "sa_sidecar", os.path.basename(dirpath)))
    return found


def classify(ref, project_file):
    """exists | missing | relative_ok (non-POSIX path AE resolves beside the project)."""
    if not ref.startswith("/"):
        sibling = os.path.join(os.path.dirname(project_file), os.path.basename(ref.replace("\\", "/")))
        return "relative_ok" if os.path.exists(sibling) else "missing"
    return "exists" if os.path.exists(ref) else "missing"


def build(out_path):
    refs = {}     # media path -> [ {project, kind, project_file, status} ]
    projects = {}
    for pf, kind, name in find_project_files():
        paths = scan_project(pf) if kind != "capcut" and kind != "sa_sidecar" else scan_json_paths(pf)
        key = f"{kind}:{name}"
        entry = projects.setdefault(key, {"kind": kind, "name": name, "files": [],
                                          "refs": 0, "missing": 0})
        entry["files"].append(pf)
        for p in paths:
            status = classify(p, pf)
            refs.setdefault(p, []).append(
                {"project": key, "kind": kind, "project_file": pf, "status": status})
            entry["refs"] += 1
            if status == "missing":
                entry["missing"] += 1

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    data = {"refs": refs, "projects": projects}
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=1, ensure_ascii=False)

    uniq = len(refs)
    missing = sum(1 for p, u in refs.items() if all(x["status"] == "missing" for x in u))
    print(f"projects        {len(projects)}")
    print(f"unique media    {uniq}")
    print(f"total refs      {sum(len(v) for v in refs.values())}")
    print(f"missing files   {missing}")
    print(f"written         {out_path}")
    return data


def load(out_path):
    with open(out_path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def cmd_check(data, targets):
    refs = data["refs"]
    for t in targets:
        t = norm(os.path.abspath(os.path.expanduser(t)))
        users = refs.get(t, [])
        if not users:
            print(f"FREE      {t}")
        else:
            names = sorted({u["project"] for u in users})
            print(f"USED x{len(users):<4} {t}")
            for n in names:
                print(f"          -> {n}")


def cmd_users(data, d):
    d = norm(os.path.abspath(os.path.expanduser(d))).rstrip("/") + "/"
    hits = {p: u for p, u in data["refs"].items() if p.startswith(d)}
    for p in sorted(hits):
        names = sorted({u["project"] for u in hits[p]})
        print(f"{p}\n    {', '.join(names)}")
    print(f"\n{len(hits)} referenced file(s) under {d}")


def cmd_free(data, d):
    d = os.path.abspath(os.path.expanduser(d))
    used = set(data["refs"])
    n_free = n_used = 0
    for dirpath, dirnames, filenames in os.walk(d):
        dirnames[:] = [x for x in dirnames if x not in SKIP_DIRS and not x.startswith(".")]
        for fn in filenames:
            if fn.startswith("."):
                continue
            full = norm(os.path.join(dirpath, fn))
            if full in used:
                n_used += 1
            else:
                n_free += 1
                print(full)
    print(f"\n{n_free} free, {n_used} referenced under {d}", file=sys.stderr)


def cmd_missing(data):
    rows = []
    for p, users in data["refs"].items():
        miss = [u for u in users if u["status"] == "missing"]
        if miss:
            rows.append((p, sorted({u["project"] for u in miss})))
    for p, names in sorted(rows):
        print(f"{os.path.basename(p)}\n    want: {p}\n    for : {', '.join(names)}")
    print(f"\n{len(rows)} missing file(s)")


def _test():
    import tempfile
    assert norm("a") == "a"
    assert is_media_path("/x/y.mp4") and not is_media_path("/x/y.txt")
    assert not is_media_path("y.mp4"), "relative paths are not indexed"
    assert not is_media_path(None)
    with tempfile.TemporaryDirectory() as td:
        # CapCut-shaped JSON: nested, with a self-location key that must be skipped.
        j = os.path.join(td, "draft_info.json")
        real = os.path.join(td, "clip.mp4")
        open(real, "w").close()
        json.dump({"draft_fold_path": "/should/skip.mp4",
                   "materials": {"videos": [{"path": real},
                                            {"path": "/nope/gone.mov"}]}}, open(j, "w"))
        got = scan_json_paths(j)
        assert real in got and "/nope/gone.mov" in got, got
        assert "/should/skip.mp4" not in got, "self-location key leaked into the index"
        assert classify(real, j) == "exists"
        assert classify("/nope/gone.mov", j) == "missing"
        # A Windows path resolves beside the project -> relative_ok, not missing.
        open(os.path.join(td, "BG T.jpg"), "w").close()
        assert classify(r"C:\Users\U\Footage\BG T.jpg", j) == "relative_ok"
        assert classify(r"C:\Users\U\Footage\absent.jpg", j) == "missing"
        # Premiere: uncompressed XML fallback + percent-decoding.
        pr = os.path.join(td, "p.prproj")
        with open(pr, "w") as fh:
            fh.write(f"<x><ActualMediaFilePath>{os.path.dirname(real)}/clip%20one.mp4"
                     f"</ActualMediaFilePath></x>")
        assert scan_prproj(pr) == [norm(f"{os.path.dirname(real)}/clip one.mp4")]
        # AE: fullpath blob out of binary noise.
        ae = os.path.join(td, "a.aep")
        with open(ae, "wb") as fh:
            fh.write(b'\x00\x01{"fullpath":"/Users/you/Foot\\u00e9/a.mp4"}\xff')
        assert scan_aep(ae) == [norm("/Users/you/Footé/a.mp4")], scan_aep(ae)
    print("ok")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", nargs="?", choices=["build", "check", "users", "missing", "free"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--test", action="store_true")
    a = ap.parse_args()
    if a.test:
        return _test()
    if a.cmd == "build":
        return build(a.out) and None
    if not os.path.exists(a.out):
        sys.exit(f"no index at {a.out} — run: sa_refmap.py build")
    data = load(a.out)
    if a.cmd == "check":
        cmd_check(data, a.args)
    elif a.cmd == "users":
        cmd_users(data, a.args[0])
    elif a.cmd == "free":
        cmd_free(data, a.args[0])
    elif a.cmd == "missing":
        cmd_missing(data)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
