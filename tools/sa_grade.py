#!/usr/bin/env python3
"""House grade — apply a real .cube LUT to image or video via ffmpeg.
Local, exact, repeatable. The house look, not an approximation.

  sa_grade.py <input> <lut> [--strength 0.8] [--out PATH]

<lut> = an alias for a LUT you keep in luts/ next to this script, or a full .cube path:
  outdoor  -> outdoor.cube   (general outdoor)
  core     -> core.cube      (indoor master / corporate)
  green    -> green.cube     (green-tone indoor)
  events   -> events.cube    (events, blue)
  warm     -> warm.cube      (warm yellow, product)
--strength blends LUT with original (1.0 = full, 0.8 = subtle: the dialled-back look reviewers preferred).
"""
import sys, os, shutil, subprocess
FFMPEG = os.environ.get("FFMPEG") or shutil.which("ffmpeg") or "ffmpeg"
LUTDIR = os.path.join(os.path.dirname(__file__), "luts")
ALIAS = {"outdoor": "outdoor.cube", "core": "core.cube", "green": "green.cube",
         "events": "events.cube", "warm": "warm.cube"}
VID = (".mp4",".mov",".mkv",".webm",".m4v")

def resolve_lut(name):
    if os.path.isfile(name): return name
    if name.lower() in ALIAS: return os.path.join(LUTDIR, ALIAS[name.lower()])
    p = os.path.join(LUTDIR, name if name.endswith(".cube") else name+".cube")
    if os.path.isfile(p): return p
    sys.exit(f"LUT not found: {name}. Options: {', '.join(ALIAS)}")

def main():
    if len(sys.argv) < 3: print(__doc__); sys.exit(1)
    inp = os.path.expanduser(sys.argv[1]); lut = resolve_lut(sys.argv[2])
    strength = 1.0
    if "--strength" in sys.argv: strength = float(sys.argv[sys.argv.index("--strength")+1])
    if "--out" in sys.argv: out = os.path.expanduser(sys.argv[sys.argv.index("--out")+1])
    else:
        b,e = os.path.splitext(inp); out = f"{b}_graded{e}"
    # escape colon/space in lut path for ffmpeg filter
    lp = lut.replace("\\","/").replace(":","\\:").replace(" ","\\ ")
    if strength >= 0.999:
        vf = f"lut3d='{lp}'"
    else:
        vf = (f"split[a][b];[b]lut3d='{lp}'[g];"
              f"[a][g]blend=all_mode=normal:all_opacity={strength}")
    is_vid = inp.lower().endswith(VID)
    cmd = [FFMPEG,"-y","-i",inp,"-vf",vf]
    if is_vid: cmd += ["-c:a","copy","-c:v","libx264","-crf","17","-preset","slow"]
    cmd += [out]
    print(f"grading {os.path.basename(inp)}  LUT={os.path.basename(lut)}  strength={strength}")
    subprocess.run(cmd, check=True)
    print(f"-> {out}")

if __name__ == "__main__":
    main()
