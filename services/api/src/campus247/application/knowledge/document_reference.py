"""Prefer explicitly referenced documents before bounded retrieval, never facts."""
import re

from campus247.application.conversation.followup import normalized_question


def referenced_document_groups(question, versions):
    """Keep each explicit, eligible reference as a separate retrieval budget.

    This is bibliographic selection only. The caller still validates current
    grants, original hashes, applicability and relevance for every returned row.
    Missing references never acquire a synthetic version or inferred source.
    """
    numbers = set(re.findall(r"\b(?:qd|quyet dinh|quy che)(?:\s+so)?\s*(\d{1,5})\b", normalized_question(question)))
    if len(numbers) < 2:
        return None
    groups = []
    for number in sorted(numbers):
        matching = [v["version_id"] for v in versions if re.search(r"\b"+number+r"\b", normalized_question(v["title"]))]
        if not matching:
            return None
        groups.append(matching)
    return groups


def focused_multi_document_question(question):
    """After references resolve, search the question body without their titles.

    Only a pure reference preamble is removed. Full user scope remains on the
    caller's authorization/applicability checks and downstream answer request.
    """
    match = re.search(r"(?is)\bTheo\s+([^,;:\n]+)[,;:]\s*(.+)$", question)
    if not match:
        return question
    preamble = normalized_question(match[1])
    references = re.findall(r"\b(?:qd|quyet dinh|quy che)(?:\s+so)?\s*\d{1,5}\b", preamble)
    remainder = preamble
    for reference in references:
        remainder = remainder.replace(reference, " ")
    if len(references) < 2 or set(remainder.split()) - {"va", "voi", "cung", "doi", "chieu"}:
        return question
    return match[2].strip()


def preferred_document_versions(question, versions):
    text = normalized_question(question)
    decisions = set(re.findall(r"\b(?:qd|quyet dinh|quy che)(?:\s+so)?\s*(\d{1,5})\b", text))
    if len(decisions) > 1:
        # A preference must retain every explicitly requested document. Missing
        # references leave the eligible set open for retrieval/clarification.
        selected = []
        for number in sorted(decisions):
            matching = [v["version_id"] for v in versions if re.search(r"\b" + number + r"\b", normalized_question(v["title"]))]
            if not matching:
                return None
            selected.extend(matching)
        return list(dict.fromkeys(selected))
    if len(decisions) == 1:
        number = next(iter(decisions))
        matching = [v["version_id"] for v in versions if re.search(r"\b" + number + r"\b", normalized_question(v["title"]))]
        if matching: return matching
    if "hoc bong stem quy chau a" in text:
        matching = [v["version_id"] for v in versions if "hoc bong stem quy chau a" in normalized_question(v["title"])]
        if matching: return matching
    exemption = any(term in text for term in ("mien", "giam", "ho tro", "ho so", "han nop"))
    if "mien giam hoc phi" in text and "han nop" in text:
        matching = [v["version_id"] for v in versions if "mien giam hoc phi" in normalized_question(v["title"])]
        if matching: return matching
    if "hoc phi" in text and not exemption:
        matching = [v["version_id"] for v in versions if "hoc phi" in normalized_question(v["title"])
            and not any(term in normalized_question(v["title"]) for term in ("mien", "giam", "ho tro", "ho so"))]
        if matching: return matching
    if any(term in text for term in ("phong may", "phong thuc hanh may tinh")):
        matching = [v["version_id"] for v in versions if "noi quy" in normalized_question(v["title"])
            and any(term in normalized_question(v["title"]) for term in ("phong may", "phong thuc hanh may tinh"))]
        if matching: return matching
    return None


def focused_named_document_question(question):
    """Call only after an eligible named document has narrowed the search."""
    prefix, separator, rest = question.partition(",")
    if (separator and rest.strip() and normalized_question(prefix).startswith("theo ")
            and "hoc bong stem quy chau a" in normalized_question(prefix)
            and re.search(r"\bmau\b|\bso yeu ly lich\b", normalized_question(prefix))):
        body = re.sub(r"(?i)\b(ý|và|mục|câu)(?=\d)", r"\1 ", rest.strip())
        return body
    return question


def named_form_rerank_question(question):
    """Keep the named form context for ranking after focused candidate search."""
    if focused_named_document_question(question) == question:
        return None
    return re.sub(r"(?i)\b(ý|và|mục|câu)(?=\d)", r"\1 ", question)


def named_notice_rerank_question(question):
    """Retain the full explicitly named notice query for sealed section context."""
    text = normalized_question(question)
    year = re.search(r"\b20\d{2}\s*[-–/]\s*20\d{2}\b", question)
    if (year and "thong bao hoc bong stem quy chau a" in text
            and question[year.end():].strip(" ,:;?\n\t")):
        return question
    return None


def verified_form_rerank_text(title, section, text, verified_sections):
    """Ranking context is reviewed metadata; quoted evidence stays unchanged."""
    from campus247.application.knowledge.platform_models import PlatformError
    if not isinstance(section, str) or not section or section not in verified_sections:
        raise PlatformError(409, "SOURCE_LOCATOR_MISMATCH", "Mục biểu mẫu không khớp bản nguồn đã duyệt.")
    return title + "\n" + section + "\n" + text


def verified_edge_rerank_text(title, section, text, geometry, verified_sections):
    """Use the sealed relationship locator only for a reconstructed edge parent."""
    if not geometry or geometry.get("evidence_kind") != "edge":
        return text
    return verified_form_rerank_text(title, section, text, verified_sections)


def focused_lab_permission_question(question):
    """Normalize device/permission synonyms for retrieval; keep the user goal elsewhere."""
    text = normalized_question(question)
    if ("usb" in text and any(term in text for term in ("xin phep", "cho phep", "dong y"))
            and any(term in text for term in ("phong may", "phong thuc hanh may tinh"))):
        return question + "\nGắn thiết bị nhớ ngoài (USB); sự đồng ý."
    return question
