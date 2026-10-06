#!/usr/bin/env python3
"""Studio asset memory — index every media file so nothing 'vanishes' again.
Local SQLite catalogue of all video/image/audio across Downloads + Projects.
No torch, no cloud — runs on a tight disk. (CLIP visual-content search is a
future add-on once disk is freed; this gives name/path/project recall now.)

  sa_assets.py scan                       # (re)build index
  sa_assets.py find <keyword>             # search by name/path/project
  sa_assets.py stats                      # totals
"""
import sys, os, sqlite3, time, hashlib

DB = os.path.join(os.path.dirname(__file__), "assets.db")
# folders to index, colon-separated; override with SA_ASSET_ROOTS
ROOTS = [os.path.expanduser(p) for p in
         os.environ.get("SA_ASSET_ROOTS", "~/Downloads:~/Documents/Claude/Projects").split(":") if p]
EXT = (".mp4",".mov",".mkv",".webm",".m4v",".jpg",".jpeg",".png",".heic",
       ".tif",".tiff",".mp3",".wav",".m4a",".aac",".srt",".prproj",".aep")
SKIP = ("OneDrive","CloudStorage",".Trash","node_modules","venv")

def conn():
    c = sqlite3.connect(DB)
    c.execute("""CREATE TABLE IF NOT EXISTS assets(
        path TEXT PRIMARY KEY, name TEXT, ext TEXT, project TEXT,
        size INTEGER, mtime REAL, kind TEXT)""")
    return c

def kind_of(e):
    if e in (".mp4",".mov",".mkv",".webm",".m4v"): return "video"
    if e in (".jpg",".jpeg",".png",".heic",".tif",".tiff"): return "image"
    if e in (".mp3",".wav",".m4a",".aac"): return "audio"
    if e == ".srt": return "caption"
    return "project"

def project_of(path):
    parts = path.split(os.sep)
    if "Projects" in parts:
        i = parts.index("Projects")
        if i+1 < len(parts): return parts[i+1]
    if "Downloads" in parts:
        i = parts.index("Downloads")
        if i+1 < len(parts) and "." not in parts[i+1]: return parts[i+1]
    return ""

def scan():
    c = conn(); n = 0
    for root in ROOTS:
        if not os.path.isdir(root): continue
        for dp, dns, fns in os.walk(root):
            dns[:] = [d for d in dns if not any(s in d for s in SKIP)]
            if any(s in dp for s in SKIP): continue
            for fn in fns:
                e = os.path.splitext(fn)[1].lower()
                if e not in EXT: continue
                fp = os.path.join(dp, fn)
                try: st = os.stat(fp)
                except OSError: continue
                c.execute("REPLACE INTO assets VALUES(?,?,?,?,?,?,?)",
                    (fp, fn, e, project_of(fp), st.st_size, st.st_mtime, kind_of(e)))
                n += 1
    c.commit(); c.close()
    print(f"indexed {n} assets -> {DB}")

def find(kw):
    c = conn(); q = f"%{kw.lower()}%"
    rows = c.execute("""SELECT name,project,kind,size,path FROM assets
        WHERE lower(name) LIKE ? OR lower(path) LIKE ? OR lower(project) LIKE ?
        ORDER BY mtime DESC LIMIT 40""", (q,q,q)).fetchall()
    if not rows: print("no match."); return
    for name,proj,kind,size,path in rows:
        mb = size/1e6
        print(f"  [{kind:7}] {name}  ({mb:.1f}MB)  proj={proj or '-'}\n           {path}")
    print(f"{len(rows)} match(es).")

def stats():
    c = conn()
    tot = c.execute("SELECT COUNT(*),SUM(size) FROM assets").fetchone()
    print(f"total: {tot[0]} files, {(tot[1] or 0)/1e9:.1f} GB")
    for k,cnt,sz in c.execute("SELECT kind,COUNT(*),SUM(size) FROM assets GROUP BY kind ORDER BY 2 DESC"):
        print(f"  {k:9} {cnt:5}  {(sz or 0)/1e9:.2f} GB")

def main():
    if len(sys.argv) < 2: print(__doc__); sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "scan": scan()
    elif cmd == "find" and len(sys.argv) > 2: find(" ".join(sys.argv[2:]))
    elif cmd == "stats": stats()
    else: print(__doc__)

if __name__ == "__main__":
    main()
