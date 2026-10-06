<!--
Sync Impact Report (done by codex)
Version: 1.0.0
Ratified: 2026-09-05
Last amended: 2026-09-05
Scope: Studio Spec Kit pilot, Claude consistency gates, CapCut training-video timing guardrails, and reusable workflow/tool changes.
Template sections replaced: all placeholders removed.
Follow-up required: Root workspace Spec Kit init remains deferred until the Studio workspace has a clean reviewable baseline.
-->

# Studio Spec Kit Pilot Constitution

## Core Principles

### I. Evidence Before Narrative
Every Studio task starts from current evidence, not memory vibes. Agents MUST read the active session state/log, relevant Studio memory references, and named source files before making implementation claims. If evidence conflicts, the agent MUST state the conflict and resolve it before proceeding. UI actions, button labels, timeline timings, and tool states MUST NOT be invented.

Rationale: Recent CapCut training-video issues came from plausible but unverified narration and skipped UI beats.

### II. Protected Originals
Original CapCut projects, raw media, final masters, and the editor's own working cuts are immutable unless the editor explicitly authorizes a destructive edit. Revision work MUST use duplicates, review exports, support files, or documented plans. Any direct-editing workflow MUST prove the target file is a duplicate or scratch artifact first.

Rationale: Studio video work is production work; one accidental overwrite can destroy hours of editorial judgment.

### III. Timing Serves Comprehension
Training videos are paced for the learner, not for the speed of the raw screen recording. Agents MUST build a timing plan before editing: narration, captions, callouts, freezes, and screen movement must line up. Busy content screens should stay at or below 1.2x, review moments at or below 1.0x, and stable-frame pauses/freezes MUST be added when the voice needs more time. Compound narration lines MUST be split at real action boundaries.

Rationale: One module's failure mode was not just speed; it was voice, visual, and callout timing drifting apart.

### IV. Studio Memory And Session Truth
`Sessions/state.json` is the live truth for ongoing work, `log.jsonl` is the append-only history, and Studio Brain/memory references are the long-term institutional record. Every Codex-authored traceable addition to session state, worklogs, specs, and reference docs MUST include `(done by codex)`.

Rationale: Saad switches between Claude and Codex mid-task. The system must preserve continuity without asking him to repeat context.

### V. Whole-System Scope, Local-First Safety
Spec Kit applies wherever a repeatable Studio workflow benefits from clear intent, plans, tasks, gates, and verification. It is not limited to CapCut. Source media and screen recordings MUST NOT be sent to generation services, and routine checks run locally; any other upload needs Saad's approval for that specific upload. Shell workflow steps, community extensions, bundles, and presets MUST be source-reviewed before adoption.

Rationale: Spec Kit can improve video, automation, design, research, and tooling work, but only if it respects Studio safety rules.

### VI. Verified Before Done
An agent may only call work complete when outputs exist, relevant tests or validators pass, evidence counts are current, limitations are recorded, and session/memory updates are done. If verification is incomplete, the agent MUST say what remains unverified.

Rationale: "Looks done" is not enough for a cross-agent production system.

## Operational Rules

1. Existing Studio projects MUST NOT be reinitialized with Spec Kit until the root workspace has a clean, reviewable baseline.
2. Pilot artifacts live in `Projects/SA_SpecKit_Pilot/` and do not replace `AGENTS.md`, `CLAUDE.md`, Studio Brain, or the `Sessions/` protocol.
3. Reusable Studio tools, workflow changes, and cross-project process changes SHOULD receive a Spec Kit feature spec, plan, tasks, and verification record.
4. One-off creative outputs may use a lighter brief when the work is not reusable, but CapCut training-video revisions still require timing and action gates.
5. Community extensions, presets, bundles, and workflow shell steps are untrusted until source-reviewed.
6. Any contradiction between source media, CapCut project state, session state, and memory must be treated as a blocker until reconciled.

## Governance

This constitution is authoritative for the Studio Spec Kit pilot. Amendments require an explicit Studio-approved change, a version bump, a dated impact note, and updates to affected specs/plans/templates. Root-level Spec Kit initialization requires a separate decision after confirming the Studio workspace is safe to mutate. Versioning follows semantic intent: major for principle changes, minor for new operational rules, patch for clarifications.
