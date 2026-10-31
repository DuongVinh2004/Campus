# A3 — Sinh, kiểm chứng, kết quả có kiểu

## Tóm tắt (≤ 8 dòng)

- Đã đọc A0 trước A3; hoàn thành kiểm định chỉ đọc, không gọi mạng, mô hình trả phí hay runtime.
- Bằng chứng: mã hiện tại, 20 cặp nguồn–phát biểu chạy trực tiếp qua `check_statement`, các probe bằng gateway giả và **212 kiểm thử đạt**.
- Xác nhận các đường bỏ sót điều kiện ở dữ kiện, hiển thị nội dung chưa kiểm trong câu làm rõ và nhận nhầm phát biểu cá nhân qua ngoại lệ “kỷ luật”.
- Ngữ cảnh bị loại theo kích thước nhưng không được phản ánh đầy đủ bằng `partial`; chưa có kiểm độ phủ từng ý.
- Lỗi lọt kiểm xác định dưới đây **không đồng nghĩa** đã lọt kiểm ngữ nghĩa thật; độ chính xác và tính nhất quán của mô hình thật chưa đo trong phiên này.
- Không sửa/tạo/xóa tệp; không đọc nội dung ca holdout. Các đường dẫn `rag_v2/…` dưới `services/api/src/campus247/`.

## Phát hiện

### A3-01 [BLOCKER][confirmed] Nhánh dữ kiện vẫn bỏ điều kiện ngoài cửa sổ hoặc khác cách diễn đạt

- Vị trí: [rag_v2/service.py:58](C:/Users/Duong%20Vinh/Vinh/services/api/src/campus247/rag_v2/service.py:58), các dòng 53–75, 171–195.
- Bằng chứng: dùng `extract_facts` trên dòng `Học phí đại trà K64: 580.500 đồng/tín chỉ.` rồi thử ba đoạn cha: điều kiện **đứng trước** dòng; đứng sau với câu `Mức này dành cho học phần học lại.`; hoặc `Chỉ áp dụng…` sau hơn 600 ký tự. Cả ba trả `answer`, **0 lời gọi mô hình**, chỉ hiển thị dòng học phí.
- Tác động tài liệu mới: chú thích đầu bảng, điều kiện ở đoạn trước, cuối bảng dài hoặc văn phong “dành cho” bị mất. **Sửa ở §9–§10 chưa đủ vì** mã hiện tại chỉ dò một tập cụm từ và tối đa 600 ký tự phía sau trong đoạn cha.
- Tác động ổn định/vận hành: đây là đường hiển thị phát biểu chưa kiểm ngữ nghĩa; trích nguyên văn một dòng không bảo đảm kết luận áp dụng đúng.
- Đề xuất thiết kế: dữ kiện phải mang liên kết tới tiêu đề, điều kiện, ngoại lệ và chú thích của đơn vị cấu trúc. Chỉ đi đường nhanh khi chứng minh được bao đóng điều kiện; trường hợp khác phải kiểm ngữ nghĩa.
- Kiểm chứng: kiểm xác định với điều kiện trước/sau, khoảng cách thay đổi, chú thích bảng và cách diễn đạt tương đương; 0 lời gọi thật cho kiểm cơ chế.

### A3-02 [BLOCKER][confirmed] Ngoại lệ “kỷ luật” cho phép phát biểu về cá nhân đã được dẫn nguồn

- Vị trí: [rag_v2/discipline.py:58](C:/Users/Duong%20Vinh/Vinh/services/api/src/campus247/rag_v2/discipline.py:58), dòng 58–64, 93–97; [agent/nodes/rag_v2.py:159](C:/Users/Duong%20Vinh/Vinh/services/api/src/campus247/agent/nodes/rag_v2.py:159).
- Bằng chứng: nguồn tổng hợp chính thức chứa `Sinh viên Nguyễn Văn An bị kỷ luật.`; `discipline_failure` trả `None`. Chạy qua đồ thị bằng gateway giả chấp nhận phát biểu cho `terminal=answered`, một claim. Biến thể `…đã bị kỷ luật khi vi phạm nội quy.` cũng qua.
- Tác động tài liệu mới: quyết định xử lý một người có tên riêng có thể được coi là quy định chung. Bộ dò không nhận tên riêng; thêm chữ “khi” làm vượt kiểm cáo buộc.
- Tác động ổn định/vận hành: **sửa ở §17 chưa đủ vì** điều kiện nguồn chính thức và khớp từ không chứng minh phát biểu là quy tắc chung. Đây là lỗi của cổng xác định, chưa phải bằng chứng mô hình thật sẽ sinh phát biểu đó.
- Đề xuất thiết kế: tách chính sách phát biểu cá nhân khỏi kiểm nguồn; phân biệt quy tắc có biến đối tượng với sự kiện về thực thể có tên. Không quyết định ngoại lệ an toàn bằng một cụm từ và danh sách đại từ.
- Kiểm chứng: probe trên Outcome đã được chấp nhận, tên tổng hợp, chủ ngữ thay đổi, thì bị lược và “khi” chỉ hoàn cảnh quá khứ; 0 lời gọi thật để kiểm cổng.

### A3-03 [BLOCKER][confirmed] Câu làm rõ có thể chứa khẳng định thực tế chưa kiểm chứng

- Vị trí: [rag_v2/generation/generate.py:39](C:/Users/Duong%20Vinh/Vinh/services/api/src/campus247/rag_v2/generation/generate.py:39), dòng 39–42, 85–87; [rag_v2/service.py:129](C:/Users/Duong%20Vinh/Vinh/services/api/src/campus247/rag_v2/service.py:129).
- Bằng chứng: mô hình giả trả `decision=clarify`, `clarify_question="Bạn phải nộp 999 hồ sơ trước khi hỏi lại?"`. Dịch vụ hiển thị nguyên câu này trong kết quả `clarify`, không chạy kiểm xác định/ngữ nghĩa. Bộ lọc chỉ kiểm độ dài, URL, `@` và chuỗi ≥8 chữ số.
- Tác động tài liệu mới: mô hình có thể đưa mức thu, hạn nộp hoặc điều kiện suy đoán vào tiền đề của câu hỏi làm rõ.
- Tác động ổn định/vận hành: đường `clarify` tạo ngoại lệ đối với nguyên tắc mọi khẳng định thực tế phải được kiểm và dẫn nguồn.
- Đề xuất thiết kế: mô hình đề xuất slot thiếu; máy chủ dựng câu hỏi từ nhãn slot đã kiểm. Nếu cho phép văn bản tự do, phải kiểm tiền đề thực tế như claim.
- Kiểm chứng: JSON giả chứa câu hỏi có tiền đề sai, số ngắn và điều kiện không có nguồn; 0 lời gọi thật.

### A3-04 [HIGH][confirmed] Đóng gói bỏ cả đoạn cha, có nhánh vượt ngân sách và không báo thiếu ngữ cảnh

- Vị trí: [rag_v2/service.py:208](C:/Users/Duong%20Vinh/Vinh/services/api/src/campus247/rag_v2/service.py:208), dòng 208–223; [rag_v2/verification/semantic.py:36](C:/Users/Duong%20Vinh/Vinh/services/api/src/campus247/rag_v2/verification/semantic.py:36); `scripts/run_public_rag.py:118`.
- Bằng chứng: `CONTEXT_BYTES=19_000` là **tổng** byte JSON của các đoạn cha, tối đa 6 đoạn; không phải 19 KB cho từng đoạn. Đoạn 60 KB bị bỏ nguyên khối, không cắt an toàn theo cấu trúc. Probe có một cha 60 KB và một cha nhỏ chỉ gửi cha nhỏ, rồi trả `answer`, `partial_note=None`.
- Tác động tài liệu mới: bảng 500 hàng hoặc ngoại lệ cuối đoạn có thể biến mất. Nếu không cha nào vừa, dịch vụ giữ các unit con; probe 12 unit con tạo payload messages **41.182 byte**, vượt trần 28.000 byte còn phải cộng overhead của cổng.
- Tác động ổn định/vận hành: có một cha vừa thì mất các unit không được đưa vào `parents`; không cha nào vừa thì quay về nhánh không có giới hạn byte tương đương. Nhánh này còn có thể sinh 9–12 nguồn, trong khi semantic từ chối >8 nguồn; probe 9 nguồn trả `None`, 0 dispatch.
- Đề xuất thiết kế: một bộ đóng gói dùng chung ngân sách payload thực, giới hạn nguồn thống nhất; chọn hàng kèm header/chú thích/điều kiện và ghi rõ phần loại bỏ. Thiếu bao đóng điều kiện phải chặn claim liên quan.
- Kiểm chứng: các tổ hợp cha lớn/nhỏ, bảng 500 hàng, 8/9/12 nguồn, Unicode và câu hỏi dài; đo byte sau serialize; 0 lời gọi thật.

### A3-05 [BLOCKER][confirmed] Thiếu một ý chưa từng được sinh vẫn được gắn nhãn `answer`

- Vị trí: [rag_v2/outcome/compose.py:33](C:/Users/Duong%20Vinh/Vinh/services/api/src/campus247/rag_v2/outcome/compose.py:33), dòng 33, 78–82; [rag_v2/verification/semantic.py:17](C:/Users/Duong%20Vinh/Vinh/services/api/src/campus247/rag_v2/verification/semantic.py:17).
- Bằng chứng: nguồn có cả `Sinh viên nộp đơn bảo lưu.` và `Hồ sơ bảo lưu cần giấy xác nhận.`; hỏi `Thủ tục và hồ sơ bảo lưu?`; gateway giả chỉ sinh câu đầu. Kết quả **`answer`, không partial note**. `coverage` mặc định 1.0 và service không truyền giá trị đo được; semantic được chỉ dẫn không kiểm độ đầy đủ.
- Tác động tài liệu mới: danh sách dài, nhiều môn, nhiều mốc hoặc nhiều điều kiện dễ bị bỏ mục mà không có tín hiệu thiếu.
- Tác động ổn định/vận hành: xác nhận bằng probe cơ chế còn thiếu mà REPORT §15–§19 đã nêu; đếm claim được nhận không đo được ý chưa xuất hiện.
- Đề xuất thiết kế: tạo các facet có ID và đối tượng/phạm vi; mỗi claim liên kết facet và span nguồn; chỉ cho `answer` khi mọi facet bắt buộc có trạng thái được giải quyết. Đo tính đầy đủ của danh sách từ cấu trúc nguồn.
- Kiểm chứng: kiểm máy các trạng thái facet bị thiếu, bị loại, không nguồn và cần làm rõ; sau đó khoảng 60 lượt thật cho 20 câu mới ×3.

### A3-06 [HIGH][confirmed] Kiểm xác định chỉ kiểm tập giá trị, chưa kiểm quan hệ và điều kiện

- Vị trí: [rag_v2/verification/deterministic.py:168](C:/Users/Duong%20Vinh/Vinh/services/api/src/campus247/rag_v2/verification/deterministic.py:168), dòng 27–49, 168–184.
- Bằng chứng: P09–P14, P16–P17 trong bảng bên dưới đều là phát biểu sai nhưng `passed=True`: đổi tiền tệ/khối lượng, lấy số hàng khác, đổi số La Mã/số chữ, tráo phần trăm và bỏ điều kiện. `_number("0.125")` còn đồng nhất với `125`.
- Tác động tài liệu mới: bảng nhiều hàng/cột, đơn vị mới và quy ước số khác kho hiện tại làm tăng số claim chỉ còn semantic bảo vệ.
- Tác động ổn định/vận hành: đây là lỗi lọt tầng xác định, không chứng minh đã vượt semantic thật. Sai quan hệ hàng bảng cũng đang được một test xem là `passed` tại `tests/rag_v2/verification/test_deterministic.py:106`.
- Đề xuất thiết kế: kiểm bộ giá trị có kiểu gồm đối tượng–thuộc tính–giá trị–đơn vị–phạm vi–điều kiện, liên kết span/hàng/cột; không so tập số độc lập.
- Kiểm chứng: bộ kiểm biến đổi từng thành phần, hoán vị hàng/cột và đơn vị; 0 lời gọi thật cho parser, khoảng 40 lượt semantic thật để đo lớp chặn còn lại.

### A3-07 [HIGH][confirmed] Ngày, phủ định và phạm vi đúng vẫn bị chặn trước semantic

- Vị trí: [rag_v2/verification/deterministic.py:65](C:/Users/Duong%20Vinh/Vinh/services/api/src/campus247/rag_v2/verification/deterministic.py:65), dòng 65–99, 124–155.
- Bằng chứng: P05–P08, P15 và P20 bị từ chối dù diễn đạt tương đương. Ngày dấu chấm được nhận bởi `DATE` nhưng không bởi `DAY_MONTH`; phủ định kép bị so theo từ; câu kết hợp hai nguồn K64/K65 bị yêu cầu phù hợp **từng** scope.
- Tác động tài liệu mới: văn bản pháp lý, ngày ISO, đơn vị quy đổi, phần trăm viết chữ và câu so sánh nhiều đối tượng dễ bị từ chối nhầm.
- Tác động ổn định/vận hành: claim bị loại trước semantic; một claim còn tốt thì service không sửa claim lỗi. **Sửa ở §18 chưa đủ vì** thay độ dài cụm phủ định không giải quyết cấu trúc logic và chuẩn hóa kiểu giá trị.
- Đề xuất thiết kế: chuẩn hóa ngày thống nhất; có chính sách rõ về chuyển đơn vị; biểu diễn phủ định/ngoại lệ theo mệnh đề; kiểm scope theo claim con–nguồn tương ứng.
- Kiểm chứng: kiểm tương đương hai chiều, phủ định kép và phép hợp nhiều nguồn; 0 lời gọi thật.

**Các luật hiện có của `check_statement` và điều kiện kích hoạt**

| Luật | Khi kích hoạt |
|---|---|
| `UNIT_NOT_CITED` | Không có ref, ref không tồn tại, marker liên hệ không thuộc nguồn đã dẫn hoặc văn bản sau khôi phục rỗng. |
| `DATE_NOT_IN_SOURCE` | Tập ngày đầy đủ hoặc ngày–tháng trong claim không là tập con của nguồn; hai bộ nhận dạng không hỗ trợ cùng định dạng. |
| `CODE_NOT_IN_SOURCE` | Mã chữ–số hoặc mã văn bản dạng số/ký hiệu không xuất hiện trong nguồn đã dẫn. |
| `NUMBER_NOT_IN_SOURCE` | Số đã chuẩn hóa hoặc số trước `%` không thuộc tập giá trị của nguồn; không giữ liên kết với hàng, đối tượng hay đơn vị. |
| `NEGATION_MISMATCH`: nguồn ngắn | Nguồn sau fold ≤600 ký tự: tập từ phủ định/ngoại lệ khác tập của câu nguồn chọn bằng trùng từ. |
| `NEGATION_MISMATCH`: mọi nguồn | Claim thêm số lần xuất hiện từ phủ định/ngoại lệ; hoặc từ ngay sau phủ định không khớp nguồn. |
| `NEGATION_MISMATCH`: bỏ cụm | Claim chứa cụm đủ ba từ sau phủ định nguồn, nhưng không có tiền tố được chấp nhận như phủ định, “ngoại”, “chỉ”. |
| `SCOPE_MISMATCH` | Khóa/năm/ngành nhận dạng trong claim không phù hợp với metadata của bất kỳ unit được dẫn nào. |
| Không có luật entailment đầy đủ | Không kiểm riêng danh từ đơn vị, số chữ/La Mã, gắn số với đối tượng, hay mọi điều kiện khẳng định. `SEMANTIC_UNSUPPORTED` do service bổ sung sau semantic. |

**20 cặp đã chạy ngoại tuyến**

Lệnh thực thi: mã truyền qua stdin vào `.venv/Scripts/python.exe -B -`; mỗi cặp dựng `Unit`, `Statement` rồi gọi `check_statement`. `PASS` dưới đây chỉ là kết quả tầng xác định.

| ID | Nguồn → Phát biểu | Đánh giá | Kết quả thực tế |
|---|---|---|---|
| P01 | `Mức thu 100 đồng.` → `Mức thu 999 đồng.` | Sai | Chặn `NUMBER_NOT_IN_SOURCE` |
| P02 | `Mã AB123 được dùng.` → `Mã AB124 được dùng.` | Sai | Chặn `CODE_NOT_IN_SOURCE` |
| P03 | `Sinh viên không được nghỉ học.` → `Sinh viên được nghỉ học.` | Sai | Chặn `NEGATION_MISMATCH` |
| P04 | `Hạn ngày 01 tháng 9 năm 2026.` → `Hạn 01/09/2026.` | Đúng | PASS |
| P05 | Cùng nguồn P04 → `Hạn 2026-09-01.` | Đúng | Chặn `DATE_NOT_IN_SOURCE` |
| P06 | `Hạn 01.09.2026.` → `Hạn 01/09/2026.` | Đúng | Chặn `DATE_NOT_IN_SOURCE`, `NUMBER_NOT_IN_SOURCE` |
| P07 | `Không phải không được nộp đơn.` → `Được nộp đơn.` | Cùng nghĩa cho phép | Chặn `NEGATION_MISMATCH` |
| P08 | `Khối lượng 1 kg.` → `Khối lượng 1000 g.` | Đúng về lượng | Chặn `NUMBER_NOT_IN_SOURCE` |
| P09 | `Giá 100 USD.` → `Giá 100 EUR.` | Sai | **PASS** |
| P10 | `Khối lượng 5 kg.` → `Khối lượng 5 tấn.` | Sai | **PASS** |
| P11 | Bảng: hàng A có 10,20; hàng B có 30,40 → `B có giá trị 10 và 20.` | Sai | **PASS** |
| P12 | `Học kỳ II nộp hồ sơ.` → `Học kỳ IV nộp hồ sơ.` | Sai | **PASS** |
| P13 | `Tối đa ba hồ sơ.` → `Tối đa năm hồ sơ.` | Sai | **PASS** |
| P14 | `Mức A 10%, mức B 20%.` → `Mức A 20%.` | Sai | **PASS** |
| P15 | `Tỷ lệ 50 phần trăm.` → `Tỷ lệ 50%.` | Đúng | Chặn `NUMBER_NOT_IN_SOURCE` |
| P16 | `Mức A 0.125.` → `Mức A 125.` | Đổi giá trị thập phân | **PASS** |
| P17 | `Sinh viên nộp hồ sơ nếu đã tốt nghiệp.` → `Sinh viên nộp hồ sơ.` | Bỏ điều kiện | **PASS** |
| P18 | Nguồn phòng đào tạo; claim trích ref `missing` | Ref sai | Chặn `UNIT_NOT_CITED` |
| P19 | `Liên hệ bộ phận.` → `Liên hệ PUBLIC_CONTACT_EMAIL_UNKNOWN.` | Marker không thuộc nguồn | Chặn `UNIT_NOT_CITED` |
| P20 | Hai unit `K64 dùng A1.`, `K65 dùng B2.`, scope tương ứng → `K64 dùng A1 và K65 dùng B2.` dẫn cả hai | Đúng | Chặn `SCOPE_MISMATCH` |

### A3-08 [HIGH][confirmed] Viết lại câu hỏi không được kiểm bảo toàn đối tượng và giá trị

- Vị trí: [rag_v2/generation/rewrite.py:43](C:/Users/Duong%20Vinh/Vinh/services/api/src/campus247/rag_v2/generation/rewrite.py:43), dòng 43–49; `agent/nodes/rag_v2.py:113–115`.
- Bằng chứng: đầu vào `Học phí K67 bao nhiêu?`; gateway giả trả `Học phí K68 bao nhiêu?`; `rewrite_question` nhận nguyên kết quả K68. Chỉ có kiểm chuỗi, độ dài và link/address.
- Tác động tài liệu mới: mã khóa, chương trình và viết tắt mới có thể bị thay hoặc diễn giải lại; truy hồi và semantic sau đó cùng kiểm theo câu hỏi đã đổi.
- Tác động ổn định/vận hành: **sửa prompt ở §17 chưa đủ vì** ràng buộc giữ nguyên mã/từ của câu mới chưa được máy kiểm. Tần suất mô hình thật đổi sai chưa đo.
- Đề xuất thiết kế: trả các thao tác thêm/thay đại từ có span thay vì toàn bộ câu viết lại; khóa các số, mã, tên và đính chính tường minh của lượt mới; giữ câu gốc trong kiểm liên quan.
- Kiểm chứng: gateway giả đổi mã, số, phủ định và chủ đề phải bị từ chối; khoảng 60 lượt thật trên hội thoại có quy ước đặt tên mới.

### A3-09 [MEDIUM][confirmed] Prompt sinh mang giả định phạm vi gắn với kho hiện tại

- Vị trí: [rag_v2/generation/prompt.py:12](C:/Users/Duong%20Vinh/Vinh/services/api/src/campus247/rag_v2/generation/prompt.py:12); `generation/rewrite.py:15`; `verification/semantic.py:13–20`.
- Bằng chứng: prompt sinh diễn giải riêng `"K70_and_earlier"` và chỉ dẫn “nguồn không nêu khóa/ngành thì coi là áp dụng chung”. Prompt rewrite nêu `"KS/KTS", "CN", "TC", "K67"`. Prompt semantic không có ví dụ đặc thù tương tự.
- Tác động tài liệu mới: tên tệp có quy ước khác hoặc nguồn thiếu phạm vi do mất header có thể bị suy thành áp dụng chung. Đây là nguy cơ suy từ chỉ dẫn hiện tại; chưa đo tỷ lệ mô hình thật bị dẫn sai.
- Tác động ổn định/vận hành: bổ sung tài liệu có thể cần sửa prompt theo tên nguồn; ví dụ đặc thù không tạo hợp đồng phạm vi kiểm được.
- Đề xuất thiết kế: đưa phạm vi đã xác thực vào trường có kiểu; phân biệt `unknown` với `all`. Quy ước tên nguồn được xử lý lúc nạp, không truyền thành luật suy luận trong prompt chung.
- Kiểm chứng: fixture tên trung tính, tên có range khác và header thiếu; khoảng 40 lượt thật để so tác động prompt.

### A3-10 [HIGH][confirmed] Debug vẫn ghi câu hỏi thô dù đã có trường băm

- Vị trí: [rag_v2/generation/generate.py:76](C:/Users/Duong%20Vinh/Vinh/services/api/src/campus247/rag_v2/generation/generate.py:76), dòng 76–81; `generation/rewrite.py:50–54`.
- Bằng chứng: `content` chứa trường `question` và được ghi cùng `question_sha`; rewrite ghi `previous`, `question`, `rewritten`. Probe thay `Path.open` bằng buffer bộ nhớ xác nhận `raw_question_in_content=True`; không ghi tệp.
- Tác động tài liệu mới: câu hỏi về nguồn mới và nội dung nguồn được chụp nếu bật biến debug; dữ liệu không tự trở thành dữ liệu tổng hợp.
- Tác động ổn định/vận hành: **sửa ở §9 chưa đủ vì** băm một trường không loại câu hỏi khỏi `content`; rewrite bổ sung đường ghi thô. Đây là rủi ro khi bật debug, không phải xác nhận rò mặc định.
- Đề xuất thiết kế: capture mặc định chỉ lưu mã, số đếm, digest; capture nội dung phải có chế độ tổng hợp được kiểm tách khỏi runtime phục vụ.
- Kiểm chứng: buffer giả và canary trong câu hỏi/lịch sử/nguồn, kiểm mọi đường capture; 0 lời gọi thật.

### A3-11 [MEDIUM][confirmed] Timeout ở lần sửa có thể bị báo thành nội dung không xác minh được

- Vị trí: [rag_v2/service.py:230](C:/Users/Duong%20Vinh/Vinh/services/api/src/campus247/rag_v2/service.py:230), dòng 230–261.
- Bằng chứng: lần đầu sinh `Nộp 999 hồ sơ.` bị kiểm xác định loại; lần sửa ném `TimeoutError` ngay khi còn đủ ngân sách. Nhánh `continue` kết thúc vòng hai lượt, dùng lại `verdicts` lần đầu; probe trả **`refuse/unverified`**, không phải `transient_error`.
- Tác động tài liệu mới: tài liệu khó làm tăng nhu cầu sửa; lỗi hạ tầng trong lần sửa bị lẫn với thiếu bằng chứng nội dung.
- Tác động ổn định/vận hành: người dùng không nhận retry hint; thống kê loại lỗi và trace không phản ánh đúng lần cuối. Không tái hiện `UnboundLocalError` cũ: trường hợp này dùng dữ liệu cũ đã khởi tạo.
- Đề xuất thiết kế: trạng thái từng attempt phải tách thành thành công, không hỗ trợ, dữ liệu hỏng, timeout; kết thúc vòng không được ngầm sử dụng verdict từ attempt trước.
- Kiểm chứng: bảng chuyển trạng thái generation/repair/timeout và ngân sách còn lại; 0 lời gọi thật.

## Phần đã kiểm và thấy ổn (ngắn, để biết phạm vi đã phủ)

- Chạy:
  `.venv/Scripts/python.exe -B -m pytest tests/rag_v2/generation tests/rag_v2/verification tests/rag_v2/outcome tests/rag_v2/observability tests/rag_v2/test_service.py tests/rag_v2/test_rewrite.py tests/rag_v2/test_discipline_replay.py tests/rag_v2/test_output_guard.py -q -p no:cacheprovider --capture=sys`
  → **212 passed in 9.53s**, exit 0. Capture mặc định ban đầu không chạy được vì sandbox chặn tệp tạm; capture trong bộ nhớ chạy được.
- Semantic lỗi nhà cung cấp, timeout, JSON hỏng, thiếu/trùng chỉ số hoặc boolean sai kiểu trả `None`; service thử tối đa hai lần rồi `transient_error`, không nhận claim chưa kiểm.
- Trên đường sinh thông thường, mọi claim qua deterministic đều phải qua semantic; không thấy nhánh bỏ semantic vì claim “đơn giản”. Ngoại lệ dữ kiện nằm ở A3-01; câu làm rõ nằm ở A3-03.
- `REPAIRABLE` gồm mọi mã xác định trừ `SEMANTIC_UNSUPPORTED`. Chỉ sửa khi toàn bộ claim bị loại; bản sửa vẫn phải kiểm lại xác định và semantic. Không thấy vòng sửa tự cấp quyền bỏ kiểm.
- `answer` nhưng 0 claim được nhận → `refuse/unverified` khi có nguồn. `clarify` → kết quả hỏi lại; `no_source`/`out_of_scope` → từ chối có lý do tương ứng. Decision lạ/thiếu được xử lý như `answer` và vẫn phải kiểm claim.
- Không có kiểm độc lập tính đúng của decision từ chối; nguồn có đáp án vẫn có thể bị mô hình tuyên bố `no_source`. Đây là giới hạn còn nêu trong REPORT §18–§19.
- Nhiệt độ mặc định **0.0** (`ports/llm.py:69`); không có seed trong hợp đồng request. RRF phá hòa bằng `unit_id` (`retrieval/hybrid.py`); thứ tự ổn định với cùng kết quả truy hồi/snapshot, nhưng thêm nguồn hoặc đổi nội dung có thể đổi thứ tự. Chưa đo độ nhất quán mô hình thật.
- Ngân sách service mặc định 12 giây; generation tối đa hai attempt trong cửa sổ tối đa 8 giây, mỗi call ≤5 giây; semantic tối đa hai attempt ≤3,5 giây và dùng ngân sách chung. Node còn có timeout ngoài 12 giây bao gồm rewrite và ủy quyền.
- Các lỗi port trong khối điều phối được đổi thành kết quả có kiểu; `CancelledError` được truyền tiếp. `analyze` đứng ngoài `try`, nên bảo đảm không ném lỗi phụ thuộc hợp đồng đầu vào chuỗi hợp lệ.
- Trace lọc allowlist, chặn giá trị không hữu hạn và không chứa văn bản câu hỏi; log lỗi thông thường không in `str(exc)`. Capture debug là ngoại lệ A3-10.
- `contacts.py` dùng bộ nhận diện dùng chung, marker băm theo loại/giá trị và chỉ khôi phục marker thuộc nguồn được dẫn; cơ chế này tổng quát hơn luật từ khóa “kỷ luật”.
- Các kiểm hash, binding nguồn, publication, simulation và giữ các luật an toàn khác trong ngoại lệ kỷ luật đã có kiểm thử đạt; vấn đề A3-02 nằm ở phân biệt cá nhân/quy tắc.

## Câu hỏi mở cần chủ dự án quyết định (nếu có)

- Có cho phép đổi cách biểu diễn tương đương như `1 kg → 1000 g`, số chữ → số và ngày ISO không? Cần chốt chính sách để parser và tiêu chí chấm thống nhất; đổi giá trị/đơn vị sai vẫn phải chặn.
- Khi chỉ giải quyết được một phần câu hỏi, đề xuất mặc định trả `partial` kèm danh sách ý còn thiếu. Đây là lựa chọn trải nghiệm; kiểm độ phủ bằng mã vẫn cần có.

## Thiết kế đề xuất cho sinh + kiểm chứng ổn định trên văn phong mới

1. Biểu diễn nguồn theo cấu trúc: mệnh đề, bảng, header, chú thích, điều kiện, ngoại lệ và phạm vi có trạng thái `known/unknown/all`.
2. Dữ kiện nhanh chỉ được dùng khi có bằng chứng bao đóng điều kiện và liên kết chính xác tới đối tượng.
3. Viết lại bằng thao tác có span; khóa giá trị, mã, phủ định và đính chính của lượt mới.
4. Lập facet câu hỏi có ID, đối tượng và slot; giữ cả câu gốc để kiểm liên quan.
5. Đóng gói theo ngân sách payload thực, kèm dependency của nguồn; ghi nhận rõ facet/đoạn bị bỏ.
6. Sinh claim nguyên tử liên kết facet và span; kiểm số/ngày/đơn vị theo kiểu và quan hệ hàng/cột.
7. Semantic chỉ quyết định hỗ trợ từng claim; lỗi hoặc thiếu verdict phải đóng an toàn.
8. Câu hỏi làm rõ do máy chủ dựng từ slot đã kiểm; không hiển thị tiền đề thực tế tự do chưa xác minh.
9. Tách chính sách phát biểu cá nhân khỏi từ khóa và kiểm nguồn; giữ nguyên kiểm quyền/publication.
10. Máy chủ tính `answer/partial/refuse` từ claim, coverage và trạng thái nguồn; decision mô hình là đề xuất.
11. Điều phối bằng trạng thái attempt rõ ràng và deadline chung; không tái dùng verdict của attempt lỗi.
12. Kiểm bằng phép biến đổi văn phong, bảng lớn, đơn vị/ngày mới, nhiều ý và thứ tự nguồn; sau đó đo mô hình thật ×3 trên tài liệu mới độc lập.