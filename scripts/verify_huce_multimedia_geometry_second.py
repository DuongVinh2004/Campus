"""Verify and activate only the reviewed multimedia geometry source."""
import argparse
import asyncio
import json
import time
from contextlib import closing
from datetime import UTC, datetime

from audit_huce_rag_20261023 import API, client
from complete_huce_corpus import actors
from continue_huce_completion_20261025 import CORPUS, OUT, read, save, sha
from knowledge_platform import TENANT, components
from review_huce_curriculum_geometry import MULTIMEDIA
from campus247.domain.retrieval import AuthorizedScope, RetrievalContext, SimulationPolicy

CASES = [
    ("semester_1", "Theo kế hoạch 71CNDPT K71, học kỳ 1 có học phần 531800 không?", ["531800"], True),
    ("semester_4", "Theo kế hoạch 71CNDPT K71, học kỳ 4 học phần 531816 có tên và số tín chỉ thế nào?", ["531816"], True),
    ("elective_1", "Theo kế hoạch 71CNDPT K71, học kỳ 5 nhóm tự chọn 1 ghi những học phần nào?", ["531833", "531834"], True),
    ("elective_2", "Theo kế hoạch 71CNDPT K71, học kỳ 6 nhóm tự chọn 2 ghi những học phần nào?", ["531835", "531836"], True),
    ("prerequisite_game", "Theo sơ đồ 71CNDPT K71, 531816 là học phần tiên quyết của 451802 không?", ["531816", "451802", "→"], True),
    ("prerequisite_politics", "Theo sơ đồ 71CNDPT K71, 428801 là học phần tiên quyết của 428802 không?", ["428801", "428802", "→"], True),
    ("corequisite_vr", "Theo sơ đồ 71CNDPT K71, 531829 và 531830 có quan hệ song hành không?", ["531829", "531830", "↔"], True),
    ("corequisite_audio", "Theo sơ đồ 71CNDPT K71, 531819 và 531820 có quan hệ song hành không?", ["531819", "531820", "↔"], True),
    ("unproven_cohort", "Theo sơ đồ 71CNDPT K70, 531819 và 531820 có quan hệ song hành không?", [], False),
    ("wrong_semester", "Theo kế hoạch 71CNDPT K71, học kỳ 8 học phần 531800 có tên và số tín chỉ thế nào?", [], False),
    ("unverified_prior_study", "Theo sơ đồ 71CNDPT K71, 531816 là học phần học trước của 451802 không?", [], False),
    ("unprinted_edge", "Theo sơ đồ 71CNDPT K71, 531800 là học phần tiên quyết của 531881 không?", [], False),
    ("unlabelled_pe_credit", "Theo đúng sơ đồ 71CNDPT K71, GD thể chất 2 có phải là môn 2 tín chỉ không?", [], False),
]


async def probes(number, attempt):
    release = read(CORPUS / f"candidate-release-{number}.json")
    version = next(r["version_id"] for r in release["members"] if r["source_id"] == MULTIMEDIA)
    pool, _, _, runtime = await components(); _, owner = actors()
    roles = frozenset(r.value for r in owner.roles)
    context = RetrievalContext(AuthorizedScope(TENANT, "HUCE", owner.subject_id, roles, roles, frozenset({"FIT"}),
        frozenset({"PUBLIC"})), "vi", datetime.now(UTC), SimulationPolicy.DENY, "d"*32)
    cases = []
    try:
        for name, question, terms, expected in CASES:
            items = await runtime.preview_search(owner, question, context, release["release_id"])
            relevant = [r for r in items if r["document_version_id"] == version]
            found = any(all(t in r["content_text"] for t in terms) for r in relevant)
            hashes = all(sha(r["content_text"].encode()) == r["evidence_sha256"] for r in items)
            passed = (found if expected else not relevant) and hashes
            cases.append({"name": name, "question": question, "expected_terms": terms, "expected_present": expected,
                "passed": passed, "items": items, "expected_version": version, "hashes_verified": hashes})
            print(json.dumps({"name": name, "passed": passed}), flush=True)
        save(OUT / f"multimedia-candidate-probes-{attempt}.json", {"release_id": release["release_id"], "cases": cases,
            "all_passed": all(c["passed"] for c in cases), "passed": sum(c["passed"] for c in cases), "total": len(cases)})
    finally:
        await pool.close()


def activate(number, attempt):
    previous_number, integrity_number, expected_generation = {"12": ("10", "07", 18), "13": ("12", "08", 19)}[number]
    release = read(CORPUS / f"candidate-release-{number}.json"); previous = read(CORPUS / f"candidate-release-{previous_number}.json")
    integrity = read(CORPUS / f"candidate-integrity-{integrity_number}.json")
    probes = read(OUT / f"multimedia-candidate-probes-{attempt}.json")
    assert integrity["all_passed"] and integrity["release_id"] == release["release_id"]
    assert probes["all_passed"] and probes["release_id"] == release["release_id"]
    before_members = {r["source_id"]: r for r in previous["members"]}; members = {r["source_id"]: r for r in release["members"]}
    assert members.keys() == before_members.keys() and len(members) == 114
    assert {k for k in members if members[k] != before_members[k]} == {MULTIMEDIA}
    with closing(client()) as c:
        before = c.get(API+"/state"); before.raise_for_status(); before = before.json()
        assert before["desired"]["release_id"] == previous["release_id"] and before["desired"]["generation"] == release["expected_generation"] == expected_generation
        response = c.post(API+"/previews", json={"operation": "activate", "target_id": release["release_id"], "expected_generation": expected_generation})
        response.raise_for_status(); preview = response.json()
        assert preview["payload"]["target_sha256"] == release["membership_sha256"]
        assert {r["source_id"]: r for r in preview["payload"]["members"]} == members
        save(OUT / f"multimedia-activation-preview-{attempt}.json", {k:v for k,v in preview.items() if k != "confirmation_token"})
        response = c.post(API+"/confirmations", headers={"Idempotency-Key": "huce-completion-20261025-02-multimedia-"+attempt},
            json={"preview_id": preview["preview_id"], "confirmation_token": preview["confirmation_token"], "confirmed": True})
        response.raise_for_status(); save(OUT / f"multimedia-activation-confirmation-{attempt}.json", response.json())
        until = time.monotonic()+45
        while time.monotonic() < until:
            response = c.get(API+"/state"); response.raise_for_status(); state = response.json()
            if state["is_serving"] and state["desired"]["release_id"] == release["release_id"] and state["desired"]["generation"] == expected_generation+1:
                break
            time.sleep(.5)
        else:
            raise RuntimeError("Activation recorded; live acknowledgement not verified")
        response = c.get(API+"/availability"); response.raise_for_status()
        save(OUT / f"multimedia-activation-ready-{attempt}.json", {"at": datetime.now(UTC), "desired": state["desired"],
            "serving": state["serving"], "availability": response.json(), "unchanged_members": 113})
        print({"activated": True, "generation": expected_generation+1, "release_id": release["release_id"]})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("mode", choices=["probes", "activate"])
    parser.add_argument("--release", choices=["12", "13"], default="13")
    parser.add_argument("--attempt", choices=["01", "02"], default="02")
    args = parser.parse_args()
    asyncio.run(probes(args.release, args.attempt)) if args.mode == "probes" else activate(args.release, args.attempt)
