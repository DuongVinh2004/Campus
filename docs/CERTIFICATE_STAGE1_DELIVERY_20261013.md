# Bàn giao chặng đầu Campus 24/7 — 13/10/2026

Đã nối luồng đăng nhập → hỏi có nguồn → chuẩn bị hồ sơ trong chat hoặc màn hình
thủ tục → preview → xác nhận → cán bộ tiếp nhận/bổ sung/duyệt/từ chối → sinh viên
theo dõi và xem kết quả. Sinh viên/cán bộ cùng đọc dữ liệu backend. Tính bền vững
được kiểm bằng restart tiến trình thật và hai lần restart API demo đang dùng.

Theo yêu cầu bổ sung trực tiếp, đã bỏ nhãn demo/mô phỏng khỏi màn hình và bản giấy
xác nhận. Điều chỉnh này là yêu cầu sản phẩm về cách trình bày; dữ liệu, environment
guard, quyền, session binding, confirmation, version CAS, cap và audit được giữ.
Các evidence/record cũ còn nguyên. Thay assertion nhãn HTML trong test phản ánh
yêu cầu mới; không đổi các kiểm tra auth/ownership/transition/retry.

## Thay đổi

- Domain DocumentRequest thêm WAITING_STUDENT, sửa draft và submit supplement.
- Application CertificateService kiểm profile, role/queue/ownership, preview
  payload/session binding, expiry, consume một lần, CAS và idempotent replay.
  Retry xác nhận ban đầu sau bổ sung vẫn trả hồ sơ cũ, không tạo trùng.
- Port transaction và SQLiteCertificateRepository lưu hồ sơ, preview, replay,
  audit và session revocation; migration CREATE TABLE/INDEX IF NOT EXISTS additive.
  PostgreSQL chưa có ownership/runtime được xác minh, nên không chạy migration
  hoặc mở thêm database đó. Đây là adapter local/demo, chưa là persistence production.
- Router/gateway mới theo hợp đồng thật. Bootstrap chính có điểm inject typed
  service để tích hợp về sau; runtime 8002 dùng cùng service/router hiện có lớp
  identity/error/rate-limit, không khởi tạo provider hoặc paid-ledger writer.
- UI `/login`, `/tickets`, `/staff`, `/chat` dùng API cho luồng này qua build flag.
  Legacy gateway và các nghiệp vụ ngoài phạm vi vẫn có UnsupportedOperationError.
  UI giữ form/preview khi lỗi, retry cùng key, không tạo state thành công thay API.
- Chat định tuyến ý định giấy xác nhận bằng code xác định, hỏi mục đích/nơi nộp
  và mở form có thể sửa. Việc gửi đi qua application service sau explicit confirm.
  Chưa có tác tử tự trích toàn bộ trường trong hội thoại, GraphRAG hoặc multi-agent đầy đủ.
- Nguồn hướng dẫn lấy snapshot human-reviewed trang 35/39; đã đọc ảnh gốc để
  tách quy trình giấy xác nhận và nghỉ học tạm thời. Web tool không tải được bản
  phát hành trong lượt này; không tuyên bố đã xác minh hiệu lực chính sách hiện tại.

## Kiểm chứng

| Kiểm tra | Quan sát và evidence |
|---|---|
| Backend cuối | 44 passed, 0 failed/skipped, backend-04.xml, 8.19s. Auth, ownership, queue, expiry/payload/session mismatch, replay/restart, bổ sung/từ chối, lỗi proxy, CAS đồng thời |
| Frontend | 28 passed, frontend-tests-03.json. Preview không tự gửi; lỗi 503 không hiện thành công, retry cùng body/key; chat/history/session shell regression |
| Build cuối | frontend-build-03.json, exit 0, Next 16.3.8 compile/TypeScript/static pages qua |
| Lint giới hạn | Ruff F/E9 các module backend mới qua; không tuyên bố toàn repository sạch |
| Restart tiến trình | process-restart-01.json: ba worker 8003 do runner sở hữu, cùng DB giữ pending preview/session, submit, replay và lịch sử; không reset/xóa dữ liệu |
| Browser luồng bổ sung | Hồ sơ ...c9f9e51f: submit → accept → WAITING_STUDENT → supplement → accept → READY; cán bộ mở đúng nội dung mới; tám event vẫn còn sau restart |
| Browser build03 | Login bằng mã, chat grounded; mở citation trang 39/toàn văn; form chat → preview → explicit confirm → mã ...44049501; không có nhãn demo/mô phỏng trong các màn hình này |
| Backend readback cuối | delivery-readback-01.json: hồ sơ tạo từ chat READY, 5 audit = 5 history event; 2 source hash đúng; history final grounded; readback không gọi provider |

Các lần không qua được giữ: Vitest sandbox EPERM realpath trước khi chạy lại;
một lệnh pytest trỏ nhầm `test_identity.py` không chạy test; ruff chưa có trong
fixture Python nên dùng executable đã có trong `.venv`; runner review ban đầu lỗi
KeyError đã sửa trước khi ghi report. Đây không phải test pass. Lint ban đầu có
unused import đã sửa bằng type annotation. Suite toàn repo chưa chạy lại; failure
citation simulation-label đã ghi ở báo cáo RAG trước nhiệm vụ không được sửa để
làm toàn repo xanh.

## Baseline phát triển

48 câu có group/history/source version/locator/hash/expected concepts/behavior.
Rubric và chính sách tách tập cuối ở `evals/CERTIFICATE_DEVELOPMENT_RUBRIC_20261013.md`.
Đáp án không được nhập vào FAQ/metadata/prompt tuning.

| Phép đo | Kết quả | Giới hạn |
|---|---|---|
| Retrieval thật | 48/48 đã đo, không failure/skip; nguồn cần thiết 36/40 ca có gold source; p50 2.672s, p95 3.109s | Raw standalone query, chưa rewrite history. Bốn miss: 012,020,029,039. All-required parent coverage không là Recall@10/answer correctness |
| Provenance matcher | report01 so raw OCR ghép trang với canonical hash nên metric ban đầu không hợp lệ. report02 rescore theo đúng trang 35/39 | Giữ report01; không rerun inference, không sửa source/expected answer. Corpus RAG dùng human-reviewed + source minimization khác raw corpus |
| Generation live | 4 ca có nguồn / 5 turn trả grounded; agent review correctness/completeness/support = 2/2 trong phạm vi này; 5/5 source readback hash và persisted final checks | Chỉ mẫu phát triển, không phải reviewer độc lập hoặc chất lượng phổ quát |
| Thiếu bằng chứng về phí | 1 turn safe_refusal, không bịa mức phí; thông báo “không đạt chuẩn xác thực nguồn gốc” chưa giải thích thiếu căn cứ hữu ích | Không tính là trả lời đúng; quality giải thích chỉ 1/2, completeness 0. Cần sửa wording/refusal taxonomy ở chặng sau |
| Calls/token/cost baseline live | 24 provider calls, 43,422 charged input tokens, 1,109 charged output tokens, conservative cost 0.0143574 USD; 6 turn p50 6.500s, p95 7.203s | Reservations bao gồm cả classification/routing; không phải invoice. Browser cuối là kiểm riêng, không trộn vào thống kê mẫu |

Retrieval dùng BM25+BGE-M3 → RRF → reranker → parent, index fingerprint
`903531eb92b01e4ebb71ef6413b40fcba7b626e3480ddc6e3e580cfe634249fb`, cùng model
pins/caps đã có. Native tăng 1606 → 1942 inference, 347606 → 388607 tokens trong
baseline retrieval. Paid snapshot trước/sau retrieval bằng nhau: 0 provider calls.

Lượt live đầu ước lượng tối đa 18 calls nhưng thực tế 20 vì bỏ sót hai bước
sensitive_classifier/route_intent. Cap tổng 3 USD/8500 calls không bị thay đổi.
Report cũ giữ nguyên; runner đã sửa headroom tối đa sáu calls/turn và kiểm native
cap trước turn. Ca phí được đo riêng bốn calls, nằm trong giới hạn mới sáu calls.
Không hoàn lại uncertain reservations hoặc nâng/reset budget. Snapshot cuối nằm
trong delivery-readback-01.json; ngân sách ít calls còn lại là giới hạn live checks.

## Phạm vi còn lại

Adapter SQLite này đã đạt luồng local/synthetic được giao, chưa là rollout
production. Chưa có tích hợp dữ liệu/SSO trường, biểu mẫu chi tiết được xác minh,
chữ ký số, email thật, PDF/ảnh attachment, PostgreSQL nghiệp vụ, tải đồng thời lớn
hoặc LangGraph checkpoint wired vào graph. Chưa đánh giá generation đủ 48 ca,
tập cuối độc lập hoặc production quality. Chưa triển khai phúc khảo, GraphRAG mở
rộng và multi-agent đầy đủ theo phạm vi chặng sau.

Ưu tiên tiếp: cải thiện thông báo thiếu bằng chứng; xử lý các miss retrieval và
OCR/cấu trúc bảng; tập đánh giá cuối độc lập; adapter PostgreSQL sau khi xác minh
ownership/migration scope; conversational field proposal và tool integration sâu
hơn. Không tăng ngân sách để làm benchmark xanh.

Hướng dẫn chạy và trình diễn: `CERTIFICATE_STAGE1_RUNBOOK_20261013.md`.
Kiểm kê trước sửa: `CERTIFICATE_STAGE1_INVENTORY_20261013.md`.
Evidence: `infra/local/certificate-stage1-20261013-01/`.
Không commit/push, không xóa/reset, không sửa archive/corpus/index/guard hoặc dữ
liệu cũ. Chỉ restart các PID demo do nhiệm vụ này tạo, đã đối chiếu receipt/ancestry.
