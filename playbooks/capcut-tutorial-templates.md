# CapCut tutorial templates: the recipe for Claude
> Use this when the editor asks for a tutorial, walkthrough, feature tour, system explainer, or internal training video.
> These rules come from the editor's top three non-brand tutorial projects. Real project titles, products and people are withheld; each master is named by what it is. Brand films are separate; use the [style DNA](style-dna.md) for those.
> Companion pages: [the three masters at a glance](capcut-tutorial-masters.md) · [CapCut hub](capcut.md) · [CapCut draft format](capcut-draft-format.md) · [CapCut live eyes](capcut-live-eyes.md)

## The Three Master References

| Reference | What the original was | Best used for | Final/export window |
|---|---|---|---|
| Master 1: Short walkthrough | A one-minute walkthrough of an internal web tool | Short screen-record walkthrough | `00:00:00.967` to `00:01:02.600` / 61.6s |
| Master 2: Feature tour | A feature tutorial for a business phone app | Dense app feature tutorial | `00:16:46.367` to `00:20:06.467` / 200.1s |
| Master 3: Long training | An HR process module built on an animated explainer | Long training module from an animated base | `01:44:31.100` to `01:53:54.967` / 563.9s |

## What To Portray To Claude

Tell Claude this clearly:

The editor does not need a brand-new style each time. For tutorial work, first identify which of the three masters the new brief resembles, then recreate that structure with the new script, screen recording, VO, and titles.

The job is not only editing. The job is reducing the editor's manual CapCut labour:

1. Turn the brief into a scene map.
2. Write VO lines and on-screen text.
3. Generate VO clips line-by-line.
4. Create or analyse screen recordings.
5. Pre-place VO, titles, captions, music, and outro in CapCut.
6. Leave the editor only the taste pass: small visual nudges, final export, and approval.

## Shared DNA Across All Three

- Output: 1920x1080, 16:9, internal/corporate tutorial.
- Music starts exactly at the export in-point, never late.
- Outro: the company logo outro (landscape, white-background version) closes the video.
- Default transitions: `Slow Fade`; use `Gradual Fade` sparingly; avoid flashy transitions.
- Main effect: `Blur`, used only when it helps focus attention or hides visual clutter.
- VO is usually split into small line/scene clips (`SubBlock_*.mp3`, `SBL-*.wav`, or numbered VO files).
- The timeline is layered: screen/base video, title layer, caption/subtitle layer, VO, music, logo/outro.
- The final draft is identified by: export range + background music + outro attached.
- Never build a VO-only skeleton. A useful skeleton must include VO, step/title text, captions, music, and outro placement.

## Master 1: Short walkthrough

The original: a one-minute walkthrough of an internal web tool.

Use this for short system walkthroughs: one raw screen recording, a simple task, 4-7 steps, under 90 seconds.

Timeline facts:
- Draft: one CapCut project's `draft_info.json`, read directly.
- Export: 61.6s.
- Tracks in project: 10 video, 8 audio, 5 text.
- In export: 31 video segments, 25 audio segments, 35 text segments.
- Transitions: 6 `Slow Fade`.
- Effects: 2 `Blur`.

Structure:
- 0-10s: title card and promise.
- 10-45s: step-by-step walkthrough.
- 45-55s: centred benefit closer: `Simple`, `Fast`, `Transparent`.
- 55-62s: logo outro (landscape).

Approved style rules (from review of the approved master):
- Opening title must be two-level: big title, smaller subtitle underneath.
- Step title format: `Step N:` bold, the rest semibold. Do not make both parts bold.
- Captions/VO text are separate from step titles.
- Short benefit words are centred, not bullets.
- VO and on-screen text must match.
- Product and portal names keep their exact official casing (the reference's portal name ends in a lowercase letter, and it stays lowercase).

Reusable scene recipe:

```text
Title: [System Name]
Subtitle: Quick & Easy / Simple Guide / How to [task]

Step 1: [action]
Caption: [natural spoken instruction]

Step 2: [action]
Caption: [natural spoken instruction]

Closer:
[Benefit 1]
[Benefit 2]
[Benefit 3]
[final reassurance line]
```

Use this master when the user says:
- "Make a quick walkthrough."
- "Explain how to submit/request/track something."
- "We have a screen recording and need an internal how-to."

## Master 2: Feature tour

The original: a feature tutorial for a business phone app.

Use this for app tutorials with many features, many sections, and more text guidance.

Timeline facts:
- Draft: one CapCut project's `draft_info.json` (a copy of the working draft), read directly.
- Export: 200.1s.
- Tracks in project: 33 video, 44 text, 1 sticker, 9 audio.
- In export: 46 video segments, 141 text segments, 4 audio segments.
- Transitions in export: `Slow Fade`, `Gradual Fade`.
- Text density is high: roughly one text segment every 1-2 seconds.

Structure:
- Intro: what the app does and what the tutorial will cover.
- Setup sequence: download, access account, sign in, connect mobile app, scan QR code.
- Feature sequence: calling and in-call features, one feature per beat, then personalisation.
- End: thank you + support-desk email + logo outro.

Visual language:
- Three text layers often coexist:
  - Spoken caption line.
  - Section title.
  - Step/action label.
- Use boxed/balanced text placement, never flush to the edge.
- Break long captions at natural phrase boundaries.
- Use sentence case except product names/acronyms.
- Use bullets only for feature lists, not for short benefit closers.

Known things to watch:
- CapCut can create bad spacing artefacts: `benefi cial`, `fi rst`, and words run together (`supportdesk`). Always visually check email addresses and words with `fi`.
- Product copy must stay precise. Links and support emails must be checked before export.
- If the video already has complete on-screen text, separate SRT may be unnecessary.

Use this master when the user says:
- "Explain an app."
- "Show all features."
- "Make a 3-5 minute tutorial."
- "The viewer needs to follow many UI actions."

## Master 3: Long training module

The original: an HR process module built on an animated explainer.

Use this for long training or HR/process videos where there is already an animated explainer base or a full presentation-style video.

Timeline facts:
- Draft: one CapCut project's `draft_info.json`, read directly.
- Export: 563.9s, about 9.4 minutes.
- Tracks in project: 27 video, 34 text, 7 sticker, 27 audio.
- In export: 73 video segments, 18 text segments, 3 sticker segments, 62 audio segments.
- Transitions: mostly `Slow Fade`, one `Dissolve`.
- Music restarts at section markers, roughly every 3-4 minutes.

Structure:
- Uses a long base video/animation (the music-free export of the animation) as the backbone.
- Adds many small VO blocks on top.
- Adds text only when the base animation needs correction, emphasis, or extra clarity.
- Keeps scenes longer than screen-record tutorials; median video segment is about 8s.

Visual language:
- Do not overload the screen with extra captions if the animation already carries text.
- Let the animation breathe.
- Use section music restarts as chapter markers.
- Overlay text is used as a correction/emphasis layer, not as the whole story.

Use this master when the user says:
- "This is a full training."
- "Use this PowerPoint/animation/base video."
- "The video is 5-10 minutes."
- "We need narration over an existing animated explainer."

## Choosing The Right Master

| Brief type | Use |
|---|---|
| One process, one system, short how-to | Master 1: Short walkthrough |
| App tour with many functions | Master 2: Feature tour |
| Long HR/training/process module | Master 3: Long training |
| External brand/event/social film | Not these; use the [style DNA](style-dna.md) |

## Brief-To-CapCut Workflow

1. Classify the project: short walkthrough / feature tour / long training.
2. Write a scene map before editing.
3. Produce VO as separate line or scene clips.
4. If there is screen recording, analyse the recording and map in/out points to each scene.
5. Build the CapCut skeleton with all necessary layers:
   - base/screen video,
   - VO clips,
   - title/step text,
   - caption text,
   - music at the in-point,
   - logo outro.
6. Apply only approved transitions/effects: Slow Fade, Gradual Fade, Blur.
7. Run QA:
   - VO matches text,
   - titles are balanced,
   - no flush-edge text,
   - no broken words/emails,
   - no bullets where centred words are better,
   - outro attached,
   - export range starts at music.

## What Claude Should Ask For

Ask for only what is truly missing:

- The brief or script.
- The raw screen recording, if it is a screen walkthrough.
- The preferred voice if not obvious.
- Any official email/link that appears on screen.

Do not ask the editor how to style it. Use these masters first.

## Fast Prompt For Claude

```text
This is a tutorial/walkthrough video. Use the editor's top tutorial references:
Master 1 (short walkthrough), Master 2 (feature tour) and Master 3 (long training).
Classify the brief into short screen walkthrough / dense feature tutorial / long training module.
Follow playbooks/capcut-tutorial-templates.md.
Build the scene map, VO, captions, title hierarchy, and CapCut skeleton so the editor only needs a taste pass.
Brand videos are separate; do not use the style DNA unless this is a brand/social film.
```

