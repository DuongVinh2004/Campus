"""Ratings counted per cited source, without any trace of who rated or what was asked; read only by knowledge managers."""
from __future__ import annotations

import asyncio
import json
import sqlite3
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from campus247.application.knowledge.answer_quality import AnswerQualityStore, attach_quality_recording, titled_report
from campus247.domain.shared.values import generate_uuid7
from campus247.ports.identity import IdentityContext, IdentityRole
from campus247.presentation.identity import IdentityMiddleware
from campus247.presentation.knowledge_quality import create_quality_router

NOW = datetime(2026, 11, 17, 3, 0, tzinfo=UTC)
D = timedelta(days=1)


@pytest.fixture
def store(tmp_path):
    return AnswerQualityStore(tmp_path / "quality.sqlite3")


def rate(store, versions, *, helpful, days_ago=1):
    return store.record(helpful=helpful, version_ids=versions, at=NOW - days_ago * D)


class TestStore:
    def test_a_rating_counts_once_for_each_distinct_cited_version(self, store):
        assert rate(store, ["v1", "v2", "v1"], helpful=False) == 2
        assert {s["version_id"]: s["not_helpful"] for s in store.report(now=NOW, min_votes=1)["sources"]} == {"v1": 1, "v2": 1}

    def test_an_answer_without_citations_records_nothing(self, store):
        assert rate(store, [], helpful=False) == 0 and store.report(now=NOW, min_votes=1)["ratings"] == 0
        assert store.record(helpful=True, version_ids=[None, "", "x" * 65, 5]) == 0  # type: ignore[list-item]

    def test_a_source_is_listed_only_after_the_minimum_number_of_ratings(self, store):
        rate(store, ["v1"], helpful=False)
        rate(store, ["v1"], helpful=False)
        assert store.report(now=NOW)["sources"] == []
        rate(store, ["v1"], helpful=True)
        (only,) = store.report(now=NOW)["sources"]
        assert (only["helpful"], only["not_helpful"], only["share_not_helpful"]) == (1, 2, 0.667)

    def test_sources_are_ordered_by_share_then_count_and_old_ratings_are_ignored(self, store):
        for _ in range(4):
            rate(store, ["bad"], helpful=False)
        for _ in range(3):
            rate(store, ["mixed"], helpful=False)
            rate(store, ["mixed"], helpful=True)
        for _ in range(5):
            rate(store, ["old"], helpful=False, days_ago=45)
        report = store.report(now=NOW, days=30)
        assert [s["version_id"] for s in report["sources"]] == ["bad", "mixed"] and report["ratings"] == 10
        assert [s["version_id"] for s in store.report(now=NOW, days=60)["sources"]] == ["old", "bad", "mixed"]  # same share: more not-helpful ratings first

    def test_rows_older_than_the_retention_period_are_deleted_when_a_new_rating_arrives(self, store):
        rate(store, ["v1"], helpful=False, days_ago=200)
        rate(store, ["v2"], helpful=True, days_ago=1)
        with sqlite3.connect(store.path) as db:
            assert [row[0] for row in db.execute("SELECT version_id FROM answer_ratings")] == ["v2"]

    def test_nothing_that_identifies_a_person_or_a_question_is_stored(self, store):
        rate(store, ["v1"], helpful=False)
        with sqlite3.connect(store.path) as db:
            assert [row[1] for row in db.execute("PRAGMA table_info(answer_ratings)")] == ["id", "at", "version_id", "helpful"]


class FakeFeedbackService:
    def __init__(self, versions, rating="NOT_HELPFUL", fail=False):
        self.versions, self.rating, self.fail = versions, rating, fail

    async def record_feedback(self, **kwargs):
        if self.fail:
            raise PermissionError("not the owner")
        return SimpleNamespace(rating=SimpleNamespace(value=self.rating), answer_reference=SimpleNamespace(source_document_version_ids=self.versions))


class TestAttach:
    def test_a_saved_rating_is_counted_and_the_receipt_is_returned_unchanged(self, store):
        service = FakeFeedbackService(["v1"])
        attach_quality_recording(service, store)
        receipt = asyncio.run(service.record_feedback(actor_id="a", conversation_id="c", message_id="m", rating="NOT_HELPFUL"))
        assert receipt.rating.value == "NOT_HELPFUL" and store.report(now=datetime.now(UTC), min_votes=1)["sources"][0]["not_helpful"] == 1

    def test_a_refused_feedback_is_not_counted(self, store):
        service = FakeFeedbackService(["v1"], fail=True)
        attach_quality_recording(service, store)
        with pytest.raises(PermissionError):
            asyncio.run(service.record_feedback())
        assert store.report(now=datetime.now(UTC), min_votes=1)["ratings"] == 0

    def test_a_failing_statistics_store_never_fails_the_persons_feedback(self, store, tmp_path):
        errors = []
        broken = AnswerQualityStore(tmp_path / "q2.sqlite3")
        broken.record = lambda **kwargs: (_ for _ in ()).throw(sqlite3.OperationalError("disk full"))  # type: ignore[method-assign]
        service = FakeFeedbackService(["v1"])
        attach_quality_recording(service, broken, on_error=errors.append)
        assert asyncio.run(service.record_feedback()).rating.value == "NOT_HELPFUL" and len(errors) == 1


class FakeFreshness:
    def __init__(self, rows=None, fail=False):
        self.rows, self.fail = rows or [], fail

    async def current_rows(self):
        if self.fail:
            raise RuntimeError("database unavailable")
        return self.rows


def test_titles_are_added_for_sources_of_the_current_release_only(store):
    for _ in range(3):
        rate(store, ["v1", "v2"], helpful=False)
    report = asyncio.run(titled_report(store, FakeFreshness([{"version_id": "v1", "title": "Quy chế", "owner_unit": "Phòng Đào tạo"}]), now=NOW))
    by_id = {s["version_id"]: s for s in report["sources"]}
    assert by_id["v1"]["title"] == "Quy chế" and by_id["v1"]["in_current_release"] is True
    assert by_id["v2"]["title"] is None and by_id["v2"]["in_current_release"] is False


class Adapter:
    def __init__(self):
        self.contexts = {}

    def resolve_token(self, token):
        if token in self.contexts:
            return self.contexts[token]
        raise ValueError("bad token")


def build_client(store, freshness):
    adapter, now = Adapter(), datetime.now(UTC)
    for token, role in (("kadmin", IdentityRole.KNOWLEDGE_ADMIN), ("admin", IdentityRole.SYSTEM_ADMIN), ("student", IdentityRole.STUDENT), ("officer", IdentityRole.SUPPORT_OFFICER)):
        adapter.contexts[token] = IdentityContext(generate_uuid7(), "ext:" + token, "t", (role,), token, now, now + timedelta(hours=1), tenant_id="t",
                                                  session_id=generate_uuid7(), student_code="SV1" if role == IdentityRole.STUDENT else None)
    app = FastAPI()
    app.add_middleware(IdentityMiddleware, adapter=adapter)
    app.include_router(create_quality_router(store, freshness, clock=lambda: NOW))
    return TestClient(app)


@pytest.fixture
def client(store):
    for _ in range(3):
        rate(store, ["v1"], helpful=False)
    with build_client(store, FakeFreshness([{"version_id": "v1", "title": "Quy chế", "owner_unit": "Phòng Đào tạo"}])) as test_client:
        yield test_client, store


def auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.parametrize("token", ["kadmin", "admin"])
def test_managers_read_the_report(client, token):
    test_client, _ = client
    reply = test_client.get("/v1/knowledge/answer-quality", headers=auth(token))
    assert reply.status_code == 200 and reply.headers["cache-control"] == "no-store"
    body = reply.json()
    assert body["sources"][0]["title"] == "Quy chế" and body["sources"][0]["share_not_helpful"] == 1.0 and body["minimum_votes"] == 3


@pytest.mark.parametrize(("token", "status"), [("student", 403), ("officer", 403), (None, 401)])
def test_nobody_else_reads_it(client, token, status):
    test_client, _ = client
    reply = test_client.get("/v1/knowledge/answer-quality", headers=auth(token) if token else {})
    assert reply.status_code == status and "sources" not in reply.text


def test_the_days_parameter_is_bounded(client):
    test_client, _ = client
    assert test_client.get("/v1/knowledge/answer-quality?days=0", headers=auth("kadmin")).status_code == 422
    assert test_client.get("/v1/knowledge/answer-quality?days=181", headers=auth("kadmin")).status_code == 422
    assert test_client.get("/v1/knowledge/answer-quality?days=7", headers=auth("kadmin")).status_code == 200


def test_the_counts_are_still_served_when_the_knowledge_database_is_down(store):
    for _ in range(3):
        rate(store, ["v1"], helpful=False)
    with build_client(store, FakeFreshness(fail=True)) as test_client:
        body = test_client.get("/v1/knowledge/answer-quality", headers=auth("kadmin")).json()
    assert body["sources"][0]["version_id"] == "v1" and body["sources"][0]["title"] is None and body["sources"][0]["in_current_release"] is False


class TestVerificationCounts:
    """F4.4: kept and dropped statements per day, as counts only."""

    @staticmethod
    def checks(verbatim, semantic):
        from campus247.rag_v2.types import StatementCheck
        return tuple(StatementCheck("PASSED", v, s) for v, s in zip(verbatim, semantic))

    def test_counts_accumulate_per_day_and_reason_and_report_shares(self, store):
        store.record_verification(checks=self.checks([True, False], ["NOT_RUN", "PASSED"]), rejected_counts={"NUMBER_NOT_IN_SOURCE": 1}, at=NOW - D)
        store.record_verification(checks=self.checks([False], ["PASSED"]), rejected_counts={"NUMBER_NOT_IN_SOURCE": 1, "SEMANTIC_UNSUPPORTED": 2}, at=NOW)
        report = store.verification_report(now=NOW)
        assert (report["statements"], report["verbatim"], report["semantic"]) == (3, 1, 2)
        assert report["rejected"] == {"NUMBER_NOT_IN_SOURCE": 2, "SEMANTIC_UNSUPPORTED": 2} and report["rejected_total"] == 4
        assert report["rejected_share"] == round(4 / 7, 3) and report["verbatim_share"] == round(1 / 3, 3)
        assert [d["day"] for d in report["daily_rejected"]] == ["2026-11-16", "2026-11-17"]

    def test_unknown_reason_text_is_never_stored_and_old_days_fall_out_of_the_window(self, store):
        store.record_verification(checks=(), rejected_counts={"free text with a name": 3, "OK_CODE": 1}, at=NOW - 40 * D)
        assert store.verification_report(now=NOW, days=30)["rejected"] == {}
        assert store.verification_report(now=NOW, days=60)["rejected"] == {"OK_CODE": 1}
        assert "free text" not in sqlite3.connect(store.path).execute("SELECT group_concat(kind) FROM verification_counts").fetchone()[0]

    def test_observer_records_answers_and_a_failing_store_never_fails_the_answer(self, store):
        from campus247.agent.nodes import rag_v2
        from campus247.application.knowledge.answer_quality import attach_verification_recording
        before = len(rag_v2.OUTCOME_OBSERVERS)
        errors = []
        attach_verification_recording(store, on_error=errors.append)
        attach_verification_recording(store)  # idempotent
        assert len(rag_v2.OUTCOME_OBSERVERS) == before + 1
        observer = rag_v2.OUTCOME_OBSERVERS[-1]
        try:
            observer(SimpleNamespace(kind="answer", checks=self.checks([True], ["NOT_RUN"]), rejected_counts={}), {})
            observer(SimpleNamespace(kind="clarify", checks=(), rejected_counts={"X": 1}), {})
            assert store.verification_report(now=datetime.now(UTC))["statements"] == 1
            store.record_verification = lambda **kw: (_ for _ in ()).throw(sqlite3.OperationalError("disk"))  # type: ignore[method-assign]
            observer(SimpleNamespace(kind="answer", checks=(), rejected_counts={}), {})
            assert len(errors) == 1
        finally:
            rag_v2.OUTCOME_OBSERVERS.remove(observer)

    def test_only_managers_read_the_route(self, store):
        store.record_verification(checks=self.checks([True], ["NOT_RUN"]), rejected_counts={"NUMBER_NOT_IN_SOURCE": 1}, at=NOW)
        with build_client(store, FakeFreshness()) as c:
            ok = c.get("/v1/knowledge/answer-quality/verification", headers=auth("kadmin"))
            assert ok.status_code == 200 and ok.json()["rejected"] == {"NUMBER_NOT_IN_SOURCE": 1}
            assert c.get("/v1/knowledge/answer-quality/verification", headers=auth("student")).status_code == 403
            assert c.get("/v1/knowledge/answer-quality/verification").status_code == 401
