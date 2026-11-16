"""Exact compound document references constrain relevance, never authorization."""
import re

from campus247.domain.retrieval import RetrievalCandidate, RetrievalQuery


def requested_identifiers(query: RetrievalQuery) -> tuple[str, ...]:
    # Compound alphanumeric document references; ordinary words and quantities
    # do not create an exact-document restriction.
    inferred = re.findall(r"\b[A-Z]{2,}[A-Z0-9]*(?:[-/][A-Z0-9]{2,})+\b", query.text.upper())
    return tuple(dict.fromkeys(value.upper() for value in (*query.exact_identifiers, *inferred)))


def matches_requested_document(candidate: RetrievalCandidate, identifiers: tuple[str, ...]) -> bool:
    metadata = "\n".join((candidate.document_number or "", candidate.title,
                           "\n".join(candidate.section_path))).upper()
    return any(re.search(r"(?<![A-Z0-9])" + re.escape(value) + r"(?![A-Z0-9])", metadata)
               for value in identifiers)
