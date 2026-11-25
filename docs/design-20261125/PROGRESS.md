# Tiến độ thực thi đợt F-series (nhánh `feat/f-series-20261126`)

Cập nhật lần cuối: 26/11/2026. Mỗi gói con ghi trạng thái: XONG (đã chạy kiểm trong lượt làm), ĐANG LÀM, CHƯA LÀM, BỊ CHẶN.
Bằng chứng là các ca do máy sinh có đáp án kiểm bằng code; khả năng dùng với người dùng thật chưa đo.

## Quyết định ghi lại khi làm

- Tên route admin cờ dùng dấu `/` thay dấu `:` để khớp FastAPI: `POST /v1/admin/features/{key}/preview`, `POST /v1/admin/features/confirm`, `GET /v1/admin/features/audit`.
- Token xác nhận của F0 là HMAC-SHA256 của `preview_id|actor|payload_hash` (khóa `CONFIRMATION_SIGNING_KEY`), không dùng `ConfirmationTokenService` vì lớp đó gắn với `ActionPreviewValue` (phiên, hội thoại). Cùng nguyên tắc: gắn người, nội dung, hết hạn 10 phút, dùng một lần.
- Gate chạy BÊN TRONG middleware danh tính (thêm trước `IdentityMiddleware` trong `create_app`), nên thấy được người gọi; `operational_boundary` của runtime 8015 vẫn là lớp ngoài cùng.
- Job nền được gắn cờ bằng `run_gated` (dừng task khi cờ tắt, chạy lại khi bật) thay vì sửa chữ ký từng `run_*`.
- `/v1/auth/oidc*` vẫn nằm trong `BLOCKED_LEGACY_API_PREFIXES` của `runtime_routes.py` (quyết định có sẵn của chủ dự án): cờ `identity.oidc` có sẵn nhưng route vẫn bị chặn ở lớp ngoài; không đổi ở đợt này.
- Trang `knowledge/policy-graph` bị tắt mặc định theo §5.6 của tài liệu F0 (`knowledge.policy_graph` = tắt); G-PG bật lại.
- Tick `crawl` và `auto_publication` chạy trong tiến trình worker ingest riêng (không phải API); cờ của chúng hiện chỉ có tác dụng ở API (route), chưa dừng tick trong worker.

## Bảng gói con

| Gói | Trạng thái | Commit | Bằng chứng / ghi chú |
|---|---|---|---|
| F0.1 registry + resolution | XONG | 354ee37 | `tests/features/test_feature_service.py` |
| F0.3 store + service + profile | XONG | 354ee37 | cùng tệp; lan truyền ≤ 2,5 s kiểm bằng đồng hồ giả |
| F0.2 sổ cờ + quét route/trang | XONG | 354ee37 | `tests/features/test_feature_gate.py` (mỗi route phục vụ và mỗi trang thuộc một cờ) |
| F0.4 gate middleware + trang | XONG | 354ee37 | ma trận tắt theo từng cờ có tiền tố API |
| F0.5 job / tool / pipeline | XONG (trừ tick worker ingest) | xem log | `run_gated`, `ToolRegistry` ẩn tool tắt, `answer_cache`/`verbatim` đọc qua `features.runtime`; `tests/features/test_feature_tools.py` |
| F0.6 API admin | XONG | 354ee37 | `tests/features/test_feature_admin_api.py` |
| F0.7 web | XONG | xem log | vitest `features.test.tsx` (4), `FeatureFlagsPanel.test.tsx` (3); `tsc --noEmit` sạch; nav lọc trong AppShell (chỉ stage phần của tôi, phần dở của chủ dự án để nguyên) |
| F0.8 quan sát + acceptance | MỘT PHẦN | xem log | khối `features` trong ops status + `FeatureService.summary()` (test). Chưa làm: ô hiển thị trên OperationsPanel, cảnh báo hết hạn, kịch bản web_acceptance tắt rooms |
| F1.1 domain | XONG | fcc1362 | `domain/announcements.py`; `tests/announcements/test_announcements_flow.py` |
| F1.2 danh bạ + gold 40 bộ | XONG | fcc1362 | `test_audience_gold_and_perf.py`: 40/40 bộ trùng truy vấn SQL tham chiếu độc lập |
| F1.3 lưu trữ + phát theo lô | XONG | fcc1362 | bảng `ann_*` trong campus-ops.sqlite3; tiêm lỗi 11 điểm + giữa lô: mỗi người đúng 1 delivery + 1 thông báo; 30 000 người trong 1,6 s (`evals/results/announcements-20261126/perf.json`) |
| F1.4 API | XONG | fcc1362 | `test_announcements_api.py`; đổi `PUT /{id}` thành `PUT /{id}/draft` (để cờ tách route soạn và route đọc) |
| F1.5 job + cờ | XONG | fcc1362 | 4 job qua `run_gated`; hẹn giờ ≤ 60 s kiểm bằng đồng hồ giả |
| F1.6 đồng bộ kho tri thức | MỘT PHẦN | — | `AnnouncementService` có móc `knowledge_sync.publish/revoke`, test thu hồi/hết hạn bằng bản giả; CHƯA nối adapter vào `KnowledgePlatform.upload()` và chưa có test RAG provider giả |
| F1.7 web | MỘT PHẦN | xem log | hộp thư, chi tiết (`?id=`), soạn có đếm người nhận trực tiếp, vitest 4; CHƯA có: thống kê, hàng đợi duyệt, thu hồi/sửa trên giao diện, thẻ trang chủ, nút trong học liệu, trang công khai riêng |
| F1.8 tool chat | CHƯA LÀM | — | |
| F4.0 provider phát lại | CHƯA LÀM | — | cần sổ ghi phản hồi provider theo băm yêu cầu; chưa có sẵn trong repo |
| F4.1 `checks`/`rejected_counts` trong Outcome | CHƯA LÀM | — | chặn bởi F4.0 (phải chứng minh không đổi hành vi trước khi sửa mã RAG) |
| F4.2 support_spans + biên nhận + API | MỘT PHẦN | xem log | `rag_v2/outcome/support_spans.py`: 200 cặp máy sinh từ `data/rag_v2_index/units.jsonl`, ≥ 99 % đoạn chứa đủ số (`tests/rag_v2/test_support_spans.py`); kho + service + `GET /v1/answer-receipts/{id}` có test (`tests/features/test_answer_receipts.py`); CHƯA nối ghi biên nhận từ luồng chat (cần F4.1) |
| F4.3 giao diện huy hiệu/tô đoạn | CHƯA LÀM | — | |
| F4.4 số đo trang chất lượng | CHƯA LÀM | — | |
| G-PG, F2, F3, F5, F6, F7, F8 | CHƯA LÀM | — | hết ngân sách của lượt chạy này; tiếp tục ở lượt sau theo thứ tự README §3 |

- Trang động `[id]` không chạy được trên 8015 vì `runtime_routes.page_routes()` liệt kê trang tĩnh; chi tiết thông báo dùng `/announcements?id=`.

## Hồi quy đã chạy (lượt này)

- `tests/features` 70 đạt; `tests/test_runtime_routes.py` đạt; `tests/architecture` đạt; `tests/rag_v2` 418 đạt, 1 lỗi `INDEX_OUTSIDE_WORKSPACE` (môi trường, `tests/rag_v2/test_i2_lifecycle.py`).
- `tests/operations/test_runtime_audit_fixes.py`: 30 lỗi `must stay inside workspace` giống hệt ở commit gốc 6888822 (đã kiểm bằng worktree) → có sẵn từ trước, không do đợt này.
- vitest toàn bộ: 8 lỗi do `/v1/features` lấy mất mock fetch của test khác; đã sửa bằng cách tắt tự tải trong NODE_ENV=test, 5 tệp liên quan chạy lại đạt (cần chạy lại toàn bộ ở cuối).
