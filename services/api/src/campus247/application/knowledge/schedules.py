"""Durable, session-scoped URL checks and effective-date readiness.

No service identity, session renewal, review, or publication authority is
invented here. A background tick must revalidate the actual signed session.
Definitions, cancellations and slot outcomes are additive idempotency records;
restarting the application requires a new authenticated resume request.
"""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from campus247.application.knowledge.document_identity import RefreshUrlInput
from campus247.application.knowledge.intake import KnowledgeIntake
from campus247.application.knowledge.platform_models import PlatformError, digest
from campus247.domain.shared.values import generate_uuid7
from campus247.application.knowledge.platform_models import json_value

SCHEMA = "knowledge-session-schedule-v1"


class ScheduleInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["URL_REFRESH", "RELEASE_DUE"]
    target_id: UUID
    not_before: datetime
    expires_at: datetime
    interval_seconds: int = Field(default=3600, ge=900, le=86400)
    expected_original_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    expected_generation: int | None = Field(default=None, ge=0)
    confirmed: Literal[True]

    @model_validator(mode="after")
    def validate_schedule(self):
        for value in (self.not_before, self.expires_at):
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError("Schedule times require an explicit timezone")
        if self.expires_at <= self.not_before:
            raise ValueError("Schedule expiry must follow its first due time")
        if self.kind == "URL_REFRESH" and (self.expected_original_sha256 is None or self.expected_generation is not None):
            raise ValueError("A URL schedule needs its exact original hash only")
        if self.kind == "RELEASE_DUE" and (self.expected_generation is None or self.expected_original_sha256 is not None):
            raise ValueError("A release readiness schedule needs its expected generation only")
        return self


def due_slot(definition, now):
    """Coalesce missed URL intervals; never replay a backlog on restart."""
    start, end = (datetime.fromisoformat(definition[field]) for field in ("not_before", "expires_at"))
    if now < start or now >= end:
        return None
    if definition["kind"] == "RELEASE_DUE":
        return 0
    return int((now-start).total_seconds()) // definition["interval_seconds"]


class KnowledgeSchedules:
    def __init__(self, platform):
        self.platform, self.repo = platform, platform.repo
        self.intake = KnowledgeIntake(platform)
        self._sessions = {}
        self.running = False

    def _current(self, actor, revalidate):
        # The callback comes from the authenticated transport, never from a
        # stored document, schedule, actor ID, or caller-supplied identity JSON.
        current = revalidate()
        self.platform.admin(current)
        if (current.subject_id, current.tenant_id, current.session_id, current.issuer) != (
                actor.subject_id, actor.tenant_id, actor.session_id, actor.issuer):
            raise PlatformError(403, "SCHEDULE_SESSION_CHANGED", "Lịch cần đúng phiên quản trị đã cấu hình.")
        return current

    def resume(self, actor, revalidate):
        self._current(actor, revalidate)
        self._sessions[(actor.subject_id, actor.session_id)] = (actor, revalidate)
        return {"state": "SESSION_BOUND", "expires_at": actor.expires_at.isoformat(),
            "publication_authority": False, "survives_session_expiry": False}

    async def _binding(self, conn, body):
        if body.kind == "URL_REFRESH":
            row = await conn.fetchrow("""SELECT f.original_id,f.acquisition,a.sha256,a.object_key,a.byte_size,a.media_type
                FROM knowledge_intake_fetch f JOIN knowledge_artifact a ON a.id=f.original_id AND a.tenant_id=f.tenant_id
                WHERE f.intake_id=$1 AND f.tenant_id=$2""", body.target_id, self.repo.tenant)
            if not row or row["sha256"] != body.expected_original_sha256:
                raise PlatformError(409, "SOURCE_FETCH_BINDING", "Cần đúng hồ sơ URL đã tải và hash nguồn.")
            self.platform.storage.read(row)
            acquisition = json_value(row["acquisition"])
            from campus247.application.knowledge.values import public_document_url
            public_document_url(acquisition["requested_url"])
            return {"acquisition_sha256": digest(acquisition), "original_sha256": row["sha256"]}
        pointer = await self.repo.pointer(conn)
        if pointer["generation"] != body.expected_generation:
            raise PlatformError(409, "STALE_GENERATION", "Release đã đổi; tải lại.")
        release, members = await self.platform._release(conn, str(body.target_id))
        for member in members:
            version = await self.platform._eligible(conn, member["version_id"])
            if version["effective_from"] and body.not_before < version["effective_from"]:
                raise PlatformError(422, "SCHEDULE_BEFORE_EFFECTIVE", "Lịch kiểm hiệu lực không được sớm hơn ngày áp dụng đã xác minh.")
        if str(release["predecessor_id"] or "") != str(pointer["release_id"] or ""):
            raise PlatformError(409, "STALE_RELEASE_BASE", "Cần dựng release trên membership hiện tại.")
        return {"membership_sha256": release["membership_sha256"], "profile_sha256": digest(json_value(release["profile"])),
            "pointer": pointer}

    async def create(self, actor, body, key, revalidate):
        self._current(actor, revalidate)
        now = datetime.now(UTC)
        if body.expires_at > actor.expires_at or body.expires_at <= now:
            raise PlatformError(422, "SCHEDULE_SESSION_LIMIT", "Lịch phải kết thúc trong thời hạn phiên hiện tại.")
        fingerprint = digest({"schedule": body.model_dump(mode="json"), "session_id": actor.session_id, "issuer": actor.issuer})
        async with self.repo.transaction() as conn:
            replay = await self.repo.replay(conn, actor.subject_id, "schedule:create:"+key, fingerprint)
            if replay:
                self.resume(actor, revalidate)
                return {**replay, "is_replay": True}
            binding = await self._binding(conn, body)
            definition = {**body.model_dump(mode="json", exclude={"confirmed"}), "id": generate_uuid7(), "schema": SCHEMA,
                "session_id": actor.session_id, "issuer": actor.issuer, "binding": binding,
                "created_at": now.isoformat(), "publication_authority": False}
            self._current(actor, revalidate)
            await self.repo.remember(conn, actor.subject_id, "schedule:create:"+key, fingerprint, definition)
            await self.repo.audit(conn, actor.subject_id, "knowledge.schedule.created", definition["id"],
                {"kind": body.kind, "definition_sha256": digest(definition), "publication_authority": False})
        self.resume(actor, revalidate)
        return definition

    async def _definitions(self, conn, actor, *, current_session=False, identifier=None):
        # Filter before LIMIT. Cancelled, expired, future or already consumed
        # definitions must not hide an older due schedule behind recent history.
        due_filter = """AND (result->>'not_before')::timestamptz<=clock_timestamp()
            AND (result->>'expires_at')::timestamptz>clock_timestamp()
            AND NOT EXISTS(SELECT 1 FROM knowledge_platform_request cancelled
                WHERE cancelled.tenant_id=definition.tenant_id AND cancelled.actor_id=definition.actor_id
                AND cancelled.request_key='schedule:cancel:'||(definition.result->>'id'))
            AND NOT EXISTS(SELECT 1 FROM knowledge_platform_request consumed
                WHERE consumed.tenant_id=definition.tenant_id AND consumed.actor_id=definition.actor_id
                AND consumed.request_key='schedule:run:'||(definition.result->>'id')||':'||
                    CASE WHEN definition.result->>'kind'='RELEASE_DUE' THEN '0'
                    ELSE floor(extract(epoch FROM (clock_timestamp()-(definition.result->>'not_before')::timestamptz)) /
                        (definition.result->>'interval_seconds')::integer)::bigint::text END)""" if current_session else ""
        rows = await conn.fetch("""SELECT result FROM knowledge_platform_request definition WHERE tenant_id=$1 AND actor_id=$2
            AND request_key LIKE 'schedule:create:%' AND result->>'schema'=$3
            AND ($4::text IS NULL OR result->>'session_id'=$4) AND ($5::text IS NULL OR result->>'id'=$5)
            """+due_filter+" ORDER BY created_at "+("ASC" if current_session else "DESC")+" LIMIT 200",
            self.repo.tenant, actor.subject_id, SCHEMA, actor.session_id if current_session else None, str(identifier) if identifier else None)
        return [json_value(row["result"]) for row in rows]

    async def list(self, actor):
        self.platform.admin(actor)
        async with self.repo.transaction() as conn:
            definitions = await self._definitions(conn, actor)
            items = []
            for definition in definitions:
                cancelled = await conn.fetchval("""SELECT EXISTS(SELECT 1 FROM knowledge_platform_request
                    WHERE tenant_id=$1 AND actor_id=$2 AND request_key=$3)""",
                    self.repo.tenant, actor.subject_id, "schedule:cancel:"+definition["id"])
                last = await conn.fetchval("""SELECT result FROM knowledge_platform_request
                    WHERE tenant_id=$1 AND actor_id=$2 AND request_key LIKE $3 ORDER BY created_at DESC LIMIT 1""",
                    self.repo.tenant, actor.subject_id, "schedule:run:"+definition["id"]+":%")
                state = ("CANCELLED" if cancelled else "EXPIRED" if datetime.now(UTC) >= datetime.fromisoformat(definition["expires_at"])
                    else "SESSION_REQUIRED" if definition["session_id"] != actor.session_id or (actor.subject_id, actor.session_id) not in self._sessions
                    else "ACTIVE")
                items.append({**definition, "state": state, "can_resume": definition["session_id"] == actor.session_id,
                    "last_outcome": json_value(last) if last else None})
            return {"items": items, "publication_authority": False,
                "session_expires_at": actor.expires_at.isoformat(), "background_running": self.running}

    async def cancel(self, actor, identifier):
        self.platform.admin(actor)
        async with self.repo.transaction() as conn:
            await conn.execute("SELECT pg_advisory_xact_lock(hashtextextended($1,0))",
                self.repo.tenant+":schedule:"+str(identifier))
            definitions = await self._definitions(conn, actor, identifier=identifier)
            if not any(item["id"] == str(identifier) for item in definitions):
                raise PlatformError(404, "SCHEDULE_NOT_FOUND", "Không có lịch trong phạm vi này.")
            key = "schedule:cancel:"+str(identifier)
            fingerprint = digest({"cancel": str(identifier)})
            replay = await self.repo.replay(conn, actor.subject_id, key, fingerprint)
            if replay:
                return {**replay, "is_replay": True}
            result = {"id": str(identifier), "state": "CANCELLED"}
            await self.repo.remember(conn, actor.subject_id, key, fingerprint, result)
            await self.repo.audit(conn, actor.subject_id, "knowledge.schedule.cancelled", str(identifier), result)
            return result

    async def tick(self, actor, revalidate):
        self._current(actor, revalidate)
        async with self.repo.transaction() as conn:
            definitions = await self._definitions(conn, actor, current_session=True)
        outcomes = []
        for definition in definitions:
            if len(outcomes) >= 20:
                break
            if definition["session_id"] != actor.session_id or definition["issuer"] != actor.issuer:
                continue
            slot = due_slot(definition, datetime.now(UTC))
            if slot is None:
                continue
            async with self.repo.transaction() as conn:
                await conn.execute("SELECT pg_advisory_xact_lock(hashtextextended($1,0))",
                    self.repo.tenant+":schedule:"+definition["id"])
                if await conn.fetchval("""SELECT EXISTS(SELECT 1 FROM knowledge_platform_request
                    WHERE tenant_id=$1 AND actor_id=$2 AND request_key=$3)""",
                    self.repo.tenant, actor.subject_id, "schedule:cancel:"+definition["id"]):
                    continue
                key = "schedule:run:"+definition["id"]+":"+str(slot)
                fingerprint = digest({"definition": definition, "slot": slot})
                replay = await self.repo.replay(conn, actor.subject_id, key, fingerprint)
                if replay:
                    continue
                self._current(actor, revalidate)
                # Lock order matches every identity/release decision command.
                from campus247.application.knowledge.edition_release import lock_decisions
                await lock_decisions(self.platform, conn)
                try:
                    # Savepoint: a rejected command cannot leave partial source/job writes.
                    async with conn.transaction():
                        outcome = await self._run(conn, actor, definition, key, revalidate)
                except PlatformError as error:
                    outcome = {"state": "BLOCKED", "code": error.code}
                self._current(actor, revalidate)
                result = {"schedule_id": definition["id"], "slot": slot, "at": datetime.now(UTC).isoformat(),
                    "publication_authority": False, **outcome}
                await self.repo.remember(conn, actor.subject_id, key, fingerprint, result)
                await self.repo.audit(conn, actor.subject_id, "knowledge.schedule.tick", definition["id"], result)
                outcomes.append(result)
        return {"outcomes": outcomes, "publication_authority": False}

    async def _run(self, conn, actor, definition, key, revalidate):
        if definition["kind"] == "RELEASE_DUE":
            body = ScheduleInput.model_validate({k: definition[k] for k in ScheduleInput.model_fields if k != "confirmed"} | {"confirmed": True})
            binding = await self._binding(conn, body)
            if binding != definition["binding"]:
                raise PlatformError(409, "SCHEDULE_BINDING_CHANGED", "Căn cứ hoặc pointer đã đổi; cần đối chiếu lại.")
            release, members = await self.platform._release(conn, str(body.target_id))
            versions = [await self.platform._eligible(conn, member["version_id"], publisher=actor.subject_id) for member in members]
            self.platform.activation_time(versions)
            from campus247.application.knowledge.edition_release import activation_resolution
            activation_resolution(*release["_edition_state"])
            return {"state": "AWAITING_CONFIRMATION", "release_id": str(body.target_id), "expected_generation": body.expected_generation}
        last = await conn.fetchval("""SELECT result FROM knowledge_platform_request
            WHERE tenant_id=$1 AND actor_id=$2 AND request_key LIKE $3 AND result ? 'job_id'
            ORDER BY created_at DESC LIMIT 1""", self.repo.tenant, actor.subject_id, "schedule:run:"+definition["id"]+":%")
        previous_id, expected_hash = definition["target_id"], definition["expected_original_sha256"]
        if last:
            previous = json_value(last)
            job = await conn.fetchrow("SELECT state FROM knowledge_ingestion_job WHERE id=$1 AND tenant_id=$2", previous["job_id"], self.repo.tenant)
            if job and job["state"] in {"QUEUED", "RUNNING", "RETRY_WAIT"}:
                return {"state": "WAITING_FOR_JOB", "job_id": previous["job_id"], "intake_id": previous["intake_id"]}
            fetched = await conn.fetchval("""SELECT a.sha256 FROM knowledge_intake_fetch f JOIN knowledge_artifact a
                ON a.id=f.original_id AND a.tenant_id=f.tenant_id WHERE f.intake_id=$1 AND f.tenant_id=$2""",
                previous["intake_id"], self.repo.tenant)
            if fetched:
                previous_id, expected_hash = previous["intake_id"], fetched
        # A refresh still uses the existing acquisition, hash, URL, tenant,
        # network and worker guards; fetching itself happens after this transaction.
        self._current(actor, revalidate)
        if due_slot(definition, datetime.now(UTC)) is None:
            raise PlatformError(409, "SCHEDULE_EXPIRED", "Lịch đã hết hạn; không tạo hồ sơ mới.")
        result = await self.intake.refresh_url(actor, previous_id, RefreshUrlInput(expected_original_sha256=expected_hash),
            key, _connection=conn)
        return {"state": "QUEUED", "job_id": result["job_id"], "intake_id": result["intake_id"]}

    async def serve(self):
        self.running = True
        try:
            while True:
                for key, (actor, revalidate) in list(self._sessions.items()):
                    try:
                        await self.tick(actor, revalidate)
                    except Exception:  # Fail closed; require an authenticated resume after dependency/auth failure.
                        self._sessions.pop(key, None)
                await asyncio.sleep(15)
        finally:
            self.running = False
            self._sessions.clear()  # In-memory credentials only; definitions and evidence stay durable.
