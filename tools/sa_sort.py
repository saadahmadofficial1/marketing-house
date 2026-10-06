#!/usr/bin/env python3
"""Sort media into DEST/<Camera>/<YYYY-MM-DD>/ using embedded metadata.
  sa_sort.py <src> <dest>                # dry run -> sort_plan.txt
  sa_sort.py <src> <dest> --apply        # COPY (originals stay)
  sa_sort.py <src> <dest> --apply --move # MOVE (frees the source)

Camera + date read via mdls (built-in, no install). Serial via exiftool if present.
Collision-safe: same name+size at dest = skip; different size = suffixed.
"""
import os, sys, subprocess, shutil, datetime

MEDIA = {".mp4",".mov",".mxf",".avi",".jpg",".jpeg",".arw",".raw",".dng",".heic",".png",".mp3",".wav"}
MODEL = {"ILCE-7SM3":"A7SIII", "ILME-FX3":"FX3"}  # friendly names; others pass through

_BUNDLED = os.path.join(os.path.dirname(__file__), "external", "exiftool", "exiftool")
if shutil.which("exiftool"):
    EXIFTOOL = ["exiftool"]
elif os.path.exists(_BUNDLED):
    EXIFTOOL = ["/usr/bin/perl", _BUNDLED]   # ponytail: GitHub clone, runs on macOS system perl
else:
    EXIFTOOL = None
HAVE_EXIF = EXIFTOOL is not None

def _mdls(p, attr):
    try:
        out = subprocess.run(["mdls","-raw","-name",attr,p],
                             capture_output=True, text=True, timeout=20).stdout.strip()
        return "" if out in ("(null)","") else out
    except Exception: return ""

def _exif(p):
    # exiftool reads camera Model + body Serial from VIDEO too (mdls can't). One call.
    try:
        out = subprocess.run(EXIFTOOL+["-s3","-Model","-SerialNumber","-CreateDate",p],
                             capture_output=True, text=True, timeout=30).stdout.splitlines()
        out += ["",""]; return out[0].strip(), out[1].strip(), out[2].strip()
    except Exception: return "","",""

def cam_and_date(p):
    model = serial = d = ""
    if HAVE_EXIF:
        model, serial, d = _exif(p)
        d = d[:10].replace(":","-")           # exif date 2026:06:08 -> 2026-06-08
    cam = MODEL.get(model, model or "Unknown")
    if serial: cam = f"{cam}_{serial[-4:]}"   # split the two bodies cleanly
    if not d: d = _mdls(p, "kMDItemContentCreationDate")[:10]
    if not d: d = datetime.date.fromtimestamp(os.path.getmtime(p)).isoformat()
    return cam, d

def main():
    if len(sys.argv) < 3:
        sys.exit("usage: sa_sort.py <src> <dest> [--apply] [--move]")
    src, dest = sys.argv[1].rstrip("/"), sys.argv[2].rstrip("/")
    apply, move = "--apply" in sys.argv, "--move" in sys.argv
    plan = []
    for d,_,fs in os.walk(src):
        if "/.Trash" in d or "_DUPES_QUARANTINE" in d: continue
        for f in fs:
            if f.startswith(".") or os.path.splitext(f)[1].lower() not in MEDIA: continue
            p = os.path.join(d, f)
            try: size = os.path.getsize(p)
            except OSError: continue
            cam, day = cam_and_date(p)
            plan.append((p, os.path.join(dest, cam, day, f), size))

    rep = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "sort_plan.txt"))
    bycam = {}
    with open(rep, "w") as o:
        o.write(f"{len(plan)} files -> {dest}/<Camera>/<date>/\n\n")
        for s,dst,sz in plan:
            cam = dst.replace(dest+"/","").split("/")[0]
            bycam[cam] = bycam.get(cam,0)+1
            o.write(f"{s}\n  -> {dst}\n")
    print(f"{len(plan)} files. by camera: {bycam} -> {rep}")
    if not apply:
        print("dry run. review sort_plan.txt, then --apply (copy) or --apply --move"); return

    done = 0
    for s,dst,sz in plan:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if os.path.exists(dst):
            if os.path.getsize(dst)==sz: continue          # already there
            b,e = os.path.splitext(dst); dst = f"{b}_dup{e}" # diff content, keep both
        try:
            shutil.move(s,dst) if move else shutil.copy2(s,dst); done += 1
        except OSError as e: print("skip",s,e)
    print(f"{'moved' if move else 'copied'} {done} files -> {dest}")

if __name__ == "__main__":
    main()
