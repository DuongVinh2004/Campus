"""Bounded public dialogue regression, persisted finals and exact source readback.

The questions below are separate from the retrieval tuning dataset. Expected
facts are bound to the reviewed source rows, not to an earlier model response.
No retries, provider-cap changes or history/database resets are performed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

from evaluate_advanced_rag import frames
from run_public_rag import CAMPUS, CORPUS, TENANT, checked

SCENARIOS = (
    ("scholarship-year", (
        ("Muốn được xét học bổng khuyến khích học tập thì cần những điều kiện gì?", "grounded_answer", (100,), ("rèn luyện",)),
        ("Còn sinh viên năm thứ nhất trong học kỳ I thì số tín chỉ phải thế nào?", "grounded_answer", (100,), ("bằng", "tối đa")),
    )),
    ("dual-program-followup", (
        ("Khi nào em được đăng ký học thêm chương trình thứ hai?", "grounded_answer", (126,), ("năm thứ hai",)),
        ("Nếu chương trình thứ nhất có kết quả dưới mức trung bình thì sao?", "grounded_answer", (126,), ("dừng",)),
    )),
    ("topic-switch", (
        ("Muốn học nhóm tại thư viện thì em đến đâu?", "grounded_answer", (106,), ("tầng 2",)),
        ("Vậy em đang học năm thứ nhất, có được đổi ngành không?", "grounded_answer", (124,), ("không", "năm thứ nhất")),
        ("Còn đăng ký học thêm chương trình thứ hai thì sớm nhất khi nào?", "grounded_answer", (126,), ("năm thứ hai",)),
    )),
    ("two-sources", (
        ("Ở thư viện, học nhóm đến tầng nào; còn học thêm chương trình thứ hai sớm nhất ở năm mấy?", "grounded_answer", (106, 126), ("tầng 2", "năm thứ hai")),
    )),
    ("missing-future-source", (
        ("Lịch nghỉ Tết năm 2030 của HUCE bắt đầu và kết thúc chính xác ngày nào?", "safe_refusal", (), ("chưa tìm thấy tài liệu chính thức",)),
    )),
    ("missing-referent", (
        ("Còn trường hợp đó thì sao?", "clarification_request", (), ()),
    )),
)


def retain(target: Path, value: dict) -> None:
    with checked(target).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)


def evaluate(target: Path, only: str | None) -> None:
    import httpx
    from campus247.infrastructure.retrieval.public_knowledge import PublicKnowledgeStore

    source = PublicKnowledgeStore(CORPUS, tenant_id=TENANT, campus_id=CAMPUS)
    canonical_sources = {row["chunk_id"]: row for row in source.rows}
    selection = [s for s in SCENARIOS if not only or s[0] in only.split(",")]
    if not selection:
        raise ValueError("unknown scenario")
    # Hard bound independent of selection and application/provider controls.
    if sum(len(s[1]) for s in selection) > 12:
        raise ValueError("dialogue evaluation request cap")
    results = []
    with httpx.Client(base_url="http://127.0.0.1:8001", timeout=45, trust_env=False) as client:
        auth = client.get("/v1/auth/demo-session")
        auth.raise_for_status()
        headers = {"Authorization": "Bearer " + auth.json()["token"]}
        for name, turns in selection:
            created = client.post("/v1/conversations", headers=headers, json={})
            created.raise_for_status()
            cid = created.json()["id"]
            for ordinal, (question, expected_class, indices, answer_terms) in enumerate(turns, start=1):
                start = time.monotonic()
                response = client.post(f"/v1/conversations/{cid}/messages:stream", headers=headers,
                                       json={"content": question})
                events = frames(response.text)
                final = next((value for kind, value in reversed(events) if kind == "message.completed"), None)
                failure = next((value.get("code") for kind, value in events if kind == "message.failed"), None)
                verified_sources = []
                if final:
                    for mapping in final["citations"]:
                        citation = mapping["citation"]
                        read = client.get(f"/v1/conversations/{cid}/messages/{final['message_id']}"
                                          f"/citations/{citation['citation_id']}/source", headers=headers)
                        valid_hash = False
                        if read.status_code == 200:
                            content = read.json()
                            canonical = canonical_sources.get(citation["chunk_id"])
                            valid_hash = (hashlib.sha256(content["content_text"].encode()).hexdigest()
                                          == content["content_sha256"] and canonical is not None
                                          and content["content_sha256"] == canonical["quote_span_hash"]
                                          and content["content_text"] == canonical["content_text"])
                        verified_sources.append({"chunk_id": citation["chunk_id"], "section": citation["locator"],
                                                 "valid_hash": valid_hash, "http_status": read.status_code})
                history = client.get(f"/v1/conversations/{cid}/messages", headers=headers)
                history.raise_for_status()
                history_body = history.json()
                messages = history_body.get("items", []) if isinstance(history_body, dict) else history_body
                persisted = next((m.get("final_result") for m in messages
                                  if final and m["id"] == final["message_id"]), None)
                expected = [{"chunk_id": source.rows[i]["chunk_id"], "content_sha256": source.rows[i]["quote_span_hash"]}
                            for i in indices]
                returned = {row["chunk_id"] for row in verified_sources}
                # Multi-source questions must return BOTH required parent records;
                # switch questions accept either reviewed representation.
                coverage = ({r["chunk_id"] for r in expected}.issubset(returned) if name == "two-sources"
                            else not expected or bool(returned & {r["chunk_id"] for r in expected}))
                answer = (final or {}).get("content", "").casefold()
                # Source review found this equality exception being rendered
                # as a minimum. Passing keywords alone would hide that error.
                equality_kept = (name != "scholarship-year" or ordinal != 2
                                 or not any(term in answer for term in ("tối thiểu bằng", "ít nhất bằng")))
                passed = bool(final and final["response_class"] == expected_class and persisted == final
                              and coverage and equality_kept and all(term in answer for term in answer_terms)
                              and (bool(verified_sources) if expected_class == "grounded_answer" else not verified_sources)
                              and all(row["valid_hash"] for row in verified_sources))
                row = {"scenario": name, "turn": ordinal, "question": question, "conversation_id": cid,
                       "expected_class": expected_class, "expected_sources": expected, "passed": passed,
                       "failure": failure, "http_status": response.status_code,
                       "latency_ms": round((time.monotonic() - start) * 1000), "final": final,
                       "history_matches_final": bool(final and persisted == final), "sources": verified_sources}
                results.append(row)
                retain(target.with_name(f"{target.stem}-{len(results):02d}.json"), row)
                print(json.dumps({"scenario": name, "turn": ordinal, "passed": passed, "failure": failure,
                                  "response_class": (final or {}).get("response_class"),
                                  "history_matches": row["history_matches_final"], "latency_ms": row["latency_ms"]}), flush=True)
                time.sleep(7)
    retain(target, {"scope": "public_dialogue_regression_live_HTTP_SSE_current_public_sources", "results": results,
                    "passed": sum(r["passed"] for r in results), "total": len(results),
                    "limit": "Source coverage, required terms and persisted final equality; inspect claims against cited source. Not a production correctness certificate."})


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--only")
    args = parser.parse_args()
    destination = checked(args.output)
    if destination.exists():
        raise ValueError("new evidence file required")
    evaluate(destination, args.only)
