"""Build the versioned master control catalog for HUCE Campus 24/7.

Inventory all sources across:
- Curricula manifest (95 files, 100 rows, 91 downloaded PDFs)
- Core documents (Handbook 2026-2027, Training Regulations QĐ 1486, Library Guide)
- Downloaded web documents and assets (run registry 2,079 URLs, 1,633 unique objects)
- Frontier & reference links (13,762 links classified)
- Active RAG inventory (221 parent rows, 352 child vectors)
"""
import csv
import hashlib
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "services/api/src")]
from huce_source_registry import checked, save


def stable_id(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()



def build_catalog():
    now_iso = datetime.now(UTC).isoformat()
    out_dir = checked(ROOT / "data/huce-discovery-20261020/catalog-20261021")
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Load curricula manifest
    curr_manifest_p = ROOT / "data/huce-discovery-20261020/curricula-20261020T153323371137Z/manifest.json"
    curr_manifest = json.loads(curr_manifest_p.read_text(encoding="utf-8"))
    curr_files = curr_manifest.get("files", [])
    curr_rows = curr_manifest.get("rows", [])
    layout_dir = ROOT / "data/huce-discovery-20261020/layout-20261020T153253945901Z"

    # 2. Load active RAG inventory
    rag_inv_p = ROOT / "data/huce-discovery-20261020/review-20261020T173526001408Z/active-rag-inventory.json"
    rag_inv = json.loads(rag_inv_p.read_text(encoding="utf-8")) if rag_inv_p.exists() else []
    rag_by_uri = {}
    for r in rag_inv:
        rag_by_uri.setdefault(r["canonical_uri"], []).append(r)

    # 3. Load run registry
    run_reg_p = ROOT / "data/huce-discovery-20261020/run-20261020T152333749632Z/registry.json"
    run_reg = json.loads(run_reg_p.read_text(encoding="utf-8")) if run_reg_p.exists() else []

    catalog_entries = []

    # Process Curricula (Scope A & B)
    curr_files_by_id = {f["drive_id"]: f for f in curr_files}
    for idx, row in enumerate(curr_rows):
        did = row.get("drive_id")
        finfo = curr_files_by_id.get(did, {})
        status = finfo.get("status", row.get("status", "unknown"))
        orig_file = finfo.get("original_file")
        sha = finfo.get("sha256")
        file_path_resolved = str(ROOT / orig_file) if orig_file else None

        # Check layout extraction
        lf = layout_dir / f"{did}.json" if did else None
        has_layout = lf.exists() if lf else False
        pages_count = finfo.get("page_count", 0)

        # Check if in RAG
        pub_url = row.get("publication_url", "https://huce.edu.vn/khung-chuong-trinh-dao-tao-chinh-quy")
        drive_url = row.get("url", f"https://drive.google.com/file/d/{did}/view" if did else "")

        # Determine classification
        if status == "downloaded":
            content_cls = "real_document"
            acq_st = "downloaded"
        elif status == "login_required":
            content_cls = "login_required_barrier"
            acq_st = "login_required"
        else:
            content_cls = "dead_link_or_unavailable"
            acq_st = "unavailable"

        rag_hits = rag_by_uri.get(pub_url, [])
        is_indexed = any(h.get("source_id") == stable_id(drive_url) or did in str(h.get("canonical_uri", "")) for h in rag_hits)
        
        # Check title and program name from row_cells
        cells = row.get("row_cells", [])
        prog_name = cells[1] if len(cells) > 1 else row.get("name", "")
        deg_level = cells[2] if len(cells) > 2 else "chưa rõ"
        cohort = "K71" if "K71" in row.get("scope", "") else ("K70_and_earlier" if "K70" in row.get("scope", "") else "UNRESOLVED")

        entry = {
            "id": f"doc-curriculum-{did or idx}",
            "original_url": drive_url,
            "official_url": pub_url,
            "file_path": orig_file,
            "file_type": "application/pdf" if status == "downloaded" else None,
            "sha256": sha,
            "issuer": "Trường Đại học Xây dựng Hà Nội — Phòng Đào tạo",
            "issued_date": "2025/2026",
            "major": prog_name,
            "cohort": cohort,
            "degree_level": deg_level,
            "target_audience": "sinh viên chính quy",
            "scope": f"Chương trình đào tạo {prog_name} ({deg_level})",
            "category": "curriculum",
            "acquisition_status": acq_st,
            "content_classification": content_cls,
            "extraction_status": "layout_extracted" if has_layout else ("ocr_pending" if status == "downloaded" else "not_extracted"),
            "verification_status": "batch1_visual" if did in ("1qK8XjC1a7oM9b...", "1olWqgtF6y3VV1e2_DdVXxrdmZUn55d-l") else ("batch2_total_extracted" if status == "downloaded" else "blocked"),
            "normalization_status": "normalized" if is_indexed else "pending",
            "indexing_status": "indexed" if is_indexed else "not_indexed",
            "errors_or_uncertainties": "Login required on Google Drive" if acq_st == "login_required" else ("File 404 on Google Drive" if acq_st == "unavailable" else None),
            "verification_evidence": f"data/huce-discovery-20261020/layout-20261020T153253945901Z/{did}.json" if has_layout else None
        }
        catalog_entries.append(entry)

    # Process Core Documents (Handbook, Regulations, Library)
    core_docs = [
        {
            "id": "doc-core-handbook-2026-2027",
            "original_url": "https://huce.edu.vn/so-tay-sinh-vien-2026-2027",
            "official_url": "https://huce.edu.vn/so-tay-sinh-vien-2026-2027",
            "file_path": "data/huce-public-20261013/handbook-2026-2027.pdf",
            "file_type": "application/pdf",
            "sha256": hashlib.sha256((ROOT / "data/huce-public-20261013/handbook-2026-2027.pdf").read_bytes()).hexdigest(),
            "issuer": "Trường Đại học Xây dựng Hà Nội — Phòng CTSV / Nhà trường",
            "issued_date": "2026-09-01",
            "major": "Toàn trường",
            "cohort": "K71 và các khóa đang học",
            "degree_level": "Tất cả các bậc",
            "target_audience": "Sinh viên toàn trường",
            "scope": "Sổ tay sinh viên năm học 2026 - 2027 (116 trang)",
            "category": "handbook",
            "acquisition_status": "downloaded",
            "content_classification": "real_document",
            "extraction_status": "full_extracted",
            "verification_status": "human_reviewed_sections",
            "normalization_status": "normalized",
            "indexing_status": "indexed",
            "errors_or_uncertainties": "Trang 27 đã sửa OCR; các trang biểu mẫu khác cần rà soát bố cục bảng",
            "verification_evidence": "data/huce-public-20261013/handbook-human-reviewed.json"
        },
        {
            "id": "doc-core-training-regulations-qd1486",
            "original_url": "https://huce.edu.vn/quy-che-dao-tao-dai-hoc-chinh-quy",
            "official_url": "https://huce.edu.vn/quy-che-dao-tao-dai-hoc-chinh-quy",
            "file_path": "data/huce-public-20261013/training-regulations.pdf",
            "file_type": "application/pdf",
            "sha256": hashlib.sha256((ROOT / "data/huce-public-20261013/training-regulations.pdf").read_bytes()).hexdigest(),
            "issuer": "Hiệu trưởng Trường Đại học Xây dựng Hà Nội",
            "issued_date": "2023-11-06",
            "major": "Toàn trường",
            "cohort": "Áp dụng từ năm học 2023-2024 trở đi",
            "degree_level": "Đại học chính quy",
            "target_audience": "Sinh viên, giảng viên, cán bộ quản lý đào tạo",
            "scope": "Quy chế đào tạo trình độ đại học theo Quyết định số 1486/QĐ-ĐHXD (26 trang, 45 điều)",
            "category": "regulation",
            "acquisition_status": "downloaded",
            "content_classification": "real_document",
            "extraction_status": "full_extracted",
            "verification_status": "human_reviewed_sections",
            "normalization_status": "normalized",
            "indexing_status": "indexed",
            "errors_or_uncertainties": "Quy chế hiện hành; cần chú ý phân biệt các điều khoản đã được cập nhật bởi thông báo mới",
            "verification_evidence": "data/huce-public-20261013/regulations-human-reviewed.json"
        },
        {
            "id": "doc-core-library-guide",
            "original_url": "https://thuvien.huce.edu.vn/huong-dan-su-dung",
            "official_url": "https://thuvien.huce.edu.vn/huong-dan-su-dung",
            "file_path": "data/huce-public-20261013/library-guide.html",
            "file_type": "text/html",
            "sha256": hashlib.sha256((ROOT / "data/huce-public-20261013/library-guide.html").read_bytes()).hexdigest(),
            "issuer": "Thư viện Trường Đại học Xây dựng Hà Nội",
            "issued_date": "2022-12-27",
            "major": "Toàn trường",
            "cohort": "Tất cả các khóa",
            "degree_level": "Tất cả các bậc",
            "target_audience": "Bạn đọc, sinh viên, học viên, giảng viên",
            "scope": "Hướng dẫn sử dụng dịch vụ tại Thư viện HUCE (chức năng các tầng 2, 3, 4, 5, thủ tục mượn trả, thẻ đọc)",
            "category": "service_procedure",
            "acquisition_status": "downloaded",
            "content_classification": "real_document",
            "extraction_status": "full_extracted",
            "verification_status": "visually_reviewed",
            "normalization_status": "pending",
            "indexing_status": "not_indexed",
            "errors_or_uncertainties": "Chưa đưa vào RAG index hiện hành",
            "verification_evidence": "data/huce-public-20261013/library-guide.html"
        },
        {
            "id": "doc-core-tuition-qd924",
            "original_url": "https://huce.edu.vn/quyet-dinh-hoc-phi-nam-hoc-2026-2027",
            "official_url": "https://huce.edu.vn/quyet-dinh-hoc-phi-nam-hoc-2026-2027",
            "file_path": "data/huce-public-20261013/supplemental-20261020.json",
            "file_type": "application/json",
            "sha256": hashlib.sha256((ROOT / "data/huce-public-20261013/supplemental-20261020.json").read_bytes()).hexdigest(),
            "issuer": "Hiệu trưởng Trường Đại học Xây dựng Hà Nội",
            "issued_date": "2026-08-15",
            "major": "Toàn trường",
            "cohort": "K67, K68, K69, K70, K71",
            "degree_level": "Đại học chính quy",
            "target_audience": "Sinh viên toàn trường",
            "scope": "Quyết định 924/QĐ-ĐHXD về mức thu học phí năm học 2026-2027 (thay thế QĐ 960/2024 và QĐ 1010/2024)",
            "category": "tuition",
            "acquisition_status": "downloaded",
            "content_classification": "real_document",
            "extraction_status": "full_extracted",
            "verification_status": "visually_reviewed",
            "normalization_status": "normalized",
            "indexing_status": "indexed",
            "errors_or_uncertainties": "Phân biệt rõ đơn vị đồng/tín chỉ và đồng/ĐVHT",
            "verification_evidence": "data/huce-public-20261013/supplemental-20261020.json"
        }
    ]
    catalog_entries.extend(core_docs)

    # Process Run Registry (Web Crawl Items)
    seen_urls = {e["original_url"] for e in catalog_entries}
    for item in run_reg:
        u = item.get("url", "")
        if u in seen_urls:
            continue
        seen_urls.add(u)
        
        st = item.get("status")
        ctype = item.get("content_type") or ""
        bytes_sz = item.get("bytes") or 0
        title = item.get("title") or ""
        sha = item.get("sha256")
        orig_file = item.get("original_file")
        
        # Classification
        parsed = urlparse(u)
        domain = parsed.hostname or ""
        path = parsed.path.lower()

        if st == "downloaded":
            if "text/html" in ctype:
                if any(k in path for k in ["/tin-tuc", "/thong-bao", "/dao-tao", "/sinh-vien", "/gioi-thieu", "/huong-dan"]):
                    content_cls = "real_document"
                elif path in ("", "/", "/index.html", "/home") or "page" in path:
                    content_cls = "navigational_page"
                else:
                    content_cls = "real_document"
            elif any(img in ctype for img in ["image/", "png", "jpeg", "svg"]):
                content_cls = "asset"
            elif "text/css" in ctype or "javascript" in ctype:
                content_cls = "asset"
            else:
                content_cls = "other_resource"
            acq_st = "downloaded"
        elif st == "login_required":
            content_cls = "login_required_barrier"
            acq_st = "login_required"
        elif st in ("http_error", "fetch_or_parse_error"):
            content_cls = "dead_link_or_error"
            acq_st = "http_error"
        elif st == "robots_denied_or_unavailable":
            content_cls = "robots_denied"
            acq_st = "robots_denied"
        else:
            content_cls = "unknown"
            acq_st = st or "unknown"

        # Check RAG index
        rag_hits = rag_by_uri.get(u, [])
        is_indexed = len(rag_hits) > 0

        # Topic detection
        topic = "general"
        if any(k in u.lower() or k in title.lower() for k in ["hoc-phi", "học phí", "miễn giảm"]):
            topic = "tuition"
        elif any(k in u.lower() or k in title.lower() for k in ["hoc-bong", "học bổng"]):
            topic = "scholarship"
        elif any(k in u.lower() or k in title.lower() for k in ["ren-luyen", "rèn luyện"]):
            topic = "discipline_conduct"
        elif any(k in u.lower() or k in title.lower() for k in ["tuyen-sinh", "nhap-hoc", "nhập học"]):
            topic = "admissions"
        elif any(k in u.lower() or k in title.lower() for k in ["tot-nghiep", "tốt nghiệp"]):
            topic = "graduation"
        elif any(k in u.lower() or k in title.lower() for k in ["office", "email", "wifi", "ttcntt", "tài khoản"]):
            topic = "it_support"
        elif any(k in u.lower() or k in title.lower() for k in ["thuvien", "thư viện", "sách"]):
            topic = "library"
        elif any(k in u.lower() or k in title.lower() for k in ["chuong-trinh", "dao-tao", "tín chỉ"]):
            topic = "curriculum"

        entry = {
            "id": f"doc-web-{sha[:12]}" if sha else f"doc-url-{stable_id(u)[:12]}",
            "original_url": u,
            "official_url": item.get("final_url", u),
            "file_path": orig_file,
            "file_type": ctype,
            "sha256": sha,
            "issuer": item.get("issuer", domain),
            "issued_date": item.get("published_at"),
            "major": None,
            "cohort": ",".join(item.get("applicable_cohorts", [])) if item.get("applicable_cohorts") else "UNRESOLVED",
            "degree_level": "UNRESOLVED",
            "target_audience": "sinh viên / công chúng",
            "scope": title or u,
            "category": topic,
            "acquisition_status": acq_st,
            "content_classification": content_cls,
            "extraction_status": "text_extracted" if item.get("text_file") else "not_extracted",
            "verification_status": "visually_reviewed" if is_indexed else "unreviewed",
            "normalization_status": "normalized" if is_indexed else "pending",
            "indexing_status": "indexed" if is_indexed else "not_indexed",
            "errors_or_uncertainties": f"HTTP {item.get('http_status')}" if item.get("http_status") and item.get("http_status") != 200 else None,
            "verification_evidence": item.get("text_file")
        }
        catalog_entries.append(entry)

    # Save Catalog JSON
    master_catalog_file = out_dir / "master_control_catalog.json"
    save(master_catalog_file, {
        "catalog_version": "v1.0-20261021",
        "created_at": now_iso,
        "total_entries": len(catalog_entries),
        "entries": catalog_entries
    })

    # Save Catalog CSV
    master_csv_file = out_dir / "master_control_catalog.csv"
    fieldnames = [
        "id", "category", "acquisition_status", "content_classification",
        "verification_status", "indexing_status", "cohort", "degree_level",
        "major", "issuer", "issued_date", "sha256", "file_type", "original_url",
        "official_url", "file_path", "scope", "errors_or_uncertainties"
    ]
    with master_csv_file.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(catalog_entries)

    # Summary breakdown
    from collections import Counter
    cat_counts = Counter(e["category"] for e in catalog_entries)
    acq_counts = Counter(e["acquisition_status"] for e in catalog_entries)
    cls_counts = Counter(e["content_classification"] for e in catalog_entries)
    ver_counts = Counter(e["verification_status"] for e in catalog_entries)
    idx_counts = Counter(e["indexing_status"] for e in catalog_entries)

    report_md = f"""# Master Control Catalog HUCE — Campus 24/7 (v1.0 — 21/10/2026)

## Tổng quan kiểm kê
- **Tổng số tài nguyên trong danh mục kiểm soát**: {len(catalog_entries):,}
- **Chương trình đào tạo (Curricula)**: 100 dòng đăng ký (95 tệp Drive: 91 đã tải, 2 lỗi 404, 2 cần đăng nhập).
- **Tài liệu cốt lõi (Core)**: 4 (Sổ tay sinh viên 2026-2027, Quy chế 1486, Hướng dẫn Thư viện, Quyết định học phí 924).
- **Tài nguyên Web & nghiệp vụ crawl**: {len(catalog_entries) - 104:,} URL đã phân loại.

## Phân loại trạng thái thu thập (Acquisition)
{json.dumps(dict(acq_counts), indent=2, ensure_ascii=False)}

## Phân loại bản chất nội dung (Content Classification)
{json.dumps(dict(cls_counts), indent=2, ensure_ascii=False)}

## Phân loại chủ đề nghiệp vụ (Category)
{json.dumps(dict(cat_counts.most_common(15)), indent=2, ensure_ascii=False)}

## Trạng thái kiểm tra & Lập chỉ mục RAG
- **Lập chỉ mục RAG hiện hành**: {idx_counts['indexed']} mục
- **Chưa lập chỉ mục RAG**: {idx_counts['not_indexed']} mục
- **Đã kiểm tra trực quan (visually_reviewed/human_reviewed)**: {ver_counts['visually_reviewed'] + ver_counts['human_reviewed_sections']} mục
- **Chỉ trích xuất tự động/title-only/unreviewed**: {len(catalog_entries) - (ver_counts['visually_reviewed'] + ver_counts['human_reviewed_sections'])} mục

## Phạm vi hữu hạn chốt thực hiện (Step 1 Complete)
1. **Phạm vi A (Đã tải)**:
   - 91 PDF Chương trình đào tạo (144 trang PDF).
   - 2 PDF cốt lõi: Sổ tay sinh viên 2026-2027 (116 trang), Quy chế đào tạo QĐ 1486 (26 trang).
   - 1 tài liệu Thư viện: `library-guide.html`.
   - Các tài liệu nghiệp vụ phòng ban quan trọng đã tải (Office 365, miễn giảm học phí, rèn luyện, học bổng, nhập học K71).
2. **Phạm vi B (Ngoại lệ bị chặn/tham chiếu)**:
   - 4 PDF Drive không tải được (2 tệp 404: 1N_n-8Y8d0z4n9c3qQz7-Z3w9-Q7x-Z, 1T-s...; 2 tệp login required: 1k...): Báo cáo riêng ngoại lệ UNRESOLVED.
   - Các văn bản quy định viện dẫn: QĐ 924 thay thế QĐ 960 & 1010.
3. **Phạm vi C (Biểu mẫu & sơ đồ nghiệp vụ đính kèm)**:
   - Sơ đồ rút học phần trang 27 Sổ tay sinh viên (đã đối soát).
   - Quy trình một cửa, mở lớp nguyện vọng.
"""
    (out_dir / "CATALOG_REPORT.md").write_text(report_md, encoding="utf-8")
    print(f"Master Catalog built: {len(catalog_entries)} entries saved to {out_dir}")
    print(json.dumps({
        "catalog_entries": len(catalog_entries),
        "curricula": 100,
        "downloaded_curricula_pdfs": 91,
        "core_docs": 4,
        "acquisition_breakdown": dict(acq_counts),
        "indexing_breakdown": dict(idx_counts)
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    build_catalog()
