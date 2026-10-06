"""Screen-anchored pacing plan for one module -> an sa_dubcut plan.json.

Each line owns a ZONE of the recording (from its screen anchor to the next). Its window
is the motion in that zone plus static padding up to voice+gap. Anything in the zone
outside the window contains no motion by construction, so dropping it is invisible:
the frames either side of the cut are the same frozen screen. Nothing on screen is lost.

    python3 sa_plan_pacing.py module.json
    module.json: {"video", "vo_dir", "bounds": [line start anchors, s], "out",
                  optional "gap" (default 0.9) and "exclude": [[start, end], ...] faults to cut}
"""
import json, subprocess, sys, re, os

FFMPEG = os.path.expanduser("~/.local/bin/ffmpeg")
if not os.path.exists(FFMPEG):
    FFMPEG = "ffmpeg"

def freezes(video, n=0.002, d=1.2):
    out = subprocess.run([FFMPEG, "-hide_banner", "-nostats",
                          "-i", video, "-vf", f"freezedetect=n={n}:d={d}", "-map", "0:v:0",
                          "-f", "null", "-"], capture_output=True, text=True).stderr
    s = [float(x) for x in re.findall(r"freeze_start: ([0-9.]+)", out)]
    e = [float(x) for x in re.findall(r"freeze_end: ([0-9.]+)", out)]
    return list(zip(s, e))

def dur(p):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                 "-of", "csv=p=0", p], capture_output=True, text=True).stdout)

def motion_in(a, b, F):
    """Motion spans inside [a,b] = [a,b] minus the freezes, PLUS instant cuts.

    freezedetect can end one freeze and start the next on the same frame: the screen
    changed in a single frame (a tap-through). That gap is zero-length, so plain
    subtraction never sees it - the Jobs tab visit in the Driver module vanished that
    way. Each such seam is recorded as a 0.1s motion event."""
    spans, t = [], a
    Fs = sorted(F)
    for k, (fs, fe) in enumerate(Fs):
        if fe <= a or fs >= b:
            continue
        if fs > t:
            spans.append((t, min(fs, b)))
        t = max(t, fe)
        nxt = Fs[k + 1][0] if k + 1 < len(Fs) else None
        if nxt is not None and nxt - fe < 0.05 and a < fe < b:
            spans.append((fe - 0.05, fe + 0.05))
    if t < b:
        spans.append((t, b))
    spans.sort()
    return [(x, y) for x, y in spans if y - x > 0.05]
    # NOTE: a 0.1s seam between two freezes IS a screen change (an instant tap-through).
    # Filtering seams dropped the Jobs-tab visit from the Driver module (23 Sep).

def subtract(spans, cuts):
    """spans minus cuts (both lists of (a, b))."""
    out = []
    for a, b in spans:
        pieces = [(a, b)]
        for c0, c1 in cuts:
            nxt = []
            for x, y in pieces:
                if c1 <= x or c0 >= y:
                    nxt.append((x, y))
                    continue
                if c0 > x:
                    nxt.append((x, c0))
                if c1 < y:
                    nxt.append((c1, y))
            pieces = nxt
        out += [(x, y) for x, y in pieces if y - x > 0.05]
    return out


def tighten(video, keeps, out):
    """Render the source with the excluded faults cut out. sa_dubcut expects a pre-cut
    source plus `keeps` to map original times onto it."""
    ff = FFMPEG
    parts = "".join(f"[0:v]trim=start={a:.3f}:end={b:.3f},setpts=PTS-STARTPTS[v{i}];"
                    for i, (a, b) in enumerate(keeps))
    fc = parts + "".join(f"[v{i}]" for i in range(len(keeps))) + f"concat=n={len(keeps)}:v=1:a=0[v]"
    subprocess.run([ff, "-y", "-v", "error", "-i", video, "-filter_complex", fc, "-map", "[v]",
                    "-c:v", "libx264", "-crf", "16", "-preset", "medium", "-r", "30", out], check=True)


def plan(video, bounds, vos, gap=0.9, pre=0.3, post=1.2, exclude=()):   # post: let the new screen land
    F = freezes(video)
    X = sorted(tuple(e) for e in exclude)
    T = dur(video)
    edges = list(bounds) + [T]
    segs, report = [], []
    for i, vo in enumerate(vos):
        za, zb = edges[i], edges[i + 1]
        need = dur(vo) + gap
        # the seam at the very start of a zone is the screen this line opens on - it
        # must not drag the window back across the previous screen's frozen stretch
        mot = [m for m in subtract(motion_in(za, zb, F), X)          # faults are cut, not kept
               if not (m[0] <= za + 0.25 and m[1] - m[0] < 0.3)]   # only a SHORT seam at the start
        if mot:
            w0, w1 = max(za, mot[0][0] - pre), min(zb, mot[-1][1] + post)
        else:
            w0, w1 = za, za
        # pad with static until the window can carry its line at normal speed
        if w1 - w0 < need:
            w1 = min(zb, w0 + need)
        if w1 - w0 < need:
            w0 = max(za, w1 - need)
        segs.append({"n": i + 1, "src": [round(w0, 3), round(w1, 3)], "vo": vo,
                     "zone": [round(za, 3), round(zb, 3)]})
        dropped = (w0 - za) + (zb - w1)
        report.append((i + 1, za, zb, w0, w1, need, dropped, len(mot)))
    result = {"source": video, "gap": gap, "segments": segs}
    if X:
        result["keeps"] = [list(k) for k in subtract([(0.0, T)], X)]
        result["exclude"] = [list(x) for x in X]
    return result, report, F

if __name__ == "__main__":
    cfg = json.load(open(sys.argv[1]))
    import glob
    vos = sorted(glob.glob(os.path.join(os.path.expanduser(cfg["vo_dir"]), "*.mp3")))
    # gap: breath after each line. 0.9s is the settle FLOOR; Saad's own T12 re-cut had a
    # 1.7s median and 0.9 felt rushed on the Driver (23 Sep), so modules set it here.
    p, rep, F = plan(os.path.expanduser(cfg["video"]), cfg["bounds"], vos, gap=cfg.get("gap", 0.9),
                     exclude=[(e["start"], e["end"]) if isinstance(e, dict) else tuple(e)
                              for e in cfg.get("exclude", [])])
    if p.get("keeps"):
        tight = os.path.splitext(cfg["out"])[0] + "_tight.mp4"
        tighten(os.path.expanduser(cfg["video"]), p["keeps"], tight)
        p["source"] = os.path.abspath(tight)
        print(f"faults cut: {sum(b - a for a, b in p['exclude']):.1f}s -> {tight}")
    json.dump(p, open(cfg["out"], "w"), indent=1)
    kept = sum(r[4] - r[3] for r in rep)
    print(f"{'ln':>2} {'zone':>15} {'window':>15} {'voice+gap':>9} {'dropped':>8} motion")
    for n, za, zb, w0, w1, need, dropped, m in rep:
        print(f"{n:2d} {za:6.1f}-{zb:6.1f}  {w0:6.1f}-{w1:6.1f}  {need:8.1f}s {dropped:7.1f}s  {m}")
    print(f"\nsource {dur(os.path.expanduser(cfg['video'])):.1f}s -> windows keep {kept:.1f}s")
