# Chặng 6 — Service Agent, phúc khảo và vận hành tri thức

Ngày: 13/10/2026. Trạng thái: thiết kế. Ước lượng: **16–30 giờ Codex hoạt động**, trước dự phòng. [Kiến trúc chung](00_SHARED_ARCHITECTURE.md).

## 1. Mục tiêu và phạm vi

Hoàn thiện sản phẩm đã chốt: hai quy trình xin xác nhận/phúc khảo, hỗ trợ chung, không gian cán bộ và quản trị nguồn. Tái sử dụng nền hồ sơ chặng 1; Service Agent hỗ trợ thu thập dữ liệu và chuẩn bị action, còn backend thực thi và cán bộ quyết định nghiệp vụ.

Phần graph phục vụ quản trị quan hệ khi chặng 5 đủ điều kiện. Nếu graph chưa hoàn tất, triển khai quản trị tài liệu và nghiệp vụ qua nguồn/hybrid trước, giữ interface để tích hợp sau.

## 2. Service Agent và tool boundary

| Công cụ | Effect |
|---|---|
| read_own_requests | Đọc hồ sơ hiện tại theo quyền |
| read_eligible_course_records | Đọc học phần từ backend mô phỏng có nguồn dữ liệu |
| explain_procedure | Truy nguồn hướng dẫn và điều kiện |
| prepare_request_draft | Tạo/cập nhật bản nháp qua application service |
| build_action_preview | Chuẩn hóa dữ liệu, kiểm điều kiện và tạo preview |
| submit_confirmed_request | Chỉ qua confirmation executor đáng tin cậy |
| request_human_support | Tạo yêu cầu hỗ trợ có context được phép |

Phân biệt thay đổi bản nháp với gửi hồ sơ. Draft vẫn cần quyền và history phù hợp. Conversation intent không thay confirmation. Không cho LLM tạo user ID, role, approved status, signature hoặc idempotency receipt.

Agent có thể tạm dừng để hỏi trường thiếu. Resume kiểm lại quyền, tình trạng hồ sơ, payload hash, thời hạn và policy/source version liên quan. Payload quan trọng thay đổi tạo preview mới.

## 3. Nghiệp vụ phúc khảo

Luồng: chọn học phần mô phỏng → đọc hướng dẫn → chuẩn bị đề nghị → xem trước → xác nhận → cán bộ tiếp nhận → bổ sung nếu cần → trả kết quả nghiệp vụ demo.

Trường đề xuất: course record reference, học kỳ, lý do, tệp theo yêu cầu nguồn, contact preference nếu đủ điều kiện và requester lấy từ identity. Backend kiểm eligibility/deadline từ cấu hình có căn cứ; chưa xác minh phải được đánh dấu mô phỏng hoặc chờ cán bộ.

Không tự tính lại/chấm điểm bằng LLM. Kết quả điểm hoặc quyết định phúc khảo chỉ lấy từ backend/cán bộ trong demo. Không thêm thanh toán hoặc liên kết hệ thống trường thật trong chặng này.

Ưu tiên state machine hồ sơ hiện có với loại request riêng. Mọi transition có actor policy, expected version và audit. Cần giữ immutable history để truy nguyên trước/sau.

## 4. Hỗ trợ chung và cán bộ

Student hoặc AI có thể đề nghị chuyển cán bộ. Context chuyển gồm câu hỏi, thông tin được phép, evidence refs, các phần chưa giải quyết và reason; không chuyển transcript nhạy cảm vượt scope.

Queue hỗ trợ claim/assign/transfer/respond/request-information/resolve theo policy. Đồng thời hai cán bộ nhận cùng hồ sơ phải có conflict rõ. Hiển thị đã tiếp nhận chỉ khi queue record tồn tại; không bịa thời gian phản hồi hoặc nhân sự trực.

## 5. Quản trị tri thức

Luồng: upload/reference → immutable source snapshot → parse/OCR → inspection → draft version → review → build index/graph candidate → publish active version.

- Giữ original bytes, hash và locator. Sửa OCR tạo rendition/version mới cùng mapping, không ghi đè nguồn.
- Candidate contextual text, FAQ và graph edges tách khỏi source evidence.
- Metadata: campus, audience, effective interval, supersedes scope, publication/review state.
- Nếu hệ thống hiện có separation of duties, giữ editor/reviewer khác nhau; dùng tài khoản mô phỏng phù hợp để kiểm thử.
- Publish phải đủ metadata, review, hash và compatibility; build thất bại không đổi active pointer.
- Source withdrawn/superseded bị loại khỏi current mode và cache theo quyền; history/evidence vẫn giữ.

OCR/tables trong phạm vi chọn lọc, kiểm tra những đoạn có số/ngưỡng/ngoại lệ quan trọng. Dữ liệu chưa kiểm chứng không được trình bày như nguồn chính thức.

## 6. Dữ liệu và tài liệu kết quả

Tái sử dụng request, preview, confirmation, idempotency và audit repositories. Có adapter từ model UI cũ nếu cần; state browser không là nguồn sự thật của hồ sơ.

Đối chiếu [kiểm kê chặng 1](../CERTIFICATE_STAGE1_INVENTORY_20261013.md), transaction port và các module certificate/document-request đang được phát triển. Có thể tổng quát hóa chúng hoặc xây service phúc khảo riêng qua port phù hợp; giữ dữ liệu và khả năng đọc hồ sơ chặng 1, tránh hai repository khác nhau tự tạo hai nguồn sự thật cho cùng request.

File đính kèm có type/size/path constraints, storage location và access policy. Không để agent tự chọn đường dẫn filesystem từ input. Tài liệu demo được render từ template có version, gắn request và checksum; tải lại kiểm ownership. Có nhãn mô phỏng và không giả chữ ký/số hiệu chính thức.

Transaction quản lý việc tạo request và idempotency outcome. Với hiệu ứng notification/file generation ngoài transaction, dùng outbox hoặc cơ chế retry/reconcile phù hợp; trạng thái uncertain không trở thành success vì retry hết hạn.

## 7. Giao diện

Sinh viên: hồ sơ theo loại, preview, trạng thái, bổ sung và tải kết quả. Cán bộ: queue, detail, căn cứ, thao tác và history. Quản trị: nguồn gốc, rendition, hiệu lực, review, lỗi build và active version; graph review khi có.

Giữ UI thống nhất và trải nghiệm mobile, keyboard, loading/error/retry. Các trạng thái dữ liệu/quyền thật được phản ánh; không dùng demo mock để che chức năng API còn thiếu.

## 8. Work packages và thời gian

| Gói | Công việc | Giờ Codex |
|---|---|---:|
| S6-01 | Service tool contracts, draft/preview/resume | 3–5 |
| S6-02 | Phúc khảo, hỗ trợ chung, persistence và state transitions | 5–9 |
| S6-03 | Source review/version/build/publish và graph hooks | 4–8 |
| S6-04 | Ba giao diện, tài liệu demo và end-to-end verification | 4–8 |

## 9. Acceptance

- Hai nghiệp vụ chạy xuyên frontend/backend/storage và sống qua restart.
- Chuẩn bị hồ sơ từ chat, user sửa, xác nhận, cán bộ xử lý và student nhận outcome đúng.
- Invalid/expired/mismatched confirmation không có effect; retries không tạo duplicate.
- Role/owner/queue/version conflict được kiểm ở application service, không chỉ ở UI.
- Hoạt động bổ sung/từ chối/transfer có history và reason, không mất nội dung cũ.
- Attachment/document download theo quyền; tài liệu demo có nhãn rõ.
- Publish/withdraw/version switch thay eligibility và cache đúng, giữ sources/evidence cũ.
- Report cả tình huống thiếu nguồn, thiếu eligibility data, model error và unknown effect.

## 10. Chuyển tiếp

Adapter/migration additive nối model nghiệp vụ cũ với model mới; không reset DB để có schema sạch. Nếu phải xây application service mới, chuyển từng loại request và giữ cách đọc lịch sử. Không thay policy backend bằng phán đoán của agent.
