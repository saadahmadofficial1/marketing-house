"""Isolated historical retrieval experiment: keyword counts vs BM25 vs dense vs hybrid search
over the brain's own chunks, fully offline. (done by codex)

Needs YOUR OWN cases.json beside it: the original question set quotes private notes and is not
published. Format: a list of {"query": "...", "evidence_groups": [["term", "term"], ["other term"]]};
a hit counts when its chunk contains every term of any one group. Also reads ../eval_set.json
and the workspace folders listed in main(), so adjust those names to yours."""
import collections
import hashlib
import json
import math
import re
import socket
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
BRAIN = HERE.parent            # brain/: server.py, rag.py, eval_set.json
ROOT = BRAIN.parent            # the workspace the brain indexes
sys.path.insert(0, str(BRAIN))
import server
import rag
import numpy as np
from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2

# Fail closed: this experiment only uses the model already cached locally.
def offline(*args, **kwargs):
    raise RuntimeError('Network disabled for local retrieval experiment')
socket.socket.connect = offline
socket.create_connection = offline

def dump(name, data):
    (HERE / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')

def tokens(text):
    return re.findall(r'\w+', text.casefold())

class BM25:
    def __init__(self, docs):
        self.post = collections.defaultdict(list)
        self.lengths = []
        for i, d in enumerate(docs):
            ts = tokens(d['body'])
            self.lengths.append(len(ts))
            for term, freq in collections.Counter(ts).items():
                self.post[term].append((i, freq))
        self.n = len(docs)
        self.avg = sum(self.lengths) / max(1, self.n)
    def search(self, query, k=12):
        scores = collections.defaultdict(float)
        for term in set(tokens(query)):
            postings = self.post.get(term, [])
            idf = math.log(1 + (self.n - len(postings) + .5) / (len(postings) + .5))
            for i, tf in postings:
                norm = 1.2 * (.25 + .75 * self.lengths[i] / max(1, self.avg))
                scores[i] += idf * tf * 2.2 / (tf + norm)
        return sorted(scores, key=lambda i: (-scores[i], i))[:k]

def chunk_files(files):
    docs = []
    for name, path in sorted(files.items()):
        text = path.read_text(encoding='utf-8', errors='replace')
        for si, sec in enumerate(server._sections(text)):
            for ci, body in enumerate(rag._chunk(sec['heading'], sec['body'])):
                docs.append(dict(id=f'{name}:{si}:{ci}', file=name, heading=sec['heading'],
                                 body=body, entities=rag._find_entities(body)))
    return docs

def old_sparse(query, docs, k=12):
    terms = [t.lower() for t in query.split() if len(t) > 2]
    scores = [(sum(d['body'].lower().count(t) for t in terms), i) for i,d in enumerate(docs)]
    return [i for s,i in sorted(scores, key=lambda x: (-x[0],x[1]))[:k] if s > 0]

def fused(query, dense, sparse, docs):
    scores = collections.defaultdict(float)
    for arm in (dense, sparse):
        for rank, i in enumerate(arm):
            scores[i] += 1/(61+rank)
    entities = set(rag.find_entities(query))
    for i in scores:
        if entities.intersection(docs[i]['entities'].split(',')):
            scores[i] *= 1.15
    pool = sorted(scores, key=lambda i: (-scores[i], i))[:16]
    hits = rag.rerank(query, [{**docs[i], 'score': scores[i]} for i in pool], top_k=8)
    return server._demote_superseded(hits)[:5]

def main():
    start = time.time()
    current = server._index_files()
    # Do not let this study's own conclusions contaminate the benchmark.
    current = {k:v for k,v in current.items() if not v.is_relative_to(HERE)}
    eligible = set(ROOT.glob('*.md'))
    for directory in ('Reference','Projects','Sessions','Team_Log'):
        eligible.update(p for p in (ROOT/directory).rglob('*')
                        if p.is_file() and p.suffix.lower() in {'.md','.txt','.srt','.vtt','.jsonl'}
                        and not p.is_relative_to(HERE) and '.git' not in p.parts
                        and 'node_modules' not in p.parts and '.venv' not in p.parts
                        and HERE.name not in p.parts)
    manifest = []
    selected = {p.resolve() for p in current.values()}
    for p in sorted(eligible):
        data = p.read_bytes()
        text = data.decode('utf-8', errors='replace')
        headings = [line[:250] for line in text.splitlines() if line.startswith('#') and
                    re.search(r'2026|May|June|July|August|September',line)]
        manifest.append(dict(path=str(p.relative_to(ROOT)), bytes=len(data), sha256=hashlib.sha256(data).hexdigest(),
                             current_search=p.resolve() in selected, dated_headings=headings))
    dump('manifest.json', manifest)
    # Corpus expansion omits raw logs here: they need structured parsing and authority handling.
    expanded = dict(current)
    for p in sorted(eligible):
        if p.resolve() not in selected and p.suffix.lower() in {'.md','.txt','.srt','.vtt'}:
            expanded[str(p.relative_to(ROOT))] = p
    docs = chunk_files(current)
    more = chunk_files(expanded)
    print(f'Inventory {len(manifest)} files; current {len(current)} files/{len(docs)} chunks; expanded {len(expanded)} files/{len(more)} chunks', flush=True)
    bm = BM25(docs)
    bm_more = BM25(more)
    cases = json.loads((HERE/'cases.json').read_text())
    legacy = json.loads((BRAIN/'eval_set.json').read_text())['cases']
    short = {p.name:k for k,p in server.BRAIN_FILES.items()}
    allcases = [{**c,'kind':'evidence'} for c in cases] + [{**c,'kind':'legacy'} for c in legacy]
    model = ONNXMiniLM_L6_V2()
    fingerprint = hashlib.sha256(json.dumps([d['body'] for d in docs]).encode()).hexdigest()
    cache = HERE/'embeddings.npy'
    if cache.exists() and (HERE/'embedding_fingerprint.txt').read_text() == fingerprint:
        embeddings = np.load(cache)
    else:
        batches = []
        for j in range(0,len(docs),64):
            batches.append(np.asarray(model([d['body'] for d in docs[j:j+64]])))
            if j % 640 == 0: print(f'Local embeddings {j}/{len(docs)}',flush=True)
        embeddings = np.concatenate(batches)
        np.save(cache,embeddings)
        (HERE/'embedding_fingerprint.txt').write_text(fingerprint)
    embeddings /= np.maximum(np.linalg.norm(embeddings,axis=1,keepdims=True),1e-12)
    queries = np.asarray(model([c['query'] for c in allcases]))
    queries /= np.maximum(np.linalg.norm(queries,axis=1,keepdims=True),1e-12)
    results=[]
    for c,q in zip(allcases,queries):
        dense=np.argsort(-(embeddings@q),kind='stable')[:12].tolist()
        sparse=old_sparse(c['query'],docs)
        better=bm.search(c['query'])
        methods={
            'keyword_counts':[docs[i] for i in sparse[:5]],
            'bm25':[docs[i] for i in better[:5]],
            'dense':[docs[i] for i in dense[:5]],
            'existing_hybrid':fused(c['query'],dense,sparse,docs),
            'bm25_hybrid':fused(c['query'],dense,better,docs),
            'expanded_bm25':[more[i] for i in bm_more.search(c['query'],5)]}
        out={**c,'methods':{}}
        for method,hits in methods.items():
            def relevant(h):
                if c['kind']=='evidence':
                    normalized = ' '.join(h['body'].casefold().split())
                    return any(all(' '.join(term.casefold().split()) in normalized for term in group) for group in c['evidence_groups'])
                pool=set(c['expected_files'])|{short[f] for f in c['expected_files'] if f in short}
                return h['file'] in pool or Path(h['file']).name in pool
            rank=next((i+1 for i,h in enumerate(hits) if relevant(h)),None)
            out['methods'][method]={'rank':rank,'hits':[dict(file=h['file'],heading=h['heading'],body=h['body']) for h in hits]}
        results.append(out)
    dump('results.json',results)
    summary={}
    for kind in ('evidence','legacy'):
        rows=[r for r in results if r['kind']==kind]
        summary[kind]={m:{'n':len(rows),'hit_at_1':sum(r['methods'][m]['rank']==1 for r in rows),
                         'hit_at_5':sum(r['methods'][m]['rank'] is not None for r in rows),
                         'mrr_at_5':round(sum(1/r['methods'][m]['rank'] if r['methods'][m]['rank'] else 0 for r in rows)/len(rows),3)} for m in methods}
    hashes=collections.Counter(r['sha256'] for r in manifest)
    summary['corpus']={'inventory_files':len(manifest),'current_files':len(current),'current_chunks':len(docs),
                       'expanded_files':len(expanded),'expanded_chunks':len(more),'duplicate_copies':sum(v-1 for v in hashes.values()),
                       'elapsed_seconds':round(time.time()-start,1),'network':'disabled','production_changed':False}
    dump('summary.json',summary)
    print(json.dumps(summary,indent=2),flush=True)

if __name__=='__main__':
    main()
