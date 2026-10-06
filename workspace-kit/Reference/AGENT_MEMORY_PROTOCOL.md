# AGENT MEMORY PROTOCOL

> A portable, battle-tested spec for giving AI agents a **strong, durable, shared long-term memory** on a single laptop.
> Written from a working system (the "Studio Brain") and generalised so any agent — Hermes, OpenClaw, or others — can adopt it.
> **Goal:** memory so solid that even if the MacBook is slow, reset, crashes, or restarts, the agents recall everything and stay in sync.

**Version:** 1.0 · **Author system:** Studio Brain (Claude) · **Date:** 2026-06-06

---

## 0. THE ONE RULE (read this first)

> **Markdown files are the only source of truth. Everything else is rebuildable.**

The vector database, the search index, the agent's RAM, the chat history — all of it is *disposable cache*. The plain `.md` files on disk ARE the memory. If you lose the index, you rebuild it from the `.md`. If you lose RAM, you reload from the `.md`. If the laptop resets, the `.md` files survive (because they're backed up — see §6).

This single principle is why the system survives a slow/resetting machine: **the truth is always tiny, plain text, and on disk.**

---

## 1. WHY THIS PATTERN WINS

| Problem | This pattern's answer |
|---|---|
| Agent forgets between sessions | Memory lives in files, not in the conversation |
| Laptop slow / low RAM | Truth is plain text; only load what's needed |
| Laptop resets / crashes | Backups outside the working folder restore everything |
| Two agents drift apart | Both read/write ONE shared file set (§7) |
| Memory gets big & noisy | Two-tier: hot brief + cold searchable archive (§3) |
| Can't find old facts | Hybrid search: meaning + keyword + entity tags (§5) |
| Memory silently rots | Eval harness catches retrieval decay (§8) |
| Wrong facts pile up | Monthly consolidation dedupes & fixes contradictions (§9) |

---

## 2. FILE LAYOUT

Pick ONE folder as the brain root. Both agents point at it. Example:

```
~/brain/
├── INSTINCTS.md      # compressed one-line reflexes — loaded FIRST, every session
├── MEMORY.md         # core facts: who/what/identity/standing context
├── FEEDBACK.md       # corrections + standing rules (full reasoning)
├── PROJECTS.md       # active + past work, status, decisions
├── WORKLOG.md        # dated session-by-session log (append-only)
├── PEOPLE.md         # humans + agents: names, roles, preferences
├── INBOX.md          # shared message bus between agents (§7)
└── index/            # DERIVED — vector DB / search index (rebuildable, gitignored)
```

Rules:
- **Few files, clear purpose.** Don't make 50 files. Each file = one category.
- **Every file is append-friendly.** New knowledge goes to the bottom under a dated heading.
- **`## headings` are the chunk boundaries.** The search layer splits on them.

---

## 3. TWO-TIER MEMORY (hot vs cold)

The mistake most agent memories make: dump everything into context every time. That's slow and blows the context window.

- **HOT (always loaded at session start):** `INSTINCTS.md` (full) + the *headings index* of the big files. Tiny. This is the **briefing**.
- **COLD (loaded on demand):** the full body of any section, pulled by search only when relevant.

**Briefing = instincts (full) + core facts (full) + everything-else (headings only).**
Keep the briefing under ~50KB. If it grows past that, move detail to cold and leave a heading.

> A new session calls `briefing()` once → instantly knows the reflexes + what exists → searches for the rest as needed.

---

## 4. INSTINCTS (the soul)

`INSTINCTS.md` = compressed, one-line learned reflexes. The highest-signal file. Loaded first, in full, every session — so the agent acts on them **without being asked**.

Format — one line each, dated:
```
## ACTIVE INSTINCTS
- [2026-06-03] All copy = British English. No exceptions.
- [2026-06-02] Check cost BEFORE running expensive ops. Cheapest tool that meets the bar.
- [2026-06-06] User is non-technical. Agent does ALL the technical work. Never hand back commands.
```

Rules:
- **One line. Terse.** Full reasoning goes in `FEEDBACK.md`; only the distilled reflex goes here.
- **Add one whenever** the user corrects a pattern, states a standing preference, or approves a repeatable approach.
- **Never silently delete.** If an instinct is wrong, mark it corrected with a date.

This file is the difference between an agent that *remembers facts* and one that *behaves consistently*. It's the personality + the rules. The soul.

---

## 5. RETRIEVAL (how the agent finds things)

Don't rely on one search method. Use **hybrid**:

1. **Dense (vector / semantic):** embed each chunk locally. Catches meaning even when words differ ("cheapest way to make a clip" → finds the budget rule). Use a small **local** embedding model (e.g. all-MiniLM-L6-v2 via ONNX) — no cloud, no API key, survives offline.
2. **Sparse (keyword):** plain term-frequency over the same chunks. Catches exact names, IDs, codes that vectors miss.
3. **Fuse them (Reciprocal Rank Fusion, K=60):** combine both ranked lists. Beats either alone.
4. **Entity boost (lightweight knowledge graph):** keep a vocab list of your important nouns (people, projects, products). Tag each chunk with the entities it mentions. If the query names an entity the chunk has → multiply its score (×1.15). Cheap, no LLM extraction.
5. **Rerank:** reorder top candidates by how many distinct query terms each covers. Catches relevance the score missed.

**Auto-reindex:** before each search, check file mtimes; re-embed only the files that changed. Index stays fresh, cost stays near zero.

**Always have a fallback:** wrap the vector layer in try/except. If the DB is missing/broken, fall back to keyword search over the raw `.md`. **The memory must never hard-fail.**

---

## 6. DURABILITY (survive a reset/crash) — THE PART MOST SYSTEMS SKIP

A single copy is not memory. It's a liability. Three layers, all **local**, all **outside the brain folder** so one bad `rm` can't take both:

```
~/brain_backups/          # OUTSIDE ~/brain/
├── vault/                # a git repo that DOES track the .md content (full history)
├── snapshots/            # rotating .tar.gz, keep last 30
└── backup.log
```

Backup job (run daily via launchd on macOS — NOT cron; cron needs Full Disk Access and fails silently). Caveat: a launchd job that runs a shell script cannot read `~/Documents`, `~/Desktop` or `~/Downloads` without Full Disk Access either, and fails just as silently. `~/brain/` as laid out here is fine; if your brain or workspace lives in a protected folder, have launchd open a small applet that holds the grant — see the [macOS nightly recipe](../../playbooks/templates/macos-nightly-launchd.md).

The job:
1. Copy all `.md` into `vault/`, then `git commit` → versioned history (`git log` to see every change, `git diff` to revert).
2. `tar.gz` snapshot into `snapshots/`, prune to last 30.
3. Append one line to `backup.log`.

**Do NOT back up the vector index** — it's rebuildable from the `.md` in seconds. Backing up the markdown backs up everything that matters (tiny + fast).

> Test it: delete the brain folder in a sandbox, restore from the latest snapshot, run the eval (§8). If recall is unchanged, your durability is real.

---

## 7. SHARED MEMORY FOR MULTIPLE AGENTS ⭐ (what a shared chat group alone does not give you)

Two agents "in the same group" is NOT shared memory. They each have their own context. Real shared memory = **both agents read and write the same `.md` file set on the same disk.** Telegram is just the chat transport; the files are the brain.

### 7.1 Topology
```
  Hermes  ─┐
           ├──►  ~/brain/  (single source of truth)  ◄── both read + write
 OpenClaw ─┘
           └──►  ~/brain/INBOX.md  (message bus for agent-to-agent handoff)
```
Both agents are configured with the **same brain root path**. Neither keeps private memory that the other can't see. If one learns something, it writes to the shared files → the other inherits it on its next read.

### 7.2 Write discipline (avoid clobbering each other)
Two writers on one file = risk of overwrite. Rules that prevent it:

1. **Append-only, never rewrite.** Add new content at the bottom under a dated heading. Never rewrite a whole file in place (except the monthly consolidation, §9, which one agent runs alone).
2. **Atomic writes.** Write to a temp file, then `mv` over the target (rename is atomic on the same filesystem). A half-written file never exists.
3. **Lock file.** Before writing, create `~/brain/.lock`. If it exists, wait + retry (max ~5s). Delete it after. Prevents two simultaneous appends interleaving.
4. **Attribution.** Every entry is stamped with which agent wrote it:
   ```
   ### [2026-06-06] [Hermes] Found cheaper API route for X
   ...
   ```
   So you can always see who learned what.

### 7.3 Agent-to-agent handoff (INBOX.md)
The shared message bus. When Hermes needs OpenClaw to pick something up (or vice versa):

```
## INBOX  (append-only; reader marks [DONE] when handled)

### [2026-06-06 14:30] Hermes → OpenClaw
Task: scrape the 3 links in PROJECTS.md §"Research X" and summarise into MEMORY.md.
Status: OPEN

### [2026-06-06 15:02] OpenClaw → Hermes
Re: above. Done. Summary in MEMORY.md §"X findings". 
Status: DONE
```

Rules:
- Sender appends an entry with `Status: OPEN` and a clear, self-contained task (assume the reader has zero prior context).
- Receiver, on its turn, scans `INBOX.md` for `OPEN` items addressed to it, does the work, appends a reply, flips to `DONE`.
- This is how they "share memory" reliably — not by hoping Telegram scrollback survives, but by a durable on-disk queue.

### 7.4 The golden rule of multi-agent memory
> **Telegram is ephemeral. The files are forever.** Anything that matters must land in a `.md` file. If it only exists in the chat, it doesn't exist.

---

## 8. EVALS (prove the memory still works)

Don't trust retrieval — measure it. Keep a small test set:

```json
{ "query": "what language do we write in",
  "expected_files": ["INSTINCTS.md", "FEEDBACK.md"] }
```

A script replays each query through the live search and reports:
- **Recall@1 / @3 / @5** — did the right file appear in the top K?
- **MRR** — how high did it rank, averaged.
- **Per-query failures** — exactly which lookups broke.

Run it after any big edit or reindex. If recall drops, retrieval is rotting — fix before it bites. A healthy system sits at Recall@3 ≈ 100%.

---

## 9. CONSOLIDATION (keep memory clean)

Monthly (or on a trigger), ONE agent runs a cleanup pass:
- Dedupe repeated entries.
- Fix contradictions (newer fact wins; mark the old one corrected, don't delete history).
- Prune dead/stale items.
- Rebuild the index.
- Log a summary to `WORKLOG.md`.

Be conservative: **flag rather than delete** when unsure. Memory you might need beats memory you nuked.

---

## 10. SESSION LIFECYCLE (every agent, every session)

```
START  →  call briefing()  → load INSTINCTS (full) + headings index
WORK   →  search() for anything you don't already have
         →  log() new learnings IN REAL TIME (not just at the end)
         →  check INBOX.md for OPEN items addressed to you
END    →  ensure everything important is written to a .md
         →  (backup job runs daily on its own schedule)
```

**Log in real time.** The #1 cause of lost memory is "I'll write it at the end" — then the session dies first. Write the moment you learn it.

---

## 11. TIPS & TRICKS (hard-won)

1. **Truth tiny, cache big.** Keep the source-of-truth small and plain; let the derived layers (index, RAM) be as big as they want — they're disposable.
2. **Never hard-fail.** Every memory operation has a fallback. Vector down → keyword. Index corrupt → rebuild from `.md`. The agent should degrade, never die.
3. **Dates on everything.** Every entry dated. Lets you resolve "which fact is newer" and makes consolidation possible.
4. **Correct, don't delete.** When a fact changes, append the correction + mark the old one. History is how you debug a bad decision later.
5. **Instincts > facts.** A reflex that fires automatically beats a fact you have to look up. Promote repeated corrections into one-line instincts.
6. **Entity vocab is cheap intelligence.** A hand-written list of your ~30 important nouns, tagged onto chunks, gives 80% of a knowledge graph for 1% of the effort.
7. **Backups live OUTSIDE the source folder.** Same-folder backup dies with the folder. Different location = real redundancy.
8. **launchd, not cron** (macOS) — with a caveat. cron silently fails on `~/Documents` without Full Disk Access, and so does a launchd job that runs a script there: launchd jobs cannot read `~/Documents`, `~/Desktop` or `~/Downloads` without Full Disk Access. Keep the brain and its backups outside those folders, or wrap the script in an applet granted Full Disk Access once ([macOS nightly recipe](../../playbooks/templates/macos-nightly-launchd.md)).
9. **Atomic write or corruption.** Temp-file-then-rename. Especially with two agents writing.
10. **The chat is not the memory.** Telegram/terminal scrollback is ephemeral. If it's not in a file, it's gone.
11. **One consolidator.** Many appenders, but only ONE agent rewrites files (during consolidation). Avoids merge wars.
12. **Self-contained entries.** Write every note assuming the reader (a future session, or the other agent) has zero context. Include paths, names, the "why."
13. **Restart = reload.** After changing the memory server's code, the agent must reload it. Verify the new behaviour is live before trusting it.
14. **Measure, don't assume.** Spot-checks lie as the corpus grows. The eval set is the only honest signal.

---

## 12. MINIMUM VIABLE VERSION (start here, grow later)

If you want this running today with the least effort:

1. Make `~/brain/` with `INSTINCTS.md`, `MEMORY.md`, `WORKLOG.md`, `INBOX.md`.
2. Point both agents at that path. Tell them: *read all four at session start; append (never overwrite) with dated + attributed entries; use INBOX.md to hand tasks to each other.*
3. Add a daily backup: copy `~/brain/*.md` into `~/brain_backups/` + git commit.
4. That's it. You now have shared, durable memory.

Add the vector search (§5), evals (§8), and consolidation (§9) later, when the archive gets big enough that plain reading is slow. **Don't over-build on day one — the four files + backups are 80% of the value.**

---

## 13. ONE-PARAGRAPH SUMMARY (paste this to your agents)

> You share one memory: the markdown files in `~/brain/`. These files are the only truth — everything else is rebuildable cache. At the start of every session, read `INSTINCTS.md` (your standing reflexes) and the headings of the other files, then search for detail as needed. When you learn something, write it immediately to the right `.md` file: append at the bottom, under a dated `### [YYYY-MM-DD] [YourName]` heading, never overwrite. To hand a task to the other agent, append it to `INBOX.md` with `Status: OPEN`; when you handle one addressed to you, reply and flip it to `DONE`. Telegram is just chat — it disappears. The files are forever; if it matters, it goes in a file. The whole thing is backed up daily to a separate folder, so a crash or reset loses nothing.

---
🔗 [[INDEX]] · [[CLAUDE]]
