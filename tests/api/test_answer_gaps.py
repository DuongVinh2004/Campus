"""Refused answers counted per cluster of sources, with no trace of who asked or what was asked."""
from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from campus247.agent.nodes import rag_v2 as node
from campus247.application.knowledge.answer_quality import AnswerQualityStore, attach_gap_recording
from campus247.domain.shared.values import generate_uuid7
from campus247.ports.identity import IdentityContext, IdentityRole
from campus247.presentation.identity import IdentityMiddleware
from campus247.presentation.knowledge_quality import create_quality_router

NOW = datetime(2026, 11, 20, 3, 0, tzinfo=UTC)
D = timedelta(days=1)


@pytest.fixture
def store(tmp_path):
    return AnswerQualityStore(tmp_path / "quality.sqlite3")


def refuse(store, versions, reason="no_source", days_ago=1):
    return store.record_gap(reason=reason, version_ids=versions, at=NOW - days_ago * D)


class TestStore:
    def test_the_same_sources_and_reason_make_one_cluster(self, store):
        refuse(store, ["v2", "v1"])
        refuse(store, ["v1", "v2", "v1"])
        refuse(store, ["v1", "v2"], reason="unverified")
        refuse(store, ["v9"])
        report = store.gaps_report(now=NOW, min_count=1)
        counts = sorted((g["count"], g["reason"], tuple(g["version_ids"])) for g in report["clusters"])
        assert counts == [(1, "no_source", ("v9",)), (1, "unverified", ("v1", "v2")), (2, "no_source", ("v1", "v2"))]

    def test_only_the_three_strongest_sources_name_the_cluster_and_five_are_kept(self, store):
        refuse(store, ["a", "b", "c", "d", "e", "f"])
        (cluster,) = store.gaps_report(now=NOW, min_count=1)["clusters"]
        assert cluster["version_ids"] == ["a", "b", "c"]

    def test_a_cluster_is_listed_only_after_the_minimum_count_and_inside_the_window(self, store):
        for _ in range(2):
            refuse(store, ["v1"])
        assert store.gaps_report(now=NOW)["clusters"] == []
        refuse(store, ["v1"])
        refuse(store, ["v1"], days_ago=45)  # outside 30 days
        (cluster,) = store.gaps_report(now=NOW)["clusters"]
        assert cluster["count"] == 3

    def test_the_trend_compares_with_the_week_before(self, store):
        for days in (1, 2, 3):
            refuse(store, ["v1"], days_ago=days)
        for days in (8,):
            refuse(store, ["v1"], days_ago=days)
        (cluster,) = store.gaps_report(now=NOW, min_count=1)["clusters"]
        assert (cluster["count_7d"], cluster["previous_7d"], cluster["is_new_trend"]) == (3, 1, True)

    def test_nothing_about_the_person_or_the_question_can_be_stored(self, store, tmp_path):
        refuse(store, ["v1"])
        db = sqlite3.connect(tmp_path / "quality.sqlite3")
        columns = {row[1] for row in db.execute("PRAGMA table_info(answer_gaps)")}
        assert columns == {"id", "at", "reason", "cluster_key", "version_ids"}
        assert "Hỏi" not in repr(db.execute("SELECT * FROM answer_gaps").fetchall())

    def test_unusable_input_records_nothing_and_old_rows_expire(self, store):
        assert store.record_gap(reason="x" * 50, version_ids=["v1"], at=NOW) == 0
        assert store.record_gap(reason="Not Valid", version_ids=["v1"], at=NOW) == 0
        assert store.record_gap(reason="no_source", version_ids=[5, None, "x" * 65], at=NOW) == 1  # type: ignore[list-item]
        assert store.gaps_report(now=NOW, min_count=1)["clusters"][0]["version_ids"] == []
        store.path.unlink()
        AnswerQualityStore(store.path)
        refuse(store, ["v1"], days_ago=200)
        refuse(store, ["v1"], days_ago=1)  # writing prunes rows older than the retention
        assert store.gaps_report(now=NOW, days=180, min_count=1)["clusters"][0]["count"] == 1

    def test_a_decision_is_remembered_with_who_and_why_and_resolving_needs_a_release(self, store):
        refuse(store, ["v1"])
        key = store.gaps_report(now=NOW, min_count=1)["clusters"][0]["cluster_key"]
        with pytest.raises(ValueError):
            store.decide(key, action="RESOLVED", note="Đã bổ sung nguồn mới", release_ref="", actor="u1", at=NOW)
        with pytest.raises(ValueError):
            store.decide(key, action="WHATEVER", note="x", release_ref="", actor="u1", at=NOW)
        store.decide(key, action="NEEDS_SOURCE", note="Cần thêm thông báo học phí", release_ref="", actor="u1", at=NOW)
        decision = store.gaps_report(now=NOW, min_count=1)["clusters"][0]["decision"]
        assert decision["action"] == "NEEDS_SOURCE" and decision["note"] == "Cần thêm thông báo học phí" and decision["actor"] == "u1"
        store.decide(key, action="RESOLVED", note="Đã bổ sung", release_ref="rel-9", actor="u2", at=NOW)
        assert store.gaps_report(now=NOW, min_count=1)["clusters"][0]["decision"]["release_ref"] == "rel-9"


class Row(dict):
    pass


def outcome(kind, reason, chunk_ids=("c1",)):
    return SimpleNamespace(kind=kind, reason=reason, citations=tuple(SimpleNamespace(chunk_ids=(c,)) for c in chunk_ids))


ROWS = {"c1": {"document_version_id": "v1"}, "c2": {"document_version_id": "v2"}}


class TestObserver:
    def teardown_method(self):
        node.OUTCOME_OBSERVERS.clear()

    def test_a_refusal_is_counted_with_the_versions_it_pointed_at_and_nothing_else(self, store):
        attach_gap_recording(store)
        node.notify_outcome(outcome("refuse", "no_source", ("c1", "c2")), ROWS)
        node.notify_outcome(outcome("answer", None), ROWS)
        node.notify_outcome(outcome("clarify", None), ROWS)
        (cluster,) = store.gaps_report(now=datetime.now(UTC), min_count=1)["clusters"]
        assert cluster["version_ids"] == ["v1", "v2"] and cluster["reason"] == "no_source" and cluster["count"] == 1

    def test_a_refusal_with_no_source_pointer_still_counts_under_its_reason(self, store):
        attach_gap_recording(store)
        node.notify_outcome(outcome("refuse", "out_of_scope", ()), ROWS)
        (cluster,) = store.gaps_report(now=datetime.now(UTC), min_count=1)["clusters"]
        assert cluster["version_ids"] == [] and cluster["reason"] == "out_of_scope"

    def test_a_failing_recorder_never_breaks_the_answer(self, store, monkeypatch):
        attach_gap_recording(store, on_error=lambda e: errors.append(type(e).__name__))
        errors = []
        monkeypatch.setattr(store, "record_gap", lambda **kw: (_ for _ in ()).throw(RuntimeError("disk full")))
        node.notify_outcome(outcome("refuse", "no_source"), ROWS)
        assert errors == ["RuntimeError"]

    def test_attaching_twice_does_not_double_count(self, store):
        attach_gap_recording(store)
        attach_gap_recording(store)
        node.notify_outcome(outcome("refuse", "no_source"), ROWS)
        assert store.gaps_report(now=datetime.now(UTC), min_count=1)["clusters"][0]["count"] == 1


class Adapter:
    def __init__(self):
        self.contexts = {}

    def resolve_token(self, token):
        if token in self.contexts:
            return self.contexts[token]
        raise ValueError("bad token")


class FakeFreshness:
    async def current_rows(self):
        return [{"version_id": "v1", "title": "Thông báo học phí", "owner_unit": "Phòng Tài chính"}]


@pytest.fixture
def client(store):
    adapter = Adapter()
    for token, role in (("kadmin", IdentityRole.KNOWLEDGE_ADMIN), ("student", IdentityRole.STUDENT), ("officer", IdentityRole.SUPPORT_OFFICER)):
        now = datetime.now(UTC)
        adapter.contexts[token] = IdentityContext(subject_id=generate_uuid7(), external_subject="s", issuer="t", roles=(role,), display_name="T", auth_time=now,
                                                  expires_at=now + timedelta(hours=1), tenant_id="t", session_id=generate_uuid7(),
                                                  student_code="SV1" if role == IdentityRole.STUDENT else None)
    app = FastAPI()
    app.add_middleware(IdentityMiddleware, adapter=adapter)
    app.include_router(create_quality_router(store, FakeFreshness(), clock=lambda: NOW))
    with TestClient(app) as test_client:
        yield test_client


def auth(token):
    return {"Authorization": f"Bearer {token}"}


class TestApi:
    def test_a_manager_sees_clusters_with_titles(self, client, store):
        for _ in range(3):
            refuse(store, ["v1", "unknown"])
        body = client.get("/v1/knowledge/answer-quality", headers=auth("kadmin")).json()
        (cluster,) = body["gaps"]["clusters"]
        assert cluster["count"] == 3 and cluster["sources"] == [{"version_id": "unknown", "title": None, "owner_unit": None}, {"version_id": "v1", "title": "Thông báo học phí", "owner_unit": "Phòng Tài chính"}]
        assert body["gaps"]["minimum_count"] == 3 and "sources" in body  # the old ratings block is still there

    @pytest.mark.parametrize("token,status", [("student", 403), ("officer", 403)])
    def test_nobody_else_reads_or_decides(self, client, store, token, status):
        refuse(store, ["v1"])
        key = store.gaps_report(now=NOW, min_count=1)["clusters"][0]["cluster_key"]
        assert client.get("/v1/knowledge/answer-quality", headers=auth(token)).status_code == status
        reply = client.post(f"/v1/knowledge/answer-quality/gaps/{key}/decision", headers=auth(token), json={"action": "NEEDS_SOURCE", "note": "ghi chú"})
        assert reply.status_code == status

    def test_a_manager_records_a_decision_and_it_shows(self, client, store):
        for _ in range(3):
            refuse(store, ["v1"])
        key = client.get("/v1/knowledge/answer-quality", headers=auth("kadmin")).json()["gaps"]["clusters"][0]["cluster_key"]
        ok = client.post(f"/v1/knowledge/answer-quality/gaps/{key}/decision", headers=auth("kadmin"), json={"action": "NEEDS_SOURCE", "note": "Cần thêm nguồn học phí"})
        assert ok.status_code == 200
        assert client.get("/v1/knowledge/answer-quality", headers=auth("kadmin")).json()["gaps"]["clusters"][0]["decision"]["action"] == "NEEDS_SOURCE"

    @pytest.mark.parametrize("body", [{"action": "RESOLVED", "note": "xong"}, {"action": "BAD", "note": "x"}, {"action": "NEEDS_SOURCE", "note": "x" * 501}, {"note": "x"}])
    def test_bad_decisions_are_422(self, client, store, body):
        refuse(store, ["v1"])
        key = store.gaps_report(now=NOW, min_count=1)["clusters"][0]["cluster_key"]
        assert client.post(f"/v1/knowledge/answer-quality/gaps/{key}/decision", headers=auth("kadmin"), json=body).status_code == 422

    def test_a_decision_on_an_unknown_cluster_is_404(self, client):
        reply = client.post("/v1/knowledge/answer-quality/gaps/" + "0" * 40 + "/decision", headers=auth("kadmin"), json={"action": "NEEDS_SOURCE", "note": "ghi chú"})
        assert reply.status_code == 404
