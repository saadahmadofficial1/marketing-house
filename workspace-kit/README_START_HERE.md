# 👋 Start here

This folder turns Claude Code (or any AI coding agent) into an assistant that **remembers you,
remembers your work, and picks up where you left off** — instead of starting from zero every
morning.

It's empty on purpose. It's a seed, not a copy of someone else's brain. You grow your own by
using it.

## Setup — about 10 minutes, no technical knowledge needed

1. **Install Claude Code** and open **this folder** as your project.
2. **Say hello.** Really — just "hi".
3. It will ask you four questions: who you are, what you do, what must never happen, and how you
   like to be spoken to. Answer in your own words. It writes the answers into its own instruction
   files for you.
4. Done. Tell it what you're working on.

That's it. You never have to edit a file by hand.

> **Using something other than Claude Code?** Codex, Cursor, Gemini CLI and Zed read `AGENTS.md`
> instead — same content, works the same. Using a web chatbot with no file access? Paste
> `SYSTEM_PROMPT.txt` into its custom-instructions box.

## What you get from day one

- **It never asks "what were we doing?"** Your progress lives in `Sessions/`, so it resumes mid-task after a break, a restart, or a week away.
- **It learns your preferences once.** Correct it, and that correction is written down the same minute — not forgotten by tomorrow.
- **It pushes back.** It's told to check claims (yours included) rather than agree with everything. An assistant that always agrees is a fast route to being confidently wrong.
- **Your confidential work gets a checkpoint.** A data policy you fill in marks client and internal material as local-only, and the assistant is told to check it before sending a file to any outside service. Bear in mind that hosted agents such as Claude Code process whatever they read on their provider’s servers, so keep truly restricted files outside this folder.

## What's in here

| Folder / file | What it's for |
|---|---|
| `CLAUDE.md`, `AGENTS.md`, `SYSTEM_PROMPT.txt` | The assistant's standing instructions — one per tool type |
| `HOW_IT_WORKS.md` | **The tour.** Read this once, it explains every part in plain language |
| `Sessions/` | Where it saves its place so it can resume |
| `memory/` | What it has learned about you and your work |
| `Projects/` | One folder per piece of work, each with a short brief |
| `Reference/` | Reusable know-how, plus your data policy |
| `Tools/` | Small scripts it reuses instead of rewriting code each time |
| `brain/` | *(optional, later)* Meaning-based search across your playbooks, project notes and its own log (not `memory/` or `Sessions/`) |

## The one habit that decides whether this works

**Correct it out loud, every time.** "No — always British English." "Never do that without asking
me." Each correction gets written into `memory/` with the reason, and it compounds. People who do
this have a genuinely useful assistant within a fortnight. People who silently fix its output
themselves have a chatbot forever.

## Making it yours

Nothing here is fixed. Ask it to change its own rules — *"add a rule: never send anything to a
client without showing me first"* — and it edits its instruction file itself. The system is meant
to drift towards how **you** work.

---
Full explanation of every part: **`HOW_IT_WORKS.md`**
