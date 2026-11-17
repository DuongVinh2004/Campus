"""Offline retrieval probe for RAG v2: where does the gold unit get lost? (no generation model call)

Loads the v2 index in-process, uses the loopback embedding/rerank servers, and for every
answerable case reports the best rank of any unit that overlaps a gold chunk after fusion
(RRF) and the share that survive preselect + rerank. Prints only counts and case ids.

    .venv/Scripts/python.exe -B evals/runners/rag_v2_retrieval_probe.py --split dev --limit 120 --out <json>
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services/api/src"))
sys.path.insert(0, str(ROOT))

import httpx  # noqa: E402
from campus247.rag_v2.adapters.http_reranker import HTTPReranker  # noqa: E402
from campus247.rag_v2.adapters.memory_index import MemoryIndex  # noqa: E402
from campus247.rag_v2.retrieval.hybrid import retrieve  # noqa: E402
from campus247.rag_v2.retrieval.neighbors import expand_neighbors  # noqa: E402
from campus247.rag_v2.understanding.analyze import analyze  # noqa: E402


async def embed(text: str):
    async with httpx.AsyncClient(trust_env=False) as client:
        response = await client.post("http://127.0.0.1:18081/embed",
            json={"inputs": [text], "normalize": True, "truncate": False}, timeout=30)
        response.raise_for_status()
        return response.json()[0]


def _norm(text: str) -> str:
    import re
    import unicodedata
    text = unicodedata.normalize("NFD", text.lower())
    text = "".join(c for c in text if unicodedata.category(c) != "Mn").replace("đ", "d")
    text = re.sub(r"(?<=\d)[.,](?=\d{3})", "", text)
    return re.sub(r"\s+", " ", text)


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", default="data/rag_v2_index/embedded")
    parser.add_argument("--cases", default="evals/datasets/rag-v2/cases.jsonl")
    parser.add_argument("--split", default="dev")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--stride", type=int, default=1, help="take every Nth answerable case for a spread sample")
    parser.add_argument("--out", required=True)
    parser.add_argument("--no-rerank", action="store_true")
    parser.add_argument("--all-cases", action="store_true", help="include abstain/clarify cases (records top rerank score)")
    parser.add_argument("--authorized", action="store_true")
    parser.add_argument("--allowed", help="JSON array of simulated allowed unit IDs")
    parser.add_argument("--corpus", default="evals/corpus/served-chunks.jsonl")
    parser.add_argument("--embed-cache", help="Immutable JSONL query embedding cache; disables HTTP reranker")
    args = parser.parse_args()
    from evals.runners.rag_v2_context_probe import cached_embed, authorized_index, runtime_context
    embedding = cached_embed([json.loads(l) for l in Path(args.embed_cache).read_text(encoding="utf-8").splitlines()
                              if l.strip()]) if args.embed_cache else embed
    index = MemoryIndex(ROOT / args.index, embedding)
    if args.authorized:
        if not args.allowed:
            parser.error("--authorized requires --allowed")
        chunks = {r["chunk_id"]: r for r in map(json.loads, Path(args.corpus).read_text(encoding="utf-8").splitlines())}
        index = authorized_index(index, chunks, allowed=set(json.loads(Path(args.allowed).read_text(encoding="utf-8"))))
    if args.embed_cache:
        args.no_rerank = True
    reranker = None if args.no_rerank else HTTPReranker(batch_size=10)
    cases = [json.loads(line) for line in (ROOT / args.cases).read_text(encoding="utf-8").splitlines()]
    cases = [c for c in cases if c["split"] == args.split and (args.all_cases or c["expected"] == "answer")][::args.stride]
    if args.limit:
        cases = cases[:args.limit]
    if args.embed_cache:
        for case in cases:
            await embedding(analyze(case["question"], ()).search_query)
    unit_chunks = {uid: set(index.get(uid).chunk_ids) for uid in index.all_ids()}
    rows, summary = [], defaultdict(lambda: defaultdict(int))
    for case in cases:
        gold = {g["chunk_id"] for g in case["gold"]}
        answerable = case["expected"] == "answer"
        u = analyze(case["question"], ())
        key = (case["family"], case["variant"])
        top = None
        summary[key]["n"] += 1
        if u.clarify_prompt or u.out_of_scope:
            summary[key]["early_exit"] += 1
            rows.append({"case_id": case["case_id"], "early_exit": "clarify" if u.clarify_prompt else "oos",
                         "context_sha256": (await runtime_context(index, case["question"]))["context_sha256"]})
            continue
        fused = await retrieve(u, index, reranker, preselect=40, rerank_deadline_s=0, final_limit=40)
        order = [c.unit_id for c in fused.candidates]
        fused_all = [uid for uid in order]
        rank = next((i for i, uid in enumerate(fused_all, 1) if unit_chunks[uid] & gold), None) if answerable else None
        final = None
        if not args.no_rerank:
            res = await retrieve(u, index, reranker, min_rerank_logit=-100.0)
            final_ids = [c.unit_id for c in res.candidates]
            top = max((c.rerank_score for c in res.candidates if c.rerank_score is not None), default=None)
            gold_scores = [c.rerank_score for c in res.candidates if unit_chunks[c.unit_id] & gold and c.rerank_score is not None]
            final = next((i for i, uid in enumerate(final_ids, 1) if unit_chunks[uid] & gold), None)
            summary[key]["rerank_fallback"] += int(res.fallback_used)
            summary[key]["final_hit"] += int(final is not None)
            summary[key]["final_empty"] += int(not final_ids)
        summary[key]["fused_top8_hit"] += int(rank is not None and rank <= 8)
        facts = [_norm(f) for f in case.get("required_facts", [])]
        for k in (8, 12, 16, 24):
            blob = " ".join(_norm(index.get(uid).text) for uid in fused_all[:k])
            summary[key][f"facts_in_top{k}"] += int(bool(facts) and all(f in blob for f in facts))
        for seeds, cap in ((4, 16), (6, 16), (8, 20), (8, 24)):
            ids = expand_neighbors(fused_all[:12], index, seeds=seeds, cap=cap)
            blob = " ".join(_norm(index.get(uid).text) for uid in ids)
            summary[key][f"facts_nb_{seeds}_{cap}"] += int(bool(facts) and all(f in blob for f in facts))
        for k in (5, 10, 12, 16):
            summary[key][f"fused_top{k}_hit"] += int(rank is not None and rank <= k)
        summary[key]["any_hit"] += int(rank is not None)
        rows.append({"case_id": case["case_id"], "expected": case["expected"], "variant": case["variant"],
                     "fused_rank": rank, "final_rank": final, "top_score": top if not args.no_rerank else None,
                     "gold_top_score": max(gold_scores) if not args.no_rerank and gold_scores else None,
                     "fallback": res.fallback_used if not args.no_rerank else None,
                     "context_sha256": (await runtime_context(index, case["question"]))["context_sha256"]})
    out = {"summary": {f"{k[0]}|{k[1]}": dict(v) for k, v in summary.items()}, "rows": rows,
           "authorized": args.authorized, "embedding_mode": "cache" if args.embed_cache else "http",
           "rerank_mode": "disabled" if args.no_rerank else "http"}
    from evals.runners.rag_v2_eval import writable_path, write_json
    write_json(writable_path(args.out), out)
    totals = defaultdict(int)
    for v in summary.values():
        for k, n in v.items():
            totals[k] += n
    print(json.dumps(dict(totals)))


if __name__ == "__main__":
    asyncio.run(main())
