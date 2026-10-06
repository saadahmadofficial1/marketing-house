#!/usr/bin/env python3
"""Brain health map — the useful idea distilled from graphify/codegraph/claude-mem.
  sa_vaultmap.py            -> print report
  sa_vaultmap.py -o FILE    -> also write markdown report
Scans the vault's .md files, follows [[wikilinks]], and surfaces structure you
can't see reading file-by-file: god nodes, orphans, broken links.
"""
import os, re, sys, glob, collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# ponytail: skip machine/tool dirs — they aren't part of the human brain
SKIP = ("/Tools/installs/", "/Tools/external/", "/.obsidian/", "/node_modules/",
        "/.git/", "/Sessions/", "/venv/", "/.venv/", "/site-packages/", "/STARTER_KIT/")
NOSCAN = ("BRAIN_HEALTH.md",)  # exists as a note, but its content quotes broken links — don't scan
LINK = re.compile(r"\[\[([^\]|#]+)")  # [[Note]], [[Note|alias]], [[Note#h]] -> "Note"

def md_files():
    for p in glob.glob(os.path.join(ROOT, "**", "*.md"), recursive=True):
        if not any(s in p for s in SKIP):
            yield p

def key(name):  # match links to files by basename, case-insensitive
    return os.path.splitext(os.path.basename(name))[0].strip().lower()

def build():
    files = list(md_files())
    names = {key(p): os.path.relpath(p, ROOT) for p in files}
    inbound = collections.Counter()
    broken = collections.defaultdict(list)
    for p in files:
        if os.path.basename(p) in NOSCAN:
            continue
        txt = open(p, encoding="utf-8", errors="ignore").read()
        # ignore [[links]] inside code fences / inline code — they're examples, not links
        txt = re.sub(r"```.*?```", "", txt, flags=re.S)
        txt = re.sub(r"`[^`\n]*`", "", txt)
        for raw in LINK.findall(txt):
            k = key(raw)
            if k in names and k != key(p):
                inbound[k] += 1
            elif k not in names:
                broken[os.path.relpath(p, ROOT)].append(raw.strip())
    orphans = sorted(names[k] for k in names if inbound[k] == 0)
    gods = inbound.most_common(12)
    return names, inbound, gods, orphans, broken

def report():
    names, inbound, gods, orphans, broken = build()
    L = []
    a = L.append
    a(f"# Brain health map ({len(names)} notes)\n")
    a(f"- God nodes: **{len(gods)}** · Orphans: **{len(orphans)}** · "
      f"Files with broken links: **{len(broken)}**\n")
    a("## 🕸 God nodes (most-linked — your brain's backbone)")
    for k, n in gods:
        a(f"- **{n}** — {names[k]}")
    a("\n## 🌱 Orphans (nothing links here — link them or they get lost)")
    for o in orphans:
        a(f"- {o}")
    a("\n## 🔗 Broken links (point to notes that don't exist — fix the rot)")
    if not broken:
        a("- none ✅")
    for f, links in sorted(broken.items()):
        a(f"- **{f}**: {', '.join('[[%s]]' % x for x in sorted(set(links)))}")
    return "\n".join(L)

if __name__ == "__main__":
    out = report()
    print(out)
    if "-o" in sys.argv:
        dest = sys.argv[sys.argv.index("-o") + 1]
        open(dest, "w", encoding="utf-8").write(out + "\n")
        print(f"\n[written: {dest}]", file=sys.stderr)
