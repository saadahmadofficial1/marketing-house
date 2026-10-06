#!/usr/bin/env python3
"""sa_terms — make product and role names consistent across a whole training series.

The 7 Aug audit found the same thing named three ways: a role called by an old title in
one video, a key term in lower case in twelve places, a short and a long name for the same
screen three seconds apart in the same video. A trainee reads those as different things.

THE SAFETY RULE THIS TOOL ENFORCES, and the reason it exists as a tool rather than a
find-and-replace: the captions are locked to the recorded voice-over. Changing the CASE of a
word is invisible to the ear and always safe. Changing the WORDS is not — the voice would say
one thing while the screen said another, and fixing it properly means a new voice line and a
re-render, which would throw away any editing Saad has already done on that project.

So: in SRT files this tool refuses any edit that alters the spoken words. It compares the two
strings with case and punctuation stripped, and raises if they differ. Call-out labels are
never spoken, so those may be reworded freely.

    Tools/venv/bin/python3 Tools/sa_terms.py --check      # what would change
    Tools/venv/bin/python3 Tools/sa_terms.py --fix
    Tools/venv/bin/python3 Tools/sa_terms.py --test
"""
import argparse
import glob
import json
import os
import pathlib
import re
import shutil
import sys

BUILD = pathlib.Path(os.environ.get("TRAINING_ROOT", "~/Downloads/training-series")).expanduser() / "2 BUILD"

# Case-only corrections. Safe everywhere, including captions, because the ear cannot hear a
# capital letter. Longest first so "Visitor Access Pass" wins before "Access Pass".
# Example glossary: replace with your own product's locked terms.
CASING = [
    "Visitor Access Pass", "Access Pass", "Support Ticket", "Support Tickets", "Help Desk",
    "Reviewer", "Approver",
]

# Wording corrections. Call-out labels ONLY — these change what is said, so a caption
# carrying one would no longer match the voice.
LABEL_ONLY = {
    "Approval user": "Approver",
    "Review user": "Reviewer",
    "Helpdesk": "Help Desk",
}


def spoken(s):
    """What the ear hears: words only, no case, no punctuation."""
    return re.sub(r"[^a-z0-9 ]", " ", s.lower()).split()


def fix_casing(text):
    """Apply the case-only corrections. -> corrected text."""
    out = text
    for term in sorted(CASING, key=len, reverse=True):
        # match the same words in any case, but never inside a longer word
        out = re.sub(rf"(?<![A-Za-z]){re.escape(term)}(?![A-Za-z])", term, out,
                     flags=re.IGNORECASE)
    return out


def fix_label(text):
    """Call-out labels may be reworded as well as recased."""
    out = text
    for wrong, right in LABEL_ONLY.items():
        out = re.sub(rf"(?<![A-Za-z]){re.escape(wrong)}(?![A-Za-z])", right, out,
                     flags=re.IGNORECASE)
    return fix_casing(out)


def srt_blocks(path):
    return open(path, encoding="utf-8").read().strip().split("\n\n")


def do_srt(path, apply_it):
    """Recase caption text. Raises rather than let a spoken word change."""
    blocks, changed, out = srt_blocks(path), 0, []
    for b in blocks:
        lines = b.split("\n")
        if len(lines) < 3:
            out.append(b)
            continue
        body = "\n".join(lines[2:])
        new = fix_casing(body)
        if new != body:
            if spoken(new) != spoken(body):
                raise SystemExit(
                    f"{path}: refusing — this would change the spoken words, not just the "
                    f"case.\n  was: {body}\n  now: {new}\n"
                    f"That needs a new voice line and a re-render, not a text edit.")
            changed += 1
        out.append("\n".join(lines[:2] + [new]))
    if changed and apply_it:
        bak = path + ".pre_terms"
        if not os.path.exists(bak):
            shutil.copy2(path, bak)
        open(path, "w", encoding="utf-8").write("\n\n".join(out) + "\n")
    return changed


def do_stepmarks(path, apply_it):
    """Call-out labels: recase and reword."""
    d = json.load(open(path, encoding="utf-8"))
    steps = d.get("steps", d if isinstance(d, list) else [])
    changed = []
    for s in steps:
        if not isinstance(s, dict) or "label" not in s:
            continue
        new = fix_label(s["label"])
        if new != s["label"]:
            changed.append((s["label"], new))
            if apply_it:
                s["label"] = new
    if changed and apply_it:
        bak = path + ".pre_terms"
        if not os.path.exists(bak):
            shutil.copy2(path, bak)
        json.dump(d, open(path, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    return changed


def run(apply_it):
    caps = labels = 0
    for f in sorted(glob.glob(str(BUILD / "*" / "T*.srt"))):
        n = do_srt(f, apply_it)
        if n:
            caps += n
            print(f"  {os.path.basename(f):10s} {n} caption(s) recased")
    for f in sorted(glob.glob(str(BUILD / "*" / "T*_stepmarks.json"))):
        ch = do_stepmarks(f, apply_it)
        for was, now in ch:
            print(f"  {os.path.basename(f):22s} \"{was}\" -> \"{now}\"")
        labels += len(ch)
    verb = "changed" if apply_it else "would change"
    print(f"\n{caps} caption(s) and {labels} call-out label(s) {verb}")
    if apply_it:
        left = sum(do_srt(f, False) for f in sorted(glob.glob(str(BUILD / "*" / "T*.srt"))))
        print(f"verify: {left} caption(s) still wrong (expected 0)")
        if left:
            raise SystemExit("terminology pass did not converge")
    return caps, labels


def _test():
    assert fix_casing("open the support ticket") == "open the Support Ticket"
    assert fix_casing("the SUPPORT TICKETS list") == "the Support Tickets list"
    assert fix_casing("Access pass issued") == "Access Pass issued"
    # the longer name wins, so "Visitor Access Pass" is cased as one term
    assert fix_casing("open the visitor access pass") == "open the Visitor Access Pass"
    # never touch a word that merely contains a term
    assert fix_casing("supporttickets") == "supporttickets"
    assert fix_casing("Support Tickets") == "Support Tickets"
    # case-only edits leave the spoken words identical — the property the SRT pass relies on
    for s in ("open the support ticket", "the access pass is approved", "access pass issued"):
        assert spoken(fix_casing(s)) == spoken(s), s
    # rewording is allowed on labels and would be caught on captions
    assert fix_label("Sign in as Approval user") == "Sign in as Approver"
    assert spoken(fix_label("Sign in as Approval user")) != spoken("Sign in as Approval user"), \
        "a reworded label really does change the words — which is why captions refuse it"
    assert fix_label("Sign in as the Review user") == "Sign in as the Reviewer"
    assert fix_label("Open Helpdesk") == "Open Help Desk"
    print("sa_terms self-check: ok (casing, longest-first, word boundaries, "
          "spoken-words guard)")


if __name__ == "__main__":
    if "--test" in sys.argv:
        _test()
        sys.exit()
    ap = argparse.ArgumentParser()
    ap.add_argument("--fix", action="store_true")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    if not (a.fix or a.check):
        ap.error("give --check or --fix")
    run(a.fix)
