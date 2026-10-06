# Spec-driven AI work: a pilot

What happened when I applied spec-driven development – write the rules, then the spec, then the plan and tasks, and only then build – to AI production work rather than to software. The trigger was drift: agents narrating what a screen recording *should* show rather than what it does, skipping interface steps, and pacing training videos for the recording instead of the learner. The pilot produced a six-principle constitution, one worked feature spec, an eight-gate pre-flight checklist and a read-only validator. It used GitHub’s open-source [Spec Kit](https://github.com/github/spec-kit) as the frame, and it was written by AI coding agents under my direction.

**Status:** **Pilot** – one isolated feature, run end to end; not yet routine. The outputs: [the constitution](templates/spec-kit-constitution.md) · [the worked spec](templates/spec-agent-consistency-gates.md) · [the gates checklist](templates/consistency_gates_checklist.md) · the validator, [`sa_consistency_gate.py`](../tools/sa_consistency_gate.py).

---

## 1. When a full spec is worth it

| The work | Route | Why |
|---|---|---|
| A reusable tool, automation or pipeline step | **Full spec** – spec, plan, tasks, a verification gate | Other agents will run it later without the context you have today. |
| A change to how agents work (a gate, a hand-over rule, a review step) | **Full spec** | Process changes fail silently; a written acceptance test is the only way to know it holds. |
| A revision of a screen-recorded training video | **Gates, always** (action coverage and timing), spec optional | This is where drift was most expensive. |
| A research workflow you will reuse | **Full spec** | Sources, limits and output shape need to be fixed before the second run. |
| A site, app, dashboard, or brand template | **Full spec** | Anything others build on. |
| A one-off creative piece – a caption, a post, a single edit | **Light brief** | A spec would cost more than the work. The safety, memory and evidence rules still apply. |

The test I use: *if a model hallucinating here would be expensive, or the work will be repeated, write the spec.*

## 2. Pilot in an isolated folder, not at the root

Spec Kit’s guidance for existing projects allows initialising in place – but only once the current system is understood and reviewable, and it does not infer existing behaviour for you. My workspace root holds live memory, active session files, editing-support files and work in progress. So the pilot lived in its own folder, and root initialisation was deferred to a separate clean-baseline review that has not happened yet.

Four things from reading the official documentation shaped the safety rules:

- **Workflow shell steps run with your local privileges** and no separate sandbox. Every shell step is reviewed before use, and read-only steps are the default.
- **Presets, extensions and bundles from the community are not audited.** They are third-party code: source-reviewed first, like anything else ([how third-party tools are vetted](security-and-data-policy.md#5-how-third-party-ai-tools-are-vetted)).
- **Integrations differ per agent.** The Codex integration installs its skills in one folder and the Claude integration in another, so setting up one agent does not teach the other. A short, agent-neutral routing guide at the workspace level filled that gap.
- **Agent folders can hold local credentials**, so the pilot’s agent folder is kept out of version control.

## 3. The constitution: six principles

The constitution is the standing law the spec, plan and tasks are checked against. Rewritten generically (the pilot’s own text is [here](templates/spec-kit-constitution.md)):

| # | Principle | In practice |
|---|---|---|
| I | **Evidence before narrative** | Start from current evidence – the active session, the named source files – never from memory. If evidence conflicts, say so and resolve it first. Interface actions, button labels, timings and tool states are never invented. |
| II | **Protected originals** | Original projects, raw media, final masters and the owner’s working cut are immutable without explicit authorisation. Revisions use duplicates, review exports or plans; any direct-edit workflow must first prove its target is a duplicate. |
| III | **Timing serves comprehension** | Training videos are paced for the learner. Build a timing plan before editing; busy screens at most 1.2×, review moments at most 1.0×; freeze on a stable frame when the voice needs time; split compound lines at the action. |
| IV | **Session truth** | The session state file is the live truth, the log is append-only history, memory is the long-term record. Every agent-authored change is traceable to the agent that made it. |
| V | **Local-first safety, whole-system scope** | The spec discipline applies wherever a repeatable workflow benefits, not just to video. Internal material stays local unless a specific upload is approved; shell steps and community add-ons are source-reviewed before adoption. |
| VI | **Verified before done** | Done means: outputs exist, tests or validators pass, counts are current, limitations are recorded, session and memory are updated. If verification is incomplete, say what remains unverified. |

Governance: amendments need an explicit approval, a version bump and a dated impact note.

## 4. The worked feature, condensed

The first feature was the consistency gates themselves. The full spec is in [the example spec](templates/spec-agent-consistency-gates.md); here is the shape of each artefact.

- **Spec.** Three prioritised user stories, each with a test that can run on its own: *start from current truth* (P1), *align narration, actions and picture* (P2), *scale beyond one tool* (P3). Twelve functional requirements; five success criteria; edge cases (a live project mid-edit is never mutated; after two failed rebuilds, stop and ask for one concrete example).
- **Research.** What Spec Kit is (a process harness – constitution → specify → plan → tasks → implement – that GitHub frames as usable for business processes, not only code); the existing-project guidance; the per-agent integration split; the shell-step and community-add-on warnings. And one local finding that became a gate: a stale summary file from an earlier failed run sat next to the current evidence and reported a fraction of its events and frames – an agent reading it first would have made confident, wrong claims.
- **Data model.** Five entities – gate context, evidence source (with a *freshness* field: current, stale, conflicting, unknown), action beat, timing plan, workflow artefact – so the documents, the validator and any later automation use the same words.
- **Plan.** A documentation layer plus a read-only validator; standard-library Python; local files only; no project writes, uploads or publishing. A constitution check maps each principle to how the plan satisfies it.
- **Tasks.** Thirteen, in four phases: setup, research and design, implementation, verification and memory. All closed in the pilot.

## 5. What came out of it

| Output | What it does |
|---|---|
| [Consistency-gates checklist](templates/consistency_gates_checklist.md) | Gates 0–7: resume current truth, evidence ledger, classify the work, action coverage, timing, evidence conflicts, stop conditions, verification. |
| [`sa_consistency_gate.py`](../tools/sa_consistency_gate.py) | A read-only pre-flight: required documents present, active session readable, no unresolved template placeholders, no accidental root initialisation, watched-session evidence consistent. Exit 0 = no failures (warnings allowed), 1 = failures, 2 = self-test error; `--test` writes only to a temporary folder. |
| [Training action map](templates/training_action_map_template.csv) | One row per interface action – the evidence behind gate 3. |

**What it does not do.** The validator checks documents, session files and evidence counts; it does not certify that a rendered video is correct. That still needs a person, or the frame-level checks in [training-video production](training-video-production.md). It is also tied to my folder layout – read it as an example, not a drop-in.

## 6. What I’d tell someone trying this

- Start with the rules you already break, not with the template. The constitution is short because each principle names a failure that had already happened.
- Keep spec-driven work as a layer over your existing hand-over and memory system, not a replacement for it.
- Make the first feature about agent behaviour. A gate that stops drift pays back on every later task.
- Don’t copy the toolkit’s templates wholesale. I’ve credited Spec Kit and linked it above rather than reproducing its templates, scripts or skills here – fetch them from the source.

## Maturity

| Piece | Status |
|---|---|
| Isolated pilot: constitution, one feature spec, plan, research, data model, tasks | **Pilot** |
| Gates checklist used before training-video revisions | **Pilot** |
| Read-only validator | **Pilot** – self-tests pass; not yet part of the routine start-of-task check |
| Spec Kit at the root of the live workspace | **Not approved** – deferred until a clean-baseline review |

---

Related: [example spec: consistency gates](templates/spec-agent-consistency-gates.md) · [consistency-gates checklist](templates/consistency_gates_checklist.md) · [Spec Kit constitution](templates/spec-kit-constitution.md) · [how I engineer with AI coding agents](ai-engineering-method.md) · [training-video production](training-video-production.md) · [security and data policy](security-and-data-policy.md)
