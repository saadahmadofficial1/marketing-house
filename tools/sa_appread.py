#!/usr/bin/env python3
"""sa_appread — read a phone/app screen-recording as TEXT, on-device, zero tokens.

Built for a series of phone-app training videos. Same idea as
sa_screenmap, but it keeps the whole SCREEN STATE at each moment instead of just a
vocabulary of labels, and collapses runs of identical screens into one entry — so an
agent can read "what was on screen, and when it changed" without looking at pixels.

    Tools/venv/bin/python3 Tools/sa_appread.py clip.mp4 --out DIR [--every 1.5]

Output in DIR:
    screens.json   [{i, t, t_end, dur, text, elements}]  — one entry per distinct screen;
                   `elements` is [{text, x, y, w, h}] in SOURCE pixels, so a call-out box
                   can be placed on the exact element instead of measured by hand
    screens.md     the same text, readable, for an agent to read straight

Frames are deleted as it goes (--keep to keep them). Apple's Vision OCR runs
on-device; this runs locally and uploads nothing.

LIMITS, so nobody reads the output as gospel: OCR misreads small UI text and icon-only
buttons are invisible to it. It reads TEXT, not taps — pair it with the transcript and
with eyes on the frames before calling any step confirmed.
"""
import argparse, json, os, pathlib, re, shutil, subprocess, sys

FFMPEG = os.path.expanduser("~/.local/bin/ffmpeg")
if not os.path.exists(FFMPEG):
    FFMPEG = shutil.which("ffmpeg") or "ffmpeg"
HERE = pathlib.Path(__file__).resolve().parent
OCR = HERE / "bin" / "sa_ocr"


def words(t):
    return set(re.findall(r"[A-Za-z]{3,}", t.lower()))


def parse_elements(payload):
    """sa_ocr --boxes gives 'text@x,y,w,h | text@x,y,w,h'. A label may itself contain
    '@' or ',', so split on the LAST '@' and only accept four integers after it —
    anything else is kept as text with no box rather than silently dropped."""
    out = []
    for part in payload.split(" | "):
        part = part.strip()
        if not part:
            continue
        text, sep, coords = part.rpartition("@")
        if sep:
            bits = coords.split(",")
            if len(bits) == 4 and all(b.strip().lstrip("-").isdigit() for b in bits):
                x, y, w, h = (int(b) for b in bits)
                out.append({"text": text.strip(), "x": x, "y": y, "w": w, "h": h})
                continue
        out.append({"text": part, "x": None, "y": None, "w": None, "h": None})
    return out


def find_element(screen, needle):
    """The box for the element whose text contains `needle` (case-insensitive).
    Returns None when it is not on that screen — callers must treat that as
    'do not place a marking', never as 'place it somewhere sensible'."""
    n = needle.lower()
    for e in screen.get("elements", []):
        if e.get("x") is not None and n in e["text"].lower():
            return e
    return None


def same_screen(a, b, thresh=0.90):
    """Two screens count as the same if their word sets barely differ. A changing
    clock or a typed character should not open a new screen."""
    wa, wb = words(a), words(b)
    if not wa and not wb:
        return True
    if not wa or not wb:
        return False
    return len(wa & wb) / len(wa | wb) >= thresh


def run(video, out, every, keep):
    out = pathlib.Path(out)
    frames = out / "frames"
    frames.mkdir(parents=True, exist_ok=True)
    subprocess.run([FFMPEG, "-y", "-v", "error", "-i", str(video),
                    "-vf", f"fps=1/{every}", "-q:v", "3",
                    str(frames / "f_%05d.jpg")], check=True)
    jpgs = sorted(frames.glob("f_*.jpg"))
    if not jpgs:
        sys.exit("no frames extracted")
    res = subprocess.run([str(OCR), "--boxes"] + [str(j) for j in jpgs],
                         capture_output=True, text=True)
    screens, prev = [], None
    for line in res.stdout.splitlines():
        path, _, payload = line.partition("\t")
        idx = int(pathlib.Path(path).stem.split("_")[1]) - 1
        t = round(idx * every, 2)
        els = parse_elements(payload)
        text = " | ".join(e["text"] for e in els)
        if prev is not None and same_screen(prev["text"], text):
            prev["t_end"] = t + every          # same screen still up
            continue
        prev = {"i": len(screens) + 1, "t": t, "t_end": t + every,
                "text": text, "elements": els}
        screens.append(prev)
    for s in screens:
        s["t_end"] = round(s["t_end"], 2)
        s["dur"] = round(s["t_end"] - s["t"], 2)
    (out / "screens.json").write_text(json.dumps(
        {"video": str(video), "every": every, "screens": screens}, indent=1))
    md = [f"# {pathlib.Path(video).name} — {len(screens)} distinct screens "
          f"(sampled every {every}s)\n"]
    for s in screens:
        md.append(f"\n## [{s['t']:.1f}s -> {s['t_end']:.1f}s] ({s['dur']:.1f}s)\n"
                  + (s["text"].replace(" | ", "\n") or "(no text read)") + "\n")
    (out / "screens.md").write_text("".join(md))
    if not keep:
        shutil.rmtree(frames)
    print(f"{len(jpgs)} frames -> {len(screens)} screens -> {out}/screens.md")


def selftest():
    """One runnable check: the screen-collapser is the only real logic here."""
    assert same_screen("Ticket Create Save", "Ticket Create Save")
    assert same_screen("Ticket Create Save 14:02", "Ticket Create Save 14:03")
    assert not same_screen("Ticket Create Save", "Login Username Password")
    assert not same_screen("", "Login Username Password")
    # box parsing: the happy case, a label containing '@', and a malformed tail
    els = parse_elements("Approve@791,1820,229,45 | a@example.com@10,20,30,40 | Broken@1,2")
    assert els[0] == {"text": "Approve", "x": 791, "y": 1820, "w": 229, "h": 45}, els[0]
    assert els[1]["text"] == "a@example.com" and els[1]["y"] == 20, els[1]
    assert els[2]["text"] == "Broken@1,2" and els[2]["x"] is None, els[2]
    scr = {"elements": els}
    assert find_element(scr, "appro")["x"] == 791
    assert find_element(scr, "nowhere") is None
    print("ok")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("video", nargs="?")
    p.add_argument("--out")
    p.add_argument("--every", type=float, default=1.5)
    p.add_argument("--keep", action="store_true")
    p.add_argument("--test", action="store_true")
    a = p.parse_args()
    if a.test:
        selftest()
    elif a.video and a.out:
        run(a.video, a.out, a.every, a.keep)
    else:
        p.error("need video and --out (or --test)")
