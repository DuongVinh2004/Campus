"""Freshness of release sources: judgement, ordering, review notes, access and what is refused. The database is a fake
that returns rows; the SQL itself is checked separately against a real PostgreSQL."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from campus247.application.knowledge.freshness_service import (
    CURRENT_SOURCES_SQL,
    CURRENT_SOURCES_SQL_NO_DISPOSITION,
    FreshnessService,
    SourceReviewStore,
    assess_rows,
    summary,
)
from campus247.domain.shared.values import generate_uuid7
from campus247.ports.identity import IdentityContext, IdentityRole
from campus247.presentation.identity import IdentityMiddleware
from campus247.presentation.knowledge_freshness import create_freshness_router

NOW = datetime(2026, 11, 17, 3, 0, tzinfo=UTC)
A, B, C, D = (generate_uuid7() for _ in range(4))


def row(source_id, title, *, since_days=100, until_days=None, unknown=False, published_days=None):
    return {"source_id": source_id, "version_id": generate_uuid7(), "title": title, "owner_unit": "Phòng Đào tạo", "version_label": "v1",
            "effective_from": NOW - timedelta(days=since_days), "effective_until": NOW + timedelta(days=until_days) if until_days is not None else None,
            "published_at": NOW - timedelta(days=published_days) if published_days is not None else None, "created_at": NOW - timedelta(days=since_days),
            "applicability_unknown": unknown}


ROWS = [row(A, "Quy chế đào tạo", since_days=400), row(B, "Học phí 2026", since_days=10, until_days=12),
        row(C, "Thông báo lịch thi", since_days=30), row(D, "Quy định ký túc xá", since_days=360, unknown=True)]


class FakeConn:
    def __init__(self, rows, has_dispositions=True):
        self.rows, self.has_dispositions, self.queries = rows, has_dispositions, []

    async def fetchval(self, sql, *args):
        return self.has_dispositions

    async def fetch(self, sql, *args):
        self.queries.append((sql, args))
        return self.rows


class FakePool:
    def __init__(self, conn):
        self.conn = conn

    def acquire(self):
        conn = self.conn

        class Context:
            async def __aenter__(self):
                return conn

            async def __aexit__(self, *exc):
                return False

        return Context()


class TestAssessment:
    def test_orders_by_urgency_then_time_left_then_title_and_counts(self, tmp_path):
        items = assess_rows(ROWS, {}, now=NOW)
        assert [(i["title"], i["state"]) for i in items] == [("Quy chế đào tạo", "OVERDUE"), ("Quy định ký túc xá", "DUE_SOON"),
                                                            ("Học phí 2026", "DUE_SOON"), ("Thông báo lịch thi", "OK")]  # 5 days left, then 12
        assert summary(items) == {"OK": 1, "DUE_SOON": 2, "OVERDUE": 1, "EXPIRED": 0, "applicability_unknown": 1}
        assert items[1]["reason"] == "REVIEW_INTERVAL" and items[1]["days_left"] == 5
        assert items[2]["reason"] == "EFFECTIVE_UNTIL" and items[2]["days_left"] == 12

    def test_a_review_restarts_the_clock_and_is_shown(self, tmp_path):
        store = SourceReviewStore(tmp_path / "reviews.sqlite3")
        store.record(A, "reviewer-1", "Đã đối chiếu với bản gốc ngày 10/11", at=NOW - timedelta(days=3))
        items = {i["source_id"]: i for i in assess_rows(ROWS, store.latest(), now=NOW)}
        assert items[A]["state"] == "OK" and items[A]["last_review"]["note"].startswith("Đã đối chiếu")

    def test_publication_date_is_used_when_the_effective_date_is_older(self):
        old = row(A, "Cũ", since_days=900, published_days=20)
        assert assess_rows([old], {}, now=NOW)[0]["state"] == "OK"

    def test_string_dates_from_other_stores_are_accepted(self):
        text = dict(row(A, "X", since_days=10), effective_from="2026-11-01T00:00:00Z", created_at="2026-11-01T00:00:00Z")
        assert assess_rows([text], {}, now=NOW)[0]["state"] == "OK"


class TestReviewStore:
    def test_latest_review_wins_and_notes_are_validated(self, tmp_path):
        store = SourceReviewStore(tmp_path / "r.sqlite3")
        store.record(A, "u1", "Lần đầu rà soát đầy đủ", at=NOW - timedelta(days=30))
        store.record(A, "u2", "Lần hai: không có thay đổi", at=NOW - timedelta(days=1))
        assert store.latest()[A]["reviewer_id"] == "u2" and store.latest()[A]["note"].startswith("Lần hai")
        for bad in ("ngắn", "x" * 1001, "   "):
            with pytest.raises(ValueError):
                store.record(A, "u1", bad)

    def test_survives_reopening(self, tmp_path):
        SourceReviewStore(tmp_path / "r.sqlite3").record(A, "u1", "Đã kiểm tra nguồn này rồi")
        assert A in SourceReviewStore(tmp_path / "r.sqlite3").latest()


class TestService:
    @pytest.mark.asyncio
    async def test_report_runs_the_query_with_tenant_and_campus(self, tmp_path):
        conn = FakeConn(ROWS)
        service = FreshnessService(FakePool(conn), SourceReviewStore(tmp_path / "r.sqlite3"), tenant="huce-local-public")
        report = await service.report(now=NOW)
        assert conn.queries[0][0] == CURRENT_SOURCES_SQL and conn.queries[0][1] == ("huce-local-public", "HUCE")
        assert report["summary"]["OVERDUE"] == 1 and len(report["items"]) == 4

    @pytest.mark.asyncio
    async def test_an_older_database_without_dispositions_uses_the_simpler_query(self, tmp_path):
        conn = FakeConn(ROWS, has_dispositions=False)
        await FreshnessService(FakePool(conn), SourceReviewStore(tmp_path / "r.sqlite3"), tenant="t").report(now=NOW)
        assert conn.queries[0][0] == CURRENT_SOURCES_SQL_NO_DISPOSITION and "knowledge_source_disposition" not in conn.queries[0][0]

    @pytest.mark.asyncio
    async def test_only_sources_of_the_current_release_can_be_marked_reviewed(self, tmp_path):
        service = FreshnessService(FakePool(FakeConn(ROWS)), SourceReviewStore(tmp_path / "r.sqlite3"), tenant="t")
        await service.mark_reviewed(A, "u1", "Đã đối chiếu với bản gốc")
        with pytest.raises(LookupError):
            await service.mark_reviewed(generate_uuid7(), "u1", "Đã đối chiếu với bản gốc")

    def test_the_queries_only_read(self):
        for sql in (CURRENT_SOURCES_SQL, CURRENT_SOURCES_SQL_NO_DISPOSITION):
            assert sql.strip().upper().startswith("SELECT") and not any(w in sql.upper() for w in ("INSERT", "UPDATE", "DELETE", "DROP"))
            assert "$1" in sql and "$2" in sql and "NOT s.is_synthetic" in sql


class Adapter:
    def __init__(self):
        self.contexts = {}

    def resolve_token(self, token):
        if token in self.contexts:
            return self.contexts[token]
        raise ValueError("bad token")

    def add(self, token, role):
        now = datetime.now(UTC)
        self.contexts[token] = IdentityContext(subject_id=generate_uuid7(), external_subject="s", issuer="t", roles=(role,), display_name="T",
                                               auth_time=now, expires_at=now + timedelta(hours=1), tenant_id="t", session_id=generate_uuid7(),
                                               student_code="SV123456" if role == IdentityRole.STUDENT else None)


@pytest.fixture
def client(tmp_path):
    adapter = Adapter()
    for token, role in (("kadmin", IdentityRole.KNOWLEDGE_ADMIN), ("admin", IdentityRole.SYSTEM_ADMIN), ("student", IdentityRole.STUDENT),
                        ("officer", IdentityRole.SUPPORT_OFFICER)):
        adapter.add(token, role)
    service = FreshnessService(FakePool(FakeConn(ROWS)), SourceReviewStore(tmp_path / "r.sqlite3"), tenant="t")
    app = FastAPI()
    app.add_middleware(IdentityMiddleware, adapter=adapter)
    app.include_router(create_freshness_router(service))
    with TestClient(app) as test_client:
        yield test_client


def auth(token):
    return {"Authorization": f"Bearer {token}"}


class TestApi:
    @pytest.mark.parametrize("token", ["kadmin", "admin"])
    def test_managers_read_the_report(self, client, token):
        reply = client.get("/v1/knowledge/freshness", headers=auth(token))
        assert reply.status_code == 200 and reply.headers["cache-control"] == "no-store"
        body = reply.json()
        assert body["summary"]["OVERDUE"] == 1 and body["items"][0]["state"] == "OVERDUE"

    @pytest.mark.parametrize("token", ["student", "officer"])
    def test_everyone_else_is_refused(self, client, token):
        assert client.get("/v1/knowledge/freshness", headers=auth(token)).status_code == 403
        assert client.post(f"/v1/knowledge/freshness/{A}/reviewed", headers=auth(token), json={"note": "Đã đối chiếu với bản gốc"}).status_code == 403

    def test_anonymous_is_refused(self, client):
        assert client.get("/v1/knowledge/freshness").status_code == 401

    def test_marking_reviewed_changes_the_next_report(self, client):
        assert client.post(f"/v1/knowledge/freshness/{A}/reviewed", headers=auth("kadmin"), json={"note": "Đã đối chiếu với bản gốc"}).status_code == 200
        items = {i["source_id"]: i for i in client.get("/v1/knowledge/freshness", headers=auth("kadmin")).json()["items"]}
        assert items[A]["state"] == "OK" and items[A]["last_review"]["note"] == "Đã đối chiếu với bản gốc"

    def test_bad_requests(self, client):
        assert client.post(f"/v1/knowledge/freshness/{A}/reviewed", headers=auth("kadmin"), json={"note": "ngắn"}).status_code == 422
        assert client.post("/v1/knowledge/freshness/not-a-uuid/reviewed", headers=auth("kadmin"), json={"note": "Đã đối chiếu với bản gốc"}).status_code == 422
        unknown = client.post(f"/v1/knowledge/freshness/{generate_uuid7()}/reviewed", headers=auth("kadmin"), json={"note": "Đã đối chiếu với bản gốc"})
        assert unknown.status_code == 404


class TestReviewStatusForReaders:
    """Any signed-in person can learn whether a cited source is overdue for review; nothing else about the report."""

    def test_a_student_gets_only_the_state_per_source_and_unknown_ids_are_left_out(self, client):
        unknown = generate_uuid7()
        reply = client.get("/v1/knowledge/source-review-status", params={"source_ids": f"{A},{B},{C},{unknown}"}, headers=auth("student"))
        assert reply.status_code == 200 and reply.headers["cache-control"] == "no-store"
        assert reply.json() == {"states": {A: "OVERDUE", B: "DUE_SOON", C: "OK"}}

    def test_anonymous_is_refused_and_bad_ids_are_422(self, client):
        assert client.get("/v1/knowledge/source-review-status", params={"source_ids": A}).status_code == 401
        for bad in ("", "not-a-uuid", ",".join(generate_uuid7() for _ in range(21))):
            assert client.get("/v1/knowledge/source-review-status", params={"source_ids": bad}, headers=auth("student")).status_code == 422

    def test_a_review_by_a_manager_shows_at_once(self, client):
        assert client.get("/v1/knowledge/source-review-status", params={"source_ids": A}, headers=auth("student")).json()["states"][A] == "OVERDUE"
        client.post(f"/v1/knowledge/freshness/{A}/reviewed", headers=auth("kadmin"), json={"note": "Đã đối chiếu với bản gốc"})
        assert client.get("/v1/knowledge/source-review-status", params={"source_ids": A}, headers=auth("student")).json()["states"][A] == "OK"

    @pytest.mark.asyncio
    async def test_the_database_is_read_once_inside_the_cache_window(self, tmp_path):
        conn = FakeConn(ROWS)
        service = FreshnessService(FakePool(conn), SourceReviewStore(tmp_path / "r.sqlite3"), tenant="t")
        await service.review_states([A], now=NOW)
        await service.review_states([B, C], now=NOW + timedelta(minutes=4))
        assert len(conn.queries) == 1
        await service.review_states([A], now=NOW + timedelta(minutes=6))
        assert len(conn.queries) == 2
