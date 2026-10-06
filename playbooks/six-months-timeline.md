# Six months, month by month

From May to early October 2026 I set up and ran an AI-assisted media-production workspace on one Mac. I directed two AI coding agents, which wrote the tools: Claude Code throughout, and Codex from late June. This page is the timeline – what each month added, and which classes of problem were found and fixed along the way. The wording is generic on purpose: no projects, clients or people.

The detail lives in the playbooks and tools linked from each month. You can also start from the [tool index](../tools/README.md), the [starter kit](../workspace-kit/README_START_HERE.md) or the [engineering method](ai-engineering-method.md). The timeline was compiled from my work log, my fix log, the August mistake post-mortem and the workspace’s git history. The history starts on 19 June; May is reconstructed from the log.

**By early October:** 35 screen-recorded training videos (a 21-module end-to-end process series and 14 role-by-role modules) and 7 phone-app training videos – over two hours of finished training ([training-video-production.md](training-video-production.md)). Alongside them: a local memory, a CapCut project writer, and verification fleets. This repository publishes the generic subset of the tools behind all of that.

---

## At a glance

| Month | The shift | Main pages |
|---|---|---|
| May | Generating video by hand, and writing down the first rules | [ai-video-and-image-generation.md](ai-video-and-image-generation.md) |
| June | A memory and a local toolkit, so the agent stops starting from zero | [the-brain.md](the-brain.md) · [running-two-ai-agents.md](running-two-ai-agents.md) · [style-dna.md](style-dna.md) |
| July | A local-first studio: health checks, local vision, editing intelligence | [local-ai-on-a-mac.md](local-ai-on-a-mac.md) · [learning-an-editors-style.md](learning-an-editors-style.md) |
| August | Production at scale: writing CapCut projects, verifying them, and the post-mortem | [capcut.md](capcut.md) · [learning-from-mistakes.md](learning-from-mistakes.md) · [agent-organisation.md](agent-organisation.md) |
| September | Fleets of checkers, role-by-role re-cuts, phone-app recordings, a photo pipeline, one engineering method | [orchestrating-agent-fleets.md](orchestrating-agent-fleets.md) · [training-video-production.md](training-video-production.md) · [lightroom-recipe.md](lightroom-recipe.md) |
| October (to the 6th) | Code-rendered motion graphics, an event-film pipeline, and this portfolio | [code-rendered-motion-graphics.md](code-rendered-motion-graphics.md) · [learning-an-editors-style.md](learning-an-editors-style.md) |

---

## May 2026 – starting by hand

**Built**

- **Prompted image and video generation** for short vertical teasers and occasion greetings. The technique that worked was to generate anchor stills first, then make each clip travel *between* two anchors (start frame and end frame) so that the clips join. Reusing the first anchor as the last end frame makes the sequence loop seamlessly. The full craft – formula, camera moves, model choice and what was rejected – is in [ai-video-and-image-generation.md](ai-video-and-image-generation.md). The occasion work grew into an occasions calendar and visual guide ([designing-for-gulf-occasions.md](designing-for-gulf-occasions.md)).
- **Caption files** written alongside each generated piece, ready for assembly in CapCut.
- **The first written memory:** a file of corrections and a short list of standing instincts. Everything that followed grew from it.
- **One instruction file at the root of the workspace** rather than inside a project, so every job inherits the same rules.
- **AI music for brand audio** – on-hold loops and occasion beds with a regional identity. The rule I wrote after the first round of feedback was reversed by the second. The prompts, the never/always lists and the negative prompt are in [ai-music-prompting.md](ai-music-prompting.md).

**Problems found, and what changed**

| Problem class | What it looked like | What changed |
|---|---|---|
| Ask a model for a real thing, get its memory of it | Generic vehicle descriptions drifted towards other manufacturers’ cars | Name the exact model, constrain the angle, and state the exclusions several ways. Later came stronger rules: no generative AI at all on fine products such as jewellery, real structures never invented or reshaped, and generation boxed in tightly everywhere else ([photo-fidelity-retouching.md](photo-fidelity-retouching.md)) |
| Generate first, budget never | Paid generation credits ran out mid-project, twice | Cost noted per batch. Later ranked as a missing guard in the post-mortem |
| Over-correcting to feedback | One note swung the next version to the opposite extreme | Treat a note as a direction, and confirm the target before regenerating |
| Two rules that contradict | A banned-imagery rule was logged while an older prompt file still recommended that imagery | Later formalised as “patch the master, not the copy” ([learning-from-mistakes.md](learning-from-mistakes.md)) |

---

## June 2026 – a memory and a local toolkit

**Built**

- **A local memory server for the agent** (MCP), with briefing, search, log and recent-activity tools. Within the month it gained local vector search, then hybrid keyword-plus-vector retrieval with an entity boost and reranking. It also got a monthly consolidation pass, a small evaluation set (Recall@1/3/5 and mean reciprocal rank) and versioned backups. How it works: [the-brain.md](the-brain.md); how two agents share it: [running-two-ai-agents.md](running-two-ai-agents.md).
- **A note-vault layer** over the same files, with a vault health map ([`sa_vaultmap.py`](../tools/sa_vaultmap.py)).
- **A local media toolkit:** Whisper captions with British spelling; grading from house LUTs with ffmpeg; a pre-publish QA gate ([`sa_qa.py`](../tools/sa_qa.py)); a media asset index ([`sa_assets.py`](../tools/sa_assets.py)); Lightroom looks converted to `.cube` LUTs ([`sa_lut.py`](../tools/sa_lut.py), [`sa_xmp2cube.py`](../tools/sa_xmp2cube.py)); and a duplicate finder that quarantines rather than deletes ([`sa_dedupe.py`](../tools/sa_dedupe.py)). The Python dependencies are pinned in [`../tools/requirements.txt`](../tools/requirements.txt).
- **A session hand-off folder,** so a second agent can resume mid-task. It was later formalised in [`sa_session.py`](../tools/sa_session.py).
- **A one-page house-look reference** for video, stills and decks – guardrails, prompt formula, grades, captions, formats and sound ([style-dna.md](style-dna.md)). The deck part is distilled in [design-and-deck-craft.md](design-and-deck-craft.md).
- **Working discipline:**
  - the always-loaded instruction file was cut from about 230 lines to 34, so it costs less on every turn;
  - a sceptic pass before agreeing with anything, including me;
  - a library of thinking moves that fire without being asked ([thinking-prompts.md](thinking-prompts.md); how I prompt the agents generally: [how-i-prompt-ai-agents.md](how-i-prompt-ai-agents.md));
  - capability routing, so I never have to type commands;
  - a vetted-install record for outside tools ([template](templates/third_party_vetting_log.md));
  - compression of large tool output before it reaches the model ([`squeeze.py`](../tools/squeeze.py)).

**Problems found, and the fix**

| Problem class | What it looked like | Fix |
|---|---|---|
| A precision leak in retrieval | Short codes matched inside ordinary words, boosting irrelevant notes | Whole-word matching on both the index and the query side, and new evaluation cases. The evaluation harness itself was tested by feeding it a wrong answer it had to fail |
| A backup that couldn’t restore itself | The backup list missed the backup script and the evaluation set | The backup now covers its own tooling, and a restore was tested byte for byte |
| Two runs racing | A scheduled backup and a manual one collided on the git lock | An atomic lock with stale-lock recovery. Of three simultaneous launches, one ran and two skipped cleanly |
| Measuring yesterday’s build | The search index was two days stale | Re-index on search |
| Orphaned notes | Project notes linked to nothing, so the graph showed islands | Footer links on every note; the health map lists orphans |
| Install traps | `cp -R src/ dest/` spilled a folder’s contents instead of copying the folder; some installers run remote code | Copy without the trailing slash and check the result. Clone, read, then copy – never pipe a remote installer |
| Reading the words, not the intent | “16x9” taken literally midway through a vertical project | Verify the aspect ratio before every generation |
| “Improving” approved work | Approved finals were re-graded | Approved work is the reference – enforced in code in August |

---

## July 2026 – a local-first studio

**Built**

- **A health check** run at every session start ([`sa_doctor.py`](../tools/sa_doctor.py)), heartbeats on every scheduled job, and a backup freshness check.
- **A local web hub** on 127.0.0.1, with question-and-answer over my notes by a local model ([`sa_hub.py`](../tools/sa_hub.py)).
- **Local vision:**
  - describe a screenshot without loading its pixels into the chat ([`sa_peek.py`](../tools/sa_peek.py));
  - stream any video through a local vision model ([`sa_see.py`](../tools/sa_see.py));
  - explode a video into readable frames ([`sa_frames.py`](../tools/sa_frames.py));
  - a visual memory that pauses when an editing app is open and runs heavy batches only at night ([`sa_visualmem.py`](../tools/sa_visualmem.py)).

  How to run local models without hurting daytime creative work: [local-ai-on-a-mac.md](local-ai-on-a-mac.md).
- **Editing intelligence:**
  - my CapCut library mined into an edit-style reference ([`sa_capcut.py`](../tools/sa_capcut.py), [`sa_editdna.py`](../tools/sa_editdna.py), [`sa_stylebrain.py`](../tools/sa_stylebrain.py));
  - quality-scored shot extraction ([`sa_extract.py`](../tools/sa_extract.py));
  - vision-model cut sheets ([`sa_cutsheet.py`](../tools/sa_cutsheet.py));
  - a rough-cut tightener with an HTML edit-decision view ([`sa_tighten.py`](../tools/sa_tighten.py));
  - a reference-video analyser ([`sa_reel.py`](../tools/sa_reel.py));
  - my three approved tutorial edits decoded into reusable templates ([capcut-tutorial-masters.md](capcut-tutorial-masters.md), [capcut-tutorial-templates.md](capcut-tutorial-templates.md)).

  The measured style: [learning-an-editors-style.md](learning-an-editors-style.md), with the full write-up in [editing-style-full.md](editing-style-full.md) and the style brain as anonymised data in [`Reference/capcut_style_brain_anonymised.md`](../Reference/capcut_style_brain_anonymised.md).
- **Voice:** an SRT script turned into per-line voice clips with re-timed captions ([`sa_vo.py`](../tools/sa_vo.py)), and a browser voice-over studio ([`vo_studio.py`](../tools/vo_studio.py)).
- **Code-rendered video:** the first video rendered entirely from code, and a slide deck turned into a narrated video with no manual editing (*Pilot*). Both templates are in [templates/remotion/](templates/remotion/README.md).
- **Governance:**
  - an agent loop with an attempt ledger, a circuit breaker and a kill switch ([`sa_loop.py`](../tools/sa_loop.py), [constraints](templates/loop_constraints.json));
  - data classes, pinned plugins and provenance ([`sa_security.py`](../tools/sa_security.py), [`sa_provenance.py`](../tools/sa_provenance.py));
  - a runtime inspector ([`sa_inspect.py`](../tools/sa_inspect.py));
  - a browser approval console ([`sa_console.py`](../tools/sa_console.py)).
- **Sharing:** a starter kit, so a colleague’s agent can set itself up ([`../workspace-kit/`](../workspace-kit/README_START_HERE.md)), and an interactive course that explains the system.

**Problems found, and the fix**

| Problem class | What it looked like | Fix |
|---|---|---|
| Silence mistaken for success | A backup dead for 24 days; scheduled jobs stamping “ran” with nothing produced | Heartbeats paired with the health check. A job must leave a receipt |
| A check that dirtied its own repository | The health check wrote reports that git tracked, so every run looked like a change | Generated reports are untracked and rebuilt on every run |
| Self-tests nobody could reach | Three tools’ tests couldn’t be called | Fixed in a full audit. Since August, the generated tool catalogue flags any tool without a test |
| Stale pages | Local pages served from the browser cache; stale seed data in browser storage | No-store headers, and a guard against stale seed data |
| Local AI against the editing machine | Vision batches made editing stutter; models held memory after finishing | A night window, a background profile, a pause while the editing app is open, and model unload after a minute |
| A local model returning nothing usable | A newer “thinking” model’s replies weren’t being parsed | Handle the reply shape. Choose the model by a side-by-side test on real images |
| Robotic synthetic voice | Punctuation pauses were ignored | Per-phrase synthesis with inserted silences. The voices were still rejected after listening, which is the real test |

---

## August 2026 – production at scale

**Built**

- **A long screen-recorded software-training series moved from flat MP4s to editable CapCut timelines.** That meant captions as editable text layers ([`sa_capcut_captions.py`](../tools/sa_capcut_captions.py)), house-style call-outs ([`sa_stepmark.py`](../tools/sa_stepmark.py)), pacing to a replacement voice ([`sa_dubcut.py`](../tools/sa_dubcut.py)), title screens and outros. The method: [training-video-production.md](training-video-production.md).
- **CapCut’s undocumented project format,** mapped by the agents from my own projects and written safely ([capcut-draft-format.md](capcut-draft-format.md); everything CapCut in one place: [capcut.md](capcut.md)). ffmpeg can now render a CapCut project for review: in one overnight test it matched the exact length of 19 of 19 training timelines ([`sa_ffrender.py`](../tools/sa_ffrender.py), [`sa_ffbatch.py`](../tools/sa_ffbatch.py)). *Pilot* – review renders only, never delivery. There is also the SRT export CapCut lacks ([`sa_srtexport.py`](../tools/sa_srtexport.py)).
- **Verification:**
  - per-action coverage ([`sa_coverage.py`](../tools/sa_coverage.py), [`sa_actioncheck.py`](../tools/sa_actioncheck.py));
  - silent-tail detection ([`sa_tailcheck.py`](../tools/sa_tailcheck.py));
  - a pre-export check ([`sa_exportcheck.py`](../tools/sa_exportcheck.py));
  - an overnight local vision box check ([`sa_boxcheck_all.sh`](../tools/sa_boxcheck_all.sh));
  - an occlusion check ([`sa_occlude.py`](../tools/sa_occlude.py)).
- **Learning from my own edits:** an edit watcher ([`sa_editwatch.py`](../tools/sa_editwatch.py)), a final-edit diff ([`sa_finaldiff.py`](../tools/sa_finaldiff.py)), a learning curve ([`sa_learncurve.py`](../tools/sa_learncurve.py)), and my editing grammar read from approved timelines ([learning-an-editors-style.md](learning-an-editors-style.md)).
- **Animating still photographs.** The settings that worked:
  - use the model tier that renders native 1080×1920 (the cheaper tier came out at 720 wide);
  - generate the model’s minimum clip length and trim to the slot – never speed-ramp a slow move;
  - use a prompt that says *only the camera moves*, the subject is stationary, and every badge and lettering, named one by one, stays pixel-faithful;
  - test the hardest still before paying for the batch.

  When the model invented a background, grading the render didn’t fix it. Feeding a cut-out plate on pure black did. Where I rejected an animation, the slot kept the original still, and the finished piece was presented as created, not filmed. Details: [ai-video-and-image-generation.md](ai-video-and-image-generation.md).
- **The post-mortem:**
  - 76 mistakes in 16 patterns;
  - a pre-flight guard and an approved-freeze list built the same day ([`sa_guard.py`](../tools/sa_guard.py));
  - a fix log with eight failure classes;
  - the escaped-defect ledger ([learning-from-mistakes.md](learning-from-mistakes.md)).
- **Context that survives:** decision checkpoints as the context fills ([`sa_checkpoint.py`](../tools/sa_checkpoint.py)), and ground truth re-injected after compaction ([`sa_compact_brief.sh`](../tools/sa_compact_brief.sh), [`sa_threads.py`](../tools/sa_threads.py)). Why agents forget in the first place: [why-ai-agents-forget.md](why-ai-agents-forget.md).
- **A resumable overnight runner** that leaves a morning note ([`sa_nightly.sh`](../tools/sa_nightly.sh)), and an always-on-top, voice-enabled request window over the editor ([`sa_desk.py`](../tools/sa_desk.py)).
- **Live Arabic-to-English captions** that run locally and upload nothing ([`sa_livecaption.py`](../tools/sa_livecaption.py)).
- **An agent-organisation handbook:** six departments with charters, a catalogue of 72 narrow specialist roles, and the rule that a maker never verifies its own work ([agent-organisation.md](agent-organisation.md); the handbook itself ships in the [starter kit](../workspace-kit/README_START_HERE.md)).
- **Research:** 24 agent frameworks reviewed. The verdict was to install nothing and copy two ideas, plus a third ([ai-engineering-method.md](ai-engineering-method.md)). The repository-by-repository notes are in [repo-due-diligence-2026.md](repo-due-diligence-2026.md).

**Problems found, and the fix** (the full catalogues are in [learning-from-mistakes.md](learning-from-mistakes.md) and [training-video-production.md](training-video-production.md))

| Problem class | What it looked like | Fix |
|---|---|---|
| Happy path shipped, unhappy path destructive | `ffmpeg -shortest` cut the ending off 13 videos | Pad the audio, and assert every duration |
| A clone that opened its donor | New projects opened on the source project’s timeline | Write the per-timeline copy too, then read it back |
| The measurement lied | Every overlay was reported as 3–13× too small | Reproduce one case by hand. Fix the ruler, not the work |
| Checks keyed to names | “No captions” reported on fully captioned videos after I renamed a track | Key every check to content |
| A guard that could see itself | The nightly check refused every section because of its own keep-awake wrapper – and logged *ok* | Match the process actually holding the resource. Three outcomes: *ok*, *wrong*, *unknown* |
| A false learning | The diff credited me with labels the build had written | Anything that learns from a comparison must know what it produced itself |
| A donor that crashes the editor | The template project referenced footage that existed only in cloud storage | Donor rules: every media path present on disk, canvas already the target shape, fewest tracks |
| An error hidden by the sandbox | A file count in a protected cloud folder returned 0 and read as “empty” | Never discard error output when counting. Protected-folder checks go to a human |
| Field recipes | Choppy slow motion; a 16 GB cloud download that wouldn’t open; camera-card copies missing the card’s database folders; rushes too long to watch | Motion-compensated interpolation with an overshoot; carve stored entries from a zip with no central directory; check the card folders or image the whole card; a parallel agent cull with source timecode in every frame name ([media-ops-field-notes.md](media-ops-field-notes.md)) |

---

## September 2026 – fleets of checkers and new formats

**Built**

- **Every finished training video re-measured against the newer pipeline,** then revised surgically rather than rebuilt.
- **Role-by-role versions** cut by slicing finished timelines into new tabs ([`sa_timeline_slice.py`](../tools/sa_timeline_slice.py)). They got intros, outros, and music whose real ending lands on the last frame ([`sa_tailkit.py`](../tools/sa_tailkit.py), [`sa_introfull.py`](../tools/sa_introfull.py), [`sa_outro.py`](../tools/sa_outro.py)). By the end of the month the body of work stood at the 35 screen-recorded and 7 phone-app videos above.
- **Fleets of independent AI reviewers,** one per marking, each judging its marking’s start and end frames. They were used to find faults, never to approve:
  - one fleet of 132 agents checked two modules;
  - a later audit ran 332 agents – 137 checkers, one per beat, plus three refuters for every claimed fault – and confirmed 65 faults.

  The agents were reliable on faults, but several of their proposed *fixes* were guesses, so every fix was re-measured before it was applied. The method: [orchestrating-agent-fleets.md](orchestrating-agent-fleets.md), with the workflow scripts in [`../workflows/`](../workflows/README.md).
- **Phone-app recordings:**
  - the whole screen state read with on-device OCR;
  - a marking placed only where OCR proves its target is on that exact frame. Every unproven one is skipped and listed: the first full pass placed 157 markings and listed 101 skipped candidates for a human;
  - the recording composited into a phone mockup whose layout is copied from my hand-built project and calibrated against CapCut’s own render;
  - a fast-scroll detector that proposes a stepped scroll instead ([`sa_scrollscan.py`](../tools/sa_scrollscan.py)).
- **Voice-over over a provider’s official API** on its free model, with a loud warning before any paid fallback, a pronunciation-fixes file, and speed matched to approved audio ([`sa_fishvo.py`](../tools/sa_fishvo.py); a shareable version is the [Fish voice kit](../kits/fish-voice-kit/README.md)). The kit’s rule: clone only a voice you own, or one whose owner has given permission or a licence.
- **A pronunciation gate for product names.** A take is accepted only when two different speech-recognition models both hear the intended word. Among passing takes, the one closest to the approved reference wins. The gate is described in [the pronunciation gate for product names](training-video-production.md#the-pronunciation-gate-for-product-names).
- **A privacy sweep for screen recordings** ([privacy and independent checks on rendered recordings](training-video-production.md#13-privacy-and-independent-checks-on-rendered-recordings)):
  - OCR every played moment of the render, on-device;
  - fail on any e-mail address or harvested name token (names stored only as a hash);
  - check every blur against the markings visible at the same moment ([`sa_privacy_sweep.py`](../tools/sa_privacy_sweep.py), [`sa_privacy_plan_check.py`](../tools/sa_privacy_plan_check.py)).
- **Read-only observation of my live CapCut edits:** saved timeline changes and frames of the CapCut window only, kept as evidence for review rather than learned from automatically. The current control is a menu-bar indicator with a kill switch; an earlier floating control pad proved unreliable and is Experimental ([`sa_eyes.py`](../tools/sa_eyes.py), [`sa_watchbar.py`](../tools/sa_watchbar.py), [`sa_eyes_pad.py`](../tools/sa_eyes_pad.py); the method: [capcut-live-eyes.md](capcut-live-eyes.md); the launcher app: [apps/capcut-eyes](../apps/capcut-eyes/README.md)). *Pilot.* What it has seen so far: [editing-technique-observed.md](editing-technique-observed.md).
- **One evidence-first engineering method** shared by both agents ([ai-engineering-method.md](ai-engineering-method.md); the full text is in [engineering-method-full.md](engineering-method-full.md)).
- **A spec-driven pilot,** with written consistency gates for agent work ([spec-driven-ai-work.md](spec-driven-ai-work.md), [checklist](templates/consistency_gates_checklist.md)). *Pilot.*
- **Retrieval tuned by measurement.** Curated facts were weighted above project notes. On a 36-case evaluation set, Recall@1 went from 64% to 72%, Recall@3 from 83% to 97%, and mean reciprocal rank from 0.73 to 0.83. A query-expansion idea was built, measured worse (Recall@1 fell to 61%) and removed.
- **A reference-safe tidy-up of the Mac:** media that any editing project references is never moved, and every move is journalled and can be undone ([`sa_organize.py`](../tools/sa_organize.py), [`sa_refmap.py`](../tools/sa_refmap.py)). The broken references it found were repaired only where the file really existed. The rest were reported as missing, unverifiable or unmounted ([media-ops-field-notes.md](media-ops-field-notes.md)).
- **A photo pipeline for property shoots,** built so every job leaves a tool for the next one:
  - deterministic stills culling with contact sheets ([`sa_cull.py`](../tools/sa_cull.py));
  - a technical Camera Raw develop written as XMP sidecars ([`sa_rawdev.py`](../tools/sa_rawdev.py));
  - my real Lightroom edits read back out of the catalogue – safely, with the app open, by copying the catalogue and its write-ahead files first ([`sa_lrread.py`](../tools/sa_lrread.py));
  - those edits turned into scene presets ([`sa_presets.py`](../tools/sa_presets.py)).

  The recipe, with every preset value: [lightroom-recipe.md](lightroom-recipe.md). The preset files themselves are not published, because their shared base layer is a house base preset rather than my own look.
- **Imagery for a website:** a mixed photo set relit and graded to one look, and portrait backgrounds cleaned without generative fill ([photo-fidelity-retouching.md](photo-fidelity-retouching.md)).

**Problems found, and the fix**

| Problem class | What it looked like | Fix |
|---|---|---|
| “Done” read from the exit message | An install was reported finished while a consolidation step inside it had refused | Read the resulting state – the track list – not the exit text |
| A patch that silently didn’t apply | An edit matched nothing because of escaping, and the self-test still passed because its new asserts hadn’t landed either | Assert the change is present in the file after writing it |
| A build that “completed” on a broken script | An indentation error made the build script unparseable; stale results were read as fresh | Parse the script before trusting the next build |
| A box drawn round the words, not the control | Three independent checkers found 7 of 19 repaired boxes sized from where OCR put the text, cutting through cards and rows | Measure the container – the card, row or input – from the pixels, never infer it from the text inside |
| Fixed-size assumptions | Box modes with fixed widths sliced wide inputs in half or swallowed their neighbours | Seed inside the guess, then take the input’s real edges from the frame |
| An “empty space” test that wasn’t | A label placed where pixel ink was under 5% landed on top of a short value inside a field | Reject any position that overlaps text OCR can see |
| A minimum that overrode the evidence | A floor that stretched short markings pushed them past the screen change the check had just found | The screen check always wins; never extend a marking past it |
| A stale value after a move | A marking moved onto a later frozen frame kept its old end time, so it rendered for 0.68 s on a 2.90 s freeze | Recompute from the current values. After two wrong guesses, print the numbers side by side |
| A new checker that fails approved work | A new pacing check failed clips I had already approved | Run every new checker over known-good material first. Here the fault was its coarser measurement |
| A default that writes the wrong target | On a project with several timelines, a tool’s default resolved to the finished parent video | Name the timeline explicitly, and list the choices when the name doesn’t match |
| Paid jobs billed after a timeout | A generation call timed out; the job list showed nothing because it lists only completed jobs; the balance had already dropped | After any timeout, check the billing ledger, and never resubmit |
| Debating quality before reading the interface | Two exchanges about a service’s lip-sync quality when its connector had no way to accept an image | Read the tool’s parameters first |
| An automatic fix for a judgement call | An automatic white balance read beige walls as a colour cast and pushed about a quarter of a shoot cool, which lands green under warm LED light. The same day, another heuristic drove interiors to white | White balance removed from the tool entirely: camera white balance as shot, and the grade is mine. A tool may correct what it can measure unambiguously – clipped highlights, crushed shadows, noise. Colour is a look judgement |
| Generate first, search never | Twice, the right picture for a page was already in the library | Search the existing library against the copy before generating anything |
| A seek offset nobody asked for | A silent intermediate file’s stream start offset made every row play two frames late | Probe the start time and compensate |
| Flash frames at cuts | A row opened on four frames of the previous screen’s closing dialog | OCR the first frames of every row |
| Privacy beyond the held frame | Names showed in pickers, tooltips and lists that reappeared after a dialog closed | Sweep every played window, not just the frozen frame |
| Measuring the wrong thing | Whole-frame brightness on a cut-out against white hid a subject that had got darker; images judged “too small” by file size | Measure the subject, masked. Judge size against the rendered size at 2× |
| Scheduled jobs reporting false success | A backup task “succeeded” in seconds while writing nothing; an operating-system permission change silently broke three jobs; one overnight step ran ten hours and starved the rest | The health check demands a verified receipt; finished workloads are parked; permission changes are flagged for me to fix ([local-ai-on-a-mac.md](local-ai-on-a-mac.md)) |
| Unverifiable mistaken for missing | The agent couldn’t read files in a protected cloud folder | Report missing, unverifiable and unmounted separately. Never call unverifiable “gone” |
| A word the voice can’t say | A product name came out as a different word | Accept a take only when two different speech-recognition models both hear the intended word |

---

## October 2026 (to the 6th) – code-rendered motion graphics and an event-film pipeline

**Built**

- **Short motion-graphics explainer modules** (started in the last days of September). They are written as HTML and rendered headlessly, with every on-screen word cued to the voice-over’s word timestamps. Separate agents built three creative directions in parallel on identical timing. An editable CapCut review project was generated from each module’s edit plan and checked by a fixed set of 13 read-back checks, with the donor left untouched. *Built, awaiting review.* The method, including the font proofs and small-type rules: [code-rendered-motion-graphics.md](code-rendered-motion-graphics.md). The same method as a brand-agnostic kit – script, voice-over, word-timed captions, render, font proof, preview, quiz and certificate – is in [hyperframes-brand-tutorials.md](hyperframes-brand-tutorials.md), with the generator and a placeholder brand in [templates/hyperframes-brand-tutorial/](templates/hyperframes-brand-tutorial/README.md) (*Built, awaiting review*).
- **An event-film pipeline.** A timeline plan is rendered shot by shot, with speed-ramp pieces, push-ins and a beat-locked music edit, plus review sheets at each shot’s start, middle and end. The same plan is written out as an editable CapCut project with keyframes. **The first cut was rejected:** too slow, led by the venue rather than people, and the wrong story. The approved event edit I measured it against turned out to be:
  - people-led, with a median shot of about 1 s;
  - roughly ten shots every ten seconds;
  - built with transitions only at chapter changes;
  - cut on its own rhythm rather than to the beat – a random-placement test gave p ≈ 0.41.

  The rebuild was measured against that grammar, with a per-clip motion map rejecting lens zooms, shake and focus hunts, and a gate on the cut plan before anything renders. *Experimental* – the rebuild has not yet produced a cut I have reviewed. The grammar and the rules: [event films: measure the approved reference before cutting](learning-an-editors-style.md#10-event-films-measure-the-approved-reference-before-cutting); the motion gate: [culling hours of rushes with parallel AI agents](media-ops-field-notes.md#8-culling-hours-of-rushes-with-parallel-ai-agents).
- **Finishing an editor’s reel in place:** per-clip exposure fixes written as the editor’s own adjustment type, and a tilt correction measured from the vertical lines in the frame (a Hough transform).
- **Recovering another photographer’s grade** from the develop settings embedded in exported JPEGs.
- **Reference-checked storage clean-up:** an editor’s caches were cleared only after every project file had been searched for references to them ([media-ops-field-notes.md](media-ops-field-notes.md)).
- **This portfolio:** an allowlisted, sanitised and leak-scanned sync from the private workspace ([security-and-data-policy.md](security-and-data-policy.md)).

**Problems found, and the fix**

| Problem class | What it looked like | Fix |
|---|---|---|
| Cut first, measure the reference later | The first cut of an event film used about 2 s holds in its first half and leaned on venue and on-screen-text shots; it was rejected as slow and off-story | Measure the approved reference edit before cutting, and gate the plan before rendering |
| Long takes read from the start | A shot was taken from the first usable seconds of a long take, while the lens was still zooming | Read the whole of every long take and pick the right chunk. A machine motion map rejects zooms, shake, focus hunts and exposure jumps |
| Praising an accident | A large block of clips had jumped ahead of the editor’s own intro – probably while collapsing tracks – and the agent called it “a stronger hook” | An unexplained structural change in someone’s edit is a question, never a compliment. The editor’s intro and outro are structure |
| Copies that share an identity | Duplicated editing projects kept the original’s internal timeline ID, and the original then wouldn’t open (the likely cause) | Never copy a project folder wholesale. Generate new projects with new IDs ([media-ops-field-notes.md](media-ops-field-notes.md)) |
| A font that silently falls back | The risk: a mistyped font name falls back to a lookalike typeface, invisible by eye | Prove every face loads in the same headless browser, alongside a declared fake face that must fail. Use a deliberately serif fallback so a failure shows, and a strict mode that checks every text element’s computed font |
| “Is it really that font?” | Two grotesques that look identical by eye | Measure the width of the same sentence in each candidate font |
| Display type at small sizes | Words ran together at about 36 px and below | Per-size tracking and word-space tiers, set per rule. An inherited `em` value resolves once at the root and never scales |
| The animation said yes, the frame said no | A 3D-sorted element faded in behind its card while the animation library reported its opacity rising | Only rendered frames count as evidence |
| A render that needs disk the machine doesn’t have | Parallel frame capture needed several GB on an almost full disk | Stream frames straight into the encoder |
| Headless viewport smaller than the window | Page renders came out short | Render taller and crop from the top |
| An editor’s earlier version nearly lost | A first cut that existed only briefly during in-app trimming could be rebuilt only because an earlier read had been recorded | Snapshot the project file at every observed save, so any earlier state can be rebuilt |
| Cloud sync undoing deletions | With the cloud account full, local deletions and moves were restored from the server | Act on the server side, and check that the recycle bin fills before claiming space saved ([media-ops-field-notes.md](media-ops-field-notes.md)) |
| A leak scan that passed | Words hidden behind escape sequences, names hidden by literal translation, Unicode escapes, and leaks that are context rather than words | An escape-aware scanner, checks on decoded text, and an adversarial multi-agent reread of every page |

---

## Threads across the six months

- **Prose rules didn’t stop repeats; code did.** Every fix that held is something that runs and refuses ([learning-from-mistakes.md](learning-from-mistakes.md)).
- **The measurement usually fails before the work does.** When a check says everything is broken, check one case by hand – and run the checker over approved work – first.
- **Unknown is never a pass.** Every checker reports *ok*, *wrong* or *unknown*, and “done” needs evidence that matches the claim ([ai-engineering-method.md](ai-engineering-method.md)).
- **My finished edit is the specification.** Tools learn from what I changed, not from what I said. That includes measuring an approved reference *before* cutting, not after ([learning-an-editors-style.md](learning-an-editors-style.md), [my-creative-bar.md](my-creative-bar.md)).
- **Read the interface before debating the output.** A tool’s parameters, a billing ledger and a project file all answer questions faster than argument does.
- **Local first, with a clear exception.** Screen frames never go to generation services, and other company media goes to one only with approval for that project. Routine checks run locally and upload nothing. Large one-off verification passes used AI coding agents ([security-and-data-policy.md](security-and-data-policy.md)).
- **Check before building.** A generated tool catalogue ([`sa_toolindex.py`](../tools/sa_toolindex.py)) exists because tools were rebuilt that already existed – and the right picture was twice already in the library.

**Related:** [ai-engineering-method.md](ai-engineering-method.md) · [learning-from-mistakes.md](learning-from-mistakes.md) · [running-two-ai-agents.md](running-two-ai-agents.md) · [training-video-production.md](training-video-production.md) · [media-ops-field-notes.md](media-ops-field-notes.md) · [agent-organisation.md](agent-organisation.md) · [code-rendered-motion-graphics.md](code-rendered-motion-graphics.md) · [design-and-deck-craft.md](design-and-deck-craft.md) · [my-creative-bar.md](my-creative-bar.md)
