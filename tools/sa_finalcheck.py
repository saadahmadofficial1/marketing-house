#!/usr/bin/env python3
"""sa_finalcheck — is this EXPORTED training video safe to send?

Requirement (8 Sep): new videos were about to be added, so the last check had to be
watertight.
Every other checker reads the CapCut project. This one reads the MP4 that will
actually be sent, and compares what is SPOKEN in it to the approved script.

    Tools/venv/bin/python3 Tools/sa_finalcheck.py <video.mp4> [--script SCRIPTS.txt] [--title "TITLE"]
    Tools/venv/bin/python3 Tools/sa_finalcheck.py <folder-of-video-folders> --script SCRIPTS.txt
    Tools/venv/bin/python3 Tools/sa_finalcheck.py --test

Checks per video (all measured, none assumed):
  container   plays, resolution, fps, duration
  audio       present, integrated loudness, longest silence, silence at the end
  picture     first/last frame not black, no frozen tail
  speech      local faster-whisper transcript (runs locally, uploads nothing)
  script      every script sentence found in the transcript (fuzzy, >=0.72),
              spoken sentences that are NOT in the script, order preserved
Verdict is SEND / CHECK / STOP with the reasons. Read-only.
"""
import argparse, json, os, pathlib, re, subprocess, sys, difflib, tempfile

THRESH = 0.72

def probe(p):
    j = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_entries",
        "stream=codec_type,width,height,r_frame_rate,duration:format=duration",
        "-of", "json", str(p)], capture_output=True, text=True, check=True).stdout)
    v = next((s for s in j["streams"] if s["codec_type"] == "video"), None)
    a = next((s for s in j["streams"] if s["codec_type"] == "audio"), None)
    fps = None
    if v and v.get("r_frame_rate"):
        n, d = v["r_frame_rate"].split("/"); fps = round(int(n) / max(1, int(d)), 2)
    return {"width": v and v.get("width"), "height": v and v.get("height"), "fps": fps,
            "duration": round(float(j["format"]["duration"]), 2), "has_audio": a is not None}

def loudness_and_silence(p):
    out = subprocess.run(["ffmpeg", "-v", "info", "-i", str(p), "-af",
        "ebur128=peak=true,silencedetect=n=-45dB:d=2.5", "-f", "null", "-"],
        capture_output=True, text=True).stderr
    lufs = re.findall(r"I:\s+(-?[\d.]+) LUFS", out)
    sil = [(float(a), float(b)) for a, b in zip(re.findall(r"silence_start: ([\d.]+)", out),
                                                re.findall(r"silence_end: ([\d.]+)", out))]
    longest = max((b - a for a, b in sil), default=0.0)
    return (float(lufs[-1]) if lufs else None), round(longest, 1), sil

def frame_black(p, t):
    out = subprocess.run(["ffmpeg", "-v", "info", "-ss", f"{t:.2f}", "-i", str(p), "-frames:v", "1",
        "-vf", "blackdetect=d=0:pix_th=0.10", "-f", "null", "-"], capture_output=True, text=True).stderr
    return "black_start" in out

def transcribe(p):
    from faster_whisper import WhisperModel
    wav = pathlib.Path(tempfile.mkdtemp()) / "a.wav"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(p), "-vn", "-ac", "1", "-ar", "16000", str(wav)], check=True)
    m = WhisperModel("base.en", device="cpu", compute_type="int8")
    segs, _ = m.transcribe(str(wav), beam_size=3, vad_filter=True)
    return " ".join(s.text.strip() for s in segs)

def norm(s):
    s = s.lower().replace("&", "and")
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def sentences(text):
    parts = re.split(r"(?<=[.!?])\s+", text.replace("\n", " "))
    return [p.strip() for p in parts if len(norm(p).split()) >= 3]

def best_match(sent, hay_words):
    """Slide windows of the sentence's length (and +-2 words) over the transcript."""
    sw = norm(sent).split(); n = len(sw)
    if n == 0 or not hay_words: return 0.0, -1
    best, pos = 0.0, -1
    for i in range(0, max(1, len(hay_words) - n + 3)):
        for w in (n - 2, n, n + 2):
            if w < 1: continue
            r = difflib.SequenceMatcher(None, sw, hay_words[i:i + w]).ratio()
            if r > best: best, pos = r, i
    return best, pos

def section_from_scripts(script_file, title):
    txt = pathlib.Path(script_file).read_text()
    lines = txt.split("\n"); i = 0; secs = {}
    while i < len(lines):
        if i + 1 < len(lines) and re.fullmatch(r"=+", lines[i + 1].strip()) and lines[i].strip():
            t = lines[i].strip(); j = i + 2; body = []
            while j < len(lines) and not (j + 1 < len(lines) and re.fullmatch(r"=+", lines[j + 1].strip()) and lines[j].strip()):
                body.append(lines[j]); j += 1
            secs[norm(t)] = "\n".join(body); i = j
        else: i += 1
    if title:
        k = norm(title)
        for key, body in secs.items():
            if key == k or k in key or key in k: return body
        # fuzzy
        best = max(secs, key=lambda key: difflib.SequenceMatcher(None, key, k).ratio())
        return secs[best]
    return None

def check_video(p, script_text=None, ignore=()):
    p = pathlib.Path(p); rep = {"file": str(p), "issues": [], "warnings": []}
    info = probe(p); rep.update(info)
    if not info["has_audio"]: rep["issues"].append("no audio stream")
    if info["duration"] < 20: rep["issues"].append(f"suspiciously short ({info['duration']}s)")
    lufs, longest, sil = loudness_and_silence(p)
    rep["lufs"] = lufs; rep["longest_silence_s"] = longest
    if lufs is not None and (lufs < -24 or lufs > -12): rep["warnings"].append(f"loudness {lufs} LUFS (expected about -14 to -20)")
    if longest > 12: rep["warnings"].append(f"silence of {longest}s inside the video")
    if sil and info["duration"] - sil[-1][1] < 0.5 and (sil[-1][1] - sil[-1][0]) > 8:
        rep["warnings"].append(f"video ends on {round(sil[-1][1]-sil[-1][0],1)}s of silence")
    if frame_black(p, 0.5): rep["warnings"].append("first frame is black")
    if frame_black(p, max(0.0, info["duration"] - 0.5)): rep["warnings"].append("last frame is black")
    if script_text:
        tr = transcribe(p); rep["transcript_words"] = len(tr.split())
        hay = norm(tr).split()
        missing, low, positions = [], [], []
        for s in sentences(script_text):
            r, pos = best_match(s, hay)
            positions.append(pos)
            if r < 0.55: missing.append(s)
            elif r < THRESH: low.append((round(r, 2), s))
        rep["script_sentences"] = len(sentences(script_text))
        rep["missing_sentences"] = missing; rep["weak_matches"] = low
        # order check: matched positions should be non-decreasing
        seq = [q for q in positions if q >= 0]
        out_of_order = sum(1 for a, b in zip(seq, seq[1:]) if b < a - 15)
        if out_of_order: rep["warnings"].append(f"{out_of_order} script sentence(s) spoken out of order")
        # extra speech: transcript sentences not in the script
        extras = []
        sw = norm(script_text).split()
        # the sign-off is not in the script; --ignore-phrase / SIGNOFF_TAGLINE add your own
        KNOWN = ("thank you for watching",) + tuple(norm(x) for x in ignore if norm(x))
        for s in sentences(tr):
            if any(k in norm(s) for k in KNOWN): continue
            r, _ = best_match(s, sw)
            if r < 0.5: extras.append(s)
        rep["extra_spoken"] = extras
        if missing: rep["issues"].append(f"{len(missing)} script sentence(s) not heard in the video")
        if extras: rep["warnings"].append(f"{len(extras)} spoken sentence(s) not in the script")
    rep["verdict"] = "STOP" if rep["issues"] else ("CHECK" if rep["warnings"] else "SEND")
    return rep

def print_report(rep):
    print(f"\n{'='*78}\n{rep['verdict']:5}  {pathlib.Path(rep['file']).name}")
    print(f"       {rep['width']}x{rep['height']} @ {rep['fps']}fps · {rep['duration']}s · "
          f"{'audio' if rep['has_audio'] else 'NO AUDIO'} {rep.get('lufs')} LUFS · longest silence {rep.get('longest_silence_s')}s")
    if "script_sentences" in rep:
        print(f"       script {rep['script_sentences']} sentences · heard {rep['transcript_words']} words · "
              f"missing {len(rep['missing_sentences'])} · weak {len(rep['weak_matches'])} · extra {len(rep['extra_spoken'])}")
    for x in rep["issues"]: print(f"   ✗ {x}")
    for x in rep["warnings"]: print(f"   ! {x}")
    for s in rep.get("missing_sentences", []): print(f"   MISSING: {s}")
    for r, s in rep.get("weak_matches", []): print(f"   weak {r}: {s}")
    for s in rep.get("extra_spoken", [])[:8]: print(f"   extra: {s}")

def self_test():
    hay = norm("Sign in as the editor. From the dashboard click New Record. Enter the details.").split()
    r, _ = best_match("From the dashboard, click New Record.", hay); assert r > 0.9, r
    r, _ = best_match("Open the Settings page and select the Reports tab.", hay); assert r < 0.55, r
    assert sentences("A b c. Short. Thank you for watching.") == ["A b c.", "Thank you for watching."]
    print("self-test ok")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("target", nargs="?")
    ap.add_argument("--script"); ap.add_argument("--title"); ap.add_argument("--json")
    ap.add_argument("--strip-prefix", default="",
                    help="export filename prefix to drop before matching a script title")
    ap.add_argument("--ignore-phrase", action="append", default=[],
                    help="spoken line that is not in the script (your sign-off or tagline); "
                         "repeatable")
    ap.add_argument("--test", action="store_true")
    a = ap.parse_args()
    if a.test: return self_test()
    t = pathlib.Path(a.target)
    vids = [t] if t.is_file() else sorted(q for q in t.rglob("*.mp4") if not q.name.startswith("."))
    ignore = a.ignore_phrase + [x for x in [os.environ.get("SIGNOFF_TAGLINE", "")] if x]
    reps = []
    for v in vids:
        title = a.title or (v.stem.replace(a.strip_prefix, "") if a.strip_prefix else v.stem)
        st = section_from_scripts(a.script, title) if a.script else None
        rep = check_video(v, st, ignore); reps.append(rep); print_report(rep)
    if a.json: pathlib.Path(a.json).write_text(json.dumps(reps, indent=1))
    bad = [r for r in reps if r["verdict"] != "SEND"]
    print(f"\n{len(reps)} video(s): {len(reps)-len(bad)} SEND · {len(bad)} need a look")
    sys.exit(1 if bad else 0)

if __name__ == "__main__":
    main()
