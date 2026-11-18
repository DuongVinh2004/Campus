"""Measure the RAG on documents it has never seen.

The corpus the pipeline was tuned on proves nothing about a document added tomorrow. This runner takes plain-text documents from a folder
(default ``evals/datasets/unseen-docs``), pushes them through the real ingestion code (chunker, units, typed facts, scope vocabulary, local
BGE embeddings) into a throw-away in-memory index, and asks the real answering service (real generation and verification through the gateway
sidecar) the questions in ``questions.jsonl``. The running index is never touched.

Gold is machine-verified: every required or forbidden string must literally occur in the document the question names, and the answer text is
checked by code, not by a model. Scoring classes per question:

  helpful        expected=answer: answered/partial, every required fact present, no forbidden fact
  guided         expected=answer: a clarification question instead of an answer (useful, not a dead end)
  incomplete     expected=answer: answered, some but not all required facts, no forbidden fact
  off_target     expected=answer: answered with none of the required facts
  dead_end       expected=answer: refused or the turn failed
  wrong          any: a forbidden fact is shown, or an answer to a question that has none (expected abstain/oos)
  correct_stop   expected=abstain/oos: refusal or clarification

  python evals/runners/rag_unseen_doc_eval.py [--docs DIR] [--out FILE] [--only id,id] [--concurrency 2] [--no-llm-check]

``--no-llm-check`` only validates the gold against the documents (no embeddings, no provider calls).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import unicodedata
from collections import Counter, defaultdict
from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for extra in ("services/api/src", "services/worker/src", "scripts", "."):
    sys.path.insert(0, str(ROOT / extra))

DEFAULT_DOCS = ROOT / "evals/datasets/unseen-docs"
GATEWAY_URL = "http://127.0.0.1:8025"
GATEWAY_TOKEN = ROOT / "infra/local/public-rag-20261013/gateway-sidecar.token"
BGE_URL = "http://127.0.0.1:18081"


def fold(text: str) -> str:
    return " ".join(unicodedata.normalize("NFC", text).casefold().split())


def stable(*parts: str) -> str:
    digest = sha256("|".join(parts).encode()).hexdigest()
    return f"{digest[:8]}-{digest[8:12]}-7{digest[13:16]}-8{digest[17:20]}-{digest[20:32]}"


def load_questions(docs: Path):
    rows = [json.loads(line) for line in (docs / "questions.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    texts = {path.stem: path.read_text(encoding="utf-8") for path in sorted(docs.glob("*.txt"))}
    problems = []
    for row in rows:
        source = fold(texts.get(row["doc"], ""))
        if not source:
            problems.append(f"{row['id']}: unknown document {row['doc']}")
            continue
        for kind in ("required", "forbidden"):
            for fact in row[kind]:
                if fold(fact) not in source:
                    problems.append(f"{row['id']}: {kind} fact {fact!r} is not in {row['doc']}")
    return rows, texts, problems


def build_corpus(texts: dict[str, str]):
    from campus247_worker.knowledge import chunks_for_pages

    chunks = []
    for name, text in texts.items():
        title = text.splitlines()[0].strip()[:200] or name
        version = stable("version", name)
        for row in chunks_for_pages([{"page": 1, "text": text}], version, title):
            chunks.append({"chunk_id": row["id"], "document_id": stable("document", name), "version_id": version,
                           "doc_title": title, "section_label": row["section"], "page": row["page"], "text": row["text"]})
    return chunks


async def run(args) -> int:
    questions, texts, problems = load_questions(args.docs)
    if problems:
        print("GOLD PROBLEMS:\n  " + "\n  ".join(problems))
        return 2
    print(f"{len(questions)} questions over {len(texts)} documents: gold verified against the documents")
    if args.no_llm_check:
        return 0
    import httpx
    import numpy as np
    from campus247.infrastructure.llm.remote_gateway import RemoteGateway, read_token
    from campus247.rag_v2.adapters.memory_index import MemoryIndex
    from campus247.rag_v2.adapters.runtime import AuthorizedIndex
    from campus247.rag_v2.facts.extract import extract_facts
    from campus247.rag_v2.ingest.units import build_units
    from campus247.rag_v2.service import RagV2Service
    from campus247.rag_v2.vocabulary import Vocabulary
    from evals.runners.corpus_export import normalize_row
    from rag_v2_build_index import embed_units

    chunks = [normalize_row(row) for row in build_corpus(texts)]
    units = build_units(chunks)
    facts = extract_facts(units)
    print(f"{len(chunks)} chunks, {len(units)} units, {len(facts)} typed facts ({dict(Counter(f.kind for f in facts))})")
    matrix, _ = embed_units(units, batch_size=1)  # the local model server accepts one input per request

    async def embed(query):
        async with httpx.AsyncClient(base_url=BGE_URL, timeout=60, trust_env=False) as client:
            reply = await client.post("/embed", json={"inputs": [query], "normalize": True, "truncate": False})
            reply.raise_for_status()
            return np.array(reply.json()[0], dtype=np.float32)

    index = MemoryIndex.from_units(units, matrix, embed)
    rows = {c["chunk_id"]: {"content_text": c["text"], "source_id": c["document_id"], "document_version_id": c["version_id"],
                            "title": c["doc_title"], "section_path": c["section_label"], "page_start": c["page"]} for c in chunks}
    authorized = AuthorizedIndex(index, {u.unit_id: u for u in units}, rows=rows)
    gateway = RemoteGateway(GATEWAY_URL, read_token(str(GATEWAY_TOKEN)))

    class NoReranker:
        async def rerank(self, query, texts, *, deadline_s):
            return [0.0] * len(texts)

    if args.verbose:
        import campus247.rag_v2.service as service_module
        original = service_module.generate_draft

        async def traced(gateway_, question, understanding, read, **kwargs):
            draft = await original(gateway_, question, understanding, read, **kwargs)
            print(f"  [read {len(read)} units: " + "; ".join(u.path.split('>')[-1].strip()[:18] for u in read) + "]")
            print(f"  [query={question!r} terms={understanding.scope_terms} missing={understanding.missing_slots} decision={draft.decision}]")
            for statement in draft.statements:
                print("  [statement] " + statement.text[:160])
            return draft
        service_module.generate_draft = traced
    service = RagV2Service(facts, Vocabulary.from_units(units))   # names come from the documents just added
    wanted = set(args.only.split(",")) if args.only else None
    todo = [q for q in questions if wanted is None or q["id"] in wanted]
    gate = asyncio.Semaphore(args.concurrency)
    results = []

    async def one(item):
        async with gate:
            try:
                outcome = await service.answer(item["question"], (), gateway=gateway, index=authorized, reranker=NoReranker(), embed=embed)
                if args.verbose:
                    print(f"  [{item['id']}] outcome={outcome.kind} reason={getattr(outcome, 'reason', None)} citations={len(outcome.citations)} trace={outcome.trace}")
                text = "\n".join(filter(None, (outcome.text, *getattr(outcome, "suggestions", ()))))
                record = {"id": item["id"], "kind": item["kind"], "expected": item["expected"], "outcome": outcome.kind,
                          "text": outcome.text, "reason": getattr(outcome, "reason", None), "scored_text": text}
            except Exception as error:  # noqa: BLE001 -- a crashed turn is a failed turn, reported as such
                record = {"id": item["id"], "kind": item["kind"], "expected": item["expected"], "outcome": "crash",
                          "text": f"{type(error).__name__}: {error}"[:300], "reason": None, "scored_text": ""}
            record["class"] = score(item, record)
            results.append(record)
            print(f"{record['class']:>12}  {item['id']:<8} {item['kind']:<20} {record['outcome']}", flush=True)

    await asyncio.gather(*(one(item) for item in todo))
    results.sort(key=lambda r: r["id"])
    summary = summarize(results)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({"summary": summary, "results": results}, ensure_ascii=False, indent=1), encoding="utf-8")
    print_summary(summary)
    return 0


def score(item, record) -> str:
    kind, text = record["outcome"], fold(record["scored_text"])
    present = [f for f in item["required"] if fold(f) in text]
    forbidden = [f for f in item["forbidden"] if fold(f) in text]
    if item["expected"] in ("abstain", "oos"):
        if forbidden:
            return "wrong"
        return "correct_stop" if kind in ("refuse", "clarify") else "wrong"
    if kind in ("refuse", "transient_error", "crash"):
        return "dead_end"
    if kind == "clarify":
        return "guided"
    if forbidden:
        return "wrong"
    if len(present) == len(item["required"]):
        return "helpful"
    return "incomplete" if present else "off_target"


def summarize(results):
    by_kind = defaultdict(Counter)
    for r in results:
        by_kind[r["kind"]][r["class"]] += 1
    total = Counter(r["class"] for r in results)
    good = total["helpful"] + total["correct_stop"]
    return {"total": len(results), "good": good, "good_rate": round(good / max(1, len(results)), 3),
            "classes": dict(total), "by_kind": {k: dict(v) for k, v in sorted(by_kind.items())}}


def print_summary(summary):
    print(f"\n{summary['good']}/{summary['total']} good ({summary['good_rate']:.0%}); classes {summary['classes']}")
    for kind, classes in summary["by_kind"].items():
        print(f"  {kind:<20} {classes}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--docs", type=Path, default=DEFAULT_DOCS)
    parser.add_argument("--out", type=Path, default=ROOT / "evals/results/unseen-docs/latest.json")
    parser.add_argument("--only", default="")
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--no-llm-check", action="store_true", help="only validate the gold against the documents")
    parser.add_argument("--verbose", action="store_true", help="print what the generator wrote and which units it read")
    return asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
