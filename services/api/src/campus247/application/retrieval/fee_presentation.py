"""Render a model-proposed, source-verified table rate with explicit scope.

This cannot produce an answer from an empty/invalid model response. Amount,
unit, program and applicability must already match the one retrieved row.
The rendered claim still undergoes the ordinary and semantic evidence gates.
"""
import hashlib
import json
import logging
import re
from dataclasses import replace

from campus247.application.retrieval.evidence_gate import EvidenceGate, parse_grounded_claims
from campus247.application.retrieval.material_support import (
    applicable_fee_row_ranges, fee_unit_span, normalized, numeric_value, price_rate_units,
)
from campus247.application.knowledge.question_scope import tuition_answer_scope_issue
from campus247.ports.llm import LlmResponse, LlmResponseStatus


def present_verified_fee(response, bundle, question, *, threshold=None):
    if not isinstance(response, LlmResponse) or response.status != LlmResponseStatus.COMPLETED or response.tool_candidates:
        return response
    try:
        draft = parse_grounded_claims(response.output_text or "")
        if len(draft.claims) != 1 or draft.claims[0].claim_type != "fee":
            return response
        claim = draft.claims[0]
        if len(claim.citation_ids) != 1 or re.search(r"\b(?:toi|ban|em|minh|ho so|con no|da nop|gpa|ky luat)\b", normalized(claim.text)):
            return response
        record = bundle.resolve(claim.citation_ids[0])
        ranges = applicable_fee_row_ranges(record.content_text, question) if record else None
        if not ranges or len(ranges) != 3:
            return response
        cohorts = re.findall(r"\b(?:k\s*|khoa\s+)(\d{2})\b", normalized(question))
        years = re.findall(r"\b20\d{2}\s*[-–/]\s*20\d{2}\b", question)
        if len(set(cohorts)) != 1 or len(set(years)) != 1:
            return response
        if re.sub(r"\D", "", years[0]) not in re.sub(r"\D", "", record.content_text[:ranges[0][1]]):
            return response
        if re.search(r"\b(?:tong|phep tinh|no hoc phi)\b|\b\d+\s*(?:tin chi|tin)\b", normalized(question)):
            return response
        start, end = ranges[-1]
        cells = [cell.strip() for cell in record.content_text[start:end].split("|")]
        unit_range = fee_unit_span(record.content_text, ranges)
        if len(cells) != 4 or not unit_range:
            return response
        unit = record.content_text[unit_range[0]:unit_range[1]]
        expected_unit = "tin_chi" if normalized(unit) == "tin chi" else "dvht"
        # Remove only the ambiguous duplicated denominator, never substitute
        # a sole wrong unit or change a model's proposed price.
        text = claim.text
        if expected_unit == "tin_chi":
            text = re.sub(r"(?<=tín chỉ)\s*\(\s*ĐVHT\s*\)", "", text, flags=re.I)
        rates = price_rate_units(text)
        if set(rates) != {(numeric_value(cells[-1]), expected_unit)}:
            return response
        candidate = replace(claim, text=text)
        checked = replace(draft, claims=(candidate,))
        gate = EvidenceGate() if threshold is None else EvidenceGate(min_token_overlap_ratio=threshold)
        if not gate.verify(checked, bundle).passed or tuition_answer_scope_issue(question, checked, bundle):
            return response
        # Additional constraint: presentation cannot erase an unsupported
        # qualification or assertion. Every word must belong to this row's
        # source context or a verified applicability label/degree expansion.
        selected = "\n".join(record.content_text[lo:hi] for lo, hi in ranges)
        tokens = set(re.findall(r"\w+", normalized(text)))
        if re.search(r"\b(?:khong|chua|mien|giam|no|da)\b", normalized(text)):
            return response
        allowed = set(re.findall(r"\w+", normalized(selected))) | {"k" + cohorts[0], "khoa", "la", "co", "thuoc", "cho"}
        program = normalized(cells[1])
        if re.search(r"\bcn\b", program):
            allowed |= {"cu", "nhan"}
        if re.search(r"\b(?:ks|kts)\b", program):
            allowed |= {"ky", "su", "kien", "truc"}
        if "huce" in normalized(record.issuer):
            allowed.add("huce")
        if not tokens.issubset(allowed):
            return response
        # Existing content/secrets guard also applies before presentation. A
        # renderer must never erase an unsafe assertion to make it pass.
        from campus247.agent.nodes.compose import OutputGuardNode
        from campus247.agent.state import AgentState, DraftResponse, NormalizedTurn, Route, Terminal, ToolFlowState
        rendered = candidate.text + " " + " ".join(f"[{ref}]" for ref in candidate.citation_ids)
        state = AgentState(NormalizedTurn("presentation", "presentation", "presentation", question),
            route=Route.GROUNDED_FAQ, tool_flow=ToolFlowState(candidates=[]),
            draft=DraftResponse(text=rendered, is_grounded=True, gate_decision="grounded", grounded_claims=(candidate,)))
        if OutputGuardNode().execute(state).terminal == Terminal.SAFE_FAILURE:
            return response
        group = record.content_text[ranges[1][0]:ranges[1][1]].strip()
        text = f"{group} — {cells[1]}, {cells[2]}; khóa K{cohorts[0]}, năm học {years[0]}: {cells[3]} đồng/{unit}."
        output = json.dumps({"claims": [{"text": text, "citation_ids": list(claim.citation_ids), "claim_type": "fee"}]}, ensure_ascii=False)
        if output == response.output_text:
            return response
        logging.getLogger("campus247.generation").info(
            "fee_presentation before_sha256=%s after_sha256=%s source_sha256=%s",
            hashlib.sha256((response.output_text or "").encode()).hexdigest(), hashlib.sha256(output.encode()).hexdigest(), record.quote_span_hash)
        return replace(response, output_text=output)
    except (ValueError, TypeError, KeyError):
        return response
