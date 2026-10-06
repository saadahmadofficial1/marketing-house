#!/usr/bin/env python3
"""Rebuild a T##_VO_SCRIPT.txt script from what was ACTUALLY generated.

The fault this exists for: blocks get added after the first generation (T19 +2,
T20 +4) and the human-readable script is never updated. Anyone regenerating from
that file loses the added content silently. Truth lives in the locked plans:

    T##_dub.plan.json       block order + labels + source spans
    T##_captions.plan.json  the exact spoken text per block
    vo/NN.mp3               the measured duration

The prose header (pronunciation, length-floor reasoning, reviewer feedback) is the
author's and is preserved verbatim; only the block section below the ==== rule
is rebuilt, plus a stamped SYNCED FACTS panel with measured numbers.

    sa_scriptsync.py <build-folder> [--check]

--check writes nothing and exits 1 if the script is out of sync — for nightly.
"""
import json
import pathlib
import subprocess
import sys
import textwrap

RULE = "=" * 70


def vo_dur(p):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(p)],
        capture_output=True, text=True).stdout.strip()
    return float(out) if out else 0.0


def mmss(s):
    return f"{int(s // 60)}:{s % 60:04.1f}"


def load(folder):
    folder = pathlib.Path(folder)
    tag = next((f.name.split("_")[0] for f in folder.glob("*_dub.plan.json")), None)
    if not tag:
        sys.exit(f"no *_dub.plan.json in {folder}")
    segs = json.loads((folder / f"{tag}_dub.plan.json").read_text())["segments"]
    texts = {s["n"]: s["text"] for s in
             json.loads((folder / f"{tag}_captions.plan.json").read_text())["segments"]}
    return folder, tag, segs, texts


def build(folder, tag, segs, texts):
    script = folder / f"{tag}_VO_SCRIPT.txt"
    header = script.read_text().split(RULE)[0].rstrip() if script.exists() else ""

    total = 0.0
    body = []
    for s in segs:
        d = vo_dur(folder / s["vo"])
        total += d
        body.append(f"[{s['n']:02d} — {s['label'].upper()}]   ({d:.1f}s  ·  {s['vo']})")
        # ponytail: wrap at 92, matches how the originals were hand-written
        body.append(textwrap.fill(texts.get(s["n"], "*** TEXT MISSING FROM CAPTIONS PLAN ***"),
                                  92))
        body.append("")

    facts = [
        "SYNCED FACTS — measured from the generated audio, not estimated.",
        f"  blocks generated : {len(segs)}",
        f"  total narration  : {mmss(total)}",
        f"  source covered   : {segs[0]['src'][0]:.1f}s to {segs[-1]['src'][1]:.1f}s",
        "  Regenerate this panel with Tools/sa_scriptsync.py — never hand-edit the block",
        "  list. If you add a VO block, rerun the sync so this file stays the real script.",
    ]
    return header + "\n" + RULE + "\n" + "\n".join(facts) + "\n" + RULE + "\n\n" + "\n".join(body)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    check = "--check" in sys.argv
    if not args:
        sys.exit(__doc__)
    folder, tag, segs, texts = load(args[0])
    script = folder / f"{tag}_VO_SCRIPT.txt"

    if check:
        old = script.read_text() if script.exists() else ""
        found = old.count("\n[")
        if found != len(segs):
            print(f"{tag}: script lists {found} blocks, {len(segs)} were generated — OUT OF SYNC")
            return 1
        print(f"{tag}: {found} blocks, in sync")
        return 0

    new = build(folder, tag, segs, texts)
    if script.exists():
        script.with_suffix(".txt.bak").write_text(script.read_text())
    script.write_text(new)
    print(f"{tag}: rewrote {script.name} — {len(segs)} blocks "
          f"({'backup: ' + script.name + '.bak' if script.with_suffix('.txt.bak').exists() else 'new'})")
    return 0


def demo():
    """Self-check: a plan with more blocks than the script must fail --check."""
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        d = pathlib.Path(d)
        (d / "TXX_dub.plan.json").write_text(json.dumps({"segments": [
            {"n": 1, "src": [0, 1], "vo": "vo/01.mp3", "label": "a"},
            {"n": 2, "src": [1, 2], "vo": "vo/02.mp3", "label": "b"}]}))
        (d / "TXX_captions.plan.json").write_text(json.dumps({"segments": [
            {"n": 1, "text": "one"}, {"n": 2, "text": "two"}]}))
        (d / "TXX_VO_SCRIPT.txt").write_text("head\n" + RULE + "\n\n[01 — A]\none\n")
        sys.argv = ["x", str(d), "--check"]
        assert main() == 1, "stale script must be reported out of sync"
        _, tag, segs, texts = load(d)
        out = build(d, tag, segs, texts)
        assert out.count("\n[") == 2 and "two" in out and out.startswith("head")
    print("demo ok")


if __name__ == "__main__":
    sys.exit(demo() if "--demo" in sys.argv else main())
