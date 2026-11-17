"""Independent live audit; append-only receipts, existing local runtime only."""
import argparse
import asyncio
import hashlib
import json
import time
from contextlib import closing
from datetime import UTC, datetime

import httpx

from knowledge_platform import ROOT, STATE, TENANT, checked_path, components, model_budget, retain
from verify_knowledge_platform_huce import final

BASE = "http://127.0.0.1:8015"
API = "/v1/knowledge/platform"
STAMP = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")
THROTTLES = []


def request(c, method, path, **kwargs):
    for _ in range(4):
        response = c.request(method, path, **kwargs)
        if response.status_code != 429:
            return response
        delay = min(60, max(1, int(response.headers.get("Retry-After", "5"))))
        THROTTLES.append({"path": path, "status": 429, "retry_after": delay, "at": datetime.now(UTC).isoformat()})
        print(json.dumps({"rate_limited": path, "waiting_seconds": delay}), flush=True)
        time.sleep(delay + .25)
    return response


def counters():
    from multi_agent_live_resources import latest_paid_snapshot
    paid = latest_paid_snapshot()
    return {"native": model_budget(), "paid": {k: paid[k] for k in
        ("calls", "input_tokens_charged", "output_tokens_charged", "conservative_charged_usd", "unsettled_attempts_retained")}}


def client():
    c = httpx.Client(base_url=BASE, trust_env=False, timeout=100)
    creds = json.loads(checked_path(STATE / "owner-credentials.json", ROOT).read_text(encoding="utf-8"))
    assert c.post(API + "/session", json={k: creds[k] for k in ("username", "password")}).status_code == 200
    return c


async def originals(state):
    pool, _, platform, _ = await components()
    result = []
    try:
        async with pool.acquire() as conn:
            members = await conn.fetch("SELECT * FROM knowledge_release_member WHERE release_id=$1 ORDER BY version_id", state["desired"]["release_id"])
            for member in members:
                row = await platform.repo.version(conn, member["version_id"])
                entry = {k: str(row[k]) if row[k] is not None else None for k in
                    ("version_id", "title", "canonical_uri", "original_sha256", "rendition_sha256", "metadata_sha256", "effective_from", "effective_until", "processor_profile")}
                for kind in ("original", "rendition"):
                    artifact = await conn.fetchrow("SELECT * FROM knowledge_artifact WHERE id=$1", row[kind + "_id"])
                    raw = platform.storage.read(artifact)
                    entry[kind + "_hash_verified"] = hashlib.sha256(raw).hexdigest() == row[kind + "_sha256"]
                    if kind == "original":
                        suffix = ".pdf" if raw.startswith(b"%PDF-") else ".html"
                        path = checked_path(STATE / ("audit-original-" + STAMP + "-" + str(row["version_id"]) + suffix), ROOT)
                        with path.open("xb") as stream:
                            stream.write(raw)
                        entry["original_path"] = str(path)
                    else:
                        entry["rendition"] = json.loads(raw)
                chunks = await conn.fetch("SELECT DISTINCT content_text,content_checksum,page_start,page_end,section_path FROM knowledge_chunk WHERE document_version_id=$1 ORDER BY page_start,section_path", row["version_id"])
                entry["evidence"] = [dict(c) for c in chunks]
                entry["chunk_hashes_verified"] = all(hashlib.sha256(c["content_text"].encode()).hexdigest() == c["content_checksum"] for c in chunks)
                result.append(entry)
    finally:
        await pool.close()
    return result


def question(c, name, text, cid=None):
    before = counters()
    if cid is None:
        created = request(c, "POST", "/v1/conversations", json={"mode": "temporary"})
        created.raise_for_status()
        cid = created.json()["id"]
    start = time.perf_counter()
    response = request(c, "POST", f"/v1/conversations/{cid}/messages:stream", json={"content": text})
    elapsed = time.perf_counter() - start
    result = final(response.text)
    entry = {"name": name, "question": text, "conversation_id": cid, "http_status": response.status_code,
        "latency_seconds": round(elapsed, 3), "final": result, "counters_before": before, "counters_after": counters(),
        "event_types": [line[7:] for line in response.text.splitlines() if line.startswith("event: ")]}
    if not result:
        entry["stream"] = response.text
    entry["sources"] = []
    for wrapped in (result or {}).get("citations", []):
        citation = wrapped["citation"]
        path = f"/v1/conversations/{cid}/messages/{result['message_id']}/citations/{citation['citation_id']}/source"
        source = request(c, "GET", path)
        value = source.json()
        with httpx.Client(base_url=BASE, trust_env=False, timeout=15) as anon:
            denied = request(anon, "GET", path).status_code
        entry["sources"].append({"path": path, "status": source.status_code, "anonymous_status": denied, "body": value,
            "hash_verified": source.status_code == 200 and hashlib.sha256(value["content_text"].encode()).hexdigest() == citation["evidence_sha256"]})
    retain(STATE / ("independent-case-" + name + "-" + STAMP + ".json"), entry)
    print(json.dumps({"name": name, "latency": entry["latency_seconds"], "status": (result or {}).get("status"),
        "answer": (result or {}).get("content"), "conversation": cid}, ensure_ascii=False), flush=True)
    return entry


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["sources", "snapshot", "integrity", "questions", "retrieval", "security", "faults", "concurrent"])
    parser.add_argument("--cases-file")
    parser.add_argument("--question-report")
    parser.add_argument("--query", help="Explicit read-only retrieval diagnostic question")
    args = parser.parse_args()
    with closing(client()) as c:
        state = c.get(API + "/state").json()
        report = {"at": STAMP, "state": state, "availability": c.get(API + "/availability").json(), "before": counters()}
        if args.mode == "sources":
            report["originals"] = asyncio.run(originals(state))
            for item in report["originals"]:
                print(json.dumps({k: v for k, v in item.items() if k not in {"rendition", "evidence"}}, ensure_ascii=False))
                print(json.dumps(item["evidence"], ensure_ascii=False))
        elif args.mode == "snapshot":
            async def membership():
                pool, _, _, _ = await components()
                try:
                    async with pool.acquire() as conn:
                        members = await conn.fetch("SELECT source_id,version_id,index_version FROM knowledge_release_member WHERE release_id=$1 ORDER BY version_id", state["desired"]["release_id"])
                        return [{key: str(value) for key, value in dict(row).items()} for row in members]
                finally:
                    await pool.close()
            report["members"] = asyncio.run(membership())
            report["catalog"] = {"sources": len(state["sources"]), "versions": len(state["versions"]),
                "pending_versions": sum(v["review_state"] == "NEEDS_REVIEW" for v in state["versions"]),
                "fixture_absent": all("Sao Mai" not in s["title"] and not s["canonical_uri"].startswith("urn:") for s in state["sources"])}
            report["models"] = {str(port): httpx.get(f"http://127.0.0.1:{port}/info", trust_env=False, timeout=10).json() for port in (18081, 18082)}
            from campus247_worker.knowledge import available_memory
            report["available_memory_bytes"] = available_memory()
            print(json.dumps({"desired": state["desired"], "serving": state["serving"], "catalog": report["catalog"], "members": report["members"],
                "model_counts": model_budget(), "available_memory_bytes": report["available_memory_bytes"]}, ensure_ascii=False), flush=True)
        elif args.mode == "integrity":
            async def integrity():
                import base64
                import io
                import re
                from pypdf import PdfReader
                from campus247.application.knowledge.platform_models import metadata_binding
                snapshot = json.loads(checked_path(STATE / "independent-sources-20261023T125049141884.json", ROOT).read_text(encoding="utf-8"))
                pool, _, platform, _ = await components()
                rows = []
                try:
                    async with pool.acquire() as conn:
                        for source in snapshot["originals"]:
                            row = await platform.repo.version(conn, source["version_id"])
                            checks = {"version_id": source["version_id"], "metadata_hash_verified": metadata_binding(row) == row["metadata_sha256"]}
                            raw = checked_path(__import__("pathlib").Path(source["original_path"]), ROOT).read_bytes()
                            checks["original_hash_verified"] = hashlib.sha256(raw).hexdigest() == source["original_sha256"]
                            if source["version_id"].startswith("01a167c6"):
                                hashes = {hashlib.sha256(base64.b64decode(value)).hexdigest() for value in re.findall(rb'data:image/jpeg;base64,([^"\s]+)', raw)}
                                mapping = source["rendition"]["original_mapping"]
                                checks["embedded_scans_verified"] = set(mapping["embedded_document_page_sha256"].values()).issubset(hashes)
                                acquisition = checked_path(ROOT / ".tooling/tuition-credit-rag-20261020-01/acquisition.json", ROOT).read_bytes()
                                checks["acquisition_receipt_verified"] = hashlib.sha256(acquisition).hexdigest() == mapping["acquisition_receipt_sha256"]
                                checks["visual_basis"] = "Agent inspected both original embedded scans: 10/06/2026, Article 2, all tuition rows and surcharges. No end date inferred."
                            else:
                                if source["version_id"].startswith("01a168c6"):
                                    transcript = checked_path(ROOT / "data/huce-document-pipeline/ict-lab-reviewed-text-20261022-77.json", ROOT).read_bytes()
                                    basis = source["rendition"]["source_evidence"]
                                    checks["transcript_hash_verified"] = hashlib.sha256(transcript).hexdigest() == basis["transcript_sha256"]
                                    pages = [page["text"] for page in json.loads(transcript)["pages"]]
                                    jobs = json.loads(checked_path(ROOT / "data/huce-document-pipeline/ict-lab-ocr-jobs-20261022-76.json", ROOT).read_text(encoding="utf-8"))
                                    checks["page_images_verified"] = all(hashlib.sha256(checked_path(ROOT / page["image"], ROOT).read_bytes()).hexdigest() == expected
                                        and page["source_sha256"] == source["original_sha256"] for page, expected in zip(jobs["pages"], basis["page_image_sha256"], strict=True))
                                    checks["visual_basis"] = "Agent inspected both retained scan images: 09/04/2024 and Article 2; 12 clauses on page 2. Handwritten decision number remains unverified."
                                else:
                                    pages = [page.extract_text() or "" for page in PdfReader(io.BytesIO(raw)).pages]
                                    checks["visual_basis"] = "Native PDF text; agent also inspected rendered page 2 effectivity and page 8 password clause."
                                checks["evidence_at_original_locators"] = [entry["content_text"] in "\n".join(pages[entry["page_start"]-1:entry["page_end"]]) for entry in source["evidence"]]
                            checks["editorial_lines_in_evidence"] = any("Phạm vi đã đối chiếu:" in entry["content_text"] or "Loại nguồn:" in entry["content_text"] for entry in source["evidence"])
                            rows.append(checks)
                    return rows
                finally:
                    await pool.close()
            report["checks"] = asyncio.run(integrity())
            report["models"] = {str(port): httpx.get(f"http://127.0.0.1:{port}/info", trust_env=False, timeout=10).json() for port in (18081, 18082)}
            print(json.dumps(report["checks"], ensure_ascii=False), flush=True)
        elif args.mode == "security":
            from campus247.infrastructure.identity.local_owner import LocalOwnerIdentityAdapter
            adapter = LocalOwnerIdentityAdapter(checked_path(STATE / "owner-identity.json", ROOT), TENANT)
            previous = json.loads(checked_path(ROOT / args.question_report, ROOT).read_text(encoding="utf-8"))
            case = next(case for case in previous["cases"] if case["sources"])
            cid, path = case["conversation_id"], case["sources"][0]["path"]
            checks = {"owner_source": request(c, "GET", path).status_code,
                "owner_history": request(c, "GET", f"/v1/conversations/{cid}/messages").status_code,
                "wrong_citation_binding": request(c, "GET", path.replace(case["final"]["message_id"], cid)).status_code,
                "demo_login": c.get("/v1/auth/demo-session").status_code,
                "legacy_login": c.post(API + "/local-session", json={"account": "KA02"}).status_code,
                "cross_origin": c.post(API + "/search-preview", json={"query": "no model calls", "release_id": state["desired"]["release_id"]}, headers={"Origin": "https://untrusted.invalid"}).status_code}
            with httpx.Client(base_url=BASE, trust_env=False, timeout=15) as anonymous:
                checks["anonymous_state"] = anonymous.get(API + "/state").status_code
                checks["anonymous_source"] = request(anonymous, "GET", path).status_code
                token = adapter.mint_token(adapter.directory()["agent_id"])
                checks["other_owner_source"] = request(anonymous, "GET", path, headers={"Authorization": "Bearer " + token}).status_code
                checks["other_owner_history"] = request(anonymous, "GET", f"/v1/conversations/{cid}/messages", headers={"Authorization": "Bearer " + token}).status_code
                expired = adapter.mint_token(adapter.directory()["owner_id"], ttl_seconds=-1)
                checks["expired_session"] = anonymous.get(API + "/state", headers={"Authorization": "Bearer " + expired}).status_code
                checks["tampered_session"] = anonymous.get(API + "/state", headers={"Authorization": "Bearer " + token[:-5] + "abcde"}).status_code
            revoked = c.cookies.get("auth_token")
            checks["logout"] = c.post("/v1/auth/logout").status_code
            checks["revoked_session"] = c.get(API + "/state", headers={"Authorization": "Bearer " + revoked}).status_code
            report["checks"] = checks
            print(json.dumps(checks), flush=True)
        elif args.mode == "concurrent":
            from concurrent.futures import ThreadPoolExecutor
            # Both requests use the existing single BGE/gateway instances.
            with ThreadPoolExecutor(max_workers=2) as executor:
                def one(item):
                    with closing(client()) as session:
                        return question(session, *item)
                items = [("parallel_usb", "Theo nội quy phòng máy HUCE, muốn cắm USB cần ai cho phép?"),
                    ("parallel_cn", "Học phí cử nhân chính quy K71 năm học 2026-2027 là bao nhiêu đồng/tín chỉ?")]
                if args.cases_file:
                    pair = json.loads(checked_path(ROOT / args.cases_file, ROOT).read_text(encoding="utf-8"))
                    if len(pair) != 2:
                        raise ValueError("Exactly two explicit concurrent cases required")
                    items = [(item["name"], item["question"]) for item in pair]
                report["cases"] = list(executor.map(one, items))
            report["counter_attribution"] = "Concurrent per-case counters overlap; use batch before/after for total usage."
        elif args.mode == "faults":
            async def faults():
                from campus247.domain.retrieval import AuthorizedScope, RetrievalContext, SimulationPolicy
                from campus247.agent.state import AgentState, NormalizedTurn
                from campus247.agent.nodes.async_io import retrieve_evidence_node
                from campus247.application.knowledge.platform_models import PlatformError
                from campus247.infrastructure.knowledge.runtime import _TURN
                pool, _, platform, runtime = await components()
                context = RetrievalContext(AuthorizedScope(TENANT, "HUCE", "audit", frozenset({"KNOWLEDGE_ADMIN"}),
                    frozenset({"KNOWLEDGE_ADMIN"}), frozenset({"FIT"}), frozenset({"PUBLIC"})), "vi", datetime.now(UTC), SimulationPolicy.DENY, "fault-audit")
                checks = []
                real_embed, real_rerank = runtime.embedding._embed, runtime.reranker.rerank
                async def down(*a, **kw):
                    raise httpx.ConnectError("Isolated audit dependency fault")
                async def forbidden(*a, **kw):
                    raise AssertionError("Downstream model or fallback called after failed embedding")
                async def search(query):
                    return await runtime._search(query, context, dict(state["desired"]), preview=True)
                turn = AgentState(request=NormalizedTurn(session_id="fault-session", turn_id="fault-audit", user_id="audit", query="Đổi mật khẩu bao lâu một lần?"))
                try:
                    runtime.embedding._embed, runtime.reranker.rerank = down, forbidden
                    result = await retrieve_evidence_node(turn, search_fn=search, context=context)
                    checks.append({"fault": "embedding_connection", "terminal": str(result.terminal), "errors": result.errors,
                        "candidate_count": len(result.retrieval.candidate_ids), "fallback_answer": False})
                    runtime.embedding._embed, runtime.reranker.rerank = real_embed, down
                    result = await retrieve_evidence_node(turn, search_fn=search, context=context)
                    checks.append({"fault": "reranker_connection", "terminal": str(result.terminal), "errors": result.errors,
                        "candidate_count": len(result.retrieval.candidate_ids), "fallback_answer": False})
                    runtime.reranker.rerank = real_rerank
                    previous = json.loads(checked_path(ROOT / args.question_report, ROOT).read_text(encoding="utf-8"))
                    case = next(case for case in previous["cases"] if case["sources"])
                    citation = case["final"]["citations"][0]["citation"]
                    original_rows = runtime._rows
                    async def corrupt(*a, **kw):
                        return [{**row, "content_text": row["content_text"] + " altered in isolated memory only"} for row in await original_rows(*a, **kw)]
                    runtime._rows = corrupt
                    binding = _TURN.set(dict(state["desired"]))
                    try:
                        await runtime.read(citation["source_id"], citation["document_version_id"], citation["chunk_id"], context=context)
                        raise AssertionError("Corrupt source was accepted")
                    except PlatformError as error:
                        checks.append({"fault": "in_memory_source_checksum", "status": error.status, "code": error.code})
                    finally:
                        _TURN.reset(binding)
                    return checks
                finally:
                    await pool.close()
            report["checks"] = asyncio.run(faults())
            report["isolation"] = "Only this audit process's adapter methods and copied read rows altered. No serving files, DB rows, model listeners, release or source grants changed."
            print(json.dumps(report["checks"]), flush=True)
        elif args.mode == "retrieval":
            async def diagnose():
                from campus247.domain.retrieval import AuthorizedScope, RetrievalContext, SimulationPolicy
                pool, _, platform, runtime = await components()
                context = RetrievalContext(AuthorizedScope(TENANT, "HUCE", "audit", frozenset({"KNOWLEDGE_ADMIN"}),
                    frozenset({"KNOWLEDGE_ADMIN"}), frozenset({"FIT"}), frozenset({"PUBLIC"})), "vi", datetime.now(UTC), SimulationPolicy.DENY, "audit")
                evidence = []
                original_rows, original_rank = runtime._rows, runtime.reranker.rerank
                async def rows(*a, **kw):
                    result = await original_rows(*a, **kw)
                    evidence.append({"branch": "semantic" if kw.get("vector") else "lexical", "rows": [
                        {k: str(r[k]) for k in ("id", "document_version_id", "section_path", "rerank_text")} for r in result]})
                    return result
                async def rank(request):
                    result = await original_rank(request)
                    evidence.append({"inputs": [{"id": r.chunk_id, "text": r.content_text} for r in request.candidates],
                        "ranked": [{"id": str(r.chunk_id), "score": r.score} for r in result.ranked]})
                    return result
                runtime._rows, runtime.reranker.rerank = rows, rank
                try:
                    query = args.query or "Theo quy chế an toàn thông tin HUCE QĐ 2114, người sử dụng phải đổi mật khẩu tối thiểu bao lâu một lần?"
                    result = await runtime._search(query, context, state["desired"], preview=True)
                    return {"question": query, "branches": evidence, "output": result}
                finally:
                    await pool.close()
            report["diagnostic"] = asyncio.run(diagnose())
            print(json.dumps({"question": report["diagnostic"]["question"],
                "ranked": [branch for branch in report["diagnostic"]["branches"] if "ranked" in branch],
                "output": [{key: row[key] for key in ("chunk_id", "section_path", "score")} for row in report["diagnostic"]["output"]]}, ensure_ascii=False))
        else:
            cases = json.loads(checked_path(ROOT / args.cases_file, ROOT).read_text(encoding="utf-8"))
            report["cases"] = []
            prior = None
            for case in cases:
                result = question(c, case["name"], case["question"], prior if case.get("followup") else None)
                prior = result["conversation_id"]
                report["cases"].append(result)
        report["after"] = counters()
        report["throttles"] = THROTTLES
    path = STATE / ("independent-" + args.mode + "-" + STAMP + ".json")
    retain(path, report)
    print(json.dumps({"report": str(path)}))


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    main()
