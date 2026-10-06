#!/usr/bin/env python3
"""Native-resolution property-photo detail enhancement with no colour or exposure grade.

Uses only the detail fields already assigned to each working-copy JPEG: luminance
noise reduction, chroma noise reduction, and sharpening. Geometry, crop, perspective,
colour, tone, text, signage, and scene content are not changed. Files with zero detail
settings are copied byte-for-byte. Only --output and --qc are written; the --input originals
are never touched.

    python3 sa_xmp_detail_apply.py --input <jpegs+xmp> --output <out> --qc <qc> [--validate-only]
(done by codex)
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from PIL import Image, ImageFilter


DETAIL_FIELDS = ("Sharpness", "LuminanceSmoothing", "ColorNoiseReduction")
JPEG_EXTENSIONS = {".jpg", ".jpeg"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_detail_settings(xmp_path: Path) -> dict[str, int]:
    text = xmp_path.read_text(encoding="utf-8", errors="ignore")
    values: dict[str, int] = {}
    for field in DETAIL_FIELDS:
        match = re.search(rf'crs:{field}="([+-]?\d+(?:\.\d+)?)"', text)
        values[field] = round(float(match.group(1))) if match else 0
    return values


def enhance_detail(image: Image.Image, settings: dict[str, int]) -> Image.Image:
    sharpness = max(0, settings["Sharpness"])
    luma_nr = max(0, settings["LuminanceSmoothing"])
    color_nr = max(0, settings["ColorNoiseReduction"])

    rgb = image.convert("RGB")
    y, cb, cr = rgb.convert("YCbCr").split()

    if luma_nr:
        radius = 0.25 + 0.80 * min(luma_nr, 50) / 50.0
        amount = 0.12 + 0.40 * min(luma_nr, 50) / 50.0
        softened_y = y.filter(ImageFilter.GaussianBlur(radius=radius))
        y = Image.blend(y, softened_y, amount)

    if color_nr:
        radius = 0.25 + 1.20 * min(color_nr, 50) / 50.0
        amount = 0.25 + 0.60 * min(color_nr, 50) / 50.0
        cb = Image.blend(cb, cb.filter(ImageFilter.GaussianBlur(radius=radius)), amount)
        cr = Image.blend(cr, cr.filter(ImageFilter.GaussianBlur(radius=radius)), amount)

    result = Image.merge("YCbCr", (y, cb, cr)).convert("RGB")
    if sharpness:
        radius = 0.75 + 0.55 * min(sharpness, 50) / 50.0
        percent = round(24 + 58 * min(sharpness, 50) / 50.0)
        result = result.filter(
            ImageFilter.UnsharpMask(radius=radius, percent=percent, threshold=3)
        )
    return result


def process_one(source: Path, input_root: Path, output_root: Path) -> dict[str, object]:
    relative = source.relative_to(input_root)
    output = output_root / relative
    output.parent.mkdir(parents=True, exist_ok=True)
    xmp = source.with_suffix(".xmp")
    settings = read_detail_settings(xmp) if xmp.exists() else dict.fromkeys(DETAIL_FIELDS, 0)
    applied = any(settings.values())

    with Image.open(source) as opened:
        source_size = opened.size
        source_format = opened.format
        exif = opened.info.get("exif")
        icc = opened.info.get("icc_profile")
        dpi = opened.info.get("dpi")

        if not applied:
            opened.close()
            shutil.copy2(source, output)
        else:
            result = enhance_detail(opened, settings)
            save_args: dict[str, object] = {
                "format": "JPEG",
                "quality": 96,
                "subsampling": 0,
                "optimize": True,
            }
            if exif:
                save_args["exif"] = exif
            if icc:
                save_args["icc_profile"] = icc
            if dpi:
                save_args["dpi"] = dpi
            result.save(output, **save_args)
            shutil.copystat(source, output)

    with Image.open(output) as checked:
        output_size = checked.size
        output_format = checked.format

    if source_size != output_size:
        raise ValueError(f"dimension mismatch: {source_size} -> {output_size}")
    if source_format not in {"JPEG", "MPO"} or output_format not in {"JPEG", "MPO"}:
        raise ValueError(f"format mismatch: {source_format} -> {output_format}")

    return {
        "file": relative.as_posix(),
        "source_width": source_size[0],
        "source_height": source_size[1],
        "source_format": source_format,
        "output_format": output_format,
        "output_width": output_size[0],
        "output_height": output_size[1],
        "detail_enhanced": applied,
        "sharpness": settings["Sharpness"],
        "luminance_noise_reduction": settings["LuminanceSmoothing"],
        "color_noise_reduction": settings["ColorNoiseReduction"],
        "source_sha256": sha256(source),
        "output_sha256": sha256(output),
        "source_bytes": source.stat().st_size,
        "output_bytes": output.stat().st_size,
    }


def validate_one(source: Path, input_root: Path, output_root: Path) -> dict[str, object]:
    relative = source.relative_to(input_root)
    output = output_root / relative
    if not output.exists():
        raise FileNotFoundError(f"missing output: {relative}")
    xmp = source.with_suffix(".xmp")
    settings = read_detail_settings(xmp) if xmp.exists() else dict.fromkeys(DETAIL_FIELDS, 0)
    applied = any(settings.values())

    with Image.open(source) as source_image, Image.open(output) as output_image:
        source_size = source_image.size
        output_size = output_image.size
        source_format = source_image.format
        output_format = output_image.format
    if source_size != output_size:
        raise ValueError(f"dimension mismatch: {source_size} -> {output_size}")
    if source_format not in {"JPEG", "MPO"} or output_format not in {"JPEG", "MPO"}:
        raise ValueError(f"format mismatch: {source_format} -> {output_format}")

    source_digest = sha256(source)
    output_digest = sha256(output)
    if not applied and source_digest != output_digest:
        raise ValueError("zero-detail frame is not byte-identical")
    return {
        "file": relative.as_posix(),
        "source_width": source_size[0],
        "source_height": source_size[1],
        "source_format": source_format,
        "output_format": output_format,
        "output_width": output_size[0],
        "output_height": output_size[1],
        "detail_enhanced": applied,
        "sharpness": settings["Sharpness"],
        "luminance_noise_reduction": settings["LuminanceSmoothing"],
        "color_noise_reduction": settings["ColorNoiseReduction"],
        "source_sha256": source_digest,
        "output_sha256": output_digest,
        "source_bytes": source.stat().st_size,
        "output_bytes": output.stat().st_size,
    }


def write_manifest(rows: list[dict[str, object]], qc_root: Path) -> None:
    qc_root.mkdir(parents=True, exist_ok=True)
    rows.sort(key=lambda row: str(row["file"]).casefold())
    summary = {
        "total": len(rows),
        "detail_enhanced": sum(bool(row["detail_enhanced"]) for row in rows),
        "byte_identical_clean_frames": sum(
            row["source_sha256"] == row["output_sha256"] for row in rows
        ),
        "dimension_mismatches": sum(
            (row["source_width"], row["source_height"])
            != (row["output_width"], row["output_height"])
            for row in rows
        ),
    }
    (qc_root / "detail_enhancement_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    if rows:
        with (qc_root / "detail_enhancement_manifest.csv").open(
            "w", newline="", encoding="utf-8"
        ) as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--qc", type=Path, required=True)
    parser.add_argument("--property", help="Only process this top-level property folder")
    parser.add_argument("--file", help="Only process this path relative to the input root")
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--workers", type=int, default=max(1, min(3, (os.cpu_count() or 2) - 1)))
    args = parser.parse_args()

    if args.file:
        files = [args.input / args.file]
    else:
        search_root = args.input / args.property if args.property else args.input
        files = sorted(
            path for path in search_root.rglob("*") if path.suffix.lower() in JPEG_EXTENSIONS
        )
    if not files:
        raise SystemExit("No JPEG images found")

    rows: list[dict[str, object]] = []
    errors: list[dict[str, str]] = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        worker = validate_one if args.validate_only else process_one
        futures = {pool.submit(worker, source, args.input, args.output): source for source in files}
        for index, future in enumerate(as_completed(futures), 1):
            source = futures[future]
            try:
                row = future.result()
                rows.append(row)
                if not args.quiet:
                    print(f"[{index}/{len(files)}] {source.relative_to(args.input)}", flush=True)
            except Exception as exc:
                errors.append({"file": source.relative_to(args.input).as_posix(), "error": str(exc)})
                print(f"[ERROR] {source.relative_to(args.input)}: {exc}", flush=True)

    write_manifest(rows, args.qc)
    (args.qc / "detail_enhancement_errors.json").write_text(
        json.dumps(errors, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {"processed": len(rows), "errors": len(errors), "output": str(args.output)},
            indent=2,
        )
    )
    if errors:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
