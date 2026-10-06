#!/usr/bin/env python3
"""VO Studio — browser voice-over playground using Microsoft’s online Edge voices.
  python3 Tools/vo_studio.py          # then open http://localhost:7860
Type text, pick a voice, Generate → listen → Download. Free (edge-tts,
no account/subscription). The page is served on 127.0.0.1 only, but every line you
generate is sent to Microsoft’s online Edge read-aloud service, so keep confidential
scripts out. Nothing is saved unless you download it.
"""
import json, os, subprocess, tempfile, urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler

EDGE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    "installs/ppt-master/.venv/bin/edge-tts")
if not os.path.exists(EDGE):
    EDGE = "edge-tts"

KOKORO_PY = os.path.expanduser("~/ThirdParty/vo-engines/kokoro-venv/bin/python3")
KOKORO_DIR = os.path.expanduser("~/ThirdParty/vo-engines")

VOICES = [  # curated: quality voices for corporate work
    # kokoro voices removed 17 Jul — flat prosody raw, choppy when chunked (Saad rejected both)
    ("en-GB-RyanNeural",      "British male — Ryan (our default)"),
    ("en-GB-SoniaNeural",     "British female — Sonia"),
    ("en-GB-ThomasNeural",    "British male — Thomas (deeper)"),
    ("en-GB-LibbyNeural",     "British female — Libby (lighter)"),
    ("en-US-GuyNeural",       "US male — Guy"),
    ("en-US-JennyNeural",     "US female — Jenny"),
    ("en-US-EricNeural",      "US male — Eric (warm)"),
    ("en-US-AriaNeural",      "US female — Aria (news style)"),
    ("en-AU-WilliamNeural",   "Australian male — William"),
    ("en-IN-NeerjaNeural",    "Indian English female — Neerja"),
    ("en-IN-PrabhatNeural",   "Indian English male — Prabhat"),
    ("ar-AE-HamdanNeural",    "Arabic (UAE) male — Hamdan"),
    ("ar-AE-FatimaNeural",    "Arabic (UAE) female — Fatima"),
]

HTML = """<!doctype html><meta charset="utf-8">
<title>VO Studio</title>
<style>
 body{font-family:-apple-system,'Avenir Next',sans-serif;background:#1B3A4B;color:#fff;
      max-width:760px;margin:40px auto;padding:0 20px}
 h1{font-size:22px} h1 b{color:#43A047}
 textarea{width:100%;height:120px;border-radius:10px;border:0;padding:12px;font-size:15px}
 select,button,input[type=range]{font-size:15px;border-radius:8px;border:0;padding:10px}
 button{background:#2E7D32;color:#fff;font-weight:700;cursor:pointer;padding:10px 26px}
 button:disabled{opacity:.5}
 .row{display:flex;gap:10px;align-items:center;margin:14px 0;flex-wrap:wrap}
 audio{width:100%;margin-top:14px}
 a#dl{color:#43A047;font-weight:700;display:none}
 .tip{background:#264d61;border-radius:10px;padding:10px 14px;font-size:13px;line-height:1.5}
 label{font-size:13px;opacity:.85}
</style>
<h1>🎙 <b>VO Studio</b> — free, unlimited takes</h1>
<p><label>Uses Microsoft’s online Edge voices: the text you type is sent to Microsoft. Keep confidential scripts out.</label></p>
<div class="tip">💡 <b>Wrong pronunciation?</b> Spell it how it should SOUND. Try:
 “Siobhan” → “Shi-vawn” · “Worcester” → “Wuss-ter” · “SQL” → “S Q L” (spaces make it spell letters).
 Regenerate as many times as you like — it's free.</div>
<p><textarea id="t" placeholder="Type your voiceover line here…">Welcome to the new expense portal. Let's take a quick tour.</textarea></p>
<div class="row">
 <select id="v">__OPTIONS__</select>
 <label>Speed <input type="range" id="r" min="-30" max="30" value="0" step="5"
        oninput="rl.textContent=this.value+'%'"> <span id="rl">0%</span></label>
 <button id="go" onclick="gen()">Generate ▶</button>
</div>
<audio id="a" controls style="display:none"></audio>
<p><a id="dl" download="voiceover.mp3">⬇ Download this take</a></p>
<script>
async function gen(){
 const b=document.getElementById('go'); b.disabled=true; b.textContent='Generating…';
 try{
  const res=await fetch('/gen',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({text:document.getElementById('t').value,
                         voice:document.getElementById('v').value,
                         rate:document.getElementById('r').value})});
  if(!res.ok){alert(await res.text());return}
  const url=URL.createObjectURL(await res.blob());
  const a=document.getElementById('a'); a.src=url; a.style.display='block'; a.play();
  const dl=document.getElementById('dl'); dl.href=url; dl.style.display='inline';
  dl.download='VO_'+document.getElementById('v').value.replace(/[^A-Za-z0-9_]/g,'_')+'.mp3';
 }finally{b.disabled=false;b.textContent='Generate ▶'}
}
</script>"""

OPTIONS = "".join(f'<option value="{v}">{label}</option>' for v, label in VOICES)


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):  # quiet
        pass

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(HTML.replace("__OPTIONS__", OPTIONS).encode())

    def do_POST(self):
        try:
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            text, voice = body["text"].strip(), body["voice"]
            rate = int(body.get("rate", 0))
            if not text:
                raise ValueError("empty text")
            if voice.startswith("kokoro:"):
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                    out = f.name
                speed = max(0.6, min(1.5, 1.0 + rate / 100.0))
                subprocess.run([KOKORO_PY, os.path.join(KOKORO_DIR, "kokoro_say.py"),
                                text, voice.split(":", 1)[1], str(speed), out],
                               check=True, capture_output=True, timeout=300)
                ctype = "audio/wav"
            else:
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                    out = f.name
                cmd = [EDGE, "--voice", voice, "--text", text, "--write-media", out]
                if rate:
                    cmd += ["--rate", f"{'+' if rate > 0 else ''}{rate}%"]
                subprocess.run(cmd, check=True, capture_output=True, timeout=120)
                ctype = "audio/mpeg"
            data = open(out, "rb").read()
            os.unlink(out)
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            msg = f"generation failed: {e}".encode()
            self.send_response(500)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(msg)


if __name__ == "__main__":
    print("VO Studio → http://localhost:7860   (Ctrl+C to stop)")
    HTTPServer(("127.0.0.1", 7860), H).serve_forever()
