# Tools

Python, shell and Swift tools from my AI-assisted video and photo production workflow, mostly prefixed `sa_`. Each tool is a single file; most run with `python3 sa_<name>.py --help` and many have a `--test` self-check. External needs (ffmpeg, Whisper, OpenCV, CapCut, Ollama) are noted in each docstring. A few self-tests expect data from your own projects (for example a learned style file) and will say so when it is missing.

## CapCut automation

| Tool | What it does |
|---|---|
| [`sa_addsource.py`](sa_addsource.py) | Adds a hidden, muted, speed-fitted source-recording reference track to a CapCut timeline without changing the export length |
| [`sa_addvo.py`](sa_addvo.py) | Adds one voice-over track to a CapCut draft and mutes the original narration, refusing overlapping lines |
| [`sa_badge.py`](sa_badge.py) | Template-matching tracker that pins a logo badge to a moving subject in an AI-generated clip and writes smoothed position keyframes into CapCut |
| [`sa_capcut.py`](sa_capcut.py) | Reverse-engineers every local CapCut project into an edit-style report: cut pace, track mix, text, effects, transitions, music in-points and style clusters |
| [`sa_capcut_build_from_plan.py`](sa_capcut_build_from_plan.py) | Edit-plan JSON to a new CapCut review draft (picture, one voice clip per line, music with scene-boundary restart, captions) with 13 safety checks |
| [`sa_capcut_callouts.py`](sa_capcut_callouts.py) | Builds a new editable CapCut project where every call-out is its own layer, regenerating ids and verifying the draft by reading it back |
| [`sa_capcut_caption_style.py`](sa_capcut_caption_style.py) | Copies caption style and position from the editor's own finished caption to another CapCut project |
| [`sa_capcut_captions.py`](sa_capcut_captions.py) | Imports an SRT into CapCut as editable, consistently styled text layers (single style range, single shadow, exact placement) plus a two-line title |
| [`sa_capcut_colour_copy.py`](sa_capcut_colour_copy.py) | Safe CapCut copy with its own identity whose app picture is recoloured, leaving every other layer untouched |
| [`sa_capcut_corpus.py`](sa_capcut_corpus.py) | Read-only census of every CapCut project and timeline, with content-signature hashing to detect duplicate timelines |
| [`sa_capcut_flatten.py`](sa_capcut_flatten.py) | Collapses hundreds of per-call-out CapCut tracks into single 'Markings' and 'Marking names' tracks, refusing when segments overlap in time |
| [`sa_capcut_landscape_copy.py`](sa_capcut_landscape_copy.py) | Makes a 16:9 desktop copy of an approved 9:16 CapCut video: phone centred, captions right, step list left |
| [`sa_capcut_relink.py`](sa_capcut_relink.py) | Repairs 'media missing' in CapCut drafts after files move, using prefix rewrite or basename hunt with folder-tail matching and ambiguity refusal |
| [`sa_capcut_restyle.py`](sa_capcut_restyle.py) | Copies an editor's hand-made CapCut layer stack verbatim to other projects with fresh ids, re-pointed media and verify-then-restore |
| [`sa_capcut_signoff.py`](sa_capcut_signoff.py) | Idempotently appends a sign-off voice-over and caption to a CapCut timeline's tail, with a Whisper check of whether it is already spoken |
| [`sa_capcut_split_marks.py`](sa_capcut_split_marks.py) | Splits each CapCut marking into separate box and heading layers, keeping the editor's hand-nudged timing |
| [`sa_capcut_writer.py`](sa_capcut_writer.py) | Writes an editor-neutral JSON timeline plan into a new CapCut draft, including the Timelines/ read path, with rollback and a self-test |
| [`sa_delivery.py`](sa_delivery.py) | Delivery tracker that keeps disk evidence apart from exports the human has confirmed |
| [`sa_editwatch.py`](sa_editwatch.py) | Live CapCut edit watcher: diffs saved timeline JSON into plain-English edit events (moves, holds, trims, retypes, new call-outs) for style learning |
| [`sa_eyes.py`](sa_eyes.py) | Session supervisor for read-only CapCut observation: launches timeline and screen watchers with manifests, liveness checks and handoff |
| [`sa_eyes_pad.py`](sa_eyes_pad.py) | Always-on-top movable control pad for the read-only CapCut live watcher |
| [`sa_ffrender.py`](sa_ffrender.py) | Render a CapCut project file to MP4 with ffmpeg alone: exact transform geometry, styled captions with shadows, overlay call-outs, freeze-frame placeholders and a separate audio pass |
| [`sa_finaldiff.py`](sa_finaldiff.py) | Diff an editor's finished CapCut timeline against the machine-built baseline to turn every human correction into a recorded pipeline defect |
| [`sa_freezeinsert.py`](sa_freezeinsert.py) | Pure timeline transform that inserts a freeze-frame into a CapCut project: splits straddling clips, ripples later segments and stretches overlays instead of duplicating them |
| [`sa_import.py`](sa_import.py) | Register media in a CapCut project's media pool without touching the timeline, with a backup and a refusal while the app is open |
| [`sa_introfull.py`](sa_introfull.py) | Copy a finished intro, title and music recipe from a donor CapCut project to others: ripple shift, layered intro, two-weight title, lip-synced voice offset, looped music bed, and verify-or-rollback |
| [`sa_learn.py`](sa_learn.py) | Learn an editor's technique by pairing screen-capture frames (described by a local vision model) with exact timeline-save events, then purge screenshots only behind checksum gates and a receipt |
| [`sa_learncurve.py`](sa_learncurve.py) | Measure whether an automated edit pipeline is learning: the recurring corrections a human editor makes across finished videos (hold length, freezes, nudged boxes, typed labels) |
| [`sa_mobile_style.py`](sa_mobile_style.py) | Reproduces CapCut's transform, mask and smoothstep feather maths locally, matching CapCut renders to within half a pixel |
| [`sa_openline.py`](sa_openline.py) | Inserts a voiced opening line into a CapCut timeline: freeze-frame, ripple shift and cloned caption styling |
| [`sa_outro.py`](sa_outro.py) | Places a branded outro into CapCut drafts using values measured from the editor's own hand edit |
| [`sa_rolemark.py`](sa_rolemark.py) | Clones an editor's hand-typed CapCut text label so automated role-change labels match it exactly, on one idempotent track |
| [`sa_style_delta.py`](sa_style_delta.py) | Diffs a generated timeline plan against the editor's finished CapCut edit (removed, reordered, in-points, speed, reframes) as learning evidence |
| [`sa_stylebrain.py`](sa_stylebrain.py) | Mines an editor's CapCut project library into structured style fingerprints (pacing, in-points, speed, reframes, transitions) restricted to approved export ranges |
| [`sa_tailkit.py`](sa_tailkit.py) | Back-times a looping music bed so its real ending lands on the final frame and inserts a two-part voiced sign-off into a CapCut timeline |
| [`sa_timeline_slice.py`](sa_timeline_slice.py) | Slices a span out of a finished CapCut timeline into a new tab in the same project, keeping source in-points in step and registering it so CapCut shows it |
| [`sa_training_timeline_audit.py`](sa_training_timeline_audit.py) | Read-only CapCut timeline auditor that classifies captions, titles, role labels, call-outs, freezes, intros/outros, transitions and audio beds |
| [`sa_transcript.py`](sa_transcript.py) | Extract the delivered script from CapCut timelines (export-range aware, removes duplicate auto-caption layers) |
| [`sa_voiceswap.py`](sa_voiceswap.py) | Surgical CapCut voice edit: mute a stretch or drop a new voice file at an exact time without moving anything else (superseded) |

## Screen-recorded training videos

| Tool | What it does |
|---|---|
| [`sa_appbuild.py`](sa_appbuild.py) | Turns an action map and an app read into a CapCut review project, placing a call-out only where OCR proves the target is on screen |
| [`sa_applyboxes.py`](sa_applyboxes.py) | Applies verified call-out boxes: finds a pixel-stable time window, renders the overlay PNG, updates the manifest and rebuilds one CapCut track with verification |
| [`sa_applyfix.py`](sa_applyfix.py) | Safely applies measured call-out corrections: canvas validation, time/space collision detection, re-render and nearest-match CapCut retiming |
| [`sa_appread.py`](sa_appread.py) | Reads a phone-app screen recording as text: distinct screen states with OCR element boxes in source pixels, frames deleted as it goes |
| [`sa_boxfix.py`](sa_boxfix.py) | Moves a sidebar call-out onto the actually highlighted row, found by its colour band and row pitch |
| [`sa_boxkit.py`](sa_boxkit.py) | Library of sharp rounded call-out boxes as transparent PNGs in set sizes and colours |
| [`sa_clickdetect.py`](sa_clickdetect.py) | Detects click moments in a screen recording by tracking the cursor through frame differencing and catching screen changes, then flood-fills the clicked element's bounds |
| [`sa_coverage.py`](sa_coverage.py) | Finds training-video steps where the narration tells the viewer to act but no call-out is on screen |
| [`sa_cutlines.py`](sa_cutlines.py) | Collapses narration lines in a voiced training module and re-indexes text, voice clips, durations, rows and call-outs in one step |
| [`sa_dubcut.py`](sa_dubcut.py) | Paces a screen recording to a replacement voice-over with voice-anchored freeze holds, speed clamps and call-outs retimed through source time |
| [`sa_gapfill.py`](sa_gapfill.py) | Propose call-out boxes for unmarked tutorial steps: click detection finds where, a local vision model rejects boxes on empty space, and the script line yields a short imperative label |
| [`sa_gridsheet.py`](sa_gridsheet.py) | Contact sheets with a pixel-ruler grid labelled in source pixels, for measuring on-screen call-out coordinates on the exact frame |
| [`sa_markrules.py`](sa_markrules.py) | An editor's measured pacing, caption and call-out placement rules as a tested Python library, with pixel-level UI container detection |
| [`sa_panel_locate.py`](sa_panel_locate.py) | OCR-indexes a screen recording to find the moment each on-screen panel is brought into view |
| [`sa_phoneframe.py`](sa_phoneframe.py) | Puts a phone screen recording inside a device mockup on a backdrop for 9:16, printing the screen rectangle for markings |
| [`sa_plan_pacing.py`](sa_plan_pacing.py) | Screen-anchored pacing plan: drops only motionless frames inside each line's zone so nothing on screen is lost |
| [`sa_relabel.py`](sa_relabel.py) | Redraws call-out label images in place so CapCut keeps its links and the editor's adjustments |
| [`sa_script_to_lines.py`](sa_script_to_lines.py) | Splits an approved prose script into one narration beat per line, guarding decimals, codes and abbreviations |
| [`sa_scrollscan.py`](sa_scrollscan.py) | Detects too-fast scrolls in screen recordings in px/s and screen-heights/s and proposes stepped-scroll holds, on-device and report-only |
| [`sa_stepmark.py`](sa_stepmark.py) | House-style click call-outs for desktop and phone-app training videos as alpha overlays or CapCut layers, with label placement and frame-diff QA |
| [`sa_training_revision.py`](sa_training_revision.py) | Change-request planner for software-training videos: anchor-based, SHA-fingerprinted, duplicate-only revision plans with QA checklist |
| [`sa_voice_anchors.py`](sa_voice_anchors.py) | Voice anchors: pins each marking's screen to the moment its words are spoken by freezing before the transition |

## Video QA and verification

| Tool | What it does |
|---|---|
| [`sa_actioncheck.py`](sa_actioncheck.py) | Narration action auditor: splits voice-over captions into individual imperative actions and flags any instructed step with no on-screen marking nearby |
| [`sa_boxcheck.py`](sa_boxcheck.py) | Local vision-model QA: checks each call-out box sits on the element its label names, and samples uncovered stretches for missed steps |
| [`sa_boxcheck_all.sh`](sa_boxcheck_all.sh) | Overnight batch runner for the vision QA check across a whole series, with honest UNKNOWN accounting and a non-zero exit when nothing was checked |
| [`sa_check_sync.py`](sa_check_sync.py) | Three sync checks on a finished module: box versus word, box held at start/middle/end, caption versus speech onset on the waveform |
| [`sa_event_cutcheck.py`](sa_event_cutcheck.py) | Gate for an event-film cut plan before rendering: shot-length percentiles, opening density, slow motion only on high-frame-rate clips, verified source windows, duplicates, transitions, and the final shot landing on the music hit |
| [`sa_exportcheck.py`](sa_exportcheck.py) | Pre-export QA for CapCut projects: captions, title card, one-line rule, duplicate sign-off, trailing black, missing media, audio over black |
| [`sa_ffbatch.py`](sa_ffbatch.py) | Batch-render every editor timeline headlessly with ffmpeg and verify each render against its timeline (duration, caption ink, outro, voice level) |
| [`sa_ffboard.py`](sa_ffboard.py) | Self-contained HTML board pairing a render-match report with real frames, embedded so it opens offline; it runs locally and uploads nothing |
| [`sa_final_video_audit.py`](sa_final_video_audit.py) | Measures real shot lengths on finished MP4s with PySceneDetect instead of trusting timeline metadata |
| [`sa_finalboard.py`](sa_finalboard.py) | Pre-export HTML dashboard per video with a plain-language, timestamped fix list |
| [`sa_finalcheck.py`](sa_finalcheck.py) | Send/Check/Stop gate for exported videos: loudness (EBU R128), silences, black frames, plus a local Whisper transcript fuzzy-matched sentence by sentence against the approved script |
| [`sa_independent_asr.py`](sa_independent_asr.py) | Independent verify: re-transcribes the review render with a different, larger local ASR model than the build used |
| [`sa_introcheck.py`](sa_introcheck.py) | Automated QC for AI-generated presenter clips: resolution, burnt-in text (edge energy in the empty third) and subject framing side |
| [`sa_markcheck.py`](sa_markcheck.py) | Zero-model pre-flight that checks screen-training call-out specs with OCR and geometry, shortlisting only what needs AI review |
| [`sa_occlude.py`](sa_occlude.py) | Detects call-out boxes and labels covering on-screen text in rendered training videos |
| [`sa_privacy_plan_check.py`](sa_privacy_plan_check.py) | Checks before rendering that every e-mail and name on every played frame sits inside an active privacy rectangle, printing tokens masked |
| [`sa_privacy_sweep.py`](sa_privacy_sweep.py) | Privacy sweep of a rendered screen recording: local OCR every 0.25 s fails any e-mail, hashed name token or legible text inside an active blur |
| [`sa_qa.py`](sa_qa.py) | Pre-publish brand QA gate: British spelling, hashtag casing, subtitle set and local vision checks |
| [`sa_qasheet.py`](sa_qasheet.py) | Renders one review still per call-out with its box drawn on the actual playing frame |
| [`sa_residue.py`](sa_residue.py) | Measures which auto-placed call-outs a human editor still moved, to judge whether automation can be trusted |
| [`sa_screenmap.py`](sa_screenmap.py) | OCRs every on-screen UI label from delivered training videos and diffs them against the live software to flag outdated screens |
| [`sa_see.py`](sa_see.py) | Streams any video through a local vision-language model frame by frame with bounded disk use, writing timestamped JSON/Markdown descriptions |
| [`sa_tailcheck.py`](sa_tailcheck.py) | Detects silent tails, where picture outlives narration, in CapCut timelines and rendered builds, using caption end times plus ffmpeg scene-change sampling |
| [`sa_training_mastery.py`](sa_training_mastery.py) | Evidence manifest for a delivered training-video series: ffprobe specs plus local Whisper transcript vs caption similarity |
| [`sa_verify_fonts.py`](sa_verify_fonts.py) | Proves in headless Chrome that every @font-face really loads, catching silent fallback, with a strict per-element mode |
| [`sa_videocheck.py`](sa_videocheck.py) | Measure every video in a CapCut training series against a reference edit's house style |
| [`sa_vo_quality_audit.py`](sa_vo_quality_audit.py) | Read-only voice-over QA for CapCut drafts: per-line clips, WER, loudness, clipping, dropouts and an HTML report |
| [`sa_voicecheck.py`](sa_voicecheck.py) | AI voice-drift shortlist via transcription WER, with failed acoustic tests documented |
| [`sa_voiceclips.py`](sa_voiceclips.py) | One-click listening sheet: every spoken line cut to a clip beside its script, weakest first |

## Captions, transcripts and voice

| Tool | What it does |
|---|---|
| [`sa_align_beats.py`](sa_align_beats.py) | Monotonic dynamic-programming aligner that maps an approved script, beat by beat, onto a Whisper transcript's timestamps |
| [`sa_captions.py`](sa_captions.py) | Script-locked captions: text from the approved script, timing from Whisper word timestamps, with abbreviation-safe cue breaks |
| [`sa_clonevo.py`](sa_clonevo.py) | Local zero-shot voice cloning (Chatterbox) with best-of-N takes, Whisper wording check, a spectral-flux choppiness metric, tail trimming and loudness matching to a reference |
| [`sa_fishvo.py`](sa_fishvo.py) | Cloned-voice TTS through the Fish Audio API: best-of-N takes, local Whisper word check, choppiness ranking and loudness match |
| [`sa_hfcheck.py`](sa_hfcheck.py) | Detect dull or 'old radio' drift in TTS takes by measuring high-frequency (>5 kHz) energy on voiced frames, compared only between takes of the same sentence |
| [`sa_introline.py`](sa_introline.py) | Prepare a voice line for lip-synced AI video: pace to a target words-per-second without pitch change, then pad head and tail silence so the model never invents mouth movement |
| [`sa_kokoro_say.py`](sa_kokoro_say.py) | Kokoro ONNX TTS with real punctuation pauses by synthesising per phrase (engine later rejected for flat prosody) |
| [`sa_livecaption.py`](sa_livecaption.py) | Fully local live Arabic-to-English captioning: a two-tier draft/commit Whisper stream on the Apple GPU (MLX) with a CPU fallback, a glossary bias, and a browser control page plus a guest display over SSE |
| [`sa_scriptbook.py`](sa_scriptbook.py) | Extracts course-ready narration scripts from CapCut projects, separating spoken captions from on-screen labels and honouring the exported range |
| [`sa_scriptsync.py`](sa_scriptsync.py) | Rebuilds the readable voice-over script from locked plans and measured clip lengths, with a drift check for nightly runs |
| [`sa_srt.py`](sa_srt.py) | Offline faster-whisper SRT generator with British respelling and optional burn-in (superseded by sa_captions) |
| [`sa_srtexport.py`](sa_srtexport.py) | Exports SRT subtitles and a clean transcript directly from CapCut project files (CapCut cannot export SRT itself) |
| [`sa_terms.py`](sa_terms.py) | Enforces consistent product terminology across captions and call-outs, refusing any caption edit that would change the spoken words |
| [`sa_translate.py`](sa_translate.py) | Local English-to-Arabic SRT translation through Ollama that keeps every timing, as a draft for review |
| [`sa_video_corpus_read.py`](sa_video_corpus_read.py) | Idempotent batch transcriber for a registry of finished videos, writing JSON, TXT and SRT without touching originals |
| [`sa_vo.py`](sa_vo.py) | SRT script to per-line TTS clips plus an SRT re-timed to the real audio lengths |
| [`sa_vo_words.py`](sa_vo_words.py) | Word timestamps and durations for a module's voice-over clips so on-screen words land on their spoken beat |
| [`sa_voiceplan.py`](sa_voiceplan.py) | Cuts and measures each line's original audio for an original-versus-new-take voice comparison |
| [`sa_voiceref.py`](sa_voiceref.py) | Picks the best takes from recordings you own or are licensed to clone, by measurement, to build a voice-cloning reference sample |
| [`sa_voicerefresh.py`](sa_voicerefresh.py) | Detect dull AI voice takes by comparing them with fresh takes of the same words |
| [`sa_whisper.py`](sa_whisper.py) | Local faster-whisper narration transcript for aligning screen-recording beats |
| [`vo_studio.py`](vo_studio.py) | Browser voice-over studio using Microsoft's online Edge voices: type, pick a voice, adjust speed, listen and download |

## Editing and assembly

| Tool | What it does |
|---|---|
| [`sa_assemble.py`](sa_assemble.py) | First-pass CapCut assembler: turns a footage folder into a paced timeline by cloning a donor project's transitions, music bed and outro |
| [`sa_beats.py`](sa_beats.py) | Beat grid, downbeat estimates and energy-peak cut points for a music track, with a synthetic self-test |
| [`sa_console.py`](sa_console.py) | Browser approval console: plain-English edit brief to reviewed rough-cut plan, then builds a new CapCut project |
| [`sa_cut_render.py`](sa_cut_render.py) | Renders a timeline-plan JSON straight to MP4 through an ffmpeg trim/concat graph, no editor needed |
| [`sa_cutsheet.py`](sa_cutsheet.py) | Vision-model cut sheet: samples candidate moments per clip, scores usability and shake, and suggests in/out points and speed for review |
| [`sa_edit_skeleton.py`](sa_edit_skeleton.py) | Story-first edit skeleton generator: chapter map, semantic shot slots and a validated, human-approved compile to a timeline plan |
| [`sa_editdna.py`](sa_editdna.py) | Mines an editor's cut-length percentiles, rhythm spread and speed-ramp share per style from encoded CapCut projects |
| [`sa_event_fit.py`](sa_event_fit.py) | Fits an ordered shot list into measured music phrases, stretching or shrinking each shot within speed limits so every phrase lands exactly on its boundary |
| [`sa_event_motionmap.py`](sa_event_motionmap.py) | Frame-level camera-motion map for event footage: separates optical zoom from walking push-ins, flags whip pans, shake, focus hunting and exposure jumps, and returns each clip's clean usable windows |
| [`sa_event_render.py`](sa_event_render.py) | Plan-driven event-film renderer: per-shot ffmpeg render with speed-ramp curves, push-ins, grade, a per-shot fix for faces lit by LED walls, cut/fade/flash/dip transitions, a loudness-normalised music edit, and start/middle/end QA sheets |
| [`sa_explainer_build.py`](sa_explainer_build.py) | Re-runnable explainer video from a SCENES list: script to SRT to local TTS to Pillow slides to ffmpeg concat |
| [`sa_extract.py`](sa_extract.py) | Local multi-frame shot-quality scorer (sharpness, exposure clipping, optical-flow jitter, diversity de-dup) proposing source windows and speeds |
| [`sa_hold.py`](sa_hold.py) | Replace motion under on-screen call-outs with held stills while keeping total duration fixed, so voice-over stays in sync |
| [`sa_kenburns.py`](sa_kenburns.py) | Real-pixels-only 9:16 Ken Burns clips from stills with a float affine window, no generation or interpolation |
| [`sa_plan_preview.py`](sa_plan_preview.py) | Renders a quick silent review MP4 from a JSON timeline plan with ffmpeg |
| [`sa_revealreel.py`](sa_revealreel.py) | Builds a 9:16 vehicle reveal reel from stills: Ken Burns motion, procedural cloth pull and studio relight |
| [`sa_tighten.py`](sa_tighten.py) | Rough-cuts talking-head footage from Whisper word timestamps (tightens silences, drops fillers, keeps the last of repeated takes) with an HTML edit-decision review page |
| [`sa_timeline.py`](sa_timeline.py) | Plans editor-neutral timelines from a learned style corpus (master selection, in-points, speed, transforms) with per-clip evidence and review flags, plus a schema validator |
| [`sa_titlecard.py`](sa_titlecard.py) | Transparent 1920x1080 title-card PNGs: centred title and subtitle, plus step and benefits modes |
| [`sa_video_style_read.py`](sa_video_style_read.py) | Local vision-model study of editing grammar from video contact strips, as schema-validated JSON |

## Colour and photo

| Tool | What it does |
|---|---|
| [`jewellery_edit.py`](jewellery_edit.py) | True-colour RAW batch edit for product photography, with sharpness-based culling |
| [`sa_archive_clean.py`](sa_archive_clean.py) | Non-generative cleanup of scanned archival photos: non-local-means denoise plus a light unsharp |
| [`sa_brand_stamp.py`](sa_brand_stamp.py) | Stamps or engraves real logo artwork onto a generated plate at pixel level so no model ever redraws lettering |
| [`sa_card_preview.py`](sa_card_preview.py) | Renders image cards exactly as the page crops them, including the label gradient read from the stylesheet |
| [`sa_cull.py`](sa_cull.py) | Deterministic photo-shoot culler: sharpness/exposure/clipping scoring, near-duplicate grouping, best-pick and contact sheets |
| [`sa_cutout.py`](sa_cutout.py) | Local background removal with rembg for a single file or a folder |
| [`sa_decaption.py`](sa_decaption.py) | Removes burned-in captions from video stills by masked inpainting with a face-safe guard band, then a non-generative restore for thumbnails |
| [`sa_grade.py`](sa_grade.py) | Applies a .cube LUT to an image or video through ffmpeg lut3d with a strength blend |
| [`sa_hero_scrim.py`](sa_hero_scrim.py) | Bakes a smoothstep scrim into a hero image so a headline laid straight on the photo stays readable |
| [`sa_honest_2x.py`](sa_honest_2x.py) | Deterministic honest 2x listing pipeline: EXIF transpose, conservative tone, flat-area denoise, Lanczos 2x, mild sharpen, QC and hashes |
| [`sa_house_grade.py`](sa_house_grade.py) | One non-generative house treatment so photos from different days sit together: haze floor, self-levelling sky lift, capped moves |
| [`sa_hue_remap_lut.py`](sa_hue_remap_lut.py) | Hue-selective recolour that moves one hue band to a target hue, keeping whites, greys and status colours, as a 3D LUT, still or video |
| [`sa_lrread.py`](sa_lrread.py) | Reads Lightroom CC develop settings and masks straight from its private SQLite catalogue |
| [`sa_lut.py`](sa_lut.py) | Builds an exact 3D .cube LUT from any Lightroom look using an identity image |
| [`sa_match_set.py`](sa_match_set.py) | Nudges every card in a set toward two approved references on brightness and saturation, with capped corrections |
| [`sa_photo.py`](sa_photo.py) | Adaptive outdoor photo grade: white-patch balance, auto-levels, vibrance and chroma denoise |
| [`sa_photolib.py`](sa_photolib.py) | Photo library pipeline: perceptual-hash de-duplication, quality flags, local AI upscaling and Lightroom sidecars |
| [`sa_presets.py`](sa_presets.py) | Learns scene-specific Lightroom presets from a photographer's own edits |
| [`sa_rawdev.py`](sa_rawdev.py) | Measures RAW files and writes technical Camera Raw XMP sidecars (exposure, recovery, noise) |
| [`sa_review_page.py`](sa_review_page.py) | Self-contained base64 review page: before, after, as-cropped and true-size views of each card |
| [`sa_upscale.py`](sa_upscale.py) | On-device Real-ESRGAN upscaler with a filename guard that refuses protected products |
| [`sa_web_safe_zone.py`](sa_web_safe_zone.py) | Translates a picture so content that overran a site's object-fit crop lands back inside it, mirror-filling the hidden strip |
| [`sa_webcrops.py`](sa_webcrops.py) | Cuts six web delivery crops from the native still by geometry only, never touching colour |
| [`sa_xmp2cube.py`](sa_xmp2cube.py) | Approximate a Lightroom/ACR XMP preset as a 3D .cube LUT |
| [`sa_xmp_detail_apply.py`](sa_xmp_detail_apply.py) | Applies only an XMP's detail fields (noise reduction, sharpening) at native resolution, byte-copying zero-setting files |

## AI workspace operations

| Tool | What it does |
|---|---|
| [`sa_checkpoint.py`](sa_checkpoint.py) | Claude Code hook that watches transcript growth and requests a decision checkpoint every ~8 MB, before context compaction loses detail |
| [`sa_compact_brief.sh`](sa_compact_brief.sh) | Post-compaction hook that re-injects ground truth from disk (session state, open threads, checkpoints, health red lights) into a fresh Claude Code context |
| [`sa_consistency_gate.py`](sa_consistency_gate.py) | Read-only preflight validator for unresolved spec placeholders, required documents and timing consistency, with self-tests |
| [`sa_desk.py`](sa_desk.py) | Always-on-top, voice-enabled assistant window that sends requests to Claude Code with the current CapCut project as context |
| [`sa_doctor.py`](sa_doctor.py) | One-command health check for an AI workspace: compile check, verified backups, heartbeat pairing, git state, scheduled-job traces |
| [`sa_guard.py`](sa_guard.py) | Pre-flight guard for AI agents: refuses writes to work the editor has signed off, refuses while the editor app is open, makes vision batches mutually exclusive, and checks the tool catalogue before anyone builds a duplicate |
| [`sa_hub.py`](sa_hub.py) | Local-only web hub (127.0.0.1) for an AI workspace: keyword retrieval plus a local Ollama Q&A over notes, a live 'agentic OS' brain-map SVG, a health check and a tool browser |
| [`sa_inspect.py`](sa_inspect.py) | Runtime inspector for a multi-agent workspace: instruction-file hashes and drift, session-state freshness, plugin registry audit, data policy, local services and model routing |
| [`sa_loop.py`](sa_loop.py) | Agent-loop governance: readiness audit, attempt ledger, error-signature circuit breaker, kill switch and evidence-required completion, using atomic JSON writes |
| [`sa_nightcheck.sh`](sa_nightcheck.sh) | Morning dead-man switch: notifies and logs when the overnight runner left no clean-exit marker |
| [`sa_nightly.sh`](sa_nightly.sh) | Resumable overnight automation runner with a step ledger, app-open guard and AI-written morning summary |
| [`sa_peek.py`](sa_peek.py) | Describes an image with a local vision model so an AI agent reads text instead of pixels |
| [`sa_provenance.py`](sa_provenance.py) | Writes an auditable provenance manifest (hashes, tools, models, data class) for creative outputs |
| [`sa_reel.py`](sa_reel.py) | Reference-video analyser: download, transcribe, detect shots, describe each with a local vision model |
| [`sa_screenwatch.py`](sa_screenwatch.py) | Privacy-scoped capture of only the video editor's windows, with perceptual-hash dedupe and a local VLM pass, to learn how an editor works |
| [`sa_security.py`](sa_security.py) | Pins third-party agent plugins/hooks by version and hash, and gates media uploads to external AI services by data class |
| [`sa_session.py`](sa_session.py) | Canonical session-handoff contract for multiple coding agents: atomic state.json, typed event log, resume validator and legacy migration |
| [`sa_threads.py`](sa_threads.py) | Rebuilds an 'open threads' digest from disk (unfinished sessions, owed actions, recently touched git repos) so agent context compaction never loses work |
| [`sa_toolindex.py`](sa_toolindex.py) | Auto-generates a tool catalogue from each script's docstring via AST (no imports) and flags tools missing docs or self-tests |
| [`sa_vaultmap.py`](sa_vaultmap.py) | Knowledge-vault health map: most-linked notes, orphans and broken wikilinks |
| [`sa_visualmem.py`](sa_visualmem.py) | Resource-aware local visual memory: VLM image tagging that pauses when editing apps are open |
| [`sa_watch.py`](sa_watch.py) | Security-gated launcher for a pinned video-watch plugin that forces local-only transcription |
| [`sa_watchbar.py`](sa_watchbar.py) | macOS menu-bar indicator and kill switch for background screen and edit watchers |
| [`squeeze.py`](squeeze.py) | Compress large tool outputs before they reach an LLM, never returning unreadable pointers |

## Utilities

| Tool | What it does |
|---|---|
| [`media_kit.py`](media_kit.py) | Reusable media glue: parallel presigned upload/download, contact sheets, fractional crops, video probe |
| [`sa_assets.py`](sa_assets.py) | Local SQLite catalogue of video, image and audio files with scan, find and stats commands |
| [`sa_compress.py`](sa_compress.py) | Lossless APFS transparent compression that skips open, recently changed and poorly compressing files, with manifest, undo and self-test |
| [`sa_dedupe.py`](sa_dedupe.py) | Safe duplicate finder that quarantines (never deletes) by name+size or content hash, with a cross-folder mode against cloud storage |
| [`sa_font.py`](sa_font.py) | Installs Google Fonts families from the official GitHub mirror with a load test |
| [`sa_frames.py`](sa_frames.py) | Explode a video into timecode-burned frames, contact strips and an index so an AI agent can read motion frame by frame |
| [`sa_html_card_render.mjs`](sa_html_card_render.mjs) | Playwright HTML-to-PNG card renderer that throws if text overflows its box |
| [`sa_mirror_site.py`](sa_mirror_site.py) | Offline copy of a static or Next.js export that works from disk: root-absolute paths rewritten per page depth |
| [`sa_ocr.swift`](sa_ocr.swift) | On-device OCR with Apple's Vision framework (English and Arabic), with an optional --boxes mode giving pixel rectangles |
| [`sa_ocr_bounds.swift`](sa_ocr_bounds.swift) | On-device Vision OCR that prints JSON rows with text, confidence and pixel boxes |
| [`sa_organize.py`](sa_organize.py) | Safe folder tidy-up that never breaks editing projects: reference-locked, journalled and fully undoable |
| [`sa_refmap.py`](sa_refmap.py) | Which editing projects use this media file? Scans project files read-only and maps media to the projects that reference it |
| [`sa_serve_offline_site.command`](sa_serve_offline_site.command) | Double-click launcher that serves an offline site copy on a free port and stops the server on exit |
| [`sa_sort.py`](sa_sort.py) | Sorts media into camera/date folders from embedded metadata, telling identical bodies apart by serial; dry run by default |
