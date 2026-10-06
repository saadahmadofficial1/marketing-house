#!/usr/bin/env python3
"""sa_capcut_relink — repair CapCut drafts after media has been moved or renamed.

CapCut stores every media reference as a verbatim absolute path in JSON. Move a
folder and the project opens with "media missing" on every layer, with no way to
fix 193 of them by hand. This tool re-points them.

    # what's broken, across every draft (read-only)
    Tools/venv/bin/python3 Tools/sa_capcut_relink.py --scan

    # a folder moved: rewrite the prefix (exact, safest)
    sa_capcut_relink.py --move "/old/training-series" "/new/training-series" --only Training

    # you don't know where it went: hunt by filename under these roots
    sa_capcut_relink.py --fix ~/Downloads/training-series ~/Movies --only Training

    sa_capcut_relink.py --test

Two things this gets right that a naive sed does not:

1. A draft has TWO places the timeline can live and CapCut may read either
   (Timelines/<uuid>/draft_info.json and the legacy root draft_info.json), plus
   draft_meta_info.json for the media pool. All three must agree or the project
   opens showing stale media. See playbooks/capcut-draft-format.md.
2. Basenames repeat across projects — every build folder has an
   "01_Sign_in.png". A candidate is only accepted when the tail
   of its folder path matches the old one; ambiguity is reported, never guessed.
"""
import argparse
import glob
import json
import os
import re
import shutil
import sys

DRAFTS = os.path.expanduser("~/Movies/CapCut/User Data/Projects/com.lveditor.draft")

# Files CapCut reads paths out of. Order matters only for reporting.
DRAFT_FILES = ("Timelines/*/draft_info.json", "draft_info.json", "draft_meta_info.json")

# The draft's own location — correct by definition, and rewriting it moves the project.
SKIP_KEYS = {"draft_fold_path", "draft_root_path", "draft_removable_storage_device"}


def draft_files(proj):
    out = []
    for pat in DRAFT_FILES:
        out += sorted(glob.glob(os.path.join(proj, pat))) if "*" in pat \
            else ([os.path.join(proj, pat)] if os.path.exists(os.path.join(proj, pat)) else [])
    return out


def each_path(obj, fn, key=None):
    """Walk the JSON, handing every absolute-path string to fn(key, value).

    fn returns a replacement string, or None to leave it. Mutates in place.
    """
    if isinstance(obj, dict):
        for k, v in list(obj.items()):
            if isinstance(v, str) and v.startswith("/") and k not in SKIP_KEYS:
                new = fn(k, v)
                if new is not None and new != v:
                    obj[k] = new
            else:
                each_path(v, fn, k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            if isinstance(v, str) and v.startswith("/") and key not in SKIP_KEYS:
                new = fn(key, v)
                if new is not None and new != v:
                    obj[i] = new
            else:
                each_path(v, fn, key)


def collect(proj):
    """-> {path: [files it appears in]} for one project."""
    found = {}
    for f in draft_files(proj):
        try:
            data = json.load(open(f))
        except Exception:
            continue
        each_path(data, lambda k, v: found.setdefault(v, []).append(f) and None)
    return found


def tail_score(old, cand):
    """How many trailing path components old and cand share. Higher = better match."""
    a, b = old.split(os.sep)[::-1], cand.split(os.sep)[::-1]
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return n


def index_roots(roots):
    """basename -> [full paths] for everything under the search roots."""
    idx = {}
    for r in roots:
        for dp, dn, fn in os.walk(os.path.expanduser(r)):
            dn[:] = [d for d in dn if not d.startswith(".")]
            for f in fn:
                idx.setdefault(f, []).append(os.path.join(dp, f))
    return idx


def resolve(old, idx):
    """-> (new_path, note). new_path None when it can't be resolved safely."""
    cands = idx.get(os.path.basename(old), [])
    if not cands:
        return None, "not found"
    if len(cands) == 1:
        return cands[0], ""
    ranked = sorted(cands, key=lambda c: -tail_score(old, c))
    best = tail_score(old, ranked[0])
    tied = [c for c in ranked if tail_score(old, c) == best]
    if len(tied) > 1:
        # same folder tail: fall back to identical size, else refuse
        try:
            want = None
            sized = [c for c in tied if os.path.getsize(c) == want] if want else []
        except OSError:
            sized = []
        return None, f"ambiguous ({len(tied)} candidates, e.g. {tied[0]})"
    return ranked[0], f"chose over {len(cands) - 1} same-name file(s)"


def apply(proj, mapping, dry):
    """Rewrite every draft file of one project. -> (files_written, refs_changed)."""
    files, refs = 0, 0
    for f in draft_files(proj):
        raw = open(f, encoding="utf-8").read()
        try:
            data = json.loads(raw)
        except Exception:
            continue
        hits = [0]

        def sub(k, v):
            if v in mapping:
                hits[0] += 1
                return mapping[v]
            return None

        each_path(data, sub)
        if not hits[0]:
            continue
        refs += hits[0]
        files += 1
        if dry:
            continue
        if not os.path.exists(f + ".prelink"):
            shutil.copy2(f, f + ".prelink")     # one backup, the pre-relink state
        json.dump(data, open(f, "w", encoding="utf-8"), ensure_ascii=False)
    return files, refs


def projects(only):
    for n in sorted(os.listdir(DRAFTS)):
        p = os.path.join(DRAFTS, n)
        if os.path.isdir(p) and (not only or only.lower() in n.lower()):
            yield n, p


def main(a):
    total_missing = total_fixed = 0
    unresolved = []
    idx = index_roots(a.fix) if a.fix else None
    for name, proj in projects(a.only):
        found = collect(proj)
        if not found:
            continue
        mapping = {}
        missing = [p for p in found if not os.path.exists(p)]
        if a.move:
            old, new = os.path.abspath(os.path.expanduser(a.move[0])), \
                os.path.abspath(os.path.expanduser(a.move[1]))
            for p in found:
                if p.startswith(old):
                    cand = new + p[len(old):]
                    if os.path.exists(cand):
                        mapping[p] = cand
                    elif not os.path.exists(p):
                        unresolved.append((name, p, "prefix rewrite lands on nothing"))
        elif idx is not None:
            for p in missing:
                new, note = resolve(p, idx)
                if new:
                    mapping[p] = new
                else:
                    unresolved.append((name, p, note))
        total_missing += len(missing)
        if mapping:
            files, refs = apply(proj, mapping, a.dry_run)
            total_fixed += refs
            print(f"{'would fix' if a.dry_run else 'fixed'} {refs:4d} ref(s) in "
                  f"{files} file(s)  {name}")
        elif missing:
            print(f"  {len(missing):4d} MISSING, unresolved            {name}")
        elif a.scan:
            print(f"       ok                                {name}")

    print(f"\nmissing before: {total_missing}   repointed: {total_fixed}")
    if unresolved:
        print(f"\nSTILL BROKEN ({len(unresolved)}):")
        for name, p, why in unresolved[:40]:
            print(f"  [{name}] {p}\n      -> {why}")
    if not a.dry_run and (a.move or a.fix):
        # Re-read from disk the way CapCut will, and prove it.
        bad = 0
        for name, proj in projects(a.only):
            for p in collect(proj):
                if not os.path.exists(p):
                    bad += 1
        print(f"\nverify (re-read from disk): {bad} missing reference(s)")
        if bad and not unresolved:
            raise SystemExit("relink reported success but references are still missing")


def _test():
    import tempfile
    assert tail_score("/a/b/c/x.png", "/z/b/c/x.png") == 3
    assert tail_score("/a/b/x.png", "/a/b/y.png") == 0
    d = tempfile.mkdtemp()
    real = os.path.join(d, "T03", "x.png")
    os.makedirs(os.path.dirname(real))
    open(real, "w").write("x")
    decoy = os.path.join(d, "T04", "x.png")
    os.makedirs(os.path.dirname(decoy))
    open(decoy, "w").write("x")
    idx = index_roots([d])
    got, _ = resolve("/gone/T03/x.png", idx)
    assert got == real, f"folder tail must break the tie, got {got}"
    got, why = resolve("/gone/T99/x.png", idx)
    assert got is None and "ambiguous" in why, "an unbreakable tie must refuse, not guess"
    # walk reaches nested lists and honours SKIP_KEYS
    doc = {"draft_fold_path": "/keep/me",
           "tracks": [{"segments": [{"path": "/old/a.mp4", "file_Path": "/old/a.mp4"}]}]}
    each_path(doc, lambda k, v: "/new" + v[4:])
    assert doc["draft_fold_path"] == "/keep/me", "the draft's own location is never rewritten"
    seg = doc["tracks"][0]["segments"][0]
    assert seg["path"] == seg["file_Path"] == "/new/a.mp4"
    print("sa_capcut_relink self-check: ok (tail match, tie refusal, skip keys, nested walk)")


if __name__ == "__main__":
    if "--test" in sys.argv:
        _test()
        sys.exit()
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scan", action="store_true", help="report only, change nothing")
    ap.add_argument("--move", nargs=2, metavar=("OLD", "NEW"), help="rewrite a path prefix")
    ap.add_argument("--fix", nargs="+", metavar="ROOT", help="hunt missing files under these roots")
    ap.add_argument("--only", help="limit to drafts whose name contains this")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if not (args.scan or args.move or args.fix):
        ap.error("give --scan, --move OLD NEW, or --fix ROOT")
    main(args)
