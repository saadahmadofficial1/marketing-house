#!/usr/bin/env python3
"""Distill every CapCut draft into one edit-style report (EDIT_DNA).
  sa_capcut.py [-o Reference/EDIT_DNA.md]
Reads each project's draft_info.json (local CapCut timeline JSON) and extracts
what matters: canvas ratio, duration, track mix, text used, effects/transitions,
audio. Output = the patterns of how Saad actually edits.
"""
import os, json, glob, sys, collections, statistics

DRAFTS = os.path.expanduser("~/Movies/CapCut/User Data/Projects/com.lveditor.draft")

def dig(d):
    """Parse one draft_info.json -> summary dict (defensive: schema shifts)."""
    canvas = d.get("canvas_config", {})
    dur_us = d.get("duration", 0)
    tracks = d.get("tracks", [])
    tcount = collections.Counter(t.get("type", "?") for t in tracks)
    segs = sum(len(t.get("segments", [])) for t in tracks)
    mats = d.get("materials", {})
    texts = []
    for tx in mats.get("texts", []):
        c = tx.get("content", "")
        if isinstance(c, str) and c.strip():
            # content is often rich JSON: pull plain text if so
            try:
                j = json.loads(c)
                c = j.get("text") or "".join(x.get("text", "") for x in j.get("styles", [])) or ""
            except Exception:
                pass
            if c.strip():
                texts.append(c.strip().replace("\n", " ")[:80])
    effects = [e.get("name") or e.get("effect_id", "?") for e in mats.get("video_effects", [])]
    trans = [t.get("name", "?") for t in mats.get("transitions", [])]
    audios = [os.path.basename(a.get("path", "")) for a in mats.get("audios", []) if a.get("path")]
    # Saad's final-timeline heuristics (2026-07-07):
    # outro attached + bg music => the delivered timeline; export_range = his I->O
    # render selection; the bg-music segment start == true in-point.
    er = (d.get("config") or {}).get("export_range") or {}
    outro = sorted({os.path.basename(v.get("path", "")) for v in mats.get("videos", [])
                    if any(k in v.get("path", "").lower() for k in ("outro", "endcard", "logo"))})
    music_ids = {a["id"] for a in mats.get("audios", []) if a.get("type") == "music"}
    music_starts = sorted(s["target_timerange"]["start"] / 1e6
                          for t_ in tracks if t_.get("type") == "audio"
                          for s in t_.get("segments", []) if s.get("material_id") in music_ids)
    # cut pace: main video track = the one with the most segments (the primary cut sequence)
    video_tracks = [t for t in tracks if t.get("type") == "video" and t.get("segments")]
    main_track = max(video_tracks, key=lambda t: len(t["segments"]), default=None)
    cut_lengths = [s["target_timerange"]["duration"] / 1e6 for s in main_track["segments"]] if main_track else []
    cut_median = round(statistics.median(cut_lengths), 2) if cut_lengths else None
    return {
        "export_in": round(er.get("start", 0) / 1e6, 1) if er else None,
        "export_dur": round(er.get("duration", 0) / 1e6, 1) if er else None,
        "outro": outro,
        "music_starts": music_starts[:4],
        "is_final": bool(outro and music_ids),
        "cut_median": cut_median,
        "n_cuts": len(cut_lengths),
        "ratio": canvas.get("ratio", "?"),
        "size": f'{canvas.get("width","?")}x{canvas.get("height","?")}',
        "dur_s": round(dur_us / 1e6, 1),
        "tracks": dict(tcount),
        "segments": segs,
        "texts": texts,
        "effects": [e for e in effects if e],
        "transitions": [t for t in trans if t],
        "audio": audios,
    }

def cluster_label(s):
    """Bucket a FINAL project into a style, purely from real signal (no guessing):
    cut pace + whether it carries on-screen text. Mirrors the 3 known style modes
    and leaves room for a 4th ('other') when a project doesn't fit cleanly."""
    cm, has_text = s.get("cut_median"), bool(s["texts"])
    if cm is None:
        return "other/unclear"
    if cm <= 2.5 and not has_text:
        return "tribute/fast-montage"
    if 2.5 < cm <= 6 and has_text:
        return "tutorial/feature (mode A)"
    if cm > 6 and not has_text:
        return "animation/powtoon (mode B)"
    return "other/mixed"

def main():
    out = sys.argv[sys.argv.index("-o") + 1] if "-o" in sys.argv else None
    L, agg_eff, agg_tr, ratios = [], collections.Counter(), collections.Counter(), collections.Counter()
    projects = sorted(glob.glob(os.path.join(DRAFTS, "*", "draft_info.json")))
    L.append(f"# CapCut EDIT DNA — distilled from {len(projects)} local projects\n")
    finals = []
    for p in projects:
        name = os.path.basename(os.path.dirname(p))
        try:
            s = dig(json.load(open(p, encoding="utf-8")))
        except Exception as e:
            L.append(f"## {name} — unreadable ({e})")
            continue
        ratios[s["ratio"]] += 1
        agg_eff.update(s["effects"]); agg_tr.update(s["transitions"])
        badge = " · ⭐FINAL" if s.get("is_final") else ""
        L.append(f"## {name} — {s['size']} ({s['ratio']}) · {s['dur_s']}s · "
                 f"{s['segments']} clips · tracks {s['tracks']}{badge}")
        if s.get("cut_median") is not None:
            L.append(f"  - cut pace: median {s['cut_median']}s over {s['n_cuts']} cuts")
        if s.get("export_in") is not None:
            L.append(f"  - render selection (I→O): {s['export_in']}s + {s['export_dur']}s")
        if s.get("music_starts"):
            L.append(f"  - bg music starts: {', '.join(str(x)+'s' for x in s['music_starts'])} (in-point candidates)")
        if s.get("outro"):
            L.append(f"  - outro: {', '.join(s['outro'][:3])}")
        if s["texts"]:
            L.append("  - text: " + " | ".join(s["texts"][:8]))
        if s["effects"]:
            L.append("  - effects: " + ", ".join(sorted(set(s["effects"]))[:10]))
        if s["transitions"]:
            L.append("  - transitions: " + ", ".join(sorted(set(s["transitions"]))[:10]))
        if s["audio"]:
            L.append("  - audio: " + ", ".join(s["audio"][:5]))
        if s.get("is_final"):
            finals.append((name, s))

    # style census — only FINAL (delivered) timelines count; drafts/experiments skew pace stats
    clusters = collections.defaultdict(list)
    for name, s in finals:
        clusters[cluster_label(s)].append((name, s["cut_median"], s["n_cuts"]))
    census = [f"\n## STYLE CENSUS — {len(finals)} final/delivered projects, clustered by real cut pace\n"]
    for label, items in sorted(clusters.items(), key=lambda kv: -len(kv[1])):
        medians = [m for _, m, _ in items if m is not None]
        avg = round(statistics.median(medians), 2) if medians else "?"
        census.append(f"### {label} — {len(items)} projects, median-of-medians {avg}s")
        for name, cm, n in sorted(items, key=lambda x: x[0]):
            census.append(f"  - {name}: {cm}s median ({n} cuts)")
    L = L[:1] + census + L[1:]

    L.insert(1, f"\n**Ratios used:** {dict(ratios)}\n"
                f"**Top effects:** {agg_eff.most_common(10)}\n"
                f"**Top transitions:** {agg_tr.most_common(10)}\n")
    text = "\n".join(L)
    if out:
        open(out, "w", encoding="utf-8").write(text + "\n")
        print(f"written: {out}  ({len(projects)} projects, {len(finals)} final)")
    else:
        print(text)

if __name__ == "__main__":
    main()
