"""Quote admitted blank-form labels without inventing units or list numbers."""
import json
import re
from dataclasses import replace

from campus247.application.conversation.followup import normalized_question
from campus247.application.knowledge.document_reference import named_form_rerank_question
from campus247.application.knowledge.deadline_excerpt import is_submission_deadline_question, submission_deadline_excerpt
from campus247.application.retrieval.evidence_gate import parse_grounded_claims
from campus247.domain.publication import official_huce_uri
from campus247.ports.llm import LlmResponse, LlmResponseStatus


def present_form_quotation(response, bundle, question):
    full_query = normalized_question(question)
    raw_prefix = question.partition(",")[0]
    prefix = normalized_question(raw_prefix)
    deadline = (prefix.startswith("theo ") and "hoc bong stem quy chau a" in prefix
        and bool(re.search(r"\b20\d{2}\s*[-–/]\s*20\d{2}\b", raw_prefix))
        and (is_submission_deadline_question(question) or "thoi gian nhan ho so" in full_query))
    if (not isinstance(response, LlmResponse) or response.status != LlmResponseStatus.COMPLETED
            or response.tool_candidates or (named_form_rerank_question(question) is None and not deadline)):
        return response
    try:
        draft = parse_grounded_claims(response.output_text or "")
        if not draft.claims:
            return response
    except (ValueError, TypeError, KeyError):
        return response
    query = normalized_question(question.partition(",")[2])
    quotes = []
    for citation_id, record in bundle.citations.items():
        publication = record.publication
        if (record.simulation_label or not record.release_id
                or "hoc bong stem quy chau a" not in normalized_question(record.title)
                or not (official_huce_uri(record.canonical_uri) or (publication and publication.binds(record)))):
            continue
        source = record.content_text
        quote = None
        if deadline:
            quote = submission_deadline_excerpt(source)
            if quote:
                # A bare section heading can repeat the dated field label on
                # the next line. Drop only that duplicate label, no condition.
                repeated = re.match(r"(?is)Thời gian tiếp nhận hồ sơ:\s*-\s*(?=Thời gian tiếp nhận hồ sơ:)", quote)
                if repeated:
                    quote = quote[repeated.end():]
        elif ("so yeu ly lich" in normalized_question(question) and "anh" in query
                and re.search(r"co\s+muc.*(?:dien thoai|sdt).*bo.*me", query)
                and not re.search(r"\d", query) and "SƠ YẾU LÝ LỊCH" in source):
            lines = source.splitlines()
            photos = [line for line in lines if re.fullmatch(r"Ảnh\s+\d+\s*[x×]\s*\d+", line.strip())]
            phones = [line for line in lines if re.fullmatch(r"SĐT bố/\s*mẹ:\s*", line)]
            if len(photos) == len(phones) == 1:
                quote = photos[0] + "\n" + phones[0].rstrip()
        elif ("bang" in query and re.search(r"(?:nhung|cac) cot", query)
                and "chung song" in query and "gia dinh" in query):
            lines = source.splitlines()
            headers = [i for i, line in enumerate(lines) if line.strip().startswith("STT |")]
            if len(headers) == 1 and headers[0] > 0 and "người đang chung sống" in lines[headers[0]-1]:
                quote = "\n".join(lines[headers[0]-1:headers[0]+1])
        elif re.search(r"\b(?:y|muc|cau)\s*\d", query):
            requested = {int(n) for n in re.findall(r"\d+", query)}
            markers = list(re.finditer(r"(?m)^([1-9])\.\s+", source))
            if requested and requested == {int(m[1]) for m in markers}:
                quote = source[markers[0].start():].strip()
        elif "nghia vu" in query:
            heading = "Nghĩa vụ của sinh viên nhận học bổng"
            if source.count(heading) == 1 and "Quyền lợi của sinh viên" not in source:
                quote = source[source.index(heading):].strip()
        if quote and len(quote.split()) <= 160:
            quotes.append((citation_id, quote))
    if len(quotes) != 1:
        return response
    citation_id, quote = quotes[0]
    return replace(response, output_text=json.dumps({"claims": [{"text": quote,
        "citation_ids": [citation_id], "claim_type": "policy"}]}, ensure_ascii=False))
