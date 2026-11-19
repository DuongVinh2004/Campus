"""Internal eval uses unchanged ownership/source validation and persistence."""
import sys
from dataclasses import replace
from pathlib import Path

import pytest
from campus247.agent.state import DraftResponse
from campus247.application.authorization.concealment import ResourceNotFoundError
from campus247.application.conversation.history import ConversationHistoryService
from campus247.presentation.chat import create_chat_router
from campus247.presentation.citation_source import create_citation_source_router
from fastapi import FastAPI

from tests.api.test_citation_source import setup
from tests.unit.conversation.test_stream_result import grounded_state

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "infra/local/rag-fixture"))
from m2_bulk_20261012_67 import Bulk


async def runtime():
    data = await setup()
    _, identity, messages, _, _, _, reader, _, sources = data
    histories = []
    async def agent(turn, signed):
        assert signed == identity and turn.user_id == identity.subject_id
        histories.append(len(turn.history.turns))
        state = grounded_state()
        excerpt = reader.value
        candidate = dict(state.tool_flow.candidates[0], source_id=excerpt.source_id,
            document_version_id=excerpt.document_version_id, chunk_id=excerpt.chunk_id,
            title=excerpt.title, canonical_uri=excerpt.canonical_uri, version_label=excerpt.version_label,
            locator=excerpt.locator, content_text=excerpt.content_text)
        return replace(state, request=turn, tool_flow=replace(state.tool_flow, candidates=[candidate]),
            draft=DraftResponse("Học phí mô phỏng 480.000 VNĐ/tín chỉ. [CIT-001]", is_grounded=True, gate_decision="pass"))
    app = FastAPI()
    app.include_router(create_chat_router(messages, trusted_agent_runner=agent,
        history_service=ConversationHistoryService(messages, minimize=lambda text: text)))
    app.include_router(create_citation_source_router(service=sources))
    return Bulk(app, identity), reader, histories


@pytest.mark.asyncio
async def test_internal_bulk_reuses_authorized_history_guard_persistence_and_source_service():
    bulk, reader, histories = await runtime()
    cid = await bulk.create()
    first = await bulk.turn(cid, "Học phí là bao nhiêu?")
    receipt = await bulk.verify(first)
    assert receipt["persisted_final_matches"] and receipt["HTTP_SSE_claimed"] is False
    second = await bulk.turn(cid, "Còn theo quy định đó?")
    await bulk.verify(second)
    assert histories == [0, 2] and reader.calls == 2


@pytest.mark.asyncio
async def test_internal_bulk_never_bypasses_current_source_or_conversation_ownership():
    bulk, reader, _ = await runtime()
    final = await bulk.turn(await bulk.create(), "Học phí?")
    reader.value = None
    with pytest.raises(ResourceNotFoundError):
        await bulk.verify(final)
    from campus247.domain.shared.values import generate_uuid7
    bulk.identity = replace(bulk.identity, subject_id=generate_uuid7())
    with pytest.raises(AssertionError):
        await bulk.turn(final["conversation_id"], "Other actor")
