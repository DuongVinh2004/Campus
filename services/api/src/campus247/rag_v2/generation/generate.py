"""Generate a bounded draft with references resolved to stable local unit IDs."""
from __future__ import annotations

import asyncio
import json
from hashlib import sha256
import logging
import os
from collections.abc import Sequence
from dataclasses import dataclass

from campus247.ports.llm import LlmGateway, LlmRequest
from campus247.rag_v2.generation.contacts import contact_map, redact, restore
from campus247.rag_v2.generation.json_output import response_object
from campus247.rag_v2.generation.prompt import GENERATION_PROMPT, STATEMENTS_SCHEMA
from campus247.rag_v2.types import Statement, Understanding, Unit
from campus247.rag_v2.understanding.normalize import fold


DECISIONS = frozenset({"answer", "clarify", "no_source", "out_of_scope"})
SLOT_LABELS = {
    "cohort": "khóa tuyển sinh", "academic_year": "năm học",
    "program": "ngành hoặc chương trình đào tạo", "training_system": "hệ đào tạo",
    "document": "văn bản hoặc quyết định", "semester": "học kỳ", "audience": "đối tượng áp dụng",
}


@dataclass(frozen=True)
class Draft:
    """What the model proposed: how to treat the question, and statements bound to unit IDs."""
    statements: tuple[Statement, ...] = ()
    decision: str = "answer"
    clarify_question: str = ""
    missing_slots: tuple[str, ...] = ()
    malformed: bool = False      # the model output could not be parsed into the statement schema
    facets: tuple[tuple[str, str], ...] = ()   # (id, ask): the distinct things the question asks, in its own words
    statement_facets: tuple[str, ...] = ()     # facet id per statement ("" when unassigned)


async def generate_statements(
    gateway: LlmGateway, question: str, understanding: Understanding, units: Sequence[Unit],
    *, deadline_ms: int, max_output_tokens: int,
) -> list[Statement]:
    return list((await generate_draft(gateway, question, understanding, units, deadline_ms=deadline_ms,
                                      max_output_tokens=max_output_tokens)).statements)


def clarification_question(slots) -> str:
    labels = [SLOT_LABELS[slot] for slot in slots if slot in SLOT_LABELS]
    return ("Bạn cho biết " + " và ".join(labels) + " để mình tra đúng nguồn nhé?" if labels
            else "Bạn có thể nói rõ hơn bạn đang hỏi về nội dung nào không?")


def debug_capture(name, metadata, *, content=None):
    """Operational capture has no display text; raw synthetic content is a separate opt-in."""
    directory = os.environ.get("CAMPUS247_RAG_V2_DEBUG_DIR")
    if not directory:
        return
    payload = dict(metadata)
    if content is not None and os.environ.get("CAMPUS247_RAG_V2_DEBUG_CONTENT") == "synthetic":
        payload["content"] = content
    try:
        import pathlib
        with (pathlib.Path(directory) / (name + ".jsonl")).open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except OSError:
        pass


def _facets(raw, question):
    """Facets are the user's own words: an ``ask`` that is not in the question is dropped, so the
    server can show it back safely. A single facet is the whole question and adds nothing."""
    if not isinstance(raw, list):
        return ()
    folded, seen, result = fold(question), set(), []
    for item in raw[:8]:
        if not isinstance(item, dict):
            continue
        facet_id, ask = item.get("id"), item.get("ask")
        if (isinstance(facet_id, str) and isinstance(ask, str) and facet_id and facet_id not in seen
                and 2 <= len(ask.strip()) <= 80 and fold(ask.strip()) in folded):
            seen.add(facet_id)
            result.append((facet_id, " ".join(ask.split())))
    return tuple(result) if len(result) >= 2 else ()


async def generate_draft(
    gateway: LlmGateway, question: str, understanding: Understanding, units: Sequence[Unit],
    *, deadline_ms: int, max_output_tokens: int, focus: Sequence[str] = (),
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
    body = {"question": question, "question_type": understanding.question_type, "sources": evidence}
    if focus:
        # Parts of the question (its own words) that an earlier answer left uncovered; data, not instructions.
        body["missing_parts"] = list(focus)
    content = json.dumps(body, ensure_ascii=False)
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
    output = json.dumps(value, ensure_ascii=False)
    debug_capture("generation", {"request_id": "rag_v2_generation",
        "question_sha": sha256(question.encode()).hexdigest(), "question_length": len(question),
        "source_count": len(selected), "content_sha": sha256(content.encode()).hexdigest(),
        "content_length": len(content), "output_sha": sha256(output.encode()).hexdigest(),
        "output_length": len(output)}, content={"input": content, "output": output})
    decision = value.get("decision") if value else None
    if decision not in DECISIONS:
        decision = "answer"      # older or malformed output: the statements are verified exactly as before
    if decision != "answer":
        logging.getLogger("campus247.rag_v2").warning("rag_v2_gen decision=%s", decision)
        proposed = value.get("missing_slots")
        slots = tuple(dict.fromkeys(s for s in proposed if isinstance(s, str) and s in SLOT_LABELS)) if isinstance(proposed, list) else ()
        return Draft((), decision, clarification_question(slots), slots)
    rows = value.get("statements") if value else None
    drops = {"parsed": value is not None, "status": str(getattr(response, "status", "?")), "rows": 0,
             "shape": 0, "ref": 0, "contact": 0}
    if not isinstance(rows, list):
        logging.getLogger("campus247.rag_v2").warning("rag_v2_gen %s", json.dumps(drops))
        return Draft(malformed=True)
    drops["rows"] = len(rows)
    facets = _facets(value.get("facets"), question)
    facet_ids = {facet_id for facet_id, _ in facets}
    result, assigned = [], []
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
        facet = row.get("facet")
        assigned.append(facet if isinstance(facet, str) and facet in facet_ids else "")
    logging.getLogger("campus247.rag_v2").warning("rag_v2_gen %s kept=%d", json.dumps(drops), len(result))
    return Draft(tuple(result), facets=facets, statement_facets=tuple(assigned))
