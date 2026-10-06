#!/usr/bin/env python3
"""Brand QA gate — catch the recurring slips BEFORE publish.
Checks text (caption/script/SRT) and/or a project folder.

  sa_qa.py --text "caption..."        # check a string
  sa_qa.py --file path.srt            # check a file's text
  sa_qa.py --project "Projects/X"     # check folder: SRT count, etc.
  sa_qa.py --image still.png          # VISION check via local qwen3-vl (ollama)
  sa_qa.py --images folder/           # vision-check every image in a folder

Text flags: American spelling, wrong brand-hashtag case. Vision flags (local,
free, no tokens): visible hands, baked-in text/logos, AI artifacts, warped
faces/jewellery. Exit 0 = clean, 1 = issues found.
"""
import sys, os, re, json, base64, urllib.request

OLLAMA = "http://localhost:11434/api/generate"
# default = newest local vision model; override: SA_VLM=qwen2.5vl:7b sa_qa.py ...
VLM = os.environ.get("SA_VLM", "qwen3-vl:8b")
VISION_PROMPT = (
    "You are a strict QA checker for corporate marketing images. "
    "Inspect the image and answer ONLY with JSON: "
    '{"hands_visible":bool,"baked_text_or_logo":bool,"ai_artifacts":bool,'
    '"warped_face_or_jewellery":bool,"notes":"<one short line>"}. '
    "hands_visible=true if any human hand/fingers are clearly visible. "
    "baked_text_or_logo=true if any written text, watermark or brand logo is rendered inside the image. "
    "ai_artifacts=true for melted shapes, extra limbs, garbled letters, impossible geometry. "
    "warped_face_or_jewellery=true if a face or jewellery item looks distorted."
)

def check_image(path, src=None):
    src = src or os.path.basename(path)
    b64 = base64.b64encode(open(path, "rb").read()).decode()
    req = urllib.request.Request(
        OLLAMA,
        data=json.dumps({"model": VLM, "prompt": VISION_PROMPT,
                         "images": [b64], "stream": False,
                         "format": "json", "think": False, "keep_alive": "1m"}).encode(),
        headers={"Content-Type": "application/json"})
    try:
        resp = json.loads(urllib.request.urlopen(req, timeout=180).read())
        # thinking models (qwen3-vl) may put the JSON in "thinking" with empty "response"
        raw = resp.get("response") or resp.get("thinking") or "{}"
        v = json.loads(raw)
    except Exception as e:
        return [f"[{src}] vision check unavailable ({e}) — is `ollama serve` running with {VLM}?"]
    issues = []
    if v.get("hands_visible"):            issues.append(f"[{src}] HANDS visible — house rule: no hands")
    if v.get("baked_text_or_logo"):       issues.append(f"[{src}] text/logo baked into image — must be added in CapCut")
    if v.get("ai_artifacts"):             issues.append(f"[{src}] AI artifacts detected — {v.get('notes','')}")
    if v.get("warped_face_or_jewellery"): issues.append(f"[{src}] warped face/jewellery — regenerate or real-pixel edit")
    return issues

BRAND_TAG = "#YourBrand"          # the house hashtag, in its one correct case
AMERICAN = {
    "organize":"organise","organized":"organised","organization":"organisation",
    "color":"colour","colors":"colours","personalize":"personalise",
    "personalized":"personalised","center":"centre","centered":"centred",
    "realize":"realise","optimize":"optimise","favorite":"favourite",
    "catalog":"catalogue","program":"programme","defense":"defence",
    "traveler":"traveller","fiber":"fibre","analyze":"analyse",
    "canceled":"cancelled","license":"licence","meter":"metre",
}
def check_text(t, src="text"):
    issues = []
    low = t.lower()
    for us, uk in AMERICAN.items():
        if re.search(rf"\b{us}\b", low):
            issues.append(f"[{src}] American spelling '{us}' -> use '{uk}'")
    # hashtag case
    for m in re.findall(r"#\w+", t):
        if m.lower() == BRAND_TAG.lower() and m != BRAND_TAG:
            issues.append(f"[{src}] hashtag '{m}' -> must be '{BRAND_TAG}'")
    return issues

def check_project(folder):
    issues = []
    srts = [f for f in os.listdir(folder) if f.lower().endswith(".srt")]
    if srts and len(srts) < 4:
        issues.append(f"[project] only {len(srts)} SRT(s) — house rule: deliver 4 "
                      "(one per language, tagline, combined)")
    for f in os.listdir(folder):
        if f.lower().endswith((".srt",".txt")):
            try:
                issues += check_text(open(os.path.join(folder,f)).read(), f)
            except Exception: pass
    return issues

def main():
    args = sys.argv[1:]
    issues = []
    if "--text" in args:
        issues += check_text(args[args.index("--text")+1])
    if "--file" in args:
        p = os.path.expanduser(args[args.index("--file")+1])
        issues += check_text(open(p).read(), os.path.basename(p))
    if "--project" in args:
        issues += check_project(os.path.expanduser(args[args.index("--project")+1]))
    if "--image" in args:
        issues += check_image(os.path.expanduser(args[args.index("--image")+1]))
    if "--images" in args:
        d = os.path.expanduser(args[args.index("--images")+1])
        for f in sorted(os.listdir(d)):
            if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
                issues += check_image(os.path.join(d, f))
    if not any(x in args for x in ("--text","--file","--project","--image","--images")):
        print(__doc__); sys.exit(1)
    if issues:
        print(f"❌ {len(issues)} issue(s):")
        for i in issues: print("  -", i)
        sys.exit(1)
    print("✅ clean — passes brand QA")

if __name__ == "__main__":
    main()
