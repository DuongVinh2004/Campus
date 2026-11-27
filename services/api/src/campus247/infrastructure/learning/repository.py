"""Durable aggregate adapter; all mutations serialize within a tenant.

Explicit aggregate storage keeps pointer, quota, receipt and outbox atomic.
It is intentionally separate from the existing actor and public-knowledge stores.
"""
import asyncio
import json
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path

import asyncpg

from campus247.application.learning.accessible_text import OCR_COLLECTIONS, OCR_READS
from campus247.application.learning.exit_tickets import (
    EXIT_TICKET_NOTICE,
    EXIT_TICKET_READS,
)
from campus247.application.learning.practice_sets import PRACTICE_COLLECTIONS
from campus247.application.learning.tutor import TUTOR_COLLECTIONS
from campus247.domain.learning import LearningError, require
from campus247.ports.learning_repository import COLLECTIONS, empty_state


class SQLiteLearningRepository:
    def __init__(self, path: Path, *, workspace: Path, tenant_id: str, create=False):
        root = workspace.resolve(strict=True)
        self.path = Path(path).absolute()
        require(self.path.parent.resolve(strict=True).is_relative_to(root), 503, "INVALID_STORAGE", "Kho học liệu nằm ngoài workspace.")
        require(not self.path.is_symlink(), 503, "INVALID_STORAGE", "Kho học liệu không được là liên kết.")
        self.tenant_id, self.lock = tenant_id, asyncio.Lock()
        require(bool(tenant_id), 503, "INVALID_TENANT", "Chưa cấu hình phạm vi học liệu.")
        if create:
            require(not self.path.exists(), 409, "STORE_EXISTS", "Kho đã tồn tại; không khởi tạo lại.")
            with self.path.open("xb"):
                pass
            with self._connect() as db:
                db.execute("CREATE TABLE learning_state (tenant_id TEXT PRIMARY KEY, revision INTEGER NOT NULL, payload TEXT NOT NULL)")
                db.execute("INSERT INTO learning_state VALUES (?, 1, ?)", (tenant_id, json.dumps(empty_state())))
        else:
            require(self.path.is_file(), 503, "STORAGE_UNAVAILABLE", "Kho học liệu chưa được khởi tạo.")
        with self._connect() as db:
            require(db.execute("SELECT 1 FROM learning_state WHERE tenant_id=?", (tenant_id,)).fetchone() is not None, 503, "STORAGE_UNAVAILABLE", "Kho học liệu không đúng phạm vi.")

    def _connect(self):
        db = sqlite3.connect(str(self.path), timeout=15, isolation_level=None)
        db.execute("PRAGMA busy_timeout=15000")
        db.execute("PRAGMA synchronous=FULL")
        return db

    @asynccontextmanager
    async def transaction(self):
        async with self.lock:
            db = self._connect()
            try:
                db.execute("BEGIN IMMEDIATE")
                row = db.execute("SELECT revision,payload FROM learning_state WHERE tenant_id=?", (self.tenant_id,)).fetchone()
                require(row is not None, 503, "STORAGE_UNAVAILABLE", "Kho học liệu không khả dụng.")
                state = json.loads(row[1])
                before = json.dumps(state, sort_keys=True, separators=(",", ":"))
                yield state
                after = json.dumps(state, sort_keys=True, separators=(",", ":"))
                if before != after:
                    db.execute("UPDATE learning_state SET payload=?,revision=revision+1 WHERE tenant_id=? AND revision=?", (after, self.tenant_id, row[0]))
                db.commit()
            except Exception:
                db.rollback()
                raise
            finally:
                db.close()


class PostgresLearningRepository:
    """Pool must be explicitly bound to the verified deployment database.

Provision using migration0023 and provision_tenant; reads never auto-create rows.
"""
    def __init__(self, pool, *, tenant_id: str, page_feedback_schema: bool = False, page_explanations_schema: bool = False, version_changes_schema: bool = False, exit_tickets_schema: bool = False, idea_cards_schema: bool = False, accessible_text_schema: bool = False, practice_schema: bool = False, tutor_schema: bool = False):
        require(bool(tenant_id), 503, "INVALID_TENANT", "Chưa cấu hình phạm vi học liệu.")
        self.pool, self.tenant_id = pool, tenant_id
        self.collections = COLLECTIONS + ("feedback_windows", "page_feedback") if page_feedback_schema else COLLECTIONS
        if page_explanations_schema:
            self.collections += ("page_explanations",)
        if version_changes_schema:
            self.collections += ("version_change_revisions",)
        if exit_tickets_schema:
            self.collections += ("exit_tickets", "exit_submissions", "exit_reviews")
        if idea_cards_schema:
            self.collections += ("idea_topics", "idea_cards", "idea_shares", "idea_grants")
        if accessible_text_schema:
            self.collections += OCR_COLLECTIONS
        if practice_schema:
            # Order matters for the write: a set is stored before its questions, a question before answers and review state.
            self.collections += PRACTICE_COLLECTIONS
        if tutor_schema:
            # After the practice collections: a hint row points at its question, a mastery row at its concept.
            require(practice_schema, 503, "INVALID_SCHEMA", "Gia sư cần bảng ôn tập.")
            self.collections += TUTOR_COLLECTIONS

    async def provision_tenant(self):
        async with self.pool.acquire() as db:
            await db.execute("INSERT INTO learning.tenant_state(tenant_id,revision) VALUES($1,1) ON CONFLICT DO NOTHING", self.tenant_id)

    @asynccontextmanager
    async def read_view(self, actor, kind, target=None, params=None):
        """Read only authorized class rows without taking the tenant write lock."""
        params = params or {}
        try:
            async with self.pool.acquire() as db, db.transaction(readonly=True, isolation="repeatable_read"):
                exists = await db.fetchval("SELECT 1 FROM learning.tenant_state WHERE tenant_id=$1", self.tenant_id)
                require(exists == 1, 503, "STORAGE_UNAVAILABLE", "Kho học liệu chưa được cấp phát.")
                state = empty_state()
                async def rows(table, condition="TRUE", *values, projection="payload"):
                    require(table in self.collections, 503, "INVALID_COLLECTION", "Kho học liệu không hợp lệ.")
                    data = await db.fetch(f"SELECT record_key,{projection} AS payload FROM learning.{table} WHERE tenant_id=$1 AND ({condition})", self.tenant_id, *values)
                    result = {}
                    for record in data:
                        value = json.loads(record["payload"]) if isinstance(record["payload"], str) else record["payload"]
                        result[record["record_key"]] = value
                    return result
                admin = actor.has_role("SYSTEM_ADMIN")
                roles = (["INSTRUCTOR"] if actor.has_role("LECTURER") else []) + (["STUDENT"] if actor.has_role("STUDENT") else [])
                state["members"] = await rows("members", "actor_subject_id=$2 AND payload->>'status'='ACTIVE' AND role=ANY($3::text[])", actor.subject_id, roles)
                allowed = sorted({r["offering_id"] for r in state["members"].values()})
                teaching = sorted({r["offering_id"] for r in state["members"].values() if r["role"] == "INSTRUCTOR"})
                if kind in {"terms", "courses", "admin_offerings"}:
                    if admin:
                        table = "offerings" if kind == "admin_offerings" else kind
                        state[table] = await rows(table)
                        if kind == "admin_offerings":
                            state["terms"] = await rows("terms")
                    yield state
                    return
                if kind in {"capabilities", "directory"}:
                    yield state
                    return
                if kind in {"offering", "offerings"}:
                    scope = allowed if kind == "offerings" else [target] if target in allowed else []
                    state["offerings"] = await rows("offerings", "record_key=ANY($2::text[])", scope)
                    term_ids = sorted({offering["term_id"] for offering in state["offerings"].values()})
                    state["terms"] = await rows("terms", "record_key=ANY($2::text[])", term_ids)
                    yield state
                    return
                if kind == "members" and admin:
                    state["members"] = await rows("members", "offering_id=$2", target)
                    yield state
                    return
                if kind == "session_contexts":
                    state["versions"] = await rows(
                        "versions", "record_key=$2 AND offering_id=ANY($3::text[])", target, allowed
                    )
                    version = state["versions"].get(target)
                    if version:
                        offering_id, material_id = version["offering_id"], version["material_id"]
                        state["offerings"] = await rows("offerings", "record_key=$2", offering_id)
                        state["materials"] = await rows("materials", "record_key=$2 AND offering_id=$3", material_id, offering_id)
                        state["links"] = await rows("links", "material_id=$2 AND offering_id=$3", material_id, offering_id)
                        session_ids = [link["session_id"] for link in state["links"].values() if link.get("active", True)]
                        state["sessions"] = await rows(
                            "sessions", "offering_id=$2 AND record_key=ANY($3::text[])", offering_id, session_ids
                        )
                    yield state
                    return
                if kind in EXIT_TICKET_READS:
                    column = "session_id" if kind == "exit_tickets" else "record_key"
                    state["exit_tickets"] = await rows(
                        "exit_tickets", f"{column}=$2 AND offering_id=ANY($3::text[]) "
                        "AND (offering_id=ANY($4::text[]) OR published_question_revision IS NOT NULL)", target, allowed, teaching,
                    )
                    tickets = list(state["exit_tickets"].values())
                    session_ids = sorted({row["session_id"] for row in tickets} | ({target} if kind == "exit_tickets" else set()))
                    state["sessions"] = await rows("sessions", "record_key=ANY($2::text[]) AND offering_id=ANY($3::text[])", session_ids, allowed)
                    scope = sorted({row["offering_id"] for row in state["sessions"].values()})
                    state["offerings"] = await rows("offerings", "record_key=ANY($2::text[])", scope)
                    if kind == "exit_submission" and tickets and tickets[0]["offering_id"] not in teaching:
                        state["exit_submissions"] = await rows(
                            "exit_submissions", "ticket_id=$2 AND student_id=$3", target, actor.subject_id,
                        )
                    if kind != "exit_submission" and tickets:
                        version_ids = sorted({row["version_id"] for row in tickets})
                        material_ids = sorted({row["material_id"] for row in tickets})
                        state["versions"] = await rows("versions", "record_key=ANY($2::text[]) AND offering_id=ANY($3::text[])", version_ids, scope)
                        state["materials"] = await rows("materials", "record_key=ANY($2::text[]) AND offering_id=ANY($3::text[])", material_ids, scope)
                        state["links"] = await rows("links", "session_id=ANY($2::text[]) AND material_id=ANY($3::text[]) AND offering_id=ANY($4::text[])", session_ids, material_ids, scope)
                        if kind == "exit_submissions" and tickets[0]["offering_id"] in teaching:
                            state["exit_submissions"] = await rows("exit_submissions", "ticket_id=$2 AND offering_id=ANY($3::text[])", target, teaching)
                        if kind == "exit_review":
                            state["exit_reviews"] = await rows("exit_reviews", "record_key=$2", target)
                    yield state
                    return
                if kind in OCR_READS:
                    await self._read_ocr_view(state, rows, kind, target, params, allowed, teaching)
                    yield state
                    return
                scope = list(allowed)
                direct_class = {"members", "sessions", "presentations"}
                resource_table = {"materials": "sessions", "reading-instructions": "sessions", "material": "materials", "versions": "materials", "version": "versions", "content": "versions", "reader_state": "versions", "questions": "versions", "presentation": "presentations"}
                if kind in direct_class:
                    scope = [target] if target in allowed else []
                elif kind in resource_table:
                    candidates = await rows(resource_table[kind], "record_key=$2 AND offering_id=ANY($3::text[])", target, allowed)
                    scope = sorted({r["offering_id"] for r in candidates.values()})
                state["offerings"] = await rows("offerings", "record_key=ANY($2::text[])", scope)
                state["members"] = {k: v for k, v in state["members"].items() if v["offering_id"] in scope}
                if kind == "members":
                    if target in teaching:
                        state["members"] = await rows("members", "offering_id=$2", target)
                    yield state
                    return
                if kind in {"sessions", "materials", "reading-instructions"}:
                    state["sessions"] = await rows("sessions", "offering_id=ANY($2::text[])", scope)
                state["materials"] = await rows("materials", "offering_id=ANY($2::text[]) AND (offering_id=ANY($3::text[]) OR payload->>'visibility'='VISIBLE')", scope, teaching)
                material_ids = list(state["materials"])
                state["versions"] = await rows("versions", "offering_id=ANY($2::text[]) AND material_id=ANY($3::text[]) AND (offering_id=ANY($4::text[]) OR payload->>'publication_state'='PUBLISHED')", scope, material_ids, teaching)
                version_ids = list(state["versions"])
                if kind == 'content':
                    view_ids = [row['view_blob_id'] for row in state['versions'].values() if row.get('view_blob_id')]
                    state['blobs'] = await rows('blobs', 'record_key=ANY($2::text[])', view_ids)
                if kind == "materials":
                    state["links"] = await rows("links", "session_id=$2 AND offering_id=ANY($3::text[])", target, scope)
                if kind == "reader_state":
                    state["reader_states"] = await rows("reader_states", "record_key=$2 AND version_id=ANY($3::text[])", actor.subject_id + ":" + target, version_ids)
                if kind in {"bookmarks", "notifications", "annotations"}:
                    owner = "owner_id" if kind == "annotations" else "actor_id"
                    condition = f"payload->>'{owner}'=$2 AND version_id=ANY($3::text[])"
                    values = [actor.subject_id, version_ids]
                    if params.get("version_id"):
                        condition += " AND version_id=$4"
                        values.append(params["version_id"])
                    state[kind] = await rows(kind, condition, *values)
                    if kind == "notifications":
                        question_ids = sorted({item["question_id"] for item in state[kind].values() if item.get("question_id")})
                        if question_ids:
                            state["questions"] = await rows("questions", "record_key=ANY($2::text[]) AND version_id=ANY($3::text[])", question_ids, version_ids)
                        linked_notice_sessions = sorted({
                            item["session_id"] for item in state[kind].values()
                            if item.get("event_type") in {"PAGE_EXPLANATION_PUBLISHED", EXIT_TICKET_NOTICE}
                        })
                        if linked_notice_sessions:
                            state["sessions"] = await rows("sessions", "record_key=ANY($2::text[]) AND offering_id=ANY($3::text[])", linked_notice_sessions, scope)
                            state["links"] = await rows("links", "session_id=ANY($2::text[]) AND material_id=ANY($3::text[]) AND offering_id=ANY($4::text[])", linked_notice_sessions, material_ids, scope)
                if kind == "questions":
                    current_teaching = bool(set(scope) & set(teaching))
                    state["questions"] = await rows("questions", "version_id=$2 AND version_id=ANY($3::text[]) AND (payload->>'visibility'='CLASS' OR payload->>'author_id'=$4 OR $5::boolean)", target, version_ids, actor.subject_id, current_teaching)
                    private_access = [key for key, question in state["questions"].items() if current_teaching or question["author_id"] == actor.subject_id]
                    state["replies"] = await rows("replies", "question_id=ANY($2::text[]) AND (question_id=ANY($3::text[]) OR COALESCE(payload->>'visibility','CLASS')='CLASS')", list(state["questions"]), private_access)
                if kind == "reading-instructions":
                    state["reading_instructions"] = await rows("reading_instructions", "session_id=$2 AND offering_id=ANY($3::text[]) AND version_id=ANY($4::text[])", target, scope, version_ids)
                if kind in {"presentation", "presentations"}:
                    state["presentations"] = await rows("presentations", "offering_id=ANY($2::text[]) AND version_id=ANY($3::text[])", scope, version_ids)
                if kind == "upload":
                    state["uploads"] = await rows("uploads", "record_key=$2 AND payload->>'actor_id'=$3 AND offering_id=ANY($4::text[])", target, actor.subject_id, teaching)
                yield state
        except (asyncpg.PostgresError, ConnectionError, TimeoutError):
            raise LearningError(503, "STORAGE_UNAVAILABLE", "Kho học liệu chưa sẵn sàng.") from None

    @staticmethod
    async def _read_ocr_view(state, rows, kind, target, params, allowed, teaching):
        version_id = target
        public = kind in {"accessible_text", "accessible_text_page", "accessible_text_search"}
        if kind in {"ocr_job", "ocr_release"}:
            table = "ocr_jobs" if kind == "ocr_job" else "ocr_releases"
            state[table] = await rows(table, "record_key=$2 AND version_id IN (SELECT record_key FROM "
                                      "learning.versions WHERE tenant_id=$1 AND offering_id=ANY($3::text[]))", target, allowed)
            version_id = state[table].get(target, {}).get("version_id")
        if version_id is None:
            return
        state["versions"] = await rows("versions", "record_key=$2 AND offering_id=ANY($3::text[])", version_id, allowed)
        version = state["versions"].get(version_id)
        if version is None:
            return
        offering_id = version["offering_id"]
        state["offerings"] = await rows("offerings", "record_key=$2", offering_id)
        state["materials"] = await rows("materials", "record_key=$2 AND offering_id=$3", version["material_id"], offering_id)
        if version.get("view_blob_id"):
            state["blobs"] = await rows("blobs", "record_key=$2", version["view_blob_id"])
        if public:
            release_id = version.get("accessible_text_release_id")
            material = state["materials"].get(version["material_id"], {})
            if not release_id or version["publication_state"] != "PUBLISHED" or material.get("visibility") != "VISIBLE":
                return
            state["ocr_releases"] = await rows("ocr_releases", "record_key=$2 AND version_id=$3", release_id, version_id)
            release = state["ocr_releases"].get(release_id)
            if release and release["state"] == "PUBLISHED" and kind != "accessible_text":
                pages = release.get("published_pages", [])
                if kind == "accessible_text_page":
                    pages = [params["page_no"]] if params.get("page_no") in pages else []
                state["ocr_release_pages"] = await rows("ocr_release_pages", "release_id=$2 AND page_no=ANY($3::int[])", release_id, pages)
            return
        if offering_id not in teaching:
            return
        if kind == "ocr_jobs":
            state["ocr_jobs"] = await rows("ocr_jobs", "offering_id=$2", offering_id)
            state["ocr_releases"] = await rows("ocr_releases", "version_id=$2", version_id)
        elif kind == "ocr_release":
            job_id = state["ocr_releases"][target]["job_id"]
            state["ocr_jobs"] = await rows("ocr_jobs", "record_key=$2", job_id)
            if (page := params.get("page_no")) is not None:
                state["ocr_page_results"] = await rows("ocr_page_results", "job_id=$2 AND page_no=$3", job_id, page)
        if kind in {"ocr_job", "ocr_jobs"}:
            job_ids = [job["id"] for job in state["ocr_jobs"].values() if job["version_id"] == version_id]
            state["ocr_page_results"] = await rows("ocr_page_results", "job_id=ANY($2::text[])", job_ids,
                                                    projection="jsonb_build_object('job_id', job_id)")
        release_ids = list(state.get("ocr_releases", {}))
        if release_ids:
            state["ocr_release_pages"] = await rows("ocr_release_pages", "release_id=ANY($2::text[])", release_ids,
                                                     projection="jsonb_build_object('release_id', release_id, 'page_no', page_no)")
            if kind == "ocr_release" and (page := params.get("page_no")) is not None:
                state["ocr_release_pages"].update(await rows("ocr_release_pages", "release_id=$2 AND page_no=$3", target, page))

    @asynccontextmanager
    async def transaction(self):
        try:
            async with self._write_transaction() as state:
                yield state
        except (asyncpg.PostgresError, ConnectionError, TimeoutError):
            raise LearningError(503, "STORAGE_UNAVAILABLE", "Kho học liệu chưa sẵn sàng.") from None

    @asynccontextmanager
    async def exit_submission_transaction(self, actor_id, ticket_id, receipt_key):
        require("exit_tickets" in self.collections)
        try:
            async with self._write_transaction((actor_id, ticket_id, receipt_key)) as state:
                yield state
        except (asyncpg.PostgresError, ConnectionError, TimeoutError):
            raise LearningError(503, "STORAGE_UNAVAILABLE", "Kho học liệu chưa sẵn sàng.") from None

    async def _load_exit_submission(self, db, actor_id, ticket_id, receipt_key):
        # Called after locking the same tenant row as publication and enrollment.
        # Only the student's own submission and idempotency receipt enter this transaction.
        return await db.fetch("""
            WITH ticket AS (
                SELECT record_key, payload, offering_id, session_id, version_id
                FROM learning.exit_tickets WHERE tenant_id=$1 AND record_key=$3
            ), source AS (
                SELECT v.record_key, v.payload, v.material_id FROM learning.versions v
                JOIN ticket t ON v.record_key=t.version_id WHERE v.tenant_id=$1
            )
            SELECT 'exit_tickets' AS collection, record_key, payload FROM ticket
            UNION ALL SELECT 'versions', record_key, payload FROM source
            UNION ALL SELECT 'members', m.record_key, m.payload FROM learning.members m
                JOIN ticket t ON m.offering_id=t.offering_id WHERE m.tenant_id=$1 AND m.actor_subject_id=$2
            UNION ALL SELECT 'offerings', o.record_key, o.payload FROM learning.offerings o
                JOIN ticket t ON o.record_key=t.offering_id WHERE o.tenant_id=$1
            UNION ALL SELECT 'sessions', s.record_key, s.payload FROM learning.sessions s
                JOIN ticket t ON s.record_key=t.session_id WHERE s.tenant_id=$1
            UNION ALL SELECT 'materials', m.record_key, m.payload FROM learning.materials m
                JOIN source v ON m.record_key=v.material_id WHERE m.tenant_id=$1
            UNION ALL SELECT 'links', l.record_key, l.payload FROM learning.links l
                JOIN ticket t ON l.session_id=t.session_id JOIN source v ON l.material_id=v.material_id
                WHERE l.tenant_id=$1
            UNION ALL SELECT 'exit_submissions', record_key, payload FROM learning.exit_submissions
                WHERE tenant_id=$1 AND record_key=$3 || ':' || $2
            UNION ALL SELECT 'receipts', record_key, payload FROM learning.receipts
                WHERE tenant_id=$1 AND record_key=$4
            """, self.tenant_id, actor_id, ticket_id, receipt_key)

    @asynccontextmanager
    async def _write_transaction(self, exit_submission=None):
        async with self.pool.acquire() as db, db.transaction():
            row = await db.fetchrow("SELECT revision FROM learning.tenant_state WHERE tenant_id=$1 FOR UPDATE", self.tenant_id)
            require(row is not None, 503, "STORAGE_UNAVAILABLE", "Kho học liệu chưa được cấp phát.")
            state = empty_state()
            if exit_submission is None:
                for collection in self.collections:
                    state.setdefault(collection, {})
                    records = await db.fetch(f"SELECT record_key,payload FROM learning.{collection} WHERE tenant_id=$1", self.tenant_id)
                    for record in records:
                        state[collection][record["record_key"]] = json.loads(record["payload"]) if isinstance(record["payload"], str) else record["payload"]
            else:
                state.update(exit_tickets={}, exit_submissions={})
                for record in await self._load_exit_submission(db, *exit_submission):
                    payload = record["payload"]
                    state[record["collection"]][record["record_key"]] = json.loads(payload) if isinstance(payload, str) else payload
            before = json.dumps(state, sort_keys=True, separators=(",", ":"))
            original = json.loads(before)
            yield state
            after = json.dumps(state, sort_keys=True, separators=(",", ":"))
            if before != after:
                collections = self.collections if exit_submission is None else ("exit_submissions", "receipts", "audit")
                if exit_submission is not None:
                    require(all(state[name] == original.get(name) for name in state.keys() - set(collections)),
                            503, "INVALID_COLLECTION", "Thao tác ghi vượt phạm vi kho học liệu.")
                for collection in collections:
                    require(set(original[collection]).issubset(state[collection]), 409, "DATA_REMOVAL_PROHIBITED", "Không được xóa bản ghi học liệu.")
                    for key, value in state[collection].items():
                        if original[collection].get(key) != value:
                            await db.execute(f"INSERT INTO learning.{collection}(tenant_id,record_key,payload) VALUES($1,$2,$3::jsonb) ON CONFLICT(tenant_id,record_key) DO UPDATE SET payload=excluded.payload", self.tenant_id, key, json.dumps(value))
                await db.execute("UPDATE learning.tenant_state SET revision=revision+1,updated_at=clock_timestamp() WHERE tenant_id=$1 AND revision=$2", self.tenant_id, row["revision"])
