"""Bounded real candidate follow-up/multi-source check, retaining every result.

The plan is saved before answers. Only existing admitted public sources are
used; no source/review/release mutation or reviewer impersonation occurs.
"""
from datetime import UTC, datetime
import hashlib
import json
import time

import httpx

from knowledge_platform import ROOT, STATE, checked_path, model_budget, retain
from knowledge_automation_live_eval import paid
from verify_knowledge_platform_huce import final
from campus247.domain.shared.values import generate_uuid7

RATE = "b9e70f30-18ab-7d6d-819b-478e13e8ff00"
RULE = "253eb450-c57a-79a7-84a4-b0d85e12de1c"
LAB = "2d8c1b76-749f-7a7a-890b-e41c8646affe"
PLAN = [
    {"name": "tuition_scope_then_topic", "turns": [
        {"question": "Học phí ngành Công nghệ thông tin là bao nhiêu?", "status": "abstained", "response_class": "clarification_request", "sources": [], "required": ["khóa", "chương trình", "năm học"]},
        {"question": "Cử nhân K71, chính quy, năm học 2026-2027.", "status": "answered", "sources": [RATE], "required": ["592.500"]},
        {"question": "Còn chương trình kỹ sư từ K69, chính quy, năm học 2026-2027?", "status": "answered", "sources": [RATE], "required": ["547.000"], "forbidden": ["592.500"]},
        {"question": "Đổi chủ đề: Điểm thi môn Giải tích 1 của tôi là bao nhiêu?", "status": "abstained", "sources": [], "forbidden": ["592.500", "547.000"]},
    ]},
    {"name": "lab_permission_followup", "turns": [
        {"question": "Theo nội quy phòng thực hành máy tính HUCE, cắm USB cần ai đồng ý?", "status": "answered", "sources": [LAB], "required": ["cán bộ phòng máy"]},
        {"question": "Còn đến muộn bao nhiêu phút thì không được vào phòng?", "status": "answered", "sources": [LAB], "required": ["15"]},
    ]},
    {"name": "two_admitted_documents", "turns": [
        {"question": "Tôi học cử nhân CNTT K71, chính quy, năm học 2026-2027. Theo QĐ 924 và Quy chế 1486, một tín chỉ tính bao nhiêu giờ học tập và học phí mỗi tín chỉ của chương trình tôi là bao nhiêu?",
            "status": "answered", "sources": [RATE, RULE], "required": ["50", "592.500"]},
    ]},
]


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", action="append", choices=[row["name"] for row in PLAN])
    args = parser.parse_args()
    selected = [row for row in PLAN if not args.scenario or row["name"] in args.scenario]
    scope = checked_path(ROOT / "infra/local/knowledge-automation-20261026" /
        ("conversation-probe-"+datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")), ROOT)
    retain(scope / "plan.json", {"plan": selected, "frozen_at": datetime.now(UTC), "scope": "public ready-source regression, no institution-wide acceptance"})
    report = {"started_at": datetime.now(UTC), "native_before": model_budget(), "paid_before": paid(),
        "plan_sha256": hashlib.sha256((scope / "plan.json").read_bytes()).hexdigest(), "conversations": [],
        "source_review_or_release_mutation": False, "request_retries": 0}
    try:
        with httpx.Client(base_url="http://127.0.0.1:8018", trust_env=False, follow_redirects=False, timeout=90) as client:
            credentials = json.loads((STATE / "owner-credentials.json").read_bytes())
            login = client.post("/v1/knowledge/platform/session", json={key: credentials[key] for key in ("username", "password")})
            credentials = None
            login.raise_for_status()
            state = client.get("/v1/knowledge/platform/state"); state.raise_for_status()
            state = state.json()
            if state["environment"] != "rehearsal" or not state["is_serving"]:
                raise ValueError("An acknowledged rehearsal runtime is required")
            report["desired"] = state["desired"]
            for index, scenario in enumerate(selected, 1):
                conversation = client.post("/v1/conversations", json={"mode": "temporary"}); conversation.raise_for_status()
                cid = conversation.json()["id"]
                row = {"name": scenario["name"], "conversation_id": cid, "turns": []}
                report["conversations"].append(row)
                for ordinal, expected in enumerate(scenario["turns"], 1):
                    client_id = generate_uuid7()
                    started = time.perf_counter()
                    response = client.post(f"/v1/conversations/{cid}/messages:stream", json={"content": expected["question"], "client_id": client_id})
                    stream = checked_path(scope / f"stream-{index:02d}-{ordinal:02d}.sse", ROOT)
                    with stream.open("xb") as output:
                        output.write(response.content)
                    result = final(response.text.replace("\r\n", "\n"))
                    item = {"question": expected["question"], "client_id": client_id, "http_status": response.status_code,
                        "final": result, "elapsed_seconds": time.perf_counter()-started, "sources": [], "failures": []}
                    row["turns"].append(item)
                    if response.status_code != 200 or result is None:
                        item["failures"].append("http_or_terminal_result_missing")
                        break
                    text = result.get("content", "").casefold()
                    if result["status"] != expected["status"]:
                        item["failures"].append("disposition")
                    if expected.get("response_class") and result.get("response_class") != expected["response_class"]:
                        item["failures"].append("response_class")
                    if any(term.casefold() not in text for term in expected.get("required", [])):
                        item["failures"].append("required_material")
                    if any(term.casefold() in text for term in expected.get("forbidden", [])):
                        item["failures"].append("stale_topic_material")
                    actual_sources = set()
                    for citation in result.get("citations", []):
                        citation = citation["citation"]
                        path = f"/v1/conversations/{cid}/messages/{result['message_id']}/citations/{citation['citation_id']}/source"
                        source = client.get(path)
                        with httpx.Client(base_url="http://127.0.0.1:8018", trust_env=False, timeout=10) as anonymous:
                            anonymous_status = anonymous.get(path).status_code
                        body = source.json()
                        valid_hash = source.status_code == 200 and hashlib.sha256(body.get("content_text", "").encode()).hexdigest() == citation["evidence_sha256"]
                        item["sources"].append({"status": source.status_code, "anonymous_status": anonymous_status,
                            "hash_valid": valid_hash, "body": body})
                        actual_sources.add(citation["source_id"])
                        if not valid_hash or anonymous_status != 401:
                            item["failures"].append("citation_boundary")
                    if actual_sources != set(expected["sources"]):
                        item["failures"].append("source_set")
                    item["passed"] = not item["failures"]
                    print(json.dumps({"scenario": row["name"], "turn": ordinal, "status": result["status"],
                        "sources": len(actual_sources), "failures": item["failures"]}), flush=True)
                history = client.get(f"/v1/conversations/{cid}/messages"); history.raise_for_status()
                retain(scope / f"history-{index:02d}.json", history.json())
                row["history_http_status"] = history.status_code
            client.post("/v1/auth/logout")
    finally:
        report.update(finished_at=datetime.now(UTC), native_after=model_budget(), paid_after=paid())
        report["all_passed"] = len(report["conversations"]) == len(selected) and all(
            len(row["turns"]) == len(expected["turns"]) and all(turn.get("passed") for turn in row["turns"])
            for row, expected in zip(report["conversations"], selected))
        retain(scope / "receipt.json", report)
        print(json.dumps({"receipt": str(scope / "receipt.json"), "all_passed": report["all_passed"]}), flush=True)


if __name__ == "__main__":
    main()
