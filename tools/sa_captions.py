#!/usr/bin/env python3
"""sa_captions — SRT built from the LOCKED script, timed by forced alignment.

Why not plain ASR (sa_srt.py): a transcript of the voice-over inherits whatever the
recogniser mishears — "SKU" as "skew", "R&D" as "RND", British spellings flattened. For
a scripted training series the wording is already locked in the script, so the caption text must
come from the script and only the TIMING from the audio.

Method: whisper each VO clip with word timestamps, then align the script's words to the
recognised words (difflib on normalised tokens). Cue start/end come from the matched
audio words; the text shown is always the script's.

  Tools/venv/bin/python3 Tools/sa_captions.py plan.json -o video.srt
  Tools/venv/bin/python3 Tools/sa_captions.py --test

plan.json (the same segments as sa_dubcut, plus text):
  {"timing": "T03_PACED.timing.json",
   "segments": [{"n":1, "vo":"vo/01.mp3", "text":"In this video, we'll ..."}, ...]}
"""
import argparse
import difflib
import json
import os
import re
import sys

MAX_CHARS = 46          # one caption line people can actually read
MAX_WORDS = 9
MIN_CUE = 1.0           # never flash a cue shorter than this
LEAD = 0.04             # nudge cues a touch early; feels synced rather than late


def norm(w):
    """Compare-only form: case and punctuation carry no timing information."""
    return re.sub(r"[^a-z0-9&]", "", w.lower())


# A full stop after one of these is not a sentence end: 'Est. Total' is ONE button (found in
# review, 24 Sep: the cue broke as 'Est. | Total' and 'Est.' read as the end of a sentence).
ABBREV = {"est", "approx", "e.g", "i.e", "eg", "ie", "vs", "etc", "incl", "excl", "dept", "qty", "ref",
          "avg", "mr", "mrs", "dr", "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "sept", "oct",
          "nov", "dec", "fig", "inc", "ltd", "amt", "tel", "ext", "pcs", "yrs", "hrs", "mins"}
# Off by default (other callers keep their breaks): prefer a comma when a break has to move, and do
# not end a cue on a word that belongs to the next one ('...to open your | Total Breakdown.').
TIDY_BREAKS = False
DANGLING = {"a", "an", "the", "your", "to", "of", "and", "or", "in", "on", "for", "with", "at", "by",
            "from", "its", "their", "this", "that", "his", "her", "our", "my"}


def abbrev(w, nxt=None):
    """Is w an abbreviation whose full stop does NOT end the sentence? 'No.' only before a number."""
    if not w.endswith(".") or nxt is None:
        return False
    core = w[:-1].lower().lstrip("(\"'")
    return core in ABBREV or (core == "no" and nxt[:1].isdigit())


def glued(a, b):
    """Should these two words stay on the same line?

    Role and record names in a product UI are often two capitalised words — Help Desk,
    Support Ticket, Change Request, Review Lead. Splitting one across two cues reads as two
    different things to a trainee, which is exactly what the series spends its time
    teaching. Keep them together.
    An abbreviation ends in a full stop but is still part of the name ('Est. Total').
    """
    if a == "&" or b == "&":                              # 'Smith & Jones', 'R & D'
        return bool(a) and bool(b) and (a == "&" or a[0].isupper()) and (b == "&" or b[0].isupper())
    return bool(a) and bool(b) and a[0].isupper() and b[0].isupper() and (a[-1].isalnum() or abbrev(a, b))


def _toks(z):
    return [t for t in re.sub(r"[^a-z0-9&]+", " ", z.lower()).split() if t]


def no_breaks(words, keep=()):
    """-> [bool]: True at i = never break between words[i] and words[i+1] - inside a two-word
    capitalised name, right after an abbreviation, or inside any phrase in `keep` (button and
    field names, e.g. the module's marking targets)."""
    nb = [glued(words[i], words[i + 1]) or abbrev(words[i], words[i + 1]) for i in range(len(words) - 1)] + [False]
    toks = [" ".join(_toks(w)) for w in words]
    for ph in keep:
        want = _toks(ph)
        if len(want) < 2:
            continue
        for i in range(len(words) - len(want) + 1):
            if [toks[i + k] for k in range(len(want))] == want:
                for k in range(i, i + len(want) - 1):
                    nb[k] = True
    return nb


def split_cues(text, keep=()):
    """Script text -> caption-sized chunks, breaking at punctuation first.

    The length is checked BEFORE the word goes on, not after. The old order appended the
    word and then noticed the line was too long, so every cue could overshoot by a whole
    word — which is why roughly 80 captions across the series broke Saad's one-line rule
    (found 7 Aug). One bug, not eighty mistakes.

    Never inside a name: a two-word capitalised name, an abbreviation and the word after it
    ('Est. Total'), or a `keep` phrase. When the line is full there, the break moves back
    to the last point outside the name and the name goes to the next cue whole.
    """
    words = text.split()
    nb = no_breaks(words, keep)
    cues, cur = [], []                                    # cur: word indices

    def flush(upto=None):
        k = len(cur) if upto is None else upto
        if k:
            cues.append(" ".join(words[j] for j in cur[:k]))
            del cur[:k]

    for i, w in enumerate(words):
        would = len(" ".join(words[j] for j in cur + [i]))
        if cur and (would > MAX_CHARS or len(cur) + 1 > MAX_WORDS):
            cut = len(cur)                                # break before w ...
            while cut > 0 and nb[cur[cut - 1]]:
                cut -= 1                                  # ... unless that is inside a name
            if cut == 0:                                  # all one capitalised run (a title in
                cut = len(cur) - 1 if len(cur) > 1 and nb[cur[-1]] else len(cur)   # capitals): as before
            if TIDY_BREAKS:
                cut = _tidy(words, cur, cut, nb, i)
            flush(cut)
        cur.append(i)
        if w.endswith((".", "!", "?")) and not nb[i]:
            flush()                                       # a sentence always ends its cue
        elif w.endswith((",", ";", ":", "—")) and not nb[i] and len(" ".join(words[j] for j in cur)) > MAX_CHARS * 0.6:
            flush()
    if cur:
        tail = " ".join(words[j] for j in cur)
        if cues and len(cues[-1]) + 1 + len(tail) <= MAX_CHARS:
            cues[-1] += " " + tail                        # don't leave a 2-word orphan
        else:
            cues.append(tail)
    return cues


def _tidy(words, cur, cut, nb, nxt):
    """TIDY_BREAKS: a break that had to move back goes to the last comma in the line when there is
    one; and a cue never ends on 'your' / 'the' / 'to'... when that word can go with the next.
    A tidier break is taken only when the cue keeps at least two words and what moves on still
    fits one cue with the next word (nxt) - never a one-word cue, never an over-long one."""
    def fits(k):
        rest = [words[j] for j in cur[k:]] + [words[nxt]]
        return k >= 2 and len(" ".join(rest)) <= MAX_CHARS and len(rest) <= MAX_WORDS

    if cut < len(cur):
        commas = [p for p in range(1, cut + 1) if words[cur[p - 1]].endswith((",", ";", ":", "—"))
                  and not nb[cur[p - 1]]]
        if commas and fits(commas[-1]):
            cut = commas[-1]
    while fits(cut - 1) and words[cur[cut - 1]].lower() in DANGLING and not nb[cur[cut - 2]]:
        cut -= 1
    return cut


def align(script_words, heard):
    """Map each script word index -> (start, end) using the recognised words.

    heard = [(word, start, end)]. Unmatched script words inherit their neighbours,
    so a mis-recognised acronym never drops a caption.
    """
    a = [norm(w) for w in script_words]
    b = [norm(w) for w, _, _ in heard]
    times = [None] * len(a)
    for blk in difflib.SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks():
        for k in range(blk.size):
            times[blk.a + k] = (heard[blk.b + k][1], heard[blk.b + k][2])
    # fill gaps by interpolation between the nearest anchored words
    known = [i for i, t in enumerate(times) if t]
    if not known:
        return None
    for i in range(len(times)):
        if times[i]:
            continue
        prev = max([k for k in known if k < i], default=None)
        nxt = min([k for k in known if k > i], default=None)
        if prev is None:
            times[i] = times[known[0]]
        elif nxt is None:
            times[i] = times[known[-1]]
        else:
            s, e = times[prev][1], times[nxt][0]
            span = max(e - s, 0.05) / max(nxt - prev, 1)
            times[i] = (s + span * (i - prev - 1), s + span * (i - prev))
    return times


def ts(t):
    """Seconds -> SRT timestamp. Rounds in whole milliseconds: rounding the
    fractional part on its own emits ",1000" for anything just under a second."""
    ms = int(round(max(0.0, t) * 1000))
    h, rem = divmod(ms, 3600000)
    m, rem = divmod(rem, 60000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def build(plan, model_name="small"):
    from faster_whisper import WhisperModel
    timing = {s["n"]: s for s in json.load(open(plan["timing"]))["segments"]}
    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    cues = []
    for seg in plan["segments"]:
        base = timing[seg["n"]]["start"]
        segs, _ = model.transcribe(seg["vo"], language="en", word_timestamps=True)
        heard = [(w.word.strip(), w.start, w.end) for s in segs for w in (s.words or [])]
        words = seg["text"].split()
        times = align(words, heard) if heard else None
        if not times:                       # no audio words: spread evenly over the clip
            dur = timing[seg["n"]]["vo_dur"]
            times = [(dur * i / len(words), dur * (i + 1) / len(words)) for i in range(len(words))]
        i = 0
        for cue in split_cues(seg["text"]):
            n = len(cue.split())
            st, en = times[i][0], times[min(i + n - 1, len(times) - 1)][1]
            cues.append([base + st - LEAD, base + en, cue])
            i += n
    # no overlaps, no flashes
    for i, c in enumerate(cues):
        if c[1] - c[0] < MIN_CUE:
            c[1] = c[0] + MIN_CUE
        if i + 1 < len(cues) and c[1] > cues[i + 1][0]:
            c[1] = max(c[0] + 0.4, cues[i + 1][0] - 0.02)
    return cues


def read_srt(path):
    """-> [(start, end, text)] from an existing SRT."""
    out = []
    for block in open(path, encoding="utf-8").read().strip().split("\n\n"):
        lines = [l for l in block.strip().split("\n") if l.strip()]
        if len(lines) < 3:
            continue
        a, _, b = lines[1].partition(" --> ")

        def secs(t):
            h, m, rest = t.strip().split(":")
            s, _, ms = rest.partition(",")
            return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000
        out.append((secs(a), secs(b), " ".join(lines[2:]).strip()))
    return out


def resplit(cues, keep=()):
    """Re-cut existing cues to the current line rules, keeping their timing.

    Rebuilding from audio would mean transcribing every voice clip again for hours. The
    cues already sit on word-accurate times, so the words are re-timed by interpolating
    inside each existing cue and then regrouped — exact at every original boundary, and at
    worst a few hundredths out in the middle of one. Pure, so it can be tested.
    """
    words = []
    for a, b, text in cues:
        ws = text.split()
        if not ws:
            continue
        step = (b - a) / len(ws)
        for i, w in enumerate(ws):
            words.append((w, a + i * step, a + (i + 1) * step))
    if not words:
        return []
    out, i = [], 0
    for cue in split_cues(" ".join(w for w, _, _ in words), keep):
        n = len(cue.split())
        s, e = words[i][1], words[min(i + n - 1, len(words) - 1)][2]
        out.append([s, e, cue])
        i += n
    for j, c in enumerate(out):                      # no flashes, no overlaps
        if c[1] - c[0] < MIN_CUE:
            c[1] = c[0] + MIN_CUE
        if j + 1 < len(out) and c[1] > out[j + 1][0]:
            c[1] = max(c[0] + 0.4, out[j + 1][0] - 0.02)
    return out


def write_srt(cues, out):
    with open(out, "w", encoding="utf-8") as f:
        for i, (s, e, t) in enumerate(cues, 1):
            f.write(f"{i}\n{ts(s)} --> {ts(e)}\n{t}\n\n")
    print(f"-> {out}  ({len(cues)} cues, {cues[-1][1]:.1f}s)")


def _test():
    heard = [("in", 0.0, 0.2), ("this", 0.2, 0.4), ("video", 0.4, 0.9)]
    t = align(["In", "this", "video,"], heard)
    assert t[0][0] == 0.0 and t[2][1] == 0.9
    # a word the recogniser got wrong still gets a sane time from its neighbours
    t2 = align(["In", "the", "SKU", "video,"], heard)
    assert all(x is not None for x in t2), "no script word may be left untimed"
    assert t2[1][0] <= t2[2][0] <= t2[3][0], "interpolated times stay in order"
    c = split_cues("Select the Ticket Status. In this example, the status is Open.")
    assert len(c) >= 2 and c[0].endswith("."), "cues break at sentence ends"
    # the rule Saad set: one line, never wrapped. No cue may exceed it, ever.
    long_text = ("In this video, we'll learn how a Support Ticket is processed once the "
                 "Review Lead has completed the check and returned it to the Help "
                 "Desk, who then raises the Change Request.")
    for cue in split_cues(long_text):
        assert len(cue) <= MAX_CHARS, f"cue over {MAX_CHARS} chars: {len(cue)} {cue!r}"
        assert len(cue.split()) <= MAX_WORDS, f"cue over {MAX_WORDS} words: {cue!r}"
    # a two-word product-UI name is never torn across two cues
    joined = " || ".join(split_cues(long_text))
    for term in ("Support Ticket", "Review Lead", "Help Desk", "Change Request"):
        assert term in joined, f"{term} was split across two cues"
    # every word survives the split, in order
    assert " ".join(split_cues(long_text)).split() == long_text.split()
    assert ts(65.5) == "00:01:05,500"
    # re-splitting keeps every word, in order, inside the original time span
    old = [(0.0, 3.0, "We'll learn how a Support Ticket is processed once the Review"),
           (3.0, 6.0, "Lead has completed the check.")]
    new = resplit(old)
    assert " ".join(c[2] for c in new).split() == \
        " ".join(c[2] for c in old).split(), "no word may be lost or reordered"
    assert all(len(c[2]) <= MAX_CHARS for c in new), "and every new cue obeys the line rule"
    assert new[0][0] == 0.0 and abs(new[-1][1] - 6.0) < 1e-6, "the span is unchanged"
    assert all(new[i][1] <= new[i + 1][0] + 1e-9 for i in range(len(new) - 1)), \
        "cues never overlap"
    assert "Review Lead" in " || ".join(c[2] for c in new), \
        "and the name that was split across the old cues is put back together"
    _test_names()
    print("sa_captions self-check: ok (alignment, gap fill, cue split, resplit, timestamps, "
          "never inside a name or after an abbreviation's full stop)")


def _test_names():
    """Found in review, 24 Sep: 'Est. | Total' split across two cues, 'Est.' read as a sentence end."""
    global MAX_CHARS, MAX_WORDS, TIDY_BREAKS
    keep_ = (MAX_CHARS, MAX_WORDS, TIDY_BREAKS)
    try:
        MAX_CHARS, MAX_WORDS = 32, 7                          # the mobile series' settings
        line = "From the dashboard, tap Est. Total to open your Total Breakdown."
        for tidy in (False, True):
            TIDY_BREAKS = tidy
            cues = split_cues(line)
            assert " ".join(cues).split() == line.split(), "no word lost or moved"
            assert any("Est. Total" in c for c in cues), cues
            assert not any(c.endswith("Est.") for c in cues), cues
            assert all(len(c) <= MAX_CHARS for c in cues), cues
        assert split_cues(line) == ["From the dashboard,", "tap Est. Total to open", "your Total Breakdown."], \
            split_cues(line)
        # a tidier break never leaves a one-word cue or pushes the next cue over the limit
        for text in ("From the Help Desk Supervisor Dashboard, click New Request.",
                     "Make sure to fill in all the mandatory fields, including the Account Reference Number.",
                     "The Support Ticket has already been created by the Front Desk Agent and the Reviewer."):
            cues = split_cues(text)
            assert all(len(c) <= MAX_CHARS for c in cues), cues
            assert not any(len(c.split()) == 1 and not c.endswith(".") for c in cues), cues
            assert " ".join(cues).split() == text.split(), cues
        TIDY_BREAKS = False
        # a real sentence end still ends the cue; 'No.' is only an abbreviation before a number
        assert split_cues("Tap Save. Then tap Send.") == ["Tap Save.", "Then tap Send."]
        assert split_cues("Tap No. Then close it.")[0] == "Tap No."
        assert abbrev("No.", "6300") and not abbrev("No.", "Then") and not abbrev("Est.", None)
        # a keep phrase (a button / field name from the module's marks) is never split
        long = "It shows a deal and its win probability too."
        free = split_cues(long)
        assert free[0].endswith("win"), free                              # (it would split here)
        kept = split_cues(long, keep=["Win probability"])
        assert any("win probability" in c for c in kept) and " ".join(kept).split() == long.split(), kept
        # three capitalised words stay together too (the old rule carried only one word)
        cues = split_cues("Here you will find the whole Monthly Activity Summary for your team.")
        assert any("Monthly Activity Summary" in c for c in cues), cues
        assert any("Smith & Jones" in c for c in split_cues("Here, choose the company Smith & Jones Trading Division."))
        # a title in capitals (every word 'a name') breaks as it always did
        MAX_CHARS, MAX_WORDS = 46, 9
        assert split_cues("HOW TO CREATE AND ASSIGN A TICKET AS THE HELP DESK") == \
            ["HOW TO CREATE AND ASSIGN A TICKET AS", "THE HELP DESK"]
    finally:
        MAX_CHARS, MAX_WORDS, TIDY_BREAKS = keep_


if __name__ == "__main__":
    if "--test" in sys.argv:
        _test()
        sys.exit()
    ap = argparse.ArgumentParser()
    ap.add_argument("plan")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--model", default="small")
    a = ap.parse_args()
    os.chdir(os.path.dirname(os.path.abspath(a.plan)) or ".")
    write_srt(build(json.load(open(os.path.basename(a.plan))), a.model), a.out)
