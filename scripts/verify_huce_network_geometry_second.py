"""Verify the selected71MHT columns and direct links before exact activation."""
import argparse
import asyncio
import time
from contextlib import closing
from datetime import UTC, datetime

from audit_huce_rag_20261023 import API, client
from complete_huce_corpus import actors
from continue_huce_completion_20261025 import CORPUS, OUT, read, save, sha
from knowledge_platform import TENANT, components
from review_huce_network_geometry_second import LINKS, NETWORK
from campus247.domain.retrieval import AuthorizedScope, RetrievalContext, SimulationPolicy


async def probes(number, attempt):
    release = read(CORPUS / f"candidate-release-{number}.json")
    version = next(m["version_id"] for m in release["members"] if m["source_id"] == NETWORK)
    label = "network-71" if number == "19" else "network-71-full"
    witness = read(OUT / f"{label}-geometry-candidate-01.json")["extracted"]["curriculum_geometry"]
    questions = []
    for semester in [g["semester"] for g in witness["semester_groups"]]:
        terms = [code for c in witness["cells"] if c["semester"] == semester for code in c["course_codes"]]
        questions.append((f"semester_{semester}", f"Theo kế hoạch 71MHT K71, học kỳ {semester} có những học phần nào?", terms, True))
    for i, (a, b, _) in enumerate(LINKS):
        questions.append((f"link_{i}", f"Theo sơ đồ 71MHT K71, {a} là tiên quyết của {b} không?", [a, b, "→"], True))
    questions += [
        ("literal_pe_code", "Theo đúng kế hoạch 71MHT K71, mã 420102 có tên nguyên văn và mấy tín chỉ?", ["420102", "Giáo dục TC2"], True),
        ("wrong_cohort", "Theo sơ đồ 71MHT K70, 461716 là tiên quyết của 608807 không?", [], False),
        ("ambiguous_code", "Theo đúng kế hoạch 71MHT K71, mã 467710 có tên duy nhất là gì?", [], False),
        ("ambiguous_code_credit", "Theo đúng kế hoạch 71MHT K71, mã 467710 có bao nhiêu tín chỉ?", [], False),
        ("unprinted_code", "Theo đúng kế hoạch 71MHT K71, mã 430102 có tên và số tín chỉ thế nào?", [], False),
        ("unprinted_defence_code", "Theo kế hoạch 71MHT K71, học kỳ 2 có mã 480101 không?", [], False),
        ("unprinted_edge", "Theo sơ đồ 71MHT K71, 941725 là tiên quyết của 471755 không?", [], False),
        ("unverified_prior_study", "Theo sơ đồ 71MHT K71, 461716 là học trước của 608807 không?", [], False),
        ("unverified_corequisite", "Theo sơ đồ 71MHT K71, 428801 và 428802 có quan hệ song hành không?", [], False),
    ]
    if number == "19":
        questions.append(("deferred_semester", "Theo kế hoạch 71MHT K71, học kỳ 8 có những học phần nào?", [], False))
    else:
        questions += [
            ("elective_1", "Theo kế hoạch 71MHT K71, học kỳ 8 nhóm tự chọn 1 ghi những phương án nào?",
                ["Tự chọn 1: 4TC", "467713", "467710", "Bảo vệ bản quyền số2"], True),
            ("elective_2", "Theo kế hoạch 71MHT K71, học kỳ 8 nhóm tự chọn 2 ghi những phương án nào?",
                ["Tự chọn 2: 4TC", "467703", "467708"], True),
        ]
    pool, _, _, runtime = await components(); _, owner = actors()
    roles = frozenset(r.value for r in owner.roles)
    context = RetrievalContext(AuthorizedScope(TENANT, "HUCE", owner.subject_id, roles, roles,
        frozenset({"FIT"}), frozenset({"PUBLIC"})), "vi", datetime.now(UTC), SimulationPolicy.DENY, "7"*32)
    rows = []
    try:
        for name, query, terms, positive in questions:
            items = await runtime.preview_search(owner, query, context, release["release_id"])
            own = [item for item in items if item["document_version_id"] == version]
            passed = (any(all(t in item["content_text"] for t in terms) for item in own) if positive else not own)
            passed &= all(sha(item["content_text"].encode()) == item["evidence_sha256"] for item in items)
            rows.append({"name": name, "question": query, "expected_terms": terms, "expected_present": positive,
                "passed": bool(passed), "expected_version": version, "items": items})
            print({"name": name, "passed": bool(passed)}, flush=True)
        save(OUT / f"network-candidate-probes-{attempt}.json", {"release_id": release["release_id"], "cases": rows,
            "count": len(rows), "passed": sum(r["passed"] for r in rows), "all_passed": all(r["passed"] for r in rows)})
    finally:
        await pool.close()


def activate(number, attempt):
    release = read(CORPUS / f"candidate-release-{number}.json"); previous = read(CORPUS / "candidate-release-18.json")
    integrity_number = "14" if number == "19" else "15"
    integrity = read(CORPUS / f"candidate-integrity-{integrity_number}.json"); probe = read(OUT / f"network-candidate-probes-{attempt}.json")
    regression = read(OUT / "live-verdict-120-01.json")
    assert regression["all_passed"] and regression["binding"]["release_id"] == previous["release_id"]
    assert integrity["all_passed"] and integrity["release_id"] == release["release_id"]
    assert probe["all_passed"] and probe["release_id"] == release["release_id"]
    members = {m["source_id"]: m for m in release["members"]}; old = {m["source_id"]: m for m in previous["members"]}
    assert len(members) == 114 and members.keys() == old.keys() and {k for k in members if members[k] != old[k]} == {NETWORK}
    assert release["expected_generation"] == 22
    with closing(client()) as c:
        response = c.get(API + "/state"); response.raise_for_status(); state = response.json()
        assert state["is_serving"] and state["desired"]["release_id"] == previous["release_id"] and state["desired"]["generation"] == 22
        response = c.post(API + "/previews", json={"operation": "activate", "target_id": release["release_id"], "expected_generation": 22})
        response.raise_for_status(); preview = response.json()
        assert preview["payload"]["target_sha256"] == release["membership_sha256"]
        assert {m["source_id"]: m for m in preview["payload"]["members"]} == members
        save(OUT / f"network-activation-preview-{attempt}.json", {k: v for k, v in preview.items() if k != "confirmation_token"})
        response = c.post(API + "/confirmations", headers={"Idempotency-Key": "huce-completion-20261025-02-network-"+attempt},
            json={"preview_id": preview["preview_id"], "confirmation_token": preview["confirmation_token"], "confirmed": True})
        response.raise_for_status(); save(OUT / f"network-activation-confirmation-{attempt}.json", response.json())
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            response = c.get(API + "/state"); response.raise_for_status(); state = response.json()
            if state["is_serving"] and state["desired"]["release_id"] == release["release_id"] and state["desired"]["generation"] == 23:
                break
            time.sleep(.5)
        else:
            raise RuntimeError("Activation recorded; live acknowledgement not verified")
        response = c.get(API + "/availability"); response.raise_for_status()
        save(OUT / f"network-activation-ready-{attempt}.json", {"at": datetime.now(UTC), "desired": state["desired"],
            "serving": state["serving"], "availability": response.json(), "unchanged_members": 113})
        print({"activated": True, "generation": 23, "release_id": release["release_id"]})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("mode", choices=["probes", "activate"])
    parser.add_argument("--release", choices=["19", "20"], default="20")
    parser.add_argument("--attempt", choices=["01", "02"], default="02")
    args = parser.parse_args()
    asyncio.run(probes(args.release, args.attempt)) if args.mode == "probes" else activate(args.release, args.attempt)
