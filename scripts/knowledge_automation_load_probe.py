"""Two concurrent real candidate answers; retain every attempt and citation."""
import asyncio
from datetime import UTC, datetime
import hashlib
import json
import time

import httpx

from knowledge_platform import ROOT, STATE, checked_path, model_budget, retain
from knowledge_automation_live_eval import paid
from knowledge_automation_conversation_probe import LAB, RULE
from verify_knowledge_platform_huce import final
from campus247.domain.shared.values import generate_uuid7

PLAN = [
    {"question": "Theo Quy chế 1486, một tín chỉ tương đương bao nhiêu giờ học tập?", "source": RULE, "term": "50"},
    {"question": "Theo nội quy phòng thực hành máy tính HUCE, cắm USB cần ai đồng ý?", "source": LAB, "term": "cán bộ phòng máy"},
]


async def main():
    scope = checked_path(ROOT / "infra/local/knowledge-automation-20261026" /
        ("application-load-"+datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")), ROOT)
    retain(scope / "plan.json", {"concurrency": 2, "requests": PLAN, "retries": 0,
        "scope": "bounded local observation; no throughput or production SLA claim"})
    report = {"started_at": datetime.now(UTC), "native_before": model_budget(), "paid_before": paid(), "results": []}
    try:
        async with httpx.AsyncClient(base_url="http://127.0.0.1:8018", trust_env=False, timeout=90) as client:
            credentials = json.loads((STATE / "owner-credentials.json").read_bytes())
            response = await client.post("/v1/knowledge/platform/session", json={key: credentials[key] for key in ("username", "password")})
            credentials = None
            response.raise_for_status()
            state = await client.get("/v1/knowledge/platform/state"); state.raise_for_status()
            if state.json()["environment"] != "rehearsal" or not state.json()["is_serving"]:
                raise ValueError("Acknowledged rehearsal required")
            conversations = []
            for _ in PLAN:
                response = await client.post("/v1/conversations", json={"mode": "temporary"}); response.raise_for_status()
                conversations.append(response.json()["id"])
            barrier = asyncio.Event()
            async def answer(index, expected, cid):
                await barrier.wait()
                started = time.perf_counter()
                row = {"conversation_id": cid, "question": expected["question"], "citations": []}
                try:
                    response = await client.post(f"/v1/conversations/{cid}/messages:stream",
                        json={"content": expected["question"], "client_id": generate_uuid7()})
                    with checked_path(scope / f"stream-{index}.sse", ROOT).open("xb") as stream:
                        stream.write(response.content)
                    result = final(response.text.replace("\r\n", "\n"))
                    row.update(http_status=response.status_code, final=result, elapsed_seconds=time.perf_counter()-started)
                    source_ids = set()
                    for wrapped in (result or {}).get("citations", []):
                        citation = wrapped["citation"]
                        path = f"/v1/conversations/{cid}/messages/{result['message_id']}/citations/{citation['citation_id']}/source"
                        source = await client.get(path)
                        body = source.json()
                        source_ids.add(citation["source_id"])
                        row["citations"].append({"http_status": source.status_code,
                            "hash_valid": hashlib.sha256(body.get("content_text", "").encode()).hexdigest() == citation["evidence_sha256"]})
                    row["passed"] = (response.status_code == 200 and (result or {}).get("status") == "answered"
                        and expected["term"] in (result or {}).get("content", "")
                        and source_ids == {expected["source"]} and all(c["http_status"] == 200 and c["hash_valid"] for c in row["citations"]))
                except Exception as error:
                    row.update(passed=False, error_type=type(error).__name__, elapsed_seconds=time.perf_counter()-started)
                return row
            tasks = [asyncio.create_task(answer(index, expected, cid)) for index, (expected, cid) in enumerate(zip(PLAN, conversations), 1)]
            barrier.set()
            report["results"] = await asyncio.gather(*tasks)
            await client.post("/v1/auth/logout")
    finally:
        report.update(finished_at=datetime.now(UTC), native_after=model_budget(), paid_after=paid())
        report["all_passed"] = len(report["results"]) == len(PLAN) and all(row["passed"] for row in report["results"])
        retain(scope / "receipt.json", report)
        print(json.dumps({"receipt": str(scope / "receipt.json"), "all_passed": report["all_passed"],
            "results": [{key: row.get(key) for key in ("http_status", "elapsed_seconds", "passed", "error_type")} for row in report["results"]]}))


if __name__ == "__main__":
    asyncio.run(main())
