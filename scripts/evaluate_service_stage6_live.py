"""Bounded fresh read-only RAG checks through wrapper8004, existing writer8003."""
import argparse
import hashlib
import json
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "scripts"), str(ROOT / "services/api/src"), str(ROOT / "packages/synthetic/src")]
from service_stage6_workspace import retain, destination
from multi_agent_live_resources import paid_view, native_view

QUESTIONS = [
    "Theo sổ tay HUCE, quy trình đăng ký phúc khảo và kênh thanh toán được mô tả thế nào?",
    "Thi vấn đáp hoặc thực hành có được phúc khảo theo sổ tay HUCE không?",
    "Lệ phí phúc khảo cụ thể là bao nhiêu? Nếu nguồn chưa có mức tiền, hãy nói rõ phần chưa xác minh.",
]


def preflight():
    from campus247.application.multi_agent.contracts import MultiAgentPolicy
    paid, native, policy = paid_view(), native_view(), MultiAgentPolicy()
    calls = len(QUESTIONS) * policy.max_model_calls
    tokens = len(QUESTIONS) * policy.max_reserved_tokens
    native_sequences = len(QUESTIONS) * policy.max_searches * 9
    admitted = (paid["call_cap"] - paid["calls"] >= calls and Decimal(paid["remaining_usd"]) >= Decimal(tokens) * Decimal("1.2") / 1000000
        and native["caps"]["inference"] - native["counts"]["inference"] >= native_sequences
        and native["caps"]["http"] - native["counts"]["http"] >= len(QUESTIONS)*policy.max_searches*18
        and native["caps"]["tokens"] - native["counts"]["tokens"] >= native_sequences*900)
    return {"admitted": admitted, "reserved_provider_calls": calls, "paid": paid, "native": native,
        "new_writer": False, "questions": QUESTIONS, "purpose": "source guidance only; zero business confirmations",
        "browser_service_check_envelope": "one separate browser run may use up to12calls, subject to fresh per-run admission"}


def main(execute):
    check = preflight()
    retain("live-preflight-01.json", check)
    if not execute: print(json.dumps(check)); return
    if not check["admitted"]: raise RuntimeError("insufficient existing headroom; no calls dispatched")
    import httpx
    from evaluate_multi_agent_live import PacedClient, run_turn, usage_delta
    with httpx.Client(base_url="http://127.0.0.1:8004", timeout=40, trust_env=False) as transport:
        c = PacedClient(transport)
        health = c.request("GET", "/health/live"); health.raise_for_status()
        if health.json().get("owns_paid_ledger") or health.json().get("mode") != "synthetic_service_operations":
            raise ValueError("wrapper must own zero paid ledger")
        response = c.request("POST", "/v1/auth/demo-login", json={"account": "SV001"}); response.raise_for_status()
        h = {"Authorization": "Bearer " + response.json()["token"]}
        before = c.request("GET", "/v1/service-requests", headers=h).json()
        retain("live-business-before-01.json", before)
        cases = []
        for number, question in enumerate(QUESTIONS, 1):
            name = f"live-case-{number:02d}-01.json"
            if destination(name).exists(): raise FileExistsError("retain prior result")
            retain(f"live-attempt-{number:02d}-01.json", {"question": question, "no_automatic_resend": True})
            response = c.request("POST", "/v1/conversations", headers=h, json={"title": f"Service stage6 guidance {number}"})
            response.raise_for_status(); cid = response.json()["id"]
            row = {"conversation_id": cid, "question": question, "turn": run_turn(c, h, cid, question),
                "quality_review": "requires source review; not inferred from successful terminal"}
            retain(name, row); cases.append(row)
            if row["turn"]["failure"]: break
        after = c.request("GET", "/v1/service-requests", headers=h).json()
        # A concurrent user/staff action is not evidence of a model side effect.
        # Retain both snapshots and report inconclusive when the fixture is busy.
        retain("live-business-after-01.json", after)
        paid, native = paid_view(), native_view()
        retain("live-campaign-01.json", {"cases": len(cases), "expected": len(QUESTIONS), "business_rows_unchanged": before == after,
            "business_effect_attribution": "not_verified_concurrent_actions" if before != after else "observed_no_change",
            "usage": usage_delta(check["paid"], paid, check["native"], native), "paid_after": paid, "native_after": native,
            "new_writer": False, "source_hash_matches": [all(s["hash_matches"] for s in r["turn"]["sources"]) for r in cases],
            "history_matches": [r["turn"].get("history_readback_equal") for r in cases],
            "failures": [r["turn"]["failure"] for r in cases], "not_verified": list(range(len(cases)+1, len(QUESTIONS)+1))})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--execute", action="store_true")
    sys.stdout.reconfigure(encoding="utf-8"); main(parser.parse_args().execute)
