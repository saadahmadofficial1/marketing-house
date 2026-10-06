# Fidelity-first photo retouching – and when not to use AI

A photograph of a real product, building or structure is evidence of what exists. My rule is that retouching may clean and correct a photo but must never redraw it. In practice that keeps generative AI out of some work entirely and boxes it in tightly everywhere else.

The tools linked here were written by AI coding agents (Claude Code and Codex) under my direction and review. The rules came from real rejections and measured failures, listed below.

- **RAW and grade:** [`sa_cull.py`](../tools/sa_cull.py) · [`sa_rawdev.py`](../tools/sa_rawdev.py) · [`sa_lrread.py`](../tools/sa_lrread.py) · [`sa_presets.py`](../tools/sa_presets.py) · [`sa_photolib.py`](../tools/sa_photolib.py) · [`sa_photo.py`](../tools/sa_photo.py) · [`jewellery_edit.py`](../tools/jewellery_edit.py) · [`sa_upscale.py`](../tools/sa_upscale.py)
- **Sets, web and archive:** [`sa_house_grade.py`](../tools/sa_house_grade.py) · [`sa_match_set.py`](../tools/sa_match_set.py) · [`sa_card_preview.py`](../tools/sa_card_preview.py) · [`sa_web_safe_zone.py`](../tools/sa_web_safe_zone.py) · [`sa_hero_scrim.py`](../tools/sa_hero_scrim.py) · [`sa_webcrops.py`](../tools/sa_webcrops.py) · [`sa_brand_stamp.py`](../tools/sa_brand_stamp.py) · [`sa_archive_clean.py`](../tools/sa_archive_clean.py) · [`sa_honest_2x.py`](../tools/sa_honest_2x.py) · [`sa_xmp_detail_apply.py`](../tools/sa_xmp_detail_apply.py) · [`sa_cutout.py`](../tools/sa_cutout.py)
- **Recipe:** [my Lightroom recipe](lightroom-recipe.md), with every slider value of my interior scene presets (the preset files themselves are not published)

| Part | Status |
|---|---|
| Non-generative RAW workflow (cull, technical develop, one grade per set) | **Delivered** – used on property and jewellery photo sets |
| Hard lines on generative AI (jewellery, real structures and buildings, branding) | **Built, in use** – standing rules in my studio workspace, applied to every photo set |
| Interior scene presets learnt from my own Lightroom edits | **Built, in use** – a small sample; two presets rest on a single frame |
| Self-levelling house treatment for a mixed set of real photographs | **Built, in use** – used on images handed over for a website |
| Crop-aware checks (render at the real slot, translate into the safe zone, scrim) | **Built, in use** – used on the same image set |
| Archival scan clean-up, honest 2× enlargement, detail-only XMP application | **Built** |
| Generative clutter removal with crop-and-paste-back | **Experimental** – needs my explicit sign-off on each shoot |

---

## 1. The hard lines

| Subject | Generative AI | What is allowed |
|---|---|---|
| **Jewellery** | Never – a generative model redraws stones, diamonds and settings | Real-pixel edit from RAW. A non-generative upscale is the only AI step the rule allows, and only after testing one image for integrity. My local batch upscaler is stricter still: it refuses jewellery client files outright |
| **Real structures and sites** (construction, built structures) | Never invent or reshape a structure | Fidelity-first tonal enhancement only |
| **Real buildings and property** | Never change the building | Tonal work only: exposure, contrast, colour, framing. Generative fill only for a named list of temporary clutter, with my sign-off each time |
| **Branding and signage** | Never feed real logos or signage to a generative model as a reference | Generate the scene with the signage left blank, then stamp the genuine artwork in at pixel level |
| **Jewellery footage in slow motion** | No optical-flow frame synthesis | Use real camera frames. Optical flow invents in-between frames that warp and shimmer on diamond facets |
| **A file I have already approved** | No automatic re-grading or “improving” | My approved edit is the reference, not a starting point |

On the slow-motion point: 50 fps footage played at 0.75× still gives 37.5 real frames a second, which is more than a 25 or 30 fps timeline uses. So every output frame is a real camera frame, and optical flow adds nothing. It only becomes necessary below about 0.6× for a 30 fps export, or 0.5× for 25 fps.

For generated visuals elsewhere in my work, two more standing rules apply: no hands in generated imagery, and no text, logos or people baked into AI video prompts. Those are added in the edit.

---

## 2. Why generative tools fail this kind of work

These are the measured reasons, not opinions about AI.

- **It re-renders every pixel.** “Keep everything outside the removed object pixel-faithful” cannot be obeyed by a generative image model. Only a masked edit can do that.
- **It has a fixed pixel budget.** Across all 291 files from one whole-image generative enhancement run, every output came back at about 1.6 MP regardless of input: 0.3 MP in gave 1.6 MP out, and 25 MP in gave 1.6 MP out. Only the aspect ratio changed, so a 24 MP original sent through it comes back at a fifteenth of its pixels. **Generative enhancement is not upscaling.**
- **It redraws text as shapes.** Signage and unit numbers kept failing QC, so a frame that still fails after three attempts is kept as its untouched original.
- **It cannot read RAW.** Feeding it a JPEG throws away the RAW file and all of its highlight latitude.
- **For exposure, white balance and window recovery, Camera Raw on the RAW file beats it on every count.**

---

## 3. The fidelity-first method

1. **Start from RAW**, decoded with the camera’s own white balance so colour is as shot.
2. **Cull deterministically.** [`sa_cull.py`](../tools/sa_cull.py) scores sharpness, exposure and clipping, groups near-duplicate frames (brackets, burst re-shoots) and picks the best of each group. It never moves or modifies a source file.
3. **Technical develop as sidecars, not rendered files.** [`sa_rawdev.py`](../tools/sa_rawdev.py) measures each RAW and writes a Camera Raw XMP sidecar for exposure, highlight recovery, shadow lift, noise reduction and lens correction. White balance is left as shot – an automatic correction once turned a whole interior shoot green – and sharpening is 0 to match my own edits. Vibrance, saturation, HSL and tone curve stay at zero, because that is the grade and the grade is mine. Every slider stays live in Lightroom.
4. **One grade per set.** Indoor and outdoor frames need different presets; never use one preset across both. Within a set, grading each frame separately is why sets “don’t match”. Apply the correct preset to the whole set, then sync everything **except white balance and exposure**, which stay per image. [`sa_presets.py`](../tools/sa_presets.py) learns scene presets from my own Lightroom edits; [`sa_lrread.py`](../tools/sa_lrread.py) reads those edits from the catalogue.
5. **Upscale first, grade last.** An AI upscale run on already-graded files shifted colour and added halos, which broke the match across a set; the grade goes on last, where the set can still be matched. (An earlier version of this page had the order backwards.) Upscale only frames that are genuinely low-resolution, and test one image first. Even an upscaler can shift a face or a stone. [`sa_photolib.py`](../tools/sa_photolib.py) only enlarges frames that need it.
6. **Measure consistency, don’t eyeball it.** Frames shot on different days never match when each is graded by hand, so one pipeline applies one set of numbers to every image. **Know where to stop:** matching a set never justifies replacing a sky or any other part of the scene.

### Jewellery recipe (non-generative)

From [`jewellery_edit.py`](../tools/jewellery_edit.py):

- RAW decoded with camera white balance for true colour.
- Gentle brightness lift, with the highlights protected.
- **Restore deep blacks rather than over-lifting the shadows.** An early haze problem came from over-lifting.
- Clarity (local contrast), chroma noise reduction and a fine sharpen.
- **No saturation, no vibrance, no hue shift, no LUT or filter**, so the jewellery is never recoloured.

The brief was sharp, bright and clean, but not overdone.

### Outdoor recipe

From [`sa_photo.py`](../tools/sa_photo.py), which adapts per image:

1. White-patch white balance.
2. Auto-levels and dehaze.
3. Shadow lift and highlight recovery.
4. **Vibrance, never global saturation.**
5. Chroma denoise and clarity.

---

## 4. If you must remove clutter: the boxed-in prompt

Some shoots genuinely need clutter removed, such as occupied or commercial units, building exteriors and warehouses. Empty handover units don’t. For those cases I wrote one prompt that allows **one named clutter list to be removed and protects everything else**. It sits outside my fidelity-first rule, so it needs my explicit call each time.

```
You are retouching a real photograph of a real, existing property for a property listing.
The photograph is evidence of what the building actually looks like. You have exactly two
jobs: remove temporary clutter, and improve technical image quality. Nothing else changes.

═══════════════════════════════════════════════════════════════════
JOB 1 — REMOVE TEMPORARY CLUTTER
═══════════════════════════════════════════════════════════════════
Remove these, and ONLY these, when they appear:
step ladders, trestles, scaffolding towers and tools left in shot during fit-out ·
paint tins, buckets, dust sheets, loose cables and cable reels · rubbish, cardboard,
packaging, bin bags, wheelie bins · cleaning trolleys, mops, tissue and paper towel ·
traffic cones, temporary barriers, A-boards, loose signage on stands · loose tyres,
rubble and building debris · stray personal items: bags, coats, cups, phones, papers
left on a desk, worktop or floor · dirty, damaged or abandoned parked cars and vans
obstructing a building frontage · the photographer's own reflection, shadow, tripod,
and lens dust marks.

FILL WHAT WAS BEHIND THE OBJECT WITH WHAT IS ACTUALLY THERE.
Continue the existing floor, wall, ceiling, kerb, tarmac, paving or landscaping from the
surrounding area. Keep tile grid, floorboard direction, skirting lines, kerb lines,
parking bay markings, grout lines and paving joints perfectly aligned and continuous.
Do not invent furniture, plants or decorative features to fill the gap. If the correct
fill cannot be worked out from the surrounding image, leave the object in place and say so.

═══════════════════════════════════════════════════════════════════
JOB 2 — IMPROVE TECHNICAL QUALITY ONLY
═══════════════════════════════════════════════════════════════════
· Genuine visible detail and natural sharpness, with no halos
· Realistic architectural texture: wood grain, glass, leather, fabric, marble, carpet,
  metal, painted walls, exterior cladding
· Reduce sensor noise, grain, compression artefacts, blur and pixelation
· Balanced exposure: recover blown highlights and blocked shadows
· Neutral, realistic white balance — remove excessive yellow, green or blue cast
· Natural indoor lighting: no overexposed white walls, no blown ceiling lights
· Recover window areas naturally WITHOUT inventing an exterior view
· Realistic contrast and true-to-life colour, suitable for property marketing

═══════════════════════════════════════════════════════════════════
NEVER REMOVE, ALTER, REPLACE OR REDESIGN — this list overrides Job 1
═══════════════════════════════════════════════════════════════════
· Any signage, logo, company name, building name, unit or door number, floor number,
  directory board, plaque, label, or text of any kind, however small or blurred.
  If text is unclear, keep it unclear — never invent, correct or rewrite it.
· Safety and statutory signage: fire exits, extinguishers, alarms, evacuation plans
· Permanent architecture: staircases, balustrades, columns, beams, soffits, glass
  partitions, doors, windows, frames, mullions, cladding, kerbs, bollards, guard huts,
  gates, boundary walls
· Fixed services: air-conditioning units and grilles, sprinklers, smoke detectors,
  sockets, switches, light fittings, radiators, lifts and lift call panels
· Fitted furniture: reception desks, built-in joinery, fitted kitchens, sanitaryware
· The property's genuine condition: cracks, stains, wear, damp, damaged paint, worn
  grout, scuffed walls, worn carpet
· Facade scaffolding or hoarding that shows real construction work in progress
· Neighbouring buildings, the skyline, and the real view through every window
· Trees, hedges and established planting
· People who are part of the scene

IF UNSURE WHETHER SOMETHING IS CLUTTER OR PART OF THE PROPERTY, LEAVE IT AND SAY SO.
A photo with a bucket still in it is a small problem. A photo that has lost a unit
number, a fire exit sign, or the scaffolding showing the building is mid-renovation
is a misrepresentation of the property.

═══════════════════════════════════════════════════════════════════
GEOMETRY AND OUTPUT
═══════════════════════════════════════════════════════════════════
· Identical composition, crop, aspect ratio, perspective and camera angle
· Everything outside the removed clutter must stay pixel-faithful to the source
· Match the existing grain, focus, lighting direction and colour temperature so the
  retouch is invisible at 100%
· DO NOT REDUCE THE RESOLUTION. Output at least the input pixel dimensions. If you
  cannot output at the input dimensions, stop and tell me the size you can produce
  instead of returning a smaller image.

AVOID: artificial HDR · oversaturation · excessive contrast · over-bright white
interiors · fake luxury retouching · plastic or waxy furniture and surfaces ·
sharpening halos · altered sky · replaced windows or invented outdoor views · virtual
staging · changing wall colour, furniture colour, flooring, lighting design or
architectural layout · cinematic colour grading · beautification · generative
reconstruction of anything that is not on the clutter list.

The result must read as a real, neutral, professional property photograph — not
AI-generated, not over-edited, not digitally staged.
```

The prompt is sound. The tools are the problem, which is why the next step matters.

### Crop and paste back: how to keep full resolution

The “do not reduce the resolution” line is a tripwire that makes you notice, not a guarantee. Given the fixed output size measured above, a full-resolution frame sent to a generative model comes back at about 1.6 MP, and everything in it has been redrawn. So:

1. **Crop a box around just the clutter.** Keep it small. Because the output is around 1.6 MP whatever goes in, a large crop comes back at lower resolution than the pixels around it.
2. **Send only that crop**, with the prompt above.
3. **Paste the cleaned crop back** over the original at the same position.

Everything outside the box keeps its original pixels. Photoshop’s Generative Fill does the same thing in one step: brush over the object and paste the Job 1 text into the prompt box.

### Check every result before accepting it

1. **Pixel dimensions.** The same as the source, or larger. If it came back smaller, reject it.
2. **Every piece of text.** Signage, unit numbers and directory boards, letter by letter at 100%.
3. **The patch.** Tile lines, kerbs, skirting and bay markings must still line up.
4. **Windows.** The view must be the real one, not an invented one.

**Three failed attempts on the same frame → keep the original and move on.**

---

## 5. Interior grade, measured from my own edits

How I grade interiors was read out of my own Lightroom catalogue with [`sa_lrread.py`](../tools/sa_lrread.py), not described from memory, and [`sa_presets.py`](../tools/sa_presets.py) turned it into five scene presets. The preset files are not published – their shared base layer is a house base preset, not my own look – but every slider value, how to build the presets from your own edits and the per-shoot routine are in [my Lightroom recipe](lightroom-recipe.md); this is the short version.

**The sample is small.** One apartment, 18 edited frames. Eight of them carried one look synced across them, so only 10 are genuinely individual edits; two of the five presets rest on a single frame. Treat the per-scene numbers as a starting point and re-read the catalogue after each new shoot.

| Scene | Edits | Temp | Tint | Contrast | Highlights | Shadows | Whites |
|---|---:|---:|---:|---:|---:|---:|---:|
| Room, camera facing into the room | 1 | 4474 | +52 | −39 | −44 | +30 | +22 |
| Room, camera pointed against the window | 3 | 4597 | +56 | −68 | −11 | +71 | +54 |
| Kitchen | 3 | 5449 | +52 | −39 | −44 | +9 | **+80** |
| Washroom | 2 | 4381 | +42 | −27 | +7 | +10 | +30 |
| Entrance or dark corridor | 1 | 5449 | +52 | −40 | +59 | +11 | −53 |

- **Two kinds of room, not one.** An earlier version collapsed every room into one preset. I treat a room shot *into* the space (window behind or beside the camera) differently from one shot *against* the glass: against the window, contrast drops much further and shadows and whites are pushed up to open the interior while the window holds. Choosing between the two is my call by eye; bright-pixel share and the largest white blob overlap between them, so no measurement made it reliably.
- **Kitchens get Whites +80**, because they are the dimmest rooms.
- **The window gets an Object mask:** exposure down about a third of a stop, Highlights −70 to −82, Contrast −90 to −100, so the glass reads as a view rather than a white hole.
- **The reverse mask lifts what is dark:** Highlights +100 on a dim wall above a WC or on a dark front door, so it reads as a surface, not a black slab.
- **Object masks don’t transfer** to the next frame. A Luminance Range mask on the top of the range would, because the window is always the brightest thing in frame: same Highlights −75 / Contrast −90 inside it, no drawing, syncable across a set. *Planned – designed, not built.*
- **Tint +52 on every frame** is a strong magenta correction against a green cast the camera recorded under LED lighting. It was in the files, not created in post.
- **Sharpening is 0**, with crispness coming from Clarity and Dehaze; the technical develop was changed from 45 to 0 to match.
- **What is not mine:** the shared base on every frame (Exposure +0.72, Clarity +8, Dehaze +15, Saturation +3, Blacks +2) matches a house base preset applied across the set before I edited. The per-scene values, the white balance and the masks are my decisions.

---

## 6. One house treatment for a mixed set, and judging pictures where they are shown

A set of real photographs shot on different days, in different light, will never match if each one is tuned by eye. So for a set of website images I had one non-generative pipeline written that measures each frame and converges it on one target. Nothing is redrawn, reshaped, added or removed: only haze, tone, colour and framing move.

### The house treatment: [`sa_house_grade.py`](../tools/sa_house_grade.py)

1. **Find the haze floor.** In a hazy frame the darkest tone sits well above black. Sample the frame, take the darkest value (never assuming a floor darker than 90), and if it is a real floor (above 18) rescale so it lands near black. That is what dehazing actually is.
2. **Contrast and colour, adaptive.** The house values are contrast × 1.11 and colour × 1.14, but a fixed lift overcooked a frame that was already punchy (orange ground, a blue cast on the subject). So the tool measures how flat the frame is – luminance spread about 40 for flat, 70 for punchy; mean saturation about 25 flat, 60 rich – and applies only the shortfall.
3. **Lift the sky through a blurred mask.** The mask selects bright, low-saturation pixels and fades out below the upper third of the frame, so a large pale facade or a white wall is not mistaken for sky. It is blurred (radius 14): a hard per-pixel threshold speckles the gradient, which is exactly how the first attempt failed.
4. **Self-level towards a measured target.** Measure how blue the sky already is and push only as far as needed to reach the house target (104 on a 0–255 saturation scale), with a ceiling of 1.5 on how hard a flat white sky may be pushed. A white hazy sky gets a strong lift; a deep sky is barely touched.
5. **Closing pass.** Contrast and colour move a hazy frame and a clear one by different amounts, so the finished sky is measured again and trimmed, up to six times, until it sits within 6 of the target.
6. **Finish:** a touch of warmth in the highlights (+4) and coolness in the shadows (+5), a light vignette (0.14, because these are bright daylight frames) and a gentle sharpen (unsharp 1.8 / 58 / 3).

**Why it stops short.** Two cards from wholly different conditions – one golden hour with a deep sky, one in flat haze – started close on raw sky saturation and finished within reach of each other, but not equal. The hazy one genuinely had haze that day. Driving it to match exactly would have meant replacing the sky, which crosses from manipulating the photograph into changing it.

### Matching to approved references: [`sa_match_set.py`](../tools/sa_match_set.py)

Consistency is measurable. The two cards I approved define the target – their mean brightness and mean saturation – and every other card is nudged towards it. The references are never touched, a card within 2% is left alone, and every move is capped: brightness at ±22%, colour at ±15%. Colour had been capped at ±30% and three cards pinned to the cap, which is how the set ended up looking all the same. Mean saturation is set by the subject – a glass office is bound to read flatter than a turquoise aerial – so colour only gets a nudge. Brightness is what makes a set look like one family.

### Judge the picture where it is shown

- **Render it the way the page crops it.** [`sa_card_preview.py`](../tools/sa_card_preview.py) draws each card at the page’s real centre crop (about 1.14 : 1) with the label gradient laid over the bottom third, using values read off the live stylesheet, not guessed. A story that lives in the bottom of the frame is gone, and judging the file flat would never show it.
- **Translate, don’t crop, when content overruns.** A card that shows only the middle 67% of a file (16.5% hidden each side) sliced a sign that ended at 89% of the width. Cropping can’t fix that, because the crop is symmetric: taking pixels off the left also takes 16.5% of them off the surviving right edge, and getting the sign inside needed 41% of the picture removed. [`sa_web_safe_zone.py`](../tools/sa_web_safe_zone.py) slides the whole frame instead, so every internal relationship is kept, and rebuilds the bare strip by mirroring its neighbour with a 24-pixel feather. The rebuilt strip lands outside the visible window. It only does this when the strip being mirrored is plain – the worst column’s spread (98th percentile) under 14 – because glass, stone or water mirrors invisibly and a sign or a face does not.
- **Bake a scrim when the page has none.** One hero laid its white headline straight onto the photograph with no overlay, so the only thing keeping it readable was darkness already in the picture. [`sa_hero_scrim.py`](../tools/sa_hero_scrim.py) darkens the left side with a smoothstep falloff (reach 46% of the width, depth 0.72) rather than a linear one, because a linear ramp leaves a visible edge where it reaches zero. It checks the result by measuring the 75th-percentile brightness under where the headline sits. Padding the canvas to push the subject sideways does not work: extra width raises the aspect ratio past the band’s, the page flips from cropping top and bottom to cropping the sides, and the side crop eats the padding. The real fix is a gradient in the page’s CSS, and I recommended it.
- **Cut web crops by geometry only.** [`sa_webcrops.py`](../tools/sa_webcrops.py) cuts the delivery sizes from the native still and never touches colour.
- **Stamp real branding, never redraw it.** [`sa_brand_stamp.py`](../tools/sa_brand_stamp.py) puts genuine logo artwork onto a generated plate at pixel level, so no model ever redraws lettering.

### Archival scans and honest enlargement

- **Archival scans: non-generative, always.** A scanned historical photograph is a record; an AI “enhance” can invent buildings, windows or coastline that were never in the negative. [`sa_archive_clean.py`](../tools/sa_archive_clean.py) uses non-local-means denoising (strength 8, template 7, search 21): each patch is averaged with other patches that look like it, so repeated structure – rooflines, window grids, road edges – survives and grain, which matches nothing, averages away. A blur would take grain and detail together. A light unsharp afterwards (amount 0.35) restores the micro-contrast denoising costs; push it and a cleaned scan turns crunchy, which reads as fake faster than the grain did. It estimates noise from the median absolute deviation of the Laplacian and checks that edge energy at the 99th percentile barely moves.
- **Honest 2× enlargement.** [`sa_honest_2x.py`](../tools/sa_honest_2x.py) is deterministic: EXIF orientation, a conservative white balance (gains clamped to 0.76–1.26, applied at 78% strength) and tone correction, a denoise that only touches flat areas, a Lanczos 2× resize, a lighter second denoise, a mild sharpen (radius 1.15, 72%, threshold 5), then QC with before-and-after brightness, saturation and SHA-256 hashes. No generative fill, no geometry change, no object removal, no crop; originals are never written to.
- **Detail only, at native size.** [`sa_xmp_detail_apply.py`](../tools/sa_xmp_detail_apply.py) applies only the detail fields of an image’s XMP – sharpening, luminance and colour noise reduction – at native resolution. Colour, tone, crop and content are untouched, and a file with no detail settings is copied byte for byte rather than re-encoded.

---

## 7. Measure the right thing

Most wrong verdicts on pictures in my work came from measuring something easy instead of the thing that mattered. The rules that came out of them:

1. **Measure the subject, masked, not the frame average.** On a cut-out product on a white background, the white dominates the average, so a subject that got darker still reads “unchanged”. Masking out pixels brighter than about 235 flipped two verdicts in one batch:

   | Picture | Whole frame | Subject only |
   |---|---|---|
   | Cut-out A | 95 → 95, “unchanged” | 95 → 92, unchanged |
   | Cut-out B | 96 → 96, “unchanged” | 95 → 71, **went backwards** |

2. **Judge resolution against the rendered size at 2×, not the file size.** A 512-pixel-wide picture shown in a 256-pixel card is already adequate at 2×; 150-pixel portraits shown as 58-pixel avatars need only 116. Thirteen pictures flagged as “soft” in one audit were fine once measured against where they are shown.
3. **Align heads with a silhouette row profile; no face detector needed.** On portraits shot on white: treat a pixel as subject when its darkest channel is below 238, count subject pixels per row, and take the first row above 1% coverage as the top of the head, the widest run in the top quarter of the subject as the head width, and the first row wider than 1.6 × the head width as the shoulder line. In one set the group’s median head top sat at 12.1% of frame height and head width at 42.4%; one portrait measured 2.1% and 30.0%, too small and too high, and was re-cropped to match. About fifteen lines of code, nothing to install.
4. **Choose a crop by rendering the candidates at the real slot size.** A banner rendered 1440 × 520 (2.77 : 1) with `object-fit: cover`, so a 3 : 2 photograph lost 46% of its height and the back row’s heads sat 2% from being cut. Four candidate windows were rendered at the band’s real size, with its real gradient and the real headline drawn on, and compared by eye. The browser does not get to choose the crop.
5. **Stop grading when the original is already on target.** One picture measured 141 brightness and −19 warmth against a house target of 147 and −21 before anyone touched it. Two rounds of “lift it less” pushed it to 164 and −54. The right move was to leave it alone.
6. **Check grade versus redraw with numbers and named points.** “AI redraws things” becomes a measurement when you compare each version against the original, with a faithful edit of your own as the control. On an archival aerial scan:

   | Against the original scan | My non-generative clean | A generative “clean” |
   |---|---:|---:|
   | Edge overlap (do the structures line up?) | 55.5% | 27.9% |
   | Mean absolute difference | 4.7 | 13.8 |
   | Pixels changed by more than 40 levels | 0.0% | 4.6% |
   | Output size | 2836 × 2836 | 1254 × 1254 |

   The control matters: a grainy original scores low against everything, so an edge-overlap number on its own means nothing. In the other direction, a genuine grade of a group photograph scored 98% edge overlap against its original, where a plain brightness lift of the same file scored 85%. Then check named points side by side at 100% – faces, lettering, rooflines, edges – before anything is installed.
7. **Never grade identifiable faces through an image model.** Any “grade” done by an image model re-renders the faces in it. Pictures of real people are graded locally, on real pixels – for example with the house treatment above – and checked face by face.

---

## 8. Quick decision guide

| Job | Use |
|---|---|
| Exposure, white balance, highlight and window recovery | Camera Raw on the RAW file. Never generative |
| Interior grade | My scene presets, then white balance by eye and a window mask per frame |
| Consistent look across a set | One preset; sync everything except white balance and exposure |
| A mixed set shot on different days | The self-levelling house treatment, then a capped nudge towards the approved references |
| Low-resolution frame | A tested non-generative upscale first, then the grade; never a generative “enhance” |
| A picture for a web page | Judge it at the page’s real crop and size; translate rather than crop |
| Archival scan | Non-local-means clean and a light unsharp; no AI enhance |
| Pictures of real people | Local grade only; never through an image model |
| Clutter on an occupied or commercial unit | Masked crop with the prompt above, after my sign-off |
| Jewellery | RAW real-pixel edit only |
| Real structures | Tonal enhancement only; nothing invented or reshaped |
| Signage, logos, unit numbers | Never redrawn. Generate blank, then stamp the real artwork |
| A file I have already approved | Leave it alone |

---

## Related

- [My Lightroom recipe](lightroom-recipe.md) – every slider, the window and reverse masks, exteriors and product
- [Style DNA](style-dna.md) – the whole look on one page, including the guardrails
- [My creative bar](my-creative-bar.md) – fidelity, sets, framing and the 200% check
- [AI video and image generation](ai-video-and-image-generation.md) – where generation is allowed, and how it is boxed in
- [Security and data policy](security-and-data-policy.md) – what may leave the machine and what may not
