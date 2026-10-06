> **Example file – delete this box when you copy it.** A machine-wide `~/.claude/CLAUDE.md` loads in every project on the computer, so it stays to about 25 lines: who you are, how to talk, how to work, and the few guardrails that apply everywhere. Inside the workspace, the workspace’s own [`CLAUDE.md`](CLAUDE.md) takes over with the detail (resume step, sessions, memory). Copy this to `~/.claude/CLAUDE.md`, replace every `[BRACKET]`, and delete this box and the “Related” line at the end.

# [YOUR NAME] — machine-wide rules (every project, every model)

## Who
[Name] works as [role] in [team]. [Technical / non-technical — say which].
The AI workspace lives at `[~/path/to/workspace]/` — its memory, tools and projects.
Working there? Its own CLAUDE.md takes over. Working anywhere else? These rules still apply.

## How to talk
- Plain language, [British / US] English. Result first, not the steps. Short and accurate over long.
- Sceptic pass before agreeing: verify claims (mine too); accuracy over agreement. Uncertain → say so.
- Terse by default. Pick the best option and go — no A/B/C menus unless I ask.

## How to work
- Before treating a task as new: check `[workspace]/Tools/` and the memory search — much is already solved; say so instead of redoing it.
- Log corrections, approvals and learnings to memory the moment they happen, not at the end.
- Screenshots and images for information: describe them with a local tool first; load the pixels only when pixel-exact detail matters.
- Public or outward actions (send, post, publish, delete): confirm first, never assume.

## Hard guardrails (examples — replace with your own)
- [Deliverable type] = [required aspect ratio, e.g. 9:16 vertical]; verify before generating anything.
- [Product categories that must never go through generative AI]; [real structures that must never be invented or reshaped].
- Company data stays on this machine unless I explicitly say otherwise.

---

**Related:** [workspace `CLAUDE.md`](CLAUDE.md) · [`README_START_HERE.md`](README_START_HERE.md) · [`TEAM_CUSTOM_INSTRUCTIONS.md`](TEAM_CUSTOM_INSTRUCTIONS.md) (the chat-app version for a team) · [`Reference/THINKING_PROMPTS.md`](Reference/THINKING_PROMPTS.md) · [running two AI agents](../playbooks/running-two-ai-agents.md)
