# How this system works — the eight parts

Plain-language tour of what's in this folder and why each piece exists. Read once; you won't
need it again. Nothing here is locked — every part is a file you can open and change.

The whole idea in one sentence: **an AI assistant is only as good as the memory and rules it
wakes up with, so we keep those on disk instead of in a chat window that disappears.**

---

## 1. The engine — `CLAUDE.md` / `AGENTS.md` / `SYSTEM_PROMPT.txt`
The assistant's standing instructions. Claude Code reads `CLAUDE.md` automatically at the start
of every single turn, so whatever is in it is always true — no reminding, no re-explaining.

Three copies of the same thing because different tools look for different filenames:

| You use | It reads |
|---|---|
| Claude Code | `CLAUDE.md` |
| Codex, Cursor, Gemini CLI, Zed — anything following the AGENTS standard | `AGENTS.md` |
| A web chatbot with no file access | paste `SYSTEM_PROMPT.txt` into its custom-instructions box |

Keep it **short**. It loads every turn, so a bloated engine file wastes the space your actual
work needs. Detail belongs in `Reference/`, linked from the engine and read only when relevant.

**First run:** don't hand-edit it. Open this folder in Claude Code and say hello — Step 0 of the
engine makes it interview you and fill itself in.

## 2. Continuity — `Sessions/`
The part people underestimate. Every task gets a dated folder holding two files:

- `state.json` — the live truth: what the session is for, its status, the last step done and the next ones (exact shape in `Sessions/README.md`).
- `log.jsonl` — one appended line per change, so there's a trail.

`LATEST.txt` names the active folder. When you come back tomorrow, or switch from Claude to
another agent, or the chat gets wiped mid-task, the assistant reads those three files and picks
up exactly where it stopped — *"Resuming the campaign deck — last step was slide 6, next is the
data slide."* No re-briefing.

The rule that makes it work: **update as you go, not at the end.** A session file written at the
end of the day is a diary. Written continuously, it's a save point.

## 3. Memory — `memory/`
Long-term facts, one per file, listed in `memory/MEMORY.md` — the index that loads each session.
Four kinds:

- **user** — who you are, your role, how you work.
- **feedback** — corrections you've given and approaches you've approved. Always with the *why*, because the reason generalises and the instruction doesn't.
- **project** — ongoing work, goals, constraints that the files themselves don't show.
- **reference** — links to dashboards, docs, tickets.

Why one fact per file: the assistant pulls the two facts it needs instead of loading a 3,000-line
memory document into every conversation. Cheaper, faster, and it stops old facts drowning new ones.

**The habit that matters:** the moment you correct it, it writes that down — same minute, not at
session end. That's the difference between an assistant that learns and one that keeps making the
same mistake politely.

## 4. Tools — `Tools/`
Small scripts the assistant runs instead of re-writing code every time. Four to start:

| Script | What it does |
|---|---|
| `vaultmap.py` | One-screen map of everything in your workspace |
| `media_kit.py` | Common media jobs — grab frames, contact sheets, crop, probe a file |
| `security_gate.py` | Checks a file against your data policy before anything goes to a cloud service |
| `share_delta.sh` | Bundles what you've learned this month to swap with a teammate |

The point isn't these four. It's the habit: when you find yourself asking for the same thing a
third time, have the assistant save it as a script here. Your `Tools/` folder is where your
workflow accumulates. Ask it to check this folder *before* it starts writing new code — that rule
is already in the engine.

## 5. Data policy — `Reference/DATA_POLICY.json`
Four classes — PUBLIC, INTERNAL, CONFIDENTIAL, CLIENT_RESTRICTED — and a list of keywords that
sort files into them automatically. Anything above PUBLIC is local-only by default. One limit to
know: a hosted agent such as Claude Code processes whatever it reads on its provider’s servers,
so the policy guards uploads, not the agent’s own reading — keep truly restricted material
outside this folder.

Add your own client names, project codenames and brand words to `path_hints`. This is the file
that stops a confidential deck being uploaded to a cloud service because it looked like an
ordinary attachment. Five minutes to fill in; the thing you'll be glad about later.

## 6. RAG memory (optional) — `brain/`
Everything above is exact-match: the assistant reads files it knows the name of. RAG adds
*meaning-based* search — ask “what did we decide about the invoice thing?” and it finds the right
note even though you never used those words, provided the note sits in what it indexes:
`CLAUDE.md`, `Reference/`, `Projects/` and the `SA_*.md` files its `sa_log` tool writes. It does
not read `memory/` or `Sessions/`, so log a decision with `sa_log` too if you want to find it this way.

It's a small local server that indexes your notes and hands the assistant the relevant pieces.
Setup is in `brain/SETUP.md`. Add it when your notes get too big to keep track of by hand —
roughly when you stop being able to remember what you've written down. Skip it on day one; the
system works fine without it.

`evals.py` + `eval_set.json` are the quality check: a list of questions and where the answers
should be found, so you can prove the search still works after your notes grow. Replace the two
example cases with real ones.

## 7. Backups — `brain/backup_brain.sh`
Your memory files become genuinely valuable within a few weeks, and they live in one folder on
one machine. Run this on a schedule. A brain you can't restore isn't a brain, it's a risk.

Also worth doing: keep the whole folder in a private Git repository. Every save becomes a
restore point, and you can see how your own working rules changed over time.

## 8. Obsidian (optional) — a visual way in
Open this whole folder as a vault in [Obsidian](https://obsidian.md) (free; it adds its own `.obsidian` settings folder) and your notes become
a browsable, linked, searchable knowledge base with a graph view — the same files, a human
interface. Handy because `[[double-bracket links]]` between memory files then become clickable,
so you can see how your own knowledge connects. Entirely optional; the assistant doesn't care
either way.

---

## The five habits that actually make it work
The folder is just scaffolding. These are the behaviours worth copying:

1. **Write memory the moment it happens** — not at the end.
2. **Keep the always-loaded file small** — depth goes in linked files.
3. **Save the state, not the conversation** — chats vanish, `state.json` doesn't.
4. **Make it argue with you** — an assistant that agrees with everything is a very fast way to be confidently wrong.
5. **Check before building new** — most things you're about to ask for, you already solved once.
