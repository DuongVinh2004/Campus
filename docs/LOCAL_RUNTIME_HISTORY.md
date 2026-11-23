> **Archived operating notes.** This file used to be the repository README. It records how the local runtime was run and what state it was in on 24-27 Oct 2026; paths and ports below describe that history. For the current overview see the [project README](../README.md); for current commands see `.claude/skills/campus247/references/verification.md`.

# Campus 24/7

## Một bản chính để sử dụng — 27/10/2026

Mở **[Campus 24/7](http://127.0.0.1:8015/services)**. Chat có nguồn, dịch vụ học vụ,
hồ sơ của tôi, lịch học, phòng học và quyền riêng tư dùng chung menu và đăng nhập.
Quản trị nguồn xuất hiện theo quyền. `pnpm start` và
`.venv/Scripts/python.exe -B scripts/campus.py start` đều mở cùng runtime8015;
`scripts/campus.py status` kiểm trạng thái thật. Frontend3015 là thành phần nội bộ.
Các API kiểm thử8017/8018 và frontend3018 đã dừng sau kiểm tra idle, dữ liệu còn nguyên.

Tài khoản sinh viên local là `student-local`; mật khẩu ở
tệp credentials cục bộ trong workspace (không nằm trong git).
Không thay tài khoản admin, khóa, mật khẩu hoặc lịch sử cũ. Dịch vụ hỗ trợ chuẩn bị,
xem trước và lưu nháp có biên nhận trong cùng actor store, đọc lại tại Hồ sơ của tôi.
Chưa có kết nối tiếp nhận HUCE, xác thực tình trạng sinh viên, bảng điểm, lịch cá nhân
hoặc đặt phòng thật; nháp không phải hồ sơ đã gửi/cấp giấy. Không dùng fixture thay dữ liệu trường.

`pnpm build` chỉ tạo artifact frontend để kiểm tra, không khởi động một sản phẩm khác
hoặc tự chuyển dữ liệu. Build cũ, backup và evidence được giữ để phục hồi.
Phần dưới là lịch sử triển khai, không phải các địa chỉ cần chạy song song.

## Tham khảo kho tri thức — 24/10/2026

Mở [chatbot](http://127.0.0.1:8015/chat) hoặc
[đăng nhập quản trị nguồn](http://127.0.0.1:8015/login). Runtime này dùng
PostgreSQL và release 114 tài liệu HUCE, thêm 3 nguồn trùng/liên kết được đối soát;
93 nguồn có giới hạn phần chữ/bảng/sơ đồ, trong đó 12 nguồn chưa rõ khóa áp dụng.
122 phiên bản chưa duyệt được giữ lại: 119 bản lịch sử và 3 bản nguồn trùng/liên kết,
không phải 122 tài liệu mới đang đợi xử lý. Chưa kết nối SSO hoặc
hồ sơ học vụ cá nhân. Đây là entry của kho tri thức, khác runtime tổng hợp
ở cổng 3115 bên dưới.

Khởi động lại các thành phần đã lưu từ thư mục repository:

```powershell
& 'infra/local/rag-fixture/.venv/Scripts/python.exe' -B scripts/knowledge_platform_runtime.py start
& 'infra/local/rag-fixture/.venv/Scripts/python.exe' -B scripts/knowledge_platform_runtime.py status
```

Lệnh `start` dùng cluster và bản build v14 hiện có, kiểm danh tính database,
model và release, tái sử dụng tiến trình đang chạy và giữ log riêng từng lần.
Hai dịch vụ BGE ở 18081/18082 phải sẵn sàng với đúng revision đã lưu.
Lệnh không khởi tạo lại database, không thay model hoặc sửa chính sách Windows.
Kết quả kiểm chứng và giới hạn tại
[báo cáo khôi phục runtime](HUCE_RUNTIME_RECOVERY_20261024.md) và
[kế hoạch hoàn thiện kho](HUCE_CORPUS_COMPLETION_PLAN_20261024.md),
[kết quả xử lý](HUCE_CORPUS_COMPLETION_RESULT_20261024.md) và
[bảng trạng thái đủ 117 nguồn](HUCE_SOURCE_STATUS_20261024.md).

## Tham khảo bản tổng hợp trước khi hợp nhất về8015

Từ thư mục repository trên Windows, chạy `pnpm start` hoặc
`.venv/Scripts/python.exe -B scripts/campus.py start` rồi mở
http://127.0.0.1:3115. Trang web, API `/v1/*`, tệp tải xuống và streaming đều
đi qua địa chỉ này. Backend chỉ lắng nghe loopback `127.0.0.1:8006`; trình duyệt
không gọi trực tiếp backend và không cần CORS giữa hai cổng.

Lệnh khởi động tự build khi mã thay đổi, kiểm tra backend trước khi mở frontend,
không tự đổi cổng hoặc tắt tiến trình đang chiếm cổng. Ctrl+C dừng đúng hai tiến
trình con. Các bản build và log được giữ lại, không tự dọn dữ liệu. `pnpm build`
chỉ tạo bản build mới. Các lệnh `apps/web` riêng là công cụ frontend, không phải
lệnh chạy toàn ứng dụng.

Runtime dùng các bản sao SQLite nhất quán trong
`.tooling/campus-single-entry-20261015-01/runtime`; nguồn cũ được giữ nguyên.
`/health/entry` báo trạng thái tích hợp. `CAMPUS_MODEL_MODE=guarded`
không gọi model trả phí. Chế độ `retained` nối gateway DeepSeek hiện có, BGE
embedding/reranker trên loopback và ledger ngân sách tích lũy; chỉ khởi động khi
các dịch vụ model và headroom hiện có đáp ứng. Không tạo model giả hoặc quota mới.
Theo yêu cầu trực tiếp ngày 20/10/2026, trần tổng số lượt gọi và trần tổng chi phí
đã được bỏ. Bản ghi `resource-authorization-06-accounting-only.json` giữ snapshot
và liên kết lịch sử; số lượt, chi phí và các lượt chưa quyết toán vẫn được ghi nhận.
Khi bản ghi này hiện diện, backend mặc định dùng `retained`; vẫn có thể chọn
`guarded` rõ ràng. Giới hạn mỗi lượt xử lý, tài nguyên local, timeout, egress,
xác thực và phân quyền giữ nguyên. Health báo `budget: accounting_only`.
`CAMPUS_RUNTIME_DIR` có thể chỉ đến một runtime đã khởi tạo trong workspace để
kiểm thử trên bản sao độc lập. Không trỏ tới dữ liệu gốc hoặc một thư mục bất kỳ.

Kiểm thử trình duyệt thật dùng `apps/web/playwright.live.config.ts` và
`scripts/verify_campus_e2e.py NN --exclude-model`; mỗi lần cần số `NN` mới để giữ
nguyên bằng chứng cũ. Ca `--grep @model` gọi dịch vụ trả phí và phải nằm trong
phạm vi dữ liệu/ngân sách đã được người dùng cho phép. Trong chiến dịch E2E,
`CAMPUS_E2E_PAID_CALL_CEILING` chỉ thắt thêm trần calls tích lũy, không tăng quota.
Lịch học cá nhân, đặt phòng và dashboard quản trị vẫn cần tích hợp riêng; kiểm
thử hồ sơ tổng hợp không xác nhận dữ liệu hoặc quy trình chính thức của trường.

## Kế hoạch đồ án hiện tại

Định hướng triển khai hiện tại là [kế hoạch đồ án tốt nghiệp](GRADUATION_PROJECT_PLAN_20261013.md): một người, sáu tháng, tập trung vào RAG thích ứng, truy hồi trên đồ thị và hệ thống đa tác tử có kiểm chứng bằng chứng.

Sáu kế hoạch triển khai cũ đã được chuyển nguyên vẹn vào khu lưu trữ và bảng phục hồi (`archive/legacy-plans-20261013/`, chỉ có ở máy cục bộ, không nằm trong git) theo xác nhận trực tiếp của người dùng ngày 13/10/2026. Phần mô tả và quy trình cũ bên dưới được giữ làm tài liệu tham khảo lịch sử; yêu cầu trực tiếp hiện tại và hướng dẫn thực thi trong `AGENTS.md` xác định công việc triển khai.

Việc đổi kế hoạch giữ nguyên dữ liệu, bằng chứng, cơ chế bảo vệ, xác thực, phân quyền, xác nhận thao tác và các ranh giới môi trường/ngân sách. Mã nguồn và các thay đổi có sẵn được tiếp tục tận dụng.

## Tham khảo lịch sử

Campus 24/7 is a documentation-first commercial product for a single university. The initial reference deployment is an unofficial, simulated pilot for the Faculty of Information Technology at Hanoi University of Civil Engineering (HUCE).

This repository is a documentation package with machine-readable contracts, evaluation fixtures, infrastructure specifications and a draft delivery catalog. Its status is mixed: governance and selected product documents are approved, many design/contract/quality documents are reviewed, and service, UX, architecture, security and platform documents remain draft. It intentionally contains no production application code yet, and this package does not approve implementation, a real-data pilot, or production.

## Read first

1. `docs/00-governance/DOCUMENT_CONTROL.md`
2. `docs/00-governance/DECISION_REGISTER.md`
3. `docs/00-governance/DOCUMENT_MANIFEST.yaml`
4. `docs/00-governance/MASTER_TRACEABILITY_MATRIX.md`
5. `docs/00-governance/CONSISTENCY_REPORT.md`
6. `docs/README.md`
7. `tasks/README.md` before working on a task

## Important status

- Product intent: commercial, production-grade design.
- Initial institution: one university only; no SaaS or multi-tenant scope in V1.
- Data: public-source references plus deterministic synthetic data; no real student data.
- Coding executor: Gemini 3.8 Flash, operating only through reviewed atomic tasks.
- Production LLM provider: DeepSeek behind a provider-neutral gateway.
- Hosting preference: AWS.
- This is not an official HUCE service and must not be presented as one.
- The repository is synthetic-only. Do not use real student/staff data, university credentials, live institutional integrations, or paid provider calls without the separate approvals required by governance.

## Local validation

Run only offline, synthetic-safe checks from the repository root:

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
python tasks/tools/validate_catalog.py
python contracts/tools/validate_openapi.py
python evals/validate_contracts.py
```

Validation output is structural evidence only; it is not implementation, release, real-data, pilot, or production approval. Do not automatically commit, push, deploy, or change task/document approval states.
