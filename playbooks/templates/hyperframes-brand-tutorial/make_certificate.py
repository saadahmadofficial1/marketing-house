#!/usr/bin/env python3
"""A completion certificate in the brand's own type and colours, from brand.json.

    python3 make_certificate.py brand.example.json --course "Brewing basics" --modules 1 \
        --out build/certificate.html                      # blank template with {{placeholders}}
    python3 make_certificate.py brand.example.json --course "Brewing basics" --modules 1 \
        --name "Sam Example" --date "1 March" --learner-id "A-0001" --out build/sam.html --pdf

The blank keeps {{learner_name}}, {{completion_date}} and {{learner_id}} for a learning
platform or a mail merge to fill. --pdf prints A4 landscape through headless Chrome.
For a PNG, render TALLER than the page and crop from the top: headless Chrome's
--window-size gives a viewport shorter than the window, and a centre crop (as some image
tools do by default) cuts the top of the sheet.

The certificate states only what the course really checked: completion of the modules and
their knowledge checks, with no claims it cannot back.
"""
import argparse
import html
import json
import os
import pathlib
import shutil
import subprocess

TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<title>Certificate of completion</title>
<style>
{faces}
:root {{ --deep:{deep}; --accent:{accent}; --ink:{ink}; --paper:{paper}; --mist:{mist}; }}
@page {{ size: 297mm 210mm; margin: 0; }}
* {{ margin:0; padding:0; box-sizing:border-box; }}
/* A4 landscape at 150 dpi: 1754 x 1240 css px */
html, body {{ width:1754px; height:1240px; background:var(--paper); color:var(--ink);
  font-family:"{text}", {fallback}; font-synthesis:none; }}
.sheet {{ position:relative; width:1754px; height:1240px; overflow:hidden; }}
.band {{ position:absolute; left:0; top:0; bottom:0; width:300px; background:var(--deep); overflow:hidden; }}
.band::before {{ content:""; position:absolute; inset:-200px;
  background:repeating-linear-gradient({angle}deg, transparent 0 22px, var(--accent) 22px 26px); opacity:.45; }}
.band::after {{ content:""; position:absolute; top:0; bottom:0; right:0; width:10px; background:var(--accent); }}
.mark {{ position:absolute; top:84px; right:110px; font-family:"{display}", {fallback}; font-weight:700; font-size:40px; color:var(--deep); }}
.body {{ position:absolute; left:420px; right:130px; top:150px; }}
.kicker {{ font-weight:500; font-size:28px; letter-spacing:.14em; text-transform:uppercase; color:var(--accent); }}
h1 {{ font-family:"{display}", {fallback}; font-weight:700; font-size:104px; line-height:1.0; letter-spacing:-.02em; margin-top:22px; color:var(--deep); }}
.rule {{ width:200px; height:6px; background:var(--accent); border-radius:3px; margin:46px 0 44px; }}
.lead {{ font-weight:400; font-size:34px; color:var(--mist); }}
.name {{ font-family:"{display}", {fallback}; font-weight:500; font-size:78px; margin:18px 0 22px; min-height:92px;
  border-bottom:2px solid var(--mist); padding-bottom:14px; }}
.course {{ font-family:"{display}", {fallback}; font-weight:700; font-size:52px; color:var(--deep); margin-top:16px; }}
.foot {{ position:absolute; left:420px; right:130px; bottom:110px; display:flex; gap:60px; }}
.field {{ flex:1; }}
.field .val {{ font-weight:500; font-size:32px; min-height:42px; border-bottom:2px solid var(--mist); padding-bottom:10px; }}
.field .lbl {{ font-weight:500; font-size:24px; color:var(--mist); margin-top:12px; letter-spacing:.04em; }}
</style>
</head>
<body>
<div class="sheet">
  <div class="band"></div>
  <div class="mark">{wordmark}</div>
  <div class="body">
    <div class="kicker">{brand}</div>
    <h1>Certificate of<br />completion</h1>
    <div class="rule"></div>
    <div class="lead">This certifies that</div>
    <div class="name">{name}</div>
    <div class="lead">has completed {modules_text} and the knowledge checks of</div>
    <div class="course">{course}</div>
  </div>
  <div class="foot">
    <div class="field"><div class="val">{date}</div><div class="lbl">Date of completion</div></div>
    <div class="field"><div class="val">{learner_id}</div><div class="lbl">Learner ID</div></div>
    <div class="field"><div class="val">&nbsp;</div><div class="lbl">Authorised by</div></div>
  </div>
</div>
</body>
</html>
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("brand")
    ap.add_argument("--course", required=True)
    ap.add_argument("--modules", type=int, default=1)
    ap.add_argument("--name", default="{{learner_name}}")
    ap.add_argument("--date", default="{{completion_date}}")
    ap.add_argument("--learner-id", default="{{learner_id}}")
    ap.add_argument("--out", required=True)
    ap.add_argument("--pdf", action="store_true", help="also print an A4 landscape PDF")
    a = ap.parse_args()

    b = json.loads(pathlib.Path(a.brand).read_text(encoding="utf-8"))
    c, f = b["colours"], b["fonts"]
    faces = "\n".join(f'@font-face {{ font-family: "{f[r]["family"]}"; src: local("{ps}"); font-weight: {w}; }}'
                      for r in ("display", "text") for w, ps in sorted(f[r]["faces"].items()))
    e = lambda s: html.escape(str(s))                                    # noqa: E731
    page = TEMPLATE.format(
        faces=faces, deep=c["deep"], accent=c["accent"], ink=c["ink"], paper=c["paper"], mist=c["mist"],
        text=f["text"]["family"], display=f["display"]["family"], fallback=f.get("fallback", "Georgia, serif"),
        angle=b.get("motif_angle", 135), wordmark=e(b.get("wordmark", b["name"])), brand=e(b["name"]),
        name=e(a.name), date=e(a.date), learner_id=e(a.learner_id), course=e(a.course),
        modules_text="the module" if a.modules == 1 else f"all {a.modules} modules")
    out = pathlib.Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    print(out)
    if a.pdf:
        chrome = next((p for p in [os.environ.get("CHROME", ""),
                                   "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                                   shutil.which("google-chrome") or ""] if p and pathlib.Path(p).exists()), None)
        if not chrome:
            raise SystemExit("Chrome not found: set CHROME=/path/to/chrome")
        pdf = out.with_suffix(".pdf")
        subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                        "--virtual-time-budget=4000", f"--print-to-pdf={pdf}", f"file://{out.resolve()}"],
                       check=True, capture_output=True)
        print(pdf)


if __name__ == "__main__":
    main()
