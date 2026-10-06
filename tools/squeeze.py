#!/usr/bin/env python3
"""squeeze.py — shrink a big tool output / file before it hits the LLM.

Tool-mode only (NOT a proxy): hand it text, get a compressed version + savings.
Wraps headroom-ai compress() as a tool-result. Run with the venv python:
  Tools/headroom/.venv/bin/python Tools/squeeze.py BIGFILE [--out OUT]
  cat big.json | Tools/headroom/.venv/bin/python Tools/squeeze.py -

ponytail: thin wrapper, no config — compression only kicks in on big outputs
(model_limit forces it). Small inputs pass through unchanged, by design.
"""
import sys, json, argparse
from headroom import compress

def squeeze(text: str):
    # role:"tool" so headroom compresses it (user messages are protected)
    res = compress(
        [{"role": "assistant", "content": ""},
         {"role": "tool", "tool_call_id": "t1", "content": text}],
        model_limit=2000,  # force the optimizer to engage on big payloads
    )
    out = res.messages[-1]
    comp = out.get("content") if isinstance(out, dict) else str(out)
    # GUARD: CCR replaces uncompressible prose with an unreadable pointer
    # (<<ccr:...>>) meant for the proxy to re-expand. Useless for reading —
    # fall back to the original so we never hand back a pointer.
    if "<<ccr:" in comp:
        return text, res.tokens_before, res.tokens_before  # 0% — nothing readable to squeeze
    return comp, res.tokens_before, res.tokens_after


def demo():
    # INVARIANT 1: output is always readable — never a CCR pointer
    big = '{"items":[' + ",".join('{"id":%d,"name":"item-%d","status":"active","url":"https://x/%d","desc":"lorem ipsum dolor sit"}' % (i, i, i) for i in range(400)) + ']}'
    c, b, a = squeeze(big)
    assert "<<ccr:" not in c, "must never return a CCR pointer"
    assert a <= b, "tokens can't grow"
    # INVARIANT 2: prose (uncompressible here) falls back to the ORIGINAL untouched
    prose = "The quick brown fox jumps over the lazy dog. " * 2000
    c2, b2, a2 = squeeze(prose)
    assert c2 == prose and a2 == b2, "prose must pass through unchanged, no pointer"
    print("squeeze self-check OK (JSON %d->%d readable, prose passthrough)" % (b, a))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path", help="file to squeeze, or - for stdin")
    ap.add_argument("--out", help="write compressed text here (default: stdout)")
    a = ap.parse_args()
    text = sys.stdin.read() if a.path == "-" else open(a.path, encoding="utf-8", errors="replace").read()
    comp, before, after = squeeze(text)
    saved = before - after
    pct = (100 * saved // before) if before else 0
    if a.out:
        open(a.out, "w", encoding="utf-8").write(comp)
        where = a.out
    else:
        sys.stdout.write(comp)
        where = "stdout"
    sys.stderr.write(f"\n[squeeze] {before} -> {after} tokens  ({pct}% saved) -> {where}\n")

if __name__ == "__main__":
    main()
