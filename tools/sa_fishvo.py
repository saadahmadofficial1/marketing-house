#!/usr/bin/env python3
"""Narrator voice-over through the Fish Audio API, using a voice model you own or are
licensed to use (FISH_VOICE_ID). Warns before any billed fallback.

Why this exists: driving the voice from the API instead of the web page makes a whole
script one command, and every line gets the same quality gates we already built for the
local clone.

    export FISH_API_KEY=...            (or put the key in ~/.config/fishvo/fish_audio.key)

    sa_fishvo.py --credit                          what the account has left
    sa_fishvo.py --models                          my voices + their ids
    sa_fishvo.py --clone REF.wav --title "Narrator" upload reference -> new voice id
    sa_fishvo.py --voice <id> --say "text" --out line.mp3
    sa_fishvo.py --voice <id> --lines script.txt --outdir "assets/vo"

Two things the API gives us that the web page does not:
  * NO 500-CHARACTER LIMIT. That cap is the web tier's. Saad split a long transcript into
    500-char blocks by hand for the browser — over the API a whole line goes in one call
    (chunk_length only controls internal batching, 100-300).
  * The whole script in one run, each line its own file, ready for the detached-audio
    build Saad asked for on 21 Aug (one line = one draggable clip).

Engine facts checked against docs.fish.audio on 1 Sep 2026, not from memory:
  POST /v1/tts, Bearer auth, model chosen by the `model` HEADER, not the body.
  Models: s1 | s2-pro | s2.1-pro (default) | s2.1-pro-free.
  This tool defaults to the free model while the API accepts it AND, if the API ever
  refuses it, falls back to s2.1-pro while SAYING SO — a silent fall-through would spend
  money nobody chose to spend. Run --credit before any big batch.
  (The UI also offers "Drama 3 (Preview)"; it is not in the API's model list yet.)

What does NOT carry over from other engines: a stability of 0.75 measured elsewhere
means nothing here. Fish's temperature/top_p default to 0.7 and stay there until we have
measured otherwise on Saad's ear, not before.
"""
import argparse
import json
import os
import pathlib
import re
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from sa_clonevo import choppiness, match_level, trim_tail  # noqa: E402  (light imports)

BASE = "https://api.fish.audio"
KEY_FILE = pathlib.Path.home() / ".config/fishvo/fish_audio.key"
FREE_MODEL = "s2.1-pro-free"
PAID_MODEL = "s2.1-pro"
TAKES = 3
# Your trained voice model on fish.audio (list yours with --models). Set it once in the
# environment so nothing account-specific lives in the source.
DEFAULT_VOICE = os.environ.get("FISH_VOICE_ID", "")
# 0.95, measured. Requirement set 1 Sep 2026: narration must not sound slow — the 0.7 a
# web panel had been left at failed that on the first listen. Benchmark: an approved
# narration take runs at 2.74 words/sec (median
# of 61 cues in its .srt, measured per-cue so between-line pauses do not distort it). The same
# three lines through Fish came out at 1.98 w/s at 0.7x, 2.85 at 1.0 and 2.70 at 0.95 —
# so 0.95 matched it, 1.0 ran fast and 0.7 ran slow.
# The panel value was a real observation and still the wrong default: it is where he
# started, not where he landed.
SPEED = 0.95
WORD_MATCH = 0.95           # same bar as the local clone: below this the take misread


def key():
    """Key from the environment or a 0600 file. Never a literal in the source, and never
    echoed — the tool prints how many characters it found, not the key."""
    k = os.environ.get("FISH_API_KEY", "").strip()
    if not k and KEY_FILE.exists():
        k = KEY_FILE.read_text().strip()
    if not k:
        sys.exit(f"No API key. Put it in {KEY_FILE} (chmod 600) or export FISH_API_KEY.")
    return k


def prep_text(text, quiet=False):
    """Bind initialisms so Fish does not pause inside them.

    Review note (21 Aug): the voice paused inside "Q and A", as if it were three separate words.
    Spaced single capitals read as phrase boundaries here ("A" is also a word).
    Hyphens hold them together. This is ENGINE-SPECIFIC — "Q and A" was fine on
    another engine; never assume a spelling transfers between engines.
    """
    out = re.sub(r"\b([A-Z]) and ([A-Z])\b", r"\1-and-\2", text)
    loose = re.findall(r"(?<![\w-])([A-Z])(?![\w-])", out)
    if loose and not quiet:
        print(f"  ! standalone capitals {loose} — listen for a pause; "
              f"fallback spelling is the phonetic one (kyoo, ay)", file=sys.stderr)
    return out


def call(method, path, api_key, model=None, **kw):
    import requests
    h = {"Authorization": f"Bearer {api_key}"}
    if model:
        h["model"] = model
    r = requests.request(method, BASE + path, headers=h, timeout=180, **kw)
    return r


def credit(api_key):
    import requests
    me = requests.get(BASE + "/wallet/self/api-credit",
                      headers={"Authorization": f"Bearer {api_key}"}, timeout=30)
    if me.status_code == 200:
        return me.json()
    return {"error": me.status_code, "body": me.text[:200]}


def models(api_key):
    r = call("GET", "/model", api_key, params={"self": "true", "page_size": 100})
    r.raise_for_status()
    return r.json().get("items", [])


def clone(api_key, ref, title, text=None, visibility="private"):
    """Create the voice from ONE clean continuous reference take of a voice you own or are
    licensed to clone.

    The reference rule: a single continuous 7-15s take, never a splice. A montage of many
    takes is good audio and a bad reference — the model learns every take's different
    acoustic start and stop.
    """
    ref = pathlib.Path(ref)
    files = [("voices", (ref.name, ref.open("rb"), "application/octet-stream"))]
    data = {"type": "tts", "title": title, "train_mode": "fast",
            "visibility": visibility, "enhance_audio_quality": "true"}
    if text:
        data["texts"] = text          # skip ASR when we already know the words
    r = call("POST", "/model", api_key, data=data, files=files)
    r.raise_for_status()
    return r.json()


def speak(api_key, voice, text, out_wav, model=FREE_MODEL, temperature=0.7, top_p=0.7,
          speed=SPEED):
    """One take. Returns the model actually used — the free tier may be refused."""
    body = {"text": text, "reference_id": voice, "format": "wav", "chunk_length": 300,
            "normalize": True, "latency": "normal",
            "temperature": temperature, "top_p": top_p,
            "prosody": {"speed": speed, "volume": 0, "normalize_loudness": True}}
    r = call("POST", "/v1/tts", api_key, model=model, json=body)
    if r.status_code in (402, 403) and model == FREE_MODEL:
        # Free-tier access can end without notice. Say it out loud — a silent fall through
        # to the paid model is money spent without Saad choosing to spend it.
        print(f"  ! {model} refused ({r.status_code}) — falling back to {PAID_MODEL}, "
              f"THIS IS BILLED", file=sys.stderr)
        model = PAID_MODEL
        r = call("POST", "/v1/tts", api_key, model=model, json=body)
    r.raise_for_status()
    pathlib.Path(out_wav).write_bytes(r.content)
    return model


def best_of(api_key, voice, text, out_path, takes=TAKES, whisper=None, **kw):
    """Speak the line a few times, bin any take that says the wrong words, keep the
    smoothest. Same shape as the local clone's best_of — an inconsistent engine only
    becomes production-safe when something checks each take before Saad hears it."""
    import difflib
    out_path = pathlib.Path(out_path)
    # ponytail: apostrophes dropped, not spaced — Whisper writes a possessive company name
    # such as "Smith and Son's", which split to "son s" and failed every correct take.
    def words(t):
        return re.sub(r"[^a-z0-9 ]", " ", re.sub(r"['\u2019]", "", t.lower().replace("&", " and "))).split()
    want = words(text)
    scored, used = [], None
    for i in range(takes):
        tmp = out_path.with_name(f"_{out_path.stem}_take{i}.wav")
        used = speak(api_key, voice, text, tmp, **kw)
        trim_tail(tmp, None)
        ok = True
        if whisper is not None:
            heard = " ".join(s.text for s in whisper.transcribe(str(tmp))[0])
            got = words(heard)
            ok = difflib.SequenceMatcher(None, want, got).ratio() >= WORD_MATCH
        scored.append((not ok, choppiness(tmp), tmp))     # misreads sink to the bottom
    scored.sort()
    bad, chop, keep = scored[0]
    match_level(keep)                                     # the reference voice's loudness profile
    if out_path.suffix.lower() == ".mp3":
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(keep),
                        "-b:a", "192k", str(out_path)], check=True)
        keep.unlink(missing_ok=True)
    else:
        keep.replace(out_path)
    for _, _, p in scored[1:]:
        p.unlink(missing_ok=True)
    return out_path, chop, sum(1 for b, _, _ in scored if b), used


def read_lines(path):
    """One line of script per line of file. Blank lines and # comments skipped, so a
    script file can carry its own notes."""
    out = []
    for raw in pathlib.Path(path).read_text().splitlines():
        s = raw.strip()
        if s and not s.startswith("#"):
            out.append(s)
    return out


def slug(text, n=32):
    return re.sub(r"[^a-z0-9]+", "_", text.lower())[:n].strip("_")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--credit", action="store_true", help="account balance")
    ap.add_argument("--models", action="store_true", help="list my cloned voices")
    ap.add_argument("--clone", help="reference .wav -> create a voice model")
    ap.add_argument("--title", default="Narrator")
    ap.add_argument("--ref-text", help="words in the reference, skips their ASR")
    ap.add_argument("--voice", default=DEFAULT_VOICE,
                    help="voice id (defaults to $FISH_VOICE_ID)")
    ap.add_argument("--say")
    ap.add_argument("--lines", help="text file, one script line per line")
    ap.add_argument("--out", help="output file for --say")
    ap.add_argument("--outdir", default=".")
    ap.add_argument("--takes", type=int, default=TAKES)
    ap.add_argument("--speed", type=float, default=SPEED)
    ap.add_argument("--temperature", type=float, default=0.7)
    ap.add_argument("--top-p", type=float, default=0.7)
    ap.add_argument("--model", default=FREE_MODEL,
                    choices=["s1", "s2-pro", PAID_MODEL, FREE_MODEL])
    ap.add_argument("--no-verify", action="store_true",
                    help="skip the local whisper word-check (faster, less safe)")
    a = ap.parse_args()
    k = key()

    if a.credit:
        print(json.dumps(credit(k), indent=2))
        return
    if a.models:
        ms = models(k)
        if not ms:
            print("No voices on this account yet — clone one with --clone REF.wav")
        for m in ms:
            print(f"  {m.get('_id')}  {m.get('title','')}  "
                  f"state={m.get('state','')}  {m.get('created_at','')[:10]}")
        return
    if a.clone:
        m = clone(k, a.clone, a.title, a.ref_text)
        print(f"voice id: {m.get('_id')}   title: {m.get('title')}")
        print("Use it with:  --voice " + str(m.get("_id")))
        return

    if not a.voice or not (a.say or a.lines):
        ap.error("need --voice plus --say or --lines")
    whisper = None
    if not a.no_verify:
        # faster-whisper's mel filterbank throws divide-by-zero/overflow warnings on this
        # numpy build — cosmetic, the transcript comes out correct (checked word-for-word
        # against three delivered lines, 1 Sep). Muted so a real message is not buried in them.
        import warnings
        import numpy as np
        warnings.filterwarnings("ignore")
        np.seterr(all="ignore")
        from faster_whisper import WhisperModel
        whisper = WhisperModel("base.en", device="cpu", compute_type="int8")
    kw = dict(model=a.model, temperature=a.temperature, top_p=a.top_p, speed=a.speed)
    outdir = pathlib.Path(a.outdir).expanduser()
    outdir.mkdir(parents=True, exist_ok=True)

    jobs = [(a.out or str(outdir / "line.mp3"), a.say)] if a.say else [
        (str(outdir / f"{i:02d}_{slug(t)}.mp3"), t)
        for i, t in enumerate(read_lines(a.lines), start=1)]
    for out, text in jobs:
        t = prep_text(text)
        p, chop, misreads, used = best_of(k, a.voice, t, out, a.takes, whisper, **kw)
        note = f"  [{misreads} misread take(s) dropped]" if misreads else ""
        print(f"{pathlib.Path(p).name}  chop {chop:.3f}  via {used}{note}")
    print(f"\n{len(jobs)} line(s) -> {outdir}")
    print("Lower chop is smoother. It is a shortlist, not a verdict — Saad's ear decides.")


def _test():
    assert prep_text("The Q and A process", quiet=True) == "The Q-and-A process"
    assert prep_text("Q and A here", quiet=True) == "Q-and-A here"
    assert prep_text("parts and labour", quiet=True) == "parts and labour"
    assert slug("Sign in as the team lead") == "sign_in_as_the_team_lead"
    body = {"text": "x", "reference_id": "v", "format": "wav"}
    assert json.loads(json.dumps(body))["format"] == "wav"
    print("sa_fishvo self-test: ok (Q-and-A binding, slug, body shape)")


if __name__ == "__main__":
    if "--test" in sys.argv:
        _test()
    else:
        main()
