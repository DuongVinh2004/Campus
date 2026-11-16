"""Retain source-based manual review separately from immutable measurement logs."""
import json
from decimal import Decimal
from certificate_stage1_workspace import STATE, retain


if __name__ == "__main__":
    reports = [json.loads((STATE / name).read_text(encoding="utf-8")) for name in
               ("generation-baseline-01.json", "generation-missing-evidence-02.json")]
    reviews = []
    for report in reports:
        for case in report["results"]:
            if "skipped" in case:
                continue
            checks = []
            for turn in case["turns"]:
                final = turn.get("final")
                saved = next((m for m in (turn.get("history") or {}).get("items", [])
                              if final and m["id"] == final["message_id"]), None)
                checks.append({"question": turn["question"], "source_readback": all(s["hash_matches"] for s in turn["sources"]),
                    "source_count": len(turn["sources"]), "persisted_final_matches_stream": saved is not None and saved["final_result"] == final})
            fee = case["id"] == "CERT-DEV-045"
            reviews.append({"id": case["id"], "conversation_id": case["conversation_id"], "provenance_checks": checks,
                "correctness": None if fee else 2, "completeness": 0 if fee else 2,
                "citation_support": None if fee else 2, "expected_behavior_quality": 1 if fee else 2,
                "manual_basis": "Đối chiếu toàn văn source và ảnh trang 35/39: không trộn điều kiện nghỉ học vào giấy xác nhận; giữ đơn ngân hàng kèm xác nhận tình trạng học tập; câu nối tiếp giữ đúng thủ tục." if not fee else
                    "Không bịa mức phí, không báo thành công; safe_refusal nói lỗi chuẩn xác thực nguồn gốc thay vì giải thích không có căn cứ về phí. Hành vi từ chối an toàn nhưng chất lượng giải thích chưa đạt.",
                "review_scope": "Agent review of these outputs only, not an independent human final evaluation"})
    before, after = reports[0]["paid_before"], reports[-1]["paid_after"]
    retain(STATE / "generation-review-03.json", {"reviews": reviews, "source_based_answer_cases": 4,
        "missing_evidence_partial_behavior_cases": 1, "total_live_turns": sum(len(c["provenance_checks"]) for c in reviews),
        "source_reads": sum(p["source_count"] for c in reviews for p in c["provenance_checks"]),
        "calls": after["calls"]-before["calls"], "conservative_cost_usd": str(Decimal(after["conservative_charged_usd"])-Decimal(before["conservative_charged_usd"])),
        "input_tokens_charged": after["input_tokens_charged"]-before["input_tokens_charged"], "output_tokens_charged": after["output_tokens_charged"]-before["output_tokens_charged"],
        "budget_estimation_failure": "First runner planned 18 calls but used 20: omitted sensitive_classifier/route_intent. Existing 3 USD/8500 cap remained enforced. Runner now reserves headroom for six calls per turn and checks native headroom.",
        "not_claimed": ["all 48 generation cases evaluated", "held-out quality", "universal correctness", "production readiness", "invoice cost"]})
