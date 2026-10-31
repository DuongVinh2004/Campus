"""Generate a bounded draft with references resolved to stable local unit IDs."""
from __future__ import annotations

import asyncio
import json
from hashlib import sha256
import logging
import os
import re
from collections.abc import Sequence
from dataclasses import dataclass

from campus247.ports.llm import LlmGateway, LlmRequest
from campus247.rag_v2.generation.contacts import contact_map, redact, restore
from campus247.rag_v2.generation.json_output import response_object
from campus247.rag_v2.generation.prompt import GENERATION_PROMPT, STATEMENTS_SCHEMA
from campus247.rag_v2.types import Statement, Understanding, Unit


DECISIONS = frozenset({"answer", "clarify", "no_source", "out_of_scope"})


@dataclass(frozen=True)
class Draft:
    """What the model proposed: how to treat the question, and statements bound to unit IDs."""
    statements: tuple[Statement, ...] = ()
    decision: str = "answer"
    clarify_question: str = ""


async def generate_statements(
    gateway: LlmGateway, question: str, understanding: Understanding, units: Sequence[Unit],
    *, deadline_ms: int, max_output_tokens: int,
) -> list[Statement]:
    return list((await generate_draft(gateway, question, understanding, units, deadline_ms=deadline_ms,
                                      max_output_tokens=max_output_tokens)).statements)


def _clarify_question(value) -> str:
    text = " ".join(value.split()) if isinstance(value, str) else ""
    # One short question; links and addresses are never model-authored display text.
    return text if 0 < len(text) <= 200 and not re.search(r"https?:|www\.|@|\d{8,}", text) else ""


async def generate_draft(
    gateway: LlmGateway, question: str, understanding: Understanding, units: Sequence[Unit],
    *, deadline_ms: int, max_output_tokens: int,
) -> Draft:
    selected = list(units[:12])
    if not selected:
        return Draft()
    markers = contact_map(selected)
    labels = {f"U{i}": unit for i, unit in enumerate(selected, 1)}
    evidence = [{"label": f"[{label}]", "text": redact(unit.text, markers),
                 "scope": {"cohorts": unit.scope.cohorts, "programs": unit.scope.programs,
                           "academic_years": unit.scope.academic_years}}
                for label, unit in labels.items()]
    content = json.dumps({"question": question, "question_type": understanding.question_type,
                          "sources": evidence}, ensure_ascii=False)
    # Known source contacts are minimized everywhere in the model view. Other
    # user identifiers remain subject to the unmodified outbound policy.
    content = redact(content, markers)
    if len(content) > 90_000:
        raise ValueError("rag_v2 prompt exceeds bound")
    request = LlmRequest(
        request_id="rag_v2_generation", route_id="grounded_faq", model_profile="grounded_faq",
        system_instructions=GENERATION_PROMPT,
        input_items=tuple({"role": "user", "content": content[i:i + 10_000]}
                          for i in range(0, len(content), 10_000)),
        output_schema=STATEMENTS_SCHEMA, deadline_ms=deadline_ms,
        max_output_tokens=max_output_tokens,
    )
    async with asyncio.timeout(deadline_ms / 1000):
        response = await gateway.generate(request)
    value = response_object(response)
    if os.environ.get("CAMPUS247_RAG_V2_DEBUG_DIR"):  # eval-only capture of synthetic cases; off by default
        import pathlib
        with (pathlib.Path(os.environ["CAMPUS247_RAG_V2_DEBUG_DIR"]) / "generation.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"question_sha": sha256(question.encode()).hexdigest(), "unit_ids": [u.unit_id for u in selected], "content": content,
                "output": getattr(response, "output_text", None) or getattr(response, "structured_output", None)},
                ensure_ascii=False, default=str) + "\n")
    decision = value.get("decision") if value else None
    if decision not in DECISIONS:
        decision = "answer"      # older or malformed output: the statements are verified exactly as before
    if decision != "answer":
        logging.getLogger("campus247.rag_v2").warning("rag_v2_gen decision=%s", decision)
        return Draft((), decision, _clarify_question(value.get("clarify_question")))
    rows = value.get("statements") if value else None
    drops = {"parsed": value is not None, "status": str(getattr(response, "status", "?")), "rows": 0,
             "shape": 0, "ref": 0, "contact": 0}
    if not isinstance(rows, list):
        logging.getLogger("campus247.rag_v2").warning("rag_v2_gen %s", json.dumps(drops))
        return Draft()
    drops["rows"] = len(rows)
    result = []
    for row in rows[:32]:
        if not isinstance(row, dict):
            drops["shape"] += 1
            continue
        text, refs = row.get("text"), row.get("unit_ids")
        if (not isinstance(text, str) or not text.strip() or len(text) > 8_000
                or not isinstance(refs, list) or not 1 <= len(refs) <= 12):
            drops["shape"] += 1
            continue
        if any(not isinstance(ref, str) or ref not in labels for ref in refs):
            drops["ref"] += 1
            continue
        cited = [labels[ref] for ref in refs]
        # Unknown or cross-source contact labels cannot become display text.
        if restore(text, cited) is None:
            drops["contact"] += 1
            continue
        result.append(Statement(text, tuple(dict.fromkeys(unit.unit_id for unit in cited))))
    logging.getLogger("campus247.rag_v2").warning("rag_v2_gen %s kept=%d", json.dumps(drops), len(result))
    return Draft(tuple(result))
