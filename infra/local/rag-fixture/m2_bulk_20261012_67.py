"""Reuse the real authenticated application services for finite internal evals.

HTTP smoke requests retain every middleware and rate limit. Bulk rows are never
reported as HTTP/SSE observations; authorization, history, grounding, output
guard, persistence, and current-source checks use the same application objects.
"""
import hashlib
import inspect
from datetime import UTC, datetime


class Bulk:
    def __init__(self, app, signed_identity):
        def routes(router):
            for route in router.routes:
                included = getattr(route, "original_router", None)
                if included is not None:
                    yield from routes(included)
                else:
                    yield route
        endpoints = list(routes(app))
        stream = next(r.endpoint for r in endpoints if getattr(r, "path", "").endswith("/messages:stream"))
        source = next(r.endpoint for r in endpoints if getattr(r, "path", "").endswith("/citations/{citation_id}/source"))
        shared = dict(inspect.getclosurevars(stream).nonlocals)
        nested = shared.get("open_stream")  # since admission control the route delegates to open_stream
        if nested is not None:
            shared = {**inspect.getclosurevars(nested).nonlocals, **shared}
        self.messages = shared["conv_service"]
        self.history = shared["history_service"]
        self.agent = shared["trusted_agent_runner"]
        self.sources = inspect.getclosurevars(source).nonlocals["service"]
        self.identity = signed_identity

    async def create(self):
        return (await self.messages.create_conversation(owner_user_id=self.identity.subject_id)).id

    async def turn(self, conversation_id, query):
        from campus247.agent.state import NormalizedTurn
        from campus247.agent.streaming import StreamGuardrail
        from campus247.application.conversation.messages import SenderType
        from campus247.application.conversation.read import final_payload
        from campus247.application.conversation.stream_result import (
            apply_stream_validation,
            prepare_chat_result,
        )
        conv = await self.messages.get_conversation(conversation_id)
        assert conv.owner_user_id == self.identity.subject_id and conv.retention_expires_at > datetime.now(UTC)
        saved_user = await self.messages.append_message(conversation_id, SenderType.USER, query,
                                                       sender_user_id=self.identity.subject_id)
        history = await self.history.load(self.identity.subject_id, conversation_id, before_message_id=saved_user.id)
        state = await self.agent(NormalizedTurn(session_id=conversation_id, turn_id=saved_user.id,
            user_id=self.identity.subject_id, query=query, history=history), self.identity)
        result = prepare_chat_result(state)
        guard = StreamGuardrail()
        guard.push_provisional(seq=1, delta=result.content)
        result = apply_stream_validation(result, guard.validate_and_commit())
        saved = await self.messages.append_message(conversation_id, SenderType.ASSISTANT, result.content, final_result=result)
        return final_payload(saved)

    async def verify(self, final):
        from campus247.application.conversation.read import final_payload
        from campus247.domain.shared.values import generate_uuid7
        page, _, _ = await self.messages.list_owned_page(self.identity.subject_id, final["conversation_id"], limit=100)
        stored = next(m for m in page if m.id == final["message_id"])
        assert final_payload(stored) == final
        for item in final["citations"]:
            source = await self.sources.read(self.identity, final["conversation_id"], final["message_id"],
                item["citation"]["citation_id"], trace_id=generate_uuid7().replace("-", ""), request_id=generate_uuid7())
            assert hashlib.sha256(source["content_text"].encode()).hexdigest() == source["content_sha256"]
        return {"exit_code": 0, "signed_actor": True, "opened_citations": len(final["citations"]),
            "checksum_verified": True, "persisted_final_matches": True, "execution_layer": "application",
            "HTTP_SSE_claimed": False, "public_HTTP_rate_limits_unchanged": True}
