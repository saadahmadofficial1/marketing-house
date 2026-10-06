# How Saad edits — observed, not assumed

> Companion pages: [Saad's editing style, full playbook](editing-style-full.md) · [learning an editor's style from finished timelines](learning-an-editors-style.md) · [the CapCut hub](capcut.md)

Read off his real sessions: the CapCut project file for what changed, in his own numbers.
**An action seen once is an observation, not a habit.** Ask him what it was for before turning
any of it into a rule — in one August session a zoom to 248% was read as a style choice when he was only
magnifying the preview to look at it.

"The AI build" below is the first assembly an AI agent made; "his final" is the cut Saad
finished from it. Training modules are labelled A to E in place of their real titles, and
on-screen role and screen names from the training software are replaced with neutral ones.

---

## Session 1 (August), module A (a multi-role process) — 29 minutes, 216 moves

**He works in two directions at once: he cuts the dead, and he holds the important.**
Net effect on a 291s video: **−14.4s of dead time, +8.9s of holds, 5.5s shorter overall.**

### Ripple deletes — removing dead time

Four of them, closing the gap on every track at the same instant:

| Removed | Clips closed up |
|---|---|
| 6.10s | 66 |
| 3.33s | 22 |
| 2.47s | 20 |
| 2.50s | 18 |

**His method, read from the file:** split every track at the point → trim the head off the
right-hand piece → slide everything downstream earlier by exactly that amount. Video, audio,
captions and call-outs all move together, so nothing drifts out of sync.

**This is the thing the pipeline does not do.** The pacing tool ([`sa_dubcut`](../tools/sa_dubcut.py)) paces each segment to its voice
line but never removes a stretch that is simply boring. He is cutting roughly **5% of the
runtime** by hand, every video. Candidates are the quiet stretches between narration lines —
the same places [`sa_boxcheck`](../tools/sa_boxcheck.py) `--gaps` samples.

### Freeze frames — holding the important

Five, all built the same way: insert a still at the cut, then trim it back to the hold he
wants.

| Inserted | Settled at |
|---|---|
| 5.0s | 2.30s |
| 1.5s | 2.30s |
| 5.0s | 2.30s |
| 5.0s | 1.37s |
| 1.4s | 0.67s |

**Median hold 2.30s, range 0.67–2.30s.** He reaches for 2.30s repeatedly — three of five
landed there exactly.

Careful with this one: these are five moments *he chose*, not every gap in the video. It says
"when he decides a screen needs to land, he gives it about 2.3 seconds", not "every gap should
be 2.3 seconds". `DEFAULT_GAP` is 0.9s; that is the floor between ordinary steps, and the two
numbers are not in conflict. It matches his re-cut of another module (six freezes, 0.84–4.67s, median ~1.7s).

### Pace of work

Median 5 seconds between actions across 29 minutes. He works continuously, not in bursts.
Movement is decisive — median repositioning step 350px, largest 3205px — and then he stops.
Only 4% of moves were 10px or less, so the "nudge by 2 pixels" habit is real but rare: he
lands it, and only occasionally goes back to close the last few pixels.

### What was NOT a finding

- **The captions were not mistimed.** 84 caption segments slid earlier, which looked at first
  like the AI's caption timing running late. They moved because *he* ripple-deleted and everything
  downstream closed up. The captions were correct and stayed correct.
- **The zoom to 248% was not a style choice.** He was magnifying the preview to inspect it.

Both of those looked like solid conclusions from the numbers alone. Neither survived asking
what actually happened.

---
## Session 1, live-watch log (morning) — 69 frames

**Where he spent the time:** timeline ×54, preview ×8, dialog ×3, media library ×2, other ×1, timeline | preview | text panel | effects | export | media library | dialog ×1

**Most repeated on-screen action:**
- mid-edit (×6)
- mid-editing (×3)
- mid-editing timeline (×2)
- mid-editing the timeline (×1)
- no visible video content or specific elements on screen, mid-edit state (×1)
- selecting media for clipping in mid-edit mode (×1)

---

## Module A — the AI build against his final cut (session 1)

Module A's body was final (only the intro and outro were still to come), so for the first time
the whole build could be diffed against a version he is happy with. **This is the most useful
comparison available, and it should be run on every video he signs off.**

| | AI build | his final |
|---|---|---|
| Length | 291.7s | **253.9s** (−37.9s, −13%) |
| Call-out PNGs | 18 | 18 (none dropped) |
| Call-outs he typed by hand | — | **+5** |
| Freeze frames | **0** | **6** (median 2.83s) |
| Time each call-out is on screen | median 3.10s | **median 1.60s** |
| Tracks | 19 (one per call-out) | **10** (all call-outs on one lane) |
| Video segments | 1 | 41 |

### The five he had to add himself

| At | Label |
|---|---|
| 17.2s | Click New Record |
| 88.0s | **Sign in as (second role)** |
| 152.3s | Click to Generate Document |
| 162.0s | **Sign in as (third role)** |
| 214.1s | Click to Complete |

All five are either a **role switch** or the **primary action button** on a screen. Typed in
**Poppins Medium, size 5**, on screen 1.60–1.97s.

### The systematic bug behind them

The call-out planner treats "sign in" as an opening step, so it marks the FIRST one and never
the switches that follow. Checked across the series — the script tells the trainee to change
role **30 times; there are call-outs for 13**. Short single-role videos are perfect (1 for 1).
The long multi-role ones are not:

| Video | Role changes | Call-outs |
|---|---|---|
| Module B | 4 | 2 |
| Module D | 4 | 1 |
| Module A | 4 | 1 |
| Module E | **10** | **1** |

**17 role changes across the series with nothing on screen.** In a multi-role process video a
role switch is a navigation landmark — the trainee has to be told they are now a different
person. Mark every one, not just the first.

### What to change in the pipeline

1. **A call-out at every role switch**, not only the first. Detect `sign in|sign out|sign back
   in` in each script segment.
2. **Halve the call-out hold.** 3.10s is roughly twice what he leaves it up; he settles near
   1.6s.
3. **Cut dead time.** He removed 13% of this video by hand. `sa_dubcut` never does this.
4. **Freeze frames belong in the build**, not left for him — 6 here, median 2.83s.
5. **Stop building one track per call-out.** 19 tracks is unusable in CapCut; he consolidated
   to a single lane. Keep the named layers, put them on one track.

---
## Session 1, live-watch log (afternoon) — 203 frames

**Where he spent the time:** timeline ×146, preview ×24, text panel ×15, media library ×4, timeline | preview | media library ×2, other ×2

**Most repeated on-screen action:**
- mid-edit (×11)
- mid-editing (×7)
- mid-editing video clips (×4)
- mid-editing video content (×2)
- mid-editing with mask settings (×2)
- mid-editing video clips on timeline (×2)

---

## How he builds a call-out, caught in the act (session 1, module A)

Screen and project file agreeing on the same second, at 88.0s — the exact place the build
failed to mark the switch to the second role:

```
11:32:00  timeline  ->  added a clip on "video" at 88.0s lasting 1.3s     <- the freeze
11:33:01  timeline  ->  added a clip on "text"  at 88.0s lasting 2.0s     <- the label
```

**His recipe: freeze the frame first, then lay the label over it, label slightly longer than
the freeze.** Both anchored to the same timestamp. It matches the measured numbers from the
rest of the session — his freezes run 1.13–4.17s, his hand-typed labels 1.60–1.97s.

That is the unit to build. Not a box floating over moving footage, and not a freeze on its
own: a short still with a label on it, the still ending just before the label does.

**On the screenshots as a source.** Of 203 frames, 146 were read as "timeline" and the
descriptions were generic — "mid-edit", "mid-editing". The screen half earns its keep for two
things only: **what was selected** (it read the names of the selected marking PNGs and of the
paced picture file) and **which dialog was open** (a payment dialog, a receipt, CapCut's
project details). Ask it those two questions and nothing else. The project
file remains the source of truth for what actually changed.

---

---

## Session 2 (September), module B insert — 5 hours, 117 saves, the AI build against his final

The first time a whole AI-built INSERT went through his hands end to end. He kept every voice
line and every marking file, and re-cut almost everything around them. Exact evidence: one
live-watch session (117 timeline saves, before/final drafts, 356 frames;
38 frames viewed, one per 5-minute bucket, denser in the edit bursts).

| | AI insert (v7) | his final |
|---|---|---|
| Length | 175.1s | **159.1s** (237.0–396.1, −9%) |
| Picture | one paced file, 29 rows | **the AI's paced file cut into 20 pieces + 9 muted raw clips (48.9s)** |
| Freezes | baked into the paced file | **11 "Freeze" stills on top, median 3.0s** (1.2–8.8) |
| Call-out hold | median 2.47s | **median 1.73s; eight set to exactly 1.50s** |
| Call-outs moved | — | **15 of 22 nudged**, 5 login boxes moved ~230px down |
| His own assets pulled in | — | 3 marking PNGs + 1 original narration line |
| Voice lines split | — | **3 long lines cut into two pieces at the action** |

### What he does with a login

He does not mark the search field. All five "Sign in as…" boxes (c01, c06, c15, c16, c18)
were moved down 0.21–0.23 of the canvas — **onto the role's row in the account list**, the
thing the trainee actually clicks. And he does not use the AI's clean-instant freeze: he lays the
**raw recording of the sign-in** (2.0–5.3s of it, muted) so the typing and the account choice
are seen, then a 2.4s still. He had asked that day for the sign-in to be shown, and he cut
it that way. Privacy cost: a raw sign-in recording can show a real account list with staff
names, so check it before anything is published.

### Where the words land

- **A compound line is split at the action.** L10 "…select the option, / then click
  Confirm…" became two clips 5s apart so "then click Confirm" plays on the Confirm click. L05 and L15
  split the same way (4.1s gap). One narration file per *action*, not per sentence.
- **Explain the workflow chips at first sight.** L13's stage list (8.8s) was moved from 321s
  to 252s — right after the line that opens the record, the first time the chips are on screen —
  over a frozen still with the chips box held for the whole line. The second half he replaced
  with a new sentence of his own, saying who reviews the items and which stage the record
  moves to next, and had a fresh voice line generated for it the same afternoon.
- Captions kept (45 of 49), 3 retyped, 3 re-made for the moved line. Caption style is his
  usual: bottom, 75% scale.

### Markings he had to add himself (the planner's blind spots)

| At | What | How |
|---|---|---|
| 274s | Open the task list (as the second role) | his own marking PNG from the original video, scaled to 54% to fit the sidebar item + his original narration line |
| 323s | A review-queue menu item | his own marking PNG |
| 336s / 353s | Open the record from the review-queue tile | the AI's `c04` reused, twice |
| 341s | Add any notes | his own marking PNG |
| 358s | Complete the final verification → task list → record | **missing entirely** — he asked the AI for the lines afterwards |

Same lesson as module A: every navigation click (menu item, queue tile, tab) and every
text-entry gets its own marking; a step is not "covered" by the line that mentions it.

### Hold and freeze numbers (his)

- Call-out on a moving screen: **1.5s**. On a frozen explanatory screen: the whole line
  (c14 held 8.83s while L13 played).
- Freezes: 1.2, 1.3, 1.5, 2.4, 2.8, 3.0, 3.5, 3.5, 4.2, 5.0, 8.8 — median **3.0s**; the final
  approval table held 15s under the closing lines.
- Nudges on the AI's boxes: 2–5% left, 2–12% down; two boxes scaled (0.88, 1.19–1.31) to fit the
  control. The AI's boxes sit slightly up-right of where his eye wants them.
- He used raw clips with the Chrome tab strip visible (no crop) — tolerance, not a preference.

### What to change in the pipeline

1. Login marking = the role row in the account list; picture = raw sign-in, not a clean still.
2. Split every compound "do X, then Y" line into two audio files at the action boundary.
3. Workflow/stage explanations play at the first sight of the element, over a freeze, with the
   box held for the line.
4. Default call-out hold 1.5s; full-line hold only on a frozen screen.
5. Mark every navigation click and text entry; check the original video's marking set and
   narration first — he reuses his own assets when the step already exists there.
6. Freezes are layered stills, not baked into the paced picture, so he can trim them.

---

## Session 3 (September), module C (role-by-role series) — AI build (233.9s) → his cut (180.4s, −25%)

He kept all 30 markings, all 32 voice lines and the picture the AI paced; he **cut 57.5s in 16 ripple
deletes**, moved 11 markings, re-flowed the captions and rebuilt the ending. Read off the project
file; the rules below are measured, and the confidence tag says how many instances back each one.

### Pacing — the thing the AI build got wrong
- **After a line ends on a settled screen: 0.3–0.6s** (median 0.6, never past ~1.0). The AI's rows held
  the frozen tail for the whole row — that was the single biggest source of his cuts.
- **An action between two lines: 1–3.5s** (median 2.3) — the click and the state change, nothing else.
- **A result moment (toast, success modal): ~4.5s.** Do not apply the 0.6s rule there.
- **Silent rows ≤2.5s he leaves alone; ≥2.7s he cuts** unless it carries a marked result or a demo.
- Loading spinners, the middle of typing, and scrolling a list to the chosen option: **cut**. The
  next row's first frame already shows the outcome; he jump-cuts to it, mid-motion if needed.
- An interaction already shown once (search-and-pick a person) is **not shown again** — only its result.
- **No pre-roll:** he cuts to the audio clip's edge, so the gap he judges is voice-end → voice-start.
- **A line is paced to its referents, not to one source span.** If a clause names a screen the picture
  doesn't show, he cuts the picture under the line at the clause boundary (he split L16 in three).
- A freeze under a line is fine at any length (5.5s seen) **provided the words are about that screen**.

### Markings
- **Explanatory marking on a frozen screen: starts at first sight of the element, holds to the end of
  the explanation** — not a 1.5s word cue (b15 1.6→5.2s). Conversely a hover held under a line gets
  cut to the words (b13 4.5→1.67s).
- Hold = the span of the clause that names the control (+0.2 lead, +0.3 tail), extended through any
  silent row that demonstrates it. Never derived from row type.
- **Login box = the list-item rectangle** (dropdown width × row band), never the text bounds (b01 ×1.515).
- **Row/card box = the row's own container** — the card or modal edge (±3px), never the table width,
  never across the sidebar or off the modal onto the backdrop (b08, b03).
- **Buttons get air:** ~12px each side of a filled blue button, box centred (b28 ×1.134).
- **One box per named text entry:** a line naming two fields gets two boxes back-to-back, 1.5s each;
  the second carries no chip (b17 duplicated onto the ID-number field).
- Box geometry is measured on the frame at the **marking's own start**, not the row's first frame —
  validation messages move the fields after a partial entry.

### Chips
- **Chip sits beside the control, level with it, over empty space.** Fallback order when "above" is
  blocked: right-level → left-level → below with left edges aligned; stay inside the control's own
  container (b01 onto the dark panel, b03 below the row, b06 right of the sidebar item, b15 top-right).
- A chip that merely repeats the field label it covers is **fine** — he moved none of the nine form-field chips.
- A marking on a list must leave the sibling options visible: the box chooses, the chip must not hide
  what it is choosing between.
- **Occlusion is a build-time gate:** run the check on the rendered cut before install ([`sa_occlude.py`](../tools/sa_occlude.py)).
  4 chips shipped on content and cost him 4 of his 11 moves.

### Captions (58 → 57, re-flowed)
- 46 characters is the **target for starting a new cue, not a cap** — up to 54 to keep a phrase whole.
- Break at punctuation (full stop / colon > comma) when it falls within a word of the greedy cut;
  never end a cue on the first words of a new sentence; never end on a bare "and"/"or".
- **Never tear a capitalised name or UI string** across cues (a role label with its colon, a
  full status message such as "New Item Needs Assignment."). Two short sentences may share a cue.

### Ending
- Cut at the last click — loading/result footage after it is dead time. **The still is the result.**
- Closing freeze = a **separate still layer** (PNG of the settled screen), never a hold baked into the paced file.
- **~2.2s of silent still, then the sign-off, then ~0.6s tail** (≈ line + 2.8s), then the series outro
  appended at the still's end. Silence goes before the goodbye, not after it.
