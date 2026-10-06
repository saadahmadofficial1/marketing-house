#!/usr/bin/env python3
"""sa_cutsheet — per-clip cut SUGGESTIONS for a raw footage folder, for Saad to review.

This does NOT auto-edit. It cannot replicate Saad's craft (deliberate in-point choice,
speed-as-feel, reframing) — see the style notes. What it CAN do: sample several candidate
moments inside each clip, flag which look shaky vs steady, note what qwen sees, and
suggest one best window + a speed — as a starting point Saad approves or overrides.

  python3 sa_cutsheet.py <footage_folder> [--cut-len 1.8] [--candidates 4] [--limit 8]

Heavy Ollama batch (many clips x candidates) — HARD RULE: full-folder runs only 1am-6am.
A small --limit run during the day is fine (single-image-class checks), same rule as sa_see.
Output: <footage_folder>/_CUTSHEET/CUTSHEET.md + cutsheet.json
"""
import os, sys, json, base64, argparse, urllib.request
sys.path.insert(0, os.path.dirname(__file__))
from sa_assemble import probe, VIDEO_EXT, FFMPEG  # reuse — no re-writing duration/probe logic

OLLAMA = "http://localhost:11434/api/generate"
VLM = os.environ.get("SA_VLM", "qwen3-vl:8b")

JUDGE_PROMPT = (
    "You are judging one frame sampled from an event or product-showcase video clip, "
    "for use in a fast-cut highlight edit. Reply ONLY with strict JSON, no prose:\n"
    '{"usable": 1-5 int (5=sharp/well-framed/interesting, 1=blurry/awkward/boring), '
    '"looks_shaky_or_blurry": true/false, '
    '"subject": "product-closeup|person|crowd|wide-scene|other", '
    '"note": "one short factual sentence"}'
)


def _ask_judge(img_path):
    b64 = base64.b64encode(open(img_path, "rb").read()).decode()
    req = urllib.request.Request(OLLAMA, data=json.dumps(
        {"model": VLM, "prompt": JUDGE_PROMPT, "images": [b64], "stream": False,
         "format": "json", "think": False, "keep_alive": "1m"}).encode(),
        headers={"Content-Type": "application/json"})
    r = json.loads(urllib.request.urlopen(req, timeout=180).read())
    raw = r.get("response") or r.get("thinking") or "{}"
    try:
        return json.loads(raw)
    except Exception:
        return {"usable": 3, "looks_shaky_or_blurry": False, "subject": "other", "note": "[parse failed]"}


def _extract_frame(video, t, out_jpg):
    import subprocess
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-ss", str(max(t, 0)),
                    "-i", video, "-frames:v", "1", "-vf", "scale=640:-2", out_jpg], check=True)


def _motion_score(video, t, out_dir, tag):
    """Cheap shake/motion proxy: pixel diff between two frames 0.3s apart.
    ponytail: frame-diff heuristic, not real optical-flow stabilization detection —
    upgrade path if precision matters: ffmpeg vidstabdetect."""
    from PIL import Image
    f1 = os.path.join(out_dir, f"{tag}_a.jpg")
    f2 = os.path.join(out_dir, f"{tag}_b.jpg")
    _extract_frame(video, t, f1)
    _extract_frame(video, t + 0.3, f2)
    im1 = Image.open(f1).convert("L").resize((160, 90))
    im2 = Image.open(f2).convert("L").resize((160, 90))
    d1, d2 = im1.getdata(), im2.getdata()
    diff = sum(abs(a - b) for a, b in zip(d1, d2)) / len(d1)
    os.remove(f1); os.remove(f2)
    return diff  # ~0-255, higher = more change between frames


def pick_best_candidate(candidates):
    """Pure logic (no I/O): candidates = [{"motion": float, "usable": int}, ...]
    -> index of the best one. Higher usable is better; lower motion is better."""
    def score(c):
        return c["usable"] * 10 - c["motion"] * 1.0
    best_i, best_s = 0, float("-inf")
    for i, c in enumerate(candidates):
        s = score(c)
        if s > best_s:
            best_i, best_s = i, s
    return best_i


def suggest_speed(motion, subject):
    if motion > 18:
        return 0.7, "slowed to smooth handheld motion"
    if subject == "product-closeup":
        return 0.7, "slow, elegant — matches your usual detail-shot pace"
    return 1.0, "steady enough at normal speed"


def build_cutsheet(footage_dir, cut_len=1.8, n_candidates=4, limit=None, out_dir=None):
    files = sorted(f for f in os.listdir(footage_dir) if f.endswith(VIDEO_EXT))
    if limit:
        files = files[:limit]
    if not files:
        raise SystemExit(f"no video files in {footage_dir}")

    out_dir = out_dir or os.path.join(footage_dir, "_CUTSHEET")
    os.makedirs(out_dir, exist_ok=True)
    tmp_frames = os.path.join(out_dir, "_tmp_frames")
    os.makedirs(tmp_frames, exist_ok=True)

    rows = []
    for fi, f in enumerate(files):
        path = os.path.join(footage_dir, f)
        dur, w, h = probe(path)
        if dur <= 0:
            rows.append({"file": f, "error": "could not read duration"})
            continue
        span = max(dur - cut_len, 0.1)
        starts = [round(span * k / max(n_candidates - 1, 1), 2) for k in range(n_candidates)] \
            if n_candidates > 1 else [0.0]

        cands = []
        print(f"[{fi+1}/{len(files)}] {f} ({dur:.1f}s) — judging {len(starts)} candidates...")
        for ci, t in enumerate(starts):
            mid_frame = os.path.join(tmp_frames, f"{fi}_{ci}.jpg")
            _extract_frame(path, t + cut_len / 2, mid_frame)
            try:
                verdict = _ask_judge(mid_frame)
            except Exception as e:
                verdict = {"usable": 3, "looks_shaky_or_blurry": False, "subject": "other", "note": f"[vision failed: {e}]"}
            motion = _motion_score(path, t + cut_len / 2, tmp_frames, f"{fi}_{ci}")
            os.remove(mid_frame)
            cands.append({"start": t, "motion": round(motion, 1), **verdict})

        best_i = pick_best_candidate(cands)
        best = cands[best_i]
        speed, speed_why = suggest_speed(best["motion"], best.get("subject", "other"))
        rows.append({
            "file": f, "duration": round(dur, 1),
            "suggested_in": best["start"], "suggested_out": round(best["start"] + cut_len, 2),
            "shake_flag": "SHAKY — avoid" if best.get("looks_shaky_or_blurry") or best["motion"] > 22 else "ok",
            "subject": best.get("subject", "other"), "note": best.get("note", ""),
            "suggested_speed": speed, "speed_why": speed_why,
            "all_candidates": cands,
        })

    shutil_rm(tmp_frames)
    json.dump(rows, open(os.path.join(out_dir, "cutsheet.json"), "w"), indent=1)

    md = [f"# Cut sheet suggestions — {footage_dir}", f"_{len(rows)} clips, review before using in CapCut_\n",
          "| Clip | Dur | Suggested in→out | Flag | Subject | Speed | Note |",
          "|---|---|---|---|---|---|---|"]
    for r in rows:
        if "error" in r:
            md.append(f"| {r['file']} | - | - | ERROR | - | - | {r['error']} |")
            continue
        md.append(f"| {r['file']} | {r['duration']}s | {r['suggested_in']}s→{r['suggested_out']}s | "
                   f"{r['shake_flag']} | {r['subject']} | {r['suggested_speed']}x | {r['note']} |")
    open(os.path.join(out_dir, "CUTSHEET.md"), "w").write("\n".join(md) + "\n")
    print(f"\n-> {out_dir}/CUTSHEET.md  (+ cutsheet.json)")
    return out_dir


def shutil_rm(d):
    import shutil
    shutil.rmtree(d, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("footage_dir")
    ap.add_argument("--cut-len", type=float, default=1.8)
    ap.add_argument("--candidates", type=int, default=4)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    build_cutsheet(a.footage_dir, a.cut_len, a.candidates, a.limit, a.out)


def _test_pick_best_candidate():
    cands = [{"usable": 2, "motion": 5}, {"usable": 5, "motion": 30}, {"usable": 4, "motion": 8}]
    assert pick_best_candidate(cands) == 2, "should favour good-usable + low-motion over higher-usable+very-shaky"
    assert pick_best_candidate([{"usable": 3, "motion": 0}]) == 0
    print("pick_best_candidate: ok")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        _test_pick_best_candidate()
    else:
        main()
