#!/usr/bin/env python3
"""Render a CapCut draft to MP4 with ffmpeg — no CapCut, no GUI.

The brief: learn the house style from the finished videos and match it with
ffmpeg, experimenting overnight and comparing against the originals, without
touching any CapCut project.

STRICTLY READ-ONLY on his projects. Reads `draft_info.json`, writes only to an
output folder you name. Never opens, locks or modifies a CapCut file.

Why it matters: if a draft can be rendered without CapCut, the NEXT series can be
BUILT programmatically — captions, call-outs, intro, outro — and Saad only reviews.

WHAT IS EXACT (straight from the timeline, no guessing)
  geometry   transform x,y are fractions of HALF the canvas, y positive = UP
             px = W/2 + x*W/2 ,  py = H/2 - y*H/2
  timing     target_timerange / source_timerange in microseconds
  overlays   call-out PNGs with their own scale and transform
  outro      source-in, length, scale, muted — copied from the segment
  colours    text fill, shadow colour/alpha/angle/distance from the style JSON

WHAT IS CALIBRATED (CapCut's size unit is not documented in the file)
  PX_PER_UNIT converts `size * clip.scale` into pixels. Derived from one
  series title card, which the timeline pins precisely: two lines at y +0.075 and -0.075
  on an 1140px canvas sit 85.5px apart, and its units are 18*0.49 = 8.82 — so a
  line box of ~85px means ~8.6 px per unit once leading is allowed for. Captions
  (5*0.75 = 3.75 units) then land at ~32px, which reads correctly at this size.
  Tune with --k and compare; the geometry above does not move when k changes.

    sa_ffrender.py "My Project" -o /tmp/render
    sa_ffrender.py "My Project" -o /tmp/r --seconds 12    # first 12s, quick loop
    sa_ffrender.py --demo
"""
import argparse
import json
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from sa_outro import draft_path, US

FONTS = pathlib.Path.home() / "Library/Containers/com.lemon.lvoverseas/Data/Library/Fonts"
# Two constants, not one — measured, and the measurement says they cannot be shared.
# Every caption is size 5 x scale 0.75 (1315 of 1358 text segments); every title line is
# size 18 x scale 0.49 (35 of them). If both used one constant, then a caption sized to
# read at 1140p forces the title to ~80px, and at 80px the longest title line
# (38 characters) runs off the canvas from its
# x=-0.747 anchor. The widest title that stays on canvas there is 23px. So CapCut is not
# applying one linear map to both, and the honest thing is two dials Saad can judge by eye.
CAPTION_PX = 32            # 5 x 0.75 units -> reads correctly at 1140p
TITLE_PX = 28              # fits the longest title line inside the frame
PX_PER_UNIT = 8.6          # legacy single dial, still honoured by --k


def textfile(text, out_dir, i, key=''):
    """Write the caption to a file and return its path.

    drawtext `text=` escaping is a trap: a caption like "Select the Delivery
    Method, Express Post," has commas, and an escaped comma inside the value
    cascades into the next filter. `textfile=` takes the bytes verbatim.
    """
    # Namespaced per project: rendering several videos in PARALLEL into one output folder
    # had them all writing _text/000.txt, so the last writer won and every render drew the
    # same captions. The drafts were fine; the contact sheet lied.
    d = pathlib.Path(out_dir) / "_text" / (key or "one")
    d.mkdir(parents=True, exist_ok=True)
    f = d / f"{i:03d}.txt"
    f.write_text(text)
    return f


def between(a, b):
    """enable= expression with the commas escaped — an unescaped one ends the filter."""
    return f"enable=between(t\\,{a:.3f}\\,{b:.3f})"


def place(x, y, W, H):
    """CapCut transform -> pixel centre. Pure, and the part that must be exact."""
    return W / 2 + x * W / 2, H / 2 - y * H / 2


PLACEHOLDER = "##_draftpath_placeholder_"


def resolve(path, project_dir):
    """CapCut keeps its own freeze-frames behind a placeholder token.

    A freeze still is stored as
        ##_draftpath_placeholder_<UUID>_##/<hash>_<us>-sdr709.png
    and lives in the project folder itself. Left unresolved, every video with a
    freeze-frame call-out fails to render — which is most of them.
    """
    if path.startswith(PLACEHOLDER):
        return str(pathlib.Path(project_dir) / path.split("_##/", 1)[-1])
    return path


def read_spec(project, k=PX_PER_UNIT):
    """-> dict describing everything on the timeline. Read-only."""
    dp = draft_path(project)
    proj_dir = dp.parents[2] if dp.parent.name != project else dp.parent
    d = json.loads(dp.read_text())
    cv = d.get("canvas_config") or {}
    W, H = cv.get("width", 1920), cv.get("height", 1140)
    fps = d.get("fps", 30)
    vids = {m["id"]: m for m in d["materials"]["videos"]}
    txts = {m["id"]: m for m in (d["materials"].get("texts") or [])}

    auds = {m["id"]: m for m in (d["materials"].get("audios") or [])}
    picture, overlays, texts, outro, audio = [], [], [], None, []
    for tr in d["tracks"]:
        for s in tr.get("segments") or []:
            mid = s.get("material_id")
            g = s["target_timerange"]
            a, dur = g["start"] / US, g["duration"] / US
            cl = s.get("clip") or {}
            tf = cl.get("transform") or {}
            sc = cl.get("scale") or {}
            if mid in vids:
                p = resolve(vids[mid].get("path", ""), proj_dir)
                low = p.lower()
                src = (s.get("source_timerange") or {}).get("start", 0) / US
                item = {"path": p, "t": a, "dur": dur, "src": src,
                        "x": tf.get("x", 0), "y": tf.get("y", 0),
                        "scale": sc.get("x", 1.0), "vol": s.get("volume", 1.0)}
                if "OUTRO" in pathlib.Path(p).name.upper():
                    outro = item
                elif low.endswith((".mp4", ".mov")):
                    picture.append(item)
                elif low.endswith((".png", ".jpg", ".jpeg")):
                    overlays.append(item)
            elif mid in auds:
                audio.append({"path": resolve(auds[mid].get("path", ""), proj_dir), "t": a, "dur": dur,
                              "src": (s.get("source_timerange") or {}).get("start", 0) / US,
                              "vol": s.get("volume", 1.0)})
            elif mid in txts:
                try:
                    c = json.loads(txts[mid].get("content", "{}"))
                except json.JSONDecodeError:
                    continue
                st = (c.get("styles") or [{}])[0]
                fill = (((st.get("fill") or {}).get("content") or {}).get("solid") or {}).get("color", [1, 1, 1])
                sh = (st.get("shadows") or [{}])[0]
                shc = (((sh.get("content") or {}).get("solid") or {}).get("color", [0, 0, 0]))
                raw = st.get("size") or 0
                units = raw * (sc.get("x", 1.0) or 1.0)
                px = TITLE_PX if raw >= 10 else CAPTION_PX
                if k != PX_PER_UNIT:            # --k given: fall back to the single dial
                    px = round(units * k)
                texts.append({
                    "text": c.get("text", ""), "t": a, "dur": dur,
                    "px": px,
                    "font": pathlib.Path((st.get("font") or {}).get("path", "")).name or "Poppins-Regular.ttf",
                    "colour": "0x%02X%02X%02X" % tuple(round(v * 255) for v in fill[:3]),
                    "shadow": {"colour": "0x%02X%02X%02X" % tuple(round(v * 255) for v in shc[:3]),
                               "alpha": sh.get("alpha", 0.55),
                               "dist": sh.get("distance", 5.0),
                               "angle": sh.get("angle", -45.0)},
                    "x": tf.get("x", 0), "y": tf.get("y", 0),
                })
    picture.sort(key=lambda i: i["t"])
    return {"project": project, "W": W, "H": H, "fps": fps,
            "picture": picture, "overlays": overlays, "texts": sorted(texts, key=lambda i: i["t"]),
            "outro": outro, "audio": audio, "end": max([i["t"] + i["dur"] for i in picture], default=0)}


def build(spec, out_dir, seconds=None):
    """-> (cmd list, output path). Renders picture + overlays + captions."""
    W, H = spec["W"], spec["H"]
    o = spec.get("outro")
    end = min(spec["end"], seconds) if seconds else spec["end"]
    if o and not seconds:
        end = o["t"] + o["dur"]        # canvas must cover the outro from the start
    out = pathlib.Path(out_dir) / f"{spec['project'].replace(' ', '_')}_ffmpeg.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)

    inputs, fc, idx = [], [], 0
    # --- base: each picture segment trimmed from its source, laid on a black canvas ---
    fc.append(f"color=c=black:s={W}x{H}:r={spec['fps']}:d={end:.3f}[base]")
    cur = "base"
    for seg in spec["picture"]:
        if seg["t"] >= end:
            continue
        dur = min(seg["dur"], end - seg["t"])
        inputs += ["-ss", f"{seg['src']:.3f}", "-t", f"{dur:.3f}", "-i", seg["path"]]
        lbl = f"p{idx}"
        fc.append(f"[{idx}:v]setpts=PTS-STARTPTS+{seg['t']:.3f}/TB[{lbl}]")
        fc.append(f"[{cur}][{lbl}]overlay=0:0:{between(seg['t'], seg['t']+dur)}[b{idx}]")
        cur = f"b{idx}"
        idx += 1
    # --- call-out PNGs: scaled about their centre, placed by transform ---
    for ov in spec["overlays"]:
        if ov["t"] >= end:
            continue
        inputs += ["-i", ov["path"]]
        cx, cy = place(ov["x"], ov["y"], W, H)
        sw, sh = round(W * ov["scale"]), round(H * ov["scale"])
        fc.append(f"[{idx}:v]scale={sw}:{sh}[o{idx}]")
        fc.append(f"[{cur}][o{idx}]overlay={round(cx - sw/2)}:{round(cy - sh/2)}"
                  f":{between(ov['t'], min(ov['t']+ov['dur'], end))}[c{idx}]")
        cur = f"c{idx}"
        idx += 1
    # --- text: his exact colour, shadow offset from angle+distance ---
    import math
    for i, tx in enumerate(spec["texts"]):
        if tx["t"] >= end or not tx["text"].strip():
            continue
        cx, cy = place(tx["x"], tx["y"], W, H)
        sh = tx["shadow"]
        rad = math.radians(sh["angle"])
        dx, dy = sh["dist"] * math.cos(rad), -sh["dist"] * math.sin(rad)
        f = FONTS / tx["font"]
        if not f.exists():
            f = FONTS / "Poppins-Regular.ttf"
        fc.append(
            f"[{cur}]drawtext=fontfile='{f}':textfile='{textfile(tx['text'], out_dir, i, spec['project'].replace(' ', '_'))}':fontsize={tx['px']}"
            f":fontcolor={tx['colour']}:x={round(cx)}-text_w/2:y={round(cy)}-text_h/2"
            f":shadowcolor={sh['colour']}@{sh['alpha']:.2f}:shadowx={dx:.0f}:shadowy={dy:.0f}"
            f":{between(tx['t'], min(tx['t']+tx['dur'], end))}[t{i}]")
        cur = f"t{i}"

    # --- outro: his own in-point, length and scale, butted to the picture end ---
    if o and not seconds:
        inputs += ["-ss", f"{o['src']:.3f}", "-t", f"{o['dur']:.3f}", "-i", o["path"]]
        ow, oh = round(W * o["scale"]), round(H * o["scale"])
        fc.append(f"[{idx}:v]scale={ow}:{oh},crop={W}:{H}:{(ow-W)//2}:{(oh-H)//2},"
                  f"setpts=PTS-STARTPTS+{o['t']:.3f}/TB[ov]")
        fc.append(f"[{cur}][ov]overlay=0:0:{between(o['t'], o['t']+o['dur'])}[withoutro]")
        cur = "withoutro"
        idx += 1

    fc.append(f"[{cur}]format=yuv420p[v]")
    # Most of these videos carry no audio track at all — the voice-over lives INSIDE the
    # paced screen recording and plays through the picture segment's own volume.
    # (One had zero audio segments; its whole VO was embedded.) So mix both sources.
    sources = [x for x in spec["picture"] if x.get("vol", 1.0) > 0.001] + spec.get("audio", [])
    return cmd_video(spec, fc, inputs, cur, end, out), out


def audio_cmd(spec, out_dir, end):
    """Build the soundtrack in a SEPARATE pass, then mux.

    One graph carrying picture + 100+ call-out PNGs + captions + 59 audio taps runs to
    ~194 inputs, and at that size amix collapsed to a 0.01s stream (one video rendered
    silent) or the muxer rejected the timestamps outright (another). The same audio graph
    on its own is fine — measured -13.3 dB on the silent one. So: video pass, audio pass, mux.
    """
    # A clip CapCut mutes still stores volume 0.001, and 0.001 > 0.001 is False only if
    # the compare is exact — it is not, the stored value is 0.0010000000474974513.
    # Anything at or below 1% is muted; taking it as live doubled the voice.
    def has_audio(path):
        """The intro clips are video-only; feeding one to amix kills the whole graph."""
        r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a",
                            "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(path)],
                           capture_output=True, text=True).stdout
        return bool(r.strip())
    sources = [x for x in ([y for y in spec["picture"] if y.get("vol", 1.0) > 0.01] + spec.get("audio", []))
               if has_audio(x["path"])]
    inputs, fc, labels = [], [], []
    for seg in sources:
        if seg["t"] >= end or seg["vol"] <= 0.01:
            continue
        dur = min(seg["dur"], end - seg["t"])
        i = len(labels)
        inputs += ["-ss", f"{seg['src']:.3f}", "-t", f"{dur:.3f}", "-i", seg["path"]]
        fc.append(f"[{i}:a]adelay={round(seg['t']*1000)}|{round(seg['t']*1000)},"
                  f"volume={seg['vol']:.3f}[a{i}]")
        labels.append(f"[a{i}]")
    if not labels:
        return None, None
    wav = pathlib.Path(out_dir) / "_audio.wav"
    fc.append(f"{''.join(labels)}amix=inputs={len(labels)}:normalize=0:dropout_transition=0[a]")
    return (["ffmpeg", "-v", "error", "-y"] + inputs +
            ["-filter_complex", ";".join(fc), "-map", "[a]",
             "-t", f"{end:.3f}", str(wav)]), wav


def cmd_video(spec, fc, inputs, cur, end, out):
    return (["ffmpeg", "-v", "error", "-y"] + inputs +
            ["-filter_complex", ";".join(fc), "-map", "[v]",
             "-c:v", "libx264", "-crf", "18", "-preset", "medium",
             "-r", str(spec["fps"]), "-t", f"{end:.3f}", str(out)])


def render(spec, out_dir, seconds=None):
    """Video pass -> audio pass -> mux. Returns the finished file."""
    cmd, out = build(spec, out_dir, seconds)
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError("video pass: " + r.stderr[-500:])
    end = spec["end"] + (spec["outro"]["dur"] if (spec["outro"] and not seconds) else 0)
    acmd, wav = audio_cmd(spec, out_dir, min(end, seconds) if seconds else end)
    if not acmd:
        return out
    r = subprocess.run(acmd, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError("audio pass: " + r.stderr[-500:])
    final = out.with_name(out.stem + "_av.mp4")
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(out), "-i", str(wav),
                        "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                        "-c:a", "aac", "-b:a", "192k", str(final)],
                       capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError("mux: " + r.stderr[-500:])
    out.unlink(missing_ok=True)
    wav.unlink(missing_ok=True)
    return final.rename(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("-o", "--out", default="/tmp/ffrender")
    ap.add_argument("--seconds", type=float)
    ap.add_argument("--k", type=float, default=PX_PER_UNIT)
    ap.add_argument("--spec-only", action="store_true")
    a = ap.parse_args()

    spec = read_spec(a.project, a.k)
    print(f"  {a.project}")
    print(f"  canvas {spec['W']}x{spec['H']} @{spec['fps']}fps   picture ends {spec['end']:.2f}s")
    print(f"  {len(spec['picture'])} picture segs · {len(spec['overlays'])} call-outs · "
          f"{len(spec['texts'])} text · outro {'yes' if spec['outro'] else 'no'}")
    if spec["texts"]:
        t = spec["texts"][0]
        cx, cy = place(t["x"], t["y"], spec["W"], spec["H"])
        print(f"  first text: {t['px']}px {t['font']} at ({cx:.0f},{cy:.0f})  \"{t['text'][:40]}\"")
    if a.spec_only:
        print(json.dumps(spec, indent=1)[:1500])
        return 0
    try:
        out = render(spec, a.out, a.seconds)
    except RuntimeError as e:
        print(f"  ffmpeg failed: {e}")
        return 1
    print(f"  -> {out}")
    return 0


def demo():
    """Self-check: the geometry, which must be exact whatever k is."""
    W, H = 1920, 1140
    assert place(0, 0, W, H) == (960, 570), "centre"
    x, y = place(0, -0.892, W, H)
    assert x == 960 and abs(y - 1078.4) < 0.5, f"caption sits near the bottom, got {y}"
    x, _ = place(-0.747, 0, W, H)
    assert abs(x - 242.9) < 0.5, f"title sits left, got {x}"
    a = place(0, 0.075, W, H)[1]
    b = place(0, -0.075, W, H)[1]
    assert abs((b - a) - 85.5) < 0.1, "the two title lines are 85.5px apart"
    assert resolve("##_draftpath_placeholder_X_##/a.png", "/p") == "/p/a.png"
    assert resolve("/abs/b.png", "/p") == "/abs/b.png"
    assert between(1.0, 2.0) == r"enable=between(t\,1.000\,2.000)"
    print("demo ok (geometry exact, escaping)")


if __name__ == "__main__":
    sys.exit(demo() if "--demo" in sys.argv else main())
