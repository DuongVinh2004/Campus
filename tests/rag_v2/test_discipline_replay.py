"""Replay accepted v2 statements offline, with source rows built from recorded quotes."""
import json
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

import pytest

from campus247.agent.nodes.rag_v2 import GUARD_BLOCKED_MESSAGE
from campus247.agent.state import Terminal
from campus247.rag_v2.discipline import verified_general_discipline_rule
from campus247.rag_v2.types import Citation, Outcome, Statement
from tests.rag_v2.test_graph_integration import context, setup as build_stack
from tests.rag_v2.test_service import UnitIndex


ROOT = Path(__file__).resolve().parents[2]
RECORDS = json.loads((ROOT / "evals/results/rag-judge-20261028/runs/a9-disc-replay.json")
                    .read_text(encoding="utf-8"))["records"]
STATEMENT_REFS = {
    "T8-S-016": ((0, 1), (2,)),
    "T8-S-017": ((0, 1),),
    "T8-S-020": ((0,),) * 6 + ((1,),),
}


def replay_evidence(record):
    quotes, rows, citations = record["cited_quotes"], {}, []
    for i, quote in enumerate(quotes):
        # The short clause and its recorded parent quote belong to the same row.
        # Never add statement text or combine evidence from unrelated sources.
        content = max((parent for parent in quotes if quote in parent), key=len)
        digest = sha256(content.encode()).hexdigest()
        chunk = "chunk-" + digest
        rows[chunk] = {
            "chunk_id": chunk, "source_id": "doc-" + digest,
            "document_version_id": "version-" + digest,
            "content_text": content, "evidence_sha256": digest,
            "canonical_uri": "https://huce.edu.vn/quy-che", "simulation_label": False,
        }
        citations.append(Citation(str(i), (chunk,), rows[chunk]["source_id"],
            rows[chunk]["document_version_id"], "Quy chế HUCE", "Điều 1", 1, quote))
    statements = tuple(Statement(text, tuple(map(str, refs))) for text, refs in
        zip(record["statements"], STATEMENT_REFS[record["case_id"]], strict=True))
    return Outcome(record["kind"], record["text"], statements, tuple(citations)), rows


async def guarded_replay(outcome, rows):
    # Verification already happened in the recorded run. Replay the accepted Outcome
    # at the node boundary without generation, semantic calls, runtime or runner.
    stack = build_stack()

    async def accepted(*args, **kwargs):
        return outcome

    async def authorize(*args):
        return rows

    stack.node.service = SimpleNamespace(answer=accepted)
    stack.node.index = UnitIndex([])
    stack.node.authorize_sources = authorize
    state = await stack.workflow.arun(stack.turn, retrieval_context=context())
    assert not any(r.request_id.startswith("rag_v2_") for r in stack.gateway.requests)
    return state


@pytest.mark.asyncio
@pytest.mark.parametrize("record", RECORDS, ids=lambda r: r["case_id"])
@pytest.mark.parametrize("kind", ["answer", "partial"])
async def test_recorded_paraphrases_and_ocr_reach_the_guarded_answer(record, kind):
    outcome, rows = replay_evidence(record)
    outcome = replace(outcome, kind=kind)
    assert verified_general_discipline_rule(outcome, rows)
    assert any(s.text not in rows[c.chunk_ids[0]]["content_text"]
               for s in outcome.statements if "kỷ luật" in s.text
               for c in outcome.citations if c.unit_id in s.unit_ids)
    state = await guarded_replay(outcome, rows)
    assert state.terminal == Terminal.ANSWERED
    assert tuple(c.text for c in state.draft.grounded_claims) == tuple(record["statements"])
    assert "RAG_V2_" + kind.upper() in state.errors
    assert "[verified rule]" not in state.draft.text


@pytest.mark.asyncio
async def test_legal_verdict_beside_a_recorded_rule_still_fails_the_shared_guard():
    outcome, rows = replay_evidence(RECORDS[1])
    statement = outcome.statements[0]
    outcome = replace(outcome, statements=(replace(statement,
        text=statement.text + " Sinh viên vi phạm pháp luật."),))
    assert verified_general_discipline_rule(outcome, rows)
    state = await guarded_replay(outcome, rows)
    assert state.terminal == Terminal.ABSTAINED
    assert state.draft.text == GUARD_BLOCKED_MESSAGE
    assert not state.draft.grounded_claims


@pytest.mark.parametrize("kind", ["clarify", "refuse", "transient_error"])
def test_recorded_evidence_cannot_license_other_outcome_kinds(kind):
    outcome, rows = replay_evidence(RECORDS[0])
    assert not verified_general_discipline_rule(replace(outcome, kind=kind), rows)


@pytest.mark.parametrize("extra", ["mức khai trừ", "thời hạn 999 năm"])
def test_unrelated_rows_and_metadata_cannot_support_invented_terms(extra):
    outcome, rows = replay_evidence(RECORDS[1])
    statement = outcome.statements[0]
    outcome = replace(outcome, statements=(replace(statement,
        text=statement.text.rstrip(".") + " với " + extra + "."),))
    for row in rows.values():
        row["title"] = extra
    rows["unrelated"] = {**next(iter(rows.values())), "chunk_id": "unrelated",
                         "content_text": extra, "evidence_sha256": sha256(extra.encode()).hexdigest()}
    assert not verified_general_discipline_rule(outcome, rows)
