# AI music prompting – regional identity without cliché

How I prompt AI music tools (Suno and MiniMax Music) for brand audio with a Gulf and Arabic identity: on-hold and phone-system loops, occasion beds and long event cues. It covers the rule I started with and how one round of feedback reversed it, the standing never and always lists, the negative prompt, every ready prompt in full, and the fixes that worked after generation.

**What does the work:** [`sa_beats.py`](../tools/sa_beats.py) (beat grid and energy peaks, so cuts land on the music) · [`sa_tailkit.py`](../tools/sa_tailkit.py) (back-times the last stretch of music so the track’s real ending falls on the final frame) · `ffmpeg` for the pitch fix in §7.
**Read with:** [My AI generation style](ai-video-and-image-generation.md) for the picture side, and [Thinking prompts](thinking-prompts.md) for the blind-spot check that caught the event-coverage problem in §9.

| Part | Status |
|---|---|
| On-hold / phone-system prompt set | **Pilot** – the reviewer confirmed the final direction; refinement continued from there |
| The regional-identity rule (and its reversal) | **Built, in use** – applied to every music prompt since |
| Pitch-down fix for an over-prominent beat | **Pilot** – used on one track |
| Long event cues and matched sets | **Experimental** – method written for one event brief and checked against the tool’s documentation; not run end to end |

The prompts and rules are mine, written with Claude. Brand names are replaced with “the brand”, and no reviewer is named.

---

## 1. The use case: on-hold and phone-system music

| | |
|---|---|
| **Purpose** | Music that plays while callers wait on hold across every business line |
| **Format** | Instrumental only, seamless loop, no vocals |
| **Feel** | Luxury corporate: confident, premium, regional in identity without being folksy |
| **Structure** | About 30-second music segments, with short bilingual voice messages between them – Arabic first, then English. Professional, warm, proud |
| **The brand’s standing direction** | Premium, clean, minimalist, elegant. Never generic, never boring |

---

## 2. The tools (as of May–August 2026)

| Tool | Prompt style | Use it for |
|---|---|---|
| **Suno** | Short, tag-driven, in square brackets: `[genre, BPM, instruments, mood, style references, no vocals]` | Most generations. Credits are limited, so I pick one or two prompts per round rather than spraying |
| **MiniMax Music 2.7** | A descriptive paragraph | More control over feel and texture. To tone the regional element down, remove the instrument names and describe the feeling instead |

Suno facts I checked against its help centre in August 2026:

- **Length:** versions 4.5 and 5 generate up to **8 minutes in one go** (4 minutes before 4.5), and Extend adds more. A 5-minute event cue needs no stitching.
- **Commercial recordings are blocked as references.** Uploads are fingerprinted, and recognised commercial recordings are refused (“Uploaded audio matches existing work of art”). Speech-to-text also matches lyrics, so one recognisable line trips it. It is a copyright problem for paid work anyway.
- **Cover is not “something similar”.** Cover keeps the original melody and arrangement: upload a track and you get the same track re-skinned, not a sibling piece.

---

## 3. The regional-element rule, and how feedback reversed it

This is the most useful lesson on the page. A rule that sounded right was followed exactly – and that was the problem.

| Round | What came back | What changed |
|---|---|---|
| 0 | A stakeholder supplied three long, descriptive prompts; the results didn’t land | **Rule:** Suno prompts are short and tag-driven, not long sentences: genre tags, a BPM range, key instruments, mood, and one or two style references |
| 1 | The first three prompts lacked a distinct identity; they could have been for anyone | **Rule v1 – “the Arabic soul should be felt, not heard.”** Regional character always present, never dominant. **Don’t name Arabic instruments** (oud, nay, darbuka): the tools then generate full Arabic music. Describe the feeling instead – “subtle modal colour”, “Middle Eastern warmth”, “a hint of Eastern scales”. Oud and qanun as background texture, never the lead |
| 2 | The reviewer heard **nothing regional at all** | **Rule reversed.** The identity must be **clearly audible**: a listener should know at once that this is Gulf music. Oud or qanun gets a real melodic role. Frame it as **cinematic Arabic**: film-score quality, not folk, not Gulf pop, not wedding music. Premium stays; identity must not be hidden |
| 3 | One generated track was judged promising | Direction confirmed: the identity was now landing. Refine that track rather than start again |
| Separately | On another piece, the Arabic beat was too prominent | Pitch it down after generation (§7) rather than regenerate |

**What I take from it:**

- **“Describe the feeling, not the instrument” is a dial, not a law.** Naming instruments pushes the tool all the way to traditional music; describing feelings can push it all the way to generic. Set the dial by how much identity the listener must *hear*, then name the instrument and its role precisely (“oud as the lead melodic voice”, not just “oud”).
- **Write down what the reviewer said and what they meant.** A request for subtlety in round 1 meant present but tasteful, not absent.
- **Don’t merge feedback across projects.** A note meant for another job stays out of this brief, even when it arrives alongside feedback on this one.

---

## 4. Standing rules

**Never use:**

- Arabic jazz
- A lounge feel
- Piano as the lead instrument
- Gulf folk (traditional folk, wedding music, dabke) or Gulf pop
- Trance or EDM
- Saxophone
- Generic corporate muzak

**Always include:**

- A **clearly audible** Arabic and Emirati identity (updated after round 2)
- Cinematic quality – orchestral, film-score standard
- A luxury corporate feel
- Something unique, never generic
- No vocals
- A seamless, loop-ready structure
- Professional and relaxing, but not boring

**The target feel:**

> **Cinematic Arabic luxury** – like a film score set in the Gulf. Oud or qanun with a real melodic presence, orchestral strings supporting. Instantly recognisable as Gulf music; premium and modern. Not folk, not jazz, not hotel-lobby ambient, not generic.

These rules belong to the on-hold brief. An event brief can want the opposite – a traditional folk piece, for example – so the rules travel with the brief, not with the tool.

---

## 5. The negative prompt

Add to every Suno generation for this brief:

```text
no arabic jazz, no lounge, no piano lead, no khaleeji folk, no trance, no saxophone
```

---

## 6. Ready prompts, in full

### 6.1 The earliest set – instruments named, before the rules

Kept because it shows the starting point. Several of these break the rules that came later: “Arabic lounge”, “corporate lounge”, piano in the mix.

```text
[corporate ambient, Arabic lounge, 72 BPM, oud, qanun, soft strings, piano, ambient pads, warm bass, seamless loop, UAE luxury brand, professional, relaxing, not boring, no vocals]
```

```text
[modern Middle Eastern, 68 BPM, electric oud, light piano, subtle darbuka, cinematic strings, corporate lounge, elegant, uplifting, loop-ready, no lyrics, inspired by Baligh Hamdi meets Hans Zimmer]
```

```text
[Arabic ambient, 60 BPM, nay flute, soft piano, warm pads, light strings, meditative, spa-like, professional, UAE-inspired, instrumental, loopable, no percussion]
```

```text
[corporate pop, Middle Eastern fusion, 80 BPM, acoustic guitar, oud, piano, light percussion, positive, optimistic, brand-forward, professional, no vocals, loop]
```

```text
[classical Arabic orchestral, 65 BPM, full string section, oud solo, qanun, light brass, majestic, dignified, luxury, Emirati heritage feel, cinematic, instrumental only]
```

```text
[chillout lounge, Arabic electronica, 74 BPM, oud sample, deep piano chords, ambient synth pads, soft bass pulse, modern UAE luxury, no vocals, seamless loop]
```

### 6.2 Suno, identity felt (round-1 direction – superseded, but useful when you need less)

**1 – Signature brand hold**

```text
[corporate ambient, 72 BPM, subtle Middle Eastern warmth, soft strings, ambient pads, warm bass, cinematic, seamless loop, UAE luxury brand, professional, unique, not generic, no vocals]
```

**2 – Modern corporate fusion**

```text
[modern Middle Eastern fusion, 68 BPM, cinematic strings, subtle Eastern modal color, corporate lounge, elegant, uplifting, loop-ready, no lyrics, inspired by Hans Zimmer meets Gulf identity]
```

**3 – Pure calm / waiting room**

```text
[ambient corporate, 60 BPM, warm pads, light strings, meditative, spa-like, professional, hint of Eastern scales, UAE-inspired, instrumental, loopable, no percussion]
```

**4 – Uplifting and energetic (shorter holds)**

```text
[corporate pop fusion, 80 BPM, acoustic elements, light percussion, positive, optimistic, brand-forward, subtle Middle Eastern soul, professional, no vocals, loop]
```

**5 – Heritage prestige**

```text
[classical orchestral, 65 BPM, full string section, light brass, majestic, dignified, luxury, Emirati heritage atmosphere, cinematic, instrumental only, no vocals]
```

**6 – Contemporary luxury**

```text
[chillout corporate, 74 BPM, deep piano chords, ambient synth pads, soft bass pulse, modern UAE luxury feel, subtle Eastern warmth, no vocals, seamless loop]
```

**7 – After the round-1 notes**

```text
[luxury corporate cinematic, 70 BPM, subtle Arabic soul, unique identity, not generic, confident brand music, warm strings, ambient depth, Emirati DNA, no Arabic jazz, no vocals, seamless loop]
```

**8 – Soft drop (for longer holds)**

```text
[deep corporate ambient, 72 BPM, slow build, soft cinematic drop, warm bass pulse, subtle Middle Eastern modal scales, elegant tension and release, luxury feel, no EDM, no vocals, loop]
```

### 6.3 Suno, identity audible (round-2 direction – current)

**9 – Cinematic Arabic luxury** (try this first)

```text
[cinematic Arabic orchestral, 68 BPM, oud melody lead, orchestral strings, qanun accents, maqam Rast scale, luxury corporate, [city] identity, majestic and dignified, no folk patterns, no khaleeji pop, no Arabic jazz, seamless loop, no vocals, film score quality]
```

**10 – Emirati heritage cinematic**

```text
[Arabic cinematic, 70 BPM, oud as lead melodic voice, full string orchestra supporting, maqam Hijaz color, grand and dignified, Gulf identity, modern luxury, Emirati heritage atmosphere, Hans Zimmer style arrangement, no vocals, no folk, seamless loop]
```

**11 – Modern Gulf corporate**

```text
[modern Arabic corporate, 72 BPM, qanun melody, warm orchestral strings, ambient pads, Emirati soul, premium brand music, clearly Middle Eastern, confident and majestic, no Arabic jazz, no lounge, no folk, no vocals, loop-ready]
```

Some tools strip or refuse named-artist references. If yours does, describe the arrangement instead – “big film-score strings, low brass, wide cinematic mix”.

### 6.4 MiniMax Music 2.7

**1 – Main hold** (written for rule v1: the regional element subliminal)

```text
Generate an instrumental track for a luxury corporate IVR system. The music should feel premium, confident, and distinctly UAE in identity — not generic international corporate music. Include warm orchestral strings, a subtle hint of Middle Eastern modal scales felt as atmosphere rather than featured, ambient pads underneath, and a gentle bass foundation. BPM around 70-72. The Arabic influence should be subliminal — present in the harmonic color, not in any folk instrument patterns. Seamless loop, no vocals, professional and relaxing but never boring. This is for [the brand], an Emirati group with [N] years of heritage.
```

**2 – Toned down after round 1** (outdated: too subtle – nothing regional was audible)

```text
Generate a luxury corporate ambient track at 70 BPM for a UAE group's phone hold system. Keep it cinematic and premium — imagine a high-end hotel lobby in [city]. Warm strings lead with ambient pads and a subtle bass pulse. The Middle Eastern identity should live in the mood and harmonic texture only — no featured Arabic instruments, no folk patterns, no jazz influence. The feeling is: confident, heritage-rich, modern Emirati luxury. Seamless loop, fully instrumental, unique and memorable.
```

**3 – Cinematic Arabic** (recommended after round 2)

```text
Generate an instrumental track for a luxury UAE group's IVR phone system. The music must be instantly recognizable as Arabic/Emirati — not subtle background texture, but genuinely present and proud. Feature an oud as the lead melodic voice playing in maqam Rast or Hijaz, supported by a full orchestral string section, light qanun accents, and ambient pads underneath. BPM around 68-70. The tone is cinematic and majestic — like a film score set in [city]. Grand, dignified, and premium. This is NOT folk music, NOT khaleeji pop, NOT Arabic jazz — it is cinematic Arabic luxury. [The brand] is a [N]-year-old Emirati group and the music must reflect that heritage with confidence. Seamless loop, no vocals, professional.
```

### 6.5 What made the strongest prompt work

The track judged most promising came from a reformatted version of the round-2 prompt. Six things that version added made the difference:

1. **A narrative arc** – a solo oud opens, strings swell in the middle, a final lift resolves back into the loop.
2. **A specific lead** – “Hijaz-mode oud lead”, which is sharper than “maqam Hijaz” alone.
3. **Deep frame percussion** – frame-drum texture, very Gulf.
4. **Low brass** – grandeur.
5. **“Heroic, wide-screen mix”** – a spatial cue that tells the model it is a film score.
6. **Negatives as inline tags at the end** – a more effective format for Suno than a separate sentence.

A template that applies all six. It is a template, not the tested text:

```text
[cinematic Arabic orchestral, 68 BPM, Hijaz-mode oud lead, solo oud opens then orchestral strings swell, deep frame percussion, low brass, final lift resolving into a seamless loop, majestic, dignified, luxury, heroic wide-screen mix, film score quality, instrumental, no vocals, no folk, no khaleeji pop, no arabic jazz, no lounge, no piano lead]
```

---

## 7. Fixing a track after generation: pitch it down

When a generated track is right except that its Arabic rhythm sits too far forward, lowering the pitch softens the beat without a new generation:

```bash
# about 2.2 semitones down (0.88) – pitch AND tempo both drop by 12%
ffmpeg -i input.mp3 -af "asetrate=44100*0.88,aresample=44100,atempo=1.0" -q:a 2 output.mp3

# about 3 semitones down (0.84)
ffmpeg -i input.mp3 -af "asetrate=44100*0.84,aresample=44100,atempo=1.0" -q:a 2 output_deep.mp3
```

A technical note on that command, which is the one I used: `asetrate` slows the track as well as lowering it, and `atempo=1.0` changes nothing, so the result is also about 12% slower. To lower the pitch but keep the original tempo, restore it with `atempo` at the reciprocal (1/0.88 ≈ 1.136):

```bash
ffmpeg -i input.mp3 -af "asetrate=44100*0.88,aresample=44100,atempo=1.136" -q:a 2 output_same_tempo.mp3
```

Use 44100 only if the source is 44.1 kHz; check it first with `ffprobe`.

---

## 8. Long event cues and matched sets

**The five-minute arc.** Five minutes at constant maximum stops registering after about 90 seconds. Structure:

| Time | Section |
|---|---|
| 0:00 | Build |
| ~1:30 | First hit |
| ~2:15 | Drop to near-silence |
| 2:15–4:00 | Rebuild |
| ~4:00 | Full climax |
| End | Ring-out |

The drop is what makes the return land.

**A matched set for one event.** When several cues play back to back in the same room:

- **Lock the key before generating any of them**, or the transitions clash. Give every cue the same style DNA (for one epic-choral set: the same minor key, a wordless choir on open vowels, timpani, a low string ostinato, film-score orchestration, a live concert-hall sound, no electronics).
- **Vary the tempo and the lead section** so each cue has its own identity: one choir-led at a slower tempo, another with a brass ostinato in an odd metre and the choir held back for the climax.
- **“No lyrics” need not mean “no voices”.** A wordless choir keeps the power that stripping the voices out would lose.
- **Deliver WAV, 48 kHz, to the audio-visual team, not MP3.** Event rigs run loud, and MP3 artefacts show on a full choir climax.
- **Never upload the famous reference piece** (§2). Describe what you like about it instead.

---

## 9. Music beds for a live event

When a live performer cancelled the day before an event, three music beds were needed. The blind spot: the three slots added up to about **85 minutes**, and three ordinary tracks do not cover 85 minutes. The fix was **long-form beds of one to four hours**, one per slot, so nothing loops audibly.

The practical side:

- Streamed beds can carry **mid-track adverts**; use an ad-free account or offline copies.
- **Turn autoplay off**, or the player rolls into an unrelated video.
- **Never project the player’s interface** on the event screen.
- **Check the licence covers public performance** at a commercial event before relying on any streamed bed.
- Keep a recorded back-up on a separate device either way.

---

## 10. Fitting music to the picture

- **Cut on the music.** [`sa_beats.py`](../tools/sa_beats.py) gives tempo, beats, downbeat estimates and energy peaks, so montage cuts can snap to a beat.
- **Start the music exactly at the timeline’s in-point.** In my house style it is one of three tells that a cut is finished, alongside the attached logo outro and slow-fade transitions.
- **Make the music land.** Don’t butt-join loops and let the last one stop mid-phrase when the video ends. Back-time the final segment so the **file’s real ending falls on the last frame** (start = video end − tail length). [`sa_tailkit.py`](../tools/sa_tailkit.py) does this.
- **For the voice messages between hold segments,** use one consistent voice route for the whole set – see [Fish Audio voice cloning](fish-audio-voice-cloning.md).

---

## Maturity

The on-hold prompt set is a Pilot: the reviewer confirmed the direction and refinement continued. The identity rule is in use on every music prompt. The event-cue method is Experimental. Tool facts are dated May–August 2026 and will change.

## Related

- [My AI generation style](ai-video-and-image-generation.md) – video and image prompting, and its guard rails
- [Thinking prompts](thinking-prompts.md) – the blind-spot move that caught the coverage gap
- [Fish Audio voice cloning](fish-audio-voice-cloning.md) – the voice route for bilingual messages
- [Learning an editor’s style from finished timelines](learning-an-editors-style.md) – cut rhythm and transitions measured from my own finished timelines
- [The CapCut draft format](capcut-draft-format.md) – how music beds and sign-offs are placed
- [Style DNA](style-dna.md) – where the music rules sit in the whole look
- [Occasions calendar and visual guide](designing-for-gulf-occasions.md) – music direction per occasion
