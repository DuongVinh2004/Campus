"""Two frozen failures through current source retrieval, without paid generation.

Read-only database sessions; no runtime start/refresh/ack or gateway writer.
All source text retained here is from the existing public release.
"""
import asyncio
import hashlib
import json
from datetime import UTC, datetime

from knowledge_platform import ROOT, TENANT, checked_path, components, model_budget, retain
from campus247.domain.retrieval import AuthorizedScope, RetrievalContext, SimulationPolicy


async def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--lexical-only", action="store_true", help="No inference; inspect authorized FTS and preselection")
    parser.add_argument("--query", help="One explicit bounded public-source diagnostic question")
    parser.add_argument("--rehearsal", help="Exact verified rehearsal manifest; source database remains read-only")
    args = parser.parse_args()
    scope = checked_path(ROOT / "infra/local/knowledge-automation-20261026" /
        ("retrieval-diagnostic-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")), ROOT)
    baseline = checked_path(ROOT / "infra/local/knowledge-automation-20261026/independent-text-baseline-01.json", ROOT)
    cases = [c for c in json.loads(baseline.read_text(encoding="utf-8"))["cases"]
        if c["name"] in {"fresh_transfer_ceiling", "fresh_no_registration_reason"}]
    if len(cases) != 2:
        raise ValueError("Exactly two retained failures required")
    if args.query is not None:
        if not 3 <= len(args.query) <= 2000:
            raise ValueError("One bounded question required")
        cases = [{"name": "explicit-diagnostic", "question": args.query}]
    context = RetrievalContext(AuthorizedScope(TENANT, "HUCE", "local-public-diagnostic",
        frozenset({"STUDENT"}), frozenset({"STUDENT"}), frozenset({"FIT"}), frozenset({"PUBLIC"})),
        "vi", datetime.now(UTC), SimulationPolicy.DENY, "d" * 32)
    report = {"started_at": datetime.now(UTC), "paid_generation_calls": 0,
        "mode": "candidate-source retrieval diagnostic; no answer-quality acceptance",
        "native_before": model_budget(), "cases": []}
    pool, _, _, runtime = await components(rehearsal=checked_path(ROOT / args.rehearsal, ROOT) if args.rehearsal else None)
    import httpx
    async def capture_status(response):
        if response.status_code != 200:
            await response.aread()
            item.setdefault("native_failures", []).append({"status": response.status_code,
                "body": response.json()})
    for adapter, port in ((runtime.embedding, 18081), (runtime.reranker, 18082)):
        adapter._client_factory = lambda port=port: httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}",
            trust_env=False, follow_redirects=False, event_hooks={"response": [capture_status]})
    original_setup = pool._setup
    async def readonly(conn):
        if original_setup:
            await original_setup(conn)
        await conn.execute("SET default_transaction_read_only=on")
    pool._setup = readonly
    try:
        # Existing pool connections also get the same enforced read-only mode.
        async with pool.acquire() as conn:
            await conn.execute("SET default_transaction_read_only=on")
            report["database"] = await conn.fetchval("SELECT current_database()")
            pointer = await runtime.repo.pointer(conn)
        report["pointer"] = pointer
        async with pool.acquire() as conn:
            report["target_source_chunks"] = [dict(row) for row in await conn.fetch("""SELECT c.id,
                c.document_version_id,c.section_path,c.page_start,c.content_text,c.content_checksum
                FROM knowledge_release_member rm JOIN knowledge_chunk c ON c.document_version_id=rm.version_id
                WHERE rm.release_id=$1 AND (c.content_text ILIKE '%chuyển đổi kết quả%'
                OR c.content_text ILIKE '%không đăng ký học%') ORDER BY c.id""", pointer["release_id"])]
        def row_view(row):
            return {k: row.get(k) for k in ("id", "source_id", "document_version_id", "title",
                "section_path", "page_start", "content_checksum", "rerank_text", "content_text")}
        for case in cases:
            item = {"name": case["name"], "question": case["question"], "branches": []}
            report["cases"].append(item)
            original_rows = runtime._rows
            original_rerank = runtime.reranker.rerank
            async def capture_rows(conn, query, ctx, release, **kwargs):
                rows = await original_rows(conn, query, ctx, release, **kwargs)
                if kwargs.get("ids") is None:
                    item["branches"].append({"branch": "semantic" if kwargs.get("vector") else "lexical",
                        "query": query, "rows": [row_view(r) for r in rows]})
                return rows
            async def capture_rerank(request):
                item["rerank_query"] = request.query.text
                batch = {"query": request.query.text,
                    "inputs": [{"id": c.chunk_id, "text": c.content_text} for c in request.candidates]}
                item.setdefault("rerank_batches", []).append(batch)
                item.setdefault("rerank_inputs", []).extend(batch["inputs"])
                result = await original_rerank(request)
                batch["scores"] = [{"id": r.chunk_id, "score": r.score} for r in result.ranked]
                item.setdefault("rerank_scores", []).extend(batch["scores"])
                return result
            runtime._rows = capture_rows
            runtime.reranker.rerank = capture_rerank
            try:
                if args.lexical_only:
                    from campus247.application.retrieval.candidate_selection import select_parent_spans
                    async with pool.acquire() as conn:
                        rows = await runtime._rows(conn, case["question"], context, pointer["release_id"])
                    results = [row_view(r) for r in select_parent_spans(rows, [], case["question"])]
                else:
                    results = await runtime._search(case["question"], context, dict(pointer))
                item["results"] = results
                for row in results:
                    row.pop("_verified_publication", None)
                from campus247.application.retrieval.excerpts import narrow_clause
                item["generation_views"] = [narrow_clause(row["content_text"], case["question"]) for row in results]
            except ValueError as error:
                item["failure_kind"] = type(error).__name__
            finally:
                runtime._rows, runtime.reranker.rerank = original_rows, original_rerank
            print(json.dumps({"case": case["name"], "parents": len(item.get("results", [])),
                "scores": item.get("rerank_scores", [])}), flush=True)
    finally:
        await pool.close()
        report.update(finished_at=datetime.now(UTC), native_after=model_budget())
        report["code_sha256"] = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [checked_path(ROOT / "services/api/src/campus247/infrastructure/knowledge/runtime.py", ROOT),
                checked_path(ROOT / "services/api/src/campus247/application/retrieval/candidate_selection.py", ROOT)]}
        retain(scope / "receipt.json", report)
        print(json.dumps({"receipt": str(scope / "receipt.json")}))


if __name__ == "__main__":
    asyncio.run(main())
