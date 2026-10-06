#!/usr/bin/env python3
"""Prove every @font-face a composition declares really loads: no silent fallback.

    python3 verify_fonts.py build/acme_m1/index.html [more.html ...]     # exit 1 on any failure
    python3 verify_fonts.py --strict build/acme_m1/index.html            # + every text element

Why: a mistyped local() name falls back without a word, and many grotesque faces look
alike at a glance, so "it looks right" proves nothing. Three checks, all local:

  1. Every local("PostScriptName") is an installed font (macOS: system_profiler; skip with
     --no-installed-check on other systems).
  2. In the same headless Chrome family the renderer uses, every declared (family, weight)
     must load AND a deliberately DECLARED fake face must fail. document.fonts.check() is
     true for an undeclared family, so the fake has to be declared, or the test cannot fail.
  3. --strict: walk every element that carries text, read its computed font-family, and
     fail unless the first family is one of the page's @font-face families. Deliberately
     wrong examples can be allow-listed:  <meta name="verify-fonts-allow" content=".bad-example">

Make the composition's fallback a SERIF so that, even if a check is skipped, a failed load
is visible on the frame. Generalised from ../../../tools/sa_verify_fonts.py.
"""
import argparse
import html as htmlmod
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

FACE = re.compile(r"@font-face\s*\{([^}]*)\}", re.S)
CHROME_CANDIDATES = [
    os.environ.get("CHROME", ""),
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    shutil.which("google-chrome") or "", shutil.which("chromium") or "",
]


def chrome():
    for c in CHROME_CANDIDATES:
        if c and pathlib.Path(c).exists():
            return c
    raise SystemExit("Chrome not found: set CHROME=/path/to/chrome")


def installed_postscript_names():
    out = subprocess.run(["system_profiler", "-json", "SPFontsDataType"],
                         capture_output=True, text=True, check=True).stdout
    return {t.get("_name", "") for f in json.loads(out)["SPFontsDataType"] for t in f.get("typefaces", [])}


def faces(page_html):
    for body in FACE.findall(page_html):
        fam = re.search(r'font-family:\s*"([^"]+)"', body)
        wt = re.search(r"font-weight:\s*(\d+)", body)
        if fam:
            yield (fam.group(1), wt.group(1) if wt else "400",
                   re.findall(r'local\("([^"]+)"\)', body), re.findall(r"url\(([^)]+)\)", body))


def check(page, installed, strict=False):
    page_html = page.read_text(encoding="utf-8")
    fs = list(faces(page_html))
    errs = []
    if not fs:
        errs.append("no @font-face declared: nothing to prove")
    for fam, wt, srcs, urls in fs:
        if urls:
            errs.append(f"{fam} {wt}: url() source {urls}; this template expects installed fonts via local()")
        for s in srcs:
            if installed is not None and s not in installed:
                errs.append(f"{fam} {wt}: local('{s}') is not an installed font")
    specs = [f'{wt} 20px "{fam}"' for fam, wt, _, _ in fs] + ['400 20px "ZZProbe"']
    probe = ('<style>@font-face { font-family:"ZZProbe"; src: local("NoSuchFont-XYZ-123"); }</style>'
             "<script>Promise.all(%s.map(f=>document.fonts.load(f).catch(()=>[])))"
             ".then(()=>{document.title='FONTS:'+%s.map(f=>document.fonts.check(f)?1:0).join('')})"
             "</script>" % (json.dumps(specs), json.dumps(specs)))
    if strict:
        fams = sorted({fam for fam, _, _, _ in fs})
        allow = re.search(r'<meta\s+name="verify-fonts-allow"\s+content="([^"]*)"', page_html)
        probe += ("<script>document.fonts.ready.then(()=>{const ok=%s, allow=%s, seen={}, out=[];"
                  "for(const el of document.querySelectorAll('body *')){"
                  "if(['SCRIPT','STYLE','PRE','TITLE'].includes(el.tagName))continue;"
                  "if(![...el.childNodes].some(n=>n.nodeType===3&&n.textContent.trim()))continue;"
                  "if(allow&&el.closest(allow))continue;"
                  "const fam=getComputedStyle(el).fontFamily.split(',')[0].trim().replace(/^[\"']|[\"']$/g,'');"
                  "if(ok.includes(fam))continue;"
                  "const k=el.tagName.toLowerCase()+(el.id?'#'+el.id:'')+' -> '+fam;"
                  "if(!seen[k]){seen[k]=1;out.push(k+' (\"'+el.textContent.trim().slice(0,30)+'\")')}}"
                  "const p=document.createElement('pre');p.id='VFTEXT';p.textContent=JSON.stringify({ok:ok,bad:out});"
                  "document.body.appendChild(p);});</script>") % (json.dumps(fams), json.dumps(allow.group(1) if allow else ""))
    with tempfile.NamedTemporaryFile("w", suffix=".html", dir=page.parent, delete=False, encoding="utf-8") as tmp:
        tmp.write(page_html.replace("</body>", probe + "</body>"))
    try:
        dom = subprocess.run([chrome(), "--headless=new", "--disable-gpu", "--virtual-time-budget=6000",
                              "--dump-dom", f"file://{tmp.name}"], capture_output=True, text=True, timeout=120).stdout
    finally:
        pathlib.Path(tmp.name).unlink()
    m = re.search(r"<title>FONTS:([01]*)</title>", dom)
    if not m:
        errs.append("probe did not report (script error on the page?)")
    else:
        bits = m.group(1)
        for (fam, wt, _, _), b in zip(fs, bits):
            if b != "1":
                errs.append(f"{fam} {wt}: did NOT load in Chrome")
        if bits[-1:] != "0":
            errs.append("the declared fake face reported loaded: the test is not discriminating")
    if strict:
        t = re.search(r'<pre id="VFTEXT">(.*?)</pre>', dom, re.S)
        if not t:
            errs.append("strict text audit did not report")
        else:
            res = json.loads(htmlmod.unescape(t.group(1)))
            errs += [f"strict: text not in a declared family: {b}" for b in res["bad"][:25]]
    return errs, sorted({s for _, _, srcs, _ in fs for s in srcs})


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("pages", nargs="+")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--no-installed-check", action="store_true", help="skip the macOS installed-font check")
    a = ap.parse_args()
    installed = None if a.no_installed_check else installed_postscript_names()
    bad = 0
    for p in a.pages:
        errs, used = check(pathlib.Path(p).resolve(), installed, a.strict)
        bad += bool(errs)
        print(f"{p}: {'PASS' if not errs else 'FAIL'}{' (strict)' if a.strict else ''}  faces={used}")
        for e in errs:
            print("   -", e)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
