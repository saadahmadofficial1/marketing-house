#!/usr/bin/env python3
"""Remove burned-in captions from video frames, then restore for thumbnail use.

  python3 Tools/sa_decaption.py "folder"            # clean + restore -> folder/THUMBS/
  python3 Tools/sa_decaption.py "folder" --clean    # caption removal only

Detects house-style captions (pure-white fill + soft dark shadow) and inpaints them.
FACE GUARD: the mask can never reach above BAND_TOP of the frame, so faces are
untouched by construction. The restore pass is entirely non-generative (chroma
denoise + unsharp) — nothing re-draws the face, unlike an AI upscaler.

ponytail: deliberately NOT Real-ESRGAN. The bundled realesrgan-ncnn-vulkan
scrambles tiles on 4K input on this Mac (verified 7 Aug 2026, any -t value), and a
generative upscaler would shift the face anyway. If these ever need true upscaling,
fix the binary or use Topaz — don't quietly re-add ESRGAN here.
"""
import os, sys, glob
import cv2
import numpy as np
BAND_TOP = 0.55      # captions only ever live below this fraction of the height
TEXT_MIN = 250       # caption fill is pure white; footage tops out ~247
SHADOW_MAX = 190     # the soft drop-shadow around the glyphs
HALO = 24            # px around a glyph — covers the full soft shadow
# A real caption line is ~15k+ pure-white px at 4K; fabric and skin specular
# highlights in the same band only ever reach ~2.5k. 8k sits in the gap.
TEXT_FLOOR = 8000


def caption_mask(img):
    """Mask of caption glyphs + their shadow, confined to the lower band."""
    h, w = img.shape[:2]
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    band = np.zeros((h, w), np.uint8)
    band[int(h * BAND_TOP):] = 1

    text = ((g >= TEXT_MIN) & (band > 0)).astype(np.uint8)
    if text.sum() < TEXT_FLOOR * (h * w) / (2160 * 3840):   # no caption on this frame
        return None

    # The shadow is a soft gradient with no clean threshold against off-white fabric,
    # so take everything within HALO of a glyph instead of trying to threshold it.
    mask = cv2.dilate(text, np.ones((HALO * 2 + 1,) * 2, np.uint8))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((35, 35), np.uint8))
    mask *= band                               # ponytail: belt and braces on the face guard
    return mask * 255


def erase(img, mask):
    """Inpaint the masked text, then feather-blend so no ghost outline shows.

    The blend is throttled by how detailed the surrounding area is: over flat
    kandura it smooths fully, over hands or a watch it barely touches, otherwise
    it leaves an obvious blurred strip across the detail.
    """
    out = cv2.inpaint(img, mask, 15, cv2.INPAINT_TELEA)
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
    local_var = cv2.GaussianBlur(g * g, (0, 0), 25) - cv2.GaussianBlur(g, (0, 0), 25) ** 2
    detail = np.clip(np.sqrt(np.maximum(local_var, 0)) / 12.0, 0, 1)   # 0 flat … 1 busy

    core = cv2.erode(mask, np.ones((9, 9), np.uint8))
    alpha = cv2.GaussianBlur(core, (0, 0), 9).astype(np.float32) / 255.0
    alpha = (alpha * (1 - detail))[..., None]
    smooth = cv2.GaussianBlur(out, (0, 0), 6)
    return (out * (1 - alpha) + smooth * alpha).astype(np.uint8)


def restore(img):
    """Clean up video-compression mush and crisp the detail. Real pixels only.

    Chroma denoise kills the blotchy colour noise JPEG/H.264 leaves in skin and
    white fabric; the unsharp runs on luma alone so colour edges stay clean.
    """
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    a = cv2.bilateralFilter(a, 9, 30, 30)
    b = cv2.bilateralFilter(b, 9, 30, 30)
    blur = cv2.GaussianBlur(l, (0, 0), 2.5)
    l = cv2.addWeighted(l, 1.45, blur, -0.45, 0)
    return cv2.cvtColor(cv2.merge([l, a, b]), cv2.COLOR_LAB2BGR)


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    folder = os.path.expanduser(sys.argv[1].rstrip("/"))
    clean_only = "--clean" in sys.argv
    dest = os.path.join(folder, "THUMBS")
    os.makedirs(dest, exist_ok=True)

    files = sorted(f for e in ("*.jpg", "*.jpeg", "*.png")
                   for f in glob.glob(os.path.join(folder, e)))
    for p in files:
        name = os.path.basename(p)
        img = cv2.imread(p)
        m = caption_mask(img)
        if m is None:
            print(f"{name}: no caption", end="")
        else:
            img = erase(img, m)
            print(f"{name}: caption removed ({int((m > 0).sum() / 1000)}k px)", end="")
        if not clean_only:
            img = restore(img)
            print(" + restored", end="")
        print()
        out = os.path.join(dest, os.path.splitext(name)[0] + ".jpg")
        cv2.imwrite(out, img, [cv2.IMWRITE_JPEG_QUALITY, 97])
    print(f"\n→ {dest}")


def demo():
    """Self-check: the mask must never touch the top BAND_TOP of a frame."""
    img = np.full((1000, 500, 3), 200, np.uint8)
    cv2.putText(img, "CAPTION", (40, 800), cv2.FONT_HERSHEY_SIMPLEX, 2, (255, 255, 255), 8)
    cv2.putText(img, "CAPTION", (40, 200), cv2.FONT_HERSHEY_SIMPLEX, 2, (255, 255, 255), 8)
    m = caption_mask(img)
    assert m is not None, "should detect the lower caption"
    assert m[:550].sum() == 0, "face guard breached — mask reached the upper frame"
    assert m[550:].sum() > 0, "lower caption not masked"
    print("ok")


if __name__ == "__main__":
    demo() if "--demo" in sys.argv else main()
