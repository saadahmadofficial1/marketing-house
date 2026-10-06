# Capability map — what fires when (so the owner never types commands)

> On-demand routing table: which skill, subagent or server to use for a task. Assume the owner would rather not toggle things. I detect the task and switch on what I can myself; for the few things only the owner can switch on, I say so in one line.
> Honest column = **who flips it**: 🟢 me, silently · 🟡 me, but tell the owner · 🔴 the owner only (I just point).

| Situation | Capability | Who flips it | Notes |
|-----------|-----------|--------------|-------|
| Any task | **Terse mode** (the BE TERSE operating rule) | 🟢 always on | The owner never has to ask for it. Short answers and the simplest working solution are the baseline. |
| Decision / draft / plan / copy | **Thinking-move** (steelman, critique, 3-version, blind-spot, clarify) | 🟢 | Auto-fires per the Sceptic Pass rule. |
| Build a deck / read a .pptx | **pptx skill** | 🟢 | Invoke Skill silently. Same for docx/xlsx/pdf when those files appear. |
| Logo / banner / brand visual / icon / slides | **design skills** (design, banner-design, canvas-design, etc.) | 🟢 | Pick the closest skill; don't ask which. |
| Big multi-file search / "where is X across the repo" | **Explore subagent** | 🟡 | Saves main-context tokens. Harness gates auto-spawn → I recommend it in a line, the owner says go. |
| Heavy/parallel/isolatable job | **subagent** | 🟡 | Same gate. Offer; spawn on "go". |
| Risky/experimental change | **git worktree** isolation | 🟡 | Offer when a change could break working state. |
| Repetitive "every time X do Y" automation | **hook** (settings.json) | 🟡 | Persistent config → I set it up but confirm first (it's standing config). |
| Recurring/scheduled job | **scheduled task / cron** | 🟡 | Confirm before creating standing schedules. |
| Need an app connector (design, video, browser, computer use…) | **that MCP server** | 🔴 | Best kept off until needed, as each one costs context. I name which one to switch on in the Claude app → Connectors; I can’t toggle it. |
| Need a third-party MCP server that is switched off | **parked server** | 🔴 | The owner re-enables it in the Claude Code settings and restarts. |
| Company fact / past decision / brand detail | **brain** (`sa_search` / `sa_briefing`) | 🟢 | Optional server in `brain/` (see its SETUP.md). Falls back to grep on *.md if it is not set up or is stuck. |
| Context filling up | **fresh chat + Sessions/ handoff**, not /compact | 🟢 | /clear free, /compact costs. See CLAUDE_CODE_OPS.md. |
| Giant file would flood context | read in chunks / **offload to subagent** | 🟡 | Keeps the big dump out of our window. |

## Rules of the autopilot
- **Self-activate silently** what's in 🟢. Don't narrate "I'm now using the X skill" — just do it and give the result.
- **One line, then proceed** for 🟡 — offer the better path, don't stall waiting unless it's standing config (hooks/schedules) or risky.
- **Point, don't pretend** for 🔴 — I cannot turn on app-connector MCPs or restart Claude Code. Name the exact toggle, keep going with what I can do meanwhile.
- **Never bloat to look busy.** The point is fewer tokens + right tool, not more tools. If plain chat answers it, no skill/subagent/server.

---
*Distilled from the Claude Code docs into a routing table instead of storing every page. Update a row when a real case proves it wrong.*
