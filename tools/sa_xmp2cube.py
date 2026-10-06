#!/usr/bin/env python3
"""Approximate a Lightroom/ACR .xmp preset as a .cube LUT for CapCut/Premiere/DaVinci.
  sa_xmp2cube.py <preset.xmp> [out.cube] [--size 33]

LUTs are per-pixel colour/tone only — sharpening, noise reduction and true RAW
white balance can't be baked. This reproduces the LOOK: exposure, contrast,
blacks/whites/highlights/shadows, vibrance, saturation, blue hue/sat, mild WB.
ponytail: approximation for creative grading, not a colour-managed match.
"""
import sys, re, colorsys

def getf(t, key, d=0.0):
    m = re.search(rf'crs:{key}="([+-]?[0-9.]+)"', t)
    return float(m.group(1)) if m else d

def smooth_bump(x, c, w):  # gaussian-ish weight around luma c
    return 2.71828 ** (-((x-c)**2)/(2*w*w))

def build(xmp, size=33):
    t = open(xmp).read()
    expo = getf(t,"Exposure2012"); con = getf(t,"Contrast2012")/100.0
    hi = getf(t,"Highlights2012")/100.0; sh = getf(t,"Shadows2012")/100.0
    wh = getf(t,"Whites2012")/100.0; bl = getf(t,"Blacks2012")/100.0
    vib = getf(t,"Vibrance")/100.0; sat = getf(t,"Saturation")/100.0
    temp = getf(t,"Temperature",6500); tint = getf(t,"Tint")
    bhue = getf(t,"HueAdjustmentBlue")/100.0; bsat = getf(t,"SaturationAdjustmentBlue")/100.0
    asshot = getf(t,"AsShotTemperature",temp)
    # WB delta (mild): warmer if preset temp > as-shot
    warm = max(min((temp-asshot)/4000.0, 0.15), -0.15)
    rg, bg = 1+warm, 1-warm
    gg = 1 - tint/100.0*0.15

    def tone(v):
        v = v * (2**expo)                          # exposure
        v = (v-0.5)*(1+con*0.9)+0.5                # contrast around mid
        v += sh*0.28*smooth_bump(v,0.30,0.22)      # shadows
        v += hi*0.28*smooth_bump(v,0.72,0.20)      # highlights
        v += bl*0.22*smooth_bump(v,0.10,0.12)      # blacks (neg=deeper)
        v += wh*0.20*smooth_bump(v,0.92,0.12)      # whites
        return min(max(v,0.0),1.0)

    lines = ["TITLE \"%s\"" % xmp.split("/")[-1], "LUT_3D_SIZE %d" % size, ""]
    N = size-1
    for b in range(size):
        for g in range(size):
            for r in range(size):
                R,G,B = r/N, g/N, b/N
                R*=rg; G*=gg; B*=bg                # WB
                R,G,B = tone(R),tone(G),tone(B)
                h,s,v = colorsys.rgb_to_hsv(R,G,B)
                s *= (1+sat)                       # global saturation
                s *= (1+vib*(1-s)*0.9)             # vibrance (protect saturated)
                hd = (h*360)
                if 195 <= hd <= 265:               # blue range
                    hd += bhue*12; s *= (1+bsat)
                R,G,B = colorsys.hsv_to_rgb((hd%360)/360, min(s,1), v)
                lines.append("%.5f %.5f %.5f" % (min(R,1),min(G,1),min(B,1)))
    return "\n".join(lines)+"\n"

def main():
    if len(sys.argv)<2: sys.exit("usage: sa_xmp2cube.py <preset.xmp> [out.cube] [--size N]")
    xmp = sys.argv[1]
    out = sys.argv[2] if len(sys.argv)>2 and not sys.argv[2].startswith("--") \
          else xmp.rsplit(".",1)[0]+".cube"
    size = int(sys.argv[sys.argv.index("--size")+1]) if "--size" in sys.argv else 33
    open(out,"w").write(build(xmp,size))
    print("wrote",out,f"({size}^3 LUT)")

if __name__=="__main__":
    main()
