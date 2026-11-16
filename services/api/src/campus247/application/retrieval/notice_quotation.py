"""Quote explicitly requested printed notice fields from an attested original."""
import json
import re
from dataclasses import replace

from campus247.application.conversation.followup import normalized_question
from campus247.application.knowledge.document_reference import named_notice_rerank_question
from campus247.application.retrieval.evidence_gate import parse_grounded_claims
from campus247.application.retrieval.public_notice_contacts import is_pinned_public_notice
from campus247.ports.llm import LlmResponse, LlmResponseStatus


def present_notice_quotation(response, bundle, question):
    if (not isinstance(response, LlmResponse) or response.status != LlmResponseStatus.COMPLETED
            or response.tool_candidates or named_notice_rerank_question(question) is None):
        return response
    try:
        if not parse_grounded_claims(response.output_text or "").claims:
            return response
    except (ValueError, TypeError, KeyError):
        return response
    query = normalized_question(question.partition(",")[2])
    if re.search(r"hien tai|hien nay|con hieu luc|con su dung|xac thuc|ky giup", query):
        return response
    quotes = []
    for citation, record in bundle.citations.items():
        if not is_pinned_public_notice(record):
            continue
        source = record.content_text
        years = lambda value: {re.sub(r"\D", "", y) for y in re.findall(r"\b20\d{2}\s*[-–/]\s*20\d{2}\b", value)}
        if not years(question.partition(",")[0]).issubset(years(record.title + "\n" + (record.section_path or "") + "\n" + source)):
            continue
        quote = None
        if "so van ban" in query and "ngay ban hanh" in query:
            number = re.findall(r"(?m)^Số:\s*[^\n]+", source)
            date = re.findall(r"(?m)^Hà Nội, ngày\s+\d+\s+tháng\s+\d+\s+năm\s+\d{4}\s*$", source)
            if len(number) == len(date) == 1:
                quote = number[0].strip() + "\n" + date[0].strip()
        elif "thong tin lien he" in query or ("so dien thoai" in query and "email" in query):
            start = source.find("Mọi thắc mắc liên hệ")
            end = source.find("\nTrân trọng", start) if start >= 0 else -1
            if start >= 0 and end > start and "Email:" in source[start:end]:
                quote = source[start:end].strip()
        elif all(term in query for term in ("chuc danh", "ho ten", "in", "chu ky")):
            match = re.search(r"(?m)^TL\. HIỆU TRƯỞNG\nKT\. TRƯỞNG PHÒNG[^\n]+\nPHÓ TRƯỞNG PHÒNG\nThS\. [^\n]+\s*$", source)
            if match:
                quote = match[0].strip()
        if quote and len(quote.split()) <= 160:
            quotes.append((citation, quote))
    if len(quotes) != 1:
        return response
    citation, quote = quotes[0]
    return replace(response, output_text=json.dumps({"claims": [{"text": quote,
        "citation_ids": [citation], "claim_type": "policy"}]}, ensure_ascii=False))
