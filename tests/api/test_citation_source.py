"""Ownership, stored citation binding, current eligibility and fail-closed reads."""
import hashlib
import json
import sys
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "services/api/src"), str(ROOT / "packages/synthetic/src")]

from campus247.application.audit.writer import AuditWriter
from campus247.application.authorization.concealment import ResourceNotFoundError
from campus247.application.conversation.citation_source import CitationSourceService, CitationSourceUnavailable
from campus247.application.conversation.messages import ConversationMessageService
from campus247.application.conversation.stream_result import FinalChatResult, StreamCitation
from campus247.application.retrieval.context import RetrievalContextFactory, ResolvedRetrievalScope
from campus247.application.retrieval.filters import RetrievalFilterCompiler
from campus247.domain.shared.values import generate_uuid7
from campus247.infrastructure.identity.mock import SyntheticIdentityAdapter
from campus247.infrastructure.retrieval.postgres_citation_source import PostgresCitationSourceReader
from campus247.ports.citation_source import CitationSourceExcerpt
from campus247.presentation.citation_source import create_citation_source_router
from campus247.presentation.identity import IdentityMiddleware

ACTOR = "4b419a1b-6d41-7dfb-8943-2edd9f071385"


async def setup(*, response_class="grounded_answer"):
    adapter = SyntheticIdentityAdapter(secret_key="source-read-test-only", tenant_id="synthetic-institution")
    identity = adapter.resolve_token(adapter.mint_token(ACTOR))
    class Resolver:
        def resolve(self, _):
            return ResolvedRetrievalScope("synthetic-institution", "HUCE", frozenset({"STUDENT"}), frozenset({"FIT"}), frozenset({"IT_STANDARD"}))
    factory = RetrievalContextFactory(scope_resolver=Resolver(), configured_tenant_id="synthetic-institution", configured_campus_id="HUCE")
    conversations = ConversationMessageService()
    conv = await conversations.create_conversation(owner_user_id=ACTOR)
    text = "Học phí mô phỏng 480.000 VNĐ/tín chỉ. " * 20
    citation = dict(citation_id=generate_uuid7(), source_id=generate_uuid7(), document_version_id=generate_uuid7(),
        chunk_id=generate_uuid7(), source_title="Quy định học phí mô phỏng", canonical_uri="synthetic://campus247/tuition",
        version_label="simulation-v1", source_status="SYNTHETIC", locator={"section_path":"Học phí"}, quote=text[:500])
    final = FinalChatResult("answered", response_class, "480.000 VNĐ/tín chỉ [CIT-001]",
        (StreamCitation("CIT-001", json.dumps(citation)),))
    message = await conversations.append_message(conv.id, "ASSISTANT", final.content, final_result=final)
    excerpt = CitationSourceExcerpt(citation["source_id"], citation["document_version_id"], citation["chunk_id"],
        citation["source_title"], citation["canonical_uri"], citation["version_label"], "SYNTHETIC", citation["locator"],
        "HUCE Demo", datetime.now(timezone.utc)-timedelta(days=1), None, text, hashlib.sha256(text.encode()).hexdigest())
    class Reader:
        calls = 0
        value = excerpt
        async def read(self, source, version, chunk, *, context):
            self.calls += 1
            assert (source, version, chunk) == (excerpt.source_id, excerpt.document_version_id, excerpt.chunk_id)
            assert context.authorized_scope.actor_id == ACTOR
            return self.value
    reader, audit = Reader(), AuditWriter()
    service = CitationSourceService(conversations=conversations, context_factory=factory, reader=reader, audit_writer=audit, allow_simulation=True)
    return adapter, identity, conversations, conv, message, citation, reader, audit, service


async def read(data, **overrides):
    _, identity, _, conv, msg, citation, _, _, service = data
    return await service.read(overrides.get("identity", identity), conv.id,
        overrides.get("message_id", msg.id), overrides.get("citation_id", citation["citation_id"]),
        trace_id="1"*32, request_id=generate_uuid7())


@pytest.mark.asyncio
async def test_original_excerpt_no_message_writes_and_safe_audit():
    data = await setup()
    result = await read(data)
    assert result["content_text"] == data[6].value.content_text
    assert result["citation"] == data[5] and result["representation"] == "CITED_CHUNK"
    assert result["effective_from"].endswith("Z")
    assert len(await data[2].list_messages(data[3].id)) == 1
    event = data[7].get_history()[0]
    assert event.outcome == "ALLOWED" and event.resource_id is None and event.metadata_safe is None


@pytest.mark.asyncio
async def test_partial_answer_citations_open_original_source_and_keep_owner_check():
    data = await setup(response_class="partial_answer")
    result = await read(data)
    assert result["content_sha256"] == hashlib.sha256(result["content_text"].encode()).hexdigest()
    calls = data[6].calls
    with pytest.raises(ResourceNotFoundError):
        await read(data, identity=replace(data[1], subject_id=generate_uuid7()))
    assert data[6].calls == calls


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["owner", "retention", "redacted", "non_final", "citation", "message"])
async def test_concealed_bindings_do_not_read_source(case):
    data = await setup()
    _, identity, conversations, conv, message, citation, reader, audit, _ = data
    overrides = {}
    if case == "owner":
        overrides["identity"] = replace(identity, subject_id=generate_uuid7())
    elif case == "retention":
        await conversations._repo.save_conversation(replace(conv, retention_expires_at=datetime.now(timezone.utc)-timedelta(seconds=1)))
    elif case in {"redacted", "non_final"}:
        conversations._repo._messages[conv.id] = [replace(message, **({"redacted_at":datetime.now(timezone.utc)} if case == "redacted" else {"finish_status":None,"response_class":None}))]
    else:
        overrides[case+"_id"] = generate_uuid7()
    with pytest.raises(ResourceNotFoundError):
        await read(data, **overrides)
    assert reader.calls == 0 and audit.get_history()[-1].outcome == "DENIED"


@pytest.mark.asyncio
async def test_withdrawn_out_of_scope_or_revoked_grants_are_concealed():
    data = await setup()
    data[6].value = None  # Reader prefilters publication, applicability and current actor grants.
    with pytest.raises(ResourceNotFoundError):
        await read(data)


@pytest.mark.asyncio
@pytest.mark.parametrize("field", ["content_sha256", "content_text", "locator", "version_label", "effective_until"])
async def test_corrupt_or_stale_source_fails_closed(field):
    data = await setup()
    values = {"content_sha256":"0"*64, "content_text":"Unverified text", "locator":{"section_path":"Other"},
        "version_label":"changed", "effective_until":datetime.now(timezone.utc)-timedelta(seconds=1)}
    data[6].value = replace(data[6].value, **{field:values[field]})
    with pytest.raises(CitationSourceUnavailable):
        await read(data)
    assert data[7].get_history()[-1].outcome == "FAILED"


@pytest.mark.asyncio
async def test_expired_identity_never_reads_source():
    data = await setup()
    with pytest.raises(CitationSourceUnavailable):
        await read(data, identity=replace(data[1], auth_time=datetime.now(timezone.utc)-timedelta(hours=2), expires_at=datetime.now(timezone.utc)-timedelta(hours=1)))
    assert data[6].calls == 0


@pytest.mark.asyncio
async def test_auth_transport_and_unconfigured_dependency():
    data = await setup()
    adapter, _, _, conv, message, citation, _, _, service = data
    app = FastAPI()
    app.add_middleware(IdentityMiddleware, adapter=adapter)
    app.include_router(create_citation_source_router(service=service))
    path = f"/v1/conversations/{conv.id}/messages/{message.id}/citations/{citation['citation_id']}/source"
    with TestClient(app) as client:
        assert client.get(path).status_code == 401
        response = client.get(path, headers={"Authorization": "Bearer "+adapter.mint_token(ACTOR)})
        assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
        service._reader = None
        assert client.get(path, headers={"Authorization":"Bearer "+adapter.mint_token(ACTOR)}).status_code == 503


@pytest.mark.asyncio
async def test_sql_uses_shared_prefilter_readonly_and_actor_revalidation():
    data = await setup()
    context = data[8]._factory.create(data[1], effective_at=datetime.now(timezone.utc), locale="vi-VN", trace_id="1"*32, allow_simulation=True)
    class Connection:
        def transaction(self, *, readonly):
            assert readonly is True
            return self
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def fetchrow(self, sql, *args):
            assert "s.approval_status = 'APPROVED' AND v.status = 'PUBLISHED'" in sql
            assert "v.effective_until > $3" in sql and "s.audiences &&" in sql
            assert "u.status = 'ACTIVE'" in sql and "role_binding" in sql and "student_profile" in sql
            assert args[-2:] == (ACTOR, ["STUDENT"]) and "LIMIT 1" in sql
            return None
    class Pool:
        def acquire(self, **_): return Connection()
    reader = PostgresCitationSourceReader(pool=Pool(), filter_compiler=RetrievalFilterCompiler(tenant_id="synthetic-institution", campus_id="HUCE", profile_allows_simulation=True))
    assert await reader.read(data[5]["source_id"], data[5]["document_version_id"], data[5]["chunk_id"], context=context) is None
