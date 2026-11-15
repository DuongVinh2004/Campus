"""Release-bound PostgreSQL FTS + exact pgvector + real BGE rerank.

Exact vector search is deliberate for the first small slice: authorization is
applied before LIMIT without relying on filtered ANN recall. No JSON corpus is
loaded into the runtime and no lexical/fake fallback masks model failures.
"""
from __future__ import annotations

import asyncio
import contextvars
import logging
import math
import re
import time
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import UTC, datetime
from uuid import uuid4

from campus247.application.knowledge.platform_models import (
    EMBED_ARTIFACT, EMBED_MODEL, EMBED_REVISION, PlatformError, digest, metadata_binding,
)
from campus247.application.knowledge.release_members import MEMBERS_SQL
from campus247.application.retrieval.filters import RetrievalFilterCompiler
from campus247.application.retrieval.profile import load_retrieval_profile
from campus247.domain.retrieval import RetrievalContext, RetrievalQuery
from campus247.infrastructure.knowledge.repository import public_row, json_value
from campus247.infrastructure.retrieval.postgres_vector import authorized_rows_to_candidates
from campus247.infrastructure.retrieval.public_knowledge import normalized
from campus247.infrastructure.retrieval.tei import _identity, _json
from campus247.ports.citation_source import CitationSourceExcerpt
from campus247.ports.reranker import RerankRequest

# Raw BGE reranker logit a candidate must exceed to count as evidence. Measured on 40 in-scope and 57
# out-of-scope questions (evals/results/rag-judge-20261028/REPORT.md sections 11 and 13): -1.0 admits
# 29/40 instead of 26/40 in-scope answers with 0/57 out-of-scope answers at either value. Claim and
# source verification still run after this gate. Set to 0 to restore the stricter earlier behaviour.
MIN_RERANK_LOGIT = -1.0

_TURN = contextvars.ContextVar("knowledge_release_turn", default=None)

# $1=query/vector, $2=k, $3..8=the existing compiler's validated scope values.
# Candidate preview is an explicit admin operation; serving always binds $11=false.
ELIGIBILITY = """
    x.tenant_id=$10 AND x.revoked_at IS NULL AND x.review_state='APPROVED'
    AND x.rendition_sha256=rm.rendition_sha256 AND x.metadata_sha256=rm.metadata_sha256
    AND v.index_version=rm.index_version AND NOT s.is_synthetic AND ($8::boolean OR NOT s.is_synthetic)
    AND v.effective_from<=$3 AND (v.effective_until>$3 OR v.effective_until IS NULL)
    AND s.campus_scope=$4 AND s.faculty_scope && $5::varchar[]
    AND s.program_scope && $6::varchar[] AND s.audiences && $7::varchar[]
    AND ($11::boolean OR (s.approval_status='APPROVED' AND v.status='PUBLISHED'
                         AND v.applicability_reviewed_at IS NOT NULL))
    AND EXISTS(SELECT 1 FROM knowledge_review rv WHERE rv.version_id=x.version_id
        AND rv.verdict='APPROVED' AND rv.reviewer_id<>x.created_by
        AND rv.rendition_sha256=x.rendition_sha256 AND rv.metadata_sha256=x.metadata_sha256)
    AND m.build_status='READY' AND m.validated_at IS NOT NULL
    AND m.embedding_model_id='BAAI/bge-m3'
    AND m.embedding_model_revision='5617a9f61b028005a4858fdac845db406aefb181'
    AND m.dimension=1024 AND m.normalization='l2' AND m.distance_metric='cosine'
    AND m.artifact_sha256='1eebfb28493f67bba03ce0ef64bfdc7fc5a3bd9d7493f818bb1d78cd798416b4'
"""

RELATION = "FROM " + MEMBERS_SQL + """ rm
    JOIN knowledge_release r ON r.id=rm.release_id AND r.tenant_id=$10
    JOIN knowledge_release_seal seal ON seal.release_id=r.id
    JOIN knowledge_ingest_version x ON x.version_id=rm.version_id
    JOIN document_version v ON v.id=x.version_id
    JOIN knowledge_source s ON s.id=v.knowledge_source_id AND s.id=rm.source_id
    JOIN knowledge_source_scope scope ON scope.source_id=s.id AND scope.tenant_id=$10
    JOIN knowledge_chunk c ON c.document_version_id=v.id
    JOIN knowledge_chunk_input ci ON ci.chunk_id=c.id
    JOIN embedding_index_manifest m ON m.index_version=rm.index_version
    WHERE rm.release_id=$9 AND """ + ELIGIBILITY

def served_corpus_query(relation: str) -> str:
    """Reuse runtime joins/eligibility, with the union of its source scopes.

    No question or actor is involved in an inventory: each source's scope arrays are intersected
    with themselves. Campus, effective time, tenant, review, revocation, seal, index and approval
    checks are kept. Edition selection is question-dependent, so every eligible release edition
    is retained. Used by the corpus export and by v2 readiness, so both see the same chunk set.
    """
    bindings = {3: "$3", 4: "$4", 5: "s.faculty_scope", 6: "s.program_scope",
                7: "s.audiences", 8: "FALSE", 9: "$1", 10: "$2", 11: "FALSE"}
    scoped = re.sub(r"\$(\d+)\b", lambda match: bindings[int(match[1])], relation)
    return """SELECT c.id AS chunk_id,s.id AS document_id,v.id AS version_id,
        s.title AS doc_title,c.section_path AS section_label,
        c.page_start AS page,c.content_text AS text """ + scoped + " ORDER BY c.id"


PROJECTION = """c.id,c.document_version_id,c.content_text,c.content_checksum,c.section_path,c.page_start,c.page_end,
    ci.index_text,ci.input_sha256,ci.processor_profile,ci.provenance,
    s.id AS source_id,s.title,s.canonical_uri,s.owner_unit,s.is_synthetic,
    v.effective_from,v.effective_until,v.version_label,'PUBLISHED' AS document_status,'APPROVED' AS approval_status"""


def source_locator(row):
    return {key: row[key] for key in ("section_path", "page_start", "page_end") if row[key] is not None}


class KnowledgeReleaseRuntime:
    def __init__(self, platform, embedding, reranker, *, instance_id):
        self.platform, self.repo = platform, platform.repo
        self.embedding, self.reranker = embedding, reranker
        self.instance_id, self.boot_id = instance_id, str(uuid4())
        self.compiler = RetrievalFilterCompiler(tenant_id=self.repo.tenant, campus_id=self.repo.campus)
        self.current = None
        self._refresh_lock = asyncio.Lock()
        self._task = None

    async def start(self):
        await self.refresh()
        self._task = asyncio.create_task(self._heartbeat())

    async def close(self):
        if self._task:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
        async with self.repo.transaction() as conn:
            await conn.execute("""UPDATE knowledge_runtime_ack SET valid_until=clock_timestamp(),error_code='RUNTIME_STOPPED'
                WHERE tenant_id=$1 AND campus_id=$2 AND instance_id=$3 AND boot_id=$4""",
                self.repo.tenant, self.repo.campus, self.instance_id, self.boot_id)

    async def _heartbeat(self):
        while True:
            await asyncio.sleep(5)
            try:
                await self.refresh()
            except Exception:
                self.current = None  # Existing ack expires; never retain a false serving claim.

    async def refresh(self):
        async with self._refresh_lock:
            error = None
            async with self.repo.pool.acquire() as conn:
                desired = await self.repo.pointer(conn)
            try:
                if desired == self.current and desired["release_id"]:
                    # Identity/relation changes are independent of publication.
                    # Stop renewing a serving acknowledgement for a stale seal.
                    async with self.repo.transaction() as conn:
                        await self.platform._release(conn, desired["release_id"])
                if desired != self.current:
                    if desired["release_id"]:
                        async with self.repo.transaction() as conn:
                            _, members = await self.platform._release(conn, desired["release_id"])
                            for member in members:
                                version = await self.platform._eligible(conn, member["version_id"], allow_revoked=True)
                                count = await conn.fetchval("SELECT count(*) FROM knowledge_chunk WHERE document_version_id=$1 AND embedding_rag_v1 IS NOT NULL", member["version_id"])
                                expected = await conn.fetchval("SELECT chunk_count FROM embedding_index_manifest WHERE index_version=$1", member["index_version"])
                                if count != expected or not count:
                                    raise ValueError("INDEX_COUNT_MISMATCH")
                                # Original/rendition must be available before acknowledging this snapshot.
                                for artifact_id in (version["original_id"], version["rendition_id"]):
                                    artifact = await conn.fetchrow("SELECT * FROM knowledge_artifact WHERE id=$1 AND tenant_id=$2", artifact_id, self.repo.tenant)
                                    self.platform.storage.read(artifact)
                        for adapter, kind in ((self.embedding, "embedding"), (self.reranker, "reranker")):
                            async with adapter._client_factory() as client:
                                info = await _json(client, "GET", "/info", 5)
                                _identity(info, adapter.profile.model_id, adapter.profile.model_revision, kind)
                    self.current = desired
            except Exception:
                error = "RELEASE_PREPARE_FAILED"
                self.current = None
            async with self.repo.transaction() as conn:
                # Ack only the pointer we prepared; a concurrent activation wins.
                pointer = await self.repo.pointer(conn, lock=True)
                if pointer != desired:
                    self.current = None
                    return
                await conn.execute("""INSERT INTO knowledge_runtime_ack
                    (tenant_id,campus_id,instance_id,boot_id,release_id,generation,policy_generation,valid_until,error_code)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,clock_timestamp()+interval '20 seconds',$8)
                    ON CONFLICT(tenant_id,campus_id,instance_id) DO UPDATE SET
                    boot_id=EXCLUDED.boot_id,release_id=EXCLUDED.release_id,generation=EXCLUDED.generation,
                    policy_generation=EXCLUDED.policy_generation,valid_until=EXCLUDED.valid_until,
                    error_code=EXCLUDED.error_code,heartbeat_at=clock_timestamp()""",
                    self.repo.tenant, self.repo.campus, self.instance_id, self.boot_id,
                    desired["release_id"] if not error else None, desired["generation"], desired["policy_generation"], error)

    async def snapshot(self):
        await self.refresh()
        if self.current is None:
            raise PlatformError(503, "KNOWLEDGE_RUNTIME_UNAVAILABLE", "Runtime chưa chuẩn bị được release.")
        return dict(self.current)

    @asynccontextmanager
    async def turn(self, context):
        if not isinstance(context, RetrievalContext):
            raise PlatformError(403, "RETRIEVAL_CONTEXT_REQUIRED", "Thiếu phạm vi truy xuất đã xác minh.")
        self.compiler.compile(context)
        snapshot = await self.snapshot()
        snapshot["scope_sha256"] = digest(context.authorized_scope.__dict__ | {
            key: sorted(value) for key, value in context.authorized_scope.__dict__.items() if isinstance(value, frozenset)})
        token = _TURN.set(snapshot)
        try:
            yield snapshot
        finally:
            _TURN.reset(token)

    async def assert_current(self, snapshot, context=None):
        if not snapshot:
            return
        if context:
            self.compiler.compile(context)
            scope_hash = digest(context.authorized_scope.__dict__ | {
                key: sorted(value) for key, value in context.authorized_scope.__dict__.items() if isinstance(value, frozenset)})
            if snapshot.get("scope_sha256") not in (None, scope_hash):
                raise PlatformError(409, "KNOWLEDGE_SCOPE_CHANGED", "Quyền đã đổi trong lượt hỏi; vui lòng hỏi lại.")
        async with self.repo.pool.acquire() as conn:
            current = await self.repo.pointer(conn)
            if snapshot.get("release_id"):
                # Decision revisions can change without a pointer generation.
                await self._edition_selection(conn, snapshot["release_id"], None, context)
            if context is not None and snapshot.get("evidence_chunk_ids"):
                eligible = await self._rows(conn, "guard", context, snapshot["release_id"], ids=snapshot["evidence_chunk_ids"])
                if {str(row["id"]) for row in eligible} != set(snapshot["evidence_chunk_ids"]):
                    raise PlatformError(409, "KNOWLEDGE_EVIDENCE_CHANGED", "Bằng chứng không còn đủ quyền hoặc hiệu lực; vui lòng hỏi lại.")
                for evidence_query, expected in snapshot.get("edition_evidence_queries", {}).items():
                    allowed, _ = await self._edition_selection(conn, snapshot["release_id"], evidence_query, context)
                    if allowed is not None and not set(expected).issubset(set(map(str, allowed))):
                        raise PlatformError(409, "KNOWLEDGE_EVIDENCE_CHANGED", "Phiên bản không còn áp dụng cho phạm vi của câu hỏi; vui lòng hỏi lại.")
        if any(snapshot.get(k) != current[k] for k in ("release_id", "generation", "policy_generation")):
            raise PlatformError(409, "KNOWLEDGE_CHANGED", "Nguồn đã thay đổi trong lượt hỏi; vui lòng hỏi lại.")

    # Integrity work that is identical for every turn (read both artifacts, hash them three times, parse and
    # validate the snapshot) is kept for a short time. Every key carries the serving generation and the policy
    # generation, so a release or policy change drops it at once; the TTL bounds the rest. The SQL gate that
    # decides eligibility (release seal, review, dates, audience) is never cached and still runs on every read.
    VERSION_TTL_S = 30.0
    SNAPSHOT_TTL_S = 60.0

    def _generation_key(self):
        turn = _TURN.get()
        return (turn.get("release_id"), turn.get("generation"), turn.get("policy_generation")) if turn else None

    async def _memoized(self, name, key, ttl, compute):
        cache = self.__dict__.setdefault("_memo_" + name, {})
        now = time.monotonic()
        entry = cache.get(key)
        if entry is not None and now - entry[0] < ttl:
            return entry[1]
        value = await compute()
        if len(cache) > 2048:
            cache.clear()
        cache[key] = (time.monotonic(), value)
        return value

    async def _version_cached(self, conn, version_id):
        return await self._memoized("version", (str(version_id), self._generation_key()), self.VERSION_TTL_S,
                                    lambda: self.repo.version(conn, version_id))

    async def _snapshot_cached(self, conn, version_id, version):
        from campus247.application.knowledge.source_snapshot import read_snapshot
        key = (str(version_id), str(version.get("rendition_id")), version.get("rendition_sha256"),
               version.get("original_sha256"), str(version.get("effective_from")), self._generation_key())
        return await self._memoized("snapshot", key, self.SNAPSHOT_TTL_S,
                                    lambda: read_snapshot(self.platform, conn, version))

    # The release record (seal, members, edition decisions) is read and re-hashed by every authorization check, which a
    # single turn makes half a dozen times. Two checks less than RELEASE_TTL_S apart share one read; a check made
    # later (the one after generation always is) reads it again, so a decision revised during the turn is still caught.
    RELEASE_TTL_S = 3.0

    async def _edition_selection(self, conn, release_id, query, context):
        from campus247.application.knowledge.edition_release import resolved_versions
        release, members = await self._memoized("release", (str(release_id), self._generation_key()), self.RELEASE_TTL_S,
                                                lambda: self.platform._release(conn, release_id))
        binding, candidates, relations = release["_edition_state"]
        if binding is None:
            return None, {}
        if context is None:
            raise PlatformError(403, "RETRIEVAL_CONTEXT_REQUIRED", "Thiếu thời điểm và quyền truy xuất đã xác minh.")
        mapped, allowed = resolved_versions(binding, candidates, relations, query, context)
        versions = [member["version_id"] for member in members if str(member["version_id"]) not in mapped or str(member["version_id"]) in allowed]
        from campus247.application.knowledge.edition_release import edition_note
        notes = {member["version_id"]: edition_note(binding, candidates, member["version_id"]) for member in members
            if str(member["version_id"]) in allowed}
        return versions, notes

    async def _rows(self, conn, query, context, release_id, *, preview=False, vector=None, ids=None, allowed_versions=None, excluded_spans=None, scope_query=None):
        edition_versions, edition_notes = await self._edition_selection(conn, release_id,
            None if ids is not None else query if scope_query is None else scope_query, context)
        if edition_versions is not None:
            allowed_versions = edition_versions if allowed_versions is None else [value for value in allowed_versions if str(value) in set(map(str, edition_versions))]
            if not allowed_versions:
                return []
        predicate = self.compiler.compile(context)
        values = [vector if vector is not None else normalized(query), 20, *predicate.values,
                  release_id, self.repo.tenant, preview]
        extra = ""
        if ids is not None:
            values.append(ids)
            extra = " AND c.id=ANY($12::uuid[])"
        if allowed_versions is not None:
            values.append(allowed_versions)
            extra += f" AND v.id=ANY(${len(values)}::uuid[])"
        if excluded_spans:
            values.append(excluded_spans)
            extra += f" AND NOT (v.id::text || ':' || c.content_checksum)=ANY(${len(values)}::text[])"
        if vector is not None:
            order = "c.embedding_rag_v1 <=> $1::vector(1024)"
            sql = "SELECT " + PROJECTION + "," + order + " AS distance " + RELATION
            sql += " AND c.embedding_rag_v1 IS NOT NULL AND c.embedding_model_version='" + EMBED_MODEL + "@" + EMBED_REVISION + "'"
            sql += extra + " ORDER BY " + order + ",c.id LIMIT $2"
        elif ids is not None:
            # $1/$2 remain typed for stable bind numbering; no search predicate on source reads.
            sql = "SELECT " + PROJECTION + " " + RELATION + extra + " AND $1::text IS NOT NULL AND $2::int>0 ORDER BY c.id"
        else:
            # Normalize lexical frequency by document length before LIMIT.
            # Repeated syllables in a long diagram/report must not crowd a
            # concise relevant clause out of the bounded candidate union.
            sql = """WITH q AS (SELECT COALESCE((SELECT string_agg(quote_literal(term),' | ')::tsquery
                FROM unnest(tsvector_to_array(to_tsvector('simple',$1))) term),''::tsquery) AS query)
                SELECT """ + PROJECTION + ",ts_rank_cd(c.content_tsv,(SELECT query FROM q),2) AS rank_score " + RELATION
            sql += " AND c.content_tsv @@ (SELECT query FROM q)" + extra + " ORDER BY rank_score DESC,c.id LIMIT $2"
        rows = [dict(row) for row in await conn.fetch(sql, *values)]
        for row in rows:
            if edition_notes.get(str(row["document_version_id"])):
                row["applicability_note"] = edition_notes[str(row["document_version_id"])]
            if digest(row["index_text"].encode()) != row["input_sha256"]:
                raise PlatformError(409, "EMBEDDING_INPUT_INTEGRITY", "Input chỉ mục không khớp fingerprint.")
            row["rerank_text"] = row["content_text"]
            if row["processor_profile"].startswith("legacy-public-structure-v1:"):
                provenance = json_value(row["provenance"])
                start,end = provenance["indexed_char_start"],provenance["indexed_char_end"]
                if not 0 <= start < end <= len(row["content_text"]):
                    raise PlatformError(409,"INDEX_LOCATOR_INTEGRITY","Locator con không khớp parent context.")
                row["rerank_text"] = row["content_text"][start:end]
                if not row["index_text"].endswith(row["rerank_text"]):
                    raise PlatformError(409,"INDEX_LOCATOR_INTEGRITY","Input embedding không khớp đoạn được lập chỉ mục.")
            elif row["processor_profile"].startswith("verified-original-span-v2:"):
                provenance=json_value(row["provenance"])
                span=provenance["verified_rerank_span"]
                start,end=span["char_start"],span["char_end"]
                if (provenance["evidence_sha256"]!=row["content_checksum"]
                    or not 0<=start<end<=len(row["content_text"])):
                    raise PlatformError(409,"INDEX_LOCATOR_INTEGRITY","Đoạn rerank không khớp evidence gốc.")
                row["rerank_text"]=row["content_text"][start:end]
            elif row["processor_profile"].startswith("verified-corpus-original-v1:"):
                provenance = json_value(row["provenance"])
                start, end = provenance["rerank_span"]["char_start"], provenance["rerank_span"]["char_end"]
                if (provenance["evidence_sha256"] != row["content_checksum"]
                        or not 0 <= start < end <= len(row["content_text"])
                        or normalized(provenance["index_header"] + "\n" + row["content_text"][start:end]) != row["index_text"]):
                    raise PlatformError(409, "INDEX_LOCATOR_INTEGRITY", "Input và vị trí bản nguồn không khớp.")
                row["rerank_text"] = row["content_text"][start:end]
            version = await self._version_cached(conn, row["document_version_id"])
            if metadata_binding(version) != version["metadata_sha256"]:
                raise PlatformError(409, "METADATA_INTEGRITY", "Metadata nguồn không khớp review.")
            from campus247.application.knowledge.source_snapshot import snapshot_note
            scope = await self._snapshot_cached(conn, row["document_version_id"], version)
            if scope is not None:
                if row["content_checksum"] not in scope["_evidence_hashes"]:
                    raise PlatformError(409, "SOURCE_SPAN_MISMATCH", "Đoạn truy xuất không thuộc bản nguồn đã duyệt.")
                row_scope = scope.get("_evidence_scopes", {}).get(row["content_checksum"], scope)
                row["snapshot_scope"] = row_scope
                row["verified_sections"] = scope.get("_evidence_sections", {}).get(row["content_checksum"], set())
                note = snapshot_note(row_scope)
                if note:
                    row["applicability_note"] = (row.get("applicability_note", "")+" "+note).strip()
                if scope["kind"] == "COHORT_SNAPSHOT":
                    from campus247.application.knowledge.curriculum_excerpt import printed_total_excerpt, printed_course_rerank_text, printed_elective_rerank_text
                    total = printed_total_excerpt(row["content_text"], query)
                    if total is not None:
                        row["rerank_text"] = total
                    else:
                        course_text = printed_course_rerank_text(row["content_text"], query, row_scope.get("_verified_geometry"))
                        if course_text is not None:
                            row["rerank_text"] = course_text
                        else:
                            elective_text = printed_elective_rerank_text(row["content_text"], query, row_scope.get("_verified_geometry"))
                            if elective_text is not None:
                                row["rerank_text"] = elective_text
        if ids is None:
            from campus247.application.knowledge.source_snapshot import scope_allows
            rows = [row for row in rows if not row.get("snapshot_scope")
                or scope_allows(query if scope_query is None else scope_query, row["snapshot_scope"])]
            from campus247.application.knowledge.deadline_excerpt import is_submission_deadline_question, submission_deadline_excerpt
            if is_submission_deadline_question(query):
                dated = []
                for row in rows:
                    excerpt = submission_deadline_excerpt(row["content_text"])
                    if excerpt is not None:
                        row["rerank_text"] = excerpt
                        dated.append(row)
                rows = dated
        return rows

    async def search(self, query, context):
        snapshot = _TURN.get() or await self.snapshot()
        return await self._search(query, context, snapshot)

    async def preview_search(self, actor, query, context, release_id):
        self.platform.admin(actor)
        async with self.repo.transaction() as conn:
            await self.platform._release(conn, release_id)
        return await self._search(query, context, {"release_id": release_id}, preview=True)

    async def _search(self, query, context, snapshot, *, preview=False):
        if not snapshot["release_id"]:
            return []
        if not preview:
            await self.assert_current(snapshot, context)
        # A prepared release may have no usable documents after revocation.
        # Avoid spending the remaining model budget on an empty authorized set.
        async with self.repo.pool.acquire() as conn:
            predicate = self.compiler.compile(context)
            available = await conn.fetchval("SELECT EXISTS(SELECT 1 " + RELATION + " AND $1::text IS NOT NULL AND $2::int>0)",
                "availability", 20, *predicate.values, snapshot["release_id"], self.repo.tenant, preview)
        if not available:
            return []
        budget=getattr(self.platform,"model_budget",None)
        remaining=budget()["remaining_inferences"] if budget is not None else None
        if remaining is not None and remaining<4:
            raise PlatformError(503,"MODEL_BUDGET_UNAVAILABLE","Nguồn đã lưu nhưng ngân sách mô hình hiện tại không đủ cho lượt tra cứu. Không có câu trả lời được xác nhận.")
        # Reference preambles can dominate long policy titles in both FTS and
        # cached child vectors. Search the actual question; keep the complete
        # query below for applicability and downstream generation/verification.
        from campus247.application.knowledge.question_scope import focused_source_question, programme_reference_codes, programme_credit_question, programme_name_match, explicit_curriculum_reference, focused_curriculum_question
        search_query = focused_source_question(query)
        # Retrieval only: the original wording still reaches generation and claim verification.
        from campus247.application.knowledge.colloquial import expand_colloquial
        search_query = expand_colloquial(search_query)
        # Applicability must be applied before each branch's LIMIT. Otherwise
        # closely related diagrams from another cohort consume all 20 slots.
        from campus247.application.knowledge.source_snapshot import read_snapshot, scope_allows, read_release_snapshots
        async with self.repo.pool.acquire() as conn:
            versions = await self.repo.release_versions(conn, snapshot["release_id"])
            edition_versions, _ = await self._edition_selection(conn, snapshot["release_id"], query, context)
            if edition_versions is not None:
                permitted = set(map(str, edition_versions))
                versions = [version for version in versions if str(version["version_id"]) in permitted]
            scopes = await read_release_snapshots(self.platform, conn, versions)
            allowed_versions = []
            eligible_versions = []
            programme_versions = []
            named_versions = []
            total_versions = set()
            excluded_spans = []
            requested_codes = programme_reference_codes(query)
            for version in versions:
                member = {"version_id": version["version_id"]}
                scope = scopes[version["version_id"]]
                if scope:
                    excluded_spans.extend(str(member["version_id"]) + ":" + checksum
                        for checksum, row_scope in scope.get("_evidence_scopes", {}).items() if not scope_allows(query, row_scope))
                if scope and scope.get("_has_printed_total"):
                    total_versions.add(member["version_id"])
                if scope is None or scope_allows(query, scope):
                    allowed_versions.append(member["version_id"])
                    eligible_versions.append(version)
                    if scope and scope["kind"] == "COHORT_SNAPSHOT":
                        name_score = programme_name_match(query, version["title"])
                        if name_score:
                            named_versions.append((name_score, member["version_id"]))
                    if (scope and scope["kind"] == "COHORT_SNAPSHOT" and requested_codes
                            and requested_codes.intersection(code.lower() for code in scope.get("programme_codes", []))):
                        programme_versions.append(member["version_id"])
        from campus247.application.knowledge.document_reference import preferred_document_versions, referenced_document_groups, focused_multi_document_question, focused_lab_permission_question, focused_named_document_question
        preferred = preferred_document_versions(query, eligible_versions)
        reference_groups = referenced_document_groups(query, eligible_versions)
        if reference_groups and len(reference_groups) > 3:
            raise PlatformError(422, "DOCUMENT_QUERY_SCOPE_LIMIT", "Lượt tra cứu giữ tối đa ba văn bản được nêu rõ; vui lòng chia câu hỏi để giữ đủ căn cứ.")
        if reference_groups:
            search_query = focused_multi_document_question(search_query)
        if preferred:
            allowed_versions = preferred
            search_query = focused_named_document_question(focused_lab_permission_question(search_query))
        elif programme_versions:
            allowed_versions = programme_versions
            search_query = programme_credit_question(search_query, has_total=set(allowed_versions).issubset(total_versions))
        elif named_versions and (programme_credit_question(search_query) != search_query
                or explicit_curriculum_reference(query)):
            most_specific = max(score for score, identifier in named_versions)
            allowed_versions = [identifier for score, identifier in named_versions if score == most_specific]
            search_query = programme_credit_question(search_query, has_total=set(allowed_versions).issubset(total_versions))
            search_query = focused_curriculum_question(search_query)
        if not allowed_versions:
            return []
        from campus247.application.retrieval.conditional_query import conditional_retrieval_question
        search_query = conditional_retrieval_question(search_query)
        batch = await self.embedding._embed((normalized(search_query),))
        vector = "[" + ",".join(str(v) for v in batch.vectors[0].values) + "]"
        async with self.repo.pool.acquire() as conn:
            # One MVCC snapshot for both branches; exact vector ranking for M1.
            async with conn.transaction(isolation="repeatable_read", readonly=True):
                lexical, semantic = [], []
                groups = reference_groups or [allowed_versions]
                for versions_in_group in groups:
                    # One explicit document cannot consume another document's
                    # entire pre-LIMIT pool. Same query vector and all original
                    # applicability/auth predicates are retained for each group.
                    permitted_group = [value for value in versions_in_group if value in allowed_versions]
                    lexical.extend(await self._rows(conn, search_query, context, snapshot["release_id"], preview=preview, allowed_versions=permitted_group, excluded_spans=excluded_spans, scope_query=query))
                    await conn.execute("SET LOCAL enable_indexscan=off")
                    semantic.extend(await self._rows(conn, search_query, context, snapshot["release_id"], preview=preview, vector=vector, allowed_versions=permitted_group, excluded_spans=excluded_spans, scope_query=query))
        from campus247.application.retrieval.candidate_selection import select_parent_spans
        chosen = select_parent_spans(lexical, semantic, search_query, limit=5,
            required_version_groups=reference_groups or ())
        try:
            label = lambda row: str(row["section_path"])[-40:]
            logging.getLogger("campus247.retrieval").warning(
                "retrieval_pool lexical=%s semantic=%s chosen=%s", [label(r) for r in lexical],
                [label(r) for r in semantic], [label(r) for r in chosen])
        except Exception:
            pass
        by_id = {str(row["id"]): row for row in chosen}
        issuers = {str(row["source_id"]): row["owner_unit"] for row in chosen}
        # Rank bounded exact child spans; return the complete authorized parent as
        # evidence so conditions are not lost and large articles do not enter BGE.
        from campus247.application.knowledge.document_reference import named_form_rerank_question, named_notice_rerank_question, verified_form_rerank_text, verified_edge_rerank_text
        form_question = (named_form_rerank_question(query) or named_notice_rerank_question(query)) if preferred else None
        ranking_rows = []
        for row in chosen:
            ranking_text = row["rerank_text"]
            if form_question and row.get("verified_sections"):
                ranking_text = verified_form_rerank_text(row["title"], row["section_path"], ranking_text, row["verified_sections"])
            elif row.get("verified_sections"):
                ranking_text = verified_edge_rerank_text(row["title"], row["section_path"], ranking_text,
                    row.get("snapshot_scope", {}).get("_verified_geometry"), row["verified_sections"])
            ranking_rows.append({**row, "content_text": ranking_text, "content_checksum": digest(ranking_text.encode())})
        candidates = tuple(authorized_rows_to_candidates(ranking_rows, issuers.__getitem__, branch="lexical"))
        request = RerankRequest(self.reranker.profile, RetrievalQuery(form_question or search_query), context, candidates)
        if reference_groups:
            from campus247.application.retrieval.question_facets import question_facets, rerank_facets
            result = await rerank_facets(self.reranker, request, question_facets(search_query))
        else:
            result = await self.reranker.rerank(request)
        try:
            # Finite metadata only (counts, document section labels, scores); never the question
            # or passage text. Warning level because that is what this service exports.
            logging.getLogger("campus247.retrieval").warning(
                "retrieval_trace lexical=%d semantic=%d chosen=%d ranked=%d top=%s", len(lexical), len(semantic),
                len(chosen), len(result.ranked), [(str(by_id[r.chunk_id]["section_path"])[-46:], round(float(r.score), 2))
                                                  for r in result.ranked[:8] if r.chunk_id in by_id])
        except Exception:
            pass
        async with self.repo.pool.acquire() as conn:
            after_models, _ = await self._edition_selection(conn, snapshot["release_id"], query, context)
        if after_models is not None:
            permitted = set(map(str, after_models))
            if any(str(row["document_version_id"]) not in permitted for row in chosen):
                raise PlatformError(409, "KNOWLEDGE_EVIDENCE_CHANGED", "Căn cứ hoặc phạm vi phiên bản đã đổi trong lúc tra cứu; vui lòng hỏi lại.")
        if not preview:
            await self.assert_current(snapshot, context)
        output, context_bytes = [], 0
        for ranked in result.ranked:
            # BGE returns raw relevance logits, not probabilities. Negative or
            # nonfinite logits cannot establish a relevant evidence candidate.
            # This conservative gate supplements, never replaces, claim checks.
            if not math.isfinite(ranked.score) or ranked.score <= MIN_RERANK_LOGIT:
                continue
            row = by_id[ranked.chunk_id]
            from campus247.application.knowledge.source_snapshot import scope_allows
            if row.get("snapshot_scope") and not scope_allows(query, row["snapshot_scope"]):
                continue
            requested_years=set(re.findall(r"\b20\d{2}\s*[-–/]\s*20\d{2}\b",normalized(query)))
            source_years=set(re.findall(r"\b20\d{2}\s*[-–/]\s*20\d{2}\b",normalized(row["content_text"])))
            year_key=lambda value:re.sub(r"\D","",value)
            if requested_years and source_years and not ({year_key(y) for y in requested_years} & {year_key(y) for y in source_years}):
                continue  # An explicit different academic year is not applicable evidence.
            size = len(row["content_text"].encode())
            if context_bytes+size > 15000:
                continue  # Never truncate away a source's conditions to fit context.
            context_bytes += size
            from campus247.infrastructure.knowledge.publication import verified_attachment
            publication = None
            if not preview:
                async with self.repo.pool.acquire() as conn:
                    publication = await verified_attachment(self.platform, conn, row, snapshot["release_id"])
            output.append({"chunk_id": str(row["id"]), "source_id": str(row["source_id"]),
                "document_version_id": str(row["document_version_id"]), "title": row["title"],
                "issuer": row["owner_unit"], "canonical_uri": row["canonical_uri"], "version_label": row["version_label"],
                "source_status": "CURRENT", "section_path": row["section_path"], "page_start": row["page_start"],
                "page_end": row["page_end"], "content_text": row["content_text"],
                "quote_span_hash": "sha256:" + row["content_checksum"], "evidence_sha256": row["content_checksum"],
                "locator": source_locator(row),
                "effective_from": row["effective_from"].isoformat(),
                "effective_until": row["effective_until"].isoformat() if row["effective_until"] else None,
                "score": ranked.score, "simulation_label": False,
                "release_id": snapshot["release_id"], "release_generation": snapshot.get("generation"),
                "profile_version": load_retrieval_profile().profile_version, "index_version": snapshot["release_id"]})
            if publication is not None:
                output[-1]["_verified_publication"] = publication
            if not preview and row.get("snapshot_scope", {}).get("_verified_geometry"):
                from campus247.domain.curriculum import VerifiedCurriculumParent
                caps = row["snapshot_scope"]["_verified_geometry"]
                output[-1]["_verified_curriculum"] = VerifiedCurriculumParent(str(row["source_id"]),
                    str(row["document_version_id"]), row["content_checksum"], snapshot["release_id"],
                    tuple(caps["semesters"]), tuple(caps["course_codes"]), tuple(caps.get("elective_group_labels", [])))
            if row.get("applicability_note"):
                output[-1]["applicability_note"] = row["applicability_note"]
            if len(output) == 4:
                break
        if not preview:
            snapshot["evidence_chunk_ids"] = sorted({item["chunk_id"] for item in output} | set(snapshot.get("evidence_chunk_ids", [])))
            checks = snapshot.setdefault("edition_evidence_queries", {})
            checks[query] = sorted({item["document_version_id"] for item in output} | set(checks.get(query, [])))
        return output

    async def rag_v2_sources(self, query, context, chunk_ids, *, attest=False):
        """Authorize the v2 snapshot before ranking using the unchanged SQL gate.

        Local unit files contain no grants. Batched original chunk reads retain
        release seal, review, effective dates, tenant/audience and edition checks.
        No embedding/rerank or authorization decision is taken from the snapshot.

        The per-row integrity checks in `_rows` cost one metadata and snapshot read per
        chunk, so a read of the whole index takes tens of seconds. The id-bound read does
        not depend on the question (edition selection runs with query=None), so large
        reads are cached per (release, generation, policy generation, scope predicate)
        and shared by concurrent turns; only the cheap question-dependent `scope_allows`
        filter runs per turn. Reads of a few cited chunks (revalidation) are never cached.

        ``attest`` adds the server-side attestations the v1 path attaches to evidence (verified
        publication of an attachment, verified curriculum geometry). They are read only for the
        few cited chunks, never for the whole index.
        """
        snapshot = _TURN.get() or await self.snapshot()
        await self.assert_current(snapshot, context)
        if not snapshot["release_id"]:
            return {}
        ids = list(chunk_ids)
        bulk = len(ids) > 64

        async def read_rows():
            began = time.monotonic()
            try:
                async with self.repo.pool.acquire() as conn:
                    editions, _ = await self._edition_selection(conn, snapshot["release_id"], None, context)
                    rows = await self._rows(conn, query, context, snapshot["release_id"],
                        ids=ids, allowed_versions=editions)
            except BaseException as exc:
                logging.getLogger("campus247.rag_v2").warning("rag_v2_sources_read failed kind=%s ms=%d ids=%d",
                    type(exc).__name__, (time.monotonic() - began) * 1000, len(ids))
                raise
            logging.getLogger("campus247.rag_v2").warning("rag_v2_sources_read ok ms=%d rows=%d",
                (time.monotonic() - began) * 1000, len(rows))
            return rows

        if bulk:
            predicate = self.compiler.compile(context)
            key = (snapshot["release_id"], snapshot["generation"], snapshot.get("policy_generation"),
                   len(ids), digest(",".join(sorted(map(str, ids))).encode()),
                   # The predicate carries the request time first; bucket it to the day so concurrent turns share a read.
                   digest(repr([str(v)[:10] if i == 0 else str(v) for i, v in enumerate(predicate.values)]).encode()))
            cache = self.__dict__.setdefault("_v2_rows_cache", {})
            for stale in [k for k in cache if k[:3] != key[:3]]:
                cache.pop(stale, None)
            now = time.monotonic()
            entry = cache.get(key)
            if entry is not None and entry["task"].done() and entry["task"].cancelled():
                entry = None
            if entry is not None and entry["task"].done() and entry["task"].exception() is not None:
                entry = None
            if entry is None:
                entry = cache[key] = {"at": now, "task": asyncio.ensure_future(read_rows()), "refresh": None}
            elif now - entry["at"] > 300 and entry["task"].done() and (
                    entry["refresh"] is None or entry["refresh"].done()):
                # Stale-while-revalidate: this turn keeps the previous read, the next one gets the new
                # one. Cited chunks are re-read live by `rag_v2_revalidate`, so a few minutes of
                # staleness here cannot admit a revoked source into an answer.
                refresh = entry["refresh"] = asyncio.ensure_future(read_rows())

                def adopt(done, entry=entry):
                    if not done.cancelled() and done.exception() is None:
                        entry["task"], entry["at"] = done, time.monotonic()
                refresh.add_done_callback(adopt)
            try:
                # The first read keeps running if this turn gives up, so a cold start is not repeated.
                rows = await asyncio.shield(entry["task"])
            except BaseException:
                if entry["task"].done():
                    cache.pop(key, None)
                raise
            logging.getLogger("campus247.rag_v2").warning("rag_v2_sources cache=%s n=%d age_ms=%d",
                "hit" if entry["at"] != now else "miss", len(rows), (time.monotonic() - entry["at"]) * 1000)
        else:
            rows = await read_rows()
        from campus247.application.knowledge.source_snapshot import scope_allows
        output = {}
        for row in rows:
            if row.get("snapshot_scope") and not scope_allows(query, row["snapshot_scope"], any_requested=True):
                continue
            until = row["effective_until"]
            if until is not None:
                # The bulk read is cached for minutes (and bucketed to the day); validity is checked per turn.
                bound = (until if until.tzinfo else until.replace(tzinfo=UTC)) if isinstance(until, datetime)                     else datetime(until.year, until.month, until.day, tzinfo=UTC)
                if bound <= datetime.now(UTC):
                    continue
            # A row of the shared bulk read is the same object on every turn: hash its text and build its
            # evidence record once, not 2000 times per question.
            template = row.get("_v2_item")
            if template is None:
                if digest(row["content_text"].encode()) != row["content_checksum"]:
                    raise PlatformError(409, "SOURCE_INTEGRITY", "Checksum nguồn không hợp lệ.")
                template = {"chunk_id": str(row["id"]), "source_id": str(row["source_id"]),
                    "document_version_id": str(row["document_version_id"]), "title": row["title"],
                    "canonical_uri": row["canonical_uri"], "version_label": row["version_label"],
                    "source_status": "CURRENT", "locator": source_locator(row), "issuer": row["owner_unit"],
                    "section_path": row["section_path"], "page_start": row["page_start"], "page_end": row["page_end"],
                    "effective_from": row["effective_from"].isoformat(),
                    "effective_until": row["effective_until"].isoformat() if row["effective_until"] else None,
                    "content_text": row["content_text"], "evidence_sha256": row["content_checksum"],
                    "release_id": snapshot["release_id"], "release_generation": snapshot["generation"],
                    "simulation_label": False}
                if row.get("applicability_note"):
                    template["applicability_note"] = row["applicability_note"]
                if bulk:
                    row["_v2_item"] = template
            output[str(row["id"])] = dict(template)
            if attest:
                item = output[str(row["id"])]
                from campus247.infrastructure.knowledge.publication import verified_attachment
                async with self.repo.pool.acquire() as conn:
                    publication = await verified_attachment(self.platform, conn, row, snapshot["release_id"])
                if publication is not None:
                    item["_verified_publication"] = publication
                geometry = (row.get("snapshot_scope") or {}).get("_verified_geometry")
                if geometry:
                    from campus247.domain.curriculum import VerifiedCurriculumParent
                    item["_verified_curriculum"] = VerifiedCurriculumParent(
                        str(row["source_id"]), str(row["document_version_id"]), row["content_checksum"],
                        snapshot["release_id"], tuple(geometry["semesters"]), tuple(geometry["course_codes"]),
                        tuple(geometry.get("elective_group_labels", [])))
        await self.assert_current(snapshot, context)
        return output

    async def rag_v2_revalidate(self, query, context, chunk_ids):
        rows = await self.rag_v2_sources(query, context, chunk_ids, attest=True)
        if set(rows) != set(chunk_ids):
            raise PlatformError(409, "KNOWLEDGE_EVIDENCE_CHANGED", "Bằng chứng đã đổi; vui lòng hỏi lại.")
        snapshot = _TURN.get()
        if snapshot is not None:
            snapshot["evidence_chunk_ids"] = sorted(set(chunk_ids) | set(snapshot.get("evidence_chunk_ids", [])))
            checks = snapshot.setdefault("edition_evidence_queries", {})
            checks[query] = sorted({row["document_version_id"] for row in rows.values()})
            await self.assert_current(snapshot, context)
        return rows

    async def rag_v2_inventory(self):
        """Release identity and a content hash of every chunk the release can serve, for readiness.

        Read-only and question-independent: the same selection as the corpus the index was built
        from (the runtime relation with each source's scope intersected with itself). The result is
        shared by concurrent readiness probes and reused for a minute while the pointer is unchanged.
        """
        async with self.repo.pool.acquire() as conn:
            pointer = await self.repo.pointer(conn)
        if not pointer["release_id"]:
            raise PlatformError(503, "KNOWLEDGE_RUNTIME_UNAVAILABLE", "Chưa có release đang phục vụ.")
        key = (pointer["release_id"], pointer["generation"], pointer["policy_generation"])
        cached = getattr(self, "_inventory", None)
        if cached and cached[0] == key and time.monotonic() - cached[1] < 60:
            return cached[2]
        task = getattr(self, "_inventory_task", None)
        if task is None or task.done():
            task = self._inventory_task = asyncio.create_task(self._read_inventory(pointer, key))
        # Shielded: a probe that times out must not cancel the read the next probe will reuse.
        return await asyncio.shield(task)

    async def _read_inventory(self, pointer, key):
        from hashlib import sha256
        async with self.repo.pool.acquire() as conn:
            async with conn.transaction(isolation="repeatable_read", readonly=True):
                as_of = await conn.fetchval("SELECT CURRENT_TIMESTAMP")
                rows = await conn.fetch(served_corpus_query(RELATION), pointer["release_id"],
                    self.repo.tenant, as_of, self.repo.campus)
        result = {"release_id": str(pointer["release_id"]), "generation": pointer["generation"],
                  "policy_generation": pointer["policy_generation"],
                  "chunk_inventory": {str(row["chunk_id"]): sha256(row["text"].encode("utf-8")).hexdigest()
                                      for row in rows}}
        self._inventory = (key, time.monotonic(), result)
        return result

    async def read(self, source_id, version_id, chunk_id, *, context):
        snapshot = _TURN.get() or await self.snapshot()
        if not snapshot["release_id"]:
            return None
        await self.assert_current(snapshot, context)
        async with self.repo.pool.acquire() as conn:
            rows = await self._rows(conn, "source", context, snapshot["release_id"], ids=[chunk_id])
        if not rows:
            return None
        row = rows[0]
        if (str(row["source_id"]), str(row["document_version_id"])) != (source_id, version_id):
            return None
        await self.assert_current(snapshot, context)
        if digest(row["content_text"].encode()) != row["content_checksum"]:
            raise PlatformError(409, "SOURCE_INTEGRITY", "Checksum nguồn không hợp lệ.")
        return CitationSourceExcerpt(source_id, version_id, chunk_id, row["title"], row["canonical_uri"], row["version_label"],
            "CURRENT", source_locator(row),
            row["owner_unit"], row["effective_from"], row["effective_until"], row["content_text"], row["content_checksum"],
            applicability_note=row.get("applicability_note"))
