"""Build the part-3/4 case sets: real-style student questions, multi-turn dialogues, conflicting/versioned sources.

Authorship: every question was written by Claude (not by students). Every gold fact carries ``evidence``: exact
source text that this script looks up in the served index, so the gold is machine-verified; the script refuses to
write a case whose evidence is not found. Required real-user usability remains unmeasured.

  python evals/runners/make_cases_345.py

Case fields (same shape as natural-cases): case_id, style, expected, question, required_facts, forbidden_facts, plus
  history          earlier user turns of the same conversation (multi-turn)
  forbidden_claims statements that must NOT be asserted as the answer to the question asked (wrong scope/version)
  conflict         {"values": [...]}: sources disagree; best answer names both values or flags the discrepancy
  evidence         exact source substrings backing the facts (verified here)
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / "evals/datasets/rag-v2"


def norm(text: str) -> str:
    text = unicodedata.normalize("NFC", text).replace("​", "")
    return re.sub(r"\s+", " ", text).strip().lower()


UNITS = [norm(json.loads(l)["text"].split("⟦RAG_V2_SOURCE⟧")[-1])
         for l in (ROOT / "data/rag_v2_index/embedded2/units.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
CORPUS = "\n".join(UNITS)


def case(cid, kind, q, facts, evidence, *, style="real", expected="answer", history=(), forbidden=(), claims=(),
         conflict=None, note=""):
    row = {"case_id": cid, "style": style, "kind": kind, "expected": expected, "question": q,
           "required_facts": list(facts), "forbidden_facts": list(forbidden), "evidence": list(evidence)}
    if history:
        row["history"] = list(history)
    if claims:
        row["forbidden_claims"] = list(claims)
    if conflict:
        row["conflict"] = conflict
    if note:
        row["note"] = note
    return row


# ---------------------------------------------------------------- part 3: real-style questions
P3 = [
    case("RS-01", "rules", "e đi trễ 20p vô phòng thực hành máy dc ko ạ 😭", ["Đến muộn sau 15 phút thì không được vào phòng máy."],
         ["đến muộn sau 15 phút không được vào phòng máy"]),
    case("RS-02", "false_premise", "nghe nói đến muộn 30 phút vẫn được vào phòng máy nếu xin giảng viên đúng không ad", ["Quy định là đến muộn sau 15 phút không được vào phòng máy; không nêu ngoại lệ 30 phút."],
         ["đến muộn sau 15 phút không được vào phòng máy"], claims=["Đến muộn 30 phút vẫn được vào phòng máy"]),
    case("RS-03", "rules", "cắm usb của mình vào máy phòng lab thì có cần xin phép ai ko", ["Muốn gắn thiết bị nhớ ngoài như USB phải được sự đồng ý của cán bộ phòng máy."],
         ["phải được sự đồng ý của cán bộ phòng máy"]),
    case("RS-04", "rules", "trong giờ thực hành dùng laptop riêng với điện thoại được hông", ["Không được sử dụng điện thoại di động và máy tính xách tay trong phòng máy."],
         ["sử dụng điện thoại di động, sử dụng máy tính xách tay"]),
    case("RS-05", "rules", "mang chai nước vào phòng máy tính đc ko vậy", ["Cấm mang nước uống và thức ăn vào phòng máy."],
         ["cấm: mang các vật dễ cháy, nổ, nước uống, thức ăn"]),
    case("RS-06", "rules", "chơi game hay nghe nhạc trong phòng máy lúc rảnh có sao ko ạ", ["Không được dùng máy tính vào mục đích khác như chơi game, chat, nghe nhạc, xem phim."],
         ["chơi game, chat, nghe nhạc, xem phim"]),
    case("RS-07", "howto", "làm sao để tải word excel miễn phí bằng tài khoản trường cấp v ad", ["Vào office.com, bấm Sign in, nhập tài khoản và mật khẩu Office 365 nhà trường cấp, chọn Install apps rồi Microsoft 365 apps."],
         ["truy cập trang https://office.com, ấn sign in"]),
    case("RS-08", "dates", "em là tân sinh viên K71 phân hiệu HCM, nhập học online hạn chót là hôm nào ạ", ["Nhập học trực tuyến từ 18/8 đến 24h00 ngày 21/8 trên nhaphoc.huce.edu.vn."],
         ["từ 18/8 đến 24h00 ngày 21/8: nhập học trực tuyến"]),
    case("RS-09", "dates", "xác nhận nhập học trên cổng bộ thì tới mấy giờ ngày nào ad ơi", ["Xác nhận nhập học trực tuyến đến 17h00 ngày 21/8 trên hệ thống của Bộ GD&ĐT."],
         ["đến 17h00 ngày 21/8: xác nhận nhập học"]),
    case("RS-10", "safety_tips", "có người nhắn rủ làm việc nhẹ lương cao online em có nên tin ko", ["Sổ tay khuyên không tham lam những lời mời chào, dụ dỗ 'việc nhẹ lương cao' và lợi nhuận phi thực tế."],
         ["lời mời chào, dụ dỗ “việc nhẹ lương cao”"]),
    case("RS-11", "policy", "ba em là thương binh thì em cần nộp giấy tờ gì để được miễn học phí vậy ạ", ["Cần đơn đề nghị miễn, giảm học phí theo mẫu và bản sao giấy tờ chứng minh (thẻ thương binh...)."],
         ["bản sao thẻ thương binh, bệnh binh"]),
    case("RS-12", "policy", "giấy xác nhận hộ nghèo phải nộp lại mỗi năm hay chỉ nộp 1 lần v ad", ["Nộp một lần đầu khóa và nộp bổ sung giấy xác nhận hộ nghèo/cận nghèo vào đầu năm tài chính hàng năm."],
         ["nộp hồ sơ bổ sung giấy xác nhận hộ nghèo/hộ cận nghèo vào đầu năm tài chính hàng năm"]),
    case("RS-13", "policy", "mình mồ côi cả cha lẫn mẹ muốn xin miễn giảm thì cần giấy gì, có phải nộp lại mỗi kỳ không", ["Cần quyết định trợ cấp xã hội hoặc giấy xác nhận mồ côi cả cha lẫn mẹ do UBND xã/phường cấp; chỉ nộp minh chứng 01 lần cho đến hết khóa."],
         ["giấy xác nhận mồ côi cả cha lẫn mẹ"]),
    case("RS-14", "policy", "bạn em dân tộc thiểu số mà nhà cận nghèo thì có được giảm học phí ko", ["Sinh viên dân tộc thiểu số có cha/mẹ (hoặc ông bà nếu ở với ông bà) thuộc hộ nghèo, cận nghèo thuộc diện xét."],
         ["sinh viên người dân tộc thiểu số có cha hoặc mẹ hoặc cả cha và mẹ hoặc ông bà"]),
    case("RS-15", "policy", "mẹ em bị tai nạn lao động đang nhận trợ cấp thường xuyên, em có thuộc diện miễn giảm ko", ["Con cán bộ, công chức, viên chức, công nhân có cha/mẹ bị tai nạn lao động hoặc bệnh nghề nghiệp hưởng trợ cấp thường xuyên thuộc diện, căn cứ Nghị định 81/2021/NĐ-CP."],
         ["cha hoặc mẹ bị tai nạn lao động hoặc mắc bệnh nghề nghiệp được hưởng trợ cấp thường xuyên"]),
    case("RS-16", "rules", "nếu cuối cùng em ko tốt nghiệp được thì trường có cấp giấy xác nhận mấy môn đã học ko", ["Sinh viên không tốt nghiệp được Trường cấp chứng nhận về các học phần đã tích lũy trong chương trình đào tạo."],
         ["sinh viên không tốt nghiệp được trường cấp chứng nhận về các học phần đã tích luỹ"], claims=["Sinh viên không tốt nghiệp không được cấp chứng nhận về các học phần đã tích lũy"]),
    case("RS-17", "rules", "mình tốt nghiệp cao đẳng nghề rồi, muốn học liên thông lên đại học ở HUCE được ko", ["Người đã tốt nghiệp trình độ giáo dục nghề nghiệp được dự tuyển và học liên thông lên đại học theo quy định."],
         ["người đã tốt nghiệp các trình độ đào tạo của giáo dục nghề nghiệp được dự tuyển và học liên thông"]),
    case("RS-18", "rules", "tín chỉ tích lũy có tính cả môn được miễn học ko ạ", ["Số tín chỉ tích lũy tính cả các học phần được miễn học, được công nhận tín chỉ."],
         ["tính cả các học phần được miễn học, được công nhận tín chỉ"]),
    case("RS-19", "rules", "quy chế đào tạo này có áp dụng cho hệ vừa làm vừa học luôn hả", ["Có, quy chế áp dụng cho hình thức chính quy và vừa làm vừa học (và liên kết nếu không trái quy chế)."],
         ["hình thức chính quy và hình thức vừa làm vừa học"]),
    case("RS-20", "rules", "điều kiện chuyển đổi tín chỉ khi đi trao đổi sinh viên xem ở đâu vậy", ["Được quy định riêng và công khai trên trang thông tin điện tử của Trường."],
         ["được quy định riêng và công khai trên trang thông tin điện tử của trường"]),
    case("RS-21", "rules", "kế hoạch năm học thì trường duyệt trước khi bắt đầu năm học bao lâu thế ạ", ["Phòng Quản lý đào tạo trình Ban giám hiệu phê duyệt kế hoạch năm học tối thiểu 06 tuần trước khi bắt đầu năm học mới."],
         ["tối thiểu 06 tuần"]),
    case("RS-22", "language", "chứng chỉ ielts mình thi hơn 2 năm trước rồi còn dùng để miễn tiếng anh ở trường được hông", ["Chứng chỉ phải còn hiệu lực trong 02 năm kể từ ngày thi (trừ DELF và Cambridge không quy định thời hạn), nên IELTS quá 2 năm không còn hợp lệ."],
         ["trong thời hạn02năm tính từ ngày thi trừ bằng tiếng pháp delf"], note="indexed text omits the space in '02năm'"),
    case("RS-23", "language", "sv có chứng chỉ HSK 4 thì tương đương bậc mấy khung ngoại ngữ vn ạ", ["HSK cấp độ 4 tương ứng Bậc 4 (CEFR B2)."],
         ["bậc4;cefr b2;delf b2,tcf4;tiếng trung hsk cấp độ4"]),
    case("RS-24", "language", "khóa tiếng anh jaxtina học mấy buổi và mỗi buổi bao lâu ad", ["20 buổi/khóa, mỗi buổi 120 phút (18 buổi học và 2 buổi kiểm tra)."],
         ["20 buổi/khóa × 120 phút/buổi (18 buổi học + 2 buổi kiểm tra)"]),
    case("RS-25", "language", "k71 mình chưa đạt a2 đầu vào thì hạn đăng ký học ở jaxtina là tới ngày mấy", ["Hạn đăng ký học ở Trung tâm JAXTINA đến hết ngày 04/10/2026."],
         ["hạn đăng ký học ở trung tâm jaxtina đến hết ngày 04/10/2026"]),
    case("RS-26", "scholarship", "nhận học bổng stem quỹ châu á rồi thì mình phải làm những gì ạ", ["Sinh viên phải cung cấp hồ sơ theo yêu cầu, cam kết học tập tốt, tham gia các hoạt động, dùng tiền học bổng cho học tập và nộp báo cáo theo yêu cầu."],
         ["nghĩa vụ của sinh viên nhận học bổng"]),
    case("RS-27", "faculty", "muốn học chuyên ngành đa phương tiện thì có cần biết vẽ hay lập trình trước ko ạ", ["Không cần biết trước về vẽ mỹ thuật, lập trình hay máy tính; chuyên ngành không có môn liên quan xây dựng."],
         ["không cần biết trước về vẽ mỹ thuật, lập trình hay máy tính"]),
    case("RS-28", "faculty", "học chuyển tiếp tín chỉ quốc tế thì có học bổng ko, bao nhiêu phần trăm", ["Sinh viên tham gia chương trình chuyển tiếp tín chỉ được nhận học bổng từ 20% đến 30%."],
         ["được nhận học bổng từ 20% - 30%"]),
    case("RS-29", "faculty", "sinh viên đi du học dự bị đại học bên Đức có được miễn học phí ko", ["Chương trình liên kết dự bị đại học với CHLB Đức được miễn 100% học phí khi học tập tại Đức."],
         ["được miễn 100% học phí khi học tập tại đức"]),
    case("RS-30", "library", "mượn giáo trình ở thư viện thì lên tầng mấy phòng nào ad", ["Mượn trả giáo trình ở Tầng 5 – Phòng giáo trình."],
         ["mượn trả giáo trình tầng 5 – phòng giáo trình"]),
    case("RS-31", "library", "thư viện đọc sách báo tạp chí tham khảo ở tầng mấy", ["Đọc tài liệu tham khảo (sách, báo, tạp chí...) ở Tầng 3 – Phòng đọc mở."],
         ["tầng 3 – phòng đọc mở"]),
    case("RS-32", "security", "quy chế ATTT nói thiết bị lưu trữ di động gồm những loại nào vậy", ["Gồm ổ cứng di động, USB, máy tính xách tay, thẻ nhớ, CD, DVD."],
         ["ổ cứng di động, usb, máy tính xách tay, thẻ nhớ, cd, dvd"]),
    case("RS-33", "curriculum", "ngành kinh tế xây dựng k70 trở xuống tổng bao nhiêu tín chỉ và có tính thể dục quốc phòng ko", ["Tổng 190TC, không tính học phần giáo dục thể chất, giáo dục quốc phòng và an ninh."],
         ["tổng: 190tc (không tính hp giáo dục thể chất, giáo dục quốc phòng và an ninh)"], forbidden=["180TC"]),
    case("RS-34", "curriculum", "kiến trúc nội thất K71 tổng cộng bao nhiêu tc vậy ad", ["Tổng 180TC, không tính giáo dục thể chất, giáo dục quốc phòng và tiếng Anh nâng cao."],
         ["tổng: 180tc (không tính hp giáo dục thể chất và giáo dục quốc phòng và tiếng anh nâng cao)"], forbidden=["190TC"]),
    case("RS-35", "curriculum", "kinh tế xây dựng 2025 tự chọn bắt buộc 4 gồm những môn nào", ["Lựa chọn 1: 381801 Tiêu chuẩn và định mức xây dựng; lựa chọn 2: 381822 Quản lý chất lượng công trình (2TC)."],
         ["lựa chọn 1 381801- tiêu chuẩn và định mức xây dựng lựa chọn 2 381822- quản lý chất lượng công trình"]),
    case("RS-36", "event", "bài báo cáo rag tiếng việt cross-encoder của bạn Triệu Quốc Đạt trình bày lúc mấy giờ ở hội nghị fit", ["Trình bày lúc 09h00 – 09h15."],
         ["09h00 – 09h15 tối ưu xếp hạng truy xuất trong hệ thống rag tiếng việt"]),
    case("RS-37", "multi_intent", "ad cho em hỏi 2 cái: hồ sơ miễn giảm kỳ này nộp từ ngày nào tới ngày nào, với nộp ở phòng nào ạ", ["Tiếp nhận hồ sơ từ 29/9/2026 đến hết 20/10/2026.", "Nộp theo thành phần và hướng dẫn tại phụ lục thông báo (nơi nhận: Phòng Công tác sinh viên)."],
         ["từ ngày 29/9/2026 đến hết ngày 20/10/2026"]),
    case("RS-38", "emotional", "huhu em sợ lỡ hạn nộp hồ sơ miễn giảm học phí kỳ này quá, hạn cuối là ngày nào vậy ad", ["Hạn cuối là hết ngày 20/10/2026 (tiếp nhận từ 29/9/2026)."],
         ["từ ngày 29/9/2026 đến hết ngày 20/10/2026"]),
    case("RS-39", "false_premise", "em nghe bảo hồ sơ minh chứng người khuyết tật phải nộp lại mỗi học kỳ phải không ạ", ["Không: sinh viên chỉ cần nộp hồ sơ minh chứng 01 lần cho đến khi kết thúc khóa học hoặc cho đến khi có văn bản hướng dẫn mới của chính phủ."],
         ["chỉ cần nộp hồ sơ minh chứng 01 lần cho đến khi kết thúc khóa học"], claims=["Phải nộp lại hồ sơ minh chứng mỗi học kỳ"]),
    case("RS-40", "false_premise", "ad ơi thông báo nói dùng usb trong phòng máy là tự do đúng ko, ko cần hỏi ai", ["Không: phải được sự đồng ý của cán bộ phòng máy mới được gắn USB."],
         ["phải được sự đồng ý của cán bộ phòng máy"], claims=["Dùng USB trong phòng máy là tự do, không cần hỏi ai"]),
]

# ---------------------------------------------------------------- part 4a: multi-turn dialogues
FEE_Q = "Học phí năm học 2026-2027 của sinh viên K69 hệ cử nhân chính quy là bao nhiêu một tín chỉ?"
P4A = [
    case("MT-01", "ellipsis_program", "thế còn kỹ sư thì sao?", ["Chương trình KS/KTS từ K69 là 547.000 đồng/tín chỉ."],
         ["| từ k69 | 547.000"], style="multi", history=[FEE_Q], claims=["Kỹ sư K69 là 592.500 đồng/tín chỉ"]),
    case("MT-02", "ellipsis_cohort", "vậy K64 trở về trước hệ kỹ sư chính quy thì bao nhiêu?", ["K64 trở về trước chương trình kỹ sư chính quy: 580.500 đồng/tín chỉ."],
         ["k64 trở về trước | 580.500"], style="multi", history=[FEE_Q], claims=["K64 là 592.500 đồng/tín chỉ"]),
    case("MT-03", "ellipsis_program", "còn chương trình chất lượng cao từ K67?", ["Kỹ sư chất lượng cao từ K67: 533.000 đồng/tín chỉ."],
         ["từ k67 | 533.000"], style="multi", history=[FEE_Q]),
    case("MT-04", "clarify_answer", "K67 chất lượng cao", ["Kỹ sư chất lượng cao từ K67: 533.000 đồng/tín chỉ."],
         ["từ k67 | 533.000"], style="multi", history=["học phí 1 tín chỉ bao nhiêu vậy ad"]),
    case("MT-05", "clarify_answer", "k66 trở xuống cl cao", ["K66 trở về trước kỹ sư chất lượng cao: 336.000 đồng/tín chỉ."],
         ["k66 trở về trước (đvht) | 336.000"], style="multi", history=["cho em hỏi mức học phí mỗi tín chỉ"]),
    case("MT-06", "correction", "ý em hỏi K64 chương trình CDIO cơ", ["K64 chương trình kỹ sư/kiến trúc sư theo tiếp cận CDIO: 649.000 đồng/tín chỉ."],
         ["k64 | 649.000"], style="multi", history=["học phí K68 hệ cử nhân bao nhiêu 1 tín chỉ vậy"], claims=["K64 CDIO là 592.500"]),
    case("MT-07", "scope_switch", "Quy định về thời hạn hiệu lực của chứng chỉ ngoại ngữ là bao lâu?",
         ["Trong thời hạn 02 năm tính từ ngày thi, trừ DELF và Cambridge không quy định thời hạn."],
         ["trừ bằng tiếng pháp delf, chứng chỉ cambridge english không quy định thời hạn"], style="multi", history=[FEE_Q], claims=["Học phí là 592.500 đồng"]),
    case("MT-08", "ellipsis_exception", "vậy DELF thì sao?", ["DELF không quy định thời hạn hiệu lực."],
         ["trừ bằng tiếng pháp delf, chứng chỉ cambridge english không quy định thời hạn"], style="multi",
         history=["Chứng chỉ ngoại ngữ nộp để xét miễn có thời hạn hiệu lực bao lâu?"]),
    case("MT-09", "ellipsis_exception", "còn cambridge", ["Chứng chỉ Cambridge English không quy định thời hạn."],
         ["trừ bằng tiếng pháp delf, chứng chỉ cambridge english không quy định thời hạn"], style="multi",
         history=["chứng chỉ ngoại ngữ dùng xét miễn có hạn dùng bao lâu", "DELF thì sao"]),
    case("MT-10", "pronoun", "nó dùng để làm gì?", ["Phiếu/tài khoản Office 365: tải bộ cài Microsoft 365 apps (Word, Excel...) bằng tài khoản nhà trường cấp."],
         ["install apps và chọn microsoft 365 apps"], style="multi",
         history=["Trường có cấp tài khoản Microsoft Office 365 cho sinh viên không?"], note="pronoun refers to the Office 365 account; weak gold, judged leniently"),
    case("MT-11", "followup_detail", "vậy còn phụ thu chương trình Anh ngữ K71 là bao nhiêu?", ["Phụ thu chương trình Anh ngữ, Pháp ngữ: K71 là 17.000.000 đồng/năm."],
         ["k71: 17.000.000 đ/năm"], style="multi", history=["Chương trình Anh ngữ có phải đóng thêm phụ thu không?"], claims=["K71 phụ thu 15.000.000 đồng/năm"]),
    case("MT-12", "followup_detail", "thế K70 trở về trước?", ["K70 trở về trước: phụ thu 15.000.000 đồng/năm."],
         ["k70 trở về trước: 15.000.000 đ/năm"], style="multi",
         history=["Phụ thu chương trình Anh ngữ K71 là bao nhiêu?"], claims=["K70 phụ thu 17.000.000 đồng/năm"]),
    case("MT-13", "followup_detail", "còn chương trình liên kết quốc tế thì sao?", ["Phụ thu chương trình liên kết quốc tế: 19.500.000 đồng/năm."],
         ["chương trình liên kết quốc tế (tính theo thời gian đào tạo chuẩn): 19.500.000 đ/năm"], style="multi",
         history=["Phụ thu chương trình Anh ngữ K71 là bao nhiêu?"]),
    case("MT-14", "ellipsis_deadline", "còn hạn nộp thì sao?", ["Tiếp nhận hồ sơ từ 29/9/2026 đến hết 20/10/2026."],
         ["từ ngày 29/9/2026 đến hết ngày 20/10/2026"], style="multi",
         history=["Thông báo 338 học kỳ I năm học 2026-2027 miễn giảm học phí cho những ai?"], claims=["Hạn nộp 31/10/2025"]),
    case("MT-15", "pronoun_doc", "hồ sơ đó nộp bao nhiêu lần?", ["Sinh viên chỉ cần nộp hồ sơ minh chứng 01 lần cho đến khi kết thúc khóa học hoặc cho đến khi có văn bản hướng dẫn mới của chính phủ."],
         ["sinh viên chỉ cần nộp hồ sơ minh chứng 01 lần cho đến khi kết thúc khóa học"], style="multi",
         history=["Sinh viên là con thương binh cần nộp những giấy tờ gì để miễn học phí?"]),
    case("MT-16", "topic_switch", "mua laptop mới thì dùng trong phòng máy được ko?", ["Không được sử dụng máy tính xách tay trong phòng máy tính."],
         ["sử dụng điện thoại di động, sử dụng máy tính xách tay"], style="multi",
         history=["Tân sinh viên K71 phân hiệu HCM nhập học online hạn nào?"], claims=["Hạn 21/8"]),
    case("MT-17", "topic_switch_absent", "vậy trường có chỗ gửi xe máy cho sinh viên không?", ["Nguồn không nêu về chỗ gửi xe; không được bịa."],
         [], style="multi", expected="abstain", history=["Nội quy phòng máy cấm gì?"],
         note="'gửi xe' appears nowhere in the served corpus (checked)"),
    case("MT-17b", "topic_switch", "ở đây có phải đóng học phí qua cổng nào ko?", ["Nộp học phí qua cổng thông tin sinh viên sinhvien.huce.edu.vn."],
         ["đăng ký môn học, xem thời khóa biểu, tra cứu điểm, và nộp học phí"], style="multi",
         history=["Nội quy phòng máy cấm gì?"]),
    case("MT-18", "thanks_then_ask", "cảm ơn ad. cho em hỏi thêm nhập học trực tiếp là ngày nào?", ["Nhập học trực tiếp tại Trường từ 21/8 đến 22/8 theo thời gian ghi trên giấy báo nhập học."],
         ["từ 21/8 đến 22/8: nhập học trực tiếp"], style="multi", history=["K71 phân hiệu HCM nhập học online hạn nào ạ"]),
    case("MT-19", "three_turn_chain", "còn trực tiếp tại trường?", ["Từ 21/8 đến 22/8 theo thời gian ghi trên giấy báo nhập học."],
         ["từ 21/8 đến 22/8: nhập học trực tiếp"], style="multi",
         history=["K71 phân hiệu HCM xác nhận nhập học trên cổng bộ đến mấy giờ", "ok còn nhập học trực tuyến?"]),
    case("MT-20", "ellipsis_year", "thế học kỳ 1 năm học 2025-2026 thì hạn nộp là khi nào?", ["Hồ sơ HKI 2025-2026: từ 06/10/2025 đến hết 31/10/2025, nộp tại Phòng CTCT&QLSV tầng 2 Trung tâm hỗ trợ sinh viên."],
         ["từ ngày 06/10/2025 đến hết ngày 31/10/2025"], style="multi",
         history=["Hạn nộp hồ sơ miễn giảm học phí HKI 2026-2027 là khi nào?"], claims=["Hạn 20/10/2026 cho năm 2025-2026"]),
    case("MT-21", "ellipsis_year", "còn kỳ 1 năm học 2026-2027?", ["Từ 29/9/2026 đến hết 20/10/2026."],
         ["từ ngày 29/9/2026 đến hết ngày 20/10/2026"], style="multi",
         history=["Hạn nộp hồ sơ miễn giảm học phí HKI 2025-2026 là khi nào?"], claims=["Hạn 31/10/2025 cho năm 2026-2027"]),
    case("MT-22", "ellipsis_program", "ngành kiến trúc nội thất K71 thì sao?", ["Tổng 180TC (không tính GDTC, GDQP và tiếng Anh nâng cao)."],
         ["tổng: 180tc (không tính hp giáo dục thể chất và giáo dục quốc phòng và tiếng anh nâng cao)"], style="multi",
         history=["Ngành kinh tế xây dựng K70 trở xuống tổng bao nhiêu tín chỉ?"], claims=["Kiến trúc nội thất tổng 190TC"]),
    case("MT-23", "ellipsis_program", "thế kinh tế xây dựng thì sao?", ["Tổng 190TC (không tính GDTC, GDQP)."],
         ["tổng: 190tc (không tính hp giáo dục thể chất, giáo dục quốc phòng và an ninh)"], style="multi",
         history=["Ngành kiến trúc nội thất K71 tổng bao nhiêu tín chỉ?"], claims=["Kinh tế xây dựng tổng 180TC"]),
    case("MT-24", "source_request", "nguồn ở đâu vậy ad", ["Nêu nguồn là Quyết định 924/QĐ-ĐHXDHN (mức học phí năm học 2026-2027) hoặc hiển thị trích dẫn tương ứng."],
         ["quyết định số 924/qđ-đhxdhn"], style="multi", history=[FEE_Q], note="expects a citation/source pointer for the previous answer"),
    case("MT-25", "correction_subject", "không phải, em hỏi phụ thu của chương trình Pháp ngữ cơ", ["Phụ thu chương trình Anh ngữ, Pháp ngữ: K70 trở về trước 15.000.000 đ/năm; K71 17.000.000 đ/năm."],
         ["mức phụ thu đối với chương trình anh ngữ, pháp ngữ"], style="multi",
         history=["Chương trình liên kết quốc tế phụ thu bao nhiêu một năm?"]),
    case("MT-26", "vague_followup", "vậy thì sao ạ?", ["Hỏi lại để làm rõ: không đủ ngữ cảnh để trả lời."],
         [], style="multi", expected="clarify", history=["Nội quy phòng máy có cấm đồ ăn thức uống không?"]),
    case("MT-27", "repeat_question", "nói lại giúp em mức học phí vừa rồi", ["K69 hệ cử nhân: 592.500 đồng/tín chỉ."],
         ["| từ k69 | 592.500"], style="multi", history=[FEE_Q, "cảm ơn, hiểu rồi"]),
    case("MT-28", "scope_carry_range", "vậy với K70 thì học phí cử nhân là bao nhiêu?", ["K70 thuộc nhóm 'từ K69': chương trình cử nhân 592.500 đồng/tín chỉ."],
         ["từ k69 | 592.500"], style="multi", history=[FEE_Q], claims=["K70 có mức học phí khác 592.500"]),
]

# ---------------------------------------------------------------- part 4b: conflicting / versioned sources
P4B = [
    case("CF-01", "conflict_times", "phiên khai mạc hội nghị FIT_CMA2026 diễn ra từ mấy giờ đến mấy giờ vậy ạ", ["Theo Thông báo số 2: phiên khai mạc 07h30 đến 08h30 tại Hội trường tầng 2 – Nhà Thư viện."],
         ["phiên khai mạc: từ 07h30 đến 08h30", "phiên khai mạc: 7h30-8h20"], style="conflict",
         conflict={"values": ["08h30", "8h20"], "authority": "Thông báo số 2"}),
    case("CF-02", "conflict_times", "hội nghị fit_cma mở màn lúc mấy giờ và xong phần khai mạc mấy giờ", ["Khai mạc bắt đầu 07h30; kết thúc 08h30 theo thông báo số 2."],
         ["phiên khai mạc: từ 07h30 đến 08h30", "phiên khai mạc: 7h30-8h20"], style="conflict",
         conflict={"values": ["08h30", "8h20"], "authority": "Thông báo số 2"}),
    case("CF-03", "conflict_password", "theo quy định thì mật khẩu tối thiểu phải dài bao nhiêu ký tự", ["Sổ tay: nên dài hơn 8 ký tự; Quy chế ATTT: độ dài ít nhất 8 ký tự (mật khẩu an toàn cao)."],
         ["độ dài ít nhất 8 ký tự"], style="conflict", conflict={"values": ["hơn 8", "ít nhất 8"], "authority": "Quy chế ATTT 2114"}),
    case("CF-04", "year_versions", "hạn nộp hồ sơ miễn giảm học phí học kỳ 1 là ngày nào", ["Học kỳ I 2026-2027: 29/9/2026 đến hết 20/10/2026; (học kỳ I 2025-2026: 06/10/2025 đến hết 31/10/2025)."],
         ["từ ngày 29/9/2026 đến hết ngày 20/10/2026", "từ ngày 06/10/2025 đến hết ngày 31/10/2025"], style="conflict",
         conflict={"values": ["20/10/2026", "31/10/2025"], "authority": "năm học mới nhất 2026-2027"}),
    case("CF-05", "year_versions", "hạn nộp hồ sơ miễn giảm học phí kỳ 1 năm nay là hôm nào", ["Năm nay (học kỳ I năm học 2026-2027): hết ngày 20/10/2026."],
         ["từ ngày 29/9/2026 đến hết ngày 20/10/2026"], style="conflict", claims=["Hạn nộp là 31/10/2025 cho năm học 2026-2027"],
         conflict={"values": ["20/10/2026", "31/10/2025"], "authority": "năm học mới nhất 2026-2027"}),
    case("CF-06", "year_versions", "hạn nộp hồ sơ miễn giảm học phí học kỳ I năm học 2025-2026 là khi nào", ["06/10/2025 đến hết 31/10/2025."],
         ["từ ngày 06/10/2025 đến hết ngày 31/10/2025"], style="conflict", claims=["Hạn nộp 20/10/2026 cho năm học 2025-2026"]),
    case("CF-07", "scope_fee", "học phí K64 kỹ sư chính quy một tín chỉ bao nhiêu", ["K64 trở về trước chương trình kỹ sư chính quy: 580.500 đồng/tín chỉ (CDIO K64: 649.000)."],
         ["k64 trở về trước | 580.500"], style="conflict", claims=["K64 kỹ sư là 592.500 hoặc 547.000"]),
    case("CF-08", "scope_fee", "học phí K69 kỹ sư kiến trúc sư chính quy bao nhiêu 1 tc", ["Từ K69 chương trình KS/KTS: 547.000 đồng/tín chỉ."],
         ["từ k69 | 547.000"], style="conflict", claims=["K69 kỹ sư là 580.500 hoặc 870.500"]),
    case("CF-09", "scope_fee", "K69 hệ cử nhân chính quy học phí mỗi tín chỉ", ["Từ K69 chương trình cử nhân: 592.500 đồng/tín chỉ."],
         ["từ k69 | 592.500"], style="conflict", claims=["K69 cử nhân là 964.500"]),
    case("CF-10", "scope_fee", "học phí kỹ sư chất lượng cao khóa K66 trở về trước là bao nhiêu", ["K66 trở về trước kỹ sư chất lượng cao: 336.000 đồng/tín chỉ."],
         ["k66 trở về trước (đvht) | 336.000"], style="conflict", claims=["K66 CLC là 533.000"]),
    case("CF-11", "scope_fee", "kỹ sư chất lượng cao K67 trở đi học phí bao nhiêu", ["Từ K67 kỹ sư chất lượng cao: 533.000 đồng/tín chỉ."],
         ["từ k67 | 533.000"], style="conflict", claims=["K67 CLC là 336.000"]),
    case("CF-12", "scope_fee", "K65 đến K68 cử nhân học phí mỗi tín chỉ ạ", ["K65 đến K68 chương trình cử nhân: 592.500 đồng/tín chỉ."],
         ["k65 đến k68 | 592.500"], style="conflict"),
    case("CF-13", "scope_surcharge", "phụ thu chương trình Anh ngữ Pháp ngữ K71 một năm bao nhiêu", ["K71: 17.000.000 đồng/năm."],
         ["k71: 17.000.000 đ/năm"], style="conflict", claims=["K71 là 15.000.000 đồng/năm"]),
    case("CF-14", "scope_surcharge", "phụ thu chương trình Anh ngữ cho sinh viên K69 là bao nhiêu một năm", ["K70 trở về trước: 15.000.000 đồng/năm (áp dụng cho K69)."],
         ["k70 trở về trước: 15.000.000 đ/năm"], style="conflict", claims=["K69 là 17.000.000 đồng/năm"]),
    case("CF-15", "superseded", "học phí theo quyết định 960 năm 2024 là bao nhiêu một tín chỉ", ["Không có số liệu của Quyết định 960/2024 trong nguồn; Quyết định 924/2026 đã thay thế các quyết định 960 và 1010."],
         ["thay thế cho quyết định số 960/qđ-đhxdhn ngày 21 tháng 6 năm 2024"], style="conflict", expected="limit",
         claims=["Học phí theo Quyết định 960 là 592.500 hoặc 580.500 đồng/tín chỉ"], note="refusing with a pointer to Quyết định 924 is acceptable; inventing a figure is not"),
    case("CF-16", "superseded", "quyết định 924 có thay thế quyết định nào trước đó không", ["Có: thay thế Quyết định 960/QĐ-ĐHXDHN (21/6/2024) và Quyết định 1010/QĐ-ĐHXDHN (02/7/2024)."],
         ["thay thế cho quyết định số 960/qđ-đhxdhn ngày 21 tháng 6 năm 2024, quyết định số 1010/qđ-đhxdhn ngày 02 tháng 7 năm 2024"], style="conflict"),
    case("CF-17", "year_missing", "học phí K69 năm học 2025-2026 là bao nhiêu một tín chỉ", ["Nguồn chỉ có mức năm học 2026-2027 (K69 cử nhân 592.500) và nói rõ đó là năm học 2026-2027, không có số liệu năm 2025-2026."],
         ["từ k69 | 592.500"], style="conflict", expected="limit",
         claims=["Học phí K69 năm học 2025-2026 là 592.500 đồng/tín chỉ (không nói rõ đó là mức năm học 2026-2027)"],
         note="refusing is acceptable; answering must disclose the year difference"),
    case("CF-18", "applicability", "K69 có được áp dụng quyết định 94 miễn học miễn thi tiếng Anh không", ["Quyết định 94 áp dụng từ khóa tuyển sinh 2025 (K70); Khóa 69 trở về trước áp dụng quy định hiện hành cho đến hết khóa đào tạo."],
         ["đối với khóa69trở về trước áp dụng quy định hiện hành cho đến thời điểm kết thúc khóa đào tạo"], style="conflict", claims=["K69 được áp dụng Quyết định 94"]),
    case("CF-19", "applicability", "k70 có áp dụng quyết định 94 về miễn học miễn thi tiếng anh bằng ielts không", ["Có: Quyết định 94 áp dụng từ Khóa 70 trở đi, sinh viên có chứng chỉ hợp lệ được xét miễn học, miễn thi, quy đổi điểm."],
         ["áp dụng từ khóa 70 trở đi"], style="conflict"),
    case("CF-20", "program_confusion", "ngành kinh tế xây dựng tổng bao nhiêu tín chỉ", ["Tổng 190TC (không tính GDTC, GDQP)."],
         ["tổng: 190tc (không tính hp giáo dục thể chất, giáo dục quốc phòng và an ninh)"], style="conflict", claims=["Kinh tế xây dựng 180TC"]),
    case("CF-21", "program_confusion", "ngành kiến trúc nội thất K71 tổng bao nhiêu tín chỉ", ["Tổng 180TC."],
         ["tổng: 180tc (không tính hp giáo dục thể chất và giáo dục quốc phòng và tiếng anh nâng cao)"], style="conflict", claims=["Kiến trúc nội thất 190TC"]),
    case("CF-22", "degree_level_confusion", "học phí kỹ sư kiến trúc sư hệ vừa làm vừa học bao nhiêu một tín chỉ", ["Hệ vừa làm vừa học, chương trình cấp bằng kỹ sư/kiến trúc sư: 870.500 đồng/tín chỉ (khác hệ chính quy 547.000)."],
         ["2 | chương trình cấp bằng kỹ sư, kiến trúc sư | | 870.500"], style="conflict", claims=["Hệ vừa làm vừa học là 547.000"]),
    case("CF-23", "degree_level_confusion", "học phí cử nhân hệ vừa làm vừa học mỗi tín chỉ", ["Hệ vừa làm vừa học, chương trình cấp bằng cử nhân: 964.500 đồng/tín chỉ."],
         ["1 | chương trình cấp bằng cử nhân | | 964.500"], style="conflict", claims=["Cử nhân vừa làm vừa học là 592.500"]),
    case("CF-24", "ambiguous_scope", "học phí một tín chỉ năm học 2026-2027 là bao nhiêu", ["Phụ thuộc khóa/chương trình: nêu các mức (580.500, 592.500, 547.000, 533.000...) và mời chọn; không chốt một số duy nhất."],
         ["k64 trở về trước | 580.500", "từ k69 | 592.500"], style="conflict",
         claims=["Học phí mọi sinh viên là một mức duy nhất"]),
]


def verify(rows):
    bad = []
    for r in rows:
        for e in r.get("evidence", []):
            if norm(e) not in CORPUS:
                bad.append((r["case_id"], e))
    return bad


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sets = {"real-style-20261114.jsonl": P3, "multiturn-20261114.jsonl": P4A, "conflict-20261114.jsonl": P4B}
    bad = [b for rows in sets.values() for b in verify(rows)]
    if bad:
        print("EVIDENCE NOT FOUND:")
        for cid, e in bad:
            print(" ", cid, "::", e)
        sys.exit(1)
    for name, rows in sets.items():
        (D / name).write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
        print(name, len(rows), "cases, evidence verified")


if __name__ == "__main__":
    main()
