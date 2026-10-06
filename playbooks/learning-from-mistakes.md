# Learning from mistakes

In August 2026 I had the agents audit every mistake on record – 76 of them since May – and group them into 16 patterns. The finding that changed how I work: no written rule had ever stopped a repeat; only code had. This playbook covers that post-mortem, the guards that turned out not to exist, and the ledger that keeps every escaped defect open until a check catches it.

The code that came out of it: [`sa_guard.py`](../tools/sa_guard.py) (the pre-flight gate and approved-freeze list), [`sa_finaldiff.py`](../tools/sa_finaldiff.py) (my final edit against the machine build), [`sa_occlude.py`](../tools/sa_occlude.py) (is a call-out covering what it points at?) and [`sa_finalcheck.py`](../tools/sa_finalcheck.py) (the exported file against the approved script). The agent workflows that mined the record are [`../workflows/mistake-mining.js`](../workflows/mistake-mining.js) and [`../workflows/fix-log-mining.js`](../workflows/fix-log-mining.js); blank formats for your own fix log and ledger are in [`templates/fix_log_entry.md`](templates/fix_log_entry.md); the distilled lessons travel with the kit in [`HARD_WON_LESSONS.md`](../workspace-kit/Reference/HARD_WON_LESSONS.md).

---

## 1. The post-mortem (9 August 2026)

| Measure | Count |
|---|---|
| Mistakes on record, May to 9 August 2026 | 76 |
| …with a systemic guard (code that runs and refuses) | 31 |
| …noted only (in memory files, playbooks or hooks, with nothing enforcing them) | 45 |
| Recurring patterns | 16 |
| …fully guarded | 1 |
| …partially guarded (only at the exact spot that had already burned) | 6 |
| …prose only | 9 |

The one clean finding: **no written rule – injected into every turn, logged, or restated – had ever stopped a repeat. Only code had.** Every prose-only pattern had to be treated as able to come back silently the next day.

---

## 2. The sixteen patterns

Every pattern was checked against the raw list and has real, dated instances. Guard status is as it stood on 9 August, except where a later recurrence is noted.

| # | Pattern | What it looked like | Guard at the time |
|---|---|---|---|
| 1 | Verified the parameter, not the picture | “Done” declared without opening the output: an event intro presented unviewed; a web tool “fixed” with no browser check; an audio fix shipped unheard; 15 cloned editing projects reported as successful while opening on the donor timeline. | Partial – training-video pipeline only |
| 2 | The lesson was on file and unread | Known traps walked into again: a scheduler trap repeated; a sidebar fault shipped the day after it was reported; the one-heavy-batch-at-a-time rule broken; check-before-building skipped. | None |
| 3 | Patched the copy, not the master | A banned-imagery rule logged while the contradicting prompt text stayed live; a caption function patched inside 11 separate builds instead of at source; a fix not carried to a shipped sibling video. | Partial |
| 4 | Measured yesterday’s build, not today’s truth | A search index two days stale; the active-session pointer naming dead sessions, twice; a coverage check blind to hand-typed labels; a script file contradicting what had shipped. | Partial |
| 5 | Wrote before reading | Working lip-synced audio padded with no before-and-after comparison; a sign-off appended to videos that already had one; a correct call-out rewritten from memory. | Partial – sign-offs only |
| 6 | The sample crowned as the census | Four photos per folder produced a back-to-front reshoot plan; a profile of how I work built from three weeks of a newest-first file; one observed zoom written up as a style rule. | None |
| 7 | Tokens over intent | “16x9” taken literally midway through a vertical project; “skeleton” delivered as a voice-over-only minimum; feedback over-corrected to the opposite extreme. | The 9:16 case only |
| 8 | “Improved” the approved | Passes added to a locked prompt; a near-edit of a finished training video. | None |
| 9 | Theory before the error message | “Fixed” claimed repeatedly on an undiagnosed three-layer fault; three confident wrong root causes in one day while the accurate error message sat dismissed. | None in code |
| 10 | Happy path shipped, unhappy path destructive | A parser that overwrote instead of merging; an `ffmpeg -shortest` flag truncating 13 videos; a caption writer that touched every timeline in a project. | Mixed |
| 11 | Silence mistaken for success | A backup dead for 24 days; scheduled jobs stamping “ran” with nothing produced. In September: an operating-system permission regression that silently broke three scheduled jobs, and one overnight step that ran for about 10 hours and starved every step after it. | **Systemic** – heartbeats plus health-check cross-checks. Recurred once in September; caught by the receipt check (the health check reading each job’s heartbeat pair and last-success marker), not by anyone noticing. See [local-ai-on-a-mac.md](local-ai-on-a-mac.md). |
| 12 | A limit invented for one job enforced as another’s law | A 2.20× speed cap never validated against my edits; a 46-character line-break guide reused as a defect threshold. | Partial – those two constants now measured |
| 13 | Generate first; reference and budget never | Four presenter batches generated before any approved reference existed; no budget check before paid generation; hours of compute against 15 minutes of my time. | None |
| 14 | The brief was in writing and still missed | The voice-over-only skeleton; a full-body requirement swapped for a cutaway; flat MP4s delivered after editable drafts were asked for twice. | None |
| 15 | Ask a model for a real thing, get its memory of it | Cars drifting towards real makes; details of a real product invented. | Prose only |
| 16 | Rebuilt what the machine already had | A new server built while 70-plus tools sat on disk; a near-rebuild of an existing click detector. | None |

---

## 3. The five missing guards it ranked – and what happened

The post-mortem ranked the missing guards by what their pattern had cost.

| Rank | Missing guard | Pattern | What happened |
|---|---|---|---|
| 1 | A pre-flight rule gate – detect the task, run the coded checks that apply, refuse on failure | 2 | **Built the same day** in [`sa_guard.py`](../tools/sa_guard.py): the editing app must be closed, one heavy local batch at a time, and the tool catalogue is searched before a new tool is written. Partial – any rule without a coded check is still exposed, so each new rule is meant to land in the gate, not in prose. |
| 2 | A consumer-path “done” check – render it, open it, play it | 1 | Open at the time. For training videos, a later check ([`sa_finalcheck.py`](../tools/sa_finalcheck.py), September 2026) reads the exported MP4 that will actually be sent and compares what is spoken in it with the approved script. That covers one kind of output, not the general wrapper the post-mortem asked for. |
| 3 | A paid-generation gate – approved reference on file, cost per batch, comparison with doing it by hand | 13 | Open at the time, and still not built. Until it is, the September billing traps – a timed-out job is still charged, job lists show only completed jobs – are written up in the billing-trap section of [ai-video-and-image-generation.md](ai-video-and-image-generation.md). |
| 4 | An approved-freeze list that write and grade tools refuse to touch | 8 | **Built the same day** in [`sa_guard.py`](../tools/sa_guard.py). Pattern 8 moved to systemically guarded, proven by its self-test and by a live refusal against a finished video. |
| 5 | A build-versus-brief diff – requirements ticked line by line before presenting | 14 | Open at the time. |

### What genuinely got fixed

Every fix that held is code: cloud-synced folders physically denied; daytime heavy batches forced into a background profile; content-trimming by the dubbing cutter asserted in its self-test; tripled caption shadows caught by a self-check and an export rule; the edit watcher no longer logging its own writes (fixed by construction); silent automation caught by a heartbeat and the health check; briefing crashes stopped by a size budget; parser overwrites replaced by merging; `-shortest` truncation stopped by audio padding and duration asserts; donor-timeline clones caught by a verify step. As of the post-mortem, none had recurred since its guard landed. Not one of them is a sentence in a file.

---

## 4. The fix log: suspect the check first

The fix log (12 August 2026) is the front door for anything that looks wrong. Its first rule: **when a check reports something wrong across many items, suspect the check.** On 12 August, six of the eight faults found were the measuring tool accusing finished work. The corollary: if your fix doesn’t fail against the old code in a reproduction, your diagnosis is wrong – not your reproduction.

Almost every failure falls into one of eight classes. Recognising the class is usually faster than recognising the bug.

| Class | Example | Rule |
|---|---|---|
| The measurement lied | Every overlay reported “3–13× too small”, because the measuring code forgot the editor fits an image to the canvas before applying its own scale. A vision check returned nothing for every image because an output limit cut the reply short. | Check the instrument. Reproduce one case by hand first. |
| A check keyed to a *name* accused finished work | “No captions” reported on fully captioned videos, because I had renamed the track. | Key every check to content. Track names are mine to change. |
| A tool damaged finished work | An incremental overlay run replaced a whole track and destroyed 15 verified layers – and its check passed, because it only counted what it had just written. | Verify against the source of truth. Back up before every write. Never write while the editor is open. Never touch a project on the done list. |
| A false learning | The diff tool credited me with labels the build had written itself; the build’s own end-hold frame counted as a call-out I had added – a phantom +1 on every video. | Anything that learns from a comparison must know exactly what it produced itself. |
| A guard that could see itself | The nightly check refused all 17 sections because it detected its own keep-awake wrapper – and still logged *ok*. | Match the process that holds the contended resource, never the tool’s own name. |
| Silent failure | A step marked *ok* because a wrapper loop exited cleanly; a summary that searched for the word “WRONG” recorded a refusal as clean. | Three outcomes – *ok*, *wrong*, *unknown* – and unknown is never a pass. |
| A stale artefact | A reference track sized to an edit I then shortened; a duration header left behind after content was removed, which exported as black. | Re-derive or re-check on use. Never trust a stored size. |
| A pattern from one observation | One freeze frame landing on a role change looked like a rule. Measured across eight finished videos, it happened 41% of the time. | One video suggests; the full set decides. Change a default at three recurrences, with the evidence in the code comment. |

### Symptom index

The fix log is indexed by what you *see*, not by the cause – the cause is usually not what it first appears to be. These are the generic rows; the right-hand column names the guard that now catches each one.

| What you see | Likely cause | Where the guard lives |
|---|---|---|
| A batch reports every item as broken | The measurement, not the items | No tool: verify one case by hand before believing the batch. |
| “No captions” on a video you captioned | A check keyed to a track *name* | [`sa_exportcheck.py`](../tools/sa_exportcheck.py) – counts caption content, not track names. |
| “No title card” on a finished video | Title lines moved off the track the check expected | [`sa_exportcheck.py`](../tools/sa_exportcheck.py) – recognises the title by its text size, wherever it sits. |
| “Would thank the viewer twice” | Extra tracks with a sign-off-like name were carrying other labels | [`sa_exportcheck.py`](../tools/sa_exportcheck.py) – counts the spoken words, not the tracks. |
| The diff says I added a box I didn’t | The build’s own still frame, on an unnamed track | [`sa_finaldiff.py`](../tools/sa_finaldiff.py) – recognises the build’s own stills before crediting me. |
| An overnight job finished suspiciously fast | It refused itself and logged *ok* | [`sa_guard.py`](../tools/sa_guard.py) and [`sa_boxcheck_all.sh`](../tools/sa_boxcheck_all.sh) – the guard matches the contended process, never its own wrapper. |
| A menu-bar indicator stuck on one state | Its refresh timer died on an exception | [`sa_watchbar.py`](../tools/sa_watchbar.py) – the refresh step catches everything, so one error can’t stop the timer. |
| An export longer than the video | A stale duration header, or a hidden track | [`sa_exportcheck.py`](../tools/sa_exportcheck.py) – the reference-track check. |
| Black at the end of an export | The duration header claims more than the content reaches | Recompute the duration on any shortening; never trust a stored size. |
| Overlays render far too small | The measuring code applied the canvas fit before the clip’s own scale | The measurement’s scale maths: canvas fit first, then the editor’s scale. |
| A stretch of recording looks “dead” | A scan too coarse to see small movement | Re-scan at 0.5-second steps before trimming anything. |
| Picture still moving under the sign-off | A paced segment longer than about 30 seconds of source | [`sa_tailcheck.py`](../tools/sa_tailcheck.py) – does the picture outlive the narration? |
| Voice drifting ahead of the picture | The same cause, accumulated over the video | [`sa_tailcheck.py`](../tools/sa_tailcheck.py), then re-anchor the lines to the clicks. |
| A step happens with no marking | The action was buried in a compound line, or never made the step list | [`sa_actioncheck.py`](../tools/sa_actioncheck.py) – one marking per instructed action, not per sentence. |
| Two call-outs on screen at once | A box not trimmed where the next one begins | Trim the box where the next one begins. It is rare in my own edits – 10% of 95 boxes measured. |

To add your own rows, use the blank fix-log entry in [`templates/fix_log_entry.md`](templates/fix_log_entry.md): symptom first, class second, and the guard as code with evidence that it fails on the old case.

### Per-project fault files

On 12 August the agents built a fault file for each project folder from the worklog, my feedback, the memory store, the project files and the git history: **21 files, 106 faults.** They surfaced things nobody had known – the same project living in two folders; a product’s outdated name still baked into one project’s subtitles and title cards; a folder holding the rejected render rather than the approved one; two “approved” workflows contradicting each other on whether to grade or upscale first. The rule since then: a project earns a fault file the first time something goes wrong, and the entry is written the same day.

---

## 5. Guards claimed versus guards that exist

On 12 August 2026 the agents checked every protection the workspace claimed to have by reading the code, not the documentation. Six were written up as protections and did not exist:

| Claimed guard | Reality |
|---|---|
| An assertion that captioning leaves untouched timelines byte-identical | Never existed – a one-off manual check, written up as if it were standing. The caption writer still wrote every timeline in a project; only the done-list refusal stood in the way. |
| A blocker for duplicate or hidden caption tracks in the export check | Never written. Hidden caption tracks counted as normal captions. |
| An “editor is open” check in the relink tool | Absent – present in other writers, not this one. |
| A check that cloned timelines no longer point at their donor | Absent from the verify step. |
| A monthly sweep for patched-the-copy mistakes | Nothing ran it. |
| The 9:16 aspect-ratio gate before generation | Prose only – a hard rule in the instruction file with no coded enforcement anywhere. |

Five more were real but weak: a verifier credited with guarding six separate defects that its own self-test never called; a data-loss fix with no test; a timestamp fix whose only assertion also passed on the old, buggy code; a hard-coded list of build-owned tracks with no test, so the next unlisted track would bring back a false learning; and a “done” record that didn’t require its evidence field.

Believing in a guard that isn’t there is worse than knowing nothing, because work gets built on top of a safety net that doesn’t exist.

---

## 6. The escaped-defect ledger

When I finish a video, [`sa_finaldiff.py`](../tools/sa_finaldiff.py) compares my final edit with the last purely machine-built version. Every difference is a specification: something the pipeline should have done and didn’t. Any difference that got past a passing check, or a step the build missed entirely, goes into the ledger. A blank ledger entry is in [`templates/fix_log_entry.md`](templates/fix_log_entry.md).

The rules:

- Each entry escaped **once**.
- An entry closes only when a check exists that **fails on its recorded case**.
- Entries are never deleted, only marked closed.

What it recorded from 9 to 12 August 2026, across 11 finished training videos:

| Entry type | Count |
|---|---|
| A call-out passed verification, then I moved it | 40 |
| A step the build missed, which I added by hand | 10 |
| Timing – in one video I retimed 3 of 4 boxes (one 2.4 s late, two early by 2.7 s and 1.0 s) | 1 |
| Structural gaps found by the residue study below | 3 |
| **Open entries** | **54** |
| Withdrawn as a false reading | 1 (covering two findings) |

The withdrawn entry is a lesson of its own: its two “added by hand” findings were the build’s own role labels. The diff tool hadn’t treated that track as machine-made, so it read the build’s output as my work. The tool was fixed and the entry withdrawn.

### The residue study (12 August, overnight)

Fifty-three of my call-out moves were judged frame by frame. The main causes (not a complete breakdown):

- **27 of 53** existed to uncover something the graphic was sitting on. Nothing in the pipeline checked for that – the box check only asked whether the box was on the right element.
- **7** traded a correct box for a readable screen, because the label chip and the box were baked into one image.
- **9** were scroll or retiming fixes: the build measured the screen at build time, but the viewer sees the edited timeline. Four boxes marked correct were pixel-perfect when measured and wrong in the cut.
- **7 of 53** were genuinely unexplained (4 unclear, 3 cosmetic).

The response was [`sa_occlude.py`](../tools/sa_occlude.py): two local pixel tests on the frame that actually plays – is the box’s border drawn across text, and is the label chip sitting on content? **Built.** The ledger entry stays open until that check is shown to fail on the recorded case; at the ledger’s last update, no entry had yet been marked closed.

---

## 7. Two data-handling lessons

Not every mistake is in video. Two came from importing spreadsheet exports into a small tracker, and both apply to any data pipeline.

**A date that silently fails to parse looks like data that ends early.** One export wrote its dates as “07 Sept 2026” – a four-letter month abbreviation that Python’s `strptime` `%b` will not accept. About 7% of the rows failed to parse without raising an error, and because the failures were all from the newest month, the data looked as if it simply stopped weeks before it really did. Nothing looked broken; the latest date just looked a little early. The fix normalises the abbreviation before parsing and returns *nothing*, loudly, for anything still unparseable – and the lasting rule is to compare the parsed-row count with the total row count on every import, and never to accept the newest date as proof that the data is complete.

**Merge, never clobber.** An earlier version of the same importer rebuilt its file from the latest export alone, which would have silently deleted every record that had been added by hand. The importer now starts from the current file as the truth, lets the official export win by record id, always keeps manually added rows, merges any files dropped into an inbox folder, and only then moves those inbox files to a done folder – so a crash halfway leaves them in place to be merged again. An empty or failed parse never overwrites the file at all. The same rule – never overwrite a data file from a partial source – now applies to every tool that writes one.

---

## 8. What I’d pass on

- A rule in a prompt file is a hope. A check that refuses is a guard.
- Read the code, not the documentation, to find out what actually protects you.
- Three outcomes – ok, wrong, unknown. Unknown is never a pass.
- When a batch says everything is broken, check one case by hand before believing it.
- Log the fault the day it happens. A fix log written later is written from memory, and memory is what it exists to replace.
- Your own final edit is the best specification your tools will ever get.
- Compare parsed rows with total rows on every import. The newest date is not proof of completeness.

---

## How the record was mined

Neither the post-mortem nor the fix log was written from memory; both were mined from the written record by agent workflows I ran, and both workflows are published.

- **Section 1’s post-mortem** ran as [`../workflows/mistake-mining.js`](../workflows/mistake-mining.js). Readers each excavated one era of the record, oldest material first, and returned every mistake in a fixed shape: what happened, the real root cause, the cost, and whether a coded guard exists today. A pattern stage then grouped them, counting a pattern only when it had at least two instances from different months or projects. A final auditor checked each pattern against the raw list and cut any with fabricated instances before writing the ranking.
- **Section 4’s fix log** ran as [`../workflows/fix-log-mining.js`](../workflows/fix-log-mining.js). Parallel miners read the traps file, the mistake patterns, the escaped-defect ledger, the recent worklog and the dated failure comments in the tools themselves. A second phase then opened each named tool and checked whether every claimed guard really exists in the code and in its self-test – which is how the “claimed but absent” guards in section 5 were found.

The lessons that generalise beyond my own work are distilled in [Part 3 of `HARD_WON_LESSONS.md`](../workspace-kit/Reference/HARD_WON_LESSONS.md#part-3--lessons-this-system-learned-by-getting-it-wrong) in the workspace kit.

---

## Maturity

Labels follow the [status labels in the README](../README.md#status-labels). These guards protect my own workspace, so “Built, in use” is the honest label even where the work they check was delivered.

| Piece | Status | Code |
|---|---|---|
| Mistake-pattern post-mortem | **Built** – run once, completed 9 August 2026; the ranking it produced still drives which guards get built | [`../workflows/mistake-mining.js`](../workflows/mistake-mining.js) |
| Fix log and its guard check | **Built** – run once, 12 August 2026; the fix log it produced is in use | [`../workflows/fix-log-mining.js`](../workflows/fix-log-mining.js) |
| Pre-flight gate and approved-freeze list | **Built, in use** | [`sa_guard.py`](../tools/sa_guard.py) |
| Final-edit diff | **Built, in use** | [`sa_finaldiff.py`](../tools/sa_finaldiff.py) |
| Escaped-defect ledger | **Built, in use** – 54 open entries at its last update, none yet closed | [`templates/fix_log_entry.md`](templates/fix_log_entry.md) (blank format) |
| Occlusion check | **Built** | [`sa_occlude.py`](../tools/sa_occlude.py) |
| Exported-video check for training videos | **Built, in use** | [`sa_finalcheck.py`](../tools/sa_finalcheck.py) |
| Paid-generation gate; build-versus-brief diff | **Planned** – ranked by the post-mortem; not built when its guard log was written | – |

**Related:**

- [ai-engineering-method.md](ai-engineering-method.md) – the diagnosis loop and the rules these mistakes produced
- [local-ai-on-a-mac.md](local-ai-on-a-mac.md) – the silent-failure traps in scheduled jobs and local models
- [orchestrating-agent-fleets.md](orchestrating-agent-fleets.md) – the mining and verification fleets in general
- [running-two-ai-agents.md](running-two-ai-agents.md) – where corrections are logged so the other agent inherits them
- [security-and-data-policy.md](security-and-data-policy.md) – fail-closed gates, and what a leak scan misses
- [templates/fix_log_entry.md](templates/fix_log_entry.md) – blank fix-log and ledger entries
