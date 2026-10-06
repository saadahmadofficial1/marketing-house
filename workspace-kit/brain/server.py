"""Brain — local knowledge server for a team's notes vault.

Local MCP server giving any Claude session (Code, Desktop, Cowork)
instant access to your notes: a lean briefing, search, and session logging.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta
from pathlib import Path

from fastmcp import FastMCP

# Optional local vector RAG layer. If chromadb isn't installed, the brain
# falls back to keyword search and never breaks. sys.path insert makes the
# import work regardless of the MCP host's working directory.
try:
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).resolve().parent))
    import rag as _rag
    _RAG_OK = True
except Exception:
    _rag = None
    _RAG_OK = False

# Index the vault this server sits in; override with the BRAIN_DIR env var.
BRAIN_DIR = Path(os.environ.get("BRAIN_DIR") or Path(__file__).resolve().parent.parent)

BRAIN_FILES: dict[str, Path] = {
    "instincts": BRAIN_DIR / "SA_INSTINCTS.md",
    "memory": BRAIN_DIR / "SA_MEMORY.md",
    "feedback": BRAIN_DIR / "SA_FEEDBACK.md",
    "prompts": BRAIN_DIR / "SA_PROMPTS.md",
    "occasions": BRAIN_DIR / "SA_OCCASIONS.md",
    "projects": BRAIN_DIR / "SA_PROJECTS.md",
    "music": BRAIN_DIR / "SA_MUSIC.md",
    "worklog": BRAIN_DIR / "SA_WORKLOG.md",
}

# Authoritative sources rank above incidental project mentions. See
# _hybrid_search for the measured justification.
AUTHORITY_BOOST = 1.3
_CORE_FILES: frozenset[str] = frozenset(BRAIN_FILES) | {"CLAUDE.md"}


def _is_authoritative(name: str) -> bool:
    """True for files where a fact is DECIDED, not merely mentioned: the curated
    core (SA_*.md, CLAUDE.md) and the Reference/ playbooks. Everything under
    Projects/ is working material — it quotes the rules, it does not set them.
    """
    return name in _CORE_FILES or name.startswith("Reference/")


def _index_files() -> dict[str, Path]:
    """Every file fed to the vector index — wider than BRAIN_FILES.

    BRAIN_FILES governs the briefing (the curated core). The RAG index is
    deliberately broader: core brain + CLAUDE.md + Reference/*.md + every
    project doc (.md/.srt/.txt under Projects/). So retrieval can surface
    anything written there, even something the user forgot exists (memory/
    and Sessions/ are not indexed). Keyed by path-relative
    name to keep ids unique and show useful source labels in results.
    """
    files = dict(BRAIN_FILES)
    extra: list[Path] = [BRAIN_DIR / "CLAUDE.md"]
    extra += sorted((BRAIN_DIR / "Reference").glob("*.md"))  # house playbooks
    proj = BRAIN_DIR / "Projects"
    if proj.exists():
        for p in proj.rglob("*"):
            if p.is_file() and p.suffix.lower() in {".md", ".srt", ".txt"}:
                extra.append(p)
    for p in extra:
        if p.exists():
            files[str(p.relative_to(BRAIN_DIR))] = p
    return files


mcp = FastMCP(
    "sa-brain",
    instructions=(
        "Team knowledge brain. Call sa_briefing() at the start of "
        "every new conversation. Use sa_search() for specific lookups. "
        "Use sa_log() to record new learnings, corrections, or project updates "
        "so future sessions inherit them."
    ),
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (FileNotFoundError, PermissionError):
        return ""


def _sections(text: str) -> list[dict[str, str]]:
    """Split markdown into sections at ## headings."""
    out: list[dict[str, str]] = []
    heading = "Top"
    lines: list[str] = []
    for line in text.split("\n"):
        if line.startswith("## "):
            if lines:
                out.append({"heading": heading, "body": "\n".join(lines).strip()})
            heading = line.lstrip("# ").strip()
            lines = []
        else:
            lines.append(line)
    if lines:
        out.append({"heading": heading, "body": "\n".join(lines).strip()})
    return out


def _keyword_search(query: str, top_k: int = 5) -> list[dict]:
    terms = [t.lower() for t in query.split() if len(t) > 2]
    if not terms:
        return []
    hits: list[dict] = []
    for name, path in _index_files().items():
        text = _read(path)
        if not text:
            continue
        for sec in _sections(text):
            body_l = sec["body"].lower()
            head_l = sec["heading"].lower()
            score = sum(body_l.count(t) * 2 + head_l.count(t) * 5 for t in terms)
            if score > 0:
                hits.append({
                    "file": name,
                    "heading": sec["heading"],
                    "score": score,
                    "body": sec["body"][:1500],
                })
    hits.sort(key=lambda h: h["score"], reverse=True)
    return hits[:top_k]


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def sa_briefing() -> str:
    """Lean session briefing — call at the start of every session.

    ~2-4k tokens, not the whole brain (audit 2026-07-10: the old full-dump
    briefing hit ~31k tokens and defeated its own purpose). Contains: learned
    instincts (full), the ACTIVE SESSION state, recent corrections, core brand
    facts, and an index of everything else — sa_search() pulls detail on demand.
    """
    BUDGET = 12000  # chars ≈ 3k tokens, hard ceiling

    parts = [
        "# Brain — Lean Briefing",
        f"*Generated {datetime.now():%Y-%m-%d %H:%M} — indexes only; "
        "sa_search(query) fetches any full entry.*",
    ]

    def _first_sections(key: str, n: int, cap: int) -> str:
        """Newest-first files (sa_log inserts at top): take the first n sections."""
        secs = [s for s in _sections(_read(BRAIN_FILES[key])) if s["heading"] != "Top"]
        out = []
        for s in secs[:n]:
            body = s["body"][:cap] + ("…" if len(s["body"]) > cap else "")
            out.append(f"### {s['heading']}\n{body}")
        return "\n".join(out)

    def _index_block(label: str, key: str) -> str:
        headings = [s["heading"] for s in _sections(_read(BRAIN_FILES[key]))
                    if s["heading"] != "Top"]
        shown = headings[:25]
        more = f" (+{len(headings)-25} more)" if len(headings) > 25 else ""
        return (f"\n---\n## {label} — index ({len(headings)} entries){more}\n"
                + "\n".join(f"- {h}" for h in shown))

    # 1. Instincts — tiny, always full, fire automatically.
    instincts = _read(BRAIN_FILES["instincts"])
    if instincts:
        parts.append(f"\n---\n## Learned instincts (act on these)\n\n{instincts[:4000]}")

    # 2. Active session — where work stands right now (audit: both agents
    #    must resume from the same lightweight core).
    try:
        latest = (BRAIN_DIR / "Sessions" / "LATEST.txt").read_text().strip()
        st = json.loads((BRAIN_DIR / "Sessions" / latest / "state.json").read_text())
        nxt = "; ".join(st.get("next", [])[:4])
        parts.append(f"\n---\n## Active session: {latest}\n"
                     f"- purpose: {st.get('purpose','')}\n"
                     f"- status: {st.get('status','')}\n"
                     f"- last action: {st.get('last_action','')[:300]}\n"
                     f"- next: {nxt}")
    except Exception as e:
        parts.append(f"\n---\n## Active session\n(unreadable: {e} — check Sessions/LATEST.txt)")

    # 3. Recent corrections + recent work — newest 5 entries each, trimmed.
    parts.append("\n---\n## Recent corrections (newest 5)\n" + _first_sections("feedback", 5, 450))
    parts.append("\n---\n## Recent worklog (newest 3)\n" + _first_sections("worklog", 3, 350))

    # 4. Core brand facts — first sections of memory only.
    parts.append("\n---\n## Core brand facts\n" + _first_sections("memory", 3, 700))

    # 5. Everything else: index only.
    for label, key in [("All corrections", "feedback"), ("Brand memory", "memory"),
                       ("Projects", "projects"), ("Occasions", "occasions"),
                       ("Winning prompts", "prompts"), ("Music", "music")]:
        parts.append(_index_block(label, key))

    text = "\n".join(parts)
    if len(text) > BUDGET:
        text = text[:BUDGET] + "\n…[briefing truncated at budget — sa_search() for anything missing]"
    return text


def _hybrid_search(query: str, top_k: int = 8) -> list[dict]:
    """Fuse dense (vector) + sparse (keyword) retrieval via Reciprocal Rank
    Fusion, boost chunks whose named entities match the query, then rerank by
    query-term coverage. This is the 2026 best-practice default and beats
    either arm alone on precision.
    """
    dense = _rag.vector_search(query, 12)
    sparse = _rag.keyword_search_chunks(query, 12)

    K = 60  # RRF constant
    fused: dict[str, dict] = {}
    for arm in (dense, sparse):
        for rank, h in enumerate(arm):
            cur = fused.get(h["id"])
            if cur is None:
                cur = {**h, "score": 0.0}
                fused[h["id"]] = cur
            cur["score"] += 1.0 / (K + rank + 1)

    # Entity boost — if the query names a known entity the chunk is tagged with.
    # Whole-word match on BOTH sides via rag.find_entities; plain substring
    # leaks (a short code like "ART" matches inside "start") and false-boosts.
    query_ents = set(_rag.find_entities(query)) if _RAG_OK else set()
    for h in fused.values():
        ents = {e for e in (h.get("entities") or "").split(",") if e}
        if query_ents & ents:
            h["score"] *= 1.15

    # Source authority — the curated core (SA_*.md + CLAUDE.md) is where facts
    # are DECIDED; project scripts, worklogs and shotlists merely mention them
    # in passing, and used to outrank the core on fact lookups (a brand-colour
    # query returned prompt files, not the memory file). Measured on evals.py: recall@3
    # 83% -> 94%, MRR 0.73 -> 0.82. The gain plateaus from 1.2 to 2.0, so this
    # is a robust ordering change, not a fit to the 36 eval cases; 1.3 sits in
    # the middle of that plateau. Reference/ earns the same tier: without it
    # the boost pushed core files above the very playbooks CLAUDE.md cites
    # (recall@3 94% -> 97% once Reference/ was included).
    for h in fused.values():
        if _is_authoritative(h.get("file", "")):
            h["score"] *= AUTHORITY_BOOST

    ranked = sorted(fused.values(), key=lambda h: h["score"], reverse=True)
    # Rerank the top candidates by distinct-term coverage for final precision.
    return _rag.rerank(query, ranked[:top_k * 2], top_k=top_k)


@mcp.tool()
def sa_search(query: str) -> str:
    """Search the brain for specific information.

    Args:
        query: Natural-language query (e.g. "automotive prompt rules",
               "holiday colour palette", "music feedback").

    Returns the top matching sections ranked by relevance. Uses local
    vector (semantic) search when available, falling back to keyword search.
    """
    hits: list[dict] = []
    mode = "keyword"
    if _RAG_OK:
        try:
            _rag.reindex(_index_files(), _sections)  # auto-reindex changed files
            hits = _hybrid_search(query)
            mode = "hybrid+rerank"
        except Exception:
            hits = []
    if not hits:  # fallback / RAG empty
        hits = _keyword_search(query)
        mode = "keyword"
    if not hits:
        return f"No results for '{query}'. Try broader or different terms."
    hits = _demote_superseded(hits)
    lines = [f"# Search: {query}  _(mode: {mode})_\n"]
    for i, h in enumerate(hits, 1):
        score = h.get("score", "")
        tag = "  ⚠ SUPERSEDED — a newer entry corrects this" if h.get("_superseded") else ""
        lines.append(f"## {i}. [{h['file'].upper()}] {h['heading']}  ·  score {score}{tag}")
        lines.append(h["body"])
        lines.append("")
    return "\n".join(lines)


def _demote_superseded(hits: list[dict]) -> list[dict]:
    """Move corrected entries below live ones, visibly tagged. Pure.

    A corrected rule and its correction used to retrieve with equal weight, so
    search could hand back the WRONG version of a rule with full confidence.
    The old entry stays readable — history is never hidden — but it can no
    longer outrank the entry that corrects it.
    """
    for h in hits:
        blob = (h.get("heading", "") + " " + h.get("body", "")[:300]).upper()
        h["_superseded"] = "SUPERSEDED" in blob
    return sorted(hits, key=lambda h: h["_superseded"])


@mcp.tool()
def sa_reindex() -> str:
    """Rebuild the local vector index from all brain files (force full reindex).

    Use after large edits, or if semantic search results look stale.
    """
    if not _RAG_OK:
        return ("Vector RAG unavailable (chromadb not installed). "
                "Keyword search is active. Run: uv add chromadb")
    try:
        r = _rag.reindex(_index_files(), _sections, force=True)
        return (f"Reindexed {r['indexed']} files → {r['chunks']} chunks. "
                f"Files: {', '.join(r['files'])}")
    except Exception as e:
        return f"Reindex failed: {e}. Keyword search still active."


def _squeeze(text: str, cap: int = 1200) -> tuple[str, str]:
    """Compress a noisy log entry to atomic facts before it's stored.

    Idea distilled from TencentDB-Agent-Memory (L0->L1): raw dumps bloat the
    brain file, which gets re-read into context and burns tokens. So, purely
    locally (no LLM, no API):
      - collapse runs of blank lines,
      - strip trailing whitespace,
      - replace giant single tokens (base64/URLs > 200 chars) with «…»,
      - if still over `cap`, keep head + tail with a «trimmed N chars» marker.
    Returns (squeezed_text, note) — note is "" when nothing was compressed.
    """
    orig = len(text)
    lines = [ln.rstrip() for ln in text.replace("\r", "").split("\n")]
    out, blanks = [], 0
    for ln in lines:
        if not ln.strip():
            blanks += 1
            if blanks > 1:
                continue
        else:
            blanks = 0
        out.append(re.sub(r"\S{200,}", "«…»", ln))
    t = "\n".join(out).strip()
    if len(t) > cap:
        head, tail = t[: cap - 300], t[-250:]
        t = f"{head}\n\n«trimmed {len(t) - cap + 550} chars — full detail in the session log»\n\n{tail}"
    note = f"  (squeezed {orig}->{len(t)} chars)" if len(t) < orig else ""
    return t, note


@mcp.tool()
def sa_log(log_type: str, content: str, heading: str = "",
            supersedes: str = "") -> str:
    """Record a new learning, correction, or project update.

    Args:
        log_type: Target file — one of: feedback, worklog, prompts,
                  occasions, projects, music.
        content:  Markdown-formatted entry body.
        heading:  Short heading for the entry (optional).
        supersedes: Optional substring of an OLDER entry's heading in the same
                  file. That entry gets a visible SUPERSEDED marker pointing at
                  this one, and search demotes it. Nothing is ever deleted —
                  the history stays, it just stops outranking its correction.

    The entry is date-stamped and inserted near the top of the file
    (after the header) so recent items come first. Noisy/long content is
    auto-compressed to atomic facts first (see _squeeze) so the brain stays
    lean and cheap to re-read.
    """
    valid = {k for k in BRAIN_FILES if k != "memory"}
    if log_type not in valid:
        return f"Invalid type '{log_type}'. Use: {', '.join(sorted(valid))}"

    path = BRAIN_FILES[log_type]
    existing = _read(path)
    date = datetime.now().strftime("%Y-%m-%d")
    content, squeeze_note = _squeeze(content)
    entry = f"\n## [{date}] {heading}\n{content}\n\n---\n"

    # Insert after the first horizontal rule (the file header).
    parts = existing.split("---", 2)
    if len(parts) >= 3:
        new = parts[0] + "---" + entry + parts[1] + "---" + parts[2]
    elif len(parts) == 2:
        new = parts[0] + "---" + entry + parts[1]
    else:
        new = existing + "\n" + entry

    marked = ""
    if supersedes.strip():
        new, n = _mark_superseded(new, supersedes.strip(), heading or date)
        marked = (f"  (marked {n} older entr{'y' if n == 1 else 'ies'} SUPERSEDED)"
                  if n else "  (supersedes target not found — nothing marked)")

    path.write_text(new, encoding="utf-8")
    return f"Logged to {path.name}: [{date}] {heading or '(untitled)'}{squeeze_note}{marked}"


def _mark_superseded(text: str, target: str, successor: str) -> tuple[str, int]:
    """Insert a SUPERSEDED banner under every older '## ' heading containing target.

    Pure. Case-insensitive match; entries already carrying a SUPERSEDED banner are
    left alone; the newest entry (which IS the successor) is never self-marked —
    callers pass the successor heading so it can be excluded.
    """
    lines = text.splitlines()
    out, n = [], 0
    i = 0
    while i < len(lines):
        line = lines[i]
        out.append(line)
        if (line.startswith("## ") and target.lower() in line.lower()
                and successor.lower() not in line.lower()):
            nxt = lines[i + 1] if i + 1 < len(lines) else ""
            already = "SUPERSEDED" in line.upper() or "SUPERSEDED" in nxt.upper()
            if not already:
                out.append(f"**[SUPERSEDED — see: {successor}]**")
                n += 1
        i += 1
    return "\n".join(out) + ("\n" if text.endswith("\n") else ""), n


@mcp.tool()
def sa_instinct(reflex: str) -> str:
    """Capture a learned reflex — a compressed, one-line rule the brain should
    act on automatically in future sessions.

    Use this whenever the user corrects a pattern, states a standing
    preference, or approves an approach worth repeating. Instincts are terse
    (one line) and surface at the TOP of every briefing, so they fire without
    being asked. Keep the full reasoning in sa_log(feedback); put only the
    distilled reflex here.

    Args:
        reflex: One-line rule, e.g. "Captions always British English."
    """
    reflex = reflex.strip().lstrip("-").strip()
    if not reflex:
        return "Empty reflex — nothing saved."

    path = BRAIN_FILES["instincts"]
    text = _read(path)
    date = datetime.now().strftime("%Y-%m-%d")
    line = f"- [{date}] {reflex}"

    # Skip near-duplicates (same reflex text already present).
    if reflex.lower() in text.lower():
        return f"Already known — skipped duplicate: {reflex}"

    marker = "## ACTIVE INSTINCTS"
    if marker in text:
        head, _, tail = text.partition(marker)
        # insert right after the marker line (and its following blank line)
        rest = tail.split("\n", 1)
        after = rest[1] if len(rest) > 1 else ""
        new = f"{head}{marker}\n\n{line}\n{after}"
    else:
        new = text.rstrip() + f"\n\n## ACTIVE INSTINCTS\n\n{line}\n"

    path.write_text(new, encoding="utf-8")
    return f"Instinct saved: {line}"


@mcp.tool()
def sa_recent(days: int = 14) -> str:
    """What happened recently — call to catch up on past sessions.

    Args:
        days: How far back to look (default 14).

    Scans the worklog, feedback, and projects files for recent entries.
    """
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    # Also match "Month YYYY" strings for loose dating.
    now = datetime.now()
    recent_months = {
        f"{m} {now.year}"
        for m in [
            now.strftime("%B"),
            (now - timedelta(days=30)).strftime("%B"),
        ]
    }

    out = [f"# Recent activity (since {cutoff})\n"]
    found = False

    for key in ("worklog", "feedback", "projects"):
        text = _read(BRAIN_FILES[key])
        if not text:
            continue
        recent_secs = []
        for sec in _sections(text):
            iso_dates = re.findall(r"20\d{2}-\d{2}-\d{2}", sec["heading"] + sec["body"][:300])
            month_match = any(m.lower() in sec["heading"].lower() for m in recent_months)
            if (iso_dates and max(iso_dates) >= cutoff) or month_match:
                recent_secs.append(sec)
        if recent_secs:
            found = True
            out.append(f"## {key.upper()}\n")
            for sec in recent_secs[:5]:
                out.append(f"### {sec['heading']}")
                out.append(sec["body"][:800])
                out.append("")

    if not found:
        out.append("No recent dated entries found. Check SA_WORKLOG.md.")

    return "\n".join(out)


if __name__ == "__main__":
    mcp.run()
