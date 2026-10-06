#!/usr/bin/env python3
"""sa_exportcheck — is this CapCut project safe to export?

The real risk is not the missing call-outs. It is sitting down the night before a deadline to
export fifteen videos and finding a fault in the twelfth. Every fault below has actually
happened on this series, so each one is checked rather than assumed.

    python3 sa_exportcheck.py
    python3 sa_exportcheck.py "Training 03"
    python3 sa_exportcheck.py --test

Read-only. Never opens or writes a project.
"""
import argparse
import glob
import json
import os
import pathlib
import re
import sys

US = 1_000_000
SERIES_PREFIX = os.environ.get("SERIES_PREFIX", "Training ")    # CapCut project names that belong to the series
sys.path.insert(0, str(pathlib.Path(__file__).parent))

CAPTION_SPEC = {"size": 5.0, "scale": 0.75, "y": -892}
# The rule is one line per caption, never wrapped — NOT a character count. Measured 9 Aug
# with the real Poppins Regular: a 55-character line fills 52-74% of a 1920 canvas, so it
# does not wrap. The 46 in sa_captions is a readability guide for where to BREAK a new
# caption, not a defect threshold for one that already exists. Flagging 47-55 char lines
# on one module nearly had a finished project rewritten for nothing.
WRAP_RISK_CHARS = 72



def _is_title_line(texts, seg):
    """His title card is two text elements at size 18. Everything else that is text is a
    caption or a label — which is what makes captions detectable without a track name."""
    m = texts.get(seg.get("material_id"))
    if not m:
        return False
    try:
        c = json.loads(m.get("content") or "{}")
    except (json.JSONDecodeError, TypeError):
        return False
    st = (c.get("styles") or [{}])[0]
    return abs(float(st.get("size") or 0) - 18.0) < 0.01


def checks(draft, name):
    """-> [(ok, severity, message)] for one timeline. Pure, so every rule is testable."""
    out = []
    tracks = draft.get("tracks", [])
    names = [(t.get("name") or "").strip() for t in tracks]
    texts = {m["id"]: m for m in draft.get("materials", {}).get("texts", [])}
    vids = {m["id"]: m for m in draft.get("materials", {}).get("videos", [])}

    def segs_of(track_name):
        return [s for t in tracks if (t.get("name") or "").strip() == track_name
                for s in t.get("segments", [])]

    def content_end():
        e = [(s["target_timerange"]["start"] + s["target_timerange"]["duration"]) / US
             for t in tracks for s in t.get("segments", []) if s.get("target_timerange")]
        return max(e) if e else 0.0

    # Captions by CONTENT, never by track name — the same lesson the title check already
    # learned. 12 Aug: two finished modules were both reported as shipping UNCAPTIONED. They
    # carry 15 and 79 cues; Saad had simply regrouped them onto tracks he calls "Title" and
    # "Sign-off". A blocker on two finished videos, caused entirely by the checker.
    # A caption is any text element that is not a size-18 title line.
    caps = [s for t in tracks for s in t.get("segments", [])
            if s.get("material_id") in texts and not _is_title_line(texts, s)]
    out.append((bool(caps), "blocker",
                f"{len(caps)} caption segment(s)" if caps else "NO CAPTIONS — the export "
                "would ship uncaptioned"))

    # Count the title by CONTENT, not by track name. Saad regroups tracks when he edits —
    # three modules all reported "no title card" purely because the two lines had been
    # moved off the track called "Title" (9 Aug). His title is two text elements at size 18.
    title = 0
    for t in tracks:
        for s in t.get("segments", []):
            m = texts.get(s.get("material_id"))
            if not m:
                continue
            try:
                c = json.loads(m.get("content") or "{}")
            except (json.JSONDecodeError, TypeError):
                continue
            st = (c.get("styles") or [{}])[0]
            if abs(float(st.get("size") or 0) - 18.0) < 0.01:
                title += 1
    out.append((title >= 2, "important",
                "title card present" if title >= 2 else
                f"title card has {title} line(s) at size 18, expected 2"))

    # caption spec: his numbers, and one line only
    bad_len = bad_spec = 0
    for s in caps:
        m = texts.get(s.get("material_id"))
        if not m:
            continue
        try:
            c = json.loads(m.get("content") or "{}")
        except (json.JSONDecodeError, TypeError):
            continue
        st0 = (c.get("styles") or [{}])[0]
        if abs(float(st0.get("size") or 0) - 18.0) < 0.01:
            continue        # a title line parked on the caption track, not a caption
        if len(c.get("text", "")) > WRAP_RISK_CHARS:
            bad_len += 1
        st = (c.get("styles") or [{}])[0]
        if abs(float(st.get("size") or 0) - CAPTION_SPEC["size"]) > 0.01:
            bad_spec += 1
        if len(st.get("shadows") or []) > 1:
            bad_spec += 1
    out.append((bad_len == 0, "important",
                "every caption is one line" if not bad_len
                else f"{bad_len} caption(s) long enough to wrap onto two lines"))
    out.append((bad_spec == 0, "important",
                "captions match the locked spec" if not bad_spec
                else f"{bad_spec} caption(s) off spec (size or stacked shadow)"))

    # The sign-off must not be said twice — counted by the WORDS, not by tracks called
    # "Sign-off". 12 Aug: one module has four such tracks, but they carry role labels ("Sign
    # in as the Service Advisor", "Sign out"); only one actually thanks the viewer.
    said = 0
    for t in tracks:
        for s in t.get("segments", []):
            m = texts.get(s.get("material_id"))
            if not m:
                continue
            try:
                txt = json.loads(m.get("content") or "{}").get("text", "")
            except (json.JSONDecodeError, TypeError):
                continue
            if "thank you for watching" in txt.lower():
                said += 1
    out.append((said <= 1, "blocker",
                "one sign-off" if said <= 1
                else f"the viewer is thanked {said} times"))

    # trailing black: the header claiming more than the content
    end, dur = content_end(), draft.get("duration", 0) / US
    out.append((dur - end <= 0.3, "blocker",
                "no trailing black" if dur - end <= 0.3
                else f"{dur - end:.1f}s of black on the end"))

    # every referenced file must exist
    missing = []

    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k in ("path", "file_Path") and isinstance(v, str) and v.startswith("/"):
                    if not os.path.exists(v):
                        missing.append(v)
                else:
                    walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(draft)
    out.append((not missing, "blocker",
                "all media present" if not missing else f"{len(missing)} missing file(s)"))

    # "SOURCE (reference)" is the hidden original recording sa_addsource parks on the
    # remaining projects — mine, never a call-out. Counting it read 14 where 13 was true.
    callouts = [n for n in names if n and n not in
                ("Captions", "Title", "Sign-off", "Sign-off VO", "video", "audio", "text",
                 "SOURCE (reference)")]

    # A fitted artefact goes stale the moment the thing it was fitted to changes. The
    # reference track was sized to the edit's end when it was added; Saad then shortened
    # one module's tail by 2.7s and the reference kept its old length, silently extending a
    # FINISHED video. Anything hidden that outlasts the real content is a blocker.
    ref = content = 0.0
    for t in tracks:
        for s in t.get("segments", []):
            tr = s.get("target_timerange")
            if not tr:
                continue
            e = (tr["start"] + tr["duration"]) / US
            if (t.get("name") or "").strip() == "SOURCE (reference)":
                ref = max(ref, e)
            else:
                content = max(content, e)
    if ref > content + 0.05:
        out.append((False, "blocker",
                    f"the hidden reference track runs to {ref:.1f}s but the video ends at "
                    f"{content:.1f}s — it would export {ref - content:.1f}s of dead tail. "
                    f"Re-fit or remove it (sa_addsource --remove)."))

    # Captions and voice-over outliving the PICTURE. 12 Aug, one module: Saad rippled 31s out of
    # the footage, the caption and sign-off blocks stayed where they were, and 21.3s — the
    # closing line and the whole sign-off — played over BLACK. Every other
    # check passed it, because nothing was measuring whether a frame was on screen.
    last_picture = 0.0
    for t in tracks:
        if (t.get("name") or "").strip() == "SOURCE (reference)":
            continue
        for s in t.get("segments", []):
            tr = s.get("target_timerange")
            mat = vids.get(s.get("material_id"))
            if not tr or not mat:
                continue
            # anything in materials.videos IS picture — CapCut files stills there too, and
            # matching on file extension made this miss the case it was written for
            last_picture = max(last_picture, (tr["start"] + tr["duration"]) / US)
    # Threshold calibrated against his own finished work, not guessed: one module leaves 4.8s
    # and another leaves 7.4s of sign-off past the last frame, because his outro card covers
    # it. Anything up to ~8s is his normal outro space. The blackout case's 22.6s was not.
    OUTRO_ALLOWANCE = 8.0
    if last_picture and content > last_picture + OUTRO_ALLOWANCE:
        out.append((False, "blocker",
                    f"{content - last_picture:.1f}s of captions or audio play with NO PICTURE "
                    f"— the last frame is at {last_picture:.1f}s but the timeline runs to "
                    f"{content:.1f}s. Extend an end hold or bring the tail forward."))

    out.append((True, "info", f"{len(callouts)} named call-out track(s), "
                              f"{max(content, end):.0f}s long"))
    return out


def project_paths(root):
    return sorted(glob.glob(str(root / "Timelines/*/draft_info.json")))


def main(only):
    import sa_capcut_relink as R
    names = [n for n, _p in R.projects(None)
             if n.startswith(SERIES_PREFIX)]
    if only:
        names = [n for n in names if only.lower() in n.lower()]
    ready = 0
    total = [0]
    for n in names:
        paths = project_paths(pathlib.Path(R.DRAFTS) / n)
        if not paths:
            print(f"\n{n}\n   ! no timeline found")
            continue
        # PER TIMELINE, not per project. one project holds two: Timeline 01 shipped,
        # Timeline 02 has never been exported.
        # Checking only paths[0] reported the whole project blocked while Timeline 02 was
        # already fixed, and would have hidden a fault in any second timeline (9 Aug).
        for tl in paths:
            res = checks(json.load(open(tl)), n)
            blockers = [m for ok, sev, m in res if not ok and sev == "blocker"]
            warns = [m for ok, sev, m in res if not ok and sev == "important"]
            mark = "READY" if not blockers and not warns else ("BLOCKED" if blockers else "check")
            ready += (mark == "READY")
            total[0] += 1
            label = n if len(paths) == 1 else f"{n}  [timeline {paths.index(tl) + 1}]"
            print(f"\n{mark:8s} {label}")
            for ok, sev, m in res:
                if sev == "info":
                    print(f"           · {m}")
                elif not ok:
                    print(f"           {'X' if sev == 'blocker' else '!'} {m}")
    print(f"\n{ready} of {total[0]} timeline(s) ready to export with nothing outstanding")
    return ready


def _test():
    def draft(caps=3, title=2, signoff=1, dur=10.0, end=10.0, cap_text="short line",
              size=5.0, shadows=1, path="/dev/null"):
        texts, tracks = [], []
        segs = []
        for i in range(caps):
            texts.append({"id": f"c{i}", "content": json.dumps(
                {"text": cap_text, "styles": [{"size": size,
                                               "shadows": [{}] * shadows}]})})
            segs.append({"material_id": f"c{i}",
                         "target_timerange": {"start": 0, "duration": int(end * US)}})
        tracks.append({"name": "Captions", "segments": segs})
        for k in range(title):
            texts.append({"id": f"ti{k}", "content": json.dumps(
                {"text": "How to", "styles": [{"size": 18.0, "shadows": [{}]}]})})
        tracks.append({"name": "Title", "segments": [
            {"material_id": f"ti{k}", "target_timerange": {"start": 0, "duration": 1}}
            for k in range(title)]})
        # the sign-off is TEXT the viewer reads, not a track name — that is what is counted
        for k in range(signoff):
            texts.append({"id": f"so{k}", "content": json.dumps(
                {"text": "Thank you for watching.", "styles": [{"size": 5.0,
                                                                "shadows": [{}]}]})})
            tracks.append({"name": "Sign-off", "segments": [
                {"material_id": f"so{k}", "target_timerange": {"start": 0, "duration": 1}}]})
        tracks.append({"name": "Click Save", "segments": [
            {"material_id": "v", "target_timerange": {"start": 0,
                                                      "duration": int(end * US)}}]})
        return {"tracks": tracks, "duration": int(dur * US),
                "materials": {"texts": texts, "videos": [{"id": "v", "path": path}]}}

    def fails(d):
        return [m for ok, sev, m in checks(d, "x") if not ok]

    assert not fails(draft()), fails(draft())
    # no captions means no readable text at all — the sign-off cue is itself a caption
    assert any("NO CAPTIONS" in m for m in fails(draft(caps=0, signoff=0)))
    assert any("thanked 2 times" in m for m in fails(draft(signoff=2)))
    # 12 Aug: captions found by CONTENT, so renaming the track cannot hide them, and
    # role-label tracks called "Sign-off" must not read as a second sign-off.
    renamed = draft()
    renamed["tracks"][0]["name"] = "Title"          # he regroups captions onto other tracks
    assert not any("NO CAPTIONS" in m for m in fails(renamed)), fails(renamed)
    roles = draft()
    roles["materials"]["texts"].append({"id": "rl", "content": json.dumps(
        {"text": "Sign in as the Service Advisor", "styles": [{"size": 5.0, "shadows": [{}]}]})})
    roles["tracks"].append({"name": "Sign-off", "segments": [
        {"material_id": "rl", "target_timerange": {"start": 0, "duration": 1}}]})
    assert not any("thanked" in m for m in fails(roles)), fails(roles)
    assert any("black" in m for m in fails(draft(dur=15.0, end=10.0)))
    assert any("missing file" in m for m in fails(draft(path="/nope/gone.mp4")))
    # 12 Aug: 21.3s of one module played over black and every check passed it
    blackout = draft(end=10.0, dur=10.0)
    blackout["tracks"][0]["segments"][0]["target_timerange"]["duration"] = int(30 * US)
    assert any("NO PICTURE" in m for m in fails(blackout)), fails(blackout)
    # his normal outro space must NOT trip it — 4.8s and 7.4s on two finished modules
    normal = draft(end=10.0, dur=10.0)
    normal["tracks"][0]["segments"][0]["target_timerange"]["duration"] = int(17 * US)
    assert not any("NO PICTURE" in m for m in fails(normal)), fails(normal)
    assert not fails(draft(cap_text="x" * 55)), "a 55-char line does not wrap — not a defect"
    assert any("wrap" in m for m in fails(draft(cap_text="x" * 90)))
    assert any("off spec" in m for m in fails(draft(shadows=3)))
    assert any("title card has" in m for m in fails(draft(title=1))), fails(draft(title=1))
    print("sa_exportcheck self-check: ok (captions by content, renamed tracks, title,\n                              spec, sign-off by words, black, media)")


if __name__ == "__main__":
    if "--test" in sys.argv:
        _test()
        sys.exit()
    ap = argparse.ArgumentParser()
    ap.add_argument("project", nargs="?")
    main(ap.parse_args().project)
