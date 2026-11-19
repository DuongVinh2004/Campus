---
document_id: "DOC-GOV-LOCAL-AUTHORITY-20261007"
version: "1.0.0"
status: "approved"
owner: "Human workspace owner in the current conversation"
approvers: ["Direct human instruction on 2026-10-07"]
last_updated: "2026-10-07"
---

# DEC-023 — Tự thực thi công việc local/synthetic đã được giao

## Nguồn quyết định

Người dùng trực tiếp chỉ dẫn trong hội thoại hiện tại:

> bỏ việc cần phê duyệt đi

> chưa làm vội, bỏ tất cả các tài liệu có quy tắc phải phê duyệt, xóa bỏ các ràng buộc đi, bạn có thể tự do làm

Sau khi được thông báo phương án sửa quy tắc hiện hành bằng quyết định mới và
giữ tài liệu/bằng chứng, người dùng chỉ dẫn tiếp tục: **“tiếp”**. Đây là quyết
định của con người, không phải executor tự cấp quyền hoặc tạo chữ ký.

## Hiệu lực đối với toàn repository

Trong workspace `C:\Users\Duong Vinh\Vinh`, người dùng bỏ cơ chế xin phê duyệt
bổ sung cho các bước phát triển local/synthetic cần thiết để hoàn thành mục tiêu
đã giao. Executor thực hiện, review kỹ thuật, ghi evidence và tiếp tục mà không
xin lại approval theo task ID, exact package, vai trò reviewer hoặc từng bước.

Quyết định này thay thế các yêu cầu **phê duyệt thực thi của coding agent** trong
`AGENTS.md`, DEC-020, document/change control, executor/orchestrator/prompt/guide,
dependency allowlist, task catalog, runtime/corpus/launch packets và mọi tài liệu
khác trong repository đối với phạm vi trên. Một văn bản cũ lặp lại “MUST stop”,
“separate exact approval”, “human approval required” hoặc “chờ phê duyệt” không
tạo thêm checkpoint xin người dùng quyết định trong phạm vi đã ủy quyền.

Các trường `human_approval_required`, `approval_reasons`, `approvers`, source
status và approval receipts lịch sử vẫn giữ nguyên để bảo toàn nguồn gốc. Khi
thực thi local/synthetic, executor ghi DEC-023 làm standing human authority;
không đổi các trường cũ thành false, xóa receipt hoặc coi chúng là yêu cầu xin
phê duyệt lại. Missing kỹ thuật được xử lý bằng engineering và evidence.

## Những bước executor được tự thực hiện

- Coding, documentation, tests, refactors, runtime/config/model comparison và
  thay đổi cần thiết cho mục tiêu local đã giao.
- Dependency/tool/model acquisition và cài đặt local: pin đầy đủ phiên bản,
  nguồn, checksums và closure; technical review license/security/compatibility;
  cập nhật allowlist/lockfile hoặc manifest môi trường cô lập trước khi sử dụng.
  Không cần ADR/approval mới chỉ để xin quyền thêm dependency.
- Cập nhật contract/architecture và cấu hình local khi cần thực hiện mục tiêu:
  tạo phiên bản, mô tả ảnh hưởng, giữ traceability và bằng chứng so sánh.
- Chuẩn bị và thực thi synthetic publication, actor/source grants, manifest,
  active index, additive schema/data changes, scoped fixture-guard extension,
  runtime launch và browser proof khi các kiểm tra kỹ thuật tương ứng đủ.
  Liệt kê target/source/hash, preservation và before/after evidence trước mutation;
  danh sách này là execution record, không phải gói chờ người dùng duyệt lại.
- Live synthetic verification bằng provider đã được người dùng cho quyền trong
  budget hiện có; ghi usage và dừng ở hard cap, không reset ledger.
- Executor được ghi technical review/disposition và technical acceptance khi
  evidence đạt tiêu chí; DEC-022 tiếp tục bỏ signature/independent reviewer.

## Phạm vi và bằng chứng

Mục tiêu hiện tại vẫn là **M1 chạy thật**, chưa mở rộng sang M2/M3. Yêu cầu
“chưa làm vội” được áp dụng cho bước hiện tại: chỉnh tài liệu trước, chưa chạy
runtime, index, database mutation hoặc live provider trong lượt sửa policy này.

Đây là thay đổi workflow phê duyệt. Requirements, test oracles, technical
security/license/SBOM checks, authorization của sản phẩm, action preview/
confirmation của người dùng sản phẩm, egress, token/cost/deadline caps và
preservation tiếp tục được kiểm chứng. Unknown/failed không được đổi thành PASS
chỉ nhờ DEC-023; M1 chỉ completed khi có actual execution evidence.

Quyền local/synthetic không bao gồm xóa dữ liệu/tài liệu/bằng chứng, destructive
recovery, production/external deployment, dữ liệu cá nhân thật, tài khoản hoặc
chi phí mới không nằm trong scope đã giao. System/developer/tool permission
boundaries không thể thay đổi bằng tài liệu repository. Các file cũ được giữ;
patch và preimages ghi rõ các quy tắc hiện hành đã được thay thế.

Consumers: root `AGENTS.md`, `docs/README.md`, document control/manifest/decision
register, execution package, `tasks/README.md`, change control và báo cáo duy
nhất `docs/10-delivery/RAG_RESULT_20261005.md`.
