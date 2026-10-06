#!/usr/bin/env python3
"""
Take the grain out of a scanned archival photograph without inventing anything.

It was written for an old aerial photograph on a company history page. It is a
historical record, so the one thing that must not happen is an AI "enhance" pass hallucinating
buildings, windows or coastline that were never in the negative. Everything here is
non-generative: it removes noise that is already there and adds nothing.

Non-local means rather than a blur or a median. It denoises each patch using other
patches in the image that look like it, so repeated structure - rooflines, window
grids, road edges - is averaged with its own kind and survives, while grain, which
matches nothing, averages away. A gaussian blur would take the grain and the city
detail together.

The light unsharp afterwards restores micro-contrast that denoising costs. It is
deliberately small: push it and a cleaned scan turns crunchy, which reads as fake
faster than the grain did.

    sa_archive_clean.py in.png out.png [--strength 8] [--sharpen 0.35]
    sa_archive_clean.py --demo
"""
import sys
import numpy as np
import cv2
from PIL import Image


def noise_sigma(gray):
    """Robust noise estimate: MAD of the Laplacian, which ignores real edges."""
    lap = cv2.Laplacian(gray.astype(np.float32), cv2.CV_32F)
    return float(np.median(np.abs(lap - np.median(lap))) / 0.6745 / np.sqrt(20))


def edge_energy(gray):
    """How much genuine structure is present - should barely move when denoising."""
    gx = cv2.Sobel(gray.astype(np.float32), cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray.astype(np.float32), cv2.CV_32F, 0, 1, ksize=3)
    m = np.hypot(gx, gy)
    return float(np.percentile(m, 99))          # the strongest edges, not the average


def clean(im, strength=8, sharpen=0.35):
    a = np.asarray(im.convert("RGB"))
    den = cv2.fastNlMeansDenoisingColored(a, None, strength, strength, 7, 21)
    if sharpen:
        blur = cv2.GaussianBlur(den, (0, 0), 1.6)
        den = cv2.addWeighted(den, 1 + sharpen, blur, -sharpen, 0)
    return Image.fromarray(den)


def demo():
    rng = np.random.default_rng(0)
    # a picture with real structure: hard edges plus a smooth ramp
    base = np.zeros((300, 300), np.float32)
    base[:, 150:] = 200
    base[120:180, :] = 90
    base += np.linspace(0, 40, 300, dtype=np.float32)[None, :]
    clean_img = Image.fromarray(np.dstack([np.clip(base, 0, 255).astype(np.uint8)] * 3))
    noisy = np.clip(base + rng.normal(0, 12, base.shape), 0, 255).astype(np.uint8)
    noisy_img = Image.fromarray(np.dstack([noisy] * 3))

    g0 = np.asarray(noisy_img.convert("L"))
    out = clean(noisy_img, strength=10, sharpen=0.0)
    g1 = np.asarray(out.convert("L"))

    assert noise_sigma(g1) < noise_sigma(g0) * 0.6, \
        f"noise must drop substantially ({noise_sigma(g0):.2f} -> {noise_sigma(g1):.2f})"
    e0, e1 = edge_energy(np.asarray(clean_img.convert("L"))), edge_energy(g1)
    assert e1 > e0 * 0.7, f"the real edges must survive ({e0:.0f} -> {e1:.0f})"
    # and nothing may be invented: the denoised result must stay close to the truth
    err = np.abs(g1.astype(float) - np.asarray(clean_img.convert("L"), float)).mean()
    assert err < 6, f"the result must stay faithful to the original ({err:.2f}/255)"
    print("demo ok")


if __name__ == "__main__":
    if "--demo" in sys.argv:
        demo(); sys.exit(0)
    g = lambda f, d: float(sys.argv[sys.argv.index(f) + 1]) if f in sys.argv else d
    im = Image.open(sys.argv[1])
    g0 = np.asarray(im.convert("L"))
    out = clean(im, int(g("--strength", 8)), g("--sharpen", 0.35))
    g1 = np.asarray(out.convert("L"))
    out.save(sys.argv[2])
    print(f"  noise  {noise_sigma(g0):.2f} -> {noise_sigma(g1):.2f}   "
          f"edges {edge_energy(g0):.0f} -> {edge_energy(g1):.0f}   -> {sys.argv[2]}")
