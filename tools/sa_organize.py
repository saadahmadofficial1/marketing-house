#!/usr/bin/env python3
"""sa_organize — tidy a folder without breaking a single editing project.

    sa_organize.py plan                 # dry run  (default ~/Downloads) -> plan file
    sa_organize.py apply                # move for real, writing an undo journal
    sa_organize.py undo <journal>       # put every file back exactly where it was
    sa_organize.py dupes                # flag same-name + same-size groups (REPORT ONLY)
    sa_organize.py --test

Only LOOSE files in the root of <dir> are bucketed. Folders are left alone: a
folder is a project unit, and Premiere/AE resolve their media relatively, so a
folder survives a move only when it moves whole (Mac Organisation/FINDINGS.md).
Tidying the 1,100+ loose files is the actual mess; moving project folders is
high risk for almost no tidiness gain.

Four things it refuses to move:
  1. anything sa_refmap knows a project references  -> LOCKED
  2. anything changed in the last --min-age hours    -> RECENT (probably in use)
  3. anything whose twin already sits at the target  -> DUPE (flagged, never deleted)
  4. aliases/symlinks, and its own _Organised tree

Nothing is ever deleted. Every move is journalled, and `undo` is exact.
A plain-shell restore script is written next to each journal, so the moves can
be reversed even if Python or this tool is unavailable.
"""
import argparse
import collections
import json
import os
import shutil
import subprocess
import sys
import time
import unicodedata

HOME = os.path.expanduser("~")
TOOLS = os.path.dirname(os.path.abspath(__file__))
# Plans, reports and undo journals; override with ORGANIZE_DIR.
WORK = os.environ.get("ORGANIZE_DIR") or os.path.join(os.path.dirname(TOOLS), "Projects", "Mac Organisation")
REFMAP = os.path.join(TOOLS, "sa_refmap.py")
PYBIN = os.path.join(TOOLS, "venv/bin/python3")
JOURNAL_DIR = os.path.join(WORK, "undo")
BUCKET_DIR = "_Organised"

# ponytail: extension -> bucket. Unlisted extensions land in Other, which is the
# point: a surprise file stays visible instead of being silently filed away.
BUCKETS = {
    "Video":     ".mp4 .mov .mxf .avi .mkv .webm .m4v .mts .m2ts .wmv .flv",
    "Images":    ".png .jpg .jpeg .heic .gif .webp .tif .tiff .bmp .avif",
    "RAW":       ".arw .dng .cr2 .cr3 .nef .raf .orf .rw2 .xmp",
    "Audio":     ".mp3 .wav .aac .m4a .aiff .aif .flac .ogg .opus",
    "Documents": ".pdf .docx .doc .pptx .ppt .xlsx .xls .xlsm .csv .tsv .txt .md .rtf .pages .key .numbers .eml .msg",
    "Design":    ".psd .psb .ai .indd .idml .aep .prproj .drp .sketch .fig .eps .svg .cube .look .ttf .otf .woff .woff2",
    "Archives":  ".zip .rar .7z .tar .gz .tgz .bz2 .dmg .pkg .iso",
    "Web":       ".html .htm .webloc .url",
    "Subtitles": ".srt .vtt .ass .sbv .sub",
    "Code":      ".py .js .ts .json .sh .command .yml .yaml .xml .plist .ipynb",
}
EXT2BUCKET = {e: b for b, exts in BUCKETS.items() for e in exts.split()}
OTHER = "Other"

# Never bucketed, whatever the extension: macOS/Finder bookkeeping.
SKIP_NAMES = {".DS_Store", ".localized", "Icon\r"}


def nfc(s):
    """macOS gives NFD filenames, JSON carries NFC — compare in one form only."""
    return unicodedata.normalize("NFC", s)


def free_set(root):
    """Absolute paths under root that NO editing project references.

    Delegates to sa_refmap.py, which already knows how CapCut, Premiere and
    After Effects each store their paths. Never reimplement that here.
    """
    if not os.path.exists(REFMAP):
        sys.exit(f"missing {REFMAP} — the safety net is mandatory, refusing to plan")
    py = PYBIN if os.path.exists(PYBIN) else sys.executable
    try:
        out = subprocess.run([py, REFMAP, "free", root], capture_output=True,
                             text=True, timeout=1800)
    except subprocess.TimeoutExpired:
        sys.exit("sa_refmap timed out — refusing to guess which files are safe")
    if out.returncode != 0:
        sys.exit(f"sa_refmap failed, refusing to move anything:\n{out.stderr.strip()}")
    return {nfc(l) for l in out.stdout.splitlines() if l.startswith("/")}


def loose_files(root):
    """Files sitting directly in root — not folders, not our own bucket tree."""
    for name in sorted(os.listdir(root)):
        if name in SKIP_NAMES or name.startswith(".") or name == BUCKET_DIR:
            continue
        p = os.path.join(root, name)
        if os.path.islink(p) or not os.path.isfile(p):
            continue
        yield p


def bucket_of(path):
    return EXT2BUCKET.get(os.path.splitext(path)[1].lower(), OTHER)


def build_plan(root, min_age_hours):
    """Decide a destination for every loose file. Pure: touches nothing on disk."""
    free = free_set(root)
    cutoff = time.time() - min_age_hours * 3600
    moves, locked, recent, dupes = [], [], [], []
    taken = {}  # planned destination -> source, so two sources can't claim one name

    for src in loose_files(root):
        if nfc(src) not in free:
            locked.append(src)
            continue
        try:
            st = os.stat(src)
        except OSError:
            continue
        if st.st_mtime > cutoff:
            recent.append(src)
            continue

        bucket = bucket_of(src)
        name = os.path.basename(src)
        dst = os.path.join(root, BUCKET_DIR, bucket, name)

        # An identical twin already filed (same name AND size) is a duplicate:
        # flag it for Saad to review. Never delete, never silently overwrite.
        if os.path.exists(dst) and os.path.getsize(dst) == st.st_size:
            dupes.append((src, dst))
            continue
        dst = _free_name(dst, taken)
        taken[dst] = src
        moves.append((src, dst, st.st_size))

    return {"root": root, "moves": moves, "locked": locked,
            "recent": recent, "dupes": dupes}


def _free_name(dst, taken):
    """' (2)', ' (3)' … until the name is unused on disk and unclaimed in-plan."""
    if not os.path.exists(dst) and dst not in taken:
        return dst
    stem, ext = os.path.splitext(dst)
    n = 2
    while os.path.exists(f"{stem} ({n}){ext}") or f"{stem} ({n}){ext}" in taken:
        n += 1
    return f"{stem} ({n}){ext}"


def _human(n):
    for u in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or u == "TB":
            return f"{n:.0f}{u}" if u == "B" else f"{n:.1f}{u}"
        n /= 1024.0


def render_plan(plan, verbose=False):
    by_bucket = collections.Counter()
    size_by_bucket = collections.Counter()
    for _, dst, size in plan["moves"]:
        b = os.path.basename(os.path.dirname(dst))
        by_bucket[b] += 1
        size_by_bucket[b] += size

    out = [f"PLAN for {plan['root']}", ""]
    out.append(f"  move    {len(plan['moves']):>5}  loose files into {BUCKET_DIR}/")
    for b, n in by_bucket.most_common():
        out.append(f"            {b:<12} {n:>5}  {_human(size_by_bucket[b])}")
    out.append("")
    out.append(f"  LOCKED  {len(plan['locked']):>5}  in use by a project — left exactly where they are")
    out.append(f"  RECENT  {len(plan['recent']):>5}  changed recently — left alone")
    out.append(f"  DUPE    {len(plan['dupes']):>5}  identical twin already filed — flagged, NOT deleted")
    out.append("")
    if verbose:
        out.append("-- moves --")
        out += [f"  {s}\n      -> {d}" for s, d, _ in plan["moves"]]
        out.append("-- locked (in use by a project) --")
        out += [f"  {p}" for p in plan["locked"]]
        out.append("-- duplicates to review --")
        out += [f"  {s}\n      twin of {d}" for s, d in plan["dupes"]]
    return "\n".join(out)


def apply_plan(plan):
    """Move, journalling every step BEFORE it happens so a crash is still undoable."""
    os.makedirs(JOURNAL_DIR, exist_ok=True)
    stamp = time.strftime("%Y-%m-%d_%H%M%S")
    jpath = os.path.join(JOURNAL_DIR, f"undo_{stamp}.jsonl")
    spath = os.path.join(JOURNAL_DIR, f"restore_{stamp}.sh")

    done = 0
    with open(jpath, "w", encoding="utf-8") as j, open(spath, "w", encoding="utf-8") as sh:
        sh.write("#!/bin/sh\n# Emergency restore — puts every file back where it was.\n"
                 "# Run this if sa_organize.py is unavailable:  sh " + spath + "\n"
                 "set -e\n")
        for src, dst, _ in plan["moves"]:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            # Journal first: a line on disk for a move that never happened is
            # harmless (undo skips it); a move with no line is unrecoverable.
            j.write(json.dumps({"src": src, "dst": dst}, ensure_ascii=False) + "\n")
            j.flush()
            os.fsync(j.fileno())
            sh.write(f'mv -n -- "{dst}" "{src}"\n')
            try:
                shutil.move(src, dst)
                done += 1
            except OSError as e:
                print(f"  skipped {src}: {e}", file=sys.stderr)
    os.chmod(spath, 0o755)
    return done, jpath, spath


def undo(jpath):
    """Reverse a journal, newest move first. Never clobbers anything."""
    if not os.path.exists(jpath):
        sys.exit(f"no journal at {jpath}")
    with open(jpath, encoding="utf-8") as fh:
        rows = [json.loads(l) for l in fh if l.strip()]
    back = skipped = 0
    for r in reversed(rows):
        src, dst = r["src"], r["dst"]
        if not os.path.exists(dst):
            skipped += 1
            continue
        if os.path.exists(src):
            print(f"  occupied, left in place: {src}", file=sys.stderr)
            skipped += 1
            continue
        os.makedirs(os.path.dirname(src), exist_ok=True)
        shutil.move(dst, src)
        back += 1
    return back, skipped


# Folders whose contents are application bookkeeping, not Saad's files. Scanning
# them buries the real duplicates under thousands of identical draft_info.json.
DUPE_SKIP_DIRS = {"node_modules", "venv", ".venv", "__pycache__", ".git", "Library",
                  "Timelines", "Resources", "subdraft", "matting", "smart_crop",
                  "Adobe Premiere Pro Auto-Save", "Adobe After Effects Auto-Save"}

# Storage an application owns and rewrites itself. Two CapCut drafts legitimately
# hold identical draft_info.json files; listing them as "duplicates to delete"
# invites destroying a project. Off limits to a by-hand cleanup.
APP_MANAGED = ("/Movies/CapCut/User Data/", "/Library/Containers/",
               "/Library/Application Support/", "/Library/Caches/",
               TOOLS + os.sep, "/.claude/", "/DaVinci Resolve/")


def find_dupes(roots, min_size=1 << 20):
    """Same name + same size across roots. Report only — never touches disk.

    Below min_size the report is all thumbnail and icon noise, so it defaults to
    1MB: the copies actually worth reclaiming.
    """
    if isinstance(roots, str):
        roots = [roots]
    groups = collections.defaultdict(list)
    seen = set()
    for root in roots:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames
                           if d not in DUPE_SKIP_DIRS and not d.startswith(".")]
            for fn in filenames:
                if fn in SKIP_NAMES or fn.startswith("."):
                    continue
                fp = os.path.join(dirpath, fn)
                if os.path.islink(fp) or nfc(fp) in seen:
                    continue
                if any(seg in fp for seg in APP_MANAGED):
                    continue
                seen.add(nfc(fp))
                try:
                    size = os.path.getsize(fp)
                except OSError:
                    continue
                if size >= min_size:
                    groups[(nfc(fn), size)].append(fp)
    return {k: v for k, v in groups.items() if len(v) > 1}


def used_paths():
    """Every path any project references, from the refmap index. {} if absent."""
    idx = os.path.join(WORK, "refmap.json")
    if not os.path.exists(idx):
        return {}
    try:
        with open(idx, encoding="utf-8") as fh:
            return {nfc(k): v for k, v in json.load(fh)["refs"].items()}
    except (OSError, ValueError, KeyError):
        return {}


def render_dupes(dupes, used):
    """Mark each copy IN USE or free, so it is obvious which one is safe to bin."""
    wasted = sum(size * (len(v) - 1) for (_, size), v in dupes.items())
    lines = [f"DUPLICATES — {len(dupes)} groups, {_human(wasted)} held by the extra copies",
             "Report only. Nothing was moved or deleted.",
             "",
             "  IN USE = an editing project points at this copy. Do not delete it.",
             "  free   = no project references it — the safe one to delete.",
             "If every copy says free, keep one and delete the rest.",
             ""]
    for (name, size), paths in sorted(dupes.items(),
                                      key=lambda kv: -kv[0][1] * (len(kv[1]) - 1))[:500]:
        lines.append(f"{name}  ({_human(size)} x{len(paths)})")
        for fp in paths:
            refs = used.get(nfc(fp))
            if refs:
                names = sorted({r.get("project", "?") if isinstance(r, dict) else str(r)
                                for r in refs})
                who = ", ".join(names[:3]) + (f" +{len(names) - 3} more" if len(names) > 3 else "")
                lines.append(f"    IN USE  {fp}\n              <- {who}")
            else:
                lines.append(f"    free    {fp}")
        lines.append("")
    return "\n".join(lines)


def _test():
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        root = os.path.join(td, "dl")
        os.makedirs(root)
        old = time.time() - 90000  # ~25h, older than the default 24h guard

        def mk(name, data=b"x"):
            p = os.path.join(root, name)
            with open(p, "wb") as fh:
                fh.write(data)
            os.utime(p, (old, old))
            return p

        a, b, c = mk("clip.mp4", b"vid"), mk("doc.pdf", b"pdf"), mk("odd.zzz", b"?")
        locked = mk("inuse.mov", b"m")
        fresh = os.path.join(root, "new.mp4")
        with open(fresh, "wb") as fh:
            fh.write(b"n")  # left at "now" -> must be skipped as RECENT

        # Stub the safety net: everything is free except the locked clip.
        globals()["free_set"] = lambda r: {nfc(p) for p in (a, b, c, fresh)}
        globals()["JOURNAL_DIR"] = os.path.join(td, "undo")

        plan = build_plan(root, 24)
        assert len(plan["moves"]) == 3, plan["moves"]
        assert plan["locked"] == [locked], plan["locked"]
        assert plan["recent"] == [fresh], plan["recent"]
        assert bucket_of(a) == "Video" and bucket_of(b) == "Documents"
        assert bucket_of(c) == OTHER

        n, jpath, spath = apply_plan(plan)
        assert n == 3, n
        assert os.path.exists(os.path.join(root, BUCKET_DIR, "Video", "clip.mp4"))
        assert not os.path.exists(a)
        assert os.path.exists(locked) and os.path.exists(fresh), "guarded files must not move"

        back, _ = undo(jpath)
        assert back == 3, back
        assert os.path.exists(a) and os.path.exists(b), "undo must restore exactly"
        assert os.path.exists(spath) and os.access(spath, os.X_OK)

        # A same-name same-size twin is flagged, never overwritten.
        twin = os.path.join(root, BUCKET_DIR, "Video", "clip.mp4")
        os.makedirs(os.path.dirname(twin), exist_ok=True)
        shutil.copy(a, twin)
        assert len(build_plan(root, 24)["dupes"]) == 1
        assert len(find_dupes(root, min_size=0)) >= 1, "the twin pair must show up as a duplicate"

        # Same name but a DIFFERENT size is a different file: suffix, never merge.
        with open(twin, "wb") as fh:
            fh.write(b"different")
        assert not build_plan(root, 24)["dupes"], "different size is not a duplicate"
        assert build_plan(root, 24)["moves"][0][1].endswith("clip (2).mp4")
    print("ok")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", nargs="?", choices=["plan", "apply", "undo", "dupes"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("--root", default=os.path.join(HOME, "Downloads"))
    ap.add_argument("--min-age", type=float, default=24.0,
                    help="hours; files touched more recently are left alone")
    ap.add_argument("-v", "--verbose", action="store_true")
    ap.add_argument("--test", action="store_true")
    a = ap.parse_args()

    if a.test:
        return _test()
    root = os.path.abspath(os.path.expanduser(a.args[0] if a.args and a.cmd != "undo" else a.root))

    if a.cmd == "undo":
        if not a.args:
            js = sorted(f for f in os.listdir(JOURNAL_DIR) if f.endswith(".jsonl")) \
                if os.path.isdir(JOURNAL_DIR) else []
            sys.exit("usage: sa_organize.py undo <journal>\navailable:\n  " +
                     "\n  ".join(os.path.join(JOURNAL_DIR, j) for j in js) if js else
                     "no journals yet — nothing has been moved")
        back, skipped = undo(os.path.abspath(a.args[0]))
        print(f"restored {back} file(s); {skipped} skipped")
        return

    if not os.path.isdir(root):
        sys.exit(f"not a folder: {root}")

    if a.cmd == "dupes":
        roots = [os.path.abspath(os.path.expanduser(x)) for x in a.args] or [root]
        rep = render_dupes(find_dupes(roots), used_paths())
        out = os.path.join(WORK, "DUPES_REVIEW.txt")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(rep + "\n")
        print(rep.split("\n\n")[0])
        print(f"\nfull report -> {out}")
        return

    plan = build_plan(root, a.min_age)
    print(render_plan(plan, a.verbose))
    out = os.path.join(WORK, "organize_plan.txt")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(render_plan(plan, verbose=True) + "\n")
    print(f"\nfull plan -> {out}")

    if a.cmd == "apply":
        if not plan["moves"]:
            print("nothing to move")
            return
        n, jpath, spath = apply_plan(plan)
        print(f"\nmoved {n} file(s)")
        print(f"undo:      {PYBIN} {os.path.abspath(__file__)} undo '{jpath}'")
        print(f"or plain:  sh '{spath}'")
    else:
        print("dry run — nothing moved. Re-run with: apply")


if __name__ == "__main__":
    main()
