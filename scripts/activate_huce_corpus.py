"""Activate the exact verified local corpus via normal preview/confirmation."""
import json
import time
from contextlib import closing
from datetime import UTC, datetime

from audit_huce_rag_20261023 import API, client
from complete_huce_corpus import SCOPE, read
from knowledge_platform import retain


def main():
    candidate = read(SCOPE / "candidate-release-04.json")
    baseline = read(SCOPE / "retrieval-probes-08/summary.json")
    retest = read(SCOPE / "retrieval-probes-10/summary.json")
    assert baseline["release_id"] == retest["release_id"] == candidate["release_id"]
    coverage = {}
    for folder in ("retrieval-probes-08", "retrieval-probes-10"):
        for path in (SCOPE / folder).glob("*.json"):
            if path.name != "summary.json":
                row = read(path); coverage[row["source_id"]] = row
    assert len(coverage) == 114 and all(row["found"] and row["hashes_verified"] for row in coverage.values())
    originals = {row["source_id"]: row["serving_version"] for row in read(SCOPE / "inventory-01.json")["sources"] if row["serving_version"]}
    target = {row["source_id"]: row["version_id"] for row in candidate["members"]}
    assert len(target) == 114 and all(target[key] == value for key, value in originals.items())
    assert all(coverage[key]["expected_version"] == value for key, value in target.items())
    assert read(SCOPE / "candidate-integrity-01.json")["all_passed"]
    retain(SCOPE / "retrieval-coverage-final-01.json", {"release_id": candidate["release_id"], "found": 114,
        "baseline": baseline, "retest": retest,
        "retest_reason": "New explicit total-label parser and the two failed source queries; no-total focusing experiment 09 reverted. No BGE threshold or guard changed.",
        "queries": [{key: row[key] for key in ("source_id", "query", "expected_version", "found", "hashes_verified")} for row in coverage.values()],
        "limitations": "At least one successful query per source; broad questions and unverified diagram semantics remain limited."})
    with closing(client()) as c:
        before = c.get(API + "/state"); before.raise_for_status(); before = before.json()
        assert before["desired"]["generation"] == candidate["expected_generation"] == 12
        response = c.post(API + "/previews", json={"operation": "activate", "target_id": candidate["release_id"], "expected_generation": 12})
        response.raise_for_status(); preview = response.json()
        assert preview["payload"]["target_sha256"] == candidate["membership_sha256"]
        assert {row["source_id"]: row["version_id"] for row in preview["payload"]["members"]} == target
        retain(SCOPE / "activation-preview-01.json", {key: value for key, value in preview.items() if key != "confirmation_token"})
        response = c.post(API + "/confirmations", headers={"Idempotency-Key": "huce-corpus-20261024-activate-01"},
            json={"preview_id": preview["preview_id"], "confirmation_token": preview["confirmation_token"], "confirmed": True})
        response.raise_for_status(); result = response.json()
        retain(SCOPE / "activation-confirmation-01.json", result)
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            state = c.get(API + "/state"); state.raise_for_status(); state = state.json()
            availability = c.get(API + "/availability"); availability.raise_for_status(); availability = availability.json()
            if state["is_serving"] and availability["serving_documents"] == 114 and availability["generation"] == 13:
                break
            time.sleep(.5)
        else: raise RuntimeError("Activation recorded; runtime acknowledgement not verified")
        assert availability["total_sources"] == 117 and availability["equivalent_sources"] == 3
        assert availability["unresolved_sources"] == availability["actionable_pending_versions"] == 0
        retain(SCOPE / "activation-ready-01.json", {"at": datetime.now(UTC).isoformat(), "desired": state["desired"],
            "serving": state["serving"], "availability": availability, "original_three_versions_preserved": True,
            "source_scopes_are_limited": True, "confirmation_protocol_used": True})
        print(json.dumps({"activated": True, "release_id": candidate["release_id"], "generation": 13,
            "serving_documents": 114, "equivalents": 3, "originals_preserved": True}))


if __name__ == "__main__": main()
