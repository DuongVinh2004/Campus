"""Scope vocabulary read from the documents themselves.

A question names the scope it is about ("ngành Trí tuệ nhân tạo", "K69", "chương trình tiên tiến"). Which names are real majors or programmes
is a property of the documents that were added, not of this code, so the names are collected from the units when an index is loaded and
every document added later brings its own. Nothing here is specific to one document: a major is a phrase that follows "ngành" in some text,
or a cell in a table column whose header says "ngành". Initialisms ("cntt") are derived from the names, never listed.

The vocabulary answers one question for the answering service: which named scopes does this question mention, so that it can check
whether the sources it found actually carry that scope.
"""
from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field

from campus247.rag_v2.ingest.tables import cells as table_cells
from campus247.rag_v2.ingest.units import context_text, source_text
from campus247.rag_v2.understanding.normalize import fold

_WORD = r"[A-Za-zÀ-ỹĐđ][A-Za-zÀ-ỹĐđ0-9-]*"
# Words that end a name ("ngành Trí tuệ nhân tạo có mức ..."). Compared folded, so one list serves text with or without diacritics.
_STOP_WORDS = ("va", "cua", "la", "duoc", "tai", "trong", "theo", "se", "phai", "bi", "khong", "voi", "cho", "neu", "moi", "cac",
               "nhung", "nay", "den", "nao", "muc", "nam", "khoa", "hoac", "gom", "truoc", "bao", "nhieu", "gi", "he", "chuong",
               "trinh", "sinh", "vien", "hoc", "thuc", "hanh")
_STOP = "|".join(_STOP_WORDS)
# In a document the diacritics tell a function word from a syllable of a name ("có" from "cơ", "do" from "đô", "thì" from "thị").
_STOP_ACCENTED = frozenset("""và của là có thì được đã để tại trong đối theo sẽ phải bị cần không khi do với cho nếu mỗi các những này đó từ
đến nào mức năm khóa hệ hoặc gồm bằng sau trước ở ra vào như hay về nên nhưng mà cũng chỉ vẫn đang rất lên xuống dành áp nộp đóng bao
mấy gì học thực hành sinh viên chương trình""".split())
# In a document: the first word after "ngành" is capitalised, which marks where the name starts.
_AFTER_MARKER = re.compile(rf"(?i:chuyên\s+ngành|ngành)\s+([A-ZÀ-ỸĐ][A-Za-zÀ-ỹĐđ0-9-]*(?:\s+{_WORD}){{0,8}})")
# In a question (folded: lower case, no diacritics): the name ends at a stop word, a cohort or a digit. "trình" is a stop word
# ("chương trình") except inside "công trình": "ngành công trình thủy" must not be cut down to "công".
_QUESTION_AFTER_MARKER = re.compile(
    rf"(?:chuyen\s+nganh|nganh)\s+((?!(?:{_STOP})\b)[a-z][a-z-]*"
    rf"(?:\s+(?:(?<=cong\s)trinh\b|(?!(?:{_STOP})\b)(?!k\d{{2,3}}\b)[a-z][a-z-]*)){{0,5}})")
_GENERIC = frozenset(fold(w) for w in ("học", "đào tạo", "học phí", "nào", "gì", "này", "đó", "chính quy", "khác", "mình", "em", "tôi"))


def _clean(name: str) -> str:
    return " ".join(name.split()).strip(" -|:;,.()")


def _trim(name: str) -> str:
    """Cut a captured name at its first word that cannot belong to a name."""
    kept = []
    words = name.split()
    for position, word in enumerate(words):
        if position and word.casefold() in _STOP_ACCENTED:
            # "Kinh tế và Quản lý đô thị": a capitalised word after "và" continues one compound name.
            following = words[position + 1] if position + 1 < len(words) else ""
            if not (word.casefold() == "và" and following[:1].isupper()):
                break
        kept.append(word)
    return " ".join(kept)


def _usable(name: str, minimum: int = 3) -> bool:
    """A name to remember from the documents: three words or more, so single concepts ("kỹ thuật", "học kỳ") are not taken for majors."""
    words = name.split()
    folded = fold(name)
    return (minimum <= len(words) <= 9 and len(name) <= 80 and not re.search(r"\d", name) and folded not in _GENERIC
            and not folded.startswith(("dao tao ", "chuyen nganh ", "nganh ")) and not folded.endswith(" chuyen nganh"))


def initialism(name: str) -> str:
    words = fold(name).split()
    return "".join(w[0] for w in words) if len(words) >= 3 else ""


@dataclass(frozen=True)
class Vocabulary:
    """Major names found in the documents (folded, no diacritics) and the aliases derived from them."""
    majors: frozenset[str] = frozenset()
    aliases: dict[str, str] = field(default_factory=dict)   # alias -> folded major name

    @classmethod
    def from_units(cls, units: Iterable) -> Vocabulary:
        counts: Counter[str] = Counter()
        titles: set[str] = set()
        for unit in units:
            body, context = source_text(unit), context_text(unit)
            title = getattr(unit, "doc_title", "") or ""
            if title and title not in titles:
                # A document title names its major ("... — Chuyên ngành Kinh tế và Quản lý đô thị (K71QD)"), once per document.
                titles.add(title)
                for match in _AFTER_MARKER.finditer(title):
                    name = _trim(_clean(match.group(1)))
                    if _usable(name):
                        counts[fold(name)] += 1
            for match in _AFTER_MARKER.finditer(body):
                name = _trim(_clean(match.group(1)))
                if _usable(name):
                    counts[fold(name)] += 1
            # A table column headed "Ngành" lists majors, one per row.
            header = next((line for line in context.splitlines() if "|" in line), "")
            columns = [i for i, cell in enumerate(table_cells(header)) if re.search(r"\bngành\b", cell, re.IGNORECASE)
                       and not re.search(r"chương trình", cell, re.IGNORECASE)]
            if columns and "|" in body:
                for line in body.splitlines():
                    values = table_cells(line)
                    for i in columns:
                        if i < len(values) and _usable(_clean(values[i])):
                            counts[fold(_clean(values[i]))] += 1
        majors = frozenset(counts)
        # Initialisms of a name and of each part of a compound name ("Kinh tế và Quản lý đô thị": "qldt"), kept only when one
        # major has it: an ambiguous initialism is left to the question's other words.
        candidates: dict[str, set[str]] = {}
        for name in majors:
            for part in [name, *name.split(" va ")]:
                alias = initialism(part)
                if alias:
                    candidates.setdefault(alias, set()).add(name)
        aliases = {alias: next(iter(names)) for alias, names in candidates.items() if len(names) == 1}
        return cls(majors, aliases)

    def expand(self, question: str) -> str:
        """The full names of the initialisms a question uses ("QLĐT" -> "kinh te va quan ly do thi"), for the search query."""
        text = fold(question)
        names = [name for alias, name in self.aliases.items() if re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", text)]
        return " ".join(dict.fromkeys(names))

    def terms_in(self, question: str) -> tuple[str, ...]:
        """Scope names a question mentions: known majors, their initialisms, and any phrase after "ngành" (known or not)."""
        text = fold(question)
        found: dict[str, None] = {}
        for name in sorted(self.majors, key=len, reverse=True):
            if re.search(rf"(?<!\w){re.escape(name)}(?!\w)", text):
                found[name] = None
        for alias, name in self.aliases.items():
            if re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", text):
                found[name] = None
        for match in _QUESTION_AFTER_MARKER.finditer(text):
            name = _clean(match.group(1))
            # Named outright after "ngành", so even a one-word major counts here.
            if _usable(name, minimum=1) and not any(name in known or known in name for known in found):
                found[name] = None
        return tuple(found)


EMPTY = Vocabulary()
