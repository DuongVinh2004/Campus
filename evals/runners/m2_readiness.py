"""M2 input readiness and retrieval metrics; never a live acceptance substitute.

The runner may consume sealed inputs, but returns counts/reason codes only.
Expected evidence and trusted catalogs must be independently supplied. No paid
provider, database, credentials, index activation or writes occur here.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from math import log2
from typing import Any

from evals.runners.rag_gold import GoldValidationError, _query, validate_gold

SPLITS = ("dev", "validation", "sealed_test")
QUOTAS = {
    "rag": (300, 100, 100),
    "injection": (40, 30, 30),
    "abstention": (50, 25, 25),
    "multi_turn": (30, 10, 10),
}


def dataset_readiness(
    records: Sequence[dict[str, Any]], *, trusted_chunks: Sequence[dict[str, Any]],
    trusted_contexts: Mapping[str, dict[str, Any]],
) -> dict[str, Any]:
    """Check input prerequisites, not representativeness or semantic gold quality.

    Cases with two user turns may count in both their primary suite and the
    multi-turn suite. A grounded/citation case counts toward RAG only if its
    relevant evidence resolves. Scenario/source isolation remains authoritative
    in validate_gold; token overlap is an additional review signal.
    """
    try:
        integrity = validate_gold(records, trusted_chunks=trusted_chunks,
                                  trusted_contexts=trusted_contexts)
    except GoldValidationError as error:
        return {"status": "blocked", "integrity": str(error), "case_count": len(records),
                "reason_codes": [str(error)], "sealed_content_emitted": False}
    counts = {suite: Counter() for suite in QUOTAS}
    domains, versions, negative_ids = set(), set(), set()
    queries = []
    for record in records:
        case, gold = record["case"], record["gold"]
        split, suite = case["split"], case["suite"]
        if suite in {"grounded_qa", "citation"} and gold["relevant_chunks"]:
            counts["rag"][split] += 1
        if suite == "prompt_injection":
            counts["injection"][split] += 1
        if suite == "abstention":
            counts["abstention"][split] += 1
        user_turns = sum(turn["role"] == "user" for turn in case["input"]["turns"])
        if user_turns >= 2:
            counts["multi_turn"][split] += 1
        if gold["negative_labels"] or suite in {"prompt_injection", "abstention"}:
            negative_ids.add(case["case_id"])
        domains.add(gold["domain"])
        versions.update((ref["source_id"], ref["document_version_id"])
                        for ref in gold["relevant_chunks"])
        tokens = frozenset(_query(" ".join(turn["content"] for turn in
                                          case["input"]["turns"])).split())
        queries.append((split, tokens))
    deficits = {suite: {split: max(0, minimum - counts[suite][split])
                       for split, minimum in zip(SPLITS, quota, strict=True)}
                for suite, quota in QUOTAS.items()}
    reasons = ["SUITE_SPLIT_QUOTA_MISSING"] if any(
        missing for row in deficits.values() for missing in row.values()) else []
    if len(versions) < 2:
        reasons.append("ONE_SOURCE_VERSION_SMOKE_ONLY")
    if len(negative_ids) / len(records) < 0.20:
        reasons.append("ADVERSARIAL_FAILURE_COVERAGE_BELOW_20_PERCENT")
    near_pairs = sum(
        left_split != right_split and bool(left | right)
        and len(left & right) / len(left | right) >= 0.85
        for i, (left_split, left) in enumerate(queries)
        for right_split, right in queries[i + 1:]
    )
    if near_pairs:
        reasons.append("CROSS_SPLIT_NEAR_DUPLICATES_REQUIRE_REVIEW")
    return {
        "status": "blocked" if reasons else "input_checks_passed",
        "integrity": integrity, "case_count": len(records),
        "counts": {suite: {split: row[split] for split in SPLITS}
                   for suite, row in counts.items()}, "deficits": deficits,
        "domain_count": len(domains), "source_version_count": len(versions),
        "adversarial_or_failure_case_count": len(negative_ids),
        "cross_split_token_jaccard_085_pairs": near_pairs,
        "reason_codes": reasons, "sealed_content_emitted": False,
        "limitations": ["taxonomy/subgroup representativeness requires technical review",
                        "token overlap is not semantic near-duplicate detection",
                        "source publication and live model tuple are not verified",
                        "input checks never constitute M2 acceptance"],
    }


def retrieval_metrics(observations: Sequence[dict[str, Any]], *,
                      expected_attempts: Sequence[tuple[str, int]]) -> dict[str, Any]:
    """Binary case-hit Recall@k; errors and absent attempts remain denominators.

    observations contain only immutable IDs, ranks and booleans. Planned
    retrievable/exact-ID flags and gold IDs originate from the frozen manifest,
    including for failed executions. Returns no success decision for M2.
    """
    planned = set(expected_attempts)
    if len(planned) != len(expected_attempts) or not planned:
        raise ValueError("INVALID_ATTEMPT_PLAN")
    by_attempt = {}
    for row in observations:
        key = (row["case_id"], row["attempt"])
        if key not in planned or key in by_attempt:
            raise ValueError("UNPLANNED_OR_DUPLICATE_ATTEMPT")
        for field in ("retrievable", "exact_identifier", "critical"):
            if type(row[field]) is not bool:
                raise ValueError("INVALID_METRIC_FLAGS")
        if row["status"] not in {"passed", "failed", "timeout", "error", "not_verified"}:
            raise ValueError("INVALID_ATTEMPT_STATUS")
        gold, ranked = row["gold_chunk_ids"], row["retrieved_chunk_ids"]
        if not isinstance(gold, list) or not isinstance(ranked, list):
            raise ValueError("INVALID_RANK_LIST")
        if any(not isinstance(value, str) or not value for value in gold + ranked):
            raise ValueError("INVALID_CHUNK_ID")
        if len(set(gold)) != len(gold) or len(set(ranked)) != len(ranked):
            raise ValueError("DUPLICATE_RANK_ID")
        if row["retrievable"] != bool(gold) or (row["exact_identifier"] and not gold):
            raise ValueError("UNRESOLVED_METRIC_GOLD")
        if row["status"] in {"timeout", "error", "not_verified"} and ranked:
            raise ValueError("FAILURE_WITH_UNVERIFIED_RANKS")
        by_attempt[key] = row
    missing = sorted(planned - by_attempt.keys())
    if missing:
        return {"status": "not_verified", "planned_attempt_count": len(planned),
                "observed_attempt_count": len(by_attempt),
                "missing_attempts": [{"case_id": key[0], "attempt": key[1]} for key in missing],
                "metrics": None, "reason_codes": ["MISSING_ATTEMPTS"]}
    retrievable = [row for row in observations if row["retrievable"]]
    exact = [row for row in retrievable if row["exact_identifier"]]
    critical = [row for row in retrievable if row["critical"]]

    def hit(row, k):
        return bool(set(row["gold_chunk_ids"]) & set(row["retrieved_chunk_ids"][:k]))

    def rate(rows, k):
        numerator = sum(hit(row, k) for row in rows)
        return {"numerator": numerator, "denominator": len(rows),
                "value": numerator / len(rows) if rows else None}

    reciprocal, ndcg = [], []
    case_passes = {}
    for row in retrievable:
        gold = set(row["gold_chunk_ids"])
        ranks = [i for i, chunk in enumerate(row["retrieved_chunk_ids"][:10], 1)
                 if chunk in gold]
        reciprocal.append(1 / ranks[0] if ranks else 0)
        ideal = sum(1 / log2(i + 1) for i in range(1, min(10, len(gold)) + 1))
        ndcg.append(sum(1 / log2(i + 1) for i in ranks) / ideal)
        case_passes.setdefault(row["case_id"], []).append(hit(row, 10))
    metrics = {
        "recall_at_5": rate(retrievable, 5), "recall_at_10": rate(retrievable, 10),
        "exact_id_recall_at_5": rate(exact, 5), "critical_recall_at_10": rate(critical, 10),
        "mrr_at_10": sum(reciprocal) / len(reciprocal) if reciprocal else None,
        "ndcg_at_10": sum(ndcg) / len(ndcg) if ndcg else None,
        "retrieval_pass_at_all": sum(all(v) for v in case_passes.values()) / len(case_passes)
        if case_passes else None,
        "retrieval_pass_at_majority": sum(sum(v) > len(v) / 2 for v in case_passes.values())
        / len(case_passes) if case_passes else None,
    }
    return {"status": "computed", "planned_attempt_count": len(planned),
            "observed_attempt_count": len(observations), "metrics": metrics,
            "execution_failures": sum(row["status"] in {"timeout", "error", "not_verified"}
                                      for row in observations),
            "failed_retrieval_attempts": [{"case_id": row["case_id"], "attempt": row["attempt"]}
                                          for row in retrievable if not hit(row, 10)],
            "ranking_stage": "authorized hybrid candidates before reranking",
            "M2_acceptance": "not_verified",
            "semantic_repeats_verified": False}
