#!/usr/bin/env python3
"""sa_boxcheck — look at every call-out with a vision model and say if it is on the right thing.

Saad's review, 7 Aug 2026: some boxes were well placed, some were badly off, and some
important steps in the middle had no highlight at all.

Both of those got past the existing checks, and it is obvious why. `sa_stepmark --check`
proves the background does not move under a box. It has no idea whether the box is sitting on
the Save button or on the empty space beside it. Nothing in the pipeline ever LOOKED at a
frame. This does — with qwen3-vl in Ollama; this check runs locally and
uploads nothing.

Two questions, because Saad asked two:

  --verify   is each box on the element its label names?      (the badly placed boxes)
  --gaps     what important click did we never highlight?     (the missed steps)

    Tools/venv/bin/python3 Tools/sa_boxcheck.py "…/T03_PACED_LAYERS/_layers.json" --verify
    Tools/venv/bin/python3 Tools/sa_boxcheck.py "…/_layers.json" --gaps --every 12
    Tools/venv/bin/python3 Tools/sa_boxcheck.py --test

NOTE ON TIMING: a full pass over one video is dozens of vision calls and makes the Mac stutter,
which is why the house rule puts heavy Ollama batches in the 1-6am window. Use --limit during
the day to check a handful; run the whole series overnight.
"""
import argparse
import base64
import json
import os
import subprocess
import sys
import urllib.request

OLLAMA = "http://localhost:11434/api/generate"
# 2b, not 8b. Measured 7 Aug on this Mac: 2b answers a 900px screenshot in ~12s, 8b took
# ~90s and, with Ollama's format="json" forced on, returned an empty string. Reading UI text
# out of a screenshot is not a job that needs the bigger model.
VLM = os.environ.get("SA_VLM", "qwen3-vl:2b")
PAD = 260               # context around the box, so the model can see the neighbours it might confuse
# Measured 8 Aug: a WARM model answers a 900px screenshot in 2-3s; a cold one took ~50s and
# sometimes timed out entirely. The whole "this is too slow to run in the day" problem was
# the model unloading between frames, not the image size. Keep it resident for the run.
# Do NOT shrink the image to compensate — at 512px it misread the element outright.
KEEP_ALIVE = "30m"
# DO NOT set num_predict here. Tried on 8 Aug as a "speed optimisation" and it broke the
# tool outright: qwen3-vl THINKS before it answers, and the thinking counts against
# num_predict — so any cap below what the whole reply needs is spent thinking and the
# response comes back an EMPTY STRING with done_reason "length". Measured: a reply of 258
# characters consumed eval_count 780. Capped at 120/300/600 it returned nothing at all.
# (An earlier note here blamed num_ctx truncating the image — that was wrong; num_ctx 8192
# and the default both work fine. The cap on OUTPUT was always the fault.)
# Speed came from keeping the model warm, nothing else.
OUTLINE = 6

VERIFY_PROMPT = """You are checking one frame from a software training video.

A thick red rectangle has been drawn on this screenshot. It is meant to be highlighting:

    "{label}"

Look ONLY at what is inside the red rectangle. Ignore everything outside it.

Reply with strict JSON, no prose:
{{"on_target": true or false,
  "inside_the_box": "what is actually inside the rectangle, in a few words - the exact button, field or row text if you can read it",
  "confidence": "high" or "medium" or "low",
  "better_target": "if it is wrong, name the thing on screen it SHOULD be on, else empty string"}}

Be strict. If the rectangle is on empty space, on the wrong row of a list, on a heading
instead of the control, or covers several controls at once, that is on_target false."""

GAPS_PROMPT = """You are watching a software training video for a business system, one
frame at a time. This frame is from the middle of a step.

Reply with strict JSON, no prose:
{"main_action": "the single most important thing a trainee must click, select or type on this screen, in a few words",
 "element_text": "the exact visible text on that control, if readable, else empty string",
 "worth_highlighting": true or false,
 "why": "one short sentence"}

worth_highlighting is true only when a trainee would genuinely miss this step without a
pointer - a button, a dropdown, a specific field, a confirmation. It is false for a screen
that is only being read, scrolled, or waited on."""


def extract_json(text):
    """Pull the JSON object out of a model reply. -> dict, or None if there isn't one.

    None means "the model did not answer", which is NOT the same as "the box is wrong".
    Conflating those two is how the first run of this tool reported six perfectly good
    call-outs as broken (7 Aug) — a false alarm costs Saad more than a missed one, because
    he goes and looks.
    """
    if not text:
        return None
    a, b = text.find("{"), text.rfind("}")
    if a < 0 or b <= a:
        return None
    try:
        return json.loads(text[a:b + 1])
    except json.JSONDecodeError:
        return None


def ask(img_path, prompt, timeout=240):
    """-> dict from the model, or None if it failed to answer. Never a silent empty dict."""
    b64 = base64.b64encode(open(img_path, "rb").read()).decode()
    req = urllib.request.Request(OLLAMA, data=json.dumps(
        {"model": VLM, "prompt": prompt, "images": [b64], "stream": False,
         "think": False, "keep_alive": KEEP_ALIVE,
         }).encode(),
        headers={"Content-Type": "application/json"})
    try:
        raw = json.loads(urllib.request.urlopen(req, timeout=timeout).read())
    except Exception as e:
        print(f"     ! model call failed: {e}")
        return None
    return extract_json(raw.get("response") or raw.get("thinking") or "")


def crop_window(box, canvas, pad=PAD):
    """-> (cx, cy, cw, ch) crop rect around the box, clamped inside the canvas.

    Pure, so the arithmetic that decides what the model sees is testable without a model.
    Generous context on purpose: the failure Saad keeps catching is a box on the row ABOVE
    the right one, and you cannot see that in a tight crop.
    """
    x, y, w, h = box
    cw, ch = canvas
    x0 = max(0, int(x - pad))
    y0 = max(0, int(y - pad))
    x1 = min(cw, int(x + w + pad))
    y1 = min(ch, int(y + h + pad))
    return x0, y0, max(x1 - x0, 1), max(y1 - y0, 1)


def frame_with_box(video, t, box, canvas, out, pad=PAD):
    """Freeze the exact frame the render uses, draw the box on it, crop to the window.

    drawbox before crop: the coordinates in _layers.json are canvas-space, so drawing first
    means never having to translate them. This is the frame sa_stepmark froze — measure
    anywhere else and you are checking a different picture (the trap from 5 Aug).
    """
    x, y, w, h = (int(v) for v in box)
    cx, cy, cw, ch = crop_window(box, canvas, pad)
    vf = (f"drawbox=x={x}:y={y}:w={w}:h={h}:color=red@1.0:t={OUTLINE},"
          f"crop={cw}:{ch}:{cx}:{cy},scale=900:-2")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{max(t, 0):.3f}",
                    "-i", video, "-frames:v", "1", "-vf", vf, out], check=True)
    return out


def verify(manifest, limit=None, work=None):
    m = json.load(open(manifest))
    video, canvas = m["video"], m.get("canvas", [1920, 1140])
    work = work or os.path.join(os.path.dirname(manifest), "_boxcheck")
    os.makedirs(work, exist_ok=True)
    layers = m["layers"][:limit] if limit else m["layers"]
    rows = []
    for i, L in enumerate(layers, 1):
        if not L.get("box"):
            continue
        t = L["start"] + L["duration"] / 2       # the frozen frame, not a neighbour
        img = frame_with_box(video, t, L["box"], canvas,
                             os.path.join(work, f"{i:02d}.jpg"))
        r = ask(img, VERIFY_PROMPT.format(label=L["label"]))
        # three outcomes, never two: right, wrong, or the model didn't answer
        status = "unknown" if r is None else ("ok" if r.get("on_target") else "wrong")
        if status == "wrong" and contradicts_itself(L["label"], r.get("inside_the_box", "")):
            # It said "wrong" while describing the very thing the label names — e.g.
            # "Open Records List" -> "Records List", "Sign in as Review Lead" ->
            # "Demo Review Lead". Measured 13 Aug: 11 of 17 nightly flags did this
            # on qwen3-vl:2b. That is the small model being unreliable, not a defect.
            status = "unknown"
        r = r or {}
        rows.append({"n": i, "t": round(t, 2), "label": L["label"], "status": status,
                     "saw": r.get("inside_the_box", ""),
                     "confidence": r.get("confidence", ""),
                     "better": r.get("better_target", ""), "frame": img})
        mark = {"ok": "ok   ", "wrong": "WRONG", "unknown": "  ?  "}[status]
        print(f"  {mark} {i:2d}  {t:7.1f}s  {L['label'][:38]:38s} -> "
              f"{r.get('inside_the_box', 'no answer from the model')[:44]}")
        if status == "wrong" and r.get("better_target"):
            print(f"          should be on: {r['better_target']}")
    bad = [r for r in rows if r["status"] == "wrong"]
    unk = [r for r in rows if r["status"] == "unknown"]
    print(f"\n{len(rows)} call-outs checked, {len(bad)} look wrong, "
          f"{len(unk)} unanswered (unanswered is NOT a defect — re-run those)")
    if unk and not bad:
        print("nothing confirmed wrong; the unanswered ones need another pass before "
              "anyone acts on this")
    return rows


_STOP = {"the", "a", "an", "to", "of", "for", "on", "in", "is", "it", "you", "your",
         "this", "that", "from", "and", "as", "sign", "click", "open", "select", "go", "any"}


def contradicts_itself(label, saw):
    """Did the model call the box wrong while naming the element the label asks for?"""
    import re as _re

    def toks(s):
        return {w for w in _re.findall(r"[a-z]+", (s or "").lower())
                if len(w) > 2 and w not in _STOP}
    want = toks(label)
    return bool(want and want & toks(saw))


def gaps(manifest, every=10.0, limit=None, work=None):
    """Sample the stretches with NO call-out and ask what was worth pointing at."""
    m = json.load(open(manifest))
    video, canvas = m["video"], m.get("canvas", [1920, 1140])
    work = work or os.path.join(os.path.dirname(manifest), "_boxcheck")
    os.makedirs(work, exist_ok=True)
    covered = [(L["start"], L["start"] + L["duration"]) for L in m["layers"]]
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                "-of", "csv=p=0", video], capture_output=True,
                               text=True).stdout.strip())
    times = uncovered_samples(covered, dur, every)
    if limit:
        times = times[:limit]
    found = []
    for i, t in enumerate(times, 1):
        img = os.path.join(work, f"gap_{i:02d}.jpg")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{t:.3f}", "-i", video,
                        "-frames:v", "1", "-vf", "scale=1100:-2", img], check=True)
        r = ask(img, GAPS_PROMPT) or {}
        if r.get("worth_highlighting"):
            found.append({"t": round(t, 1), "action": r.get("main_action", ""),
                          "text": r.get("element_text", ""), "why": r.get("why", ""),
                          "frame": img})
            print(f"  MISSED {t:7.1f}s  {r.get('main_action','')[:46]:46s} "
                  f"[{r.get('element_text','')[:26]}]")
    print(f"\n{len(times)} uncovered moments sampled, {len(found)} worth a call-out")
    return found


def uncovered_samples(covered, duration, every):
    """-> times to sample, skipping anything already inside a call-out window.

    Pure, so the sampling logic is testable without decoding a video.
    """
    out, t = [], every / 2
    while t < duration:
        if not any(a - 0.4 <= t <= b + 0.4 for a, b in covered):
            out.append(round(t, 3))
        t += every
    return out


def _test():
    # crop stays inside the canvas even when the box hugs an edge
    assert crop_window([0, 0, 100, 40], [1920, 1140], pad=200) == (0, 0, 300, 240)
    x, y, w, h = crop_window([1900, 1130, 100, 40], [1920, 1140], pad=200)
    assert x + w <= 1920 and y + h <= 1140, "crop must never run off the canvas"
    # a mid-canvas box gets padding on all four sides
    assert crop_window([500, 500, 100, 50], [1920, 1140], pad=100) == (400, 400, 300, 250)
    # gap sampling skips covered stretches and only those
    s = uncovered_samples([(0.0, 5.0), (20.0, 25.0)], 40.0, 10.0)
    assert 5.0 not in s and not any(20 <= t <= 25 for t in s), "never sample inside a call-out"
    assert any(10 < t < 20 for t in s), "the quiet stretch between call-outs must be sampled"
    assert all(t < 40.0 for t in s), "never sample past the end of the video"
    # an entirely covered video yields nothing to check
    assert uncovered_samples([(0.0, 40.0)], 40.0, 10.0) == []
    # a model that says nothing must never be read as a defect
    assert extract_json("") is None and extract_json("sorry, I cannot") is None
    assert extract_json('{"on_target": false}') == {"on_target": False}
    assert extract_json('<think>hmm</think> {"on_target": true, "a": 1}')["on_target"] is True, \
        "the answer must survive a model that thinks out loud first"
    assert extract_json("{broken json") is None, "half an answer is no answer"
    print("sa_boxcheck self-check: ok (crop clamping, padding, gap sampling, "
          "no-answer never counted as wrong)")


if __name__ == "__main__":
    if "--test" in sys.argv:
        _test()
        sys.exit()
    ap = argparse.ArgumentParser()
    ap.add_argument("manifest", help="a *_LAYERS/_layers.json")
    ap.add_argument("--verify", action="store_true", help="is each box on the right element?")
    ap.add_argument("--gaps", action="store_true", help="what did we fail to highlight?")
    ap.add_argument("--every", type=float, default=10.0, help="gap sampling interval (s)")
    ap.add_argument("--limit", type=int, help="stop after N — use this during the day")
    ap.add_argument("-o", "--out", help="write the findings as json")
    a = ap.parse_args()
    if not (a.verify or a.gaps):
        ap.error("give --verify, --gaps, or both")
    if not a.limit:                      # a full pass is a batch; --limit spot-checks are fine
        try:
            from sa_guard import preflight
            preflight("ollama_batch")
        except ImportError:
            pass
    res = {}
    if a.verify:
        print("== box placement ==")
        res["verify"] = verify(a.manifest, a.limit)
    if a.gaps:
        print("\n== missed steps ==")
        res["gaps"] = gaps(a.manifest, a.every, a.limit)
    if a.out:
        json.dump(res, open(a.out, "w"), indent=1)
        print(f"-> {a.out}")

    # A dead vision model answers nothing, and a run that answered nothing used to exit 0 —
    # so the nightly ticked "boxcheck ok" for days while Ollama was not even running
    # (found 13 Aug: every call was 'Connection refused', the whole pass took 30 seconds).
    # Silence is not a pass.
    checked = [r for r in res.get("verify", []) if r["status"] != "unknown"]
    if a.verify and res.get("verify") and not checked:
        print("\nNOTHING was answered — the vision model is unreachable, not the boxes clean.\n"
              "Start it with: ollama serve   (models: qwen3-vl:2b, qwen3-vl:8b)", file=sys.stderr)
        sys.exit(2)
