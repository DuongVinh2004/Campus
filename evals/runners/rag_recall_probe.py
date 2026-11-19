"""Retrieval recall@k against machine-verified gold, measured exactly where the service retrieves.

For every answerable case of a cases file (default: the sealed hold-out) it runs the same analyse + retrieve call the
service uses (fused BM25 + vector + anchored RRF, no rerank deadline) and finds the best rank of
  chunk_hit  a unit that overlaps a gold chunk (loose: the same page/chunk), and
  quote_hit  a unit whose text contains the gold quote itself (strict).
No generation model is called. Prints recall@5/@12/@40 overall and per phrasing variant, and the missed case ids.

  python evals/runners/rag_recall_probe.py --cases evals/datasets/rag-v2/holdout-natural-20261114.jsonl \
      --index data/rag_v2_index/embedded2 --out evals/results/rag-natural-20261114/recall-holdout.json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import time
import unicodedata
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services/api/src"))

import httpx  # noqa: E402
from campus247.rag_v2.adapters.http_reranker import HTTPReranker  # noqa: E402
from campus247.rag_v2.adapters.memory_index import MemoryIndex  # noqa: E402
from campus247.rag_v2.retrieval.hybrid import retrieve  # noqa: E402
from campus247.rag_v2.understanding.analyze import analyze  # noqa: E402

KS = (5, 12, 40)


async def embed(text: str):
    async with httpx.AsyncClient(trust_env=False) as client:
        response = await client.post("http://127.0.0.1:18081/embed",
                                     json={"inputs": [text], "normalize": True, "truncate": False}, timeout=30)
        response.raise_for_status()
        return response.json()[0]


def norm(text: str) -> str:
    text = unicodedata.normalize("NFC", text).replace("​", "")
    return re.sub(r"\s+", " ", text).strip().lower()


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", default="evals/datasets/rag-v2/holdout-natural-20261114.jsonl")
    parser.add_argument("--index", default="data/rag_v2_index/embedded2")
    parser.add_argument("--out", required=True)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()
    index = MemoryIndex(ROOT / args.index, embed)
    reranker = HTTPReranker(batch_size=10)
    cases = [json.loads(l) for l in (ROOT / args.cases).read_text(encoding="utf-8").splitlines() if l.strip()]
    cases = [c for c in cases if c["expected"] == "answer" and c.get("gold")]
    if args.limit:
        cases = cases[:args.limit]
    unit_chunks = {uid: set(index.get(uid).chunk_ids) for uid in index.all_ids()}
    unit_text = {uid: norm(index.get(uid).text) for uid in index.all_ids()}
    rows, started = [], time.time()
    for n, case in enumerate(cases, 1):
        gold_chunks = {g["chunk_id"] for g in case["gold"]}
        quotes = [norm(g["quote"]) for g in case["gold"] if g.get("quote")]
        u = analyze(case["question"], ())
        res = await retrieve(u, index, reranker, preselect=40, rerank_deadline_s=0, final_limit=40)
        order = [c.unit_id for c in res.candidates]
        chunk_rank = next((i for i, uid in enumerate(order, 1) if unit_chunks[uid] & gold_chunks), None)
        quote_rank = next((i for i, uid in enumerate(order, 1) if any(q and q in unit_text[uid] for q in quotes)), None)
        rows.append({"case_id": case["case_id"], "style": case.get("style"), "family": case.get("family"),
                     "chunk_rank": chunk_rank, "quote_rank": quote_rank, "returned": len(order),
                     "clarify_or_oos": bool(u.clarify_prompt or u.out_of_scope)})
        if n % 25 == 0:
            print(f"{n}/{len(cases)} {time.time() - started:.0f}s", flush=True)
    out = {"n": len(rows), "rows": rows, "seconds": round(time.time() - started)}
    for label in ("chunk", "quote"):
        out[label] = {f"@{k}": sum(1 for r in rows if r[f"{label}_rank"] and r[f"{label}_rank"] <= k) / len(rows) for k in KS}
    by_style = defaultdict(list)
    for r in rows:
        by_style[r["style"]].append(r)
    out["by_style"] = {s: {f"quote@{k}": sum(1 for r in v if r["quote_rank"] and r["quote_rank"] <= k) / len(v) for k in KS} | {"n": len(v)}
                       for s, v in by_style.items()}
    out["missed_quote@12"] = [r["case_id"] for r in rows if not (r["quote_rank"] and r["quote_rank"] <= 12)]
    Path(ROOT / args.out).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("n", "seconds", "chunk", "quote", "by_style")}, ensure_ascii=False, indent=1))
    print("early exits (clarify/out-of-scope before retrieval):", sum(r["clarify_or_oos"] for r in rows))


if __name__ == "__main__":
    asyncio.run(main())
