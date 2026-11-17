"""Ask for explicit applicability before looking up a tuition amount."""
import re

from campus247.application.conversation.followup import normalized_question


def restored_search_question(original, proposed):
    """Only restore diacritics for ASCII queries; preserve every word/number."""
    if (not original.isascii() or not isinstance(proposed, str) or not proposed.strip()
            or len(proposed) > 4000 or proposed.isascii()
            or normalized_question(original) != normalized_question(proposed)):
        return None
    return proposed.strip()


def focused_source_question(question):
    prefix, separator, rest = question.partition(",")
    reference = normalized_question(prefix)
    if (separator and rest.strip() and reference.startswith("theo ")
        and re.search(r"\b(?:quyet dinh|qd|quy che)\s*\d+\b", reference)
        and not re.search(r"\bk\s*\d{2}\b|\b20\d{2}\b", reference)):
        return rest.strip()
    return question


def programme_reference_codes(question):
    return set(re.findall(r"\bk?((?:6\d|7[01])[a-z]{2,8})\b", normalized_question(question)))


def programme_name_match(question, title):
    """Bibliographic narrowing only; authorization and original evidence remain required."""
    title = re.sub(r"^(?:K\d{2}|K70_and_earlier_verify_individual_row)\s*[—–-]\s*", "", title)
    title = re.sub(r"\(K\d{2}[A-Z0-9]*\)", "", title)
    title = re.split(r"\s*/\s*(?:Programme\b|Engineering\b|Program\b)", title, flags=re.IGNORECASE)[0]
    title = re.sub(r"\s*\(20\d{2}\)\s*", " ", title)
    title = re.split(r"(?:chuyên\s+)?ngành\s+", title, flags=re.IGNORECASE)[-1]
    name = normalized_question(title)
    if len(name.split()) < 2 or len(name) < 7:
        return 0
    return len(name.split()) if " " + name + " " in " " + normalized_question(question) + " " else 0


def explicit_curriculum_reference(question):
    return bool(re.search(r"\b(?:ke hoach|khung chuong trinh|so do)\b", normalized_question(question)))


def focused_curriculum_question(question):
    """Focus a legend definition after the full query selected its programme."""
    prefix, separator, rest = question.partition(",")
    body = normalized_question(rest)
    if (separator and "chu giai" in body and "ma hp" in body
            and normalized_question(prefix).startswith("theo ") and explicit_curriculum_reference(prefix)):
        return rest.strip()
    return question


def programme_credit_question(question, *, has_total=True):
    """Use only after exact programme identifiers have selected source versions.

    Repeated programme names otherwise select the diagram header rather than
    its printed total. The returned complete parent still proves identity.
    """
    text = normalized_question(question)
    # A named physical-education component is not the programme total. Its
    # printed unit can differ between diagrams, so keep that search subject.
    if (re.search(r"giao duc the chat|gd\s*the chat|giao duc quoc phong|\bgdtc\b|\bgdqp\b", text)
            and not re.search(r"\btong\b|\btoan (?:khoa|chuong trinh)\b", text)):
        return question
    if re.search(r"\b\d{6}\b", text):
        return question
    if ("tin chi" in text or re.search(r"\btc\b", text)) and not re.search(r"\b(?:hoc ky|hoc phan|mon|ma hp)\b", text):
        if not has_total:
            return question
        return "Tổng số tín chỉ (TC) là bao nhiêu?"
    return question


def tuition_answer_scope_issue(question, draft, bundle=None):
    """A source-supported row still must apply to the cohort being asked about."""
    query = normalized_question(question)
    if "hoc phi" not in query:
        return None
    requested = {int(v) for v in re.findall(r"\b(?:k\s*|khoa\s+)(\d{2})\b", query)}
    if len(requested) != 1:
        return None
    cohort = next(iter(requested))
    for claim in draft.claims:
        text = normalized_question(claim.text)
        # A correction of a wrong unit cannot deny an applicable cohort. This
        # requires a unique source row, not the user question as factual proof.
        if bundle is not None and re.search(r"\d[.,]\d{3}", claim.text):
            from campus247.application.retrieval.material_support import (
                applicable_fee_row_ranges,
                support_issues,
            )
            for ref in claim.citation_ids:
                record = bundle.resolve(ref)
                ranges = applicable_fee_row_ranges(record.content_text, question) if record else None
                if ranges:
                    selected = "\n".join(record.content_text[start:end] for start, end in ranges)
                    if support_issues(claim.text, selected):
                        return "AI_QUESTION_SCOPE_MISMATCH"
                    denied = re.search(r"\bkhong (?:phai(?: (?:cho|muc hoc phi))?|ap dung(?: cho)?|danh cho)\b(.{0,100}?)\bk\s*" + str(cohort) + r"\b", text)
                    # A denied rate unit is different from denying the cohort.
                    if denied and not re.search(r"\b(?:dong|dvht|tin chi)\b", denied[1]):
                        return "AI_QUESTION_SCOPE_MISMATCH"
        values = [int(v) for v in re.findall(r"\bk\s*(\d{2})\b", text)]
        if not values or not re.search(r"\d[.,]\d{3}", claim.text):
            continue
        if "tro ve truoc" in text:
            applies = cohort <= min(values)
        elif re.search(r"\btu\s+k", text):
            applies = cohort >= min(values)
        else:
            applies = min(values) <= cohort <= max(values)
        if not applies:
            return "AI_QUESTION_SCOPE_MISMATCH"
    return None


def tuition_clarification(question):
    text = normalized_question(question)
    if "hoc phi" not in text or any(word in text for word in ("mien giam", "mien hoc phi", "han nop", "ho so")):
        return None
    missing=[]
    if not re.search(r"\bk\s*\d{2}\b|\bkhoa\s+\d{2}\b",text):
        missing.append("khóa học (ví dụ K71)")
    if not re.search(r"\b(cu nhan|ky su|kien truc su|cn|ks|kts|chat luong cao|vua lam vua hoc)\b",text):
        missing.append("chương trình (cử nhân, kỹ sư, chất lượng cao…) và hệ đào tạo")
    if not re.search(r"\b20\d{2}\s*[-–/]\s*20\d{2}\b",question):
        missing.append("năm học cụ thể (ví dụ 2026–2027)")
    if not missing:
        return None
    return ("Để đối chiếu đúng mức học phí, bạn cho biết " + "; ".join(missing) +
            ". Nếu học chương trình Anh ngữ/Pháp ngữ hoặc liên kết quốc tế, vui lòng nói rõ để kiểm tra phụ thu. "
            "Chỉ tên ngành CNTT chưa đủ để chọn một mức tiền.")
