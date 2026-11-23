"""P2: a student reports "missing information" and agrees to send the (redacted) question. Nothing is linked to the person."""
from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from campus247.application.knowledge.gap_reports import CONSENT_VERSION, DAILY_LIMIT, GapReportStore, redact
from campus247.domain.shared.values import generate_uuid7
from campus247.ports.identity import IdentityContext, IdentityRole
from campus247.presentation.identity import IdentityMiddleware
from campus247.presentation.knowledge_quality import create_gap_report_router

NOW = datetime(2026, 11, 21, 3, 0, tzinfo=UTC)
D = timedelta(days=1)


@pytest.fixture
def store(tmp_path):
    return GapReportStore(tmp_path / "gap-reports.sqlite3")


class TestRedact:
    def test_hides_phone_email_identity_number_and_student_ids(self):
        text = "Em có mã số 20211234, gọi 0912 345 678, mail an@gmail.com, căn cước 012345678901 hỏi về học phí"
        result = redact(text)
        assert result is not None
        for leaked in ("20211234", "0912", "gmail", "012345678901"):
            assert leaked not in result
        assert "học phí" in result and "[đã ẩn]" in result

    def test_a_question_without_personal_data_is_unchanged(self):
        assert redact("Điều kiện xét học bổng khuyến khích học tập?") == "Điều kiện xét học bổng khuyến khích học tập?"

    def test_text_is_dropped_when_something_id_like_survives(self):
        assert redact("Mã của em là SV2021123 thì tra ở đâu") is None


class TestStore:
    def test_a_report_keeps_the_redacted_text_and_a_hashed_delete_code(self, store, tmp_path):
        receipt = store.submit("Học phí kỳ này nộp ở đâu? gọi 0912345678", at=NOW)
        assert receipt.text_kept and "0912345678" not in (receipt.question or "")
        raw = sqlite3.connect(tmp_path / "gap-reports.sqlite3").execute("SELECT * FROM gap_reports").fetchall()
        assert len(raw) == 1 and receipt.delete_code not in str(raw)  # only a hash of the code is stored
        columns = [c[1] for c in sqlite3.connect(tmp_path / "gap-reports.sqlite3").execute("PRAGMA table_info(gap_reports)")]
        assert not {"subject_id", "conversation_id", "user", "student_code"} & set(columns)

    def test_expires_after_90_days_and_is_purged(self, store):
        store.submit("Câu hỏi mới về lịch thi", at=NOW - 1 * D)
        store.submit("Câu hỏi cũ về lịch thi", at=NOW - 91 * D)
        assert [s["question"] for s in store.samples(now=NOW)] == ["Câu hỏi mới về lịch thi"]
        assert store.purge(now=NOW) == 1

    def test_the_delete_code_removes_the_report_once(self, store):
        receipt = store.submit("Câu hỏi về lịch thi", at=NOW)
        assert store.delete("sai-ma") is False
        assert store.delete(receipt.delete_code) is True
        assert store.delete(receipt.delete_code) is False
        assert store.samples(now=NOW) == []

    def test_an_unsafe_text_is_counted_but_not_kept(self, store):
        receipt = store.submit("Mã của em là SV2021123 thì tra ở đâu", at=NOW)
        assert receipt.text_kept is False and store.samples(now=NOW) == [] and store.total(now=NOW) == 1

    def test_a_daily_limit_stops_flooding(self, store):
        for _ in range(DAILY_LIMIT):
            store.submit("Câu hỏi về lịch thi", at=NOW)
        with pytest.raises(OverflowError):
            store.submit("Câu hỏi về lịch thi", at=NOW)


class Adapter:
    def __init__(self):
        self.contexts = {}

    def resolve_token(self, token):
        if token in self.contexts:
            return self.contexts[token]
        raise ValueError("bad token")


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
    app.include_router(create_gap_report_router(store, clock=lambda: NOW))
    with TestClient(app) as test_client:
        yield test_client


def auth(token):
    return {"Authorization": f"Bearer {token}"}


class TestApi:
    body = {"question": "Học phí kỳ này nộp ở đâu?", "consent": True, "consent_version": CONSENT_VERSION}

    def test_anonymous_cannot_report(self, client):
        assert client.post("/v1/answer-gap-reports", json=self.body).status_code == 401

    def test_a_student_who_consents_gets_a_receipt_and_the_kept_text(self, client):
        reply = client.post("/v1/answer-gap-reports", headers=auth("student"), json=self.body)
        assert reply.status_code == 201
        data = reply.json()
        assert data["text_kept"] is True and data["question"] == self.body["question"] and data["delete_code"] and data["expires_at"].startswith("2027-02-19")

    @pytest.mark.parametrize("change", [{"consent": False}, {"consent_version": "old"}, {"question": "ab"}, {"question": "x" * 501}])
    def test_no_consent_or_a_bad_body_stores_nothing(self, client, store, change):
        reply = client.post("/v1/answer-gap-reports", headers=auth("student"), json={**self.body, **change})
        assert reply.status_code == 422 and store.total(now=NOW) == 0

    def test_the_student_can_delete_with_the_code_only(self, client, store):
        code = client.post("/v1/answer-gap-reports", headers=auth("student"), json=self.body).json()["delete_code"]
        assert client.post("/v1/answer-gap-reports/delete", headers=auth("student"), json={"delete_code": "khong-dung"}).status_code == 404
        assert client.post("/v1/answer-gap-reports/delete", headers=auth("student"), json={"delete_code": code}).status_code == 200
        assert store.total(now=NOW) == 0

    def test_only_a_manager_reads_the_reports(self, client):
        client.post("/v1/answer-gap-reports", headers=auth("student"), json=self.body)
        assert client.get("/v1/knowledge/gap-reports", headers=auth("student")).status_code == 403
        assert client.get("/v1/knowledge/gap-reports", headers=auth("officer")).status_code == 403
        data = client.get("/v1/knowledge/gap-reports", headers=auth("kadmin")).json()
        assert data["total"] == 1 and [s["question"] for s in data["samples"]] == [self.body["question"]]
        assert "delete_code" not in str(data) and "subject" not in str(data)

    def test_responses_are_not_cached(self, client):
        reply = client.post("/v1/answer-gap-reports", headers=auth("student"), json=self.body)
        assert reply.headers["Cache-Control"] == "no-store"


class TestGrouping:
    def test_similar_questions_share_a_group_and_the_biggest_group_comes_first(self):
        from campus247.application.knowledge.gap_reports import group_samples
        rows = [
            {"id": 1, "at": "2026-11-20T01:00:00Z", "expires_at": "x", "question": "Học phí kỳ này nộp ở đâu?"},
            {"id": 2, "at": "2026-11-21T01:00:00Z", "expires_at": "x", "question": "Nộp học phí kỳ này ở đâu ạ"},
            {"id": 3, "at": "2026-11-21T02:00:00Z", "expires_at": "x", "question": "Lịch thi cuối kỳ lớp SQL khi nào"},
            {"id": 4, "at": "2026-11-19T01:00:00Z", "expires_at": "x", "question": "Hoc phi ky nay nop o dau"},
        ]
        groups = group_samples(rows)
        assert [g["count"] for g in groups] == [3, 1]
        assert sorted(groups[0]["ids"]) == [1, 2, 4] and groups[0]["last_at"] == "2026-11-21T01:00:00Z"
        assert groups[0]["question"] == "Nộp học phí kỳ này ở đâu ạ"  # the most recent wording represents the group

    def test_no_samples_no_groups(self):
        from campus247.application.knowledge.gap_reports import group_samples
        assert group_samples([]) == []

    def test_the_manager_list_carries_the_groups(self, client):
        for question in ("Học phí kỳ này nộp ở đâu?", "Nộp học phí kỳ này ở đâu ạ"):
            client.post("/v1/answer-gap-reports", headers=auth("student"), json={"question": question, "consent": True, "consent_version": CONSENT_VERSION})
        data = client.get("/v1/knowledge/gap-reports", headers=auth("kadmin")).json()
        assert [g["count"] for g in data["groups"]] == [2]
