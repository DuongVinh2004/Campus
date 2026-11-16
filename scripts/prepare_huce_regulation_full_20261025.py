"""Reconcile retained OCR to individually viewed original regulation pages."""
from continue_huce_completion_20261025 import OLD, OUT, REGULATION, ROOT, read, save, sha

# Each exact replacement below was read on the rendered source, not inferred
# from normative expectations. Preserve the source's wording and numbering.
CORRECTIONS = {
    2: [("QUY CHÉ", "QUY CHẾ"), ("QĐÐ-", "QĐ-"), ("tháng II", "tháng 11"),
        ("tô chức", "tổ chức"), ("đề Hiệu trưởng", "để Hiệu trưởng")],
    3: [("thẻ hiện", "thể hiện"), ("chuyền đổi", "chuyển đổi"), ("bắt lợi", "bất lợi")],
    4: [("tô chức", "tổ chức")],
    5: [],
    6: [("có thê", "có thể"), ("tối thiêu", "tối thiểu"), ("kiêm định", "kiểm định")],
    7: [("thầm quyền", "thẩm quyền"), ("tiêu chuân", "tiêu chuẩn"),
        ("tuyên sinh", "tuyển sinh"), ("chuyên sinh viên", "chuyển sinh viên")],
    8: [("e) Cơ sở", "c) Cơ sở"), ("LẬP KÉ HOẠCH VÀ TÔ CHỨC", "LẬP KẾ HOẠCH VÀ TỔ CHỨC"),
        ("chỉ tiết", "chi tiết"), ("tô chức", "tổ chức"), ("thẻ hiện", "thể hiện")],
    9: [("khóa biêu", "khóa biểu")],
    10: [("động lực đẻ", "động lực để"), ("tông khối lượng", "tổng khối lượng"),
        ("bắt khả kháng", "bất khả kháng")],
    11: [("tắt cả", "tất cả"), ("Chương II", "Chương III"),
        ("ĐÁNH GIÁ KÉT QUẢ HỌC TẬP VÀ CÁP BẰNG TÓT NGHIỆP", "ĐÁNH GIÁ KẾT QUẢ HỌC TẬP VÀ CẤP BẰNG TỐT NGHIỆP")],
    12: [("ĐHP = }ƒ-¡ kị * ĐTX; + ky * ĐT", "ĐHP = Σ(i=1..n) k_i * ĐTX_i + k_t * ĐT"),
        ("ĐTX;:", "ĐTX_i:"), ("k¡:", "k_i:"), ("thứ ¡", "thứ i"), ("k,:", "k_t:"),
        ("Với . +, =1 (các trị số k¿, ky được quy định trong đề cương học phần).\n\n“", "Với Σ(i=1..n) k_i + k_t = 1 (các trị số k_i, k_t được quy định trong đề cương học phần).")],
    13: [("A:_ từ8,5", "A: từ 8,5"), ("B': từ8,0", "B+: từ 8,0"),
        ("B: từ7,0đến7,9", "B: từ 7,0 đến 7,9"), ("C': từ6,5", "C+: từ 6,5"),
        ("C:  từ5,5", "C: từ 5,5"), ("D': từ5,0", "D+: từ 5,0"),
        ("D:  từ4,0 đến4,9", "D: từ 4,0 đến 4,9"), ("Hộ từ", "P: từ")],
    14: [("tô chức", "tổ chức"), ("học phân", "học phần")],
    15: [("B' tươngứng", "B+ tương ứng"), ("(© tương ứng", "C tương ứng"),
        ("Cï tươngứỨng", "C+ tương ứng"), ("D' tươngứng với l,5", "D+ tương ứng với 1,5"),
        ("D tươngứng với l,0", "D tương ứng với 1,0"),
        ("L4\n}_ đ¡ X Hị\nCông thức tính điểm trung bình:  A — ¬—\n}„ Tị\n=1", "Công thức tính điểm trung bình: A = [Σ(i=1..m) a_i × n_i] / [Σ(i=1..m) n_i]"),
        ("a¡ =", "a_i =")],
    16: [("n¡ =", "n_i ="), ("thứ ¡", "thứ i"), ("4.0", "4,0")],
    17: [("chuyển đỗi", "chuyển đổi")],
    18: [("chuyền đổi", "chuyển đổi"), ("học phân", "học phần"),
        ("chuyên đổi", "chuyển đổi"), ("chuyền đỗi", "chuyển đổi"), ("e) Tại", "c) Tại")],
    19: [("§. Sinh viên", "8. Sinh viên"), ("ĐÓI VỚI", "ĐỐI VỚI")],
    20: [("chuyền cơ sở", "chuyển cơ sở"), ("khóa tuyến", "khóa tuyển")],
    21: [("nơi chuyên", "nơi chuyển"), ("xin chuyền", "xin chuyển"),
        ("chỉ tiết thâm", "chi tiết thẩm"), ("Trao đỗi", "Trao đổi")],
    22: [("có thẻ", "có thể"), ("chuyền đổi", "chuyển đổi"), ("tuyền sinh", "tuyển sinh")],
    23: [("tô chức", "tổ chức"), ("chuyên đổi", "chuyển đổi")],
    24: [("chỉ tiết", "chi tiết"), ("chuyên đổi", "chuyển đổi"), ("TỎ CHỨC", "TỔ CHỨC")],
    25: [("Tuyền sinh", "Tuyển sinh"), ("tuyên\nsinh", "tuyển\nsinh"), ("số gốc", "sổ gốc")],
    26: [("sinh viên Ề", "sinh viên"), ("Lữu trữ", "Lưu trữ")],
}


def main():
    source = ROOT / "data/huce-public-20261013/regulations-human-reviewed.json"
    old = read(source)
    material = next(r for r in read(OLD / "inspection-material-01.json")["sources"]
        if r["source_id"] == REGULATION)
    assert sha((ROOT / material["original"]).read_bytes()) == material["original_sha256"]
    pages = []
    for chunk in old["chunks"]:
        page = chunk["page"]
        if page not in CORRECTIONS:
            continue
        image = material["pages"][page-1]
        assert sha((ROOT / image["image"]).read_bytes()) == image["image_sha256"]
        text = chunk["text"]
        changes = []
        for before, after in CORRECTIONS[page]:
            assert before in text, (page, before)
            changes.append({"before": before, "after": after, "occurrences": text.count(before)})
            text = text.replace(before, after)
        # Only the isolated printed footer is excluded from the body transcript.
        lines = text.rstrip().splitlines()
        footer = lines.pop()
        assert footer.strip() == ("§" if page == 9 else str(page-1)), (page, footer)
        text = "\n".join(lines).strip()
        pages.append({"page": page, "printed_page": page-1, "text": text,
            "text_sha256": sha(text.encode()), "ocr_text_sha256": sha(chunk["text"].encode()),
            "image": image["image"], "image_sha256": image["image_sha256"],
            "corrections": changes, "excluded_footer_verbatim": footer})
    save(OUT / "regulation-reviewed-pages-01.json", {
        "original_sha256": material["original_sha256"], "original": material["original"],
        "ocr_source": str(source.relative_to(ROOT)), "ocr_source_sha256": sha(source.read_bytes()),
        "method": "full_page_visual_reconciliation_of_retained_ocr_with_exact_corrections",
        "formula_notation": "Σ(i=1..n) and underscores transcribe printed summation limits and subscripts; no mathematical term inferred",
        "source_anomalies_preserved": [
            "Article 18(3) prints a cross-reference to Article 13; not silently changed to Article 12.",
            "Article 21(1) prints point b clause 1 Article 21; reference preserved as printed.",
            "Article 21(3) prints 'hồ sơ sơ sinh viên'; duplicate word preserved.",
            "Article 10(2) prints C before C+; original row order preserved."],
        "reviewed_pages": sorted(CORRECTIONS), "complete_pdf_body": len(CORRECTIONS) == 25,
        "pages": pages, "limitations": [
            "Transcription of the retained signed 1486 source; no claim that later amendments do not exist.",
            "Referenced appendices not present in this 26-page PDF are not inferred.",
            "Regulation definitions do not verify individual curriculum diagram arrows."]})
    print({"reviewed_pages": len(pages), "corrections": sum(len(p["corrections"]) for p in pages)})


if __name__ == "__main__":
    main()
