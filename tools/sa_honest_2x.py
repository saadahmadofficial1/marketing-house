#!/usr/bin/env python3
"""Enhance property photos into honest 2x listing images.

    python3 sa_honest_2x.py <photo.jpg | folder> [...]    (HONEST2X_OUT sets the output folder)

No generative fill, no geometry change, no object removal, no crop. The pipeline is
deterministic: EXIF transpose, conservative white balance and tone correction,
flat-area denoise, Lanczos 2x upscale, light denoise, mild sharpening, QC.
(done by codex)
"""

from __future__ import annotations

import csv
import hashlib
import html
import json
import os
import shutil
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter, ImageOps


def _inputs(args):
    """Photos named on the command line; a folder contributes its JPEGs in name order."""
    out = []
    for arg in args:
        p = Path(arg).expanduser()
        out += sorted(str(f) for f in p.iterdir() if f.suffix.lower() in (".jpg", ".jpeg")) if p.is_dir() else [str(p)]
    return out


INPUT_FILES = _inputs(sys.argv[1:])

PROJECT_ROOT = Path(os.environ.get("HONEST2X_OUT", "honest_2x_output")).expanduser()
OUTPUT_ROOT = PROJECT_ROOT / "output"
ENHANCED_ROOT = OUTPUT_ROOT / "enhanced"
PREVIEW_ROOT = OUTPUT_ROOT / "previews"
QC_ROOT = PROJECT_ROOT / "QC"
ZIP_PATH = OUTPUT_ROOT / "enhanced_2x.zip"
INDEX_PATH = OUTPUT_ROOT / "index.html"


@dataclass
class Metrics:
    file: str
    output: str
    source_width: int
    source_height: int
    output_width: int
    output_height: int
    source_sha256: str
    output_sha256: str
    source_bytes: int
    output_bytes: int
    mean_luma_source: float
    mean_luma_output: float
    saturation_source: float
    saturation_output: float
    wb_gain_r: float
    wb_gain_g: float
    wb_gain_b: float


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def to_uint8(array: np.ndarray) -> np.ndarray:
    return np.clip(array * 255.0 + 0.5, 0, 255).astype(np.uint8)


def luma(rgb: np.ndarray) -> np.ndarray:
    return rgb[..., 0] * 0.2126 + rgb[..., 1] * 0.7152 + rgb[..., 2] * 0.0722


def mean_saturation(rgb: np.ndarray) -> float:
    mx = rgb.max(axis=2)
    mn = rgb.min(axis=2)
    return float(np.mean((mx - mn) / np.maximum(mx, 1e-4)))


def white_balance(rgb: np.ndarray) -> tuple[np.ndarray, tuple[float, float, float]]:
    y = luma(rgb)
    chroma = rgb.max(axis=2) - rgb.min(axis=2)
    mask = (y > 0.18) & (y < 0.86) & (chroma < 0.32)
    sample = rgb[mask]
    if sample.size < 1000:
        sample = rgb[(y > 0.12) & (y < 0.92)]
    if sample.size < 1000:
        sample = rgb.reshape(-1, 3)

    channel_means = np.percentile(sample, 55, axis=0)
    neutral = float(np.mean(channel_means))
    gains = np.clip(neutral / np.maximum(channel_means, 1e-4), 0.76, 1.26)
    strength = 0.78
    gains = 1.0 + (gains - 1.0) * strength

    balanced = np.clip(rgb * gains.reshape(1, 1, 3), 0, 1)
    return balanced, (float(gains[0]), float(gains[1]), float(gains[2]))


def tone_correct(rgb: np.ndarray) -> np.ndarray:
    y = luma(rgb)

    shadow_weight = np.clip((0.58 - y) / 0.58, 0, 1) ** 1.55
    rgb = rgb + shadow_weight[..., None] * 0.165 * (1.0 - rgb)

    y = luma(rgb)
    highlight_weight = np.clip((y - 0.70) / 0.30, 0, 1) ** 1.2
    rolled = 0.70 + (rgb - 0.70) * 0.58
    rgb = rgb * (1.0 - highlight_weight[..., None] * 0.62) + rolled * (highlight_weight[..., None] * 0.62)

    y = luma(rgb)
    highlight_guard = 1.0 - np.clip((y - 0.74) / 0.26, 0, 1)
    rgb = rgb + highlight_guard[..., None] * 0.035

    mean = np.mean(rgb, axis=(0, 1), keepdims=True)
    rgb = mean + (rgb - mean) * 1.035

    y = luma(rgb)
    mid_weight = np.clip(1.0 - np.abs(y - 0.50) * 2.0, 0, 1)
    rgb = rgb + mid_weight[..., None] * 0.040

    gray = luma(rgb)[..., None]
    rgb = gray + (rgb - gray) * 0.90
    cast_weight = 1.0 - np.clip((luma(rgb) - 0.66) / 0.28, 0, 1)
    warm_fix = rgb * np.array([1.045, 0.982, 0.965], dtype=np.float32).reshape(1, 1, 3)
    rgb = rgb * (1.0 - cast_weight[..., None]) + warm_fix * cast_weight[..., None]
    return np.clip(rgb, 0, 1)


def flat_area_denoise(image: Image.Image, radius: float, flat_strength: float, chroma_radius: float) -> Image.Image:
    rgb = image.convert("RGB")
    y, cb, cr = rgb.convert("YCbCr").split()

    edges = y.filter(ImageFilter.FIND_EDGES).filter(ImageFilter.GaussianBlur(radius=1.1))
    edge_array = np.asarray(edges).astype(np.float32) / 255.0
    flat_mask = np.clip(1.0 - edge_array * 4.5, 0.0, 1.0) ** 1.3
    flat_mask *= flat_strength

    y_array = np.asarray(y).astype(np.float32)
    y_blur = np.asarray(y.filter(ImageFilter.GaussianBlur(radius=radius))).astype(np.float32)
    y_out = y_array * (1.0 - flat_mask) + y_blur * flat_mask

    cb_out = cb.filter(ImageFilter.GaussianBlur(radius=chroma_radius))
    cr_out = cr.filter(ImageFilter.GaussianBlur(radius=chroma_radius))
    merged = Image.merge("YCbCr", (Image.fromarray(np.clip(y_out, 0, 255).astype(np.uint8)), cb_out, cr_out))
    return merged.convert("RGB")


def enhance_image(source: Path, output: Path, index: int) -> Metrics:
    with Image.open(source) as opened:
        exif = opened.info.get("exif")
        icc = opened.info.get("icc_profile")
        dpi = opened.info.get("dpi")
        original = ImageOps.exif_transpose(opened).convert("RGB")

    source_arr = np.asarray(original).astype(np.float32) / 255.0
    source_luma = float(np.mean(luma(source_arr)) * 255.0)
    source_sat = mean_saturation(source_arr)

    balanced, gains = white_balance(source_arr)
    toned = tone_correct(balanced)
    working = Image.fromarray(to_uint8(toned), "RGB")
    working = flat_area_denoise(working, radius=1.05, flat_strength=0.58, chroma_radius=1.45)

    upscaled = working.resize((working.width * 2, working.height * 2), Image.Resampling.LANCZOS)
    upscaled = flat_area_denoise(upscaled, radius=0.55, flat_strength=0.20, chroma_radius=0.75)
    sharpened = upscaled.filter(ImageFilter.UnsharpMask(radius=1.15, percent=72, threshold=5))

    output.parent.mkdir(parents=True, exist_ok=True)
    save_args: dict[str, object] = {
        "format": "JPEG",
        "quality": 95,
        "subsampling": 0,
        "optimize": True,
    }
    if exif:
        save_args["exif"] = exif
    if icc:
        save_args["icc_profile"] = icc
    if dpi:
        save_args["dpi"] = dpi
    sharpened.save(output, **save_args)

    preview = sharpened.copy()
    preview.thumbnail((1800, 1200), Image.Resampling.LANCZOS)
    preview_path = PREVIEW_ROOT / f"{index:02d}_{source.stem}_preview.jpg"
    preview_path.parent.mkdir(parents=True, exist_ok=True)
    preview.save(preview_path, format="JPEG", quality=90, optimize=True)

    with Image.open(output) as checked:
        out_arr = np.asarray(checked.resize(original.size, Image.Resampling.BICUBIC)).astype(np.float32) / 255.0
        out_w, out_h = checked.size

    return Metrics(
        file=source.name,
        output=output.name,
        source_width=original.width,
        source_height=original.height,
        output_width=out_w,
        output_height=out_h,
        source_sha256=sha256(source),
        output_sha256=sha256(output),
        source_bytes=source.stat().st_size,
        output_bytes=output.stat().st_size,
        mean_luma_source=round(source_luma, 3),
        mean_luma_output=round(float(np.mean(luma(out_arr)) * 255.0), 3),
        saturation_source=round(source_sat, 5),
        saturation_output=round(mean_saturation(out_arr), 5),
        wb_gain_r=round(gains[0], 5),
        wb_gain_g=round(gains[1], 5),
        wb_gain_b=round(gains[2], 5),
    )


def write_manifest(rows: list[Metrics]) -> None:
    QC_ROOT.mkdir(parents=True, exist_ok=True)
    with (QC_ROOT / "manifest.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].__dict__.keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow(row.__dict__)

    summary = {
        "total": len(rows),
        "all_outputs_exist": all((ENHANCED_ROOT / row.output).exists() for row in rows),
        "all_2x_dimensions": all(
            row.output_width >= row.source_width * 2 and row.output_height >= row.source_height * 2
            for row in rows
        ),
        "all_hashes_changed": all(row.source_sha256 != row.output_sha256 for row in rows),
        "output_dimensions": sorted({f"{row.output_width}x{row.output_height}" for row in rows}),
        "jpeg_quality": 95,
        "upscale_method": "Pillow Lanczos 2x",
        "generative_ai_fill": False,
        "geometry_changed": False,
        "object_removal": False,
    }
    (QC_ROOT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")


def write_index(rows: list[Metrics]) -> None:
    cards = []
    for row in rows:
        preview_name = row.output.replace("_enhanced_2x.jpg", "_preview.jpg")
        # Preview filenames include the same sequence and original stem as enhanced outputs.
        preview_name = f"{row.output[:2]}_{row.file.removesuffix('.jpg')}_preview.jpg"
        cards.append(
            f"""
      <article class="photo">
        <h2>{html.escape(row.output)}</h2>
        <a href="enhanced/{html.escape(row.output)}"><img src="previews/{html.escape(preview_name)}" alt="{html.escape(row.output)}"></a>
        <p>{row.source_width}x{row.source_height} to {row.output_width}x{row.output_height}</p>
      </article>"""
        )

    INDEX_PATH.write_text(
        """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Enhanced 2x</title>
  <style>
    body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #f5f5f2; color: #1d2522; }
    header { padding: 28px 32px 12px; position: sticky; top: 0; background: rgba(245,245,242,.95); backdrop-filter: blur(8px); border-bottom: 1px solid #ddd8cf; }
    h1 { margin: 0 0 6px; font-size: 24px; font-weight: 650; letter-spacing: 0; }
    header p { margin: 0; color: #59635e; font-size: 14px; }
    main { max-width: 1480px; margin: 0 auto; padding: 18px 24px 48px; }
    .photo { margin: 0 0 28px; padding: 18px; background: #fff; border: 1px solid #ddd8cf; border-radius: 8px; }
    .photo h2 { margin: 0 0 12px; font-size: 16px; font-weight: 600; }
    .photo img { display: block; width: 100%; height: auto; border-radius: 4px; background: #eee; }
    .photo p { margin: 10px 0 0; color: #68716d; font-size: 13px; }
  </style>
</head>
<body>
  <header>
    <h1>Enhanced 2x Review</h1>
    <p>One image per section. Originals were not modified. No generative fill or object removal.</p>
  </header>
  <main>
"""
        + "\n".join(cards)
        + """
  </main>
</body>
</html>
""",
        encoding="utf-8",
    )


def write_zip(rows: list[Metrics]) -> None:
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()
    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for row in rows:
            archive.write(ENHANCED_ROOT / row.output, arcname=row.output)


def main() -> None:
    if not INPUT_FILES:
        raise SystemExit(__doc__)
    for path in (ENHANCED_ROOT, PREVIEW_ROOT, QC_ROOT):
        path.mkdir(parents=True, exist_ok=True)

    rows: list[Metrics] = []
    for index, raw_path in enumerate(INPUT_FILES, 1):
        source = Path(raw_path)
        if not source.exists():
            raise FileNotFoundError(source)
        output = ENHANCED_ROOT / f"{index:02d}_{source.stem}_enhanced_2x.jpg"
        row = enhance_image(source, output, index)
        rows.append(row)
        print(f"[{index:02d}/{len(INPUT_FILES)}] {source.name} -> {output.name}", flush=True)

    write_manifest(rows)
    write_index(rows)
    write_zip(rows)
    print(json.dumps({"enhanced": len(rows), "zip": str(ZIP_PATH), "index": str(INDEX_PATH)}, indent=2))


if __name__ == "__main__":
    main()
