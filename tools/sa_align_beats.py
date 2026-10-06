#!/usr/bin/env python3
"""Align a finalized lines.txt (one narration beat per line) to the ORIGINAL
recording's timestamped transcript, producing a draft rows.json with per-beat
[src_a, src_b] windows in recording time.

Every role-by-role training video has both:
  - lines.txt        the finalized script Saad approved (wording is frozen)
  - transcript.json  Whisper of the ORIGINAL narrator over the recording, with
                     per-segment start/end — i.e. WHEN each panel/action is on screen

The two say the same things in the same order (the finalized script is a tidy of the
original narration), so a monotonic fuzzy match lines each beat up to the recording
time where its content appears. That time IS the row window.

    sa_align_beats.py "<build folder>"            # writes rows.json (draft)
    sa_align_beats.py "<build folder>" --dry      # print, don't write
    sa_align_beats.py --test

The output is a DRAFT: src_b still needs the freeze-rule nudge (set it just before the
screen changes) during box authoring. But the timing is right, which is the tedious part.
kind defaults to "line"; hand-edit stills/results after.
"""
import json
import pathlib
import re
import sys

STOP = {"the", "a", "an", "and", "or", "to", "of", "for", "in", "on", "is", "are", "be",
        "will", "can", "you", "we", "this", "that", "it", "its", "with", "as", "at",
        "from", "by", "now", "let", "us", "here", "see", "also", "which", "then", "into",
        "your", "their", "they", "each", "based", "such", "so", "if", "has", "have", "been",
        "these", "those", "there", "was", "were", "do", "does", "up", "out", "all", "any"}


def norm(s):
    """Content words only — the distinctive nouns/verbs carry the alignment signal.
    Rough whisper vs the tidy script share those ("record", "order", "approve",
    "dashboard") even when the phrasing and filler differ."""
    return [w for w in re.sub(r"[^a-z0-9 ]", " ", s.lower()).split() if w not in STOP]


def load_segs(path):
    d = json.loads(pathlib.Path(path).read_text())
    segs = d.get("segments") if isinstance(d, dict) else d
    return [{"start": float(s["start"]), "end": float(s["end"]),
             "toks": norm(s.get("text", ""))} for s in segs]


def score(beat_toks, seg_toks):
    """Fraction of the beat's content words the segment covers. Set-based, so word order
    and filler don't matter; normalising by the beat length (not the union) means a short
    filler segment that happens to share one common word can't score high."""
    if not beat_toks or not seg_toks:
        return 0.0
    a, b = set(beat_toks), set(seg_toks)
    return len(a & b) / len(a)


def align(lines, segs):
    """Monotonic global alignment by DP — NOT a greedy pointer.

    The greedy version (superseded 10 Sep) advanced a pointer to the best local match,
    so one shared keyword dragged it forward and every later beat collapsed onto the last
    segment: on one module the word "approval" appears for BOTH an early planning approval
    and a later PO approval, so an early beat leapt to the late segment and every beat
    after it collapsed onto the last one. A single collision must not be able to do that.

    DP instead finds the assignment of one anchor segment per beat that (a) keeps anchors
    non-decreasing (order preserved) and (b) maximises the TOTAL similarity across all
    beats — so a locally tempting but globally wrong jump is rejected because it strands
    everything after it. Segments with no beat are simply skipped (the original narration
    has filler the tidy script drops). O(beats x segs)."""
    B, S = len(lines), len(segs)
    if not B or not S:
        return [(0.0, 0.0)] * B
    bt = [norm(l) for l in lines]
    sim = [[score(bt[i], segs[j]["toks"]) for j in range(S)] for i in range(B)]
    NEG = float("-inf")
    dp = [[NEG] * S for _ in range(B)]
    back = [[-1] * S for _ in range(B)]
    dp[0] = sim[0][:]                               # beat 0 may anchor at any segment
    for i in range(1, B):
        best_prev, best_j = NEG, -1                 # running prefix-max of dp[i-1][0..j]
        for j in range(S):
            if dp[i - 1][j] > best_prev:
                best_prev, best_j = dp[i - 1][j], j
            if best_prev > NEG:                     # beat i anchors at j, i-1 at best_j<=j
                dp[i][j] = sim[i][j] + best_prev
                back[i][j] = best_j
    # backtrack from the best final anchor
    anchors = [0] * B
    j = max(range(S), key=lambda k: dp[B - 1][k])
    for i in range(B - 1, -1, -1):
        anchors[i] = j
        j = back[i][j] if i > 0 else -1
        if j < 0 and i > 0:
            j = anchors[i]                          # degenerate: share the segment
    rows = []
    for i in range(B):
        a = segs[anchors[i]]["start"]
        # end the window at the next beat's anchor (its screen), else this segment's end
        nxt = anchors[i + 1] if i + 1 < B else None
        b = segs[nxt]["start"] if nxt is not None and nxt > anchors[i] else segs[anchors[i]]["end"]
        rows.append((round(a, 2), round(b, 2)))
    return rows


def build(folder, dry=False):
    folder = pathlib.Path(folder)
    lines = [l for l in (folder / "lines.txt").read_text().splitlines() if l.strip()]
    segs = load_segs(folder / "transcript.json")
    pairs = align(lines, segs)
    rows = [[a, b, i, "line"] for i, (a, b) in enumerate(pairs)]
    out = {"rows": rows}
    txt = json.dumps(out, indent=1)
    if dry:
        for i, (a, b) in enumerate(pairs):
            print(f"  [{i:2}] {a:7.2f} -> {b:7.2f}  {lines[i][:64]}")
        # flag any non-monotonic or zero-length window — those need a hand look
        bad = [i for i, (a, b) in enumerate(pairs) if b <= a]
        if bad:
            print(f"  ! {len(bad)} zero/negative windows (hand-check): {bad}")
        return out
    (folder / "rows.json").write_text(txt)
    print(f"wrote {len(rows)} rows -> {folder/'rows.json'}")
    return out


def _test():
    segs = [
        {"start": 0, "end": 3, "text": "today we create a record in the system"},
        {"start": 3, "end": 6, "text": "first sign in as the editor user"},
        {"start": 6, "end": 9, "text": "the dashboard opens with the filters on top"},
        {"start": 9, "end": 12, "text": "total items and total orders are shown"},
    ]
    lines = ["Sign in as the Editor user.",
             "The filters at the top set what the page reports on.",
             "Total items, total orders open."]
    segd = [{"start": s["start"], "end": s["end"], "toks": norm(s["text"])} for s in segs]
    pairs = align(lines, segd)
    assert len(pairs) == 3
    # beat 1 must land on the "sign in" segment (start 3), not before it
    assert pairs[0][0] == 3, pairs
    # monotonic: each start >= previous start
    assert all(pairs[i][0] >= pairs[i - 1][0] for i in range(1, 3)), pairs
    # beat 3 lands at/after the total-items segment (start 9)
    assert pairs[2][0] >= 9, pairs

    # the regression that killed the greedy version: a keyword ("approve") shared by an
    # EARLY beat and a LATE segment must not drag the early beat forward and collapse the
    # rest. Here beat 0 is an early approval, beat 2 a late one; both say
    # "approve", but they must land on their OWN segments, not both on the late one.
    segs2 = [
        {"start": 10, "end": 13, "text": "send the draft for approval"},
        {"start": 20, "end": 23, "text": "now create the new order"},
        {"start": 40, "end": 43, "text": "approve the order now"},
    ]
    segd2 = [{"start": s["start"], "end": s["end"], "toks": norm(s["text"])} for s in segs2]
    lines2 = ["Send the draft for approval.",
              "Create a new order and pick a vendor.",
              "Select Approve to approve the order."]
    p2 = align(lines2, segd2)
    assert p2[0][0] == 10 and p2[1][0] == 20 and p2[2][0] == 40, \
        f"keyword collision dragged the alignment: {p2}"
    print("sa_align_beats self-check: ok (DP monotonic, no keyword-collision drag)")


if __name__ == "__main__":
    if "--test" in sys.argv:
        _test(); sys.exit()
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    build(args[0], dry="--dry" in sys.argv)
