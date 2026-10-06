#!/usr/bin/env python3
"""media_kit — reusable glue for common image/video chores.
Stops me re-writing the same Python every project (token saver).

The Image/video GENERATION calls go through MCP (generate_image / generate_video /
job_display) — those can't be scripted. Everything AROUND them is repetitive and
lives here. Call these instead of hand-rolling.

  from media_kit import *

  put(local, presigned_url)                     # upload one file to a presigned URL
  put_many({local: url, ...})                   # parallel upload (returns {file:code})
  grab(cdn_url, out_path)                        # download one result
  grab_many({url: out_path, ...})               # parallel download
  sheet(folder, out, cols=4, label=True)        # labelled contact sheet of a folder
  crop_grid(src, out, x0,y0,x1,y1)              # fractional crop (0..1) e.g. storyboard panel
  probe(path)                                    # ffprobe-lite: dur/res/fps of a video

CLI:
  media_kit.py sheet <folder> [out.jpg] [cols]
  media_kit.py probe <video.mp4>
"""
import os, sys, subprocess, concurrent.futures as cf

FFMPEG = __import__("shutil").which("ffmpeg") or os.path.expanduser("~/.local/bin/ffmpeg")

# ---------- upload ----------
def put(local, url):
    ct = "image/png" if local.lower().endswith(".png") else \
         "image/jpeg" if local.lower().endswith((".jpg", ".jpeg")) else \
         "video/mp4" if local.lower().endswith(".mp4") else "application/octet-stream"
    r = subprocess.run(["curl", "-s", "-X", "PUT", "-H", f"Content-Type: {ct}",
                        "--data-binary", f"@{local}", url, "-w", "%{http_code}"],
                       capture_output=True, text=True)
    return r.stdout.strip()[-3:]

def put_many(mapping):
    out = {}
    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        fut = {ex.submit(put, f, u): f for f, u in mapping.items()}
        for x in cf.as_completed(fut):
            out[fut[x]] = x.result()
    return out

# ---------- download ----------
def grab(url, out_path):
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    subprocess.run(["curl", "-sL", url, "-o", out_path], check=True)
    return out_path

def grab_many(mapping):
    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        list(ex.map(lambda kv: grab(*kv), mapping.items()))
    return list(mapping.values())

# ---------- contact sheet ----------
def sheet(folder, out=None, cols=4, label=True, thumb=380):
    from PIL import Image, ImageDraw, ImageFont
    exts = (".png", ".jpg", ".jpeg", ".webp")
    files = sorted(f for f in os.listdir(folder)
                   if f.lower().endswith(exts) and not f.startswith("_"))
    if not files:
        print("no images in", folder); return None
    out = out or os.path.join(folder, "_CONTACT_SHEET.jpg")
    s0 = Image.open(os.path.join(folder, files[0]))
    ar = s0.height / s0.width; th = int(thumb * ar)
    pad, lbl = 12, (40 if label else 0)
    rows = (len(files) + cols - 1) // cols
    cw, ch = thumb + pad, th + lbl + pad
    sh = Image.new("RGB", (cols * cw + pad, rows * ch + pad), (8, 12, 11))
    d = ImageDraw.Draw(sh)
    try: font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 18)
    except: font = ImageFont.load_default()
    for i, f in enumerate(files):
        r, c = divmod(i, cols); x, y = pad + c * cw, pad + r * ch
        im = Image.open(os.path.join(folder, f)).convert("RGB"); im.thumbnail((thumb, th))
        if label:
            d.rectangle([x, y, x + thumb, y + lbl], fill=(27, 58, 75))
            d.text((x + 8, y + 10), os.path.splitext(f)[0][:34], fill=(255, 255, 255), font=font)
        sh.paste(im, (x, y + lbl))
    sh.save(out, quality=92)
    print(f"sheet -> {out}  ({len(files)} imgs)")
    return out

# ---------- fractional crop (storyboard panels etc.) ----------
def crop_grid(src, out, x0, y0, x1, y1):
    from PIL import Image
    im = Image.open(src); w, h = im.size
    im.crop((int(w*x0), int(h*y0), int(w*x1), int(h*y1))).save(out, quality=94)
    return out

# ---------- video probe ----------
def probe(path):
    r = subprocess.run([FFMPEG, "-hide_banner", "-i", path],
                       capture_output=True, text=True)
    for line in r.stderr.splitlines():
        if "Duration" in line or "Stream" in line:
            print(line.strip())

def main():
    if len(sys.argv) < 2: print(__doc__); return
    cmd = sys.argv[1]
    if cmd == "sheet":
        sheet(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None,
              int(sys.argv[4]) if len(sys.argv) > 4 else 4)
    elif cmd == "probe":
        probe(sys.argv[2])
    else:
        print(__doc__)

if __name__ == "__main__":
    main()
