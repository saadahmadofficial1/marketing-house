# Engineering method — full version

The complete working method my AI coding agents follow for software, scripts, automations and integrations: route the work by risk, diagnose before fixing, build in checkable steps, and never call anything done without fresh evidence that matches the claim. The shorter, story-led version — with the real incident behind each rule — is [How I engineer with AI coding agents](ai-engineering-method.md).

It is packaged for Claude Code as a thin project skill, [`engineering-method/SKILL.md`](../workspace-kit/.claude/skills/engineering-method/SKILL.md), which routes coding work here and grants no extra authority. The guard rails are enforced in code by [`sa_loop.py`](../tools/sa_loop.py) (attempt ledger, three-attempt circuit breaker, kill switch and evidence-required completion, configured by [`loop_constraints.json`](templates/loop_constraints.json)), [`sa_guard.py`](../tools/sa_guard.py) (pre-flight refusals) and [`sa_doctor.py`](../tools/sa_doctor.py) (one-command health check).

**Maturity:** Built, in use — the standing rule for all coding work in the workspace; the Spec Kit step is a pilot. This page was drafted by an AI coding agent (Codex) at my direction.

---

**Scope:** software, scripts, automations, integrations, data pipelines and repeatable system changes. Do not impose this full workflow on ordinary creative editing, copywriting, document formatting or one-off marketing production.

This method adapts the useful parts of OpenAI’s skill/plugin model and the Superpowers engineering workflow to my existing AI workspace. The workspace’s own instructions, data policy, session state, capability maturity and the user’s authority remain controlling.

## Route by risk

| Work | Route |
|---|---|
| Explanation, inspection or narrow low-risk edit | Work directly; verify the relevant claim or output. |
| Bug or failed automation | Use the diagnosis loop below before changing code. |
| Multi-file or reusable change | Write a concise design and implementation plan with exact files and checks. Use an isolated Spec Kit specification (pilot; see the [constitution template](templates/spec-kit-constitution.md)) when the change needs a durable specification. |
| Risky or experimental repository change | Offer an isolated git worktree. Never move active media projects into a worktree. |
| Independent tasks with no shared mutable state | Parallel agents may help when the harness and user authorise them. Define ownership and reconcile results. |

## Diagnosis loop

1. Reproduce the failure or establish that it cannot currently be reproduced.
2. Preserve the exact error, input, environment and relevant state.
3. Minimise the failing case and identify the first point where reality diverges from expectation.
4. Form a specific hypothesis and run the cheapest discriminating check.
5. Fix the root cause, not only the visible symptom.
6. Add a regression check proportional to the risk, then run nearby checks for collateral effects.

Use a diagnosis skill or command when one is installed. Keep the loop constraints ([`loop_constraints.json`](templates/loop_constraints.json), enforced by [`sa_loop.py`](../tools/sa_loop.py)) and the three-attempt circuit breaker binding for automation.

## Build loop

For deterministic code, prefer red-green-refactor when a useful failing test can be written: observe the failure, make the smallest correct change, then improve structure while tests remain green. Do not create meaningless tests merely to satisfy the sequence. Media taste, visual judgement, generated assets and fragile external-app behaviour require rendered or application evidence instead of pretending unit tests prove them.

For substantial changes:

1. Confirm the intended outcome, exclusions and acceptance evidence.
2. Inspect existing code, tools and memory before inventing a new abstraction.
3. Break implementation into independently verifiable units with exact file ownership.
4. Implement in bounded steps and preserve unrelated user changes.
5. Review specification compliance first, then code quality and maintainability.
6. Finish only after fresh verification and an explicit handoff.

## Verification before completion

A completion statement must be backed by evidence from the current result, not an earlier run or the agent’s confidence. Match evidence to the claim:

- Code behaviour: focused test plus relevant broader checks.
- Bug fix: original reproduction no longer fails and regression check detects recurrence.
- Website/UI: rendered browser checks at relevant viewports, console errors and interaction states.
- Media pipeline: generated file inspection plus render/application checks required by its maturity level.
- Automation: execution record, failure path and recovery evidence; configuration alone is not proof it ran.
- Documentation: links, syntax and factual claims checked against current sources.

Report unknown, skipped and blocked checks plainly. Never use passing documentation generation, a tool count or a global readiness score as proof that an individual capability works. Update the canonical session state and log with the evidence (the session files are described in [Running two AI agents in one workspace](running-two-ai-agents.md)).

## Review and finish

Review in this order:

1. **Requirements:** Does the result meet the actual request, including exclusions and safety rules?
2. **Quality:** Are there correctness, security, maintainability, performance or usability problems?

Critical requirement failures block completion. At branch finish, present the real state and let the user choose whether to merge, open a PR, keep the branch or discard it; do not infer permission for those actions.

## Sources and boundaries

- OpenAI Skills Catalog: https://github.com/openai/skills — deprecated; retained only as background. OpenAI now directs users to the Plugins repository.
- OpenAI Plugins: https://github.com/openai/plugins — current packaging examples for skills, agents, hooks, apps and MCP configuration.
- Superpowers: https://github.com/obra/superpowers — inspiration for systematic debugging, planning, TDD, review and verification. Its complete mandatory workflow is not installed or copied wholesale.

External repositories are references, not trusted runtime dependencies. Review source and licensing before importing any code, hook or plugin; the rules for that review are in [Security and data policy](security-and-data-policy.md).

---

## Related

- [How I engineer with AI coding agents](ai-engineering-method.md) — the short version, with the incident behind each rule.
- [Learning from mistakes](learning-from-mistakes.md) — why only checks that refuse, not written rules, stopped repeat failures.
- [Running two AI agents in one workspace](running-two-ai-agents.md) — the session state and log every handoff relies on.
- [Security and data policy](security-and-data-policy.md) — what may leave the machine, and third-party vetting.
- [`engineering-method/SKILL.md`](../workspace-kit/.claude/skills/engineering-method/SKILL.md) — the method packaged as a Claude Code skill.
- [`loop_constraints.json`](templates/loop_constraints.json) and [`sa_loop.py`](../tools/sa_loop.py) — the circuit breaker and kill switch in code.
