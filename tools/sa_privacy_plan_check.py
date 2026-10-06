#!/usr/bin/env python3
"""Does the privacy PLAN cover every name on every played frame?

Reads the UNBLURRED source (local ffmpeg + Apple Vision OCR; this check runs locally and uploads nothing) at
every 0.25 s of every played source window in plan.json, plus each row's frozen frame,
and lists every e-mail / harvested name token whose text box is NOT inside a privacy rect
active at that instant (spans padded by PAD s). Output masks the tokens (first two
letters + length) so no name is printed. Used to fix privacy.json before re-rendering;
the rendered-picture sweep (sa_privacy_sweep.py) stays the release check.

    python3 sa_privacy_plan_check.py [PAD]
"""
import concurrent.futures as cf, json, pathlib, re, sys, tempfile
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import sa_privacy_sweep as PS

ROOT = PS.ROOT
PAD = float(sys.argv[1]) if len(sys.argv) > 1 else 0.25
TOK = json.load(open(ROOT / "privacy_tokens.json"))
NAMES = set(TOK["tokens"]) - set(TOK.get("ui_whitelist", []))


def covered(src, x, y, w, h):
    cx, cy = x + w / 2, y + h / 2
    for p in PS.priv():
        a, b = p["span"]; rx, ry, rw, rh = p["rect"]
        if a - PAD <= src <= b + PAD and rx <= cx <= rx + rw and ry <= cy <= ry + rh:
            return True
    return False


def one(src):
    with tempfile.TemporaryDirectory() as tmp:
        png = pathlib.Path(tmp) / "f.png"
        PS.grab(PS.RAW, src, png, vf="crop=1920:990:0:150")       # canvas coordinates
        out = []
        for text, (x, y, w, h), conf in PS.ocr(png):
            kinds = []
            if PS.EMAIL.search(text): kinds.append("EMAIL")
            for wd in re.findall(r"[A-Za-z]{3,}", text):
                if PS.H(wd.lower()) in NAMES: kinds.append(wd[:2] + "*" * (len(wd) - 2))
            if kinds and not covered(src, x, y, w, h):
                out.append({"src": round(src, 2), "box": [x, y, w, h], "tokens": kinds})
        return out


def main():
    plan = json.load(open(ROOT / "plan.json"))
    ts = set()
    for a, b, tg in plan["rows"]:
        t = a
        while t < b:
            ts.add(round(t, 2)); t += 0.25
        ts.add(round(b - 0.02, 2))                                # the frozen frame
    ts = sorted(t for t in ts if t < plan.get("source_end", float("inf")))    # optional: ignore past the source end
    with cf.ThreadPoolExecutor(max_workers=6) as ex:
        hits = [h for hs in ex.map(one, ts) for h in hs]
    json.dump({"pad": PAD, "frames": len(ts), "uncovered": hits}, open(ROOT / "privacy_plan_check.json", "w"), indent=1)
    print(f"{len(ts)} source frames, {len(hits)} uncovered name/e-mail boxes")
    # group into (rounded box, time run)
    runs = {}
    for h in hits:
        k = (round(h["box"][0] / 30) * 30, round(h["box"][1] / 30) * 30)
        runs.setdefault(k, []).append(h)
    for k, v in sorted(runs.items(), key=lambda kv: kv[1][0]["src"]):
        xs = [h["box"] for h in v]
        print(f"  at ~{k}: {len(v)} hits src {v[0]['src']}..{v[-1]['src']}  box x{min(b[0] for b in xs)}-{max(b[0]+b[2] for b in xs)} "
              f"y{min(b[1] for b in xs)}-{max(b[1]+b[3] for b in xs)}  {sorted(set(t for h in v for t in h['tokens']))[:5]}")


if __name__ == "__main__":
    main()
