# The agent organisation

A one-page front door to the agent-organisation handbook that ships in the workspace kit: how to run a set of AI agents like a small company – departments with charters, work that flows between them, gates nobody may bypass, and a loop that changes defaults when the same correction keeps arriving. The full handbook is [`workspace-kit/AGENT_ORCHESTRATION.md`](../workspace-kit/AGENT_ORCHESTRATION.md), with 72 role definitions in [`ROLES.md`](../workspace-kit/ROLES.md) and six half-page [charters](../workspace-kit/charters/); the patterns that actually ran, with their scripts, are in [orchestrating agent fleets](orchestrating-agent-fleets.md).

The handbook was drafted by AI agents from my working records, under my direction and review.

---

## The problem it solves

One agent that does everything – makes the thing, checks the thing, decides the thing is good – approves its own work every time. Not from dishonesty: it has seen its own reasoning, and a model shown its own working agrees with itself. Spawning more agents does not fix that. Deciding **who owns what, who may approve what, and how anyone knows a thing was done** does – which is an organisational problem, and organisations solved it long ago. Copy the organisation, not a framework.

## The ideas, in brief

| Idea | What it means |
|---|---|
| **Six departments, half-page charters** | Program Office (plan, queue, deadline), Platform (tools, backups, guards), Studio (the creative work), Knowledge (memory), Quality (independent verification), Security (veto over anything leaving the machine). Each charter says what it owns, what it may **not** do, the gates it enforces and where it escalates. |
| **The unit of work** | Never “improve the report”. Always `JOB` (one outcome you could photograph) · `INPUT` (exact paths) · `OUTPUT` (the file that will exist) · `CHECK` (the thing that proves it worked) · `OWNER`. **No job without a written CHECK** – every silent failure starts with a job that had none. |
| **A worklist and an append-only ledger** | The queue is written *before* work starts; verdicts are appended *after* Quality returns one. Resume, never restart: skip what is `ok`, continue at the first that is not. A correction is a new line, never a rewrite. |
| **Five fan-out shapes** | By independent item; by lens rather than item; pipeline rather than batch; loop until dry; a completeness critic at the end. Detail in [orchestrating agent fleets](orchestrating-agent-fleets.md#2-five-fan-out-shapes-in-order-of-value). |
| **The hand-off receipt** | What the next session reads first: the checks that **actually ran**, what passed, what failed, what is unknown and why, what stays open, and the single next action. A receipt that always says “all good” is decoration. |
| **ok / wrong / unknown** | Three outcomes, never two. **Unknown is never a pass** – a check that could not run, or a refusal that contains no complaint, is not a success. |
| **The maker never verifies its own work** | Verification runs in a fresh context with the artefact and the check only, never the reasoning that produced it. |
| **The correction loop** | Capture every correction the same minute. **Measure, don’t remember** (“9 of 9 times they shortened it, median 2.1 where I made 3.1”, not “they sometimes prefer shorter”). **The rule of three:** a correction that recurs three times is not taste – it is your wrong default; change it in code, once, with the evidence in a comment. **Taste versus defect:** a different valid choice is the owner’s preference and is recorded, not “fixed”; only being wrong is chased. |
| **Roles per job, retired when idle** | Roles are short job descriptions spawned one per item and gone afterwards – never a standing army. One role, one output, one check; a role never checks its own output; a role that has not fired in about eight weeks is deleted. |

---

## What is real and what is guidance

| Piece | Status | Evidence |
|---|---|---|
| Fan-out with schema-validated returns | **Built, in use** | Fleets of 100+ independent reviewers on screen-recorded training videos, one agent per call-out marking; the scripts are in [`../workflows/`](../workflows/README.md). |
| Independent, fresh-context verification with ok / wrong / unknown verdicts | **Built, in use** | The same fleets (majors re-checked by three refuters); the August mistake post-mortem, which found 76 mistakes in 16 patterns ([learning from mistakes](learning-from-mistakes.md)); and the leak audit of this portfolio, where an adversarial review still found 167 issues after the automated blocklist scan had passed. |
| The correction loop (measure, rule of three) | **Built, in use** | Editing defaults moved from measured corrections; see [learning an editor’s style](learning-an-editors-style.md). |
| Hand-off receipts | **Built, in use** in prose form (session state and log); **Planned** as machine-readable receipts with checksums | [running two AI agents](running-two-ai-agents.md#maturity) |
| Six departments with charters, run as a standing organisation | **Planned** – the handbook and charters are written; they have not been run day to day | [`AGENT_ORCHESTRATION.md`](../workspace-kit/AGENT_ORCHESTRATION.md), [charters](../workspace-kit/charters/) |
| The 72-role catalogue | **Planned** as a catalogue – individual roles were used inside fleets; the catalogue itself has not been run with its decay rule | [`ROLES.md`](../workspace-kit/ROLES.md) |
| The daily rhythm (start, plan, work, check, fix, learn, close) | **Planned** – guidance only | [`AGENT_ORCHESTRATION.md`, part V](../workspace-kit/AGENT_ORCHESTRATION.md) |

The honest summary: the parts that touch every job – structured fan-out and independent checking – are real and have run on large fleets. The parts that describe a standing organisation are a design I have written down and not yet operated.

## Where to start

Thirty minutes, from the handbook’s own set-up: six half-page charters, an empty worklist, ledger and corrections file, three jobs each with a CHECK line, one job done and verified in a fresh context, one receipt written. Add nothing else until something actually hurts – then add the smallest file that fixes it, never a framework.

---

Related: [orchestrating agent fleets](orchestrating-agent-fleets.md) · [`AGENT_ORCHESTRATION.md`](../workspace-kit/AGENT_ORCHESTRATION.md) · [`ROLES.md`](../workspace-kit/ROLES.md) · [charters](../workspace-kit/charters/) · [running two AI agents](running-two-ai-agents.md) · [how I engineer with AI coding agents](ai-engineering-method.md) · [learning from mistakes](learning-from-mistakes.md)
