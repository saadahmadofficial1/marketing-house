#!/usr/bin/env python3
"""Give Claude eyes on any video — locally, zero tokens.

  sa_see.py video.mov                    # 1 frame every 5s (overview)
  sa_see.py video.mov --every 0.5        # dense read (floats fine)
  sa_see.py video.mov --every 0.02       # EVERY frame of a 50fps clip
  sa_see.py video.mov --prompt "..."     # targeted question per frame
  sa_see.py --test

Streaming + storage-safe: extracts one small window of frames at a time,
describes each with a local Ollama VLM, appends to analysis.json, DELETES
the jpg, moves to the next window — a 3000-frame dense read never holds
more than ~120 small jpegs on disk. Frames are described by a local Ollama model;
this check runs locally and uploads nothing.

Output: <video>_seen/analysis.json + analysis.md (the bit Claude reads).
Model: qwen3-vl:2b default (daytime-safe); --model qwen3-vl:8b at night
for higher fidelity.
"""
import os, sys, json, base64, shutil, subprocess, urllib.request

_FF = os.path.expanduser("~/.local/bin/ffmpeg")
FFMPEG = _FF if os.path.exists(_FF) else (shutil.which("ffmpeg") or "ffmpeg")
FFPROBE = FFMPEG.replace("ffmpeg", "ffprobe")
OLLAMA = "http://localhost:11434/api/generate"
CHUNK = 120  # frames per extraction window — caps peak disk use

PROMPT = ("Describe this video frame factually in 2-3 sentences: any people "
          "(framing: full body / waist-up / close-up; are feet and hands in "
          "frame; expression; where they are looking), camera framing and "
          "angle, vehicles or key objects, lighting, any readable on-screen "
          "text (quote it), and any visual defects — warped hands, distorted "
          "face, extra limbs, melted or bent objects, flicker artifacts.")


def ask(model, img_path, prompt=PROMPT):
    b64 = base64.b64encode(open(img_path, "rb").read()).decode()
    req = urllib.request.Request(OLLAMA, data=json.dumps(
        {"model": model, "prompt": prompt, "images": [b64], "stream": False,
         "think": False, "keep_alive": "5m"}).encode(),
        headers={"Content-Type": "application/json"})
    r = json.loads(urllib.request.urlopen(req, timeout=300).read())
    return (r.get("response") or r.get("thinking") or "").strip()


def duration(vid):
    out = subprocess.run([FFPROBE, "-v", "error", "-show_entries",
                          "format=duration", "-of", "csv=p=0", vid],
                         capture_output=True, text=True, check=True).stdout
    return float(out.strip())


def see(vid, every=5.0, model=None, out=None, prompt=PROMPT, keep=False):
    vid = os.path.abspath(vid)
    model = model or os.environ.get("SA_VLM", "qwen3-vl:2b")
    out = out or os.path.splitext(vid)[0] + "_seen"
    frames = os.path.join(out, "frames")
    os.makedirs(frames, exist_ok=True)
    dur = duration(vid)
    total = max(1, int(dur / every))
    print(f"{total} frames (1 per {every}s of {dur:.1f}s) — asking {model}…")

    data, t0, n = [], 0.0, 0
    result = {"video": vid, "every": every, "model": model, "prompt": prompt,
              "frames": data}

    def flush():
        json.dump(result, open(os.path.join(out, "analysis.json"), "w"), indent=1)

    while t0 < dur:
        win = CHUNK * every
        subprocess.run([FFMPEG, "-y", "-loglevel", "error",
                        "-ss", str(t0), "-t", str(win), "-i", vid,
                        "-vf", f"fps=1/{every},scale=1280:-2",
                        os.path.join(frames, "w%04d.jpg")], check=True)
        shots = sorted(os.listdir(frames))[:CHUNK]
        for i, f in enumerate(shots):
            t = round(t0 + i * every, 3)
            if t >= dur:
                break
            p = os.path.join(frames, f)
            try:
                desc = ask(model, p, prompt)
            except Exception as e:
                desc = f"[vision failed: {e}]"
            data.append({"t": t, "desc": desc})
            n += 1
            print(f"  {t:>8.2f}s  {desc[:90]}")
            if not keep:
                os.remove(p)
        for f in os.listdir(frames):  # window leftovers beyond CHUNK
            if not keep:
                os.remove(os.path.join(frames, f))
        flush()
        t0 += win

    if not keep and os.path.isdir(frames) and not os.listdir(frames):
        os.rmdir(frames)
    md = [f"# Seen: {os.path.basename(vid)} — {n} frames @ 1/{every}s ({model})\n"]
    md += [f"- **{d['t']}s** — {d['desc']}" for d in data]
    open(os.path.join(out, "analysis.md"), "w").write("\n".join(md) + "\n")
    print(f"\n→ {out}/analysis.json + analysis.md")
    return result


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        raise SystemExit(__doc__)

    def opt(name, cast, default):
        return cast(sys.argv[sys.argv.index(name) + 1]) if name in sys.argv else default

    see(args[0],
        every=opt("--every", float, 5.0),
        model=opt("--model", str, None),
        out=opt("--out", str, None),
        prompt=opt("--prompt", str, PROMPT),
        keep="--keep-frames" in sys.argv)


def self_test():
    global ask
    import tempfile
    real = ask
    ask = lambda m, p, pr=PROMPT: "stub description"
    try:
        with tempfile.TemporaryDirectory() as tmp:
            clip = os.path.join(tmp, "t.mp4")
            subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-f", "lavfi",
                            "-i", "testsrc=duration=4:size=320x180:rate=25",
                            clip], check=True)
            r = see(clip, every=0.5, out=os.path.join(tmp, "out"))
            assert 7 <= len(r["frames"]) <= 9, len(r["frames"])
            assert r["frames"][2]["t"] == 1.0
            assert not os.path.isdir(os.path.join(tmp, "out", "frames"))  # deleted
            assert os.path.exists(os.path.join(tmp, "out", "analysis.json"))
    finally:
        ask = real
    print("sa_see self-checks: ok")


if __name__ == "__main__":
    self_test() if "--test" in sys.argv else main()
