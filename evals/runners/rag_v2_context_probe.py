"""Offline ceiling of the generator context: are the required facts inside the packed parent rows?

Mirrors the service's context packing (top fused units -> distinct parent rows, <=6 rows, <=19,000
JSON bytes) with the real corpus text, with and without sub-question retrieval. No model call.

    .venv/Scripts/python.exe -B evals/runners/rag_v2_context_probe.py --split dev --out <json>
"""
from __future__ import annotations

import argparse
import asyncio
import json
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
    args = parser.parse_args()
    index = MemoryIndex(ROOT / args.index, embed)
    chunks = {}
    for line in (ROOT / "evals/corpus/served-chunks.jsonl").read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        chunks[row["chunk_id"]] = row["text"]
    cases = [json.loads(l) for l in (ROOT / "evals/datasets/rag-v2/cases.jsonl").read_text(encoding="utf-8").splitlines()]
    cases = [c for c in cases if c["split"] == args.split and c["expected"] == "answer"]
    stats = defaultdict(lambda: defaultdict(int))
    for case in cases:
        facts = case["required_facts"]
        configs = {"base": {}, "lex80": {"lex": 80, "vec": 80}, "per20": {"per_query": 20, "lex": 80, "vec": 80},
                   "rows8": {"max_rows": 8, "per_query": 20, "lex": 80, "vec": 80, "max_bytes": 19_000},
                   "bytes22": {"max_rows": 8, "per_query": 20, "lex": 80, "vec": 80, "max_bytes": 22_000}}
        for name in args.variants.split(","):
            extra = []
            rows = await pack(index, chunks, case["question"], extra, **configs[name])
            blob = " ".join(chunks[r] for r in rows)
            ok = bool(facts) and all(fact_matches(f, blob) for f in facts)
            stats[name]["n"] += 1
            stats[name]["all_facts"] += int(ok)
            stats[name]["gold_row"] += int(any(g["chunk_id"] in rows for g in case["gold"]))
            stats[name][f"v_{case['variant']}"] += int(ok)
    Path(args.out).write_text(json.dumps({k: dict(v) for k, v in stats.items()}, indent=1), encoding="utf-8")
    print(json.dumps({k: dict(v) for k, v in stats.items()}))


if __name__ == "__main__":
    asyncio.run(main())
