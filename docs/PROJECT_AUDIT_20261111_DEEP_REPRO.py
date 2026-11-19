"""Deeper audit, 12 November 2026: isolated memory only, no application writes.

Run from repo root: .venv/Scripts/python.exe -B -X utf8
docs/PROJECT_AUDIT_20261111_DEEP_REPRO.py
Exit 0 confirms documented defects AND positive controls, not app health.
The earlier harness installs a file/database/network/subprocess write guard.
"""
import asyncio
from contextlib import contextmanager
import json
from pathlib import Path
import runpy
import sqlite3
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
assert Path.cwd().resolve() == ROOT
common = runpy.run_path(str(ROOT / "docs/PROJECT_AUDIT_20261111_REPRO.py"), run_name="audit_common")
sample, emit = common["sample"], common["emit"]

from campus247.application.assistance.state_storage import StateScope
from campus247.application.learning.explanation import LearningExplanationVerifier
from campus247.application.privacy.consent import ServiceUnavailableError
from campus247.domain.learning import LearningError
from campus247.domain.shared.values import generate_uuid7
from campus247.infrastructure.repositories.sqlite_actor_state import SQLiteActorStateStore
from campus247.infrastructure.repositories.sqlite_consents import SQLiteConsentRepository
from campus247.ports.llm import LlmResponse, LlmResponseStatus
from tests.learning_review.test_privacy_boundaries import actor


class MemoryStateStore(SQLiteActorStateStore):
    """Use actual schema, commit/CAS and receipt verification against memory SQL."""
    def __init__(self):
        self.db = sqlite3.connect(":memory:")
        # Canonical path metadata only; connect() never opens this filename.
        super().__init__(ROOT / "docs/audit-memory-only-not-created.sqlite3")

    @contextmanager
    def connect(self, **kwargs):
        with self.db:
            yield self.db


def consent_history():
    store, person = MemoryStateStore(), actor("STUDENT")
    repo = SQLiteConsentRepository(store, tenant=person.tenant_id)
    repo.record_consent(person, "QUALITY_FEEDBACK", "GRANTED", "1.0.0")
    assert len(repo.list_user_consents(person.subject_id)) == 1
    scope = StateScope(person.tenant_id, person.subject_id)
    for _ in range(999):
        cid = generate_uuid7()
        store.commit(scope, "conversation_metadata", cid, 0,
                     {"conversation_id": cid, "title": "Synthetic conversation"}, generate_uuid7())
    assert len(repo.list_user_consents(person.subject_id)) == 1
    cid = generate_uuid7()
    store.commit(scope, "conversation_metadata", cid, 0,
                 {"conversation_id": cid, "title": "Synthetic conversation"}, generate_uuid7())
    try:
        repo.list_user_consents(person.subject_id)
    except ServiceUnavailableError as error:
        assert str(error) == "CONSENT_STORAGE_UNAVAILABLE"
    else:
        raise AssertionError("Expected unrelated-receipt limit to break consent history")
    assert repo.has_active_consent(person.subject_id, "QUALITY_FEEDBACK")
    consent_count = store.db.execute("SELECT count(*) FROM unified_state_revision WHERE namespace='consent'").fetchone()[0]
    assert consent_count == 1
    emit("AUD-016", total_receipts_1000_history_ok=True, total_receipts_1001_history_unavailable=True,
         consent_revisions=consent_count, unrelated_receipts=1000, active_consent_still_readable=True)


async def worker_case(error_type):
    data = sample.__wrapped__()
    data.repo.state["versions"][data.draft].update(storage_key="memory.pdf", sha256="a" * 64,
                                                  byte_size=10, processing_state="QUEUED")
    data.repo.state["jobs"][data.draft] = {"id": data.draft, "state": "QUEUED", "attempt": 0}

    class Blob:
        def path(self, *args):
            return SimpleNamespace(stat=lambda: SimpleNamespace(st_size=10))

        async def verify(self, *args, **kwargs):
            pass

    class Scanner:
        calls = 0

        async def scan(self, *args, **kwargs):
            self.calls += 1
            raise error_type("Synthetic scanner failure")

    scanner = Scanner()
    data.service.blobs, data.service.scanner = Blob(), scanner
    escaped = 0
    for _ in range(3):
        try:
            await data.service.tick()
        except OSError:
            escaped += 1
        data.repo.state["jobs"][data.draft]["lease_until"] = "2000-01-01T00:00:00Z"
    for _ in range(2):
        await data.service.tick()
    job, version = data.repo.state["jobs"][data.draft], data.repo.state["versions"][data.draft]
    assert scanner.calls == job["attempt"] == 3
    return job, version, escaped


async def worker_recovery():
    control, control_version, escaped_control = await worker_case(TimeoutError)
    assert control["state"] == control_version["processing_state"] == "FAILED"
    assert control["error_code"] == "PROCESSING_TIMEOUT" and escaped_control == 0
    job, version, escaped = await worker_case(OSError)
    assert job["state"] == "PROCESSING" and version["processing_state"] == "SCANNING"
    assert "error_code" not in job and escaped == 3
    emit("AUD-017", handled_timeout_final_state=control["state"], os_errors_escaped=escaped,
         attempt=job["attempt"], expired_lease=True, two_more_ticks_no_recovery=True,
         job_state=job["state"], version_state=version["processing_state"], error_code_absent=True)


async def explanation_case(hide_at):
    data = sample.__wrapped__()
    text = "Synthetic reviewed lecture source."
    data.repo.state["versions"][data.published].update(storage_key="memory.pdf", sha256="b" * 64,
                                                      byte_size=10, offering_id=data.offering)
    data.service.ai_source_hashes = {"b" * 64}
    calls = []

    def hide():
        data.repo.state["materials"][data.material]["visibility"] = "HIDDEN"

    class Blob:
        async def verify(self, *args, **kwargs):
            pass

        async def extract_page(self, *args, **kwargs):
            if hide_at == "extract":
                hide()
            return text

    class Gateway:
        async def generate(self, request):
            calls.append({"route": request.route_id,
                          "source_hidden": data.repo.state["materials"][data.material]["visibility"] == "HIDDEN"})
            if request.route_id == "learning_material_verification":
                value = {"supported": True, "answers_question": True}
            else:
                value = {"explanation": text, "source_quote": text, "questions": []}
                if hide_at == "generation":
                    hide()
            return LlmResponse(LlmResponseStatus.COMPLETED, "fake", "fake", structured_output=value)

    if hide_at == "before":
        hide()
    gateway = Gateway()
    data.service.blobs = Blob()
    try:
        result = await data.service.explain(data.student, data.published, page_no=1, question="Explain the source",
                                            gateway=gateway, verifier=LearningExplanationVerifier(gateway))
    except LearningError as error:
        assert hide_at is not None and error.status == 404
        return calls, False
    assert result["answer"] == text
    return calls, True


async def explanation_egress():
    visible, allowed = await explanation_case(None)
    before, denied = await explanation_case("before")
    extracted, late_result = await explanation_case("extract")
    generation, late_generation = await explanation_case("generation")
    assert allowed and len(visible) == 2 and not any(c["source_hidden"] for c in visible)
    assert not denied and before == []
    assert not late_result and len(extracted) == 2 and all(c["source_hidden"] for c in extracted)
    assert not late_generation and len(generation) == 2 and generation[1]["source_hidden"]
    emit("AUD-018", visible_source_calls=2, hidden_before_start_calls=0,
         hidden_during_extract_calls=extracted, hidden_during_generation_verifier_called=True,
         final_response_denied=True, real_provider_calls=0)


async def main():
    consent_history()
    await worker_recovery()
    await explanation_egress()


if __name__ == "__main__":
    import os
    import sys
    if "--existing-tests" in sys.argv:
        os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
        import pytest
        raise SystemExit(pytest.main([
            "-p", "pytest_asyncio.plugin", "-p", "no:cacheprovider", "--capture=sys", "--tb=short", "-q",
            "tests/learning_review/test_privacy_boundaries.py", "tests/api/test_privacy_notice_consent.py",
        ]))
    asyncio.run(main())
