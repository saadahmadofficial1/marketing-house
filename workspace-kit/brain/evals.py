"""Brain — retrieval evaluation harness.

Closes the second gap in the brain: until now we *trusted* retrieval worked
because spot-checks passed. As the corpus grows, recall can silently decay
and we'd have no alarm. This harness fixes that.

It replays a small set of representative queries (eval_set.json) against
the live hybrid+rerank pipeline and measures:

  • Recall@1 / Recall@3 / Recall@5  — did the right file appear top-K?
  • MRR (mean reciprocal rank)       — how high did it rank, averaged
  • Per-tag pass rate                — which categories are weakening
  • Per-query failures               — exactly which lookups broke

Run any time after an edit, after a reindex, or as a fast health check.

    cd ~/your-workspace/brain
    uv run python evals.py

Add a case whenever a real session reveals a gap — this set is how we keep
the brain honest as it grows. Pass bar by tag is printed at the end.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Make rag.py + server.py importable regardless of CWD.
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import rag  # noqa: E402
from server import BRAIN_FILES, _hybrid_search, _index_files, _sections  # noqa: E402

EVAL_SET = HERE / "eval_set.json"
TOP_K = 5

# Hits label core brain files with short BRAIN_FILES keys ('feedback') and
# extras with their relative path label ('CLAUDE.md', 'Projects/.../foo.md').
# The eval set names files by basename ('feedback.md', 'CLAUDE.md'), so we
# build a reverse map and accept either form when matching.
SHORT_BY_BASENAME: dict[str, str] = {p.name: k for k, p in BRAIN_FILES.items()}


def _expand_expected(expected: set[str]) -> set[str]:
    """Add the short BRAIN_FILES key for each expected basename so a hit
    labelled 'feedback' matches an expected of 'feedback.md'."""
    out = set(expected)
    for fname in expected:
        if fname in SHORT_BY_BASENAME:
            out.add(SHORT_BY_BASENAME[fname])
    return out


def _expected_in_top_k(hits: list[dict], expected: set[str], k: int) -> int | None:
    """Return the 1-based rank at which any expected file first appears in
    the top-k results, or None if none do. Matches both the raw hit label
    (e.g. 'feedback' or 'CLAUDE.md') and the basename of any path label
    (e.g. 'Projects/Example Project/notes.md' → 'notes.md')."""
    pool = _expand_expected(expected)
    for i, h in enumerate(hits[:k], 1):
        label = h.get("file", "")
        if label in pool or Path(label).name in pool:
            return i
    return None


def main() -> int:
    cases = json.loads(EVAL_SET.read_text(encoding="utf-8"))["cases"]

    # Make sure the index is current before measuring — otherwise we're scoring
    # the previous state of the brain. force=False so unchanged files skip.
    rag.reindex(_index_files(), _sections)

    results = []
    for c in cases:
        hits = _hybrid_search(c["query"], top_k=TOP_K)
        expected = set(c["expected_files"])
        rank = _expected_in_top_k(hits, expected, TOP_K)
        results.append({
            "query": c["query"],
            "tag": c.get("tag", "untagged"),
            "expected": sorted(expected),
            "rank": rank,
            "top_hits": [Path(h.get("file", "")).name for h in hits[:3]],
        })

    n = len(results)
    r1 = sum(1 for r in results if r["rank"] == 1) / n
    r3 = sum(1 for r in results if r["rank"] and r["rank"] <= 3) / n
    r5 = sum(1 for r in results if r["rank"] and r["rank"] <= 5) / n
    mrr = sum((1 / r["rank"]) if r["rank"] else 0 for r in results) / n

    # ---- per-tag breakdown
    by_tag: dict[str, list[dict]] = {}
    for r in results:
        by_tag.setdefault(r["tag"], []).append(r)

    # ---- report
    print(f"# Brain — Retrieval Eval")
    print(f"Cases: {n}   Top-K: {TOP_K}")
    print(f"Recall@1: {r1:.0%}   Recall@3: {r3:.0%}   Recall@5: {r5:.0%}   MRR: {mrr:.2f}")
    print()
    print("## Per-tag pass rate (recall@5)")
    for tag, rs in sorted(by_tag.items()):
        hit = sum(1 for r in rs if r["rank"])
        print(f"  {tag:18s} {hit}/{len(rs)}")
    print()

    fails = [r for r in results if not r["rank"]]
    if fails:
        print(f"## ❌ Failures ({len(fails)}) — expected file not in top {TOP_K}")
        for r in fails:
            print(f"  · '{r['query']}'")
            print(f"      expected one of: {r['expected']}")
            print(f"      top-3 hits:      {r['top_hits']}")
    else:
        print("## ✅ No failures — every expected file appeared in top-K")

    # Exit code: 0 if recall@5 ≥ 80%, 1 otherwise (CI-friendly, optional).
    return 0 if r5 >= 0.80 else 1


if __name__ == "__main__":
    raise SystemExit(main())
