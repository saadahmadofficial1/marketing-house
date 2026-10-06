#!/usr/bin/env python3
"""Fit an ordered shot list into the music phrases -> plan JSON (the sa_event_render.py plan schema).

  python3 sa_event_fit.py ORDER.json VPOOL.json MUSIC_MAP.json OUT_PLAN.json
ORDER.json = {"version", "phrases":[[pool_id, ...], ...], "hero": {pool_id, src_in, dur, speed},
              "overrides": {pool_id: {zoom, anchor, trans, trans_dur, speed_floor, blurin}}}
Each phrase is filled exactly (phrase starts from music_map). Durations start at window/0.79, then
stretch (down to 0.69x, 0.5x for flagged 100fps heroes) or shrink to land on the phrase boundary.
"""
import json, sys


def fit_phrase(items, T):
    """items: [(window, floor_speed)] -> durations summing to T (each <= window/floor, >= 0.45)."""
    durs = [min(w / 0.79, 1.3) for w, _ in items]
    caps = [min(w / f, 1.6) for w, f in items]          # no body shot over 1.6s (spec max 2.1, p75 1.3)
    for _ in range(60):
        gap = T - sum(durs)
        if abs(gap) < 1e-4:
            break
        if gap > 0:
            room = [c - d for c, d in zip(caps, durs)]
            tot = sum(r for r in room if r > 1e-6)
            if tot <= 1e-6:
                raise ValueError("phrase too long for its shots: short by %.2fs" % gap)
            durs = [d + gap * r / tot if r > 1e-6 else d for d, r in zip(durs, room)]
            durs = [min(d, c) for d, c in zip(durs, caps)]
        else:
            room = [d - 0.45 for d in durs]
            tot = sum(r for r in room if r > 0)
            durs = [d + gap * r / tot if r > 0 else d for d, r in zip(durs, room)]
    return durs


def build(order, pool, music):
    pool = {m["id"]: m for m in pool}
    starts = music["phrase_starts_film"]
    shots, n = [], 0
    for pi, ids in enumerate(order["phrases"]):
        T = starts[pi + 1] - starts[pi]
        ov = order.get("overrides", {})
        items = []
        for pid in ids:
            m = pool[pid]; w = m["out"] - m["in"]
            floor = ov.get(pid, {}).get("speed_floor", 0.69 if m.get("clip", "").startswith("C") else 1.0)
            items.append((w, floor))
        durs = fit_phrase(items, T)
        for pid, d in zip(ids, durs):
            m = pool[pid]; w = m["out"] - m["in"]; o = ov.get(pid, {})
            sp = 1.0 if not m["clip"].startswith("C") else min(0.79 if w / 0.79 >= d else w / d, 1.0)
            if m["clip"].startswith("C") and str(m.get("speed_hint")) == "1" and w / 1.0 >= d:
                sp = 1.0
            used = d * sp
            src_in = round(m["in"] + max(0.0, (w - used) / 2), 3)
            n += 1
            z = o.get("zoom", m.get("zoom_hint") or 1.0)
            shots.append(dict(id="S%02d" % n, pool_id=pid, clip=m["clip"], src_in=src_in, dur=round(d, 3), speed=round(sp, 3),
                              zoom=[z, z], anchor=o.get("anchor", m.get("anchor_hint") or [0.5, 0.5]), led_warm=bool(m.get("led_warm")),
                              trans=o.get("trans", "cut"), trans_dur=o.get("trans_dur", 0.5), blurin=o.get("blurin", False),
                              note=(m.get("what") or "")[:70], **({"file": m["file"]} if m.get("file") else {})))
    # absorb rounding so the hero starts exactly on the hit
    drift = round(music["final_hit_film"] - sum(s["dur"] for s in shots), 3)
    shots[-1]["dur"] = round(shots[-1]["dur"] + drift, 3)
    h = order["hero"]; m = pool[h["pool_id"]]; o = order.get("overrides", {}).get(h["pool_id"], {})
    z = o.get("zoom", m.get("zoom_hint") or 1.0)
    shots.append(dict(id="HERO", pool_id=h["pool_id"], clip=m["clip"], src_in=h["src_in"], dur=h["dur"], speed=h["speed"], zoom=[z, z],
                      anchor=o.get("anchor", m.get("anchor_hint") or [0.5, 0.5]), trans="cut", note=(m.get("what") or "")[:70]))
    return {"version": order["version"], "music": {"file": music["file"], "segments": music["segments"]}, "shots": shots,
            "end": {"dur": 6.4, "xfade": 0.4}}


def test():
    d = fit_phrase([(0.8, 0.69), (0.6, 0.69), (1.0, 0.69)], 3.0)
    assert abs(sum(d) - 3.0) < 1e-3 and all(x <= w / 0.69 + 1e-6 for x, (w, _) in zip(d, [(0.8, 0), (0.6, 0), (1.0, 0)]))
    d = fit_phrase([(1.0, 0.69), (1.0, 0.69)], 1.5)
    assert abs(sum(d) - 1.5) < 1e-3
    print("ok")


if __name__ == "__main__":
    if sys.argv[1] == "--test":
        test(); sys.exit()
    order, pool, music = (json.load(open(p)) for p in sys.argv[1:4])
    json.dump(build(order, pool, music), open(sys.argv[4], "w"), indent=1)
    print("plan ->", sys.argv[4])
