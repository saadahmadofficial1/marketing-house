# The Claude Code layer: agents, skills and hooks

This folder is the Claude Code customisation layer of the kit: one sub-agent that reads its taste spec before deciding anything, two skills that package a method so it fires on the right request, and two hooks that keep the agent on its rules every turn and after every context compaction. It is the part of the workspace that shapes *how* Claude Code behaves; the tools that do the work are in [`../../tools/`](../../tools/README.md).

---

## What is here

| Asset | What it does | Maturity |
|---|---|---|
| [`agents/senior-video-editor.md`](agents/senior-video-editor.md) | A sub-agent for every editing decision or build. Before deciding anything it reads the owner’s taste spec – the editing grammar, the approved masters, the corrections log – and works to a fixed authority order: approved final export first, automatic analysis last. | **Built, in use** in my own workspace; this is a generic copy |
| [`skills/training-video-pipeline/SKILL.md`](skills/training-video-pipeline/SKILL.md) | The screen-recorded training-video method as a skill: the fixed replacement-voice order, the INSERT pipeline, the traps, and a job-to-tool table. The description line is written in the words people actually use (“the box is in the wrong place”, “CapCut says media is missing”) because that line is what makes a skill fire. | **Built, in use** (generic copy) |
| [`skills/engineering-method/SKILL.md`](skills/engineering-method/SKILL.md) | Routes coding, debugging and automation work through the evidence-first engineering method, scaled to risk, and stays out of ordinary creative work. | **Built, in use** |
| [`hooks/discipline.sh`](hooks/discipline.sh) | Runs on every prompt (`UserPromptSubmit`): injects eight operating rules (log in real time, verify before generating, check before building, reuse scripts…) and, when the session transcript has grown enough, asks for a checkpoint via `sa_checkpoint.py --due`. | **Built, in use** |
| [`settings.example.json`](settings.example.json) | The hooks block only: `discipline.sh` on every prompt, and `sa_compact_brief.sh` on `SessionStart` with the `compact` matcher – the post-compaction ground-truth brief. | **Built, in use** |

**A skill is a method, not a permission.** Neither skill grants authority to create branches, spawn agents, install anything, publish, upload data or change external systems; the workspace’s own rules and the human approval steps still apply.

---

## Install

1. Copy this `.claude/` folder into the root of your workspace.
2. Rename `settings.example.json` to `settings.json` (or merge its `hooks` block into your existing settings). It contains hooks only – no permission rules; add your own allow-list deliberately, never from someone else’s file.
3. Copy [`sa_checkpoint.py`](../../tools/sa_checkpoint.py) and [`sa_compact_brief.sh`](../../tools/sa_compact_brief.sh) from `../../tools/` into the workspace’s `Tools/` folder and make the shell script executable (`chmod +x`).
4. Check the paths. Both scripts, and the checkpoint call inside `discipline.sh`, assume the workspace lives at `~/Documents/Claude` with a Python virtual environment at `Tools/venv/`. Edit the `ROOT` lines if yours differs.
5. Restart Claude Code in the workspace and send any prompt, then check the transcript view (or ask the agent which operating rules it was just given) to confirm the rules block arrived. Run `/compact` once and confirm the “POST-COMPACT GROUND TRUTH” brief was injected.

**Known gap in the compact brief.** It also calls [`sa_threads.py`](../../tools/sa_threads.py) and [`sa_doctor.py`](../../tools/sa_doctor.py) with errors suppressed. If `sa_doctor.py` is missing, its section prints “all green” – a false green. Install both tools, or delete those two sections from your copy.

---

## An honesty note on hooks

A hook that injects the same rules every turn helps consistency – the agent sees them fresh, even deep into a long session. It does not stop repeats. When I had the agents audit every recorded mistake, **no written rule – hook-injected, logged or restated – had ever stopped a repeat; only code that refuses had.** So the hook is a reminder, and the real guards live in tools ([`sa_guard.py`](../../tools/sa_guard.py) refuses writes while the editor is open or to signed-off work). The full post-mortem is in [learning from mistakes](../../playbooks/learning-from-mistakes.md).

The same logic drives the compaction hook. A compaction summary can drop details; the brief re-reads the truth from disk the instant the compacted session starts – the active session state, open threads, checkpoints written while the detail was still in view, red lights from the health check – so the summary becomes a convenience rather than a single point of failure.

---

## Third-party skills I use but do not ship

Credit only – none of their code is in this repository:

- the document skills (Word, PowerPoint, Excel, PDF) from Anthropic’s public [skills repository](https://github.com/anthropics/skills);
- a design-skill set: [UI/UX Pro Max](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill) (its free, data-only skill), [impeccable](https://github.com/pbakaus/impeccable), [Emil Kowalski’s skills](https://github.com/emilkowalski/skills) and [taste-skill](https://github.com/leonxlnx/taste-skill);
- a set of engineering slash-commands (diagnose, tdd, triage and similar);
- the [ponytail](https://github.com/DietrichGebert/ponytail) “simplest working solution” plugin and a [video-watching plugin](https://github.com/bradautomates/claude-video).

The vetting rule behind that list is in [security and data policy](../../playbooks/security-and-data-policy.md#5-how-third-party-ai-tools-are-vetted).

---

Related: [running two AI agents](../../playbooks/running-two-ai-agents.md) · [learning from mistakes](../../playbooks/learning-from-mistakes.md) · [how I engineer with AI coding agents](../../playbooks/ai-engineering-method.md) · [training-video production](../../playbooks/training-video-production.md) · [kit start page](../README_START_HERE.md)
