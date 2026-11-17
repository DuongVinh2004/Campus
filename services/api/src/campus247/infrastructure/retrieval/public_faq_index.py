"""Natural-language FAQ aliases select original documents, never invented evidence."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re
import unicodedata


def words(text: str) -> list[str]:
    text = unicodedata.normalize("NFD", text.casefold()).replace("đ", "d")
    return re.findall(r"[a-z0-9]+", "".join(c for c in text if unicodedata.category(c) != "Mn"))


STOP = frozenset("toi minh em ban cho hoi la thi va cua co duoc khong nhu the nao muon can xin ve bao nhieu vay a oi mot nhung cac hay gi khi da de trong voi tren tu it nhat den se phai neu theo o dau lam sao".split())


def terms(text: str) -> list[str]:
    cleaned = " ".join(words(text))
    # Remove generic question phrases before tokenizing. Removing the single
    # syllable 'thu' would also erase 'thư' in 'thư viện' and 'thứ' in year levels.
    for phrase in ("thu tuc", "quy che", "dieu kien", "huong dan", "tra cuu"):
        cleaned = re.sub(r"\b" + phrase + r"\b", " ", cleaned)
    tokens = cleaned.split()
    return [w for w in tokens if w not in STOP] + [a + "_" + b for a, b in zip(tokens, tokens[1:])
        if a not in STOP and b not in STOP]


class PublicFaqIndex:
    def __init__(self, directory: Path, source_directory: Path):
        document = json.loads((directory / "faq.json").read_text(encoding="utf-8"))
        evidence = json.loads((directory / "evidence.json").read_text(encoding="utf-8"))
        self.entries = document["faqs"]
        if document["entry_count"] != len(self.entries):
            raise ValueError("FAQ count mismatch")
        cache = {}
        for item in evidence.values():
            path = (directory / item["source_manifest"]).resolve()
            if not path.is_relative_to(source_directory.resolve()):
                raise ValueError("FAQ source outside public corpus")
            if path not in cache:
                raw = path.read_bytes()
                cache[path] = hashlib.sha256(raw).hexdigest(), json.loads(raw)
            digest, manifest = cache[path]
            if digest != item["manifest_sha256"] or manifest.get("public_only") is not True:
                raise ValueError("FAQ manifest changed")
            original = next((c for c in manifest["chunks"] if c["url"] == item["url"]
                             and c.get("page") == item["pdf_page"]), None)
            if original is None or hashlib.sha256(original["text"].encode()).hexdigest() != item["source_text_sha256"]:
                raise ValueError("FAQ source binding changed")
        self.exact = {}
        for entry in self.entries:
            key = " ".join(words(entry["question"]))
            if key in self.exact or entry["scope"] != "public_general_information":
                raise ValueError("Duplicate or nonpublic FAQ")
            self.exact[key] = entry
            for binding in entry["sources"]:
                original = evidence[binding["evidence_ref"]]
                if any(binding[k] != original[k] for k in ("url", "pdf_page", "source_text_sha256")):
                    raise ValueError("FAQ evidence mismatch")
        # Question aliases are enough for ranking; authored answers are not sent
        # to the model or returned as authoritative document excerpts.
        self.counts = [Counter(terms(e["question"])) for e in self.entries]
        self.df = Counter(t for counts in self.counts for t in counts)

    def source_matches(self, query: str) -> list[tuple[dict, float]]:
        exact = self.exact.get(" ".join(words(query)))
        if exact:
            return [(source, 100.0) for source in exact["sources"]]
        query_terms = set(terms(query))
        query_words = " ".join(words(query))
        anchors = [phrase for phrase in ("bang diem", "hoc bong", "chuyen nganh", "hoan thi",
            "phuc khao", "tu hoc", "the sinh vien", "ky tuc xa", "song bang", "ngoai ngu",
            "hoc phi", "hoc lai", "diem ren luyen") if phrase in query_words]
        if len(query_terms) < 2:
            return []
        scores = []
        for entry, counts in zip(self.entries, self.counts):
            if anchors and not any(phrase in " ".join(words(entry["question"])) for phrase in anchors):
                continue
            if "bang diem" in anchors and any(phrase in query_words for phrase in ("xin", "cap", "thu tuc", "online")):
                candidate = " ".join(words(entry["question"]))
                if not any(phrase in candidate for phrase in ("xin", "cap", "nhan", "mot cua", "nop", "dich")):
                    continue
            matched = query_terms.intersection(counts)
            if len(matched) < 2 or len(matched) / len(query_terms) < .45:
                continue
            score = sum(math.log(1 + (len(self.entries) + 1) / self.df[t]) * (2 if "_" in t else 1)
                        for t in matched)
            scores.append((score, entry))
        scores.sort(key=lambda pair: pair[0], reverse=True)
        if not scores:
            return []
        result = []
        for score, entry in scores[:3]:
            if score < scores[0][0] * .8:
                break
            result.extend((binding, 25.0 + score) for binding in entry["sources"])
        return result
