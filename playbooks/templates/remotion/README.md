# Remotion templates: narrated slides and screen walkthroughs

Two small [Remotion](https://www.remotion.dev) compositions (React components rendered to video) for the two most common code-rendered tutorials: a slide deck turned into a narrated film, and a screen recording cut into voice-timed steps. Both size every scene from the **measured** length of its voice-over line, so changing a line re-times the film with no hand editing.

**Status: Pilot.** Each was used to render one complete video end to end (a 34-slide deck into a 5 min 33 s narrated film; a 7-scene, 50.9 s software walkthrough). Neither replaced the editor-finished cut, and the house style later moved to CapCut finishing and to [HyperFrames](../../hyperframes-brand-tutorials.md) for motion graphics. The code was written by AI coding agents under my direction.

## The two templates

| File | What it renders | Pacing | Motion |
|---|---|---|---|
| [`SlideNarration.tsx`](SlideNarration.tsx) | One exported slide image + one voice-over clip per scene, then an end card | scene = voice length + **0.7 s** of air | a gentle push-in from 1.00 to 1.04 scale; 10-frame fades in and out; a 5 s end card |
| [`ScreenWalkthrough.tsx`](ScreenWalkthrough.tsx) | A muted screen recording cut into voice-timed scenes, each with a lower-third title and a caption; full-screen title cards for steps the recording does not show | scene = voice length + **0.6 s** of air | 12-frame fades; the recording scaled 112% so the browser chrome falls outside the frame |
| [`scenes.example.json`](scenes.example.json) | The scene list for `SlideNarration`: slide image, voice clip and measured seconds per row | – | – |

Each scene’s frame count is `round((voice seconds + air) × 30)`, and the composition’s total is the sum of its scenes (plus the end card for `SlideNarration`). Both files export that total so the composition can be registered with the right length.

## The scenes file

```json
[
  { "slide": "slides/slides.001.png", "vo": "VO/01.mp3", "sec": 7.49 },
  { "slide": "slides/slides.002.png", "vo": "VO/02.mp3", "sec": 8.26 }
]
```

`sec` is the **measured** duration of the clip (`ffprobe -show_entries format=duration`), never an estimate from the word count. The walkthrough keeps its scenes inside the `.tsx` instead: `vo`, `voSec`, `title`, `caption`, and `srcStart` (seconds into the recording). Leave `srcStart` out to get a title card, with optional `bullets`.

## Register them in a Remotion project

1. Create or open a Remotion project (`npx create-video@latest`), and copy the `.tsx` files and `scenes.example.json` into `src/`.
2. Put the media under `public/`: slide PNGs, voice clips and the recording, at the paths the scenes name. `staticFile()` resolves from `public/`.
3. Register both in `src/Root.tsx`, with each duration taken from the template’s exported total:

```tsx
import React from "react";
import { Composition } from "remotion";
import { SlideNarration, totalFrames as slideFrames } from "./SlideNarration";
import { ScreenWalkthrough, totalFrames as walkFrames } from "./ScreenWalkthrough";

export const RemotionRoot: React.FC = () => (
  <>
    <Composition id="SlideNarration" component={SlideNarration}
      durationInFrames={slideFrames} fps={30} width={1920} height={1080} />
    <Composition id="ScreenWalkthrough" component={ScreenWalkthrough}
      durationInFrames={walkFrames} fps={30} width={1920} height={1080} />
  </>
);
```

4. Preview with `npx remotion studio`; render with `npx remotion render src/index.ts SlideNarration out/film.mp4`. Rendering is CPU work in headless Chrome and needs no AI model.

## What the pilots taught

- **Keep the scenes manifest next to the composition.** One pilot looked complete but could not be re-rendered: its scenes file lived in the composer’s working folder, which version control ignored.
- **Export slides with a tool that reports failure.** One presentation app’s scripted export produced no images and no error; another exported all 34. Count the files before trusting “it ran”.
- **Steps with no footage get a title card,** not invented footage. The walkthrough’s recording started inside the form, so sign-in and navigation became full-screen cards.
- **Crop, don’t blur, the browser chrome.** A test address in the URL bar was hidden by scaling the recording 112%.
- **The voice and the on-screen words must say the same thing.** A benefit line on screen that disagreed with the narration was the first thing a reviewer caught.
- **Swap a stand-in end card before release.** One pilot closed on a temporary card because the real outro was out of reach mid-run; a stand-in that renders is still a stand-in.

## Licence

Remotion has its own licence: it is free for individuals and very small teams, and companies above a size threshold need a company licence. Read [remotion.dev/license](https://www.remotion.dev/license) before using it at work.

## Related

- [hyperframes-brand-tutorial/](../hyperframes-brand-tutorial/README.md) – the HTML/GSAP route, with word-level cues and a CapCut hand-off
- [code-rendered-motion-graphics.md](../../code-rendered-motion-graphics.md) – the method behind code-rendered video
- [training-video-production.md](../../training-video-production.md) – screen-recorded training finished in CapCut
- [`sa_assemble.py`](../../../tools/sa_assemble.py) – the scenes-manifest idea, generalised for ffmpeg assembly
