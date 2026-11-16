"""Compare real BGE queries without changing serving code or relevance gates."""
import asyncio
import argparse
import re
from dataclasses import replace
from datetime import UTC, datetime
from unittest.mock import patch

from complete_huce_corpus import actors
from continue_huce_completion_20261025 import CORPUS, OUT, read, save
from knowledge_platform import TENANT, components
from verify_huce_stem_forms_second import CASES
from campus247.domain.retrieval import AuthorizedScope, RetrievalContext, RetrievalQuery, SimulationPolicy


async def main(contextual=False, original_rerank=False):
    pool, _, _, runtime = await components()
    _, owner = actors()
    roles = frozenset(r.value for r in owner.roles)
    context = RetrievalContext(AuthorizedScope(TENANT, "HUCE", owner.subject_id, roles, roles,
        frozenset({"FIT"}), frozenset({"PUBLIC"})), "vi", datetime.now(UTC), SimulationPolicy.DENY, "a"*32)
    release = read(CORPUS / "candidate-release-22.json")
    rows = []
    original = runtime.reranker.rerank
    captured = []
    current_question = ""
    async def capture(request):
        if original_rerank:
            request = replace(request, query=RetrievalQuery(re.sub(r"(?i)\b(ý|và|mục|câu)(?=\d)", r"\1 ", current_question)))
        if contextual:
            request = replace(request, candidates=tuple(replace(c,
                content_text=c.title + "\n" + "\n".join(c.section_path) + "\n" + c.content_text)
                for c in request.candidates))
        result = await original(request)
        captured.append({"query": request.query.text, "inputs": [
            {"id": c.chunk_id, "text": c.content_text} for c in request.candidates],
            "ranked": [{"id": r.chunk_id, "score": r.score} for r in result.ranked]})
        return result
    runtime.reranker.rerank = capture
    try:
        for mode in (("focused_search_original_rerank",) if original_rerank else ("current_focus", "full_original_question")):
            for name, question, terms, positive in CASES:
                if not original_rerank and name not in {"stem_application_prompts", "stem_cv", "stem_family"}:
                    continue
                current_question = question
                captured.clear()
                if mode == "full_original_question":
                    with patch("campus247.application.knowledge.document_reference.focused_named_document_question", lambda q: q):
                        items = await runtime.preview_search(owner, question, context, release["release_id"])
                else:
                    items = await runtime.preview_search(owner, question, context, release["release_id"])
                passed = (any(all(t in i["content_text"] for t in terms) for i in items) if positive else not items)
                rows.append({"name": name, "mode": mode, "passed": passed, "items": items,
                    "actual_rerank": list(captured)})
                print({"name": name, "mode": mode, "passed": passed}, flush=True)
        suffix = "05" if original_rerank else "04" if contextual else "03"
        save(OUT / f"stem-query-context-diagnostic-{suffix}.json", {"release_id": release["release_id"],
            "cases": rows, "serving_code_changed": False, "relevance_threshold_changed": False,
            "sealed_title_and_section_added_to_diagnostic_rerank_input": contextual,
            "original_question_for_rerank_only": original_rerank,
            "synthetic_scores_used": False, "activation_claimed": False})
    finally:
        runtime.reranker.rerank = original
        await pool.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--contextual", action="store_true")
    parser.add_argument("--rerank-original", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(args.contextual, args.rerank_original))
