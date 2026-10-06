# My AI generation style – Higgsfield, Kling, Veo and image models

How I direct AI video and image models for occasion reels, product and vehicle reveals, transition bridges, green-screen composites and lip-synced presenter intros. I choose the model by the job, write the shot the way a director would, lock whatever must not change with real frames, and check the picture itself before anything becomes final. Everything here comes from my own generations between May and October 2026. The prompts are rewritten with neutral placeholders: no brands, clients, people or real structures.

**What does the work:** [`media_kit.py`](../tools/media_kit.py) (upload, download, contact sheets and crops around each generation) · [`sa_frames.py`](../tools/sa_frames.py) and [`sa_see.py`](../tools/sa_see.py) (read a clip frame by frame) · [`sa_introline.py`](../tools/sa_introline.py) and [`sa_introcheck.py`](../tools/sa_introcheck.py) (lip-synced presenter clips) · [`sa_kenburns.py`](../tools/sa_kenburns.py) and [`sa_revealreel.py`](../tools/sa_revealreel.py) (motion from real pixels only) · [`sa_brand_stamp.py`](../tools/sa_brand_stamp.py) (real artwork on a generated plate) · [`sa_upscale.py`](../tools/sa_upscale.py) and [`sa_cutout.py`](../tools/sa_cutout.py) (local, non-generative prep) · [`sa_qa.py`](../tools/sa_qa.py) and [`sa_visualmem.py`](../tools/sa_visualmem.py) (local checks before and after) · [`sa_lut.py`](../tools/sa_lut.py) and [`sa_xmp2cube.py`](../tools/sa_xmp2cube.py) (carry a photo grade into the edit).
**Read with:** [Style DNA](style-dna.md) for the whole look on one page, [Fidelity-first photo retouching](photo-fidelity-retouching.md) for when generative AI must not touch a picture at all, [AI music prompting](ai-music-prompting.md) for the score, and [How I prompt AI agents](how-i-prompt-ai-agents.md) for the agent side of the work.

The prompts, rules and judgement calls are mine. I wrote most prompts together with Claude, and many I ran myself on free quota in Google Flow, so often the prompt *was* the deliverable. The helper tools linked above were written by AI coding agents (Claude Code and Codex) under my direction. Where a rule restates vendor guidance (Higgsfield’s prompting guide and model catalogue, as I recorded them in June 2026), it is paraphrased and credited in place; the camera-move names are Higgsfield’s preset names.

| Part | Status |
|---|---|
| Prompt formula, one-shot discipline, occasion styles | **Delivered** – used on approved occasion reels |
| Real-frame consistency lock (first and last frame) | **Delivered** – product push-ins; replaced for pixel-exact products (§7) |
| Lip-synced presenter intros | **Delivered** – used across a training-video series |
| Covered-to-revealed product beat | **Pilot** – one product reveal reel |
| Animating real stills (camera-only moves) | **Pilot** – one product reel; one beat rejected and kept as a still |
| Chained anchors and seamless loops | **Pilot** – one premium teaser built end to end |
| Start-and-end transition bridges | **Pilot** – one film intro |
| Green-screen background swap that keeps the filmed person | **Pilot** – worked on single scenes |
| Realism anchors for corporate stills | **Pilot** – placeholder images for a website |
| Credit and billing discipline | **Built, in use** |

---

## 1. How I think about it

- **Direct, don’t describe.** A prompt is a shot: one camera move, one subject action, and an environment that reacts. A list of nice adjectives is not a shot.
- **One strong moment beats a montage.** A single continuous eight-second shot with movement inside it beats four stitched clips. An intro is one shot of 3–4 seconds.
- **Real pixels first.** Where something must stay exactly as it is (a product, a structure, a name on a sign), I give the model real frames to travel between, or I keep the model away from it entirely.
- **Nothing baked in.** No text, logos or people in AI video prompts, and no hands in generated visuals. Words and marks go on in CapCut as real assets, because models garble letters and invent plausible-looking company names.
- **Check the composition, not the specification.** A 9:16 file can still hold a floating landscape box. A correct-length clip can still show two wallets where the story has one. Each check is listed in §16.
- **Spend like it is real money, because it is.** Check the cost at the exact settings first, quote it, and wait for a clear yes (§15).

---

## 2. Model choice by job (as of June–October 2026)

Model names and behaviour change fast, so each row is a dated fact, not a permanent truth.

| Job | What I use | Why, and the catch |
|---|---|---|
| Hero eight-second cinematic shot from text | Higgsfield Cinema Studio (`cinematic_studio_3_0`) | The best look; the dearest tier, so hero posts only |
| Standard occasion clip, image-to-video | Kling 2.6 or Kling 3.0 standard | My default. Same price; 3.0 has more features, and it is the one I use whenever a clip needs start and end frames |
| Consistency between two real frames | Kling 3.0 with start and end image | Interpolates camera and light between two real pictures (§6.1). Seedance 2.0 also takes start and end, but drifted on one arrival shot: its end frame did not lock hard |
| Native 1080 from a still | Kling 3.0 **pro** | Standard mode output only 720 × 1280 in August 2026; pro gives native 1080 × 1920 |
| Reference-driven clips and lip-sync to a supplied voice | Seedance 2.0, full model | Takes start image, end image, image references, video references and audio references. The cheaper “mini” tier was rejected (§17) |
| Testing a prompt idea | MiniMax Hailuo | Cheapest. Never test on the hero tier |
| Budget batches | Veo 3.1 Lite; Kling 3.0 Turbo (720p) | For volume. Turbo did eight locked-off b-roll clips at 7.5 credits each |
| Text-to-video with sound | Veo 3 in Google Flow | Generates engine, ambience and effects audio with the picture |
| Background swap that keeps a filmed person’s performance | Google Omni / Veo (video-to-video) | Keeps the source motion and lip-sync if the prompt locks the person (§9) |
| 4K anchor stills, characters, over-the-shoulder scenes | Nano Banana Pro (Higgsfield or Google Flow) | Strong, cheap stills. Needs explicit eye-line, horizon and prop clauses (§11) |
| Product stills locked to the real object | Kling Omni Image with image references | Holds an exact specification from three real reference frames |
| Hero still that really matters | Two models, same prompt (for example Nano Banana and Seedream) | Pick against explicit criteria: grade, realism, guard rails. Don’t marry the first output |
| Sharpening a source still before image-to-video | A dedicated upscaler, or local Real-ESRGAN ([`sa_upscale.py`](../tools/sa_upscale.py)) | A sharp, clean input gives a markedly better clip. Never a generative “enhance” on a product |
| Background removal | Local ([`sa_cutout.py`](../tools/sa_cutout.py)) | Free; it runs locally and uploads nothing |
| Voice for presenter clips | Not the video platform’s text-to-speech | One voice route for the whole series; see [Fish Audio voice cloning](fish-audio-voice-cloning.md) |
| Backup when the main pool runs dry | Kling 3.0 through another provider | The same formula works unchanged |

**What the vendor offers, in one paragraph.** Higgsfield’s own catalogue (June 2026) groups its tools roughly as: a director-style image-to-video model with more than 150 real camera-move presets; a still-image model with 50+ looks and trained character identities; a talking-avatar tool that turns a script into lip-synced video; a “mix” mode that stacks two motion presets into one continuous move; an edit model for object and layout changes; a canvas for inpainting and multi-reference product placement; a fast, cheap high-volume video model; a partner upscaler to 4K; and third-party models (Veo, Kling, Seedance and others) under one credit balance. I used a small part of that, as the table shows.

### The chains I actually run

1. **Occasion post:** (optional anchor still) → hero video → upscale if needed → CapCut for text, logo, captions and music.
2. **Premium loop:** 4K anchor stills → one clip between each pair of anchors → the first anchor reused as the last end frame → CapCut (§6.3).
3. **Product or vehicle reveal:** reference-locked hero still → covered plate made from that hero → covered-to-revealed clip (§6.6).
4. **Presenter intro:** one reference still + a supplied voice line → lip-sync model with audio generation off → automated checks → CapCut (§10).
5. **Real photo to motion:** grade → non-generative upscale → camera-only image-to-video, or a real-pixel Ken Burns move → trim to the slot (§8).

---

## 3. The formula

My working formula, the one I write every prompt against:

```text
[Camera move] + [Subject or scene] + [Time and light] + [Colour palette]
+ [Atmosphere] + [Motion detail] + [Quality] + "no people, no text, no logos"
```

For vehicles, add: `no visible brand badges or written nameplates`.

Higgsfield’s guide makes the same point in a shorter form: camera movement, then what the subject does, then how the environment reacts, then natural secondary motion. Four rules from that guide that I hold to, in my own words:

- **All three motions, every time.** Subject motion, camera motion and environment motion. Drop any one and the clip goes flat. “The camera orbits a man” is weaker than “the camera orbits a man as he straightens his cuff and turns towards the skyline, while the wind moves his jacket”.
- **Build depth in layers.** Something in the foreground (glass, leaves, fabric, smoke), the subject in the middle, a world behind (buildings, lights, landscape). It pays most with dolly-in, through-object, orbit and drone moves.
- **In image-to-video, animate only what is already in the frame.** If the picture is a person on a beach, the hair can move, the waves can roll and the camera can push in. Do not make them start surfing.
- **For social, move in the first second.** A static opening loses the viewer. Crash zoom, whip pan, fast dolly-in, a drone reveal or an orbit.

### Worked example: building one prompt

Brief: a premium still-life of a product for a calm evening post.

| Step | What I add |
|---|---|
| Camera | `Slow dolly-in.` |
| Subject and action | `A [product] rests on a dark stone plinth while a thin band of light travels slowly across its surface.` |
| Environment reacting | `Fine dust drifts through a single shaft of light; background bokeh shifts gently as the camera closes in.` |
| Light and palette | `Low warm key light from the left, deep green shadows, warm gold highlights.` |
| Atmosphere and quality | `Calm, premium, ultra-cinematic, film grain, 8K.` |
| Exclusions | `No people, no text, no logos.` |

```text
Slow dolly-in. A [product] rests on a dark stone plinth while a thin band of light travels slowly across its surface. Fine dust drifts through a single shaft of light and the background bokeh shifts gently as the camera closes in. Low warm key light from the left, deep green shadows, warm gold highlights. Calm, premium, ultra-cinematic, film grain, 8K. No people, no text, no logos.
```

Then I generate **3–4 variations** with the same mood and palette but different scenes, and pick one. The others become back-ups or posts for the following days.

---

## 4. Camera language by content type and by occasion

The first table pairs Higgsfield’s preset names with content types, adapted from their guide and narrowed to the pairings I actually reach for. The second is my own, built from what was approved.

| Content | Moves that work |
|---|---|
| Fashion and portraits | Glam, dolly-in, orbit; head tracking for an executive |
| Fine products | Lazy-Susan turn, focus change, super dolly-in, an extremely slow push-in |
| Vehicles | Car chasing, FPV drone, lateral dolly; a low tracking shot beside the wheels |
| Architecture and travel | FPV drone, crane up, hyperlapse, orbit |
| Action | Bullet time, whip pan, crash zoom |
| Corporate milestone | Crane up, orbit round a 3D element, dolly out |

| Occasion or job | Camera move I use |
|---|---|
| Religious occasions (Eid, Ramadan) | Slow push forward through an arch; a slow upward drift; gentle god rays; dust in the light |
| National day | Crane up revealing a skyline and the flag |
| Vehicle reveal | Chase → dolly behind → orbit; or rear-view row, then the cars surge away |
| Nature and social responsibility | Low FPV drone over the landscape |
| Corporate milestone | Orbit round a 3D element; dolly out |
| Executive feature | Head tracking; dolly in to the face |
| Product hero | Extremely slow push-in between two real frames (§6.1) |

---

## 5. Clip length and specification discipline

| Rule | Detail |
|---|---|
| Default length | **8 seconds**, one continuous shot with movement inside it |
| Several scenes | Generate **4 seconds each** and combine **no more than two** in CapCut |
| Intro reel | **3–4 seconds, one shot.** A 15-second stitched montage as an intro was rejected |
| Hero first scene | Split a story beat into a **setup shot and a payoff shot** (§6.5) rather than cramming the action into one clip |
| Minimum durations | Kling 3 s; Seedance 4 s; MiniMax 4 s (August 2026). A 1.07-second slot cannot be generated |
| Short slots | Generate the minimum, then **trim** to the slot and keep the opening seconds. **Never speed-ramp** a slow move: it destroys it |
| Formats | Reels **9:16**; also a **1:1** version, so compose centre-safe for both crops |
| Resolution | 720p by default; 1080p for hero posts. Check what each tier really outputs (§2) |
| Frame rate | 30 fps timelines, matching the generator default |

**Text timing for an eight-second occasion clip** (added in CapCut, never in the prompt):

| Time | On screen |
|---|---|
| 0–2 s | Picture only – let it breathe |
| 2 s | Logo fades in, top right |
| 2–4.5 s | Arabic headline |
| 4.5–6 s | Arabic headline + English headline |
| 6–8 s | Both headlines + a bilingual tagline |

I deliver that as four subtitle files: Arabic headline, English headline, tagline, and all three combined for a single-track import.

---

## 6. Consistency techniques

### 6.1 The real-frame consistency lock (first and last frame)

The problem: a product must look identical in an AI video, and any model left to imagine it will redraw it. The solution was to give the model no room to invent anything.

1. **First frame** = the real photograph, straightened and cropped to 9:16 round the piece (a simple Pillow crop, which also fixes tilt).
2. **Last frame** = a **tighter crop of the same real photograph**, about **28% further in**.
3. Kling 3.0, standard mode, sound off (silent is cheaper), 5 seconds, 9:16, guidance (cfg) about 0.5.
4. The model can only interpolate a push-in between two real pictures. It can move the camera and the light; it cannot morph the object, because both ends are real pixels.

```text
Extremely slow push-in on the [product]. The [product] stays identical from the first frame to the last – do not alter it. Only the camera and the light move. No warping, no morphing, no extra stones or parts, no flicker, no fake glitter, no cartoon sparkle.
```

**Result:** five clips (three calm push-ins and two of the variants below), product identical from start to end, about 65 credits in total, roughly 10–13 credits a clip.

### 6.2 Two “wow” variants that stay consistent

Edit only the light or focus of the *first* frame and always land on the real last frame:

| Variant | First frame | Last frame | Effect |
|---|---|---|---|
| **Light reveal** | The real frame darkened (Pillow brightness 0.30, colour 0.55) | The real lit frame | Light blooms in and the surfaces wake up |
| **Focus pull** | The real frame with a Gaussian blur, radius 14 | The real sharp frame | A rack-focus snap into the product |

### 6.3 Chained anchors and the seamless loop

For a premium teaser that must feel like one unbroken journey:

1. Generate **anchor stills** first, one per “handshake” point (4K stills).
2. Each video clip travels **between two anchors**: anchor *i* as the start image, anchor *i + 1* as the end image.
3. For a perfect loop, the **last clip’s end image is the first clip’s start image** – reuse the same uploaded media, do not re-upload a copy.
4. Video model: one that takes both start and end images (I used Seedance 2.0 and Kling 3.0 pro).

On that teaser, the anchors went through many revision rounds. That is where the credits went, not the clips.

### 6.4 Transition bridges between unrelated scenes

Kling 3.0 with a start image from one scene and an end image from the next. The prompt drives one motivated camera move plus a light or grade change that hides the cut. Three tricks do most of the work:

- **Shape rhyme:** line up a strong vertical or horizontal across both frames (a tower’s vertical edge in one frame, a row of palm trunks in the next) so the eye reads continuity.
- **Light-bloom wipe:** a sparkle or flash blooms to white and settles on the next scene – an invisible cut, made for luxury subjects.
- **Cool-to-warm grade shift:** signals a change of chapter without a hard cut.

Always include “smooth continuous / uninterrupted camera motion”, “seamless”, anamorphic, film grain, 8K. Settings: Kling 3.0 pro (12.5 credits) for the smoothest motion, sound off; music goes on in the edit.

```text
Cinematic forward dolly along the highway as a silver sedan glides ahead, the camera pushes smoothly past it while the city skyline dissolves into shimmering heat haze; the road and landscape seamlessly transform into golden desert dunes, revealing a dark premium SUV carving along a sunlit desert road, low confident tracking shot beside the vehicle, warm golden-hour light raking across the bodywork, drifting sand and soft dust trailing the wheels, anamorphic lens flares, deep contrast, premium automotive commercial atmosphere, ultra-cinematic, smooth motion, film grain, 8K
```

```text
Slow cinematic push-in toward a glass perfume bottle on a dark stone plinth, highlights beginning to catch along its edges and ripple across the glass, points of light igniting and blooming outward until a soft burst of white light fills the frame; the glow gently settles to reveal the same bottle on a marble shelf in a darkened boutique, lit by focused spotlights, elegant slow reveal, deep blacks and crystalline highlights, premium atmosphere, ultra-cinematic, smooth motion, film grain, 8K
```

**Never for fine jewellery or real engineering.** Generative video redraws stones, settings and structures, so for those products the light-bloom wipe is built in the edit from real footage (a real sparkle frame plus a white flash in CapCut) – see the guard rails in [Style DNA](style-dna.md) and [fidelity-first retouching](photo-fidelity-retouching.md). Keep people out of generated shots too; they are added from real footage in the edit.

### 6.5 Two shots for the hero scene: setup and payoff

The first scene of a reel has to be strong, and cramming a whole action into one clip makes it muddy. Split it:

- **Shot A, setup (about 4 s):** the object on the ground, the child spots it and picks it up, then calls to the stranger walking away **with his back to camera**; the stranger turns.
- **Shot B, payoff (about 3 s):** the hand-over and a shared smile.

A → B in CapCut gives a full seven-second arc. Keeping the receiver walking away in the setup also removed a recurring bug where the model duplicated the prop (§11).

### 6.6 Covered-to-revealed product beat

1. Upload **three real reference frames** of the actual product (product only, no people). An image model that takes image references holds the exact details. At 2K 9:16 it cost 0.5 credits per two variants, so four were generated and the best one picked.
2. Generate the **revealed hero** first, in the target lighting (pitch-black studio, a single overhead key).
3. Upload that hero as media and generate the **covered plate** from it: same camera, same light, the product fully under black silk. (A job id did not work as an image reference; I downloaded the image and re-uploaded it as media.)
4. Video = **start image covered → end image revealed**, 9:16, 5 s, audio off. Two video models were run side by side and the better clip picked.

```text
Black silk sheet draped over a low wide sports car in a bright modern showroom, the fabric follows the car's silhouette – bonnet, roofline, rear wing – heavy matte black cloth with soft folds and a faint sheen, polished grey stone floor, [event decor] at the edges of frame, clean white wall behind, 9:16 vertical, cinematic, shallow depth of field, fine film grain, no people, no text, no logos, no badges.
```

While the product is under the cloth there is nothing for the model to get wrong: no badge to warp and no stripe to redraw. Cut to the real photograph the moment the paint appears.

**What did not work:** a cloth drawn and composited over a still photograph. It cannot drape, so it slides across the frame like a curtain wipe. Fabric, smoke, water and anything that must wrap a 3D form has to be shot or generated, not composited. Ken Burns moves over stills are fine for detail beats, not for the hero physical action.

---

## 7. Products that must stay pixel-exact: the rule that replaced the frame lock

The frame lock in §6.1 was first used on fine jewellery, and it worked: the model only moved the camera and light. Then two things happened in the same week:

- Generated product stills used for an event intro looked like fake e-commerce posts, not authentic event content. They were rejected outright.
- A test proved the deeper problem. An image model at 2K and 4K, under the strictest “retouch only, do not change the jewellery, pixel-faithful” prompt I could write, **still rearranged pavé stones and pearl drops** and smoothed skin.

So for products that must stay pixel-exact, the standing rule is now stricter than the frame lock: **no generative model at all.** Motion comes from a real-pixel camera move over the photograph ([`sa_kenburns.py`](../tools/sa_kenburns.py): push-in, pull-out, push with drift, using a float affine window so there is no crop jitter), and the photo edit is a real-pixel RAW edit ([`jewellery_edit.py`](../tools/jewellery_edit.py)). The frame lock remains my best option where a tiny drift is tolerable, and the wrong one where it is not. Full reasoning in [Fidelity-first photo retouching](photo-fidelity-retouching.md).

The same logic covers **real branding**. Image models redraw letters as shapes, so an image-to-image pass over a real photograph can return a name with one letter changed, even when told explicitly not to touch the branding – invisible at thumbnail size, obvious only at high magnification. So I never feed photographs carrying real names or logos to a generative model as references, even when a client supplies them. I generate the plate with the signage **deliberately blank** (a bare stone band, a plain sunken disc, an unmarked bag) and stamp the genuine artwork in at pixel level with [`sa_brand_stamp.py`](../tools/sa_brand_stamp.py). When the branding *is* the point of the shot, composite the full lockup or hand over a prompt for a tool that can render it, rather than ship a building with no name on it.

---

## 8. Image-to-video from real stills

The camera may move; the subject may not be redrawn. The pattern that held on the hardest case (small instrument-cluster text), tested on that case before any money went on the batch:

```text
ONLY the camera moves: [one slow move]. The [subject] is completely stationary. Do NOT redraw, morph or warp anything: [name every badge, word and number in frame] must stay pixel-faithful and perfectly legible. The [wheel] does NOT rotate. The [lever] does NOT move. Background stays PURE BLACK – no walls, no murals, no showroom. No people, no added text.
```

| Point | Detail |
|---|---|
| Name what must stay legible | List every word, badge and number by name. “Keep text legible” on its own is not enough |
| Feed a cut-out plate | If the background behind the subject keeps getting redrawn, feed the **cut-out on pure black** and say so in the prompt. Grading the render afterwards does not fix a redrawn background |
| Model and mode | Kling 3.0 **pro**, 3 s, 9:16, sound off: native 1080 for a 1080 × 1920 timeline at 5.25 credits a clip (standard: 720 × 1280 at 4.5). Seedance at 1080p cost 36 a clip, seven times dearer for no gain on subtle moves |
| Length | Generate 3 s, trim to the slot, keep the opening seconds |
| Test first | Run the hardest frame first. One cluster close-up that drifted was rejected and the slot kept the still |
| Banner and hero panels | Describe only motion that is visible, keep the subject–camera–environment triangle gentle, and keep the first frame intact so the clip can follow a slide transition. Kling 2.6, 16:9, 5 s, sound off, 10 credits; prep with a resample to 1920 wide and a centre crop to 1920 × 1080 |

Two panel prompts that animated cleanly:

```text
Slow cinematic dolly-in toward the silver sedan on the open highway, soft clouds drifting slowly across the wide sky, faint heat shimmer rising from sun-warmed asphalt, gentle light gliding along the car's metallic body, distant city skyline softly hazing in warm morning light, premium automotive cinematic atmosphere, anamorphic, ultra-cinematic, film grain, no text, no logos
```

```text
Slow cinematic push-in, the glowing blue financial graph lines pulsing and rising upward with drifting light particles, soft light sweeping across the glass facades, city skyline behind softly shifting with drifting clouds, premium corporate atmosphere, anamorphic, ultra-cinematic, film grain, no text, no logos
```

---

## 9. Green-screen composites that keep the person

Use case: a presenter filmed on green, placed into a generated location, **keeping their face, performance and lip-sync** – one pass, no face regeneration.

**The lock phrase** (this is what stops the tool redrawing the person):

```text
Keep the [person] exactly as they are – same pose, same face, same [prop] in their hands, same body and lip movements fully preserved and in sync, do not alter or regenerate the person.
```

If it still warps, put this first: `This is a real filmed person – composite only, do not redraw the subject.`

Then, in order: clean green removal with no spill on the edges (hair, headscarf, fingers) → the environment → light on the subject matched to that environment → a natural grade → aspect ratio → `no text, no logos`.

```text
Keep the [person in their wardrobe] exactly as they are – same pose, same face, same phone in their hands, same body and lip movements fully preserved and in sync, do not alter or regenerate the person. Remove the green screen completely with clean edges and no green spill around the [hair or headscarf] and fingers. Place them standing on the grey cratered surface of the Moon, fine lunar dust at their feet catching soft light. Behind them, a deep black starfield with the planet Earth glowing in the distance – blue oceans, white clouds, soft atmospheric rim light. Add subtle realistic details high in the sky: a couple of small satellites and a distant space station drifting slowly, faint sunlight glinting off their solar panels. Cinematic key light on their face matching the cool sunlight in space, gentle rim light separating them from the dark sky, photorealistic, premium corporate commercial quality, natural colour grade, 16:9, ultra-detailed, no text, no logos.
```

For a series, swap only the environment block (office lobby, mountain, street, airport, aircraft cabin, restaurant) and keep the lock phrase, the light match and the aspect ratio. Transition ideas that suited a “work from anywhere” film: a digital wipe on the phone, a side swipe, a motion-blur whip, a cloud blend, a dim-to-stars fade, a hand-gesture wipe, and a final zoom into the phone screen.

**The other route** is a classic chroma key (CapCut, or DaVinci’s 3D keyer) over a generated **background plate**. This plate prompt worked first time at 4K, 2:3:

```text
Empty Hollywood-grade corporate interview studio background plate, no people, no chair, no furniture, no objects. Architectural back wall in deep [brand dark colour] with luxurious vertical fluted dark walnut wood panels on the left half and matte dark panelling on the right, subtle [brand accent colour] LED accent strip glowing softly along a recessed vertical seam. Warm soft top-down key light from upper left blending into cool ambient fill from upper right, gentle natural falloff into shadow toward edges, soft cinematic vignette. Polished dark matte concrete floor with very faint specular reflection, smooth transition where wall meets floor. Shallow depth of field with delicate background bokeh, defocused warm amber bokeh dots in deep background suggesting distant studio lights. Ultra-premium dignified corporate brand aesthetic, [occasion] tone, photorealistic, 8K detail, ARRI Alexa cinematic look. Background plate only. No people, no chair, no furniture, no text, no logos.
```

What made it work: negatives stacked early and repeated; brand colours given as hex values inside the prompt; “ARRI Alexa” as the anchor for cinematic colour; and a key-light direction that **matches the light already on the filmed subject**, which is what makes the composite believable. A second plate, used to match a team’s existing look, swapped the walnut for a window with a city view, a grey cove-lit wall, wood slats and visible ceiling studio lights.

---

## 10. Lip-synced presenter intros

A short clip of a presenter speaking one line to camera, made from **one reference still and a supplied voice line**. The settings matter more than the prompt: the first attempt was unusable because of three silent defaults.

| Setting | Value | Why |
|---|---|---|
| Model | Seedance 2.0, **full** model | The cheaper tier degraded lip-sync and facial motion (§17) |
| Resolution | **1080p, stated explicitly** | The default was 720p: a 720p clip in a 1080p series |
| Mode | Standard | Required for 1080p; the fast mode only does 480p and 720p |
| Generate audio | **Off** | The default was on: the model invents its own voice and bakes it in |
| References | **One** start image, nothing else | A second reference image made the presenter 34.0% of frame width instead of the approved 30.2%, and she landed mid-frame instead of to the side |
| Audio reference | The voice line, padded (below) | The model lip-syncs to it |

**Pad the audio, measured.** The model fills any audio-less stretch with invented mouth movement, and it starts animating at frame one.

- Unpadded 3.04 s line in a 5 s clip: mouth motion was **5.68** during the words and **5.93 after** them (frame-to-frame change in the mouth region at 10 fps). She kept mouthing for two seconds.
- With trailing silence, motion after the words fell to **0.50**. Trailing silence holds the mouth still.
- The agent’s metric also flagged some motion during a one-second silent head, and it argued for dropping the head. I watched both takes and kept the **one-second head**, because the trailing mouthing is what spoils a clip and the head motion does not. The eye is the reference, not the metric.

So: `1.0 s silence → the line → silence to fill the clip`, and **clip length = round(line + 2 s)**. [`sa_introline.py`](../tools/sa_introline.py) writes the padded track and prints the duration to request.

**Place it correctly in the edit.** If the clip was generated against the padded track, either start the clip’s source at the one-second head or place the voice one second in. Otherwise the lips run about a second behind the words and there is leftover mouthing at the end; one such intro had to be trimmed from 6.26 s to 5.03 s by hand to hide it.

**Generate against the original-pace voice.** A clip made against a slowed line forces a speed correction in the edit, and any error in that correction shows as drift. If a clip is wrong at the source, regenerate it rather than retiming it.

**State the composition and the silence in the prompt.** A start image does *not* anchor composition, and the model drifts to centring the subject. My generic template, assembled from the clauses that fixed each fault:

```text
Locked-off static studio shot. The presenter from the reference image stands on the RIGHT side of the frame, body occupying the right third; the left two-thirds is empty, softly lit background for a title. Natural, warm, professional delivery, looking into the camera. She speaks only while there is speech in the audio: she is silent and still before the words begin, and the instant the line ends she stops speaking, closes her mouth and holds a calm look into the camera. No camera movement, no zoom, no cuts. No text, no captions, no logos, no second person.
```

**Write the words first.** A lip-synced clip is welded to its wording, so a wording change costs a whole new generation. Agree the on-screen title and the spoken line before generating. My rule for the pair: the card names the process and its span; the voice adds the connecting word, which the card drops.

**Check every take** with [`sa_introcheck.py`](../tools/sa_introcheck.py): resolution (the 720p trap); burnt-in text (in one take of nine the model wrote the voice-over onto the wall, which showed as edge energy in the empty third: 0.0403 against a clean 0.0000); and framing against the approved set (centre about 73% of frame width, subject width about 30%). If only the framing is off, **reframe locally with a scale and pad** rather than paying for a new take.

The presenter character itself went through several rejected directions before one was approved: a stylised 3D look, a trained-identity character that did not match closely enough, and two rounds of UGC-style candidates. The bar that emerged: photoreal, convincing *while speaking* (not just accurate mouth shapes), full professional wardrobe, and natural hands.

---

## 11. Image models: stills that hold up

### The over-the-shoulder “watching” shot

My formula for a family-values occasion reel: a parent watching a value lived out by their child. The parent is a soft-focus silhouette; the scene belongs to the child.

```text
Wide cinematic 9:16, SLIGHTLY ELEVATED camera looking down past the man's [left/right] shoulder. The man (from the reference) appears ONLY as a soft-focus silhouette occupying the BOTTOM-LEFT corner, about 15–20% of the frame – just the back of his head, a shoulder and a sliver of tie. OUT OF FOCUS bokeh foreground; he must NOT dominate. His head is TURNED, facing forward, looking DIRECTLY at the child. PERFECTLY LEVEL HORIZON, NO DUTCH ANGLE, camera straight and upright. The remaining 80% is the scene in sharp focus, in three layers: foreground silhouette / middle-ground action / background bokeh. [CHILD'S ACTION]. [LOCATION AND LIGHT]. Photoreal, ARRI Alexa, premium, no text, no logos.
```

Scene variables I used, all approved on the first pass or after one revision: returning a dropped wallet to a stranger in a park; carrying a grocery bag for an elderly neighbour; dribbling round training cones on a misty sunrise pitch; pressing soil round a sapling in a community garden; holding a small trophy at an outdoor award on a sunlit lawn; reading in a bright library while glowing planets, atoms, DNA strands, blueprints, light bulbs and paper planes rise from the book; helping a classmate with a craft in a sunlit classroom; children in volunteer shirts cleaning a coastal promenade with palms and a skyline at golden hour.

To animate those stills cheaply (Kling 3.0 Turbo, 720p, 9:16, about 7.5 credits per 5 s clip):

```text
Locked-off static camera, NO camera movement, NO zoom, NO pan. Foreground silhouette in lower-left stays COMPLETELY STILL – hold him rock steady as a still soft-focus bokeh element. ONLY the middle-ground scene animates with subtle natural motion: [SCENE ACTION]. Background gently sways. Very slow, very subtle, cinematic, dignified. Hold the frame. No new elements appear, no text, no logos.
```

### Clauses I now add by default, and why

| Clause | The default it fixes |
|---|---|
| “Head turned facing forward, looking DIRECTLY at [target]” | The model gives a silhouette the back of the head, looking *away* from the action – which breaks the whole premise |
| “PERFECTLY LEVEL HORIZON, NO DUTCH ANGLE” | Canted angles creep into dramatic scenes (stages, ceremonies) |
| “Full-bleed single continuous frame, NO inset frame, picture-in-picture or letterbox; the scene fills the entire vertical frame” | A 9:16 canvas comes back with the scene as a floating landscape rectangle inside it |
| “ONE [object] only; [giver] holds it; [receiver]’s hands are empty, at their sides” | Whenever two people are near a prop, the model duplicates it. Do **not** have the receiver “reach to accept”: the reach reads as a second hand on it. Keeping the receiver walking away removed the bug entirely |
| “Pure back of head, no face or profile” | Over-the-shoulder subjects otherwise turn to show too much face |
| National dress worn completely and correctly | For anyone generated in Gulf national dress: the kandura closed, the ghutra held by the black agal, a bisht sitting properly on the shoulders, the abaya closed and the shayla correctly placed. Half-worn dress reads as disrespectful. Or put people walking away from camera, then verify the dress at pixel level |

**Reference images.** Attach the face reference on *every* over-the-shoulder generation: one fired without it was a wasted generation. If the storyboard already has a clean isolated portrait per speaker, use that as the canonical look rather than frames grabbed from a timeline.

**Consistency across a set.** Pick one anchor look (I first anchored a set to warm autumn, then corrected it to bright natural daylight) and regenerate every still that does not match – even though each regenerated still makes its already-animated clip stale. Matching is not sameness, though: hold the light and palette constant and vary **subject, camera height and angle**, or every card in a set becomes the same picture.

**Group finale for many speakers.** Don’t make seated green-screen subjects “walk”, or squeeze them side by side. Use a grid mosaic – two columns by four rows for eight people – of tight head-and-shoulders crops keyed onto a branded wall, with a thin accent-colour hairline between cells; build in one or two per beat, then lock everyone speaking together. Crop out chairs and legs. Mock the grid up free from existing crops before generating anything.

### Realism anchors for corporate stills

One of my first generated corporate stills “clearly looked AI”: a glowing holographic screen, perfect lighting with no lens flaws, an over-saturated teal-and-amber grade, mirror-perfect floor reflections and spotless surfaces. The anchors that fixed it:

- Name a real camera and lens (“shot on a full-frame mirrorless camera, 35 mm f/1.8”) and a natural handheld perspective.
- Ask for **editorial, architectural or documentary photography**. Do not say “cinematic” for a still: that word is what produces the glossy fake look.
- Replace glowing screens with ordinary matte monitors showing muted dark content.
- Add real-world imperfection on purpose: everyday clutter and wear.
- Make the brand nod through real materials (dark green marble, walnut), not by tinting the whole image in brand colour.

### Enhancing a real photograph

Rescuing a low-resolution real photograph is a fidelity job, not a generation job, and it has its own page: [Fidelity-first photo retouching](photo-fidelity-retouching.md). The short version: a generative model returns a fixed pixel budget (about 1.6 MP whatever goes in), so it is **not** upscaling, and it redraws letters as shapes. Upscale non-generatively first and grade last – upscaling an already-graded file shifts colour and adds halos – and compare original and result at 100% on signage, numbers and window views, because that is where invention shows first.

---

## 12. Occasion styles

Religious occasions take a calligraphy-forward, sacred look: deep green with warm gold and amber. National days take a heritage look in the flag colours. The full calendar, colour stories and copy rules live in the [Occasions calendar and visual guide](designing-for-gulf-occasions.md); these are the generation prompts.

**Eid al-Adha – approved** (Kling 3.0): premium 3D-render feel, no holy-site imagery.

```text
Slow cinematic push forward toward an ornate Islamic pointed arch filled with intricate cream arabesque carved geometric patterns, soft mint green background, golden crescent moon resting at the base, white hanging lantern softly glowing upper left, warm cream and gold tones, gentle god rays filtering through the arch, floating dust particles, sacred and elegant 3D render atmosphere, ultra-cinematic, film grain, 8K, no people, no text, no logos
```

**The same, with room for text** (right two-thirds clear for the CapCut overlay):

```text
Slow cinematic push forward toward an ornate Islamic pointed arch on the LEFT side of frame, intricate cream arabesque carved geometric patterns filling the arch, soft mint teal green background, golden crescent moon resting at the base of the arch, gold hanging lantern softly glowing upper left corner, open empty negative space on the RIGHT two-thirds of frame, warm cream and gold tones, gentle god rays filtering through, floating dust particles, sacred and elegant 3D render atmosphere, ultra-cinematic, film grain, 8K, no people, no text, no logos
```

**Ramadan and Eid al-Fitr – selected from four variations** (Cinema Studio):

```text
Slow cinematic upward drift through a softly lit interior, clusters of ornate Islamic lanterns hanging in warm amber and gold light, deep forest green shadows with glowing emerald reflections, rich bokeh in background, gentle swaying motion of lanterns, god rays filtering through, sacred and reverent atmosphere, ultra-cinematic, film grain, 8K detail, no people, no text, no logos
```

Why it won: warm gold against deep green, god rays and gentle motion. It was generated for Eid al-Adha but lanterns belong to Ramadan and Eid al-Fitr, so it was reassigned to those seasons.

**Alternatives – generated, not selected:**

```text
Slow cinematic wide shot of a vast desert at twilight, a luminous crescent moon rising above soft sand dunes, deep teal and midnight blue sky with warm amber horizon glow, a single glowing lantern in the foreground, ethereal mist over the dunes, sacred and peaceful atmosphere, slow camera push forward, ultra-cinematic, film grain, no people, no text, no logos
```

```text
Slow cinematic tilt upward through an ornate mosque interior, intricate geometric tilework and carved arches in deep forest green and gold, shafts of god rays streaming through high windows, floating dust particles, deep shadows and warm amber pools of light, sacred reverent atmosphere, smooth fluid camera movement, ultra-cinematic, 8K, film grain, no people, no text, no logos
```

| Do | Don’t |
|---|---|
| Crescent moon, desert night sky, a generic mosque silhouette, arabesque, god rays for Eid al-Adha | **Holy-site imagery** (the Kaaba or the Grand Mosque in Mecca). An aerial of it was generated and not used, and it is now a standing rule |
| Lanterns for Ramadan and Eid al-Fitr | Lanterns for Eid al-Adha |
| Crane up over a skyline and the flag for a national day | People, text or logos baked into any of these |
| End every occasion prompt with “no people, no text, no logos” | Montages – one strong scene |

One honest wrinkle: the approved arch clip above came before the lantern rule and carries a single small lantern as an accent. Under the rule, leave it out of Eid al-Adha prompts.

| Occasion | Colour story for the prompt |
|---|---|
| Eid, religious occasions | Deep forest green + warm amber and gold |
| Ramadan | Gold and amber + soft blue-grey |
| National days | Deep green + red + white |
| Corporate achievement | Dark green + emerald + silver |
| Social responsibility, human stories | Soft sage + warm neutrals |

Social-responsibility and human stories use **real photography**, not generation.

---

## 13. Vehicles

**Describing a car by its silhouette or light signature fails.** Asked for “a sedan with a slim horizontal LED strip” or “an SUV with four-point LEDs”, several models drew the most famous cars that match those signatures – other manufacturers’ cars – and a reviewer flagged it at once as brand-unsafe. Training data pulls towards the best-known shapes. The three-part fix:

1. **Name the exact make and model.** The model then renders the real shape instead of drifting.
2. **Rear view only.** No grille and no headlight signature means nothing brand-confusable.
3. **Ban the marks five ways:** “NO brand logos, NO emblems, NO badges, NO model names, NO text, NO licence plates”.

For a hero shot that needs guaranteed brand accuracy, license real footage or shoot it instead.

**Single-vehicle still** (4K, 9:16, used as a start frame):

```text
Hyper-cinematic shot from directly behind a [MAKE AND MODEL] in a pitch-black warehouse at night, REAR VIEW ONLY, the car facing away from camera, [TAILLIGHT SIGNATURE, e.g. "a full-width connected LED light bar spanning edge to edge across the rear"] igniting red, [REAR FEATURES, e.g. "long sloping fastback boot lid, sculpted rear shoulders, dual integrated exhaust tips"], the red taillight glow pooling on dark polished concrete floor, deep [brand colour] ambient darkness, volumetric light, absolutely NO badges NO logos NO text NO licence plate NO brand name, fine film grain, 35mm anamorphic, ultra-premium cinematic quality
```

Useful taillight descriptors: a full-width connected light bar; a three-dimensional full-width light strip; a restrained horizontal strip with inner detail; sharp crystalline C-shaped lamps; an ultra-thin bar with a coloured accent; split sporty lamps. Useful rear descriptors: sloping coupé-like rear glass, wide haunches, square upright tailgate, a clean closed rear with no exhausts for an electric car.

**Fleet teaser** (Veo 3, text-to-video, 9:16, about 5 s, with generated sound):

```text
Hyper-cinematic night shot inside a vast dark warehouse. The camera sits low directly BEHIND a row of [N] premium vehicles, all facing away from camera toward huge shutter doors rolling open to the wet night. We see only their rear ends. From left to right the vehicles are: [exact make and model, one per car]. Render each car's accurate real rear shape and taillight design, BUT every brand logo, emblem, badge, model name and lettering must be completely removed and invisible – clean unmarked tailgates only. All [N] sets of red LED taillights ignite at the exact same moment and flare bright. In perfect unison all [N] cars surge forward and accelerate hard away from camera, red tail lights streaking, exploding out through the doors into the rainy night. Fast energetic 5-second build. Anamorphic lens, [palette], fine film grain, volumetric light, ultra-premium cinematic quality. Audio: [N] engines roaring to life in unison, tyres screeching on wet floor. Absolutely NO brand logos, NO emblems, NO badges, NO model names, NO text, NO licence plates, NO visible faces, NO people.
```

---

## 14. Guard rails (non-negotiable)

| Rule | Why |
|---|---|
| **Reels are 9:16.** Verify the aspect ratio – and the composition – before *every* generation | Shorthand like “16x9” typed mid-way through a vertical project was once taken literally and burnt a generation. Never auto-flip on ambiguous shorthand; default to the project format and ask |
| **No hands** in generated visuals | They look wrong and reviewers dislike them. Crop out chairs, legs and hands |
| **No text, logos or people** baked into AI video prompts | Added in CapCut as real assets |
| **No generative model on pixel-exact products** | §7 |
| **Real structures are never invented or reshaped** | Tonal enhancement only; see [Fidelity-first photo retouching](photo-fidelity-retouching.md) |
| **Event and brand content uses real footage** | Generated stills of a real event look fake |
| **Approved files are frozen** | Never “improve” an approved file; my edit is the reference |
| **Verify every generated image before building on it** | Generate → check → confirm, never generate → assemble |
| **Search what already exists before generating** | Twice the right real picture was already on disk |
| **Frames from screen recordings never go to a generation service** | Narration text may go out; pictures may not. See [Security and data policy](security-and-data-policy.md) |

---

## 15. Credits and billing

**Prices I recorded** (Higgsfield credits unless noted; they moved during the period, which is the first lesson):

| Model and settings | Credits | When |
|---|---:|---|
| MiniMax Hailuo, 6 s | 6 | June 2026 |
| Veo 3.1 Lite, 8 s | 8 | June 2026 |
| Kling 2.6 or Kling 3.0 standard, 5 s | 10 | June 2026 |
| Kling 3.0 pro, 5 s | 12.5 | June 2026 |
| Kling 3.0 Turbo, 5 s, 720p | 7.5 | June 2026 |
| Kling 3.0 standard / pro, 3 s | 4.5 / 5.25 | August 2026 |
| Seedance 2.0, 720p, 5 s | 22.5 | June 2026 |
| Seedance 2.0, 1080p standard, 4 s / 5 s / 6 s | 36 / 45 / 54 | August–September 2026 |
| Seedance 2.0 “mini” | 15 | September 2026 (rejected on quality) |
| Cinema Studio, 8 s | 40 | June 2026 |
| Nano Banana Pro still, 2K / 4K | 2 / 4 | June 2026 |
| Non-generative upscale to 4K | 2 | June 2026 |

**The tiers I work to:** MiniMax for prompt tests → Kling standard as the default → Seedance for reference-driven or lip-synced work → Cinema Studio for hero posts only; Nano Banana Pro for stills. Typical budgets: a prompt test is three variants on the cheapest model (18 credits); a standard occasion post is three Kling variants (30); a hero post is three Cinema Studio variants (120).

**Rules:**

1. **Run the cost check at the exact parameters, every time.** One quote of 22.5 credits came from a call that had silently defaulted to 720p; the real 1080p price was 45, and a 6-second clip later cost 54. Recipe costs drift.
2. **Ask before more than 50 credits in one batch.** Quote it and wait for an explicit yes.
3. **An approving-sounding remark is not a go-ahead.** A positive comment about a take is not permission for another paid take. Only an explicit instruction is.
4. **Keep a reserve.** Don’t regenerate an imperfect take on your own judgement; quote and ask.
5. **Under a hard budget, cut the count, not the tier – and say so.** Fifteen stills at the approved tier would have cost 30 against a 20-credit ceiling, so it became ten at that tier, with the reason stated.
6. **A timed-out submission still charges.** A batch call returned “not responding”; the generations list showed nothing, because it lists only *completed* jobs. The balance had already dropped by about 235 credits, and the jobs appeared seven minutes later. After any timeout, check the **billing ledger or balance**, never the job list – and **never resubmit**.
7. **Credits can expire.** Team top-up credits were valid for 90 days (September 2026), so size a top-up to when the work will actually run. Read your own account’s billing screen; don’t quote pricing from memory.
8. **Plan for render time.** A 5-second Seedance 2.0 clip took about 30 minutes in September 2026 (a 5-second Kling 2.6 clip about 1–2 minutes in June). Run batches in parallel when there is a deadline.

---

## 16. Checking the output

| Check | How |
|---|---|
| Composition, not just canvas | Look at the frame: subject size, action clarity, face visibility, no inset box |
| Continuity | One hero object, one moment, no impossible states (no second wallet) |
| The quiet defaults | Eye-line, level horizon, centring, trailing mouth movement |
| Motion through the clip | Pull frames every 0.25–0.5 s with [`sa_frames.py`](../tools/sa_frames.py) and read them before planning the edit |
| Product integrity | Frame-extract the clip and confirm the hero object holds through the motion |
| Prompt against result | Before generating, search past similar work; after, describe the output with a local vision model ([`sa_qa.py`](../tools/sa_qa.py) `--image`, [`sa_see.py`](../tools/sa_see.py)) and compare that description with the prompt. A mismatch is flagged before credits are spent or anyone is shown it. This check runs locally and uploads nothing |
| Presenter clips | [`sa_introcheck.py`](../tools/sa_introcheck.py): resolution, burnt-in text, framing |
| Text and signage | Letter by letter at 100%, against the original |
| At the size it will be seen | Judge the card or the reel at its true display size, not the master |
| Run a new checker on approved work first | A checker that fails clips already approved is broken, not the clips |

---

## 17. What I approved and rejected, and why

| Approved | Why |
|---|---|
| An arch, arabesque and crescent Eid clip | Premium 3D-render feel and the occasion read clearly, without holy-site imagery |
| The lantern interior, picked from four | Warm gold on deep green, god rays, gentle motion |
| Product push-ins between real frames | The product was identical from start to end |
| Eight over-the-shoulder stills, first or second pass | Silhouette small, eye-line on the child, level horizon, three depth layers |
| A setup-and-payoff pair for the first scene | A clear arc, and it removed prop duplication |
| The one-second head pad on presenter clips | My eye over the agent’s metric: the trailing mouthing mattered, the head motion did not |

| Pilot – tested and kept, not yet in signed-off work | Why |
|---|---|
| A covered-to-revealed product beat (§6.6) | Nothing to redraw while covered; cut to the real photograph on the reveal |
| Camera-only animation of real detail stills (§8) | Badges and lettering stayed legible once every word was named in the prompt; the one close-up that drifted was rejected and its slot kept the still |

| Rejected | Why |
|---|---|
| Cars described by silhouette or light signature | Drifted into other manufacturers’ designs; brand-unsafe |
| Holy-site imagery for Eid al-Adha; lanterns for Eid al-Adha | Wrong for the audience and the occasion |
| Generated product stills for an event intro | Looked like fake e-commerce posts, not an authentic event |
| Generative “retouch” of fine jewellery, even with the strictest prompt | Rearranged stones; the reason §7 exists |
| A 15-second stitched montage as an intro | An intro is one shot of 3–4 seconds |
| A cloth drawn over a still for the reveal | Slid like a curtain wipe; physical hero actions are shot or generated |
| The cheaper video tier for presenter clips | Framing and resolution measured identical, but lip-sync and facial motion – the things that matter, and the things the test could not measure – were worse. When the checkable dimension is not the one that matters, say so louder than the numbers |
| A stylised presenter; an identity-trained character that did not match; two UGC-style batches | Wanted photoreal, convincing while speaking, full professional wardrobe |
| A presenter centred in frame | The left third must stay empty for the title |
| A corporate still that “clearly looked AI” | Sci-fi screen, perfect light, saturated grade, spotless surfaces (§11) |
| Image-to-image over a photo with a real company name | Changed a letter of the name |
| A set where every card looked the same | Matching is not sameness: vary subject and angle, hold the light |
| A clip generated against a slowed voice line | Forced a speed correction in the edit, and the error showed as drift |

---

## 18. Gotchas

- **Preset hijack.** On a prompt that “looks cinematic”, the platform sometimes returns a recommended viral preset instead of generating. Resubmit declining that preset to force a literal generation.
- **List and display tools crashed** on one model’s jobs (June 2026), so they could not be listed. Download from the web interface instead.
- **The upload server sometimes reports “not responding”.** Retry; it recovers. The upload flow is: request an upload URL → upload the file → confirm the media → use the confirmed media id. [`media_kit.py`](../tools/media_kit.py) does the parallel uploads and downloads.
- **A job id is not always accepted as an image reference.** Download the image and re-upload it as media.
- **A start image does not fix composition.** State the framing in words.
- **Extra references change scale.** The settled recipe outranks an old generation record that passed a second reference.
- **The model can write the voice-over onto the set.** Check every presenter take for burnt-in text.
- **Defaults are traps:** resolution 720p, audio on, and the fast mode capped below 1080p.
- **Forgetting the face reference** wastes a generation.
- **Too many props near two people** produces duplicates.
- **“Cinematic” in a still prompt** produces the fake-AI sheen; use photographic language.
- **Generative “enhance” is not upscaling,** and it cannot read RAW files.
- **Stale clips:** every regenerated still makes its animated clip stale. Track which clips need re-animating.
- **Briefing is not a go.** When someone is feeding a brief slot by slot, record it and stay quiet; don’t push to generate. When another person or tool will do the generating, sometimes the right hand-over is my *thinking* about the shot, not a dictated frame.

---

## 19. Music

Score is generated too, but it has its own rules – including one that was reversed by feedback. See [AI music prompting](ai-music-prompting.md).

---

## Maturity

Delivered for occasion clips, the real-frame lock and presenter intros; Pilot for still animation, chained loops, transition bridges, the covered-to-revealed beat, green-screen swaps and corporate realism anchors; Built, in use for the credit discipline. Model names, prices and defaults are dated facts from May to October 2026 and will change.

## Related

- [Fidelity-first photo retouching](photo-fidelity-retouching.md) – the hard lines where generative AI is never used
- [AI music prompting](ai-music-prompting.md) – tag versus paragraph prompts and the regional-identity rule
- [Fish Audio voice cloning](fish-audio-voice-cloning.md) – the voice route for presenter clips
- [Training-video production](training-video-production.md) – where the presenter intros are used
- [The CapCut draft format](capcut-draft-format.md) – where text, logos and captions go on
- [How I prompt AI agents](how-i-prompt-ai-agents.md) and [Thinking prompts](thinking-prompts.md)
- [Learning from mistakes](learning-from-mistakes.md) – why each rule became a check
- [Security and data policy](security-and-data-policy.md) – what may and may not go to a generation service
- [Style DNA](style-dna.md) – the whole look on one page, generated and real
- [Occasions calendar and visual guide](designing-for-gulf-occasions.md) – every occasion, its timing, motifs and imagery to avoid
- [My creative bar](my-creative-bar.md) – the standards every generation is judged against
- [My Lightroom recipe](lightroom-recipe.md) – the grade real photographs get before any motion
- [CapCut hub](capcut.md) – where every generated clip is finished
- [Local AI on a Mac](local-ai-on-a-mac.md) – running the local vision checks without slowing the edit
