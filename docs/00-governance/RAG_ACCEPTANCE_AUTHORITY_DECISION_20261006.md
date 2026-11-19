---
document_id: "DOC-GOV-RAG-AUTHORITY-20261006"
version: "1.0.0"
status: "approved"
owner: "Human project owner in the current conversation"
approvers: ["Direct human decision in the implementation chat on 2026-10-06"]
last_updated: "2026-10-06"
---

# Quyết định trách nhiệm và phương thức nghiệm thu M1–M3

Quyết định này ghi nhận chỉ dẫn trực tiếp của người dùng ngày 2026-10-06:

> phần chữ ký và review độc lập thì bỏ đi, tôi là người chịu trách nhiệm chính, tôi ủy quyền cho bạn làm

Trước đó, người dùng xác nhận đã review toàn bộ và ủy quyền xử lý các phần còn lại;
đồng thời chỉ dẫn:

> cái nào tốt hơn thì giữ cái đó, ko cần cứng nhắc theo cấu hình ban đầu

Đây là nguồn phê duyệt của con người, không phải chữ ký được tạo bởi executor.
Vai trò chịu trách nhiệm được xác nhận trong hội thoại; không suy diễn pháp danh,
chức danh bên ngoài hoặc đại diện pháp lý cho tổ chức.

## Điều kiện nghiệm thu đang áp dụng

Trong phạm vi triển khai và nghiệm thu M1–M3 Campus 24/7 bằng dữ liệu mô phỏng tại
workspace `C:\Users\Duong Vinh\Vinh`:

- Bỏ yêu cầu chữ ký artifact/publisher, chữ ký review và chữ ký hồ sơ nghiệm thu.
  Giữ kiểm tra checksum, exact artifact/source/version binding và provenance
  thực tế; provenance chưa ký được mô tả đúng trạng thái.
- Bỏ yêu cầu reviewer độc lập và separation-of-duties cho review runtime/corpus/
  hồ sơ nghiệm thu của phạm vi này. Người dùng chịu trách nhiệm chính; executor
  được ủy quyền thực hiện technical review, dispositions có bằng chứng và các
  bước engineering còn lại. Xác nhận review qua hội thoại là nguồn phê duyệt.
- Được đánh giá và thay cấu hình/model/runtime bằng phương án tốt hơn. Ghi phiên
  bản mới và so sánh trên cùng dữ liệu/tiêu chí trước khi chọn; không giữ model,
  số chiều hoặc tham số chỉ vì cấu hình ban đầu. Phiên bản cũ và kết quả cũ vẫn
  là snapshot lịch sử, không bị viết lại.

Quyết định này thay điều kiện **signature/independent reviewer** trong
`SEC-CTRL-012`, `SEC-CTRL-019`, `SEC-CTRL-029` và các SDLC/vendor/launch/release
checklists dẫn chiếu hai điều kiện đó, chỉ cho scope nêu trên. Không sửa AGENTS,
permission/backup controls hoặc security baseline của các scope khác.

## Bằng chứng và các kiểm tra tiếp tục thực hiện

Không chuyển technical unknown thành passed. SBOM/build-feature coverage, malware/
PII/injection scans, license obligations, finding applicability/remediation,
trusted actor/source scopes, actual M1 path, M2 quality và M3 operational
measurements tiếp tục được kiểm chứng. Việc bỏ chữ ký không thay signing key của
identity/session/action-confirmation hay bỏ authorization, egress, data-protection,
deadline/token/cost caps.

Các quyền production access/deployment, destructive actions, dependency installation
và external messaging vẫn theo chỉ dẫn trực tiếp tương ứng; quyết định này không
tạo các quyền đó. Corpus approval do người dùng/technical review được ghi trong
receipt mới; các quarantine snapshots, findings và failure evidence cũ giữ nguyên.

Downstream consumers: `docs/10-delivery/RAG_RESULT_20261005.md` và các receipts mới
trong `infra/local/rag-fixture/` từ quyết định này trở đi. Phiếu trước đó vẫn giữ
`not_verified` hoặc missing signatures theo policy cũ, không dùng chúng để tiếp tục
đòi hai điều kiện đã được người dùng bỏ trong scope hiện tại.
