"""Small BM25 index with accented/folded word and adjacent-word features."""
from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter, defaultdict
from collections.abc import Iterable
from itertools import pairwise

from campus247.rag_v2.understanding.normalize import fold


def features(text: str) -> list[str]:
    words = re.findall(r"\w+", unicodedata.normalize("NFC", text.lower()))
    result = []
    for prefix, tokens in (("a", words), ("f", [fold(w) for w in words])):
        result.extend(prefix + ":" + word for word in tokens)
        result.extend(prefix + ":" + a + " " + b for a, b in pairwise(tokens))
    return result


class BM25:
    def __init__(self, documents: Iterable[tuple[str, str]], *, k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.lengths: dict[str, int] = {}
        self.postings: dict[str, dict[str, int]] = defaultdict(dict)
        for uid, text in documents:
            if uid in self.lengths:
                raise ValueError("duplicate unit id")
            terms = Counter(features(text))
            self.lengths[uid] = sum(terms.values())
            for term, count in terms.items():
                self.postings[term][uid] = count
        self.average_length = sum(self.lengths.values()) / max(1, len(self.lengths)) or 1

    def search(self, query: str, limit: int, *, allowed: set[str] | None = None) -> list[tuple[str, float]]:
        if limit <= 0:
            return []
        scores: dict[str, float] = defaultdict(float)
        n = len(self.lengths)
        # Sorted terms fix the float summation order, so ranking does not depend on PYTHONHASHSEED.
        for term in sorted(set(features(query))):
            posting = self.postings.get(term, {})
            idf = math.log(1 + (n - len(posting) + 0.5) / (len(posting) + 0.5))
            for uid, tf in posting.items():
                if allowed is not None and uid not in allowed:
                    continue
                denominator = tf + self.k1 * (1 - self.b + self.b * self.lengths[uid] / self.average_length)
                scores[uid] += idf * tf * (self.k1 + 1) / denominator
        # Scores equal up to float noise tie-break by unit id.
        return sorted(((uid, round(score, 9)) for uid, score in scores.items()),
                      key=lambda item: (-item[1], item[0]))[:limit]

    def anchored(self, query: str, limit: int, *, allowed: set[str] | None = None,
                 max_document_frequency: int = 200) -> list[tuple[str, float]]:
        """BM25 inside the units that contain the query's rare identifiers.

        A cohort/programme code ("K71QD") or a six-digit course code names a small set of
        units exactly; ordinary BM25 lets common words in other documents outrank them.
        Units holding every identifier are searched first, otherwise any identifier.
        """
        anchors = []
        for word in set(re.findall(r"\w+", unicodedata.normalize("NFC", query.lower()))):
            mixed = re.search(r"\d", word) and re.search(r"[^\W\d_]", word)
            if mixed or re.fullmatch(r"\d{6}", word):
                posting = self.postings.get("a:" + word)
                # Discriminating power is judged inside the authorized set, so the branch does not
                # switch off when unrelated (unauthorized or other-scope) units repeat the code.
                units = set(posting) & allowed if posting and allowed is not None else set(posting or ())
                if units and len(units) <= max_document_frequency:
                    anchors.append(units)
        if not anchors:
            return []
        units = set.intersection(*anchors) or set.union(*anchors)
        if allowed is not None:
            units &= allowed
        return self.search(query, limit, allowed=units) if units else []
