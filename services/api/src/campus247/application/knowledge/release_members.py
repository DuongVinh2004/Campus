"""Read all sealed members without changing the original per-source table.

Additional independently admitted editions live in the same immutable release
profile and full membership checksum. No late insert/update/delete protection
on the original table or release is removed.
"""
MULTI_SCHEMA = "source-bound-edition-release-v2"
MEMBER_KEYS = ("source_id", "version_id", "index_version", "rendition_sha256", "metadata_sha256")

MEMBERS_SQL = """(SELECT release_id,source_id,version_id,index_version,rendition_sha256,metadata_sha256
    FROM knowledge_release_member
    UNION ALL
    SELECT release.id,extra.source_id,extra.version_id,extra.index_version,extra.rendition_sha256,extra.metadata_sha256
    FROM knowledge_release release JOIN knowledge_release_seal sealed ON sealed.release_id=release.id
    CROSS JOIN LATERAL jsonb_to_recordset(CASE WHEN release.profile->>'schema'='source-bound-edition-release-v2'
        THEN release.profile->'additional_members' ELSE '[]'::jsonb END)
    AS extra(source_id uuid,version_id uuid,index_version varchar,rendition_sha256 varchar,metadata_sha256 varchar))"""


def member_reads(sql):
    """Expand a read query only. Mutation statements must use the original table."""
    if not sql.lstrip().upper().startswith(("SELECT", "WITH")):
        raise ValueError("Release member expansion is read-only")
    return sql.replace("knowledge_release_member", MEMBERS_SQL)


def canonical_members(members):
    from campus247.application.knowledge.values import public_row
    return sorted([public_row({key: row[key] for key in MEMBER_KEYS}) for row in members], key=lambda row: (row["source_id"], row["version_id"]))


def split_members(members, requested):
    """Keep one anchor in the original table, preferring a requested rendition."""
    requested = set(map(str, requested))
    anchors, additional, sources = [], [], set()
    for member in sorted(members, key=lambda row: (row["source_id"], str(row["version_id"]) not in requested, row["version_id"])):
        if member["source_id"] in sources:
            additional.append(member)
        else:
            sources.add(member["source_id"]); anchors.append(member)
    return canonical_members(anchors), canonical_members(additional)


async def merge_members(platform, conn, previous, versions):
    """A new rendition replaces its own edition; distinct editions are retained."""
    from campus247.application.knowledge.edition_release import member_lineage
    from campus247.application.knowledge.platform_models import PlatformError
    requested = canonical_members(versions)
    all_members = canonical_members([*previous, *requested])
    lineage = {str(row["version_id"]): str(row["edition_id"]) for row in await member_lineage(platform, conn, all_members)}
    keys = [(row["source_id"], lineage.get(row["version_id"])) for row in requested]
    if len(set(keys)) != len(keys):
        raise PlatformError(422, "DUPLICATE_RELEASE_EDITION", "Chỉ chọn một rendition đã duyệt cho mỗi phiên bản nghiệp vụ.")
    result = list(previous)
    for member in requested:
        same = [row for row in result if str(row["source_id"]) == member["source_id"]]
        mapped = lineage.get(member["version_id"])
        if same and any(bool(lineage.get(str(row["version_id"]))) != bool(mapped) for row in same):
            raise PlatformError(409, "LEGACY_FAMILY_MAPPING_REQUIRED", "Cần đối chiếu định danh bản đang dùng trước khi thay đổi family; không tự gán bản cũ vào phạm vi mới.")
        result = [row for row in result if str(row["source_id"]) != member["source_id"]
            or mapped and lineage.get(str(row["version_id"])) != mapped]
        result.append(member)
    return canonical_members(result)
