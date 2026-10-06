#!/usr/bin/env python3
"""Event film — plan-driven renderer v2 (speed-ramp curves, transitions, QA).

  python3 sa_event_render.py PLAN.json render      -> shots2/ + Event_Film_<version>.mp4
  python3 sa_event_render.py PLAN.json qa          -> qa2_<version>_N.jpg (start/mid/end of every shot)
  python3 sa_event_render.py --test                -> self-check of the ramp maths
Plan: {"version","music":{"segments":[{src_in,src_out,at,fade_in,fade_out}]},
       "shots":[{id,clip,src_in,dur,speed|ramp,zoom,anchor,fx,nat,trans,trans_dur,note}],
       "end":{"dur","xfade"}}
ramp = [[u, speed], ...] over film-time fraction u in [0,1], piecewise linear (e.g. fast->slow->fast).
trans = cut | xfade | flash | dip  (into this shot). Shots are back to back; timeline = cumulative dur.
"""
import json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.environ.get("EVENT_SRC", os.path.join(HERE, "footage"))           # folder of camera clips (<clip>.MP4)
LOGO = os.environ.get("EVENT_LOGO", os.path.join(HERE, "assets", "logo.png"))
FPS, W, H = 30, 1920, 1080
PIECES = 10                                   # ramp resolution (constant-speed pieces per ramped shot)
XF = {"xfade": "fade", "crossfade": "fade", "slowfade": "fade", "glow": "fadewhite", "fadeshift": "smoothleft"}  # CapCut names -> ffmpeg
GRADE = os.environ.get("EVENT_GRADE", "eq=contrast=1.10:saturation=1.34:brightness=-0.015,"
         "colorbalance=rs=-0.01:bs=0.01:rm=-0.045:bm=0.035:rh=-0.03:bh=0.03,"
         "curves=all='0/0.02 0.5/0.49 0.85/0.92 1/1',unsharp=5:5:0.45")
# g5: calibrated against a reference event film's export on 12 frames: contrast std 0.296 (reference >=0.27),
# white p98 0.998, saturation +25% over the raw camera files, warmth +0.008 (reference -0.01..+0.01).
# An earlier warm/flat/grey-white grade was rejected.
LED_WARM = "colorbalance=rs=0.05:bs=-0.08:rm=0.09:bm=-0.09:rh=0.03:bh=-0.04"   # per-shot fix for faces lit blue by the LED walls


def speed_at(ramp, u):
    for (u0, s0), (u1, s1) in zip(ramp, ramp[1:]):
        if u0 <= u <= u1:
            return s0 + (s1 - s0) * (u - u0) / max(u1 - u0, 1e-9)
    return ramp[-1][1]


def pieces_for(shot, extra=0.0):
    """Constant-speed pieces covering dur (+ a tail handle at the final speed)."""
    if "ramp" in shot:
        d = shot["dur"] / PIECES
        out = [(d, speed_at(shot["ramp"], (i + 0.5) / PIECES)) for i in range(PIECES)]
    else:
        out = [(shot["dur"], float(shot.get("speed", 1.0)))]
    if extra > 0:
        out.append((extra, out[-1][1]))
    return out


def src_span(shot, extra=0.0):
    return sum(d * s for d, s in pieces_for(shot, extra))


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.exit("ffmpeg failed:\n" + " ".join(cmd)[:3000] + "\n" + r.stderr[-2500:])


def layout(plan):
    t = 0.0
    for i, s in enumerate(plan["shots"]):
        s["t0"] = round(t, 4); t += s["dur"]; s["t1"] = round(t, 4)
        nxt = plan["shots"][i + 1] if i + 1 < len(plan["shots"]) else None
        s["handle"] = nxt.get("trans_dur", 0.5) if nxt and nxt.get("trans") in XF else 0.0
        s["file"] = s.get("file") or os.path.join(SRC, s["clip"] + ".MP4")
    if plan["shots"]:
        plan["shots"][-1]["handle"] = plan["end"]["xfade"]
    return t


def render_shot(s, outdir):
    out = os.path.join(outdir, s["id"] + ".mov")
    ps = pieces_for(s, s["handle"])
    span = sum(d * sp for d, sp in ps)
    n = round(s["t1"] * FPS) - round(s["t0"] * FPS) + round(s["handle"] * FPS)
    fl, pos = [], 0.0
    if s.get("freeze"):                           # one still frame held for the shot (a stills bridge)
        ps, span = [(s["dur"] + s["handle"], 1.0)], 0.1
        fl.append("[0:v]trim=end_frame=1,setpts=PTS-STARTPTS,fps=%d,tpad=stop_mode=clone:stop_duration=%.3f[p0]" % (FPS, s["dur"] + s["handle"] + 0.5))
    else:
        fl.append("[0:v]split=%d%s" % (len(ps), "".join("[r%d]" % i for i in range(len(ps)))))
        for i, (d, sp) in enumerate(ps):
            fl.append("[r%d]trim=start=%.4f:duration=%.4f,setpts=(PTS-STARTPTS)/%.4f,fps=%d[p%d]" % (i, pos, d * sp, sp, FPS, i))
            pos += d * sp
    z0, z1 = s.get("zoom", [1.0, 1.0]); ax, ay = s.get("anchor", [0.5, 0.5])
    chain = "".join("[p%d]" % i for i in range(len(ps))) + "concat=n=%d:v=1:a=0," % len(ps)
    chain += "scale=3840:2160,zoompan=z='%.5f+%.6f*on/%d':x='(iw-iw/zoom)*%.3f':y='(ih-ih/zoom)*%.3f':d=1:s=%dx%d:fps=%d," % (
        z0, z1 - z0, max(n - 1, 1), ax, ay, W, H, FPS)
    if s.get("fx"):
        chain += s["fx"] + ","
    if s.get("led_warm"):
        chain += LED_WARM + ","
    chain += GRADE
    if s.get("blurin"):                           # reference-film opener: blur 0.5 -> 0 over 0.7s
        chain += ",split[sa][sb];[sb]gblur=sigma=14[sbl];[sbl][sa]xfade=transition=fade:duration=0.7:offset=0"
    tr = s.get("trans", "cut"); td = s.get("trans_dur", 0.3)
    if tr == "flash":
        chain += ",fade=t=in:st=0:d=%.3f:color=white" % min(td, 0.25)
    elif tr == "dip":
        chain += ",fade=t=in:st=0:d=%.3f" % td
    chain += ",tpad=stop_mode=clone:stop=8,trim=end_frame=%d,format=yuv422p10le[v]" % n
    fl.append(chain)
    run(["ffmpeg", "-v", "error", "-y", "-hwaccel", "videotoolbox", "-ss", "%.4f" % s["src_in"], "-t", "%.4f" % (span + 0.3),
         "-i", s["file"], "-filter_complex", ";".join(fl), "-map", "[v]", "-c:v", "prores_ks", "-profile:v", "2", "-an", out])
    return out


HF_CARD = os.path.join(HERE, "hf_endcard", "renders", "endcard.mp4")   # HyperFrames tagline + logo (6.4s)


def render_card(plan, outdir):
    out = os.path.join(outdir, "END.mov"); dur = plan["end"]["dur"]
    if os.path.exists(HF_CARD):
        run(["ffmpeg", "-v", "error", "-y", "-i", HF_CARD, "-t", "%.2f" % dur, "-vf", "fps=%d,scale=%d:%d,format=yuv422p10le" % (FPS, W, H),
             "-c:v", "prores_ks", "-profile:v", "2", "-an", out])
        return out
    run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=white:s=%dx%d:r=%d:d=%.2f" % (W, H, FPS, dur),
         "-loop", "1", "-t", "%.2f" % dur, "-i", LOGO, "-filter_complex",
         "[1:v]scale=-1:340,format=rgba,fade=t=in:st=0.4:d=0.8:alpha=1[l];[0:v][l]overlay=(W-w)/2:(H-h)/2,format=yuv422p10le[v]",
         "-map", "[v]", "-c:v", "prores_ks", "-profile:v", "2", out])
    return out


def render(plan, path):
    total = layout(plan)
    ver = plan.get("version", "v4")
    outdir = os.path.join(HERE, "shots2", ver); os.makedirs(outdir, exist_ok=True)
    only = os.environ.get("EVENT_SHOTS")
    files = []
    for s in plan["shots"]:
        f = os.path.join(outdir, s["id"] + ".mov")
        if only != "none" and (not only or s["id"] in only.split(",") or not os.path.exists(f)):
            print("render", s["id"], s["clip"], s.get("note", "")[:70]); sys.stdout.flush()
            render_shot(s, outdir)
        files.append(f)
    card = render_card(plan, outdir)
    end_t = total + plan["end"]["dur"] - plan["end"]["xfade"]
    cmd = ["ffmpeg", "-v", "warning", "-y"]
    for f in files + [card]:
        cmd += ["-i", f]
    v = ["[%d:v]settb=1/%d,setpts=N/%d/TB[i%d]" % (i, FPS, FPS, i) for i in range(len(files) + 1)]
    cur, cur_len = "[i0]", plan["shots"][0]["dur"] + plan["shots"][0]["handle"]
    for i in range(1, len(files) + 1):
        if i < len(files):
            s = plan["shots"][i]; nxt_len = s["dur"] + s["handle"]; tr = s.get("trans", "cut")
        else:
            s = None; nxt_len = plan["end"]["dur"]; tr = "slowfade"
        prev = plan["shots"][i - 1]
        lab = "[c%d]" % i
        if tr in XF:
            dur = prev["handle"]
            v.append("%s[i%d]xfade=transition=%s:duration=%.3f:offset=%.4f%s" % (cur, i, XF[tr], dur, cur_len - dur, lab))
            cur_len = cur_len - dur + nxt_len
        else:   # hard cut: drop prev handle (none) and append
            v.append("%s[i%d]concat=n=2:v=1:a=0,settb=1/%d,setpts=N/%d/TB%s" % (cur, i, FPS, FPS, lab))
            cur_len += nxt_len
        cur = lab
    v.append("%sfade=t=in:st=0:d=0.4[vout]" % cur)
    # audio: music segments + natural sound
    mus = plan["music"]["file"]; mi = len(files) + 1
    cmd += ["-i", mus]
    segs = plan["music"]["segments"]
    a = ["[%d:a]asplit=%d%s" % (mi, len(segs), "".join("[m%d]" % k for k in range(len(segs))))]
    for k, g in enumerate(segs):
        ln = g["src_out"] - g["src_in"]
        a.append("[m%d]atrim=%.3f:%.3f,asetpts=PTS-STARTPTS,afade=t=in:d=%.3f,afade=t=out:st=%.3f:d=%.3f,adelay=%d|%d[ms%d]" % (
            k, g["src_in"], g["src_out"], g.get("fade_in", 0.02), ln - g.get("fade_out", 0.02), g.get("fade_out", 0.02),
            g["at"] * 1000, g["at"] * 1000, k))
    mix = ["[ms%d]" % k for k in range(len(segs))]
    j = 0
    for s in plan["shots"]:
        if s.get("nat", 0) <= 0:
            continue
        sp = float(s.get("speed", 1.0))
        cmd += ["-ss", "%.3f" % s["src_in"], "-t", "%.3f" % (s["dur"] * sp), "-i", s["file"]]
        a.append("[%d:a]aformat=channel_layouts=stereo,%svolume=%.3f,afade=t=in:d=0.12,afade=t=out:st=%.3f:d=0.15,adelay=%d|%d[n%d]" % (
            mi + 1 + j, ("atempo=%.3f," % sp) if abs(sp - 1) > 0.01 and sp >= 0.5 else "", s["nat"], max(s["dur"] - 0.15, 0),
            s["t0"] * 1000, s["t0"] * 1000, j))
        mix.append("[n%d]" % j); j += 1
    a.append("".join(mix) + "amix=inputs=%d:normalize=0:duration=longest,atrim=0:%.3f,afade=t=out:st=%.3f:d=1.5,loudnorm=I=-17:TP=-1.5:LRA=7[aout]" % (
        len(mix), end_t, end_t - 1.5))
    out = os.path.join(HERE, "Event_Film_%s.mp4" % ver)
    cmd += ["-filter_complex", ";".join(v + a), "-map", "[vout]", "-map", "[aout]", "-c:v", "libx264", "-preset", "slow",
            "-crf", "16", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "256k", "-ar", "48000", "-movflags", "+faststart",
            "-t", "%.3f" % end_t, out]
    run(cmd)
    print("-> %s (%.2fs)" % (out, end_t))


def qa(plan):
    from PIL import Image, ImageDraw, ImageFont
    layout(plan); ver = plan.get("version", "v4")
    out = os.path.join(HERE, "Event_Film_%s.mp4" % ver)
    qdir = os.path.join(HERE, "qa2", ver); os.makedirs(qdir, exist_ok=True)
    font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 18)
    rows = []
    for s in plan["shots"]:
        ims = []
        for t in (s["t0"] + 0.04, (s["t0"] + s["t1"]) / 2, s["t1"] - 0.05):
            f = os.path.join(qdir, "%s_%.2f.jpg" % (s["id"], t))
            run(["ffmpeg", "-v", "error", "-y", "-ss", "%.3f" % t, "-i", out, "-frames:v", "1", "-vf", "scale=400:-2", f])
            ims.append(Image.open(f))
        rows.append((s, ims))
    per = 10
    for p in range(0, len(rows), per):
        chunk = rows[p:p + per]
        sheet = Image.new("RGB", (400 * 3, 247 * len(chunk)), "black"); d = ImageDraw.Draw(sheet)
        for r, (s, ims) in enumerate(chunk):
            for c, im in enumerate(ims):
                sheet.paste(im, (c * 400, r * 247 + 22))
            d.text((4, r * 247 + 2), "%s %s %.2f-%.2f %s %s" % (s["id"], s["clip"], s["t0"], s["t1"],
                    ("ramp" if "ramp" in s else "x%.2f" % float(s.get("speed", 1))), s.get("note", "")[:70]), fill="yellow", font=font)
        sheet.save(os.path.join(HERE, "qa2_%s_%d.jpg" % (ver, p // per + 1)), quality=82)
    print("qa sheets:", (len(rows) + per - 1) // per)


def test():
    s = {"dur": 2.0, "ramp": [[0, 1.0], [0.4, 1.0], [0.55, 0.35], [1, 0.35]]}
    ps = pieces_for(s)
    assert abs(sum(d for d, _ in ps) - 2.0) < 1e-9
    assert ps[0][1] == 1.0 and abs(ps[-1][1] - 0.35) < 1e-9
    assert abs(speed_at([[0, 1], [1, 0.5]], 0.5) - 0.75) < 1e-9
    assert abs(src_span({"dur": 2.0, "speed": 0.5}) - 1.0) < 1e-9
    assert abs(src_span({"dur": 1.0, "speed": 1.0}, extra=0.3) - 1.3) < 1e-9
    print("ok")


if __name__ == "__main__":
    if sys.argv[1] == "--test":
        test(); sys.exit()
    plan = json.load(open(sys.argv[1]))
    plan["music"].setdefault("file", os.path.join(HERE, "assets", "music.mp3"))
    (render if sys.argv[2] == "render" else qa)(plan, *([sys.argv[1]] if sys.argv[2] == "render" else []))
