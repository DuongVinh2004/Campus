"""Read-only bindings and immutable progress manifest; never declares acceptance."""
import asyncio
import hashlib
import json
import subprocess
from datetime import UTC, datetime

from knowledge_platform import ROOT, TENANT, checked_path, components, retain

SCOPE = ROOT / "infra/local/knowledge-automation-20261026"
CODE = [
    "services/api/src/campus247/application/knowledge/" + name + ".py" for name in
    ("document_identity", "document_reference", "evidence_units", "edition_decisions", "rendition_corrections", "intake", "platform", "source_snapshot", "version_resolver")
] + [
    "services/api/src/campus247/infrastructure/knowledge/" + name + ".py" for name in ("fetch", "repository", "runtime", "storage")
] + [
    "services/worker/src/campus247_worker/" + name + ".py" for name in ("knowledge", "knowledge_parse", "knowledge_layout", "knowledge_render", "knowledge_ocr")
] + [
    "services/api/src/campus247/presentation/knowledge_platform.py",
    "services/api/migrations/versions/0019_document_intake_lineage.py",
    "services/api/migrations/versions/0020_intake_fetch_receipts.py",
    "services/api/migrations/versions/0021_edition_decision_history.py",
    "services/api/migrations/versions/0022_rendition_corrections.py",
    "services/worker/src/campus247_worker/knowledge_ocr_network_guard.cjs",
    "apps/web/src/features/knowledge/KnowledgeIntake.tsx", "apps/web/src/features/knowledge/KnowledgePlatform.tsx",
    "apps/web/src/features/knowledge/RenditionCorrection.tsx",
    "evals/runners/knowledge_claims.py", "evals/datasets/knowledge-independent-20261026.json",
    "evals/datasets/knowledge-independent-20261026-v2.json",
    "scripts/knowledge_platform.py",
] + ["scripts/" + name + ".py" for name in ("knowledge_automation_baseline", "knowledge_automation_checkpoint", "knowledge_automation_pilot",
    "knowledge_automation_rehearsal", "knowledge_automation_restore", "knowledge_automation_restore_bundle", "knowledge_automation_verify_restore",
    "knowledge_automation_verify", "knowledge_automation_freeze_gold", "knowledge_automation_live_eval", "assemble_knowledge_automation_eval",
    "assess_knowledge_material", "measure_knowledge_snapshot_reads")]


async def inspect():
    baseline = json.loads((SCOPE / "baseline-20261026T084032116612.json").read_text(encoding="utf-8"))
    status = subprocess.run(["git", "status", "--porcelain=v1", "-uno"], cwd=ROOT, text=True, capture_output=True, encoding="utf-8", check=True)
    tracked = status.stdout.splitlines()
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, capture_output=True, check=True).stdout.strip()
    report = {"at": datetime.now(UTC).isoformat(), "goal_complete": False,
        "tracked_path_state_matches_initial": tracked == baseline["tracked_changes"], "git_head_unchanged": head == baseline["git_head"],
        "tracked_change_count": len(tracked), "tracked_changes": tracked,
        "code_sha256": {name: hashlib.sha256(checked_path(ROOT / name, ROOT).read_bytes()).hexdigest() for name in CODE},
        "build_source": "frontend-knowledge-automation-20261026-07",
        "operational_runtime": "8015/3015, unchanged process composition and schema 0018; edited source is not a claim of deployed operational code",
        "rehearsal_runtime": "8016/3016, explicitly selected restored copy 008daf8c925a, schema 0020; generation not enabled",
        "acceptance_limits": ["Advanced merged tables/diagram semantics and verified OCR evidence-unit integration incomplete", "Edition decisions persist in 0021; admin decision UI and serving integration incomplete",
            "No scoped automation policy granted or enabled; independent reviewer/preview/confirmation retained",
            "Three-real-document full pilot, novel-source upload-to-answer and 46-source migration incomplete",
            "Scoped cross-store bundle and restored runtime/citation/revocation verified once; load tests and other test-tenant artifact stores not covered",
            "11-question existing-runtime baseline completed in explicit segments; two false abstentions, one missing personal-API explanation and one initial missing-final attempt remain",
            "New correction feature tested in schema0022; active prototype still schema0020, so correction UI is intentionally unavailable there"],
        "retained_failures": ["Parser import hit no-socket guard; adapter replaced with PDFMiner, guard preserved",
            "Novel official URL failed strict TLS chain validation; no TLS bypass",
            "BGE smoke had a response failure and later a retained lease wait before successful checkpoint/resume smoke",
            "Persistent duplicate fixture initially consumed older queued job; exact job selection now retains shared lease/fencing guards",
            "Verification runner initially rejected workspace root as artifact path; only command cwd handling corrected; failed output retained",
            "Evidence resume test expected only one stage; now verifies both immutable EXTRACT/EVIDENCE receipts are unchanged across resume",
            "Bundle initially tried the operational store for other test tenants; first attempt retained, scope corrected to exact operational tenant",
            "Local OCR resolution anchor was not a real JSON file; parent/module closure validated without creating files outside workspace",
            "Windows NODE_OPTIONS consumed backslashes in preload path; forward-slash path corrected, network/process guard kept enabled",
            "OCR retry encountered the retained failed-job lease; waited for natural expiry without bypass or reset",
            "Restored paid gateway denied a second ledger writer; kept lock, no lease bypass; baseline used existing8015 writer",
            "Initial baseline first request had no final and campaign stopped; one explicit diagnostic succeeded, then remaining10 ran; all12 observations retained"],
        "new_model_campaign": False, "agent_quota_delta": "not measured; shared model ledger deltas are not uniquely attributable"}
    restored = SCOPE / "schema-rehearsal-restored-20261026T101117685822.json"
    original_restore = json.loads(restored.read_text(encoding="utf-8"))
    pool, _, platform, _ = await components(rehearsal=restored)
    try:
        async with pool.acquire() as conn:
            report["restored_database"] = await conn.fetchval("SELECT current_database()")
            report["restored_pointer"] = await platform.repo.pointer(conn)
            report["restored_original_records"] = {table: await conn.fetchval("SELECT count(*) FROM " + table) for table in
                ("knowledge_source", "document_version", "knowledge_ingest_version", "knowledge_review", "knowledge_release", "knowledge_release_member")}
            report["restored_original_record_counts_unchanged"] = all(original_restore["source_fingerprint"]["counts"][name] == count
                for name, count in report["restored_original_records"].items())
            job = await conn.fetchrow("SELECT * FROM knowledge_ingestion_job WHERE id=$1 AND tenant_id=$2", "01a177c5-b453-7cc9-b09d-20da4a0d1d3c", TENANT)
            steps = await conn.fetch("SELECT stage,input_sha256,config_sha256,output_sha256,result FROM knowledge_job_step WHERE job_id=$1 ORDER BY stage", job["id"])
            report["stem_ui_reuse"] = {"job_id": str(job["id"]), "stage": job["stage"], "state": job["state"],
                "steps": [dict(row) for row in steps], "ocr_or_embedding_stage_present": any(row["stage"].startswith(("OCR", "EMBED", "EXTRACT", "RENDER")) for row in steps)}
            ocr_job = "01a1785f-7bdb-7858-9f28-ebcd96a45802"
            ocr_steps = await conn.fetch("SELECT stage,input_sha256,config_sha256,output_sha256,result FROM knowledge_job_step WHERE job_id=$1 ORDER BY stage",ocr_job)
            report["ui_ocr_synthetic_sample"]={"job_id":ocr_job,"steps":[dict(row) for row in ocr_steps],
                "actual_ui_view_verified":True,"sample_limit":"synthetic image PDF with native heading; OCR misread final word; not real-document semantic acceptance"}
    finally:
        await pool.close()
    from campus247_worker.knowledge import available_memory
    report["resource_snapshot"] = {"available_memory_bytes":available_memory(),"worker_low_watermark_bytes":2*1024**3,
        "observed_worker_resource_wait":True,"watermark_changed":False,"cpu_load_or_sla_measured":False}
    report["verification_receipt"] = "infra/local/knowledge-automation-20261026/verify-20261026T135251027454/receipt.json"
    report["local_ocr_smoke_receipt"] = "infra/local/knowledge-automation-20261026/verify-20261026T131424477172/receipt.json"
    report["independent_baseline_receipt"] = "infra/local/knowledge-automation-20261026/independent-text-baseline-01.json"
    report["independent_diagnostic_receipt"] = "infra/local/knowledge-automation-20261026/independent-text-diagnostic-01.json"
    report["restore_bundle_receipt"] = "infra/local/knowledge-automation-20261026/schema-rehearsal-bundle-20261026T125636532306.json"
    report["restore_runtime_receipt"] = "infra/local/knowledge-automation-20261026/restore-runtime-20261026T130034144065.json"
    report["account_usage_receipt"] = "infra/local/knowledge-automation-20261026/account-usage-20261026T132337322222.json"
    report["ui_build_matches_source"] = all((ROOT / "infra/local/knowledge-platform-20261023/frontend-knowledge-automation-20261026-07/src/features/knowledge" / name).read_bytes()
        == (ROOT / "apps/web/src/features/knowledge" / name).read_bytes() for name in ("KnowledgeIntake.tsx","KnowledgePlatform.tsx","RenditionCorrection.tsx"))
    report["test_matrix"] = {f"T{index:02}":{"state":"not_verified_end_to_end"} for index in range(1,51)}
    scoped = {1:"real public PDF intake and synthetic native/table/raster checks",2:"tab close/reopen preserved exact intake job",
        3:"real PostgreSQL scoped replay",4:"real PostgreSQL conflict on changed payload",5:"real published evidence reuse without OCR/render/embed",
        7:"different origin remains separate; explicit reconciliation required",9:"pinned public DNS and redirect unit checks",
        11:"native-header plus raster/table/diagram fixtures",20:"separate edition/rendition identities; actual correction workflow incomplete",
        21:"deterministic future effective-day resolver",22:"source-bound independent decision history and replacement tests",
        23:"unit/dependency partial amendment tests; serving integration absent",24:"multi-cohort resolver partition tests",
        25:"real recorded decision known-at test",26:"cycle/conflict scoped resolution tests",28:"existing review/confirmation controls retained; no automation policy enabled",
        33:"committed parser/render/OCR checkpoint reuse; separate real BGE crash/resume smoke",34:"real lease/fencing tests",
        35:"full input/profile/hash mismatches rejected",36:"tenant-bound cache/source tests",37:"multi-document selector union tests",
        38:"selector language-variant tests; no fresh live answers",40:"known invented course/credits mutation detected",
        42:"actual resource wait observed; no ledger/cap/watermark reset",43:"scoped PG/artifact/SQLite bundle and restored runtime verified",
        50:"owned historical citation opened after restore; fresh logged-out session denied"}
    for index,scope in scoped.items():
        report["test_matrix"][f"T{index:02}"]={"state":"verified_in_limited_scope","scope":scope}
    report["acceptance_matrix"] = {f"AC-{index:02}":{"state":"partial_or_not_verified","acceptance_complete":False} for index in range(1,29)}
    # Hash evidence and logs, never embed credentials or full source/user payloads.
    receipts = {}
    for path in sorted(checked_path(SCOPE, ROOT).rglob("*")):
        path = checked_path(path, ROOT)
        if path.is_file():
            receipts[str(path.relative_to(ROOT))] = {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size}
    report["retained_evidence"] = receipts
    target = SCOPE / ("checkpoint-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f") + ".json")
    retain(target, report)
    print(json.dumps({"receipt": str(target), "goal_complete": False, "tracked_changes": len(tracked),
        "stem_ui_reuse": report["stem_ui_reuse"]["stage"], "original_counts_unchanged": report["restored_original_record_counts_unchanged"]}))


if __name__ == "__main__":
    asyncio.run(inspect())
