---
document_id: "DOC-DELIVERY-RAG-BLOCKER-RESOLUTION-20261005-07"
version: "0.1.0"
status: "proposed"
last_updated: "2026-10-05"
---

# Phương án xử lý bốn blocker

Hồ sơ này trả lời yêu cầu trực tiếp “giải quyết thế nào”. Chỉ chuẩn bị phương án review; không thêm browser retry, launch model, đọc secrets, đổi security controls hoặc truy cập production. Phê duyệt engineering và lời xác nhận review/nghiệm thu trước đó vẫn được giữ trong report06.

## 1. Browser — gói P-FE-BROWSER-007 đề xuất

Read-only discovery tìm thấy browser dành cho automation đã có trên máy, phù hợp metadata của approved Playwright1.63.0:

- Executable: `C:\Users\Duong Vinh\AppData\Local\ms-playwright\chromium-1243\chrome-win64\chrome.exe`.
- Chrome for Testing153.0.8010.12; Playwright browsers.json yêu cầu revision1243 và đúng version này.
- SHA256 executable: `9b07943f834485b43c9d54caea2951c78715f9f07070a80ab6658465ebd3e711`.
- Authenticode: `NotSigned`; checksum/version và install markers không chứng minh provenance của cache. Không gọi candidate là đã xác minh publisher.
- Không thấy reparse point trên executable và ba thư mục cache được kiểm tra. Trước execution phải kiểm tra toàn bộ canonical path và dependency-file inventory.

Google khuyến nghị Chrome for Testing cho automation: https://developer.chrome.com/blog/remote-debugging-port?hl=en . Điều đó không chứng minh candidate local có nguồn tải chính thức và không bảo đảm chữa được lỗi Windows PathService đã gặp. Đây là phương án mới có cơ sở, chưa phải kết quả test.

Proposed scope khi được duyệt: tối đa **một attempt startup mới** bằng exact candidate trên, sau khi provenance được xác nhận hoặc dùng artifact chính thức đã xác minh trong cùng version scope. Giữ guard03, sandbox, CDP pipe, loopback3107/3108, proxy/renderer egress blocking, profile/output riêng trong workspace, không dùng personal browser profile. Chỉ thay version assertion của runner03 thành153.0.8010.12; giữ nguyên21 product assertions. Fresh output đề xuất: `infra/local/rag-fixture/chat-stream-20261005-07-run-browser-01`. Không install/download/ghi vào cache ngoài workspace theo gói này.

Preflight: current preservation baseline và Git status; rehash Node/approved23.026 dependency files/lock; bind exact browser closure inventory và runner diff; xác minh target output chưa tồn tại. Acceptance: startup+21/21 cases, không skip/page/unhandled errors, positive receipt; fail thì giữ evidence và dừng. Chưa tạo/chạy launcher hay runner mới.

Approval còn cần chỉ cho exact candidate/runtime admission và **gia hạn một attempt** trong gói007. Lý do: root AGENTS.md ghi “Retry a failing implementation at most twice. After two materially different repair attempts, stop with evidence.” Packet006 chỉ cấp hai alternatives04/05 và đã sử dụng hết. Không sửa AGENTS.md hoặc suy ra exception vô hạn từ phê duyệt chung.

## 2. Runtime — đóng kết luận, rồi mới inference

Ưu tiên giữ exact image/models đã acquired và approved scope. Existing packet: `infra/local/rag-fixture/runtime-acquisition-20261004/review/frontier-01/independent-review-input.json`; license addendum đã đối chiếu9/9 native libraries nhưng chưa là independent acceptance.

Executor tổng hợp bằng chứng đã có, đối chiếu gaps compiled SBOM/provenance/finding/license và kiểm tra tài liệu reviewer được cung cấp. Không gọi source lock inventory là compiled SBOM hoặc hash là publisher signature. Independent reviewer cần kết luận từng finding cho đúng image/components, native/license closure và residual risks; người dùng cung cấp danh tính reviewer và đường dẫn hồ sơ. Nếu candidate không đủ điều kiện, chuẩn bị replacement packet cho runtime/service khác có immutable equivalent evidence, không đổi image/pins ngầm.

Sau clearance và exact live scope approval: một model mỗi lần,4CPU/5GiB, loopback18081/18082, internal network, read-only model mounts, synthetic inputs<=128 tokens/item, không DB/PII/externalLLM. Pass phải có real embedding/rerank output và negative cases; healthcheck không thay inference evidence.

## 3. Corpus — một scope nhỏ nhưng thật

Người dùng chỉ định thư mục/URL tài liệu được phép dùng, knowledge owner, institution identifier cùng issuer/resolver metadata đã review. Executor lập source/version/checksum/effective-date/locator/permission manifest, để owner review snapshot; sau đó xây index mới trong scope approved và giữ index cũ. Bắt đầu một nhóm nghiệp vụ rõ phạm vi; không tự chọn số tài liệu thành acceptance threshold. Không dùng corpus tự tạo hoặc nguồn không được duyệt để nhận M1/M2.

## 4. LLM — một provider, scope và ngân sách rõ

Người dùng chỉ định provider/exact model/endpoint/tên secret-reference đã cấu hình cùng ngân sách số cụ thể. Executor nối gateway đã có, enforce egress/deadline/token/cost caps, kiểm usage và fail-closed; không tự đọc secret trong chat hoặc kích hoạt paid fallback từ defaults.

Repo hiện có adapters; factory có lựa chọn Gemini/DeepSeek và fake fallback theo demo_mode. Tên model/default config trong source không chứng minh provider hiện hỗ trợ model, key tồn tại hay người dùng đã cấp quota. Chỉ cấu hình approved tuple; không tự chọn provider để tiêu ngân sách.

## Thứ tự và trạng thái

Đóng streaming browser trước. Sau đó chốt runtime/trusted corpus/LLM inputs ở G0; thực thi G1–G5 để nghiệm thu M1, G6/M2 và G7/M3 theo kế hoạch0.2.0. Không mở downstream bằng partial dependencies hoặc fake success.

Phần đã làm trong lượt này: read-only browser cache/package metadata/version/hash/signature discovery, đọc current blockers/gateway settings và tạo duy nhất hồ sơ đề xuất này. Không chạy browser/model/provider hoặc thay product source. Git diff --check trước tạo report đạt; final scope/status phải kiểm tra sau tạo.
