# W8 — test web đỏ (L-17), tương phản chế độ tối (L-16), danh sách nháp (L-21)

Đọc `W0-common.md`. Mã phiên W8. Phiên W7 đã sửa xong khu vực chat (`app/chat/page.tsx`, `AppShell.tsx`, `features/chat/*`): không sửa lại mã các tệp đó; được sửa test của chúng nếu test lệch thiết kế mới.

Sở hữu: `apps/web/vitest.config.ts` và một tệp setup mới (ví dụ `apps/web/src/test/setup.ts`), mọi tệp `*.test.ts(x)` trong `apps/web/src`, `apps/web/src/features/documents/OperationalServiceWorkspace.tsx`, `apps/web/src/styles/tokens.css` (chỉ màu nút/tương phản), `apps/web/src/app/globals.css` nếu cần cho cùng mục đích.

## Việc
1. **L-17: 58 test vitest đỏ** (danh sách và thông điệp: `evals/results/audit-opus-20261101/vitest-failures.json`; phân nhóm trong `REPORT.md` mục L-17).
   - (a) 24 ca đỏ vì jsdom thiếu `ResizeObserver` (kéo vào qua `components/shared/PanelResizeHandle.tsx`): thêm polyfill tối thiểu trong setup của vitest, không đổi component.
   - (b) Khoảng 33 ca lệch thiết kế/nội dung. Với từng tệp, đọc component hiện tại để xác định test cũ hay mã sai:
     - nếu là thiết kế mới có chủ ý (văn bản, vai trò, luồng đã đổi), cập nhật test theo hành vi hiện tại nhưng giữ ý nghĩa kiểm: không bịa, không báo đã gửi khi chỉ là nháp, xác nhận trước khi ghi, không lộ dữ liệu;
     - nếu là lỗi thật của component, không sửa component (trừ `OperationalServiceWorkspace.tsx`), ghi vào báo cáo kèm bằng chứng.
     - Không xóa test và không `skip`; nếu buộc phải bỏ một khẳng định, ghi lý do.
   - (c) `app/chat/page.history.test.tsx` và `page.resume.test.tsx` (chập chờn khi chạy song song): tìm nguyên nhân phụ thuộc thời gian và làm test ổn định.
2. **L-16 tương phản.** Ở chế độ tối, nút "Chuẩn bị thủ tục mới" (trang Hồ sơ của tôi, `OperationalServiceWorkspace.tsx`) có chữ trắng trên nền `rgb(158,216,207)`, tỉ lệ 1,59:1. Sửa đạt ≥ 4,5:1 ở cả sáng và tối, qua token màu dùng chung nếu nút dùng token. Thêm test tương phản nếu `tokens.test.ts` có cơ chế phù hợp.
3. **L-21 danh sách nháp.** Ở "Nháp đã lưu của tôi", các mục cùng tên "Hỗ trợ thủ tục học vụ" không phân biệt được, và bấm vào thì nội dung mở bên dưới, ngoài khung nhìn.
   - Mỗi mục hiển thị một dòng trích ngắn của nội dung (≤ 80 ký tự, lấy từ `form.reason`/`purpose`).
   - Khi mở một nháp, cuộn và đặt focus vào biểu mẫu.
   - Có test.
4. **Hoàn tất L-10 (token chỉ còn trong cookie HttpOnly).** Máy chủ (W6) đã bỏ `token` khỏi JSON của `POST /v1/knowledge/platform/session`; W7 đã chuyển khu vực chat sang chỉ dùng cookie. Các tệp sau còn đọc/ghi `campus247_token` hoặc gửi `Authorization: Bearer` từ `localStorage` — chuyển sang `credentials: "include"`, không đọc/ghi token: `features/knowledge/OwnerLogin.tsx` (đang `localStorage.setItem("campus247_token", result.token)` → sẽ ghi `undefined`; ưu tiên số 1, và hỗ trợ `?redirect=` nội bộ an toàn — chỉ đường dẫn tương đối bắt đầu bằng `/`, không `//`), `lib/api/client.ts`, `lib/unified-assistant-runtime.tsx`, `lib/data/api/certificate-gateway.ts`, `lib/data/api/service-gateway.ts`, `features/knowledge/KnowledgeIntake.tsx`, `KnowledgePlatform.tsx`, `RenditionCorrection.tsx`, `features/assistance/BaselineRecorder.tsx`, `WorkflowDefinitionPanel.tsx`. (Các tệp này thêm vào danh sách sở hữu của W8.) Giữ mọi kiểm quyền/xác nhận khác. Test: đăng nhập đặt cookie và điều hướng, không ghi localStorage; redirect ngoài miền bị bỏ qua.
5. **Kiểm:** chạy toàn bộ `npx.cmd --no-install vitest run` (từ `apps/web`) trước và sau, cùng `npx.cmd --no-install tsc --noEmit --incremental false`. Mục tiêu: 0 test đỏ, hoặc danh sách ca còn đỏ, mỗi ca có nguyên nhân là lỗi thật đã ghi.
