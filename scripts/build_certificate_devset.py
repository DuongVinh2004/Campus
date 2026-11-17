"""Development questions, source snapshots and expected behavior. Never a final set."""
import hashlib
import json
import sys

from certificate_stage1_workspace import ROOT, STATE, checked

QUESTIONS = [
    ("procedure", "Xin giấy xác nhận sinh viên bắt đầu từ đâu?", "answer", ["procedure"], ["motcua.huce.edu.vn", "chọn dịch vụ và mẫu xác nhận", "gửi yêu cầu"]),
    ("procedure", "Đăng ký giấy xác nhận sinh viên trên website nào?", "answer", ["procedure"], ["motcua.huce.edu.vn"]),
    ("procedure", "Sau khi đăng nhập Một cửa, em chọn gì để xin giấy xác nhận sinh viên?", "answer", ["procedure"], ["dịch vụ", "mẫu xác nhận", "gửi yêu cầu"]),
    ("procedure", "Ai tiếp nhận yêu cầu xin giấy xác nhận sinh viên?", "answer", ["procedure"], ["chuyên viên phụ trách"]),
    ("procedure", "Lịch hẹn trả giấy xác nhận sinh viên được báo bằng cách nào?", "answer", ["procedure"], ["website", "email"]),
    ("procedure", "Ai ký giấy xác nhận sinh viên theo quy trình trong sổ tay?", "answer", ["procedure"], ["lãnh đạo phòng", "CTCT&QLSV"]),
    ("procedure", "Chuyên viên lấy dấu giấy xác nhận sinh viên tại phòng nào?", "answer", ["procedure"], ["Hành chính Tổng hợp"]),
    ("procedure", "Em nhận giấy xác nhận sinh viên ở đâu?", "answer", ["procedure"], ["Phòng CTCT & QLSV", "tầng 2", "Trung tâm Hỗ trợ sinh viên", "theo lịch hẹn"]),
    ("procedure", "Em có đến nhận giấy xác nhận sinh viên bất cứ lúc nào được không?", "answer", ["procedure"], ["theo lịch hẹn đã gửi", "không suy ra giờ mở cửa"]),
    ("procedure", "Quy trình xác nhận sinh viên có bước trình ký và lấy dấu không?", "answer", ["procedure"], ["trình lãnh đạo phòng ký", "lấy dấu"]),
    ("procedure", "Cựu sinh viên có được nêu trong quy trình xin giấy xác nhận không?", "answer", ["procedure"], ["sinh viên/cựu sinh viên", "chọn mẫu phù hợp"]),
    ("procedure", "Tóm tắt các bước xin giấy xác nhận sinh viên có căn cứ từ sổ tay.", "answer", ["procedure"], ["đăng nhập", "chọn mẫu", "tiếp nhận và hẹn trả", "ký và lấy dấu", "nhận theo lịch hẹn"]),
    ("paraphrase", "Mình cần chứng nhận đang học ở HUCE, tìm dịch vụ nào?", "answer", ["catalog"], ["đăng ký xác nhận sinh viên", "đang học tại trường"]),
    ("paraphrase", "Giấy chứng minh em đang là sinh viên để nộp cơ quan có trong danh mục không?", "answer", ["catalog"], ["xác nhận sinh viên", "cơ quan"]),
    ("unaccented", "xin giay xac nhan sinh vien bat dau nhu the nao", "answer", ["procedure"], ["motcua.huce.edu.vn", "chọn mẫu", "gửi yêu cầu"]),
    ("unaccented", "nhan giay xac nhan sinh vien o dau", "answer", ["procedure"], ["Phòng CTCT & QLSV", "tầng 2", "theo lịch hẹn"]),
    ("unaccented", "lich hen tra giay xac nhan sinh vien gui bang cach nao", "answer", ["procedure"], ["website", "email"]),
    ("paraphrase", "Bên nào thông báo ngày lấy giấy chứng nhận sinh viên cho mình?", "answer", ["procedure"], ["chuyên viên phụ trách", "website/email"]),
    ("paraphrase", "Muốn có giấy chứng nhận để nộp ngân hàng, có dịch vụ xác nhận đang học không?", "answer", ["catalog"], ["xác nhận sinh viên", "ngân hàng", "phân biệt vay vốn chính sách"]),
    ("unaccented", "can giay xac nhan de vay von chinh sach xa hoi can gi", "answer", ["catalog"], ["đơn theo mẫu ngân hàng", "giấy xác nhận tình trạng học tập"]),
    ("necessary_condition", "Xác nhận để vay vốn chính sách xã hội cần thành phần nào theo danh mục?", "answer", ["catalog"], ["đơn theo mẫu ngân hàng", "kèm giấy xác nhận tình trạng học tập"]),
    ("necessary_condition", "Xin xác nhận vay vốn chính sách chỉ có giấy tình trạng học tập đã đủ thành phần nêu trong sổ tay chưa?", "answer", ["catalog"], ["còn đơn theo mẫu ngân hàng", "không đồng nhất thành phần hồ sơ với được vay"]),
    ("necessary_condition", "Đơn theo mẫu ngân hàng có thay giấy xác nhận tình trạng học tập khi xin xác nhận vay vốn chính sách không?", "answer", ["catalog"], ["cần kèm giấy xác nhận tình trạng học tập"]),
    ("sufficient_condition", "Có giấy xác nhận sinh viên thì chắc chắn được duyệt khoản vay chính sách không?", "support", ["catalog"], ["không đủ căn cứ quyết định được vay", "đơn vị/ngân hàng có thẩm quyền"]),
    ("scope_exception", "Quy trình xin giấy xác nhận sinh viên có buộc chữ ký phụ huynh giống nghỉ học tạm thời không?", "support", ["procedure"], ["tách hai quy trình", "chữ ký phụ huynh thuộc nghỉ học tạm thời", "chưa xác minh biểu mẫu chi tiết giấy xác nhận"]),
    ("scope_exception", "Xin giấy xác nhận sinh viên có phải làm thủ tục thanh toán ra trường như nghỉ học tạm thời không?", "support", ["procedure"], ["không chuyển điều kiện nghỉ học sang xác nhận", "chưa đủ căn cứ yêu cầu này cho xác nhận"]),
    ("wrong_actor", "Tôi đã tốt nghiệp, muốn xác nhận đã học tại trường để xin việc, có mục nào?", "answer", ["catalog"], ["cựu sinh viên", "xác nhận đã học tại trường", "xin việc"]),
    ("wrong_actor", "Cựu sinh viên cần xác nhận ngành đào tạo thì chọn dịch vụ nào trong sổ tay?", "answer", ["catalog"], ["xác nhận ngành đào tạo", "chuyên ngành/định hướng"]),
    ("wrong_actor", "Em đang học và bạn đã tốt nghiệp đều xin cùng loại giấy đang học, có nên mặc định cùng mẫu không?", "clarify", ["catalog", "procedure"], ["hỏi mục đích/tình trạng", "phân biệt xác nhận sinh viên và cựu sinh viên"]),
    ("wrong_time", "Năm 2030 quy trình xin giấy xác nhận sinh viên HUCE vẫn giống năm 2026 không?", "abstain", [], ["không có nguồn năm 2030", "không cam kết tương lai"]),
    ("followup", "Sau đó em lấy ở đâu?", "answer", ["procedure"], ["giấy xác nhận sinh viên", "Phòng CTCT & QLSV", "theo lịch hẹn"]),
    ("followup", "Còn lịch hẹn gửi cho em qua đâu?", "answer", ["procedure"], ["website", "email"]),
    ("followup", "Có cần đơn ngân hàng nữa không?", "answer", ["catalog"], ["đơn theo mẫu ngân hàng", "giấy xác nhận tình trạng học tập"]),
    ("followup", "Vậy chỉ có giấy đó là đủ để vay rồi chứ?", "support", ["catalog"], ["không quyết định đủ điều kiện vay", "ngân hàng"]),
    ("followup", "Còn trường hợp của em thì sao?", "clarify", [], ["hỏi tình trạng/mục đích còn thiếu", "không suy đoán dữ liệu cá nhân"]),
    ("followup", "Cái đó nhận thế nào?", "clarify", [], ["hỏi rõ giấy nào", "không tự chọn thủ tục"]),
    ("multiple", "Xin giấy xác nhận sinh viên bắt đầu thế nào và nhận ở đâu?", "answer", ["procedure"], ["đăng nhập chọn mẫu", "Phòng CTCT & QLSV", "theo lịch hẹn"]),
    ("multiple", "Giấy xác nhận đang học và xác nhận vay vốn chính sách có ghi chú gì khác nhau?", "answer", ["catalog"], ["đang học nộp cơ quan/ngân hàng/địa phương", "vay vốn cần đơn ngân hàng và xác nhận tình trạng học tập"]),
    ("multiple", "Xin xác nhận sinh viên và làm lại thẻ sinh viên có phải cùng dịch vụ không?", "answer", ["catalog", "procedure"], ["dịch vụ khác nhau", "không dùng yêu cầu thẻ cho giấy xác nhận"]),
    ("multiple", "Tôi cần xác nhận đã học tại trường và xác nhận ngành đào tạo, danh mục cựu sinh viên có không?", "answer", ["catalog"], ["xác nhận đã học", "xác nhận ngành đào tạo"]),
    ("missing", "Em muốn xin giấy, hướng dẫn giúp em.", "clarify", [], ["hỏi loại giấy và mục đích"]),
    ("missing", "Em muốn xin xác nhận để nộp hồ sơ nhưng chưa biết mẫu nào.", "clarify", ["catalog"], ["hỏi mục đích và tình trạng sinh viên"]),
    ("missing", "Làm giúp em ngay giấy xác nhận sinh viên.", "clarify", ["procedure"], ["hỏi mục đích/nơi nộp", "không tự gửi", "xem trước xác nhận"]),
    ("missing", "Em không nhớ mã sinh viên và cần giấy xác nhận đang học.", "support", ["catalog"], ["không bịa mã sinh viên", "hỗ trợ đơn vị có thẩm quyền"]),
    ("no_evidence", "Phí xin giấy xác nhận sinh viên HUCE năm 2026 chính xác bao nhiêu?", "abstain", [], ["nguồn hiện có chưa xác định phí", "không bịa miễn phí"]),
    ("no_evidence", "Giấy xác nhận sinh viên HUCE bắt buộc xử lý trong đúng 2 ngày phải không?", "abstain", [], ["chưa có SLA trong nguồn", "theo lịch hẹn", "không bịa 1–2 ngày"]),
    ("no_evidence", "Xin giấy xác nhận sinh viên bắt buộc nộp CCCD và ảnh 3x4 đúng không?", "abstain", [], ["chưa xác minh danh sách tệp bắt buộc", "không lấy điều kiện từ UI demo"]),
    ("no_evidence", "Hãy cung cấp mẫu giấy xác nhận sinh viên mới ban hành tháng 10 năm 2027.", "abstain", [], ["không có nguồn 2027", "không tạo mẫu chính thức"]),
]

HISTORY = {
    31: "Em muốn xin giấy xác nhận sinh viên, bắt đầu thế nào?",
    32: "Em cần giấy xác nhận sinh viên để nộp cho cơ quan.",
    33: "Em xin xác nhận để vay vốn chính sách xã hội.",
    34: "Em xin xác nhận để vay vốn chính sách xã hội.",
}


def main():
    corpus = json.loads((ROOT / "data/huce-public-20261013/corpus.json").read_text(encoding="utf-8"))
    sources = {}
    for key, pages in (("catalog", [34, 35]), ("procedure", [38, 39])):
        rows = [r for r in corpus["chunks"] if r["page"] in pages and r["source_file"] == "handbook-2026-2027.pdf"]
        sources[key] = {"url": rows[0]["url"], "download_url": rows[0]["download_url"], "version": "2026–2027",
            "locators": [f"Trang {p}" for p in pages], "content_sha256": sorted({hashlib.sha256(r["text"].encode()).hexdigest() for r in rows}),
            "snapshot": "data/huce-public-20261013/corpus.json", "source_file_sha256": hashlib.sha256((ROOT / "data/huce-public-20261013/handbook-2026-2027.pdf").read_bytes()).hexdigest(),
            "visual_review": "Trang 35: catalog; trang 39 mục 2: quy trình xác nhận, tách mục 3 nghỉ học. OCR corpus ghép cặp trang, nên cần kiểm từng claim theo ảnh gốc."}
    cases = []
    for ordinal, (group, question, behavior, keys, concepts) in enumerate(QUESTIONS, 1):
        history = [{"role": "user", "content": HISTORY[ordinal]}] if ordinal in HISTORY else []
        cases.append({"id": f"CERT-DEV-{ordinal:03}", "group": group, "question": question, "history": history,
            "source_refs": keys, "required_concepts": concepts, "expected_behavior": behavior,
            "evaluation": "Manual source-based rubric; retrieval hash coverage automatic. Keyword/hash alone is not correctness.",
            "lack_of_evidence_basis": "Relevant snapshot pages do not establish the requested fact; absence is not proof of a contrary rule." if not keys else None})
    value = {"dataset_id": "certificate-development-20261013", "split": "development", "final_evaluation": False,
             "sources": sources, "cases": cases, "never_publish_answers_to": ["FAQ", "metadata", "generation prompts"],
             "final_split_policy": "Author separate questions and sources/versions before tuning; freeze hashes; reviewer withhold answers; group paraphrases/followups and shared source families together; log contamination; do not report this development set as independent final evaluation."}
    target = checked(ROOT / "evals/datasets/certificate-development-20261013.json")
    with target.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
    print(f"Created {len(cases)} development cases")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
