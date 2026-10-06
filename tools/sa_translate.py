#!/usr/bin/env python3
"""Local SRT translator EN<->AR (FREE — gemma3:4b via Ollama; runs locally and uploads nothing).
  python3 Tools/sa_translate.py subtitles.srt          # EN -> Arabic -> subtitles_ar.srt
  python3 Tools/sa_translate.py subtitles.srt --to en  # Arabic -> English
Keeps all timings; translates text lines only. Review before publishing — it's a draft.
"""
import os, sys, json, re, urllib.request

OLLAMA = "http://localhost:11434/api/generate"
LLM = os.environ.get("SA_LLM", "gemma3:4b")
# comma-separated brand/product names never to translate, e.g. SA_KEEP_TERMS="Acme, Acme Pro"
KEEP = os.environ.get("SA_KEEP_TERMS", "")

def tr(text, target):
    lang = "Modern Standard Arabic (formal, suitable for corporate subtitles)" if target == "ar" else "British English"
    req = urllib.request.Request(OLLAMA, data=json.dumps({
        "model": LLM, "stream": False, "think": False, "keep_alive": "2m",
        "prompt": (f"Translate this subtitle line to {lang}. Keep brand and product names exactly as written"
                   + (f" ({KEEP} — do not translate them)" if KEEP else "")
                   + f". Reply with ONLY the translation, nothing else.\n\n{text}")}).encode(),
        headers={"Content-Type": "application/json"})
    r = json.loads(urllib.request.urlopen(req, timeout=120).read())
    return (r.get("response") or "").strip().strip('"')

def main():
    if len(sys.argv) < 2: sys.exit(__doc__)
    target = "en" if "--to" in sys.argv and "en" in sys.argv[sys.argv.index("--to")+1] else "ar"
    src = os.path.expanduser(sys.argv[1])
    blocks = open(src, encoding="utf-8").read().strip().split("\n\n")
    out_blocks = []
    for b in blocks:
        lines = b.split("\n")
        head = [l for l in lines if l.strip().isdigit() or "-->" in l]
        text = " ".join(l for l in lines if l not in head).strip()
        out_blocks.append("\n".join(head + [tr(text, target) if text else ""]))
        print(f"  {len(out_blocks)}/{len(blocks)}", end="\r")
    out = os.path.splitext(src)[0] + f"_{target}.srt"
    open(out, "w", encoding="utf-8").write("\n\n".join(out_blocks) + "\n")
    print(f"\n✓ {out}")

if __name__ == "__main__":
    main()
