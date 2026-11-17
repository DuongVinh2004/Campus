"""Current source/actor eligibility before projecting any cited chunk content."""
import asyncio

from campus247.application.retrieval.filters import RetrievalFilterCompiler
from campus247.ports.citation_source import CitationSourceExcerpt


class PostgresCitationSourceReader:
    def __init__(self, *, pool, filter_compiler: RetrievalFilterCompiler):
        if pool is None or not isinstance(filter_compiler, RetrievalFilterCompiler):
            raise ValueError("explicit source read dependencies required")
        self._pool, self._compiler = pool, filter_compiler

    async def read(self, source_id, version_id, chunk_id, *, context):
        predicate = self._compiler.compile(context)
        scope = context.authorized_scope
        async with asyncio.timeout(2):
            async with self._pool.acquire(timeout=2) as conn:
                async with conn.transaction(readonly=True):
                    row = await conn.fetchrow("""
                        SELECT s.id AS source_id, v.id AS document_version_id, c.id AS chunk_id,
                            s.title, s.canonical_uri, s.owner_unit, s.is_synthetic,
                            v.version_label, v.effective_from, v.effective_until,
                            c.section_path, c.page_start, c.page_end,
                            c.content_text, c.content_checksum
                        FROM knowledge_source s
                        JOIN document_version v ON v.knowledge_source_id = s.id
                        JOIN knowledge_chunk c ON c.document_version_id = v.id
                        WHERE s.id = $1::uuid AND v.id = $2::uuid AND c.id = $9::uuid
                        AND """ + predicate.asyncpg_sql + """
                        AND EXISTS (SELECT 1 FROM user_identity u WHERE u.id = $10::uuid
                            AND u.status = 'ACTIVE'
                            AND (NOT s.is_synthetic OR u.is_synthetic))
                        AND (SELECT array_agg(r.role::text ORDER BY r.role::text)
                            FROM role_binding r WHERE r.user_id = $10::uuid) = $11::text[]
                        AND (NOT ('STUDENT' = ANY($11::text[])) OR EXISTS (
                            SELECT 1 FROM student_profile sp WHERE sp.user_id = $10::uuid
                            AND sp.faculty_code = ANY($5::varchar[])
                            AND sp.program_code = ANY($6::varchar[])))
                        LIMIT 1
                    """, source_id, version_id, *predicate.values, chunk_id,
                        scope.actor_id, sorted(scope.roles))
        if row is None:
            return None
        locator = {key: row[key] for key in ("section_path", "page_start", "page_end") if row[key] is not None}
        return CitationSourceExcerpt(
            str(row["source_id"]), str(row["document_version_id"]), str(row["chunk_id"]),
            row["title"], row["canonical_uri"], row["version_label"],
            "SYNTHETIC" if row["is_synthetic"] else "CURRENT", locator, row["owner_unit"],
            row["effective_from"], row["effective_until"], row["content_text"], row["content_checksum"])
