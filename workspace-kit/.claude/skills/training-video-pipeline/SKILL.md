---
name: training-video-pipeline
description: "Screen-recorded training-video pipeline – call-out boxes, captions and CapCut projects. Use for ANY task involving: software training videos or screen recordings, call-outs or highlight boxes on a screen recording, a box that looks wrong or badly placed, burning or importing captions, building or repairing CapCut projects, pacing a video to a replacement voice-over, CapCut saying media is missing, checking captions for accuracy or consistent terminology, or watching and learning from the owner's own edits."
---

<!-- An example of packaging a method as a Claude Code skill: the description line is the
     trigger (written in the words people actually use), the body is the method, and the
     tools do the work. Tools live in the workspace's Tools/ folder; the published versions
     are in this repository's tools/ folder (links below). A skill grants no authority to
     branch, install, publish or upload. -->

# Training-video pipeline

## Read this before any edit

1. Read the editing grammar (`Reference/SAAD_EDITING_GRAMMAR.json`, template [here](../../../../Reference/SAAD_EDITING_GRAMMAR.json)) and the editing-style note. They are the spec, not a suggestion.
2. **Story map first.** [`sa_edit_skeleton.py`](../../../../tools/sa_edit_skeleton.py) builds the chapter map. Never cut clip by clip in raw-footage order.
3. **Review timeline only.** Never the owner’s original project, never the source footage.
4. **Authority order:** the owner’s approved final export and corrections → the named approved timeline → a reviewed cutsheet → the grammar → automatic analysis. Draft duration, unused clips and automatic decisions rank last, always.
5. **Review first.** Build the first assembly, then stop. It is never “final” until the owner approves vibe, music, timing and story flow.

Everything below is already built and tested. **Call the tool; do not rewrite the logic.** Every tool has `--test` – run it if you change anything. Before writing ANY CapCut draft JSON, read the draft-schema note ([the CapCut draft format](../../../../playbooks/capcut-draft-format.md)).

**Replacement voice-over? The order is fixed** (relearned the hard way – voice pinned onto raw footage gave two audio tracks, dead air and drift):
[`sa_dubcut`](../../../../tools/sa_dubcut.py) (pace the picture to the voice; the original audio does not survive the mux) → [`sa_stepmark`](../../../../tools/sa_stepmark.py) on the **paced** timeline → [`sa_captions`](../../../../tools/sa_captions.py) (script text, speech timing, one-line cues of at most 46 characters) → the CapCut build. Never anchor a voice-over onto raw footage.

**Deliver the voice detached.** Picture silent; every line its own audio clip at its own timestamp on a separate track; captions synced to that same timing. The owner can then cut or swap a single line without touching the picture.

**Anchor lines to the screen, not to the old narration** – that was the cause of every “sync issue”. A local voice clone ([`sa_clonevo`](../../../../tools/sa_clonevo.py)) is for new series only; never mix engines inside a delivered series.

## The INSERT pipeline (placing a new section into the owner’s project)

When the owner says “put this new section into my project at TIME”:

1. **Park on new named tracks** at the stated time – `INSERT <name>`, `INSERT call-outs`, `INSERT VO`, `INSERT Captions`. The owner’s tracks stay byte-identical (compare every original track, serialised, against the pre-insert backup). They slide the insert into place themselves. The header duration grows only if the insert runs past the old end.
2. **Revisions are strip-and-swap.** Remove the tracks whose name starts with `INSERT` plus their materials, then add the new build. Never patch segments in place.
3. **Browser footage:** crop the tab strip (about 44 px) rather than demanding a re-record; keep the address bar; pad to the canvas with the page’s own background colour; halve 60 fps to 30. Check the sign-in seconds frame by frame for anything that should not be on screen before using them.
4. **Insert voice at speed 1.0.** A slightly slower take read as slow beside the existing lines. Judge tempo against the neighbouring audio, in context.
5. **Narration speaks the screen.** Use the button’s exact visible words; the owner’s wording wins over the interface’s. A role change is a bare “Now sign in as the …” – no scene-setting preamble.
6. **Measure boxes only on frames extracted from the exact video they overlay.** Mapping coordinates through crop-and-scale arithmetic from another frame once put two boxes 40 px low. Composite and look before writing, every time, and **re-prove every box after any re-pace.**
7. **If the line says “click X”, the pacing holds X’s screen through that line.** A box once fired over an empty page because a dialog closed 0.1 s into the line – extend the pre-click freeze so the click lands inside the line.
8. **Chips never cover row content.** Place the label right or left of the box when below would sit on data.
9. **Editing one line later:** overwrite the audio file at the same path and update that material’s and segment’s durations; delete and rebuild that line’s captions from the new speech timing – and **bound the deletion window by the line’s own end**, never end-plus-slack (slack once swallowed the next line’s first cue; caught by counting cues).
10. **Verify every count in the draft after writing:** boxes, captions and voice clips; no overlaps; both draft copies byte-equal; originals intact; media paths exist.
11. **Voice pace is not visual pace.** Busy screens play at about 1.0×, never compressed past about 1.2×. When the voice is longer, freeze at a stable moment; add 1–2 s of breathing room after actions; hold sign-in screens about 2 s past the line.
12. **A marking dies before its screen does.** End every box at least 0.3 s before its click or transition, and after any re-pace check each box at its **end** time, not just its middle. **A box that cannot fit inside its screen’s lifetime is a pacing fault** – slow the segment or add a freeze; don’t just shorten the box.
13. **Measure on the live system** when position or persistence is in doubt, rather than doing frame archaeology.
14. **From the owner’s own re-cut:** mark the account’s row in the sign-in list, not the search field; show the raw sign-in, then a short still. **Split a compound line at the action** (“…select the location, / then click Issue…”) into two audio files so each half lands on its own screen. Explain workflow chips at first sight over a freeze. Hold a call-out about 1.5 s on a moving screen; the full line only on a frozen one. Freezes are layered stills, not baked into the paced picture. Every navigation click and text entry gets a marking. A marking style is never invented – copy the series’ approved style exactly. After two rejected rounds on one deliverable, stop and ask for one concrete example.

## The rule that has cost the most when broken

**A tool printing “done” proves a file was written, not that it is correct.** Three times a build reported total success and was wrong – 193 layers pointing at nothing, 15 projects opening on the wrong timeline, 3.7 minutes of video silently dropped. Verify by re-reading the artefact the way the consumer will. Every check has three outcomes – **ok, wrong, unknown** – and unknown is never a pass.

## Confidentiality – stated honestly

- Screen frames never go to generation services.
- Routine checks on frames (box placement, gap finding) run on a **local vision model only**.
- Narration **text** may go to an approved voice service.
- Large one-off verification passes used hosted AI coding agents – and a hosted sub-agent processes whatever it reads, so use one only on material cleared for that, or point it at a local model.
- A generation connector often sits next to an approved text-to-speech tool with an upload function of its own; never point that upload at confidential material.

## Which tool for what

| Job | Tool |
|---|---|
| Story-first chapter map before any clip is placed | [`sa_edit_skeleton.py`](../../../../tools/sa_edit_skeleton.py) |
| Pace a screen recording to a replacement voice-over | [`sa_dubcut.py`](../../../../tools/sa_dubcut.py) |
| Draw call-out boxes and freeze the frame under each | [`sa_stepmark.py`](../../../../tools/sa_stepmark.py) |
| Check a box sits on the right control (local vision) | [`sa_boxcheck.py --verify`](../../../../tools/sa_boxcheck.py) |
| Find important steps with no call-out | [`sa_boxcheck.py --gaps`](../../../../tools/sa_boxcheck.py) |
| Captions from the locked script, timed by the audio | [`sa_captions.py`](../../../../tools/sa_captions.py) |
| A CapCut project with one track per call-out | [`sa_capcut_callouts.py`](../../../../tools/sa_capcut_callouts.py) |
| A full new review draft from a plan (picture, voice per line, music, captions) | [`sa_capcut_build_from_plan.py`](../../../../tools/sa_capcut_build_from_plan.py) |
| Put captions and title screens into a CapCut project | [`sa_capcut_captions.py`](../../../../tools/sa_capcut_captions.py) |
| Add or remove the series sign-off, idempotently | [`sa_capcut_signoff.py`](../../../../tools/sa_capcut_signoff.py) |
| **CapCut says media is missing** | [`sa_capcut_relink.py --fix ROOT`](../../../../tools/sa_capcut_relink.py) |
| Make role and product names consistent | [`sa_terms.py --fix`](../../../../tools/sa_terms.py) |
| Correct a call-out’s words without breaking CapCut | [`sa_relabel.py --fix`](../../../../tools/sa_relabel.py) |
| Pre-export checks on a project | [`sa_exportcheck.py`](../../../../tools/sa_exportcheck.py) |
| Refuse writes while CapCut is open or to signed-off work | [`sa_guard.py`](../../../../tools/sa_guard.py) |
| Watch the owner edit, live (project file) | [`sa_editwatch.py`](../../../../tools/sa_editwatch.py) |
| Capture the editor window while they edit | [`sa_screenwatch.py`](../../../../tools/sa_screenwatch.py) |
| Menu-bar light so the owner can see watching is on | [`sa_watchbar.py`](../../../../tools/sa_watchbar.py) |
| Learn from a finished session, then delete the frames | [`sa_learn.py`](../../../../tools/sa_learn.py) |
| Dull or “old radio” drift between voice takes | [`sa_hfcheck.py`](../../../../tools/sa_hfcheck.py) |
| Local voice clone, best of N takes | [`sa_clonevo.py`](../../../../tools/sa_clonevo.py) |

## Things that will bite you

- **CapCut must be closed before writing any project** (`pgrep -x CapCut`). The newest `draft_info.json` modification time tells you which project is open. Writing a draft CapCut holds in memory loses the work when it saves.
- **Never overwrite a track the owner has edited.** Compare the project’s current caption text with the subtitle file that generated it: identical means untouched; different means they edited it – leave it and tell them.
- **A draft has two read paths** (`draft_info.json` and `Timelines/<uuid>/draft_info.json`) plus `draft_meta_info.json` for the media pool. Write all of them, and **write the same blob to both copies** – building each file separately mints different ids and the copies diverge. After any write, assert the two copies are equal.
- **`path` is not the only key holding a file location** – `file_Path` outnumbered it 60 to 16 on one draft.
- **Never hard-code a project name a tool depends on.** Resolve it by pattern; folders are the owner’s to rename.
- **Media paths are stored verbatim and absolute.** Moving a folder breaks every layer.
- **Voice placement:** `t = max(t_est, prev_end + 0.30)`, using real `ffprobe` durations, never estimates.
- **Voice takes:** sweep stability 0.3 / 0.5 / 0.75 per line and pick by high-frequency energy within the same wording ([`sa_hfcheck`](../../../../tools/sa_hfcheck.py)); a stubborn dull line gets 0.9. Still poor after about five takes = the wording, not the delivery: flag it for the owner’s ear and stop.
- **`screencapture` silently refuses any filename starting with a dot** – it exits 0, writes nothing and says it “cannot write file”. It is not a permissions problem.
- **`ffprobe` takes one `-show_entries`** – a second one silently replaces the first.
- **Pad audio to the video with `apad=whole_dur=`**, never `-shortest`, which trims picture.
- **A vision model that fails to answer is not a defect found.** Keep three outcomes. A false alarm costs the owner more than a miss, because they go and look.
- **Heavy local-model batches run only at night** (1–6 am); they make the machine stutter while the owner works. Single checks are fine any time.

## Locked numbers (generic)

- CapCut’s on-screen position readout is the normalised value × 1000: −892 in the interface is `y = -0.892` in the JSON.
- **Captions:** always one line, never wrapped, at most 46 characters.
- **Pacing:** speed cap 1.6× (`SPEED_MAX`), readable screens at about 1.2×, 0.9 s between lines, 2.5 s tail hold. If a segment feels rushed, split it and write a second line; never raise the cap.
- **Sign-off:** identical on every video in a series; never “in the next video…”.

## Learning from the owner’s own edits

[`sa_editwatch`](../../../../tools/sa_editwatch.py) reads the project file (what changed, in numbers); [`sa_screenwatch`](../../../../tools/sa_screenwatch.py) captures the editor window (how it was done). [`sa_learn`](../../../../tools/sa_learn.py) joins them after the owner closes CapCut, writes the technique note, then deletes the frames.

**Most of what an editor does is looking, not authoring** – zooming, scrubbing, nudging to compare. Never turn a watched action into a rule without asking what it was for: a zoom to 248% was once read as a style choice when it was only magnifying the preview. Telling the owner’s edits from the agent’s own needs no bookkeeping: they can only edit while CapCut is open, and every write tool here refuses to run unless it is closed.

---

Related: [training-video production](../../../../playbooks/training-video-production.md) · [the CapCut draft format](../../../../playbooks/capcut-draft-format.md) · [learning an editor’s style](../../../../playbooks/learning-an-editors-style.md) · [`senior-video-editor` agent](../../agents/senior-video-editor.md) · [tools index](../../../../tools/README.md)
