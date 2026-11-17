"""Narrow disciplinary-rule exception over the verified v2 outcome, never raw drafts."""
from __future__ import annotations

import re
import unicodedata
from hashlib import sha256

from campus247.application.retrieval.citations import CitationBundle
from campus247.domain.publication import official_huce_uri
from campus247.rag_v2.types import Outcome

_CONNECTIVES = frozenset({
    "and", "cac", "cho", "cua", "duoc", "khi", "mot", "neu", "nhung", "theo", "thi", "trong", "voi",
    "bao", "bi", "co", "la", "de", "tai", "nay", "do"})


def _fold(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text.casefold())
                   if unicodedata.category(c) != "Mn").replace("đ", "d")


def _squash(text: str) -> str:
    """Folded text without spaces: tolerant of case, diacritics and OCR gaps ("kỷ luậ t")."""
    return re.sub(r"\s+", "", _fold(text))


def _meaningful_words(sentence: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]+", _fold(sentence))
            if w not in _CONNECTIVES and (len(w) >= 3 or w.isdigit())]


def _named_subject(sentence, titles):
    """An individual cannot become a generic rule by adding a conditional adjunct."""
    runs, run = [], []
    previous_end = 0
    for match in re.finditer(r"\b[^\W\d_]+\b", sentence):
        word = match.group()
        if run and not sentence[previous_end:match.start()].isspace():
            if len(run) >= 2:
                runs.append(" ".join(run))
            run = []
        if word[0].isupper():
            run.append(word)
        else:
            if len(run) >= 2:
                runs.append(" ".join(run))
            run = []
        previous_end = match.end()
    if len(run) >= 2:
        runs.append(" ".join(run))
    if any(name not in titles for name in runs):
        return True
    # Also recognize a one-word personal subject after the generic role.
    subject = re.search(r"\b(?:sinh viên|bạn)\s+(\w+)\b", sentence, re.I)
    return bool(subject and (subject[1][0].isupper() or any(c.isdigit() for c in subject[1])))


def discipline_failure(outcome: Outcome, rows) -> str | None:
    """Why the exception does not apply, as a content-free code; None when it applies.

    Outcome.statements contains only accepted v2 statements (deterministic and semantic
    verification on the generation path). Each meaningful word of a sentence that mentions
    discipline must also occur in every cited source row, so a paraphrase cannot add a level,
    number or consequence the source lacks. Sentences aimed at a person, or asserting that someone
    was or will be disciplined without a condition, stay blocked. CitationBundle preserves v1's
    typed publication binding and simulation test.
    """
    if outcome.kind not in {"answer", "partial"}:
        return "kind"
    affected = [s for s in outcome.statements if re.search(r"kỷ luật", s.text, re.I)]
    if not affected:
        return "no_statement"
    for statement in affected:
        if not statement.unit_ids:
            return "no_unit"
        discipline_sentences = []
        titles = "\n".join(str(rows.get(chunk, {}).get("title") or "")
                           for c in outcome.citations if c.unit_id in statement.unit_ids for chunk in c.chunk_ids)
        # Check each sentence: a generic first sentence cannot license a later
        # personal accusation, even when both were quoted from a source.
        for sentence in re.split(r"(?<=[.!?;])\s+|\n+", statement.text):
            if not re.search(r"kỷ luật", sentence, re.I):
                continue
            discipline_sentences.append(sentence)
            if _named_subject(sentence, titles):
                return "named_subject"
            text = " ".join(sentence.casefold().split())
            if re.search(r"\b(?:bạn|em|tôi|mình|anh|chị|ông|bà|mssv|mã sinh viên|tên|"
                         r"sinh viên này|sinh viên đó|sv\d+)\b", text):
                return "personal"
            accusation = (re.search(r"sinh viên (?:đã |sẽ |phải )?bị kỷ luật", text)
                          or re.search(r"\b(?:đã|sẽ|phải) (?:bị|chịu)(?: xử lý)? kỷ luật", text))
            if accusation and not re.search(r"\b(?:nếu|khi|trường hợp)\b", text):
                return "accusation"
        sources = []
        for ref in statement.unit_ids:
            citations = [c for c in outcome.citations if c.unit_id == ref]
            if len(citations) != 1:
                return "citation_count"
            citation = citations[0]
            if not citation.chunk_ids or not citation.quote:
                return "citation_empty"
            for chunk in citation.chunk_ids:
                row = rows.get(chunk)
                if row is None:
                    return "row_missing"
                if (row.get("chunk_id") != chunk or row.get("source_id") != citation.document_id
                        or row.get("document_version_id") != citation.version_id):
                    return "row_binding"
                if citation.quote not in row.get("content_text", ""):
                    return "quote_not_in_row"
                if sha256(row["content_text"].encode()).hexdigest() != row.get("evidence_sha256"):
                    return "evidence_hash"
                record = CitationBundle.build([row]).resolve("CIT-001")
                if record.simulation_label:
                    return "simulation"
                if not (official_huce_uri(record.canonical_uri)
                        or record.publication is not None and record.publication.binds(record)):
                    from urllib.parse import urlparse
                    return f"source_not_official host={urlparse(record.canonical_uri).hostname} publication={record.publication is not None}"
                sources.append(row["content_text"])
        # A statement may combine several cited sources: its words must be found across all of them.
        source = _squash(" ".join(sources))
        numbers = set(re.findall(r"\d+", " ".join(sources)))
        if not all((word in numbers) if word.isdigit() else (word in source)
                   for sentence in discipline_sentences for word in _meaningful_words(sentence)):
            return "word_not_in_source"
    return None


def verified_general_discipline_rule(outcome: Outcome, rows) -> bool:
    return discipline_failure(outcome, rows) is None
