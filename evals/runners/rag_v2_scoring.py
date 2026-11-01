"""Shared, deterministic minimum scorer. Pure functions only; no corpus/network IO.

A1 checks local clauses, polarity, labels and declared forbidden facts. A2 checks
unsupported literal values, not independent semantic entailment. Neither is a
general natural-language judge; unmeasured source text is never a passing A2.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
import re
import statistics
import unicodedata
from collections import defaultdict
from decimal import Decimal

ANSWERED = {"answer", "partial"}
VARIANT_LIMITS = {"form+no_diacritics": .92, "keyword": .85, "slang": .75}
VARIANTS = {"form", "no_diacritics", "keyword", "slang"}
_STOP = set("la va cua cho co the duoc nhung thi ma o tai tu den khi da se hay hoac cac mot nhu".split())


def normalize(text):
    text = unicodedata.normalize("NFKD", text.casefold().replace("đ", "d"))
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"(?<=\d)\s*tc\b", " tin chi", text)
    text = re.sub(r"(?<=\d)(?:[.,]|\s+)(?=\d{3}(?:\D|$))", "", text)
    return " ".join(re.findall(r"[a-z0-9]+", text))


def _fold(text):
    text = unicodedata.normalize("NFKD", text.casefold().replace("đ", "d"))
    return "".join(c for c in text if not unicodedata.combining(c))


def _canonical(text):
    text = _fold(text)
    # Equivalences are intentionally small, shared and covered by mutations.
    text = re.sub(r"\b(?:mien phi|khong thu phi)\b", "freefee", text)
    text = re.sub(r"\bhoan toan\b", "", text)
    text = re.sub(r"(?<=\d)\s*tc\b", " tin chi", text)
    text = re.sub(r"(?<=\d)(?:[.,]|\s+)(?=\d{3}(?:\D|$))", "", text)
    def scale(m):
        return format(Decimal(m[1].replace(",", ".")) *
                      (1000 if m[2] in {"nghin", "ngan"} else 1000000), "f")
    text = re.sub(r"\b(\d+(?:[.,]\d+)?)\s+(nghin|ngan|trieu)(?=\s+(?:dong|vnd)\b)", scale, text)
    # Number words only before explicit measure nouns: avoid changing subjects.
    words = {"mot": 1, "hai": 2, "ba": 3, "bon": 4, "nam": 5, "sau": 6,
             "bay": 7, "tam": 8, "chin": 9, "muoi": 10}
    text = re.sub(r"\b(" + "|".join(words) + r")(?=\s+(?:ngay|gio|thang|kg|dong|tin chi)\b)",
                  lambda m: str(words[m[1]]), text)
    # Keep decimal/code boundaries; leading zeros in standalone values are cosmetic.
    text = re.sub(r"(?<![\w.])0+(\d+)(?!\w)", lambda m: str(int(m[0])), text)
    return " ".join(re.findall(r"[a-z]+\d+[a-z0-9]*|\d+(?:[.,]\d+)?|[a-z]+", text))


def _clauses(text):
    # A full stop inside a token (office.com, 3.5) does not end a clause.
    return [part.strip() for part in re.split(r"[;\n!?]+|(?<!\d)\.(?!\w)|,\s*(?:còn|nhưng|con|nhung)\b",
                                             text, flags=re.I) if part.strip()]


def _negative(text):
    return bool(re.search(r"\b(?:khong|chua|cam|chang)\b", text))


def _polarities(needle, words, numbers, reference):
    """Polarities a clause stating this fact may have: the fact's own, and that of the gold
    statement it was taken from ("181TC" listed from "181TC (Không tính HP thể chất)" is
    legitimately stated inside a negated clause; "miễn học phí" taken from a positive statement is not)."""
    allowed = {_negative(needle)}
    for text in reference:
        for part in _clauses(text):
            clause = _canonical(part)
            present = clause.split()
            if words + numbers and all(t in present for t in words + numbers):
                allowed.add(_negative(clause))
    return allowed


def fact_matches(fact, answer, reference=()):
    """Match one fact within one clause; do not pool labels/numbers across rows.

    Short facts require every content word. Long facts retain the historical
    lexical tolerance, but their numbers/units must co-occur locally. Contradictory
    occurrences fail even if another occurrence states the correct fact. `reference` is the
    gold text the fact comes from; it only widens the polarity a correct statement may have.
    """
    needle = _canonical(fact)
    if not needle:
        return False
    tokens = needle.split()
    numbers = [t for t in tokens if re.fullmatch(r"\d+(?:[.,]\d+)?", t)]
    words = [t for t in tokens if t not in _STOP and t not in numbers
             and t not in {"khong", "chua", "cam", "chang"}]
    if not words and not numbers:
        return False
    matches = []
    allowed = _polarities(needle, words, numbers, reference)
    for part in _clauses(answer):
        clause = _canonical(part)
        present = clause.split()
        if any(n not in present for n in numbers):
            continue
        required = len(words) if len(words) <= 6 else math.ceil(.85 * len(words))
        if sum(w in present for w in words) < required:
            continue
        # Units remain bound to their values, including table cells (|).
        bindings = re.findall(r"\b(\d+(?:[.,]\d+)?)\s+([a-z]+)", needle)
        if any(not re.search(r"\b" + re.escape(n + " " + unit) + r"\b", clause)
               for n, unit in bindings):
            continue
        if len(numbers) == 1:
            before = needle.split(numbers[0], 1)[0].split()
            labels = [t for t in before if t not in _STOP and t not in {"khong", "chua", "cam", "chang"}]
            positions = list(re.finditer(r"(?<!\w)\d+(?:[.,]\d+)?(?!\w)", clause))
            if labels and not any(m[0] == numbers[0] and all(label in
                    clause[positions[i - 1].end() if i else 0:m.start()].split() for label in labels)
                    for i, m in enumerate(positions)):
                continue
        matches.append(_negative(clause) in allowed)
    return bool(matches) and all(matches)


def fact_errors(case, text):
    # Gold quotes only widen the polarity of a required fact; a forbidden fact is judged on its own words.
    reference = tuple(g["quote"] for g in case.get("gold", []) if isinstance(g.get("quote"), str))
    return {"missing_facts": [f for f in case.get("required_facts", []) if not fact_matches(f, text, reference)],
            "forbidden_facts": [f for f in case.get("forbidden_facts", []) if fact_matches(f, text)]}


def classify(case, row):
    if infra_error(row) or row.get("outcome_class") not in ANSWERED | {"refuse", "clarify"}:
        return "error"
    if row.get("outcome_class") in ANSWERED:
        if case["expected"] != "answer":
            return "wrongly_answered"
        return "thin" if any(fact_errors(case, row.get("answer_text", "")).values()) else "full"
    return "refused_or_clarified" if case["expected"] == "answer" else "correctly_declined"


def _literals(text):
    folded = _fold(text)
    folded = re.sub(r"\[(?:(?:cit[-_]|[suc])?\d+)(?:\s*,\s*(?:cit[-_]|[suc])?\d+)*\]", "", folded)
    dates = set()
    def date(m):
        a, b, c = map(int, m.groups())
        dates.add(f"date:{a:04}-{b:02}-{c:02}" if len(m[1]) == 4 else f"date:{c:04}-{b:02}-{a:02}")
        return " "
    folded = re.sub(r"\b(\d{1,4})[/.-](\d{1,2})[/.-](\d{1,4})\b", date, folded)
    folded = re.sub(r"\b(?:ngay\s+)?(\d{1,2})\s+thang\s+(\d{1,2})\s+nam\s+(\d{4})\b", date, folded)
    codes = {"code:" + m[0].lower() for m in re.finditer(
        r"\b(?:[a-z]+[-/]\d+[\w/-]*|\d+/[a-z][\w/-]*|[a-z]+\d+[a-z0-9]*)\b", folded)}
    canonical = _canonical(folded)
    numbers = {"num:" + str(Decimal(n.replace(",", "."))) for n in
               re.findall(r"(?<!\w)\d+(?:[.,]\d+)?(?!\w)", canonical)}
    return codes | dates | numbers


def unsupported_statements(answer, cited_texts):
    """Minimum literal check only, not semantic verification of every claim."""
    supported = set().union(*(_literals(t) for t in cited_texts)) if cited_texts else set()
    return [part for part in _clauses(answer) if _literals(part) - supported]


def quote_matches(gold, cited):
    gold, cited = " ".join(gold.split()), " ".join(cited.split())
    return min(len(gold), len(cited)) >= 20 and (gold in cited or cited in gold)


def cites_gold(case, cited_ids, chunk_text=None, cited_quotes=()):
    if {g["chunk_id"] for g in case.get("gold", [])} & set(cited_ids):
        return True
    quotes = [g["quote"] for g in case.get("gold", []) if len(g.get("quote", "").strip()) >= 20]
    texts = [" ".join((chunk_text or {}).get(uid, "").split()) for uid in cited_ids]
    return (any(" ".join(q.split()) in text for q in quotes for text in texts)
            or any(quote_matches(q, cited) for q in quotes for cited in cited_quotes))


def percentile(values, fraction=.95):
    ordered = sorted(values)
    return ordered[max(0, math.ceil(fraction * len(ordered)) - 1)] if ordered else None


def ratio(numerator, denominator, threshold, *, maximum=False, strict=False):
    value = numerator / denominator if denominator else None
    passed = None if value is None else (
        value < threshold if strict else value <= threshold if maximum else value >= threshold)
    return {"numerator": numerator, "denominator": denominator, "value": value,
            "threshold": threshold, "passed": passed}


def infra_error(row):
    return (row.get("outcome_class") in {"error", "transient_error"} or bool(row.get("error"))
            or row.get("final_event") is not True or (row.get("http_status") or 200) >= 400)


def error_label(case, row):
    if infra_error(row):
        return "INFRA"
    if case["expected"] == "answer" and row.get("outcome_class") == "refuse":
        return "OVER_REFUSE"
    if case["expected"] != "answer" and row.get("outcome_class") in ANSWERED:
        return "OVER_ANSWER"
    trace = row.get("trace") or {}
    if trace.get("failure_layer") in {"CORPUS_MISSING", "INGEST", "RETRIEVAL", "RERANK", "GENERATION", "VERIFICATION"}:
        return trace["failure_layer"]
    if trace.get("in_pool") is False or trace.get("in_chosen") is False:
        return "RETRIEVAL"
    return "UNLABELED"


def bootstrap_ci_by_group(values, groups, *, samples=2000, seed=20261031):
    """Wilson for reference; percentile bootstrap resamples whole groups.

    Pass document IDs when known, otherwise group_id. Repeats/paraphrases stay
    together. Wilson's independence assumption is not claimed for those rows.
    """
    if len(values) != len(groups) or samples < 1 or any(v not in (0, 1) for v in values):
        raise ValueError("Invalid binary samples/groups")
    if not values:
        return {"wilson": None, "bootstrap": None, "groups": 0, "seed": seed, "samples": samples}
    n, p, z = len(values), sum(values) / len(values), 1.959963984540054
    den = 1 + z * z / n
    mid = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    grouped = defaultdict(list)
    for group, value in zip(groups, values):
        grouped[group].append(value)
    totals = [(sum(grouped[g]), len(grouped[g])) for g in sorted(grouped, key=str)]
    rng, estimates = random.Random(seed), []
    for _ in range(samples):
        chosen = rng.choices(totals, k=len(totals))
        estimates.append(sum(x[0] for x in chosen) / sum(x[1] for x in chosen))
    return {"wilson": [max(0, mid - half), min(1, mid + half)],
            "bootstrap": [percentile(estimates, .025), percentile(estimates, .975)],
            "groups": len(totals), "seed": seed, "samples": samples,
            "method": "whole-group percentile bootstrap; Wilson reference assumes independent rows"}


def metrics(rows, cases, chunk_text=None, *, confidence=True):
    answers = [r for r in rows if cases[r["case_id"]]["expected"] == "answer"]
    negative = [r for r in rows if cases[r["case_id"]]["expected"] != "answer"]
    displayed = [r for r in rows if r["outcome_class"] in ANSWERED]
    incorrect, uncited, unsupported, misses, failures = [], [], [], [], []
    measured = 0
    for r in rows:
        c, reasons = cases[r["case_id"]], []
        key = {"case_id": r["case_id"], "repeat": r.get("repeat", 1)}
        facts = fact_errors(c, r.get("answer_text", ""))
        answered = r["outcome_class"] in ANSWERED
        if c["expected"] == "answer" and answered and any(facts.values()):
            incorrect.append(key | facts); reasons.append("A1")
        if answered:
            if not r.get("citation_count", len(r.get("citation_chunk_ids", []))):
                uncited.append(key); reasons.append("uncited_answer")
            texts = r.get("cited_texts")
            ids = r.get("citation_chunk_ids", [])
            if texts is None and chunk_text is not None and all(uid in chunk_text for uid in ids) and (
                    ids or not r.get("citation_count", len(ids))):
                texts = [chunk_text[uid] for uid in ids]
            if texts is not None:
                measured += 1
                extra = unsupported_statements(r.get("answer_text", ""), texts)
                if extra:
                    unsupported.append(key | {"statements": extra}); reasons.append("A2")
            if not cites_gold(c, ids, chunk_text, r.get("cited_quotes", [])):
                misses.append(key); reasons.append("A5")
        if c["expected"] != "answer" and (infra_error(r) or r["outcome_class"] not in {"refuse", "clarify"}):
            reasons.append("A3")
        if c["expected"] == "answer" and not answered:
            reasons.append("A4")
        if infra_error(r):
            reasons.append("A7")
        if reasons:
            failures.append(key | {"criteria": reasons, "label": error_label(c, r)})
    grouped = defaultdict(list)
    for r in rows:
        grouped[r["case_id"]].append(r)
    repeated = {cid: rs for cid, rs in grouped.items()
                if len(rs) == len({r.get("repeat", 1) for r in rs}) and {1, 2, 3} <= {r.get("repeat", 1) for r in rs}}
    inconsistent = [cid for cid, rs in repeated.items() if len({r["outcome_class"] for r in rs}) != 1]
    for cid in inconsistent:
        if not any(f["case_id"] == cid for f in failures):
            failures.append({"case_id": cid, "repeat": None, "criteria": ["A6"], "label": "UNLABELED"})
    variants = {v: ratio(sum(r["outcome_class"] in ANSWERED for r in answers if cases[r["case_id"]]["variant"] in v.split("+")),
        sum(cases[r["case_id"]]["variant"] in v.split("+") for r in answers), limit) for v, limit in VARIANT_LIMITS.items()}
    seconds = [r["seconds"] for r in rows if isinstance(r.get("seconds"), (int, float))]
    first = [r["first_byte_seconds"] for r in rows if r.get("first_byte_seconds") is not None]
    content = [r["first_content_seconds"] for r in rows if r.get("first_content_seconds") is not None]
    timing = {"median_seconds": statistics.median(seconds) if seconds else None, "p95_seconds": percentile(seconds),
        "first_byte_median_seconds": statistics.median(first) if first else None, "first_byte_p95_seconds": percentile(first),
        "first_content_median_seconds": statistics.median(content) if content else None, "first_content_p95_seconds": percentile(content),
        "thresholds_seconds": {"median": 6, "p95": 12, "first_byte_median": 2}, "samples": len(seconds), "first_byte_samples": len(first)}
    timing["passed"] = (statistics.median(seconds) <= 6 and percentile(seconds) <= 12 and statistics.median(first) <= 2
        if rows and len(seconds) == len(first) == len(rows) else None)
    passes = [v["passed"] for v in variants.values()]
    result = {"A1": ratio(len(incorrect), len(answers), .02, maximum=True) | {"incorrect": incorrect},
        "uncited_answer": {"value": len(uncited), "threshold": 0, "passed": not uncited if displayed else None, "cases": uncited},
        "A2": {"value": len(unsupported), "threshold": 0,
               "passed": False if unsupported else True if displayed and measured == len(displayed) else None,
               "measured_answers": measured, "unmeasured_answers": len(displayed) - measured, "cases": unsupported,
               "method": "Minimum deterministic literal check; not independent semantic verification"},
        "A3": ratio(sum(not infra_error(r) and r["outcome_class"] in {"refuse", "clarify"} for r in negative), len(negative), .98),
        "A4": {"by_variant": variants, "passed": False if False in passes else None if None in passes else True},
        "A5": ratio(len(displayed) - len(misses), len(displayed), .95) | {"misses": misses},
        "A6": ratio(len(repeated) - len(inconsistent), len(repeated), .95) | {"inconsistent_cases": inconsistent},
        "A7": ratio(sum(infra_error(r) for r in rows), len(rows), .01, maximum=True, strict=True),
        "A8": timing, "A9": {"passed": None, "status": "EXTERNAL", "reason": "Separate safety/routing/tool campaign required"},
        "failures": failures}
    error_types, phases = defaultdict(int), defaultdict(int)
    for r in rows:
        if not infra_error(r):
            continue
        error = r.get("error") or ("HTTP" if (r.get("http_status") or 200) >= 400 else "MissingFinalOrErrorOutcome")
        error_types[error if re.fullmatch(r"[A-Za-z_]{1,80}", str(error)) else "other"] += 1
        phase = (r.get("trace") or {}).get("failure_layer")
        phases[phase if phase in {"CORPUS_MISSING", "INGEST", "RETRIEVAL", "RERANK", "GENERATION", "VERIFICATION"} else "unattributed"] += 1
    result["A7"].update(by_error_type=dict(error_types), by_phase=dict(phases))
    if confidence:
        def group(r):
            c = cases[r["case_id"]]
            return c.get("document_id") or c.get("group_id") or c["case_id"]
        for name, rs, bad in (("A1", answers, incorrect), ("A3", negative, None), ("A5", displayed, misses)):
            keys = {(x["case_id"], x["repeat"]) for x in (bad or [])}
            values = [int((not infra_error(r) and r["outcome_class"] in {"refuse", "clarify"}) if name == "A3"
                          else ((r["case_id"], r.get("repeat", 1)) in keys) == (name == "A1")) for r in rs]
            result[name]["ci95"] = bootstrap_ci_by_group(values, [group(r) for r in rs])
    return result


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def distribution_issues(cases):
    issues = []
    if not cases or sum(c["expected"] != "answer" for c in cases) / len(cases) < .2:
        issues.append("negative_share")
    groups = defaultdict(list)
    for c in cases:
        groups[c.get("group_id", c["case_id"])].append(c.get("variant"))
    if any(len(v) != 4 or set(v) != VARIANTS for v in groups.values()):
        issues.append("group_variants")
    return issues


def record_issues(records, cases, repeats=3):
    issues, lookup, seen = [], {c["case_id"] for c in cases}, defaultdict(list)
    if len(lookup) != len(cases):
        issues.append("duplicate_case_ids")
    for r in records:
        if r.get("case_id") not in lookup:
            issues.append("unknown_case")
        repeat = r.get("repeat", 1)
        if type(repeat) is not int or repeat < 1:
            issues.append("invalid_repeat")
        seen[r.get("case_id")].append(repeat)
    if any(len(v) != len(set(v)) for v in seen.values()):
        issues.append("duplicate_repeat")
    if any(set(seen[cid]) != set(range(1, repeats + 1)) for cid in lookup):
        issues.append("missing_or_unexpected_repeat")
    return sorted(set(issues))


def validate_records(records, cases, repeats=3):
    if record_issues(records, cases, repeats):
        raise ValueError("Incomplete or duplicate result cases/repeats")


def campaign_issues(manifests, records=(), cases=None):
    issues = []
    if not manifests or any(not m or any(not m.get(k) for k in ("cases_sha256", "engine", "campaign_id")) for m in manifests):
        issues.append("missing_manifest")
    for field in ("cases_sha256", "engine", "campaign_id"):
        if len({m.get(field) for m in manifests}) > 1:
            issues.append("mixed_" + field)
    if cases is not None and any(m.get("cases_sha256") != fingerprint(cases) for m in manifests if m):
        issues.append("cases_sha256_mismatch")
    for field in ("engine", "campaign_id", "cases_sha256"):
        values = {r.get(field) for r in records if r.get(field) is not None}
        expected = {m.get(field) for m in manifests if m.get(field)}
        if len(values) > 1 or values and expected and not values <= expected:
            issues.append("mixed_record_" + field)
    return sorted(set(issues))


def attempt_metrics(records, journal=()):
    first, last = {}, {}
    for r in journal or records:
        key = (r["case_id"], r.get("repeat", 1))
        attempt = r.get("attempt_index", 1)
        if key not in first or attempt < first[key].get("attempt_index", 1):
            first[key] = r
        if key not in last or attempt > last[key].get("attempt_index", 1):
            last[key] = r
    def rate(rs):
        rs = list(rs)
        return ratio(sum(infra_error(r) for r in rs), len(rs), .01, maximum=True, strict=True)
    known = bool(first) and all(r.get("attempt_index") == 1 for r in first.values())
    return {"first_attempt": rate(first.values()) if known else {"value": None, "passed": None},
            "after_retry": rate(last.values()), "all_attempts": rate(journal or records),
            "journal_available": bool(journal), "first_attempt_measured": known}
