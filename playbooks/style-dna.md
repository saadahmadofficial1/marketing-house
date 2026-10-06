# Style DNA – the look on one page

This is the one-page source of truth for how my content looks – video, image and background – written so that any AI session, or any person, can “know the look” in a glance. It pulls the guardrails, the prompt formula, the grades, the caption rules, the formats and the sound together; the detail lives in the playbooks linked from each section.

- **Tools that apply it:** [`sa_titlecard.py`](../tools/sa_titlecard.py) (two-tier titles) · [`sa_capcut_captions.py`](../tools/sa_capcut_captions.py) (captions as editable CapCut text) · [`sa_exportcheck.py`](../tools/sa_exportcheck.py) and [`sa_qa.py`](../tools/sa_qa.py) (pre-export and pre-publish checks) · [`sa_grade.py`](../tools/sa_grade.py) and [`sa_lut.py`](../tools/sa_lut.py) (grades on video) · [`sa_kenburns.py`](../tools/sa_kenburns.py) (real-pixel motion from stills) · [`sa_brand_stamp.py`](../tools/sa_brand_stamp.py) (real logos, never redrawn) · [`sa_upscale.py`](../tools/sa_upscale.py) and [`sa_guard.py`](../tools/sa_guard.py) (guardrails in code)
- **Style as data:** [`SAAD_EDITING_GRAMMAR.json`](../Reference/SAAD_EDITING_GRAMMAR.json) and [`EDIT_DNA_STATS.json`](../Reference/EDIT_DNA_STATS.json)
- **Deep detail:** [AI video and image generation](ai-video-and-image-generation.md) · [Lightroom recipe](lightroom-recipe.md) · [Fidelity-first photo retouching](photo-fidelity-retouching.md) · [Occasions calendar and visual guide](designing-for-gulf-occasions.md) · [Design and deck craft](design-and-deck-craft.md)

The tools were written by AI coding agents (Claude Code and Codex) under my direction and review. The look is mine; where a grade or rule came from someone else, the page says so.

| Part | Status |
|---|---|
| Guardrails (section 0) | **Built, in use** – standing rules in my workspace; several are enforced in code |
| Generated-video style and prompt formula | **Delivered** – used on approved occasion videos |
| Tribute and farewell montage style | **Built, in use** – measured across four delivered real-footage projects |
| Image grades and the preset-per-scene rule | **Delivered** – used on delivered photo sets |
| Background modes and colour by occasion | **Built, in use** |
| Caption rules | **Delivered** – house style on delivered videos |
| Deck and slide craft | **Built, in use** – my standing rules |

---

## 0. The guardrails – break these and the work is rejected or the credits are burnt

| Rule | Why | How it is held |
|---|---|---|
| **Reels are 9:16 vertical.** Verify the ratio before every generation; never auto-flip on an ambiguous “16x9” | A generation fired on an unconfirmed ratio is wasted, and a 9:16 file can still contain a landscape picture (see section 2) | Asked and confirmed before generating; composition checked, not only the canvas |
| **No hands in generated visuals** | Generated hands are the most common giveaway, and reviewers dislike them. Crop out stray chairs, legs and hands too | A clause in every image and video prompt |
| **Jewellery and fine products never go through a generative image model** | It redraws stones, settings and pearl drops, even under the strictest retouch-only prompt | Real-pixel edit from RAW only. A non-generative upscale is the only AI touch, after a one-image test; the local upscaler refuses protected product files by name |
| **Real engineering, structures and property are never invented or reshaped** | The picture is evidence of what exists | Fidelity-first tonal work only; a 200% check on every letter, edge and structural line |
| **AI video prompts never bake in text, logos or people** | Models garble lettering and invent plausible-looking brand text | Every prompt ends “no people, no text, no logos”; text, logo and captions are added in the edit |
| **Never auto-grade or “improve” an approved final** | My approved edit is the reference other work is matched to; running a tool over it destroys the reference | Approved files are frozen; new work goes into a new project or timeline every time |

---

## 1. Video style

**Stack:** a cinematic image-to-video or text-to-video model for the scene, then CapCut for text, logo, captions and grade. Model choice by job is in [AI video and image generation](ai-video-and-image-generation.md).

**Specs:** 8 seconds · 9:16, composed so a 1:1 centre crop also works · 720p by default, 1080p for hero posts.

**Motion:** slow, smooth and cinematic. “One by one” reveals, with elements appearing gradually. One continuous eight-second shot with internal movement and no cuts. A luxury feel: god rays, dust particles, bokeh, depth of field. Graceful and atmospheric, never frantic.

**How many:** three or four variations per occasion – same mood and palette, different scene – and I pick the hero. One strong scene beats a montage. If several scenes are genuinely needed, generate them at four seconds each and combine no more than two in the edit. An intro is three to four seconds and one shot.

**Prompt formula:**

```
[Camera move] + [Subject / scene] + [Time / light] + [Colour palette] + [Atmosphere]
+ [Motion detail] + [Quality] + "no people, no text, no logos"
```

For vehicles, add “no visible brand badges or written nameplates”, name the exact model rather than describing a silhouette, and show the rear only (section 2).

**Worked example** – a selected lanterns visual (lanterns are now reserved for Ramadan and Eid Al Fitr), broken into the formula:

| Part | In the prompt |
|---|---|
| Camera move | “Slow cinematic upward drift through a softly lit interior” |
| Subject / scene | “clusters of ornate Islamic lanterns hanging” |
| Time / light | “in warm amber and gold light … god rays filtering through” |
| Colour palette | “deep forest green shadows with glowing emerald reflections” |
| Atmosphere | “rich bokeh in background … sacred and reverent atmosphere” |
| Motion detail | “gentle swaying motion of lanterns” |
| Quality | “ultra-cinematic, film grain, 8K detail” |
| Exclusions | “no people, no text, no logos” |

**Advanced – chained-anchor loops for premium teasers.** Make 4K anchor stills first, one per “handshake” point. Each clip is a journey between two anchors, with anchor *i* as the start image and anchor *i + 1* as the end image. Reuse the first anchor as the last end image and the teaser loops seamlessly.

**Grade on video:** a LUT made from the photo preset ([`sa_lut.py`](../tools/sa_lut.py) for an exact one), applied in CapCut or with [`sa_grade.py`](../tools/sa_grade.py).

**Voice and captions are off by default.** No voice-over or captions in any style unless I ask for them; several styles are music-only by design.

### 1b. Tribute and farewell montage style

For real-footage emotional montages – a colleague’s farewell, a milestone tribute – decoded from a delivered farewell film and measured across four delivered real-footage projects. It is distinct from both tutorial pacing and the generated-reel style above.

- **Cut pace is fast:** a median shot of about **1.8 seconds** (the median of the four projects’ own medians, 1.84 s, not a single-project guess). Raw event and candid footage; no screen recording.
- **No on-screen text or captions at all.** B-roll and music carry the emotion.
- **Two or three stacked video tracks**, with some clips repositioned and scaled for collage moments, rather than one linear track.
- **One continuous emotional music bed** – a piano piece, for instance – running the whole montage into the outro, with no jarring cuts in the score.
- **Slow Fade transitions**, the same as in tutorials, which confirms it as the house-wide default rather than a mode-specific choice.
- **Two filter or grade layers** run the full length of the montage and stop just before the outro.
- **A short bridge clip of about three seconds**, itself slow-faded, hands over to the **logo outro** (landscape, white, 16:9) – the same close as every other video type.

**Known limits of the automated census**, so it is not over-trusted: it measures cut pace over the *whole draft*, not the approved export range, so a project with untrimmed extra footage reads long (the hand-verified tutorial pace is a 4.0-second median); and it can only tell whether text is present, not whether a style is text-light or text-heavy. Treat it as supporting evidence, not a replacement for a hand-verified read. The measured rhythm for every edit family is in [Learning an editor’s style](learning-an-editors-style.md) and [`EDIT_DNA_STATS.json`](../Reference/EDIT_DNA_STATS.json).

---

## 2. Image and photo style

**My look:** bright, punchy, clean colour, crisp. High exposure (open, lifted). High contrast with **deep blacks**, never grey-lifted. A deep, rich, dehazed blue sky. Warm-neutral white balance. Vibrance pushed hard and saturation only nudged, so the colours that matter pop without the whole frame going electric. Zero haze; sharp and denoised. A cautious, technically correct grade is a rejected grade – and so is a blanket-pumped one.

**One approved preset per scene class.** I don’t publish other people’s presets, so this lists the classes and what each is for, not their numbers:

| Scene | What the look does |
|---|---|
| **Interiors** (rooms, kitchens, washrooms, corridors) | My own five scene presets, with every value: [Lightroom recipe](lightroom-recipe.md) |
| **Indoor people, showroom, office** | A dedicated indoor look; never the outdoor one |
| **Outdoor site and aerial** | Bright, flat and open: heavy negative contrast, highlights pulled down, shadows lifted hard, the black point almost untouched. It sets **no white balance**, which is why white balance stays per image, and no noise reduction or sharpening, which are judged per image after the grade |
| **Older outdoor sets** | Bright, lifted shadows, **deep** blacks, denoised, vibrance rather than saturation – the opposite intent to the look above |
| **Jewellery and fine products** | **No saturation or vibrance** (true colour, never recoloured), protected highlights, deep-ish shadows, clarity |

Two outdoor looks with opposite intent were both approved inside a few weeks, each for its own work. **Every preset has an owner, a date and a scope**, and quoting a banked recipe without checking whose approval it carries is how you deliver a confidently wrong grade.

**Indoor is never outdoor – the biggest grade mistake.** A whole set uses one preset; “it doesn’t match the LUTs” means each shot was graded separately. Apply the right preset to all of them, then sync every setting **except white balance and exposure**, which stay per image. **Upscale or enhance first, grade last:** an AI upscale run after grading shifted colour and added halos and broke the match. (My notes once recorded this order backwards while giving the reason for the right one; the approved and used order is enhance, then grade.)

**Multi-person reels.** For legacy and family pieces, over-the-shoulder framing: the parent as a soft-focus silhouette in the lower left, about 15–20% of the frame, with the action beyond. For a group finale, a 2 × 4 grid mosaic of tight head-and-shoulders crops on a branded wall, separated by a hairline in the brand accent colour.

**Image-model defaults to override in the prompt:**

- Faces drift to profile or away from the action: write “head turned facing forward, looking directly at [target]”.
- Dramatic scenes creep into Dutch angles: write “perfectly level horizon, no Dutch angle”.
- A vertical request can come back as a landscape picture floating inside a 9:16 canvas: write “full-bleed single continuous frame, no inset frame, picture-in-picture or letterbox”. Check the composition – subject size, action, how much face shows – not just the canvas ratio.
- Vehicles described by their light signature drift into the most famous matching brands. Name the exact model, show the **rear only**, and forbid badges, emblems, model names, text and number plates in so many words.

---

## 3. Background style by mode and occasion

Pick the mode for the occasion and the background follows from it. The full calendar, with every date rule and the imagery to avoid, is in [Occasions calendar and visual guide](designing-for-gulf-occasions.md).

| Mode | Background look | When |
|---|---|---|
| **Calligraphy-forward** | White or light background, a faint mosque silhouette, Arabic calligraphy as the hero | Eid, Ramadan, Mawlid, Isra and Mi’raj |
| **3D CGI / tech** | Glossy 3D, a city skyline, cinematic light, silver and neon green | Earth Day, safety days, company milestones |
| **Real photography** | Real people, warm neutrals, a light, semi-transparent brand-colour overlay | Mother’s Day, CSR, employee stories |
| **Heritage / archival** | Black-and-white vintage photography, illustrated heritage icons (falcon, camel, dhow), green, red and white | National Day, legacy pieces |
| **Editorial stock** | Bold creative stock, large white text, minimal branding – the logo only | Awareness days, international occasions |

**House rules for every design, poster and social post:**

- **Never invent colours.** Derive every tint and shade in OKLCH from the brand’s own two colours.
- **The brand’s own typefaces, at most two.** No fallback to the overused defaults (Inter, Roboto, Arial, system fonts), and no clichéd gradients, particularly purple on white – both called out as generic AI defaults in Anthropic’s published [frontend aesthetics prompting guide](https://github.com/anthropics/claude-cookbooks/blob/main/coding/prompting_for_frontend_aesthetics.ipynb).
- **A dominant colour with a sharp accent** beats a timid, evenly spread palette (the same guide makes this point).
- **No emoji in graphics** unless the brand itself uses them.
- **Light overlays, generous space, fewer text elements.** Let the picture breathe; when in doubt, strip it back.

---

## 4. Colour and type constants

- **Two brand colours, everything else derived:** a deep primary and a brighter accent.
- **Colour by occasion:**

  | Occasion family | Palette |
  |---|---|
  | Islamic | Green as the hero, with white; or deep forest green with warm amber and gold |
  | Ramadan | Gold and amber, with a soft blue-grey |
  | National | Deep green, white and red (the flag’s colours) |
  | CSR and nature | Sage and earth tones |
  | Tech and milestones | Silver, metallic, a neon-green glow |
  | Human stories | Warm neutrals and soft pastels |

- **Type:** one display face for headlines, one clean sans for body; never more than two families.
- **Logo:** always in the same corner (top right) and always bilingual.
- **Two-tier text hierarchy:** the title centred and larger, any supporting line smaller and lighter beneath it; step labels with one part bold and the rest semibold or medium, never both bold, because all-bold reads flat. [`sa_titlecard.py`](../tools/sa_titlecard.py) bakes this in.

---

## 5. Captions

- **Balanced, boxed framing:** text sits inside an invisible box with equal padding left and right, never flush to one edge.
- **Break long lines at natural phrase boundaries** – “this platform enables / employees to make and receive office calls” – and mark the break in the script.
- **Sentence case**, lowercase except for brand names and acronyms. **No all-caps tag dumps** of the “TRANSFER | CONFERENCE | RECORD” kind.
- **Title above, subtitle below**, on the same horizontal centre.
- **On-screen words match the narration word for word.** If a card says one thing while the voice says another, the card changes.
- **Verify position and spacing before export**, and eyeball every e-mail address and every word containing “fi”: the editor’s kerning once rendered “fi” words with a gap in the middle.
- Captions go in as editable CapCut text, not burnt-in pixels: [`sa_capcut_captions.py`](../tools/sa_capcut_captions.py). [`sa_exportcheck.py`](../tools/sa_exportcheck.py) checks captions, title card and the one-line rule before export; [`sa_qa.py`](../tools/sa_qa.py) checks British spelling and hashtag casing before publishing.

---

## 6. Decks and slides

Titles carry the story; one title style throughout; no punchline titles; put content into a table, a big number, a quote, a diagram or an image instead of overloading a slide; body text never under 24 px and titles 48 px or more on a 1920 × 1080 slide. The full rules are in [Design and deck craft](design-and-deck-craft.md).

---

## 7. Formats and aspect ratios

| Output | Format |
|---|---|
| Reels and occasion videos | **9:16 vertical**, composed so a 1:1 centre crop also works. Verify before every generation |
| Training and tutorial videos | 16:9 landscape |
| The logo outro | Landscape, white, 16:9, the same on every video type |
| Generated clip length | 8 seconds for one scene; 4 seconds each if two are combined |

An ambiguous instruction such as “16x9” for a reel is a question, not a setting: ask, don’t flip.

---

## 8. Music and sound

- **Three tells of a finished video:** the music starts exactly at the timeline’s in-point, the logo outro is attached, and the transitions are slow fades. A cut missing any of them is a draft.
- **Montages run on one continuous music bed** into the outro.
- **Arabic identity in the music has to be audible but cinematic.** My first direction – “felt, not heard” – was judged to have no Arabic or Emirati character at all; the correction was a real melodic role for oud or qanun inside a film-score arrangement. Never Arabic jazz, lounge, a piano lead, folk or wedding styles, trance, saxophone or generic corporate muzak. Prompts and rules: [AI music prompting](ai-music-prompting.md).
- **Too prominent can be fixed without regenerating.** When a reviewer found the Arabic beat too prominent on an occasion track, the fix was to pitch the whole file down about two semitones (`asetrate` × 0.88) or three (× 0.84) in ffmpeg. Done this way the tempo drops by the same ratio, so check the slower pace still fits the cut.
- **No voice-over by default** (section 1).

---

## Related

- [AI video and image generation](ai-video-and-image-generation.md) – models, the master formula, the cinematic triangle and what was approved or rejected
- [My Lightroom recipe](lightroom-recipe.md) – my interior presets and the window mask, with every value
- [Fidelity-first photo retouching](photo-fidelity-retouching.md) – the hard lines on generative AI and the measured reasons
- [Occasions calendar and visual guide](designing-for-gulf-occasions.md) – every occasion, its date rule, motifs and imagery to avoid
- [Design and deck craft](design-and-deck-craft.md) – the slide rules in full
- [My creative bar](my-creative-bar.md) – how I judge whether something is finished
- [Learning an editor’s style](learning-an-editors-style.md) – cut rhythm and story shape measured from finished timelines
- [AI music prompting](ai-music-prompting.md) – music tools, the Arabic element rule and ready-to-use prompts
