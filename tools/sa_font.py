#!/usr/bin/env python3
"""sa_font — install Google Fonts families locally, and find their stable paths.

Why this exists (lessons from 5 Aug 2026, don't relearn them):
  1. fonts.google.com/download can be BLOCKED on a managed network — curl just hangs
     and times out. Never use it. Pull from the google/fonts GitHub mirror.
  2. Adobe Fonts / Creative Cloud "installed" fonts are NOT files you can point
     a script at: they live as hidden random-named .otf under CoreSync and the
     names change on every re-sync. Design apps see them, ffmpeg/PIL do not.
     For any render pipeline the font must be a real file in ~/Library/Fonts.
  3. Downloading is not installing — always load-test before declaring success.

Usage:
    python3 sa_font.py install Poppins           # download all faces + verify
    python3 sa_font.py path Poppins SemiBold     # stable path for scripts
    python3 sa_font.py list Poppins              # what's installed locally
"""
import json
import shutil
import sys
import urllib.error
import urllib.request
from pathlib import Path

FONT_DIR = Path.home() / "Library" / "Fonts"
API = "https://api.github.com/repos/google/fonts/contents/{lic}/{slug}"
# google/fonts splits families across three licence folders; try each.
LICENCES = ("ofl", "apache", "ufl")
TIMEOUT = 30


def _slug(family):
    return family.lower().replace(" ", "").replace("-", "")


def _fetch(url, timeout=TIMEOUT):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.read()


def _listing(family):
    """Return [(filename, download_url)] of .ttf files for a family, or []."""
    for lic in LICENCES:
        try:
            entries = json.loads(_fetch(API.format(lic=lic, slug=_slug(family))))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                continue
            if e.code == 403:
                sys.exit("GitHub API rate-limited (60/hr unauthenticated). Wait an hour.")
            raise
        return [(e["name"], e["download_url"]) for e in entries
                if e["name"].lower().endswith(".ttf")]
    return []


def install(family):
    files = _listing(family)
    if not files:
        sys.exit(f"'{family}' not found in google/fonts. Check spelling (e.g. 'Playfair Display').")

    FONT_DIR.mkdir(parents=True, exist_ok=True)
    written = []
    for name, url in files:
        dest = FONT_DIR / name
        try:
            data = _fetch(url)
        except Exception as e:
            print(f"  FAIL {name}: {e}")
            continue
        # ponytail: sniff the magic bytes instead of parsing the table directory —
        # a truncated/HTML-error download is the realistic failure, not a subtly
        # corrupt font. The PIL load below is the real check.
        if data[:4] not in (b"\x00\x01\x00\x00", b"true", b"ttcf", b"OTTO"):
            print(f"  FAIL {name}: not a font (got {data[:16]!r})")
            continue
        dest.write_bytes(data)
        written.append(dest)

    ok = _verify(written)
    print(f"\n{len(ok)}/{len(files)} faces installed to {FONT_DIR}")
    if ok:
        print(f"Scripts should reference e.g. {ok[0]}")
        print("Restart Photoshop / Premiere / AE for them to appear there.")
    return ok


def _verify(paths):
    """Load each file the way a render pipeline would. Downloaded != usable."""
    try:
        from PIL import ImageFont
    except ImportError:
        print("(Pillow missing — skipped load test)")
        return paths
    ok = []
    for p in sorted(paths):
        try:
            fam, style = ImageFont.truetype(str(p), 40).getname()
            print(f"  ok  {fam} {style}")
            ok.append(p)
        except Exception as e:
            print(f"  BAD {p.name}: {e}")
    return ok


def find(family, style=None):
    pat = f"{family.replace(' ', '')}*"
    hits = sorted(FONT_DIR.glob(pat + ".ttf")) + sorted(FONT_DIR.glob(pat + ".otf"))
    if style:
        s = style.lower().replace(" ", "")
        hits = [h for h in hits if s in h.stem.lower().replace("-", "").replace(" ", "")]
    return hits


def main():
    args = sys.argv[1:]
    if len(args) < 2:
        sys.exit(__doc__)
    cmd, family, rest = args[0], args[1], args[2:]

    if cmd == "install":
        install(family)
    elif cmd == "path":
        hits = find(family, " ".join(rest) if rest else None)
        if not hits:
            sys.exit(f"No local '{family}' font. Run: sa_font.py install {family}")
        print(hits[0])
    elif cmd == "list":
        hits = find(family)
        print("\n".join(str(h) for h in hits) if hits else f"No local '{family}'.")
    else:
        sys.exit(__doc__)


def _selftest():
    """Offline check of the parsing/lookup logic. Run: sa_font.py --selftest"""
    assert _slug("Playfair Display") == "playfairdisplay"
    assert _slug("Noto-Sans") == "notosans"
    hits = find("Poppins", "SemiBold")
    assert hits and "SemiBold" in hits[0].name, "Poppins SemiBold not installed"
    assert not find("Poppins", "NotAWeight"), "style filter too loose"
    print("selftest ok")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
    else:
        main()
