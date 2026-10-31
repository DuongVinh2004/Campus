"""Offline ceiling of the generator context: are the required facts inside the packed parent rows?

Mirrors the service's context packing (top fused units -> distinct parent rows, <=6 rows, <=19,000
JSON bytes) with the real corpus text, with and without sub-question retrieval. No model call.

    .venv/Scripts/python.exe -B evals/runners/rag_v2_context_probe.py --split dev --out <json>
"""
from __future__ import annotations

import argparse
import asyncio
import json
import hashlib
import math
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services/api/src"))

import httpx  # noqa: E402
from campus247.rag_v2.adapters.memory_index import MemoryIndex  # noqa: E402
from campus247.rag_v2.retrieval.hybrid import retrieve  # noqa: E402
from campus247.rag_v2.understanding.analyze import analyze  # noqa: E402

sys.path.insert(0, str(ROOT))
from evals.runners.rag_v2_eval import fact_matches  # noqa: E402


def cached_embed(records):
    """Immutable query cache; misses/invalid vectors fail without HTTP fallback."""
    vectors = {}
    dimension = None
    for row in records:
        text = row.get("text", row.get("question"))
        key = hashlib.sha256(text.encode()).hexdigest() if text is not None else row.get("text_sha256")
        vector = tuple(row["embedding"])
        if (not key or not vector or any(type(x) not in (int, float) or not math.isfinite(x) for x in vector)
                or not any(vector) or dimension is not None and len(vector) != dimension):
            raise ValueError("Invalid embedding cache")
        if key in vectors and vectors[key] != vector:
            raise ValueError("Conflicting embedding cache entries")
        vectors[key], dimension = vector, len(vector)
    async def lookup(text):
        key = hashlib.sha256(text.encode()).hexdigest()
        if key not in vectors:
            raise ValueError("Query missing from immutable embedding cache")
        return vectors[key]
    return lookup


def authorized_index(index, chunks, *, allowed):
    from campus247.rag_v2.adapters.runtime import AuthorizedIndex
    if not set(allowed) <= set(index.all_ids()):
        raise ValueError("Simulated grant contains unknown unit IDs")
    units = {uid: index.get(uid) for uid in index.all_ids() if uid in allowed}
    chunk_ids = {cid for unit in units.values() for cid in unit.chunk_ids}
    rows = {cid: {"chunk_id": cid, "content_text": r.get("text", r.get("content_text", "")),
        "title": r.get("doc_title", r.get("title", "")), "section_path": r.get("section_label", ""),
        "source_id": r.get("document_id", r.get("source_id")),
        "document_version_id": r.get("version_id", r.get("document_version_id")),
        "page_start": r.get("page", r.get("page_start")), "effective_from": r.get("effective_from"),
        "effective_until": r.get("effective_until")} for cid, r in chunks.items() if cid in chunk_ids}
    return AuthorizedIndex(index, units, rows=rows)


def context_hash(sources):
    return hashlib.sha256(json.dumps(sources, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":")).encode()).hexdigest()


async def runtime_context(index, question):
    """Capture the REAL service/generator payload with a local recording gateway.

    No mirror of packing limits: changes to runtime packing are exercised here.
    Facts are empty to probe the retrieval/generation path. Authorization is
    simulated, not SQL/release authorization verification.
    """
    from campus247.rag_v2.service import RagV2Service
    from campus247.rag_v2.generation.contacts import contact_map, redact
    class Captured(BaseException):
        pass
    class View:
        def __init__(self, index):
            self.index, self.parents = index, []
        def __getattr__(self, name):
            return getattr(self.index, name)
        def chunk_unit(self, chunk_id):
            unit = self.index.chunk_unit(chunk_id)
            if unit is not None:
                self.parents.append(unit)
            return unit
    class Gateway:
        sources = []
        async def generate(self, request):
            content = "".join(item["content"] for item in request.input_items)
            self.sources = json.loads(content)["sources"]
            # Stop before provider/semantic work or generation debug capture.
            raise Captured()
    gateway = Gateway()
    view = View(index) if hasattr(index, "chunk_unit") else index
    try:
        await RagV2Service().answer(question, (), gateway=gateway, index=view, reranker=None, embed=None)
    except Captured:
        pass
    candidates = list(getattr(view, "parents", []))
    candidates += [index.get(uid) for uid in index.all_ids()]
    candidates = [u for u in candidates if u is not None]
    markers = contact_map(candidates)
    selected, seen = [], set()
    for source in gateway.sources:
        unit = next((u for u in candidates if u.unit_id not in seen and redact(u.text, markers) == source["text"]), None)
        if unit is not None:
            selected.append(unit)
            seen.add(unit.unit_id)
    chunk_ids = sorted({cid for u in selected for cid in u.chunk_ids})
    return {"units": gateway.sources, "chunk_ids": chunk_ids, "context_sha256": context_hash(gateway.sources),
            "packing": "RagV2Service -> generate_draft (recording gateway)", "provider_calls": 0}


async def embed(text: str):
    async with httpx.AsyncClient(trust_env=False) as client:
        response = await client.post("http://127.0.0.1:18081/embed",
            json={"inputs": [text], "normalize": True, "truncate": False}, timeout=30)
        response.raise_for_status()
        return response.json()[0]


def sub_questions(question: str) -> list[str]:
    parts = [p.strip(" ,;?.") for p in re.split(r"\?|;|, và |,? và |, còn |\bcòn\b", question) if len(p.strip()) > 12]
    return parts if len(parts) > 1 else []


async def pack(index, chunks, question, extra, *, max_rows=6, max_bytes=19_000, per_query=12, lex=40, vec=40):
    rows, seen, used = [], set(), 0
    queries = [question] + extra
    ranked = []
    for q in queries:
        u = analyze(q, ())
        if u.out_of_scope or u.clarify_prompt:
            continue
        res = await retrieve(u, index, None, lexical_k=lex, vector_k=vec, preselect=max(40, per_query), rerank_deadline_s=0, final_limit=per_query)
        ranked.append([c.unit_id for c in res.candidates])
    # interleave: best of each query first
    order = [uid for tier in zip(*[r + [None] * (per_query - len(r)) for r in ranked]) for uid in tier if uid]
    for uid in order:
        chunk_id = index.get(uid).chunk_ids[0]
        if chunk_id in seen or chunk_id not in chunks:
            continue
        size = len(json.dumps(chunks[chunk_id], ensure_ascii=False).encode())
        if len(rows) < max_rows and used + size <= max_bytes:
            rows.append(chunk_id); seen.add(chunk_id); used += size
    return rows


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", default="dev")
    parser.add_argument("--index", default="data/rag_v2_index/embedded")
    parser.add_argument("--out", required=True)
    parser.add_argument("--variants", default="base")
    parser.add_argument("--cases", default="evals/datasets/rag-v2/cases.jsonl")
    parser.add_argument("--corpus", default="evals/corpus/served-chunks.jsonl")
    parser.add_argument("--authorized", action="store_true")
    parser.add_argument("--allowed", help="JSON array of simulated allowed unit IDs (required with --authorized)")
    parser.add_argument("--embed-cache", help="JSONL text/embedding cache; no HTTP when supplied")
    args = parser.parse_args()
    embedding = cached_embed([json.loads(l) for l in Path(args.embed_cache).read_text(encoding="utf-8").splitlines()
                              if l.strip()]) if args.embed_cache else embed
    index = MemoryIndex(ROOT / args.index, embedding)
    chunks = {}
    corpus = {}
    for line in (ROOT / args.corpus).read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        chunks[row["chunk_id"]] = row["text"]
        corpus[row["chunk_id"]] = row
    if args.authorized:
        if not args.allowed:
            parser.error("--authorized requires --allowed")
        allowed = json.loads(Path(args.allowed).read_text(encoding="utf-8"))
        index = authorized_index(index, corpus, allowed=set(allowed))
    cases = [json.loads(l) for l in (ROOT / args.cases).read_text(encoding="utf-8").splitlines()]
    cases = [c for c in cases if c["split"] == args.split and c["expected"] == "answer"]
    if args.embed_cache:
        for case in cases:
            await embedding(analyze(case["question"], ()).search_query)
    stats = defaultdict(lambda: defaultdict(int))
    contexts = []
    for case in cases:
        facts = case["required_facts"]
        configs = {"base": {}, "lex80": {"lex": 80, "vec": 80}, "per20": {"per_query": 20, "lex": 80, "vec": 80},
                   "rows8": {"max_rows": 8, "per_query": 20, "lex": 80, "vec": 80, "max_bytes": 19_000},
                   "bytes22": {"max_rows": 8, "per_query": 20, "lex": 80, "vec": 80, "max_bytes": 22_000}}
        for name in args.variants.split(","):
            extra = []
            if args.authorized:
                if name != "base":
                    parser.error("--authorized uses runtime limits; only --variants base is supported")
                context = await runtime_context(index, case["question"])
                contexts.append({"case_id": case["case_id"], "context_sha256": context["context_sha256"],
                                 "chunk_ids": context["chunk_ids"]})
                rows = context["chunk_ids"]
                blob = " ".join(s["text"] for s in context["units"])
            else:
                rows = await pack(index, chunks, case["question"], extra, **configs[name])
                blob = " ".join(chunks[r] for r in rows)
            ok = bool(facts) and all(fact_matches(f, blob) for f in facts)
            stats[name]["n"] += 1
            stats[name]["all_facts"] += int(ok)
            stats[name]["gold_row"] += int(any(g["chunk_id"] in rows for g in case["gold"]))
            stats[name][f"v_{case['variant']}"] += int(ok)
    from evals.runners.rag_v2_eval import writable_path, write_json
    write_json(writable_path(args.out), {"summary": {k: dict(v) for k, v in stats.items()},
        "contexts": contexts, "authorized": args.authorized, "embedding_mode": "cache" if args.embed_cache else "http"})
    print(json.dumps({k: dict(v) for k, v in stats.items()}))


if __name__ == "__main__":
    asyncio.run(main())
