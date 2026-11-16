"""Activate exactly the two CS diagrams and common STEM notice additions."""
import time
import xml.etree.ElementTree as ET
from contextlib import closing
from datetime import UTC, datetime

from audit_huce_rag_20261023 import API, client
from continue_huce_completion_20261025 import CORPUS, OUT, ROOT, checked, read, save, sha
from prepare_huce_stem_full_second import STEM
from review_huce_csqt_geometry_second import CS, CSQT


def main():
    release = read(CORPUS / "candidate-release-32.json")
    previous = read(CORPUS / "candidate-release-25.json")
    integrity = read(CORPUS / "candidate-integrity-23.json")
    regression = read(OUT / "live-verdict-294-01.json")
    fingerprint = read(OUT / "api-code-fingerprint-18.json")
    assert all(sha(checked(ROOT / p).read_bytes()) == h for p, h in fingerprint["sha256"].items())
    suites = ET.parse(checked(OUT / "regression-tests-26.xml")).getroot().iter("testsuite")
    totals = {k: 0 for k in ("tests", "failures", "errors", "skipped")}
    for suite in suites:
        for key in totals:
            totals[key] += int(suite.get(key, "0"))
    assert totals == {"tests": 343, "failures": 0, "errors": 0, "skipped": 4}
    assert integrity["all_passed"] and integrity["release_id"] == release["release_id"]
    assert regression["all_passed"] and regression["count"] == 294
    assert regression["binding"]["release_id"] == previous["release_id"]
    for filename, count in (("csqt-71-candidate-probes-06.json", 32), ("cs-71-candidate-probes-06.json", 32),
            ("stem-notice-details-candidate-probes-06.json", 15)):
        probe = read(OUT / filename)
        assert probe["all_passed"] and probe["count"] == count and probe["release_id"] == release["release_id"]
    members = {m["source_id"]: m for m in release["members"]}
    old = {m["source_id"]: m for m in previous["members"]}
    assert len(members) == 114 and members.keys() == old.keys()
    assert {k for k in members if members[k] != old[k]} == {CS, CSQT, STEM}
    priority = {r["source_id"]: r for r in read(OUT / "source-execution-priorities-01.json")["sources"]}
    assert all(priority[k]["execution_priority"] == "CURRENT_FOCUS" for k in members if members[k] != old[k])
    assert release["expected_generation"] == 26
    with closing(client()) as c:
        response = c.get(API + "/state")
        response.raise_for_status()
        state = response.json()
        assert state["is_serving"] and state["desired"]["release_id"] == previous["release_id"] and state["desired"]["generation"] == 26
        response = c.post(API + "/previews", json={"operation": "activate", "target_id": release["release_id"], "expected_generation": 26})
        response.raise_for_status()
        preview = response.json()
        assert preview["payload"]["target_sha256"] == release["membership_sha256"]
        assert {m["source_id"]: m for m in preview["payload"]["members"]} == members
        save(OUT / "it-common-activation-preview-01.json", {k: v for k, v in preview.items() if k != "confirmation_token"})
        response = c.post(API + "/confirmations", headers={"Idempotency-Key": "huce-completion-20261025-02-it-common-01"},
            json={"preview_id": preview["preview_id"], "confirmation_token": preview["confirmation_token"], "confirmed": True})
        response.raise_for_status()
        save(OUT / "it-common-activation-confirmation-01.json", response.json())
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            response = c.get(API + "/state")
            response.raise_for_status()
            state = response.json()
            if state["is_serving"] and state["desired"]["release_id"] == release["release_id"] and state["desired"]["generation"] == 27:
                break
            time.sleep(.5)
        else:
            raise RuntimeError("Activation recorded; live acknowledgement not verified")
        save(OUT / "it-common-activation-ready-01.json", {"at": datetime.now(UTC), "desired": state["desired"],
            "serving": state["serving"], "unchanged_members": 111, "changed_source_ids": sorted({CS, CSQT, STEM}),
            "execution_scope_manifest": "source-execution-priorities-01.json", "focused_end_to_end_QA_pending": True})
        print({"activated": True, "generation": 27, "release_id": release["release_id"]})


if __name__ == "__main__":
    main()
