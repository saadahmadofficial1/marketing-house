# Why AI agents forget – an audit of a multi-agent set-up

A personal set-up of several AI agents kept asking for facts it had already been told. The complaint was “it forgets”; the audit found that almost nothing was being forgotten – most of it had never been allowed to be remembered. This page gives the five causes, the evidence that proved each one, and the fix approach: safe configuration changes by a script that backs up first and skips anything unexpected, the rest applied by an agent from a checklist prompt, and a test that actually measures recall.

The script is published as [`templates/apply_safe_fixes.sh`](templates/apply_safe_fixes.sh). The memory design that avoids these causes in my own workspace is in [running-two-ai-agents.md, section 6](running-two-ai-agents.md#6-long-term-memory) and, as a portable specification, in [`AGENT_MEMORY_PROTOCOL.md`](../workspace-kit/Reference/AGENT_MEMORY_PROTOCOL.md).

---

## The set-up, in the abstract

Two always-on assistant agents, each with its own built-in memory, plus two coding agents and a shared folder of Markdown notes meant to be the common memory. The audit was run by a coding agent on a different machine, from a debug bundle of configuration files, logs and memory files – read-only, nothing changed during the audit itself.

The one-paragraph answer it produced: **memory saves had been failing silently for weeks; retrieval matched exact keywords only; the main agent had been switched to a weak free model by an old batch change; a nightly reset wiped the working context every day; and five memory stores disagreed about which was the real one.** Any one of these makes an agent look forgetful. Together they made it certain.

---

## The five causes

| # | Cause | Symptom | Evidence that proved it | Fix |
|---|---|---|---|---|
| 1 | A memory size cap silently rejecting saves | Facts told to the agent don’t persist; it asks again next day. | **Error log.** Every save for more than two weeks bounced with a line of the form *“memory would be at 2,780/2,200 chars – over the limit”* (and *1,562/1,375* for the user profile). The caps were the shipped defaults. The model almost never retried with a shorter entry, so nothing was written. | Raise the caps (here to 8,000 and 4,000 characters) in the configuration file; the agent reads overrides at start-up. Restart, then confirm a save lands. |
| 2 | Keyword-only recall | Even saved facts aren’t found unless the question repeats the stored wording – a fact saved under “notebook” is invisible to a question about “laptop”. | **Source code.** The memory plug-in retrieved candidates by SQLite full-text search first; its vector layer only re-ranked those candidates and was a hashed bag of words, not embeddings. Zero keyword hits meant zero results, whatever the vectors said. Its capacity also degrades past a few hundred items. | Make the shared Markdown notes the retrieval path – they already had a synonym layer and an index – and keep the agent’s built-in memory as a small scratchpad. A standing instruction: search the shared notes before answering anything about the owner, projects or history. Rebuild the index nightly; it was six days stale. |
| 3 | A silent downgrade of the main agent to a weak free model | The main agent ignores its own memory rules, re-asks, and gives thin answers. | **Configuration audit log.** A batch configuration file applied weeks earlier had set the main agent’s primary model to a free 20-billion-parameter model on a router – contradicting the agent’s own instruction file, which named a stronger model. The same drift broke a scheduled job, whose own error message said the global inference configuration had changed under it. | Restore the intended primary model, keep the free model only as the last fallback, and pin the scheduled job to an explicit provider and model so a global change can’t move it again. |
| 4 | A nightly session reset wiping working context | Everything learned during the day is gone the next morning. | **Configuration values.** A daily reset at a fixed late-evening hour, plus compaction starting at only 30% of the context window. Harmless when saves work – fatal when they don’t, because the reset destroys the only copy. | Fix cause 1 first; that is the real fix. Keep the nightly reset (it prevents context rot), and optionally start compaction later (50%). |
| 5 | Several competing memory stores, no single source of truth | Different agents give different answers, and none is complete. | **The files themselves.** Five stores; three of them claimed in writing to be the canonical one. The store one agent actually read was months old, had the wrong time zone and stale process IDs, and held a “free tier only” preference that probably inspired cause 3. Its daily memory files had stopped being written nearly two weeks earlier. | Declare one store the source of truth – the one with scopes, a validator and an indexer, which the agents’ own instincts already pointed at. Patch the others’ headers to redirect there; treat any note-taking app as a one-way, human-readable mirror, never read back as truth. |

### Found on the way – worth fixing, not the cause

- **Instruction fossils.** Both coding agents’ instruction files were near-identical snapshots from months earlier: a hard-coded dated notes file to read “for today”, start-up reads of files that probably no longer existed, and a model preference that contradicted the real configuration. Replaced with short, dateless files pointing at the one memory store.
- **Permissive agent settings.** One agent’s approval and access settings were looser than its work needed. Flagged for the owner to decide – not changed, because that is a security decision, not a memory fix. (More on this in [security-and-data-policy.md](security-and-data-policy.md).)
- **A state database that had gone malformed** weeks earlier, with a backup left behind. Check the live one: `sqlite3 <state.db> "PRAGMA integrity_check;"` should print `ok`.
- **Scheduled-job hygiene.** One job ran at the same hour as the session reset and hit rate limits; another timed out (934 seconds against a 600-second limit).
- **Upstream bugs** in the agent framework itself, logged on every session close. Reported, not patched – configuration can’t fix source code.

And what was healthy: the gateway, the scheduled jobs (mostly green), a secret scan of the debug bundle (no keys leaked), and a well-designed memory-scoping file with a validator – both kept as they were.

---

## The fix approach

### 1. Safe fixes by an idempotent script

Three configuration-only fixes were automated in [`templates/apply_safe_fixes.sh`](templates/apply_safe_fixes.sh): raise the memory caps, restore the intended model, and rebuild the shared index. The script’s rules matter more than its contents:

- **Back up before every change**, with a timestamp in the backup’s name.
- **Change only the exact expected line.** The caps are replaced only if the file contains the shipped default lines character for character; anything else is skipped with a ⚠️ and a note to edit by hand. Never guess at a file that has drifted.
- **Skip, never fail hard.** A missing tool or file is reported and the next fix runs.
- **Safe to run twice.** On a second run the expected lines are gone, so it skips.
- **Never touch credentials** – environment files, auth files and tokens are out of scope.

The template is written for the configuration keys of the two open-source agent frameworks that set-up used. Read it before running it, and change the keys and values for yours.

### 2. The rest, applied by an agent from a checklist prompt

Everything that needs judgement – replacing instruction files, patching memory headers, pinning a scheduled job, health checks – went into a prompt pasted into a coding agent on the target machine, with the full audit report beside it. A generic version:

```text
You are applying a reviewed fix pack to this machine's AI-agent set-up. The full audit is in
AUDIT_REPORT.md next to this file – read it first. Rules:

- Back up every file before touching it (copy to <file>.bak-fixpack-<date>).
- Never touch .env files, auth files, tokens or credentials.
- If a file doesn't match what a step expects, skip that step and report it – don't improvise.
- Apply the steps in order. After each step, run its verification.

Step 1 – <fix>. Verify: <the one command whose output proves it>.
Step 2 – <fix>. Verify: <...>.
...
Step N – Optional: ask the owner before doing any of these: <security or behaviour changes
         that are the owner's decision, not a fix>.

Final report: a numbered list, one line per step – ✅ applied / ⚠️ skipped (why) / ❌ failed
(error). Nothing else.
```

The three outcomes in the final report are deliberate: a skipped step is not a failure and not a success, and the owner needs to see which it was.

### 3. Verify

| Fix | Check |
|---|---|
| Memory caps | The configuration file shows the new values; the next save appears in the memory file, not in the error log. |
| Model | The agent’s configuration reports the intended primary model; the scheduled job runs without the drift error. |
| Index | The index file carries today’s generation time, and a nightly job keeps it so. |
| One source of truth | Each agent’s memory header points at the same store. |
| Database | The integrity check prints `ok`. |
| **Recall itself** | Tell the agent a new fact today. Tomorrow, ask about it **in different words**. This is the only test that measures the complaint. |

---

## What it says about any agent memory

- **Check the error log before blaming the model.** “It forgets” was a full-memory error, logged every time, for weeks.
- **Silent rejection is the worst failure mode.** A save that bounces without telling anyone looks exactly like a model that didn’t bother.
- **Keyword recall is not memory.** People never ask the same way twice. Test recall with a paraphrase, or use real embeddings with a keyword fallback – the hybrid search in my own workspace does both ([running-two-ai-agents.md](running-two-ai-agents.md#6-long-term-memory)).
- **A cheaper model is a behaviour change, not a cost change.** A weaker model stops following instructions it used to follow, including the instruction to write things down.
- **One source of truth, written down in one place.** Five stores is not redundancy; it is five chances to read the wrong one.
- **Pin anything that runs unattended** to an explicit model and provider, so a global change can’t silently move it.

---

## Maturity

| Piece | Status | Where |
|---|---|---|
| The audit (five causes and their evidence) | **Built, awaiting review** – written from a debug bundle; read-only | This page |
| Safe-fix script | **Built, awaiting review** – handed over to the owner to run | [`templates/apply_safe_fixes.sh`](templates/apply_safe_fixes.sh) |
| Checklist prompt | **Built, awaiting review** | The generic version above |

**Related:**

- [running-two-ai-agents.md](running-two-ai-agents.md) – the memory design that avoids these causes: two tiers, hybrid search, supersede markers, evals
- [`AGENT_MEMORY_PROTOCOL.md`](../workspace-kit/Reference/AGENT_MEMORY_PROTOCOL.md) – the portable memory specification: inbox hand-off, write discipline, one consolidator
- [local-ai-on-a-mac.md](local-ai-on-a-mac.md) – more silent failures in scheduled jobs and local models
- [learning-from-mistakes.md](learning-from-mistakes.md) – silence mistaken for success, as a recurring pattern
- [security-and-data-policy.md](security-and-data-policy.md) – approvals, pinned plugins and what agents may touch
