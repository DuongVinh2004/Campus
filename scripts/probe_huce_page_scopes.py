"""Live BGE probes for the three changed source scopes, before activation."""
import asyncio
import json
from datetime import UTC, datetime

from complete_huce_corpus import SCOPE, actors, read
from knowledge_platform import TENANT, components, retain
from campus247.application.knowledge.source_snapshot import read_snapshot, scope_allows
from campus247.domain.retrieval import AuthorizedScope, RetrievalContext, SimulationPolicy


async def main():
    release = read(SCOPE / "candidate-release-05.json")
    targets = {row["source_id"]: row["version_id"] for row in release["members"]}
    env = "8d1a03a4-7cc5-7903-834a-05084fbb6ed0"
    cs = "f634f981-e997-70dc-89ea-f78f8e327268"
    calendar = "c2454951-46ce-7a56-8421-ca4927bf3339"
    queries = [(env, "Kế hoạch Đại học B7 ngành Kỹ thuật môi trường K69MTC ghi khóa nào?", True),
        (env, "Kế hoạch Đại học B7 ngành Kỹ thuật môi trường K70MTC ghi khóa nào?", True),
        (cs, "Kế hoạch ngành Khoa học máy tính áp dụng cho khóa 69 là trình độ kỹ sư hay cử nhân?", True),
        (cs, "Kế hoạch ngành Khoa học máy tính áp dụng từ khóa 70 là trình độ kỹ sư hay cử nhân?", True),
        (calendar, "Kế hoạch giảng dạy và học tập năm học 2026-2027 của Khoa CNTT nhắc đến những khóa nào?", True),
        (calendar, "Theo kế hoạch giảng dạy và học tập năm học 2026-2027, K68 thi vào ngày nào?", False)]
    pool, _, platform, runtime = await components(); _, owner = actors()
    roles = frozenset(role.value for role in owner.roles)
    context = RetrievalContext(AuthorizedScope(TENANT, "HUCE", owner.subject_id, roles, roles,
        frozenset({"FIT"}), frozenset({"PUBLIC"})), "vi", datetime.now(UTC), SimulationPolicy.DENY, "a"*32)
    results = []
    try:
        for source_id, question, positive in queries:
            items = await runtime.preview_search(owner, question, context, release["release_id"])
            selected = [row for row in items if row["document_version_id"] == targets[source_id]]
            correct_scopes = True
            async with pool.acquire() as conn:
                version = await platform.repo.version(conn, targets[source_id]); scope = await read_snapshot(platform, conn, version)
                for row in selected:
                    row_scope = scope.get("_evidence_scopes", {}).get(row["evidence_sha256"], scope)
                    correct_scopes &= scope_allows(question, row_scope)
            passed = bool(selected) == positive and correct_scopes
            results.append({"source_id": source_id, "version_id": targets[source_id], "question": question,
                "expected_present": positive, "passed": passed, "items": items})
            print(json.dumps({"source_id": source_id, "expected_present": positive, "passed": passed}), flush=True)
        retain(SCOPE / "page-scope-probes-02.json", {"release_id": release["release_id"], "cases": results,
            "all_passed": all(row["passed"] for row in results), "changed_sources": [env, cs, calendar]})
    finally: await pool.close()


if __name__ == "__main__": asyncio.run(main())
