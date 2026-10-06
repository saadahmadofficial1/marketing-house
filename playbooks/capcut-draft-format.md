# The CapCut draft format, and how the tools write it safely

CapCut has no public project API, so my tools read and write its project files directly. This is the format as my AI coding agents worked it out from my own projects – the identity rules that decide whether a project opens at all, the geometry maths, the material shapes – and the guard rails every writer follows.

Every fact here was verified against real projects on my machine in 2026; none is guessed. The format is undocumented and could change with a CapCut update, so the tools re-verify what they write instead of trusting this page. The code was written by AI coding agents (Claude Code and Codex) under my direction and review; I did not write it by hand.

**Where the work is done:** the writers and readers listed in [section 8](#8-how-the-tools-write-safely) and in the full [CapCut tool table](capcut.md#8-every-capcut-tool) · the plan format they accept, [`templates/timeline_plan.schema.json`](templates/timeline_plan.schema.json) · the read-only watcher, [CapCut Eyes](../apps/capcut-eyes/README.md) · the hub page, [CapCut](capcut.md).

## Status at a glance

| Part | Status | Notes |
|---|---|---|
| New-project builder that clones a donor project ([`sa_capcut_callouts.py`](../tools/sa_capcut_callouts.py)) | **Built, in use** | Used to build a full training series that was delivered, including one module authored entirely by code |
| Caption importer ([`sa_capcut_captions.py`](../tools/sa_capcut_captions.py)) | **Built, in use** | Editable text layers in the house style, on delivered videos |
| Media-pool import and outro append ([`sa_import.py`](../tools/sa_import.py), [`sa_outro.py`](../tools/sa_outro.py)) | **Built, in use** | The only writes allowed on finished videos |
| Read-only renderer – a draft to MP4 with ffmpeg alone ([`sa_ffrender.py`](../tools/sa_ffrender.py)) | **Pilot** | In an overnight experiment it rendered 19 of 19 training timelines to their exact length; used for review renders, not delivery |
| Plan-driven writer ([`sa_capcut_writer.py`](../tools/sa_capcut_writer.py)) | **Built, awaiting review** | Structurally verified; the live open-in-CapCut test is still pending |
| Read-only observation of my edits ([`sa_eyes.py`](../tools/sa_eyes.py), [CapCut Eyes](../apps/capcut-eyes/README.md)) | **Pilot** | Capture runs locally; records saved timeline changes and the CapCut window only |

## Contents

1. [Where things live](#1-where-things-live)
2. [Units and serialisation](#2-units-and-serialisation)
3. [Identity: the rules that decide whether a project opens](#3-identity-the-rules-that-decide-whether-a-project-opens)
4. [Geometry](#4-geometry)
5. [Material, segment and track shapes](#5-material-segment-and-track-shapes)
6. [Layering and magic values](#6-layering-and-magic-values)
7. [The media pool](#7-the-media-pool)
8. [How the tools write safely](#8-how-the-tools-write-safely)
9. [Verifying a written draft](#9-verifying-a-written-draft)
10. [Rendering a draft without CapCut](#10-rendering-a-draft-without-capcut)
11. [Watching edits without touching them](#11-watching-edits-without-touching-them)
12. [Open questions](#12-open-questions)

---

## 1. Where things live

Projects sit under `~/Movies/CapCut/User Data/Projects/com.lveditor.draft/<project>/`:

```
<project>/draft_info.json                    legacy root copy of the timeline
<project>/Timelines/<uuid>/draft_info.json   current, per-timeline copy
<project>/Timelines/project.json             which timelines exist, which is main
<project>/draft_meta_info.json               identity (draft_id, name, folder) + media pool
```

A project keeps its timeline in **two** places, and CapCut may read either. Writing only one of them looks like success and isn’t: the first 15 projects built this way all opened showing the donor project’s timeline. A later tool wrote only the per-timeline copy, so CapCut kept showing the old cut while the new one sat on disk – I caught that by asking whether the changes were actually in CapCut itself.

CapCut’s own index of all projects (`root_meta_info.json`, one level up) registers new projects itself on launch. It is never written.

## 2. Units and serialisation

| Thing | Unit |
|---|---|
| All timeline times and durations | **integer microseconds** (`US = 1_000_000`) |
| `draft_info.json` `create_time` / `update_time` | seconds since the epoch |
| `draft_meta_info.json` `tm_draft_create` / `tm_draft_modified` | microseconds since the epoch |
| Every id | upper-case UUID4: `str(uuid.uuid4()).upper()` |

Serialise the way CapCut does: single-line JSON, `ensure_ascii=False`, no indentation.

The `duration` header is what CapCut **exports**. Anything that shortens a project must recompute it from the end of the content – one removal left the header at 56.5 s on a project that now ended earlier, and CapCut exports the difference as black.

## 3. Identity: the rules that decide whether a project opens

CapCut indexes projects by `draft_id` and timeline id. A cloned project needs **every** identifier regenerated, or several projects claim one identity and none of them open.

**The opening invariant.** These are not independent ids – they must be one and the same UUID:

```
draft_info.json "id"
  == Timelines/<folder-uuid>
  == project.json "main_timeline_id"
  == project.json timelines[0].id
```

A fresh folder UUID that differs from `draft_info.id` means the project won’t open. Verified on three healthy projects, after it cost a full debugging round.

Donor identity also leaks through skeleton files: `timeline_layout.json` (its dock lists timeline ids) and `draft_biz_config.json` (keyed by timeline UUID) are rewritten; `template-2.tmp`, `draft_info.json.bak` and `draft_cover.jpg` (the donor’s thumbnail) are deleted. Then the whole folder is searched for the donor’s UUIDs until there are zero hits.

| Trap | Symptom | Fix |
|---|---|---|
| Donor’s root `draft_info.json` kept | Every new project opens showing the donor’s timeline – same duration, same size | Write the new content to **both** read paths |
| `draft_id` copied from the donor | Projects don’t appear, or collide in CapCut’s list | Fresh UUID per project in `draft_meta_info.json` |
| `project.json` left stale | Won’t open – `main_timeline_id` points at a deleted folder, or lists timelines that aren’t there | Fresh project id, exactly one timeline entry, `main_timeline_id` = the folder that exists |
| Timeline folder keeps the donor’s UUID | Two projects claim the same timeline | Rename the folder to the fresh UUID |
| Relative media paths | Every layer opens as missing media | CapCut stores paths verbatim – always absolute |
| The two copies built separately | The root and per-timeline copies drift apart (a caption tool minted fresh ids per copy) | Build once, write the **same blob** to both paths |
| A project folder copied wholesale | Three copies kept the original’s `Timelines/<uuid>` folder and `main_timeline_id`, so four projects shared one timeline id – and the original stopped opening. (The likely cause rather than a proven one: CapCut’s logs are encrypted.) | Never copy a project folder. Build from a donor skeleton with every id regenerated, as the writers do; park bad copies outside CapCut’s folder rather than editing its index |

**One exception to “write both”.** Sync the root copy only when the project has exactly one timeline. On a multi-timeline project the root is the finished parent video, and overwriting it with one slice would destroy it. The tools gate this on `len(glob("Timelines/*/draft_info.json")) == 1`.

## 4. Geometry

Verified against layers I placed by hand.

**Position.** `clip.transform` x and y are **fractions of half the canvas, with y positive upwards**:

```
px = W/2 + x * W/2
py = H/2 - y * H/2
```

Worked example: a caption at y = −0.892 on a 1920 × 1140 canvas lands at py = 570 + 0.892 × 570 ≈ 1078.

**CapCut’s UI readouts**, as they map to the file:

| UI value | In the file |
|---|---|
| Position (e.g. −892) | UI value ÷ 1000 (`transform.y = -0.892`) |
| Scale (e.g. 75%) | percent ÷ 100 (`0.75`) |
| Shadow opacity, blurriness | UI number ÷ 100 |
| Shadow distance, angle | as shown |

Shadow pixel offset: `dx = distance · cos(angle)`, `dy = −distance · sin(angle)`.

**Rotation.** `clip.rotation` is in degrees, and **positive is clockwise**. The sign was checked against a human correction: on one clip I had set +0.5° by eye, which corrected a measured +0.58° lean. To straighten a shot by code, measure the tilt from the frame’s own verticals (window frames, door edges, display cases) with a Hough line transform, and write the opposite rotation. The method and my eye agreed to within a tenth of a degree.

**The compositor fits an image to the canvas *before* applying `clip.scale`.** Doing the maths scale-first nearly condemned a set of correct boxes in one of my timelines.

**Overlay maths goes through the segment’s own scale.** An intro clip sitting at scale 1.06 to fill the canvas moves 1.06 canvas pixels for every clip pixel. Tracking in clip pixels without that factor made an overlay drift against the subject. Read the scale off the segment (`clip.scale.x`); never hard-code it.

**Canvas size varies per video** – heights of 1140, 1032 and 1020 pixels all occur. Probe it every time.

**Sidestep all of it for overlays.** Call-outs are authored as **full-canvas transparent PNGs** (or alpha MOVs) and placed at scale 1, transform 0, each on its own named track. They land exactly where they were drawn, I can still drag and resize them, and a wrong box is fixed by re-rendering the same filename – CapCut reloads it on open and the draft is never touched.

## 5. Material, segment and track shapes

The rule is to **clone a donor’s shape and change only what must change**.

**Video material** – `id`, `path` (absolute), `media_path ""`, `material_name` and `name` = the basename, `width`, `height`, `duration` (µs), `category_name "local"`, the other id and URL fields blank, and `type "video"`. PNG stills are `type "photo"`; an alpha MOV overlay must be flipped from photo to video after the call-out builder writes it.

**Audio material** – **never authored from scratch**: a hand-built audio schema opens as a silent clip that can’t be dragged. Clone the donor’s material and segment; change `id`, `path`, `name` and `duration`, and blank `music_id`, `text_id`, `tone_type` and `local_material_id`. Voice-over uses `type "extract_music"` at volume 1.0.

**Text material** – `content` is a JSON **string**, not an object: the text, `styles[0].size`, `styles[0].font.path`, fill at `styles[0].fill.content.solid.color` as `[r, g, b]` floats from 0 to 1, shadow at `styles[0].shadows[0]`. **Collapse to one style spanning the whole text.** Several overlapping style ranges stack their shadows – three at 50% opacity is not 50% – which was the “heavy shadow” bug. Don’t clone the donor’s first text material blindly: in my donor it was a Light weight, which vanishes over a bright software UI.

**Segment** (illustrative values):

```json
{
  "id": "<UPPER-UUID>", "material_id": "<UPPER-UUID>", "speed": 1.0,
  "source_timerange": {"start": 0, "duration": 2770000},
  "target_timerange": {"start": 12400000, "duration": 2770000},
  "render_timerange": {"start": 0, "duration": 0},
  "extra_material_refs": [], "render_index": 1, "visible": true,
  "clip": {"scale": {"x": 1.0, "y": 1.0}, "rotation": 0.0,
           "transform": {"x": 0.0, "y": 0.0},
           "flip": {"horizontal": false, "vertical": false}, "alpha": 1.0}
}
```

Text segments have `source_timerange: null`, not a dict. For speed-changed clips, `source_duration = timeline_duration × speed`; the speed material (`type "speed"`, `mode 0`) is referenced from `extra_material_refs`.

**Keyframes** – a segment’s `common_keyframes` carry a `time_offset` in **absolute source time**, in microseconds, not time from the segment’s start. A move across a whole clip therefore has keyframes at `source_start` and at `source_start + source_duration`. Verified by reading two of my own drafts. The plan-driven writer adds neither keyframes nor music by itself; writing keyframes from code has only been tried on an experimental build, so treat it as unproven and leave level or move keyframes to the editor where it matters.

**Per-clip adjustments** – brightness, highlights and shadows are not fields on the segment. Each is a material in the `effects` group (types `brightness`, `highlight`, `shadow`, `sub_type` none) linked to its clip, and the value is stored as a **fraction** of the UI slider: −0.15 ≈ slider −15. Clone the shape from a project where the adjustment was made by hand; don’t author it from scratch.

**Two-weight titles** – a title whose first line is Light and second line Black or Regular is one text material with **two** style ranges: `[0, len(line1) + 1]` and `[len(line1) + 1, len(full_text)]`. The ranges must be recomputed whenever the text changes, or the weight break lands in the middle of a word. This is the one deliberate exception to “one style range”: captions keep a single range; two-weight titles keep exactly two.

**Track** – `id`, `type` (video, text or audio), `attribute 0`, `flag 0`, `is_default_name`, `name`, `segments`. Named tracks are easy for me to find and drag.

The materials groups are `videos`, `texts`, `audios`, `speeds`, `transitions`, `stickers` and `video_effects`; the tools create any that are missing.

## 6. Layering and magic values

**`render_index` – higher paints on top:**

| Layer | render_index |
|---|---|
| Picture | 0 |
| Call-out layers | 1 … N |
| Assembled main clips | i + 2 |
| Titles | 900 + i |
| Sign-off text | 950 + i |
| Captions (always on top) | 20000 + i |

**A muted clip stores volume `0.0010000000474974513`**, and `vol > 0.001` is *true* for it in floating point. The mute test is `vol <= 0.01`; otherwise muted clips leak into a render and double the voice. `last_nonzero_volume` remembers the level before muting.

**Hidden and muted segments are normal.** I audition by stacking alternative takes on parallel tracks and muting or hiding the rejects – 1 to 39 hidden segments per timeline in one series – and they stay in the project. Every reader filters first:

```python
live = lambda s: s.get("visible", True) is not False and (s.get("volume") is None or s.get("volume") > 0)
```

An agent once skipped this, heard a rejected line in a hidden take, and reported a finished video as faulty.

**Transitions attach to a segment’s end.** After splitting a clip, the transition reference stays only on the last piece.

**Freeze stills** are CapCut’s own extracted frames, stored as `##_draftpath_placeholder_<UUID>_##/<hash>_<microseconds>-sdr709.png`, where the number is the source timestamp. Resolve the tail against the project folder, or renders fail. They are separate stills, not stretched clips – a checker that looks for `source_duration` much shorter than `target_duration` finds none of them.

**Two legitimate audio patterns.** The voice can be embedded in the paced picture with no audio track at all, or the picture is muted at 0.001 and the voice sits on separate audio tracks. Both occur in my approved edits; new builds use the second, so any single line can be swapped.

**An intro laid twice.** The intro tool places the full clip on top and a shorter cut underneath (skipping the 1-second head pad) for the fade. Anything that anchors to “the intro” must take the longest segment and carry its `source_timerange.start` into the frame maths.

**Inserting at the head needs two numbers.** When a new opening line went in after the intro, everything was shifted from `intro_end + gap` – but the content’s first audio began exactly on the intro’s last frame, so it stayed put and would have talked over the new line. Shift from the instant the intro ends; place the new audio at `intro_end + gap`.

## 7. The media pool

Media can be added to a project **without touching the timeline** by appending to the `type == 0` group of `draft_meta_info.json → draft_materials` ([`sa_import.py`](../tools/sa_import.py)). The clip appears in the project’s media panel ready to drag; not one segment moves. That matters because every finished video starts its content at 0.00 s – an insert would shift every caption and call-out.

Fields: `file_Path` (capital P, absolute), `extra_info` = filename, `duration` (µs), `metetype` `"video"` or `"music"` (MP3s are “music”; the misspelling is CapCut’s), `type 0`, `id` (upper-case UUID), `roughcut_time_range {0, µs}`, `sub_time_range {−1, −1}`, create/import times −1, `item_source 1`, `md5 ""`, width and height. De-duplicate on `file_Path`.

**`path` is not the only path key.** `file_Path`, `source_material_path` and `font_path` also hold absolute paths – on one draft, `file_Path` outnumbered `path` 60 to 16. Rewriting `path` alone fixes the timeline while the media pool still shows missing files.

**Relinking after files move** ([`sa_capcut_relink.py`](../tools/sa_capcut_relink.py)): `--scan` to report, `--move OLD NEW` for a known rename, `--fix ROOT` to hunt by filename. Basenames repeat across build folders, so it matches on the tail of the folder path and **refuses on a tie** rather than guessing. It never rewrites `draft_fold_path` or `draft_root_path` – those are the draft’s own location.

## 8. How the tools write safely

The write rules, each one earned:

1. **CapCut must be closed** (`pgrep -x CapCut`). CapCut holds the open project in memory and writes it back on save, silently undoing a repair. The newest `draft_info.json` modification time shows which project is live. On one machine `pgrep -x CapCut` did not see the running app, so the check also reads the process list by command name (`ps -axo comm`) – and never by a plain text search for “capcut”, which matches the search’s own command line.
2. **Back up beside the file first** (`.pre_captions`, `.pre_outro`, `.pre_import` …), once only. Re-read from disk after writing; restore if verification fails.
3. **New builds go to a new project.** Writers refuse to overwrite an existing project. The donor is strictly read-only and is found by a name pattern, not a hard-coded name – I renamed it once already. Choose it by three tests: every media path in it exists on disk (a donor that referenced cloud-only footage made every generated project crash CapCut on open, even with its tracks stripped), its canvas is already the target shape, and it has the fewest tracks and segments ([media-ops field notes](media-ops-field-notes.md#5-choosing-a-donor-project-for-generated-capcut-projects)).
4. **My finished timelines are deliverables-only.** The sanctioned writes, each at my request, are the outro append, media-pool imports and surgical retimes matched by call-out filename – plus, once, three revision inserts written onto their own tracks. A wrong box already in a draft is fixed by re-rendering the same image file.
5. **“Which projects may I touch” is derived** from the progress record I maintain, on every run – never a hard-coded list. A week-old list once nearly wrote labels into two videos I had since finished.
6. **Once a timeline is hand-adjusted, edit it surgically.** Rebuild from the original plan only while that plan is still the truth – after a freeze insert, the plan’s times no longer match the draft.

How the main writers apply them:

| Tool | Writes | Safety |
|---|---|---|
| [`sa_capcut_callouts.py`](../tools/sa_capcut_callouts.py) | A new project: picture plus one independent layer per call-out | Copies the donor, deletes its baggage, regenerates every id, writes one blob to both read paths, then `verify()` re-opens everything and raises instead of printing success |
| [`sa_capcut_captions.py`](../tools/sa_capcut_captions.py) | One text track of editable captions | Clones my own text style; builds once per unique input so both copies stay identical; backup; refuses while CapCut is open |
| [`sa_capcut_writer.py`](../tools/sa_capcut_writer.py) | A new lightweight project from a reviewed timeline plan ([schema](templates/timeline_plan.schema.json)) | Validates the plan; copies metadata only, not multi-gigabyte caches; deletes the half-written project on any failure |
| [`sa_import.py`](../tools/sa_import.py) | Media-pool entries only | Backup; refuses while CapCut is open |
| [`sa_outro.py`](../tools/sa_outro.py) | Appends the outro at the end of a finished video | The one sanctioned timeline write – appending moves nothing; checked against the backup that no existing segment moved |
| [`sa_freezeinsert.py`](../tools/sa_freezeinsert.py) | A freeze-frame at time t | Splits straddling clips, ripples later segments, stretches overlays rather than duplicating them |
| [`sa_capcut_flatten.py`](../tools/sa_capcut_flatten.py) | Collapses per-call-out tracks into two tracks | Refuses when segments overlap in time |
| [`sa_introfull.py`](../tools/sa_introfull.py) · [`sa_tailkit.py`](../tools/sa_tailkit.py) | Intro, title and music recipe; sign-off and music bed | The intro tool verifies or rolls back; both sync the root copy only on single-timeline projects |

The recipe for a brand-new project, as used on the module authored entirely by code:

1. Clone the donor scaffold with the call-out builder (fresh ids, verified, no overwrite).
2. Flip any MOV overlay material from photo to video.
3. Add the voice track by cloning the donor’s own audio material and segment shape – one segment per line.
4. Place lines with `t = max(t_estimate, previous_end + 0.30)` using real MP3 durations; anchor action lines to their on-screen moments.
5. Add captions with the caption importer.
6. Verify like the consumer would (section 9).

## 9. Verifying a written draft

A “done” message proves nothing. Every write is followed by a read-back:

- Both `draft_info.json` copies agree byte for byte; durations agree to 0.1 s.
- `project.json` lists exactly one timeline; `main_timeline_id` points at it; the folder exists.
- `draft_id` differs from the donor’s; `draft_name` matches the folder name.
- Every referenced media path exists on disk.
- Every box is inside the canvas: `w > 0`, `h > 0`, `x + w ≤ W`, `y + h ≤ H`. A box once written as corner coordinates into a width/height field ran 1,752 px off the canvas.
- Track and segment counts match the plan; no overlapping segments on a track; header duration = content end.
- Captions match the spec: size 5, `|y + 0.89| < 0.06`, one line. For captions the tool itself split, at most 46 characters; this is a build rule, not a test for my hand edits, where a cue can run to 54 to keep a phrase whole.
- Checks key on **content, never track names** – I rename tracks. A title is size-18 text; the sign-off is the words “thank you for watching”.

**House text spec**, as it maps to the file: captions are font size 5, scale 75%, position (0, −892), shadow 50 / 15 / 5 / −45, Poppins Regular, always one line. The title is two stacked size-18 elements at scale 49%, position (−747, 0): a Light first line and a Regular second line.

## 10. Rendering a draft without CapCut

[`sa_ffrender.py`](../tools/sa_ffrender.py) reads a draft read-only and renders it with ffmpeg: picture, call-out images, captions, title card, voice-over and outro. On one module it produced 45.833 s – the timeline’s 36.73 s of picture plus the 9.10 s outro, exactly. A timeline that can be rendered by code can also be built by code.

ffmpeg traps that cost real time:

- `drawtext text=` escaping cascades when a caption contains a comma – use `textfile=`.
- Create the base canvas at the **full** length including the outro, or the outro lands past the end of the stream driving the overlays and never draws.
- **Never use `-shortest` on the final mux.** The outro is muted, so the audio ends at the picture’s end and `-shortest` silently cuts the outro off. Pad audio to the video instead.
- **One giant filter graph doesn’t scale.** Picture, 100+ call-out images, captions and ~59 audio taps reached ~194 inputs; at that size the audio mix collapsed to a 0.01 s stream (one module rendered silent) and the muxer rejected the timestamps on another. Render video in one pass, audio in a second, then mux.
- `ffprobe` takes one `-show_entries` – a second silently replaces the first. Use `format=duration:stream=width,height` in a single flag.

## 11. Watching edits without touching them

To learn how I actually edit, a local observation system watches CapCut while I work. It never writes to a draft or a source file.

- **What changed**: every saved timeline is checked once per second. Events record the project, timeline id, exact time, before/after hashes and numeric changes to timing, trims, speed, volume, position, scale, rotation, opacity, tracks, keyframes and text ([`sa_editwatch.py`](../tools/sa_editwatch.py)).
- **How it was changed**: the CapCut window – never the full desktop, email or browser – is captured about every three seconds when it materially changes.
- **What survived**: the first and final saved draft of every touched timeline are kept. Reverted or temporary changes are evidence of process, not promoted into my style.

The menu-bar controller ([`sa_watchbar.py`](../tools/sa_watchbar.py)) owns the watcher processes: if it closes or crashes, both watchers stop, so nothing can record invisibly. It shows whether both evidence streams are live or only one – a half-live state is treated as degraded, not as working.

**Snapshot live drafts at every observed save.** CapCut keeps no history beyond a `.bak` file and its latest mini-draft. I once asked for the first version of an edit back – a long trimmed stringout that existed only while I was trimming inside CapCut, before anything had written to the project. It was rebuilt exactly as a new project (87 segments, 783.8 s, verified with no source overruns), but only because an earlier read had been recorded. The rule since: before touching anything in a live draft, and at every save the watcher sees, copy `draft_info.json` into the session folder.

Each session is isolated with a manifest, the event log, the before/final drafts and a frame index. The controls, states and evidence layout are documented in the [CapCut Eyes README](../apps/capcut-eyes/README.md). Capture runs locally and uploads nothing; the learning pass is a review of the preserved evidence by an AI coding agent, frames are never sent to generation services, and screenshots are deleted after the learning pass, behind a checksum receipt ([`sa_learn.py`](../tools/sa_learn.py)). **A single action is always an observation, never a style rule**: repeated sessions, or my direct correction, are needed before the editing grammar changes. Evidence counts that disagree are named before planning – one session’s stale observation file reported 12 events and 68 frames where the manifest showed 117 and 356.

## 12. Open questions

- **CapCut’s text size unit.** 1,315 of 1,358 text segments in one series are captions (size 5 at scale 0.75) and 35 are title lines (size 18 at scale 0.49). No single pixel-per-unit constant renders both correctly, so the renderer’s constant waits on a side-by-side comparison I judge by eye.
- **The plan-driven writer** has passed structural checks but not yet a live open in CapCut – the first attempt was correctly refused because CapCut was open.
- **Optical-flow slow motion.** No draft on my machine has ever saved an optical-flow setting, so its key is unknown. It is set in CapCut’s UI, never by writing the file. (It is rarely needed: 50 fps footage at 0.75× still gives 37.5 real frames a second, more than a 25 or 30 fps export uses; interpolation only starts to matter below about 0.6× for a 30 fps export.)
- **Format drift.** Nothing here comes from CapCut documentation. Every writer re-verifies its own output for that reason.

## Related

- [CapCut hub](capcut.md) – how I work in CapCut, the editing grammar as data, tutorial templates and every CapCut tool.
- [CapCut Eyes](../apps/capcut-eyes/README.md) – the read-only watcher described in section 11.
- [Learning an editor’s style](learning-an-editors-style.md) – what reading these files taught about my editing.
- [Training-video production](training-video-production.md) – the series these writers were built on.
- [Media-ops field notes](media-ops-field-notes.md#5-choosing-a-donor-project-for-generated-capcut-projects) – how to choose a donor project.
- [CapCut live eyes](capcut-live-eyes.md) – the working note behind section 11.
- [Learning from mistakes](learning-from-mistakes.md) – why each write rule is enforced in code.
