# Brand tutorial videos with HyperFrames: from script to certificate

How I make short, voice-led tutorial modules for a brand – an animated picture written as code, every on-screen word landing on its spoken beat, finished as an editable CapCut draft and closed with a knowledge check and a certificate. This is the stage-by-stage method, the numbers it runs on and the traps it hit; the code was written by AI coding agents (Claude Code and Codex) under my direction and review.

Everything here is reusable for any brand: the brand-agnostic kit is [templates/hyperframes-brand-tutorial/](templates/hyperframes-brand-tutorial/README.md) (generator, example brand “Acme”, example module, quiz, certificate). The production tools it was generalised from are [`sa_vo_words.py`](../tools/sa_vo_words.py), [`sa_verify_fonts.py`](../tools/sa_verify_fonts.py) and [`sa_capcut_build_from_plan.py`](../tools/sa_capcut_build_from_plan.py), and the review-preview muxer is published in its template form, [`mux_preview.py`](templates/hyperframes-brand-tutorial/mux_preview.py); the type, font and 3D craft behind it is in [code-rendered-motion-graphics.md](code-rendered-motion-graphics.md).

## Status at a glance

| Part | Status | Notes |
|---|---|---|
| The pipeline below, end to end | **Built, awaiting review** | Used on a multi-module internal course; the course itself stays private |
| Brand-agnostic template | **Built, awaiting review** | Generator, checks, font proof, certificate and preview mux all run on the example module |
| CapCut review draft built from the edit plan | **Built, in use** | 13 read-back checks on every build; the donor project is hash-checked untouched |
| Font proof in headless Chrome | **Built, in use** | Catches the silent fallback that a look-alike sans hides |
| Three creative directions on one timing | **Pilot** | Done once, by three agents in parallel; one direction was chosen for the course |
| Quiz and certificate | **Built, awaiting review** | Three questions per module; every answer is taught inside its module |

## Contents

1. [When to make a tutorial this way](#1-when-to-make-a-tutorial-this-way)
2. [The pipeline in one table](#2-the-pipeline-in-one-table)
3. [Script](#3-script)
4. [Voice](#4-voice)
5. [Word timings](#5-word-timings)
6. [The edit plan and the fixed timing core](#6-the-edit-plan-and-the-fixed-timing-core)
7. [The composition](#7-the-composition)
8. [Render](#8-render)
9. [Prove the fonts](#9-prove-the-fonts)
10. [Review preview](#10-review-preview)
11. [Hand-off to an editable CapCut draft](#11-hand-off-to-an-editable-capcut-draft)
12. [Knowledge check and certificate](#12-knowledge-check-and-certificate)
13. [Changing a finished module](#13-changing-a-finished-module)
14. [Traps](#14-traps)
15. [What isn’t solved](#15-what-isnt-solved)

---

## 1. When to make a tutorial this way

| The brief | Route |
|---|---|
| Teaching a software procedure, step by step | Screen recording, paced and marked: [training-video-production.md](training-video-production.md) |
| An existing slide deck that needs a voice | Slides plus voice in Remotion: [templates/remotion/](templates/remotion/README.md) |
| Brand values, policies in plain words, “how we do things here”, a product explained | **This route**: animated type and simple shapes, written as code, timed to the voice |

The code route earns its keep when the same brand will need many modules: once the brand file and the scene types exist, a new module is a script, a voice-over and a scene list. It is the wrong tool for anything that should show the real product on screen.

The house style it inherits came from reviewers’ corrections on earlier tutorials, and stays the rule:

- **The voice and the on-screen words say the same thing.** A subtitle that paraphrased its line was the first thing caught, every time.
- **A title sits above a smaller subtitle**; the two are never both bold.
- **Short lists are centred words or chips, never bullets.**
- **Text-light scenes of about 8 seconds**, slow fades, and music that can restart at a section change.
- **Each module stands alone.** No “in the next video” line, because each module ships with its own quiz.

## 2. The pipeline in one table

| # | Stage | In | Out | Tool | The check that gates it |
|---|---|---|---|---|---|
| 1 | Script | brief and source documents | one sentence per line | – | audited against the sources; captions ≤ 46 characters |
| 2 | Voice | lines | one clip per line | cloned voice ([fish-audio-voice-cloning.md](fish-audio-voice-cloning.md)) | words heard back; speed matched to approved audio |
| 3 | Word timings | clips + lines | `words.json` | [`vo_words.py`](templates/hyperframes-brand-tutorial/vo_words.py) | one clip per line; real durations |
| 4 | Edit plan | words + scene list | voice starts, scene windows, captions | [`build_module.py`](templates/hyperframes-brand-tutorial/build_module.py) | every cue word is heard; no voice over voice |
| 5 | Composition | plan + brand | `index.html` (HyperFrames/GSAP) | `build_module.py` | text flat at z = 0; nothing below the caption line |
| 6 | Render | composition | silent picture + end frame | HyperFrames CLI | lint clean; rendered frames match snapshots; no dead frames under the voice |
| 7 | Font proof | composition | pass / fail | [`verify_fonts.py`](templates/hyperframes-brand-tutorial/verify_fonts.py) | declared fake face fails; every real face loads |
| 8 | Preview | picture + clips + bed | review MP4 | [`mux_preview.py`](templates/hyperframes-brand-tutorial/mux_preview.py) | music ~14 dB under the voice |
| 9 | CapCut draft | edit plan + media | new editable project | [`sa_capcut_build_from_plan.py`](../tools/sa_capcut_build_from_plan.py) | 13 read-back checks; donor untouched |
| 10 | Quiz and certificate | module | questions + certificate | [`make_certificate.py`](templates/hyperframes-brand-tutorial/make_certificate.py) | every answer taught in the module |

## 3. Script

- **One sentence per line, one clip per line.** Short lines voice better, caption cleanly and can be replaced alone.
- **Write for a 46-character caption.** The caption splitter breaks at punctuation and never ends a phrase on a small word (“the”, “in”, “of”), but a sentence that only just overruns leaves an orphan like “tab.” on a line of its own. Write sentences that split well, or check each line before voicing.
- **Audit the script against its sources before any voice exists.** On the course this was built for, an audit of the first draft against the source documents found one statement that was wrong, eight that were over- or understated, and every section reference out of date – all cheaper to fix in text than in a rendered module. Where the source itself was ambiguous, the question went to the document owner instead of being settled by the writer.
- **Teach every quiz answer inside its module.** Write the knowledge check alongside the script, not after it.
- **Put the visual in the script.** Each line notes the scene it plays over and the words that should appear; that note becomes the scene list in [section 6](#6-the-edit-plan-and-the-fixed-timing-core).

## 4. Voice

The route I use is a cloned voice over an API, one line per clip, chosen take by take – the full method, with its consent rule, is in [fish-audio-voice-cloning.md](fish-audio-voice-cloning.md). The parts that matter to a motion-graphics module:

- **Speed is measured, not chosen.** Match the words per second of narration that was already approved; the speed a voice panel happens to show is where someone started, not where they landed.
- **Three takes of each line**, any take whose words come back wrong is dropped, and the smoothest survivor is kept ([`sa_fishvo.py`](../tools/sa_fishvo.py)).
- **Brand and product names get a pronunciation entry the first time they are wrong**, and every later line inherits the fix.
- **The voice is never sped up to fit the picture.** The picture is built around the voice ([section 6](#6-the-edit-plan-and-the-fixed-timing-core)).

## 5. Word timings

[`vo_words.py`](templates/hyperframes-brand-tutorial/vo_words.py) runs faster-whisper locally on each clip and writes, per line, the clip’s file, its script text, its **real** duration and every word with its start and end:

```json
{"file": "vo/acme_m1/02_use_one_spoon.mp3", "text": "Use one spoon of leaves per cup, and steep for three minutes.",
 "dur": 4.69, "words": [{"w": "Use", "s": 0.0, "e": 0.31}, {"w": "one", "s": 0.37, "e": 0.68}]}
```

Two habits keep this honest:

- **A cue word the voice does not say stops the build.** The generator raises an error instead of guessing a time, because a guessed cue is exactly the sync fault a reviewer feels.
- **Recognisers split and merge words**, especially names. Inside a word-by-word line, an unheard word is placed halfway between its neighbours and reported, so a person can listen to that spot. On the production course the recogniser heard the organisation’s own name as two unrelated words; the line was fine, and only the listen confirmed it.

## 6. The edit plan and the fixed timing core

Before any picture exists, an editor agent writes an **edit plan**: where each voice line starts, which scene plays over it, which word each item lands on, the caption cues, the music and its level changes, and the CapCut track layout. The picture is then built to the plan, never the other way round.

The timing core is a handful of constants, shared by every picture variant of a module:

| Constant | Value | Why |
|---|---|---|
| Title card | 5.0 s (4–5 s) | the title is readable for 3 s before it moves |
| First line | title + 0.2 s | – |
| Gap between lines | **0.9 s** default | a screen has to settle; longer where a scene needs a hold |
| Key line hold | 2.5 s minimum | the line the module exists to teach |
| Hero hold | 3.0 s of near-silence | the one moment the music is pulled right down |
| Tail after the last line | 2.5 s | the final frame lands instead of snapping away |
| End frame | 6.3 s | a fixed length the CapCut builder checks |
| Scene opens before its line | 0.3 s | the picture is ready when the voice starts |
| Item lands before its word | 0.15 s | the same lead as a call-out box |
| Voice speed | 1.0, never sped up | gaps grow instead |

The result on the first module: a storyboard estimate of 2:12 became **2:28** – 4 s of title, 6.3 s of end frame and the comprehension holds. Nothing was sped up to recover it.

Two outputs come from the plan, and both are deliberately boring JSON so any later tool can read them:

- **`<id>_timing.json`** – total, voice starts, scene windows, voice files. Its SHA-256 is the module’s timing identity: a picture re-render that leaves it byte-identical drops straight into the existing CapCut draft.
- **`<id>_edit_plan.json`** – voice placement (line, file, start, duration, gap before), caption cues, music file and level, the ending, and the draft canvas.

**Safe zones**, written into the plan: the logo top-right, fixed, the real vector file and never redrawn; nothing but captions below y = 960 px (the caption’s centre sits about 1,022 px down at CapCut’s y = −0.892); at least 120 px of side padding everywhere.

## 7. The composition

The generator writes one HTML page: a HyperFrames composition (`data-composition-id`, `data-start`, `data-duration` on every scene) with one paused GSAP timeline registered for the renderer. The look is **one continuous 3D world**:

- **A depth backdrop** of line shards at eight depths. At every scene change the camera **pushes through it** (z 0 → 340 over the boundary, easing in and out, with a few degrees of yaw), then drifts back inside the scene: a camera move, not a cut.
- **Items arrive from depth and land flat.** Readable text always ends at z = 0 facing the camera; headlines reveal from a mask, cards swing in from z −1,400, chips from z −500.
- **Every on-screen word is cued to its spoken word.** A `words` item reveals a sentence word by word on the voice’s own timestamps, which is the rule the house style calls “every word on its beat”.
- **One movement per beat.** A reviewer flagged a moment where an elastic bounce, a double wobble and a sentence fading in all happened at once, so it read as two transitions firing in one beat. The fix became the rule: one `back.out` settle, no springs, and text arrives **after** the motion settles.
- **Each scene leaves by rushing past the camera** in its last 0.35 s while the backdrop push carries on, so the eye follows the camera, not a cut.

**Three creative directions, one timing.** For the first module, three designer agents each forked the builder and produced a different picture on identical voice and timing: kinetic full-frame type with colour-block cuts; the 3D depth world; and a line system drawn from the brand’s own mark, with chapter numerals and an editorial grid. Because all three shared the timing core, any of them could drop into the same CapCut draft, and the choice was made by watching, not by imagining. Review of the three set two standing minimums: **at least 120 px of side padding** (one direction let text touch the edge) and **minimum text sizes of 36 px for list items, 34 px for small headings and 32 px for labels** (another went too small to read on a laptop).

**Self-review before anyone else sees it.** The first assembly pass caught a logo overlapping a headline, two words colliding, text running off screen, a dead frame, and three places where the screen text and the voice disagreed – all fixed before the preview went out.

## 8. Render

- HyperFrames renders the page in headless Chrome and encodes with ffmpeg. The CLI version used here (0.8.91) needs **Node 22 or newer**; a wrapper script ran it on Node 22 while the system kept Node 20.
- **Render time** on an Apple-silicon laptop: about 70 s for a flat 2½-minute module, and about 2 min 40 s for the same module in the 3D depth style. Modules ran 2½–5 minutes.
- **Render two files:** the silent picture up to the end of the body, and the 6.3 s end frame on its own, so the end frame can be swapped for the brand’s real outro in the editor.
- **Disk.** Four parallel capture workers need about 4.6 GB of temporary frames. On a nearly full disk, `HF_CAPTURE_PARALLEL_STREAM=true` keeps the four workers and streams frames instead, and a single worker streams straight into the encoder with no frame files at all.
- **Evidence after every render:** lint with 0 errors; the rendered frames compared with the composition’s snapshots (they matched to encoder noise, about 46 dB PSNR); and a **dead-frame scan** that counts edges every 0.5 s and fails any run of 1 s or more with nothing on screen while the voice is speaking.
- **Only rendered frames count as evidence** of what the viewer sees – see the 3D z-sort trap in [code-rendered-motion-graphics.md](code-rendered-motion-graphics.md#the-3d-z-sort-trap).

## 9. Prove the fonts

A brand’s typeface is usually a licensed grotesque that looks very like the sans-serif every system falls back to, so “it looks right” proves nothing. [`verify_fonts.py`](templates/hyperframes-brand-tutorial/verify_fonts.py) loads every declared face in the same headless browser, alongside a **declared fake face that must fail**; a strict mode reads the computed font of every text element. Fonts are referenced by installed PostScript name through CSS `local()` and the files are never copied into a project. The full method, including how a typeface was proved by measuring text widths, is in [code-rendered-motion-graphics.md](code-rendered-motion-graphics.md#2-prove-the-type-is-really-the-type).

## 10. Review preview

[`mux_preview.py`](templates/hyperframes-brand-tutorial/mux_preview.py) lays each voice clip at its planned start under the silent picture, adds the music bed and pads the audio to the picture’s length. At a bed volume of 0.16 the music measured about **14 dB under the voice** (−31.7 against −17.9 LUFS). The preview is for watching, not for delivery: the deliverable is the editable draft.

## 11. Hand-off to an editable CapCut draft

The finishing editor gets a **new** CapCut project, never a patch to an existing one, built from the edit plan by [`sa_capcut_build_from_plan.py`](../tools/sa_capcut_build_from_plan.py). How CapCut projects are written safely is in [capcut-draft-format.md](capcut-draft-format.md).

| Track | Content |
|---|---|
| Picture | the silent render, scale 1, from 0 to the end of the body |
| End frame | the 6.3 s end-frame render, to be swapped for the brand outro; its material type must be *video* |
| Voice-over | one detached clip per line at its planned start, volume 1.0, no overlaps |
| Music | one bed from source 0 at volume 0.03; if the bed is shorter than the module it restarts at a **scene boundary** chosen before it would run out, so it runs to the end without overlapping itself |
| Captions | the plan’s cues: one line each, at most 46 characters, size 5 at y = −0.892, scale 75%, no background band |

**The 13 read-back checks**, run on every build and again on demand:

1. both copies of the project file are byte-identical;
2. one timeline id agrees across the project file, its folder, the project index and the layout file;
3. the draft id is fresh and the draft name matches its folder;
4. every media path exists;
5. no two clips overlap on any track;
6. the header duration equals picture + end frame equals the content end equals the export range;
7. every voice clip sits at its planned start (±0.01 s) with its real measured duration;
8. the music has the planned volume, starts at source 0 and covers the module in the planned segments;
9. the captions are the script’s words, one line each, within the character limit and in the house style;
10. the end frame is a *video* material starting at the picture’s real end;
11. nothing still points at the donor project’s media or ids;
12. the donor project is unchanged (SHA-256);
13. no other project changed; the only new entry is this one.

Around them: the editor must be closed before **every** write (checked each time, stopping if it opens), the target name must be free, the whole projects folder is snapshotted first, and the donor’s proxy-media list – which still named the donor’s own source files – is cleared. Level changes in the music (the title breathing, the hero hold pulled down) are left as notes for the editor to keyframe by hand, because writing CapCut’s keyframe schema from code is not proven.

## 12. Knowledge check and certificate

- **Three questions per module**, written with the script. Each question names the line and the words that teach its answer, and `build_module.py --check` fails if those words are not heard in that line’s voice-over (see [`example/quiz.json`](templates/hyperframes-brand-tutorial/example/quiz.json)).
- **Explanations quote the module**, so a wrong answer sends the learner back to the moment that taught it.
- **The certificate** ([`make_certificate.py`](templates/hyperframes-brand-tutorial/make_certificate.py)) is A4 landscape in the brand’s own type and colours, with `{{learner_name}}`, `{{completion_date}}` and `{{learner_id}}` left for the learning platform or a mail merge. It claims only what the course checked: completion of the modules and their knowledge checks.
- **Rendering it to an image:** headless Chrome’s `--window-size` gives a viewport shorter than the window, so render taller than the page and crop from the **top**; an image tool’s default centre crop cuts the top of the sheet. PDF printing has no such problem.

## 13. Changing a finished module

The course this method was built on changed typeface after it was rendered. Everything was swapped with **no timing change**:

- Each module’s timing file stayed byte-identical (checked by SHA-256), so the existing CapCut drafts still lined up and only the picture files were replaced.
- **Re-measure anything fitted to text after a font change.** Marking boxes drawn round words no longer fitted the new type; all 12 were refitted from the new glyph boxes (`getBBox`).
- **Reflow by hand at natural phrases.** Wider tracking pushed a card title onto three lines; an explicit break after the first phrase and 10 px less padding fixed it. Names are never split across lines.
- **Look for timing bugs while you are in there.** One chip was cued to the *first* “how” in its line, so it landed before the seven chips it belonged with; it now cues to the second.
- Before and after, every line and chip row was measured in the headless browser, so “no line re-wrapped” is a measurement, not a hope.

## 14. Traps

| Trap | What happened | Guard |
|---|---|---|
| Child at negative z inside a 3D card | The item sorted behind the card face: its fade was invisible and it popped in about 0.5 s late, while the browser still reported opacity rising | Card text moves on y only, or enters from z > 0 and settles onto the card; judge only rendered frames |
| Font fallback that looks right | A mistyped installed-font name fell back silently to a look-alike sans | Declared fake face that must fail; deliberately serif fallback; strict computed-font audit |
| `word-spacing` in em on the root | Resolved once against the root’s 16 px and inherited as ~1.3 px, so it never widened anything | Type tokens as custom properties (`--ls`, `--ws`), resolved per element |
| Elastic easing plus a fade in one beat | Read as a glitch | One movement per beat; text lands after motion settles |
| Cue to a repeated word | The chip landed on the first “how”, not the one it belonged to | `nth` on the cue; review the cue list against the script |
| Full disk mid-render | Parallel capture needed ~4.6 GB of frames and failed | Streamed capture; check free space first |
| Short headless viewport | Screenshots cut the bottom of the page | Render taller, crop from the top |
| Donor leftovers | The new draft’s proxy list still named the donor’s 18 source files | Clear it; check no donor id or path survives |
| Two transitions where one was meant | A merge of two layers used two cross-fades with different starts | One cross-fade, one start |
| A plan that drifts from its renders | – | One timing file per module, hashed; a re-render must leave it byte-identical |

## 15. What isn’t solved

- **Music level changes** are left for the editor to keyframe; CapCut’s keyframe schema is not proven for writing from code.
- **The CapCut builder still carries a per-module table** (paths, names, the module’s picture length) and expects a donor project; the template emits the plan it reads, but adding a module there is a manual step.
- **CapCut captions do not yet use the brand face**: they need the licensed desktop font installed where CapCut can see it.
- **The quiz is data, not a player.** It is designed to be loaded into whichever learning platform hosts the course.

---

**Related:** [code-rendered-motion-graphics.md](code-rendered-motion-graphics.md) · [templates/hyperframes-brand-tutorial/](templates/hyperframes-brand-tutorial/README.md) · [templates/remotion/](templates/remotion/README.md) · [fish-audio-voice-cloning.md](fish-audio-voice-cloning.md) · [training-video-production.md](training-video-production.md) · [capcut.md](capcut.md) · [capcut-draft-format.md](capcut-draft-format.md)
