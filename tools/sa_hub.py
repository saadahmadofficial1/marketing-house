#!/usr/bin/env python3
"""Studio Hub — everything in one local website.  http://localhost:8777
  python3 Tools/sa_hub.py            # start + open browser
Tabs: Home (brief + ask) · VO Studio · Prompts · Toolbox · QA Inbox ·
Activity · Health. Serves the existing self-contained HTML tools in-place;
binds 127.0.0.1 only. The hub itself runs locally; the VO Studio tab sends the text
you type to Microsoft's online Edge voices.
"""
import os, sys, json, re, glob, socket, subprocess, urllib.request, urllib.parse, webbrowser
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PORT = 8777

def fresh_brief():
    """Today's brief: a few live counts from the workspace, one {tone, text} per line."""
    sessions = sorted(glob.glob(os.path.join(ROOT, "Sessions", "2*")))
    latest = os.path.basename(sessions[-1]) if sessions else "none yet"
    notes = len(glob.glob(os.path.join(ROOT, "*.md")))
    return [{"tone": "ok", "text": f"Latest session: {latest}."},
            {"tone": "ok", "text": f"{notes} core notes and {len(sessions)} session folders on file."}]

# ---- ask-anything: stdlib keyword retrieval over the brain files + local Ollama ----
OLLAMA = "http://localhost:11434/api/generate"
LLM = os.environ.get("SA_LLM", "gemma3:4b")  # fast text model; vision jobs keep qwen3-vl:8b
STOP = set("the a an is are was were be to of in on for with and or how what which when where who why my our your this that do does did i we you it as at by from".split())

def _chunks():
    out = []
    for f in glob.glob(os.path.join(ROOT, "SA_*.md")) + [os.path.join(ROOT, "Projects", "VISUAL_MEMORY.md")]:
        try: text = open(f, encoding="utf-8").read()
        except OSError: continue
        name = os.path.basename(f)
        for c in re.split(r"\n(?=## )", text):
            c = c.strip()
            if len(c) > 40: out.append((name, c))
    return out

def _retrieve(q, k=6, budget=6000):
    words = [w for w in re.findall(r"[a-z0-9']+", q.lower()) if w not in STOP]
    scored = []
    for name, c in _chunks():
        cl = c.lower()
        s = sum(cl.count(w) for w in words)
        if s: scored.append((s, name, c))
    scored.sort(key=lambda x: -x[0])
    picked, used, srcs = [], 0, []
    for s, name, c in scored[:k * 3]:
        if used + len(c) > budget: continue
        picked.append(c[:2000]); used += len(c); srcs.append(name)
        if len(picked) >= k: break
    return "\n\n---\n\n".join(picked), sorted(set(srcs))

def ask_llm(q):
    ctx, srcs = _retrieve(q)
    if not ctx:
        return {"answer": "I couldn't find anything about that in the workspace files.", "sources": []}
    prompt = ("You are the assistant for Saad Ahmad (marketing and media production). Answer his question "
              "in 2-4 short, plain-English sentences using ONLY the context below. British English. "
              "If the context doesn't contain the answer, say so plainly.\n\n"
              f"CONTEXT:\n{ctx}\n\nQUESTION: {q}\n\nANSWER:")
    req = urllib.request.Request(OLLAMA, data=json.dumps(
        {"model": LLM, "prompt": prompt, "stream": False, "think": False,
         "keep_alive": "1m"}).encode(), headers={"Content-Type": "application/json"})
    try:
        r = json.loads(urllib.request.urlopen(req, timeout=180).read())
        ans = (r.get("response") or r.get("thinking") or "").strip()
        ans = re.sub(r"<think>.*?</think>", "", ans, flags=re.S).strip()
        return {"answer": ans or "The model returned nothing — try rephrasing.", "sources": srcs}
    except OSError:
        return {"answer": "Ollama isn't running — open the Ollama app, then ask again.", "sources": []}


def brainmap_data():
    """Live snapshot of the 4 agentic layers: applications, routines, memory, skills."""
    import glob as _g, json as _j
    # APPLICATIONS: local MCP servers + app connectors (curated — app side has no readable config)
    apps = []
    try:
        cfg = _j.load(open(os.path.expanduser(
            "~/Library/Application Support/Claude/claude_desktop_config.json")))
        apps += [{"name": k, "kind": "local MCP"} for k in (cfg.get("mcpServers") or {})]
    except Exception:
        pass
    apps += [{"name": n, "kind": "app connector"} for n in
             ("Higgsfield", "Canva", "Claude-in-Chrome", "Computer Use", "Scheduled Tasks", "Ollama (local)")]
    # ROUTINES: scheduled tasks
    routines = []
    for p in sorted(_g.glob(os.path.expanduser("~/.claude/scheduled-tasks/*/SKILL.md"))):
        name = os.path.basename(os.path.dirname(p))
        desc = ""
        for line in open(p, encoding="utf-8", errors="ignore").read().splitlines():
            if line.startswith("description:"):
                desc = line.split(":", 1)[1].strip()[:90]; break
        routines.append({"name": name, "desc": desc})
    # MEMORY: live counts
    notes = len([f for f in _g.glob(os.path.join(ROOT, "*.md"))])
    proj_docs = len(_g.glob(os.path.join(ROOT, "Projects", "**", "*.md"), recursive=True))
    vm = 0
    try:
        vm = open(os.path.join(ROOT, "Projects", "VISUAL_MEMORY.md"), encoding="utf-8").read().count("\n## ")
    except OSError:
        pass
    memory = [
        {"name": "Core brain notes", "count": notes},
        {"name": "Project documents", "count": proj_docs},
        {"name": "Visual memories (qwen)", "count": vm},
        {"name": "Vector index (sa-brain RAG)", "count": 1},
        {"name": "Sessions (continuity)", "count": len(_g.glob(os.path.join(ROOT, "Sessions", "2*")))},
    ]
    # SKILLS: every workspace tool with its one-line purpose
    skills = []
    for p in sorted(_g.glob(os.path.join(HERE, "*.py"))):
        try:
            src = open(p, encoding="utf-8", errors="ignore").read(400)
            doc = src.split('"""')[1].splitlines()[0][:80] if '"""' in src else ""
        except Exception:
            doc = ""
        skills.append({"name": os.path.basename(p), "desc": doc})
    return {"apps": apps, "routines": routines, "memory": memory, "skills": skills}


def vo_running():
    with socket.socket() as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", 7860)) == 0

class H(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=ROOT, **k)

    def log_message(self, *a):  # ponytail: quiet server
        pass

    def end_headers(self):
        # never let the browser cache HTML/CSV — kills stale-page confusion for good
        if self.path.endswith((".html", ".csv", "/")) or self.path in ("", "/brainmap"):
            self.send_header("Cache-Control", "no-store, must-revalidate")
        super().end_headers()

    def _json(self, obj, code=200):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            b = SHELL.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)
        elif self.path == "/api/brief":
            self._json(fresh_brief())
        elif self.path.startswith("/api/ask"):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get("q", [""])[0].strip()
            self._json(ask_llm(q) if q else {"answer": "Type a question first.", "sources": []})
        elif self.path == "/api/run/doctor":
            r = subprocess.run([sys.executable, os.path.join(HERE, "sa_doctor.py")],
                               capture_output=True, text=True, timeout=120)
            self._json({"ok": r.returncode == 0, "out": r.stdout})
        elif self.path == "/api/qa":
            qdir = os.path.join(ROOT, "Projects", "_QA_INBOX")
            files = sorted(os.path.basename(f) for e in ("*.png","*.jpg","*.jpeg","*.webp")
                           for f in glob.glob(os.path.join(qdir, e)))
            rep = ""
            try: rep = open(os.path.join(qdir, "QA_REPORT.md"), encoding="utf-8").read()
            except OSError: pass
            self._json({"files": files, "report": rep})
        elif self.path == "/api/brainmap":
            self._json(brainmap_data())
        elif self.path == "/brainmap":
            b = BRAINMAP.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)
        elif self.path == "/api/vo":
            if not vo_running():
                subprocess.Popen([sys.executable, os.path.join(HERE, "vo_studio.py")],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                 start_new_session=True)
            self._json({"running": vo_running()})
        else:
            super().do_GET()

SHELL = r"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Studio Hub</title>
<style>
:root{--bg:#0a0f0e;--panel:#0d1714;--line:#1c2b27;--ac:#2E7D32;--ac2:#43A047;--tx:#e8efec;--mut:#7f938c}
*{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%}
body{display:flex;background:var(--bg);color:var(--tx);font:15px/1.5 -apple-system,'Avenir Next',Segoe UI,sans-serif;font-feature-settings:"kern" 1}
aside{width:210px;min-width:210px;background:linear-gradient(180deg,#0d1d18,#0a0f0e);border-right:1px solid var(--line);padding:22px 12px;display:flex;flex-direction:column;gap:4px}
aside .brand{font-size:17px;font-weight:700;letter-spacing:-.2px;padding:0 10px 16px}
aside .brand small{display:block;color:var(--mut);font-weight:400;font-size:11px;letter-spacing:.06em;text-transform:uppercase;margin-top:2px}
aside button{all:unset;cursor:pointer;display:flex;align-items:center;gap:10px;padding:10px 12px;border-radius:10px;font-size:14px;color:var(--tx)}
aside button:hover{background:#10201b}
aside button.on{background:rgba(46,125,50,.16);color:var(--ac2);font-weight:600}
aside button:focus-visible{outline:2px solid var(--ac2);outline-offset:2px}
aside .dot{width:8px;height:8px;border-radius:99px;background:var(--mut)}
aside button.on .dot{background:var(--ac2)}
aside .foot{margin-top:auto;color:var(--mut);font-size:11px;padding:0 10px}
main{flex:1;display:flex;flex-direction:column;min-width:0}
iframe{border:0;width:100%;height:100%;flex:1;background:#fff}
#home{padding:40px;max-width:860px;overflow:auto}
#home h1{font-size:24px;letter-spacing:-.3px;margin-bottom:4px}
#home .sub{color:var(--mut);font-size:13px;margin-bottom:26px}
.brief{background:linear-gradient(180deg,#10201b,#0d1714);border:1px solid var(--line);border-left:3px solid var(--ac);border-radius:16px;padding:20px 24px;margin-bottom:22px}
.brief h3{font-size:12px;text-transform:uppercase;letter-spacing:.08em;color:var(--mut);font-weight:600;margin-bottom:10px}
.brief p{font-size:16px;line-height:1.55;margin:6px 0;max-width:65ch;font-variant-numeric:tabular-nums}
.bdot{width:9px;height:9px;border-radius:99px;display:inline-block;margin-right:10px}
.bdot.ok{background:var(--ac2)}.bdot.warn{background:#ffce5a}.bdot.bad{background:#ff6b5e}
.quick{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}
.quick a,.quick button{all:unset;cursor:pointer;background:#0d1714;border:1px solid var(--line);border-radius:12px;padding:16px;font-size:14px;color:var(--tx)}
.quick a:hover,.quick button:hover{border-color:var(--ac)}
.quick small{display:block;color:var(--mut);font-size:12px;margin-top:4px}
#panes>section{display:none;height:100%}
#panes>section.on{display:flex;flex-direction:column}
pre{white-space:pre-wrap;font:13px/1.6 ui-monospace,Menlo,monospace;padding:24px;overflow:auto;color:var(--tx)}
.toolbar{padding:14px 24px;border-bottom:1px solid var(--line);display:flex;gap:10px;align-items:center}
.toolbar input{background:#0d1714;border:1px solid var(--line);border-radius:10px;padding:9px 14px;color:var(--tx);font-size:14px;width:320px}
.toolbar input:focus{outline:2px solid var(--ac);border-color:transparent}
.toolbar button{all:unset;cursor:pointer;background:rgba(46,125,50,.16);color:var(--ac2);padding:9px 16px;border-radius:10px;font-size:13px;font-weight:600}
.toolbar button:focus-visible{outline:2px solid var(--ac2);outline-offset:2px}
.ask{display:flex;gap:10px;margin-bottom:22px}
.ask input{flex:1;background:#0d1714;border:1px solid var(--line);border-radius:12px;padding:13px 16px;color:var(--tx);font-size:15px}
.ask input:focus{outline:2px solid var(--ac);border-color:transparent}
.ask button{all:unset;cursor:pointer;background:var(--ac);color:#fff;font-weight:600;padding:0 22px;border-radius:12px;font-size:14px}
.ask button:focus-visible{outline:2px solid var(--ac2);outline-offset:2px}
#answer p{font-size:16px;line-height:1.55;margin:6px 0;max-width:65ch}
#answer .src{color:var(--mut);font-size:12px;margin-top:8px}
@media(max-width:760px){aside{width:64px;min-width:64px}aside .brand,aside button span,aside .foot{display:none}}
</style></head><body>
<aside>
  <div class="brand">Studio Hub<small>runs locally</small></div>
  <button data-t="home" class="on"><i class="dot"></i><span>Home</span></button>
  <button data-t="vo"><i class="dot"></i><span>VO Studio</span></button>
  <button data-t="prompts"><i class="dot"></i><span>Prompts</span></button>
  <button data-t="toolbox"><i class="dot"></i><span>Toolbox</span></button>
  <button data-t="qa"><i class="dot"></i><span>QA Inbox</span></button>
  <button data-t="activity"><i class="dot"></i><span>Activity</span></button>
  <button data-t="health"><i class="dot"></i><span>Health</span></button>
  <div class="foot">Runs locally; the VO Studio tab sends typed text to Microsoft&rsquo;s online voices.</div>
</aside>
<main id="panes">
  <section data-p="home" class="on"><div id="home">
    <h1 id="hi">Welcome back, Saad</h1><div class="sub" id="date"></div>
    <form id="askf" class="ask" autocomplete="off">
      <input id="askq" placeholder="Ask anything &mdash; &ldquo;what did we decide about the intro music?&rdquo;, &ldquo;which videos are still in review?&rdquo;" aria-label="Ask anything">
      <button type="submit">Ask</button>
    </form>
    <div id="askout" class="brief" style="display:none"><h3>Answer</h3><div id="answer"></div></div>
    <div class="brief"><h3>Today&rsquo;s brief</h3><div id="brief"><p style="color:var(--mut)">Loading&hellip;</p></div></div>
    <div class="quick">
      <button onclick="go('toolbox')">Open toolbox<small>every tool, one line each</small></button>
      <button onclick="go('activity')">Recent activity<small>the work log, filterable</small></button>
      <button onclick="go('health')">Health check<small>is everything still wired up?</small></button>
    </div>
  </div></section>
  <section data-p="vo"><iframe title="VO Studio" data-vo="1"></iframe></section>
  <section data-p="prompts">
    <div class="toolbar"><input id="pq" placeholder="Filter prompts&hellip;" aria-label="Filter prompts"></div>
    <pre id="prompts">Loading&hellip;</pre>
  </section>
  <section data-p="toolbox">
    <div class="toolbar"><input id="tq" placeholder="Filter tools&hellip;" aria-label="Filter tools"><span style="color:var(--mut);font-size:12px">Just ask Claude in plain words &mdash; it runs these for you.</span></div>
    <div id="toolbox" style="padding:10px 24px;overflow:auto"></div>
  </section>
  <section data-p="qa">
    <div class="toolbar"><span style="color:var(--mut);font-size:13px">Drop generated images into <b style="color:var(--tx)">Projects/_QA_INBOX</b> &mdash; checked nightly at 4am. PASS = safe to spend credits.</span></div>
    <div id="qafiles" style="padding:14px 24px 0"></div><pre id="qareport"></pre>
  </section>
  <section data-p="activity">
    <div class="toolbar"><input id="aq" placeholder="Filter activity&hellip;" aria-label="Filter activity"></div>
    <pre id="activity">Loading&hellip;</pre>
  </section>
  <section data-p="health">
    <div class="toolbar"><button onclick="doctor(this)">Run health check</button></div>
    <pre id="health">Press &ldquo;Run health check&rdquo;.</pre>
  </section>
</main>
<script>
const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
$("#date").textContent=new Date().toLocaleDateString("en-GB",{weekday:"long",day:"numeric",month:"long",year:"numeric"});
function go(t){
  $$("aside button").forEach(b=>b.classList.toggle("on",b.dataset.t===t));
  $$("#panes>section").forEach(s=>s.classList.toggle("on",s.dataset.p===t));
  if(t==="qa")loadQA();
  const fr=$(`#panes>section[data-p="${t}"] iframe`);
  if(fr&&!fr.src){
    if(fr.dataset.vo){fetch("/api/vo").then(r=>r.json()).then(()=>setTimeout(()=>fr.src="http://localhost:7860",1500));}
    else fr.src=fr.dataset.src;
  }
}
$$("aside button").forEach(b=>b.onclick=()=>go(b.dataset.t));
fetch("/api/brief").then(r=>r.json()).then(L=>{
  $("#brief").innerHTML=L.map(b=>`<p><span class="bdot ${b.tone}"></span>${b.text}</p>`).join("");
});
let PROMPTS="";
fetch("/SA_PROMPTS.md").then(r=>r.text()).then(t=>{PROMPTS=t;$("#prompts").textContent=t;});
$("#pq").oninput=e=>{
  const q=e.target.value.toLowerCase();
  $("#prompts").textContent=q?PROMPTS.split(/\n(?=#)/).filter(s=>s.toLowerCase().includes(q)).join("\n"):PROMPTS;
};
$("#askf").onsubmit=e=>{
  e.preventDefault();
  const q=$("#askq").value.trim(); if(!q)return;
  $("#askout").style.display="block";
  $("#answer").innerHTML=`<p style="color:var(--mut)">Thinking locally&hellip;</p>`;
  fetch("/api/ask?q="+encodeURIComponent(q)).then(r=>r.json()).then(j=>{
    $("#answer").innerHTML=`<p>${j.answer.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/\n+/g,"</p><p>")}</p>`+
      (j.sources.length?`<div class="src">From: ${j.sources.join(" · ")}</div>`:"");
  }).catch(()=>{$("#answer").innerHTML=`<p>Something went wrong — is the Hub still running?</p>`});
};
// Toolbox: parsed live from INDEX.md tools table (single source of truth)
let TOOLS=[];
fetch("/INDEX.md").then(r=>r.text()).then(t=>{
  TOOLS=t.split("\n").filter(l=>/^\| `Tools\//.test(l)).map(l=>{
    const c=l.split("|").map(s=>s.trim());
    return {name:c[1].replace(/`/g,"").replace("Tools/",""), desc:c[2].replace(/\*\*/g,"").replace(/`/g,"")};
  });
  renderTools("");
});
function renderTools(q){
  $("#toolbox").innerHTML="<table style='width:100%;border-collapse:collapse;font-size:14px'>"+
    TOOLS.filter(t=>(t.name+t.desc).toLowerCase().includes(q)).map(t=>
      `<tr><td style="padding:9px 14px 9px 0;border-bottom:1px solid var(--line);white-space:nowrap;color:var(--ac2);font:600 13px ui-monospace,Menlo,monospace">${t.name}</td>`+
      `<td style="padding:9px 0;border-bottom:1px solid var(--line);max-width:65ch">${t.desc}</td></tr>`).join("")+"</table>";
}
$("#tq").oninput=e=>renderTools(e.target.value.toLowerCase());
// QA inbox
function loadQA(){fetch("/api/qa").then(r=>r.json()).then(j=>{
  $("#qafiles").innerHTML=j.files.length?j.files.map(f=>{
    const tone=f.startsWith("PASS_")?"ok":f.startsWith("FAIL_")?"bad":"warn";
    return `<p style="margin:4px 0;font-variant-numeric:tabular-nums"><span class="bdot ${tone}"></span>${f}</p>`;
  }).join(""):`<p style="color:var(--mut)">Inbox empty &mdash; drop images in and check back tomorrow morning.</p>`;
  $("#qareport").textContent=j.report||"";
});}
// Activity feed = the work log
let WL="";
fetch("/SA_WORKLOG.md").then(r=>r.text()).then(t=>{WL=t;$("#activity").textContent=t;});
$("#aq").oninput=e=>{
  const q=e.target.value.toLowerCase();
  $("#activity").textContent=q?WL.split(/\n(?=## )/).filter(s=>s.toLowerCase().includes(q)).join("\n"):WL;
};
function doctor(btn){btn.textContent="Checking…";fetch("/api/run/doctor").then(r=>r.json())
  .then(j=>{$("#health").textContent=j.out;btn.textContent="Run health check";});}
</script></body></html>"""


BRAINMAP = r"""<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Studio Brain Map</title>
<style>
:root{--bg:#0a0f0e;--tx:#e8efec;--mut:#7f938c;--green:#2E7D32;--blue:#3B82F6;--amber:#F59E0B;--purple:#A78BFA}
*{box-sizing:border-box;margin:0}body{background:var(--bg);color:var(--tx);
font:14px/1.5 -apple-system,'Avenir Next',sans-serif;display:flex;height:100vh;overflow:hidden}
#map{flex:1}aside{width:340px;border-left:1px solid #1c2b27;padding:18px;overflow-y:auto}
aside h2{font-size:15px;margin-bottom:10px}aside li{list-style:none;padding:7px 10px;margin:4px 0;
background:#0d1714;border-radius:8px;font-size:13px}aside li b{display:block}
aside li span{color:var(--mut);font-size:12px}
#legend{position:fixed;top:14px;left:16px;font-size:12px;color:var(--mut)}
#legend b{color:var(--tx);font-size:15px;display:block;margin-bottom:4px}
.dot{display:inline-block;width:9px;height:9px;border-radius:50%;margin:0 5px 0 12px}
</style></head><body>
<div id="legend"><b>🧠 Studio Agentic OS — live map</b>
<span class="dot" style="background:var(--blue)"></span>Applications
<span class="dot" style="background:var(--amber)"></span>Routines
<span class="dot" style="background:var(--green)"></span>Memory
<span class="dot" style="background:var(--purple)"></span>Skills
</div>
<svg id="map"></svg>
<aside><h2 id="side-title">Click a layer or node</h2><ul id="side-list"></ul></aside>
<script>
const COL={apps:"#3B82F6",routines:"#F59E0B",memory:"#2E7D32",skills:"#A78BFA"};
const LABEL={apps:"Applications",routines:"Routines",memory:"Memory",skills:"Skills"};
fetch("/api/brainmap").then(r=>r.json()).then(d=>{
  const svg=document.getElementById("map"),W=svg.clientWidth,H=svg.clientHeight;
  svg.setAttribute("viewBox",`0 0 ${W} ${H}`);
  const cx=W/2,cy=H/2,NS="http://www.w3.org/2000/svg";
  const el=(t,a)=>{const e=document.createElementNS(NS,t);for(const k in a)e.setAttribute(k,a[k]);return e};
  const layers=Object.keys(COL);
  layers.forEach((key,li)=>{
    const items=d[key],base=li*Math.PI/2-Math.PI/4,R=Math.min(W,H)*.36;
    const gx=cx+Math.cos(base)*R*.72,gy=cy+Math.sin(base)*R*.72;
    // hub node per layer
    const hub=el("circle",{cx:gx,cy:gy,r:34,fill:COL[key],opacity:.92,style:"cursor:pointer"});
    hub.onclick=()=>show(key,items);svg.appendChild(el("line",{x1:cx,y1:cy,x2:gx,y2:gy,stroke:"#1c2b27","stroke-width":2}));
    svg.appendChild(hub);
    const t=el("text",{x:gx,y:gy+4,fill:"#04120c","text-anchor":"middle","font-size":"12","font-weight":"800",style:"cursor:pointer"});
    t.textContent=items.length;t.onclick=()=>show(key,items);svg.appendChild(t);
    const lbl=el("text",{x:gx,y:gy+52,fill:"#e8efec","text-anchor":"middle","font-size":"13","font-weight":"700"});
    lbl.textContent=LABEL[key];svg.appendChild(lbl);
    // item nodes fanned around hub
    items.forEach((it,i)=>{
      const a=base+((i/(items.length))-.5)*1.5,r2=R*.72+70+(i%3)*26;
      const x=cx+Math.cos(a)*r2,y=cy+Math.sin(a)*r2;
      svg.appendChild(el("line",{x1:gx,y1:gy,x2:x,y2:y,stroke:COL[key],"stroke-width":.7,opacity:.35}));
      const c=el("circle",{cx:x,cy:y,r:6,fill:COL[key],opacity:.85,style:"cursor:pointer"});
      c.onclick=()=>show(key,[it]);svg.appendChild(c);
      const tt=el("title");tt.textContent=(it.name||"")+(it.count!==undefined?" · "+it.count:"");c.appendChild(tt);
    });
  });
  // core
  svg.appendChild(el("circle",{cx,cy,r:52,fill:"#1B3A4B",stroke:"#2E7D32","stroke-width":3}));
  const core=el("text",{x:cx,y:cy+5,fill:"#fff","text-anchor":"middle","font-size":"15","font-weight":"800"});
  core.textContent="BRAIN";svg.appendChild(core);
  function show(key,items){
    document.getElementById("side-title").textContent=LABEL[key]+" ("+items.length+")";
    document.getElementById("side-list").innerHTML=items.map(it=>
      "<li style='border-left:3px solid "+COL[key]+"'><b>"+(it.name||"")+
      (it.count!==undefined?" — "+it.count:"")+"</b><span>"+(it.desc||it.kind||"")+"</span></li>").join("");
  }
});
</script></body></html>"""

def main():
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), H)
    url = f"http://localhost:{PORT}"
    print(f"Studio Hub -> {url}  (Ctrl-C to stop)")
    if "--no-open" not in sys.argv:
        webbrowser.open(url)
    srv.serve_forever()

if __name__ == "__main__":
    main()
