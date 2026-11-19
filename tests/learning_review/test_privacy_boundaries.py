"""Independent regressions for revocation and list/transport authorization."""
import copy
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from campus247.application.learning.service import LearningService
from campus247.domain.learning import LearningError
from campus247.domain.shared.values import generate_uuid7
from campus247.ports.identity import IdentityContext, IdentityRole
from campus247.ports.learning_repository import empty_state
from campus247.presentation.learning import create_learning_router


class IsolatedMemoryRepository:
    def __init__(self, state):
        self.state = state

    @asynccontextmanager
    async def transaction(self):
        pending = copy.deepcopy(self.state)
        yield pending
        self.state = pending


def actor(role, subject=None):
    instant = datetime.now(timezone.utc)
    return IdentityContext(subject_id=subject or generate_uuid7(), external_subject="independent-review", issuer="review", roles=(IdentityRole(role),), display_name="Synthetic review actor", auth_time=instant, expires_at=instant + timedelta(hours=1), tenant_id="independent-learning-review", session_id=generate_uuid7(), student_code="SYN-REVIEW" if role == "STUDENT" else None)


@pytest.fixture
def sample():
    teacher, student = actor("LECTURER"), actor("STUDENT")
    offering, material, draft, published, private_question, presentation = (generate_uuid7() for _ in range(6))
    state = empty_state()
    state["offerings"][offering] = {"id": offering, "status": "ACTIVE", "download_allowed": True}
    for person, role in [(teacher, "INSTRUCTOR"), (student, "STUDENT")]:
        member_id = generate_uuid7()
        state["members"][member_id] = {"id": member_id, "offering_id": offering, "actor_subject_id": person.subject_id, "role": role, "status": "ACTIVE"}
    state["materials"][material] = {"id": material, "offering_id": offering, "visibility": "VISIBLE", "title": "Synthetic private draft", "current_published_version_id": published}
    for version_id, publication in [(draft, "DRAFT"), (published, "PUBLISHED")]:
        state["versions"][version_id] = {"id": version_id, "material_id": material, "version_no": 1 if version_id == draft else 2, "processing_state": "READY", "publication_state": publication, "page_count": 3, "revision": 1}
    state["questions"][private_question] = {"id": private_question, "version_id": published, "author_id": student.subject_id, "visibility": "PRIVATE_TO_INSTRUCTORS", "status": "ACTIVE", "body": "Private student question"}
    state["presentations"][presentation] = {"id": presentation, "offering_id": offering, "version_id": published, "host_id": teacher.subject_id, "page_no": 2, "sequence": 1, "status": "ACTIVE"}
    repo = IsolatedMemoryRepository(state)
    service = LearningService(repo, SimpleNamespace(max_bytes=50*1024**2), tenant_id=teacher.tenant_id, signing_key="synthetic-review-key")
    return SimpleNamespace(service=service, repo=repo, teacher=teacher, student=student, offering=offering, material=material, draft=draft, published=published, presentation=presentation)


@pytest.mark.asyncio
async def test_global_lecturer_role_removal_revokes_draft_preview_even_with_stale_class_assignment(sample):
    downgraded = actor("STUDENT", sample.teacher.subject_id)
    with pytest.raises(LearningError):
        await sample.service.query(downgraded, "version", sample.draft)


@pytest.mark.asyncio
async def test_global_lecturer_role_removal_revokes_private_student_questions(sample):
    downgraded = actor("STUDENT", sample.teacher.subject_id)
    try:
        questions = await sample.service.query(downgraded, "questions", sample.published)
    except LearningError:
        return
    assert not questions, "A stale INSTRUCTOR assignment must not expose private questions after role removal"


@pytest.mark.asyncio
async def test_presentation_list_does_not_disclose_now_retracted_source(sample):
    sample.repo.state["versions"][sample.published]["publication_state"] = "RETRACTED"
    rows = await sample.service.query(sample.student, "presentations", sample.offering)
    assert rows == [], "Retracted source must disappear from presentation lists as well as direct reads"


@pytest.mark.asyncio
async def test_presentation_list_does_not_disclose_now_hidden_material(sample):
    sample.repo.state["materials"][sample.material]["visibility"] = "HIDDEN"
    rows = await sample.service.query(sample.student, "presentations", sample.offering)
    assert rows == [], "Hidden materials must not leak source metadata through presentation lists"


@pytest.mark.asyncio
async def test_explanation_rechecks_session_after_await_before_returning_private_answer():
    current = actor("STUDENT")
    revoked = False
    class ExplanationStub:
        ai_gateway = object()
        ai_verifier = object()
        async def explain(self, *args, **kwargs):
            nonlocal revoked
            revoked = True  # Models logout while the inference request is awaiting a provider.
            return {"answer": "Private source answer"}
        async def query(self, *args, **kwargs):
            return {}
    app = FastAPI()
    @app.middleware("http")
    async def identity(request, next_handler):
        request.state.identity = current
        def revalidate():
            if revoked:
                raise ValueError("Synthetic session revoked")
            return current
        request.state.revalidate_identity = revalidate
        return await next_handler(request)
    app.include_router(create_learning_router(ExplanationStub()))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://review.test") as client:
        response = await client.post(f"/v1/learning/versions/{generate_uuid7()}/explain", json={"page_no": 1, "question": "Explain"})
    assert response.status_code == 401
    assert "Private source answer" not in response.text
