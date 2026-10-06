# How I engineer with AI coding agents

I direct the work; AI coding agents (Claude Code and Codex) write the code; deterministic checks decide whether it works. This is the method behind the studio workspace’s tools: route work by risk, diagnose before fixing, and never call anything done without fresh evidence. Almost every rule here was paid for by a real failure.

This page is the summary with the incidents behind it. The full method, as both agents read it, is in [engineering-method-full.md](engineering-method-full.md); it ships to other workspaces as a thin skill in [`../workspace-kit/.claude/skills/engineering-method/`](../workspace-kit/.claude/skills/engineering-method/SKILL.md). The code that enforces it: [`sa_loop.py`](../tools/sa_loop.py) (run ledger and circuit breaker), [`sa_guard.py`](../tools/sa_guard.py) (pre-flight refusals), [`sa_doctor.py`](../tools/sa_doctor.py) (health check), [`sa_nightly.sh`](../tools/sa_nightly.sh) (overnight runner) and [`sa_toolindex.py`](../tools/sa_toolindex.py) (generated tool catalogue). The binding limits live in [`templates/loop_constraints.json`](templates/loop_constraints.json).

---

## Who does what

| Role | Responsibility |
|---|---|
| Me | Set the goal, the exclusions and what counts as proof. Review the result against the brief. Approve anything irreversible. |
| AI coding agents | Check what already exists, write the code and its self-test, run the checks, record the evidence in the session files. |
| Checks and guards | Refuse unsafe writes, stop runaway retries, and report *ok*, *wrong* or *unknown* – never a guess. |

All the code in this repository was written by AI coding agents under my direction and review. My part is the specification, the judgement calls and the refusal to accept “done” without evidence.

The method borrows the useful parts of two public sources – OpenAI’s published skill and plugin packaging, and the open-source Superpowers workflow for systematic debugging, planning, test-driven development and review – without installing either wholesale. Both are references, not runtime dependencies.

---

## 1. Route the work by risk

Not every task deserves the full process. Creative editing, copywriting, document formatting and one-off production stay outside it.

| Work | Route |
|---|---|
| Explanation, inspection or a small low-risk edit | Do it directly; verify the specific claim or output. |
| Bug or failed automation | The diagnosis loop below, before any code changes. |
| Multi-file or reusable change | A short design and plan naming the exact files and checks – and, for a durable workflow change, a written spec (section 6). |
| Risky or experimental change | Offer an isolated git worktree. Active media projects never move into one. |
| Independent tasks with no shared state | Parallel agents, each owning named files, with a reconcile step at the end. See [orchestrating-agent-fleets.md](orchestrating-agent-fleets.md). |

---

## 2. Diagnose before fixing

1. Reproduce the failure – or establish that it can’t currently be reproduced.
2. Preserve the exact error, input, environment and state.
3. Shrink the failing case and find the first point where reality diverges from expectation.
4. Form one specific hypothesis and run the cheapest check that tells the alternatives apart.
5. Fix the root cause, not the visible symptom.
6. Add a regression check in proportion to the risk, then run nearby checks for side effects.

### Fourteen rules, each from a real incident

| Rule | The incident that taught it |
|---|---|
| Read the actual error before forming a theory. | An overnight image job’s error message named the cause all along; three confident wrong root causes were proposed before anyone read it. |
| Reproduce on the failing case, not a lookalike. | An hour went on testing an image that worked while the three that failed sat untouched. |
| Benchmark the real workload. | Timings taken with a placeholder prompt measured nothing; the real prompt behaved completely differently. |
| Change one variable, measure, revert if worse. | Every “fix” in one model-settings investigation changed two things at once, so no conclusion held until the steps were isolated. |
| Look at the picture, not the parameter. | Call-out boxes passed every numeric check and sat on the wrong button. |
| A non-answer is not a defect. | A tool that can’t verify must report *unknown* – never pass, never fail. False alarms cost more than misses, because I go and look. |
| A limit built for one purpose is not a test for another. | A 46-character caption guide (where to break a line) was misused as a defect threshold and nearly rewrote a finished project. |
| When two jobs share a resource, run them one after the other. | Two local-model batches at once produced timeouts that looked like the fix had failed. |
| A join that returns zero is broken, not empty. | “0 of 203 frames match the edit log” was a timestamp bug. |
| The newest slice is not the history. | A newest-first file read from the top described three weeks and missed three months. |
| Read the resulting state, not the exit message. | An install was reported done while the step that merges call-out tracks had refused inside its own output (two labels started on the same line at the same moment). The project still had 131 video tracks – the state I had already called unusable. One read of the track list would have shown it. The rule since then: after every install, read the track list, not the exit message – a refusal from [`sa_capcut_flatten.py`](../tools/sa_capcut_flatten.py) is printed, not raised. |
| Assert that a patch landed. | A scripted edit to a tool silently did nothing because its text escaping didn’t match the file – and the tool’s self-test still passed, because the new assertions hadn’t landed either. After any scripted patch, check that the replacement is present in the file, or rewrite the whole function. |
| Read a tool’s parameters before debating model quality. | A request to animate a still portrait through a hosted motion-graphics connector was being treated as a prompting problem. Its compose call takes exactly three parameters – a prompt, a project id and a design source – and no media parameter, so no wording could ever have worked, and firing it would have billed a render for a graphics video built from a text description. |
| Name the target explicitly when a default can resolve to the parent. | A helper’s default draft path resolved to a multi-timeline project’s *main* timeline – the finished parent video – not the short sub-timeline meant to get an outro. Run as-is, it would have written into the finished film. [`sa_outro.py`](../tools/sa_outro.py) and [`sa_tailkit.py`](../tools/sa_tailkit.py) now take an explicit `--timeline "<name>"` and list the available names when one doesn’t match. |

### When something breaks

> reproduce on the exact failing input → read the raw error → search memory for the symptom → one-variable experiments with measurements → fix → **add the check that would have caught it** → log the cause and the guard the same turn.

A fix without its guard is half a fix. The reasoning behind that rule is in [learning-from-mistakes.md](learning-from-mistakes.md); the blank entry formats are in [templates/fix_log_entry.md](templates/fix_log_entry.md).

### Recall paths: where past failures live

Diagnosis is faster when the agent knows where to look before it starts theorising. Each kind of question has one place that answers it.

| What you need | Where it lives |
|---|---|
| Has this failed before, and how was it fixed? | Memory search for the *symptom* – every correction since May, with superseded entries ranked down ([`../workspace-kit/brain/`](../workspace-kit/brain/)). |
| Defects that got past a passing check | The escaped-defect ledger – each entry stays open until a check fails on its recorded case ([learning-from-mistakes.md, section 6](learning-from-mistakes.md#6-the-escaped-defect-ledger)). |
| Every known trap in the video pipeline, and the guard that stops it | The pipeline-traps file, one entry per trap with its guard (private; summarised in [training-video-production.md](training-video-production.md)). |
| Recurring mistake patterns since day one | The post-mortem ([learning-from-mistakes.md, section 2](learning-from-mistakes.md#2-the-sixteen-patterns)). |
| My own feedback, verbatim | The feedback log, newest first – read it to the bottom for the early era. |
| Is the system healthy right now? | [`sa_doctor.py`](../tools/sa_doctor.py) – 0.3 seconds, run at every session start. |
| Did last night’s automation actually finish? | The nightly log and the attention note, which appears only when a run did not finish ([`sa_nightly.sh`](../tools/sa_nightly.sh), [`sa_nightcheck.sh`](../tools/sa_nightcheck.sh)). |
| Which tools already exist, before building anything | The generated tool catalogue ([`sa_toolindex.py`](../tools/sa_toolindex.py)) – it can’t go stale because it is rebuilt from each script’s own docstring. |

---

## 3. Build in small, checkable steps

- **Tests where they mean something.** Red–green–refactor when a useful failing test can be written; no tests written just to satisfy a ritual.
- **Rendered evidence where tests can’t reach.** Visual judgement, generated assets and fragile desktop-app behaviour need a rendered frame or an in-app check. A unit test cannot prove a call-out sits on the right button.
- **For substantial changes:** confirm the outcome, exclusions and acceptance evidence; check existing code and memory first; split the work into units that can each be verified, with clear file ownership; leave unrelated changes alone; review against the requirements first, then for quality; finish only after fresh verification and a written handoff.
- **Every tool carries its own `--test`.** The generated tool catalogue ([`sa_toolindex.py`](../tools/sa_toolindex.py)) flags any script without a docstring or a self-test.

---

## 4. “Done” needs evidence that matches the claim

| Claim | Evidence required |
|---|---|
| Code behaviour | A focused test plus the relevant broader checks. |
| Bug fix | The original reproduction no longer fails, and a regression check would catch a recurrence. |
| Website or UI | Rendered browser checks at the relevant sizes, console errors and interaction states. |
| Media pipeline | Inspection of the generated file, plus the render or in-app checks its maturity level requires. |
| Automation | An execution record, the failure path and recovery evidence. Configuration alone is not proof it ran. |
| Documentation | Links, syntax and factual claims checked against current sources. |

Three claims are banned outright in the binding constraints file:

- calling a feature production-ready before a real application test;
- claiming a speed, effect or transition was applied without verifying it;
- claiming a percentage of automation without measured project evidence.

Unknown, skipped and blocked checks are reported as exactly that. A passing documentation build, a tool count or a system-wide readiness score is never proof that an individual capability works.

**Review order:** requirements first (does it meet the actual request, including exclusions and safety rules?), then quality (correctness, security, maintainability, performance, usability). At the end of a branch I decide whether to merge, open a pull request, keep it or discard it – the agent never assumes that permission.

### Website or UI: what the evidence has to cover

Web image work taught a few rules that a passing build never checks:

1. **Read the rendered page, not the fetched HTML.** On a JavaScript-rendered page a plain fetch returns markup with no image addresses in it. Load the page in a real browser and read the DOM: each image’s `src`, `currentSrc` and `srcset`, plus `getComputedStyle(el).backgroundImage` for images set in CSS.
2. **Scroll the whole page first.** Images lazy-load; anything below the fold is missing until it has been scrolled into view.
3. **Take the original, not the thumbnail.** `currentSrc` is usually the small responsive variant the browser picked; `src` often still holds the original. When only a sized variant exists, walk the CDN’s size ladder from the largest step down and keep the largest that returns 200.
4. **Hydration puts deleted elements back.** On a server-rendered React page, removing an element from the static HTML is not enough: strip it from the server-component payload too, or hydration restores it on load.
5. **Verify off the server, with a cache-buster.** Request the page with a throwaway `?v=` query before concluding anything about a local mirror or a deploy; a cached copy proves nothing.
6. **Check the whole page, not just the slot.** Before moving an image into a slot, search the entire page for it. A photo moved into a new block once duplicated one already shown two blocks away; I had checked the slot, not the page.

---

## 5. Guard rails for automation

The rules live in one machine-readable constraints file that every engineering run reads through [`sa_loop.py`](../tools/sa_loop.py), which also keeps a run ledger of each attempt and its evidence. A generic copy of the file is in [`templates/loop_constraints.json`](templates/loop_constraints.json).

| Guard | Rule |
|---|---|
| Circuit breaker | Stop after 3 failed attempts at the same action, the same error 3 times, or 5 failures in a row. Then: stop, preserve the evidence, update the session state, escalate to me. |
| Kill switch | A single pause file blocks every automated write; tools report state only. Removing it needs my approval. |
| Never overwrite | Existing editing projects and sequences, original footage and photographs, my working cut, final masters. |
| Needs explicit human approval | Deleting files; publishing or sending anything externally; installs needing administrator rights; uploading company footage to cloud services; changing the workspace’s brand rules. |
| Completion requires | Output files exist; relevant tests or validators pass; safety checks pass; session state is updated; known limitations are recorded. |

### Maturity is per capability, not per system

| Level | What it may do |
|---|---|
| L1 | Report or recommend only. No changes to any project. |
| L2 | Build a new, disposable review artefact after a human request. Never overwrite. |
| L3 | Run unattended – only after repeated verified L2 runs and my explicit approval. |

At the last update of the constraints file, the production tools (extraction, cut sheets, tightening, timeline planning, the editing-project writer, style comparison) sat at L2. Publishing and destructive clean-up stayed at L1. Nothing was at L3.

### The pre-flight guard

[`sa_guard.py`](../tools/sa_guard.py) turns lessons into refusals. It refuses to write while the editing app is open (the app overwrites its project file on exit), refuses a second heavy local-model batch while one is running, refuses any write to a project I have marked done – reading that list fresh on every call – and searches the tool catalogue before a new tool is written. It is proven by its self-test and by a live refusal against a finished video.

---

## 6. Specs for reusable changes (pilot)

Under a pilot running since September 2026, reusable tools, workflows and cross-project process changes should get a written specification before code: a feature spec, a plan, a task list and a verification record, in the shape of GitHub’s open-source [Spec Kit](https://github.com/github/spec-kit). If a lighter brief is used instead, the reason is written down. One-off creative work keeps a short brief – the overhead isn’t worth it for something that won’t be repeated.

The pilot runs in an isolated folder, not at the root of the live workspace: the workspace holds active memory, session files and editing-project support files, so initialising there waits for a separate clean-baseline review. Spec Kit is an added layer over the session protocol and the instruction files, never a replacement for them. Community extensions, presets and workflow shell steps are treated as untrusted until their source has been read, because a workflow shell step runs locally with full privileges.

The pilot’s constitution has six principles:

| # | Principle | In one line |
|---|---|---|
| I | Evidence before narrative | Start from the current session state, memory and named source files; never invent UI actions, button labels, timings or tool states; name any conflict and resolve it before proceeding. |
| II | Protected originals | Original editing projects, raw media, final masters and my working cuts are immutable without my explicit say-so; revisions work on duplicates, review exports or written plans. |
| III | Timing serves comprehension | Build a timing plan before editing; busy screens at or below 1.2×, review moments at or below 1.0×, freeze on a stable frame when the voice needs time, and split compound lines at real action boundaries. |
| IV | Session truth | Session state is the live truth, the log is append-only history and the memory store is the long-term record; the second agent’s additions carry its attribution marker. |
| V | Whole-system scope, local-first safety | Specs apply to any repeatable workflow, not only video; internal material stays local unless a specific upload is approved; extensions and shell steps are source-reviewed first. |
| VI | Verified before done | Outputs exist, tests or validators pass, evidence counts are current, limitations are recorded and session and memory are updated – otherwise say what remains unverified. |

One operational rule sits under all six: any contradiction between the source media, the editing project, the session state and memory is a blocker until it is reconciled.

- The constitution as written: [`templates/spec-kit-constitution.md`](templates/spec-kit-constitution.md).
- A worked example feature spec, turning agent-consistency rules into testable requirements: [`templates/spec-agent-consistency-gates.md`](templates/spec-agent-consistency-gates.md).
- The same gates as a pre-flight checklist for any agent task: [`templates/consistency_gates_checklist.md`](templates/consistency_gates_checklist.md).
- When a spec is worth it, and the pilot in more depth: [spec-driven-ai-work.md](spec-driven-ai-work.md).

**Packaged as a skill.** The whole method travels as a thin project skill, [`../workspace-kit/.claude/skills/engineering-method/SKILL.md`](../workspace-kit/.claude/skills/engineering-method/SKILL.md). Its description routes coding, debugging, automation, integration and reusable system work to the method, and keeps it off ordinary creative or marketing production. It states plainly that it grants no authority to create branches, spawn agents, install plugins, publish, upload data or change external systems – those permissions stay with me.

---

## 7. Outside ideas: what I took and what I left

On 9 August 2026 I had the agents judge published harness-engineering ideas against the working system. Most lost. Five were chosen for immediate work:

| Idea | What it fixed | Where it stands |
|---|---|---|
| Make the overnight runner survive the night | A suspended 3 am job looked identical to a finished one. | [`sa_nightly.sh`](../tools/sa_nightly.sh) runs the heavy local work between 1 and 6 am and leaves a morning note; an attention file appears only when a run did not finish. **Built, in use** – nightly logs run to October 2026. The macOS side of it is in [local-ai-on-a-mac.md](local-ai-on-a-mac.md). |
| Resume, don’t restart | A long batch of agent jobs killed partway through could only restart by trusting a prose summary. | Each finished step is written to a ledger; a re-run picks up at the first unfinished step. **Built, in use.** |
| Supersede markers in memory | A corrected rule and its correction came back from search with equal weight. | Logging a correction marks the old entry superseded and search ranks it down. Nothing is deleted. **Built, in use.** |
| Every escaped defect becomes a permanent test | Misses evaporated into the worklog. | The escaped-defect ledger, described in [learning-from-mistakes.md](learning-from-mistakes.md). **Built, in use** as a ledger; closing entries is slow. |
| A generated tool catalogue | Hand-kept maps went stale and tools got rebuilt from scratch. | [`sa_toolindex.py`](../tools/sa_toolindex.py) writes the catalogue from each script’s own docstring and runs inside the health check, so it can’t drift. My private catalogue of the main tools folder listed 162 tools at its 6 October 2026 generation; 146 of them are published, alongside 49 from working branches and project folders – 195 in [`../tools/README.md`](../tools/README.md). **Built, in use.** |

And what I declined:

| Category | Why not |
|---|---|
| Memory servers and vector-database products | The features I need take tens of lines. One popular option silently deletes “contradictory” memories, which a corrections log must never do. |
| Multi-agent frameworks | Their one useful trick – ledgers, stall thresholds, handoffs – is about 25 lines natively. The rest is token cost and install surface. |
| Multi-agent debate | The research the agents reviewed suggested it converges confidently on wrong answers. Independent checkers that refuse rather than guess are stronger. |
| Workflow schedulers and daemons | One Mac needs a scheduler plus a step ledger, not another service to babysit. |
| Hosted health checks, extra cloud agents, cloud sandboxes | Each would send job data to yet another outside service. Routine checks run locally and upload nothing; the two coding agents read what they work on, and anything else leaves only through an approved, logged route. |
| Chatbot guardrail products | They police chat text. My risk is file side-effects, which are handled by code. |
| Text-evaluation suites | They score text and models. My signal is pixels and my own final edits. |

Two ideas came from Anthropic’s published articles on harnesses for long-running agents and apps: agree in writing what “done” means for a chunk of work before starting it, and periodically delete harness parts the model no longer needs. A third – a startup routine should *run* a health check, not just read state – is now part of Step 0: every session runs the 0.3-second [`sa_doctor.py`](../tools/sa_doctor.py) as it resumes, and a red light there outranks the plan.

The one install that survived review was an OS-level sandbox for trialling third-party code – still in beta, so to be pinned to a fixed version, and marked optional. The full vetting process is in [security-and-data-policy.md](security-and-data-policy.md).

### On the list

The same review queued a second tier for later. None of it is built: a search of the worklog on 6 October 2026 found no record of any of these items, so every one is **Planned**.

| Idea | What it would do | Status |
|---|---|---|
| A capped loop over headless runs | A short shell loop over headless agent runs: fresh context each pass, files as the only memory, a hard iteration cap and a scoped tool list. The session files already do the hard part. | **Planned** |
| Weekly consolidation with search telemetry | Log which memory searches ran and what came back, then write a weekly propose-only review file (merge, supersede, promote) that I approve line by line. | **Planned** |
| A central policy hook and shadow git checkpoints | One guard module called from one hook, plus automatic checkpoint commits an agent can roll back to. Standing configuration, so it needs my explicit yes first. | **Planned** |
| Confirm-before-write and errors that teach | Small shared helpers – show the diff and ask before writing; error messages that say what to do next – adopted as each tool is next touched. | **Planned** |
| A golden regression runner | Replay every closed escaped-defect case against the current tools, alongside playbook counters and an edit-cost number, so the ledger becomes measurable evidence. | **Planned** |
| Fleet stall detection and majority voting | Standing features of the agent-fleet runner: flag a worker that has stopped making progress, and decide contested findings by vote. A one-off two-of-three refuter vote already exists inside [`../workflows/adversarial-verify.js`](../workflows/adversarial-verify.js); the standing fleet feature does not. | **Planned** |
| Budget alarms on always-loaded memory | Fail the existing memory evals when the files loaded into every session grow past their size budget. | **Planned** |

---

## Maturity

Labels follow the [status labels in the README](../README.md#status-labels). This is internal tooling for my own workspace, so “Built, in use” is the honest ceiling: it is relied on daily, but it is not itself a delivered output.

| Piece | Status | Code |
|---|---|---|
| Risk routing, diagnosis loop, evidence rules | **Built, in use** – written into both agents’ standing instructions | [engineering-method-full.md](engineering-method-full.md) |
| Run ledger, circuit breaker, kill switch | **Built, in use** | [`sa_loop.py`](../tools/sa_loop.py) |
| Pre-flight guard and approved-freeze list | **Built, in use** | [`sa_guard.py`](../tools/sa_guard.py) |
| Health check at every session start | **Built, in use** | [`sa_doctor.py`](../tools/sa_doctor.py) |
| Overnight runner that resumes | **Built, in use** | [`sa_nightly.sh`](../tools/sa_nightly.sh) |
| Generated tool catalogue | **Built, in use** | [`sa_toolindex.py`](../tools/sa_toolindex.py) |
| Specs for reusable changes, and the method packaged as a skill | **Pilot** – isolated pilot folder since September 2026; not initialised at the workspace root | [`templates/spec-kit-constitution.md`](templates/spec-kit-constitution.md), [`SKILL.md`](../workspace-kit/.claude/skills/engineering-method/SKILL.md) |
| Written “done” contracts for agent batches | **Planned** – queued in the 9 August review | – |
| The “On the list” items above | **Planned** | – |

**Related:**

- [engineering-method-full.md](engineering-method-full.md) – the full method as the agents read it
- [learning-from-mistakes.md](learning-from-mistakes.md) – the mistakes behind these rules, and the escaped-defect ledger
- [spec-driven-ai-work.md](spec-driven-ai-work.md) – when a spec is worth it
- [orchestrating-agent-fleets.md](orchestrating-agent-fleets.md) – parallel agents, verification fleets and their limits
- [running-two-ai-agents.md](running-two-ai-agents.md) – session hand-off between Claude Code and Codex
- [local-ai-on-a-mac.md](local-ai-on-a-mac.md) – local models and unattended jobs on one machine
- [security-and-data-policy.md](security-and-data-policy.md) – data classes, gates and vetting third-party tools
