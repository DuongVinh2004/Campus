"""Check the existing contact-policy alternative without relabeling factual QA."""
import json
import re
from contextlib import closing
from datetime import UTC, datetime

from audit_huce_rag_20261023 import API, client, counters, request
from continue_huce_completion_20261025 import CORPUS, OUT, ROOT, checked, read, save, sha
from verify_knowledge_platform_huce import final

PUBLISHER = "https://ctsv.huce.edu.vn/thong-bao-ve-chuong-trinh-hoc-bong-stem-quy-chau-a-nam-hoc-2025-2026-2"


def main():
    factual_file = checked(OUT / "live-verdict-224-01.json")
    factual = read(factual_file)
    assert factual["count"] == 224  # The complete immutable batch must finish first.
    fingerprint_file = checked(OUT / "api-code-fingerprint-20.json")
    fingerprint = read(fingerprint_file)
    assert all(sha(checked(ROOT / name).read_bytes()) == value for name, value in fingerprint["sha256"].items())
    release = read(CORPUS / "candidate-release-32.json")
    candidate_file = checked(OUT / "stem-notice-details-candidate-02.json")
    candidate = read(candidate_file)
    assert candidate["original_sha256"] == "91c13da397638af2bd3d39177b2c68387bb6bd90ee234331724b982a6cb0ee4e"
    source_text = "\n".join(p["text"] for p in candidate["pages"])
    emails = set(re.findall(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b", source_text))
    phones = set(re.findall(r"\b0\d{9,10}\b", source_text))
    assert emails and phones
    case = next(c for c in read(OUT / "it-common-live-cases-224-01.json") if c["name"] == "stem_notice_contact")
    before = counters()
    with closing(client()) as c:
        state_before = request(c, "GET", API + "/state").json()["desired"]
        assert state_before["generation"] == 27 and state_before["release_id"] == release["release_id"]
        created = request(c, "POST", "/v1/conversations", json={"mode": "temporary"})
        created.raise_for_status()
        conversation = created.json()["id"]
        response = request(c, "POST", f"/v1/conversations/{conversation}/messages:stream", json={"content": case["question"]})
        result = final(response.text) or {}
        events = [line[7:] for line in response.text.splitlines() if line.startswith("event: ")]
        deltas = "".join(json.loads(next(line[6:] for line in block.splitlines() if line.startswith("data: ")))["delta"]
            for block in response.text.split("\n\n") if "event: message.delta\n" in block)
        history_response = request(c, "GET", f"/v1/conversations/{conversation}/messages")
        history_response.raise_for_status()
        history = history_response.json()
        history_text = json.dumps(history, ensure_ascii=False)
        after_state = request(c, "GET", API + "/state").json()["desired"]
    checks = {
        "http_ok": response.status_code == 200,
        "completed_abstention": result.get("status") == "abstained" and events[-1:] == ["message.completed"],
        "no_failed_event": "message.failed" not in events,
        "official_original_link": PUBLISHER in result.get("content", "") and "trang 2" in result.get("content", ""),
        "no_raw_contact_any_stream_frame": not any(v in response.text for v in emails | phones),
        "no_raw_contact_joined_deltas": not any(v in deltas for v in emails | phones),
        "no_raw_contact_in_history": not any(v in history_text for v in emails | phones),
        "safe_result_persisted": bool(result.get("content") and result.get("message_id"))
            and result.get("content", "") in history_text and result.get("message_id", "") in history_text,
        "no_factual_citations_claimed": result.get("citations") == [],
        "release_and_generation_unchanged": after_state == state_before,
        "code_unchanged": all(sha(checked(ROOT / name).read_bytes()) == value for name, value in fingerprint["sha256"].items()),
    }
    receipt = {"at": datetime.now(UTC), "checks": checks, "all_checks_passed": all(checks.values()),
        "conversation_id": conversation, "question": case["question"], "final": result, "event_types": events,
        "binding": state_before, "stream_sha256": sha(response.content), "history_sha256": sha(history_response.content),
        "candidate_sha256": sha(candidate_file.read_bytes()), "fingerprint_sha256": sha(fingerprint_file.read_bytes()),
        "factual_qa_receipt": str(factual_file.relative_to(ROOT)), "factual_qa_sha256": sha(factual_file.read_bytes()),
        "factual_pass_count_unchanged": factual["passed"], "counters_before": before, "counters_after": counters(),
        "method": "One fresh real API turn scans every returned SSE frame and persisted history against original contact values. It verifies a completed safe source-opening alternative under the unchanged history policy. It does not count the inline contact factual case as passed."}
    save(OUT / "contact-safe-stream-verdict-01.json", receipt)
    print({"checks": checks, "all_checks_passed": receipt["all_checks_passed"], "factual_pass_count_unchanged": factual["passed"]})
    assert receipt["all_checks_passed"]


if __name__ == "__main__":
    main()
