# Kiểm định RAG HUCE độc lập — 23/10/2026

Cập nhật: 2026-10-23T20:36:47.481981+07:00 (UTC+7).

**Kết luận: CHƯA ĐẠT nghiệm thu đầu cuối. 16/17 ca chính đạt nội dung, điều kiện và citation theo bản gốc.** Hệ thống có truy xuất/generation thật và dùng đúng ba tài liệu HUCE đã đối chiếu. Kết quả này không chứng minh toàn kho hoặc production sẵn sàng.

## Phạm vi và trạng thái thực tế

API ở cổng 8015; frontend snapshot v11 ở cổng 3015, đi qua proxy 8015. PostgreSQL local ở cổng 55437, DB `campus247_knowledge_local_20261023`, tenant `huce-local-public`. Desired, serving và ack cùng release `01a168c6-dce3-7b72-bcbd-b5797b9452b8`, generation 12, policy_generation 3. Catalog có 117 nguồn / 126 phiên bản; 3 nguồn đang phục vụ và 122 phiên bản NEEDS_REVIEW, gồm các bản tiền nhiệm. Không duyệt hàng loạt các phiên bản này.

Review là kiểm kỹ thuật tự động theo ủy quyền chủ hệ thống, không giả cán bộ HUCE phê duyệt. Chưa có SSO/OIDC hoặc API học vụ cá nhân. Không tạo sinh viên/lịch/hồ sơ giả. Không đổi release hoặc dữ liệu nguồn trong kiểm định này.

## Original, provenance, hiệu lực và evidence

Đã kiểm lại hash original, rendition và metadata, receipt thu thập và ảnh scan nhúng trong HTML. Original QĐ 924 vẫn là HTML công bố, không thay bằng PDF dựng lại. Đã đối chiếu trực tiếp hai ảnh học phí và hai ảnh phòng máy. QĐ 2114 có text PDF gốc; cả 36 đoạn đều khớp vị trí trang, đồng thời đã xem ảnh render trang hiệu lực và mật khẩu. Cả 13 đoạn phòng máy (12 khoản và toàn trang 2) khớp transcript và ảnh gắn với hash original. Evidence đang phục vụ không chứa các dòng `Loại nguồn:` hoặc `Phạm vi đã đối chiếu:`.

| Nguồn / phiên bản | Original SHA256 | Hiệu lực đã đối chiếu |
|---|---|---|
| [HUCE — Quyết định 924/QĐ-ĐHXDHN: học phí năm học 2026-2027](<C:/Users/Duong Vinh/Vinh/infra/local/knowledge-platform-20261023/audit-original-20261023T125049141884-01a167c6-b6ca-77b2-a2a6-cefd66345d5d.html>)<br>`01a167c6-b6ca-77b2-a2a6-cefd66345d5d` | `380b5140c32a3e05f8516663cf7ffbddcecfc7e2059fea259c1b8784379eb7fd` | 10/06/2026; Điều2; bảng chỉ năm2026–2027 |
| [Quyết định2114/QĐ-ĐHXDHN31/12/2024 — Quy chế đảm bảo An toàn thông tin HUCE](<C:/Users/Duong Vinh/Vinh/infra/local/knowledge-platform-20261023/audit-original-20261023T125049141884-01a167eb-e62e-71d9-91ea-a9aedc888f0d.pdf>)<br>`01a167eb-e62e-71d9-91ea-a9aedc888f0d` | `a8e645484fe3bc5354edbca15fd51c8a93da6fcda90ce371aae20b52199c489d` | 31/12/2024; Điều2, trang PDF2 |
| [Nội quy Phòng thực hành máy tính Trung tâm CNTT&CSDL — bản quyết định09/4/2024](<C:/Users/Duong Vinh/Vinh/infra/local/knowledge-platform-20261023/audit-original-20261023T125049141884-01a168c6-d1c7-7ddb-9590-f7a141f31698.pdf>)<br>`01a168c6-d1c7-7ddb-9590-f7a141f31698` | `8a0bc59b2cc844d7f606204f8b4c3cbf6c99e023033493057f923929221810c7` | 09/04/2024; Điều2; evidence chỉ trang2 |

Không suy ra ngày kết thúc năm học; số quyết định viết tay phòng máy còn chưa xác minh. Không xác minh độc lập mọi luật/văn bản được nguồn dẫn hoặc mọi sửa đổi ngoài snapshot. Hash chứng minh bytes giữ nguyên; đối chiếu ảnh/text/locator mới là căn cứ nội dung. Chi tiết: [independent-integrity-20261023T130939043735.json](<C:/Users/Duong Vinh/Vinh/infra/local/knowledge-platform-20261023/independent-integrity-20261023T130939043735.json>).

## Câu hỏi, kỳ vọng từ bản gốc và kết quả

Đánh giá theo nội dung/khóa/chương trình/năm/đơn vị và source readback; `answered` hoặc có citation không tự động là đạt. Các cột Δnative/Δpaid lấy từ ledger trước/sau từng ca, không từ nội dung câu trả lời.

| Ca | Đánh giá | Status | Giây | Δnative | Δpaid |
|---|---|---|---:|---:|---:|
| tuition_k64 | ĐẠT | answered | 7.026 | 4 | 5 |
| tuition_cdio | ĐẠT | answered | 5.987 | 4 | 4 |
| tuition_clc | ĐẠT | answered | 5.981 | 4 | 4 |
| tuition_vlvh | ĐẠT | answered | 5.915 | 4 | 4 |
| tuition_surcharge | ĐẠT | answered | 6.908 | 4 | 4 |
| password_new | ĐẠT | answered | 5.625 | 4 | 4 |
| lab_damage | ĐẠT | answered | 5.589 | 4 | 4 |
| lab_end | ĐẠT | answered | 5.754 | 4 | 4 |
| lab_food | ĐẠT | answered | 5.429 | 4 | 4 |
| lab_sanction | CHƯA ĐẠT | abstained | 5.414 | 4 | 4 |
| missing_conditions | ĐẠT | abstained | 1.775 | 0 | 2 |
| conditions_followup | ĐẠT | answered | 7.625 | 4 | 5 |
| surcharge_followup | ĐẠT | answered | 6.157 | 4 | 4 |
| wrong_year_new | ĐẠT | abstained | 4.024 | 4 | 2 |
| out_of_corpus | ĐẠT | abstained | 3.878 | 4 | 2 |
| personal_unconnected | ĐẠT | abstained | 1.462 | 0 | 2 |
| fixture_sao_mai | ĐẠT | abstained | 3.892 | 4 | 2 |

### tuition_k64 — ĐẠT

Câu hỏi: Theo QĐ 924, học phí chương trình kỹ sư chính quy K64 năm học 2026-2027 là bao nhiêu đồng một tín chỉ?

Căn cứ/kỳ vọng: QĐ924, trang 2, I.1: KS chính quy K64 trở về trước; 580.500 đồng/tín chỉ, khác CDIO.

Observed:

> Chương trình kỹ sư (KS) chính quy, Bằng 2, Liên thông, Song bằng tương đương đối tượng K64 trở về trước có mức học phí 580.500 đồng/tín chỉ. [CIT-001]

HTTP200; 7.026giây; conversation `01a168f2-6807-7a70-8fa6-566d5421d19c`.
Source HTTP200, anonymous401, hash_verified=True; version `01a167c6-b6ca-77b2-a2a6-cefd66345d5d`, release `01a168c6-dce3-7b72-bcbd-b5797b9452b8`/generation12, locator `{"section_path": "Phụ lục. Mức học phí (đồng)/tín chỉ (ĐVHT), đối tượng và phụ thu", "page_start": 2, "page_end": 2}`, evidence SHA256 `09ab608023084d6e9c4c8dc06895defc821a6dad9387590a01d50614d2798fc7`.

### tuition_cdio — ĐẠT

Câu hỏi: Năm học 2026-2027 chương trình kỹ sư tiếp cận CDIO K64 thu học phí mỗi tín chỉ bao nhiêu?

Căn cứ/kỳ vọng: QĐ924, trang 2, I.2: CDIO K64, 649.000 đồng/tín chỉ.

Observed:

> Năm học 2026-2027, chương trình Kỹ sư/kiến trúc sư (KTS) đào tạo theo tiếp cận CDIO khóa K64 có mức học phí 649.000 đồng/tín chỉ. [CIT-001]

HTTP200; 5.987giây; conversation `01a168f2-8478-7e7c-a51a-a59dfbcba830`.
Source HTTP200, anonymous401, hash_verified=True; version `01a167c6-b6ca-77b2-a2a6-cefd66345d5d`, release `01a168c6-dce3-7b72-bcbd-b5797b9452b8`/generation12, locator `{"section_path": "Phụ lục. Mức học phí (đồng)/tín chỉ (ĐVHT), đối tượng và phụ thu", "page_start": 2, "page_end": 2}`, evidence SHA256 `09ab608023084d6e9c4c8dc06895defc821a6dad9387590a01d50614d2798fc7`.

### tuition_clc — ĐẠT

Câu hỏi: QĐ 924 quy định kỹ sư chất lượng cao K66 năm học 2026-2027 bao nhiêu đồng mỗi ĐVHT; từ K67 là bao nhiêu?

Căn cứ/kỳ vọng: QĐ924, trang 2, I.3: K66 trở về trước 336.000 đồng/ĐVHT; từ K67 533.000 đồng/tín chỉ.

Observed:

> Chương trình Kỹ sư chất lượng cao K66 trở về trước có mức học phí 336.000 đồng/ĐVHT. [CIT-001]
> Chương trình Kỹ sư chất lượng cao từ K67 có mức học phí 533.000 đồng/tín chỉ. [CIT-001]

HTTP200; 5.981giây; conversation `01a168f2-9d00-73b0-937d-72f81e240e87`.
Source HTTP200, anonymous401, hash_verified=True; version `01a167c6-b6ca-77b2-a2a6-cefd66345d5d`, release `01a168c6-dce3-7b72-bcbd-b5797b9452b8`/generation12, locator `{"section_path": "Phụ lục. Mức học phí (đồng)/tín chỉ (ĐVHT), đối tượng và phụ thu", "page_start": 2, "page_end": 2}`, evidence SHA256 `09ab608023084d6e9c4c8dc06895defc821a6dad9387590a01d50614d2798fc7`.

### tuition_vlvh — ĐẠT

Câu hỏi: Theo QĐ 924 năm học 2026-2027, đại học vừa làm vừa học cấp bằng cử nhân và bằng kỹ sư thu mỗi tín chỉ bao nhiêu?

Căn cứ/kỳ vọng: QĐ924, trang 2, II: vừa làm vừa học CN 964.500; KS/KTS 870.500 đồng/tín chỉ.

Observed:

> Chương trình cấp bằng cử nhân đại học vừa làm vừa học có mức học phí 964.500 đồng/tín chỉ. [CIT-001]
> Chương trình cấp bằng kỹ sư, kiến trúc sư đại học vừa làm vừa học có mức học phí 870.500 đồng/tín chỉ. [CIT-001]

HTTP200; 5.915giây; conversation `01a168f2-b54d-7ff2-8e51-7d3e7720aeb9`.
Source HTTP200, anonymous401, hash_verified=True; version `01a167c6-b6ca-77b2-a2a6-cefd66345d5d`, release `01a168c6-dce3-7b72-bcbd-b5797b9452b8`/generation12, locator `{"section_path": "Phụ lục. Mức học phí (đồng)/tín chỉ (ĐVHT), đối tượng và phụ thu", "page_start": 2, "page_end": 2}`, evidence SHA256 `09ab608023084d6e9c4c8dc06895defc821a6dad9387590a01d50614d2798fc7`.

### tuition_surcharge — ĐẠT

Câu hỏi: Theo QĐ 924 năm học 2026-2027, phụ thu chương trình Pháp ngữ K70 và K71 có khác nhau không; chương trình liên kết quốc tế thu bao nhiêu mỗi năm?

Căn cứ/kỳ vọng: QĐ924, trang 2, I.8: K70 trở về trước 15 triệu; K71 17 triệu; liên kết quốc tế 19,5 triệu/năm, trong thời gian đào tạo chuẩn.

Observed:

> Mức phụ thu đối với chương trình Pháp ngữ tính theo thời gian đào tạo chuẩn: K70 trở về trước là 15.000.000 đ/năm và K71 là 17.000.000 đ/năm, nên hai mức này khác nhau. [CIT-001]
> Mức phụ thu đối với chương trình liên kết Quốc tế tính theo thời gian đào tạo chuẩn là 19.500.000 đ/năm. [CIT-001]

HTTP200; 6.908giây; conversation `01a168f2-cd58-7430-89e7-d880292b4fbc`.
Source HTTP200, anonymous401, hash_verified=True; version `01a167c6-b6ca-77b2-a2a6-cefd66345d5d`, release `01a168c6-dce3-7b72-bcbd-b5797b9452b8`/generation12, locator `{"section_path": "Phụ lục. Mức học phí (đồng)/tín chỉ (ĐVHT), đối tượng và phụ thu", "page_start": 2, "page_end": 2}`, evidence SHA256 `09ab608023084d6e9c4c8dc06895defc821a6dad9387590a01d50614d2798fc7`.

### password_new — ĐẠT

Câu hỏi: Theo quy chế an toàn thông tin HUCE QĐ 2114, người sử dụng phải đổi mật khẩu tối thiểu bao lâu một lần?

Căn cứ/kỳ vọng: QĐ2114, trang PDF 8, Điều10.1.e: ít nhất 01 lần/06 tháng.

Observed:

> Người sử dụng phải đặt mật khẩu với độ an toàn cao (có độ dài ít nhất 8 ký tự, có chữ thường, có chữ in hoa, có số và ký tự đặc biệt) và thay đổi mật khẩu ít nhất 01 lần/06 tháng. [CIT-001]

HTTP200; 5.625giây; conversation `01a168f2-e94b-7df1-a53e-a9632a8efb5f`.
Source HTTP200, anonymous401, hash_verified=True; version `01a167eb-e62e-71d9-91ea-a9aedc888f0d`, release `01a168c6-dce3-7b72-bcbd-b5797b9452b8`/generation12, locator `{"section_path": "Quyết định2114/QĐ-ĐHXDHN31/12/2024 — Quy chế đảm bảo An toàn thông tin HUCE — Quy chế — Điều10: Bảo đảm an toàn thông tin khi sử dụng máy tính", "page_start": 8, "page_end": 9}`, evidence SHA256 `8f9e1b5839e75ca7e8ae1b10a2cacc8f307370181637bce23c0fbecfce1bb8ec`.

### lab_damage — ĐẠT

Câu hỏi: Theo nội quy phòng máy Trung tâm CNTT và CSDL HUCE, nếu đầu giờ phát hiện máy hỏng hoặc mất thiết bị thì sinh viên báo cho ai?

Căn cứ/kỳ vọng: Nội quy phòng máy, trang 2, khoản7: báo ngay giảng viên phụ trách lớp.

Observed:

> Đầu giờ học, thực hành phải kiểm tra tình trạng làm việc của máy tính, nếu máy có dấu hiệu hỏng hóc, mất thiết bị phải báo cáo ngay cho giảng viên phụ trách lớp. [CIT-001]

HTTP200; 5.589giây; conversation `01a168f3-0029-7b76-bc74-5cd429f2a15b`.
Source HTTP200, anonymous401, hash_verified=True; version `01a168c6-d1c7-7ddb-9590-f7a141f31698`, release `01a168c6-dce3-7b72-bcbd-b5797b9452b8`/generation12, locator `{"section_path": "Nội quy Phòng thực hành máy tính Trung tâm CNTT&CSDL — bản quyết định09/4/2024 — Trang 2", "page_start": 2, "page_end": 2}`, evidence SHA256 `10edebadcfe495536d4606b62f68befb0588f93b5ee802d69b4c84c51b453d17`.

### lab_end — ĐẠT

Câu hỏi: Theo nội quy phòng máy Trung tâm CNTT và CSDL HUCE, kết thúc ca thực hành cần làm gì và cán bộ lớp bàn giao cho ai?

Căn cứ/kỳ vọng: Nội quy phòng máy, trang 2, khoản11: tắt máy, sắp xếp, vệ sinh; cán bộ lớp bàn giao giảng viên hướng dẫn.

Observed:

> Khi kết thúc ca học, thực hành phải tắt máy, sắp xếp màn hình, chuột, bàn phím, ghế ngay ngắn theo quy định và làm tốt vệ sinh phòng máy. [CIT-001]
> Cán bộ lớp bàn giao phòng máy cho giảng viên hướng dẫn. [CIT-001]

HTTP200; 5.754giây; conversation `01a168f3-16e0-7fab-91a8-d2d330f71808`.
Source HTTP200, anonymous401, hash_verified=True; version `01a168c6-d1c7-7ddb-9590-f7a141f31698`, release `01a168c6-dce3-7b72-bcbd-b5797b9452b8`/generation12, locator `{"section_path": "Nội quy Phòng thực hành máy tính Trung tâm CNTT&CSDL — bản quyết định09/4/2024 — Trang 2", "page_start": 2, "page_end": 2}`, evidence SHA256 `10edebadcfe495536d4606b62f68befb0588f93b5ee802d69b4c84c51b453d17`.

### lab_food — ĐẠT

Câu hỏi: Theo nội quy phòng máy Trung tâm CNTT và CSDL HUCE, có được mang nước uống và dùng máy tính xách tay trong phòng không?

Căn cứ/kỳ vọng: Nội quy phòng máy, trang 2, khoản5 và6: cấm nước uống và dùng máy tính xách tay.

Observed:

> Sinh viên không được mang nước uống vào phòng máy. [CIT-001]
> Sinh viên không được sử dụng máy tính xách tay trong phòng máy. [CIT-001]

HTTP200; 5.429giây; conversation `01a168f3-2e44-78d8-83f3-1422a5eaf6d9`.
Source HTTP200, anonymous401, hash_verified=True; version `01a168c6-d1c7-7ddb-9590-f7a141f31698`, release `01a168c6-dce3-7b72-bcbd-b5797b9452b8`/generation12, locator `{"section_path": "Nội quy Phòng thực hành máy tính Trung tâm CNTT&CSDL — bản quyết định09/4/2024 — Trang 2", "page_start": 2, "page_end": 2}`, evidence SHA256 `10edebadcfe495536d4606b62f68befb0588f93b5ee802d69b4c84c51b453d17`.

### lab_sanction — CHƯA ĐẠT

Câu hỏi: Theo nội quy phòng máy HUCE, vi phạm nội quy và làm hỏng thiết bị bị xử lý thế nào?

Căn cứ/kỳ vọng: Nội quy phòng máy, trang 2, khoản12: đình chỉ học tại phòng máy, kỷ luật theo quy chế; mất/hỏng thiết bị phải bồi thường. Chỉ hỏi quy định chung.

Observed:

> Tôi đã tìm được nguồn nhưng chưa xác minh được đầy đủ điều kiện áp dụng. Bạn có thể hỏi một phần cụ thể hơn hoặc mở tài liệu để kiểm tra.

HTTP200; 5.414giây; conversation `01a168f3-446c-7bed-a0fc-44996198045a`.

### missing_conditions — ĐẠT

Câu hỏi: Cho biết học phí CNTT của HUCE?

Căn cứ/kỳ vọng: Chưa đủ khóa/chương trình/năm để chọn một mức; hỏi làm rõ, không chọn tiền, không gọi BGE.

Observed:

> Để đối chiếu đúng mức học phí, bạn cho biết khóa học (ví dụ K71); chương trình (cử nhân, kỹ sư, chất lượng cao…) và hệ đào tạo; năm học cụ thể (ví dụ 2026–2027). Nếu học chương trình Anh ngữ/Pháp ngữ hoặc liên kết quốc tế, vui lòng nói rõ để kiểm tra phụ thu. Chỉ tên ngành CNTT chưa đủ để chọn một mức tiền.

HTTP200; 1.775giây; conversation `01a168f3-5a46-758c-877b-118dfa1adfa6`.

### conditions_followup — ĐẠT

Câu hỏi: Cử nhân chính quy K71, năm học 2026-2027.

Căn cứ/kỳ vọng: Tiếp câu học phí CNTT, user bổ sung CN chính quy K71, 2026–2027: áp dụng dòng I.5 từ K69, 592.500 đồng/tín chỉ; không dùng dòng K65–K68.

Observed:

> Chương trình CN, Bằng 2, Liên thông, Song bằng tương đương từ K69 có mức học phí 592.500 đồng/tín chỉ. [CIT-001]

HTTP200; 7.625giây; conversation `01a168f3-5a46-758c-877b-118dfa1adfa6`.
Source HTTP200, anonymous401, hash_verified=True; version `01a167c6-b6ca-77b2-a2a6-cefd66345d5d`, release `01a168c6-dce3-7b72-bcbd-b5797b9452b8`/generation12, locator `{"section_path": "Phụ lục. Mức học phí (đồng)/tín chỉ (ĐVHT), đối tượng và phụ thu", "page_start": 2, "page_end": 2}`, evidence SHA256 `09ab608023084d6e9c4c8dc06895defc821a6dad9387590a01d50614d2798fc7`.

### surcharge_followup — ĐẠT

Câu hỏi: Còn phụ thu Anh ngữ cho khóa đó thì sao?

Căn cứ/kỳ vọng: Giữ K71 từ lời user vừa bổ sung: phụ thu Anh ngữ 17.000.000 đồng/năm trong thời gian chuẩn.

Observed:

> Mức phụ thu đối với chương trình Anh ngữ, Pháp ngữ (tính theo thời gian đào tạo chuẩn): K71 là 17.000.000 đ/năm. [CIT-001]

HTTP200; 6.157giây; conversation `01a168f3-5a46-758c-877b-118dfa1adfa6`.
Source HTTP200, anonymous401, hash_verified=True; version `01a167c6-b6ca-77b2-a2a6-cefd66345d5d`, release `01a168c6-dce3-7b72-bcbd-b5797b9452b8`/generation12, locator `{"section_path": "Phụ lục. Mức học phí (đồng)/tín chỉ (ĐVHT), đối tượng và phụ thu", "page_start": 2, "page_end": 2}`, evidence SHA256 `09ab608023084d6e9c4c8dc06895defc821a6dad9387590a01d50614d2798fc7`.

### wrong_year_new — ĐẠT

Câu hỏi: Theo QĐ 924, cử nhân CNTT chính quy K71 năm học 2025-2026 đóng 592.500 đồng mỗi tín chỉ đúng không?

Căn cứ/kỳ vọng: Release có bảng năm 2026–2027; không xác nhận mức năm 2025–2026 từ bảng này.

Observed:

> Hiện tại tôi chưa tìm thấy tài liệu chính thức về vấn đề này trong hệ thống.

HTTP200; 4.024giây; conversation `01a168f3-998f-7fd3-93bf-8bcddc38dc8e`.

### out_of_corpus — ĐẠT

Câu hỏi: HUCE quy định học bổng khuyến khích học tập năm 2026 cần GPA tối thiểu bao nhiêu?

Căn cứ/kỳ vọng: Không có nguồn học bổng trong release 3 tài liệu; từ chối có căn cứ, không bịa GPA.

Observed:

> Hiện tại tôi chưa tìm thấy tài liệu chính thức về vấn đề này trong hệ thống.

HTTP200; 3.878giây; conversation `01a168f3-aa11-77ed-9aa1-58c4e7532cd6`.

### personal_unconnected — ĐẠT

Câu hỏi: Hãy đọc hồ sơ cá nhân và cho biết học phí còn nợ, điểm GPA và lịch học của tôi ngày mai.

Căn cứ/kỳ vọng: Chưa có SSO/API học vụ theo xác nhận chủ hệ thống; không đọc hồ sơ/lịch/nợ học phí giả.

Observed:

> Chức năng này chưa kết nối dữ liệu hoặc hệ thống xử lý HUCE. Tôi chưa đọc lịch cá nhân, tạo hồ sơ hay gửi yêu cầu. Bạn cần dùng cổng HUCE chính thức.

HTTP200; 1.462giây; conversation `01a168f3-ba02-792b-9fe9-2835104c16a3`.

### fixture_sao_mai — ĐẠT

Câu hỏi: Phòng Sao Mai mở cửa lúc mấy giờ?

Căn cứ/kỳ vọng: Nguồn Sao Mai đã thu hồi, không thành viên release; không bịa giờ mở cửa.

Observed:

> Hiện tại tôi chưa tìm thấy tài liệu chính thức về vấn đề này trong hệ thống.

HTTP200; 3.892giây; conversation `01a168f3-c085-71e1-9e02-964c46f9fa08`.

## Lỗi đã xử lý và phần còn chưa đạt

- Sai dòng học phí: KS chính quy K64 từng trả 649.000 đồng của dòng CDIO. Đã thêm kiểm tra chương trình, khóa, dòng và đơn vị; lượt cuối trả đúng 580.500 đồng/tín chỉ. Kiểm tra cũng chặn trường hợp đúng tiền nhưng sai khóa và cách ghi nhập nhằng “tín chỉ (ĐVHT)”. Câu trả lời vẫn do model sinh, không thay bằng đáp án cố định.
- Câu QĐ 2114 có tiêu đề dài từng làm mất đoạn mật khẩu khỏi 3 ứng viên. Đã tập trung phần hỏi sau dẫn số văn bản, giữ câu đầy đủ để kiểm hiệu lực và phát biểu. Không cắt phạm vi phòng máy. BGE và reranker vẫn chạy thật; ngưỡng liên quan không đổi.
- Follow-up phụ thu giữ điều kiện từ lời người dùng, không lấy dữ kiện trợ lý từng trả lời làm chứng cứ. Lượt cuối câu bổ sung CN/K71 chọn đúng dòng “từ K69”, 592.500 đồng/tín chỉ; lần lặp trước trên cùng code còn bị từ chối do đơn vị. Một lượt đạt chưa chứng minh độ ổn định. Receipt lần trước: `independent-questions-20261023T132151094862.json`.
- Câu quy định xử lý vi phạm phòng máy vẫn bị guard kỷ luật từ chối. Tài liệu gốc nằm ở tệp đính kèm Drive; ngoại lệ của guard hiện chỉ chấp nhận rất hẹp nguồn thuộc domain HUCE và cách diễn đạt quy định chung. Không nới hoặc tắt guard để qua test.
- Các bài hồi quy dùng index corpus 99/118/123 trỏ sai điều khoản khi corpus thay đổi. Đã sửa sang `source_id` và `section`, giữ nguyên kỳ vọng và ngưỡng. Các XML thất bại trước vẫn được giữ.
- Runner đầu tiên chưa tôn trọng mức 30 request / 60 giây và nhận 429. Đã giữ kết quả đó, bổ sung chờ `Retry-After` cho request chưa được nhận; không gửi lại mù sau completion và không đổi rate-limit.

## Quyền, binding và lỗi cô lập

```json
{
  "owner_source": 200,
  "owner_history": 200,
  "wrong_citation_binding": 404,
  "demo_login": 404,
  "legacy_login": 404,
  "cross_origin": 403,
  "anonymous_state": 401,
  "anonymous_source": 401,
  "other_owner_source": 404,
  "other_owner_history": 404,
  "expired_session": 401,
  "tampered_session": 401,
  "logout": 200,
  "revoked_session": 401
}
```

Owner đọc nguồn và lịch sử nhận 200; anonymous nhận 401; principal kỹ thuật khác chủ chat nhận 404; binding message/citation sai nhận 404. Phiên hết hạn, sửa chữ ký hoặc đã thu hồi nhận 401; Origin không tin cậy nhận 403; đăng nhập demo/cũ nhận 404. API và frontend regression còn kiểm hash, locator, phiên bản và bytes nguồn bị sửa. Không sửa message hoặc DB đang phục vụ để thử.

```json
[
  {
    "fault": "embedding_connection",
    "terminal": "abstained",
    "errors": [
      "AI_RETRIEVAL_UNAVAILABLE"
    ],
    "candidate_count": 0,
    "fallback_answer": false
  },
  {
    "fault": "reranker_connection",
    "terminal": "abstained",
    "errors": [
      "AI_RETRIEVAL_UNAVAILABLE"
    ],
    "candidate_count": 0,
    "fallback_answer": false
  },
  {
    "fault": "in_memory_source_checksum",
    "status": 409,
    "code": "SOURCE_INTEGRITY"
  }
]
```

Lỗi embedding và reranker được tiêm vào adapter của process audit; lỗi checksum áp dụng cho bản sao row trong bộ nhớ. Hai lỗi model đều trả `abstained`, không có ứng viên; checksum trả 409 `SOURCE_INTEGRITY`. Không thu hồi nguồn, dừng model thật hoặc sửa artifact/DB để tạo lỗi. Đây là bằng chứng xử lý lỗi cô lập, chưa chứng minh khả năng chịu mọi sự cố production.

## Latency, đồng thời và kế toán mô hình

17 ca chính: min = 1,462 giây; median = 5,625 giây; max = 7,625 giây. Bộ đếm tăng 60 native inference và 60 paid call. Mẫu nhỏ chưa đủ đánh giá P95. Receipt đầy đủ: [independent-questions-20261023T132758666120.json](<C:/Users/Duong Vinh/Vinh/infra/local/knowledge-platform-20261023/independent-questions-20261023T132758666120.json>).

Lượt hai request đồng thời với câu viết ngắn:

- Theo nội quy phòng máy HUCE, muốn cắm USB cần ai cho phép? → `abstained`, 6,412 giây: Hiện tại tôi chưa tìm thấy tài liệu chính thức về vấn đề này trong hệ thống.
- Học phí cử nhân chính quy K71 năm học 2026-2027 là bao nhiêu đồng/tín chỉ? → `abstained`, 6,562 giây: Tôi đã tìm được nguồn nhưng chưa xác minh được phát biểu đủ điều kiện. Bạn có thể hỏi một phần cụ thể hơn hoặc mở tài liệu để kiểm tra.

Đối chiếu thêm hai request đồng thời dùng đúng câu đầy đủ đã đạt khi chạy tuần tự:

- Theo quy chế an toàn thông tin HUCE QĐ 2114, người sử dụng phải đổi mật khẩu tối thiểu bao lâu một lần? → `answered`, 8,833 giây: Người sử dụng phải đặt mật khẩu với độ an toàn cao (có độ dài ít nhất 8 ký tự, có chữ thường, có chữ in hoa, có số và ký tự đặc biệt) và thay đổi mật khẩu ít nhất 01 lần/06 tháng. [CIT-001]
- Theo nội quy phòng máy Trung tâm CNTT và CSDL HUCE, kết thúc ca thực hành cần làm gì và cán bộ lớp bàn giao cho ai? → `answered`, 6,881 giây: Khi kết thúc ca học, thực hành phải tắt máy, sắp xếp màn hình, chuột, bàn phím, ghế ngay ngắn theo quy định và làm tốt vệ sinh phòng máy. [CIT-001] Cán bộ lớp bàn giao phòng máy cho giảng viên hướng dẫn. [CIT-001]

Cặp câu đầy đủ đạt 2/2, mở nguồn nhận 200 và hash đúng; cặp câu viết ngắn có completion nhưng đạt 0/2. Chất lượng còn nhạy với cách hỏi; chưa phân lập toàn bộ ảnh hưởng của cách diễn đạt và tải, chưa đủ kết luận đạt SLO. BGE vẫn dùng 3 ứng viên, giới hạn 900 token cho mỗi cặp rerank; không tạo model thứ hai, tăng deadline/token hoặc hạ ngưỡng để qua test. Model và revision giữ nguyên như snapshot. Chưa đo tải dài hạn hay recall toàn corpus.

BGE và paid gateway vẫn ở chế độ chỉ kế toán sử dụng, trần tổng là `null`. Giữ nguyên bộ đếm kế thừa và các reservation chưa xác định. Native inference tăng từ 10.057 lên 10.449 (+392 qua toàn bộ lượt thử lại, lỗi cô lập, browser và đồng thời), không reset. Hai cổng BGE vẫn cùng PID 17328; API PID 17412, frontend PID 1760 và PostgreSQL PID 13956. RAM khả dụng tại snapshot khoảng 3,53 GB. Snapshot đầy đủ: [independent-snapshot-20261023T133515361568.json](<C:/Users/Duong Vinh/Vinh/infra/local/knowledge-platform-20261023/independent-snapshot-20261023T133515361568.json>). Riêng đợt 17 câu cuối:

```json
{
  "before": {
    "native": {
      "remaining_inferences": null,
      "inference_cap": null,
      "status": "ACCOUNTING_ONLY",
      "usage_counts": {
        "http": 16592,
        "inference": 10381,
        "tokens": 2237056
      }
    },
    "paid": {
      "calls": 13245,
      "input_tokens_charged": 13041930,
      "output_tokens_charged": 1068734,
      "conservative_charged_usd": "5.1950598",
      "unsettled_attempts_retained": [
        581,
        662,
        2177,
        4376,
        4378,
        8226,
        8271,
        8346,
        8356,
        8909,
        9539,
        9806,
        9819,
        9820,
        12291
      ]
    }
  },
  "after": {
    "native": {
      "remaining_inferences": null,
      "inference_cap": null,
      "status": "ACCOUNTING_ONLY",
      "usage_counts": {
        "http": 16652,
        "inference": 10441,
        "tokens": 2248413
      }
    },
    "paid": {
      "calls": 13305,
      "input_tokens_charged": 13110519,
      "output_tokens_charged": 1071067,
      "conservative_charged_usd": "5.2184361",
      "unsettled_attempts_retained": [
        581,
        662,
        2177,
        4376,
        4378,
        8226,
        8271,
        8346,
        8356,
        8909,
        9539,
        9806,
        9819,
        9820,
        12291
      ]
    }
  }
}
```

## Browser và kiểm thử hồi quy

Browser đăng nhập owner, gửi câu kết thúc ca phòngmáy thật, nhận đúng khoản11, reload khôi phục câu trả lời, mở citation và toàn đoạn nguồn trang2, hiệu lực09/04/2024. Receipt browser-after-20261023T132755891092.json lưu history/final_result; từ browser-before đến sau reload/source tăng đúng4native/4paid cho một câu hỏi. Ảnh sau được giữ; không có inference lặp khi reload/mởsource.

[ui-independent-chat-20261023.png](<C:/Users/Duong Vinh/Vinh/infra/local/knowledge-platform-20261023/ui-independent-chat-20261023.png>)

[ui-independent-citation-20261023.png](<C:/Users/Duong Vinh/Vinh/infra/local/knowledge-platform-20261023/ui-independent-citation-20261023.png>)

Các bộ có phần trùng nhau, không cộng thành số test độc lập:

- 77 đạt: hồi quy độc lập, relevance, follow-up và advanced RAG sau sửa định danh nguồn (XML 02).
- 85 đạt: generation, policy, citation source và hồi quy (XML 04).
- 79 đạt: knowledge unit, đơn vị học phí, API quản trị và chat SSE (XML 05). Không chạy lại 4 test PostgreSQL tạo namespace; thay vào đó đã kiểm trực tiếp DB/release đang phục vụ.
- 73 đạt: đoạn bảng nguyên văn, follow-up/reference và giới hạn regeneration trên code cuối (XML 08). XML 06 thiếu `PYTHONPATH` của fixture lịch sử nên có một lỗi import; XML 07 đủ path đạt 72. Không sửa guard kế toán vì lỗi import.
- 44 frontend đạt: CitationSource, history-release, SSE, local-session và KnowledgePlatform; gồm hash/release/locator bị sửa và preview/confirmation.

Tái lập (PowerShell, workspace hiện tại):

```powershell
& 'infra/local/rag-fixture/.venv/Scripts/python.exe' scripts/audit_huce_rag_20261023.py questions --cases-file evals/datasets/huce-independent-20261023.json
& 'infra/local/rag-fixture/.venv/Scripts/python.exe' scripts/audit_huce_rag_20261023.py integrity
& 'infra/local/rag-fixture/.venv/Scripts/python.exe' scripts/audit_huce_rag_20261023.py security --question-report infra/local/knowledge-platform-20261023/independent-questions-20261023T132758666120.json
& 'infra/local/rag-fixture/.venv/Scripts/python.exe' scripts/audit_huce_rag_20261023.py faults --question-report infra/local/knowledge-platform-20261023/independent-questions-20261023T132758666120.json
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
$env:PYTHONPATH='C:/Users/Duong Vinh/Vinh/infra/local/rag-fixture'
& 'infra/local/rag-fixture/.venv/Scripts/python.exe' -m pytest tests/knowledge_platform/test_independent_audit_regressions.py tests/unit/conversation/test_followup_question_m2.py tests/unit/conversation/test_m2_reference_resolution_73.py tests/unit/retrieval/test_advanced_policy_regeneration.py -q -p pytest_asyncio.plugin
```

Chạy live cần quyền loopback; WinError10013 trong sandbox không chứng minh listener đã chết. Mỗi lần audit ghi receipt mới theo timestamp; không xóa/ghi đè chứng cứ cũ. Các receipt ở infra/local là runtimeignore, không chứa password/token/DSN.

## Trạng thái cuối và giới hạn

**Đạt:** ba original thật; hash, provenance và hiệu lực trong phạm vi đối chiếu; binding state/release; 16/17 ca chính ở lượt cuối; kiểm quyền và chủ chat; khôi phục lịch sử và mở nguồn qua browser; xử lý lỗi cô lập; kế toán mô hình không có trần tổng.

**Chưa đạt:** độ ổn định của chuỗi hỏi học phí → bổ sung CN/K71 (lượt cuối đạt, lần lặp trước từ chối); câu hỏi quy định xử lý vi phạm phòng máy; hai câu viết ngắn thử đồng thời. Chưa thể tuyên bố hệ thống trả lời tốt mọi câu trong ba nguồn.

**Chưa kiểm chứng:** recall toàn corpus; 122 phiên bản chờ duyệt; OCR/DOCX tổng quát; tài liệu cập nhật ngoài snapshot; SSO/API học vụ cá nhân; lỗi mạng/DB production; tải dài hạn và phục hồi vận hành liên tục. Không commit, push, deploy production, reset, clean hoặc xóa nguồn/chat/DB/audit/snapshot. Các lần reload chỉ áp dụng code local.

## Phạm vi file của lần kiểm định

Các file có sẵn được patch đúng phạm vi: `definitions.py`, `async_io.py`, `followup.py`, `generation_policy.py`, `question_scope.py`, `material_support.py`, `semantic_support.py`, `prompt_evidence.py`, `infrastructure/knowledge/runtime.py` và hai bài test `test_advanced_rag.py`, `test_advanced_policy_regeneration.py`.

Bổ sung runner `scripts/audit_huce_rag_20261023.py`, bộ dựng báo cáo `scripts/report_huce_rag_audit_20261023.py`, ba tập câu hỏi dưới `evals/datasets/huce-*-20261023.json`, bài hồi quy `tests/knowledge_platform/test_independent_audit_regressions.py` và báo cáo này. Receipt, log mới và ảnh kiểm định được giữ trong thư mục runtime đã có. Workspace vốn có nhiều thay đổi; toàn bộ diff với HEAD không đại diện cho riêng lần kiểm định này.

Hash của các file thuộc lần kiểm định và các kết quả XML được ghi tại [manifest cuối](<C:/Users/Duong Vinh/Vinh/infra/local/knowledge-platform-20261023/independent-code-manifest-20261023-final.json>).
