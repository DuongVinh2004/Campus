"""Single definition of contact-like values that must stay on this machine.

Used by the outbound policy (to deny) and by the evidence view builder (to
replace values with neutral markers before a model sees them).
"""
import re

EMAIL_PATTERN = re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b")
PHONE_PATTERN = re.compile(r"(?<!\w)(?:\+?[1-9]\d{9,14}|0\d{9,10})(?!\w)")
IP_PATTERN = re.compile(r"(?<!\w)(?:\d{1,3}\.){3}\d{1,3}(?!\w)")
STUDENT_ID_PATTERN = re.compile(r"\b(?:SV|MSV|STU)[-_]?\d{4,}\b", re.IGNORECASE)

_TEST_EMAIL_SUFFIXES = (".example", ".invalid", ".test")


def contact_matches(text: str):
    """Yield (kind, value) for every contact-like value the outbound policy would deny."""
    for match in EMAIL_PATTERN.finditer(text):
        if not match.group(0).rsplit("@", 1)[-1].lower().endswith(_TEST_EMAIL_SUFFIXES):
            yield "EMAIL", match.group(0)
    for kind, pattern in (("PHONE", PHONE_PATTERN), ("NUMBER", IP_PATTERN), ("ID", STUDENT_ID_PATTERN)):
        for match in pattern.finditer(text):
            yield kind, match.group(0)
