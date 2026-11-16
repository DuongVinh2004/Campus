"""Fresh optional chat memory; no extraction, automatic save or history import."""
from dataclasses import replace
import json
import re

from campus247.agent.prompts.composer import PromptBlock, TrustDomain
from campus247.application.document_request.certificates import CertificateError


def with_personal_context(turn, actor, memory, *, current_identity=None):
    if memory is None:
        return turn
    previous_guard = turn.context_guard
    fingerprint = []
    # Retrieval stays relevant and bounded to the current user query. No wildcard.
    terms = list(dict.fromkeys(re.findall(r'\w{3,80}', turn.query.casefold())))[:8]
    query = {'conversation_id': turn.session_id, 'terms': terms or [turn.query[:80]], 'limit': 3}

    def fresh():
        current = current_identity() if current_identity else actor
        if (current.tenant_id, current.subject_id, current.roles, current.session_id) != (
                actor.tenant_id, actor.subject_id, actor.roles, actor.session_id):
            raise CertificateError(403, 'MEMORY_ACTOR_CHANGED', 'Tài khoản hoặc phiên đã đổi')
        memory.scope(current)
        return current

    def retrieve():
        current = fresh()
        mode = memory.mode(current, turn.session_id)
        if mode == 'temporary':
            return None
        try:
            return memory.retrieve(current, query)
        except CertificateError as exc:
            if exc.code == 'MEMORY_DISABLED':
                return None
            raise

    def guard():
        if previous_guard:
            previous_guard()
        if memory.history_suppression_stamp(fresh(), turn.session_id) != suppression:
            raise CertificateError(409, 'MEMORY_CONTEXT_CHANGED', 'Suppression đã đổi; không tái dùng history cũ')
        value = retrieve()
        digest = value.get('sha256') if value else None
        if fingerprint and fingerprint[0] != digest:
            raise CertificateError(409, 'MEMORY_CONTEXT_CHANGED', 'Memory/consent đã đổi; cần soạn lại')

    def block():
        value = retrieve()
        fingerprint[:] = [value.get('sha256') if value else None]
        if not value or not value['items']:
            return None
        return memory.use(fresh(), query, value['sha256'], lambda projection: PromptBlock(
            TrustDomain.MEMORY, json.dumps(projection, ensure_ascii=False), 'actor-chat-memory'))

    temporary = memory.mode(fresh(), turn.session_id) == 'temporary'
    suppression = memory.history_suppression_stamp(fresh(), turn.session_id)
    return replace(turn, personal_memory=None if temporary else block,
        history=None if suppression else turn.history,
        presentation=None if temporary else turn.presentation, context_guard=guard)
