"""Local contact views, using the same recognizer as the existing egress gate."""
from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable

from campus247.domain.contact_values import contact_matches
from campus247.rag_v2.types import Unit

MARKER = re.compile(r"PUBLIC_CONTACT_[A-Z]+_[A-Z0-9]+")


def contact_map(units: Iterable[Unit]) -> dict[str, str]:
    # Content-derived labels retain their identity when a subset is cited.
    values = {pair for unit in units for pair in contact_matches(unit.text)}
    return {
        "PUBLIC_CONTACT_" + kind + "_" + hashlib.sha256(
            (kind + "\0" + value).encode()).hexdigest()[:16].upper(): value
        for kind, value in sorted(values)
    }


def redact(text: str, markers: dict[str, str]) -> str:
    for marker, value in sorted(markers.items(), key=lambda pair: -len(pair[1])):
        text = re.sub(r"(?<!\w)" + re.escape(value) + r"(?!\w)", marker, text)
    return text


def restore(text: str, units: Iterable[Unit]) -> str | None:
    markers = contact_map(units)
    if any(match.group() not in markers for match in MARKER.finditer(text)):
        return None
    return MARKER.sub(lambda match: markers[match.group()], text)
