"""Minimize contact values from the one pinned public notice in model views.

The original source, citation hashes and returned quotations remain local and
unchanged. This does not authorize a payload or sanitize user input/secrets.
The existing outbound policy still validates every model request.
"""
import re

from campus247.application.conversation.followup import normalized_question
from campus247.application.retrieval.citations import CitationBundle

PUBLIC_NOTICE_ORIGINAL = "91c13da397638af2bd3d39177b2c68387bb6bd90ee234331724b982a6cb0ee4e"
_EMAIL_FIELD = re.compile(r"\bEmail:\s*([\w.+-]+@[\w.-]+\.[A-Za-z]{2,})\b", re.I)
_PHONE_FIELD = re.compile(r"\b(?:Số điện thoại|Điện thoại):\s*(0\d{9,10})\b", re.I)


def is_pinned_public_notice(record):
    publication = record.publication
    return (not record.simulation_label and publication is not None
        and publication.original_sha256 == PUBLIC_NOTICE_ORIGINAL and publication.binds(record)
        and "hoc bong stem quy chau a" in normalized_question(record.title))


def public_notice_contact_redactor(bundle):
    values = set()
    if isinstance(bundle, CitationBundle):
        for record in bundle.citations.values():
            if is_pinned_public_notice(record):
                values.update(("EMAIL", m[1]) for m in _EMAIL_FIELD.finditer(record.content_text))
                values.update(("PHONE", m[1]) for m in _PHONE_FIELD.finditer(record.content_text))
    replacements = [(re.compile(r"(?<!\w)" + re.escape(value) + r"(?!\w)"),
        f"PUBLIC_CONTACT_{kind}_{chr(65 + index)}") for index, (kind, value) in enumerate(sorted(values))]

    def redact(text):
        for pattern, marker in replacements:
            text = pattern.sub(marker, text)
        return text

    return redact


# Department and unit mailboxes published in HUCE's official notices. They are shared role addresses, not personal
# data, so an answer that quotes them may be shown and kept in history. Staff mailboxes (name + initials) are not
# listed and stay protected. Only the history policy uses this; the outbound model policy is unchanged.
_UNIT_MAILBOXES = (
    "dhxaydung", "daotao", "ktqh", "xaydung", "congtrinhthuy", "khcn", "ktdb", "dtqt", "tuyensinhhcm",
    "tuyensinhdhcq", "tuyensinhdh_ltcq", "tuyensinhdh_vlvh", "tuyensinhsdh", "cokhi", "thuvien", "doanthanhnien",
    "vatlieu", "ttcntt", "ktx", "fit", "pfiev", "moitruong", "tv", "yt", "congtrinhbien", "ctsv")
UNIT_MAILBOX = re.compile(r"(?<![\w.+-])(?:" + "|".join(map(re.escape, _UNIT_MAILBOXES)) + r")@huce\.edu\.vn(?![\w-])", re.I)
