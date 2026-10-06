# studio — a local MCP server for editing and photo work

**Status: Built, in use.** It is connected in Saad's own Claude Code setup. The code was written by AI coding agents under Saad's direction, and its test suite runs against his own CapCut projects and photo sets.

`studio` is a small [MCP](https://modelcontextprotocol.io) server with six tools. They let an AI assistant read CapCut drafts, export their captions, audit the call-outs in a tutorial, cull a photo shoot, look up an editing style and search prompt playbooks. The server runs locally and uploads nothing: it makes no network calls.

Below, "the vault" means `STUDIO_ROOT`, which by default is this repository. Most of the server's logic comes from the published tools in [`tools/`](../../tools/), which it reuses rather than rewrites:

- `sa_actioncheck`, `sa_capcut`, `sa_captions`, `sa_editdna` and `sa_console` are imported.
- `sa_cull` is run as a separate process.

| Tool | What it does | Writes? |
|---|---|---|
| `style_lookup(style)` | Looks up the editing grammar family for a style in [`Reference/SAAD_EDITING_GRAMMAR.json`](../../Reference/SAAD_EDITING_GRAMMAR.json): chapters, slot pattern, cut rhythm, transition budget and rules. It also returns cut-length statistics: the saved [`Reference/EDIT_DNA_STATS.json`](../../Reference/EDIT_DNA_STATS.json) and, if you have built a full style brain of your own (`STUDIO_STYLE_BRAIN`), live numbers recomputed from it. The live numbers are aggregates only and never include project names. `style` can be a family, a style type, plain words (e.g. `montage`, `software demo`, `farewell`), or `list`. | No |
| `capcut_project_summary(project, timeline?, allow_large?)` | Summarises a CapCut draft: duration, canvas, fps, export (In/Out) range, every track with its segment counts, compound clips, caption/title/text counts, cut pace, transitions and effects. It also lists media the draft uses that is **missing on disk**, including media inside compound clips. Use `project="list"` to see the 30 most recently saved projects. | No |
| `capcut_export_srt(project, out_path?, timeline?, timeline_range?, caption_size?, allow_large?)` | Writes the draft's captions to a **new** `.srt` file. By default it covers only the export range and times it from the In point, so the subtitles line up with the exported video. Captions inside compound clips are included. Returns the path, the cue count and a preview of 3 cues. | One new `.srt` |
| `callout_audit(project, timeline?, timeline_range?, caption_size?, allow_large?)` | Splits the narration into individual instructed actions and lists any that have no visible call-out image or label from 5 s before to 4 s after the narrated action. It looks inside compound clips and understands phone-app narration (tap, press, swipe, scroll, long-press, go back, return, enter). The results are **candidates to verify on frames**, never a pass. The result is "incomplete" if the draft has no captions, or if almost none of the narration reads as instructions. | No |
| `photo_cull(folder, limit?)` | Scores up to `limit` JPGs (default 100, max 500) for sharpness, exposure and clipping, groups near-duplicates, and picks the best of each group. It writes a report, a picks list and a contact sheet into a **new** folder. | One new folder |
| `prompt_search(query, limit?)` | Searches prompt playbooks: by default [`playbooks/ai-video-and-image-generation.md`](../../playbooks/ai-video-and-image-generation.md) and [`playbooks/ai-music-prompting.md`](../../playbooks/ai-music-prompting.md), or your own files via `STUDIO_PROMPT_FILES`. Results are ranked the same way [the brain's](../../playbooks/the-brain.md) keyword search ranks them. Returns each entry's heading, date, score and `quoted_text`, cut to 1,500 characters. | No |

## Safety guarantees

- **CapCut projects are only read.** No tool writes inside the CapCut drafts folder or anywhere under `~/Movies/CapCut`.
- **The vault is only read.** No tool writes anywhere under the vault (`STUDIO_ROOT`, which includes `tools/` and `Reference/`), so nothing stray can end up in your notes or a git commit.
- **Other spellings of a folder can't get past the checks.** The Mac's disk ignores letter case, so a folder is matched both by name (ignoring case and Unicode form) and by file identity. `~/movies/capcut/...`, an upper-case path, a firmlink such as `/System/Volumes/Data/Users/you/...` and a symlink all count as the real folder.
- **Default output folders are checked where they really lead.** The SRT and cull folders under the output root are resolved before anything is created. If one of them is a symlink into CapCut or the vault, the call is refused and nothing is written.
- **Nothing is ever overwritten.** The SRT, the cull report and the picks list are opened with exclusive-create and no-follow; the contact sheet is written into a folder the server has just created and checked is empty. An existing `out_path` is refused. A default SRT name or a cull folder gets ` (2)`, ` (3)`… added if the name is already taken.
- **Output only goes to allowed folders.**
  - The allowed folders are `~/Downloads`, `~/Desktop`, `~/Documents` (except the vault), `~/Movies` (except CapCut), `~/Pictures` and the output root. `STUDIO_WRITE_ROOTS` overrides this list.
  - The tools never write under `~/Library`, any hidden (`.`) path, or a network path (`/net`, `/Network`).
  - A path must be absolute, have the right suffix, and its parent folder must already exist.
- **Original photos are only read.** `photo_cull` creates a fresh, timestamped folder and writes nothing anywhere else. If the call is cancelled or times out, the scoring process is stopped.
- **The vault stays clean.** No vault file is modified. Vault modules are loaded with bytecode writing switched off, so no `.pyc` files appear in `tools/`. Vault functions that print to the terminal, overwrite files or exit the process (`export()`, `main()`, `write_srt`…) are never called.
- **No network, even by accident.**
  - fastmcp's PyPI update check is switched off in code, before fastmcp is imported.
  - Media paths on network shares (`/net`, `/Network`, SMB/NFS/AFP mounts) are never touched, so an unreachable share can't stall a call. They are counted as "not checked". A drive that isn't plugged in is reported without being probed.
- **Drafts that can't be read safely are refused, not guessed at.**
  - An encrypted timeline is reported as encrypted.
  - A timeline file over 60 MB is refused unless `allow_large=true`, because one 805 MB draft takes about a minute to parse.
  - A half-saved file is retried once.
- **Inputs and results are size-capped.**
  - Inputs: a query or style can be up to 200 characters, and a query up to 12 words. A project or timeline name can be up to 300 characters, and a path up to 1,024. Anything longer, or anything containing a NUL character, is refused with a short message.
  - Results: 60 tracks, 25 missing files, 50 audit candidates, 30 picks, 30 unreadable photo names, 20 prompt results. Images are never returned.
- **Returned text is labelled as data.** Prompts, captions and titles come straight from local files. Some prompts are written as instructions ("You are retouching…"). The server instructions and tool descriptions tell the client to treat this text as data, never as instructions to follow.

## How it reads a draft

- **Choosing the project and timeline.** The project is matched by exact folder name, then a unique part of the name, with suggestions if nothing matches. The timeline is the one named in `timeline`, otherwise CapCut's `main_timeline_id`; if neither is recorded, the first timeline on disk is used (the project summary says so in its notes), and only then the legacy root `draft_info.json`. Pass `timeline` when a project has several.
- **Compound clips.** CapCut keeps a compound clip's contents in `materials.drafts` and links the timeline segment to it through `extra_material_refs`. The server reads inside each placed compound clip, nested up to 4 deep. An inner time `x` appears on the timeline at `T + (x − S) / speed`, where `T` is where the clip sits and `S` is where its source range starts. Anything outside the clip's window is cut off. A hidden compound clip hides its contents. Over 40 of Saad's own projects use compound clips; one training module alone keeps 72 of its media files and most of its call-outs inside them.
- **Finding the captions.** The tool looks for a track named "Captions" first, then CapCut's own caption track, then the most common small text style. It matches on both text size and vertical position: in Saad's projects the desktop training videos use size 5, the phone-app ones size 8, and a commercial size 6. Hidden captions and switched-off tracks are skipped. `caption_size` forces a size.
- **Two caption tracks at once.** Narration sentences are joined one track at a time, so two tracks are never interleaved. In the SRT, cues that start within 0.2 s of each other are merged into one two-line cue, and every other cue is trimmed at the next cue's start. The 0.2 s minimum never pushes a cue past the next one. Both tools return a warning that lists the overlapping times. Four of Saad's real training modules have such moments.
- **Phone-app narration.** The `sa_actioncheck` verb list was written for desktop software training. The server adds tap, press, swipe, scroll, long-press, go back, return and enter by rebuilding the vault's own patterns with a longer verb list. The vault file itself is untouched. It also splits at `: ` and at `, or <verb>`.
- **"Incomplete" audits.** A draft gets "incomplete" when no actions are recognised, or when it has 10+ narration sentences and fewer than 15% of them hold an action. Measured on the local projects, the training videos score 0.24 or more actions per sentence and the brand films score 0–0.05.
- **SRT timestamps** are rounded to whole milliseconds with `sa_captions.ts`. The vault's `sa_srtexport.stamp` can produce an invalid `,1000`.

## Run

You need macOS (the folder checks and the CapCut paths assume it), [uv](https://docs.astral.sh/uv/) and Python 3.12; the draft tools also need CapCut's desktop app and its drafts. The server pins `fastmcp==3.3.1`, the same pin as the [brain server](../../workspace-kit/brain/), and holds `mcp` and `pydantic` at the versions that server was tested with; `uv.lock` records the exact set.

`photo_cull` also needs a second Python with OpenCV, numpy and Pillow, because the server's own environment has none of them. From the repository root, `python3 -m venv .venv && .venv/bin/pip install opencv-python-headless numpy pillow` makes the default one (tested on Python 3.9 with OpenCV 5.0.0.93, numpy 2.0.2, Pillow 11.3.0; `tools/requirements.txt` lists what the other tools need).

```bash
cd mcp/studio
uv sync --frozen                                  # once: builds .venv from uv.lock
uv run --offline --frozen python server.py        # stdio transport (what an MCP client starts)
uv run --offline --frozen python test_server.py   # end-to-end checks
```

`--offline --frozen` means a missing `.venv` fails loudly instead of downloading from PyPI.

Settings are environment variables, all optional:

| Variable | Default |
|---|---|
| `STUDIO_ROOT` (the vault) | this repository (two folders up from `server.py`) |
| `STUDIO_CAPCUT_DRAFTS` | `~/Movies/CapCut/User Data/Projects/com.lveditor.draft` |
| `STUDIO_OUT` (new SRTs and cull folders) | `~/Downloads/Studio MCP` |
| `STUDIO_WRITE_ROOTS` (`:`-separated) | see Safety guarantees |
| `STUDIO_MAX_DRAFT_MB` | `60` |
| `STUDIO_CULL_PYTHON` (a Python with OpenCV, for `photo_cull`) | `<STUDIO_ROOT>/.venv/bin/python3` |
| `STUDIO_STYLE_BRAIN` (full style brain, for live cut stats) | `<STUDIO_ROOT>/Reference/CAPCUT_STYLE_BRAIN.json`; skipped if missing |
| `STUDIO_PROMPT_FILES` (`:`-separated; relative to `STUDIO_ROOT`, or absolute) | `playbooks/ai-video-and-image-generation.md:playbooks/ai-music-prompting.md` |

A full style brain is built from your own CapCut projects with [`tools/sa_stylebrain.py`](../../tools/sa_stylebrain.py). It lists project names and every cut, so it stays private (the repository's `.gitignore` already excludes it). The repository ships only the anonymised summary, [`Reference/capcut_style_brain_anonymised.json`](../../Reference/capcut_style_brain_anonymised.json), which has no per-cut rows. Without a full brain, `style_lookup` returns the saved statistics only.

`test_server.py` runs the server in memory and calls all six tools on real local data:

- the most recently saved captioned project, which is only read;
- two optional regression projects of your own, if you name them: `STUDIO_TEST_COMPOUND_PROJECT` (call-outs kept inside compound clips) and `STUDIO_TEST_PHONE_PROJECT` (phone-app narration);
- a temporary copy of 10 photos;
- the prompt playbooks.

It also checks every refusal path, including other spellings of CapCut and vault folders, symlinked default folders, NUL bytes and over-long inputs. It covers the edge cases on synthetic drafts: compound clips, phone narration, overlapping caption tracks, the audit window, and network media. It checks that cancelling a cull stops the scoring process. Afterwards it verifies the CapCut project and the photo copies are unchanged, and deletes its temporary folder.

## Register with Claude Code

Use the absolute path of your clone:

```bash
claude mcp add --scope user studio -- uv run --directory <path>/mcp/studio python server.py
```

Once `uv sync` has run, you can add `--offline --frozen` after `uv run` so that starting the server never contacts PyPI.

## Speed

| Operation | Time |
|---|---|
| Cold start to first response | ~0.5–4 s (importing fastmcp is the bulk) |
| Reading a typical draft | 0.01–0.15 s |
| `photo_cull` | ~1–4 s fixed, plus ~0.05–0.1 s per photo; progress is reported while it runs |
| All 121 readable projects on Saad's machine through summary, audit and SRT export | ~6 s |
