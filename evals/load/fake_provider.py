"""TEST ONLY. Replace the HTTP call to the paid model provider with a local fake, keeping everything else real.

Used by evals/load/sitecustomize.py when CAMPUS_LOADTEST_FAKE_PROVIDER=1, to measure CPU, memory and queueing of the
whole chat pipeline at 100 users without paying for a single call. What stays real: the gateway's egress policy,
operation bounds, budget reservation and settlement, ledger record writing (redirected to a scratch directory, never
the paid ledger), retrieval, verification, guards, persistence and streaming.

Each fake reply is valid for its call (route, safety, rewrite, generation with a verbatim source sentence, semantic
verdict) and waits for a latency drawn from the measured provider latency of that call type (ledger, 25,817 calls,
2026-11-14: p50/p90 ms route 906/1265, safety 875/1156, generation 1218/1891, semantic 860/1141).
"""
from __future__ import annotations

import asyncio
import json
import math
import os
import random
import re
from pathlib import Path

LATENCY_MS = {  # (p50, p90) per call kind
    "route": (906, 1265), "safety": (875, 1156), "generation": (1218, 1891), "semantic": (860, 1141),
    "rewrite": (906, 1265), "other": (900, 1300)}
_rng = random.Random(int(os.environ.get("CAMPUS_LOADTEST_SEED", "7")))


def _latency_s(kind: str) -> float:
    p50, p90 = LATENCY_MS.get(kind, LATENCY_MS["other"])
    sigma = math.log(p90 / p50) / 1.2816
    return math.exp(math.log(p50) + sigma * _rng.gauss(0, 1)) / 1000


def _kind(system: str) -> str:
    if "bộ phân loại an toàn" in system:
        return "safety"
    if "route thuộc grounded_faq" in system or "\"route\"" in system and "grounded_faq" in system:
        return "route"
    if system.startswith("Bạn trả lời bằng tiếng Việt ngắn gọn"):
        return "generation"
    if system.startswith("Kiểm tra: phát biểu có được đoạn dẫn hỗ trợ"):
        return "semantic"
    if system.startswith("Viết lại câu hỏi") or system.startswith("Bạn nhận một câu sinh viên gõ"):
        return "rewrite"
    return "other"


def _sentence(text: str) -> str | None:
    body = text.split("⟦RAG_V2_SOURCE⟧")[-1]
    for line in re.split(r"\n+|(?<=[.;!?])\s+", body):
        line = line.strip(" |\t")
        if 25 <= len(line) <= 220 and "⟦" not in line:
            return line
    return None


def _reply(kind: str, payload: dict) -> dict:
    messages = payload.get("messages", [])
    user = "".join(m.get("content", "") for m in messages if m.get("role") != "system")
    if kind == "safety":
        return {"severity": "normal", "is_crisis": False, "confidence": 0.9}
    if kind == "route":
        return {"route": "grounded_faq"}
    if kind == "rewrite":
        try:
            data = json.loads(user)
            return {"question": data.get("latest_question") or data.get("question") or ""}
        except ValueError:
            return {"question": ""}
    if kind == "generation":
        try:
            sources = json.loads(user).get("sources", [])
        except ValueError:
            sources = []
        for i, source in enumerate(sources, 1):
            sentence = _sentence(source.get("text", ""))
            if sentence:
                return {"decision": "answer", "missing_slots": [],
                        "statements": [{"text": sentence, "unit_ids": [f"U{i}"]}]}
        return {"decision": "no_source", "missing_slots": [], "statements": []}
    if kind == "semantic":
        try:
            count = len(json.loads(user).get("statements", []))
        except ValueError:
            count = 1
        return {"verdicts": [{"i": i, "supported": True} for i in range(count)]}
    return {}


async def _handler(request):
    import httpx
    payload = json.loads(request.content or b"{}")
    system = next((m.get("content", "") for m in payload.get("messages", []) if m.get("role") == "system"), "")
    kind = _kind(system)
    await asyncio.sleep(_latency_s(kind))
    content = json.dumps(_reply(kind, payload), ensure_ascii=False)
    body = {"id": "fake", "model": "deepseek-flash",
            "choices": [{"finish_reason": "stop", "message": {"role": "assistant", "content": content}}],
            "usage": {"prompt_tokens": max(1, len(json.dumps(payload, ensure_ascii=False)) // 3),
                      "completion_tokens": max(1, len(content) // 3)}}
    return httpx.Response(200, json=body)


def install(ledger_dir: str) -> None:
    """Route provider HTTP to the fake and redirect paid-ledger writes to ``ledger_dir``."""
    import httpx
    real_client = httpx.AsyncClient

    def client(*args, **kwargs):
        # The provider call is the only AsyncClient built without a base_url and with an explicit TLS context;
        # embedding / rerank / frontend clients keep the real transport.
        if "base_url" not in kwargs and "verify" in kwargs and "transport" not in kwargs:
            kwargs["transport"] = httpx.MockTransport(_handler)
        return real_client(*args, **kwargs)

    httpx.AsyncClient = client
    Path(ledger_dir).mkdir(parents=True, exist_ok=True)

    import importlib.abc
    import importlib.machinery
    import sys

    class _PatchLedger(importlib.abc.MetaPathFinder):
        def find_spec(self, name, path, target=None):
            if name != "run_public_rag":
                return None
            spec = importlib.machinery.PathFinder.find_spec(name, path)
            if spec is None or spec.loader is None:
                return spec
            loader = spec.loader
            original = loader.exec_module

            def exec_module(module):
                original(module)
                def retain(record_name, value, _dir=Path(ledger_dir)):
                    path = _dir / (record_name + ".json")
                    with path.open("w", encoding="utf-8") as stream:
                        # same encoding as the real retain(), so the measured CPU matches
                        stream.write(json.dumps({**value}, ensure_ascii=False, separators=(",", ":"), default=str))
                module.retain = retain
            loader.exec_module = exec_module
            return spec

    sys.meta_path.insert(0, _PatchLedger())
