# Consistency gates: a pre-flight checklist for any agent task

Eight gates an AI agent passes before it plans, edits or claims “done” – written for the moment a model hits a limit and another one picks the work up, or for when narration, picture and call-outs in a training video start drifting apart. They came out of a spec-driven pilot ([spec-driven AI work](../spec-driven-ai-work.md)); gate 3 and gate 4 are specific to screen-recorded training videos, the rest apply to any task. A read-only validator was built alongside them – [`sa_consistency_gate.py`](../../tools/sa_consistency_gate.py), tied to its own folder layout, so treat it as an example of “your consistency-gate script”.

**Maturity:** **Pilot** – written and used during one spec-driven pilot; not yet routine.

---

## Gate 0 – Resume current truth

- [ ] Load the memory briefing, if there is one.
- [ ] Read the session pointer, then the active session’s state file and the end of its log.
- [ ] Read only the reference files this task needs.
- [ ] For substantial automation, read the loop-constraints file (attempt limits, kill switch, never-overwrite list).
- [ ] Say the current project, last step and next step in one line.

**Session state wins over memory until the two are reconciled.** If they disagree, say so before doing anything.

## Gate 1 – Build an evidence ledger

Name the files behind the plan, and make no claim about a button, a status, a timing or an edit without a source in this list:

- [ ] source recording or raw clip;
- [ ] editing project – or the duplicate being worked on;
- [ ] current export, if any, with the exact timeline, export range and file identity pinned;
- [ ] captions, voice-over script, subtitle file or timing table;
- [ ] frame index, timeline events, manifest and learning notes from any watched session;
- [ ] the reference documents the plan relies on.

## Gate 2 – Classify the work

Pick the process depth:

| Class | Process |
|---|---|
| Revision of a screen-recorded training video | Always gates 3 and 4. |
| Reusable tool or workflow | A spec, plan and tasks – or a written exception saying why not. |
| Creative one-off | A lighter brief, still under brand, memory and evidence rules. |
| Research | Source-backed claims; limitations recorded. |
| Destructive or publishing action | Explicit human approval, per action. |

## Gate 3 – Action coverage (screen-recorded training)

Build an action map before editing (template: [`training_action_map_template.csv`](training_action_map_template.csv)):

- [ ] every primary button press gets its own beat;
- [ ] every navigation click, field entry, role switch, save, status change and verification gets a beat – or an explicit, written exclusion;
- [ ] the exact visible wording is used when the screen shows it;
- [ ] button actions are short imperative lines;
- [ ] any line that says “do X, then Y” is split into two beats at the action;
- [ ] no stretch of the source is skipped without walking its frames for actions;
- [ ] sign-ins show the account row being chosen, not just the search box.

If the map cannot prove coverage, stop and ask for the missing source or one concrete example.

## Gate 4 – Timing serves the viewer

The raw recording is evidence, not pacing law:

- [ ] busy content screens at 1.0–1.2× at most;
- [ ] review and comprehension moments at 1.0× or slower;
- [ ] stable frames frozen for 1–3 s when the narration needs room (layered stills where the editor allows);
- [ ] call-outs on a moving screen held about 1.5–2.1 s; full-line explanations only on a frozen screen;
- [ ] captions, voice, call-out and screen movement share the same action beat;
- [ ] after any re-pace, every call-out box re-proved on the actual final frame.

Compression is allowed only when it makes the story clearer. If the viewer cannot follow the step, it is too fast.

## Gate 5 – Name evidence conflicts before planning

The trap, in general form: **a stale artefact from an earlier failed run disagrees with the current manifest.** In the pilot, a summary file left by a failed first pass reported a fraction of the events and frames that the current manifest, frame index and learning notes recorded; an agent that read it first would have made confident, wrong claims about coverage.

- [ ] Read the manifest, the event log, the frame index and the notes together.
- [ ] If their counts disagree, name the conflict and which source wins – before planning.

## Gate 6 – Stop conditions

Stop instead of improvising when:

- [ ] the source clip, project file or export is missing;
- [ ] evidence counts conflict and cannot be reconciled;
- [ ] a call-out target cannot be proven on the final frame;
- [ ] the edit would touch an original or the owner’s working cut;
- [ ] an upload, publish, delete, overwrite or other destructive command is needed without approval;
- [ ] two rebuild attempts have failed – ask the owner for one concrete example, then adjust from that.

## Gate 7 – Verification before “done”

- [ ] Run the relevant tests or validators – including your consistency-gate script (`--json`), if you have one.
- [ ] Update the session state and append to the log.
- [ ] Update memory or reference files if new reusable learning came out of the task.
- [ ] Say what was verified **and what was not**.

---

Related: [spec-driven AI work](../spec-driven-ai-work.md) · [example spec: agent consistency gates](spec-agent-consistency-gates.md) · [training-video production](../training-video-production.md) · [Spec Kit constitution](spec-kit-constitution.md) · [`loop_constraints.json`](loop_constraints.json)
