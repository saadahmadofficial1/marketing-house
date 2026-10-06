# HyperFrames brand-tutorial template

A brand-agnostic kit for making short, voice-led tutorial modules for any brand: one Python generator writes a HyperFrames/GSAP composition whose every on-screen word lands on its spoken beat, plus the timing file, captions and edit plan that hand the module to an editable CapCut review draft. The method behind it is in [hyperframes-brand-tutorials.md](../../hyperframes-brand-tutorials.md).

**Status: Built, awaiting review.** The generator, its checks, the font verifier, the certificate and the preview mux all run on the example below. The composition was checked frame by frame in headless Chrome; the HyperFrames render itself is the route the production modules used (CLI 0.8.91, Node 22 or newer). The code was written by AI coding agents under my direction, generalised from a production course whose content stays private.

## What is in the folder

| File | What it does |
|---|---|
| [`build_module.py`](build_module.py) | Module JSON + brand JSON + word timings → HyperFrames project (`index.html`, `hyperframes.json`, `package.json`), `<id>_timing.json`, `<id>_edit_plan.json` and `<id>.srt`. `--check` validates without writing. `--synthetic` lays a module out before any voice exists. |
| [`brand.example.json`](brand.example.json) | The placeholder brand “Acme”: neutral colours, fonts by installed PostScript name, type tokens, motif angle, caption limit, music levels. Swap the values, keep the keys. |
| [`example/module.json`](example/module.json) | A three-line example module (brewing a cup of tea): script lines, a hold, three scenes and every item’s cue word. |
| [`example/words.example.json`](example/words.example.json) | The shape [`vo_words.py`](vo_words.py) produces. This copy is **synthetic** (even spacing at 2.7 words/s) so the example builds with no audio. |
| [`example/quiz.json`](example/quiz.json) | A two-question knowledge check. Each answer names the line and the words that teach it. |
| [`vo_words.py`](vo_words.py) | Word timestamps and real durations for each voice-over clip, locally with faster-whisper. |
| [`verify_fonts.py`](verify_fonts.py) | Proves every declared face loads in headless Chrome, with a declared fake face that must fail; `--strict` checks the computed font of every text element. |
| [`mux_preview.py`](mux_preview.py) | Review preview: silent render + each voice clip at its planned start + an optional music bed. |
| [`make_certificate.py`](make_certificate.py) | A completion certificate in the brand’s type and colours, blank with `{{placeholders}}` or filled; `--pdf` prints A4 landscape. |

## Run the example

```bash
cd playbooks/templates/hyperframes-brand-tutorial
python3 build_module.py example/module.json --brand brand.example.json \
    --words example/words.example.json --check
python3 build_module.py example/module.json --brand brand.example.json \
    --words example/words.example.json --out build/acme_m1
python3 verify_fonts.py --strict build/acme_m1/index.html
cd build/acme_m1 && npm run check && npm run render     # HyperFrames: Node 22+
```

The example builds a 29.76 s module: a 4.9 s title, three content scenes (5.22 s, 6.59 s with a 1 s hold, 6.75 s), and a 6.3 s end frame; six captions, none over 46 characters.

## Make your own module

1. **Brand.** Copy `brand.example.json`. Fonts are named by their **installed PostScript names** and loaded with CSS `local()`: licensed font files are never copied into a project. Keep the fallback a serif, so a failed load shows on the frame instead of passing as a look-alike sans.
2. **Script.** Write `module.json`: one entry in `lines` per voice-over clip, short sentences, captions of at most 46 characters in mind. The on-screen words must say what the voice says.
3. **Voice.** Record or generate one clip per line (see [fish-audio-voice-cloning.md](../../fish-audio-voice-cloning.md) for the cloned-voice route), name them `01_…`, `02_…`, then:
   `python3 vo_words.py --clips vo/<id> --lines lines.txt --out vo/<id>_words.json`
4. **Scenes.** Give every scene its first and last line, a background (`deep`, `paper` or `void`) and its items. Every item names its cue:
   `{"line": 2, "word": "three"}` lands 0.15 s before that word; `{"line": 2, "at": "start"}` lands on the line’s start; add `"nth": 2` for a repeated word.
5. **Build and check.** `--check` fails on any cue word the voice does not say, a caption over the limit, captions that are not the script words, voice over voice, or a quiz answer the module never teaches.
6. **Render, prove the fonts, preview.** `npm run render` in the project folder, `verify_fonts.py --strict`, then `mux_preview.py`.
7. **Hand off to CapCut.** `<id>_edit_plan.json` carries `vo_placement`, `captions.cues`, `music` and `capcut_review_draft` in the shape [`sa_capcut_build_from_plan.py`](../../../tools/sa_capcut_build_from_plan.py) reads. That builder is the production version and still carries its own module table and donor-project settings: add your module there, or copy its approach.
8. **Certificate.** `make_certificate.py brand.json --course "…" --modules N --out certificate.html`.

## Item types

| Type | Moves | Use for |
|---|---|---|
| `kicker` | rises 18 px and fades in, uppercase, tracked | step labels |
| `headline` | masked reveal from below | the scene’s one big statement |
| `sub` | rises 24 px and fades in | a supporting line |
| `words` | **each word appears on its spoken beat** | a sentence the voice is saying right now |
| `chips` | each chip arrives from depth (z −500 → 0) on its word | short lists, never bullets |
| `cards` | the card swings in from z −1,400; its text then rises on y | two to four facts |
| `stamp` | one `back.out` settle, no spring | the closing word of a scene |

Readable text always ends **flat at z = 0**. Card text moves on y only: a child animated from negative z inside a 3D card with its own background sorts behind the card face, so its fade never shows, while the browser still reports its opacity rising.

## Timing constants

`TITLE 5.0 s` · `LEAD 0.2 s` · `GAP 0.9 s` · `TAIL 2.5 s` · `END 6.3 s` · `SCENE_LEAD 0.3 s` · `EXIT 0.35 s` · `CUE_OFFSET −0.15 s` · 1920 × 1080 at 30 fps · nothing below y = 960 except captions. If an editor has already placed the voice, put their starts in `module.json` as `vo_starts` and the generator uses those instead of computing them.

## Credits and licences

[HyperFrames](https://github.com/heygen-com/hyperframes) (HeyGen, Apache 2.0) renders HTML compositions to video through headless Chrome and ffmpeg. [GSAP](https://gsap.com) drives the animation and is loaded from its CDN; check its current licence terms for your use. faster-whisper provides the local word timings. Avenir Next is used only because it ships with macOS; name your own brand’s licensed faces instead.

## Related

- [hyperframes-brand-tutorials.md](../../hyperframes-brand-tutorials.md) – the method, stage by stage
- [code-rendered-motion-graphics.md](../../code-rendered-motion-graphics.md) – font proof, small-size type, 3D traps
- [templates/remotion/](../remotion/README.md) – the React alternative for slide decks and screen walkthroughs
- [training-video-production.md](../../training-video-production.md) – screen-recorded training, the other half of the tutorial work
