#!/usr/bin/env python3
"""Prove every @font-face a module uses really loads (no silent Helvetica fallback).

    python3 sa_verify_fonts.py m1_varB m2_varB ...      # exit 1 on any failure
    python3 sa_verify_fonts.py --strict m2_varB         # + every text element must resolve to the display family

Each argument is a module folder holding index.html, under SA_MODULES_DIR (default: the current
folder). The brand's fonts are settings - placeholders here, set them for your brand:
    SA_DISPLAY_FONT_PREFIX   PostScript-name prefix of the display family videos must use
    SA_DOCS_ONLY_FONT        PostScript-name prefix of a text family reserved for documents
    SA_RETIRED_FONT          a family name that must no longer appear anywhere

A grotesk display face looks like Helvetica, so a mistyped local() name falls back invisibly.
For each page: every local() name must be an installed PostScript name, and in headless
Chrome every declared (family, weight) must load while a DECLARED fake face must not
(document.fonts.check() is true for undeclared families, so the fake must be declared).

--strict (opt-in; default behaviour unchanged): the @font-face check alone does not see faces named
directly in font-family (e.g. Georgia on a stand-in wordmark). Strict mode walks every element that
carries text, reads its computed font-family and fails unless the first family is a display-family
@font-face family, or the element sits inside a selector the page allow-lists for deliberately WRONG
examples:  <meta name="verify-fonts-allow" content=".wm, .wm2, #ty-hb">"""
import html as htmlmod
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile

HERE = pathlib.Path(os.environ.get("SA_MODULES_DIR", ".")).resolve()   # the folder of module pages
DISPLAY_PREFIX = os.environ.get("SA_DISPLAY_FONT_PREFIX", "BrandDisplay-")
DOCS_ONLY = os.environ.get("SA_DOCS_ONLY_FONT", "BrandText-")
RETIRED = os.environ.get("SA_RETIRED_FONT", "OldDisplayFace")
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
FACE = re.compile(r"@font-face\s*\{\{?([^}]*)\}", re.S)


def installed_postscript_names():
    out = subprocess.run(["system_profiler", "-json", "SPFontsDataType"],
                         capture_output=True, text=True, check=True).stdout
    return {t.get("_name", "") for f in json.loads(out)["SPFontsDataType"]
            for t in f.get("typefaces", [])}


def faces(html):
    for body in FACE.findall(html):
        fam = re.search(r'font-family:\s*"([^"]+)"', body)
        wt = re.search(r"font-weight:\s*(\d+)", body)
        srcs = re.findall(r'local\("([^"]+)"\)', body)
        urls = re.findall(r"url\(([^)]+)\)", body)
        if fam:
            yield fam.group(1), (wt.group(1) if wt else "400"), srcs, urls


def check(page, installed, strict=False):
    html = page.read_text()
    fs = list(faces(html))
    errs = []
    if RETIRED and RETIRED in html:
        errs.append(f"{RETIRED} reference still present")
    # Brand rule (6 Oct 2026): the display family for videos/design/captions; the text family is documents-only.
    if DOCS_ONLY and DOCS_ONLY in html:
        errs.append(f"{DOCS_ONLY} text family used — documents only; videos must use the display family")
    for fam, wt, srcs, urls in fs:
        if urls:
            errs.append(f"{fam} {wt}: url() source {urls} (expected installed fonts via local())")
        for s in srcs:
            if s not in installed:
                errs.append(f"{fam} {wt}: local('{s}') is not an installed font")
    specs = [f"{wt} 20px \"{fam}\"" for fam, wt, _, _ in fs] + ['400 20px "ZZProbe"']
    probe = ('<style>@font-face { font-family:"ZZProbe"; src: local("NoSuchFont-XYZ-123"); }</style>'
             "<script>Promise.all(%s.map(f=>document.fonts.load(f).catch(()=>[])))"
             ".then(()=>{document.title='FONTS:'+%s.map(f=>document.fonts.check(f)?1:0).join('')})"
             "</script>" % (json.dumps(specs), json.dumps(specs)))
    if strict:
        ci = sorted({fam for fam, _, srcs, _ in fs if srcs and all(x.startswith(DISPLAY_PREFIX) for x in srcs)})
        allow = re.search(r'<meta\s+name="verify-fonts-allow"\s+content="([^"]*)"', html)
        probe += ("<script>document.fonts.ready.then(()=>{const ci=%s, allow=%s, seen={}, out=[];"
                  "for(const el of document.querySelectorAll('body *')){"
                  "if(['SCRIPT','STYLE','PRE'].includes(el.tagName))continue;"
                  "if(![...el.childNodes].some(n=>n.nodeType===3&&n.textContent.trim()))continue;"
                  "if(allow&&el.closest(allow))continue;"
                  "const fam=getComputedStyle(el).fontFamily.split(',')[0].trim().replace(/^[\"']|[\"']$/g,'');"
                  "if(ci.includes(fam))continue;"
                  "const k=el.tagName.toLowerCase()+(el.id?'#'+el.id:'')+(el.className&&el.className.baseVal===undefined?'.'+el.className.trim().split(/\\s+/).join('.'):'')+' -> '+fam;"
                  "if(!seen[k]){seen[k]=1;out.push(k+' (\"'+el.textContent.trim().slice(0,30)+'\")')}}"
                  "const p=document.createElement('pre');p.id='VFTEXT';p.textContent=JSON.stringify({ci:ci,bad:out});"
                  "document.body.appendChild(p);});</script>") % (json.dumps(ci), json.dumps(allow.group(1) if allow else ""))
    with tempfile.NamedTemporaryFile("w", suffix=".html", dir=page.parent, delete=False) as tmp:
        tmp.write(html.replace("</body>", probe + "</body>"))
    try:
        dom = subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--virtual-time-budget=6000",
                              "--dump-dom", f"file://{tmp.name}"], capture_output=True, text=True,
                             timeout=120).stdout
    finally:
        pathlib.Path(tmp.name).unlink()
    m = re.search(r"<title>FONTS:([01]*)</title>", dom)
    if not m:
        errs.append("probe did not report (page script error?)")
    else:
        bits = m.group(1)
        for (fam, wt, _, _), b in zip(fs, bits):
            if b != "1":
                errs.append(f"{fam} {wt}: did NOT load in Chrome")
        if bits[-1:] != "0":
            errs.append("fake probe font reported loaded — test is not discriminating")
    if strict:
        t = re.search(r'<pre id="VFTEXT">(.*?)</pre>', dom, re.S)
        if not t:
            errs.append("strict text audit did not report")
        else:
            res = json.loads(htmlmod.unescape(t.group(1)))
            if not res["ci"]:
                errs.append("strict: no display-family @font-face declared")
            for b in res["bad"][:25]:
                errs.append(f"strict: text not in the display family: {b}")
    used = sorted({s for _, _, srcs, _ in fs for s in srcs})
    return errs, used


if __name__ == "__main__":
    installed = installed_postscript_names()
    bad = 0
    strict = "--strict" in sys.argv
    for d in [a for a in sys.argv[1:] if a != "--strict"]:
        errs, used = check(HERE / d / "index.html", installed, strict)
        bad += bool(errs)
        print(f"{d}: {'PASS' if not errs else 'FAIL'}{' (strict text audit)' if strict else ''}  faces={used}")
        for e in errs:
            print("   -", e)
    sys.exit(1 if bad else 0)
