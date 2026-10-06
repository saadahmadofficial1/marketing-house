# Workflows: multi-agent scripts

Seven scripts that fan work out to many AI sub-agents and check the results independently – research sweeps, mistake mining, a five-lens pre-release review, per-item adversarial verification, and a read-only safety check before deleting files. They are written for **Claude Code’s workflow runner**, which supplies the globals `agent()`, `parallel()`, `pipeline()`, `phase()`, `log()` and `args`; they are **not** standalone Node programs and will not run with `node`. The method behind them – when to fan out, which shape, and the honest limits – is in [orchestrating agent fleets](../playbooks/orchestrating-agent-fleets.md).

Like everything here, the scripts were written by AI coding agents under my direction; I set the questions, the checks and the bar for “done”.

---

## The scripts

| Script | What it does | Phases | Edit before running | `args` | Maturity |
|---|---|---|---|---|---|
| [`research-fanout.js`](research-fanout.js) | One researcher per “pillar” (memory, tools and skills, workflows, scheduling, feedback loops, guardrails) sweeps the open-source ecosystem with web search, judged against what already works; a synthesiser writes a do-now / do-later / install / reject memo. | Research → Synthesise | `OURS` (a frank description of what you already run, and your house rules – most candidates should lose against it) and `PILLARS` (one entry per research area). | none | **Built** – run once (August 2026); research fan-outs in general are in regular use |
| [`frameworks-intel.js`](frameworks-intel.js) | Reads a list of named projects and their most-discussed open **and** closed issues (desk research, install nothing), returns a structured record per project, then one decision memo across the field. | Research → Judge | `GROUPS` (two or three targets per agent; names in brackets are hints the agent must verify) and `CONTEXT` (who the verdict is for and what they already have). | none | **Built** – run once (August 2026) |
| [`adversarial-verify.js`](adversarial-verify.js) | One checker per call-out marking reads the marking’s start and end frames and files faults by kind (screen, target, chip, script) and severity; every **major** fault then faces three independent refuters who measure the pixels. A fault is dropped only if at least two refuters demonstrate it wrong. | Check → Verify | The `ask()` and `refute()` prompts: the marking’s look and the layout facts are specific to one series. | `{a: {dir, items: [{name, purpose, phrase}]}, b: {…}, contentX?}` – frames named `<name>_S.png` and `<name>_E.png` in each `dir`; `purpose` is the label text, `phrase` the narration over it; `contentX` (default 248) is where page content starts. | **Built, in use** – the same check-then-refute shape ran on several verification fleets, the largest over 300 agents |
| [`mistake-mining.js`](mistake-mining.js) | Readers excavate every recorded mistake era by era, each with root cause, cost and whether a *systemic* guard exists today; a second agent groups them into recurring patterns; an auditor writes the scoreboard and the top missing guards. | Excavate → Pattern → Audit | `SOURCES` (where your corrections and logs live) and `ERAS` (one brief per period of your own history). | `{root}` – the workspace root (required) | **Built** – run once, August 2026 |
| [`fix-log-mining.js`](fix-log-mining.js) | Mines trap lists, mistake patterns, escaped-defect notes, the worklog and failure comments in code into a fast-lookup fix log; a verifier then opens each claimed guard in the code and its self-test and grades it *exists-and-tested*, *exists-untested*, *claimed-but-absent* or *none*. | Mine → Verify guards | `SOURCES` (the files to mine – names will differ in your workspace). | `{root}` – the workspace root | **Built** – run once, August 2026 |
| [`five-lens-review.js`](five-lens-review.js) | Five reviewers judge one artefact independently – a first-time user, an IT security reviewer, a hostile sceptic, the same user three months later, and a completeness critic – then one agent ranks the fix list: must fix, should fix, reject. | Critique → Rank | The file names inside each lens prompt. | `{kit}` – the folder under review (required) | **Built** – run before a starter kit was shared with colleagues; a later adversarial review of this portfolio used the same idea |
| [`pre-delete-safety-check.js`](pre-delete-safety-check.js) | Before anyone deletes duplicates: two guards write protected-file lists (files editing projects still reference; inputs live work still uses), two checks hunt false positives in the duplicate lists, and two sceptics per result try to refute it. Read-only; the owner deletes. | Guard → Check → Refute | Nothing – driven entirely by `args`. | `{dir, out, exact, renamed, local, projects?, workspace?, rules?}` – see the header comment | **Pilot** – the original ran once before a real clean-up; this generic rewrite has not itself been run |

Each returns plain JSON: `research-fanout` → `{report, pillars}`; `frameworks-intel` → `{projects, verdict}`; `adversarial-verify` → per-side counts of checked, perfect, confirmed and dropped majors, plus the faults; `mistake-mining` → `{document, mistakeCount, guardless}`; `fix-log-mining` → `{fixes, verdict}`; `five-lens-review` → `{findings, ranked}`; `pre-delete-safety-check` → one record per task with its result, both votes, `refuted_by` and `stands`.

---

## Two design rules every script follows

1. **Structured returns at every fan-out.** Each researcher, checker and refuter must return JSON that matches a schema – a failure is visible instead of subtly malformed prose, and an agent that returns nothing is recorded as a failure, not a quiet zero. Only the single synthesis or ranking agent at the end returns prose.
2. **Checkers never see the maker’s reasoning.** A verifier gets the artefact and the claim – the frames, the files, the finding – never the chain of thought that produced it. A model shown its own working agrees with itself. Refuters are told to *refute*, measure rather than guess, and treat “probably fine” as no refutation.

## An honest note on privacy

Sub-agents run on the hosted model, so **whatever a sub-agent reads is processed by that model’s provider** – frames, documents, file paths, the lot. Use these scripts only on material cleared for that, or point the agents at a local model. In my own work, screen frames never go to generation services and routine checks run locally; the large one-off verification passes used hosted AI coding agents.

## Running one

In Claude Code, ask for the workflow to be run and give the script and its `args` as JSON values (an object or array, not a JSON-encoded string). Concurrency is capped by the runner, so passing a hundred items is fine; they queue. Read the result before acting on it – a refuted finding is not proof the item is fine, only that this finding did not survive.

Credit: the runner, its `agent()` / `pipeline()` / `parallel()` API and the structured-output mechanism are Claude Code’s.

---

Related: [orchestrating agent fleets](../playbooks/orchestrating-agent-fleets.md) · [the agent organisation](../playbooks/agent-organisation.md) · [learning from mistakes](../playbooks/learning-from-mistakes.md) (what mistake mining found) · [repository due diligence](../playbooks/repo-due-diligence-2026.md) (what the research fan-outs found) · [`workspace-kit/AGENT_ORCHESTRATION.md`](../workspace-kit/AGENT_ORCHESTRATION.md)
