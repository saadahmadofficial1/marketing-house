#!/usr/bin/env python3
"""sa_tailcheck — does the picture outlive the narration? (the silent-tail lesson, 9 Aug)

One module shipped with 6 seconds of real UI steps playing after the last voiced line.
Nothing caught it: sa_coverage audits the
script against the screen, and the script was its whole universe — footage past the last
script segment was invisible to every check. Saad found it himself.

This is the missing check, both places the fault can live:

  CapCut projects   last caption end + last audio end vs content end, per timeline.
  Build folders     T*_PACED.mp4 duration vs last SRT cue end (where the silent tail was born).

A tail is allowed TAIL_HOLD (2.5s) of settle; beyond ALLOW (3.0s) it is missing content,
not padding. Read-only — never writes a project.

    Tools/venv/bin/python3 Tools/sa_tailcheck.py           # audit everything
    Tools/venv/bin/python3 Tools/sa_tailcheck.py --test
"""
import glob
import json
import os
import pathlib
import re
import subprocess
import sys

US = 1_000_000
ALLOW = 3.0                                 # TAIL_HOLD 2.5s + margin (builds)
ALLOW_PROJECT = 4.5                         # series outro holds measure 3.3-4.3s, all
                                            # proven static by the build motion check
CAPCUT = pathlib.Path("~/Movies/CapCut/User Data/Projects/com.lveditor.draft").expanduser()
SERIES = pathlib.Path(os.environ.get("TRAINING_ROOT", "~/Downloads/training-series")).expanduser()
SERIES_PREFIX = os.environ.get("SERIES_PREFIX", "Training ")   # CapCut project names in the series
BUILD = SERIES / "2 BUILD"


def timeline_tail(draft):
    """Pure: draft_info dict -> {caption_end, audio_end, content_end} in seconds.
    Sign-off card tracks count as captions: one module carries its outro on a separate
    'Sign-off' text track, and only counting 'Captions' false-flagged it."""
    cap = aud = end = 0.0
    for t in draft.get("tracks", []):
        nm = (t.get("name") or "").strip().lower()
        is_cap = nm == "captions" or nm.startswith("sign-off")
        for s in t.get("segments", []):
            tr = s.get("target_timerange") or {}
            e = (tr.get("start", 0) + tr.get("duration", 0)) / US
            end = max(end, e)
            if is_cap:
                cap = max(cap, e)
            if t.get("type") == "audio":
                aud = max(aud, e)
    return {"caption_end": cap, "audio_end": aud, "content_end": end}


def verdict(tail, allow=ALLOW):
    """Pure: tail dict -> (silent_tail_seconds, reason) — worst uncovered stretch.

    Captions only: the audio segment is padded to the video (apad) so its end says
    nothing about where SPEECH ends — trusting it passed a 24s silent tail."""
    voiced = tail["caption_end"]
    gap = tail["content_end"] - voiced
    if voiced == 0:                          # no captions = not built yet
        return 0.0, "no captions in project (not built — not a tail fault)"
    if gap > allow:
        return gap, (f"picture runs {gap:.1f}s past the captions "
                     f"(captioned to {voiced:.1f}s, content to {tail['content_end']:.1f}s)")
    return gap, "ok"


def thankyou_start(path):
    """-> start time of the 'Thank you for watching' cue, or None."""
    txt = pathlib.Path(path).read_text()
    m = re.search(r"(\d+):(\d+):(\d+)[,.](\d+) --> [^\n]*\n[^\n]*Thank you for watching",
                  txt, re.I)
    if not m:
        return None
    h, mi, s_, ms = (int(x) for x in m.groups())
    return h * 3600 + mi * 60 + s_ + ms / 1000


def srt_end(path):
    """-> (last cue end seconds, last cue text)."""
    txt = pathlib.Path(path).read_text()
    last, last_text = 0.0, ""
    for m in re.finditer(r"--> (\d+):(\d+):(\d+)[,.](\d+)\s*\n(.*)", txt):
        h, mi, s, ms = (int(x) for x in m.groups()[:4])
        e = h * 3600 + mi * 60 + s + ms / 1000
        if e > last:
            last, last_text = e, m.group(5).strip()
    return last, last_text


def tail_motion(mp4, start, end):
    """Does the picture CHANGE between narration end and content end?
    -> 'static hold' (outro freeze — fine) or 'MOVING content' (missing narration).
    Samples the tail at 2fps and takes the max successive-frame difference."""
    out = subprocess.run(
        ["ffmpeg", "-v", "info", "-ss", f"{start:.2f}", "-to", f"{end:.2f}", "-i", str(mp4),
         "-vf", "fps=2,scale=160:-1,select='gt(scene\\,0.003)',metadata=print",
         "-f", "null", "-"], capture_output=True, text=True)
    changes = out.stderr.count("lavfi.scene_score")
    return "MOVING content" if changes else "static hold"


def media_dur(path):
    out = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                          "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    try:
        return float(out.stdout.strip())
    except ValueError:
        return 0.0


def audit_projects():
    bad = []
    for p in sorted(CAPCUT.glob("*")):
        if not p.name.startswith(SERIES_PREFIX):
            continue
        for f in sorted(glob.glob(str(p / "Timelines/*/draft_info.json"))) or \
                 [str(p / "draft_info.json")]:
            if not os.path.exists(f):
                continue
            try:
                tail = timeline_tail(json.load(open(f)))
            except (json.JSONDecodeError, OSError):
                continue
            if tail["content_end"] < 5:      # empty/scratch timeline
                continue
            gap, why = verdict(tail, ALLOW_PROJECT)
            mark = "SILENT TAIL" if why != "ok" and "not built" not in why else "  "
            print(f"  {mark:11s} {p.name[:44]:44s} {why}")
            if mark.strip():
                bad.append((p.name, why))
    return bad


def audit_builds():
    bad = []
    for mp4 in sorted(BUILD.glob("*/T*_PACED.mp4")):
        srt = next(iter(sorted(mp4.parent.glob("*.srt"))), None)
        if not srt:
            continue
        vd = media_dur(mp4)
        se, last_cue = srt_end(srt)
        ty = thankyou_start(srt)
        if ty and tail_motion(mp4, ty, vd) == "MOVING content":
            why = (f"process steps still playing during the sign-off "
                   f"(thank-you starts {ty:.1f}s, picture changes up to {vd:.1f}s) "
                   f"— narrate them or move the sign-off (the silent-tail fault)")
            print(f"  OUTRO CLASH {mp4.parent.name[:40]:40s} {why}")
            bad.append((mp4.parent.name, why))
            continue
        gap = vd - se
        if gap > ALLOW:
            motion = tail_motion(mp4, se, vd)
            why = (f"{gap:.1f}s tail after captions ({se:.1f}->{vd:.1f}s): {motion}; "
                   f"last cue {last_cue!r}")
            mark = "SILENT TAIL" if motion == "MOVING content" else "hold ok    "
            print(f"  {mark} {mp4.parent.name[:40]:40s} {why}")
            if motion == "MOVING content":
                bad.append((mp4.parent.name, why))
        else:
            print(f"  {'':11s} {mp4.parent.name[:40]:40s} ok ({gap:+.1f}s)")
    return bad


def _test():
    d = {"tracks": [
        {"name": "video", "type": "video", "segments": [
            {"target_timerange": {"start": 0, "duration": int(27.3 * US)}}]},
        {"name": "Captions", "type": "text", "segments": [
            {"target_timerange": {"start": int(22.0 * US), "duration": int(1.8 * US)}}]},
        {"name": "audio", "type": "audio", "segments": [
            {"target_timerange": {"start": 0, "duration": int(19.3 * US)}}]}]}
    t = timeline_tail(d)
    assert abs(t["caption_end"] - 23.8) < 0.01 and abs(t["audio_end"] - 19.3) < 0.01
    gap, why = verdict(t)                    # the real silent-tail numbers: must flag
    assert gap > ALLOW and "past the captions" in why
    d["tracks"][1]["segments"].append(
        {"target_timerange": {"start": int(25.3 * US), "duration": int(2.0 * US)}})
    assert verdict(timeline_tail(d))[1] == "ok", "caption near the end must pass"
    assert "not built" in verdict({"caption_end": 0, "audio_end": 0, "content_end": 30})[1]
    import tempfile
    s = pathlib.Path(tempfile.mkdtemp()) / "x.srt"
    s.write_text("1\n00:00:20,000 --> 00:00:23,800\nYour tagline here.\n")
    e, txt = srt_end(s)
    assert abs(e - 23.8) < 0.01 and txt.startswith("Your tagline")
    print("sa_tailcheck self-check: ok (flags the real silent-tail numbers, passes a covered tail)")


if __name__ == "__main__":
    if "--test" in sys.argv:
        _test()
        sys.exit()
    print("CapCut projects (live truth):")
    b1 = audit_projects()
    print("\nBuild folders (PACED vs SRT):")
    b2 = audit_builds()
    n = len(b1) + len(b2)
    print(f"\n{n} silent tail(s) found" if n else "\nevery video's picture ends with its narration")
