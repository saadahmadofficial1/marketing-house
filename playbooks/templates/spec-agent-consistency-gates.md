# Example feature spec: consistency gates for AI agents

A worked example of a feature specification in the shape GitHub’s open-source [Spec Kit](https://github.com/github/spec-kit) uses – prioritised user stories with independent tests, functional requirements, entities, success criteria, edge cases and assumptions – applied not to software but to how AI agents behave on production work. It turns a handful of consistency rules (start from current truth; match narration, actions and picture; give reusable changes a spec) into requirements someone can test. The checklist that came out of it is [consistency_gates_checklist.md](consistency_gates_checklist.md); the method around it is [spec-driven AI work](../spec-driven-ai-work.md).

**Status:** **Pilot.** Written by AI coding agents under my direction during one isolated pilot. Spec Kit is an added layer here, not a replacement for the session protocol that agents already follow.

---

## Feature specification: agent consistency gates

**Feature branch:** `001-agent-consistency-gates` · **Status:** drafted for pilot implementation

**Input:** a request for a thorough structure that stops agent drift – narration that does not match the screen, skipped interface steps, pacing too fast for the viewer – and that survives a hand-over from one model to another mid-task.

### User story 1 – Start from current truth (priority P1)

As the owner, I want any agent to begin from the active session, memory and current evidence, so I never have to re-explain work after a model hits a limit or drifts.

**Why this priority:** without current state and evidence, every later plan can be confidently wrong.

**Independent test:** start a new task with an active session and a stale observation file sitting next to newer evidence. The gate must name the active session and warn that the stale file’s counts conflict with the current manifest.

**Acceptance scenarios**
1. **Given** the session pointer names an active session, **when** the gate runs, **then** it reads that session’s state file and confirms its log has entries.
2. **Given** an older observation file reports fewer events and frames than the current files, **when** the gate runs, **then** it warns that the manifest and learning notes are the safer authority.
3. **Given** a required reference document is missing, **when** an agent tries to start implementing, **then** the gate fails before any implementation claim is made.

### User story 2 – Align narration, actions and picture (priority P2)

As the owner, I want every real interface action in a training video mapped to a narrated beat, a caption, a call-out, a pause or a documented exclusion, so videos never skip a step or move too fast to follow.

**Why this priority:** the failure that prompted this was not speed alone – voice, picture and call-outs drifted apart because narration followed the raw recording, not the learner.

**Independent test:** feed the gate a watched-session evidence folder whose current notes record many more timeline events and frames than a stale summary file beside it. The gate must flag the stale evidence before any final edit is claimed.

**Acceptance scenarios**
1. **Given** a recording contains a primary button press, **when** a narration plan is prepared, **then** that press gets its own short imperative beat using the button’s exact visible wording.
2. **Given** a line says “do X, then Y”, **when** timing is planned, **then** the line is split at the action.
3. **Given** the narration needs more time than the recording gives, **when** the edit is planned, **then** a freeze or pause on a stable frame is inserted, rather than speeding the learner through the screen.
4. **Given** a call-out is placed after re-pacing, **when** verification runs, **then** its box is checked on the actual final frame.

### User story 3 – Scale beyond one tool (priority P3)

As the owner, I want the same discipline for other tools, automations, sites, designs and research workflows once the work becomes repeatable or risky.

**Why this priority:** a spec layer earns its keep across the whole system, not as a patch for one editor.

**Independent test:** start a change to a reusable tool or workflow. The process must either create a spec, plan and tasks, or record why a lighter brief is enough.

**Acceptance scenarios**
1. **Given** a new reusable workflow is requested, **when** work begins, **then** the agent creates or references a spec, plan, tasks and a verification gate.
2. **Given** a one-off creative request with no reusable impact, **when** work begins, **then** a lighter brief is allowed, still under the safety and memory rules.
3. **Given** a community extension, preset or shell workflow is proposed, **when** adoption is considered, **then** a source review and safety note are required before anything is installed.

---

### Functional requirements

- **FR-001** – Before substantial work, the agent MUST load the workspace memory and the active session state and log.
- **FR-002** – Incoming work MUST be classified (creative output, training-video revision, system tooling, research, other reusable workflow) before the process depth is chosen.
- **FR-003** – The agent MUST keep an evidence ledger of the source media, project files, exports, scripts, session folders and reference documents behind its claims.
- **FR-004** – For training-video revisions, every primary button, navigation click, role switch, field entry, save and status change MUST be covered by a beat, unless an exclusion is documented.
- **FR-005** – The timing plan MUST stop raw screen pace from dominating comprehension: content screens at most 1.2×, review moments at most 1.0×, stable-frame freezes when narration needs time.
- **FR-006** – Compound narration MUST be split at action boundaries, so every visual action has its own spoken or captioned beat.
- **FR-007** – The agent MUST detect stale or conflicting evidence, such as a summary file whose counts disagree with the current manifest, frame index, event log or notes.
- **FR-008** – Destructive edits, publishing, uploads and cloud processing of internal media MUST be blocked without explicit approval for that specific action.
- **FR-009** – Original projects and media MUST be preserved by default; experiments use duplicates or review artefacts.
- **FR-010** – Reusable tools, workflows and process changes SHOULD receive spec artefacts, unless the agent documents why the lighter path fits.
- **FR-011** – Completion MUST require verification output, a session update and any relevant memory or reference update.
- **FR-012** – The pilot MUST provide a short agent-facing routing guide, so an agent can recover the working style without re-reading every historical file.

### Key entities

| Entity | Fields |
|---|---|
| **Gate context** | request type · active session · risk level (low, medium, high, blocked) · required references · spec folder (optional) · verification required |
| **Evidence source** | path or approved URL · kind (session, memory, source media, project file, export, frame index, timeline events, manifest, learning note, official documentation) · freshness (current, stale, conflicting, unknown) · claim supported · limitations |
| **Action beat** | source time · visible action · exact on-screen wording · voice-over line or exclusion · caption line · call-out required · verification frame after re-pacing |
| **Timing plan** | voice duration · visual duration · speed factor · freeze points · call-out hold · caption in/out · the learner reason for the pacing |
| **Workflow artefact** | type (constitution, spec, plan, task list, validator, output, session or memory update) · location · created by · authorship marker present · verification |

### Success criteria

- **SC-001** – The gate flags the stale-summary pattern: a leftover file whose counts are a fraction of the current evidence.
- **SC-002** – Training-video plans give every primary button press its own narrated beat, including the final verification step of a workflow.
- **SC-003** – Every reusable workflow change has spec artefacts or a documented exception before implementation starts.
- **SC-004** – Spec Kit is not initialised at the root of the live workspace until that workspace has a clean, reviewable baseline.
- **SC-005** – Completion reports include the verifier’s output, or a clear statement of what remains unverified.

### Edge cases

- A live project is mid-edit: the pilot must never mutate it or the owner’s working cut.
- Evidence can conflict because older local files remain beside newer ones.
- Raw recordings may contain internal data; local-only analysis is the default.
- The owner may take over by hand after failed rebuilds: **after two failed rounds, stop and ask for one concrete example** rather than rebuild again.
- A community extension or preset can look helpful and still needs a source review before use.

### Assumptions

- The pilot is read-only with respect to live editing projects.
- Agents keep using the workspace memory, the agent instruction files and the session folders as their primary continuity system.
- Spec Kit is an added specification and gate layer, not the project manager.

---

## Condensed plan

| Item | Content |
|---|---|
| Summary | A documentation layer plus a read-only validator that brings spec discipline to agent work without mutating live projects or replacing the session protocol. |
| Technical context | Workspace process pilot; Python standard library for the validator; local filesystem only; read-only checks by default – no project writes, no uploads, no publishing. |
| Constitution check | Each of the six principles (see [the constitution](spec-kit-constitution.md)) mapped to how the plan satisfies it: evidence before narrative → session checks and conflict warnings; protected originals → read-only validator; timing serves comprehension → the agent-facing timing gate; session truth → session updates with authorship markers; local-first safety → a warning on workflow shell steps; verified before done → validator runs before any “ready” claim. |
| Rollout | Keep the pilot isolated; use the gate document before the next training-video revision; run the validator before claiming process work is ready; consider root initialisation only after a separate clean-baseline review. |

## Task outline

| Phase | Tasks |
|---|---|
| 1. Setup | Initialise an isolated pilot folder · write the pilot constitution · write this feature spec |
| 2. Research and design | Read the official Spec Kit documentation (workflows, integrations, presets, existing-project guidance) · inspect the editing-style references and current watched-session evidence · define the gate entities and the validator’s command-line contract |
| 3. Implementation | Write the agent-facing gate document · write the routing guide · build the read-only validator (`--json`, `--test`; exit 0 = no failures, 1 = failures, 2 = self-test error) · add a workflow overlay for the pre-flight |
| 4. Verification and memory | Run the validator’s self-tests and live checks · update memory, index, tool catalogue and session log · report findings, sources and remaining cautions to the owner |

---

Related: [spec-driven AI work](../spec-driven-ai-work.md) · [consistency-gates checklist](consistency_gates_checklist.md) · [Spec Kit constitution (pilot)](spec-kit-constitution.md) · [training action map template](training_action_map_template.csv) · [training-video production](../training-video-production.md)
