#!/usr/bin/env python3
"""Studio Creative Console — the visible control layer over the existing Studio pipeline.

Saad speaks plainly; this routes the request through tools we already have and
puts a clickable approval page in front of him. It builds NOTHING new for
editing — it orchestrates:

  sa_extract.py    technical shot selection (sharp/steady/exposed)  -> cutsheet.json
  sa_timeline.py   editor-neutral plan in a learned Style Brain style
  sa_plan_preview  optional silent review MP4
  sa_capcut_writer   build a NEW CapCut project only

Flow:
  python3 Tools/sa_console.py "Premium 20s vertical product launch reel, cinematic style" /path/to/footage
    -> runs extract (unless a fresh _CUTSHEET exists), plans a timeline,
       writes Console/<slug>/{index.html,state.json,previews/}, opens the browser,
       and serves Approve/Reject/Reorder/Use-alternate + Build buttons.

Everything auto-chosen stays marked "needs review" until Saad approves it in the
page. Approving writes a human-reviewed cutsheet that the build tools consume, so
in/out points, speed and clip order are exactly what he approved — never raw
guesses. Non-destructive: only new projects, originals untouched.

ponytail: stdlib http.server + vanilla JS, no framework/CDN (offline + safe).
"""
import argparse
import http.server
import json
import os
import pathlib
import re
import shutil
import socketserver
import subprocess
import sys
import threading
import webbrowser

ROOT = pathlib.Path(__file__).resolve().parents[1]
TOOLS = ROOT / "Tools"
VENV_PY = TOOLS / "venv" / "bin" / "python"
PY = str(VENV_PY) if VENV_PY.exists() else sys.executable
CONSOLE_ROOT = ROOT / "Console"

# Plain words -> real Style Brain style_type (see CAPCUT_STYLE_BRAIN.json).
STYLE_WORDS = [
    (("tribute", "farewell", "goodbye", "memory", "retire"), "tribute_farewell"),
    (("tutorial", "walkthrough", "how to", "how-to", "screen", "demo", "guide", "explainer"), "tutorial_or_explainer"),
    (("fast", "punchy", "hype", "energetic", "quick montage"), "fast_montage"),
    (("event", "reel", "highlight", "premium", "luxury", "launch", "gala"), "vertical_event_montage"),
]
DEFAULT_STYLE = "vertical_event_montage"


def parse_brief(text):
    """Plain-English brief -> routing dict. Pure, self-tested."""
    low = " " + text.lower() + " "
    style = DEFAULT_STYLE
    for words, canonical in STYLE_WORDS:
        if any(w in low for w in words):
            style = canonical
            break
    if re.search(r"\b(9[:x]16|vertical|reel|portrait|story|stories)\b", low):
        orientation = "vertical"
    elif re.search(r"\b(1[:x]1|square)\b", low):
        orientation = "square"
    elif re.search(r"\b(16[:x]9|landscape|wide|horizontal)\b", low):
        orientation = "landscape"
    else:
        orientation = "vertical"
    m = re.search(r"(\d+)[\s-]*(?:s|sec|secs|second|seconds)\b", low)
    duration = float(m.group(1)) if m else None
    # a short human name: first strong noun-ish chunk, else the style
    focus = ""
    fm = re.search(r"focus(?:\s+on)?\s+([^.\n]+)", low)
    if fm:
        focus = fm.group(1).strip()[:80]
    if any(word in low for word in ("explore", "ambitious", "more ideas", "expand")):
        scope_mode = "expand"
    elif any(word in low for word in ("simplest", "minimum", "reduce", "fastest")):
        scope_mode = "reduce"
    elif any(word in low for word in ("do not add", "hold scope", "exactly")):
        scope_mode = "hold"
    else:
        scope_mode = "selective_expand"
    return {"style": style, "orientation": orientation, "scope_mode": scope_mode,
            "duration": duration, "focus": focus, "brief": text.strip()}


def slugify(text):
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return (s or "project")[:48]


def concepts(route):
    """Three deterministic concept directions from the brief + chosen style.
    v1: template-driven (no model call). Safe / Premium(recommended) / Bold."""
    focus = route["focus"] or "the hero subject and its scale"
    base = {
        "vertical_event_montage": "vertical event montage — clean holds, rhythmic build",
        "tribute_farewell": "tribute montage — slow, warm, continuous music",
        "tutorial_or_explainer": "step-by-step walkthrough — readable pacing, on-screen focus",
        "fast_montage": "fast montage — punchy cuts on the beat",
    }.get(route["style"], "event montage")
    return [
        {"id": "safe", "name": "Safe", "recommended": False,
         "line": "Straightforward %s. Best moments in shot order, minimal risk." % base,
         "notes": "Lowest revision risk. Good when the client is conservative."},
        {"id": "premium", "name": "Premium", "recommended": True,
         "line": "Premium %s built around %s. Deliberate in-points, learned speeds, breathing holds." % (base, focus),
         "notes": "Recommended: matches the house story-first bar without over-cutting."},
        {"id": "bold", "name": "Bold", "recommended": False,
         "line": "Bold %s — tighter cuts, stronger speed ramps, more negative space for titles." % base,
         "notes": "Higher impact, higher revision risk. Pitch when they want standout."},
    ]


def ensure_cutsheet(footage, force, limit):
    folder = pathlib.Path(footage).expanduser().resolve()
    cutsheet = folder / "_CUTSHEET" / "cutsheet.json"
    if cutsheet.is_file() and not force:
        print("reusing existing cutsheet: %s" % cutsheet)
        return cutsheet
    cmd = [PY, str(TOOLS / "sa_extract.py"), str(folder)]
    if limit:
        cmd += ["--limit", str(limit)]
    print("running sa_extract (technical pass)...")
    subprocess.run(cmd, check=True)
    return cutsheet


def build_plan(footage, name, route, cutsheet, out_path, files=None):
    cmd = [PY, str(TOOLS / "sa_timeline.py"), "plan", str(footage),
           "--name", name, "--style", route["style"],
           "--cutsheet", str(cutsheet), "--brief", route["brief"],
           "--out", str(out_path)]
    if route["duration"]:
        cmd += ["--duration", str(route["duration"])]
    if files:
        cmd += ["--files", *files]
    subprocess.run(cmd, check=True)
    return json.loads(pathlib.Path(out_path).read_text(encoding="utf-8"))


def console_state(name, route, cutsheet_data, plan):
    """Merge technical cutsheet rows with plan clips into one review model."""
    by_file = {row["file"]: row for row in cutsheet_data.get("clips", []) if "error" not in row}
    clips = []
    for c in plan["tracks"][0]["clips"]:
        fname = pathlib.Path(c["file"]).name
        row = by_file.get(fname, {})
        clips.append({
            "file": fname, "path": c["file"],
            "preview": pathlib.Path(row.get("preview", "")).name if row.get("preview") else "",
            "role": c["role"],
            "source_start": c["source_start"], "source_out": round(c["source_start"] + c["source_duration"], 3),
            "timeline_duration": c["timeline_duration"], "speed": c["speed"],
            "confidence": row.get("confidence", "unknown"),
            "quality_score": row.get("quality_score", None),
            "flags": row.get("flags", []),
            "evidence": c.get("evidence", ""),
            "alternate_windows": [{"in": a.get("start"), "out": a.get("end"),
                                   "quality": a.get("quality_score")} for a in row.get("alternate_windows", [])],
            # review decisions (default: pending -> included, needs approval)
            "approved": False, "rejected": False, "order": len(clips),
        })
    return {
        "schema": "console/1.0", "project": name, "brief": route["brief"],
        "route": route, "canvas": plan["canvas"],
        "style": plan["style"], "concepts": concepts(route),
        "chosen_concept": "premium",
        "clips": clips,
        "coverage_warnings": coverage_warnings(clips, route),
        "artifact_chain": {
            "brief": "verified", "concept": "ask", "analysis": "verified",
            "selects": "ask", "timeline": "blocked", "build": "blocked",
            "qa": "blocked", "learning": "blocked"
        },
        "review_labels": ["AUTO_FIXED", "ASK", "BLOCKED", "NOTE"],
        "build": {"last": None, "log": []},
    }


def coverage_warnings(clips, route):
    warn = []
    if route["duration"]:
        total = sum(c["timeline_duration"] for c in clips)
        if total < route["duration"] * 0.85:
            warn.append("Planned %.1fs is short of the %.0fs target — add B-roll or more selects." % (total, route["duration"]))
    low = [c["file"] for c in clips if c["confidence"] == "low"]
    if low:
        warn.append("%d low-confidence shot(s) need a look: %s" % (len(low), ", ".join(low[:6])))
    if not any(c["role"] == "opener" for c in clips):
        warn.append("No clear opener — pick a strong establishing shot.")
    return warn


def write_console(project_dir, state, cutsheet_data):
    project_dir.mkdir(parents=True, exist_ok=True)
    previews = project_dir / "previews"
    previews.mkdir(exist_ok=True)
    src_previews = pathlib.Path(state["route_footage"]) / "_CUTSHEET" / "previews"
    for c in state["clips"]:
        if c["preview"] and (src_previews / c["preview"]).is_file():
            shutil.copy2(src_previews / c["preview"], previews / c["preview"])
    (project_dir / "state.json").write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    (project_dir / "index.html").write_text(HTML, encoding="utf-8")


def approved_cutsheet(state):
    """Console decisions -> human-reviewed cutsheet the build tools trust."""
    rows = []
    kept = [c for c in state["clips"] if c["approved"] and not c["rejected"]]
    kept.sort(key=lambda c: c["order"])
    for c in kept:
        rows.append({
            "file": c["file"], "path": c["path"],
            "suggested_in": c["source_start"], "suggested_out": c["source_out"],
            "suggested_speed": c["speed"], "reviewed": True,
            "quality_score": c.get("quality_score"), "confidence": c.get("confidence"),
        })
    return {"schema_version": "2.0", "analysis": "human-approved-console", "clips": rows}, [c["file"] for c in kept]


def do_build(project_dir, state, target):
    footage = state["route_footage"]
    name = "%s (%s)" % (state["project"], target)
    ac, files = approved_cutsheet(state)
    if not files:
        return "No approved clips — approve at least one first."
    tmp_cut = project_dir / "_approved_cutsheet.json"
    tmp_cut.write_text(json.dumps(ac, indent=2), encoding="utf-8")
    plan_path = project_dir / "_approved_plan.json"
    try:
        build_plan(footage, state["project"], state["route"], tmp_cut, plan_path, files=files)
    except subprocess.CalledProcessError as e:
        return "Plan build failed: %s" % e
    cmd = [PY, str(TOOLS / "sa_capcut_writer.py"), str(plan_path), "--name", name]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    except Exception as e:
        return "Build call failed: %s" % e
    out = (r.stdout + r.stderr).strip()
    ok = r.returncode == 0
    msg = "%s %s: %s" % ("OK" if ok else "FAILED", target, out[-500:])
    state["build"]["last"] = target
    state["build"]["log"].append(msg)
    (project_dir / "state.json").write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    return msg


def serve(project_dir, port=8777):
    state_path = project_dir / "state.json"

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=str(project_dir), **k)

        def log_message(self, *a):
            pass

        def _json(self, obj, code=200):
            body = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length) or b"{}")
            if self.path == "/save":
                st = json.loads(state_path.read_text())
                st["clips"] = payload.get("clips", st["clips"])
                st["chosen_concept"] = payload.get("chosen_concept", st["chosen_concept"])
                state_path.write_text(json.dumps(st, indent=2) + "\n", encoding="utf-8")
                return self._json({"ok": True})
            if self.path == "/build":
                st = json.loads(state_path.read_text())
                st["clips"] = payload.get("clips", st["clips"])
                msg = do_build(project_dir, st, payload.get("target", "capcut"))
                return self._json({"ok": msg.startswith("OK"), "message": msg})
            self._json({"ok": False, "error": "unknown"}, 404)

    with socketserver.TCPServer(("127.0.0.1", port), Handler) as httpd:
        url = "http://127.0.0.1:%d/index.html" % port
        print("\nStudio Creative Console → %s   (Ctrl-C to stop)\n" % url)
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nconsole stopped.")


def run(brief, footage, port, force_extract, limit):
    route = parse_brief(brief)
    footage = str(pathlib.Path(footage).expanduser().resolve())
    name = slugify(route["focus"] or route["style"]) + "-" + route["orientation"]
    cutsheet = ensure_cutsheet(footage, force_extract, limit)
    cutsheet_data = json.loads(pathlib.Path(cutsheet).read_text())
    project_dir = CONSOLE_ROOT / slugify(name)
    plan_path = project_dir / "_plan.json"
    project_dir.mkdir(parents=True, exist_ok=True)
    plan = build_plan(footage, name, route, cutsheet, plan_path)
    state = console_state(name, route, cutsheet_data, plan)
    state["route_footage"] = footage
    write_console(project_dir, state, cutsheet_data)
    print("console ready: %s" % (project_dir / "index.html"))
    serve(project_dir, port)


# ---------------- self-checks ----------------

def self_test():
    r = parse_brief("Create a premium 20-second vertical product launch reel, cinematic style, focus on the hero shot")
    assert r["style"] == "vertical_event_montage", r
    assert r["orientation"] == "vertical" and r["duration"] == 20.0, r
    assert "hero shot" in r["focus"], r
    r2 = parse_brief("square fast punchy montage")
    assert r2["style"] == "fast_montage" and r2["orientation"] == "square", r2
    # approved_cutsheet keeps only approved, in reordered order, marked reviewed
    state = {"clips": [
        {"file": "b.mp4", "path": "/x/b.mp4", "source_start": 1, "source_out": 3, "speed": 0.7,
         "approved": True, "rejected": False, "order": 1, "quality_score": 80, "confidence": "high"},
        {"file": "a.mp4", "path": "/x/a.mp4", "source_start": 0, "source_out": 2, "speed": 1.0,
         "approved": True, "rejected": False, "order": 0, "quality_score": 70, "confidence": "medium"},
        {"file": "c.mp4", "path": "/x/c.mp4", "source_start": 0, "source_out": 2, "speed": 1.0,
         "approved": False, "rejected": True, "order": 2},
    ]}
    ac, files = approved_cutsheet(state)
    assert files == ["a.mp4", "b.mp4"], files
    assert all(row["reviewed"] for row in ac["clips"]) and len(ac["clips"]) == 2
    assert slugify("Launch Reel! (v2)") == "launch-reel-v2"
    print("sa_console self-checks: ok")


HTML = r"""<!doctype html><html><head><meta charset="utf-8">
<title>Studio Creative Console</title>
<style>
:root{--bg:#0e1116;--card:#171c24;--edge:#242c38;--ink:#e8edf4;--dim:#8b97a8;--ok:#3fb984;--no:#e0645f;--gold:#d9b66b;--accent:#4c8dff}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 -apple-system,Segoe UI,Roboto,sans-serif}
header{padding:20px 28px;border-bottom:1px solid var(--edge);position:sticky;top:0;background:var(--bg);z-index:5}
h1{margin:0;font-size:19px;letter-spacing:.3px}.brief{color:var(--dim);margin-top:4px;max-width:900px}
.wrap{padding:22px 28px;max-width:1200px}
.row{display:flex;gap:16px;flex-wrap:wrap}
.concept{flex:1;min-width:220px;background:var(--card);border:1px solid var(--edge);border-radius:12px;padding:14px;cursor:pointer}
.concept.on{border-color:var(--gold);box-shadow:0 0 0 1px var(--gold)}
.concept h3{margin:0 0 6px}.concept .rec{color:var(--gold);font-size:12px;font-weight:600}
.concept p{color:var(--dim);margin:6px 0 0;font-size:13px}
h2{margin:26px 0 10px;font-size:15px;color:var(--dim);text-transform:uppercase;letter-spacing:1px}
.warn{background:#2a2113;border:1px solid #4a3a17;color:#e7cd93;border-radius:10px;padding:10px 14px;margin:6px 0}
.clip{display:flex;gap:14px;background:var(--card);border:1px solid var(--edge);border-radius:12px;padding:12px;margin-bottom:12px;align-items:flex-start}
.clip.rej{opacity:.4}.clip.app{border-color:var(--ok)}
.clip img{width:150px;height:200px;object-fit:cover;border-radius:8px;background:#000;flex:none}
.meta{flex:1;min-width:0}.meta b{font-size:15px}
.tag{display:inline-block;font-size:12px;padding:2px 8px;border-radius:20px;border:1px solid var(--edge);margin:2px 6px 2px 0;color:var(--dim)}
.tag.high{color:var(--ok);border-color:var(--ok)}.tag.low{color:var(--no);border-color:var(--no)}
.tag.flag{color:var(--gold);border-color:var(--gold)}
.ev{color:var(--dim);font-size:13px;margin-top:6px}
.ctl{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px;align-items:center}
button{background:var(--edge);color:var(--ink);border:0;border-radius:8px;padding:7px 12px;cursor:pointer;font-size:13px}
button:hover{filter:brightness(1.2)}button.ok{background:var(--ok);color:#062}button.no{background:var(--no);color:#400}
button.big{padding:11px 20px;font-size:15px;font-weight:600}
select,input{background:#0e1116;color:var(--ink);border:1px solid var(--edge);border-radius:7px;padding:6px}
.bar{position:sticky;bottom:0;background:var(--bg);border-top:1px solid var(--edge);padding:16px 28px;display:flex;gap:12px;align-items:center}
.log{color:var(--dim);font-size:13px;margin-left:auto;max-width:50%;white-space:pre-wrap}
.pill{font-size:12px;color:var(--dim)}
</style></head><body>
<header><h1>Studio Creative Console <span class="pill" id="fmt"></span></h1><div class="brief" id="brief"></div></header>
<div class="wrap">
  <h2>Concept — pick a direction</h2><div class="row" id="concepts"></div>
  <div id="warns"></div>
  <h2>Selected clips — approve what makes the cut</h2><div id="clips"></div>
</div>
<div class="bar">
  <button class="big" onclick="save()">Save decisions</button>
  <button class="big ok" onclick="build('capcut')">Build in CapCut</button>
  <span class="pill" id="count"></span>
  <div class="log" id="log"></div>
</div>
<script>
let S=null;
async function load(){S=await (await fetch('state.json?'+Date.now())).json();render();}
function render(){
  document.getElementById('brief').textContent=S.brief;
  document.getElementById('fmt').textContent=S.canvas.width+'×'+S.canvas.height+' · '+S.style.type+' · '+(S.style.masters||[]).join(', ');
  const cc=document.getElementById('concepts');cc.innerHTML='';
  S.concepts.forEach(k=>{const d=document.createElement('div');d.className='concept'+(S.chosen_concept===k.id?' on':'');
    d.innerHTML='<h3>'+k.name+(k.recommended?' <span class="rec">★ recommended</span>':'')+'</h3><div>'+k.line+'</div><p>'+k.notes+'</p>';
    d.onclick=()=>{S.chosen_concept=k.id;render();};cc.appendChild(d);});
  const w=document.getElementById('warns');w.innerHTML='';
  (S.coverage_warnings||[]).forEach(t=>{const e=document.createElement('div');e.className='warn';e.textContent='⚠ '+t;w.appendChild(e);});
  const list=[...S.clips].sort((a,b)=>a.order-b.order);
  const box=document.getElementById('clips');box.innerHTML='';
  list.forEach((c)=>{const i=S.clips.indexOf(c);const d=document.createElement('div');
    d.className='clip'+(c.rejected?' rej':(c.approved?' app':''));
    const conf='<span class="tag '+(c.confidence==='high'?'high':(c.confidence==='low'?'low':''))+'">'+c.confidence+(c.quality_score!=null?' · '+c.quality_score+'/100':'')+'</span>';
    const flags=(c.flags||[]).map(f=>'<span class="tag flag">'+f+'</span>').join('');
    const alts=(c.alternate_windows||[]).map((a,ai)=>'<option value="'+a.in+','+a.out+'">alt '+(ai+1)+': '+a.in+'–'+a.out+'s ('+(a.quality||'?')+')</option>').join('');
    d.innerHTML='<img src="previews/'+c.preview+'" onerror="this.style.opacity=.15">'+
      '<div class="meta"><b>'+c.file+'</b> &nbsp;<span class="tag">'+c.role+'</span>'+conf+flags+
      '<div class="ev">src '+c.source_start+'–'+c.source_out+'s · timeline '+c.timeline_duration+'s · '+c.speed+'×</div>'+
      '<div class="ev">'+(c.evidence||'')+'</div>'+
      '<div class="ctl">'+
        '<button class="ok" onclick="dec('+i+',\'app\')">Approve</button>'+
        '<button class="no" onclick="dec('+i+',\'rej\')">Reject</button>'+
        '<button onclick="mv('+i+',-1)">↑</button><button onclick="mv('+i+',1)">↓</button>'+
        'speed <input type="number" step="0.1" min="0.1" style="width:64px" value="'+c.speed+'" onchange="S.clips['+i+'].speed=parseFloat(this.value)">'+
        (alts?' <select onchange="setwin('+i+',this.value)"><option>use alternate…</option>'+alts+'</select>':'')+
      '</div></div>';
    box.appendChild(d);});
  const ap=S.clips.filter(c=>c.approved&&!c.rejected).length;
  document.getElementById('count').textContent=ap+' approved / '+S.clips.length;
}
function dec(i,k){const c=S.clips[i];if(k==='app'){c.approved=!c.approved;c.rejected=false;}else{c.rejected=!c.rejected;c.approved=false;}render();}
function mv(i,dir){const c=S.clips[i];const list=[...S.clips].sort((a,b)=>a.order-b.order);const p=list.indexOf(c);const q=p+dir;if(q<0||q>=list.length)return;const o=list[p].order;list[p].order=list[q].order;list[q].order=o;render();}
function setwin(i,v){if(!v.includes(','))return;const[a,b]=v.split(',').map(parseFloat);S.clips[i].source_start=a;S.clips[i].source_out=b;render();}
async function save(){await fetch('/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({clips:S.clips,chosen_concept:S.chosen_concept})});flash('Saved.');}
async function build(t){flash('Building in '+t+'…');const r=await (await fetch('/build',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({clips:S.clips,target:t})})).json();flash(r.message);}
function flash(m){document.getElementById('log').textContent=m;}
load();
</script></body></html>"""


def main():
    ap = argparse.ArgumentParser(description="Studio Creative Console")
    ap.add_argument("brief", nargs="?", help='e.g. "premium 20s vertical product launch reel, cinematic style"')
    ap.add_argument("footage", nargs="?", help="folder of source clips")
    ap.add_argument("--port", type=int, default=8777)
    ap.add_argument("--force-extract", action="store_true", help="re-run technical analysis even if a cutsheet exists")
    ap.add_argument("--limit", type=int, help="only analyse the first N clips (daytime/test)")
    ap.add_argument("--test", action="store_true")
    a = ap.parse_args()
    if a.test:
        return self_test()
    if not a.brief or not a.footage:
        ap.error("need: brief and footage folder (or --test)")
    run(a.brief, a.footage, a.port, a.force_extract, a.limit)


if __name__ == "__main__":
    main()
