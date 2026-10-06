#!/usr/bin/env python3
"""Local upscaler (FREE — replaces credit-based upscale_image). Real-ESRGAN on-device.
  python3 Tools/sa_upscale.py image.png            # 4x -> image_4x.png
  python3 Tools/sa_upscale.py image.png --2x       # 2x
  python3 Tools/sa_upscale.py folder/              # batch
GUARDRAIL: refuses jewellery / fine-product files — any path containing a word listed in
SA_UPSCALE_PROTECT (default "jewellery,jewelry"). Real-pixel workflow only, never AI on stones.
"""
import os, sys, glob, subprocess

_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "external", "realesrgan")
BIN = os.path.join(_DIR, "realesrgan-ncnn-vulkan")
MODELS = os.path.join(_DIR, "models")   # binary looks for ./models unless told
PROTECT = [w.strip().lower() for w in os.environ.get("SA_UPSCALE_PROTECT", "jewellery,jewelry").split(",") if w.strip()]

def up(path, scale):
    if any(w in path.lower() for w in PROTECT):
        print(f"⛔ SKIPPED (protected fine product = never AI): {os.path.basename(path)}")
        return
    out = os.path.splitext(path)[0] + f"_{scale}x.png"
    r = subprocess.run([BIN, "-i", path, "-o", out, "-s", str(scale),
                        "-n", "realesrgan-x4plus", "-m", MODELS],
                       capture_output=True, text=True)
    print(("✓ " + os.path.basename(out)) if os.path.exists(out) else f"✗ {path}: {r.stderr.strip()[-120:]}")

def main():
    if len(sys.argv) < 2: sys.exit(__doc__)
    scale = 2 if "--2x" in sys.argv else 4
    t = os.path.expanduser(sys.argv[1])
    files = ([f for e in ("*.png","*.jpg","*.jpeg","*.webp") for f in glob.glob(os.path.join(t, e))
              if "_2x" not in f and "_4x" not in f] if os.path.isdir(t) else [t])
    for f in files: up(f, scale)

if __name__ == "__main__":
    main()
