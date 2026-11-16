"""Quote an exact reviewed cell/group for a single-field curriculum question."""
import json
import re
from dataclasses import replace

from campus247.application.conversation.followup import normalized_question
from campus247.application.retrieval.evidence_gate import parse_grounded_claims
from campus247.ports.llm import LlmResponse, LlmResponseStatus


def present_curriculum_quotation(response, bundle, question):
    if not isinstance(response, LlmResponse) or response.status != LlmResponseStatus.COMPLETED or response.tool_candidates:
        return response
    query = normalized_question(question)
    if re.search(r"tien quyet|song hanh|hoc truoc|dieu kien|tong|cong cac", query):
        return response
    codes = set(re.findall(r"\b\d{6}\b", query))
    group = re.search(r"\btu chon\s+(\d+)\b", query)
    catalogue = re.findall(r"\b(?:hptcbb|required elective)\s+\d+\b", query)
    if catalogue and (len(catalogue) != 1 or codes or group):
        return response
    physical = re.findall(r"\b(?:giao duc|gd)\s+the chat\s+([1-3])\b", query)
    if physical and (len(physical) != 1 or codes or group):
        return response
    if len(codes) != 1 and group is None and not physical and not catalogue:
        return response
    try:
        draft = parse_grounded_claims(response.output_text or "")
        if not draft.claims:
            return response
    except (ValueError, TypeError, KeyError):
        return response
    quotes = []
    for citation_id, record in bundle.citations.items():
        attestation = record.curriculum
        if not attestation or not attestation.binds(record):
            continue
        if catalogue:
            if catalogue[0] not in {normalized_question(label) for label in attestation.elective_groups}:
                continue
        elif len(attestation.semesters) != 1:
            continue
        if len(codes) == 1 and not codes.issubset(attestation.course_codes):
            continue
        source = record.content_text
        if physical:
            # Quote only an explicit printed TC value. The number in a PE
            # name supplies no credit value in other admitted diagrams.
            matches = [part.strip() for part in source.split("\n\n")
                if normalized_question(part).startswith("giao duc the chat " + physical[0])
                and re.search(r"\b\d+\s*TC\b", part, re.I)]
            if len(matches) == 1:
                quotes.append((citation_id, matches[0]))
            continue
        pattern = (rf"(?mi)^{re.escape(catalogue[0])}\b" if catalogue else
            rf"(?mi)^TỰ CHỌN\s+{group[1]}\b" if group else rf"(?m)^{next(iter(codes))}\s*[-–—]\s*\d+")
        matches = list(re.finditer(pattern, source))
        if len(matches) != 1:
            continue
        start = matches[0].start()
        ends = [position for separator in ("\n\n", "\nTổng:") if (position := source.find(separator, start)) >= 0]
        end = min(ends) if ends else len(source)
        quote = source[start:end].strip()
        if quote and len(quote.split()) <= 160:
            quotes.append((citation_id, quote))
    if len(quotes) != 1:
        return response
    citation_id, quote = quotes[0]
    return replace(response, output_text=json.dumps({"claims": [{"text": quote,
        "citation_ids": [citation_id], "claim_type": "policy"}]}, ensure_ascii=False))
