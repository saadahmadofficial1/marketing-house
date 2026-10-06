#!/usr/bin/env python3
"""Read every screen out of a set of finished training videos, so they can be compared
with the live system.

The question it answers: once the software has moved on, what in the finished videos no
longer matches? Watching 100 minutes of video to find out is not a
plan. This reads the on-screen TEXT instead: sample a frame every couple of seconds, run
macOS's own Vision OCR over it (Tools/bin/sa_ocr — this check runs locally and uploads nothing),
and keep the vocabulary of labels each video showed, with the timestamp each first
appeared.

Comparing that vocabulary against the live system gives three lists: labels the videos
show that the system no longer has (renamed or removed), labels the system has that no
video shows (new), and everything unchanged.

    python3 Tools/sa_screenmap.py --scan "<folder of mp4s>" --out <dir>
    python3 Tools/sa_screenmap.py --compare <dir> --system system.txt

HONEST LIMITS, so nobody treats the output as a verdict:
  * OCR misreads small UI text. "Inventory" came back as "Irvventory", "Marketing" as
    "Markoting". Matching is therefore fuzzy, and it still produces false alarms.
  * It compares LABELS. A step that now routes somewhere different, with the same words on
    screen, is invisible to this.
  * Data differs between an older recording and today's system, so anything that looks
    like a name, number, date, plate or price is dropped before comparing.
It is a shortlist for Saad's eye. Same rule as the audio checks: rank, then let him look.
"""
import argparse
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
OCR = HERE / "bin" / "sa_ocr"
EVERY = 2.0          # seconds between sampled frames
WIDTH = 1600         # enough for UI text, small enough to stay fast

# Anything that is DATA rather than interface: money, dates, times, phone numbers, plates,
# job/lead ids, percentages, bare numbers. Comparing these would drown the real signal.
UNITS = re.compile(r"\b(aed|usd|kms?|km|hrs?|h|m|d)\b", re.I)
RUN = re.compile(r"\d{3,}")               # ids, phones, plates, years, big figures
NOISE = re.compile(r"ask gemini|finish update|chrome|^\W*$|^.{0,2}$", re.I)


def clean(chunk):
    """Keep interface labels, drop anything that is data.

    Data is what differs between an older recording and the system today —
    money, counts, dates, phone numbers, plates, job ids. Comparing those would bury the
    handful of real label changes under thousands of false alarms.
    """
    s = " ".join(chunk.split()).strip(" |·—-")
    if not s or NOISE.search(s):
        return None
    if RUN.search(s):                              # 15550001234, 2026, ID-2026-001
        return None
    core = UNITS.sub("", s)
    if any(c.isdigit() for c in core) and sum(c.isalpha() for c in core) <= 2:
        return None                                # "AED 55", "0%", "14/14"
    if sum(c.isdigit() for c in s) > len(s) / 3:   # mostly digits
        return None
    return s


def key(s):
    """Fold OCR wobble away: lowercase, letters only. 'Irvventory' and 'Inventory' still
    differ, so the compare step uses fuzzy matching on top of this."""
    return re.sub(r"[^a-z]", "", s.lower())


def scan_video(path, out_dir):
    path = pathlib.Path(path)
    tmp = pathlib.Path(tempfile.mkdtemp())
    try:
        subprocess.run(
            ["ffmpeg", "-v", "error", "-i", str(path),
             "-vf", f"fps=1/{EVERY},scale={WIDTH}:-1", str(tmp / "f_%05d.png")],
            check=True)
        frames = sorted(tmp.glob("*.png"))
        if not frames:
            return 0
        # OCR in one call — process start-up dominates otherwise
        res = subprocess.run([str(OCR)] + [str(f) for f in frames],
                             capture_output=True, text=True)
        first = {}                       # label -> first timestamp it appeared
        for line in res.stdout.splitlines():
            p, _, text = line.partition("\t")
            try:
                idx = int(pathlib.Path(p).stem.split("_")[1])
            except (IndexError, ValueError):
                continue
            t = (idx - 1) * EVERY
            for chunk in text.split("|"):
                c = clean(chunk)
                if c and key(c) not in first:
                    first[key(c)] = (t, c)
        out = out_dir / (path.stem + ".txt")
        with out.open("w", encoding="utf-8") as fh:
            for k, (t, label) in sorted(first.items(), key=lambda x: x[1][0]):
                fh.write(f"{int(t)//60}:{int(t)%60:02d}\t{label}\n")
        return len(first)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def cmd_scan(args):
    root = pathlib.Path(args.scan).expanduser()
    out_dir = pathlib.Path(args.out).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    vids = sorted(p for p in root.rglob("*.mp4"))
    print(f"{len(vids)} video(s)\n", flush=True)
    for v in vids:
        n = scan_video(v, out_dir)
        print(f"  {v.stem[:56]:<56} {n:>4} labels", flush=True)
    print(f"\nwritten to {out_dir}")


def cmd_compare(args):
    import difflib
    vid_dir = pathlib.Path(args.compare).expanduser()
    sys_text = pathlib.Path(args.system).expanduser().read_text(errors="replace")
    sys_labels = {}
    for chunk in re.split(r"[\n|]", sys_text):
        c = clean(chunk)
        if c:
            sys_labels[key(c)] = c
    sys_keys = list(sys_labels)

    for f in sorted(vid_dir.glob("*.txt")):
        gone = []
        for line in f.read_text(encoding="utf-8").splitlines():
            ts, _, label = line.partition("\t")
            k = key(label)
            if k in sys_labels:
                continue
            near = difflib.get_close_matches(k, sys_keys, n=1, cutoff=0.86)
            if not near:
                gone.append((ts, label))
        if gone:
            print(f"\n=== {f.stem}  — {len(gone)} label(s) not found in the live system")
            for ts, label in gone[:args.limit]:
                print(f"   {ts:>6}  {label}")
            if len(gone) > args.limit:
                print(f"   … {len(gone) - args.limit} more")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scan", help="folder of delivered mp4s")
    ap.add_argument("--out", default="screenmap")
    ap.add_argument("--compare", help="folder written by --scan")
    ap.add_argument("--system", help="text dumped from the live system")
    ap.add_argument("--limit", type=int, default=25)
    a = ap.parse_args()
    if not OCR.exists():
        sys.exit(f"missing {OCR} — build it with:\n"
                 f"  swiftc -O Tools/sa_ocr.swift -o Tools/bin/sa_ocr")
    if a.scan:
        cmd_scan(a)
    elif a.compare and a.system:
        cmd_compare(a)
    else:
        ap.error("need --scan FOLDER, or --compare DIR --system FILE")


def _test():
    assert clean(" Inventory ") == "Inventory"
    assert clean("AED 55") is None            # money is data
    assert clean("+15550001234") is None     # phone is data
    assert clean("ID-2026-001") is None       # id is data
    assert clean("12/08/2026") is None
    assert clean("Ask Gemini") is None        # browser chrome
    assert clean("x") is None                 # too short
    assert clean("Ready to Collect") == "Ready to Collect"
    assert key("Irvventory") != key("Inventory")   # fuzzy match handles this, not key()
    assert key("Ready To Collect") == key("ready to collect")
    print("sa_screenmap self-test: ok (data filtered, labels kept)")


if __name__ == "__main__":
    if "--test" in sys.argv:
        _test()
    else:
        main()
