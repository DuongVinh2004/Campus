"""Keep contact-like source values out of model views and out of final answers.

Source text, citation hashes and quotations stay local and unchanged. Only the
text sent to a model is rewritten. The model never sees or produces a value, so
the answer points to the original document instead of repeating it. The outbound
policy still validates every request; user input is never rewritten here.
"""
import re

from campus247.application.retrieval.citations import CitationBundle
from campus247.domain.contact_values import contact_matches

MARKER = re.compile(r"PUBLIC_CONTACT_[A-Z]+_[A-Z0-9]+")
MARKER_REPLACEMENT = "(xem thông tin liên hệ trong tài liệu gốc)"


def evidence_contact_redactor(bundle):
    values = set()
    if isinstance(bundle, CitationBundle):
        for record in bundle.citations.values():
            values.update(contact_matches(record.content_text))
    # Longest first so a value is never partly replaced by one it contains.
    ordered = sorted(values)
    markers = {(kind, value): f"PUBLIC_CONTACT_{kind}_{chr(65 + index) if index < 26 else index}"
               for index, (kind, value) in enumerate(ordered)}
    replacements = [(re.compile(r"(?<!\w)" + re.escape(value) + r"(?!\w)"), markers[(kind, value)])
                    for kind, value in sorted(ordered, key=lambda item: -len(item[1]))]

    def redact(text):
        for pattern, marker in replacements:
            text = pattern.sub(marker, text)
        return text

    return redact


def present_without_contact_markers(text):
    return MARKER.sub(MARKER_REPLACEMENT, text)
