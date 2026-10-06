# CapCut Eyes

A local, read-only watcher that records how I edit in CapCut – what changed in the saved timeline, what CapCut’s window showed while it changed, and which changes survived – so my AI agents learn from what I actually do rather than from what I say I do. It never writes to a CapCut project; a menu-bar light shows when it is watching, and closing the controller stops everything.

**The parts:** [`sa_eyes.py`](../../tools/sa_eyes.py) (session supervisor) · [`sa_editwatch.py`](../../tools/sa_editwatch.py) (timeline reader) · [`sa_screenwatch.py`](../../tools/sa_screenwatch.py) (CapCut-window capture) · [`sa_watchbar.py`](../../tools/sa_watchbar.py) (menu-bar indicator and kill switch) · [`sa_eyes_pad.py`](../../tools/sa_eyes_pad.py) (floating control pad) · [`sa_learn.py`](../../tools/sa_learn.py) (learning pass and screenshot purge) · launchers in [`workspace-kit/launchers/`](../../workspace-kit/launchers/) · [`make_apps.sh`](make_apps.sh) (builds the two app bundles). The method is written up in [the CapCut draft format, section 11](../../playbooks/capcut-draft-format.md#11-watching-edits-without-touching-them), the working note [CapCut live eyes](../../playbooks/capcut-live-eyes.md) and the hub page [CapCut](../../playbooks/capcut.md#5-live-edit-watching-capcut-eyes).

The code was written by AI coding agents (Claude Code and Codex) under my direction and review.

## Status

| Part | Status | Notes |
|---|---|---|
| Timeline watcher ([`sa_editwatch.py`](../../tools/sa_editwatch.py)) | **Pilot** | Run across ten monitored projects; its events fed the measured editing rules |
| Window capture ([`sa_screenwatch.py`](../../tools/sa_screenwatch.py)) | **Pilot** | CapCut windows only |
| Session supervisor ([`sa_eyes.py`](../../tools/sa_eyes.py)) | **Pilot** | One isolated evidence folder per session |
| Menu-bar indicator and kill switch ([`sa_watchbar.py`](../../tools/sa_watchbar.py)) | **Built, in use** | The current control, started from a session that already has folder access |
| Floating control pad ([`sa_eyes_pad.py`](../../tools/sa_eyes_pad.py)) | **Experimental** | My first request; it proved unreliable in a live check, so I chose the menu bar instead |
| The two `.app` bundles ([`make_apps.sh`](make_apps.sh)) | **Experimental** | Prototypes, not the verified launch route (see [Running it](#running-it)) |
| Fully local learning pass (`sa_learn.py --analyse`) | **Experimental** | Kept for compatibility; it failed on live sessions, so the learning pass is now an AI-agent review |

---

## What it watches

Three kinds of evidence, joined by the clock:

| Evidence | Source | How often | What is recorded |
|---|---|---|---|
| **What changed** | Every saved CapCut timeline (each timeline’s `draft_info.json`) | Checked once a second | Project, timeline id, exact time, before and after hashes, and numerical changes to clip timing, source trim, speed, volume, position, scale, rotation, opacity, tracks, keyframes and text |
| **How it was changed** | CapCut’s own windows | About every three seconds, only when the picture has materially changed | A PNG per change, with its capture time, window id, size and hash |
| **What survived** | The first and final saved draft of every touched timeline | At the start and end of the session | Two copies per timeline, so reverted or temporary changes can be told apart from kept ones |

CapCut saves the whole timeline to JSON every few seconds while I work, so most of what I do can be read as numbers – which box moved and exactly where, how long a freeze was held, which word was retyped – instead of guessed from pixels. The window capture adds the one thing the file can’t: which panel was open and what was selected.

Every readable CapCut project and every timeline is in scope, and projects created after a session starts are picked up automatically. Up to two CapCut windows are captured at once, because I often keep the timeline on one screen and the preview on the other.

### What it never does

- It never writes to a CapCut project or a source-media file.
- It never captures the desktop, mail, messages or a browser – only windows owned by CapCut.
- It never sends frames to a generation service. Capture runs locally and uploads nothing; the one route the frames take is the learning pass described below, where an AI coding agent reads them.
- It never turns one observation into a rule. A single action is an observation; repeated sessions or my direct correction are needed before my editing grammar changes.
- It never deletes screenshots on its own. Frames are removed only after the learning is written down, and only behind a checksum receipt.

---

## The menu-bar indicator

[`sa_watchbar.py`](../../tools/sa_watchbar.py) puts a short text title in the macOS menu bar, refreshed every three seconds from what is actually on disk. I asked for a visible sign whenever the watchers run: two background processes reading my project and my screen with nothing on screen to show for it is not something anyone should take on trust.

| Title | Colour | Meaning |
|---|---|---|
| `REC 12·47` | Orange circle | Both watchers live and CapCut open: 12 timeline events, 47 frames so far |
| `LOG 12·47` | Yellow circle | Timeline evidence live, window capture unavailable – **degraded** |
| `PIC 12·47` | Yellow circle | Window capture live, timeline reading unavailable – **degraded** |
| `12` with an eye | – | Watchers ready, waiting because CapCut is closed |
| `paused` | – | I paused it |
| `OFF` | Warning sign | Neither watcher is running |
| `error` | Warning sign | The refresh itself failed; the old title is never left standing |
| `?` in place of a count | – | Watching is live but the evidence folder can’t be read – the state is still true, only the counter is missing |

A yellow state is treated as broken, not as working. Orange was chosen after an early white idle dot proved impossible to pick out on a second screen.

**Menu items:** a live line (“N edits · N screenshots · CapCut open/closed”), **Pause watching** / **Resume watching**, **Open the edit log**, **Open the screenshots**, **Finish recording for Claude to learn**, and **Quit**, which stops both watchers rather than hiding the icon.

**Ownership:** the controller starts the watchers with its own process id (`--owner-pid`); if the controller closes or crashes, both watchers stop on their own. Nothing can keep recording invisibly. A session that has been finished for review stays paused across menu-bar restarts; resuming is always an explicit click.

**A fault worth knowing about:** macOS once refused the controller read access to the evidence folder. The resulting error escaped into the refresh timer, the timer died, and the menu bar froze on its last title – “paused” – while both watchers were still running. A frozen indicator is worse than an ugly one, because it shows a state that was true once as if it were true now. The refresh now catches every error and shows `error` or `?` instead.

## The control pad

[`sa_eyes_pad.py`](../../tools/sa_eyes_pad.py) is a small always-on-top window (306 × 176 px) with a draggable header that works on any monitor, including ones placed left of or above the main display. It remembers its position, collapses to a 250 × 42 strip, and allows only one copy at a time.

| Pad state | Dot | Shown when |
|---|---|---|
| Eyes live | Orange | Both watchers running and CapCut open |
| Eyes ready | Green | Both watchers running, waiting for CapCut |
| Timeline only / Picture only | Yellow | One watcher missing – degraded |
| Eyes paused | Grey | No watcher running; the session is kept |
| Ready for Claude | Purple | Recording stopped and the evidence preserved for the review |
| Waiting to learn | Purple | The older local route, waiting for CapCut to close |
| Learning saved | Green | The older local route finished and cleaned up |

Its buttons are **Resume**, **Pause** and **Finish for Claude**, and a status line shows the CapCut project saved most recently with the session’s saves and frames. Closing the pad stops the watchers. The pad proved unreliable in a live check, which is why the menu bar is the current control.

## Evidence counts

Every count shown in the menu bar or the pad is read off the session’s files at that moment, never remembered:

| Count | Read from |
|---|---|
| Timeline events (“saves”, “edits”) | Non-empty lines in `timeline_events.jsonl` |
| Frames (“screenshots”) | Non-empty lines in `frames/frame_index.jsonl` |
| Frame storage | Total size of the session’s PNGs (shown by `sa_eyes.py status`) |

When two sources disagree, the disagreement is named before anything is planned from them. One session’s stale observation file reported 12 events and 68 frames where the manifest showed 117 and 356.

## A session, start to finish

```text
python3 tools/sa_eyes.py start      # new session (or resume an unfinished one), launch both watchers
python3 tools/sa_eyes.py status     # state, events, frames, MB, which processes are live
python3 tools/sa_eyes.py stop       # pause: stop both watchers, keep the session
python3 tools/sa_eyes.py handoff    # finish: stop and preserve everything for the review pass
python3 tools/sa_eyes.py test       # self-check
```

Each session is isolated in `Sessions/_eyes/<session-id>/`:

| Path | Holds |
|---|---|
| `manifest.json` | Scope, privacy rules, state and watcher process ids |
| `timeline_events.jsonl`, `timeline_changes.md` | The exact edits, as data and as plain English |
| `timeline_before/`, `timeline_final/` | First and final drafts of every touched timeline |
| `frames/frame_index.jsonl` | Capture time, CapCut window id, dimensions and hash of every frame |
| `observations.json`, `learning.md` | The visual reading and the session’s findings |
| `purge_receipt.json` | Hashes of screenshots deleted after the learning pass |
| `editwatch.log`, `screenwatch.log`, `finish.log` | Process logs |

The manifest’s fields are `schema`, `session_id`, `status`, `started_at`, `ended_at`, `timeline_scope` (“all CapCut projects and all timeline draft_info.json files”), `visual_scope` (“CapCut windows only”), `data_route`, `project_mutation` (“none”), `learning_policy` (only changes that survive to the final draft can become candidates), `cleanup_policy` (screenshots deleted only behind checksum-backed coverage) and `pids`, plus `resumed_at`, `visible_owner_pid`, `learning_owner`, `claude_handoff_at` and `frame_disposition` when they apply. A session’s `status` moves through `starting` → `watching_or_waiting_for_capcut` → `stopped` → `stopped_pending_claude_learning`; `restarting`, `stop_requested` and the older local-route states also occur.

**The learning pass.** “Finish” stops capture immediately and marks the session for review. An AI coding agent (Claude) then reads the exact event log against the frames and records only what the evidence supports. I made the agent the owner of this pass after the fully local learner failed on live sessions. In the terms used across this repository: frames never go to a generation service and capture runs locally and uploads nothing, but this per-session pass is done by an AI coding agent reading the CapCut-window frames – which include CapCut’s preview of whatever footage is open – on its provider’s model, after which the frames are purged behind a checksum receipt. The screen half of the evidence earns its keep for two questions only – what was selected, and which dialog was open. The project file stays the source of truth for what changed.

---

## Running it

### The verified route

Start the menu-bar controller from a Terminal (or an agent session) that already has access to the folders CapCut uses:

```text
python3 tools/sa_watchbar.py
```

macOS privacy controls can stop an unsigned app opened from Finder reading `~/Movies` (where CapCut keeps its projects) or `~/Documents`. A process started from a session that already has that access inherits it, which is why this is the route in use.

### Building the app bundles (Experimental)

[`make_apps.sh`](make_apps.sh) builds two bundles from the launchers published in [`workspace-kit/launchers/`](../../workspace-kit/launchers/):

| Bundle | Built from | Runs |
|---|---|---|
| `CapCut Eyes.app` | `capcut_eyes.command` | The control pad, [`sa_eyes_pad.py`](../../tools/sa_eyes_pad.py) |
| `CapCut Eyes Menu.app` | `capcut_eyes_menu.zsh` | The menu-bar controller, [`sa_watchbar.py`](../../tools/sa_watchbar.py), unless one is already running; output goes to `Sessions/_eyes/menu.log` |

```text
apps/capcut-eyes/make_apps.sh                                   # bundles in apps/capcut-eyes/build/
WORKSPACE=/path/to/workspace apps/capcut-eyes/make_apps.sh
OUT_DIR="$HOME/Applications" PYTHON=/path/to/venv/bin/python3 apps/capcut-eyes/make_apps.sh
apps/capcut-eyes/make_apps.sh --help
```

| Setting | Default | Meaning |
|---|---|---|
| `WORKSPACE` | The repository root | The folder that holds `tools/`. The tools find the workspace from their own location, so session evidence lands in `Sessions/_eyes/` beside the tools folder |
| `TOOLS_DIR` | `$WORKSPACE/tools` | Where the CapCut Eyes tools are |
| `PYTHON` | `$TOOLS_DIR/venv/bin/python3`, else `python3` on the path | The interpreter baked into the bundles |
| `LAUNCHERS` | `workspace-kit/launchers` | The source launchers |
| `OUT_DIR` | `apps/capcut-eyes/build` | Where the bundles go (ignored by git) |
| `BUNDLE_PREFIX` | `local.capcut-eyes` | Bundle identifier prefix |

What the script does: it copies each launcher into `Contents/MacOS/`, swaps the launcher’s placeholder workspace path for `${WORKSPACE}`, `${TOOLS_DIR}` and `${PYTHON}` (with build-time defaults written at the top, still overridable when run), writes a minimal `Info.plist` (a menu-bar-only app, `LSUIElement`, macOS 12 or later), and checks the result with `plutil -lint` and `zsh -n`. It refuses to replace a bundle it didn’t build, removes a bundle whose build fails so the next run can retry, and never touches CapCut or anything outside `OUT_DIR`.

### Requirements

- macOS 12 or later and the CapCut desktop app, with projects in its default location (`~/Movies/CapCut/User Data/Projects/com.lveditor.draft`).
- Python 3 with `tkinter` (the pad), `rumps` (the menu bar) and `pyobjc-framework-Quartz` (finding CapCut’s windows): `python3 -m pip install rumps pyobjc-framework-Quartz`.
- **Screen Recording** permission for whichever app starts the watcher (System Settings → Privacy & Security → Screen & System Audio Recording). Without it the window capture refuses to run rather than writing black frames.
- Read access to `~/Movies` for the timeline reader.

## Faults it was built around

Each of these happened on a live session and is now handled in code:

| Fault | Fix |
|---|---|
| The menu bar froze on “paused” while recording continued, after a folder-permission error killed its refresh timer | Every refresh error is caught and shown as `error` or `?` |
| macOS `screencapture` silently refuses a filename starting with a dot; the failure was misread as a missing permission for an hour | Hidden filenames are rejected up front, and stderr is read before blaming permissions |
| Only the largest window was captured, so the second screen was missed | Up to two document windows, ranked named → on-screen → size |
| An untitled, never-shown grey CapCut surface outranked the real timeline window | Named windows rank first |
| A dead (zombie) watcher still answered “alive” to a simple process check | Liveness also reads the process state and command line |
| A zoom to 248% was recorded as a style choice; I was only magnifying the preview | One action is an observation; the review asks what it was for |
| An earlier watcher’s leftover screenshots couldn’t be proven fully covered by its observation file | They are kept separate and never deleted automatically |

## Related

- [CapCut hub](../../playbooks/capcut.md) – how I work in CapCut and every CapCut tool.
- [The CapCut draft format](../../playbooks/capcut-draft-format.md) – the project files this reads, and why nothing here writes them.
- [Learning an editor’s style](../../playbooks/learning-an-editors-style.md) – what the watched sessions taught, with the numbers.
- [Editing technique, observed](../../playbooks/editing-technique-observed.md) – the session-by-session record.
- [CapCut live eyes](../../playbooks/capcut-live-eyes.md) – the working note this system runs by.
- [Security and data policy](../../playbooks/security-and-data-policy.md) – what stays local and why.
