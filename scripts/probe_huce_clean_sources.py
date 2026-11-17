import asyncio
import json
from datetime import UTC, datetime

from complete_huce_corpus import SCOPE, actors, read
from knowledge_platform import TENANT, components, retain
from campus247.domain.retrieval import AuthorizedScope, RetrievalContext, SimulationPolicy


async def main():
    release = read(SCOPE / "candidate-release-06.json")
    versions = {row["source_id"]: row["version_id"] for row in release["members"]}
    questions = {"129ba0a6-652e-70b8-8532-8e63661262ce": "Học bổng STEM Quỹ Châu Á 2025-2026 có mức tiền và điều kiện gì?",
        "44c96321-30ae-72aa-8453-182aacdb2bed": "Hướng dẫn giảng viên chủ nhiệm nhập điểm rèn luyện sinh viên đăng nhập hệ thống nào?",
        "5c0b7c32-2740-720a-87a5-3db734608d01": "Theo hướng dẫn HUCE, tải Office 365 bằng tài khoản Nhà trường như thế nào?"}
    pool, _, _, runtime = await components(); _, owner = actors(); roles = frozenset(role.value for role in owner.roles)
    context = RetrievalContext(AuthorizedScope(TENANT, "HUCE", owner.subject_id, roles, roles, frozenset({"FIT"}), frozenset({"PUBLIC"})),
        "vi", datetime.now(UTC), SimulationPolicy.DENY, "a"*32)
    cases = []
    try:
        for source, question in questions.items():
            rows = await runtime.preview_search(owner, question, context, release["release_id"])
            found = [row for row in rows if row["document_version_id"] == versions[source]]
            passed = bool(found) and all("Previous Post" not in row["content_text"] and "Next Post" not in row["content_text"] and "cắp học bổng" not in row["content_text"] for row in found)
            cases.append({"source_id": source, "version_id": versions[source], "question": question, "items": rows, "passed": passed})
            print(json.dumps({"source_id": source, "passed": passed}), flush=True)
        retain(SCOPE / "clean-source-probes-01.json", {"release_id": release["release_id"], "cases": cases, "all_passed": all(row["passed"] for row in cases)})
    finally: await pool.close()


if __name__ == "__main__": asyncio.run(main())
