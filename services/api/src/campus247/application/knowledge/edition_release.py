"""Seal source-bound edition decisions into a release and recheck them on use.

The existing immutable release profile carries this additive binding. Legacy
unmapped members keep their existing admission contract; mapping never supplies
missing source authority. Distinct editions remain separate sealed members.
"""
from dataclasses import asdict
from datetime import UTC, datetime, timedelta, timezone
import re

from campus247.application.knowledge.platform_models import PlatformError, digest
from campus247.application.knowledge.version_resolver import ResolutionQuery, load_resolution_state, resolve_editions
from campus247.application.retrieval.profile import load_retrieval_profile
from campus247.application.knowledge.platform_models import json_value
from campus247.application.knowledge.release_members import MULTI_SCHEMA, canonical_members, split_members

SCHEMA = "source-bound-edition-release-v1"
AXES = ("programmes", "cohorts", "academic_years")
BUSINESS_ZONE = timezone(timedelta(hours=7))


async def lock_decisions(platform, conn):
    # Same order in decision/review/release commands; no model or OCR work is
    # performed while this short transaction lock is held.
    await conn.execute("SELECT pg_advisory_xact_lock(hashtextextended($1,0))", "edition-serving:"+platform.repo.tenant)


def business_day(at_time):
    return at_time.astimezone(BUSINESS_ZONE).date()


async def member_lineage(platform, conn, members):
    if not await conn.fetchval("SELECT to_regclass('knowledge_version_lineage') IS NOT NULL"):
        return []
    return [dict(row) for row in await conn.fetch("""SELECT l.version_id,l.edition_id,e.source_id FROM knowledge_version_lineage l
        JOIN knowledge_document_edition e ON e.id=l.edition_id AND e.tenant_id=l.tenant_id
        WHERE l.tenant_id=$1 AND l.version_id=ANY($2::uuid[]) ORDER BY e.source_id,l.version_id""",
        platform.repo.tenant, [member["version_id"] for member in members])]


async def current_binding(platform, conn, members):
    lineage = await member_lineage(platform, conn, members)
    if not lineage:
        return None, (), ()
    # Read families separately: a release can exceed the admin query's 30-family
    # bound, while each resolver partition must remain bounded.
    families = sorted({row["source_id"] for row in lineage}, key=str)
    candidates, relations, states = [], [], []
    now = datetime.now(UTC)
    for family in families:
        query = ResolutionQuery(family_ids=(family,), at_day=business_day(now), known_at=now)
        found, links, binding, _ = await load_resolution_state(platform, conn, query, admitted_only=True,
            member_version_ids=[row["version_id"] for row in lineage])
        candidates.extend(found); relations.extend(links); states.append(binding)
    mapped_ids = {row["edition_id"] for row in lineage}
    by_id = {row.edition_id: row for row in candidates}
    for identifier in mapped_ids:
        candidate = by_id.get(identifier)
        if (candidate is None or candidate.identity.verification != "VERIFIED" or candidate.blocking_issues
            or candidate.identity.effective.from_day is None or candidate.identity.effective.end_kind == "UNKNOWN"
            or any(getattr(candidate.identity.scope, axis).kind == "UNKNOWN" for axis in AXES)):
            raise PlatformError(409, "EDITION_SOURCE_DECISION_REQUIRED", "Cần quyết định độc lập có căn cứ về định danh, ngày và phạm vi trước khi dùng bản này trong release.")
    member_sources = {str(row["version_id"]): str(row["source_id"]) for row in members}
    if any(member_sources[str(row["version_id"])] != str(row["source_id"]) for row in lineage):
        raise PlatformError(409, "RELEASE_INTEGRITY", "Member không thuộc đúng family của phiên bản.")
    binding = {"members": [{key: str(value) for key, value in row.items()} for row in lineage], "families": states}
    # Independently reviewed but unpublished editions may veto a conflicting
    # conclusion once effective. They never acquire membership or permission.
    # Future preparations do not invalidate the current seal before their day.
    if binding is not None:
        now = datetime.now(UTC)
        live_candidates, live_relations = [], []
        for family in sorted({c.identity.family_id for c in candidates}, key=str):
            found, links, _, _ = await load_resolution_state(platform, conn,
                ResolutionQuery(family_ids=(family,), at_day=business_day(now), known_at=now),
                admitted_only=True, member_version_ids=[row["version_id"] for row in binding["members"]], include_prepared=True)
            live_candidates.extend(c for c in found if c.identity.verification == "VERIFIED")
            live_relations.extend(links)
        candidates, relations = live_candidates, live_relations
    return binding, candidates, relations


async def release_profile(platform, conn, members, *, requested=()):
    profile = asdict(load_retrieval_profile())
    binding, _, _ = await current_binding(platform, conn, members)
    if binding is None:
        return profile
    _, additional = split_members(members, requested)
    return {"schema": MULTI_SCHEMA, "retrieval_profile": profile, "edition_binding": binding,
        "edition_binding_sha256": digest(binding), "additional_members": additional}


async def check_profile(platform, conn, profile, members):
    """Return current candidates only when every sealed decision still matches."""
    profile = json_value(profile)
    plain = asdict(load_retrieval_profile())
    if profile == plain:
        if await member_lineage(platform, conn, members):
            raise PlatformError(409, "EDITION_BINDING_REQUIRED", "Bản có định danh cần release gắn quyết định phiên bản; hãy chuẩn bị release mới.")
        return None, (), ()
    fields = {"schema", "retrieval_profile", "edition_binding", "edition_binding_sha256"}
    if isinstance(profile, dict) and profile.get("schema") == MULTI_SCHEMA:
        fields.add("additional_members")
    if (not isinstance(profile, dict) or set(profile) != fields
        or profile["schema"] not in (SCHEMA, MULTI_SCHEMA) or profile["retrieval_profile"] != plain
        or digest(profile["edition_binding"]) != profile["edition_binding_sha256"]):
        raise PlatformError(409, "RELEASE_INTEGRITY", "Binding phiên bản của release không khớp.")
    binding, candidates, relations = await current_binding(platform, conn, members)
    if binding != profile["edition_binding"]:
        raise PlatformError(409, "EDITION_DECISIONS_CHANGED", "Quyết định hoặc bằng chứng phiên bản đã đổi; cần chuẩn bị và xác nhận lại release.")
    if profile["schema"] == MULTI_SCHEMA:
        additional = profile["additional_members"]
        mapped = {row["version_id"] for row in binding["members"]} if binding else set()
        if (not isinstance(additional, list) or any(not isinstance(row, dict) or set(row) != {"source_id", "version_id", "index_version", "rendition_sha256", "metadata_sha256"} for row in additional)
            or additional != canonical_members(additional) or any(row["version_id"] not in mapped for row in additional)):
            raise PlatformError(409, "RELEASE_INTEGRITY", "Bản bổ sung cần membership và định danh đã được gắn vào release.")
    return binding, candidates, relations


async def prepared_members(platform, conn, members, requested):
    """Prune only editions explicitly replaced/expired at intended activation.

    A future candidate is prepared against its source-based start. The current
    pointer remains unchanged, and confirmation still checks the actual day.
    Distinct cohorts and supplements survive as distinct sealed members.
    """
    binding, candidates, relations = await current_binding(platform, conn, members)
    if binding is None:
        return members
    requested = set(map(str, requested))
    targets = {row["edition_id"] for row in binding["members"] if row["version_id"] in requested}
    day = max([business_day(datetime.now(UTC)), *[c.identity.effective.from_day for c in candidates if str(c.edition_id) in targets]])
    removable = set()
    member_editions = {row["edition_id"] for row in binding["members"]}
    for family in sorted({c.identity.family_id for c in candidates}, key=str):
        family_candidates = [c for c in candidates if c.identity.family_id == family]
        result = resolve_editions(ResolutionQuery(family_ids=(family,), at_day=day, **scope_partitions(family_candidates)), family_candidates, relations)
        if result["state"] == "NEEDS_INFORMATION":
            continue  # Preserve the disputed editions; activation explains why.
        chosen = {row["edition_id"] for segment in result["segments"] for row in segment["selected"]}
        if chosen - member_editions:
            continue  # An unselected draft can veto, never silently remove a family.
        concluded = {row["edition_id"] for segment in result["segments"] for row in segment["excluded"]
            if row["reason"] in {"EXPLICIT_REPLACEMENT", "EXPIRED_FOR_QUERY"}}
        removable.update(concluded - chosen)
    pruned = {row["version_id"] for row in binding["members"] if row["edition_id"] in removable and row["version_id"] not in requested}
    return canonical_members([row for row in members if str(row["version_id"]) not in pruned])


def scope_partitions(candidates):
    axes = {}
    for axis in AXES:
        values = {value for c in candidates for value in getattr(c.identity.scope, axis).values}
        outside = "__UNLISTED_SCOPE__"
        while outside in values:
            outside += "_"
        axes[axis] = tuple(sorted(values | {outside}))
    partitions = 1
    for values in axes.values():
        partitions *= len(values)
    if partitions > 128:
        raise PlatformError(409, "EDITION_PARTITION_LIMIT", "Phạm vi cần chia nhỏ trước khi xác nhận release.")
    return axes


def activation_resolution(binding, candidates, relations, *, at_time=None):
    """Verify all scope partitions, including values outside the listed sets.

    Checking only the new member's scope would silently drop an older cohort.
    Preparation of future editions remains possible; activation uses today.
    """
    if binding is None:
        return
    now = at_time or datetime.now(UTC)
    member_editions = {row["edition_id"] for row in binding["members"]}
    if any(str(c.edition_id) in member_editions and c.identity.effective.from_day > business_day(now) for c in candidates):
        raise PlatformError(409, "EDITION_NOT_YET_EFFECTIVE", "Phiên bản nghiệp vụ chưa tới ngày áp dụng ghi trong nguồn; giữ bản đang dùng.")
    selected_members = set()
    for family in sorted({c.identity.family_id for c in candidates}, key=str):
        family_candidates = [c for c in candidates if c.identity.family_id == family]
        axes = scope_partitions(family_candidates)
        result = resolve_editions(ResolutionQuery(family_ids=(family,), at_day=business_day(now), known_at=now, **axes), family_candidates, relations)
        if result["state"] == "NEEDS_INFORMATION":
            raise PlatformError(409, "EDITION_RESOLUTION_REQUIRED", "Còn mâu thuẫn hoặc căn cứ phiên bản chưa đủ; release chưa được kích hoạt.")
        chosen = {row["edition_id"] for segment in result["segments"] for row in segment["selected"]}
        if chosen - member_editions:
            raise PlatformError(409, "EDITION_MEMBERSHIP_INCOMPLETE", "Release thiếu bản còn áp dụng ở một phạm vi; không được thay bản đó chỉ theo thứ tự tải lên.")
        selected_members.update(chosen)
    if member_editions - selected_members:
        raise PlatformError(409, "EDITION_MEMBER_NOT_APPLICABLE", "Release chứa bản chưa tới hiệu lực, đã hết hạn hoặc đã bị thay thế theo căn cứ.")


def question_axes(query, candidates):
    """Use explicit literal scope references, never authorization as applicability."""
    from campus247.application.conversation.followup import normalized_question
    clauses = [normalized_question(part) for part in re.split(r"[,;.!?]|\b(?:mà|nhưng|ma|nhung)\b", query, flags=re.IGNORECASE)]
    def mentioned(value, axis):
        literal = normalized_question(value)
        cohort = re.fullmatch(r"k?\s*(\d{2})", literal) if axis == "cohorts" else None
        pattern = r"(?:k\s*|khoa\s+k?\s*)"+cohort[1] if cohort else re.escape(literal)
        for clause in clauses:
            for match in re.finditer(r"(?<!\w)"+pattern+r"(?!\w)", clause):
                prefix = clause[:match.start()]
                if not re.search(r"\b(?:khong thuoc|khong phai|ngoai tru|loai tru|tru)(?:\s+\w+){0,4}\s*$", prefix):
                    return True
        return False
    axes = {}
    for axis in AXES:
        values = {v for c in candidates for v in getattr(c.identity.scope, axis).values}
        axes[axis] = tuple(sorted(v for v in values if mentioned(v, axis)))
    return axes


def resolved_versions(binding, candidates, relations, query, context, *, axes=None):
    if binding is None:
        return None
    selected = set()
    now = datetime.now(UTC)
    for family in sorted({c.identity.family_id for c in candidates}, key=str):
        family_candidates = [c for c in candidates if c.identity.family_id == family]
        # Opening a particular citation exposes its explicit applicability note.
        # It does not assert that the edition applies to an unspecified student.
        scope = axes if axes is not None else scope_partitions(family_candidates) if query is None else question_axes(query, family_candidates)
        result = resolve_editions(ResolutionQuery(family_ids=(family,), at_day=business_day(context.effective_at), known_at=now, **scope), candidates, relations)
        selected.update(row["edition_id"] for segment in result["segments"] for row in segment["selected"])
    # Legacy members remain subject to the existing eligibility and original
    # source-snapshot guards. Mapped versions must also pass this resolver.
    mapped = {row["version_id"] for row in binding["members"]}
    allowed = {row["version_id"] for row in binding["members"] if row["edition_id"] in selected}
    return mapped, allowed


def edition_note(binding, candidates, version_id):
    if binding is None:
        return None
    member = next((row for row in binding["members"] if row["version_id"] == str(version_id)), None)
    if member is None:
        return None
    candidate = next(c for c in candidates if str(c.edition_id) == member["edition_id"])
    effective = candidate.identity.effective
    scope = "; ".join(axis+"="+("ALL" if getattr(candidate.identity.scope, axis).kind == "ALL" else ", ".join(getattr(candidate.identity.scope, axis).values)) for axis in AXES)
    return (f"Căn cứ gốc của phiên bản {member['edition_id']}: hiệu lực từ {effective.from_day.isoformat()}"
        +(f" đến trước {effective.until_day.isoformat()}" if effective.until_day else "; không có ngày kết thúc được nêu")+f"; phạm vi gốc {scope}. Quan hệ thay thế và quyền hiện tại được kiểm lại khi mở nguồn.")
