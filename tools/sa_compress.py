#!/usr/bin/env python3
"""sa_compress.py — lossless, invisible APFS compression, with a record of every file.

Files stay where they are and open exactly as before (macOS decompresses on read).
Every file compressed is appended to Tools/kpi/compressed_manifest.csv (Saad's rule,
1 Oct 2026: compressing is fine as long as we remember what was compressed).

  Tools/venv/bin/python3 Tools/sa_compress.py PATH... [--min-age-days 7] [--dry-run]
  Tools/venv/bin/python3 Tools/sa_compress.py --selftest

Undo one file:  ditto --nohfsCompression F F.tmp && mv F.tmp F

Only pays off on text-like data (transcripts, logs, JSON, CSV, WAV, PSD, uncompressed raws).
Video, JPEG, PNG, zip are already compressed — skipped by extension.
Skips: files changed in the last N days, files open in any app, files that shrink <10%.
ponytail: shells out to macOS's own `ditto --hfsCompression`; no afsctool install needed.
"""
import argparse, csv, datetime, filecmp, os, stat, subprocess, tempfile, time
from pathlib import Path

MANIFEST = Path(__file__).resolve().parent / "kpi" / "compressed_manifest.csv"
SKIP_EXT = {".mp4", ".mov", ".m4v", ".mkv", ".mxf", ".avi", ".webm", ".mp3", ".m4a", ".aac",
            ".jpg", ".jpeg", ".png", ".heic", ".webp", ".gif", ".zip", ".gz", ".7z", ".rar",
            ".xz", ".zst", ".bz2", ".dmg", ".pkg", ".safetensors", ".gguf", ".bin", ".pdf",
            ".arw", ".dng", ".tif", ".tiff",  # tested 1 Oct: Sony ARW + our TIFFs gain 0%
            ".sqlite", ".db", ".sqlite-wal", ".sqlite-shm"}  # dbs: apps hold them open
MIN_SIZE = 256 * 1024


def disk_bytes(p):
    return os.stat(p).st_blocks * 512


def open_files():
    # one lsof snapshot: never swap the inode under an app that's still writing
    out = subprocess.run(["lsof", "-u", str(os.getuid()), "-Fn"], capture_output=True, text=True).stdout
    return {l[1:] for l in out.splitlines() if l.startswith("n/")}


def squash(f):
    """Compress one file in place. Returns (before, after) bytes on disk, or None if skipped."""
    st = os.stat(f)
    tmp = f.with_name("." + f.name + ".sacz")
    if subprocess.run(["ditto", "--hfsCompression", str(f), str(tmp)]).returncode:
        tmp.unlink(missing_ok=True)
        return None
    before, after = st.st_blocks * 512, disk_bytes(tmp)
    unchanged = os.stat(f).st_mtime == st.st_mtime
    if not unchanged or after > before * 0.9 or not filecmp.cmp(f, tmp, shallow=False):
        tmp.unlink()
        return None
    os.replace(tmp, f)
    return before, after


def candidates(paths, min_age_days, busy):
    cutoff = time.time() - min_age_days * 86400
    for root in paths:
        root = Path(root).expanduser()
        walk = [root] if root.is_file() else (Path(d) / n for d, _, ns in os.walk(root) for n in ns)
        for f in walk:
            try:
                st = os.lstat(f)
            except OSError:
                continue
            if (stat.S_ISREG(st.st_mode) and st.st_size >= MIN_SIZE and st.st_mtime < cutoff
                    and not st.st_flags & stat.UF_COMPRESSED and f.suffix.lower() not in SKIP_EXT
                    and not f.name.endswith(".sacz") and str(f) not in busy):
                yield f


def run(paths, min_age_days=7, dry=False):
    busy = open_files()
    new = not MANIFEST.exists()
    saved = n = 0
    with open(MANIFEST, "a", newline="") as fh:
        w = csv.writer(fh)
        if new:
            w.writerow(["date", "path", "before_bytes", "after_bytes"])
        for f in candidates(paths, min_age_days, busy):
            if dry:
                print("would try", f)
                continue
            r = squash(f)
            if r:
                w.writerow([datetime.date.today().isoformat(), str(f), r[0], r[1]])
                fh.flush()
                saved += r[0] - r[1]
                n += 1
    print("compressed %d files, saved %.2f GB  (record: %s)" % (n, saved / 1e9, MANIFEST))
    return saved


def selftest():
    global MANIFEST
    with tempfile.TemporaryDirectory() as d:
        MANIFEST = Path(d) / "m.csv"
        f = Path(d) / "log.txt"
        f.write_text("same line again and again\n" * 200000)
        old = time.time() - 30 * 86400
        os.utime(f, (old, old))
        original = f.read_text()
        assert run([d]) > 0, "should save space on repetitive text"
        assert f.read_text() == original, "content must be identical"
        assert os.stat(f).st_flags & stat.UF_COMPRESSED, "flag must be set"
        assert abs(os.stat(f).st_mtime - old) < 2, "date must be kept"
        assert "log.txt" in MANIFEST.read_text(), "must be recorded"
        assert run([d]) == 0, "second run must skip already-compressed"
    print("selftest ok")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--min-age-days", type=float, default=7)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    selftest() if a.selftest else run(a.paths, a.min_age_days, a.dry_run)
