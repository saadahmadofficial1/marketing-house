# Code-rendered motion graphics: type, fonts, 3D and evidence

How I make motion graphics that are written as code and rendered headlessly – HTML and GSAP pages rendered to video by HyperFrames, every on-screen word cued to the voice-over’s word timestamps – and the craft rules that make them look designed rather than generated: proving the typeface, setting small type, keeping 3D readable, and trusting only rendered frames. The code was written by AI coding agents (Claude Code and Codex) under my direction and review.

The production pipeline built on this, stage by stage, is [hyperframes-brand-tutorials.md](hyperframes-brand-tutorials.md), with a reusable kit in [templates/hyperframes-brand-tutorial/](templates/hyperframes-brand-tutorial/README.md). The tools are [`sa_verify_fonts.py`](../tools/sa_verify_fonts.py) (font proof), [`sa_vo_words.py`](../tools/sa_vo_words.py) (word timings), [`mux_preview.py`](templates/hyperframes-brand-tutorial/mux_preview.py) (review preview, in the template) and [`sa_capcut_build_from_plan.py`](../tools/sa_capcut_build_from_plan.py) (editable CapCut draft); the React alternative is [templates/remotion/](templates/remotion/README.md).

## Status at a glance

| Part | Status | Notes |
|---|---|---|
| Code-rendered modules (HyperFrames/GSAP), word-cued | **Built, awaiting review** | Five modules of 2½–5 minutes rendered for one internal course |
| Font proof (fake face, strict computed-font audit) | **Built, in use** | Run on every render |
| Font identity by text-width measurement | **Built, in use** | A repeatable answer to “is that really the typeface?” |
| Small-size type recipe | **Built, in use** | Measured in the same headless browser that renders |
| Editable CapCut review draft from the edit plan | **Built, in use** | 13 read-back checks |
| Slide deck or screen recording to video in Remotion | **Pilot** | One complete video each; see [templates/remotion/](templates/remotion/README.md) |

## Contents

1. [What “code-rendered” buys](#1-what-code-rendered-buys)
2. [Prove the type is really the type](#2-prove-the-type-is-really-the-type)
3. [Small type in a display face](#3-small-type-in-a-display-face)
4. [Weight by role](#4-weight-by-role)
5. [3D that stays readable](#5-3d-that-stays-readable)
6. [Motion grammar](#6-motion-grammar)
7. [Three directions on one timing](#7-three-directions-on-one-timing)
8. [Rendering and the evidence it leaves](#8-rendering-and-the-evidence-it-leaves)
9. [Finishing in an editor](#9-finishing-in-an-editor)
10. [The earlier pilot: Remotion](#10-the-earlier-pilot-remotion)
11. [Credits](#11-credits)
12. [What isn’t solved](#12-what-isnt-solved)

---

## 1. What “code-rendered” buys

A module is a Python script that writes one HTML page: the scenes as elements, the motion as one paused GSAP timeline, the timing from the voice-over. A renderer plays that timeline frame by frame in headless Chrome and encodes the frames. What that buys over animating by hand:

- **Timing is data.** Every item is cued to a spoken word’s timestamp ([`sa_vo_words.py`](../tools/sa_vo_words.py)), so re-voicing a line re-times its picture automatically, and a cue to a word the voice never says is a build error rather than a sync fault nobody notices.
- **Variants are cheap.** Three different looks were built in parallel on identical timing (section 7).
- **Changes are surgical.** A typeface change across a whole course re-rendered every module with each module’s timing file byte-identical (checked by SHA-256), so the editor’s existing drafts still lined up.
- **Everything is diffable and checkable**: fonts, sizes, cue lists and text can be audited by script before a frame is rendered.

What it costs: the craft does not come free. A page that renders is not a page that reads well, and most of this playbook is about the gap.

## 2. Prove the type is really the type

A brand’s typeface is very often a licensed grotesque – and grotesques look alike. When a font fails to load, the browser falls back to a system sans that is close enough to pass a glance. So “it looks right” is not evidence. Three checks are:

1. **Reference fonts by installed PostScript name** through CSS `local()`; never copy licensed font files into a project. Check every name against the installed list.
2. **Load every declared face in the renderer’s own browser, beside a declared fake face that must fail.** `document.fonts.check()` returns true for a family that was never declared, so a probe for an undeclared fake proves nothing; the fake has to be declared and must report not loaded. One run, on the renderer’s own Chrome: four used faces `check=true / status=loaded`, the declared fake `check=false / status=error`. The production snapshot then reported its fonts loaded, and the rendered frames matched the snapshots to encoder noise.
3. **Strict mode: read the computed font of every element that carries text.** A face named directly in `font-family` never shows up in the `@font-face` check – a stand-in wordmark in a system serif, for instance. Strict mode fails any text element whose first computed family is not a declared face, unless a page deliberately allow-lists it as a wrong example (`<meta name="verify-fonts-allow" content=".bad-example">`).

And one design choice: **make the fallback a serif.** If every check were skipped, a failed load would still show on the frame instead of hiding as a look-alike sans.

### Is it really that typeface? Measure the width

Asked whether a finished video was really set in the brand face, I answered by measurement, not by eye. Draw the same sentence at 72 px with canvas `measureText()` in each candidate face and compare the widths with the face the page uses:

| Face | Width at weight 500 | Width at weight 700 |
|---|---|---|
| The face the video page uses | 1,175.04 px | 1,211.18 px |
| The licensed brand display face | **1,175.04 px** | **1,211.18 px** |
| Helvetica Neue | 1,281.74 px | 1,322.35 px |
| Helvetica / Arial | 1,236.55 px | 1,312.28 px |
| The display face used before the change | 1,296.86 px | 1,361.23 px |

Identical to two decimal places at both weights, and 60–150 px away from every look-alike. A side-by-side of the width test against a rendered frame closed the question. The method works for any “is it really font X?” argument.

## 3. Small type in a display face

Display cuts are drawn for big sizes: tight spacing that looks right at 88 px makes small text run together. Measured in the rendering browser, the display cut’s word space was **about 0.16 em against about 0.27 em** for the same family’s text cut, and its letters about **4% tighter**. At 36 px and below, card and interface text visibly ran together (“gotthis”, “ajournalist”).

When a brand rules that video uses the display cut only (the text cut being kept for documents), small text needs opening up. The recipe:

**Type tokens, resolved per element.** Set the spacing as inherited custom properties and apply them through one low-specificity rule:

```css
#root { --ls: .015em; --ws: .07em; }
:where(#root *:not(svg, svg *)) { letter-spacing: var(--ls); word-spacing: var(--ws); }
.t-small { --ls: .025em; --ws: .08em; }   /* text at or under ~26 px */
.t-mid   { --ls: .008em; --ws: .05em; }   /* 38–54 px lines at z = 0 */
/* headlines, questions and stamps keep their own explicit values */
```

**The trap this avoids:** `word-spacing: .08em` set directly on the root resolves **once**, against the root’s 16 px, and every child inherits about 1.3 px – so a comment claiming it widened headline word space was simply wrong. Custom properties inherit unresolved, so each element resolves the em against its own size.

**Values that held up**, per role:

| Text | Size | Tracking | Word space | Weight note |
|---|---|---|---|---|
| Subtitles | 38 px | +.016 em | .06 em | regular |
| Chips | 36 px | +.016 em | .06 em | regular |
| Card and tile labels | 34–36 px | +.012 to +.014 em | .05 em | medium |
| Card titles | 35 px | +.008 em | – | medium |
| Small labels, tags | ≤ 26 px | +.02 to +.025 em | .06–.08 em | medium on dark grounds |
| Uppercase kickers | 26–30 px | .12–.13 em | – | trailing tracking compensated |
| Codes on white cards | 24 px | .09 em | – | regular: medium competed with the card title |
| Tags on dark | 24 px | .06 em | .06 em | medium, colour alpha lowered to .72 so they stay quiet |

**Uppercase kickers** carry tracking after their last letter too, which pushes centred lines off centre and makes padding look uneven. Take it back: `margin-right` (or `padding-right`) minus the tracking, or padding on the left of a centred line.

**Weight steps on dark grounds.** A 38 px closing subtitle on a deep-coloured ground looked thin in regular and went to medium; it still sat clearly under the 88 px bold line above it. A footer line over the busy dark backdrop got the same step.

**Reflow by hand.** Extra tracking pushed one card title onto three lines; an explicit break after its first phrase and 10 px less padding fixed it. Breaks go at natural phrases; names are never split. All four lines of one card set were made to break the same way so the set reads as one. Every line and chip row was measured before and after, so “nothing re-wrapped” was a measurement.

## 4. Weight by role

The weights are decided by what the text is doing, once, and then applied everywhere:

| Text | Weight |
|---|---|
| Titles and big statements | Bold |
| The highlight word inside a title | Bold, in the accent colour |
| Subtitles and secondary lines | Regular |
| On-screen sentences that match the voice | Regular |
| Small labels, chips, tags, kickers, card labels | Medium |
| Stamps (“NO”, “ALWAYS.”) | Bold |
| Captions | Medium |
| Not used unless asked | Light, Black, any italic |

A title and its subtitle are **never both bold**: the pair is a bold title over a regular subtitle, or a medium module number beside a regular course name.

## 5. 3D that stays readable

- **One continuous world.** A backdrop of patterned shards at several depths, in a 1,600 px perspective. At every scene change the camera **pushes through it** – z from 0 to 340 over the boundary, easing in and out, with a few degrees of yaw – then drifts back inside the scene. The viewer reads that as a camera move, not a cut.
- **Readable text lands flat at z = 0, facing the camera.** Things may arrive from depth, swing, fan out or fold, but anything the viewer must read ends square to the lens.
- **Scenes leave by rushing past the camera** (z to 620, fading, in the last 0.35 s) while the backdrop push carries on.

### The 3D z-sort trap

In a `transform-style: preserve-3d` card that has its own background, a child animated in **from negative z sorts behind the card face**. Its fade-in is invisible, and the item simply pops in about half a second late. Meanwhile GSAP and `getBoundingClientRect()` both report its opacity rising on schedule, so every DOM-based check passes.

The fix: children of a backgrounded 3D card enter from **z > 0** and settle onto the card, or animate on **y** only. The lesson is bigger than the fix: **only rendered frames are evidence of what the viewer sees.** The DOM describes intent.

## 6. Motion grammar

- **One movement per beat.** A reviewer stopped on a moment where an elastic bounce with a double wobble and a sentence fading in all happened together, so two transitions fired in one beat. It became one `back.out` settle, and the sentence now lands on its word after the motion has finished.
- **No springs and no wobbles.** Eases are `power3.out` for arrivals, `power3.inOut` for camera pushes, `expo.out` for masked headline reveals.
- **Text arrives after motion settles.** In the template, a card swings in over 0.8 s and its text rises 0.6 s later.
- **One cross-fade, one start.** A merge of two layers originally used two fades with different starts; it is now one 0.7 s cross-fade where everything leaves and arrives together.
- **Transitions are baked into the render.** The finished picture is one clip in the editor, so editor transitions would have nothing to attach to; everything inside a chapter is in-frame motion.

## 7. Three directions on one timing

For the first module, three agents each forked the builder and designed a different picture on **identical voice and timing**:

| Direction | Look |
|---|---|
| Kinetic type | full-frame type, colour-block cuts, words colliding on the beat |
| 3D depth | the camera flies through layered planes; a two-door split opens and closes on a seam |
| Line system | lines drawn from the brand’s own mark drive every transition; chapter numerals; an editorial grid |

Because the timing core was shared, any of the three could replace the picture in the same editor draft, and the choice was made by watching all three. The review of the three became standing minimums: **at least 120 px of side padding** everywhere, and minimum text sizes of **36 px for list items, 34 px for small headings and 32 px for labels**. It also caught a closing subtitle that did not match its voice line word for word, which breaks the rule that the screen says what the voice says.

## 8. Rendering and the evidence it leaves

- **Renderer.** HyperFrames (CLI 0.8.91 here, which needs Node 22 or newer) plays the timeline in headless Chrome and encodes with ffmpeg. A wrapper ran it on Node 22 without changing the system default, with its skills sync and cloud vision switched off.
- **Speed.** About 70 s for a flat 2½-minute module and about 2 min 40 s for the 3D version, on an Apple-silicon laptop.
- **A full disk.** Four parallel capture workers wrote about 4.6 GB of temporary frames and failed on a nearly full disk. Streaming capture (`HF_CAPTURE_PARALLEL_STREAM=true`) kept four workers without the frame files; a single worker streams straight into the encoder.
- **A short viewport.** Headless Chrome’s `--window-size` gives a viewport shorter than the window, so stills taken that way lose their bottom edge. Render taller and crop from the top; a centre crop cuts the top instead.
- **What every render leaves behind:** lint with 0 errors; 35–42 snapshot stills inspected per module, plus native-size crops of every small label; rendered frames compared with those snapshots (about 46 dB PSNR, encoder noise); a dead-frame scan counting edges every 0.5 s with **no run of 1 s or more** of an empty frame under the voice; the font proof (section 2); and the module’s timing file hash, unchanged unless the timing was meant to change.

## 9. Finishing in an editor

A code render is not the deliverable; an **editable** draft is. The picture, a separate end frame, one voice clip per line, the music bed and the captions are written into a new CapCut project from the module’s edit plan by [`sa_capcut_build_from_plan.py`](../tools/sa_capcut_build_from_plan.py), with 13 read-back checks and the donor project hash-checked untouched. The full track layout and the checks are in [hyperframes-brand-tutorials.md](hyperframes-brand-tutorials.md#11-hand-off-to-an-editable-capcut-draft); how CapCut files are written safely is in [capcut-draft-format.md](capcut-draft-format.md). The review preview that goes out first ([`mux_preview.py`](templates/hyperframes-brand-tutorial/mux_preview.py)) keeps the voice detached in exactly the same way, with the music about 14 dB under it.

## 10. The earlier pilot: Remotion

Before HyperFrames, the first fully code-rendered videos were made in Remotion, through an open-source agentic video project’s Remotion composer:

- **A slide deck to a narrated film.** A 34-slide deck became a 5 min 33 s film at 1920 × 1080, 30 fps: one slide and one voice line per scene, 0.7 s of air after each line, a 1.00 → 1.04 push-in, fades, and an end card. It was rendered and checked end to end; it remained a pilot.
- **A screen walkthrough recreated in code.** Seven scenes and 50.9 s: voice per scene, lower-thirds, burned-in captions, fades, title cards for the two steps the recording did not show, and a 112% zoom that kept a test address out of frame. It rendered on the CPU with no AI model involved.

Both templates are published in [templates/remotion/](templates/remotion/README.md). What carried forward: size every scene from the **measured** voice length; keep the scenes manifest next to the composition (one pilot could not be re-rendered without it); and count exported files before trusting an export (one slide app exported nothing and reported nothing).

## 11. Credits

- [HyperFrames](https://github.com/heygen-com/hyperframes) by HeyGen (Apache 2.0) – HTML compositions rendered to video through headless Chrome and ffmpeg.
- [GSAP](https://gsap.com) – the animation timeline; check its current licence terms for your use.
- [Remotion](https://www.remotion.dev) – React video; it has its own licence, and companies above a size threshold need a company licence.
- faster-whisper – local word timestamps.
- The typefaces are the brand owner’s licensed fonts, referenced as installed and never redistributed.

## 12. What isn’t solved

- **The reviewer’s eye is still the last check.** The checks prove the fonts, the timing, the cues and the frames; they do not prove the module is good.
- **Captions in the editor** do not yet use the brand face; that needs the licensed desktop font installed where the editor can see it.
- **Music level changes** inside the editor draft are left for a person to keyframe.
- **A short headless viewport** is worked around, not fixed: every still is rendered tall and cropped.

---

**Related:** [hyperframes-brand-tutorials.md](hyperframes-brand-tutorials.md) · [templates/hyperframes-brand-tutorial/](templates/hyperframes-brand-tutorial/README.md) · [templates/remotion/](templates/remotion/README.md) · [training-video-production.md](training-video-production.md) · [capcut-draft-format.md](capcut-draft-format.md) · [fish-audio-voice-cloning.md](fish-audio-voice-cloning.md)
