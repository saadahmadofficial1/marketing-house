#!/usr/bin/env python3
"""Mine Saad's cut rhythm from the CapCut style brain into hard numbers.

  python3 Tools/sa_editdna.py           # writes Reference/EDIT_DNA_STATS.json
  python3 Tools/sa_editdna.py --test

Reads Reference/CAPCUT_STYLE_BRAIN.json (45 encoded projects) and answers,
per style_type: how long are his cuts, how regular is the rhythm, how much
speed-ramping does he use, how dense are the layers. sa_timeline can then
plan cuts that match HIS numbers instead of generic defaults.
"""
import json
import pathlib
import statistics
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
BRAIN = ROOT / "Reference" / "CAPCUT_STYLE_BRAIN.json"
OUT = ROOT / "Reference" / "EDIT_DNA_STATS.json"


def percentile(sorted_values, pct):
    if not sorted_values:
        return None
    k = (len(sorted_values) - 1) * pct / 100
    lo, hi = int(k), min(int(k) + 1, len(sorted_values) - 1)
    return round(sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * (k - lo), 3)


def project_cuts(project):
    """Video-track picture cuts only — the rhythm Saad actually feels."""
    return [s["timeline_duration"] for s in project.get("segments", [])
            if s.get("track_type") == "video" and s.get("role") == "picture"
            and s.get("timeline_duration", 0) > 0.05]


def mine(brain):
    styles = {}
    for project in brain.get("projects", []):
        style = project.get("style_type") or "unknown"
        cuts = project_cuts(project)
        if not cuts:
            continue
        entry = styles.setdefault(style, {"projects": 0, "cuts": [], "speeds": [], "layers": []})
        entry["projects"] += 1
        entry["cuts"].extend(cuts)
        entry["speeds"].extend(s.get("speed", 1.0) for s in project.get("segments", [])
                               if s.get("track_type") == "video")
        video_tracks = {s.get("track_index") for s in project.get("segments", [])
                        if s.get("track_type") == "video"}
        entry["layers"].append(len(video_tracks))
    report = {}
    for style, entry in sorted(styles.items()):
        cuts = sorted(entry["cuts"])
        speeds = entry["speeds"]
        ramped = [s for s in speeds if abs(s - 1.0) > 0.01]
        report[style] = {
            "projects": entry["projects"],
            "total_cuts": len(cuts),
            "cut_seconds": {
                "p25": percentile(cuts, 25), "median": percentile(cuts, 50),
                "p75": percentile(cuts, 75), "p90": percentile(cuts, 90),
            },
            # low = metronomic rhythm, high = loose storytelling pacing
            "rhythm_spread": round(statistics.pstdev(cuts) / statistics.mean(cuts), 3) if len(cuts) > 1 else None,
            "speed_ramp_share": round(len(ramped) / len(speeds), 3) if speeds else 0,
            "common_speeds": sorted({round(s, 2) for s in ramped})[:6],
            "avg_video_layers": round(statistics.mean(entry["layers"]), 1),
        }
    return report


def main():
    brain = json.loads(BRAIN.read_text(encoding="utf-8"))
    report = mine(brain)
    OUT.write_text(json.dumps({
        "generated_from": str(BRAIN.relative_to(ROOT)),
        "project_count": brain.get("project_count"),
        "principle": "Plan cuts to match these measured numbers, not generic defaults.",
        "styles": report,
    }, indent=1) + "\n", encoding="utf-8")
    print("EDIT DNA -> %s" % OUT.relative_to(ROOT))
    for style, stats in report.items():
        print("  %-28s %3d cuts | median %.2fs | rhythm %.2f | ramps %d%%" % (
            style, stats["total_cuts"], stats["cut_seconds"]["median"] or 0,
            stats["rhythm_spread"] or 0, stats["speed_ramp_share"] * 100))


def self_test():
    fake = {"projects": [{"style_type": "x", "segments": [
        {"track_type": "video", "role": "picture", "timeline_duration": 1.0, "speed": 1.0, "track_index": 0},
        {"track_type": "video", "role": "picture", "timeline_duration": 2.0, "speed": 0.7, "track_index": 0},
        {"track_type": "text", "role": "title", "timeline_duration": 9.0, "track_index": 1},
    ]}]}
    r = mine(fake)
    assert r["x"]["total_cuts"] == 2 and r["x"]["cut_seconds"]["median"] == 1.5
    assert r["x"]["speed_ramp_share"] == 0.5 and r["x"]["common_speeds"] == [0.7]
    print("sa_editdna self-checks: ok")


if __name__ == "__main__":
    self_test() if "--test" in sys.argv else main()
