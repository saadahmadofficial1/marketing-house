# Session handoff: how two AI agents pick up each other’s work

I switch between two AI coding agents – Claude Code and Codex – usually because one has hit its usage limit halfway through a task. Neither can see the other’s chat. This page is the full working of the handoff that lets the second agent carry on without me re-explaining anything: the session folder on disk, the one schema both agents write to, the checkpoints and the brief that make context compaction survivable, the open-threads report, and the checks that catch a stale or broken handoff. I designed the rules – most of them exist because something went wrong first – and the code was written by AI coding agents under my direction.

**Status: Built, in use** – every day since June 2026 (see the [status labels](../README.md#status-labels)). By 6 October 2026 there were 61 dated session folders, the first from 25 June, holding 800 log lines – 240 of them written by Codex.

The overview of the whole two-agent set-up, including the long-term memory, is [running-two-ai-agents.md](running-two-ai-agents.md). This page goes deeper on the handoff alone.

| Tool | Job |
|---|---|
| [`sa_session.py`](../tools/sa_session.py) | Creates a session, writes `state.json` atomically to one schema, appends log lines, validates a folder before a resume, migrates old shapes |
| [`sa_checkpoint.py`](../tools/sa_checkpoint.py) | Asks for a written checkpoint each time the transcript grows by about a tenth of the context window |
| [`sa_compact_brief.sh`](../tools/sa_compact_brief.sh) | Re-reads the ground truth from disk the moment a conversation is compacted |
| [`sa_threads.py`](../tools/sa_threads.py) | Lists every unfinished thread across all sessions, not just the active one |
| [`sa_doctor.py`](../tools/sa_doctor.py) with [`sa_loop.py`](../tools/sa_loop.py) | The start-of-session health check, including the age and validity of the active handoff |

All five use the Python standard library (plus `git` for the repository scan); nothing to install. Each script runs locally and uploads nothing.

**Contents:** [1 The problem](#1-the-problem) · [2 The folder](#2-the-folder) · [3 Step 0](#3-step-0-auto-resume) · [4 The three files](#4-the-three-files) · [5 One contract](#5-one-contract-written-atomically) · [6 Safety rules](#6-the-safety-rules-and-what-enforces-each) · [7 Checkpoints](#7-checkpoints-before-compaction) · [8 The compact brief](#8-the-compact-brief) · [9 Open threads](#9-open-threads) · [10 The provenance marker](#10-the-provenance-marker) · [11 Catching a stale handoff](#11-catching-a-stale-handoff) · [12 What went wrong first](#12-what-went-wrong-before-the-rules) · [13 Adopting it](#13-adopting-it) · [14 Maturity and known gaps](#14-maturity-and-known-gaps)

---

## 1. The problem

Work gets lost in four ways when AI agents are your main collaborators:

1. **Usage limits hit mid-task.** I switch from Claude to Codex, or back, with a half-finished job. Without a handoff I would have to re-explain the brief, every decision made so far and the state of every file.
2. **Context compaction.** When a conversation fills its context window it is summarised, and a summary is lossy by nature. A rule I stated in two plain sentences can vanish while pages of tool output survive.
3. **Two different products.** Claude Code and Codex share nothing – no memory, no chat history, no instruction file. A chat window can’t hand work to a different tool.
4. **Tomorrow.** Even with one agent, the next morning’s session starts cold.

The answer to all four is the same: **the chat is disposable; the state lives on disk**, in plain files any agent can read. No database, no server, no cloud account – a folder and a protocol both agents follow.

---

## 2. The folder

```
Sessions/
├── LATEST.txt                  the name of the active session folder – one line
├── README.md                   the protocol, so any agent knows the rules
├── OPEN_THREADS.md             every unfinished thread (sa_threads.py --write)
├── _nightly/attention.md       anything the overnight checks want me to see
└── 2026-03-12_product-reel-30s/
    ├── state.json              the whiteboard: current truth, edited in place
    ├── log.jsonl               the logbook: one line per change, append-only
    └── checkpoints/
        ├── 01.md               decisions written down before the context filled
        └── _state.json         transcript size when the last checkpoint was taken
```

One folder per task, and – since 8 July 2026 – at least one per working day. More work means more folders, never a bigger, more fragile file.

---

## 3. Step 0: auto-resume

Both agents’ instruction files – `CLAUDE.md` for Claude Code, `AGENTS.md` for Codex – open with the same step, ahead of everything else:

> 1. Read `Sessions/LATEST.txt` → the active session folder (fallback: the newest `Sessions/<date>_<slug>/`).
> 2. Read its `state.json` (live truth) and the tail of `log.jsonl`. Say one line – “Resuming X – last step Y, next Z” – and continue. Run the health check too: a red light there outranks the plan. Read the overnight attention note if there is one.
> 3. As you work, keep `state.json` current in real time and append one line per change to `log.jsonl`, tagged with your agent name. New session → update `LATEST.txt`.
> 4. **Daily record:** every working day gets its own folder, created at the first task of the day and updated after every major step – not at the end of the session, and not only when asked. If `LATEST.txt` points at yesterday, start today’s folder.
>
> Treat the task as fresh only if no recent session folder exists.

Codex’s copy adds one framing line: if I am talking to it, Claude has almost certainly hit its limit and I have switched mid-task, so it must not ask what we are working on. When in doubt, it reads the latest state first.

Three details matter more than they look:

- **The resume is said out loud.** “Resuming the product reel – last step was regenerating lines 5 and 6, next is checking them against the cut.” I can correct a wrong resume in one word; a silent wrong resume costs an hour.
- **Both agents start lean, the same way.** Active session first, then the rules in their own instruction file, then targeted lookups in [the brain](the-brain.md) (the shared long-term memory) – never loading every memory file. An early audit found Codex had been told to load all of its memory files while Claude retrieved on demand; it wasted context and made the two agents behave differently ([section 12](#12-what-went-wrong-before-the-rules)).
- **Save points, not a diary.** A session file written at the end of the day is a diary; written after every step, it is a save point. Compaction can erase the chat at any moment, and the session files are the only memory the other agent ever sees.

---

## 4. The three files

The examples below are made up – a 30-second vertical product reel for a desk lamp – but the shapes are exactly what the tools write.

### `LATEST.txt` – the pointer

```
2026-03-12_product-reel-30s
```

One line: the folder name. One source of truth for “what is active”.

### `state.json` – the whiteboard

```json
{
  "session": "2026-03-12_product-reel-30s",
  "updated": "2026-03-12T16:42:05+04:00",
  "agent": "codex",
  "purpose": "30-second vertical product reel for a new desk lamp",
  "status": "rough cut built; voice-over 4 of 6 lines approved",
  "last_action": "regenerated lines 5 and 6 at speed 0.95 (done by codex)",
  "next": [
    "listen to lines 5 and 6 against the cut",
    "lock the music bed under the voice",
    "export review copy, 1080x1920"
  ],
  "extra": {
    "aspect_ratio": "9:16, verified before any generation",
    "deliverables": ["review MP4", "editable project"],
    "rules": ["no hands in generated shots", "no text, logos or people baked into AI clips"],
    "waiting_on": "approval of the hero shot"
  }
}
```

Current truth only. It is overwritten as things change; the history lives in the log.

### `log.jsonl` – the logbook

```
{"ts": "2026-03-12T09:05:11+04:00", "agent": "claude", "event": "session_created", "note": "30-second vertical product reel for a new desk lamp"}
{"ts": "2026-03-12T10:20:40+04:00", "agent": "claude", "event": "decision", "note": "hero shot opens on the switch-on, not the packshot"}
{"ts": "2026-03-12T11:02:13+04:00", "agent": "claude", "event": "correction", "note": "captions sat below the safe zone; moved up"}
{"ts": "2026-03-12T13:30:57+04:00", "agent": "codex", "event": "resume", "note": "picked up from state: rough cut built, lines 5-6 pending (done by codex)"}
{"ts": "2026-03-12T16:42:05+04:00", "agent": "codex", "event": "vo_generated", "note": "lines 5 and 6 regenerated at speed 0.95 (done by codex)"}
```

One JSON object per line, appended and never edited. The fourth line is the handoff itself: a different agent, resuming from the state file.

### Why JSON, and why two files

- **Two questions, two rates of change.** `state.json` answers “where are we now?”; `log.jsonl` answers “how did we get here, and who did it?”.
- **JSON, not prose.** Two different agents must read the state identically every time. “Moved the music down a bit, I think it’s approved” gets misread; `"status": "approved"` doesn’t.
- **Not a semantic search.** “What is the current status?” needs the exact truth, not the closest match. The brain holds facts that outlive a task; the session folder holds the task.
- **JSON Lines for the log**, because a line can be added without reading or rewriting the rest of the file.

---

## 5. One contract, written atomically

The contract is simple: every `state.json` has exactly these eight keys, and every log line exactly these four. Both agents are meant to call [`sa_session.py`](../tools/sa_session.py) instead of hand-writing JSON.

| `state.json` key | Meaning |
|---|---|
| `session` | The folder name |
| `updated` | ISO 8601 timestamp with time zone |
| `agent` | Who wrote it last: `claude`, `codex` or me |
| `purpose` | One line: what this session is for |
| `status` | Short current status |
| `last_action` | The most recent completed step |
| `next` | List of next steps, in order |
| `extra` | Everything session-specific – deliverables, rules, learnings, what we’re waiting on |

A log line is `{"ts", "agent", "event", "note"}`, with `event` a short snake_case slug such as `decision`, `correction` or `vo_generated`.

```bash
sa_session.py new product-reel-30s --agent claude --purpose "30-second vertical product reel"
sa_session.py update --agent codex --status "rough cut built" \
    --last-action "regenerated lines 5 and 6 (done by codex)" --next "check lines 5-6;lock music;export"
sa_session.py log codex vo_generated "lines 5 and 6 regenerated at speed 0.95 (done by codex)"
sa_session.py check               # exit 0 = safe to resume; exit 1 = fix first
sa_session.py migrate             # bring every old folder to the contract, originals kept
sa_session.py repair-active-log   # normalise only the live session's log
sa_session.py --test              # self-checks
```

How each command behaves:

- **`new`** puts today’s date in front of the slug, writes a contract-shaped `state.json`, logs `session_created`, then points `LATEST.txt` at the new folder. Pass a bare slug: two of my folders ended up with the date twice because a dated slug was passed in.
- **`update`** reads whatever is in the file, brings it to the contract first, then sets the fields given, stamps `agent` and `updated`, and splits `--next` on semicolons. The command line sets the headline fields (`purpose`, `status`, `last_action`, `next`); any other field passed from Python lands under `extra`, and existing `extra` content is carried over untouched.
- **`log`** appends one line in one write. It never reads or rewrites the history.
- **`check`** is the resume validator – see [section 11](#11-catching-a-stale-handoff). Across 61 folders it runs in 0.03 seconds.

**The atomic write.** A crash halfway through writing must never leave half a JSON object, because the next resume would fail on it. The state is written to a temporary file in the same folder and then renamed over the original – a rename within one folder is all-or-nothing:

```python
def _atomic_write(path, text):
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".tmp_", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)
```

**Migration without loss.** `migrate` maps every historical shape onto the contract and drops nothing:

| Old key or case | Becomes |
|---|---|
| `project`, `active_project` | `purpose` |
| `current_status`, `current_action` | `status` |
| `owner` | `agent` (defaults to `claude` if neither exists) |
| `next_step`, `pending` | `next` – a single string becomes a one-item list; if `next` and `pending` both exist, `pending` is kept under `extra` |
| Any other key | Moved under `extra`, unchanged |
| No `session` | The folder name |
| No `updated` | The time of the migration |
| Log line with no `event` | `event` set to `note` |
| Log line whose text was put in `event`, with no `note` | The text becomes the `note`; `event` becomes `legacy_note` |

The originals are saved once as `state.json.pre_canonical` and `log.jsonl.pre_canonical`, and a second run never overwrites them. A made-up folder in the old style:

```json
{"active_project": "Event photo cull", "current_status": "212 of 640 selected",
 "pending": ["client pick of hero frames"], "schedule": {"fri": "deliver selects"}}
```

comes out of `migrate` as:

```json
{
  "session": "2026-10-05_event-photo-cull",
  "updated": "2026-10-06T12:45:07+04:00",
  "agent": "claude",
  "purpose": "Event photo cull",
  "status": "212 of 640 selected",
  "last_action": "",
  "next": ["client pick of hero frames"],
  "extra": {"schedule": {"fri": "deliver selects"}}
}
```

Timestamps are written in UTC+4, my time zone; it is one constant at the top of the script.

---

## 6. The safety rules, and what enforces each

These come from the protocol in the live `Sessions/README.md`, generalised. The right-hand column is the honest part: some rules are enforced by code, some only by an instruction.

| # | Rule | Why | Enforced by |
|---|---|---|---|
| 1 | **One active agent at a time.** Don’t write here unless you are the agent I’m talking to. | No simultaneous writes, so no lock is needed. | Me. Nothing in code stops two agents writing at once. |
| 2 | **The log is append-only.** Add lines; never edit, reorder or delete old ones. | An append can’t corrupt history. | `log` only appends; `migrate` saves the original before it normalises anything. |
| 3 | **Overwrite the value, keep the shape.** No renamed or invented top-level keys; a new kind of information goes under `extra`. | Every reader looks in the same place. | `update` re-shapes before writing; `check` and the health check flag missing keys. |
| 4 | **Validate before and after saving.** | One broken bracket breaks the next resume. | The atomic write; `check` parses the file. |
| 5 | **Tag every log line** with `ts`, `agent`, `event` and `note`. Keep it boring and consistent. | Any tool can read any session. | `log` writes all four; the health check counts rows that miss one. |
| 6 | **Never touch the other agent’s instruction file or memory folder.** The shared ground is `Sessions/` only. | Each agent’s behaviour stays its own. | Instruction only. |
| 7 | **New session: create the folder, then update `LATEST.txt`.** | The pointer never names a folder that doesn’t exist yet. | `new` does both, in that order; `check` flags a pointer to a missing folder. |
| 8 | **Codex marks what it adds with “(done by codex)”.** | Provenance survives compaction. | Instruction only – measured compliance in [section 10](#10-the-provenance-marker). |

The first version of rule 3 said new information should go under `notes` or `pending`; the contract folded both into the single `extra` bucket. The design principle holds either way: append-only history, a stable schema and one writer make the folder strong by construction. In practice, the rules enforced by code have held and the rules that are only instructions have drifted – [section 12](#12-what-went-wrong-before-the-rules) has the numbers.

---

## 7. Checkpoints before compaction

A summary written when the context is full has already lost what a summary written at a tenth of the way would have kept. So instead of relying on one compaction at the end, [`sa_checkpoint.py`](../tools/sa_checkpoint.py) asks for a checkpoint each time the conversation grows by about a tenth of the window – my rule of thumb is “every 100,000 tokens of a million”. It has been in use since 19 August 2026.

**The trigger.** Claude Code keeps each conversation’s transcript on disk as a JSON Lines file, and its size is a usable proxy for context consumed. On the day it was calibrated, 84 MB of transcript covered roughly one full context plus a compaction, so the step is set at **8 MB**. A hook runs `sa_checkpoint.py --due` on every turn; it prints nothing until the transcript has grown 8 MB since the last checkpoint, so a normal turn is unchanged.

**Why transcript size, and not an off-the-shelf tool.** Three open-source memory add-ons for Claude Code were reviewed the same day. None triggered on context growth: one checkpointed on lifecycle events, one on the volume of tool output, and one was a search index rather than a checkpointer. Two of the three could send content to an outside service, which my data policy doesn’t allow for client material. Triggering on tool output would also have been backwards: measured on the session that prompted this, **70% of the transcript was tool output and only 10% was my own words**. A tool that checkpoints on tool output checkpoints hardest on the noise and can sail past a turn where I correct a rule in two plain sentences.

**What happens when one is due.** Nothing is summarised automatically. The request lands in the agent’s context and the agent writes the checkpoint itself, while the detail is still in front of it. The request asks for only what a compaction would lose:

- decisions I made, and any rule or preference I stated;
- corrections to the agent, and what the correct behaviour is;
- things measured, with their numbers;
- what was delivered, and what is still owed.

It skips tool output, file listings and anything that can be re-read from disk. The agent then runs `sa_checkpoint.py --mark`, which records the transcript size and a counter in `checkpoints/_state.json`. Anything durable also goes to the brain: a checkpoint is for this session, the brain is for good. A made-up example:

```markdown
# Checkpoint 01 – product reel, after the first review
- Decision: open on the switch-on; the packshot moves to the last 3 seconds.
- Rule stated: captions never sit below the platform safe zone.
- Correction: I used the old accent colour; the brief has the new one.
- Measured: rough cut 31.4 s, so 1.4 s must go – trim the second product turn.
- Delivered: rough cut v1. Owed: voice-over lines 5–6, music bed, review export.
```

`--list` shows the checkpoints of the active session, and `--demo` proves the trigger arithmetic on a temporary folder (3 MB is not due, 9 MB is, and it never fires twice for the same growth). By 6 October there were 41 checkpoints across 23 sessions.

---

## 8. The compact brief

Compaction summarises the conversation, and a summary can drop details. [`sa_compact_brief.sh`](../tools/sa_compact_brief.sh) makes that survivable. It is wired to Claude Code’s session-start event for compaction, so the moment a compacted conversation resumes, the ground truth is re-read from disk and put into context. The summary becomes a convenience instead of a single point of failure – which only works because everything that matters was logged to files as it happened. It has been in use since 9 August 2026.

What it prints, in order, within a budget of about 90 lines:

| Section | Content |
|---|---|
| Active session | The first 1,800 characters of `state.json`, then the last three log lines (each cut to 260 characters) |
| Progress tracker | My own progress file for the current series of work (specific to my workspace) |
| Open threads | The first 46 lines of the [open-threads report](#9-open-threads) – every other unfinished thread, not just the active one |
| Checkpoints | Every checkpoint written during this session, up to 2,200 characters each – “prefer the checkpoint where they disagree, because it was written while the detail was still in front of me” |
| Health | The health check’s red lights only |
| Overnight | The last three lines of the overnight attention note |
| Known defects | The count of open gaps in the automated checkers |
| Standing pointers | Where full recall lives – the method notes, the mistake patterns, the debugging rules, the tool catalogue, a brain search – and the hard rules that must survive any summary |

It closes with the rule that matters most: **if the summary and this briefing disagree, the briefing wins; and if something is not there at all, say “I don’t have that” rather than reconstructing it from memory.**

Even with the brief in place, one failure got through. On 19 August, after a compaction, the agent re-typed a voice-over regeneration prompt from memory instead of reading the script’s line file. The wrong line was generated: one sentence played twice in the cut and the real line was missing. It was caught only by transcribing the finished render against the script. The brief can put the truth in front of an agent; it can’t make the agent read a file rather than trust its own recollection. The standing rule since: never compose a regeneration prompt from memory – read the line file.

---

## 9. Open threads

On 14 August I named two code repositories, and the workspace had never heard of either. The compact brief had recovered the active session in perfect detail and lost every other commitment. A better summary wasn’t the fix; never depending on one was. [`sa_threads.py`](../tools/sa_threads.py) walks the whole workspace and answers one question – what is still open?

| Source | What it reports |
|---|---|
| Sessions | Every `state.json` whose status doesn’t match *done, complete, delivered, finished, shipped, closed* or *archived* – or which still owes something under a field such as `next_step`, `blocking`, `remaining`, `open_questions` or a `waiting_on…` key. A debt keeps a thread open even when the status says delivered. |
| Code repositories | Every git checkout under the home folder (five levels deep, skipping system and package folders) touched in the last 45 days, with its remote, branch and number of uncommitted files. The scan gives up after 45 seconds rather than hang. |
| The brain | The six newest project entries, so long-running work is named. |

```bash
sa_threads.py           # digest: 8 sessions (3 owed lines each), 10 repositories
sa_threads.py --full    # everything, untruncated
sa_threads.py --write   # also save Sessions/OPEN_THREADS.md
sa_threads.py --demo    # self-check
```

Made-up output:

```
--- OPEN THREADS: 2 session(s) not closed ---
  [ 0d] 2026-03-12_product-reel-30s
        status: rough cut built; voice-over 4 of 6 lines approved
  [ 3d] 2026-03-09_event-photo-cull
        status: 212 of 640 selected
--- CODE REPOS touched in the last 45 days: 1 ---
  [ 2d] portfolio-site (main)  1 uncommitted
```

Two gaps turned up while I tested it on made-up folders for this page:

- **It doesn’t read the contract’s own fields.** Owed items are collected from the older top-level keys, not from `next` or `extra`. A contract-shaped session whose status says “delivered” but whose `next` still lists a step is treated as closed and drops out of the report – the very failure the report was built to stop.
- **“Completed” doesn’t count as done.** The pattern matches the whole word *complete*, so a session with the status “completed” stays listed. That errs on the safe side.

---

## 10. The provenance marker

Since 6 August 2026, everything Codex adds – a commitment, a state item, a log note, a handoff entry, a worktree summary, a memory record – carries the exact marker **(done by codex)**. Where the phrase would damage the output – source code, binary media, client-facing creative work – the matching session log or handoff entry carries it instead.

The reason is compaction. When Claude’s context is summarised, the summary can absorb Codex’s work as Claude’s own or lose track of who did what. A literal string in the files survives any summary, so Claude can keep account of Codex’s work accurately, and so can I.

Measured on 6 October: of Codex’s 99 log lines since the rule began, **94 carry the marker (95%)**; its 141 lines from before the rule carry none. The marker also shows where [rule 6](#6-the-safety-rules-and-what-enforces-each) has been bent: several sections of Claude’s instruction file carry it, so it is visible exactly which lines Codex wrote there.

---

## 11. Catching a stale handoff

A handoff fails quietly. The pointer names yesterday’s job, or a state file is half the old shape, and the next agent resumes the wrong thing with total confidence. Three layers catch it.

**1. The resume validator – `sa_session.py check`.** Run before resuming; exit code 1 means fix first. It flags:

- `LATEST.txt` missing, or naming a folder that doesn’t exist;
- the active `state.json` missing, unreadable, or missing any of the eight keys (with the hint to run `migrate`);
- **pointer drift:** another folder’s state or log was modified more than 60 seconds after the active folder’s – “newer work exists in X but LATEST points at Y – confirm the pointer before resuming”.

**2. The health check at Step 0.** [`sa_doctor.py`](../tools/sa_doctor.py) runs `audit` in [`sa_loop.py`](../tools/sa_loop.py), which inspects the active handoff:

| Finding | Level |
|---|---|
| `LATEST.txt` missing, or pointing at a missing folder | fail |
| Active state missing any of the eight keys, or unreadable | fail |
| Active state’s `updated` more than 0.1 hours in the future | fail |
| Active state older than 48 hours | warn |
| Any active log line missing `ts`, `agent`, `event` or `note` | fail |

Findings score 1 for ok, 0.5 for warn and 0 for fail, averaged to a score out of 100: L3 at 90 or above with no failures, L2 from 70, L1 from 45, otherwise L0. Any failure turns the doctor’s line red, and a red light outranks the plan. The same audit also runs a circuit breaker for long agent loops – three attempts at one action, the same error three times, or five failures in a row stop the loop; a template of those settings is [`templates/loop_constraints.json`](templates/loop_constraints.json).

**3. The daily-record rule.** If `LATEST.txt` points at yesterday, start today’s folder. That one is an instruction, not code; the 48-hour warning above is the code that backs it up.

It works on the real thing. While I was writing this page, `check` failed on the day’s own session folder: it had been written without the tool, and six of the eight keys were missing.

Two gotchas came out of testing the checks on made-up folders:

- **`migrate` causes a false pointer alarm.** It rewrites old folders, so their modification time becomes the newest, and `check` then reports newer work elsewhere. Any `log` line on the active session clears it.
- **No red is not the same as green.** The compact brief greps the doctor’s output for red lights and prints “all green” if it finds none – including when the doctor couldn’t run at all, for example because its interpreter path is wrong.

---

## 12. What went wrong before the rules

| When | What went wrong | What fixed it |
|---|---|---|
| Late June to early July | `LATEST.txt` went stale more than once, and later work was logged inside an older session’s file. Nothing checked that the pointer matched the newest work. | The pointer-drift check in `check` (10 July) |
| Same period | Six session folders had six different top-level shapes of `state.json` – the old keys in [section 5](#5-one-contract-written-atomically) are the ones `migrate` was written to map – and 34 of 57 log lines had no `event`. No tool could read every session with one contract. | The contract and `sa_session.py` (10 July). `migrate` brought all seven sessions over with their originals kept; 61 of 61 log lines then carried an event, and the validator passed. |
| Same period | Codex’s instruction file pointed at a memory folder that didn’t exist, and told it to load every memory file while Claude retrieved on demand. The start-up briefing alone was about 31,000 tokens. | One lean start for both agents; the briefing rebuilt to a hard budget of 12,000 characters, about 3,000 tokens (10 July) |
| 15 July | A second audit found Claude had hand-written a new session’s `state.json` in the wrong shape instead of calling `new`, and two log lines had no `note`. | Migrated and repaired. Standing rule: write through the tool, never echo JSON by hand. |
| 6 August | Outside the log’s `agent` field, nothing in the files said which work was Codex’s – and a compaction summary can blur it. | The provenance marker |
| 9 August | I asked that a compaction should forget nothing; a summary on its own can’t promise that. | The compact brief |
| 14 August | The brief recovered the active session and lost every other commitment. | The open-threads report |
| 19 August | A single summary written when the context is full is written at the lossiest possible moment. | Checkpoints every 8 MB of transcript |
| 6 October | A recount for this page: 22 of 60 state files and 252 of 800 log lines were off the contract again. | Open – see below |

The October recount is the most useful finding on this page. **Every one of the 252 off-contract log lines was written by Claude; all 240 of Codex’s lines pass.** The likeliest reason is one sentence: Codex’s instruction file tells it to write session files through `sa_session.py`; Claude’s tells it to keep the files current but never names the tool. Codex followed its instruction; Claude hand-wrote JSON. Two-thirds of the bad lines date from August, the month with the most logged work (351 of the 800 lines). Forty-one of them have no timestamp at all, which `migrate` can’t repair: it fills a missing `event` or `note`, never a time.

It is the same lesson as the [mistakes post-mortem](learning-from-mistakes.md): a rule in an instruction file is not a guard, and a rule missing from one agent’s file is no rule at all. The obvious fix – name the tool in both instruction files, and validate every write to `Sessions/` with a hook rather than a request – hasn’t been made yet.

---

## 13. Adopting it

**1. The protocol, no code.** Copy [`workspace-kit/Sessions/README.md`](../workspace-kit/Sessions/README.md) into a `Sessions/` folder in your workspace, and put Step 0 at the top of each agent’s instruction file – the kit’s [`CLAUDE.md`](../workspace-kit/CLAUDE.md) and [`AGENTS.md`](../workspace-kit/AGENTS.md) already carry it, as Step 1 after a first-run interview. Use one agent at a time. That alone gives you most of the value; in the kit, the session files are kept by hand from the written protocol.

**2. The contract.** Add [`sa_session.py`](../tools/sa_session.py) and point it at your workspace:

```bash
export WORKSPACE_ROOT=/path/to/your/workspace
python3 sa_session.py --test
python3 sa_session.py new first-task --agent claude --purpose "one line on what this is for"
python3 sa_session.py check
```

Change the time-zone constant (`GST`, UTC+4) to yours. Then name the tool in **both** agents’ instruction files – [section 12](#12-what-went-wrong-before-the-rules) is what happens if you name it in one. If you already have old session folders, run `migrate` once and then a `log` line on the active session, to clear the false pointer alarm.

**3. Compaction, in Claude Code.** [`workspace-kit/.claude/settings.example.json`](../workspace-kit/.claude/settings.example.json) wires two hooks: one on every prompt runs [`discipline.sh`](../workspace-kit/.claude/hooks/discipline.sh), which ends by calling `sa_checkpoint.py --due`; one on the session-start event for compaction runs `sa_compact_brief.sh`. The step-by-step install, including a test compaction, is in the kit’s [`.claude/README.md`](../workspace-kit/.claude/README.md). Before you use them:

- Tell the scripts where the workspace is. `sa_session.py`, `sa_checkpoint.py` and `sa_compact_brief.sh` read `WORKSPACE_ROOT`; `sa_threads.py` reads `SA_WORKSPACE`; `sa_doctor.py` and `sa_loop.py` use the folder above their own, so keep them in the workspace’s `Tools/`. `sa_checkpoint.py` works out where Claude Code keeps your transcripts from the workspace path.
- The hook finds the workspace from Claude Code’s project folder and falls back to the system Python if there is no virtual environment. The brief doesn’t: it calls the threads report and the doctor through `Tools/venv/bin/python3`, so give it that interpreter (or edit the two lines), or it will report “all green” without having run the doctor.
- The brief’s progress-tracker section and its standing pointers name files from my workspace. Replace them with your own, or delete them.
- Check the 8 MB step against your own transcripts: find the size at which a conversation compacts, and use about a tenth of it.

In my set-up both hooks are wired into Claude Code only; Codex gets the same ground truth through Step 0.

**4. Long-term memory.** The handoff covers the task in hand. For facts that outlive it – preferences, corrections, past decisions – see [the-brain.md](the-brain.md) for how mine works, the portable [`AGENT_MEMORY_PROTOCOL.md`](../workspace-kit/Reference/AGENT_MEMORY_PROTOCOL.md), and the optional local search server in [`workspace-kit/brain/`](../workspace-kit/brain/SETUP.md). The Claude Code operating notes on clearing versus compacting are in [`CLAUDE_CODE_OPS.md`](../workspace-kit/Reference/CLAUDE_CODE_OPS.md) – in short, a fresh chat per task beats compacting a long one, because the session folder carries the state for free.

---

## 14. Maturity and known gaps

| Piece | Status |
|---|---|
| Session folder, pointer, Step 0 and the daily record | **Built, in use** – daily since June 2026 |
| The contract and `sa_session.py` (atomic writes, `check`, `migrate`) | **Built, in use** – since July 2026 |
| Checkpoints as the context fills | **Built, in use** – since August 2026; 41 checkpoints in 23 sessions |
| The compact brief | **Built, in use** – since August 2026, Claude Code only |
| The open-threads report | **Built, in use** – with the two gaps in [section 9](#9-open-threads) |
| The provenance marker | **Built, in use** – 95% of Codex’s log lines since the rule |
| Handoff checks in the health check | **Built, in use** |

Known gaps, all open as of 6 October 2026:

1. **Contract drift.** Nothing enforces the contract at write time; an agent that hand-writes JSON breaks it ([section 12](#12-what-went-wrong-before-the-rules)).
2. **The open-threads report ignores `next` and `extra`**, so a contract-shaped session can drop out while it still owes a step ([section 9](#9-open-threads)).
3. **`--mark` counts a checkpoint whether or not one was written.** Three sessions have a checkpoint counted and no checkpoint file.
4. **`migrate` can’t restore a missing timestamp**, and running it raises a false pointer alarm until the active session is touched.
5. **The compact brief can print “all green” when the doctor didn’t run.**
6. **One agent at a time is a human rule.** No lock protects the folder from two agents writing at once.

The handoff itself has never needed to be more complicated than three plain files. Everything else on this page exists to keep those three files true.

---

**Related:**

- [running-two-ai-agents.md](running-two-ai-agents.md) – the whole two-agent set-up, in one page
- [the-brain.md](the-brain.md) – the shared long-term memory that sits beside the handoff, in full
- [learning-from-mistakes.md](learning-from-mistakes.md) – why a rule in an instruction file is not a guard
- [why-ai-agents-forget.md](why-ai-agents-forget.md) – an audit of another multi-agent set-up whose memory was failing silently
- [security-and-data-policy.md](security-and-data-policy.md) – what each agent may send where
- [`workspace-kit/Sessions/README.md`](../workspace-kit/Sessions/README.md) – the protocol, ready to copy
- [`AGENT_MEMORY_PROTOCOL.md`](../workspace-kit/Reference/AGENT_MEMORY_PROTOCOL.md) – the portable long-term memory specification
