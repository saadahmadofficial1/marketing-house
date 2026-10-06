#!/usr/bin/env python3
"""Live Arabic (Emirati) speech -> English captions. Fully local — it runs on
this computer and uploads nothing. Built for live bilingual events after a
conferencing add-on failed the Gulf-Arabic-to-English test.

  sa_livecaption.py                        # BROWSER APP at localhost:8765 (default)
  sa_livecaption.py --file speech.m4a      # test on a recording (do this first!)
  sa_livecaption.py --selfcheck            # end-to-end check with synthetic Arabic
  sa_livecaption.py --device 1             # terminal mode, no browser
  sa_livecaption.py --list                 # show audio inputs

App mode: pick the input, press Start. /view is the clean full-screen page for
the guests' screen. Transcript saved to Sessions/livecaption_<date>.txt.
Engine: mlx_whisper on the Apple GPU (run via Tools/venvs/mlx), falling
back to faster-whisper CPU from Tools/venv. Both fully local.
On event day: mixer line feed arrives as a USB audio device.
"""
import argparse, datetime, http.server, json, os, queue, re, subprocess, sys, threading, time

import numpy as np

TOOLS = os.path.dirname(os.path.abspath(__file__))
FFMPEG = os.path.expanduser("~/.local/bin/ffmpeg")
if not os.path.exists(FFMPEG):
    FFMPEG = "ffmpeg"
_EDGE = os.environ.get("EDGE_TTS", "edge-tts")  # only needed for --selfcheck
SR = 16000

# Decoder bias — the names that must come out right at this event. Put the
# host company, brands, venue and VIP guest names here before each event.
EVENT_TERMS = ("Example Company, Example Brand, Example Event, Example Venue, "
               "Speaker Names")

# The prompt alone doesn't stop literal renderings of names: Whisper can translate a
# proper noun word for word. Map known mistranslations back to the correct name here
# (deterministic fixups after translation).
FIXUPS = {
    "the example company": "Example Company",
}


def fix(text):
    for wrong, right in FIXUPS.items():
        text = re.sub(re.escape(wrong), right, text, flags=re.IGNORECASE)
    return text


VIEW = """<!doctype html><meta charset="utf-8"><title>Live captions</title><style>
body{background:#1B3A4B;color:#F5F5F2;font:600 5.5vh/1.35 -apple-system,Helvetica,Arial,sans-serif;
margin:0;height:100vh;display:flex;flex-direction:column;justify-content:flex-end;padding:6vh 7vw;box-sizing:border-box}
#live{min-height:1.5em;opacity:.6;font-weight:400}.done{min-height:1.4em}
.old{opacity:.45;font-size:.6em;font-weight:400}
#tag{position:fixed;top:3vh;right:4vw;font-size:1.8vh;letter-spacing:.2em;color:#B89B5E;font-weight:400}
</style><div id="tag">LIVE TRANSLATION</div>
<div class="old" id="o1"></div><div class="done" id="d"></div><div id="live"></div>
<script>const es=new EventSource('/events');let h=[];
es.onmessage=e=>{const m=JSON.parse(e.data);
if(m.type==='partial'){live.textContent=m.text;return}
if(m.type!=='caption')return;h.push(m.text);live.textContent='';
o1.textContent=h[h.length-2]||'';d.textContent=m.text;};
</script>"""

CONTROL = """<!doctype html><meta charset="utf-8"><title>Live Translation</title><style>
:root{--bg:#1B3A4B;--ivory:#F5F5F2;--sand:#B89B5E}
body{background:var(--bg);color:var(--ivory);font:16px/1.5 -apple-system,Helvetica,Arial,sans-serif;
margin:0;min-height:100vh;padding:5vh 8vw;box-sizing:border-box}
h1{font-family:Georgia,serif;font-weight:400;font-size:34px;margin:0 0 4px}
.k{color:var(--sand);letter-spacing:.18em;font-size:12px;text-transform:uppercase}
.row{display:flex;gap:14px;align-items:center;flex-wrap:wrap;margin:26px 0}
select{background:#234B5E;color:var(--ivory);border:1px solid #2E5C70;border-radius:8px;padding:10px 14px;font-size:15px}
button{border:0;border-radius:8px;padding:12px 26px;font-size:15px;font-weight:600;cursor:pointer}
#start{background:var(--sand);color:var(--bg)}#stop{background:#7A2E2E;color:var(--ivory);display:none}
#status{font-size:14px;opacity:.8}
#caps{margin-top:30px;border-top:1px solid #2E5C70;padding-top:22px;font-size:22px;line-height:1.6;min-height:30vh}
#caps div{margin-bottom:10px}#caps div:last-child{color:#fff;font-weight:600}
a{color:var(--sand)}
.note{font-size:13px;opacity:.55;margin-top:26px;max-width:640px}
</style>
<div class="k">Fully local — runs on this computer, uploads nothing</div>
<h1>Live Translation — Arabic → English</h1>
<div class="row">
  <select id="dev"></select>
  <select id="model"><option value="__DEF__">Recommended (__DEF__)</option>
  <option value="__ALT__">__ALT__</option></select>
  <button id="start">Start</button><button id="stop">Stop</button>
  <span id="status">ready</span>
</div>
<div><a href="/view" target="_blank">Open the guest screen (full-screen this on the caption display)</a></div>
<div id="caps"></div>
<div class="note">A grey draft line appears within ~2 seconds and refines; the finished line locks in when the speaker pauses. Transcript is saved automatically.
On event day, choose the USB audio device carrying the mixer feed — never a room microphone.</div>
<script>
const caps=document.getElementById('caps'),st=document.getElementById('status');
fetch('/devices').then(r=>r.json()).then(d=>{
  dev.innerHTML=d.map(x=>`<option value="${x.i}">${x.name}</option>`).join('');});
start.onclick=async()=>{st.textContent='starting… (model loads ~15s first time)';
  const r=await fetch('/start',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({device:+dev.value,model:model.value})});
  if(!r.ok){st.textContent=await r.text();return}
  start.style.display='none';stop.style.display='inline-block';};
stop.onclick=async()=>{await fetch('/stop',{method:'POST'});
  start.style.display='inline-block';stop.style.display='none';st.textContent='stopped';};
const live=document.createElement('div');live.style.opacity='.55';live.style.fontStyle='italic';
const es=new EventSource('/events');
es.onmessage=e=>{const m=JSON.parse(e.data);
  if(m.type==='status'){st.textContent=m.text;
    if(m.text==='stopped'){start.style.display='inline-block';stop.style.display='none';}return;}
  if(m.type==='partial'){live.textContent=m.text;caps.appendChild(live);return;}
  const d=document.createElement('div');d.textContent=m.text;
  caps.insertBefore(d,live.parentNode===caps?live:null);live.textContent='';
  while(caps.children.length>9)caps.removeChild(caps.firstChild);
  d.scrollIntoView({block:'nearest'});};
</script>"""

clients, history = [], []
APP = {"stop": None, "proc": None, "running": False, "models": {}, "logf": None}


def push(type_, text):
    msg = {"type": type_, "text": text}
    if type_ == "partial":
        print(f"          · {text}", flush=True)
    if type_ == "caption":
        history.append(text)
        stamp = datetime.datetime.now().strftime("%H:%M:%S")
        print(f"[{stamp}] {text}", flush=True)
        if APP["logf"]:
            APP["logf"].write(f"[{stamp}] {text}\n")
            APP["logf"].flush()
    for q in clients:
        q.put(msg)


def list_devices():
    out = subprocess.run([FFMPEG, "-f", "avfoundation", "-list_devices", "true", "-i", ""],
                         capture_output=True, text=True).stderr
    sec = out[out.index("audio devices"):]
    return [{"i": int(m.group(1)), "name": m.group(2).strip()}
            for m in re.finditer(r"\[(\d+)\] (.+)", sec)]


# Engine: Apple-GPU mlx_whisper when this runs in Tools/venvs/mlx (measured on
# the M4 Pro 21 Aug: large-v3 factor 0.17, medium 0.05 — vs 0.85/0.44 on CPU).
# faster-whisper CPU is the fallback so the tool still works from Tools/venv.
try:
    import mlx_whisper
    ENGINE = "mlx"
    MLX_REPO = {"small": "mlx-community/whisper-small-mlx",
                "medium": "mlx-community/whisper-medium-mlx",
                "large-v3": "mlx-community/whisper-large-v3-mlx"}
except ImportError:
    ENGINE = "cpu"
DRAFT_SIZE = "medium" if ENGINE == "mlx" else "small"
DEFAULT_FINAL = "large-v3" if ENGINE == "mlx" else "medium"


def get_model(size):
    if ENGINE == "mlx":
        return size  # mlx_whisper caches models internally, keyed by repo
    if size not in APP["models"]:
        push("status", f"loading {size} model…")
        from faster_whisper import WhisperModel
        # cpu_threads=10: measured on the M4 Pro 21 Aug — default 4 threads gave
        # factor 2.16 (unusable live); 10 threads gives 0.85 large-v3 / 0.44 medium.
        m = WhisperModel(size, device="cpu", compute_type="int8", cpu_threads=10)
        m.transcribe(np.zeros(SR, np.float32), language="ar")  # warm up
        APP["models"][size] = m
    return APP["models"][size]


def reader(proc, chunks, secs):
    """ffmpeg f32le mono 16k on stdout -> numpy chunks of `secs` seconds."""
    need = int(SR * secs) * 4
    buf = b""
    while True:
        data = proc.stdout.read(need - len(buf))
        if not data:
            break
        buf += data
        if len(buf) >= need:
            chunks.put(np.frombuffer(buf, np.float32).copy())
            buf = b""
    if len(buf) > SR:  # trailing partial second(s)
        chunks.put(np.frombuffer(buf, np.float32).copy())
    chunks.put(None)


def pipeline(model, chunks, live=True):
    """Consume chunks until None; returns (lines, busy_seconds, audio_seconds)."""
    full, busy_t, audio_t = [], 0.0, 0.0
    while True:
        chunk = chunks.get()
        if chunk is None:
            return full, busy_t, audio_t
        # ponytail: fixed windows, so a word can split at a boundary; VAD-aligned
        # windows are the upgrade if it bothers anyone in testing
        if live and chunks.qsize() > 2:  # falling behind — drop rather than lag
            push("status", "listening (dropping backlog to stay live)")
            while chunks.qsize() > 1:
                chunks.get()
        t0 = time.time()
        text = translate(model, chunk)
        busy_t += time.time() - t0
        audio_t += len(chunk) / SR
        if text:
            push("caption", text)
            full.append(text)


def translate(model, audio, glossary=True):
    # glossary=False for drafts: the bias makes the small model hallucinate
    # glossary phrases into speech that never said them (seen live 21 Aug);
    # finals carry the glossary and the fixups, which is where names matter.
    prompt = EVENT_TERMS if glossary else None
    if ENGINE == "mlx":
        r = mlx_whisper.transcribe(audio, path_or_hf_repo=MLX_REPO[model],
                                   task="translate", language="ar",
                                   condition_on_previous_text=False,
                                   initial_prompt=prompt)
        return fix(r["text"].strip())
    segs, _ = model.transcribe(audio, task="translate", language="ar",
                               vad_filter=True, beam_size=1,
                               condition_on_previous_text=False,
                               initial_prompt=prompt)
    return fix(" ".join(s.text.strip() for s in segs).strip())


def stream_loop(draft_model, final_model, chunks):
    """Two-tier streaming: a fast draft line every ~2s while someone speaks,
    a considered final line committed when they pause (or at the 12s cap).
    Saad's spec, 21 Aug: a draft within about two seconds, and a final line only once
    the sentence has been understood."""
    SILENCE_RMS = 0.0035   # ponytail: fixed threshold, fine on a clean mixer feed;
    QUIET_SECS = 0.8       # noisy-room auto-calibration is the upgrade if needed
    CAP_SECS = 12
    cur = np.zeros(0, np.float32)
    quiet, spoke, last_draft_len = 0.0, False, 0
    finals = queue.Queue()

    def final_worker():
        while True:
            audio = finals.get()
            if audio is None:
                return
            text = translate(final_model, audio)
            if text:
                push("caption", text)
    ft = threading.Thread(target=final_worker, daemon=True)
    ft.start()

    while True:
        chunk = chunks.get()
        if chunk is None:
            if spoke and len(cur):
                finals.put(cur)
            finals.put(None)
            ft.join()
            return
        rms = float(np.sqrt(np.mean(chunk ** 2)))
        cur = np.concatenate([cur, chunk])
        if rms < SILENCE_RMS:
            quiet += len(chunk) / SR
        else:
            quiet, spoke = 0.0, True

        end = spoke and (quiet >= QUIET_SECS or len(cur) >= SR * CAP_SECS)
        if end:
            finals.put(cur)
            cur = np.zeros(0, np.float32)
            quiet, spoke, last_draft_len = 0.0, False, 0
        elif not spoke and len(cur) > SR * 2:
            cur = cur[-SR:]          # rolling silence — keep only the last second
        elif spoke and len(cur) - last_draft_len >= SR * 2:
            last_draft_len = len(cur)
            text = translate(draft_model, cur[-SR * 6:], glossary=False)  # last ≤6s
            if text:
                push("partial", text + " …")


def worker(device, size):
    try:
        draft = get_model(DRAFT_SIZE)  # fast rough drafts (~2s cadence)
        final = get_model(size)        # the considered line that gets committed
        proc = subprocess.Popen(
            [FFMPEG, "-f", "avfoundation", "-i", f":{device}",
             "-ar", str(SR), "-ac", "1", "-f", "f32le", "pipe:1"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        APP["proc"] = proc
        time.sleep(0.7)
        if proc.poll() is not None:
            push("status", "could not open that input — check microphone permission "
                           "(System Settings → Privacy → Microphone → Terminal)")
            APP["running"] = False
            return
        chunks = queue.Queue()
        threading.Thread(target=reader, args=(proc, chunks, 0.5), daemon=True).start()
        push("status", "listening")
        stream_loop(draft, final, chunks)
    except Exception as e:
        push("status", f"error: {e}")
    finally:
        APP["running"] = False
        push("status", "stopped")


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def _send(self, body, ctype="text/html; charset=utf-8", code=200):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.end_headers()
        self.wfile.write(body.encode() if isinstance(body, str) else body)

    def do_GET(self):
        if self.path == "/events":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            q = queue.Queue()
            clients.append(q)
            try:
                for line in history[-3:]:
                    self.wfile.write(
                        f"data: {json.dumps({'type': 'caption', 'text': line})}\n\n".encode())
                self.wfile.flush()
                while True:
                    self.wfile.write(f"data: {json.dumps(q.get())}\n\n".encode())
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                clients.remove(q)
        elif self.path == "/devices":
            self._send(json.dumps(list_devices()), "application/json")
        elif self.path == "/view":
            self._send(VIEW)
        else:
            alt = "medium" if DEFAULT_FINAL == "large-v3" else "large-v3"
            self._send(CONTROL.replace("__DEF__", DEFAULT_FINAL).replace("__ALT__", alt))

    def do_POST(self):
        if self.path == "/start":
            if APP["running"]:
                self._send("already running", code=409)
                return
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"] or 0)) or "{}")
            if "turbo" in body.get("model", ""):
                self._send("turbo cannot translate", code=400)
                return
            APP["running"] = True
            threading.Thread(target=worker,
                             args=(int(body.get("device", 0)),
                                   body.get("model", DEFAULT_FINAL)),
                             daemon=True).start()
            self._send("ok")
        elif self.path == "/stop":
            if APP["proc"]:
                APP["proc"].kill()
            self._send("ok")
        else:
            self._send("?", code=404)


def serve(port):
    # localhost only by default (/start and /stop have no auth). To show /view on
    # another machine on the same network, set LIVECAPTION_HOST=0.0.0.0.
    host = os.environ.get("LIVECAPTION_HOST", "127.0.0.1")
    http.server.ThreadingHTTPServer((host, port), Handler).serve_forever()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--device", type=int)
    ap.add_argument("--file")
    ap.add_argument("--selfcheck", action="store_true")
    ap.add_argument("--model", default=DEFAULT_FINAL)
    ap.add_argument("--stream", action="store_true",
                    help="with --file: exercise the live draft/commit path")
    # 8s window: whisper pads every call to 30s, so the encoder cost is nearly
    # fixed — bigger windows waste less of it. 8s keeps captions timely enough.
    ap.add_argument("--window", type=int, default=8)
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args()

    if a.list:
        for d in list_devices():
            print(f"[{d['i']}] {d['name']}")
        return
    if "turbo" in a.model:
        ap.error("large-v3-turbo cannot translate (distilled without the translate "
                 "task — verified 21 Aug: it returns Arabic). Use large-v3 or medium.")

    logp = os.path.join(os.path.dirname(TOOLS), "Sessions",
                        f"livecaption_{datetime.date.today()}.txt")
    os.makedirs(os.path.dirname(logp), exist_ok=True)
    APP["logf"] = open(logp, "a", encoding="utf-8")

    if a.selfcheck:
        wav = "/tmp/sa_lc_check.mp3"
        subprocess.run([_EDGE, "--voice", "ar-AE-FatimaNeural", "--text",
                        "\u0645\u0631\u062d\u0628\u0627 \u0628\u0643\u0645 \u062c\u0645\u064a\u0639\u0627 \u0641\u064a \u0641\u0639\u0627\u0644\u064a\u0629 \u0627\u0644\u064a\u0648\u0645",  # Arabic for "Welcome, everyone, to today's event"
                        "--write-media", wav], check=True, capture_output=True)
        a.file = wav

    if a.file or a.device is not None:  # terminal modes (unchanged behaviour)
        threading.Thread(target=serve, args=(a.port,), daemon=True).start()
        print(f"captions page: http://localhost:{a.port}/view")
        print(f"loading whisper {a.model} (local, one-off ~15s)…")
        model = get_model(a.model)
        if a.file:
            cmd = [FFMPEG, "-i", a.file, "-ar", str(SR), "-ac", "1", "-f", "f32le", "pipe:1"]
        else:
            cmd = [FFMPEG, "-f", "avfoundation", "-i", f":{a.device}",
                   "-ar", str(SR), "-ac", "1", "-f", "f32le", "pipe:1"]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        chunks = queue.Queue()
        if a.stream or a.device is not None:  # the same draft/commit path the app uses
            threading.Thread(target=reader, args=(proc, chunks, 0.5), daemon=True).start()
            print("listening — Ctrl-C to stop\n")
            stream_loop(get_model(DRAFT_SIZE), model, chunks)
            return
        threading.Thread(target=reader, args=(proc, chunks, a.window), daemon=True).start()
        full, busy_t, audio_t = pipeline(model, chunks, live=False)
        if a.file:
            rtf = busy_t / max(audio_t, 0.01)
            verdict = ("REALTIME OK" if rtf < 0.9 else
                       "BORDERLINE — will keep up, dropping backlog on dense speech" if rtf < 1.1
                       else "TOO SLOW — use --model medium")
            print(f"\n— done. {audio_t:.0f}s audio in {busy_t:.0f}s ({verdict}, factor {rtf:.2f})")
            print(f"transcript: {logp}")
        if a.selfcheck:
            joined = " ".join(full).lower()
            ok = any(w in joined for w in ("welcome", "event", "today"))
            print("SELFCHECK", "PASS" if ok else f"FAIL — got: {joined!r}")
            sys.exit(0 if ok else 1)
        return

    # default: browser app
    url = f"http://localhost:{a.port}"
    print(f"Live Translation app: {url}   (Ctrl-C quits)")
    if not a.no_browser:
        subprocess.run(["open", url], check=False)
    serve(a.port)


if __name__ == "__main__":
    main()
