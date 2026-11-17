"""Verify complete71MTC semesters/links plus contrary inputs, then exact activation."""
import argparse
import asyncio
import time
from contextlib import closing
from datetime import UTC, datetime

from audit_huce_rag_20261023 import API, client
from complete_huce_corpus import actors
from continue_huce_completion_20261025 import CORPUS, OUT, read, save, sha
from knowledge_platform import TENANT, components
from prepare_huce_environment_geometry_second import ENVIRONMENT, LINKS
from campus247.domain.retrieval import AuthorizedScope, RetrievalContext, SimulationPolicy


async def probes(attempt):
    release = read(CORPUS / "candidate-release-17.json")
    version = next(m["version_id"] for m in release["members"] if m["source_id"] == ENVIRONMENT)
    witness = read(OUT / "environment-geometry-candidate-01.json")["extracted"]["curriculum_geometry"]
    questions = []
    for semester in range(1, 10):
        terms = [code for c in witness["cells"] if c["semester"] == semester for code in c["course_codes"]]
        questions.append((f"semester_{semester}", f"Theo kế hoạch 71MTC K71, học kỳ {semester} có những học phần nào?", terms, True))
    for i, (kind, a, b, _) in enumerate(LINKS):
        label, symbol = ("tiên quyết", "→") if kind == "PREREQUISITE" else ("song hành", "↔")
        questions.append((f"link_{i}", f"Theo sơ đồ 71MTC K71, {a} và {b} có quan hệ {label} thế nào?", [a, b, symbol], True))
    questions += [
        ("wrong_cohort", "Theo sơ đồ 71MTC K70, 250101 là tiên quyết của 250102 không?", [], False),
        ("wrong_semester", "Theo kế hoạch 71MTC K71, học kỳ 10 có những học phần nào?", [], False),
        ("wrong_course_semester", "Theo kế hoạch 71MTC K71, học kỳ 9 có 988803 không?", [], False),
        ("unprinted_link", "Theo sơ đồ 71MTC K71, 988803 là tiên quyết của 098880 không?", [], False),
        ("prior_study", "Theo sơ đồ 71MTC K71, 250101 là học trước của 250102 không?", [], False),
        ("wrong_relation_type", "Theo sơ đồ 71MTC K71, 250101 là tiên quyết của 250103 không?", [], False),
        ("unprinted_pe_credit", "Theo đúng kế hoạch 71MTC K71, GD thể chất 2 có phải là 2 tín chỉ không?", [], False),
        ("unknown_elective_count", "Theo kế hoạch 71MTC K71, học kỳ 5 nhóm tự chọn tự do phải chọn mấy môn?", [], False),
        ("placeholder_not_known_code", "Theo kế hoạch 71MTC K71, học kỳ 2 có mã 480101 không?", [], False),
    ]
    pool, _, _, runtime = await components(); _, owner = actors()
    roles = frozenset(r.value for r in owner.roles)
    context = RetrievalContext(AuthorizedScope(TENANT, "HUCE", owner.subject_id, roles, roles,
        frozenset({"FIT"}), frozenset({"PUBLIC"})), "vi", datetime.now(UTC), SimulationPolicy.DENY, "c"*32)
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
        save(OUT / f"environment-candidate-probes-{attempt}.json", {"release_id": release["release_id"], "cases": rows,
            "count": len(rows), "passed": sum(r["passed"] for r in rows), "all_passed": all(r["passed"] for r in rows)})
    finally:
        await pool.close()


def activate():
    release = read(CORPUS / "candidate-release-17.json"); previous = read(CORPUS / "candidate-release-14.json")
    integrity = read(CORPUS / "candidate-integrity-12.json"); probe = read(OUT / "environment-candidate-probes-02.json")
    regression = read(OUT / "live-verdict-90-02.json")
    assert regression["all_passed"] and regression["binding"]["release_id"] == previous["release_id"]
    assert integrity["all_passed"] and integrity["release_id"] == release["release_id"]
    assert probe["all_passed"] and probe["release_id"] == release["release_id"]
    members = {r["source_id"]: r for r in release["members"]}; old = {r["source_id"]: r for r in previous["members"]}
    assert len(members) == 114 and members.keys() == old.keys() and {k for k in members if members[k] != old[k]} == {ENVIRONMENT}
    assert release["expected_generation"] == 21
    with closing(client()) as c:
        response = c.get(API + "/state"); response.raise_for_status(); before = response.json()
        assert before["is_serving"] and before["desired"]["release_id"] == previous["release_id"] and before["desired"]["generation"] == 21
        response = c.post(API + "/previews", json={"operation": "activate", "target_id": release["release_id"], "expected_generation": 21})
        response.raise_for_status(); preview = response.json()
        assert preview["payload"]["target_sha256"] == release["membership_sha256"]
        assert {r["source_id"]: r for r in preview["payload"]["members"]} == members
        save(OUT / "environment-activation-preview-01.json", {k: v for k, v in preview.items() if k != "confirmation_token"})
        response = c.post(API + "/confirmations", headers={"Idempotency-Key": "huce-completion-20261025-02-environment-01"},
            json={"preview_id": preview["preview_id"], "confirmation_token": preview["confirmation_token"], "confirmed": True})
        response.raise_for_status(); save(OUT / "environment-activation-confirmation-01.json", response.json())
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            response = c.get(API + "/state"); response.raise_for_status(); state = response.json()
            if state["is_serving"] and state["desired"]["release_id"] == release["release_id"] and state["desired"]["generation"] == 22:
                break
            time.sleep(.5)
        else:
            raise RuntimeError("Activation recorded; live acknowledgement not verified")
        response = c.get(API + "/availability"); response.raise_for_status()
        save(OUT / "environment-activation-ready-01.json", {"at": datetime.now(UTC), "desired": state["desired"],
            "serving": state["serving"], "availability": response.json(), "unchanged_members": 113})
        print({"activated": True, "generation": 22, "release_id": release["release_id"]})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("mode", choices=["probes", "activate"])
    parser.add_argument("--attempt", choices=["01", "02"], default="02")
    args = parser.parse_args()
    asyncio.run(probes(args.attempt)) if args.mode == "probes" else activate()
