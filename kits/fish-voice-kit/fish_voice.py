#!/usr/bin/env python3
"""Fish Audio voice kit — turn a text file into spoken lines in your own cloned voice.

Works in any language Fish supports, including Arabic. Everything goes through your own
Fish Audio account, using the free S2.1 Pro model over the official API, so it does not
spend credits. If Fish ever refuses the free model, the kit says so loudly before it
uses the paid one.

Clone only a voice that is yours, or one whose owner has given you explicit permission
or a licence to use it.

SEVERAL KEYS ARE FINE — one per team member or language. Put every key in fish_key.txt,
one per line, and the kit pools the voices from all of them into a single list. You
pick a voice; it works out which key that voice belongs to and uses it automatically.
The key is sent only to Fish Audio and is never printed.

You need two things, and SETUP puts them in place:
  1. fish_key.txt   your Fish Audio API key, or one per line if you have several
  2. lines.txt      the words you want spoken, one line per line

The voice is NOT set by hand — the first time you generate, the kit reads your accounts
and asks which voice to use, then remembers.

Deliberately built on ffmpeg alone for the audio work, so the only Python package needed
is `requests`. No machine-learning install, nothing to compile.
"""
import argparse
import json
import os
import pathlib
import re
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
BASE = "https://api.fish.audio"
FREE_MODEL = "s2.1-pro-free"      # free tier; the paid one is s2.1-pro
PAID_MODEL = "s2.1-pro"
LUFS = -16.0                      # ordinary broadcast speech level
PEAK = -1.5
TAIL = 0.15                       # seconds of silence kept at the end of each line


def die(msg):
    print("\n" + msg + "\n")
    sys.exit(1)


def read_keys():
    """Every API key in fish_key.txt, newest format first.

    A line may be just the key, or `label: key` so the accounts are tellable apart in
    menus — "arabic: sk-fish-..." reads better than "account 2". Lines starting with #
    are ignored, so the file can explain itself to whoever fills it in.
    """
    if os.environ.get("FISH_API_KEY", "").strip():
        return [("account", os.environ["FISH_API_KEY"].strip())]
    p = HERE / "fish_key.txt"
    if not p.exists():
        die("Missing fish_key.txt. Double-click SETUP.command first.")
    out = []
    for line in p.read_text(encoding="utf-8-sig").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if ":" in s and not s.startswith("sk-"):
            label, _, k = s.partition(":")
            out.append((label.strip(), k.strip()))
        else:
            out.append((f"account {len(out) + 1}", s))
    if not out:
        die("fish_key.txt is empty — open it, paste your API key, and save (Cmd+S).")
    return out


def need_ffmpeg():
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        die("ffmpeg is not installed. Run SETUP again — it installs it for you.")


def call(method, path, key, model=None, **kw):
    import requests
    h = {"Authorization": f"Bearer {key}"}
    if model:
        h["model"] = model              # Fish picks the model by HEADER, not in the body
    return requests.request(method, BASE + path, headers=h, timeout=180, **kw)


def account_voices(label, key):
    """Every voice on ONE account — the only complete list for that account.

    A public voice can be looked up by anyone, but a private one is visible only to the
    account that owns it. So an account's own key is the single source of truth about
    what it holds; a voice found by searching the public directory is a hint until it is
    checked against this.
    """
    r = call("GET", "/model", key, params={"self": "true", "page_size": 100})
    if r.status_code == 401:
        die(f"The key labelled '{label}' was rejected. Check it in fish_key.txt.")
    items = r.json().get("items", []) if r.status_code == 200 else []
    for m in items:
        m["_account"], m["_key"] = label, key
    return items


def all_voices(keys):
    out = []
    for label, k in keys:
        out.extend(account_voices(label, k))
    return out


def pick_voice(keys, wanted=None):
    """Return (voice_id, key_that_owns_it), confirmed against the accounts.

    Never trusts a stored id on its own: the id is looked up across every configured
    account, which is also how the right key gets chosen when there is more than one.
    """
    mine = all_voices(keys)
    if not mine:
        die("No cloned voices on " + ("these accounts." if len(keys) > 1 else
            "this account.") + "\nClone your own voice (or one you have permission to "
            "use) at fish.audio, or run:  fish_voice.py --clone recording.wav")
    by_id = {m["_id"]: m for m in mine}

    if wanted:
        if wanted not in by_id:
            die(f"Voice {wanted} is not on any of your accounts.")
        return wanted, by_id[wanted]["_key"]

    p = HERE / "my_voice.txt"
    if p.exists():
        for line in p.read_text(encoding="utf-8-sig").splitlines():
            s = line.strip()
            if s and not s.startswith("#"):
                if s in by_id:
                    return s, by_id[s]["_key"]
                print(f"my_voice.txt names {s}, which is not on any of your accounts.\n"
                      f"Ignoring it and asking you instead.\n")
                break

    if len(mine) == 1:
        only = mine[0]
        print(f"Using your only voice: {only.get('title')}\n")
        p.write_text(only["_id"] + "\n", encoding="utf-8")
        return only["_id"], only["_key"]

    print("Which voice should I use?\n")
    multi = len(keys) > 1
    for i, m in enumerate(mine, start=1):
        langs = ",".join(m.get("languages") or []) or "?"
        where = f"   [{m['_account']}]" if multi else ""
        print(f"  {i}. {m.get('title','(no title)')}   ({langs}){where}   "
              f"{m.get('task_count', 0)} generations   made {m.get('created_at','')[:10]}")
    print()
    try:
        choice = mine[int(input("Number: ").strip()) - 1]
    except (ValueError, IndexError, EOFError, KeyboardInterrupt):
        die("Not a valid choice — nothing generated.")
    p.write_text(choice["_id"] + "\n", encoding="utf-8")
    print(f"\nSaved '{choice.get('title')}' into my_voice.txt. "
          f"Delete that file to be asked again.\n")
    return choice["_id"], choice["_key"]


def speak(key, voice, text, out_mp3, model=FREE_MODEL, speed=1.0, temperature=0.7,
          top_p=0.7):
    """One line -> one mp3, tidied and levelled."""
    body = {"text": text, "reference_id": voice, "format": "wav", "chunk_length": 300,
            "normalize": True, "latency": "normal",
            "temperature": temperature, "top_p": top_p,
            "prosody": {"speed": speed, "volume": 0, "normalize_loudness": True}}
    r = call("POST", "/v1/tts", key, model=model, json=body)
    if r.status_code in (402, 403) and model == FREE_MODEL:
        # Never fall through to the paid model silently — that is someone's money.
        print(f"  ! the free model was refused ({r.status_code}); using {PAID_MODEL}, "
              f"WHICH IS CHARGED")
        model = PAID_MODEL
        r = call("POST", "/v1/tts", key, model=model, json=body)
    if r.status_code != 200:
        die(f"Fish Audio said {r.status_code}: {r.text[:300]}")
    raw = pathlib.Path(str(out_mp3) + ".raw.wav")
    raw.write_bytes(r.content)
    # Trim the trailing silence (reverse, cut the new leading silence, reverse back) and
    # set an even loudness, so no line comes out quieter than its neighbours.
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", str(raw), "-af",
         f"areverse,silenceremove=start_periods=1:start_silence={TAIL}:"
         f"start_threshold=-45dB,areverse,loudnorm=I={LUFS}:TP={PEAK}:LRA=11",
         "-b:a", "192k", str(out_mp3)], check=True)
    raw.unlink(missing_ok=True)
    return model


def load_fixes():
    """Pronunciation respellings, from pronunciation.txt: `written form => say it like`.

    The reliable cure for a mispronounced word in any TTS is to respell it the way it
    should sound, in the same script — vowelled Arabic for a word the model guesses wrong,
    words instead of digits for numbers, an Arabic transliteration for a Latin brand name.
    Each fix, once added, applies to every line generated from then on. That is the whole
    learning loop: a word only has to be got wrong once.
    """
    p = HERE / "pronunciation.txt"
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8-sig").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=>" not in s:
            continue
        a, _, b = s.partition("=>")
        if a.strip():
            out.append((a.strip(), b.strip()))
    return out


def apply_fixes(text, fixes):
    used = []
    for wrong, right in fixes:
        if wrong in text:
            text = text.replace(wrong, right)
            used.append(wrong)
    return text, used


AR_MARKS = re.compile(r"[\u064B-\u0652\u0640]")   # tashkeel + tatweel


def normalise(s):
    """Flatten the differences that do not change how a word sounds, so the comparison
    reports real mismatches instead of spelling variants: Arabic diacritics, the alef
    forms, taa marbuta, and all punctuation in either script."""
    s = AR_MARKS.sub("", s)
    s = re.sub(r"[\u0623\u0625\u0622\u0671]", "\u0627", s)   # alef forms -> bare alef
    s = (s.replace("\u0629", "\u0647").replace("\u0649", "\u064A")   # taa marbuta, alef maqsura
          .replace("\u0624", "\u0648").replace("\u0626", "\u064A"))  # hamza seats
    s = re.sub(r"[^\w\s\u0600-\u06FF]", " ", s)   # keep the Arabic block
    return " ".join(s.lower().split())


_ASR_OFF = False        # set once we learn this account cannot use speech-to-text


def transcribe(key, path, language=None):
    """Fish's own speech-to-text.

    IMPORTANT: /v1/asr is billed against API credit and is NOT covered by the free
    s2.1-pro-free model — a free account gets 402 back (checked September 2026). So the read-back
    check switches itself off, once, with a message. It must never fail quietly: a check
    that silently does nothing is worse than no check, because it looks like a pass.
    """
    global _ASR_OFF
    if _ASR_OFF:
        return None
    data = {"ignore_timestamps": "true"}
    if language:
        data["language"] = language
    with open(path, "rb") as fh:
        r = call("POST", "/v1/asr", key, data=data,
                 files=[("audio", (pathlib.Path(path).name, fh, "audio/mpeg"))])
    if r.status_code == 402:
        _ASR_OFF = True
        print("\n  (Read-back check off: Fish's speech-to-text needs paid API credit,\n"
              "   which the free model does not include. Everything else works as "
              "normal.)\n")
        return None
    if r.status_code != 200:
        _ASR_OFF = True
        print(f"\n  (Read-back check off: speech-to-text returned {r.status_code}.)\n")
        return None
    return r.json().get("text", "")


def check_line(key, path, spoken_text):
    """Did the voice actually say the words? Returns (verdict, what_was_heard).

    THIS IS A SHORTLIST, NOT A VERDICT ON THE SOUND. Speech-to-text is forgiving: it can
    report the right word from a mangled reading, and it can mishear a perfectly good
    one. It catches swallowed and substituted words, which is most of what goes wrong.
    Anything it flags is for a human to listen to, not to act on blindly.
    """
    heard = transcribe(key, path)
    if heard is None:
        return "unchecked", ""
    want, got = normalise(spoken_text), normalise(heard)
    if want == got:
        return "ok", heard
    import difflib
    ratio = difflib.SequenceMatcher(None, want.split(), got.split()).ratio()
    return ("close" if ratio >= 0.8 else "differs"), heard


def name_for(i, text):
    """A readable filename where the language allows one, a plain number where it does
    not. Arabic, Chinese and the like get line_03.mp3 rather than a row of underscores."""
    latin = re.sub(r"[^a-zA-Z0-9]+", "_", text).strip("_").lower()[:34]
    return f"{i:02d}_{latin}.mp3" if len(latin) >= 4 else f"line_{i:02d}.mp3"


def main():
    ap = argparse.ArgumentParser(description="Speak a text file in your cloned voice.")
    ap.add_argument("--list", action="store_true", help="show my cloned voices")
    ap.add_argument("--credit", action="store_true", help="show my account balances")
    ap.add_argument("--clone", help="a recording of your own voice, or one you have "
                    "permission to use, to clone a new voice from")
    ap.add_argument("--title", default="My voice", help="name for the cloned voice")
    ap.add_argument("--say", help="speak one sentence instead of the whole file")
    ap.add_argument("--lines", default="lines.txt")
    ap.add_argument("--outdir", default="output")
    ap.add_argument("--voice", help="voice id, if you already know which one")
    ap.add_argument("--speed", type=float, default=1.0,
                    help="0.8 slower, 1.2 faster (default 1.0)")
    ap.add_argument("--model", default=FREE_MODEL,
                    choices=["s1", "s2-pro", PAID_MODEL, FREE_MODEL])
    ap.add_argument("--no-check", action="store_true",
                    help="skip the read-back check on each line")
    a = ap.parse_args()
    keys = read_keys()

    if a.credit:
        for label, k in keys:
            r = call("GET", "/wallet/self/api-credit", k)
            bal = r.json().get("credit", "?") if r.status_code == 200 else f"error {r.status_code}"
            print(f"  {label:<12} credit {bal}")
        print("\nThe free model works at zero credit — a 0 here is not a problem.")
        return

    if a.list:
        mine = all_voices(keys)
        if not mine:
            print("No voices yet. Clone one on fish.audio, or use --clone.")
        for m in mine:
            langs = ",".join(m.get("languages") or []) or "?"
            print(f"  {m.get('_id')}   {m.get('title','')}   ({langs})   "
                  f"[{m['_account']}]   {m.get('task_count', 0)} generations")
        print("\nNothing to copy by hand — GENERATE asks which one to use the first "
              "time, and remembers it.")
        return

    if a.clone:
        need_ffmpeg()
        f = pathlib.Path(a.clone)
        if not f.exists():
            die(f"No such audio file: {f}")
        label, k = keys[0]
        if len(keys) > 1:
            print("Which account should the new voice go on?\n")
            for i, (lb, _) in enumerate(keys, start=1):
                print(f"  {i}. {lb}")
            try:
                label, k = keys[int(input("\nNumber: ").strip()) - 1]
            except (ValueError, IndexError, EOFError, KeyboardInterrupt):
                die("Not a valid choice — nothing created.")
        r = call("POST", "/model", k,
                 data={"type": "tts", "title": a.title, "train_mode": "fast",
                       "visibility": "private", "enhance_audio_quality": "true"},
                 files=[("voices", (f.name, f.open("rb"), "application/octet-stream"))])
        if r.status_code not in (200, 201):
            die(f"Fish Audio said {r.status_code}: {r.text[:300]}")
        vid = r.json().get("_id")
        (HERE / "my_voice.txt").write_text(str(vid) + "\n", encoding="utf-8")
        print(f"Voice created on {label}: {vid}\nSaved into my_voice.txt — "
              f"you can generate now.")
        return

    need_ffmpeg()
    voice, key = pick_voice(keys, a.voice)
    if a.say:
        texts = [a.say]
    else:
        p = pathlib.Path(a.lines)
        if not p.is_absolute():
            p = HERE / a.lines
        if not p.exists():
            die(f"Missing {a.lines}. Put the words you want spoken in it, one per line.")
        texts = [s.strip() for s in p.read_text(encoding="utf-8-sig").splitlines()
                 if s.strip() and not s.strip().startswith("#")]
    if not texts:
        die("Nothing to say — lines.txt has no text in it yet.")

    out = HERE / a.outdir
    out.mkdir(parents=True, exist_ok=True)
    fixes = load_fixes()
    print(f"Speed {a.speed} · {len(texts)} line(s)"
          f"{f' · {len(fixes)} pronunciation fix(es) loaded' if fixes else ''}\n")
    flagged = []
    for i, t in enumerate(texts, start=1):
        spoken, applied = apply_fixes(t, fixes)
        f = out / name_for(i, t)
        used = speak(key, voice, spoken, f, model=a.model, speed=a.speed)
        bits = []
        if used != FREE_MODEL:
            bits.append(f"{used} — CHARGED")
        if applied:
            bits.append("fixed: " + ", ".join(applied))
        verdict = "skipped"
        if not a.no_check:
            verdict, heard = check_line(key, f, spoken)
            if verdict in ("differs", "close"):
                bits.append(verdict.upper())
                flagged.append((f.name, spoken, heard))
        print(f"  {i:>2}. {f.name}" + (f"   [{' · '.join(bits)}]" if bits else ""))
    print(f"\nDone. {len(texts)} file(s) in the '{a.outdir}' folder.")
    if flagged:
        print(f"\n{len(flagged)} line(s) did not come back as written — listen to these:")
        for n, want, heard in flagged:
            print(f"\n  {n}\n    written: {want}\n    heard:   {heard}")
        print("\nIf a word is genuinely mispronounced, add one line to "
              "pronunciation.txt:\n    the word => how it should sound\n"
              "and every future line is fixed. If it sounds fine, ignore this — the "
              "checker mishears too.")


def _test():
    assert name_for(1, "Sign in as the advisor") == "01_sign_in_as_the_advisor.mp3"
    welcome = "\u0645\u0631\u062d\u0628\u0627 \u0628\u0643\u0645"   # Arabic "welcome"
    assert name_for(3, welcome) == "line_03.mp3"   # Arabic -> numbered
    assert name_for(7, "\u061F\u061F") == "line_07.mp3"   # two Arabic question marks
    assert len(name_for(2, "x" * 200)) <= 42

    # key file parsing: labelled, bare, commented and blank lines
    import tempfile
    global HERE
    keep = HERE
    HERE = pathlib.Path(tempfile.mkdtemp())
    (HERE / "fish_key.txt").write_text(
        "# my keys\n\narabic: sk-fish-AAA\nenglish:sk-fish-BBB\nsk-fish-CCC\n")
    got = read_keys()
    assert got == [("arabic", "sk-fish-AAA"), ("english", "sk-fish-BBB"),
                   ("account 3", "sk-fish-CCC")], got
    HERE = keep
    print("fish_voice self-test: ok (filenames, Arabic fallback, multi-account keys)")


if __name__ == "__main__":
    if "--test" in sys.argv:
        _test()
    else:
        main()
