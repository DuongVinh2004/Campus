# Thiết kế đợt tính năng nâng cao và cờ tính năng — Campus 24/7 (25/11/2026)

Bộ tài liệu này thiết kế chi tiết chín hạng mục chủ dự án đã chọn ngày 25/11/2026:

| Mã | Tài liệu | Tên | Cỡ ước lượng |
|---|---|---|---|
| F0 | [01-feature-flags.md](01-feature-flags.md) | Cờ tính năng cho **mọi** tính năng trong dự án | M |
| F1 | [02-announcements.md](02-announcements.md) | Thông báo chính thức gửi đúng đối tượng, được chatbot dùng làm nguồn | L |
| F2 | [03-policy-rules-engine.md](03-policy-rules-engine.md) | Quy chế thành luật chạy được, mô phỏng "nếu… thì…" có chứng minh | XL |
| F3 | [04-policy-change-impact.md](04-policy-change-impact.md) | Phân tích tác động khi quy chế thay đổi, phát hiện mâu thuẫn | L |
| F4 | [05-answer-evidence.md](05-answer-evidence.md) | Bằng chứng kiểm chứng từng ý của câu trả lời, hiển thị cho người dùng | M |
| F5 | [06-procedure-agent.md](06-procedure-agent.md) | Agent làm thủ tục từ đầu đến cuối | XL |
| F6 | [07-proactive-assistant.md](07-proactive-assistant.md) | Trợ lý chủ động nhắc việc | M |
| F7 | [08-socratic-tutor-mastery.md](08-socratic-tutor-mastery.md) | Gia sư hỏi gợi mở và bản đồ nắm vững của lớp | L |
| F8 | [09-multimodal-input.md](09-multimodal-input.md) | Hỏi bằng ảnh và giọng nói | L |

Cỡ ước lượng: S ≤ 1 ngày làm, M 2–4 ngày, L 1–2 tuần, XL > 2 tuần (một người, có kiểm thử).

---

## 1. Hiện trạng đã kiểm trong code (25/11/2026)

Thiết kế dựa trên việc đọc mã ở nhánh `feat/rag-answer-layout` (HEAD `56e0661`). Những điểm có ảnh hưởng trực tiếp:

| Chủ đề | Sự thật trong mã | Tệp |
|---|---|---|
| Thành phần runtime 8015 | `make_app()` dựng app từ `create_app()` rồi gắn thêm router campus ops, learning, admin ops, freshness, quality, gap report, OIDC; middleware `operational_boundary` chặn đường dẫn ngoài danh sách | `scripts/knowledge_platform.py:364-790` |
| Danh sách đường dẫn được phục vụ | `ALLOWED_API_PREFIXES`, `BLOCKED_LEGACY_API_PREFIXES`, trang đọc từ thư mục `apps/web/src/app`; có test bắt buộc mỗi route thuộc một danh sách | `scripts/runtime_routes.py`, `tests/test_runtime_routes.py` |
| Bật/tắt hiện có | Rải rác bằng biến môi trường: `CAMPUS_LEARNING_ENABLED`, `CAMPUS_LEARNING_AI_ENABLED`, `CAMPUS247_RAG_ANSWER_CACHE`, `CAMPUS247_RAG_SKIP_VERBATIM_SEMANTIC`, `CAMPUS247_PARALLEL_CLASSIFY`, `CAMPUS247_OIDC_CONFIG`; phía web bằng `NEXT_PUBLIC_*` (đóng cứng lúc build) | `bootstrap/settings.py`, `scripts/knowledge_platform.py`, `apps/web/src/components/AppShell.tsx` |
| Capability theo trạng thái hệ thống | `CapabilityManager` có 7 trạng thái và 8 capability, nhưng `/v1/capabilities` đang **bị chặn** trên runtime 8015 | `presentation/capabilities.py`, `scripts/runtime_routes.py:30` |
| Hồ sơ chạy | `infra/profiles/{local,cloud}.toml`, schema chặt (thừa hay thiếu khóa đều lỗi) | `scripts/runtime_profile.py` |
| Vai trò | `STUDENT, LECTURER, SUPPORT_OFFICER, KNOWLEDGE_ADMIN, KNOWLEDGE_CONTRIBUTOR, SYSTEM_ADMIN` | `ports/identity.py:11` |
| Danh bạ demo | 44 tài khoản (40 sinh viên, 4 cán bộ), có `faculty_code`, `class_code`, `unit` nhưng **không** đưa vào `IdentityContext` (chủ đích, để không thu hẹp truy hồi) | `infrastructure/identity/local_directory.py:107` |
| Thông báo | Hộp thư cá nhân `ops_notifications` (SQLite campus ops), gửi qua `store.notify()` trong cùng giao dịch; nhắc hạn có idempotency `ops_reminders_sent` và tùy chọn `ops_reminder_prefs` | `infrastructure/repositories/sqlite_campus_ops.py`, `application/campus_ops/reminders.py` |
| Việc nền | Một tiến trình giữ advisory lock Postgres chạy mọi job (`BackgroundLeader`): lịch tri thức, nhắc thi, nhắc phiếu ra lớp, nhắc độ tươi nguồn, kiểm truy hồi khi đổi release, cảnh báo, worker học liệu | `scripts/knowledge_platform.py:604-660` |
| Đồ thị quy chế | Có mô hình nút/cạnh (`Condition` với `ConditionPredicate` so sánh `> >= < <= =`, `ConditionGroup` ALL/ANY, `supersedes`, `conflict_key`, khoảng hiệu lực), duyệt và phát hành có xác nhận; **ẩn trên runtime v2** vì chưa dựng từ đơn vị `rag_v2` (E3, mục 7 của `EXECUTION_DESIGN_20261119.md`) | `domain/policy_graph.py`, `application/policy_graph/service.py` |
| Kiểm chứng câu trả lời | `rag_v2` đã kiểm **từng phát biểu**: tất định (số, mã, ngày, phủ định, đơn vị), trích nguyên văn, nơi chốn, ngữ nghĩa bằng model; phát biểu trượt bị bỏ; `StatementVerdict.reasons` là mã hữu hạn | `rag_v2/verification/*`, `rag_v2/types.py:82-95` |
| Ấn bản và release | Quyết định ấn bản gắn nguồn, release niêm phong theo trục `programmes, cohorts, academic_years`; `ReleaseWatch` phát hiện release mới | `application/knowledge/edition_*.py`, `release_check.py` |
| Thao tác có ghi | Preview → token xác nhận ký HMAC → confirm có idempotency; tool registry cấm tham số `actor_id, role, tenant_id...` | `domain/action/*`, `application/action/idempotency.py`, `agent/tools/registry.py` |
| Quy trình dịch vụ | `ServiceWorkflow` có phiên bản, máy trạng thái `SUBMITTED → VALIDATING → PROCESSING → WAITING_STUDENT → READY/REJECTED` | `domain/service_workflow.py` |
| Ôn tập | Câu hỏi chỉ trích trang nó dẫn, chấm chính xác bằng code, lặp ngắt quãng SM-2 rút gọn, thống kê lớp chỉ khi ≥ 5 sinh viên | `application/learning/practice.py`, `practice_sets.py:31` |
| OCR | Tesseract/Poppler local cho học liệu và tài liệu tri thức | `infrastructure/learning/*`, memory `learning-ocr-native-runtime` |
| Migration Postgres | Mới nhất `0032_learning_practice.py`; guard bắt duyệt hash migration | `services/api/migrations/versions/` |
| Chi phí model | Gateway sidecar 8025 giữ khóa, sổ cái và trần ngày; trần cloud tạm 5 USD / 2000 lượt/ngày (chủ dự án chưa chốt); giới hạn 5 s với provider **không được nâng** khi chưa hỏi | memory `rollout-phase1-state`, `rag-eval-and-retained-bounds` |

Hệ quả cho thiết kế:

1. **F4 phần lớn đã có ở phía máy chủ.** Phần còn thiếu là đưa biên nhận kiểm chứng ra giao diện, lưu lại để tra soát, và đo lường. F4 nhờ vậy nhỏ hơn đề xuất ban đầu (M thay vì L).
2. **F2 và F3 phụ thuộc vào việc đưa đồ thị quy chế lên runtime v2.** Bước này là gói nền chung `G-PG` (trong [03-policy-rules-engine.md](03-policy-rules-engine.md) §6) và phải làm trước cả hai.
3. **Muốn bật tắt tính năng lúc đang chạy, web phải đọc cờ từ API**, vì `NEXT_PUBLIC_*` đã đóng cứng lúc build.
4. **Gửi thông báo theo đối tượng cần lớp, khoa và khóa của người nhận.** Hiện các trường này mới nằm trong tệp danh bạ. F1 đọc chúng qua một cổng danh bạ riêng, **không** đưa vào `IdentityContext`, để không làm thay đổi phạm vi truy hồi RAG.

---

## 2. Nguyên tắc chung cho mọi tính năng trong đợt

Các nguyên tắc này đi theo các bất biến dự án đang giữ.

1. **Model đề xuất, code quyết định.** Mọi kết luận có hệ quả (đủ điều kiện, gửi đơn, gửi thông báo, chấm điểm) do code tất định đưa ra, trên dữ liệu đã duyệt.
2. **Mọi thao tác ghi đi qua preview → xác nhận → idempotency → audit.** Không có ngoại lệ cho agent.
3. **Không có nguồn thì không trả lời.** Câu trả lời và kết luận phải trỏ về đoạn nguồn đã phát hành; thiếu nguồn thì từ chối và gợi ý đường khác.
4. **Mỗi tính năng có cờ riêng ([F0](01-feature-flags.md)).** Tính năng mới mặc định **tắt**. Tắt cờ chỉ ẩn hoặc chặn, **không xóa dữ liệu**.
5. **Chi phí model đi qua gateway có trần.** Mỗi tính năng có ngân sách lượt gọi riêng, cấu hình được, và bị từ chối an toàn khi hết.
6. **Không đổi lõi RAG khi chưa hỏi chủ dự án.** Không đổi chỉ mục, model, ngưỡng, giới hạn 5 s. Những điểm buộc phải chạm vào lõi được ghi rõ là "cần duyệt".
7. **Dữ liệu cá nhân tối thiểu.** Thống kê chỉ hiện khi nhóm đủ lớn (k ≥ 5, giống `MIN_CLASS_FOR_STATS`). Không lưu nội dung câu hỏi nếu không có đồng ý.
8. **Đo được thì mới gọi là xong.** Mỗi tính năng có bộ kiểm gold do máy kiểm (theo `AGENTS.md`). Khả năng dùng với người dùng thật ghi là **chưa đo**.
9. **Theo nếp kiến trúc sẵn có:** domain thuần (không I/O) → application service → port → adapter (SQLite/Postgres) → presentation (FastAPI router) → `apps/web/src/features/<tên>`.

---

## 3. Phụ thuộc và thứ tự làm

```
F0 cờ tính năng ──┬─> F1 thông báo ──────────────┬─> F6 trợ lý chủ động
                  │                              │
                  ├─> G-PG đồ thị trên v2 ─┬─> F2 luật chạy được ─┬─> F5 agent thủ tục
                  │                        └─> F3 tác động thay đổi ┘  (F3 dùng F1 để soạn thông báo)
                  ├─> F4 bằng chứng kiểm chứng (độc lập)
                  ├─> F7 gia sư + bản đồ nắm vững (độc lập, dùng học liệu)
                  └─> F8 ảnh + giọng nói (độc lập; ảnh dùng OCR có sẵn)
```

Thứ tự đề xuất: **F0 → F1 → F4 → G-PG → F2 → F3 → F6 → F5 → F7 → F8**.

- F0 trước tiên vì mọi tính năng sau gắn vào nó.
- F1 trước vì nhu cầu thật cao nhất, và F3, F6 dùng nó.
- F4 sớm vì nhỏ, rủi ro thấp, và tăng độ tin cậy cho mọi thứ phía sau.
- F5 sau F2 vì agent cần luật chạy được để kiểm điều kiện.
- F7 và F8 độc lập, làm song song được nếu có người.

Các cặp chạy song song được (không chung tệp ghi hay migration): {F4, F7}, {F4, F8}, {F7, F8}. F1, F3 và F6 cùng chạm `campus_ops`, nên làm tuần tự.

---

## 4. Quyết định cần chủ dự án (gom một chỗ)

| # | Quyết định | Đề xuất của người thiết kế | Chặn phần nào |
|---|---|---|---|
| D1 | Lưu ghi đè cờ ở SQLite trong thư mục state hay bảng Postgres (cần migration và duyệt hash) | SQLite `feature-flags.sqlite3`, giống `gap-reports.sqlite3`; đổi sang Postgres khi lên cloud nhiều máy | F0.3 |
| D2 | Ai được gửi thông báo: chỉ `SUPPORT_OFFICER`/`SYSTEM_ADMIN`, hay thêm `LECTURER` cho lớp mình dạy | Cả ba; giảng viên chỉ gửi cho lớp học phần của mình; gửi toàn trường cần người thứ hai duyệt | F1 |
| D3 | Thông báo có vào kho tri thức để chatbot trích dẫn không | Có, qua đúng luồng duyệt/phát hành hiện có, tự hết hiệu lực theo `expires_at` | F1.6 |
| D4 | Ngân sách model riêng cho mỗi tính năng (lượt/ngày) | F2 0 (không gọi model khi chạy luật), F3 200, F5 300, F6 0, F7 500, F8 300; tổng nằm trong trần gateway | F2, F3, F5, F7, F8 |
| D5 | F4 hiển thị mức kiểm chứng cho sinh viên hay chỉ cho cán bộ | Cho mọi người, dạng gọn; chi tiết mã lý do chỉ cho cán bộ | F4 |
| D6 | F8 nhận dạng giọng nói: model local (RAM ~1–2 GB) hay dịch vụ ngoài (có phí, dữ liệu ra ngoài) | Local, chỉ bật trên máy đủ RAM; cloud 8 GB để tắt | F8.2 |
| D7 | F6 tần suất tối đa | ≤ 3 nhắc chủ động/ngày/người, không nhắc 22:00–07:00 | F6 |
| D8 | F7 có cho model tạo câu hỏi gợi mở tự do không | Có, nhưng chỉ dựa trên trang học liệu đã duyệt, kiểm trích dẫn bằng code như `verify_citation`; giảng viên tắt được theo lớp | F7 |
| D9 | F5: agent được **gửi** đơn hay chỉ **soạn** để sinh viên tự bấm gửi | Chỉ soạn và đưa ra preview; sinh viên luôn là người bấm xác nhận | F5 |

Các quyết định này không chặn phần thiết kế. Chúng chỉ chặn đúng gói con được ghi trong cột cuối.

---

## 5. Tiêu chí xong cho cả đợt

1. Mọi tính năng hiện có và mới đều có trong sổ cờ (`features/registry.py`). Test quét route bị đỏ nếu có route `/v1` hoặc trang web chưa gắn cờ.
2. Với cấu hình mặc định, hành vi runtime 8015 **không đổi**: bộ `web_acceptance.mjs` và hồi quy đầy đủ (`run_full_regression.py`) vẫn đạt như trước.
3. Mỗi tính năng F1–F8 có các tiêu chí nghiệm thu trong tài liệu riêng của nó. Mỗi tiêu chí có lệnh kiểm tái lập được và số liệu ghi lại.
4. Tắt từng cờ: route trả `404 FEATURE_DISABLED`, mục điều hướng biến mất, job ngừng tick, tool agent biến mất khỏi danh sách, dữ liệu còn nguyên. Có test tự động cho từng cờ.
5. Không có bí mật, dữ liệu cá nhân hay nội dung câu hỏi trong log hoặc evidence.

---

## 6. Quy ước trong các tài liệu con

- Đường dẫn mã viết tương đối từ gốc repo; `campus247/...` nghĩa là `services/api/src/campus247/...`.
- Lỗi API theo `create_problem_details` sẵn có (`presentation/errors.py`): `status`, `code`, `title`, `detail`, kèm `Cache-Control: no-store` cho dữ liệu cá nhân.
- Thời gian lưu UTC ISO-8601; hiển thị theo `Asia/Ho_Chi_Minh`.
- ID là UUIDv7 (`domain/shared/values.generate_uuid7`).
- Mỗi gói con có mã `Fx.y`, được làm và commit riêng, kèm test.
