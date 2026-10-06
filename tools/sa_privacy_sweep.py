#!/usr/bin/env python3
"""Privacy sweep of the RENDERED review cut (24 Sep). Local only: ffmpeg frame grabs +
Apple Vision OCR (ocr_bounds_local). This check runs locally and uploads nothing, and
no vision model sees a frame.

    python3 sa_privacy_sweep.py harvest       # name/e-mail tokens from the UNBLURRED source rects
    python3 sa_privacy_sweep.py sweep [video] # every 0.25 s of the render -> privacy_sweep.json

A frame FAILS when OCR reads (a) any e-mail address, (b) any harvested person-name token as
a whole word, or (c) any word of 3+ letters inside a blur rect while that rect is active.
The harvested tokens are stored hashed (sha1), never in clear, so the report itself carries
no names. Tokens that are ordinary English words (/usr/share/dict/words) or script words are
dropped - they would fire on UI text; e-mails and rect-legibility still cover those people.
"""
import concurrent.futures as cf, hashlib, json, os, pathlib, re, subprocess, sys, tempfile

P = pathlib.Path(__file__).resolve().parent
# the review-cut project folder (holds BUILD/ and the unblurred SOURCE.mp4); override with SWEEP_DIR
M = pathlib.Path(os.environ.get("SWEEP_DIR", str(P))).expanduser()
ROOT = M / "BUILD"
RAW = pathlib.Path(os.environ.get("SWEEP_SOURCE", str(M / "SOURCE.mp4"))).expanduser()
# the local Apple Vision OCR helper (prints JSON rows with text, box, confidence)
OCR = pathlib.Path(os.environ.get("OCR_BOUNDS", str(P / "ocr_bounds_local"))).expanduser()
_PRIV = None


def priv():
    """The blur rects (privacy.json in the review-cut folder), read on first use."""
    global _PRIV
    if _PRIV is None:
        _PRIV = json.load(open(M / "privacy.json"))
    return _PRIV


def duration(video):
    """Length of a video in seconds (ffprobe), so no grab is asked for past its end."""
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", str(video)], capture_output=True, text=True, check=True)
    return float(r.stdout.strip())

EMAIL = re.compile(r"[A-Za-z0-9._%+-]+\s?@\s?[A-Za-z0-9.-]+\.[a-z]{2,}|@[A-Za-z0-9-]{2,}\.", re.I)   # incl. an OCR-truncated "@domain."
H = lambda s: hashlib.sha1(s.encode()).hexdigest()[:16]


def ocr(png):
    if not pathlib.Path(png).exists(): return []
    r = subprocess.run([str(OCR), str(png)], capture_output=True, text=True)
    if r.returncode != 0: raise RuntimeError(f"OCR failed on {png}: {r.stderr[:200]}")
    j = json.loads(r.stdout)
    return [(r["text"], [round(v) for v in r["box"]], r["confidence"]) for r in j["rows"]]


def grab(video, t, out, vf=None):
    cmd = ["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.3f}", "-i", str(video), "-frames:v", "1"]
    if vf: cmd += ["-vf", vf]
    subprocess.run(cmd + [str(out)], check=True)


def harvest():
    """OCR each privacy rect on the unblurred SOURCE (canvas y + 150) at start/mid/end."""
    vocab = set()
    try: vocab |= {w.strip().lower() for w in open("/usr/share/dict/words")}
    except OSError: pass
    for f in ("lines.txt", "MAP.md", "script_checked.md"):
        vocab |= {w.lower() for w in re.findall(r"[A-Za-z]+", (M / f).read_text())}
    toks, emails = {}, 0
    end = duration(RAW)
    with tempfile.TemporaryDirectory() as tmp:
        for k, p in enumerate(priv()):
            a, b = p["span"]; x, y, w, h = p["rect"]
            for t in (a + 0.1, (a + b) / 2, min(b - 0.1, end - 0.1)):
                png = pathlib.Path(tmp) / f"h{k}_{t:.2f}.png"
                grab(RAW, t, png, vf=f"crop={w + 20}:{h + 20}:{max(0, x - 10)}:{max(0, y + 150 - 10)}")
                for text, _, conf in ocr(png):
                    if EMAIL.search(text): emails += 1
                    for wd in re.findall(r"[A-Za-z]{3,}", text):
                        if wd.lower() not in vocab:
                            toks[wd.lower()] = toks.get(wd.lower(), 0) + 1
    out = {"tokens": sorted(H(t) for t in toks), "n_tokens": len(toks), "emails_seen_in_source": emails,
           "note": "sha1[:16] of lower-case name tokens read inside the privacy rects on the unblurred source"}
    json.dump(out, open(ROOT / "privacy_tokens.json", "w"), indent=1)
    print(f"harvested {len(toks)} name-like tokens (stored hashed), {emails} e-mail sightings in the source rects")


def active_rects(src_t):
    return [p for p in priv() if p["span"][0] <= src_t <= p["span"][1]]


def sweep(video=None):
    video = pathlib.Path(video or ROOT / "PACED.mp4")   # the picture itself (overlays carry only script text)
    plan = json.load(open(ROOT / "plan.json"))
    tk = json.load(open(ROOT / "privacy_tokens.json"))
    names = set(tk["tokens"]) - set(tk.get("ui_whitelist", []))
    end = plan["end"]; ts = [round(i * 0.25, 2) for i in range(int(end / 0.25))]
    if len(sys.argv) > 3: ts = json.loads(sys.argv[3])          # re-check a given list of times

    # PACED is the rows concatenated at round(tg * 30) frames each, so the true row
    # boundaries are the cumulative FRAME counts, not plan["rowstart"] (which drifts by up
    # to ~0.1 s; the first sweep mis-mapped 8 boundary frames to the previous row).
    starts, acc = [], 0
    for a, b, tg in plan["rows"]:
        n = int(round(tg * 30)); starts.append((acc / 30, (acc + n) / 30, a, b)); acc += n

    def src_of(t):                      # which source instant is on screen at export time t
        f = (int(t * 30) + 0.5) / 30    # the frame displayed at t
        for rs, re_, a, b in starts:
            if rs <= f < re_:
                return min(b - 1 / 30, a + (f - rs))
        return None

    def one(t):
        with tempfile.TemporaryDirectory() as tmp:
            png = pathlib.Path(tmp) / "f.png"; grab(video, t, png)
            hits = []
            s = src_of(t); rects = active_rects(s) if s is not None else []
            for text, (x, y, w, h), conf in ocr(png):
                if EMAIL.search(text): hits.append(("email", conf))
                for wd in re.findall(r"[A-Za-z]{3,}", text):
                    if H(wd.lower()) in names: hits.append(("name", conf))
                cx, cy = x + w / 2, y + h / 2
                for p in rects:
                    rx, ry, rw, rh = p["rect"]
                    if rx <= cx <= rx + rw and ry <= cy <= ry + rh and re.search(r"[A-Za-z]{3,}", text):
                        hits.append(("legible-in-blur:" + p["what"][:40], conf))
            return t, s, hits

    res = []
    with cf.ThreadPoolExecutor(max_workers=4) as ex:
        for t, s, hits in ex.map(one, ts):
            if hits: res.append({"t": t, "src": s, "hits": hits})
    out = {"video": str(video), "frames": len(ts), "step_s": 0.25, "flagged": res,
           "verdict": "PASS" if not res else "FAIL"}
    json.dump(out, open(ROOT / "privacy_sweep.json", "w"), indent=1)
    print(f"privacy sweep: {len(ts)} frames, {len(res)} flagged -> {out['verdict']}")
    for r in res[:40]: print("  ", r["t"], r["src"], r["hits"])


if __name__ == "__main__":
    {"harvest": harvest, "sweep": lambda: sweep(sys.argv[2] if len(sys.argv) > 2 else None)}[sys.argv[1]]()
