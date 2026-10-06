#!/usr/bin/env python3
"""Local background removal (FREE — replaces credit-based remove_background).
  Tools/venv/bin/python Tools/sa_cutout.py photo.jpg            # -> photo_cutout.png
  Tools/venv/bin/python Tools/sa_cutout.py folder/              # every image in folder
First run downloads the model (~170MB) once, then works offline.
NOT for fine-jewellery hero shots — real-pixel workflow stays manual.
"""
import os, sys, glob

def cut(path, session):
    from rembg import remove
    from PIL import Image
    out = os.path.splitext(path)[0] + "_cutout.png"
    Image.open(path).convert("RGBA")  # validates file
    with open(path, "rb") as f:
        result = remove(f.read(), session=session)
    open(out, "wb").write(result)
    print(f"✓ {os.path.basename(out)}")
    return out

def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    from rembg import new_session
    session = new_session("isnet-general-use")  # best general model
    target = os.path.expanduser(sys.argv[1])
    if os.path.isdir(target):
        imgs = [f for e in ("*.png", "*.jpg", "*.jpeg", "*.webp")
                for f in glob.glob(os.path.join(target, e)) if "_cutout" not in f]
        for p in imgs: cut(p, session)
        print(f"{len(imgs)} image(s) done")
    else:
        cut(target, session)

if __name__ == "__main__":
    main()
