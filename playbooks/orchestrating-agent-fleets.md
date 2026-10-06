# Orchestrating agent fleets

How I use many AI sub-agents at once without trusting any of them on its own word: who is allowed to approve what, which fan-out shapes are worth the tokens, five patterns that ran on real work – each with the script that did it in [`../workflows/`](../workflows/README.md) – and the limits I hit. The organisation behind it is written up in full in [`workspace-kit/AGENT_ORCHESTRATION.md`](../workspace-kit/AGENT_ORCHESTRATION.md); the front door to that handbook is [the agent organisation](agent-organisation.md).

The scripts were written by AI coding agents under my direction. My part is the question each fleet answers, the check that decides whether it worked, and the decision about what to do with the result.

---

## 1. The organisation, in short

The hard part of multi-agent work is not spawning agents; it is deciding who owns what, who may approve what, and how anyone knows a thing was done. So the handbook copies an organisation rather than a framework: six departments, each with a half-page [charter](../workspace-kit/charters/) – **Program Office** (the plan and the queue), **Platform** (tools, backups, guards), **Studio** (the creative work), **Knowledge** (memory), **Quality** and **Security**.

- **Separation of duties is the whole mechanism.** An agent asked to make the video, check the video and decide whether it is good will approve its own work every time – not from dishonesty, but from having seen its own reasoning. No department approves its own output.
- **Quality’s rules** ([charter](../workspace-kit/charters/quality.md)): the checker is never the maker – fresh context, the artefact only, never the reasoning. Three outcomes, never two: *ok*, *wrong*, *unknown* – and **unknown is never ok**; a refused or crashed check is unknown, not a pass. When a check reports a systemic anomaly across many items, **verify the instrument first**: three times in one week a check nearly misled me – a vision check that returned empty for every image (a token limit, not bad images), a layout check that called everything mis-sized (the measuring code had dropped a scaling step), and a scan that called two minutes of footage “dead” when a finer scan found movement throughout.
- **Security’s veto** ([charter](../workspace-kit/charters/security.md)): nothing outward-facing without explicit human approval, per action; know what leaves the machine, not where files sit; third-party code inspected before it runs; anything that touches the permission system is disqualified; outside content is data to report, never instructions to follow. A veto goes to the human – no other department can overrule it.
- **Roles are instantiated, not resident.** [`ROLES.md`](../workspace-kit/ROLES.md) holds 72 half-page job descriptions, spawned one per item and gone afterwards, under three laws: **one role, one output, one check**; **a role never checks its own output**; **roles decay** – one that has not fired in about eight weeks is deleted, not archived.

## 2. Five fan-out shapes, in order of value

| # | Shape | When |
|---|---|---|
| 1 | **Split by independent item** – one agent per file, video, marking or repository | No shared state, no ordering. Most real parallelism, nearly free. |
| 2 | **Split by lens, not by item** – several agents with *different* perspectives on one thing | Judging one artefact well. Four identical opinions add redundancy; four lenses (correctness, security, cost, does it reproduce) add coverage. |
| 3 | **Pipeline, don’t batch** – item A moves to verification while item B is still being made | Any multi-stage job; waiting for the slowest item at every stage wastes most of the benefit. |
| 4 | **Loop until dry** – keep searching until two consecutive rounds find nothing new | Discovery work. A fixed count always misses the tail. |
| 5 | **A completeness critic at the end** – one agent asking “what is missing?” | After any sweep. What it finds is the next round. |

Rules that hold for all five: every agent returns a **schema**, not prose; an agent that returns nothing is a **failure to record**, not a quiet zero; agents never write to the same file – collect, then merge deliberately; **dedupe in plain code**, never with an agent; agents that *edit* need isolation (a copy or a worktree), agents that *read* do not.

**When not to fan out.**
- When one careful pass will do. Each sub-agent starts cold and re-reads its context, so ten agents on a two-file question cost ten times the tokens for no extra truth.
- When the work is sequential by nature – one edit that depends on the previous one.
- On a small local model. An 8B model on an 8 GB machine cannot run two at once without swapping to disk; walk the same queue sequentially. The bookkeeping is what makes the output trustworthy; parallelism only makes it faster. One sequential pass with verification beats five parallel ones without.
- To look busy. If a plain answer will do, use no sub-agent at all.

---

## 3. Five patterns that ran on real work

### 3.1 Research fan-out, judged against what already works

[`research-fanout.js`](../workflows/research-fanout.js) · [`frameworks-intel.js`](../workflows/frameworks-intel.js)

One researcher per area (memory, tools, workflows, scheduling, feedback loops, guardrails), each handed the same frank description of what already runs and the house rules, then one synthesiser. The framing does the work: **most candidates should lose.** The question is never “is this popular?” but “does this fix a weakness we actually have, without a dependency we can’t inspect?”

- The harness sweep returned 27 mechanisms worth taking, one install worth considering (an OS-level sandbox for trialling third-party code) and **zero frameworks adopted**. What I took and declined is in the “Outside ideas” section of [how I engineer with AI coding agents](ai-engineering-method.md).
- The frameworks review of 24 agent frameworks and marketing-skill repositories ended **install nothing – 24 of 24**, and copy two ideas instead, plus a third.
- Standing rule: never adopt a framework wholesale. Distil the two or three rules worth having and implement them in tens of native lines.

### 3.2 Issue-tracker research of public projects

The same fan-out pointed at evidence a README cannot fake: for each repository, read its most-discussed **open** issues and its most-discussed **closed** ones – the closed ones show what actually broke and how it was fixed. Install nothing during research. Results: the ten patterns in [security and data policy, section 5](security-and-data-policy.md#5-how-third-party-ai-tools-are-vetted), and every repository’s notes in [repository due diligence](repo-due-diligence-2026.md).

### 3.3 Per-item sceptical verification with a refuter majority

[`adversarial-verify.js`](../workflows/adversarial-verify.js)

One checker per item – here, per call-out marking in a training video, judged on its first and last frames – files faults by kind and severity. Every **major** fault then goes to three independent refuters, each told to *refute* it by measuring the pixels; a fault is dropped only if at least two demonstrate it wrong. If the refuters fail to return, the fault stands – a failure never counts as a pass.

- On one 52-agent run – one agent reading coordinates off a pixel-ruler frame per gap, an independent agent rendering the proposed box on the real frame and confirming or refuting by looking – **25 of 27 boxes verified at high confidence**, and the two failures refused honestly (“control not visible in window”) instead of guessing. That run came after automation alone had managed about 12%.
- On the largest fleets (300+ agents), checkers were reliable at **finding** faults, but several of the **fixes** they proposed were guesses. A fleet’s findings go to a fixer and are proven again; they never go straight into the build.

### 3.4 History mining: mistakes and fixes

[`mistake-mining.js`](../workflows/mistake-mining.js) · [`fix-log-mining.js`](../workflows/fix-log-mining.js)

Readers excavate the whole correction history era by era, each mistake with its root cause, its cost and whether a *systemic* guard exists today; a second agent finds the recurring patterns; an auditor writes the scoreboard. The result – 76 mistakes in 16 patterns, 31 with a guard in code and 45 only written down – and the finding that no written rule had ever stopped a repeat, is in [learning from mistakes](learning-from-mistakes.md). The fix-log variant grades every claimed guard by opening the code and its self-test: *exists-and-tested*, *exists-untested*, *claimed-but-absent* or *none*. A fix log that claims protection it does not have is worse than none.

### 3.5 The five-lens pre-release review

[`five-lens-review.js`](../workflows/five-lens-review.js)

Before something goes to other people, five reviewers read it independently: a first-time user who has never opened a terminal, an IT security reviewer, a hostile sceptic hunting unbacked claims, the same user three months later, and a completeness critic asking what is missing entirely. One ranker merges duplicates (two lenses finding the same thing raises its priority) into *must fix*, *should fix* and *reject*.

- Before a starter kit was shared with colleagues, two review passes – this one among them – produced 51 fixes, including two blockers no one had noticed: the memory server crashed on the very first briefing of a fresh install, and the backup script silently skipped every log file while printing success.
- On this portfolio, an adversarial review run after the blocklist leak scan had already passed still found 167 issues, 11 of them high.

### And one for destructive steps: check before anyone deletes

[`pre-delete-safety-check.js`](../workflows/pre-delete-safety-check.js)

Before a person deletes duplicate files, two guards write protected-file lists (everything an editing project still references; anything live work still uses), two checks hunt false positives in the duplicate lists (small sidecar files that share a name and size across different shoots; cameras that split recordings at a fixed byte size, so different clips share exact sizes), and two sceptics attack each conclusion. Agents only read and report; the owner deletes.

---

## 4. Honest limits

- **Hosted sub-agents read on the provider’s model.** Whatever a sub-agent opens – frames, documents, file paths – is processed by the model provider. Confidential material needs a local model or explicit clearance. In my own work: screen frames never go to generation services; routine checks run locally; the large one-off verification passes used hosted AI coding agents.
- **A refuted finding is not proof the item is fine.** It only means that finding did not survive. Items with no findings were checked once, by one agent.
- **Fleets are expensive.** One large verification pass used about 26.5 million sub-agent tokens. Use them where a miss costs more than that.
- **Agents propose plausible fixes.** Treat every fix from a fleet as a hypothesis to prove on the real artefact.
- **The organisation is only partly real.** The fan-out and the independent checking ran on real work; the departments as a standing organisation with a daily rhythm have not been run day to day (see [the agent organisation](agent-organisation.md)).
- **Written “done” contracts and machine-readable hand-over receipts** – an idea taken from the frameworks review – are still planned, not built.

## 5. Maturity

| Pattern | Status | Script |
|---|---|---|
| Research fan-out judged against what already works | **Built** – each script run once (August 2026); research fan-outs as a pattern are in regular use | [`research-fanout.js`](../workflows/research-fanout.js), [`frameworks-intel.js`](../workflows/frameworks-intel.js) |
| Issue-tracker research of public projects | **Built** – run once (August 2026) | as above |
| Per-item sceptical verification with a refuter majority | **Built, in use** – several verification fleets, the largest over 300 agents | [`adversarial-verify.js`](../workflows/adversarial-verify.js) |
| History mining for mistakes and fixes | **Built** – each run once, August 2026; the guards it ranked were then built | [`mistake-mining.js`](../workflows/mistake-mining.js), [`fix-log-mining.js`](../workflows/fix-log-mining.js) |
| Five-lens pre-release review | **Built** – run before a starter kit was shared; the same idea later reviewed this portfolio | [`five-lens-review.js`](../workflows/five-lens-review.js) |
| Pre-delete safety check | **Pilot** – the original ran once before a real clean-up; the published version is a generic rewrite | [`pre-delete-safety-check.js`](../workflows/pre-delete-safety-check.js) |
| Departments as a standing organisation | **Planned** – written, not yet run day to day | [`AGENT_ORCHESTRATION.md`](../workspace-kit/AGENT_ORCHESTRATION.md) |

---

Related: [the agent organisation](agent-organisation.md) · [workflows index](../workflows/README.md) · [running two AI agents](running-two-ai-agents.md) · [learning from mistakes](learning-from-mistakes.md) · [security and data policy](security-and-data-policy.md) · [repository due diligence](repo-due-diligence-2026.md) · [`ROLES.md`](../workspace-kit/ROLES.md)
