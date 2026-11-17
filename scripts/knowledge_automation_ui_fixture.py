"""One clearly synthetic draft on an explicit restored 0022 runtime; no review.

Normal HTTP intake/auth plus the ordinary fenced worker targeted at exactly the
new fixture's jobs. Never consumes another restored queue item or publishes.
"""
import argparse
import asyncio
import json
from datetime import UTC, datetime
from uuid import uuid4

import httpx

from knowledge_platform import ROOT, STATE, checked_path, components, model_budget, rehearsal_bundle_paths, retain


async def run(manifest):
    paths = rehearsal_bundle_paths(manifest)
    binding = json.loads(manifest.read_text(encoding="utf-8"))
    if not paths or binding["revision"] != "0022":
        raise ValueError("Complete verified schema0022 restore bundle required")
    output = checked_path(ROOT / "infra/local/knowledge-automation-20261026" /
        ("ui-fixture-"+datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")), ROOT)
    report = {"started_at": datetime.now(UTC), "manifest": str(manifest), "database": binding["database"],
        "port": 8018, "synthetic_document": True, "independent_review_attempted": False,
        "publication_attempted": False, "paid_generation_calls": 0, "native_before": model_budget()}
    from tests.knowledge_platform.test_layout_intake import synthetic_pdf
    raw = synthetic_pdf("image")
    with httpx.Client(base_url="http://127.0.0.1:8018", trust_env=False, timeout=30) as client:
        credentials = json.loads((STATE / "owner-credentials.json").read_text(encoding="utf-8"))
        login = client.post("/v1/knowledge/platform/session", json={key: credentials[key] for key in ("username", "password")})
        credentials = None
        login.raise_for_status()
        try:
            state = client.get("/v1/knowledge/platform/state"); state.raise_for_status()
            state = state.json()
            if state.get("environment") != "rehearsal" or state["desired"] != binding["source_pointer"]:
                raise ValueError("Exact restored runtime binding required")
            report["pointer_before"] = state["desired"]
            response = client.post("/v1/knowledge/platform/intakes", files={"file":
                ("synthetic-ui-ocr-draft.pdf", raw, "application/pdf")}, data={"metadata": "{}"},
                headers={"Idempotency-Key": "ui-fixture-"+uuid4().hex})
            response.raise_for_status(); accepted = response.json(); report["accepted"] = accepted
            pool, _, platform, _ = await components(rehearsal=manifest)
            try:
                from advanced_rag_frontend import NODE
                from campus247_worker.knowledge import KnowledgeIngestionWorker
                from campus247_worker.knowledge_ocr import LocalOcrAdapter
                from knowledge_platform import models
                embedding, _ = models()
                worker = KnowledgeIngestionWorker(platform.repo, platform.storage, embedding, owner="scoped-ui-fixture-"+uuid4().hex,
                    parser_python=ROOT / ".venv/Scripts/python.exe", platform=platform,
                    ocr_adapter=LocalOcrAdapter(platform.storage, node=NODE, package_root=NODE.parents[1] / "package.json"))
                report["intake_worker_outcome"] = await worker.run_once(target_job_id=accepted["job_id"])
                result = client.get(f"/v1/knowledge/platform/intakes/{accepted['intake_id']}/pages/1/ocr")
                result.raise_for_status(); report["ocr"] = result.json()
                metadata = {"title": "Synthetic UI OCR fixture — no institutional facts", "owner_unit": "Synthetic UI test fixture",
                    "canonical_uri": "urn:campus247:synthetic-ui-test:"+uuid4().hex, "programs": ["SYNTHETIC_TEST_ONLY"],
                    "audiences": ["KNOWLEDGE_ADMIN"], "effective_from": None, "effective_until": None}
                response = client.post(f"/v1/knowledge/platform/intakes/{accepted['intake_id']}/metadata",
                    json={"expected_revision": 1, "metadata": metadata}, headers={"Idempotency-Key": "ui-fixture-metadata-"+uuid4().hex})
                response.raise_for_status(); resolved = response.json(); report["resolved"] = resolved
                report["version_worker_outcome"] = await worker.run_once(target_job_id=resolved["job_id"])
                preview = client.get(f"/v1/knowledge/platform/versions/{resolved['version_id']}/correction-preview")
                preview.raise_for_status(); report["correction_preview"] = preview.json()
                state = client.get("/v1/knowledge/platform/state"); state.raise_for_status()
                report["pointer_after"] = state.json()["desired"]
                if report["pointer_after"] != report["pointer_before"]:
                    raise ValueError("Unexpected serving pointer mutation")
                report["status"] = "synthetic_draft_ready_for_ui_comparison"
            finally:
                await pool.close()
        finally:
            client.post("/v1/auth/logout")
            report.update(finished_at=datetime.now(UTC), native_after=model_budget())
            retain(output / "receipt.json", report)
            print(json.dumps({"receipt": str(output / "receipt.json"), "status": report.get("status", "incomplete")}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    args = parser.parse_args()
    asyncio.run(run(checked_path(ROOT / args.manifest, ROOT)))
