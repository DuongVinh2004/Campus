from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from campus247.application.document_request.local_preparation import LocalPreparationService, PreparationForm
from campus247.application.knowledge.platform import KnowledgePlatform
from campus247.application.knowledge.platform_models import PlatformError
from campus247.domain.action.confirmation import ConfirmationTokenService
from campus247.domain.shared.values import generate_uuid7
from campus247.infrastructure.repositories.sqlite_actor_state import SQLiteActorStateStore
from campus247.ports.identity import IdentityContext, IdentityRole


@pytest.fixture
def setup(tmp_path):
    now = datetime.now(UTC)
    actor = IdentityContext(subject_id=generate_uuid7(), external_subject="local", issuer="local-student",
        roles=(IdentityRole.STUDENT,), display_name="Test local", auth_time=now, expires_at=now+timedelta(hours=1),
        tenant_id="local-preparation-test", session_id=generate_uuid7(), is_synthetic=False, student_code="LOCAL-TEST")
    store = SQLiteActorStateStore(tmp_path / "actor.sqlite3")
    platform = KnowledgePlatform(SimpleNamespace(tenant=actor.tenant_id), None, ConfirmationTokenService("test-only-key"))
    return LocalPreparationService(store, platform), actor


def save(service, actor, preview, client=None, **changes):
    return service.save(actor, preview["preview_id"], changes.get("token", preview["confirmation_token"]),
        client or generate_uuid7(), changes.get("confirmed", True), changes.get("guard", lambda: actor))


def test_owned_draft_signed_preview_replay_restart_and_revision(setup):
    service, actor = setup
    for kind in ("STUDENT_CERTIFICATE", "GRADE_APPEAL", "GENERAL_SUPPORT"):
        preview = service.preview(actor, PreparationForm(kind=kind, reason="Nội dung tự khai chưa xác thực"))
        client = generate_uuid7()
        result = save(service, actor, preview, client)
        assert result["effect"] == "draft_saved" and result["document"]["sent_to_university"] is False
        assert result["document"]["status"] == "DRAFT"
        assert save(service, actor, preview, client) == {**result, "is_replay": True}
        record = service.read(actor, result["document"]["id"])
        assert record == result["document"]
        updated = service.preview(actor, PreparationForm(kind=kind, reason="Nội dung chỉnh sửa"), record["id"], record["version"])
        assert save(service, actor, updated)["document"]["version"] == 2
    reopened = LocalPreparationService(service.store, service.platform)
    assert len(reopened.list(actor)["items"]) == 3
    with service.store.connect() as conn:
        assert conn.execute("SELECT count(*) FROM campus_preparation_revision").fetchone()[0] == 6
        assert conn.execute("SELECT count(*) FROM campus_preparation_receipt").fetchone()[0] == 6


def test_role_tenant_expiry_owner_and_session_scope(setup):
    service, actor = setup
    preview = service.preview(actor, PreparationForm(kind="GENERAL_SUPPORT", reason="Hỏi thủ tục"))
    saved = save(service, actor, preview)
    other = replace(actor, subject_id=generate_uuid7())
    assert service.list(other)["items"] == []
    with pytest.raises(PlatformError) as error:
        service.read(other, saved["document"]["id"])
    assert error.value.status == 404
    with pytest.raises(PlatformError):
        save(service, other, preview)
    for denied in (replace(actor, tenant_id="other"), replace(actor, roles=(IdentityRole.KNOWLEDGE_ADMIN,)),
                   replace(actor, is_synthetic=True), replace(actor, session_id=""),
                   replace(actor, expires_at=actor.auth_time+timedelta(microseconds=1))):
        with pytest.raises(PlatformError):
            service.list(denied)
    with pytest.raises(PlatformError):
        save(service, replace(actor, session_id=generate_uuid7()), preview)


def test_confirmation_tampering_conflict_and_revocation_fail_closed(setup):
    service, actor = setup
    form = PreparationForm(kind="GENERAL_SUPPORT", reason="Nháp cần giữ")
    preview = service.preview(actor, form)
    for changes in ({"confirmed": False}, {"token": "forged"}, {"guard": lambda: replace(actor, session_id=generate_uuid7())}):
        with pytest.raises(PlatformError):
            save(service, actor, preview, **changes)
    assert service.list(actor)["items"] == []
    result = save(service, actor, preview)
    record = result["document"]
    first = service.preview(actor, form, record["id"], 1)
    second = service.preview(actor, form, record["id"], 1)
    save(service, actor, first)
    with pytest.raises(PlatformError) as error:
        save(service, actor, second)
    assert error.value.code == "STALE_VERSION"
    assert service.read(actor, record["id"])["version"] == 2
    with pytest.raises(PlatformError):
        service.preview(actor, form, record["id"], 1)
    with pytest.raises(PlatformError):
        service.preview(actor, PreparationForm(kind="GRADE_APPEAL", reason="Không đổi loại"), record["id"], 2)
