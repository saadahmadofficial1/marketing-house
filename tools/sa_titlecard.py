#!/usr/bin/env python3
"""Brand title-card PNG generator — the approved type-hierarchy rules baked in.
  python3 sa_titlecard.py "Expense Request System" "Quick & Easy"
  python3 sa_titlecard.py "Step 1:" "Log in to the portal" --step
  python3 sa_titlecard.py "Simple" "Fast" "Transparent" --benefits
Outputs 1920x1080 transparent PNG (overlay for CapCut) into ~/Desktop.
Rules enforced: title centred+large, subtitle below smaller/semibold, no bullets,
step label bold + rest semibold. Fonts: ClashDisplay (CapCut font dir).
"""
import os, sys
from PIL import Image, ImageDraw, ImageFont

FONTS = os.path.expanduser("~/Library/Containers/com.lemon.lvoverseas/Data/Library/Fonts/")
BOLD, SEMI = FONTS + "ClashDisplay-Bold.otf", FONTS + "ClashDisplay-Semibold.otf"
MED = FONTS + "ClashDisplay-Medium.otf"  # approved body weight (from a signed-off final)
W, H = 1920, 1080
WHITE = (255, 255, 255, 255)
SHADOW = (0, 0, 0, 92)

def draw_center(d, y, text, font):
    w = d.textlength(text, font=font)
    x = (W - w) / 2
    d.text((x + 4, y + 4), text, font=font, fill=SHADOW)   # soft shadow like the drafts
    d.text((x, y), text, font=font, fill=WHITE)
    return font.size

def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a for a in sys.argv[1:] if a.startswith("--")}
    if not args: sys.exit(__doc__)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    if "--benefits" in flags:                       # approved: ONE centred word per card, Medium — sync each to its VO beat
        f = ImageFont.truetype(MED, 76)
        for t in args:
            img2 = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            d2 = ImageDraw.Draw(img2)
            w = d2.textlength(t, font=f)
            d2.text(((W - w) / 2 + 4, H * 0.46 + 4), t, font=f, fill=SHADOW)
            d2.text(((W - w) / 2, H * 0.46), t, font=f, fill=WHITE)
            o = os.path.expanduser(f"~/Desktop/benefit_{t.replace(' ', '_')}.png")
            img2.save(o); print(f"✓ {o}")
        return
    elif "--step" in flags:                         # approved: TOP of frame, "Step N:" Bold + rest Medium
        fb, fm = ImageFont.truetype(BOLD, 72), ImageFont.truetype(MED, 72)
        label, rest = args[0], " " + " ".join(args[1:])
        w = d.textlength(label, font=fb) + d.textlength(rest, font=fm)
        x, y = (W - w) / 2, H * 0.08
        d.text((x + 4, y + 4), label, font=fb, fill=SHADOW); d.text((x, y), label, font=fb, fill=WHITE)
        x2 = x + d.textlength(label, font=fb)
        d.text((x2 + 4, y + 4), rest, font=fm, fill=SHADOW); d.text((x2, y), rest, font=fm, fill=WHITE)
        name = ("step_" + args[0] + "_" + "_".join(args[1:])[:20]).replace(":", "")
    else:                                           # title big centred + subtitle below smaller semibold
        title, sub = args[0], args[1] if len(args) > 1 else ""
        draw_center(d, H * 0.40, title, ImageFont.truetype(BOLD, 104))
        if sub:
            draw_center(d, H * 0.40 + 140, sub, ImageFont.truetype(SEMI, 56))
        name = "title_" + title[:24]
    out = os.path.expanduser(f"~/Desktop/{name.replace(' ', '_')}.png")
    img.save(out)
    print(f"✓ {out}")

if __name__ == "__main__":
    main()
