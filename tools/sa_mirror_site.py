#!/usr/bin/env python3
"""
Take a working offline copy of a static site, so it can be opened and shared without
the repo.

We have the approved build's URL but not its source, so the only way to show Saad his
new pictures in place - or to hand anyone a before/after - is to pull the whole thing
down and swap the images in the copy.

Two things make the copy actually work rather than merely exist:

  Absolute paths are rewritten RELATIVE to each page's own depth. A Next.js export
  references /_next/... and /images/..., which resolve to the filesystem root when the
  file is opened directly, so every stylesheet and picture silently fails. /en/about/
  needs ../../images/x.jpg while /en/ needs ../images/x.jpg - the depth is per page.

  Routes are saved as <path>/index.html. A link to /en/about/ then finds its file the
  same way the server would, and relative asset paths from it still line up.

    sa_mirror_site.py https://example.com out_dir [--max 400]
    sa_mirror_site.py --unfreeze out_dir      # only re-patch an existing copy
    sa_mirror_site.py --demo
"""
import re, sys, pathlib, urllib.parse, urllib.request, collections

ASSET_RE = re.compile(r'(?:src|href)="([^"]+)"|url\((["\']?)([^)"\']+)\2\)')
PAGE_EXT = ("", ".html", "/")
SKIP = ("mailto:", "tel:", "javascript:", "data:", "#")


def depth_prefix(rel_path):
    """How many '../' a file at rel_path needs to reach the mirror root."""
    return "../" * (len(pathlib.PurePosixPath(rel_path).parts) - 1)


def to_relative(html, rel_path):
    """Rewrite every root-absolute reference to one relative to this page."""
    up = depth_prefix(rel_path)
    html = re.sub(r'((?:src|href)=")/(?!/)', lambda m: m.group(1) + up, html)
    html = re.sub(r'(url\(["\']?)/(?!/)', lambda m: m.group(1) + up, html)
    html = re.sub(r'(srcset="[^"]*)', lambda m: m.group(1).replace(" /", " " + up), html)
    return html


def fetch(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(), r.headers.get_content_type()


def local_path(url, origin):
    """Where a URL lands on disk. Routes become <path>/index.html."""
    p = urllib.parse.urlparse(url).path
    if p.endswith("/") or "." not in pathlib.PurePosixPath(p).name:
        return (p.strip("/") + "/index.html").lstrip("/")
    return p.lstrip("/")


# The site hides scroll-reveal sections with .reveal {opacity:0} and its own JavaScript
# adds .in when they scroll into view. In a static copy that JavaScript never completes -
# Next.js hydration expects a server behind it - so every revealed section stays invisible
# forever. The page looks half-empty and it is NOT obvious why: the markup is all there,
# the images all load 200, they are simply transparent.
#
# The site's stylesheet already carries the .reveal.in rules that make them visible, so the
# honest fix is to do exactly what its own script would have done, at load.
# The override goes in the STYLESHEET, not the HTML. Injecting a <script> or <style>
# into the page body does not survive: React hydration rebuilds the DOM and throws the
# injected tags away - verified, they vanish between the served HTML and the live DOM.
# A linked stylesheet in <head> is never touched, so that is where the fix belongs.
UNFREEZE_CSS = """
/* --- UNFREEZE-REVEALS --- offline copy only.
   The site hides scroll-reveal sections with .reveal{opacity:0} and its own JavaScript
   adds .in when they scroll into view. In a static copy that JavaScript never completes,
   so those sections stay invisible forever: the markup is all there, every image loads
   200, and the page still looks half-empty with no visible cause. */
.reveal, .reveal * { opacity: 1 !important; transform: none !important;
                     visibility: visible !important; animation: none !important; }
"""


def unfreeze_reveals(out):
    """Make scroll-revealed sections visible in an offline copy. Returns files touched."""
    out = pathlib.Path(out)
    n = 0
    for f in out.rglob("*.css"):
        t = f.read_text(errors="ignore")
        if "UNFREEZE-REVEALS" in t:
            continue
        f.write_text(t + UNFREEZE_CSS, encoding="utf-8")
        n += 1
    return n


def crawl(start, out, max_pages=400):
    out = pathlib.Path(out)
    origin = "{0.scheme}://{0.netloc}".format(urllib.parse.urlparse(start))
    seen, queue = set(), collections.deque([start])
    assets, pages, failed = set(), 0, []

    while queue and pages < max_pages:
        url = queue.popleft()
        if url in seen:
            continue
        seen.add(url)
        try:
            body, ctype = fetch(url)
        except Exception as e:
            failed.append((url, str(e)[:60])); continue
        rel = local_path(url, origin)
        dst = out / rel
        dst.parent.mkdir(parents=True, exist_ok=True)

        if "html" not in ctype:
            dst.write_bytes(body); continue
        pages += 1
        html = body.decode("utf-8", "replace")

        for m in ASSET_RE.finditer(html):
            ref = m.group(1) or m.group(3)
            if not ref or ref.startswith(SKIP) or ref.startswith(("http", "//")):
                if ref and ref.startswith(origin):
                    pass
                else:
                    continue
            full = urllib.parse.urljoin(url, ref.split("#")[0])
            if not full.startswith(origin) or full in seen:
                continue
            name = pathlib.PurePosixPath(urllib.parse.urlparse(full).path).name
            if "." in name and not name.endswith(".html"):
                assets.add(full)
            else:
                queue.append(full)

        dst.write_text(to_relative(html, rel), encoding="utf-8")

    for a in sorted(assets):
        if a in seen:
            continue
        seen.add(a)
        rel = local_path(a, origin)
        dst = out / rel
        if dst.exists():
            continue
        try:
            body, _ = fetch(a)
        except Exception as e:
            failed.append((a, str(e)[:60])); continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(body)

    return pages, len(assets), failed


def demo():
    assert depth_prefix("en/index.html") == "../"
    assert depth_prefix("en/about/index.html") == "../../"
    assert depth_prefix("index.html") == ""
    h = '<img src="/images/a.jpg"><link href="/_next/x.css"><i style="background:url(/b.png)">'
    r = to_relative(h, "en/about/index.html")
    assert '../../images/a.jpg' in r and '../../_next/x.css' in r and 'url(../../b.png)' in r, r
    # at the root the leading slash is simply dropped - "/x.jpg" resolves to the
    # filesystem root when opened as a file, "x.jpg" resolves beside the page
    r2 = to_relative('<img src="/x.jpg"><a href="https://z.com/y">', "index.html")
    assert 'src="x.jpg"' in r2, r2
    assert "https://z.com/y" in r2, "an absolute URL to another host must be left alone"
    assert local_path("https://s.com/en/about/", "") == "en/about/index.html"
    assert local_path("https://s.com/images/a.jpg", "") == "images/a.jpg"
    assert local_path("https://s.com/en/news", "") == "en/news/index.html"

    # a copy whose reveal sections are still frozen is a copy that looks half-empty
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        t = pathlib.Path(d) / "en" / "index.html"
        t.parent.mkdir(parents=True)
        t.write_text("<html><body><div class='reveal'>x</div></body></html>")
        css = pathlib.Path(d) / "_next" / "a.css"
        css.parent.mkdir(parents=True)
        css.write_text(".reveal{opacity:0}")
        assert unfreeze_reveals(d) == 1, "the stylesheet is what must be patched"
        out = css.read_text()
        assert "opacity: 1 !important" in out and out.startswith(".reveal{opacity:0}")
        assert unfreeze_reveals(d) == 0, "running it twice must not append twice"
    print("demo ok")


if __name__ == "__main__":
    if "--demo" in sys.argv:
        demo(); sys.exit(0)
    mx = int(sys.argv[sys.argv.index("--max") + 1]) if "--max" in sys.argv else 400
    if sys.argv[1] == "--unfreeze":
        print(f"  unfroze reveals in {unfreeze_reveals(sys.argv[2])} pages"); sys.exit(0)
    p, a, f = crawl(sys.argv[1], sys.argv[2], mx)
    n = unfreeze_reveals(sys.argv[2])
    print(f"  {p} pages, {a} assets -> {sys.argv[2]}   (reveals unfrozen in {n} stylesheets)")
    if f:
        print(f"  {len(f)} failed:")
        for u, e in f[:15]:
            print("    ", u, e)
