"""Split an already reviewed legend from semester loads, preserving every byte."""
import argparse
import asyncio
import json
import time
from contextlib import closing
from copy import deepcopy
from datetime import UTC, datetime

from audit_huce_rag_20261023 import API, client
from complete_huce_corpus import SCOPE, actors, read
from knowledge_platform import ROOT, TENANT, components, retain
from prepare_huce_evidence_20261025 import OUT
from campus247.application.knowledge.platform_models import digest
from campus247.application.knowledge.source_snapshot import validate_snapshot
from campus247.domain.retrieval import AuthorizedScope, RetrievalContext, SimulationPolicy

MATERIALS = "dc43e7f5-466f-7ce3-8fe2-a10a0c809d9b"


def prepare():
    plan = read(SCOPE / "candidate-plan-07.json")
    entry = next(r for r in plan["sources"] if r["source_id"] == MATERIALS)
    candidate = deepcopy(read(ROOT / entry["candidate"]))
    members = read(SCOPE / "candidate-release-07.json")["members"]
    candidate["previous_version_id"] = next(r["version_id"] for r in members if r["source_id"] == MATERIALS)
    block = candidate["extracted"]["blocks"][0]
    text = block["text"]
    split = [0, text.index("HK 1"), text.index("Mã HP-X-Y"), len(text)]
    candidate["pages"] = []
    for n, (start, end) in enumerate(zip(split, split[1:])):
        candidate["pages"].append({"block_id": block["block_id"], "page": block["page"],
            "char_start": start, "char_end": end, "text": text[start:end],
            "text_sha256": digest(text[start:end].encode()),
            "section": candidate["title"] + " · trang 1 · " + ["tiêu đề", "tổng từng học kỳ", "chú giải mã HP-X-Y"][n]})
    assert "".join(r["text"] for r in candidate["pages"]) == text
    candidate["applicability"]["reviewed_at"] = datetime.now(UTC).isoformat()
    validate_snapshot(candidate, candidate["extracted"], original_sha256=candidate["original_sha256"],
        effective_from=datetime.fromisoformat(candidate["applicability"]["reviewed_at"]))
    target = OUT / "materials-legend-candidate-01.json"
    retain(target, candidate)
    entry.update(candidate=str(target.relative_to(ROOT)), candidate_sha256=digest(target.read_bytes()), parents=3)
    retain(SCOPE / "candidate-plan-08.json", plan)
    print(json.dumps({"changed_source": MATERIALS, "exact_spans": 3, "content_added_or_removed": False}))


async def verify():
    import verify_huce_corpus_integrity as integrity
    await integrity.main("08", "05")
    release = read(SCOPE / "candidate-release-08.json")
    old = read(SCOPE / "candidate-release-07.json")
    previous = {r["source_id"]: r for r in old["members"]}
    members = {r["source_id"]: r for r in release["members"]}
    assert {key for key in members if members[key] != previous[key]} == {MATERIALS}
    pool, _, _, runtime = await components()
    _, owner = actors(); roles = frozenset(r.value for r in owner.roles)
    context = RetrievalContext(AuthorizedScope(TENANT, "HUCE", owner.subject_id, roles, roles,
        frozenset({"FIT"}), frozenset({"PUBLIC"})), "vi", datetime.now(UTC), SimulationPolicy.DENY, "f"*32)
    results = []
    try:
        for query, positive in [
            ("Theo kế hoạch kỹ sư Công nghệ kỹ thuật vật liệu xây dựng K71 bản 2025, X và Y trong chú giải Mã HP-X-Y là gì?", True),
            ("Kế hoạch kỹ sư Công nghệ kỹ thuật vật liệu xây dựng K71 năm 2025 chú giải X và Y của mã HP là gì?", True),
            ("Theo kế hoạch kỹ sư Công nghệ kỹ thuật vật liệu xây dựng K70 bản 2025, X và Y trong chú giải Mã HP-X-Y là gì?", False)]:
            items = await runtime.preview_search(owner, query, context, release["release_id"])
            selected = [r for r in items if r["document_version_id"] == members[MATERIALS]["version_id"]]
            passed = bool(selected) == positive
            results.append({"query": query, "expected_present": positive, "passed": passed, "items": items})
            print(json.dumps({"expected_present": positive, "passed": passed}), flush=True)
        result = {"release_id": release["release_id"], "cases": results, "all_passed": all(r["passed"] for r in results)}
        retain(OUT / "legend-repair-probes-01.json", result)
        assert result["all_passed"]
    finally:
        await pool.close()


def activate():
    release = read(SCOPE / "candidate-release-08.json")
    assert read(OUT / "legend-repair-probes-01.json")["all_passed"]
    assert read(SCOPE / "candidate-integrity-05.json")["all_passed"]
    with closing(client()) as c:
        state = c.get(API + "/state").json()
        assert state["desired"]["release_id"] == read(SCOPE / "candidate-release-07.json")["release_id"]
        assert state["desired"]["generation"] == 16
        response = c.post(API + "/previews", json={"operation": "activate", "target_id": release["release_id"], "expected_generation": 16})
        response.raise_for_status(); preview = response.json()
        assert preview["payload"]["target_sha256"] == release["membership_sha256"]
        assert {r["source_id"]: r for r in preview["payload"]["members"]} == {r["source_id"]: r for r in release["members"]}
        retain(OUT / "legend-activation-preview-01.json", {k: v for k, v in preview.items() if k != "confirmation_token"})
        response = c.post(API + "/confirmations", headers={"Idempotency-Key": "huce-legend-repair-20261025-01"},
            json={"preview_id": preview["preview_id"], "confirmation_token": preview["confirmation_token"], "confirmed": True})
        response.raise_for_status(); retain(OUT / "legend-activation-confirmation-01.json", response.json())
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            state = c.get(API + "/state").json()
            if state["is_serving"] and state["desired"]["release_id"] == release["release_id"] and state["desired"]["generation"] == 17:
                break
            time.sleep(.5)
        else:
            raise RuntimeError("Runtime acknowledgement not verified")
        retain(OUT / "legend-activation-ready-01.json", {"desired": state["desired"], "serving": state["serving"],
            "availability": c.get(API + "/availability").json(), "unchanged_members": 113})
        print(json.dumps({"generation": 17, "release_id": release["release_id"]}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("prepare", "verify", "activate"))
    args = parser.parse_args()
    if args.mode == "verify":
        asyncio.run(verify())
    elif args.mode == "prepare":
        prepare()
    else:
        activate()
