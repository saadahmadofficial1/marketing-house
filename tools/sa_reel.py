#!/usr/bin/env python3
"""Reel Intelligence — paste a link, learn everything from it. Zero tokens.
  Tools/venv/bin/python3 Tools/sa_reel.py <url> [--keep]
Downloads (yt-dlp) → transcribes (faster-whisper, any language) → describes
visuals (frames → local qwen) → writes one report to Projects/Reel_Intel/
(auto-indexed by the local brain). Media deleted after unless --keep.
Better than typical "video analyzer" skills: it SEES the video, not just hears it.
"""
import os, re, sys, glob, json, base64, shutil, datetime, subprocess, tempfile, urllib.request

from sa_security import gate, assert_writes_allowed

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VENV_BIN = os.path.join(ROOT, "Tools", "venv", "bin")
YTDLP = os.path.join(VENV_BIN, "yt-dlp")
_FF = os.path.expanduser("~/.local/bin/ffmpeg")
FFMPEG = _FF if os.path.exists(_FF) else (shutil.which("ffmpeg") or "ffmpeg")
OUT = os.path.join(ROOT, "Projects", "Reel_Intel")
OLLAMA = "http://localhost:11434/api/generate"
VLM = os.environ.get("SA_VLM", "qwen3-vl:8b")

VPROMPT = ("Describe this video shot for a director who will recreate it: "
           "1) subject + action 2) framing (close/medium/wide, angle) 3) setting "
           "4) lighting & colour grade 5) any on-screen text (quote exactly) "
           "6) graphics/effects. Max 3 sentences, factual.")

ANALYSIS_PROMPT = """Analyze this PUBLIC reference video for a corporate content team.
Return strict JSON only with keys: spoken_hook, visual_hook, structure (array), techniques
(array), pacing, cta, key_points (array), adapt_for_brand (array), avoid_copying (array),
priority (LOW|MEDIUM|HIGH), evidence (array of objects with timestamp and reason).
Distinguish evidence from inference. Never recommend copying distinctive protected creative.

TRANSCRIPT:
%s

VISUAL SHOTS:
%s
"""

CATEGORY_HINTS = {
    "product": ("product", "launch", "unboxing", "packshot", "review"),
    "people_interview": ("interview", "testimonial", "podcast", "talking head", "story"),
    "event": ("event", "conference", "ceremony", "festival", "exhibition"),
    "travel_place": ("travel", "city", "hotel", "destination", "tour"),
    "food": ("food", "recipe", "restaurant", "cooking", "chef"),
    "tutorial_explainer": ("tutorial", "how to", "step", "feature", "demo"),
    "corporate_communication": ("company", "employee", "leadership", "corporate"),
    "editing_technique": ("edit", "transition", "camera", "cinematic", "color grade"),
    "ai_tooling": (" ai ", "agent", "model", "automation", "claude", "openai"),
}


def detect_category(text):
    low = " " + text.lower() + " "
    scored = [(sum(low.count(word) for word in words), name)
              for name, words in CATEGORY_HINTS.items()]
    score, name = max(scored)
    return name if score else "general_reference"


def ask_analysis(transcript, visuals):
    prompt = ANALYSIS_PROMPT % (transcript, "\n".join(visuals))
    req = urllib.request.Request(OLLAMA, data=json.dumps(
        {"model": VLM, "prompt": prompt, "stream": False, "format": "json",
         "think": False, "keep_alive": "1m"}).encode(),
        headers={"Content-Type": "application/json"})
    response = json.loads(urllib.request.urlopen(req, timeout=90).read())
    return json.loads(response.get("response") or response.get("thinking") or "{}")


def update_index(record):
    path = os.path.join(OUT, "index.json")
    rows = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else []
    rows = [row for row in rows if row.get("url") != record["url"]]
    rows.append(record)
    rows.sort(key=lambda row: row.get("analyzed_at", ""), reverse=True)
    temp = path + ".tmp"
    json.dump(rows, open(temp, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    os.replace(temp, path)

def see(img):
    b64 = base64.b64encode(open(img, "rb").read()).decode()
    req = urllib.request.Request(OLLAMA, data=json.dumps(
        {"model": VLM, "prompt": VPROMPT, "images": [b64], "stream": False,
         "think": False, "keep_alive": "1m"}).encode(),
        headers={"Content-Type": "application/json"})
    r = json.loads(urllib.request.urlopen(req, timeout=300).read())
    return (r.get("response") or r.get("thinking") or "").strip()

def main():
    url = sys.argv[1]
    keep = "--keep" in sys.argv
    fast = "--fast" in sys.argv
    assert_writes_allowed("reference video intelligence report")
    decision = gate(url, "public-reference-download", "PUBLIC")
    if not decision["allowed"]:
        raise SystemExit("BLOCKED: " + decision["reason"])
    os.makedirs(OUT, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="reel_")
    try:
        # 1. download (best <=1080p mp4)
        print("downloading…")
        subprocess.run([YTDLP, "-q", "--no-playlist",
                        # android client dodges YouTube's SABR block; harmless elsewhere
                        "--extractor-args", "youtube:player_client=android",
                        "-f", "b[height<=1080]/b",
                        "--merge-output-format", "mp4",
                        "-o", os.path.join(tmp, "v.%(ext)s"),
                        "--print-to-file", "%(title)s\n%(uploader)s\n%(duration)s", os.path.join(tmp, "meta.txt"),
                        url], check=True)
        vid = next(os.path.join(tmp, f) for f in os.listdir(tmp) if f.startswith("v."))
        title, uploader, dur = (open(os.path.join(tmp, "meta.txt")).read().strip().splitlines() + ["?", "?", "?"])[:3]

        # 2. transcribe (any language)
        print("transcribing…")
        sys.path[:0] = glob.glob(os.path.join(ROOT, "Tools", "venv", "lib", "python3*", "site-packages"))
        from faster_whisper import WhisperModel
        model = WhisperModel("base", device="cpu", compute_type="int8")
        segs, info = model.transcribe(vid)
        lines = [f"[{s.start:5.1f}s] {s.text.strip()}" for s in segs]
        transcript = "\n".join(lines) or "(no speech detected)"

        # 3. SHOT detection — one frame per cut (this is what a remake needs)
        print("detecting shots…")
        fr = os.path.join(tmp, "fr"); os.makedirs(fr)
        r = subprocess.run([FFMPEG, "-loglevel", "info", "-i", vid,
                            "-vf", "select='eq(n\\,0)+gt(scene\\,0.30)',showinfo,scale=960:-2",
                            "-vsync", "vfr", os.path.join(fr, "s%03d.jpg")],
                           capture_output=True, text=True)
        times = re.findall(r"pts_time:([0-9.]+)", r.stderr)
        frames = sorted(os.listdir(fr))
        if len(frames) < 3:  # single-take video -> sample every 3s instead
            for f in frames: os.unlink(os.path.join(fr, f))
            subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", vid,
                            "-vf", "fps=1/3,scale=960:-2", os.path.join(fr, "s%03d.jpg")], check=True)
            frames = sorted(os.listdir(fr))
            times = [str(i*3) for i in range(len(frames))]
        print(f"{len(frames)} shot(s) — describing each…")
        visuals = []
        for i, f in enumerate(frames):
            ts = float(times[i]) if i < len(times) else i*3
            end = float(times[i+1]) if i+1 < len(times) else None
            span = f"{ts:.1f}s→{end:.1f}s ({end-ts:.1f}s)" if end else f"{ts:.1f}s→end"
            try:
                visuals.append(f"### Shot {i+1} · {span}\n{see(os.path.join(fr, f))}")
            except Exception as e:
                visuals.append(f"### Shot {i+1} · {span}\n[vision failed: {e}]")
                break  # ollama down -> don't hammer

        # 4. local content-intelligence pass (degrades honestly if Ollama is unavailable)
        try:
            if fast:
                raise RuntimeError("fast mode: deep local analysis intentionally skipped")
            intelligence = ask_analysis(transcript, visuals)
            analysis_status = "local_model_complete"
        except Exception as error:
            intelligence = {"error": str(error), "priority": "UNREVIEWED",
                            "adapt_for_brand": [], "evidence": []}
            analysis_status = "needs_local_model_or_human_review"
        category = detect_category(title + "\n" + transcript)

        # 5. report + structured record → brain-indexed folder
        slug = re.sub(r"[^\w]+", "_", title.lower())[:50] or "reel"
        day = datetime.date.today().isoformat()
        rp = os.path.join(OUT, f"{day}_{slug}.md")
        jp = os.path.join(OUT, f"{day}_{slug}.json")
        record = {
            "schema_version": "reference-intel/1.0", "title": title, "url": url,
            "uploader": uploader, "duration": float(dur) if str(dur).replace('.', '', 1).isdigit() else dur,
            "language": getattr(info, "language", "?"), "category": category,
            "analyzed_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
            "data_class": "PUBLIC", "transcript": lines, "visuals": visuals,
            "intelligence": intelligence, "analysis_status": analysis_status,
            "review": {"approved": False, "reviewer": None, "reviewed_at": None},
            "retention": {"temporary_media_deleted_after_report": not keep,
                          "original_user_media_deleted": False},
            "provenance": {"tools": ["yt-dlp", "ffmpeg", "faster-whisper", VLM],
                           "external_services": [], "data_left_machine": False},
        }
        json.dump(record, open(jp, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
        open(rp, "w").write(f"""# Reel intel: {title}
> {url} · by {uploader} · {dur}s · language {getattr(info, 'language', '?')} · category {category} · analysed {day}
> Review: **PENDING** · analysis: `{analysis_status}` · public source, processed locally

## Transcript
{transcript}

## Shot-by-shot (scene-cut detection, local qwen)
{chr(10).join(visuals)}

## Content intelligence
```json
{json.dumps(intelligence, indent=2, ensure_ascii=False)}
```

## Decision gate
- Evidence timestamps verified: pending
- Adaptation approved: pending
- Copyright/originality check: do not copy distinctive creative; adapt only general techniques
- Structured record: `{os.path.basename(jp)}`
""")
        update_index({"title": title, "url": url, "category": category,
                      "priority": intelligence.get("priority", "UNREVIEWED"),
                      "analysis_status": analysis_status, "report": os.path.basename(rp),
                      "record": os.path.basename(jp), "analyzed_at": record["analyzed_at"]})
        print(f"\nreport → {os.path.relpath(rp, ROOT)}")
        if keep:
            kept = os.path.join(OUT, os.path.basename(vid))
            shutil.move(vid, kept)
            print(f"video kept → {os.path.relpath(kept, ROOT)}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _tests():
    assert detect_category("Live from the conference: our festival event recap") == "event"
    assert detect_category("How to use this software feature step by step") == "tutorial_explainer"
    assert detect_category("unrelated subject") == "general_reference"
    print("sa_reel self-checks: ok")

if __name__ == "__main__":
    if "--test" in sys.argv:
        _tests()
    else:
        main()
