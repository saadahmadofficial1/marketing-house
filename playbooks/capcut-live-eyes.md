> Related: [CapCut hub](capcut.md) · [observed editing technique](editing-technique-observed.md) · [learning an editor's style](learning-an-editors-style.md) · [CapCut draft format §11](capcut-draft-format.md#11-watching-edits-without-touching-them) · [the CapCut Eyes app](../apps/capcut-eyes/)

# CapCut Live Eyes

The editor's CapCut observation system is local, read-only and session-based. It learns from the
combination of CapCut's saved timeline and the visible CapCut editor window.

## What the eye records

- **What changed:** every saved CapCut timeline is checked once per second. Events include
  the project, timeline ID, exact time, before/after hashes and numerical changes to clip
  timing, source trim, speed, volume, position, scale, rotation, opacity, tracks, keyframes
  and text ([`sa_editwatch.py`](../tools/sa_editwatch.py)).
- **How it was changed:** every materially changed CapCut window is captured about every
  three seconds. It never captures the full desktop, email, messages or browser windows
  ([`sa_screenwatch.py`](../tools/sa_screenwatch.py)).
- **What survived:** the session keeps the first and final saved draft for every touched
  timeline. Reverted or temporary changes are process/inspection evidence; they are not
  promoted into the editor's style.

Every readable current CapCut project folder and all its timelines are in scope. Projects
and timelines created after a session starts are discovered automatically. The reader never
writes to a CapCut draft or source-media file.

## Start, pause and finish

The current control is the orange/yellow **CapCut Eyes** item in the Mac top taskbar,
provided by [`sa_watchbar.py`](../tools/sa_watchbar.py). A movable floating pad ([`sa_eyes_pad.py`](../tools/sa_eyes_pad.py)) came first;
the taskbar item replaced it when the pad proved unreliable in a live UI check. The controller is
launched in an authorised local background session because macOS blocks a directly opened
unsigned app bundle from reading the protected Documents and Movies folders. The `.app` bundles
([apps/capcut-eyes](../apps/capcut-eyes/)) remain prototypes and are not the verified launch route.

The taskbar controller owns the watcher processes: if the controller closes or crashes, both
watchers automatically stop. This prevents invisible recording.

Its states are:

- `🟠 REC` — both exact timeline reading and CapCut-window capture are live.
- `🟡 LOG` — timeline evidence is live but visual capture is unavailable.
- `🟡 PIC` — visual capture is live but timeline reading is unavailable.
- `👁` — watchers are ready and waiting because CapCut is closed.
- `⏸ paused` or `⚠️ OFF` — not watching.

Control commands, when needed:

```text
python3 tools/sa_eyes.py start
python3 tools/sa_eyes.py status
python3 tools/sa_eyes.py stop
python3 tools/sa_eyes.py handoff
```

`Finish recording for Claude to learn` stops capture immediately and marks the session as
pending Claude review. It preserves the screenshots, exact event log and before/final draft
evidence ([`sa_eyes.py`](../tools/sa_eyes.py) `handoff`). The taskbar must not start a local vision model or automatically delete frames. Claude performs
the visual learning pass, records what is genuinely supported, and only then may the covered
screenshots be removed under the standing cleanup approval. The editor made Claude the learning
owner after the automatic local learner failed more than once.

## Evidence and memory

Each run is isolated in its own session folder (`<session-id>/`):

- `manifest.json` — scope, privacy rules, state and watcher process IDs;
- `timeline_events.jsonl` and `timeline_changes.md` — exact edits;
- `timeline_before/` and `timeline_final/` — evidence for survived vs reverted changes;
- `frames/frame_index.jsonl` — exact capture time, CapCut window ID, dimensions and hash;
- `observations.json` and `learning.md` — local visual reading and final-session findings;
- `purge_receipt.json` — hashes of screenshots deleted after successful learning.

The durable human-readable record is the [observed editing technique](editing-technique-observed.md) page. A single action
is always an observation, never a style rule. Repeated sessions or the editor's direct correction
are required before changing the editing grammar.

## Privacy design and honest limits

The recording runs locally and uploads nothing: both watchers write their evidence to the
local session folder, and frames are never sent to generation services or any other third-party
service. The one deliberate exception is the learning pass, which the editor assigned to Claude:
at hand-off, Claude reviews the session evidence, frames included. That replaced an earlier route
in which a local vision model did all the reading on the machine; the tool keeps that fully local
route for compatibility. The system sees saved timeline states
and changed visual frames; it does not continuously record video or claim to know every mouse
movement between frames. A yellow menu-bar state means one of the two evidence streams is
missing and must be treated as degraded.

An older watcher left 954 legacy screenshots in a separate legacy folder.
They are not mixed into new sessions and must not be deleted automatically because the old
observation file does not prove complete coverage.
