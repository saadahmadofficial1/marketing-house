"""Brain — local vector RAG layer.

Chunk → embed → ChromaDB (persistent, local). Embeddings use Chroma's
built-in ONNX all-MiniLM-L6-v2 — on-device after a one-time model download,
no torch.

Designed to be imported with a try/except: if chromadb is unavailable the
caller falls back to keyword search, so the brain never breaks.
"""

from __future__ import annotations

import fcntl
import os
import re
import threading
from pathlib import Path

import chromadb
from chromadb.config import Settings

# Store the vector DB next to this file, wherever the brain lives.
LIVE_CHROMA_DIR = Path(__file__).resolve().parent / "chroma_db"
# Set SA_BRAIN_CHROMA_DIR to point tests at a throwaway index, so they never open the live one.
_env_dir = os.environ.get("SA_BRAIN_CHROMA_DIR", "").strip()
_CHROMA_DIR = Path(os.path.expanduser(_env_dir)) if _env_dir else LIVE_CHROMA_DIR
_COLLECTION = "brain"

_client = None
_collection = None
# tracks last-seen mtime per file so we only reindex what changed; seeded from
# the index itself so a restarted server doesn't re-embed everything
_mtimes: dict[str, str] = {}
_mtimes_loaded = False


class IndexBusy(RuntimeError):
    """Another process owns the vector index — only one process may open it."""


# Single owner (audit 2026-10-12): Chroma keeps the HNSW index in memory, so a
# SECOND process that merely opens the same index (Codex's brain server, an eval
# run) and writes to it leaves sqlite and HNSW out of step — the 29 Jun and
# 12 Oct corruption. The first process to open the index takes this lock for
# its whole life; everyone else gets IndexBusy and uses keyword search.
# The lock sits NEXT TO the index folder, so renaming the folder can't move it.
_owner_fd = None


def _take_ownership() -> None:
    global _owner_fd
    if _owner_fd is not None:
        return
    lock = _CHROMA_DIR.parent / f".{_CHROMA_DIR.name}.owner.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    fd = open(lock, "w")
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        fd.close()
        raise IndexBusy("the vector index is open in another app (Claude or Codex)")
    _owner_fd = fd  # never closed: released by the OS when this process exits

# Lightweight entity vocabulary — tagged onto each chunk at index time so
# retrieval can boost chunks about the same subsidiary / person / project /
# occasion the query is about (cheap knowledge-graph signal, no LLM extraction).
ENTITIES: tuple[str, ...] = (
    # Fill with your organisation's entities — business units, brands, leaders,
    # recurring projects/events. Used as a cheap knowledge-graph signal.
    "YOUR-UNIT-1", "YOUR-BRAND-1", "YOUR-LEADER-1", "YOUR-EVENT-1",
)


# Precompile a word-boundary regex per entity. Plain substring matching is a
# precision LEAK: short codes match inside common words ("ART" in "start",
# "ACE" in "place", "EAR" in "learn"), producing false entity tags and false
# score boosts. \b ... \b matches the entity only as a whole word/token.
_ENTITY_RE: dict[str, re.Pattern] = {
    e: re.compile(r"\b" + re.escape(e) + r"\b", re.IGNORECASE)
    for e in ENTITIES
}


def find_entities(text: str) -> list[str]:
    """List known entities mentioned in the text as whole words (case-insensitive)."""
    return [e for e, rx in _ENTITY_RE.items() if rx.search(text)]


def _find_entities(text: str) -> str:
    """Comma-joined entity list for chunk metadata (Chroma needs scalars)."""
    return ",".join(find_entities(text))


def _get_collection():
    global _client, _collection
    if _collection is None:
        _take_ownership()  # raises IndexBusy before Chroma is ever touched
        _CHROMA_DIR.mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(
            path=str(_CHROMA_DIR),
            settings=Settings(anonymized_telemetry=False, allow_reset=True),
        )
        # default embedding fn = onnx MiniLM, downloaded once, cached locally
        _collection = _client.get_or_create_collection(
            name=_COLLECTION,
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


def _chunk(heading: str, body: str, max_chars: int = 1800,
           overlap_paras: int = 1) -> list[str]:
    """Split a long section body into embed-sized chunks, heading-prefixed.

    Chunks overlap by the last ``overlap_paras`` paragraph(s) so context is
    never cut mid-thought — a fact split across a boundary stays retrievable
    from either side.
    """
    body = body.strip()
    if not body:
        return []
    if len(body) <= max_chars:
        return [f"{heading}\n{body}"]
    chunks, cur = [], []
    size = 0
    paras = []
    for para in body.split("\n\n"):
        # a paragraph with no blank lines can be huge (one was 145k chars):
        # cut it into overlapping pieces that fit
        step = max_chars - 200
        paras += [para[i:i + max_chars] for i in range(0, len(para), step)] or [para]
    for para in paras:
        if size + len(para) > max_chars and cur:
            chunks.append(f"{heading}\n" + "\n\n".join(cur))
            # carry a short tail into the next chunk for overlap — never a whole
            # long paragraph, or chunks double in size and repeat each other
            # (measured 12 Oct: R@3 92% / R@5 97% vs 89% / 94% keeping short paragraphs whole)
            tail = cur[-1][-300:] if overlap_paras else ""
            cur = [tail] if tail else []
            size = sum(len(p) + 2 for p in cur)
        cur.append(para)
        size += len(para) + 2
    if cur:
        chunks.append(f"{heading}\n" + "\n\n".join(cur))
    return chunks


# Crash-safety (added after the 2026-06-29 corruption): reindex fires on the
# search hot path, so (a) never run two reindexes at once — the overlap of
# delete+upsert from two callers is what mismatches sqlite vs the HNSW
# segment; (b) isolate failures per file so one bad file can't abort mid-write.
_REINDEX_LOCK = threading.Lock()


def reindex(brain_files: dict[str, Path], sectioner, force: bool = False) -> dict:
    """Index changed brain files into Chroma. Returns {indexed, chunks, files}.
    Other processes are kept out by the owner lock in _get_collection()."""
    if not _REINDEX_LOCK.acquire(blocking=False):
        return {"indexed": 0, "chunks": 0, "files": [],
                "skipped": "another reindex is already running"}
    try:
        return _reindex_locked(brain_files, sectioner, force)
    finally:
        _REINDEX_LOCK.release()


def _reindex_locked(brain_files: dict[str, Path], sectioner, force: bool) -> dict:
    global _mtimes_loaded
    col = _get_collection()
    if not _mtimes_loaded:  # what the index already holds, so a restart is cheap
        for m in col.get(include=["metadatas"])["metadatas"]:
            if m and "mtime" in m:
                _mtimes.setdefault(m["file"], m["mtime"])
        _mtimes_loaded = True
    indexed_files, total_chunks, errors = [], 0, []

    for name, path in brain_files.items():
        try:
            # exact ns as text: Chroma rounds float metadata, so a float never matches
            mtime = str(path.stat().st_mtime_ns)
        except FileNotFoundError:
            continue
        if not force and _mtimes.get(name) == mtime:
            continue  # unchanged since last index

        try:
            text = path.read_text(encoding="utf-8")
            ids, docs, metas = [], [], []
            for si, sec in enumerate(sectioner(text)):
                for ci, chunk in enumerate(_chunk(sec["heading"], sec["body"])):
                    ids.append(f"{name}:{si}:{ci}")
                    docs.append(chunk)
                    metas.append({
                        "file": name,
                        "heading": sec["heading"],
                        "entities": _find_entities(chunk),
                        "mtime": mtime,
                    })
            # read + chunk BEFORE any write, so a parse error costs nothing.
            # Upsert first, then drop only the ids that no longer exist: a failed
            # upsert leaves the old chunks searchable instead of emptying the file
            # (the old delete-first order is how SA_MEMORY fell to 0, 12 Oct).
            old = set(col.get(where={"file": name}, include=[])["ids"])
            if docs:
                col.upsert(ids=ids, documents=docs, metadatas=metas)
                total_chunks += len(docs)
            stale = list(old - set(ids))
            if stale:
                col.delete(ids=stale)
            _mtimes[name] = mtime
            indexed_files.append(name)
        except Exception as e:  # one bad file must not kill the whole pass
            errors.append(f"{name}: {e}")

    out = {"indexed": len(indexed_files), "chunks": total_chunks,
           "files": indexed_files}
    if errors:
        out["errors"] = errors
    return out


def vector_search(query: str, top_k: int = 12) -> list[dict]:
    """Semantic (dense) search. One arm of the hybrid pipeline."""
    col = _get_collection()
    res = col.query(query_texts=[query], n_results=top_k)
    ids = (res.get("ids") or [[]])[0]
    docs = (res.get("documents") or [[]])[0]
    metas = (res.get("metadatas") or [[]])[0]
    dists = (res.get("distances") or [[]])[0]
    hits = []
    for cid, doc, meta, dist in zip(ids, docs, metas, dists):
        if not isinstance(doc, str):
            continue
        # Chroma can briefly surface a stale HNSW id whose deleted SQLite row
        # has no metadata. Keep retrieval alive and let a rebuild remove it.
        meta = meta or {}
        hits.append({
            "id": cid,
            "file": meta.get("file", "?"),
            "heading": meta.get("heading", "?"),
            "score": round(1 - dist, 3),  # cosine sim
            "body": doc,
            "entities": meta.get("entities", ""),
        })
    return hits


def keyword_search_chunks(query: str, top_k: int = 12) -> list[dict]:
    """Sparse (keyword) search over the SAME chunk units as vector_search, so
    the two arms can be fused cleanly via RRF. Scores by term frequency."""
    col = _get_collection()
    terms = [t.lower() for t in query.split() if len(t) > 2]
    if not terms:
        return []
    data = col.get(include=["documents", "metadatas"])
    ids = data.get("ids") or []
    docs = data.get("documents") or []
    metas = data.get("metadatas") or []
    hits = []
    for cid, doc, meta in zip(ids, docs, metas):
        if not isinstance(doc, str):
            continue
        meta = meta or {}
        dl = doc.lower()
        score = sum(dl.count(t) for t in terms)
        if score > 0:
            hits.append({
                "id": cid,
                "file": meta.get("file", "?"),
                "heading": meta.get("heading", "?"),
                "score": score,
                "body": doc,
                "entities": meta.get("entities", ""),
            })
    hits.sort(key=lambda h: h["score"], reverse=True)
    return hits[:top_k]


def rerank(query: str, hits: list[dict], top_k: int = 8) -> list[dict]:
    """Dependency-free reranker: reorders candidates by distinct query-term
    coverage (how many different query words a chunk actually contains), which
    catches relevance that raw frequency/cosine miss. This is the local,
    always-on rerank; a cross-encoder model can later replace this fn if
    higher precision is ever needed.
    """
    terms = {t.lower() for t in query.split() if len(t) > 2}
    if not terms or not hits:
        return hits[:top_k]
    for h in hits:
        if not isinstance(h.get("body"), str):
            continue
        dl = h["body"].lower()
        coverage = sum(1 for t in terms if t in dl) / len(terms)
        # blend existing fused score with coverage (coverage dominates ties)
        h["score"] = round(h.get("score", 0) * 0.5 + coverage, 4)
    hits.sort(key=lambda h: h["score"], reverse=True)
    return hits[:top_k]
