"""Focus narrow permission questions on an exact numbered source clause."""
import re
import unicodedata

from campus247.application.retrieval.citations import CitationBundle


def words(text: str) -> list[str]:
    value = "".join(c for c in unicodedata.normalize("NFD", text.casefold())
                    if unicodedata.category(c) != "Mn").replace("đ", "d")
    return re.findall(r"[a-z0-9]+", value)


def narrow_clause(content: str, query: str) -> str:
    tokens = words(query)
    question = " ".join(tokens)
    if "co duoc" not in question or "khong" not in tokens:
        return content
    # Keep contiguous phrases; do not create artificial phrases by removing
    # stop words. Distinctive action phrases select a clause over broad rules.
    stop = {"co", "duoc", "khong", "toi", "em", "minh", "ban", "voi", "trong", "va", "hay", "la",
            "ky", "tuc", "xa", "thu", "vien", "sinh", "truong"}
    phrases = {(a, b) for a, b in zip(tokens, tokens[1:]) if a not in stop and b not in stop}
    boundaries = list(re.finditer(r"(?m)^\s*\d+\.\s+", content))
    if len(boundaries) < 3 or len(phrases) < 2:
        return content
    ranked = []
    for index, boundary in enumerate(boundaries):
        end = boundaries[index + 1].start() if index + 1 < len(boundaries) else len(content)
        excerpt = content[boundary.start():end].strip()
        source_words = words(excerpt)
        matches = phrases.intersection(zip(source_words, source_words[1:]))
        ranked.append((len(matches), excerpt))
    ranked.sort(key=lambda value: value[0], reverse=True)
    if ranked[0][0] >= 2 and ranked[0][0] > 2 * ranked[1][0]:
        return ranked[0][1]
    return content


def question_focused_context(bundle: CitationBundle, query: str) -> str:
    if not isinstance(bundle, CitationBundle):
        # Retain the prompt-only internal protocol. The actual graph always
        # builds a typed CitationBundle and verifies every final citation.
        return bundle.to_prompt_context()
    blocks = []
    for citation_id, source in sorted(bundle.citations.items()):
        section = f" ({source.section_path})" if source.section_path else ""
        # Only the model's view is narrowed. The evidence gate, immutable
        # citation identity, source readback and checksum keep the full source.
        excerpt = narrow_clause(source.content_text, query)
        applicability = getattr(source, "applicability_note", None)
        note = f"\nPhạm vi bản nguồn (metadata): {applicability}" if applicability else ""
        blocks.append(f"[{citation_id}] Nguồn: {source.title}{section}{note}\nNội dung: {excerpt}")
    return "\n\n".join(blocks)
