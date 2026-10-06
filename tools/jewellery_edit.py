#!/usr/bin/env python3
"""Jewellery product edit — bright, clear, TRUE colour, no filter, jewellery unchanged.
RAW (.ARW) decoded with CAMERA white balance = colour exactly as shot.
Adjustments: gentle brightness/shadow lift + clarity + chroma denoise + sharpen.
NO saturation boost, NO vibrance, NO hue shift, NO LUT/filter -> jewellery never recoloured.

  jewellery_edit.py sheet                 # contact sheet of ALL + rank csv (from JPGs, fast)
  jewellery_edit.py preview DSC01234      # before/after of one (RAW)
  jewellery_edit.py batch                 # edit all sharp shots in range
  jewellery_edit.py batch DSC01234 ...    # edit a specific list
"""
import os, sys, glob, csv
import numpy as np
from PIL import Image, ImageOps, ImageFilter, ImageDraw, ImageFont
import rawpy

SRC = os.path.expanduser(os.environ.get("JEWEL_SRC", "~/Downloads/IMAGES"))
OUT = os.path.join(SRC, "Edited")
LO, HI = 1, 9999                         # inclusive DSC frame range to process (narrow per shoot)
SHARP_MIN = 12.0                         # blur cutoff (FIND_EDGES variance on JPG preview)

def in_range(name):
    try: n = int(name.replace("DSC","").split(".")[0])
    except: return False
    return LO-2 <= n <= HI+2             # small margin so nothing is missed

def arw(name): return os.path.join(SRC, name+".ARW")
def jpg(name): return os.path.join(SRC, name+".JPG")

def names():
    out=[]
    for f in sorted(glob.glob(os.path.join(SRC,"DSC*.ARW"))):
        nm=os.path.splitext(os.path.basename(f))[0]
        if in_range(nm): out.append(nm)
    return out

# ---------- editing ----------
def decode_raw(name):
    with rawpy.imread(arw(name)) as r:
        rgb = r.postprocess(use_camera_wb=True,      # TRUE colour as shot
                            no_auto_bright=False,     # good base exposure
                            bright=1.0,
                            output_bps=8,
                            gamma=(2.222,4.5),
                            highlight_mode=rawpy.HighlightMode.Clip)
    return Image.fromarray(rgb)

def edit(im):
    a = np.asarray(im).astype(np.float32)
    # 1. DEHAZE — restore deep black point (kills milky haze; the house look = deep blacks)
    luma = 0.299*a[...,0]+0.587*a[...,1]+0.114*a[...,2]
    blk = np.percentile(luma, 0.8)
    a = (a - blk) * (255.0/(255.0-blk)); a = np.clip(a,0,255)
    # 2. brightness — gamma to open midtones (bright, controlled, NOT washed)
    m = (0.299*a[...,0]+0.587*a[...,1]+0.114*a[...,2]).mean()/255.0
    m = min(max(m,0.05),0.95)
    g = np.log(0.55)/np.log(m); g = min(max(g,0.6),1.0)    # brighten only, keep contrast
    a = 255.0*np.power(a/255.0, g)
    # 3. highlight protection (soft knee) so spotlights/whites don't blow
    a2 = a/255.0; a2 = np.where(a2>0.85, 0.85+(a2-0.85)*0.6, a2); a = a2*255.0
    im = Image.fromarray(np.clip(a,0,255).astype(np.uint8))
    # 4. chroma denoise (clean) — light radius so detail stays crisp, no colour shift
    y,cb,cr = im.convert("YCbCr").split()
    cb=cb.filter(ImageFilter.MedianFilter(3)); cr=cr.filter(ImageFilter.MedianFilter(3))
    im = Image.merge("YCbCr",(y,cb,cr)).convert("RGB")
    # 5. clarity (local-contrast punch) + crisp fine-detail sharpen on the jewellery
    im = im.filter(ImageFilter.UnsharpMask(radius=40,  percent=18,  threshold=3))
    im = im.filter(ImageFilter.UnsharpMask(radius=1.2, percent=135, threshold=2))
    return im

def do_edit(name):
    return edit(decode_raw(name))

# ---------- selection / sheet ----------
def score_jpg(name):
    im = ImageOps.exif_transpose(Image.open(jpg(name))).convert("RGB")
    s=im.copy(); s.thumbnail((900,900))
    L=np.asarray(s.convert("L").filter(ImageFilter.FIND_EDGES),dtype=np.float32)
    sharp=float(L.var())
    lu=np.asarray(s.convert("L"),dtype=np.float32)/255.0
    expo=1-abs(lu.mean()-0.5)
    return sharp, expo

def sheet():
    ns=names(); rows=[]
    for nm in ns:
        sh,ex=score_jpg(nm); rows.append((nm,sh,ex))
    rows.sort(key=lambda r:-r[1])
    with open(os.path.join(SRC,"rank.csv"),"w") as f:
        f.write("file,sharpness,exposure,pick\n")
        for nm,sh,ex in rows:
            f.write(f"{nm},{sh:.1f},{ex:.2f},{'Y' if sh>=SHARP_MIN else ''}\n")
    # contact sheet (all), green box = pick
    COLS=6; TH=300; pad=6; lbl=22
    sample=ImageOps.exif_transpose(Image.open(jpg(rows[0][0]))).convert("RGB")
    ar=sample.height/sample.width; th=int(TH*ar)
    R=(len(rows)+COLS-1)//COLS; cw=TH+pad; ch=th+lbl+pad
    sheet=Image.new("RGB",(COLS*cw+pad,R*ch+pad),(20,20,22)); d=ImageDraw.Draw(sheet)
    try: font=ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf",13)
    except: font=ImageFont.load_default()
    for i,(nm,sh,ex) in enumerate(rows):
        r,c=divmod(i,COLS); x=pad+c*cw; y=pad+r*ch
        im=ImageOps.exif_transpose(Image.open(jpg(nm))).convert("RGB"); im.thumbnail((TH,th))
        sheet.paste(im,(x,y+lbl))
        pick = sh>=SHARP_MIN
        d.rectangle([x,y,x+TH,y+lbl],fill=(0,120,60) if pick else (0,0,0))
        d.text((x+4,y+3),f"{nm.replace('DSC0','')}  s{sh:.0f} {'PICK' if pick else 'soft'}",
               fill=(255,255,255),font=font)
    p=os.path.join(SRC,"_contact_ALL.jpg"); sheet.save(p,quality=88)
    picks=[r[0] for r in rows if r[1]>=SHARP_MIN]
    print(f"{len(rows)} shots ranked. {len(picks)} picks (sharp). sheet -> {p}\nrank.csv written.")
    return picks

def preview(name):
    before=decode_raw(name); after=do_edit(name)
    w=820; rs=lambda i:i.resize((w,int(w*i.height/i.width)))
    b,a=rs(before),rs(after)
    sh=Image.new("RGB",(w,b.height+a.height+6),(0,0,0))
    sh.paste(b,(0,0)); sh.paste(a,(0,b.height+6))
    p=f"/tmp/jewel_ba_{name}.jpg"; sh.save(p,quality=92)
    print(f"before/after -> {p}")

def batch(lst):
    os.makedirs(OUT,exist_ok=True)
    if not lst:
        sh,_=0,0
        lst=[nm for nm in names() if score_jpg(nm)[0]>=SHARP_MIN]
    n=0
    for nm in lst:
        if not os.path.exists(arw(nm)): print("skip (no ARW):",nm); continue
        out=os.path.join(OUT, nm+"_EDIT.jpg")
        do_edit(nm).save(out,quality=96,subsampling=0)
        n+=1; print(f"  {nm} -> {os.path.basename(out)}")
    print(f"edited {n} -> {OUT}")

def main():
    if len(sys.argv)<2: print(__doc__); return
    cmd=sys.argv[1]
    if cmd=="sheet": sheet()
    elif cmd=="preview": preview(sys.argv[2])
    elif cmd=="batch": batch(sys.argv[2:])
    else: print(__doc__)

if __name__=="__main__":
    main()
