"""Brain — local vector RAG layer.

Chunk → embed → ChromaDB (persistent, local). Embeddings use Chroma's
built-in ONNX all-MiniLM-L6-v2 — on-device after a one-time model download,
no torch.

Designed to be imported with a try/except: if chromadb is unavailable the
caller falls back to keyword search, so the brain never breaks.
"""

from __future__ import annotations

import os
import re
import threading
from pathlib import Path

import chromadb
from chromadb.config import Settings

# Store the vector DB next to this file, wherever the brain lives.
_CHROMA_DIR = Path(__file__).resolve().parent / "chroma_db"
_COLLECTION = "brain"

_client = None
_collection = None
# tracks last-seen mtime per file so we only reindex what changed
_mtimes: dict[str, float] = {}

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
    for para in body.split("\n\n"):
        if size + len(para) > max_chars and cur:
            chunks.append(f"{heading}\n" + "\n\n".join(cur))
            # carry the tail paragraph(s) into the next chunk for overlap
            cur = cur[-overlap_paras:] if overlap_paras else []
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
    """Index changed brain files into Chroma. Returns {indexed, chunks, files}."""
    if not _REINDEX_LOCK.acquire(blocking=False):
        return {"indexed": 0, "chunks": 0, "files": [],
                "skipped": "another reindex is already running"}
    try:
        return _reindex_locked(brain_files, sectioner, force)
    finally:
        _REINDEX_LOCK.release()


def _reindex_locked(brain_files: dict[str, Path], sectioner, force: bool) -> dict:
    col = _get_collection()
    indexed_files, total_chunks, errors = [], 0, []

    for name, path in brain_files.items():
        try:
            mtime = path.stat().st_mtime
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
                    })
            # read + chunk BEFORE any write, so a parse error costs nothing
            col.delete(where={"file": name})
            if docs:
                col.upsert(ids=ids, documents=docs, metadatas=metas)
                total_chunks += len(docs)
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
