# Mục tiêu: một RAG hoàn chỉnh, đo được, không phải vá lặp lại (2026-10-28)

## Mục tiêu
Xây lõi RAG v2 (hiểu câu hỏi, truy xuất, sinh câu trả lời, kiểm chứng, xử lý lỗi) sao cho:
1. Mỗi câu trả lời hiển thị đều truy được tới đoạn nguồn, và mọi số liệu, mã, ngày, điều kiện trong câu trả lời đều xuất hiện trong đoạn nguồn được dẫn (kiểm bằng mã, không bằng cảm nhận).
2. Khi không chắc, hệ thống từ chối hoặc hỏi lại, không bịa. Lỗi hạ tầng không bao giờ thành "câu trả lời sai" hay "lỗi trắng".
3. Chất lượng được chứng minh bằng bộ giữ kín và chạy lặp, không bằng vài ví dụ.

Không hệ RAG nào bảo đảm 0 câu sai tuyệt đối. Cam kết ở đây là giới hạn trên đo được: với n ca giữ kín mà không có câu sai nào, tỷ lệ sai thật có giới hạn trên khoảng 3/n ở mức tin cậy 95% (n=500 → ≤ 0,6%). Mọi chỗ hệ thống không chắc phải rơi vào từ chối, không rơi vào trả lời sai.

## Nhận định về hệ thống hiện tại (vì sao không vá tiếp)
- Câu trả lời được lắp từ nhiều mảnh đặc thù: trích dẫn riêng cho từng loại văn bản (`present_*_quotation`), thông báo ghim bằng mã băm, các quy tắc học phí, bộ chọn 3 ứng viên ghi cứng. Mỗi mảnh sửa một lỗi cũ và tạo mặt lỗi mới.
- Bộ kiểm chứng là một mô hình khác chấm "đã trả lời đúng câu hỏi chưa" và cho kết quả dao động giữa các lần chạy; 15/18 lần từ chối là câu đã có nguồn nhưng bị coi là chưa đủ.
- Rerank bị giới hạn bởi CPU (khoảng 0,45 giây mỗi cặp, ngắt ở 3 giây), buộc phải cắt ứng viên rất sớm.
- Kho trộn đoạn dài (trang sổ tay) với đoạn ngắn (khoản quy chế), chưa có cấu trúc "điều kiện cần có" cho từng loại câu hỏi.

Quyết định: giữ hạ tầng (Postgres/pgvector, mô hình nhúng và rerank, API, giao diện, lớp an toàn, hợp đồng SSE) và xây lại phần lõi truy xuất–sinh–kiểm chứng thành v2 sau cờ cấu hình. Chạy cả hai trên cùng bộ ca và chỉ chuyển sang v2 khi nó vượt v1 theo tiêu chí nghiệm thu. Không sửa v1 thêm ngoài lỗi chặn.

## Kiến trúc v2
1. **Nạp tài liệu có cấu trúc.** Quy chế tách theo Điều/khoản, bảng tách theo dòng, sổ tay tách theo mục và trang. Mỗi đơn vị có ID ổn định, phiên bản, hiệu lực, phạm vi áp dụng (khóa, chương trình), và kiểm tra tự động khi nạp (số đoạn, đoạn rỗng, trùng, vị trí trích).
2. **Dữ kiện có kiểu cho nhóm rủi ro cao.** Học phí, hạn nộp, điều kiện tiên quyết, đầu mối liên hệ trích thành bảng có nguồn; câu trả lời cho nhóm này lấy trực tiếp từ bảng, không để mô hình tự đọc số.
3. **Hiểu câu hỏi xác định.** Chuẩn hóa viết tắt, không dấu, năm học; nhận diện chủ đề, khóa, chương trình, năm; có danh sách "thông tin bắt buộc" cho từng loại câu hỏi và hỏi lại khi thiếu (thay cho bộ chấm "đã đủ chưa" bằng mô hình).
4. **Truy xuất hai tầng đủ rộng.** Từ khóa + vector lấy 40–60 ứng viên, tiền chọn ít nhất 12 cho rerank; rerank chạy trên phần cứng/lượng tử hóa đủ nhanh, lùi về xếp hạng dự phòng khi hết thời gian thay vì thất bại.
5. **Sinh có ràng buộc.** Mô hình chỉ được viết phát biểu kèm ID đoạn nguồn; mỗi phát biểu qua kiểm tra xác định (số, mã, ngày, phủ định, điều kiện bắt buộc có trong đoạn dẫn) và một bước kiểm chứng ngữ nghĩa có kết quả có cấu trúc. Phát biểu không qua thì bỏ phát biểu đó; không còn phát biểu nào thì từ chối.
6. **Kết quả có kiểu.** Trả lời đầy đủ, trả lời một phần có ghi chú, hỏi lại có gợi ý, từ chối kèm lý do, lỗi tạm thời kèm cách thử lại. Mỗi loại có thông báo riêng, không còn "dịch vụ chưa hoàn tất" chung chung.
7. **Quan sát được.** Mỗi lượt ghi: số ứng viên, điểm, lý do loại từng phát biểu, kiểu kết quả, độ trễ từng tầng (không ghi nội dung câu hỏi hay dữ liệu cá nhân).

## Tiêu chí nghiệm thu (đề xuất, chốt ở M0)
Đo trên bộ giữ kín, mỗi ca chạy 3 lần:
- Câu sai trên câu có đáp án (đã trả lời nhưng sai hoặc thiếu điều kiện quan trọng): ≤ 2%. Phát biểu không có nguồn: 0 trong mẫu rà.
- Từ chối đúng trên câu ngoài phạm vi và câu mơ hồ: ≥ 98%.
- Trả lời hoặc trả lời một phần trên câu có đáp án: ≥ 92% (chuẩn form và không dấu), ≥ 85% (từ khóa), ≥ 75% (lóng).
- Dẫn đúng mục nguồn: ≥ 95%.
- Độ nhất quán giữa 3 lần chạy: ≥ 95% ca cho cùng loại kết quả.
- Lỗi/hết thời gian không xử lý được: < 1%.
- Độ trễ: trung vị ≤ 6 giây, p95 ≤ 12 giây, byte đầu tiên phát ra ≤ 2 giây.
- An toàn: bộ safety/injection/nhiều lượt/routing theo định mức, không có rò dữ liệu.

## Cách làm để không phải sửa đi sửa lại
1. **Đặc tả và bộ đo trước, mã sau.** Bộ ca lớn có đáp án chuẩn kèm đoạn nguồn kiểm tự động, chia phát triển 70%, giữ kín 30% (không ai xem khi sửa).
2. **Lát cắt dọc theo họ chủ đề** (quy chế đào tạo → sổ tay → học phí/thông báo → chương trình đào tạo). Mỗi lát chỉ được coi là xong khi qua tiêu chí nghiệm thu của riêng nó; không chuyển sang lát sau khi lát trước chưa xanh.
3. **Ngân sách lỗi.** Mỗi vòng sửa phải nêu nguyên nhân gốc trong phân loại lỗi cố định (kho thiếu, nạp sai, truy xuất, sinh, kiểm chứng, từ chối nhầm, hạ tầng); lỗi cùng loại xuất hiện lần hai thì phải sửa ở tầng thiết kế, không vá ca riêng.
4. **Chống hồi quy tự động.** Mọi thay đổi chạy lại bộ phát triển trong CI cục bộ; bộ giữ kín chỉ chạy ở mốc.
5. **Kiểm chéo ba họ mô hình.** DeepSeek sinh trong hệ thống, `gpt-6.1-sol` (Codex, mức `high`) viết mã, bộ ca và đáp án chuẩn, Claude đặc tả, kiểm và chấm. Người viết mã và người kiểm là hai họ mô hình khác nhau.

## Phân công để tiết kiệm hạn mức Claude
Codex (`codex exec -m gpt-6.1-sol -c model_reasoning_effort="high" -s workspace-write`) làm phần lớn công việc nặng; Claude chỉ làm những việc cần phán đoán hoặc quyền mà Codex không nên có.

| Việc | Codex | Claude |
|---|---|---|
| Xuất kho, sinh 600–800 câu hỏi, đáp án chuẩn và đoạn nguồn | làm toàn bộ | viết đặc tả ngắn, rà 15% mẫu |
| Bộ phân tích Điều/khoản, bảng, sổ tay; dữ kiện có kiểu; chỉ mục v2 | viết mã và test | đọc diff tóm tắt, chạy test |
| Hiểu câu hỏi, truy xuất, rerank dự phòng, sinh ràng buộc, kiểm chứng | viết mã và test | đặc tả giao diện, duyệt thiết kế |
| Đo trên runtime, phân loại lỗi, báo cáo số liệu | chạy bộ chạy có sẵn, viết bản tóm tắt | đọc bản tóm tắt, kiểm số liệu gốc ngẫu nhiên |
| Rà đối kháng mã và câu trả lời | một phiên Codex riêng chỉ đọc | quyết định xử lý |
| Khởi động lại runtime, đổi ngưỡng, ghi quy tắc, mọi hành động có tác dụng ngoài kho mã | không | làm |

Cách giao việc (mỗi nhiệm vụ một phiên `codex exec`, tệp ghi rời nhau, theo thứ tự hoặc song song khi không đụng chung tệp):
- Thư mục làm việc là repo này; Codex chạy với sandbox ghi trong repo, không có quyền mạng ngoài việc gọi nhà cung cấp mô hình.
- Mỗi nhiệm vụ có bản giao việc cố định: mục tiêu, tệp được sửa, tiêu chí xong (lệnh test cụ thể), điều cấm (không commit/push, không xóa, không đụng `infra/local/**`, không in bí mật, không đổi ngưỡng gate hay đáp án chuẩn để cho qua).
- Kết quả của Codex vào tệp báo cáo ngắn; Claude chỉ đọc báo cáo và `git diff --stat`, chạy lại lệnh kiểm chứng rồi mới chấp nhận. Không đọc toàn bộ mã Codex viết nếu kiểm chứng đã xanh.
- Mọi thay đổi dùng tệp trong cây làm việc hiện tại (vì có nhiều thay đổi chưa commit), nên mỗi vòng Claude chạy `git status` trước và sau để thấy đúng những gì Codex đã đổi.
- Chi phí: hạn mức của gói ChatGPT; khi gần chạm giới hạn thì tạm dừng và báo, không chuyển sang việc khác tự ý.

## Các mốc
- **M0 (quy tắc và đặc tả):** dọn quy tắc ràng buộc không cần; chốt tiêu chí nghiệm thu, phân loại lỗi, định dạng bộ ca.
- **M1 (bộ đo):** xuất kho, Codex sinh 600–800 câu và đáp án chuẩn, kiểm tự động đoạn trích, mình rà 15% để đo nhãn sai; chia phát triển/giữ kín; chạy v1 làm đường cơ sở 3 lần.
- **M2 (nạp có cấu trúc):** bộ phân tích Điều/khoản, bảng, sổ tay; dữ kiện có kiểu; kiểm tra tự động; chỉ mục v2.
- **M3 (hiểu câu hỏi và truy xuất):** chuẩn hóa, thông tin bắt buộc, truy xuất rộng, rerank nhanh, xếp hạng dự phòng.
- **M4 (sinh và kiểm chứng):** sinh ràng buộc theo ID nguồn, kiểm xác định, kiểm chứng có cấu trúc, kết quả có kiểu.
- **M5 (ổn định):** chịu lỗi, streaming, kiểm tải, ngân sách mô hình, giám sát.
- **M6 (an toàn):** bộ safety/injection/nhiều lượt/routing và red-team.
- **M7 (so sánh và chuyển):** v1 so với v2 trên bộ giữ kín; chuyển cờ khi v2 đạt toàn bộ tiêu chí.
- **M8 (chốt):** báo cáo cuối kèm giới hạn còn lại, runbook vận hành.

## Rủi ro
- Bộ ca và đáp án chuẩn do mô hình viết nên có thể bỏ sót cách hỏi bất ngờ của người thật; giảm bằng ba họ mô hình, bộ giữ kín và đo nhãn sai.
- Codex gửi nội dung trong prompt tới nhà cung cấp ngoài: chỉ đưa văn bản kho đã duyệt, không dữ liệu cá nhân hay bí mật; dùng hạn mức tài khoản ChatGPT của bạn.
- Xây lại lõi tốn công hơn vá: đổi lại mỗi lát cắt có tiêu chí dừng rõ.
- Phần cứng (CPU) giới hạn rerank: M3 cần thử lượng tử hóa trước; nếu chưa đủ, cần quyết định về GPU hoặc mô hình rerank nhẹ hơn.
- Các ranh giới giữ nguyên: xác thực và phân quyền, egress và quyền riêng tư, không in bí mật, không xóa dữ liệu hay backup, không commit/push khi chưa được bảo.
