# My creative bar

The standards I hold my own work to, and the ones I expect from anyone – a person or an AI agent – who works with me: how I judge a grade, a set, a frame, a cut and a caption; how I fix things; my red lines; and how to brief me and report back. I am a creative lead, not a programmer, and this page is the part of my work that is mine to pass on.

- **Where the bar is written into tools:** [`sa_guard.py`](../tools/sa_guard.py) refuses writes to signed-off work · [`sa_finaldiff.py`](../tools/sa_finaldiff.py) turns every correction I make to a timeline into a recorded defect · [`sa_titlecard.py`](../tools/sa_titlecard.py) bakes in the two-tier title hierarchy · [`sa_capcut_captions.py`](../tools/sa_capcut_captions.py) and [`sa_exportcheck.py`](../tools/sa_exportcheck.py) hold the caption rules · [`sa_tailcheck.py`](../tools/sa_tailcheck.py) catches picture that outlives its narration · [`sa_cull.py`](../tools/sa_cull.py) makes the contact sheets I judge a whole take from · [`sa_upscale.py`](../tools/sa_upscale.py) refuses protected product files · [`sa_provenance.py`](../tools/sa_provenance.py) keeps the evidence behind a claim
- **The bar applied:** [Style DNA](style-dna.md) · [Lightroom recipe](lightroom-recipe.md) · [Fidelity-first photo retouching](photo-fidelity-retouching.md) · [Learning an editor’s style](learning-an-editors-style.md) and [`SAAD_EDITING_GRAMMAR.json`](../Reference/SAAD_EDITING_GRAMMAR.json) · [Training-video production](training-video-production.md)

The tools were written by AI coding agents (Claude Code and Codex) under my direction and review. The judgement they encode is mine.

| Part | Status |
|---|---|
| The standards on this page | **Built, in use** – standing rules in my workspace that every agent reads |
| Rules enforced in code (frozen approved work, protected products, caption and export checks, correction diffs) | **Built, in use** |

---

## 1. The eye

**Grade strong, on the right lever.** A cautious, technically correct grade is a rejected grade, and a blanket-pumped one is too – they are the same failure in opposite directions. Global saturation plus global contrast gives an electric, fake-HDR sky; a neutral “safe” grade reads meek. Bright, punchy, deep blacks is the floor, not a style option. But the strength goes on one lever only: vibrance, not saturation; one colour channel, not the global slider. Colour noise reduction on, luminance noise reduction off, so detail stays sharp. The full numbers for my interiors are in [my Lightroom recipe](lightroom-recipe.md).

**Judge the set before the shot.** A set graded frame by frame never matches, however good each frame is. One preset across the set, then sync everything except white balance and exposure. Upscale or enhance first and grade last, because an AI upscale run after grading shifts colour and adds halos. The same instinct applies to generated work: in one series I re-anchored every still to bright natural daylight after the first pass drifted into autumn warmth, even though it made already-rendered clips stale. Consistency is worth the rework.

**Frame in camera.** Cropping is clean-up, not composition. Across 35 matched before-and-after pairs from one event shoot, the framing is unchanged in every one. When a job needed more landscape frames, the answer was to grade more landscape originals, not to crop portraits. Even the auto-straighten in my own tooling is deliberately timid: it only acts at half a degree or more.

**Check the composition, not the specification.** A file can pass every dimension check and still be wrong. A 9:16 file with a landscape picture floating inside it is a landscape picture. An over-the-shoulder shot that shows too much of the face has missed the brief. A scene that should hold one wallet and holds two is wrong at any resolution. I also watch for the models’ quiet defaults – a subject turned away from the action, Dutch angles creeping into dramatic scenes – and each one I catch becomes a permanent prompt clause.

**Sampling is not looking.** An automated audit once judged sixteen photo folders from four random samples each and wrote off one of them. The full contact-sheet review found it was the most complete set in the whole library. I review the whole take cheaply on contact sheets, name the rejects by number and reason – empty chairs, motion blur – and pick the hero myself.

**Every preset has an owner, a date and a scope.** I have had three approved looks supersede each other inside seven weeks, each for its own work. Quoting a banked recipe without checking whose approval it carries, and for what, is how you deliver a confidently wrong grade.

**My approval is a lock, not praise.** When I say a file is good, that covers that file – not the batch, and not the next version.

---

## 2. How I fix things

**The artefact is the specification.** When words fail, I hand over the thing itself – my finished exports, my own re-cut, my Lightroom catalogue – and the answer is read off the files, not off my sentence. My own re-cut of one training video produced constants no description could: seven razor cuts, six inserted freeze frames totalling 12.8 seconds, one dull 6.53-second stretch removed, and five of the six freezes landing exactly on segments already running at the speed cap. The video went from 140.9 to 147.2 seconds – longer, and longer was correct. On another timeline my in-point (213.0 seconds) overruled the project’s own stored export range (224.0 seconds), and mine was right. [`sa_finaldiff.py`](../tools/sa_finaldiff.py) now diffs every finished timeline I sign off against the machine-built one.

**Two tiers of text, never two of the same weight.** The title centred and larger; any supporting line smaller and lighter beneath it. Step labels with one part bold and the rest semibold – or, my own preference, medium – never both bold, because all-bold reads flat and crumpled. It recurs often enough that it is built into [`sa_titlecard.py`](../tools/sa_titlecard.py).

**Fix with fidelity, not cleverness.** When a code-rendered version of a video came back looking almost right but inconsistent, the instruction was to learn from my real finals rather than keep iterating the pipeline. A low-resolution original gets a tested non-generative upscale rather than a generative “enhance”, and the result is compared with the original at 100% on signage, numbers and window views, because that is where invention shows first.

**The prompt is the deliverable.** I often run generations myself, on free quota, from the prompts I am given. So a reusable, complete text prompt is frequently worth more to me than a batch of fired generations. And before hunting for a new engine, check what already exists: a voice I needed was one the house already used across other videos.

**Engineer the risk out, or don’t use the model.** When a model has to touch a real subject, make it impossible for it to invent: give it a first and a last frame that are both real photographs of the same thing, the last a tighter real crop, so it can only move the camera and the light. Where the risk is still too high – jewellery is the case – the answer now is no model at all.

**The deliverable stays editable.** Picture on its own track, every graphic its own draggable layer, every label a native text segment, the voice on its own audio track. A flat render is a preview, not a hand-over, because it removes exactly the work I keep for myself. The division is: the agent assembles, I polish.

**Approved work is frozen.** No tool re-grades or “improves” something I have approved; my approved file is the reference everything else is matched to, and running a tool over it destroys the reference. Originals are checksum-baselined before a pixel moves and outputs go to a parallel folder, with proof afterwards that nothing original changed. New work goes into a new CapCut project every time – never into mine.

**A correction only counts once it is in code.** A promise to remember is not a fix. Every recurring failure in my workspace was closed the same way: a hook that re-injects the rules on every turn; start-and-finish heartbeats on silent nightly jobs; a backup check that needs a verified log line and a real snapshot instead of reading the newest file in a folder; a call-out checker that freezes the exact rendered frame and looks, instead of only proving the background was still. The full story is in [Learning from mistakes](learning-from-mistakes.md).

---

## 3. The bar

**Premium is the strong move on the right lever, and zero on every wrong one.** In video that reads as restraint. Across fifty of my parsed CapCut projects, Slow Fade appears 53 times, Camera Glow 24, Gradual Fade 14, and Blur, at 22, is essentially the only effect. Calm dissolves, never flashy wipes. Let the video breathe; don’t fill every second with motion or text.

**One strong scene beats a montage.** A single eight-second cinematic shot is more powerful than a stitched sequence. If several scenes are genuinely needed, generate them at four seconds and combine no more than two. An intro is a reel: three to four seconds, one shot.

**A finished video has three tells:** the music starts exactly at the timeline’s in-point, the logo outro is attached, and the transitions are slow fades. I use them myself to tell which of several near-identical drafts is the real one. A cut missing any of them is not final.

**Derive from the masters; don’t invent a style per brief.** I name the master projects, and pacing, title hierarchy, voice-over sync, step labels, captions, transitions and timeline structure are derived from them before anything new is invented. Where earlier work already solved a slide, reuse its treatment verbatim and design only what is genuinely new. Two pacing modes came off my masters: screen-recording walkthroughs cut at a 4.0-second median shot with a text element roughly every two seconds; animated, illustrated scenes run about 8.0 seconds and stay text-light. The measured style is in [Learning an editor’s style](learning-an-editors-style.md).

**Caption craft is part of the deliverable.** Text sits in an invisible box with equal padding left and right, never flush to one edge. Long lines break at natural phrase boundaries. No all-caps tag dumps. Sentence case, lowercase except brands and acronyms. On-screen words match the narration word for word – if a card says “efficient” while the voice says “simple, fast, transparent”, the card changes. And every e-mail address and every word containing “fi” is eyeballed before export, because the editor’s kerning once split those words in two. More in [Style DNA, section 5](style-dna.md#5-captions).

**A screen recording is raw material, not footage.** Crop the browser chrome so no address shows. Cut a demonstration of a step the approved script removed. Flag anyone’s personal details visible in frame for a decision before anything is delivered. [Training-video production](training-video-production.md) has the full method.

**Complete, not condensed.** When someone senior has approved a message, every design option carries the complete wording and only the treatment varies. Simple, for me, means the words are simple – not that the content is thin. A course I commissioned was rebuilt three times for this reason: the light version was boring, the playful version hid the actual course, and the accepted one carries every module with nothing hidden.

**Density is a delivery criterion.** I watch to the end. A strong opening with a thin back half is a defect, and I will name it by timecode. Consistency of wording is the same kind of criterion: when a caption disagrees with the screen, the screen wins over the written spec.

**Read every frame for what the audience will infer.** No holy-site imagery for Eid Al Adha; lanterns belong to Ramadan and Eid Al Fitr; vehicles described by silhouette drift into famous competitors’ shapes; dense ornamental Arabic at full message length collides with itself. None of these is a craft error, and each would pass any technical check. The full list is in the [occasions guide](designing-for-gulf-occasions.md#4-imagery-that-is-culturally-wrong).

**Check at 200%, and know when to stop.** For anything real, the QA gate is a 200% zoom: reject at once if any letter, logo curve, structural member, railing, wall opening or edge has moved. The right answer to a third failed attempt is **omission** – ship the original or drop the frame – never a looser prompt.

**Credits are a ceiling, and the trade-off is said out loud.** On my plan, cheap models for prompt tests, a mid-price model as the default, the premium model only for hero posts, and nothing over 50 credits in one batch without asking. If a request would break the ceiling, do less at the approved tier and say so; absorbing it silently and letting me find out later is the failure.

**Never claim a capability that isn’t evidenced.** Label working, experimental and planned honestly, and keep the raw input, the result and the method behind any number. One inflated figure poisons every honest one beside it – the same goes for public copy, where an award or certification is only claimed once it is confirmed. That is why every page here carries a status label.

---

## 4. Red lines

- **Jewellery and fine products no longer go through a generative model.** It was tested: even the strictest retouch-only prompt rearranged stones. Real-pixel RAW edit or a non-generative upscale only, and the upscaler refuses protected files by name.
- **Real engineering and real property are never invented or reshaped.**
- **Event and brand content uses real footage and real photographs.** Only.
- **Approved and hand-edited files are frozen.** A new project every time; proof of non-destruction, not assurance.
- **Work material leaves only by an approved route.** Screen frames never go to generation services; other work media goes to a generation service only with my approval for that job, and the upload is logged; routine checks run locally and upload nothing. Nothing from work goes into a public repository – this one included – beyond generic methods and tools.
- **Reels are 9:16.** Verify the ratio and the composition before every generation; never auto-flip on an ambiguous “16x9”.
- **No hands in generated visuals, and no text, logos or people baked into generated video.** Real brand marks are composited in the edit, because models garble them and invent plausible company text.
- **Never shorten copy that someone senior approved.** Vary the treatment, never the sentence.
- **Never run unread code next to work files.** No blind one-line installers; no framework that quietly routes data off the machine.
- **Never present a roadmap item as a live capability.**
- **Heavy local compute only at night.** Large local vision batches run between 1 and 6 a.m.; my deadline work is on the same machine, and a batch that eats the memory makes my timeline stutter.

---

## 5. Working with me

**Decide the execution; spread the creative options.** Technical choices are made and stated, not offered as a menu – a menu hands the judgement back to me, and I have said I am not technical. Creative output goes the other way: three or four variations of the same idea, same mood, different scene, and I pick the hero rather than receiving a single finished cut.

**Use initiative with tools, inside a fence.** Install and use what makes the work better, then tell me. Three things still stop at me: my money, work data, and anything that needs a graphical installer or a new toolchain on the production machine. Unread code never runs next to work files: read it first, then bring me one line – this one, it does this, code checked, installing it. And an outside tool still has to win a measured head-to-head. On a real interview take, our own silence-trimmer ([`sa_tighten.py`](../tools/sa_tighten.py)) removed 31.9 seconds of dead air – 37% of the clip – and caught a repeated take, while a popular open-source editor’s default preset removed nothing.

**The broken foundation goes first.** I will reorder a plan so the thing that is quietly broken gets fixed before the clever features are built on it. In one case that ordering stopped a script that would have silently deleted records.

**A reviewer’s call is theirs.** When a decision belongs to the person who signs the work off, flag it with the options and the consequence; don’t make it for them.

**Tell the truth about conditions.** If a location, a source file or a schedule isn’t right, say so and recommend the fix – a reshoot, a new input – rather than dressing up what you have. And stop a running job the moment it is going wrong, with originals untouched and accepted work left where it is.

**I brief and leave.** Work is expected to carry on inside the fence I set while I am away. Pausing for a confirmation I am not there to give wastes the window; stepping past the fence breaks the one thing I made myself.

---

## 6. How to brief me and report back

I am a non-technical creative lead. Write to me the way I would brief a colleague.

**Reporting back:**

- **Result first.** About three short bullets in plain British English: what was done, where it is, whether it worked.
- **The file already open** in front of me. Something built and never opened might as well not exist.
- **Outcomes and locations, not flags and paths.** I don’t want less information – I want it as what happened and where.
- **One next action**, clearly mine or clearly yours.
- **Keep the written record current as you go.** I switch between AI agents when one hits a usage limit, and an unwritten state means the next one starts from nothing.

A constructed example of the same report, written twice:

> **Confusing:** Ran the locked enhance prompt across the folder tree; 58 stems reconciled against the ledger, zero duplicate/missing/original-only stems, outputs written to the parallel path, SHA-256 baseline re-verified byte-identical on retained originals.

> **Clear:** The folder is done and open on your screen – all 58 pictures. Nothing you had already approved was touched, and I checked the originals afterwards: none of them changed. One picture I left as the original, because the AI kept rewriting the lettering on a road sign.

Note what the clear version keeps: the count, the finding, the reason.

**Reading my briefs:**

- **I brief in one run, and every clause is live.** A single message can carry six or eight asks, including fences – don’t touch this, leave that alone. Enumerate my clauses back as a checklist and close every one; a do-not-touch item binds exactly as hard as a do-item. Answering only the loudest clause costs a whole round.
- **My negative verdicts are short and carry no diagnosis.** Finding the cause is your job; asking me what exactly is wrong hands my own work back to me. A vague count is an order to sweep, not to ask: when I said some call-outs were badly placed, a hand review of all 110 found 17 real errors that an automated check had passed.
- **My praise names the mechanism that worked** – that is the most useful feedback I give – and it often carries the one outstanding defect inside it. Find it.
- **My corrections are relative, never absolute.** Each note nudges away from the last version I saw, and I will reject the opposite extreme just as fast. Move one notch, show one sample, then batch.
- **A question may be an instruction, and an instruction may sound like a question.** If a clause names a deliverable and what I will do with it, build it. If it only asks whether something is possible, answer that first, before building anything.
- **Never hand me a command.** Run it. Only four things stop at me: passwords and admin rights, money, a permission I have to click, and anything physical.
- **Read past my typing.** My spelling in a chat is never the subject. The output is a different register: British English, sentence case, dates as 6 October 2026, and terminology checked against the real system rather than the script.
- **Check my claims too.** Verify what matters, say when you are unsure, and challenge me respectfully. Agreeing with something of mine that doesn’t hold up is a failure, not politeness. The prompts I use to get that behaviour are in [Thinking prompts](thinking-prompts.md).

---

## Related

- [Style DNA](style-dna.md) – the look on one page
- [My Lightroom recipe](lightroom-recipe.md) – my grade, measured from my own edits
- [Fidelity-first photo retouching](photo-fidelity-retouching.md) – clean and correct, never redraw
- [Learning an editor’s style](learning-an-editors-style.md) – my cut rhythm and story shape as data
- [Training-video production](training-video-production.md) – the bar applied to screen-recorded training
- [Learning from mistakes](learning-from-mistakes.md) – why only code stops a repeat
- [How I engineer with AI coding agents](ai-engineering-method.md) – evidence before “done”
- [Thinking prompts](thinking-prompts.md) – the prompts that make an agent check, critique and steelman
