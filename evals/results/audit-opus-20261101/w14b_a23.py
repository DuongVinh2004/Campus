"""Measure AU-A23 ranks and exact packed source text without a provider call."""
import asyncio
import importlib.util
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT / "services/api/src"), str(ROOT)]
spec = importlib.util.spec_from_file_location("w14_probe", ROOT / "evals/runners/rag_v2_context_probe.py")
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)
from campus247.rag_v2.ingest.units import source_text
from campus247.rag_v2.retrieval import hybrid
from campus247.rag_v2.understanding.analyze import analyze
from evals.runners.rag_v2_eval import fact_matches


async def main():
    output = HERE / "w14b-AU-A23.json"
    assert output.resolve().is_relative_to(ROOT) and not output.exists()
    case = next(row for line in (HERE / "cases.jsonl").read_text(encoding="utf-8").splitlines()
                if (row := json.loads(line))["case_id"] == "AU-A23")
    corpus = {row["chunk_id"]: row for line in (ROOT / "evals/corpus/served-chunks.jsonl").read_text(encoding="utf-8").splitlines()
              if (row := json.loads(line))}
    base = probe.MemoryIndex(ROOT / "data/rag_v2_index/embedded3", probe.embed)
    index = probe.authorized_index(base, corpus, allowed=set(base.all_ids()))
    u = analyze(case["question"], ())
    target = [index.get(uid) for uid in index.all_ids()
              if source_text(index.get(uid)).startswith("29 Logistics đô thị Cầu Đường Cử nhân")]
    assert len(target) == 1 and target[0].kind == "table_row"
    allowed = {uid for uid in index.all_ids() if hybrid.scope_allows(u, index.get(uid))}
    queries = {"original": u.search_query, "focused": hybrid.focused_query(u.search_query)}
    ranks = {name: next((i for i, (uid, _) in enumerate(index.lexical(q, len(allowed), allowed=allowed), 1)
                        if uid == target[0].unit_id), None) for name, q in queries.items()}
    out = {"case_id": case["case_id"], "required_facts": case["required_facts"],
           "queries": queries, "target": asdict(target[0]), "lexical_ranks": ranks, "provider_calls": 0}
    for label, flag in (("A", False), ("B", True)):
        hybrid.FOCUSED_LEXICAL = flag
        retrieval = await hybrid.retrieve(u, index, None, rerank_deadline_s=0, final_limit=12)
        context = await probe.runtime_context(index, case["question"])
        blob = " ".join(source["text"] for source in context["units"])
        out[label] = {"focused_lexical": flag,
                      "facts_in_context": all(fact_matches(f, blob) for f in case["required_facts"]),
                      "line29_in_context": source_text(target[0]) in blob,
                      "target_in_retrieved_candidates": target[0].unit_id in [c.unit_id for c in retrieval.candidates],
                      "target_parent_packed": bool(set(target[0].chunk_ids).intersection(context["chunk_ids"])),
                      "candidates": [asdict(c) for c in retrieval.candidates], "trace": dict(retrieval.trace),
                      "context": context}
    with output.open("x", encoding="utf-8") as handle:
        json.dump(out, handle, ensure_ascii=False, indent=2)
    print(json.dumps({"lexical_ranks": ranks, **{label: {key: value for key, value in out[label].items()
                     if key not in {"candidates", "context", "trace"}} for label in ("A", "B")}}))


asyncio.run(main())
