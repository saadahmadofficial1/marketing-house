# Claude Code — ops cheatsheet (the bits that matter for us)

> On-demand. From the official troubleshooting page, filtered to the common pains (context burn, hangs, a misbehaving MCP/hook). Written for the Mac app — WSL/ripgrep-Linux/garbled-terminal sections dropped.

## Context fills fast / `/compact` burns tokens  ← our #1 pain
- **`/clear` is free, `/compact` is not.** `/clear` wipes context for a fresh start at zero cost; `/compact` re-reads everything to summarise = tokens. Prefer a fresh chat per task (the Sessions/ handoff makes that safe).
- **Targeted compact:** `/compact keep only the plan and the diff` — drops the big stuff instead of summarising all of it.
- **"Autocompact is thrashing" error** = a huge file/tool-output keeps refilling context right after compaction. Recover by: reading the big file in chunks (line range / one function), `/compact` with a focus that drops it, offloading that file's work to a **subagent** (separate context window), or `/clear` if the old chat is done.
- **Big file → subagent.** Anything that would flood context (huge logs, long files) → hand to a subagent so it stays out of our window.

## Usage limits — what actually burns the quota (support.claude.com, Jun 2026)
- **ONE shared limit across ALL surfaces** — Claude Code + desktop app + claude.ai all draw from the same usage budget. So any scheduled background routines compete with your own daytime usage → keep them lean.
- **Long conversations cost EXTRA:** once a chat is big enough to trigger auto context-management, that management itself consumes more of the limit — on top of the long context. Confirms our fresh-chat-per-task rule (not just cheaper, it dodges this surcharge).
- **Biggest burners:** higher effort level · extended thinking · tools/connectors (web search, Research, MCP). Counter all three: connectors off until needed, terse answers, extended thinking only when it pays.
- **Context window:** 200K standard / 500K enterprise tokens per conversation.
- Everything else in that article (short instructions, RAG/Projects, remove unused files, disable idle tools) = already our standing practice.

## Claude Code hangs / freezes
- Ctrl+C to cancel. If still dead, close the terminal and restart.
- **Conversation is NOT lost:** `claude --resume` in the same folder picks the session back up. (Pairs with our Sessions/ handoff — belt and braces.)

## Something feels off — find the culprit
- **`/doctor`** (inside Claude Code): one-pass check of install, settings, MCP servers, context usage. First thing to run when anything's weird.
- **High CPU/memory:** restart between big tasks; add large build dirs to `.gitignore`; `claude --safe-mode` disables all plugins/MCP/hooks for the session — if the problem vanishes, a customisation is the cause. 

---
*Source: code.claude.com troubleshooting page, 2026-06-28. Kept the context/compact + resume + safe-mode bits; skipped WSL, ripgrep-on-Linux, IDE-terminal glyph fixes (not our setup).*
