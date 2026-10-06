#!/usr/bin/env python3
"""Collapse a run of narration lines into one, and reindex the whole module behind it.

Saad, 14 Sep, after reviewing a sales module: the narration walked through the sign-in
steps (name, password, login). The rule is that a sign-in gets ONE line —
"Sign in as the Quality Controller." — never the username / account / password / LOGIN steps,
even when the approved script spells them out. Same for every mid-video role switch.

Deleting a narration line is not a one-file edit: line index is the join key across lines.txt,
vo/*.mp3 (position = index), vo/vo_durs.json, rows.json and boxes.json. Getting any one of
them out of step puts every later marking on the wrong screen. This does all five together.

    sa_cutlines.py "<module>" --cut 1-4 --text "Sign in as the Quality Controller." \
                               --audio /tmp/new.mp3 --keepbox 03_account \
                               --label "Quality Controller account"
    sa_cutlines.py "<module>" --cut 3-4                 # pure delete, no replacement line
    sa_cutlines.py "<module>" --plan                    # show what would change, write nothing

--cut A-B keeps index A and removes A+1..B. With --text/--audio, index A's line and voice are
replaced; without them, index A is left alone and only A+1..B go. --keepbox names the ONE
marking from the cut range that survives onto the kept line (the account/role row, per the
standing rule that every module opens on a real sign-in screen with the role marked); every
other marking in the range is dropped.

Run `--plan` first. Always. Then rebuild the module: the caption track, plan and callouts are
all derived from these files and must be regenerated.
"""
import json
import pathlib
import shutil
import subprocess
import sys


def dur(p):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", str(p)], capture_output=True, text=True)
    return round(float(out.stdout.strip()), 3)


def index_map(n, cuts):
    """old index -> new index, or None if the line is removed.

    cuts is a list of (keep, last) pairs; keep survives, keep+1..last are removed.
    """
    removed = set()
    for keep, last in cuts:
        removed.update(range(keep + 1, last + 1))
    m, new = {}, 0
    for old in range(n):
        if old in removed:
            m[old] = None
        else:
            m[old] = new
            new += 1
    return m, removed


def apply(root, cuts, texts, audios, keepboxes, labels, plan_only):
    root = pathlib.Path(root)
    lines = [l.strip() for l in (root / "lines.txt").read_text().splitlines() if l.strip()]
    vo = sorted((root / "vo").glob("*.mp3"))
    rows = json.loads((root / "rows.json").read_text())
    boxes = json.loads((root / "boxes.json").read_text())
    if len(vo) != len(lines):
        sys.exit(f"REFUSING: {len(lines)} lines but {len(vo)} voice clips — already out of step.")

    m, removed = index_map(len(lines), cuts)
    keepset = {k for k, _ in cuts}

    # which boxes survive
    drop_boxes, move_boxes = [], {}
    for name, sp in boxes.items():
        li = sp["line"]
        if li in removed:
            keep_for = next((k for k, last in cuts if k < li <= last), None)
            if keep_for is not None and keepboxes.get(keep_for) == name:
                move_boxes[name] = keep_for      # survives, moves onto the kept line
            else:
                drop_boxes.append(name)

    print(f"  lines {len(lines)} -> {len(lines) - len(removed)}   removing {sorted(removed)}")
    for k, last in cuts:
        print(f"  cut {k}-{last}: keep [{k}] " + (f"replaced by {texts[k]!r}" if k in texts else "unchanged"))
        print(f"       drops lines {list(range(k+1, last+1))}")
        if keepboxes.get(k):
            print(f"       marking kept: {keepboxes[k]}" + (f"  relabelled {labels[k]!r}" if k in labels else ""))
    print(f"  boxes dropped ({len(drop_boxes)}): {drop_boxes}")
    if plan_only:
        print("\n  --plan: nothing written.")
        return 0

    # back everything up once, under one suffix
    for f in ("lines.txt", "rows.json", "boxes.json"):
        shutil.copy2(root / f, root / (f + ".pre_cutlines"))
    if not (root / "vo_backup_pre_cutlines").exists():
        shutil.copytree(root / "vo", root / "vo_backup_pre_cutlines")

    # 1. lines.txt
    new_lines = []
    for old, li in enumerate(lines):
        if m[old] is None:
            continue
        new_lines.append(texts.get(old, li))
    (root / "lines.txt").write_text("\n".join(new_lines) + "\n")

    # 2. voice: rename into place with a temp dir so no clip is clobbered mid-move
    tmp = root / "_vo_new"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir()
    durs = []
    for old, src in enumerate(vo):
        if m[old] is None:
            continue
        newi = m[old]
        slug = "_".join(new_lines[newi].lower().split()[:6])
        slug = "".join(c for c in slug if c.isalnum() or c == "_")[:32]
        dst = tmp / f"{newi+1:02d}_{slug}.mp3"
        shutil.copy2(audios[old] if old in audios else src, dst)
        durs.append(dur(dst))
    shutil.rmtree(root / "vo")
    tmp.rename(root / "vo")
    (root / "vo" / "vo_durs.json").write_text(json.dumps(durs, indent=1))

    # 3. rows.json — drop removed lines, remap the rest
    kept_rows = []
    for r in rows["rows"]:
        li = r[2]
        if li is None:
            kept_rows.append(r); continue
        if m.get(li) is None:
            continue
        r[2] = m[li]
        kept_rows.append(r)
    rows["rows"] = kept_rows
    (root / "rows.json").write_text(json.dumps(rows, indent=1))

    # 4. boxes.json — drop, move, remap
    out = {}
    for name, sp in boxes.items():
        if name in drop_boxes:
            continue
        li = move_boxes[name] if name in move_boxes else sp["line"]
        sp["line"] = m[li]
        if name in move_boxes:
            k = move_boxes[name]
            if k in labels:
                sp["label"] = labels[k]
            if k in texts:                       # cue must match the NEW line
                sp["cue"] = " ".join(texts[k].split()[:4]).rstrip(",.:;")
        out[name] = sp
    (root / "boxes.json").write_text(json.dumps(out, indent=1))

    print(f"\n  written. voice clips now {len(durs)}, boxes {len(out)}.")
    print("  REBUILD the module — captions, plan and callouts all derive from these files.")
    return 0


def main():
    argv = sys.argv[1:]
    if not argv:
        sys.exit(__doc__)
    root = argv[0]
    cuts, texts, audios, keepboxes, labels = [], {}, {}, {}, {}
    i = 1
    cur = None
    while i < len(argv):
        a = argv[i]
        if a == "--cut":
            lo, hi = argv[i + 1].split("-")
            cur = int(lo)
            cuts.append((cur, int(hi))); i += 2
        elif a == "--text":
            texts[cur] = argv[i + 1]; i += 2
        elif a == "--audio":
            audios[cur] = argv[i + 1]; i += 2
        elif a == "--keepbox":
            keepboxes[cur] = argv[i + 1]; i += 2
        elif a == "--label":
            labels[cur] = argv[i + 1]; i += 2
        elif a == "--plan":
            i += 1
        else:
            sys.exit(f"unknown arg {a}")
    return apply(root, cuts, texts, audios, keepboxes, labels, "--plan" in argv)


def demo():
    """Self-check: the index map is what every other file is remapped through."""
    m, removed = index_map(10, [(1, 4), (7, 8)])
    assert removed == {2, 3, 4, 8}, removed
    assert m[0] == 0 and m[1] == 1          # 0 and the kept line survive in place
    assert m[2] is None and m[4] is None    # cut range gone
    assert m[5] == 2 and m[6] == 3          # everything after shifts down by 3
    assert m[7] == 4 and m[8] is None
    assert m[9] == 5                        # and by 4 after the second cut
    assert sorted(v for v in m.values() if v is not None) == list(range(6))
    print("demo ok")


if __name__ == "__main__":
    if "--demo" in sys.argv:
        demo()
    else:
        sys.exit(main())
