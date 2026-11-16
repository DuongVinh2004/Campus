"""Verify71DS against its sealed candidate and normal activation controls."""
import argparse
import asyncio
import re
import time
from contextlib import closing
from datetime import UTC, datetime

from audit_huce_rag_20261023 import API, client
from complete_huce_corpus import actors
from continue_huce_completion_20261025 import CORPUS, OUT, read, save, sha
from knowledge_platform import TENANT, components
from review_huce_data_science_second import DATA_SCIENCE, LINKS
from campus247.domain.retrieval import AuthorizedScope, RetrievalContext, SimulationPolicy


def requirements():
    review = read(OUT / "data-science-71-reviewed-geometry-01.json")
    rows = []
    def add(name, question, terms=None):
        question = question.replace("hoạch71DS", "hoạch 71DS").replace("đồ71DS", "đồ 71DS")
        question = question.replace(",", ", ")
        for token in ("mã", "và", "của", "phần", "chất", "kỳ"):
            question = re.sub(r"(" + token + r")(?=\d)", r"\1 ", question)
        rows.append({"name": "ds_" + name, "question": question,
            "expected_terms": terms or [], "expected_present": terms is not None})
    for semester in range(1, 8):
        cells = [c for c in review["cells"] if c["semester"] == semester]
        terms = [code for c in cells for code in c["course_codes"]]
        terms += [c["text"] for c in cells if not c["course_codes"]]
        add(f"semester_{semester}", f"Theo kế hoạch71DS K71, học kỳ {semester} có những học phần nào?", terms)
    for i, (a, b, _) in enumerate(LINKS):
        add(f"link_{i}", f"Theo sơ đồ71DS K71, {a} là tiên quyết của {b} không?", [a, b, "→"])
    add("corequisite", "Theo sơ đồ71DS K71,941708 và941709 có quan hệ song hành không?", ["941708", "941709", "↔"])
    add("code_literal", "Theo đúng kế hoạch71DS K71,mã941704 có tên nguyên văn và mấy tín chỉ?", ["941704", "2", "GT ngành KHDL"])
    add("total", "Theo kế hoạch71DS K71,tổng tín chỉ in sẵn và phần loại trừ là gì?", ["130TC", "Không tính", "giáo dục thể chất", "Giáo dục quốc phòng"])
    for name, question in [
        ("wrong_cohort", "Theo kế hoạch71DS K70, học kỳ1 có những học phần nào?"),
        ("conflicting_cohort", "Theo kế hoạch71DS K71 và K70,941704 có bao nhiêu tín chỉ?"),
        ("wrong_semester", "Theo kế hoạch71DS K71, học kỳ2 có học phần941704 không?"),
        ("unprinted_credit", "Theo kế hoạch71DS K71,GD thể chất1 ghi mấy tín chỉ?"),
        ("placeholder_code", "Theo kế hoạch71DS K71,mã480101 ghi tên và mấy tín chỉ?"),
        ("unprinted_edge", "Theo sơ đồ71DS K71,941724 là tiên quyết của941706 không?"),
        ("wrong_relation", "Theo sơ đồ71DS K71,941708 là tiên quyết của941709 không?"),
        ("prior_study", "Theo sơ đồ71DS K71,400101 là học trước của407701 không?"),
        ("unknown_code", "Theo kế hoạch71DS K71,mã999999 có tên và mấy tín chỉ?"),
    ]:
        add(name, question)
    return rows


async def probes(attempt):
    release = read(CORPUS / "candidate-release-21.json")
    version = next(m["version_id"] for m in release["members"] if m["source_id"] == DATA_SCIENCE)
    pool, _, _, runtime = await components()
    _, owner = actors()
    roles = frozenset(r.value for r in owner.roles)
    context = RetrievalContext(AuthorizedScope(TENANT, "HUCE", owner.subject_id, roles, roles,
        frozenset({"FIT"}), frozenset({"PUBLIC"})), "vi", datetime.now(UTC), SimulationPolicy.DENY, "8"*32)
    rows = []
    try:
        for row in requirements():
            items = await runtime.preview_search(owner, row["question"], context, release["release_id"])
            own = [item for item in items if item["document_version_id"] == version]
            passed = (any(all(t in item["content_text"] for t in row["expected_terms"]) for item in own)
                if row["expected_present"] else not own)
            passed &= all(sha(item["content_text"].encode()) == item["evidence_sha256"] for item in items)
            rows.append({**row, "passed": bool(passed), "items": items})
            print({"name": row["name"], "passed": bool(passed)}, flush=True)
        save(OUT / f"data-science-candidate-probes-{attempt}.json", {"release_id": release["release_id"],
            "cases": rows, "count": len(rows), "passed": sum(r["passed"] for r in rows),
            "all_passed": all(r["passed"] for r in rows)})
    finally:
        await pool.close()


def activate():
    release = read(CORPUS / "candidate-release-21.json")
    previous = read(CORPUS / "candidate-release-20.json")
    integrity = read(CORPUS / "candidate-integrity-16.json")
    probe = read(OUT / "data-science-candidate-probes-02.json")
    regression = read(OUT / "live-verdict-44-01.json")
    assert regression["all_passed"] and regression["binding"]["release_id"] == previous["release_id"]
    assert integrity["all_passed"] and integrity["release_id"] == release["release_id"]
    assert probe["all_passed"] and probe["release_id"] == release["release_id"]
    members = {m["source_id"]: m for m in release["members"]}
    old = {m["source_id"]: m for m in previous["members"]}
    assert len(members) == 114 and members.keys() == old.keys()
    assert {k for k in members if members[k] != old[k]} == {DATA_SCIENCE}
    assert release["expected_generation"] == 23
    with closing(client()) as c:
        response = c.get(API + "/state"); response.raise_for_status(); state = response.json()
        assert state["is_serving"] and state["desired"]["release_id"] == previous["release_id"] and state["desired"]["generation"] == 23
        response = c.post(API + "/previews", json={"operation": "activate", "target_id": release["release_id"], "expected_generation": 23})
        response.raise_for_status(); preview = response.json()
        assert preview["payload"]["target_sha256"] == release["membership_sha256"]
        assert {m["source_id"]: m for m in preview["payload"]["members"]} == members
        save(OUT / "data-science-activation-preview-01.json", {k: v for k, v in preview.items() if k != "confirmation_token"})
        response = c.post(API + "/confirmations", headers={"Idempotency-Key": "huce-completion-20261025-02-data-science-01"},
            json={"preview_id": preview["preview_id"], "confirmation_token": preview["confirmation_token"], "confirmed": True})
        response.raise_for_status(); save(OUT / "data-science-activation-confirmation-01.json", response.json())
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            response = c.get(API + "/state"); response.raise_for_status(); state = response.json()
            if state["is_serving"] and state["desired"]["release_id"] == release["release_id"] and state["desired"]["generation"] == 24:
                break
            time.sleep(.5)
        else:
            raise RuntimeError("Activation recorded; live acknowledgement not verified")
        response = c.get(API + "/availability"); response.raise_for_status()
        save(OUT / "data-science-activation-ready-01.json", {"at": datetime.now(UTC), "desired": state["desired"],
            "serving": state["serving"], "availability": response.json(), "unchanged_members": 113})
        print({"activated": True, "generation": 24, "release_id": release["release_id"]})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["probes", "activate"])
    parser.add_argument("--attempt", choices=["01", "02"], default="02")
    args = parser.parse_args()
    asyncio.run(probes(args.attempt)) if args.mode == "probes" else activate()
