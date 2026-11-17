"""Verify12 original columns and publish the exact two-source corrective batch."""
import argparse
import asyncio
import time
from contextlib import closing
from datetime import UTC, datetime

from audit_huce_rag_20261023 import API, client
from complete_huce_corpus import actors
from continue_huce_completion_20261025 import CORPUS, OUT, read, save, sha
from knowledge_platform import TENANT, components
from prepare_huce_economics_electives_second import ECONOMICS
from prepare_huce_environment_geometry_second import ENVIRONMENT
from campus247.domain.retrieval import AuthorizedScope, RetrievalContext, SimulationPolicy


async def probes():
    release = read(CORPUS / "candidate-release-18.json")
    version = next(m["version_id"] for m in release["members"] if m["source_id"] == ECONOMICS)
    candidate = read(OUT / "economics-elective-columns-candidate-01.json")
    questions = []
    for group in candidate["extracted"]["curriculum_geometry"]["elective_groups"]:
        query = f"Theo kế hoạch ngành Kinh tế xây dựng K71 bản 2025, nhóm {group['label']} ghi hai phương án học phần nào?"
        terms = [option["value"]["text"][:6] for option in group["options"]]
        questions.append((group["id"], query, terms, True, group["page"]))
    questions += [
        ("wrong_cohort", "Theo kế hoạch ngành Kinh tế xây dựng K70 bản 2025, nhóm HPTCBB 1 ghi gì?", [], False, None),
        ("unprinted_group", "Theo kế hoạch ngành Kinh tế xây dựng K71 bản 2025, nhóm HPTCBB 7 ghi gì?", [], False, None),
        ("unverified_semester", "Theo kế hoạch ngành Kinh tế xây dựng K71 bản 2025, học kỳ 2 nhóm HPTCBB 1 gồm môn nào?", [], False, None),
        ("unverified_edge", "Theo kế hoạch ngành Kinh tế xây dựng K71 bản 2025, 361455 là tiên quyết của 360401 không?", [], False, None),
        ("unverified_count", "Theo kế hoạch ngành Kinh tế xây dựng K71 bản 2025, HPTCBB 1 phải chọn mấy môn?", [], False, None),
    ]
    pool, _, _, runtime = await components(); _, owner = actors()
    roles = frozenset(r.value for r in owner.roles)
    context = RetrievalContext(AuthorizedScope(TENANT, "HUCE", owner.subject_id, roles, roles,
        frozenset({"FIT"}), frozenset({"PUBLIC"})), "vi", datetime.now(UTC), SimulationPolicy.DENY, "8"*32)
    rows = []
    try:
        for name, query, terms, expected, page in questions:
            items = await runtime.preview_search(owner, query, context, release["release_id"])
            own = [item for item in items if item["document_version_id"] == version]
            passed = (any(all(t in item["content_text"] for t in terms) and item["page_start"] == page for item in own)
                if expected else not own)
            passed &= all(sha(item["content_text"].encode()) == item["evidence_sha256"] for item in items)
            if expected:
                passed &= all(item["page_start"] == page for item in own)
            rows.append({"name": name, "question": query, "expected_present": expected, "expected_terms": terms,
                "expected_page": page, "passed": bool(passed), "items": items, "expected_version": version})
            print({"name": name, "passed": bool(passed)}, flush=True)
        save(OUT / "economics-column-probes-01.json", {"release_id": release["release_id"], "cases": rows,
            "count": len(rows), "passed": sum(r["passed"] for r in rows), "all_passed": all(r["passed"] for r in rows)})
    finally:
        await pool.close()


def activate():
    release = read(CORPUS / "candidate-release-18.json"); previous = read(CORPUS / "candidate-release-14.json")
    mtc_release = read(CORPUS / "candidate-release-17.json")
    integrity = read(CORPUS / "candidate-integrity-13.json")
    economics = read(OUT / "economics-column-probes-01.json"); environment = read(OUT / "environment-candidate-probes-02.json")
    regression = read(OUT / "live-verdict-90-02.json")
    # The preceding complete run isolates the exact old flattened-table failure
    # corrected here. It is retained as89/90, never relabelled a passing run.
    assert regression["binding"]["release_id"] == previous["release_id"] and regression["passed"] == 89
    assert {r["name"] for r in regression["verdicts"] if not r["passed"]} == {"evidence_economics_k71"}
    assert integrity["all_passed"] and integrity["release_id"] == release["release_id"]
    assert economics["all_passed"] and economics["release_id"] == release["release_id"]
    assert environment["all_passed"] and environment["release_id"] == mtc_release["release_id"]
    members = {r["source_id"]: r for r in release["members"]}; old = {r["source_id"]: r for r in previous["members"]}
    assert len(members) == 114 and members.keys() == old.keys()
    assert {k for k in members if members[k] != old[k]} == {ECONOMICS, ENVIRONMENT}
    assert members[ENVIRONMENT] == next(m for m in mtc_release["members"] if m["source_id"] == ENVIRONMENT)
    assert release["expected_generation"] == 21
    with closing(client()) as c:
        response = c.get(API + "/state"); response.raise_for_status(); state = response.json()
        assert state["is_serving"] and state["desired"]["release_id"] == previous["release_id"] and state["desired"]["generation"] == 21
        response = c.post(API + "/previews", json={"operation": "activate", "target_id": release["release_id"], "expected_generation": 21})
        response.raise_for_status(); preview = response.json()
        assert preview["payload"]["target_sha256"] == release["membership_sha256"]
        assert {r["source_id"]: r for r in preview["payload"]["members"]} == members
        save(OUT / "columns-activation-preview-01.json", {k: v for k, v in preview.items() if k != "confirmation_token"})
        response = c.post(API + "/confirmations", headers={"Idempotency-Key": "huce-completion-20261025-02-columns-01"},
            json={"preview_id": preview["preview_id"], "confirmation_token": preview["confirmation_token"], "confirmed": True})
        response.raise_for_status(); save(OUT / "columns-activation-confirmation-01.json", response.json())
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            response = c.get(API + "/state"); response.raise_for_status(); state = response.json()
            if state["is_serving"] and state["desired"]["release_id"] == release["release_id"] and state["desired"]["generation"] == 22:
                break
            time.sleep(.5)
        else:
            raise RuntimeError("Activation recorded; live acknowledgement not verified")
        response = c.get(API + "/availability"); response.raise_for_status()
        save(OUT / "columns-activation-ready-01.json", {"at": datetime.now(UTC), "desired": state["desired"],
            "serving": state["serving"], "availability": response.json(), "unchanged_members": 112})
        print({"activated": True, "generation": 22, "release_id": release["release_id"]})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("mode", choices=["probes", "activate"])
    args = parser.parse_args()
    asyncio.run(probes()) if args.mode == "probes" else activate()
