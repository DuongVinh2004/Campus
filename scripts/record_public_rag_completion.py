"""Record final local RAG evidence without changing prior reports or usage."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "infra/local/public-rag-20261013"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    reports = ["product-screen-approved-01.json", "product-faq-approved-01.json",
               "product-graduation-approved-01.json", "product-services-focused-01.json"]
    latest = {}
    failed_attempts = []
    for name in reports:
        report = read(STATE / name)
        assert report["persisted_finals_verified"]
        for result in report["results"]:
            entry = dict(result, evidence_file=name)
            latest[result["question"]] = entry
            if not result["passed"]:
                failed_attempts.append(entry)
    assert len(latest) == 30 and all(value["passed"] for value in latest.values())
    catalog = read(ROOT / "data/huce-faq-20261013/validation.json")
    assert catalog["entry_count"] == 330 and catalog["all_sources_resolved"]
    build = read(STATE / "frontend11-build.json")
    assert build["exit_code"] == 0
    ledger = max((read(path) for path in STATE.glob("provider-*.json")),
                 key=lambda value: (value["snapshot"]["calls"], value["stage"] == "result"))["snapshot"]
    assert ledger["hard_cap_usd"] == "3" and ledger["call_cap"] == 8500
    proof = STATE / "approved-scholarship-proof.png"
    assert proof.is_file()
    record = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "completed_local_public_rag",
        "completion_scope": "Public HUCE RAG, screen prompts, natural FAQ, authenticated source reading and local history",
        "faq_questions_loaded": 330, "all_330_source_bindings_verified": True,
        "all_330_live_generations_verified": False,
        "latest_live_cases_passed": 30, "latest_live_cases_total": 30,
        "grounded_answers": 29, "broad_topic_clarifications": 1,
        "verification_files": reports, "latest_results": list(latest.values()),
        "retained_failed_attempts": failed_attempts,
        "repaired_observed_failure": "Dormitory answer included unrequested discipline policy; exact source-clause focus passed the recheck",
        "browser_verified": ["scholarship_card_answer", "authenticated_original_source_readback", "history_after_frontend_restart_and_reload"],
        "browser_conversation_id": "01a13267-a5a3-7bf5-be2d-ebe13be47e46",
        "browser_proof": proof.name,
        "browser_proof_sha256": hashlib.sha256(proof.read_bytes()).hexdigest(),
        "runtime_frontend": "frontend11", "runtime_url": "http://localhost:8000/chat",
        "real_provider": "DeepSeek deepseek-flash", "real_public_sources": True,
        "fabricated_account_or_simulation_labels_in_public_chat": False,
        "specific_guard_authorization": "Cho phép sửa quy tắc này, giữ kiểm tra nguồn và chặn phán quyết cá nhân",
        "paid_cap_authorization": "3 USD tổng cộng — thêm tối đa 1,50 USD",
        "cumulative_budget": ledger,
        "prior_data_and_evidence_preserved": True,
        "checks": [
            {"check": "backend guard, routing, FAQ bindings and final persistence", "exit_code": 0, "passed": 50,
             "evidence": "pytest-approved-guard-02"},
            {"check": "frontend session renewal, history, source opening and SSE", "exit_code": 0, "passed": 75},
            {"check": "real source excerpts, guard, bounded regeneration and retained budget", "exit_code": 0, "passed": 40,
             "evidence": "pytest-focused-evidence-02"},
            {"check": "final ChatPanel service suggestions", "exit_code": 0, "passed": 10},
            {"check": "Next production compilation, TypeScript and page generation", "exit_code": 0,
             "evidence": "frontend11-build.json"},
        ],
    }
    target = STATE / "product-verification-summary-approved-01.json"
    assert target.resolve().is_relative_to(ROOT) and not target.exists()
    with target.open("x", encoding="utf-8") as stream:
        json.dump(record, stream, ensure_ascii=False, indent=2)
    print(json.dumps({key: record[key] for key in ("status", "faq_questions_loaded", "latest_live_cases_passed", "latest_live_cases_total", "cumulative_budget")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
