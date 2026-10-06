#!/usr/bin/env python3
"""Safe dedupe by (name,size) — never deletes the last copy, never hard-deletes.
  sa_dedupe.py <root>                     # dry run within one folder
  sa_dedupe.py <root> --apply             # MOVE dupes to <root>/_DUPES_QUARANTINE
  sa_dedupe.py <root> --against <other>   # drop files in <root> that ALSO exist in <other>
  sa_dedupe.py <root> --against <other> --apply

--against keeps <other> untouched (e.g. OneDrive) and quarantines the <root> copy
(e.g. MacBook), to free local space. Metadata-only (no content read), reversible.
"""
import os, sys, shutil, collections, hashlib

# Path fragments that mark the master copy to keep (comma-separated in DEDUPE_KEEP_HINTS).
KEEP_HINTS = tuple(h for h in os.environ.get("DEDUPE_KEEP_HINTS", "masters").split(",") if h)
USE_HASH = False  # set by --hash; content fingerprint for LOCAL files (no cloud download)

def _is_local(p, size):
    if size == 0: return True
    try: return os.stat(p).st_blocks * 512 >= size  # materialised, not online-only stub
    except OSError: return False

def _key(p, name, size):
    # strongest: content hash for already-downloaded files (catches renames);
    # online-only files fall back to name+size so they're never downloaded.
    if USE_HASH and _is_local(p, size):
        try:
            h = hashlib.blake2b(digest_size=16)
            with open(p, "rb") as fh:
                for chunk in iter(lambda: fh.read(1 << 20), b""): h.update(chunk)
            return ("hash", h.hexdigest(), size)
        except OSError: pass
    return (name, size)

def _walk(root, skip_quar=True):
    quar = os.path.join(root, "_DUPES_QUARANTINE")
    for d, _, fs in os.walk(root):
        if "/.Trash" in d or (skip_quar and d.startswith(quar)): continue
        for f in fs:
            if f.startswith("."): continue
            p = os.path.join(d, f)
            try: size = os.path.getsize(p)
            except OSError: continue
            yield _key(p, f.lower(), size), p

def main():
    if len(sys.argv) < 2:
        sys.exit("usage: sa_dedupe.py <root> [--against <other>] [--apply]")
    root = sys.argv[1].rstrip("/")
    apply = "--apply" in sys.argv
    global USE_HASH
    USE_HASH = "--hash" in sys.argv
    against = None
    if "--against" in sys.argv:
        against = sys.argv[sys.argv.index("--against") + 1].rstrip("/")
    quar = os.path.join(root, "_DUPES_QUARANTINE")
    plan, freed = [], 0

    if against:  # cross-folder: drop root copies that exist in `against`
        other = {k for k, _ in _walk(against)}
        for k, p in _walk(root):
            if k in other:
                plan.append((against, p, k[-1])); freed += k[-1]
    else:  # within-folder dedupe
        groups = collections.defaultdict(list)
        for k, p in _walk(root): groups[k].append(p)
        def rank(p):
            return (0 if any(h in p for h in KEEP_HINTS) else 1, p.count("/"), len(p))
        for k, paths in groups.items():
            if len(paths) < 2: continue
            paths.sort(key=rank)
            for d in paths[1:]:
                plan.append((paths[0], d, k[-1])); freed += k[-1]

    rep = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dedupe_plan.txt")
    rep = os.path.abspath(rep)
    with open(rep, "w") as o:
        o.write(f"{len(plan)} files to remove, ~{freed/1e9:.2f} GB. KEEP shown first.\n\n")
        for keep, drop, s in sorted(plan, key=lambda x: -x[2]):
            o.write(f"[{s/1e6:.1f} MB]\n  KEEP {keep}\n  DROP {drop}\n")
    print(f"{len(plan)} dupes, ~{freed/1e9:.2f} GB -> {rep}")

    if apply:
        moved = 0
        for keep, drop, s in plan:
            rel = os.path.relpath(drop, root)
            dst = os.path.join(quar, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            try: shutil.move(drop, dst); moved += 1
            except OSError as e: print("skip", drop, e)
        print(f"moved {moved} files -> {quar}  (review, then trash it)")
    else:
        print("dry run. review the plan, then re-run with --apply")

if __name__ == "__main__":
    main()
