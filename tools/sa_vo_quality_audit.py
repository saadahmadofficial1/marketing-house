#!/usr/bin/env python3
"""Read-only VO quality audit for the active audio in a CapCut draft.

This does not pretend to be an all-knowing damaged-voice detector. Earlier testing
already proved that the "old radio / not the same person" drift can pass normal
acoustic tests. This tool gives Saad a fast, evidence-backed shortlist:

* exact active audio clips from the saved CapCut draft, including compound clips
* a local audio snippet for each line
* transcript confidence / WER when captions are available
* simple loudness, clipping, silence and dropout measurements

This check runs locally and uploads nothing. The tool never edits CapCut or source files.
"""

from __future__ import annotations

import argparse
import csv
import html
import io
import json
import math
import os
import pathlib
import re
import subprocess
import sys
import warnings
from dataclasses import dataclass, asdict
from typing import Any

import numpy as np

warnings.filterwarnings("ignore", category=RuntimeWarning)


US = 1_000_000
CAPTION_Y = -0.892
VOICE_EXTS = {".mp3", ".wav", ".m4a", ".aac", ".mp4", ".mov"}
FRESH_PREFIX = os.environ.get("VO_FRESH_PREFIX", "narrator-")   # file-name prefix of freshly generated TTS lines
ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_DRAFTS = pathlib.Path.home() / "Movies/CapCut/User Data/Projects/com.lveditor.draft"


@dataclass
class ClipRow:
    time_s: float
    end_s: float
    duration_s: float
    source_s: float
    volume: float
    track: str
    context: str
    file: str
    path: str
    clip_file: str
    script: str = ""
    heard: str = ""
    wer: float | None = None
    logprob: float | None = None
    no_speech: float | None = None
    rms_db: float | None = None
    peak_db: float | None = None
    clipping_pct: float | None = None
    silence_pct: float | None = None
    dropout_count: int | None = None
    roughness_db: float | None = None
    hf_ratio: float | None = None
    flags: str = ""
    priority: float = 0.0


@dataclass
class Subdraft:
    id: str
    name: str
    type: str
    duration_s: float
    path: pathlib.Path
    draft: dict[str, Any]


def mmss(t: float) -> str:
    m = int(t // 60)
    s = t - m * 60
    return f"{m:02d}:{s:05.2f}"


def words(text: str) -> list[str]:
    return re.sub(r"[^a-z0-9 ]", " ", text.lower()).split()


def wer(ref: str, hyp: str) -> float:
    r = words(ref)
    h = words(hyp)
    if not r:
        return 0.0
    d = [[0] * (len(h) + 1) for _ in range(len(r) + 1)]
    for i in range(len(r) + 1):
        d[i][0] = i
    for j in range(len(h) + 1):
        d[0][j] = j
    for i in range(1, len(r) + 1):
        for j in range(1, len(h) + 1):
            d[i][j] = min(
                d[i - 1][j] + 1,
                d[i][j - 1] + 1,
                d[i - 1][j - 1] + (r[i - 1] != h[j - 1]),
            )
    return d[-1][-1] / len(r)


def read_json(path: pathlib.Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8", errors="replace"))


def choose_draft(project: pathlib.Path, draft: pathlib.Path | None) -> pathlib.Path:
    if draft:
        return draft
    timelines = sorted((project / "Timelines").glob("*/draft_info.json"))
    if timelines:
        return max(timelines, key=lambda p: p.stat().st_mtime)
    return project / "draft_info.json"


def unwrap_subdraft(data: dict[str, Any]) -> dict[str, Any]:
    nested = ((data.get("materials") or {}).get("drafts") or [])
    if nested and isinstance(nested[0].get("draft"), dict):
        return nested[0]["draft"]
    return data


def load_subdrafts(project: pathlib.Path) -> list[Subdraft]:
    out: list[Subdraft] = []
    for config_path in sorted((project / "subdraft").glob("*/sub_draft_config.json")):
        try:
            config = read_json(config_path)
            data = read_json(config_path.parent / config.get("draft_json_file", "draft_content.json"))
        except Exception:
            continue
        out.append(
            Subdraft(
                id=str(config.get("id") or config_path.parent.name),
                name=str(config.get("name") or ""),
                type=str(config.get("type") or ""),
                duration_s=float(config.get("rough_cut_duration") or 0) / US,
                path=config_path.parent,
                draft=unwrap_subdraft(data),
            )
        )
    return out


def matching_subdraft(material: dict[str, Any], segment: dict[str, Any], subdrafts: list[Subdraft]) -> Subdraft | None:
    if material.get("path") or material.get("media_path"):
        return None
    if not material.get("has_audio") and material.get("extra_type_option") != 2:
        return None
    duration_s = float(material.get("duration") or segment["target_timerange"]["duration"]) / US
    wanted_type = str(material.get("type") or "")
    candidates = [s for s in subdrafts if not wanted_type or s.type == wanted_type]
    if not candidates:
        candidates = subdrafts
    candidates = sorted(candidates, key=lambda s: abs(s.duration_s - duration_s))
    if candidates and abs(candidates[0].duration_s - duration_s) <= 0.25:
        return candidates[0]
    return None


def resolve_path(value: str, project_dir: pathlib.Path) -> pathlib.Path:
    if value.startswith("##_draftpath_placeholder_"):
        return project_dir / value.split("_##/", 1)[-1]
    return pathlib.Path(value).expanduser()


def material_maps(draft: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    mats = draft.get("materials") or {}
    audios = {m.get("id"): m for m in mats.get("audios") or []}
    videos = {m.get("id"): m for m in mats.get("videos") or []}
    drafts = {m.get("id"): m for m in mats.get("drafts") or []}
    return audios, videos, drafts


def text_content(material: dict[str, Any]) -> str:
    try:
        content = json.loads(material.get("content") or "{}")
    except json.JSONDecodeError:
        return ""
    return (content.get("text") or "").strip()


def text_size(material: dict[str, Any]) -> float:
    try:
        content = json.loads(material.get("content") or "{}")
    except json.JSONDecodeError:
        return 0.0
    styles = content.get("styles") or [{}]
    return float(styles[0].get("size") or 0.0)


def segment_range(segment: dict[str, Any], base_s: float) -> tuple[float, float]:
    tr = segment["target_timerange"]
    start = base_s + int(tr["start"]) / US
    duration = int(tr["duration"]) / US
    return start, start + duration


def collect_captions(
    draft: dict[str, Any],
    project_dir: pathlib.Path,
    subdrafts: list[Subdraft],
    base_s: float = 0.0,
    context: str = "main",
) -> list[tuple[float, float, str, str]]:
    captions: list[tuple[float, float, str, str]] = []
    _audios, videos, drafts = material_maps(draft)
    texts = {m.get("id"): m for m in (draft.get("materials") or {}).get("texts") or []}
    for track in draft.get("tracks") or []:
        if track.get("visible") is False:
            continue
        for seg in track.get("segments") or []:
            if seg.get("visible") is False:
                continue
            mat = texts.get(seg.get("material_id"))
            if mat:
                text = text_content(mat)
                size = text_size(mat)
                y = ((seg.get("clip") or {}).get("transform") or {}).get("y", 0)
                if text and size < 10 and abs(float(y) - CAPTION_Y) < 0.08:
                    start, end = segment_range(seg, base_s)
                    captions.append((start, end, text, context))
                continue
            dmat = drafts.get(seg.get("material_id"))
            inner = dmat.get("draft") if dmat else None
            if isinstance(inner, dict):
                start, _end = segment_range(seg, base_s)
                captions.extend(collect_captions(inner, project_dir, subdrafts, start, f"{context}/compound"))
                continue
            vmat = videos.get(seg.get("material_id"))
            sd = matching_subdraft(vmat, seg, subdrafts) if vmat else None
            if sd:
                start, _end = segment_range(seg, base_s)
                captions.extend(collect_captions(sd.draft, project_dir, subdrafts, start, f"{context}/subdraft:{sd.name or sd.id}"))
    return sorted(captions)


def intended_text(captions: list[tuple[float, float, str, str]], start: float, end: float) -> str:
    parts = []
    seen = set()
    for cap_start, cap_end, text, _ctx in captions:
        if min(end, cap_end) - max(start, cap_start) <= 0.12:
            continue
        norm = re.sub(r"\s+", " ", text).strip()
        if norm and norm not in seen:
            parts.append(norm)
            seen.add(norm)
    return " ".join(parts).strip()


def collect_audio(
    draft: dict[str, Any],
    project_dir: pathlib.Path,
    captions: list[tuple[float, float, str, str]],
    subdrafts: list[Subdraft],
    base_s: float = 0.0,
    context: str = "main",
    min_volume: float = 0.15,
) -> list[ClipRow]:
    audios, videos, drafts = material_maps(draft)
    rows: list[ClipRow] = []
    for ti, track in enumerate(draft.get("tracks") or []):
        if track.get("visible") is False:
            continue
        track_type = track.get("type") or ""
        for seg in sorted(track.get("segments") or [], key=lambda s: s["target_timerange"]["start"]):
            if seg.get("visible") is False:
                continue
            start, end = segment_range(seg, base_s)
            volume = float(seg.get("volume", 1.0) or 0.0)
            dmat = drafts.get(seg.get("material_id"))
            inner = dmat.get("draft") if dmat else None
            if isinstance(inner, dict):
                rows.extend(collect_audio(inner, project_dir, captions, subdrafts, start, f"{context}/compound", min_volume))
                continue
            if track_type not in {"audio", "video"} or volume < min_volume:
                continue
            mat = audios.get(seg.get("material_id")) or videos.get(seg.get("material_id"))
            if not mat:
                continue
            sd = matching_subdraft(mat, seg, subdrafts)
            if sd:
                rows.extend(collect_audio(sd.draft, project_dir, captions, subdrafts, start, f"{context}/subdraft:{sd.name or sd.id}", min_volume))
                continue
            path = resolve_path(mat.get("path") or "", project_dir)
            if not path.exists() or path.suffix.lower() not in VOICE_EXTS:
                continue
            source = seg.get("source_timerange") or {}
            source_s = int(source.get("start", 0)) / US
            duration_s = end - start
            if duration_s <= 0.15:
                continue
            rows.append(
                ClipRow(
                    time_s=round(start, 3),
                    end_s=round(end, 3),
                    duration_s=round(duration_s, 3),
                    source_s=round(source_s, 3),
                    volume=round(volume, 4),
                    track=f"{track_type}:{ti}",
                    context=context,
                    file=path.name,
                    path=str(path),
                    clip_file="",
                    script=intended_text(captions, start, end),
                )
            )
    return rows


def run_ffmpeg_clip(src: pathlib.Path, dst: pathlib.Path, start_s: float, duration_s: float) -> bool:
    dst.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-v",
        "error",
        "-ss",
        f"{max(0.0, start_s):.3f}",
        "-t",
        f"{duration_s:.3f}",
        "-i",
        str(src),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "44100",
        "-b:a",
        "160k",
        str(dst),
    ]
    proc = subprocess.run(cmd, capture_output=True)
    return proc.returncode == 0 and dst.exists() and dst.stat().st_size > 1000


def decode_float(path: pathlib.Path, sr: int = 44100) -> tuple[np.ndarray, int]:
    proc = subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            str(sr),
            "-f",
            "f32le",
            "-",
        ],
        capture_output=True,
    )
    if proc.returncode != 0 or not proc.stdout:
        return np.array([], dtype=np.float32), sr
    return np.frombuffer(proc.stdout, dtype=np.float32), sr


def db(value: float) -> float:
    return 20.0 * math.log10(max(value, 1e-12))


def audio_metrics(path: pathlib.Path) -> dict[str, float | int | None]:
    samples, sr = decode_float(path)
    if len(samples) < sr // 10:
        return {
            "rms_db": None,
            "peak_db": None,
            "clipping_pct": None,
            "silence_pct": None,
            "dropout_count": None,
            "roughness_db": None,
            "hf_ratio": None,
        }
    samples = np.nan_to_num(samples.astype(np.float32))
    peak = float(np.max(np.abs(samples)))
    rms = float(np.sqrt(np.mean(samples * samples)))
    clipping = float(np.mean(np.abs(samples) >= 0.985) * 100.0)

    frame = max(1, int(sr * 0.02))
    n = len(samples) // frame
    framed = samples[: n * frame].reshape(n, frame) if n else samples.reshape(1, -1)
    frame_rms = np.sqrt(np.mean(framed * framed, axis=1) + 1e-12)
    frame_db = 20 * np.log10(frame_rms + 1e-12)
    silence = float(np.mean(frame_db < -45.0) * 100.0)
    roughness = float(np.mean(np.abs(np.diff(frame_db)))) if len(frame_db) > 1 else 0.0

    dropout_count = 0
    low = frame_db < -45.0
    if len(low) > 8:
        i = 1
        while i < len(low) - 1:
            if not low[i]:
                i += 1
                continue
            j = i
            while j < len(low) and low[j]:
                j += 1
            run_ms = (j - i) * 20
            before = np.max(frame_db[max(0, i - 5):i]) if i > 0 else -120
            after = np.max(frame_db[j:min(len(frame_db), j + 5)]) if j < len(frame_db) else -120
            if 30 <= run_ms <= 260 and before > -35 and after > -35:
                dropout_count += 1
            i = j

    nfft = 2048
    hop = 512
    if len(samples) < nfft:
        hf_ratio = None
    else:
        win = np.hanning(nfft).astype(np.float32)
        starts = range(0, len(samples) - nfft + 1, hop)
        spectra = []
        voiced = []
        for st in starts:
            chunk = samples[st:st + nfft]
            crms = float(np.sqrt(np.mean(chunk * chunk)))
            if crms <= 1e-5:
                continue
            mag = np.abs(np.fft.rfft(chunk * win)) + 1e-9
            spectra.append(mag)
            voiced.append(crms)
        if not spectra:
            hf_ratio = None
        else:
            spec = np.vstack(spectra)
            rms_arr = np.array(voiced)
            keep = rms_arr > np.percentile(rms_arr, 55)
            spec = spec[keep] if np.any(keep) else spec
            freqs = np.fft.rfftfreq(nfft, 1 / sr)
            total = np.sum(spec, axis=1) + 1e-9
            hf = np.sum(spec[:, freqs > 5000], axis=1)
            hf_ratio = float(np.median(hf / total))

    return {
        "rms_db": round(db(rms), 2),
        "peak_db": round(db(peak), 2),
        "clipping_pct": round(clipping, 4),
        "silence_pct": round(silence, 2),
        "dropout_count": int(dropout_count),
        "roughness_db": round(roughness, 2),
        "hf_ratio": round(hf_ratio, 4) if hf_ratio is not None else None,
    }


_MODEL = None


def whisper_model():
    global _MODEL
    if _MODEL is None:
        from faster_whisper import WhisperModel

        _MODEL = WhisperModel("base.en", device="cpu", compute_type="int8")
    return _MODEL


def transcribe(path: pathlib.Path) -> tuple[str, float, float]:
    segs, _info = whisper_model().transcribe(str(path), language="en", beam_size=5)
    segs = list(segs)
    text = " ".join(s.text for s in segs).strip()
    logprob = sum(s.avg_logprob for s in segs) / len(segs) if segs else 0.0
    no_speech = max((s.no_speech_prob for s in segs), default=0.0)
    return text, logprob, no_speech


def score_rows(rows: list[ClipRow]) -> None:
    rms_values = np.array([r.rms_db for r in rows if r.rms_db is not None], dtype=float)
    median_rms = float(np.median(rms_values)) if len(rms_values) else -20.0
    for row in rows:
        flags = []
        score = 0.0
        if row.wer is not None and row.script:
            if row.wer >= 0.20:
                flags.append("transcript-mismatch")
                score += min(4.0, row.wer * 4.0)
            elif row.wer > 0.0:
                flags.append("minor-transcript-drift")
                score += row.wer
        if row.logprob is not None and row.logprob < -0.38:
            flags.append("low-confidence-read")
            score += 1.2
        if row.clipping_pct is not None and row.clipping_pct > 0.02:
            flags.append("possible-clipping")
            score += 1.5
        if row.dropout_count and row.dropout_count >= 2:
            if (row.wer == 0.0 or row.wer is None) and (row.logprob is None or row.logprob > -0.34):
                flags.append("pause-gaps")
                score += 0.3 if row.dropout_count < 8 else 0.8
            else:
                flags.append("short-dropouts")
                score += min(2.5, row.dropout_count * 0.7)
        if row.silence_pct is not None and row.silence_pct > 45 and row.duration_s > 1.5:
            flags.append("very-sparse-audio")
            score += 0.8
        if row.rms_db is not None and abs(row.rms_db - median_rms) > 4.0:
            flags.append("volume-outlier")
            score += 0.9
        if row.file.startswith(FRESH_PREFIX):
            flags.append("fresh-generated-line")
            score += 0.2
        row.flags = ", ".join(flags)
        row.priority = round(score, 3)


def write_reports(rows: list[ClipRow], out_dir: pathlib.Path, title: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    data = [asdict(r) for r in rows]
    (out_dir / "voice_qc.json").write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    with (out_dir / "voice_qc.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(data[0].keys()) if data else ["empty"])
        writer.writeheader()
        writer.writerows(data)
    rows_sorted = sorted(rows, key=lambda r: (-r.priority, r.time_s))
    esc = lambda value: html.escape(str(value or ""))
    body = []
    for row in rows_sorted:
        rel = pathlib.Path(row.clip_file).name
        body.append(
            f"""
<section class="row {'hot' if row.priority >= 1.5 else ''}">
  <div class="meta">
    <b>{esc(mmss(row.time_s))}</b><span>{esc(row.duration_s)}s</span>
    <span>priority {row.priority:.2f}</span><span>{esc(row.flags or 'listen check')}</span>
  </div>
  <audio controls preload="none" src="clips/{esc(rel)}"></audio>
  <div class="file">{esc(row.file)}</div>
  <div class="grid">
    <div><h3>Script / caption</h3><p>{esc(row.script)}</p></div>
    <div><h3>Whisper heard</h3><p>{esc(row.heard)}</p></div>
  </div>
  <div class="nums">
    WER {'' if row.wer is None else f'{row.wer:.3f}'} ·
    confidence {'' if row.logprob is None else f'{row.logprob:.3f}'} ·
    RMS {'' if row.rms_db is None else f'{row.rms_db:.1f}'} dB ·
    peak {'' if row.peak_db is None else f'{row.peak_db:.1f}'} dB ·
    silence {'' if row.silence_pct is None else f'{row.silence_pct:.0f}'}% ·
    dropouts {row.dropout_count if row.dropout_count is not None else ''}
  </div>
</section>"""
        )
    page = f"""<!doctype html>
<meta charset="utf-8">
<title>{esc(title)} VO quality audit</title>
<style>
body{{margin:0;background:#101114;color:#e9eaee;font:14px/1.5 -apple-system,BlinkMacSystemFont,Segoe UI,sans-serif}}
main{{max-width:1100px;margin:0 auto;padding:28px}}
h1{{font-size:22px;margin:0 0 4px}}
.note{{border:1px solid #3c414b;background:#171a20;padding:12px 14px;margin:16px 0;color:#c7c9d1}}
.row{{border-top:1px solid #262932;padding:14px 0}}
.row.hot{{background:#17130f;box-shadow:0 0 0 100vmax #17130f;clip-path:inset(0 -100vmax)}}
.meta{{display:flex;gap:12px;align-items:baseline;color:#aaaeb8;font-size:12px}}
.meta b{{font-size:14px;color:#fff;font-variant-numeric:tabular-nums}}
audio{{width:100%;height:32px;margin:8px 0}}
.file{{color:#8f949e;font-size:12px;word-break:break-all;margin-bottom:8px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:14px}}
h3{{font-size:11px;letter-spacing:.02em;text-transform:uppercase;color:#777c86;margin:0 0 3px}}
p{{margin:0}}
.nums{{color:#858b96;font-size:12px;margin-top:8px;font-variant-numeric:tabular-nums}}
@media(max-width:760px){{.grid{{grid-template-columns:1fr}}}}
</style>
<main>
<h1>{esc(title)} VO quality audit</h1>
<div class="note"><b>Read this as a shortlist, not a final verdict.</b> Past testing
showed that the radio-like TTS voice drift cannot be caught reliably by
acoustic metrics alone. High-priority rows deserve a re-listen or regeneration;
low-priority rows are not guaranteed clean.</div>
{''.join(body)}
</main>"""
    (out_dir / "voice_qc.html").write_text(page, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True, help="CapCut project folder or project name under CapCut drafts")
    parser.add_argument("--draft", help="Optional explicit draft_info.json path")
    parser.add_argument("--out", required=True, help="Output report folder")
    parser.add_argument("--after", type=float, default=0.0, help="Only include clips whose timeline start is after this many seconds")
    parser.add_argument("--min-volume", type=float, default=0.15)
    parser.add_argument("--no-transcribe", action="store_true")
    parser.add_argument("--title", default="")
    args = parser.parse_args()

    project = pathlib.Path(args.project).expanduser()
    if not project.exists():
        project = DEFAULT_DRAFTS / args.project
    if not project.exists():
        raise SystemExit(f"project not found: {args.project}")
    draft_path = choose_draft(project, pathlib.Path(args.draft).expanduser() if args.draft else None)
    draft = read_json(draft_path)
    subdrafts = load_subdrafts(project)
    out_dir = pathlib.Path(args.out).expanduser()
    clips_dir = out_dir / "clips"

    captions = collect_captions(draft, project, subdrafts)
    rows = collect_audio(draft, project, captions, subdrafts, min_volume=args.min_volume)
    rows = [r for r in rows if r.time_s >= args.after]
    rows.sort(key=lambda r: (r.time_s, r.track, r.file))

    deduped: list[ClipRow] = []
    seen = set()
    for row in rows:
        key = (row.path, round(row.source_s, 2), round(row.duration_s, 2), round(row.time_s, 2))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    rows = deduped

    for index, row in enumerate(rows, start=1):
        src = pathlib.Path(row.path)
        safe_stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", pathlib.Path(row.file).stem)[:72]
        name = f"{index:03d}_{int(row.time_s // 60):02d}m{int(row.time_s % 60):02d}s_{safe_stem}.mp3"
        dst = clips_dir / name
        if run_ffmpeg_clip(src, dst, row.source_s, row.duration_s):
            row.clip_file = str(dst)
            metrics = audio_metrics(dst)
            for key, value in metrics.items():
                setattr(row, key, value)
            if not args.no_transcribe:
                try:
                    heard, logprob, no_speech = transcribe(dst)
                    row.heard = heard
                    row.logprob = round(logprob, 3)
                    row.no_speech = round(no_speech, 3)
                    row.wer = round(wer(row.script, heard), 3) if row.script else None
                except Exception as exc:
                    row.heard = f"[transcription unavailable: {exc}]"
        else:
            row.clip_file = ""
            row.flags = "extract-failed"
            row.priority = 9.0
    score_rows(rows)
    write_reports(rows, out_dir, args.title or project.name)

    flagged = [r for r in rows if r.priority >= 1.5]
    print(f"{len(rows)} active voice/audio clips audited from {draft_path}")
    print(f"{len(flagged)} high-priority re-listen candidates")
    print(f"report: {out_dir / 'voice_qc.html'}")
    for row in sorted(flagged, key=lambda r: (-r.priority, r.time_s))[:30]:
        print(
            f"{mmss(row.time_s)} priority={row.priority:.2f} "
            f"flags={row.flags or '-'} file={row.file}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
