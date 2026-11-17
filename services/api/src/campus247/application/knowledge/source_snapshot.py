"""Explicit source snapshots: retrieval availability is not legal effectiveness."""
import re
from functools import lru_cache
from datetime import datetime, timedelta, timezone

from campus247.application.conversation.followup import normalized_question
from campus247.application.knowledge.platform_models import PlatformError, digest

PROCESSOR = "verified-corpus-original-v1:source-bound-snapshot"
KINDS = frozenset({"COHORT_SNAPSHOT", "INFORMATION_SNAPSHOT", "EVENT_SNAPSHOT"})
LEGAL_EFFECTIVITY = {
    "17707af1ae8f150178a8e45412230ff0496e3aab5cc257f6706bb503bfd71f33": (
        "2023-11-05T17:00:00+00:00", "7849add61d5f7a009b390165d62e25d1a688799e1872bfd5f1de8f4d2f1bbe76"),
}
NOTE = ("Bản nguồn lưu trữ được đối chiếu ngày {date}. Đây là ngày đối chiếu bản chụp, "
        "không phải ngày hiệu lực pháp lý; chỉ dùng đúng khóa, chương trình, năm và điều kiện nêu trong nội dung nguồn. "
        "Chỉ các đoạn trích được cung cấp thuộc phạm vi bản chữ này. Không xác nhận các thay đổi sau bản nguồn này.")


def snapshot_note(scope):
    if scope.get("kind") == "LEGAL_EFFECT":
        date = datetime.fromisoformat(scope["legal_effective_from"]).astimezone(timezone(timedelta(hours=7))).date()
        return (f"Ngày hiệu lực đã đối chiếu từ ngày ký và Điều 2 của bản gốc: {date.isoformat()}. "
            "Chỉ các trang và đoạn được nêu trong nguồn đã được đưa vào phiên bản này; không xác nhận toàn bộ tài liệu hoặc mọi sửa đổi về sau.")
    if scope.get("kind") not in KINDS:
        raise ValueError("Unknown source snapshot kind")
    instant = datetime.fromisoformat(scope["reviewed_at"])
    if instant.tzinfo is None:
        raise ValueError("Snapshot review requires a timezone")
    note = NOTE.format(date=instant.date().isoformat())
    if scope.get("academic_years"):
        note += " Phạm vi năm học của bản này: " + ", ".join(scope["academic_years"]) + "."
    if scope["kind"] == "COHORT_SNAPSHOT":
        cohorts = ", ".join(scope.get("cohorts", []))
        note += (f" Khóa đã đối chiếu: {cohorts}." if cohorts else " Nguồn chưa xác định khóa; không gán cho một khóa cụ thể.")
        if scope.get("_verified_geometry"):
            note += " Chỉ các ô, bảng và đường nối có chứng cứ hình học đi kèm được xác nhận; không suy quan hệ khác từ vị trí môn hoặc chữ phẳng, không dùng thiếu đường nối làm bằng chứng phủ định."
            repeated = scope["_verified_geometry"].get("ambiguous_course_codes", [])
            if repeated:
                note += " Mã " + ", ".join(repeated) + " xuất hiện ở nhiều ô nguồn; giữ nguyên từng ô, không tự quyết định tên duy nhất."
        else:
            note += " Bản chữ này không xác minh quan hệ mũi tên tiên quyết/song hành."
            note += " Chưa xác minh đầy đủ vị trí ô theo học kỳ."
        if scope.get("_has_printed_total") is False:
            note += " Chưa xác định tổng tín chỉ toàn chương trình trong bản chữ; không cộng các ô học kỳ để suy ra tổng."
        if scope.get("mixed_cohort_table"):
            note += " Bảng gộp nhiều khóa chưa được đối chiếu từng hàng; không gán lịch hoặc ô bảng cho một khóa cụ thể."
    return note


def validate_snapshot(rendition, extracted, *, original_sha256, effective_from):
    scope = rendition.get("applicability", {})
    legal = scope.get("kind") == "LEGAL_EFFECT"
    expected = LEGAL_EFFECTIVITY.get(original_sha256)
    valid_applicability = (bool(expected) and scope.get("admission_only") is False
        and scope.get("legal_effective_from") == expected[0]
        and scope.get("effectivity_image_sha256") == expected[1]
        and effective_from == datetime.fromisoformat(expected[0])) if legal else (
            scope.get("kind") in KINDS and scope.get("legal_effective_from") is None and scope.get("admission_only") is True
            and datetime.fromisoformat(scope["reviewed_at"]) == effective_from)
    if (rendition.get("processor") != PROCESSOR or not valid_applicability
            or any(key.startswith("_") for key in scope)
            or rendition.get("original_sha256") != original_sha256
            or extracted.get("original_sha256") != original_sha256
            or not rendition.get("pages") or rendition.get("issues")):
        raise PlatformError(409, "SNAPSHOT_BINDING_REQUIRED", "Bản chụp cần căn cứ và đối chiếu bản gốc đúng phạm vi.")
    snapshot_note(scope)
    blocks = {str(block["block_id"]): block for block in extracted["blocks"]}
    for page in rendition["pages"]:
        block = blocks.get(str(page.get("block_id")))
        start, end = page.get("char_start"), page.get("char_end")
        page_end = page.get("page_end", page.get("page"))
        if (not block or type(start) is not int or type(end) is not int
                or not 0 <= start < end <= len(block["text"])
                or page["text"] != block["text"][start:end]
                or page.get("page") != block.get("page")
                or page_end != block.get("page_end", block.get("page"))
                or (page.get("page") is not None and (type(page_end) is not int or page_end < page["page"]))
                or digest(page["text"].encode()) != page.get("text_sha256")):
            raise PlatformError(409, "SOURCE_SPAN_MISMATCH", "Đoạn trích không khớp vị trí trong bản gốc đã đối chiếu.")
        if "[Nội dung bài là tệp đính kèm trong iframe; xem nguồn PDF liên kết.]" in page["text"]:
            raise PlatformError(409, "SOURCE_PLACEHOLDER_REJECTED", "Chỉ dẫn biên tập không phải nội dung bản gốc.")
        if scope.get("cohort_partitioned"):
            text = normalized_question(block["text"])
            printed = {"K" + value for value in re.findall(r"\bk\s*(\d{2})(?=\b|[a-z])", text)}
            printed |= {"K" + value for value in re.findall(r"ap dung (?:cho|tu) khoa\s*(\d{2})\b", text)}
            cohorts = page.get("cohorts", [])
            if (scope["kind"] != "COHORT_SNAPSHOT" or not cohorts or set(cohorts) != printed
                    or not set(cohorts).issubset(scope.get("cohorts", []))):
                raise PlatformError(409, "SOURCE_COHORT_SPAN_MISMATCH", "Khóa của đoạn không khớp tiêu đề in trên trang nguồn.")
    from campus247.application.knowledge.curriculum_geometry import geometry_scopes
    geometry_scopes(rendition, extracted)
    return scope


@lru_cache(maxsize=1024)
def _query_facts(query: str):
    """Everything scope_allows reads from the question alone, computed once per question, not once per row."""
    text = normalized_question(query)
    years = frozenset(re.sub(r"\D", "", year) for year in re.findall(r"\b20\d{2}\s*[-–/]\s*20\d{2}\b", query))
    flat_layout_question = bool(re.search(r"tien quyet|song hanh|hoc truoc|dieu kien (?:de )?hoc", text)
                                or re.search(r"(?:hoc ky\s*(?:thu\s+)?|\bhk\s*)(?:\d|[ivx]+\b)", text))
    requested = set(re.findall(r"\b(?:k\s*|khoa\s+)(\d{2})(?=\b|[a-z])", text))
    # "K70 trở xuống / trở về trước" names every cohort up to K70, "từ K69 trở đi" every cohort from K69.
    for number, direction in re.findall(
            r"\b(?:k\s*|khoa\s+)(\d{2})\s*(tro xuong|tro ve truoc|ve truoc|va truoc|tro len|tro di|tro ve sau|va sau)\b", text):
        bound = int(number)
        down = direction in ("tro xuong", "tro ve truoc", "ve truoc", "va truoc")
        requested |= {str(n) for n in (range(50, bound + 1) if down else range(bound, 81))}
    codes = frozenset(re.findall(r"\bk?((?:6\d|7[01])[a-z]{2,8})\b", text))
    return text, years, flat_layout_question, frozenset(requested), codes


def scope_allows(query, scope, *, any_requested=False):
    """Whether a snapshot row's scope fits the question.

    By default every cohort and programme code the question names must belong to the row. With
    `any_requested` the row is kept when it belongs to at least one of them, so a question that
    compares two programmes can reach the rows of each; rows of a programme that was not asked
    about are still excluded.
    """
    text, years, flat_layout_question, requested_cohorts, codes = _query_facts(query)
    allowed_years = {re.sub(r"\D", "", year) for year in scope.get("academic_years", [])}
    if allowed_years and ((years and not years.intersection(allowed_years))
            or (scope.get("requires_academic_year") and not years)):
        return False
    if scope["kind"] != "COHORT_SNAPSHOT":
        return True
    if scope.get("_verified_geometry"):
        from campus247.application.knowledge.curriculum_geometry import geometry_allows
        if not geometry_allows(query, scope["_verified_geometry"]):
            return False
    elif flat_layout_question:
        # Native text alone does not encode arrow/line geometry, and flattened text does not prove the diagram's
        # column mapping (prerequisites, "học kỳ 3" placement).
        return False
    requested = requested_cohorts
    if requested and scope.get("mixed_cohort_table"):
        return False
    allowed = {str(value).removeprefix("K").removeprefix("k") for value in scope.get("cohorts", [])}
    if requested and not (requested & allowed if any_requested else requested.issubset(allowed)):
        return False
    row_codes = {str(code).lower() for code in scope.get("programme_codes", [])}
    return not codes or bool(codes & row_codes if any_requested else codes.issubset(row_codes))


async def read_snapshot(platform, conn, version, *, artifacts=None):
    if version["processor_profile"] != PROCESSOR:
        return None
    import json
    if artifacts is None:
        artifact = await conn.fetchrow("SELECT * FROM knowledge_artifact WHERE id=$1 AND tenant_id=$2",
            version["rendition_id"], platform.repo.tenant)
        raw = platform.storage.read(artifact)
    else:
        artifact, raw = artifacts[version["rendition_id"]]
        if artifact["tenant_id"] != platform.repo.tenant or digest(raw) != artifact["sha256"]:
            raise PlatformError(409, "ARTIFACT_INTEGRITY", "Artifact ngoài phạm vi hoặc không khớp hash.")
    if digest(raw) != version["rendition_sha256"]:
        raise PlatformError(409, "ARTIFACT_INTEGRITY", "Rendition không khớp review.")
    rendition = json.loads(raw)
    if artifacts is None:
        source = await conn.fetchrow("SELECT * FROM knowledge_artifact WHERE id=$1 AND tenant_id=$2",
            rendition["source_extraction_id"], platform.repo.tenant)
        extracted_raw = platform.storage.read(source)
    else:
        from uuid import UUID
        source, extracted_raw = artifacts[UUID(rendition["source_extraction_id"])]
        if source["tenant_id"] != platform.repo.tenant or digest(extracted_raw) != source["sha256"]:
            raise PlatformError(409, "ARTIFACT_INTEGRITY", "Artifact ngoài phạm vi hoặc không khớp hash.")
    if digest(extracted_raw) != rendition["source_extraction_sha256"]:
        raise PlatformError(409, "ARTIFACT_INTEGRITY", "Bản trích gốc không khớp đối chiếu.")
    extracted = json.loads(extracted_raw)
    scope = validate_snapshot(rendition, extracted, original_sha256=version["original_sha256"],
        effective_from=version["effective_from"])
    from campus247.application.knowledge.curriculum_excerpt import printed_total_excerpt
    row_scopes = {}
    if scope.get("cohort_partitioned"):
        for page in rendition["pages"]:
            cohorts = page["cohorts"]
            row_scopes[page["text_sha256"]] = {**scope, "cohorts": cohorts,
                "programme_codes": [code for code in scope.get("programme_codes", []) if any(code.startswith(cohort[1:]) for cohort in cohorts)]}
    from campus247.application.knowledge.curriculum_geometry import geometry_scopes
    geometry = geometry_scopes(rendition, extracted)
    if geometry is not None:
        caps, per_parent = geometry
        scope = {**scope, "_verified_geometry": caps}
        row_scopes = {checksum: {**row_scopes.get(checksum, scope), "_verified_geometry": value}
            for checksum, value in per_parent.items()}
    sections = {}
    for page in rendition["pages"]:
        if page.get("section"):
            sections.setdefault(page["text_sha256"], set()).add(page["section"])
    return {**scope, "_evidence_scopes": row_scopes, "_evidence_hashes": {page["text_sha256"] for page in rendition["pages"]},
        "_evidence_sections": sections,
        "_has_printed_total": any(printed_total_excerpt(page["text"], "Tổng số tín chỉ TC?") for page in rendition["pages"])}


async def read_release_snapshots(platform, conn, versions):
    """Request-scoped batch reads. Every payload is still hash-checked per request.

    Nothing is cached across authorization, revocation, release or policy changes.
    The serving query still applies current eligibility before returning evidence.
    """
    import json
    from uuid import UUID
    bound = {}
    selected = [version for version in versions if version["processor_profile"] == PROCESSOR]
    rendition_ids = {version["rendition_id"] for version in selected}
    if not rendition_ids:
        return {version["version_id"]: None for version in versions}
    rows = await conn.fetch("SELECT * FROM knowledge_artifact WHERE id=ANY($1::uuid[]) AND tenant_id=$2", list(rendition_ids), platform.repo.tenant)
    for row in rows:
        bound[row["id"]] = (row, platform.storage.read(row))
    extraction_ids = set()
    for version in selected:
        if version["rendition_id"] not in bound or digest(bound[version["rendition_id"]][1]) != version["rendition_sha256"]:
            raise PlatformError(409, "ARTIFACT_INTEGRITY", "Rendition không khớp review.")
        extraction_ids.add(UUID(json.loads(bound[version["rendition_id"]][1])["source_extraction_id"]))
    rows = await conn.fetch("SELECT * FROM knowledge_artifact WHERE id=ANY($1::uuid[]) AND tenant_id=$2", list(extraction_ids), platform.repo.tenant)
    for row in rows:
        bound[row["id"]] = (row, platform.storage.read(row))
    if not extraction_ids.issubset(bound):
        raise PlatformError(409, "ARTIFACT_INTEGRITY", "Thiếu bản trích nguồn trong phạm vi hiện tại.")
    return {version["version_id"]: await read_snapshot(platform, conn, version, artifacts=bound) for version in versions}
