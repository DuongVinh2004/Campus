"""Read-only T16 data checks; no RAG code, evaluation output or reports read.

Run: python -B evals/datasets/rag-v2/newdoc/check.py
Case groups are author annotations, not inferred model judgements:
001-006 multiple requests; 007-009 table; 010-012 conditions/exceptions;
013-018 other answers; 019-021 near domain; 022-023 outside;
024-025 lack a referent. Empty absent_terms on the last two is intentional:
they abstain because the object is missing, not because a term is absent.
"""

from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys
import unicodedata


def normalize(value):
    value = unicodedata.normalize("NFD", value.casefold().replace("đ", "d"))
    return " ".join("".join(c for c in value if unicodedata.category(c) != "Mn").split())


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    base = Path(__file__).resolve().parent
    root = base.parents[3]
    corpus_path = root / "evals/corpus/served-chunks.jsonl"
    document = (base / "document.md").read_text(encoding="utf-8")
    corpus_bytes = corpus_path.read_bytes()
    corpus_rows = [json.loads(line) for line in corpus_bytes.decode("utf-8").splitlines() if line.strip()]
    # Search every decoded value, including titles and metadata, not just text.
    corpus = normalize("\n".join(json.dumps(row, ensure_ascii=False) for row in corpus_rows))
    doc_norm = normalize(document)
    errors = []

    def check(condition, message):
        if not condition:
            errors.append(message)

    raw_cases = (base / "cases.jsonl").read_text(encoding="utf-8")
    lines = raw_cases.splitlines()
    check(all(line.strip() for line in lines), "blank JSONL line")
    cases = [json.loads(line) for line in lines if line.strip()]
    check(len(cases) == 25, "expected 25 cases")
    check([c.get("case_id") for c in cases] == [f"NEWDOC-{n:03d}" for n in range(1, 26)], "case IDs/order")
    check("\\u" not in raw_cases, "JSONL must retain Unicode characters (ensure_ascii=False)")
    counts = Counter(c.get("expected") for c in cases)
    check(counts == {"answer": 18, "abstain": 7}, "answer/abstain distribution")
    variants = {"form", "no_diacritics", "keyword", "slang"}
    questions = []
    answer_variants = Counter()
    fields = {"case_id", "question", "expected", "required_facts", "quote", "variant"}
    for c in cases:
        cid = c["case_id"]
        answer = c["expected"] == "answer"
        check(set(c) == fields | (set() if answer else {"absent_terms"}), f"{cid}: schema fields")
        question = c["question"]
        check(isinstance(question, str) and bool(question.strip()), f"{cid}: empty question")
        questions.append(normalize(re.sub(r"[^\w\s]", " ", question)))
        check(c["variant"] in variants, f"{cid}: invalid variant")
        if c["variant"] == "no_diacritics":
            check(normalize(question) == question.casefold(), f"{cid}: diacritics in no_diacritics")
        facts, quote = c["required_facts"], c["quote"]
        check(isinstance(facts, list) and len(facts) <= 3, f"{cid}: facts count")
        check(isinstance(quote, str), f"{cid}: quote type")
        if answer:
            answer_variants[c["variant"]] += 1
            check(bool(facts) and bool(quote), f"{cid}: missing answer gold")
            check(quote in document, f"{cid}: quote is not verbatim")
            for fact in facts:
                check(isinstance(fact, str) and 0 < len(fact) <= 60, f"{cid}: fact length/type")
                check(fact in document and fact in quote, f"{cid}: fact not verbatim/in quote: {fact}")
        else:
            check(facts == [] and quote == "", f"{cid}: abstain gold must be empty")
            terms = c["absent_terms"]
            check(isinstance(terms, list) and len(terms) <= 5, f"{cid}: absent_terms count")
            for term in terms:
                check(isinstance(term, str) and len(term.split()) == 1, f"{cid}: absent term must be one word")
                key = normalize(term)
                check(bool(key) and key not in doc_norm and key not in corpus, f"{cid}: term present: {term}")
                check(key in normalize(question), f"{cid}: absent term not in question")
    check(len(set(questions)) == len(questions), "duplicate normalized question")
    check(all(answer_variants[v] >= 3 for v in variants), "each answer variant needs >=3 cases")

    indexed = {c["case_id"]: c for c in cases}
    groups = {
        "multi": range(1, 7), "table": range(7, 10), "condition": range(10, 13),
        "other_answer": range(13, 19), "near_domain": range(19, 22),
        "outside": range(22, 24), "ambiguous": range(24, 26),
    }
    for name, numbers in groups.items():
        for n in numbers:
            c = indexed.get(f"NEWDOC-{n:03d}", {})
            check(c.get("expected") == ("answer" if n <= 18 else "abstain"), f"group {name}: {n}")
            if name == "multi":
                check(len(c.get("required_facts", [])) >= 2, f"multi {n}: needs multiple gold facts")
            if name == "table":
                check(c.get("quote", "").startswith("| MDS-"), f"table {n}: missing table row")
            if name == "condition":
                check(any(t in c.get("quote", "") for t in ("Nếu", "Trường hợp")), f"condition {n}: missing conditional evidence")
            if name == "near_domain":
                check("may doc sach" in normalize(c.get("question", "")), f"near-domain {n}: topic missing")
                check(bool(c.get("absent_terms")), f"near-domain {n}: needs absent detail")
            if name == "ambiguous":
                check(c.get("absent_terms") == [], f"ambiguous {n}: no artificial absent term")

    novelty = ["máy đọc sách", "đọc sách điện tử", "mượn máy đọc"]
    for term in novelty:
        check(normalize(term) not in corpus, f"topic keyword present in corpus: {term}")
        check(normalize(term) in doc_norm, f"topic keyword missing from document: {term}")
    identifier = "8793/QĐ-ĐHXDHN"
    check(identifier in document and normalize(identifier) not in corpus, "document identifier collision")
    check("8793" not in corpus, "numeric identifier collision")
    table_lines = [line for line in document.splitlines() if line.startswith("|")]
    check(len(table_lines) >= 7, "table needs header, delimiter and >=5 rows")
    check(all(len(line.strip().strip("|").split("|")) == 3 for line in table_lines), "table must have 3 columns")
    check(len(re.findall(r"(?m)^### Điều \d+\.", document)) >= 3, "numbered articles missing")
    check(len(re.findall(r"(?m)^\d+\. ", document)) >= 3, "numbered clauses missing")
    check(len(set(re.findall(r"\d+(?:/\d+)*", document))) >= 6, "need >=6 distinct numbers/dates/codes")
    check("PUBLIC_CONTACT_" not in document, "contact placeholder present")
    check("Đầu mối liên hệ" in document and "Phòng Công tác sinh viên" in document, "contact department missing")
    check(not re.search(r"(?<!\d)(?:\+84|0)[\d .-]{8,12}\d(?!\d)", document), "possible phone number")
    # Plain Markdown has no fixed pagination; this is only a length sanity check.
    word_count = len(document.split())
    check(1800 <= word_count <= 3500, f"document length outside approximate 3-5 page range: {word_count}")

    print(f"corpus_chunks={len(corpus_rows)}; corpus_sha256={hashlib.sha256(corpus_bytes).hexdigest()}")
    print(f"cases={len(cases)}; expected={dict(counts)}; answer_variants={dict(sorted(answer_variants.items()))}")
    print("groups=" + json.dumps({k: len(v) for k, v in groups.items()}, ensure_ascii=False))
    print(f"document_words={word_count}; table_data_rows={len(table_lines)-2}; topic_keyword_matches=0" if not any(normalize(t) in corpus for t in novelty) else "topic_keyword_matches>0")
    print(f"errors={len(errors)}")
    for error in errors:
        print("ERROR: " + error)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
