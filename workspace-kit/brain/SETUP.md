# Brain RAG — semantic memory (optional but powerful)

This is the **vector search** layer over your notes. Your file-based memory works
without it; this adds search by meaning, not exact words, over the files listed below.

It's already **generic** — it indexes the vault this `brain/` folder sits inside
(or the folder named in the `BRAIN_DIR` environment variable). No paths to edit.
What it reads: the eight `SA_*.md` brain files at the vault root (where `sa_log`
writes), `CLAUDE.md`, `Reference/*.md`, and the `.md`, `.srt` and `.txt` files
under `Projects/`. It does not index `memory/` or `Sessions/`; the briefing reads
the active session directly.

A fresh kit has none of the `SA_*.md` files yet: `sa_log` creates each one the first
time it writes to it, and `sa_instinct` creates `SA_INSTINCTS.md`, so early briefings
are mostly empty headings. `SA_MEMORY.md` (the core facts the briefing shows) is the
one you write yourself.

## One-time setup (ask your Claude to do this for you)
1. Install **uv** (Python runner): https://docs.astral.sh/uv/
2. In this folder: `uv sync` (builds the local environment).
3. Register it as an MCP server in Claude Code — tell Claude:
   *"Add the brain MCP server at this folder — run `server.py` with uv."*
   It'll wire the config for you.
4. First run indexes your notes automatically (rebuilds anytime files change).

## Tools you get
The server registers as `sa-brain` and exposes six tools:
- `sa_briefing()` — a lean briefing (instincts, active session, recent corrections) at session start
- `sa_search("...")` — search by meaning and keywords across your notes (keyword-only if the vector layer is not installed)
- `sa_log(log_type, content)` — record a learning so future sessions inherit it; it is added to `SA_<TYPE>.md` at the vault root (feedback, worklog, projects, prompts, occasions, music)
- `sa_instinct(reflex)` — save a one-line standing rule that tops every briefing (`SA_INSTINCTS.md`)
- `sa_recent(days=14)` — what happened recently, from the worklog, feedback and projects files
- `sa_reindex()` — rebuild the vector index after big edits, or if results look stale

## Notes
- The vector DB (`chroma_db/`) is **yours** — it builds from your files, never copy
  someone else's. It's git-ignored on purpose.
- **On-device** after a one-time model download — embeddings run locally, no API key.
- The search runs on your machine, but whatever it hands to a hosted agent such as
  Claude Code is then processed on its provider’s servers, like anything else
  the agent reads.
- Don't cloud-sync `chroma_db/` across two machines (it can corrupt). Let each
  machine build its own.
