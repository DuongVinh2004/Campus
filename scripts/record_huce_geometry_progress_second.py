"""Append honest per-source progress for the active generation22 release."""
import asyncio
import argparse
import json
from collections import Counter
from contextlib import closing
from datetime import UTC, datetime

from audit_huce_rag_20261023 import API, client
from complete_huce_corpus import actors
from continue_huce_completion_20261025 import CORPUS, OUT, ROOT, REGULATION, read, save
from knowledge_platform import TENANT, components
from prepare_huce_economics_electives_second import ECONOMICS
from prepare_huce_environment_geometry_second import ENVIRONMENT
from prepare_huce_mechanical_geometry_second import MECHANICAL
from review_huce_curriculum_geometry import MULTIMEDIA
from review_huce_network_geometry_second import NETWORK
from review_huce_data_science_second import DATA_SCIENCE
from prepare_huce_stem_full_second import STEM
from review_huce_building_services_second import BUILDING_SERVICES
from review_huce_construction_economics_english_second import SOURCE as KTE
from review_huce_csqt_geometry_second import CS, CSQT
from campus247.application.knowledge.platform_models import digest
from campus247.domain.shared.values import generate_uuid7


async def main(network=False, science=False, stem=False, boundary=False, public_details=False, it_common=False):
    boundary = boundary or public_details or it_common
    number, generation, suffix = ("32", 27, "07") if it_common else ("31", 27, "07") if public_details else ("25", 26, "06") if boundary else ("22", 25, "05") if stem else ("21", 24, "04") if science else ("20", 23, "03") if network else ("18", 22, "02")
    stem = stem or boundary
    science = science or stem
    cells, edges, columns, remaining_reviews = (332, 84, 41, 82) if science else (278, 70, 34, 83) if network else (210, 56, 25, 84)
    if boundary:
        cells, edges, columns, remaining_reviews = 411, 110, 50, 81
    if public_details:
        cells, edges, columns, remaining_reviews = 630, 147, 77, 78
    if it_common:
        cells, edges, columns, remaining_reviews = 314, 65, 41, 11
    release = read(CORPUS / f"candidate-release-{number}.json")
    with closing(client()) as c:
        response = c.get(API + "/state"); response.raise_for_status(); state = response.json()
        response = c.get(API + "/availability"); response.raise_for_status(); availability = response.json()
    assert state["is_serving"] and state["desired"]["release_id"] == release["release_id"] and state["desired"]["generation"] == generation
    baseline = "06" if public_details or it_common else "05" if boundary else "04" if stem else "03" if science else "02" if network else "01"
    dispositions = read(OUT / f"source-dispositions-{baseline}.json"); status = read(OUT / f"source-status-{baseline}.json")
    members = {m["source_id"]: m for m in release["members"]}
    plan = {e["source_id"]: e for e in read(CORPUS / f"candidate-plan-{number}.json")["sources"]}
    notes = {
        REGULATION: "Đã đối chiếu phần thân Quy chế1486, PDF2–26:21 điều/95 đơn vị,15 đoạn nối trang; giữ trang quyết định và ngày hiệu lực. Phụ lục được dẫn nhưng không có trong PDF vẫn ngoài phạm vi; không xác nhận mọi sửa đổi về sau.",
        MULTIMEDIA: "71CNDPT K71:60 ô môn/nhóm,7 cột học kỳ và13 đường nối đã đối chiếu. Giữ hai nhóm tự chọn, chữ viết tắt và tổng130TC có loại trừ. Không suy số môn phải chọn hoặc tín chỉ từ số trong tên GDTC/GDQP.",
        MECHANICAL: "K71KM:75 ô môn,9 cột học kỳ và20 đường nối đã đối chiếu. GDTC1/2/3 ghi rõ1TC; mã quốc phòng480101 ghi8. Giữ tổng180TC có loại trừ, chữ gốc 'ký thuật'/'Đổi mơi' và BL2; không diễn giải BL2 hoặc suy đường nối thiếu.",
        ENVIRONMENT: "71MTC K71:75 ô môn/nhóm,9 cột học kỳ và23 đường nối đã đối chiếu, gồm đường gấp khúc và hướng lên. GDTC không ghi tín chỉ;4801xx là mã chưa xác định. Tự chọn tự do ghi3TC và ba phương án2/2/3; không suy số môn phải chọn hoặc cộng tổng. Danh mục tự chọn riêng và ý nghĩa BL1/BL2 còn thiếu.",
        ECONOMICS: "Kinh tế xây dựng bản2025, K71 theo hàng công bố HUCE:đã đối chiếu riêng12 cột HPTCBB/Required Elective và24 ô phương án ở PDF1–2. Giữ khác biệt tên mã381801 giữa hai trang. Chưa xác minh ô môn theo học kỳ, đường nối và tổng chương trình; không suy số phương án phải chọn.",
    }
    if network:
        notes = {NETWORK: "71MHT K71:68 ô môn/nhóm,9 cột học kỳ và14 đường tiên quyết đã đối chiếu. Ảnh phóng to xác nhận chữ 'Bảo vệ bản quyền số2' thực sự được in; bốn ô lồng thuộc hai nhóm tự chọn học kỳ8. Mã467710 in cho hai tên khác nhau:giữ cả hai khi liệt kê, từ chối tên/tín chỉ duy nhất theo mã. Giữ420102 và48011x nguyên văn. Nhóm tự chọn4TC không chứng minh số môn phải chọn hoặc tín chỉ từng phương án; danh mục riêng/quy tắc khối còn thiếu."}
    if science:
        notes = {DATA_SCIENCE: "71DS K71:54 ô môn,7 cột học kỳ và14 đường nối đã đối chiếu, gồm13 tiên quyết và1 song hành941708↔941709. Giữ nguyên chữ viết tắt; GD thể chất1/2/3 không ghi tín chỉ,48xxxx là mã quốc phòng chưa xác định. Tổng130TC có loại trừ. Không suy đường nối thiếu, điều kiện cá nhân, danh mục riêng hoặc sửa đổi về sau. Lượt probe01 nhập dính chữ không đạt22/32 được giữ lại; probe02 khoảng trắng chuẩn32/32, chưa chứng minh mọi lỗi nhập liệu được xử lý."}
    if stem:
        notes = {STEM: "Thông báo46 học bổng STEM Quỹ Châu Á năm học2025–2026:giữ các khoản1–6 PDF1–2, thêm nguyên văn bốn trang biểu mẫu PDF3–6 đã đọc, gồm9 gợi ý, quyền/nghĩa vụ, hoạt động, lưu ý AI, sơ yếu lý lịch và bảng gia đình.19parent/22chunk, dòng chấm thay bằng khoảng trắng; không điền dữ liệu cá nhân. Rerank giữ câu hỏi đầy đủ và metadata mục từ rendition kiểm hash, ngưỡngBGE>0 giữ nguyên. Không suy đợt tuyển hiện đang mở; hạn13/02/2026 đã qua. Tiêu đề nghi thức/chữ ký/footer liên hệ PDF1–2 chưa chép toàn bộ; nguồn vẫn một phần. QA199 câu ghi riêng, không suy từ probe8/8 thành kiểm hội thoại đạt."}
    if boundary:
        notes.update({
            ENVIRONMENT: "71MTC K71:75 ô/9 học kỳ,22 quan hệ giữ lại. Đường098813 từng bị gán nhầm sang097704; ảnh gốc và đầu mũi tên ở bên trái biên học kỳ. Giữ ngoài phạm vi cả đích097704 và phương án097712, không suy ý định học vụ hoặc quy tắc khối. Bản gốc/bản23 quan hệ và mọi báo cáo cũ vẫn giữ. Ô tự chọn tự do3TC có ba giá trị2/2/3 được giữ nguyên, không suy số môn phải chọn. GDTC không ghi tín chỉ;4801xx chưa xác định. Đã thêm kiểm trục, số đầu và chiều đường thẳng; đường gấp khúc vẫn cần chứng cứ riêng.",
            BUILDING_SERVICES: "71HK K71:79 ô/9 học kỳ/27 quan hệ đã đối chiếu,16 tiên quyết và11 song hành; ba ô mã lồng thuộc một nhóm tự chọn4TC. Giữ chữĐai,BL2),REVITS và08 nguyên văn. GDTC không ghi tín chỉ;4801xx chưa xác định. Ba phương án tự chọn đều ghi2; không suy số môn phải chọn, tổng nhóm hoặc diễn giảiBL1/BL2. QA hội thoại mới ghi riêng, probe50/50 không thay cho QA cuối."})
        notes[STEM] += " HTML CTSV và PDF gốc đã pin hash trong stem-publication-acquisition-01.json. API boot16 đạt199/199 trong một lượt hữu hạn; lượt mới sau sửa MTC/HK ghi riêng."
    if public_details:
        notes = {
            KTE: "K71KTE:87 ô/9 học kỳ,13 quan hệ đưa vào phạm vi, gồm7 tiên quyết/6 song hành. Mã511802 in hai tên khác nhau trong học kỳ8; giữ cả hai và từ chối tra cứu duy nhất theo mã. Quan hệ song hành ở ô511802 bên dưới với511803 nhìn thấy rõ nhưng giữ riêng vì mã không duy nhất; không coi đó là không có đường nối. Hai ô361456/361457 được xem phóng to để giữ đúng dấu chấm ngh.vụ vượt biên hàng. GDTC430101/430102/430103 ghi1TC;4801xx chưa xác định. GiữĐai,GiảI,block và tổng190TC có loại trừ, không tự sửa chữ hoặc suy học vụ.",
            CSQT: "K71CSQT:66 ô/9 học kỳ/12 tiên quyết đã xem riêng trên bản gốc chương trình Anh ngữ hợp tác Mississippi. Đối chiếu độc lập66/66 ô và tiêu đề bằng glyph PDFium. Không chuyển phạm vi sang71CS. GiữGD Thế chất2 không ghi tín chỉ,4801xx và tổng180TC có loại trừ; không suy song hành hoặc đường nối không được vẽ.",
            CS: "71CS:66 ô/9 học kỳ/12 tiên quyết đã xem riêng trên bản gốc, không dùng ảnh K71CSQT thay thế. Đối chiếu độc lập66/66 ô và tiêu đề bằng glyph PDFium; chặn nhầm chương trình và sai khóa. GiữGD Thế chất2 không ghi tín chỉ,4801xx và tổng180TC có loại trừ; không suy song hành hoặc đường nối không được vẽ.",
            STEM: "Thông báo46 STEM Quỹ Châu Á2025–2026:giữ nguyên19parent cũ, thêm5 mục tiêu đề/căn cứ/đoạn kết và liên hệ/nơi nhận/chức danh-họ tên in dưới chữ ký, tổng24parent/27chunk. Đã xem riêng hai trang thông báo; không dùng OCR lỗi làm bản chữ chuẩn. Con dấu và chữ ký tay giữ dưới dạng ảnh, không xác thực chữ ký. Thông tin liên hệ được dẫn theo thông báo lịch sử; không khẳng định còn hiện hành. Không thu thập hoặc điền dữ liệu cá nhân của sinh viên; các văn bản được dẫn làm căn cứ chưa có toàn văn. Publisher/Drive/original vẫn kiểm hash. QA294 đạt trên generation26; QA nguồn mới ghi riêng, không thay bằng probe ứng viên.",
        }
    if it_common:
        notes = {
            CSQT: "K71CSQT:66 ô/9 học kỳ/12 tiên quyết đã xem riêng trên bản gốc chương trình Anh ngữ hợp tác Mississippi. Đối chiếu độc lập66/66 ô và tiêu đề bằng glyph PDFium; không chuyển phạm vi sang71CS. GiữGD Thế chất2 không ghi tín chỉ,4801xx và tổng180TC có loại trừ. Probe32/32 ghi riêng, QA hội thoại theo bản phát hành hiện tại ghi riêng.",
            CS: "71CS:66 ô/9 học kỳ/12 tiên quyết đã xem riêng trên bản gốc. Đối chiếu độc lập66/66 ô và tiêu đề bằng glyph PDFium, chặn nhầm chương trình và sai khóa. GiữGD Thế chất2 không ghi tín chỉ,4801xx và tổng180TC có loại trừ. Ngữ cảnh mục cho quan hệ lấy từ rendition của đúng parent; không đổi câu trích hoặc ngưỡngBGE.",
            STEM: "Thông báo46 STEM Quỹ Châu Á2025–2026:giữ19parent cũ, thêm5 mục tiêu đề/căn cứ/đoạn kết-liên hệ/nơi nhận/chức danh-họ tên in dưới chữ ký, tổng24parent/27chunk. Bốn mục được lặp đúng tiêu đề gốc làm ngữ cảnh; mục dùng để chọn/xếp hạng phải thuộc rendition đúng parent. Con dấu/chữ ký tay giữ dạng ảnh; không xác thực chữ ký, không khẳng định liên hệ còn hiện hành hoặc đợt tuyển còn mở. Không điền dữ liệu sinh viên. Các văn bản được dẫn làm căn cứ chưa có toàn văn; nguồn vẫn một phần. Probe15/15 và QA hội thoại ghi riêng, không thay thế nhau.",
        }
    pool, _, platform, _ = await components(); _, owner = actors(); platform.admin(owner)
    try:
        async with pool.acquire() as conn:
            assert await conn.fetchval("SELECT current_database()") == "campus247_knowledge_local_20261023"
        for row in dispositions["sources"]:
            identifier = row["source_id"]
            if identifier not in notes:
                continue
            entry = plan[identifier]; candidate = read(ROOT / entry["candidate"])
            row.update(category="PARTIAL_SOURCE_TEXT", note=notes[identifier], evidence={"candidate": entry["candidate"],
                "candidate_sha256": entry["candidate_sha256"], "release_id": release["release_id"],
                "version_id": members[identifier]["version_id"], "applicability": candidate["applicability"],
                "university_approval_claimed": False})
            async with platform.repo.transaction() as conn:
                key = "completion-20261025-02-geometry" + number + "-disposition:" + identifier; fingerprint = digest(row)
                if not await platform.repo.replay(conn, owner.subject_id, key, fingerprint):
                    new_id = generate_uuid7()
                    await conn.execute("""INSERT INTO knowledge_source_disposition(id,tenant_id,source_id,original_sha256,category,
                        related_source_id,note,evidence,created_by) VALUES($1,$2,$3,$4,$5,$6,$7,$8::jsonb,$9)""",
                        new_id, TENANT, identifier, row["original_sha256"], row["category"], row["related_source_id"],
                        row["note"], json.dumps(row["evidence"]), owner.subject_id)
                    await platform.repo.audit(conn, owner.subject_id, "knowledge.source.classified", identifier,
                        {"disposition_id": new_id, "category": row["category"]})
                    await platform.repo.remember(conn, owner.subject_id, key, fingerprint, {"id": new_id})
        for row in status["sources"]:
            if row["source_id"] in members:
                row["serving_version"] = members[row["source_id"]]["version_id"]
            if row["source_id"] in notes:
                row["verified_limit"] = notes[row["source_id"]]
        priorities = {r["source_id"]: r for r in read(OUT / "source-execution-priorities-01.json")["sources"]} if it_common else {}
        if it_common:
            for row in status["sources"]:
                row["execution_priority"] = priorities[row["source_id"]]["execution_priority"]
                row["workstream"] = priorities[row["source_id"]]["group"]
        counts = dict(Counter(r["category"] for r in dispositions["sources"]))
        dispositions["counts"] = counts
        status.update(release_id=release["release_id"], generation=generation, counts=counts)
        save(OUT / f"source-dispositions-{suffix}.json", dispositions); save(OUT / f"source-status-{suffix}.json", status)
        remaining = [r for r in status["sources"] if r["category"] in {"PARTIAL_SOURCE_TEXT", "SOURCE_SCOPE_UNRESOLVED"}]
        deferred_sources = [r for r in remaining if priorities[r["source_id"]]["group"] == "DE_SAU"] if it_common else []
        if it_common:
            remaining = [r for r in remaining if priorities[r["source_id"]]["group"] != "DE_SAU"]
            assert len(remaining) == 22 and len(deferred_sources) == 71
        save(OUT / ("remaining-evidence-worklist-focused-02.json" if it_common else "remaining-evidence-worklist-08.json" if public_details else "remaining-evidence-worklist-07.json" if boundary else "remaining-evidence-worklist-06.json" if stem else "remaining-evidence-worklist-05.json" if science else "remaining-evidence-worklist-04.json" if network else "remaining-evidence-worklist-03.json"), {"sources": remaining, "count": len(remaining),
            "scope": "CNTT_AND_COMMON" if it_common else "historical_all_documents", "deferred_sources": deferred_sources,
            "unresolved_specific_cohorts": 6 if it_common else 7, "fully_bound_one_page_curricula": [MULTIMEDIA, NETWORK, DATA_SCIENCE, CSQT, CS] if it_common else [MULTIMEDIA, MECHANICAL, ENVIRONMENT] + ([NETWORK] if network or science else []) + ([DATA_SCIENCE] if science else []) + ([BUILDING_SERVICES] if boundary else []) + ([KTE, CSQT, CS] if public_details else []),
            "deferred_curriculum_edges": [] if it_common else (["71MTC098813 intended target unverified; neither097704 nor097712 admitted"] if boundary else []) + (["K71KTE lower511802↔511803 is visually bound but code511802 is not unique; unqualified code lookup remains withheld"] if public_details else []),
            "catalogue_columns_only": [] if it_common else [ECONOMICS], "uncompleted_diagram_reviews": remaining_reviews,
            "STEM_forms_pending": False if stem else "stem-draft-blockers-01.json", "STEM_forms_QA_recorded_separately": True,
            "SSO_and_real_API_connected": False,
            "all_content_complete": False})
        save(OUT / f"progress-receipt-{suffix}.json", {"at": datetime.now(UTC), "desired": state["desired"],
            "availability": availability, "source_counts": counts, "all_remaining_work_complete": False,
            "scope": "CNTT_AND_COMMON" if it_common else "historical_all_documents", "focused_source_count": 46 if it_common else None,
            "deferred_source_count": 71 if it_common else 0,
            "regulation_body_units": 95, "regulation_cross_page_parents": 15,
            "geometry_material_sources": 93, "geometry_material_pages": 321, "initial_curriculum_candidates": 6258,
            "fully_reviewed_curriculum_cells": cells, "fully_reviewed_curriculum_edges": edges,
            "fully_reviewed_semester_columns": columns, "catalogue_columns_reviewed_separately": 0 if it_common else 12,
            "catalogue_option_cells_reviewed_separately": 0 if it_common else 24, "remaining_full_diagram_reviews": remaining_reviews,
            "deferred_curriculum_edge_count": 0 if it_common else 2 if public_details else 1 if boundary else 0,
            "live_QA_receipt_separate": True, "SSO_API": "not_connected_missing_actual_HUCE_configuration_and_grants"})
        print({"generation": generation, "counts": counts, "limited": len(remaining), "all_complete": False})
    finally:
        await pool.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--network", action="store_true")
    group.add_argument("--data-science", action="store_true")
    group.add_argument("--stem", action="store_true")
    group.add_argument("--boundary", action="store_true")
    group.add_argument("--public-details", action="store_true")
    group.add_argument("--it-common", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(args.network, args.data_science, args.stem, args.boundary, args.public_details, args.it_common))
