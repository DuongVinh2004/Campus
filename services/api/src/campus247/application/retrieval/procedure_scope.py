"""Keep claims bound to named procedures when the user compares them."""
import re

from campus247.application.retrieval.material_support import normalized, support_issues


def sections(content):
    headings = list(re.finditer(r"(?mi)^\s*[0-9]+\.\s*Quy trình\s+([^\n]+)", content))
    result = {}
    for index, heading in enumerate(headings):
        name = re.sub(r"^(?:xin|cấp|đăng ký)\s+", "", heading[1].strip(), flags=re.I)
        anchor = normalized(name)
        if len(anchor.split()) < 3:
            continue
        end = headings[index+1].start() if index+1 < len(headings) else len(content)
        result[anchor] = content[heading.start():end]
    return result


def requested_procedure_names(question, bundle):
    """Original source headings help generation retain each procedure's name."""
    request = normalized(question)
    names = set()
    for record in bundle.citations.values():
        for heading in re.finditer(r"(?mi)^\s*[0-9]+\.\s*(Quy trình\s+([^\n]+))", record.content_text):
            anchor = normalized(re.sub(r"^(?:xin|cấp|đăng ký)\s+", "", heading[2].strip(), flags=re.I))
            if len(anchor.split()) >= 3 and anchor in request:
                names.add(heading[1].strip())
    return sorted(names)


def procedure_scope_issues(question, draft, bundle, threshold):
    source_sections = {ref: sections(record.content_text) for ref, record in bundle.citations.items()}
    request = normalized(question)
    requested = {name for values in source_sections.values() for name in values if name in request}
    if len(requested) < 2:
        return {}
    issues = {}
    for claim in draft.claims:
        body = normalized(claim.text)
        named = {name for name in requested if name in body}
        if not named:
            issues[claim.claim_id] = "MISSING_PROCEDURE_SCOPE"
            continue
        if len(named) != 1:
            continue  # Cross-procedure relations still require semantic checks.
        target = next(iter(named))
        relevant = [source_sections.get(ref, {}).get(target, "") for ref in claim.citation_ids]
        text = " ".join(part for part in relevant if part)
        tokens = {word.lower() for word in re.findall(r"\w+", claim.text) if len(word) > 2}
        overlap = sum(word in text.lower() for word in tokens)/max(1, len(tokens))
        if not text or support_issues(claim.text, text) or overlap < threshold:
            issues[claim.claim_id] = "MISBOUND_PROCEDURE_SCOPE"
    return issues
