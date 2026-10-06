# Local AI and unattended jobs on one Mac

The same Mac that I edit on all day also runs local vision and language models and a set of scheduled jobs overnight. This page is how that works without making editing lag, and without jobs failing silently: which model runs when and on what, why running models in parallel gains nothing, the macOS privacy trap that kills scheduled jobs with no visible error, and the receipts that make a silent failure visible by the next morning. Every rule here came from a trap that was actually hit.

The tools: [`sa_visualmem.py`](../tools/sa_visualmem.py) (the visual-memory indexer, with a daytime and an overnight profile), [`sa_see.py`](../tools/sa_see.py) and [`sa_peek.py`](../tools/sa_peek.py) (describe a video or an image locally so the agent reads text instead of pixels), [`sa_qa.py`](../tools/sa_qa.py) (local guardrail check on generated stills), [`sa_translate.py`](../tools/sa_translate.py) (local English–Arabic subtitles), [`sa_guard.py`](../tools/sa_guard.py) (refuses a second heavy batch), [`sa_nightly.sh`](../tools/sa_nightly.sh) and [`sa_nightcheck.sh`](../tools/sa_nightcheck.sh) (the overnight runner and its 07:00 dead-man check) and [`sa_doctor.py`](../tools/sa_doctor.py) (the health check that reads every job’s receipts). The scheduling files are in [`../workspace-kit/scheduling/`](../workspace-kit/scheduling/README.md); step-by-step recipes are in [`templates/macos-nightly-launchd.md`](templates/macos-nightly-launchd.md) and [`templates/scheduled-agent-prompts.md`](templates/scheduled-agent-prompts.md).

---

## 1. Who does what

Tokens are the scarce resource, and so is the Mac’s attention while I’m editing. Anything a local model or a plain script can do, it does; the coding agent does only what only it can.

| Worker | Job | Model (as of October 2026) |
|---|---|---|
| Small local vision model | Daytime visual memory, quick “what is in this image” reads, frame descriptions for the agent | `qwen3-vl:2b` via Ollama |
| Larger local vision model | Overnight visual memory and deeper QA passes on generated stills | `qwen3-vl:8b` via Ollama |
| Small local language model | English ↔ Arabic subtitle drafts, timings kept, text lines only – always reviewed before publishing | `gemma3:4b` via Ollama |
| Free cloud text-to-speech | Draft voice-overs only – it sends the script text to an online service, so confidential scripts stay out | edge-tts |
| Plain scripts | Everything deterministic | – |
| The coding agents | Building, judgement calls, anything that needs reasoning across files | Claude Code, Codex |

How the 8B model earned the overnight slot: on three images I had checked by eye first, it caught 3 of 3 problems; an older 7B model caught 2 of 3 and missed the subtle hands in a grid of portraits – exactly the failure the no-hands guardrail exists to catch. Warm speed was the same for both, about 7–11 seconds an image.

---

## 2. Vision models by day without hurting the edit

The first version ran the 8B model on full-size originals in 150-image batches during the day, and editing lagged. The visual-memory indexer now has two profiles:

| Setting | Daytime (`background`) | Overnight (`overnight`) |
|---|---|---|
| Model | 2B | 8B |
| Images per run | 20 | 150 |
| Analysis copy, longest side | 1,024 px | 1,600 px |
| Pause between images | 4 s | 1 s |
| Request timeout | 240 s | 300 s |
| Keep the model loaded between images | 2 minutes | 1 minute |
| Pause when a creative app is open | Yes | No |

The rules that make the daytime profile safe:

- **Never the original.** Each image is resized to a temporary JPEG (`sips -Z <size>`, quality 82) and only that copy is sent to the model. Originals are opened read-only and the copy is deleted afterwards.
- **Step aside for creative work.** Before the run, and again before every image, the indexer checks the process list for an editing, motion-graphics or grading app (CapCut or DaVinci Resolve, for example). If one is open it stops with “nothing changed” rather than competing for the GPU.
- **Unload when done.** At the end of a run it sends `keep_alive: 0`, so the model’s memory is handed back to the editor immediately.
- **Respect the kill switch.** A single pause file stops the run before it starts and between images.
- **Results are plain text.** One JSON line per image plus a searchable Markdown file, against a fixed schema ([`templates/visual_memory.schema.json`](templates/visual_memory.schema.json)), so search never has to open an image again.

Two settings were tuned from failures, and the reasons are written into the code:

- **Timeout and keep-alive.** A cold model takes about 50 seconds to load and a reply about 30, so a 90-second timeout failed single images. A 20-second keep-alive was shorter than the pause for a creative app, so the model unloaded and paid the load cost again every time. Hence 240 seconds and 2 minutes.
- **The output budget (`num_predict`) must be generous, not absent and not tight.** At 420 tokens the reply was cut off mid-string, and the same three images failed every night – because a thinking-style model’s reasoning counts against the budget. Removing the limit was worse: on dense, text-heavy screenshots the model never stopped, and three images took 12 minutes of timeouts. A normal reply needs about 800 tokens; 2,000 clears every image measured and still bounds the pathological ones, so one bad file can’t eat the night. **Never set `num_ctx` on a vision call** – it truncates the image itself.

### Talking to a thinking-style vision model

- Send `"think": false`, and still read **both** reply fields: a thinking model may put its whole answer in `thinking` and leave `response` empty. The vision tools here all read `response or thinking`.
- Pass the JSON schema as `format` and use temperature 0, so the reply is parseable and repeatable.
- Bound the reply in the prompt as well: at most 12 readable-text entries – the headings a person would notice first – each under 100 characters, the whole reply under 2,000. Without it the model tries to transcribe an entire document from a screenshot.

---

## 3. Local models don’t run in parallel “for free”

Two local-model batches share the same GPU and memory lanes. Running two at once didn’t halve the time; it produced timeouts that looked as if the latest fix had failed. So:

- **One heavy batch at a time.** [`sa_guard.py`](../tools/sa_guard.py) refuses a second while one is running, matching the process that holds the model – never its own name or wrapper, after one version refused forever against itself.
- **Heavy batches only between 1 and 6 am.** By day: single-image checks and the small model only. Anything bigger is queued for the night.
- **Benchmark the real workload.** Timings taken with a placeholder prompt measured nothing; the real prompt behaved completely differently.

---

## 4. Scheduling on macOS: the silent exit 126

**The trap.** A `cron` or `launchd` job whose script lives in `~/Documents` (or reads from it) is refused by macOS privacy controls (TCC). It fails with exit 126 – or 2 with “Operation not permitted”, or 127 when the script sits in another protected folder – and nothing appears on screen. My memory backup ran this way and was dead for 24 days before anyone noticed.

My own memory protocol, written early on, said “use launchd, not cron – cron fails silently without Full Disk Access”. That turned out to be half right: launchd fails exactly the same way. The protected folder is the problem, not the scheduler.

**Two routes that work:**

| Route | How | Use it for |
|---|---|---|
| The agent app’s own scheduled tasks | The scheduled agent already has file access. Each task’s prompt starts by writing a STARTED heartbeat and ends by writing FINISHED or FAILED (section 5). | Agent-shaped jobs: digests, an inbox QA pass, memory consolidation. Prompt skeletons in [`templates/scheduled-agent-prompts.md`](templates/scheduled-agent-prompts.md). |
| A frozen applet run by launchd | Wrap the script once in an AppleScript applet, grant **that applet** Full Disk Access a single time, and have the launchd job open the applet. | The overnight runner and anything that must run with the agent app closed. |

The applet is one line, built once:

```bash
osacompile -o ~/Library/<Name>/Nightly.app \
  -e 'do shell script "$HOME/<workspace>/Tools/sa_nightly.sh"'
```

Then: System Settings → Privacy & Security → Full Disk Access → add the applet. The job’s plist runs `/usr/bin/open -W -a ~/Library/<Name>/Nightly.app` at a fixed early-morning time, with `PATH` and `HOME` set explicitly and `KeepAlive` → `SuccessfulExit = false`, so a failed run retries and a clean one stops. **All later edits go into the shell script; never re-save the applet** – the grant was given to that exact applet, and the point is never having to grant it again. Optional extras: a one-off `pmset repeat wakeorpoweron` so the Mac is awake before the job, and `caffeinate -im` around the heavy step. The full plist and the dead-man checker are in [`templates/macos-nightly-launchd.md`](templates/macos-nightly-launchd.md) and [`../workspace-kit/scheduling/`](../workspace-kit/scheduling/README.md).

**Re-check after every macOS update.** The grant regressed twice in three months. The second time, a full health check found three scheduled jobs failing at once – exit 2, exit 127 and exit 126 – while their scripts existed and were executable. Only a person can re-grant Full Disk Access, so the health check’s job is to make the failure loud, not to fix it.

**Skip the step, not the night.** An early version of the overnight runner exited entirely if the editing app was open, which I usually leave open. That silently skipped the whole night – the tool catalogue, the morning note and the clean-exit marker – and tripped the 07:00 dead-man check every day. Now only the step that reads editing projects is skipped; everything else still runs.

---

## 5. Make silence visible: receipts, not “ran”

A scheduled job that did nothing looks exactly like one that worked, unless something checks. These are the receipts the health check reads:

| Trap that was hit | Receipt that catches it now |
|---|---|
| **Catch-up runs that did nothing.** When the agent app opened after a missed night, every scheduled task was stamped “ran” in the same second, with zero output. | Each task appends `<time> <job> STARTED` to a heartbeat log as its first step and `FINISHED <result>` or `FAILED <reason>` as its last. The health check flags any STARTED from the last three days with no matching FINISHED. |
| **Jobs that never leave a trace.** Two scheduled tasks fired and produced nothing, with no run log at all. | Every task’s last step is “always leave a trace”: its output file, or a FAILED line. A missing trace is itself the failure. |
| **A run that never reached the end.** | The runner writes a `last_success` timestamp only on a clean exit; the 07:00 check ([`sa_nightcheck.sh`](../tools/sa_nightcheck.sh)) notifies me and drops a note into the day’s session folder if it is older than 10 hours. The next session reads the note first. (That checker is currently refused by macOS – see Maturity below.) |
| **A report that wasn’t true.** A “done: 150 images” report arrived while the real job was still running. | Check the process list and the state files before logging any result. |
| **A pass that arrived too quickly.** A nightly check “completed” 17 sections in one second and logged *ok*: its guard had seen its own wrapper and refused. | Know roughly how long the real work takes; a result far faster than that is a failure until proven otherwise. |
| **Receipts with no content.** “Backup ok” says nothing. | Receipts carry counts – files backed up, archive size, snapshots retained – so an empty run is visible in the line itself. |

### One step must not starve the night

One overnight step – a pass over every call-out in a long video series – ran for about 10 hours: started at 01:22, still going at 11:13. The steps after it never ran, the run never reached its clean exit, and the marker went stale. The step’s workload was finished, so it is now **parked** behind a one-line switch in the runner rather than deleted. Two rules came out of it: park a workload when its project is finished, and give every step a time cap so one can’t eat the window. The first is done; per-step time caps are still **Planned**.

---

## 6. Unverifiable is not missing

The agent’s shell runs sandboxed. In a cloud-synced folder it hits “Operation not permitted” on every path – and `find <folder> 2>/dev/null | wc -l` then prints **0**, which reads as “the folder is empty”. It isn’t; the error was thrown away. **Never discard error output when counting in a protected folder.**

The same distinction decided a repair job on broken references in editing projects. Of 1,346 broken links, 11 were genuinely repairable. The rest were reported in three separate buckets, never added together:

| Bucket | Count | Meaning |
|---|---|---|
| Missing | 1,046 | Genuinely not on this Mac any more (raw shoot folders archived after delivery). |
| Unverifiable | 284 | In a folder the agent’s process cannot read. Not proven missing – merely unchecked. |
| Unmounted | 5 | On an external or network volume that wasn’t mounted. |

For the unverifiable bucket the agent wrote a read-only script for me to run in my own Terminal, which does have access; whatever it finds becomes a second repair pass. Reporting all 1,335 as “missing” would have been wrong for more than a fifth of them.

The same applies to camera cards and network shares: a card re-inserted can mount twice, as a ghost duplicate under a second name. Check both before declaring a backup complete.

---

## 7. Small traps worth knowing

- **A narrow no-break space in screen-recording names.** macOS puts a narrow no-break space (U+202F) before “PM” in screen-recording filenames. A typed path with an ordinary space never matches. Glob for the file; don’t type its name.
- **PowerPoint’s AppleScript export fails silently; Keynote’s works.** To turn a deck into slide images by script, open it in Keynote and `export … as slide images`.
- **Protected folders can be blocked per process.** If the agent can’t read a file in Downloads or a synced folder, ask the human to drag it into the workspace rather than widening permissions.
- **Describe images locally before loading pixels.** Screenshots pasted into a chat are the biggest token drain. [`sa_peek.py`](../tools/sa_peek.py) describes an image with the local model and the agent reads the text; pixels are loaded only when pixel-exact detail matters.
- **Free cloud voice is for drafts.** It’s free and fast for timing a cut, but it sends the script to an online service.

---

## Maturity

Labels follow the [status labels in the README](../README.md#status-labels).

| Piece | Status | Code |
|---|---|---|
| Two-profile visual memory (small model by day, larger overnight; creative-app pause; unload) | **Built, in use** | [`sa_visualmem.py`](../tools/sa_visualmem.py) |
| Local image and video descriptions for the agent | **Built, in use** | [`sa_peek.py`](../tools/sa_peek.py), [`sa_see.py`](../tools/sa_see.py) |
| Local guardrail check on generated stills | **Built** – tested live; shortlists for a person, signs nothing off | [`sa_qa.py`](../tools/sa_qa.py) |
| Local English–Arabic subtitle drafts | **Built, in use** – drafts only, always reviewed | [`sa_translate.py`](../tools/sa_translate.py) |
| One heavy batch at a time | **Built, in use** | [`sa_guard.py`](../tools/sa_guard.py) |
| Overnight runner through a frozen applet, with resume ledger | **Built, in use** – unblocked in mid-September 2026; nightly logs run to October | [`sa_nightly.sh`](../tools/sa_nightly.sh) |
| 07:00 dead-man check | **Built** – currently refused by macOS (last exit 126) after the permissions regression; it needs the same applet treatment as the runner | [`sa_nightcheck.sh`](../tools/sa_nightcheck.sh) |
| Heartbeat pairing and last-success checks | **Built, in use** | [`sa_doctor.py`](../tools/sa_doctor.py) |
| A direct check that Full Disk Access is still granted | **Planned** – today a lost grant shows up only indirectly, as failing jobs in the health check | – |
| Per-step time caps in the overnight runner | **Planned** | – |

**Related:**

- [running-two-ai-agents.md](running-two-ai-agents.md) – the division of labour between the coding agents, the local models and scripts
- [learning-from-mistakes.md](learning-from-mistakes.md) – “silence mistaken for success” as a recurring pattern, and how it recurred
- [ai-engineering-method.md](ai-engineering-method.md) – the overnight runner and the guard rails for automation
- [why-ai-agents-forget.md](why-ai-agents-forget.md) – silent failures in another agent set-up’s memory
- [security-and-data-policy.md](security-and-data-policy.md) – what may leave the machine, and what never does
