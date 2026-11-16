"""Source-specific retrieval probes and exact membership activation for K71KM."""
import argparse
import asyncio
import time
from contextlib import closing
from datetime import UTC, datetime

from audit_huce_rag_20261023 import API, client
from complete_huce_corpus import actors
from continue_huce_completion_20261025 import CORPUS, OUT, read, save, sha
from knowledge_platform import TENANT, components
from prepare_huce_mechanical_geometry_second import LINKS, MECHANICAL
from campus247.domain.retrieval import AuthorizedScope, RetrievalContext, SimulationPolicy


async def probes(attempt):
    release = read(CORPUS / "candidate-release-14.json")
    version = next(r["version_id"] for r in release["members"] if r["source_id"] == MECHANICAL)
    candidate = read(OUT / "mechanical-geometry-candidate-01.json")
    witness = candidate["extracted"]["curriculum_geometry"]
    cases = []
    for n in range(1, 10):
        terms = [code for cell in witness["cells"] if cell["semester"] == n for code in cell["course_codes"]]
        cases.append((f"semester_{n}", f"Theo kế hoạch K71KM K71, học kỳ {n} có những học phần nào?", terms, True))
    for i, (kind, a, b, _) in enumerate(LINKS):
        label, symbol = ("tiên quyết", "→") if kind == "PREREQUISITE" else ("song hành", "↔")
        cases.append((f"link_{i}", f"Theo sơ đồ K71KM K71, {a} và {b} có quan hệ {label} thế nào?", [a, b, symbol], True))
    cases += [
        ("wrong_cohort", "Theo sơ đồ K71KM K70, 010213 là tiên quyết của 010212?", [], False),
        ("wrong_semester", "Theo kế hoạch K71KM K71, học kỳ 10 có học phần nào?", [], False),
        ("wrong_course_semester", "Theo kế hoạch K71KM K71, học kỳ 9 có 280203 không?", [], False),
        ("unprinted_link", "Theo sơ đồ K71KM K71, 280203 là tiên quyết của 010212?", [], False),
        ("unverified_prior_study", "Theo sơ đồ K71KM K71, 010213 là học trước của 010212?", [], False),
        ("wrong_link_type", "Theo sơ đồ K71KM K71, 250102 là tiên quyết của 250103?", [], False),
    ]
    pool, _, _, runtime = await components(); _, owner = actors()
    roles = frozenset(r.value for r in owner.roles)
    context = RetrievalContext(AuthorizedScope(TENANT, "HUCE", owner.subject_id, roles, roles,
        frozenset({"FIT"}), frozenset({"PUBLIC"})), "vi", datetime.now(UTC), SimulationPolicy.DENY, "e"*32)
    results = []
    try:
        for name, question, terms, expected in cases:
            items = await runtime.preview_search(owner, question, context, release["release_id"])
            relevant = [item for item in items if item["document_version_id"] == version]
            found = any(all(t in item["content_text"] for t in terms) for item in relevant)
            hashes = all(sha(item["content_text"].encode()) == item["evidence_sha256"] for item in items)
            passed = (found if expected else not relevant) and hashes
            results.append({"name": name, "question": question, "expected_terms": terms, "expected_present": expected,
                "passed": passed, "items": items, "expected_version": version, "hashes_verified": hashes})
            print({"name": name, "passed": passed}, flush=True)
        save(OUT / f"mechanical-candidate-probes-{attempt}.json", {"release_id": release["release_id"], "cases": results,
            "all_passed": all(r["passed"] for r in results), "passed": sum(r["passed"] for r in results), "total": len(results)})
    finally:
        await pool.close()


def activate():
    release = read(CORPUS / "candidate-release-14.json")
    previous = read(CORPUS / "candidate-release-13.json")
    integrity = read(CORPUS / "candidate-integrity-09.json")
    probe = read(OUT / "mechanical-candidate-probes-02.json")
    assert integrity["all_passed"] and integrity["release_id"] == release["release_id"]
    assert probe["all_passed"] and probe["release_id"] == release["release_id"]
    members = {r["source_id"]: r for r in release["members"]}
    before_members = {r["source_id"]: r for r in previous["members"]}
    assert len(members) == 114 and members.keys() == before_members.keys()
    assert {k for k in members if members[k] != before_members[k]} == {MECHANICAL}
    assert release["expected_generation"] == 20
    with closing(client()) as c:
        response = c.get(API + "/state"); response.raise_for_status(); before = response.json()
        assert before["is_serving"] and before["desired"]["release_id"] == previous["release_id"]
        assert before["desired"]["generation"] == 20
        response = c.post(API + "/previews", json={"operation": "activate", "target_id": release["release_id"], "expected_generation": 20})
        response.raise_for_status(); preview = response.json()
        assert preview["payload"]["target_sha256"] == release["membership_sha256"]
        assert {r["source_id"]: r for r in preview["payload"]["members"]} == members
        save(OUT / "mechanical-activation-preview-01.json", {k: v for k, v in preview.items() if k != "confirmation_token"})
        response = c.post(API + "/confirmations", headers={"Idempotency-Key": "huce-completion-20261025-02-mechanical-01"},
            json={"preview_id": preview["preview_id"], "confirmation_token": preview["confirmation_token"], "confirmed": True})
        response.raise_for_status(); save(OUT / "mechanical-activation-confirmation-01.json", response.json())
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            response = c.get(API + "/state"); response.raise_for_status(); state = response.json()
            if state["is_serving"] and state["desired"]["release_id"] == release["release_id"] and state["desired"]["generation"] == 21:
                break
            time.sleep(.5)
        else:
            raise RuntimeError("Activation recorded; live acknowledgement not verified")
        response = c.get(API + "/availability"); response.raise_for_status()
        save(OUT / "mechanical-activation-ready-01.json", {"at": datetime.now(UTC), "desired": state["desired"],
            "serving": state["serving"], "availability": response.json(), "unchanged_members": 113})
        print({"activated": True, "generation": 21, "release_id": release["release_id"]})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("mode", choices=["probes", "activate"])
    parser.add_argument("--attempt", choices=["01", "02"], default="02")
    args = parser.parse_args()
    asyncio.run(probes(args.attempt)) if args.mode == "probes" else activate()
