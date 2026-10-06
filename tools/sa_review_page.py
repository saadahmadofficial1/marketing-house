#!/usr/bin/env python3
"""
Build the one file a reviewer opens to judge a website's sector cards: before, after, and the
crop the site actually shows.

Everything is embedded as base64 so the page works from Downloads with no server
and no network — it opens on any machine, including one that has never seen
this repo.

The middle column is the important one. Live cards are often NOT 16:9: a site
crops them to the card's own shape with object-fit, so a picture can be approved flat and
still lose its subject on the page. This shows the crop, not the file.

    python3 sa_review_page.py

Folders and the output file are environment variables, so nothing project-specific lives
in the source: REVIEW_NEW_DIR / REVIEW_OLD_DIR (the cards, new and live), REVIEW_STRIP_NEW_DIR /
REVIEW_STRIP_OLD_DIR (a secondary image strip), REVIEW_OUT (the page). Edit ORDER and
CAPABILITY below to name your own cards.
"""
import base64, io, os, pathlib
from PIL import Image

NEW = pathlib.Path(os.environ.get("REVIEW_NEW_DIR", "images/new/cards")).expanduser()
OLD = pathlib.Path(os.environ.get("REVIEW_OLD_DIR", "images/live/cards")).expanduser()
CAP_NEW = pathlib.Path(os.environ.get("REVIEW_STRIP_NEW_DIR", "images/new/strip")).expanduser()
CAP_OLD = pathlib.Path(os.environ.get("REVIEW_STRIP_OLD_DIR", "images/live/strip")).expanduser()

# A secondary image strip. Its own component, its own language, so the sector cards'
# tone matching never touches it.
# (file, title, what changed) - example entries; list your own.
CAPABILITY = [
    ("strip-1.jpg", "Capability one",   "what changed, in one line"),
    ("strip-2.jpg", "Capability two",   "what changed, in one line"),
    ("strip-3.jpg", "Capability three", "what changed, in one line"),
    ("strip-4.jpg", "Capability four",  "what changed, in one line"),
]
OUT = pathlib.Path(os.environ.get("REVIEW_OUT", "sector-images-review.html")).expanduser()

# The card's REAL rendered size on your page, measured in the browser: REVIEW_CARD_PX="W,H".
# Judging a card at any other size is how text inside a picture ends up sliced in half.
CARD_PX = tuple(int(v) for v in os.environ.get("REVIEW_CARD_PX", "240,200").split(","))
CARD_RATIO = round(CARD_PX[0] / CARD_PX[1], 3)   # the shape object-fit: cover crops to
# (file stem, card title, what changed and why) - example entries; list your own cards.
ORDER = [
    ("sector-1", "Sector one",   "two approved references combined into one frame."),
    ("sector-2", "Sector two",   "approved — one of the two references the rest of the set is matched to."),
    ("sector-3", "Sector three", "was a city aerial that did not show the sector at all; now a subject-led frame."),
    ("sector-4", "Sector four",  "approved — the other reference."),
]


def b64(im, w):
    im = im.resize((w, round(w * im.height / im.width)), Image.LANCZOS)
    buf = io.BytesIO(); im.convert("RGB").save(buf, "JPEG", quality=84, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def true_size(im):
    """The card at the exact pixel size a visitor gets, magnified with NO new detail.

    This is the only view that answers "can anyone actually read that?".
    """
    c = card_crop(im).resize(CARD_PX, Image.LANCZOS)
    return c.resize((CARD_PX[0] * 3, CARD_PX[1] * 3), Image.NEAREST)


def card_crop(im):
    """What object-fit: cover actually puts on screen."""
    w, h = im.size
    nw = round(h * CARD_RATIO)
    if nw <= w:
        return im.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
    nh = round(w / CARD_RATIO)
    return im.crop((0, (h - nh) // 2, w, (h - nh) // 2 + nh))


rows = []
for key, title, note in ORDER:
    new = Image.open(NEW / f"{key}.jpg").convert("RGB")
    old_p = OLD / f"{key}.jpg"
    old = Image.open(old_p).convert("RGB") if old_p.exists() else None
    rows.append(f"""
    <section>
      <h2>{title}</h2>
      <p class="note">{note}</p>
      <div class="grid">
        <figure><img src="{b64(old, 560) if old else ''}" alt=""><figcaption>live site today</figcaption></figure>
        <figure><img src="{b64(new, 560)}" alt=""><figcaption>new file, full frame</figcaption></figure>
        <figure class="crop"><img src="{b64(card_crop(new), 560)}" alt=""><figcaption>what the card shows ({CARD_RATIO}:1 crop)</figcaption></figure>
        <figure class="real"><img src="{b64(true_size(new), 560)}" alt=""><figcaption>at its real size on the page — {CARD_PX[0]}&times;{CARD_PX[1]} px, magnified, no detail added</figcaption></figure>
      </div>
    </section>""")

cap_rows = []
for fn, title, note in CAPABILITY:
    n = Image.open(CAP_NEW / fn).convert("RGB")
    o_p = CAP_OLD / fn
    o = Image.open(o_p).convert("RGB") if o_p.exists() else None
    cap_rows.append(f"""
      <figure><img src="{b64(o, 300) if o else ''}" alt=""><figcaption>{title} &mdash; before</figcaption></figure>
      <figure class="crop"><img src="{b64(n, 300)}" alt=""><figcaption>{title} &mdash; now</figcaption></figure>""")

cap_html = f"""
<section>
  <h2>Capability strip</h2>
  <p class="note">Replaced together as one set, so light and tone match across the strip.
  The strip keeps its own look &mdash; the sector cards' tone matching never touches it.
  Each pair is before on the left, now on the right.</p>
  <div class="grid cap">{''.join(cap_rows)}</div>
</section>"""

html = f"""<!doctype html><meta charset="utf-8">
<title>Sector card images — review</title>
<style>
 :root {{ color-scheme: light }}
 body {{ margin:0; padding:40px 24px 80px; background:#fafaf8; color:#1b1b19;
        font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif; }}
 .wrap {{ max-width:1180px; margin:0 auto }}
 h1 {{ font-size:30px; font-weight:600; letter-spacing:-.02em; margin:0 0 6px }}
 .sub {{ color:#6a6a63; margin:0 0 40px; max-width:62ch }}
 section {{ margin:0 0 46px; padding:0 0 34px; border-bottom:1px solid #e6e5df }}
 section:last-of-type {{ border:0 }}
 h2 {{ font-size:19px; font-weight:600; margin:0 0 4px }}
 .note {{ color:#6a6a63; margin:0 0 16px; max-width:80ch }}
 .grid {{ display:grid; grid-template-columns:repeat(4,1fr); gap:14px }}
 @media (max-width:1180px) {{ .grid {{ grid-template-columns:repeat(2,1fr) }} }}
 @media (max-width:820px) {{ .grid {{ grid-template-columns:1fr }} }}
 figure {{ margin:0 }}
 img {{ width:100%; display:block; border-radius:6px; background:#eee }}
 figcaption {{ font-size:12px; color:#8a8a82; margin-top:7px }}
 .crop figcaption {{ color:#1b1b19; font-weight:600 }}
 .real figcaption {{ color:#8a1f1f; font-weight:600 }}
 .real img {{ image-rendering:pixelated }}
 .cap {{ grid-template-columns:repeat(4,1fr) }}
 @media (max-width:1180px) {{ .cap {{ grid-template-columns:repeat(2,1fr) }} }}
 footer {{ color:#8a8a82; font-size:13px; margin-top:20px; max-width:72ch }}
</style>
<div class="wrap">
<h1>Sector card images</h1>
<p class="sub">Every card its own kind of picture, one light. The last column is the one
that matters: the card at the size a visitor really sees it, {CARD_PX[0]}&times;{CARD_PX[1]} px. If something
cannot be read there, it cannot be read.</p>
{''.join(rows)}
{cap_html}
<footer>Ungraded on purpose — the masters are yours to grade with your approved .xmp preset.
Full-size masters: <code>~/Downloads/WEBSITE/&lt;BRAND&gt;/</code>.</footer>
</div>"""

OUT.write_text(html)
print(f"  {OUT}  {OUT.stat().st_size/1e6:.1f} MB")
