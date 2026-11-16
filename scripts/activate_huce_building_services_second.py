"""Activate only the sealed71HK replacement after every required retained check."""
import time
from contextlib import closing
from datetime import UTC, datetime

from audit_huce_rag_20261023 import API, client
from continue_huce_completion_20261025 import CORPUS, OUT, read, save
from review_huce_building_services_second import BUILDING_SERVICES


def main():
    release = read(CORPUS / "candidate-release-23.json")
    previous = read(CORPUS / "candidate-release-22.json")
    integrity = read(CORPUS / "candidate-integrity-18.json")
    probe = read(OUT / "building-services-candidate-probes-03.json")
    native = read(OUT / "building-services-native-crosscheck-02.json")
    regression = read(OUT / "live-verdict-199-02.json")
    ready = read(OUT / "api-restart-ready-17.json")["after"]
    assert ready["release_id"] == previous["release_id"] and ready["generation"] == 25
    assert regression["all_passed"] and regression["binding"]["release_id"] == previous["release_id"]
    assert integrity["all_passed"] and integrity["release_id"] == release["release_id"]
    assert probe["all_passed"] and probe["release_id"] == release["release_id"] and probe["count"] == 50
    assert native["all_passed"] and native["source_id"] == BUILDING_SERVICES and native["count"] == 79
    members = {m["source_id"]: m for m in release["members"]}
    old = {m["source_id"]: m for m in previous["members"]}
    assert len(members) == 114 and members.keys() == old.keys()
    assert {k for k in members if members[k] != old[k]} == {BUILDING_SERVICES}
    assert release["expected_generation"] == 25
    with closing(client()) as c:
        response = c.get(API + "/state"); response.raise_for_status(); state = response.json()
        assert state["is_serving"] and state["desired"]["release_id"] == previous["release_id"] and state["desired"]["generation"] == 25
        response = c.post(API + "/previews", json={"operation": "activate", "target_id": release["release_id"], "expected_generation": 25})
        response.raise_for_status(); preview = response.json()
        assert preview["payload"]["target_sha256"] == release["membership_sha256"]
        assert {m["source_id"]: m for m in preview["payload"]["members"]} == members
        save(OUT / "building-services-activation-preview-01.json", {k: v for k, v in preview.items() if k != "confirmation_token"})
        response = c.post(API + "/confirmations", headers={"Idempotency-Key": "huce-completion-20261025-02-building-services-01"},
            json={"preview_id": preview["preview_id"], "confirmation_token": preview["confirmation_token"], "confirmed": True})
        response.raise_for_status(); save(OUT / "building-services-activation-confirmation-01.json", response.json())
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            response = c.get(API + "/state"); response.raise_for_status(); state = response.json()
            if state["is_serving"] and state["desired"]["release_id"] == release["release_id"] and state["desired"]["generation"] == 26:
                break
            time.sleep(.5)
        else:
            raise RuntimeError("Activation recorded; live acknowledgement not verified")
        response = c.get(API + "/availability"); response.raise_for_status()
        save(OUT / "building-services-activation-ready-01.json", {"at": datetime.now(UTC), "desired": state["desired"],
            "serving": state["serving"], "availability": response.json(), "unchanged_members": 113})
        print({"activated": True, "generation": 26, "release_id": release["release_id"]})


if __name__ == "__main__":
    main()
