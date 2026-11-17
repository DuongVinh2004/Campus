"""Compare real ranking context on retained failed queries; no score bypass."""
import asyncio
import argparse
from dataclasses import replace
from datetime import UTC, datetime
from unittest.mock import patch

from complete_huce_corpus import actors
from continue_huce_completion_20261025 import CORPUS, OUT, read, save
from knowledge_platform import TENANT, components
from campus247.application.knowledge import document_reference
from campus247.application.retrieval import candidate_selection
from campus247.domain.retrieval import AuthorizedScope, RetrievalContext, SimulationPolicy


async def main(attempt="01", number="30", probe_attempt="01"):
    release = read(CORPUS / f"candidate-release-{number}.json")
    files = (f"stem-notice-details-candidate-probes-{probe_attempt}.json",) if attempt in {"04", "05"} else (f"cs-71-candidate-probes-{probe_attempt}.json", f"stem-notice-details-candidate-probes-{probe_attempt}.json")
    failures = [c for file in files
        for c in read(OUT / file)["cases"] if not c["passed"]]
    assert failures
    pool, _, _, runtime = await components()
    _, owner = actors()
    roles = frozenset(r.value for r in owner.roles)
    context = RetrievalContext(AuthorizedScope(TENANT, "HUCE", owner.subject_id, roles, roles,
        frozenset({"FIT"}), frozenset({"PUBLIC"})), "vi", datetime.now(UTC), SimulationPolicy.DENY, "e" * 32)
    original_rerank = runtime.reranker.rerank
    original_focus = document_reference.focused_named_document_question
    original_select = candidate_selection.select_parent_spans
    original_words = candidate_selection.words
    captured, results = [], []
    mode, expected_version = "", ""

    def focus(question):
        if mode == "notice_focus_and_reviewed_metadata" and "Theo thông báo học bổng STEM" in question:
            return question.partition(",")[2].strip()
        return original_focus(question)

    async def rerank(request):
        if mode in {"notice_metadata_without_title", "notice_native_context"}:
            adjusted = []
            for candidate in request.candidates:
                text = candidate.content_text
                if candidate.document_version_id == expected_version:
                    prefix = candidate.title + "\n" + "\n".join(candidate.section_path) + "\n"
                    assert text.startswith(prefix)
                    text = text[len(prefix):] if mode == "notice_native_context" else text[len(candidate.title) + 1:]
                adjusted.append(replace(candidate, content_text=text))
            request = replace(request, candidates=tuple(adjusted))
        if mode in {"edge_reviewed_metadata", "selection_reviewed_metadata"}:
            request = replace(request, candidates=tuple(replace(c,
                content_text=c.title + "\n" + "\n".join(c.section_path) + "\n" + c.content_text)
                if c.document_version_id == expected_version else c for c in request.candidates))
        result = await original_rerank(request)
        captured.append({"query": request.query.text,
            "inputs": [{"id": c.chunk_id, "version_id": c.document_version_id, "text": c.content_text} for c in request.candidates],
            "scores": [{"id": r.chunk_id, "score": r.score} for r in result.ranked]})
        return result

    def select(lexical, semantic, query, *, limit=3):
        if mode != "selection_reviewed_metadata":
            return original_select(lexical, semantic, query, limit=limit)
        originals = {str(r["id"]): r for r in lexical + semantic}
        def metadata(rows):
            return [{**r, "rerank_text": r["section_path"] + "\n" + r["rerank_text"]}
                if isinstance(r.get("section_path"), str) and r["section_path"] in r.get("verified_sections", set()) else r for r in rows]
        selected = original_select(metadata(lexical), metadata(semantic), query, limit=limit)
        return [originals[str(r["id"])] for r in selected]

    def phrase_words(text):
        tokens = original_words(text)
        return tokens + ["@phrase:" + " ".join(tokens[i:i+n]) for n in (2, 3) for i in range(len(tokens)-n+1)]

    runtime.reranker.rerank = rerank
    try:
        for case in failures:
            expected_version = case["expected_version"]
            modes = ("raw", "phrase_selection") if attempt == "05" else ("raw", "notice_metadata_without_title", "notice_native_context") if attempt == "04" else ("raw", "edge_reviewed_metadata" if case["name"] == "edge_e8" else "notice_focus_and_reviewed_metadata", "selection_reviewed_metadata")
            for mode in modes:
                captured.clear()
                with patch.object(document_reference, "focused_named_document_question", focus), patch.object(candidate_selection, "select_parent_spans", select), patch.object(candidate_selection, "words", phrase_words if mode == "phrase_selection" else original_words):
                    items = await runtime.preview_search(owner, case["question"], context, release["release_id"])
                own = [r for r in items if r["document_version_id"] == expected_version]
                passed = any(all(t in r["content_text"] for t in case["expected_terms"]) for r in own)
                results.append({"name": case["name"], "question": case["question"], "mode": mode,
                    "passed": passed, "expected_terms": case["expected_terms"], "items": items, "ranking": list(captured)})
                print({"name": case["name"], "mode": mode, "passed": passed}, flush=True)
        save(OUT / f"public-details-context-diagnostic-{attempt}.json", {"release_id": release["release_id"], "cases": results,
            "production_files_changed": False, "thresholds_or_deadlines_changed": False,
            "synthetic_scores_used": False, "activation_claimed": False})
    finally:
        runtime.reranker.rerank = original_rerank
        await pool.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", choices=("01", "02", "03", "04", "05"), default="01")
    parser.add_argument("--release", choices=("30", "31"), default="30")
    parser.add_argument("--probe-attempt", choices=("01", "02", "03"), default="01")
    args = parser.parse_args()
    asyncio.run(main(args.attempt, args.release, args.probe_attempt))
