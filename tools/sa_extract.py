#!/usr/bin/env python3
"""Local footage extraction and shot-quality scoring for rough cuts.

Produces exact source windows for sa_timeline.py and the CapCut builder. Uses
multi-frame computer vision instead of judging one still. No cloud required.

  Tools/venv/bin/python Tools/sa_extract.py FOOTAGE --limit 8
  Tools/venv/bin/python Tools/sa_extract.py FOOTAGE --cut-len 1.8 --candidates 6
  Tools/venv/bin/python Tools/sa_extract.py --test
"""
import argparse
import json
import math
import os
import pathlib
import shutil
import sys

import cv2
import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from sa_assemble import VIDEO_EXT, probe


def clamp(value, low=0.0, high=100.0):
    return max(low, min(high, float(value)))


def sharpness_score(gray):
    variance = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    return clamp(22.0 * math.log10(variance + 1.0)), variance


def exposure_score(gray):
    shadow = float(np.mean(gray <= 8))
    highlight = float(np.mean(gray >= 247))
    median = float(np.median(gray))
    midpoint_penalty = abs(median - 127.5) / 127.5 * 28.0
    clipping_penalty = (shadow + highlight) * 180.0
    return clamp(100.0 - midpoint_penalty - clipping_penalty), {
        "median_luma": round(median, 1),
        "shadow_clip_pct": round(shadow * 100, 2),
        "highlight_clip_pct": round(highlight * 100, 2),
    }


def frame_signature(frame):
    gray = cv2.cvtColor(cv2.resize(frame, (32, 18)), cv2.COLOR_BGR2GRAY)
    return gray.astype(np.float32).flatten()


def signature_similarity(left, right):
    a, b = left - np.mean(left), right - np.mean(right)
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    return 0.0 if denom == 0 else clamp(float(np.dot(a, b) / denom) * 100.0)


def motion_metrics(grays):
    translations, flow_amounts = [], []
    for before, after in zip(grays, grays[1:]):
        points = cv2.goodFeaturesToTrack(before, maxCorners=120, qualityLevel=0.02,
                                         minDistance=8, blockSize=5)
        if points is None or len(points) < 8:
            continue
        moved, status, _ = cv2.calcOpticalFlowPyrLK(before, after, points, None)
        if moved is None:
            continue
        good_before = points[status.flatten() == 1].reshape(-1, 2)
        good_after = moved[status.flatten() == 1].reshape(-1, 2)
        if len(good_before) < 8:
            continue
        delta = good_after - good_before
        translation = np.median(delta, axis=0)
        translations.append(translation)
        flow_amounts.append(float(np.median(np.linalg.norm(delta, axis=1))))
    if not translations:
        return {"motion_px": 0.0, "jitter_px": 0.0, "smoothness": 70.0}
    translations = np.asarray(translations)
    if len(translations) > 1:
        acceleration = np.diff(translations, axis=0)
        jitter = float(np.median(np.linalg.norm(acceleration, axis=1)))
    else:
        jitter = 0.0
    motion = float(np.median(flow_amounts))
    smoothness = clamp(100.0 - jitter * 12.0)
    return {"motion_px": round(motion, 2), "jitter_px": round(jitter, 2),
            "smoothness": round(smoothness, 1)}


def quality_score(sharpness, exposure, smoothness):
    return round(clamp(sharpness * 0.42 + exposure * 0.28 + smoothness * 0.30), 1)


def quality_flags(sharpness, exposure_detail, motion):
    flags = []
    if sharpness < 45:
        flags.append("soft_or_blurry")
    if exposure_detail["shadow_clip_pct"] > 18:
        flags.append("crushed_shadows")
    if exposure_detail["highlight_clip_pct"] > 12:
        flags.append("clipped_highlights")
    if motion["jitter_px"] > 3.2:
        flags.append("camera_jitter")
    if motion["motion_px"] > 18:
        flags.append("very_fast_motion")
    return flags


def suggested_speed(metrics):
    if metrics["jitter_px"] > 3.2 or metrics["motion_px"] > 12:
        return 0.7, "slow energetic/unstable movement for readability"
    if metrics["motion_px"] > 5:
        return 0.8, "slight slow-down preserves controlled movement"
    return 1.0, "motion already readable at normal speed"


def sample_window(video, start, duration, samples=7):
    capture = cv2.VideoCapture(str(video))
    if not capture.isOpened():
        raise RuntimeError("cannot decode video")
    times = np.linspace(start + duration * 0.08, start + duration * 0.92, samples)
    frames = []
    for at in times:
        capture.set(cv2.CAP_PROP_POS_MSEC, float(at) * 1000.0)
        ok, frame = capture.read()
        if ok and frame is not None:
            width = frame.shape[1]
            if width > 640:
                scale = 640.0 / width
                frame = cv2.resize(frame, None, fx=scale, fy=scale,
                                   interpolation=cv2.INTER_AREA)
            frames.append(frame)
    capture.release()
    if len(frames) < 3:
        raise RuntimeError("too few decodable frames")
    grays = [cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) for frame in frames]
    sharp_rows = [sharpness_score(gray) for gray in grays]
    exposure_rows = [exposure_score(gray) for gray in grays]
    sharpness = float(np.percentile([row[0] for row in sharp_rows], 35))
    raw_sharpness = float(np.percentile([row[1] for row in sharp_rows], 35))
    exposure = float(np.mean([row[0] for row in exposure_rows]))
    exposure_detail = {
        key: round(float(np.mean([row[1][key] for row in exposure_rows])), 2)
        for key in exposure_rows[0][1]
    }
    motion = motion_metrics(grays)
    score = quality_score(sharpness, exposure, motion["smoothness"])
    return {
        "quality_score": score,
        "sharpness_score": round(sharpness, 1),
        "laplacian_variance": round(raw_sharpness, 1),
        "exposure_score": round(exposure, 1),
        **exposure_detail,
        **motion,
        "flags": quality_flags(sharpness, exposure_detail, motion),
        "signature": frame_signature(frames[len(frames) // 2]),
        "preview_frame": frames[len(frames) // 2],
    }


def candidate_starts(duration, cut_len, count):
    usable = max(duration - cut_len, 0.0)
    if usable == 0 or count <= 1:
        return [0.0]
    edge = min(0.35, usable * 0.08)
    return [round(float(x), 3) for x in np.linspace(edge, max(usable - edge, edge), count)]


def rank_candidates(candidates):
    ranked = sorted(range(len(candidates)), key=lambda i: candidates[i]["quality_score"], reverse=True)
    if not ranked:
        return []
    selected = [ranked[0]]
    for index in ranked[1:]:
        similarity = max(signature_similarity(candidates[index]["signature"],
                                              candidates[chosen]["signature"])
                         for chosen in selected)
        candidates[index]["duplicate_similarity"] = round(similarity, 1)
        if similarity < 94:
            selected.append(index)
    return selected


def clean_candidate(candidate):
    return {key: value for key, value in candidate.items()
            if key not in ("signature", "preview_frame")}


def analyze_folder(folder, cut_len=1.8, candidates=5, limit=None, out=None):
    folder = pathlib.Path(folder).expanduser().resolve()
    files = sorted(path for path in folder.iterdir() if path.suffix in VIDEO_EXT)
    if limit:
        files = files[:limit]
    if not files:
        raise SystemExit("no video footage found")
    out = pathlib.Path(out).expanduser().resolve() if out else folder / "_CUTSHEET"
    previews = out / "previews"
    previews.mkdir(parents=True, exist_ok=True)
    rows = []
    for file_index, video in enumerate(files, 1):
        duration, width, height = probe(str(video))
        print("[%s/%s] %s %.1fs" % (file_index, len(files), video.name, duration))
        if duration <= 0:
            rows.append({"file": video.name, "error": "unreadable duration"})
            continue
        window = min(cut_len, duration)
        tested = []
        for index, start in enumerate(candidate_starts(duration, window, candidates)):
            try:
                result = sample_window(video, start, window)
                result.update({"start": start, "end": round(start + window, 3)})
                tested.append(result)
            except Exception as error:
                tested.append({"start": start, "end": round(start + window, 3),
                               "quality_score": 0.0, "flags": ["decode_failed"],
                               "error": str(error), "signature": np.zeros(576),
                               "preview_frame": None})
        diverse = rank_candidates(tested)
        best_index = diverse[0] if diverse else max(range(len(tested)), key=lambda i: tested[i]["quality_score"])
        best = tested[best_index]
        preview_name = "%03d_%s.jpg" % (file_index, video.stem)
        if best.get("preview_frame") is not None:
            cv2.imwrite(str(previews / preview_name), best["preview_frame"])
        speed, speed_reason = suggested_speed(best)
        confidence = "high" if best["quality_score"] >= 72 and not best["flags"] else (
            "medium" if best["quality_score"] >= 52 else "low")
        rows.append({
            "file": video.name, "path": str(video), "duration": round(duration, 3),
            "source_dimensions": {"width": width, "height": height},
            "suggested_in": best["start"], "suggested_out": best["end"],
            "suggested_speed": speed, "speed_why": speed_reason,
            "quality_score": best["quality_score"], "confidence": confidence,
            "reviewed": False,
            "flags": best["flags"], "preview": str(previews / preview_name),
            "alternate_windows": [clean_candidate(tested[i]) for i in diverse[1:3]],
            "all_candidates": [clean_candidate(row) for row in tested],
        })
    payload = {"schema_version": "2.0", "source_folder": str(folder),
               "analysis": "local-multiframe", "clips": rows}
    (out / "cutsheet.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    md = ["# Footage extraction", "", "Source: `%s`" % folder, "",
          "| Clip | Best source | Quality | Confidence | Speed | Flags |",
          "|---|---:|---:|---|---:|---|"]
    for row in rows:
        if "error" in row:
            md.append("| %s | - | - | low | - | %s |" % (row["file"], row["error"]))
        else:
            md.append("| %s | %.2f-%.2fs | %.1f/100 | %s | %.2fx | %s |" % (
                row["file"], row["suggested_in"], row["suggested_out"],
                row["quality_score"], row["confidence"], row["suggested_speed"],
                ", ".join(row["flags"]) or "clean"))
    (out / "CUTSHEET.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("-> %s" % out)
    return payload


def self_test():
    sharp = np.zeros((120, 160), np.uint8)
    cv2.rectangle(sharp, (20, 20), (140, 100), 255, 2)
    blurred = cv2.GaussianBlur(sharp, (31, 31), 0)
    assert sharpness_score(sharp)[0] > sharpness_score(blurred)[0]
    normal = np.full((120, 160), 128, np.uint8)
    clipped = np.zeros((120, 160), np.uint8)
    assert exposure_score(normal)[0] > exposure_score(clipped)[0]
    starts = candidate_starts(10, 2, 5)
    assert len(starts) == 5 and starts[0] >= 0 and starts[-1] <= 8
    candidates = [{"quality_score": 90, "signature": np.arange(12, dtype=np.float32)},
                  {"quality_score": 80, "signature": np.arange(12, dtype=np.float32)},
                  {"quality_score": 70, "signature": np.arange(12, dtype=np.float32)[::-1]}]
    assert rank_candidates(candidates) == [0, 2]
    assert suggested_speed({"jitter_px": 4, "motion_px": 2})[0] == 0.7
    print("sa_extract self-checks: ok")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("folder", nargs="?")
    parser.add_argument("--cut-len", type=float, default=1.8)
    parser.add_argument("--candidates", type=int, default=5)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--out")
    parser.add_argument("--test", action="store_true")
    args = parser.parse_args()
    if args.test:
        self_test()
    elif not args.folder:
        parser.error("folder is required")
    else:
        analyze_folder(args.folder, args.cut_len, args.candidates, args.limit, args.out)


if __name__ == "__main__":
    main()
