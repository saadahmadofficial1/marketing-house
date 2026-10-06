#!/usr/bin/env python3
"""Gate a cut plan against SPEC_CUT.md before anything is rendered.

  python3 sa_event_cutcheck.py PLAN.json VERIFIED_POOL.json      -> prints PASS/FAIL per rule, exit 1 on any FAIL
  python3 sa_event_cutcheck.py --test
"""
import json, statistics, sys

HIT = 37.03


def pct(xs, p):
    xs = sorted(xs); k = (len(xs) - 1) * p; f = int(k)
    return xs[f] + (xs[min(f + 1, len(xs) - 1)] - xs[f]) * (k - f)


def check(plan, pool):
    pool = {m["id"]: m for m in pool}
    shots = plan["shots"]; res = []
    ok = lambda name, cond, info="": res.append((name, bool(cond), info))
    t, starts = 0.0, []
    for s in shots:
        starts.append(round(t, 3)); t += s["dur"]
    body = shots[:-1]
    durs = [s["dur"] for s in body]
    ok("final shot starts on the hit (37.03 +-0.03)", abs(starts[-1] - HIT) <= 0.03, "starts %.3f" % starts[-1])
    ok("final shot 2.0-3.0s", 2.0 <= shots[-1]["dur"] <= 3.0, "%.2f" % shots[-1]["dur"])
    med = statistics.median(durs)
    ok("body median 0.95-1.15s", 0.95 <= med <= 1.15, "%.3f" % med)
    ok("p25 >= 0.70", pct(durs, .25) >= 0.70, "%.3f" % pct(durs, .25))
    ok("p75 <= 1.30", pct(durs, .75) <= 1.30, "%.3f" % pct(durs, .75))
    ok("no body shot > 2.1s", max(durs) <= 2.1, "max %.2f" % max(durs))
    ok("33-38 body shots", 33 <= len(body) <= 38, str(len(body)))
    first10 = sum(1 for st in starts if st < 10)
    ok(">= 8 shots in first 10s", first10 >= 8, str(first10))
    ok("shot 1 <= 1.6s", shots[0]["dur"] <= 1.6, "%.2f" % shots[0]["dur"])
    bad_src, bad_speed = [], []
    for s in shots:
        m = pool.get(s.get("pool_id"))
        used = s["dur"] * float(s.get("speed", 1.0))
        if not m or m["clip"] != s["clip"] or s["src_in"] < m["in"] - 0.02 or s["src_in"] + used > m["out"] + 0.02:
            bad_src.append(s["id"])
        sp = float(s.get("speed", 1.0))
        if sp < 0.39 or sp > 1.1 or (sp < 0.69 and int((m or {}).get("fps", 50)) < 100):
            bad_speed.append(s["id"])
    ok("every shot inside its verified window", not bad_src, ",".join(bad_src))
    ok("speeds legal (<0.69 only on 100fps)", not bad_speed, ",".join(bad_speed))
    slow = sum(1 for s in shots if float(s.get("speed", 1)) < 0.69)
    ok("<= 3 deep slow-mo shots", slow <= 3, str(slow))
    trans = [s for s in shots if s.get("trans", "cut") != "cut"]
    ok("<= 4 transitions", len(trans) <= 4, str(len(trans)))
    keys = [(s["clip"], round(s["src_in"])) for s in shots]
    dup = len(keys) - len(set(keys))
    ok("no duplicate source moments", dup == 0, str(dup))
    adj = [shots[i]["id"] for i in range(1, len(shots)) if shots[i]["clip"] == shots[i - 1]["clip"]]
    ok("no same clip back to back", not adj, ",".join(adj))
    zooms = [s for s in shots if s.get("zoom", [1, 1])[0] != s.get("zoom", [1, 1])[-1]]
    ok("no keyframed push-ins", not zooms, ",".join(s["id"] for s in zooms))
    return res


def main():
    plan = json.load(open(sys.argv[1])); pool = json.load(open(sys.argv[2]))
    res = check(plan, pool)
    for name, good, info in res:
        print("%s  %-45s %s" % ("PASS" if good else "FAIL", name, info))
    sys.exit(0 if all(g for _, g, _ in res) else 1)


def test():
    pool = [{"id": "P1", "clip": "C1", "in": 0, "out": 100, "fps": 100}, {"id": "P2", "clip": "C2", "in": 0, "out": 100, "fps": 50}]
    shots = []
    for i in range(36):
        shots.append({"id": "S%d" % i, "pool_id": "P%d" % (1 + i % 2), "clip": "C%d" % (1 + i % 2), "src_in": i, "dur": HIT / 36, "speed": 0.79})
    shots.append({"id": "F", "pool_id": "P1", "clip": "C1", "src_in": 90, "dur": 2.5, "speed": 0.79})
    res = check({"shots": shots}, pool)
    assert all(g for _, g, _ in res), [r for r in res if not r[1]]
    shots[3]["dur"] += 0.5
    assert not dict((n, g) for n, g, _ in check({"shots": shots}, pool))["final shot starts on the hit (37.03 +-0.03)"]
    print("ok")


if __name__ == "__main__":
    test() if sys.argv[1] == "--test" else main()
