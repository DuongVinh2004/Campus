"""New-document test: add one unseen document to a COPY of the corpus, index it and ask questions about it.

The real index, database and corpus are never touched. The v2 core (understanding -> retrieval ->
generation -> verification) runs in process with the same gateway as the API; the safety and routing
nodes of the graph are not part of this test.

    build  --document newdoc/document.md            # writes data/rag_v2_index_newdoc (fresh; refuses to overwrite)
    run    --cases newdoc/cases.jsonl --out <json>   # one model-backed answer per case (--index/--corpus: any other snapshot)
    score  --results <json> --cases newdoc/cases.jsonl
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services/api/src"))
sys.path.insert(0, str(ROOT))
from evals.runners import rag_v2_scoring as scoring

DATASET = ROOT / "evals/datasets/rag-v2/newdoc"
CORPUS_DIR = ROOT / "data/rag_v2_newdoc_corpus"
INDEX_DIR = ROOT / "data/rag_v2_index_newdoc"
MAX_CHUNK = 1800


def chunks_of(document: Path) -> list[dict]:
    """Split by article heading and keep each table whole; merge short neighbours up to MAX_CHUNK."""
    lines = document.read_text(encoding="utf-8").strip().splitlines()
    if lines and lines[0].startswith("*"):      # the "simulated document" notice is not source text
        lines = lines[1:]
    text = "\n".join(lines)
    heading = next((re.sub(r"^#+\s*", "", ln).strip() for ln in lines if ln.startswith("## ")), lines[0])
    number = re.search(r"Số:\s*(\S+)", text)
    title = f"HUCE — {heading}" + (f" ({number.group(1)})" if number else "")
    blocks, current = [], []
    for line in lines:
        if re.match(r"^(#+\s*)?Điều\s+\d+", line) and current:
            blocks.append("\n".join(current).strip())
            current = []
        current.append(line)
    blocks.append("\n".join(current).strip())
    parts, tables = [], []
    for block in blocks:
        rows = [ln for ln in block.splitlines() if ln.lstrip().startswith("|")]
        prose = "\n".join(ln for ln in block.splitlines() if not ln.lstrip().startswith("|")).strip()
        if prose:
            parts.append(prose)
        if rows:
            tables.append("\n".join(rows))
    merged = []
    for part in parts + tables:
        if merged and len(merged[-1]) + len(part) + 2 <= MAX_CHUNK and not part.lstrip().startswith("|"):
            merged[-1] += "\n\n" + part
        else:
            merged.append(part)
    document_id = str(uuid5(NAMESPACE_URL, "newdoc:" + title))
    version_id = str(uuid5(NAMESPACE_URL, "newdoc-version:" + title))
    rows = []
    for number, body in enumerate(merged, 1):
        first = body.splitlines()[0].strip().lstrip("# ")[:80]
        rows.append({"chunk_id": str(uuid5(NAMESPACE_URL, f"newdoc-chunk:{title}:{number}")),
                     "document_id": document_id, "version_id": version_id, "doc_title": title,
                     "doc_family": "khac", "section_label": first, "page": number, "text": body})
    return rows


def build(args) -> int:
    new_rows = chunks_of(Path(args.document))
    if CORPUS_DIR.exists() or INDEX_DIR.exists():
        sys.exit("newdoc corpus/index already exist; choose a clean state (nothing is overwritten)")
    CORPUS_DIR.mkdir(parents=True)
    source = (ROOT / "evals/corpus/served-chunks.jsonl").read_text(encoding="utf-8")
    with (CORPUS_DIR / "served-chunks.jsonl").open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(source if source.endswith("\n") else source + "\n")
        for row in new_rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"{len(new_rows)} new chunks")
    return subprocess.call([sys.executable, "-B", str(ROOT / "scripts/rag_v2_build_index.py"),
                            "--corpus", str(CORPUS_DIR / "served-chunks.jsonl"), "--output", str(INDEX_DIR), "--embed"])


async def run(args) -> int:
    from campus247.bootstrap.settings import get_settings
    from campus247.infrastructure.llm.factory import create_llm_gateway
    from campus247.rag_v2.adapters.index_store import read_index
    from campus247.rag_v2.adapters.memory_index import MemoryIndex
    from campus247.rag_v2.adapters.runtime import AuthorizedIndex
    from campus247.rag_v2.service import RagV2Service
    from evals.runners.rag_v2_context_probe import embed
    from evals.runners.rag_v2_eval import campaign_manifest, writable_path, write_json

    snapshot = read_index(Path(args.index))
    index = MemoryIndex.__new__(MemoryIndex)
    index.manifest = snapshot.manifest
    index._initialize(snapshot.units, snapshot.embeddings, embed)
    rows = {}
    for line in Path(args.corpus).read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        rows[row["chunk_id"]] = {"chunk_id": row["chunk_id"], "content_text": row["text"], "title": row["doc_title"],
                                 "section_path": row["section_label"], "source_id": row["document_id"],
                                 "document_version_id": row["version_id"], "page_start": row["page"],
                                 "effective_from": None, "effective_until": None}
    authorized = AuthorizedIndex(index, {u.unit_id: u for u in snapshot.units}, rows=rows)
    service = RagV2Service(snapshot.facts)
    gateway = create_llm_gateway(settings=get_settings())
    cases = [json.loads(line) for line in Path(args.cases).read_text(encoding="utf-8").splitlines() if line.strip()]
    records = []
    manifest = campaign_manifest(cases, "in-process:RagV2Service", "v2")
    for case in cases:
        started = time.perf_counter()
        outcome = await service.answer(case["question"], (), gateway=gateway, index=authorized, reranker=None,
                                       embed=embed)
        records.append({"case_id": case["case_id"], "kind": str(getattr(outcome.kind, "value", outcome.kind)),
                        "repeat": 1, "attempt_index": 1, "seconds": time.perf_counter() - started,
                        "text": outcome.text, "cited_quotes": [c.quote for c in outcome.citations],
                        "statements": [s.text for s in outcome.statements]})
        print(case["case_id"], records[-1]["kind"], flush=True)
    write_json(writable_path(args.out), {"metadata": manifest, "records": records, "journal": records})
    return 0


def score(args) -> int:
    case_list = [json.loads(line) for line in Path(args.cases).read_text(encoding="utf-8").splitlines() if line.strip()]
    cases = {c["case_id"]: c for c in case_list}
    records = json.loads(Path(args.results).read_text(encoding="utf-8"))["records"]
    repeats = getattr(args, "repeat", 1)
    scoring.validate_records(records, case_list, repeats=repeats)
    full = thin = refused = wrong_ans = right_ref = errors = cited_ok = 0
    normalized_records = []
    for record in records:
        case = cases[record["case_id"]]
        normalized = record | {"outcome_class": record["kind"], "answer_text": record.get("text", ""),
                               "repeat": record.get("repeat", 1),
                               "final_event": record["kind"] not in {"transient_error", "error"},
                               "citation_chunk_ids": record.get("citation_chunk_ids", []),
                               "citation_count": sum(len(q.strip()) >= 20 for q in record.get("cited_quotes", [])),
                               "cited_texts": [q for q in record.get("cited_quotes", []) if len(q.strip()) >= 20]}
        if normalized["outcome_class"] == "transient_error":
            normalized["outcome_class"] = "error"
        normalized_records.append(normalized)
        label = scoring.classify(case, normalized)
        if label == "error":
            errors += 1
            continue
        answered = record["kind"] in scoring.ANSWERED
        if answered:
            cited_ok += any(scoring.quote_matches(case.get("quote", ""), q) for q in record.get("cited_quotes", []))
        if case["expected"] == "answer":
            if not answered:
                refused += 1
            elif label == "full":
                full += 1
            else:
                thin += 1
        elif answered:
            wrong_ans += 1
        else:
            right_ref += 1
    n_answer = sum(c["expected"] == "answer" for c in cases.values())
    normalized_cases = {cid: c | {"gold": c.get("gold", [{"chunk_id": "unresolved-newdoc-gold", "quote": c.get("quote", "")}]),
                                  "variant": c.get("variant", "form")} for cid, c in cases.items()}
    print(json.dumps({"answerable": n_answer, "full": full, "thin": thin, "refused": refused, "cited_quote_overlaps_gold": cited_ok,
                      "no_answer": len(cases) - n_answer, "correctly_declined": right_ref, "wrongly_answered": wrong_ans,
                      "errors": errors, "metrics": scoring.metrics(normalized_records, normalized_cases),
                      "limits": "Direct service path; SQL publication, routing, cross-user isolation and side effects are not measured"}, ensure_ascii=False))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    b = sub.add_parser("build")
    b.add_argument("--document", default=str(DATASET / "document.md"))
    r = sub.add_parser("run")
    r.add_argument("--cases", default=str(DATASET / "cases.jsonl"))
    r.add_argument("--out", required=True)
    r.add_argument("--index", default=str(INDEX_DIR))
    r.add_argument("--corpus", default=str(CORPUS_DIR / "served-chunks.jsonl"))
    s = sub.add_parser("score")
    s.add_argument("--results", required=True)
    s.add_argument("--cases", default=str(DATASET / "cases.jsonl"))
    s.add_argument("--repeat", type=int, default=1)
    args = parser.parse_args()
    if args.command == "build":
        return build(args)
    if args.command == "run":
        return asyncio.run(run(args))
    return score(args)


if __name__ == "__main__":
    raise SystemExit(main())
