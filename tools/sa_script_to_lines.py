#!/usr/bin/env python3
"""Turn an approved SCRIPTS_TO_SEND prose script into a build lines.txt — one narration beat
per line, the shape build_s0*.py expects.

    sa_script_to_lines.py SCRIPTS_TO_SEND/06_Example_Module.txt vo_folder/lines.txt

It is a DRAFT of the beats: the wording is final (the script is approved) but the split into
one-action-per-line is refined later against the recording during action-map authoring. Voice
clips are per line and reusable in any order, so this is safe to voice immediately.

Rules, learned from hand-cutting an earlier module (9 Sep):
- skip the CAPS title, the ==== rule and the "Title card:" line; the body starts after them.
- join a paragraph's wrapped lines, repairing "walk-\\nin" hyphen breaks.
- one sentence per beat, splitting on . ! ? followed by a capital — but never inside a decimal,
  a code like AB-2026-123, or an abbreviation (e.g., i.e., UAE). "do X, then Y" stays one line;
  the row/marking split happens in the action map, not here.
"""
import re, sys, pathlib

ABBR = {"e.g", "i.e", "vs", "no", "mr", "mrs", "ms", "dr", "st", "etc", "uae", "u.a.e"}

def body(text):
    lines = text.splitlines()
    # find the "Title card:" line; body is everything after it (skipping blanks)
    start = 0
    for i, l in enumerate(lines):
        if l.strip().lower().startswith("title card:"):
            start = i + 1; break
    else:
        # no title card — skip the CAPS header + ==== rule
        start = 0
        while start < len(lines) and (not lines[start].strip() or set(lines[start].strip()) <= set("=")
                                      or lines[start].strip().isupper()):
            start += 1
    return "\n".join(lines[start:])

def paragraphs(b):
    for para in re.split(r"\n\s*\n", b):
        p = para.strip()
        if not p: continue
        p = re.sub(r"-\n(\w)", r"\1", p)      # repair walk-\nin
        p = re.sub(r"\s*\n\s*", " ", p)       # join wrapped lines
        p = re.sub(r"\s{2,}", " ", p).strip()
        if p: yield p

def sentences(p):
    # split after . ! ? when the next non-space is a capital/quote and the token before the
    # dot is not an abbreviation or a bare initial
    out, buf = [], ""
    tokens = re.split(r"(?<=[.!?])(\s+)", p)
    for chunk in tokens:
        if chunk.isspace():
            prev = buf.rstrip()
            last = re.split(r"[\s(]", prev)[-1].rstrip(".!?").lower()
            # keep joined if abbreviation, single letter, or a number (decimals / "50")
            if last in ABBR or len(last) <= 1 or last.isdigit():
                buf += chunk; continue
            out.append(buf.strip()); buf = ""
        else:
            buf += chunk
    if buf.strip(): out.append(buf.strip())
    # merge a stray fragment that starts lowercase back onto the previous sentence
    merged = []
    for s in out:
        if merged and s[:1].islower():
            merged[-1] = merged[-1] + " " + s
        else:
            merged.append(s)
    return merged

def convert(src):
    beats = []
    for p in paragraphs(body(pathlib.Path(src).read_text())):
        beats.extend(sentences(p))
    return beats

if __name__ == "__main__":
    src, out = sys.argv[1], sys.argv[2]
    beats = convert(src)
    pathlib.Path(out).write_text("\n".join(beats) + "\n")
    print(f"{len(beats)} beats -> {out}")
    for i, b in enumerate(beats, 1):
        assert len(b) < 320, f"beat {i} too long: {b[:80]}"
    # show the first and last two so the split can be eyeballed
    for b in beats[:2] + ["..."] + beats[-2:]:
        print("  " + b[:96])
