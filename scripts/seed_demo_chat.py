"""Give simulated students a real chat history: ask the RUNNING assistant real questions (paid provider via the gateway).

    python scripts/seed_demo_chat.py --limit 3          # measure: ask 3 questions, report provider calls used
    python scripts/seed_demo_chat.py --max-calls 150    # continue with the rest, stop if the call budget is reached

Answers and citations are whatever the live RAG returns over public HUCE sources; nothing is written into the
conversation store directly. Questions come from scripts/demo/campus_2026hk1.py; each is asked once (receipt in
infra/local/seed-demo-2026hk1/chat-receipt.json). Paced under the per-account limit (30 requests/minute).
"""
from __future__ import annotations

import argparse
import codecs
import json
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "services/api/src")]
from demo import campus_2026hk1 as sem  # noqa: E402

BASE = "http://127.0.0.1:8015"
GATEWAY = "http://127.0.0.1:8025/health"
RECEIPT = ROOT / "infra/local/seed-demo-2026hk1/chat-receipt.json"
CREDENTIALS = ROOT / "infra/local/knowledge-platform-20261023/campus-directory-credentials.json"


def gateway_calls() -> int:
    value = httpx.get(GATEWAY, trust_env=False, timeout=5).json()
    return int(value.get("ok", 0)) + int(value.get("failed", 0))


def final_of(stream: str):
    for block in stream.split("\n\n"):
        if "event: message.completed" in block:
            return json.loads("\n".join(line[5:].lstrip() for line in block.splitlines() if line.startswith("data:")))
    return None


def ask(client: httpx.Client, question: str) -> dict:
    for _ in range(6):
        conversation = client.post("/v1/conversations", json={"mode": "persistent"})
        if conversation.status_code != 429:
            break
        time.sleep(int(conversation.headers.get("Retry-After", "5")) + 1)
    conversation.raise_for_status()
    conversation_id = conversation.json()["id"]
    for _ in range(6):
        with client.stream("POST", f"/v1/conversations/{conversation_id}/messages:stream", json={"content": question}) as response:
            if response.status_code in (429, 503):
                time.sleep(int(response.headers.get("Retry-After", "5")) + 1)
                continue
            response.raise_for_status()
            decoder, buffer = codecs.getincrementaldecoder("utf-8")(), ""
            for raw in response.iter_bytes():
                buffer += decoder.decode(raw).replace("\r\n", "\n")
            final = final_of(buffer) or {}
            return {"conversation_id": conversation_id, "outcome": final.get("outcome_kind") or final.get("response_class"),
                    "citations": len(final.get("citations") or [])}
    raise RuntimeError("assistant stayed busy")


def rate(receipt: dict, students: list[dict]) -> None:
    """About half of the students rate the answer they got (mostly helpful), through the real feedback endpoint."""
    import random
    import uuid
    rng = random.Random(77)
    by_user = {s["username"]: s for s in students}
    clients: dict[str, httpx.Client] = {}
    rated = 0
    for question, result in receipt["asked"].items():
        if result.get("rated") in ("HELPFUL", "NOT_HELPFUL") or rng.random() < 0.45:
            continue
        student = by_user[result["student"]]
        client = clients.get(student["username"])
        if client is None:
            client = httpx.Client(base_url=BASE, trust_env=False, timeout=60, headers={"Origin": BASE})
            client.post("/v1/knowledge/platform/session", json={"username": student["username"], "password": student["password"]}).raise_for_status()
            clients[student["username"]] = client
        messages = client.get(f"/v1/conversations/{result['conversation_id']}/messages").json()["items"]
        answer = next((m for m in reversed(messages) if str(m.get("sender_type", "")).lower().endswith("assistant")), None)
        if answer is None:
            continue
        helpful = result.get("outcome") == "grounded_answer" and rng.random() < 0.85
        from campus247.domain.shared.values import generate_uuid7  # the feedback API takes UUIDv7 client ids
        body = {"rating": "HELPFUL" if helpful else "NOT_HELPFUL", "client_id": generate_uuid7()}
        if not helpful:
            body["comment"] = rng.choice(["Câu trả lời chưa nói rõ thời hạn.", "Em cần thông tin cụ thể cho khóa của em.",
                                          "Chưa trả lời đúng ý em hỏi."])
        reply = client.post(f"/v1/conversations/{result['conversation_id']}/messages/{answer['id']}/feedback", json=body)
        result["rated"] = body["rating"] if reply.status_code in (200, 201) else f"HTTP {reply.status_code}"
        rated += reply.status_code in (200, 201)
        RECEIPT.write_text(json.dumps(receipt, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"rated": rated}))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=len(sem.CHAT_QUESTIONS))
    parser.add_argument("--max-calls", type=int, default=150, help="stop before the gateway counter grows by more than this")
    parser.add_argument("--rate", action="store_true", help="only rate answers already received (no provider calls)")
    args = parser.parse_args()
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8")) if RECEIPT.exists() else {"seed_batch": sem.BATCH, "asked": {}}
    students = [a for a in json.loads(CREDENTIALS.read_text(encoding="utf-8"))["accounts"] if a["role"] == "STUDENT"]
    if args.rate:
        rate(receipt, students)
        return 0
    clients: dict[str, httpx.Client] = {}
    start_calls, asked_now = gateway_calls(), 0
    for n, question in enumerate(sem.CHAT_QUESTIONS):
        if question in receipt["asked"]:
            continue
        if asked_now >= args.limit:
            break
        used = gateway_calls() - start_calls
        if used >= args.max_calls:
            print(json.dumps({"stopped": "call budget reached", "calls": used}))
            break
        student = students[(n * 7) % len(students)]  # spread over many students; some get two or three
        client = clients.get(student["username"])
        if client is None:
            client = httpx.Client(base_url=BASE, trust_env=False, timeout=180, headers={"Origin": BASE})
            client.post("/v1/knowledge/platform/session", json={"username": student["username"], "password": student["password"]}).raise_for_status()
            clients[student["username"]] = client
        before = gateway_calls()
        result = ask(client, question)
        result.update(student=student["username"], provider_calls=gateway_calls() - before)
        receipt["asked"][question] = result
        RECEIPT.parent.mkdir(parents=True, exist_ok=True)
        RECEIPT.write_text(json.dumps(receipt, ensure_ascii=False, indent=1), encoding="utf-8")
        asked_now += 1
        print(json.dumps({"n": n + 1, **{k: result[k] for k in ("outcome", "citations", "provider_calls")}}), flush=True)
        time.sleep(2.5)
    print(json.dumps({"asked_this_run": asked_now, "provider_calls_this_run": gateway_calls() - start_calls,
                      "asked_total": len(receipt["asked"])}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
