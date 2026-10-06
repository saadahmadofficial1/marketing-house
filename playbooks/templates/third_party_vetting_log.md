# Installed from GitHub-trending digest — 2026-06-28
All MIT-licensed, vetted before install. Location: `Tools/installs/`.

## ✅ markitdown (Microsoft) — READY, on PATH
- Converts Word/PDF/PPTX/Excel/HTML → clean Markdown.
- Venv: `markitdown-venv/`. Command `markitdown` is symlinked to `~/.local/bin` → use anywhere:
  `markitdown report.docx > report.md`

## ✅ ppt-master — READY (Claude skill + Python env)
- Generates editable PowerPoint (native shapes + optional audio narration) from a document.
- Deps installed in `ppt-master/.venv` (python-pptx, PyMuPDF, edge-tts, reportlab, etc. — all mainstream).
- It's a Claude **skill** at `ppt-master/skills/ppt-master/SKILL.md`. To use it inside Claude Code it needs wiring as a skill (ask Claude to do this). To run a generation it needs an AI API key in a `.env` (Saad adds his own — Claude never enters keys).

## ✅ taste-skill — READY (Claude skill, design rules)
- Anti-"AI-slop" design taste rules (frontend/brand). Overlaps STYLE_DNA §6.
- It's a bundle of Claude **skills** (`taste-skill/skills/*/SKILL.md`); `skill.sh` is just a name→path lookup (harmless). No installer run. Wire as a skill to use, or read the SKILL.md rules directly.

## ⏸ open-notebook — PREPPED, NOT LAUNCHED
- Self-hosted NotebookLM alt (research/content). `open-notebook/docker-compose.yml` fetched.
- Needs Docker Desktop running + an encryption key + an AI key. Launch together when wanted:
  `cd Tools/installs/open-notebook && docker compose up -d` → http://localhost:8502
- Left unlaunched on purpose (standing service + your keys = do it with you present).

## voicebox — RECONSIDERED, approved for install
First skipped; Saad reversed that after the trending digest flagged it again
(48.8k stars at review, MIT, fully local, no red flags). Real desktop app (Tauri +
Python backend), not a pip package — needs Rust/Bun/Xcode toolchain to build from source,
or the official signed DMG (voicebox.sh). No Docker on this Mac, so DMG is the path.
Claude can't run a GUI installer or silently add a new dev toolchain — Saad installs the
DMG himself, then Claude wires its local REST API (localhost:17493) into
`Tools/vo_studio.py` as extra voice options (Chatterbox Multilingual — has Arabic — and
Qwen3-TTS look most promising; bundled Kokoro engine already tested+rejected, skip it).

---
# Added 2026-06-29 — kepano/obsidian-skills (MIT)
Source: github.com/kepano/obsidian-skills. Installed into `~/.claude/skills/` (not Tools/installs).

## ✅ obsidian-markdown — READY (Claude skill)
- Correct Obsidian syntax when writing vault notes: wikilinks `[[ ]]`, embeds `![[ ]]`, callouts `> [!type]`, properties/frontmatter.
- Auto-fires when working with vault .md files. Refs: CALLOUTS / EMBEDS / PROPERTIES.md.

## ✅ defuddle — READY (Claude skill + CLI on PATH)
- Clean web extraction → markdown, strips nav/ads = fewer tokens than WebFetch.
- CLI installed globally: `defuddle parse <url> --md` (v0.19.1, ~/.local/node/bin/defuddle).
- Use for normal web pages; NOT for .md URLs (those go straight to WebFetch).

## skipped: obsidian-bases, json-canvas, obsidian-cli — niche, add if needed.
