# My Lightroom recipe – interiors, windows, exteriors and product

These are my develop settings as I actually used them, read out of my own Lightroom catalogue rather than described from memory. The page covers a per-scene interior recipe, the window mask, the reverse mask that lifts dark corners, and the rules I keep to outdoors and on product photography. The preset files themselves are not published: their shared base layer is a house base preset rather than my own look (section 2). Every value is on this page instead, and [`sa_presets.py`](../tools/sa_presets.py) builds the same presets from your own edits.

- **Presets:** not published as files – the five scene recipes (room away from the window, room against the window, kitchen, washroom, dark entrance or corridor) are given value by value in [section 3](#3-the-five-interior-presets), and [section 10](#10-using-the-presets) shows how to build them from your own catalogue
- **Tools that do the work:** [`sa_lrread.py`](../tools/sa_lrread.py) reads my edits from the catalogue · [`sa_presets.py`](../tools/sa_presets.py) turns them into scene presets · [`sa_rawdev.py`](../tools/sa_rawdev.py) writes the technical develop as sidecars · [`sa_cull.py`](../tools/sa_cull.py) picks the keepers · [`sa_photolib.py`](../tools/sa_photolib.py) de-duplicates and upscales only what needs it · [`sa_xmp2cube.py`](../tools/sa_xmp2cube.py) and [`sa_lut.py`](../tools/sa_lut.py) turn a preset into a video LUT · [`sa_photo.py`](../tools/sa_photo.py) and [`jewellery_edit.py`](../tools/jewellery_edit.py) for outdoor and product grades
- **The rules around it:** [Fidelity-first photo retouching](photo-fidelity-retouching.md) · [Style DNA](style-dna.md)

The tools were written by AI coding agents (Claude Code and Codex) under my direction and review. The edits they read, and the decisions in them, are mine.

| Part | Status |
|---|---|
| Five interior scene presets | **Built, in use** – learnt from 10 individual edits; two of the five rest on a single frame; the preset files are not published (section 2) |
| Reading edits straight out of the Lightroom catalogue | **Built, in use** |
| Technical develop written as Camera Raw sidecars | **Built, in use** |
| A window mask that syncs across a whole set (luminance range) | **Planned** – designed and offered, not built |
| Preset to video LUT (approximate and exact) | **Built, in use** |

---

## 1. Where the numbers come from

I don’t describe my grade; I let the tools read it. Lightroom’s cloud version never writes XMP sidecars, so the only record of what I did is its own catalogue:

- `Managed Catalog.mcat` inside the Lightroom library is a SQLite document store. Each revision row carries the capture date and a SHA-256 that points at the develop settings.
- `settings/<sha256>` beside it is plain Camera Raw XMP: every slider and every mask.
- The edits are joined back to the original files by capture time, matched against the JPEG twin’s EXIF `DateTimeOriginal`.

```
python3 tools/sa_lrread.py --shoot "<shoot folder>" --json edits.json   # every edit, every mask
python3 tools/sa_presets.py --shoot "<shoot folder>" --dry               # show the presets, write nothing
python3 tools/sa_presets.py --shoot "<shoot folder>"                     # build and install them
```

### The first reading was wrong, and why that matters

One apartment shoot gave 18 edited frames. Grouped naively by room, the first reading looked like this:

| Scene (first reading) | Frames | Temp | Contrast | Highlights | Shadows | Whites |
|---|---:|---:|---:|---:|---:|---:|
| Away from the window | 6 | 5449 | −40 | −44 | +11 | −53 |
| Washroom | 5 | 5449 | −40 | −44 | +11 | −53 |
| Against the window | 4 | 4606 | −66 | −28 | +41 | +37 |
| Kitchen | 3 | 5449 | −39 | −44 | +9 | +80 |

Two different rooms with identical numbers is not a recipe; it is one look synced across eight frames. A setting repeated byte for byte across frames carries no per-scene judgement, so [`sa_presets.py`](../tools/sa_presets.py) now counts a repeated setting once. That left **10 genuinely individual edits**, and the presets in section 3 are built from those. It is a small sample: treat every per-scene number as a starting point, not a law, and re-read the catalogue after the next shoot to firm them up.

---

## 2. The shared base – and which part is not mine

Every frame in the set carries the same base:

| Slider | Value |
|---|---|
| Exposure | **+0.72** |
| Clarity | +8 |
| Dehaze | +15 |
| Vibrance | +15 |
| Saturation | +3 |
| Blacks | +2 |
| Texture | 0 |
| Sharpening | **0** |
| Noise reduction (luminance and colour) | 0 |
| HSL, tone curve, colour grading | untouched |

To be straight about authorship: Exposure +0.72, Clarity +8, Dehaze +15, Saturation +3 and Blacks +2 match a house base preset that was applied across the whole set before I edited, so a set shares one base. I kept it. What is mine is everything that changes from scene to scene in section 3, the white balance, and the masks in sections 6 and 7.

---

## 3. The five interior presets

Values are exactly what is in my `.xmp` preset files; the files themselves stay private because they carry the house base from section 2.

| Preset | Edits | Temp | Tint | Contrast | Highlights | Shadows | Whites |
|---|---:|---:|---:|---:|---:|---:|---:|
| 01a Room – away from the window | 1 *(thin)* | 4474 | +52 | −39 | −44 | +30 | +22 |
| 01b Room – against the window | 3 | 4597 | +56 | −68 | −11 | +71 | +54 |
| 02 Kitchen | 3 | 5449 | +52 | −39 | −44 | +9 | **+80** |
| 03 Washroom | 2 | 4381 | +42 | −27 | +7 | +10 | +30 |
| 04 Entrance – dark corridor | 1 *(thin)* | 5449 | +52 | −40 | +59 | +11 | −53 |

What each one is doing:

- **01a, into the room** (window behind or beside the camera). A moderate contrast cut and a shadow lift. One frame only – a rough start.
- **01b, against the window** (camera pointed into the glass). The strongest group and the one genuinely different treatment: contrast dropped much further (−68 against −39), shadows pushed hard (+71) and whites lifted (+54) to open the interior. Global highlights barely move (−11), because the glass is handled by its own mask (section 6) rather than by dragging the whole frame down.
- **02 Kitchen.** Kitchens are the dimmest rooms, so they get a big whites lift (+80) on an otherwise standard base.
- **03 Washroom.** The coolest white balance and the gentlest contrast cut; highlights are allowed up (+7) to keep tiles and sanitaryware clean.
- **04 Entrance and dark corridor.** Highlights up (+59) and whites down (−53): lift the mid-to-bright tones of a dim corridor without letting a door plate or light fitting clip. One frame only.

**01a against 01b is my call, by eye.** Measuring could not make it: bright-pixel share and the largest white blob both overlap, so a wardrobe with a window off to one side scores the same as a bedroom shot straight into the glass. [`sa_presets.py`](../tools/sa_presets.py) keeps a plain list, `against-the-window.txt`, in the shoot folder; I add frame numbers to it as I go and those frames take 01b.

---

## 4. White balance first, every time

- **Temperature is set by eye on every picture.** Inside one apartment it ran from 3314 K to 5499 K. The preset carries a starting point, not an answer. One click of the white-balance eyedropper on a white wall beats any guess.
- **Tint +52 is a green cast the camera recorded under LED lighting**, not something post-production created. A strong magenta correction on every frame is the giveaway.
- **No automatic white balance in the technical develop.** [`sa_rawdev.py`](../tools/sa_rawdev.py) once set its own: a heuristic read a beige wall as a red cast and cooled the frame by up to −14, which on warm LED interiors lands squarely in green, and a whole shoot came out green. It was removed. Interior white balance under mixed daylight and LED is a judgement, so it belongs with the grade. Camera white balance as shot is the honest starting point.

---

## 5. Crispness without the sharpening slider

- **Sharpening stays at 0.** Crispness comes from Clarity and Dehaze in the base. The technical develop had been writing Sharpening 45; it was changed to 0 so the baseline stopped arguing with my taste.
- **Never Texture, HSL, the tone curve or colour grading** on these interiors.
- **Noise is judged per image.** The presets set noise reduction to 0, so after applying one, check noise on each frame. A dim corridor shot dark and rescued in post is noisier than its ISO suggests. The technical develop handles this by judging noise on *effective* ISO rather than the dial:

  `effective ISO = ISO × 2^exposure × (1 + 0.6 × shadows/100)`

  | Effective ISO | Luminance noise reduction |
  |---|---:|
  | up to 800 | 10 |
  | up to 1,600 | 20 |
  | up to 2,500 | 28 |
  | up to 4,000 | 35 |
  | up to 12,000 | 42 |
  | above | 50 |

  Colour noise reduction sits at 30. An ISO 100 frame pushed +1.6 EV with Shadows +70 is treated like ISO 400.

---

## 6. Windows: the Object mask

I use Lightroom’s **Object mask** on the glass: brush roughly round the window and let Lightroom refine the edge. Five of the 18 edited frames carry a mask; three sit dead on a window:

| Room | Exposure | Highlights | Shadows | Contrast |
|---|---:|---:|---:|---:|
| Living room | −0.25 | **−71** | – | **−100** |
| Bedroom | −0.29 | **−82** | +57 | **−90** |
| Bedroom | −0.39 | −15 | −29 | −54 |

**The window recipe:** exposure down about a third of a stop, highlights crushed hard (−70 to −82), contrast dropped almost flat (−90 to −100). That kills the glare so the glass reads as a view rather than a white hole. Amounts vary with the light: the third example is far gentler than the other two.

In Lightroom: **Masking → Objects**, brush over the window, then set the values inside the mask.

---

## 7. The reverse mask: lifting what is dark

The other two masks are not on windows at all, and they work the opposite way – to lift something dark:

| On | Highlights | Shadows | Contrast |
|---|---:|---:|---:|
| A dim wall above a WC in a guest bathroom | **+100** | +73 | – |
| A dark front door in an entrance hall | **+100** | −100 | −100 |

The door mask lifts the bright end of a dark surface while holding its shadows and flattening it, so the door reads as a door rather than a black slab. One more frame carries two paint-brush masks with no surviving values: painted, then reset.

---

## 8. Making the window mask travel *(Planned)*

An Object mask is tied to its own picture. It will not sync to the rest of a set; the AI selection would land somewhere arbitrary in every other frame.

A **Luminance Range mask** would travel. In these interiors the window is always the brightest thing in the frame by a wide margin, so a luminance mask on the top of the range catches the glass automatically in every photo, with no drawing, and the same treatment goes inside it: **Highlights −75, Contrast −90**. That single change would make the whole recipe syncable across a set. It is designed and offered, not built. Before trusting it I would check every frame for a bright wall in direct sun or an exposed ceiling light, which the same mask would also catch.

---

## 9. Outliers worth knowing

- **A contrasty appliance close-up:** Contrast −87, Highlights −68, Shadows −59, Whites +80, Blacks +58 – flattened hard. Detail shots get their own handling rather than a room preset.
- **A bathroom set to 3314 K:** far cooler than anything else in the set, to cancel a strong warm cast in that room.
- **A dark living room, rescued:** Contrast −86, Shadows +71, Whites +65.

---

## 10. Using the presets

**Build them once, from your own edits.** The preset files are not published, so make your own:

- *From your catalogue:* `python3 tools/sa_presets.py --shoot "<shoot folder>"` reads your edits for that shoot and writes one Camera Raw preset per scene into `~/Library/Application Support/Adobe/CameraRaw/Settings/Property/` (add `--dry` to see the numbers first, or `--out <folder>` to write them somewhere else). Photoshop’s Camera Raw picks them up on its own, under a group called **Property**.
- *By hand:* create five presets in Lightroom and type in the values from sections 2 and 3.
- *Lightroom (cloud version):* Edit panel → Presets → the `…` menu → Import Presets → select the `.xmp` files that `sa_presets.py` wrote.

**Per shoot.**

1. **Cull.** `python3 tools/sa_cull.py "<shoot>" --recurse -o <out> --sheet` scores sharpness, exposure and clipping, groups brackets and burst re-shoots, picks the best of each and writes contact sheets. It never moves a source file.
2. **Upscale before grading, never after**, and only frames that are genuinely low-resolution. An AI upscale run on already-graded files shifted colour and added halos across a set, so the grade goes on last, where the set can still be matched. [`sa_photolib.py`](../tools/sa_photolib.py) only ever enlarges what needs it; test one image first.
3. **Technical develop (Camera Raw or Lightroom Classic).** `python3 tools/sa_rawdev.py "<shoot>" --recurse` writes a sidecar per RAW: exposure only outside a median-luma band of 0.34–0.60 (target 0.46), never extra exposure on a frame already more than 2% clipped (lift shadows instead), highlights and whites pulled in proportion to clipping, a black point only when the frame is genuinely hazy, and vibrance, saturation, HSL and tone curve left at zero. The cloud version of Lightroom ignores sidecars, so there the presets do all the work.
4. **Sort by file name**, so each scene sits together; the room is in the name.
5. **Select a scene group and click its preset**, choosing 01a or 01b by eye.
6. **White balance by eye**, every frame.
7. **Mask the windows** (section 6) and lift dark corners where needed (section 7).
8. **Check noise** per frame (section 5).
9. **Sync within a scene, but never white balance or exposure**, which stay per image.

---

## 11. Exteriors

I am not publishing exterior presets. The outdoor looks I grade to were set for specific jobs and are not all mine to publish, so their numbers stay out of this page. What I hold to outdoors is the method:

- **Bright, punchy, deep blacks.** A cautious, technically correct grade reads as meek. A black point lifted to grey reads as haze.
- **Strength on the right lever.** Vibrance does the heavy lifting; global saturation stays small. Global saturation plus global contrast gives the electric fake-HDR sky.
- **Colour noise reduction on, luminance noise reduction off**, so detail stays sharp.
- **One preset per set, and indoor is never outdoor.** Grading each frame separately is why a set “doesn’t match”. Apply one preset to the whole set and sync everything except white balance and exposure.
- **Check whose look it is before quoting it.** In one seven-week stretch two approved outdoor looks with opposite intent were both on file: one bright, flat and open (heavy negative contrast, shadows lifted hard, the black point almost untouched, no white balance in the preset), the other bright with deep blacks. Recommending the wrong one is how you deliver a confidently wrong grade. Every preset has an owner, a date and a scope.
- **Upscale or enhance first, grade last.** My notes once recorded this backwards (“grade, then upscale”) while giving the reason for the opposite: an upscale run after grading shifted colour and added halos. The order that was approved and used is enhance first, then grade.
- **Know where to stop.** Matching a set never justifies replacing a sky.

The code version of this, for batches outside Lightroom, is [`sa_photo.py`](../tools/sa_photo.py), and it adapts per image:

| Step | What it does |
|---|---|
| White balance | White-patch on the 97th-percentile highlights, then a slight cool bias (blue × 1.03) |
| Levels and dehaze | Black and white points at the 0.5th and 99.6th percentiles of luminance, then a gamma that puts the median at 0.46 |
| Shadows and highlights | A soft, luminance-weighted lift of the darks and pull of the brights |
| Vibrance, never saturation | Up to 22%, weighted towards dull pixels so already-saturated colour is protected |
| Chroma denoise | A 3-pixel median on the colour channels only; luminance untouched |
| Clarity | A mild unsharp mask (radius 1.6, 85%, threshold 2) |

For a mixed set of outdoor pictures shot on different days, the self-levelling house treatment in [Fidelity-first photo retouching](photo-fidelity-retouching.md#6-one-house-treatment-for-a-mixed-set-and-judging-pictures-where-they-are-shown) measures each frame and converges it on one target instead.

---

## 12. Product: jewellery and fine products

Jewellery never goes near a generative image model; it redraws stones and settings. The grade is a real-pixel edit from RAW, and it never recolours. [`jewellery_edit.py`](../tools/jewellery_edit.py):

| Step | Setting |
|---|---|
| Decode | RAW with the **camera white balance**, so colour is exactly as shot |
| Black point | Reset at the 0.8th percentile of luminance – deep blacks, no milky haze |
| Brightness | Gamma towards a mean of 0.55, brighten-only (gamma clamped 0.6–1.0), so contrast is kept |
| Highlights | Soft knee above 0.85 (slope 0.6), so spotlights and white metal don’t blow |
| Colour noise | 3-pixel median on the colour channels only |
| Clarity | Unsharp mask, radius 40, 18%, threshold 3 |
| Fine detail | Unsharp mask, radius 1.2, 135%, threshold 2 |
| Never | Saturation, vibrance, hue shift, LUT or filter |

Selection is by sharpness: the variance of an edge filter on the preview, with a cut-off of 12. If a product frame needs enlarging, [`sa_upscale.py`](../tools/sa_upscale.py) runs a non-generative upscaler on the Mac and refuses protected product files by name.

---

## 13. From a preset to video

CapCut and other editors cannot read an `.xmp`; they need a `.cube` LUT.

- **Quick and approximate:** `python3 tools/sa_xmp2cube.py preset.xmp look.cube` reads the sliders and approximates exposure, contrast, the four tone sliders, vibrance, saturation, blue hue and saturation, and mild white balance. No Lightroom needed.
- **Exact:** `python3 tools/sa_lut.py identity strip.png` makes a 1089 × 33 identity strip (33³ colours). Import it into Lightroom, apply the preset, export it as sRGB with resizing, sharpening and cropping off, then `python3 tools/sa_lut.py frompng graded.png look.cube`. That captures Lightroom’s real maths.
- **Limits:** a LUT is colour and tone only. Sharpening, noise reduction and true RAW white balance cannot be baked into it, so add sharpening in the editor.
- **In CapCut:** select the clip → Adjustment → LUT → Import → choose the `.cube`, at 100% for an exact LUT. Outside CapCut, [`sa_grade.py`](../tools/sa_grade.py) applies a `.cube` through ffmpeg with a strength blend.

---

## Related

- [Fidelity-first photo retouching](photo-fidelity-retouching.md) – the hard lines on generative AI, the measured reasons, and the house treatment for mixed sets
- [Style DNA](style-dna.md) – the whole look on one page: guardrails, grades, captions and aspect ratios
- [My creative bar](my-creative-bar.md) – how I judge a grade, a set and a frame
- [Occasions calendar and visual guide](designing-for-gulf-occasions.md) – what to shoot and show for each occasion
- [Tools index](../tools/README.md) – every published tool, including the colour and photo set
