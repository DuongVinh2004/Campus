# Thiết kế thực thi các việc làm được ngay (19/11/2026)

Trạng thái: **thiết kế đã được chủ dự án đồng ý theo đề xuất** (chỉ dẫn trực tiếp ngày 19/11: "tôi đồng ý với đề xuất tốt nhất của bạn"). Tài liệu này chưa thay đổi mã.
Bằng chứng: các số dòng dưới đây là mã trên `origin/main` (`5756c87`), đọc ngày 19/11. Mỗi gói ghi rõ phải đọc lại gì trước khi sửa (bước 0).

Tài liệu nguồn: [FEATURE_PROGRESS_20261117](FEATURE_PROGRESS_20261117.md), [FEATURE_READY_TASKS_20261117](FEATURE_READY_TASKS_20261117.md),
[GROUP_B](GROUP_B_DESIGN_20261117.md), [GROUP_C](GROUP_C_DESIGN_20261117.md), [BUGFIX_PLAN_20261118](08-quality/BUGFIX_PLAN_20261118.md),
[NEXT_SESSION_PROMPT_20261118](08-quality/NEXT_SESSION_PROMPT_20261118.md), [RAG_GENERALIZATION_PROGRESS_20261118](08-quality/RAG_GENERALIZATION_PROGRESS_20261118.md).

---

## 0. Hiện trạng đã kiểm (19/11)

| Mục | Trạng thái kiểm được | Bằng chứng |
|---|---|---|
| Mã nguồn | Toàn bộ mã đã được commit và merge vào `origin/main` (PR #2, #3). Không còn tệp mã chưa theo dõi trong `scripts/`, `services/`, `apps/web/src`, `packages/`, `evals/runners/`, `tests/`, `infra/cloud/` | `git status --short --untracked-files=all <các thư mục>` → 0 |
| Nhánh `main` cục bộ | Chậm hơn `origin/main` một commit merge | `git rev-parse` |
| RAG R1–R4 | Đã làm: bộ đo tài liệu chưa thấy 47/47, bộ giữ lại 17/18; bộ chặn kỷ luật đã sửa (N6 hết) | `RAG_GENERALIZATION_PROGRESS_20261118.md` |
| `rerank_scores: []` | **Đã rõ nguyên nhân**: tắt rerank có chủ ý. `rag_v2/service.py:286-290` gọi `retrieve(..., rerank_deadline_s=0)` vì rerank làm giảm tỉ lệ giữ gold (92 % → 83 %). Nhưng `retrieval/hybrid.py:194` vẫn `raise TimeoutError`, nên trace ghi `RRF_TIMEOUT` cho mọi lượt: nhãn sai, dễ hiểu lầm là lỗi | đọc mã |
| N7 phòng học | Vẫn N+1: `RoomFinder.tsx:170-190` gọi `roomsApi.availability` từng phòng (lô 6 song song). Phía server, `service.availability` (`campus_ops/service.py:137`) chạy 2 truy vấn mỗi phòng (`_busy`, dòng 120) | đọc mã |
| N5 đồ thị quy chế | `PolicyGraphService` gắn cứng với kho v1 `PublicHybridKnowledgeStore` (`bootstrap/app.py:502-510` kiểm fingerprint chỉ mục và nguồn v1). Runtime vận hành chạy `rag_v2`, nên **không nối thẳng được**; cần một tính năng riêng | đọc mã |
| C3.5 nhãn nguồn | Web đã có nhãn `stale` nhưng chỉ suy từ `source_status` (`app/chat/page.tsx:44`). Trích dẫn chưa mang trạng thái rà soát (OVERDUE) | grep |
| C1 | Đã có đếm "chưa hữu ích" theo nguồn (`answer_quality.py`, `GET /v1/knowledge/answer-quality`). Chưa có sự kiện từ chối (ABSTAINED) và chưa có giao diện | grep |
| C2.4 | `nightly_retrieval.py` đã nhận `--trigger release` (dòng 152), nhưng chưa có gì gọi khi kích hoạt release | grep |
| B1.5 | `reminders.py` mới có nguồn lịch thi; chưa có phiếu ra lớp. `exit_tickets.py:79` có sẵn cách tính `OPEN/CLOSED` theo `closes.utc` | đọc mã |
| PWA | `clearPwaCaches` khai báo ở `components/PwaRegister.tsx:6` nhưng **không nơi nào gọi**, nên đăng xuất chưa xóa cache trang | grep |
| Học liệu trên runtime vận hành | Runtime chỉ nạp học liệu khi có `infra/local/learning-materials-20261104-01/config.json` (`knowledge_platform.py:403-409`); danh sách revision chấp nhận của DB vận hành là `0017/0018/0022/0023/0024` (dòng 282), không gồm 0025–0031 của học liệu | đọc mã |
| Ổ đĩa | 89 GB trống / 386 GB (22 %), không còn ở mức nghiêm trọng như ngày 17/11. Có 117 thư mục `.pytest-tmp-*` trong repo, không bị `.gitignore` bỏ qua | `df`, `ls` |

---

## 1. Phạm vi

**"Làm được ngay"** giữ sáu điều kiện của `FEATURE_READY_TASKS`: không chờ quyết định, không gọi provider trả phí, không tải phần mềm mới,
không dùng dịch vụ ngoài, không đổi cách truy hồi hay sinh câu trả lời, không dùng dữ liệu thật.

Hai gói vượt điều kiện, nhưng chủ dự án đã cho phép từ trước, nên vẫn được đưa vào:
- **E5**: phát hành thử một tài liệu. Đổi chỉ mục sống một lần, đã được cho phép ở mục C7 của `NEXT_SESSION_PROMPT`.
- **E17**: mở rộng bộ giữ lại RAG. Tốn khoảng 150 lượt gọi provider mỗi lần chạy; mục 2 của `RAG_GENERALIZATION_PROGRESS` đã đề ra và chủ dự án đã đồng ý.

**Ngoài phạm vi** (cần đầu vào mà đồng ý chung không thay được): xem mục 6.

---

## 2. Quy tắc chung cho mọi gói

1. **Nhánh**: mỗi gói một nhánh từ `origin/main` (`fix/…`, `feat/…`, `chore/…`). Nếu gói sau cần mã chưa merge của gói trước thì tạo từ HEAD của gói trước, và ghi thứ tự ở mô tả commit.
2. **Bước 0**: đọc lại các dòng được dẫn. Mã đổi khác với tài liệu thì sửa thiết kế trong commit của gói, không làm theo tài liệu cũ.
3. **Test đỏ trước, xanh sau** cho mọi lỗi. Mỗi tính năng có test đơn vị và test tích hợp ở biên (API/route).
4. **Lệnh kiểm** (chạy từ gốc repo):
   - Python: `.venv/Scripts/python.exe -B -m pytest <đường dẫn> -q -o pythonpath="services/api/src services/worker/src packages/synthetic/src" --basetemp=.pytest-tmp-<gói>-<ngày> -p no:cacheprovider`
   - Web (trong `apps/web`): `npx vitest run <đường dẫn>`, `npx tsc --noEmit -p .`
   - Tập CI: `run_full_regression.py --ci` trước khi merge mỗi đợt.
   - Giao diện thật: dựng snapshot frontend mới, đổi runtime 3015 (memory `ui-rebuild-restart`), rồi `node scripts/qa/web_acceptance.mjs`. Không chạy dồn, vì giới hạn 429.
5. **Bằng chứng**: `evals/results/<gói>-<stamp>/`, gồm lệnh, mã thoát, tệp kết quả và ảnh nếu có.
6. **An toàn**:
   - Không nâng giới hạn 5 s của provider; không đổi model hay chỉ mục ngoài E5.
   - Không xóa dữ liệu ngoài danh sách đã duyệt; không push hay merge khi chưa được duyệt.
   - Route `/v1` mới phải nằm trong `ALLOWED_API_PREFIXES` của `scripts/runtime_routes.py`. `tests/test_runtime_routes.py` sẽ báo nếu thiếu.
7. **Dừng gói**: chỉ dừng khi gặp trở ngại đã kiểm chứng. Ghi lại mục bị chặn, bằng chứng và đầu vào tối thiểu cần, rồi làm tiếp các gói độc lập.

---

## 3. Tổng quan các gói

| ID | Gói | Cỡ | Phụ thuộc | Tệp chính (khóa xung đột) |
|---|---|---|---|---|
| E0 | Dọn nền: `.gitignore` thư mục test tạm, danh sách dọn có duyệt, đồng bộ `main` | S | — | `.gitignore`, `scripts/maintenance/` |
| E1 | Khả dụng phòng theo lô (N7) | M | — | `presentation/campus_ops.py`, `application/campus_ops/service.py`, `features/rooms/RoomFinder.tsx`, `lib/…rooms` |
| E2 | Nhãn trace "chỉ RRF" thay cho `RRF_TIMEOUT` giả | S | — | `rag_v2/retrieval/hybrid.py` |
| E3 | Đồ thị quy chế: ẩn có kiểm soát trên runtime v2 | S | — | `app/knowledge/page.tsx`, `SourceOperations.tsx`, `web_acceptance.mjs` |
| E4 | Học liệu theo lớp: dữ liệu mô phỏng + luồng nghiệm thu | M–L | — | `scripts/learning_*`, `scripts/qa/web_acceptance.mjs` |
| E5 | Phát hành thử một tài liệu rồi thu hồi | M | RAM | không đổi mã (trừ khi tìm thấy lỗi) |
| E6 | Quét virus thật qua API (ClamAV bật) | M | RAM | `infrastructure/knowledge/multipart.py` (nếu chọn quét trước khi ghi đĩa) |
| E7 | C3.5 nhãn "nguồn quá hạn rà soát" trong trích dẫn | M | — | `presentation/chat.py`, `features/chat/CitationDrawer.tsx`, `app/chat/page.tsx` |
| E8 | C1 sự kiện từ chối (P1, không chữ) + tab "Chất lượng câu trả lời" | M–L | — | `application/knowledge/answer_quality.py`, `presentation/knowledge_quality.py`, `features/knowledge/` |
| E9 | C2.4 + C2.6: chạy kiểm truy hồi khi kích hoạt release, chốt baseline | S–M | model server | `evals/runners/nightly_retrieval.py`, leader jobs |
| E10 | B1.5 nhắc phiếu ra lớp sắp đóng | M | E4 (để kiểm trên UI) | `application/campus_ops/reminders.py`, `application/learning/exit_tickets.py` |
| E11 | B1.6 phần còn lại: công tắc "nguồn" theo vai trò | S | — | `features/notifications/ReminderPreferences.tsx` |
| E12 | PWA: xóa cache khi đăng xuất + kiểm trình duyệt thật | S | — | `components/PwaRegister.tsx`, `lib/store.tsx`/`Navbar.tsx` |
| E13 | B3.3–B3.6 ôn tập (migration 0032 trên DB tạm) | L | — | `migrations/versions/0032_…`, `application/learning/practice*.py`, `presentation/learning.py`, `features/learning/` |
| E14 | B4.1–B4.3 đo truy hồi tiếng Anh + nền i18n + 4 màn hình | L | model server | `evals/datasets/`, `apps/web/src/lib/i18n/` |
| E15 | Kiểm trên Postgres thật: SQL độ mới nguồn + diễn tập khôi phục vào DB tạm | M | Postgres cục bộ | `scripts/` sao lưu, không đổi mã nếu đạt |
| E16 | A2.8 chạy tải có số liệu vận hành (cổng thử, provider giả) | M | — | `evals/runners/rag_load_test.py`, `evals/load/` |
| E17 | Mở rộng bộ giữ lại RAG (3 loại tài liệu mới, chạy một lần) | M | ~150 lượt gọi | `evals/datasets/unseen-docs-heldout/` |

**Thứ tự đề xuất** (một người làm tuần tự, tổng khoảng 20–26 ngày):
E0 → E2 → E1 → E12 → E3 → E7 → E11 → E4 → E10 → E8 → E9 → E15 → E16 → E5 → E6 → E13 → E14 → E17.
Lý do: sửa lỗi người dùng thấy trước, rồi đến giao diện nhỏ, rồi các luồng cần dữ liệu mô phỏng. Các gói cần RAM (E5, E6) gom vào một buổi.
Hai gói lớn (E13, E14) để cuối.

**Song song an toàn** (khóa xung đột tách rời):
- {E1, E2, E7, E13} chạm tệp khác nhau.
- E7 và E8 cùng chạm vùng `knowledge`, nên làm tuần tự.
- E10 cần E4 để kiểm trên giao diện, nhưng phần pytest làm trước được.

---

## 4. Thiết kế chi tiết

### E0 — Dọn nền

- **`.gitignore`**: thêm `.pytest-tmp*/`. Hiện 117 thư mục loại này nằm trong `git status`, làm khó việc kiểm phạm vi.
- **`scripts/maintenance/list_test_temp.py`**: chỉ đọc. Liệt kê thư mục `.pytest-tmp-*` ở gốc repo, mỗi mục gồm kích thước, lần sửa cuối và có đọc được không (nhiều thư mục báo `Permission denied`). Kết quả ghi ra CSV.
  Script **không xóa**. Chủ dự án duyệt danh sách thì mới chạy `--delete <tệp danh sách>`. Lệnh này chỉ nhận thư mục khớp `^\.pytest-tmp-` nằm ngay dưới gốc repo, và từ chối symlink/junction.
- **Đồng bộ `main`**: `git fetch` rồi `git switch main && git merge --ff-only origin/main`. Không đụng nhánh khác.
- **Kiểm**: pytest cho script (thư mục giả, chặn đường dẫn ngoài gốc, chặn junction); `git status --short | grep -c pytest-tmp` = 0.

### E1 — Khả dụng phòng theo lô (N7)

**API mới** `GET /v1/rooms/availability?date=YYYY-MM-DD&room_ids=id1,id2,…`:
- Khai báo **trước** `/v1/rooms/{room_id}/availability` (`presentation/campus_ops.py:92`). Đường dẫn không trùng mẫu, nhưng giữ thứ tự để rõ ràng.
- Xác thực giống endpoint một phòng: cùng dependency phiên, cùng giới hạn tốc độ.
- `room_ids`: 1–60 id (một lần tải có 34 phòng), không trùng, mỗi id ≤ 64 ký tự. Sai thì 422 `INVALID_ROOM_IDS`. Ngày sai thì 422 `INVALID_DATE`, cùng thông điệp như hiện nay.
- Phản hồi:
  ```json
  {"date":"2026-11-20","open":"07:00","close":"21:00","limits":{…},
   "items":[{"room":{…room_view…},"busy":[…]}],"missing":["id-không-tồn-tại"]}
  ```
  `limits` chỉ trả một lần cho cả lô.

**Service** `CampusOpsService.availability_many(room_ids, day)`:
- Kiểm ngày một lần, rồi lấy các phòng bằng một truy vấn `id IN (…)`.
- Thêm `_busy_many(rooms, start, end)` chạy đúng 2 truy vấn:
  - `ops_room_bookings WHERE room_id IN (…)`;
  - `ops_schedule WHERE location IN (…codes…)`.
  Kết quả gom theo phòng, mỗi phòng sắp xếp như `_busy`.
- `_busy` giữ nguyên cho các đường đặt chỗ, vì đường đó cần kết nối transaction (`conn=`).
- **Bất biến**: với mọi phòng, `availability_many(...).items[i]` phải bằng `availability(room_i, day)` trừ trường `limits`. Test thuộc tính kiểm điều này trên dữ liệu tổng hợp có đặt chỗ chồng giờ, lịch thi và lịch học.

**Web**:
- `roomsApi.availabilityMany(ids, date)`.
- `loadAvailability` gọi theo lô 60 id, giữ cơ chế `availReqIdRef` để bỏ phản hồi cũ. Lỗi lô thì giữ bản đồ cũ và hiện lỗi nhẹ như hiện tại (`catch(() => null)`).
- Hành vi hiển thị không đổi.

**Kiểm**:
- pytest: bất biến ở trên, 422 các kiểu, không đăng nhập thì 401, `missing` đúng, và đúng 2 truy vấn SQL (đếm bằng store giả).
- vitest: một lần gọi cho 34 phòng, phản hồi cũ bị bỏ qua.
- `web_acceptance.mjs`: thêm khẳng định trang `/rooms` gọi ≤ 2 yêu cầu `/v1/rooms/*availability*` mỗi lần tải.

### E2 — Nhãn trace "chỉ RRF"

- Ở `retrieval/hybrid.py:192-209`, khi `rerank_deadline_s == 0`: không `raise TimeoutError` nữa, đặt `trace["status"] = "RRF_ONLY"`, và **giữ nguyên** `fallback = True` cùng thứ tự `chosen`.
  Hiện nhánh này chỉ sắp lại theo `fused_score`, và `ranked[:final_limit]` đã sắp như vậy, nên kết quả không đổi.
- Không đổi tham số, ứng viên hay ngữ cảnh. Đây chỉ là nhãn quan sát. Ghi rõ lý do tắt rerank (số đo ở `service.py:286-289`) trong docstring `retrieve`.
- Bước 0: grep `RRF_TIMEOUT` ở số liệu vận hành, luật cảnh báo và evals. Ngày 19/11 chỉ thấy ở `hybrid.py:209`.
- **Kiểm**:
  - pytest trên chỉ mục tổng hợp: danh sách `candidates` và `fallback` giống hệt trước khi sửa (so snapshot); `status == "RRF_ONLY"`.
  - Đường có rerank (`deadline > 0`) vẫn ra `RERANKED`/`RRF_TIMEOUT` như cũ.
  - `tests/rag_v2` toàn bộ đạt.

### E3 — Đồ thị quy chế trên runtime v2

**Kết luận đánh giá N5**: chưa nối được an toàn.
- Dịch vụ cần repository đồ thị, `citation_source_reader`, và chỉ mục/nguồn v1 khớp fingerprint (`bootstrap/app.py:502-514`).
- Runtime vận hành đọc chỉ mục `rag_v2`.
- Muốn nối phải dựng đồ thị từ đơn vị v2, tức một tính năng mới cần thiết kế riêng (ghi ở mục 7).

**Việc làm ngay**:
- Liên kết tới `/knowledge/policy-graph` chỉ hiện khi API có mặt: gọi `GET /v1/policy-graph/versions` một lần khi mở `/knowledge`; trả 404 thì ẩn liên kết.
  Liên kết nằm ở `app/knowledge/page.tsx` và `SourceOperations.tsx`.
- Trang mở trực tiếp vẫn giữ thông báo hiện có.
- `web_acceptance.mjs`: giữ ngoại lệ 404 đúng một route, thêm khẳng định liên kết bị ẩn trên 8015.
- **Kiểm**: vitest (có API thì hiện, 404 thì ẩn, lỗi mạng thì ẩn) và cổng nghiệm thu.

### E4 — Học liệu theo lớp trên giao diện thật (WP10)

**Bước 0 — chẩn đoán, chỉ đọc**:
- (a) có `infra/local/learning-materials-20261104-01/config.json` không;
- (b) revision của DB vận hành;
- (c) `GET /v1/learning/...` với `student-local` trả gì.

**Hướng A** (học liệu đã chạy trên runtime vận hành, chỉ thiếu lớp):
- Thêm `scripts/learning_seed_synthetic_class.py`. Script gọi **chính API/learning service**, không ghi SQL tay, để tạo:
  - 1 lớp `MÔ PHỎNG — Lớp thử QA`;
  - 2 buổi;
  - 1 tài liệu TXT/PDF tổng hợp;
  - 1 phiếu ra lớp đóng sau 26 giờ (dùng cho E10).
- Gán `student-local` vào lớp.
- Nếu chưa có tài khoản giảng viên, tạo **một** danh tính mô phỏng `lecturer-local` theo cách `learning_local_identity.py` đang làm, gắn cờ mô phỏng. Đây là tài khoản mới được nêu rõ ở đây, và đã nằm trong đồng ý ngày 19/11.
- Script idempotent: chạy lại không tạo trùng. Có `--dry-run`.

**Hướng B** (runtime vận hành không có bảng học liệu 0025–0031):
- Không áp migration vào DB vận hành.
- Dựng runtime diễn tập riêng bằng `learning_local_setup.py` trên cổng **8016**. Script này đã thiết kế để không đụng kho của người dùng (docstring dòng 1).
- Thêm cờ `--base http://127.0.0.1:8016` cho `web_acceptance.mjs`.

Đề xuất: chọn A nếu bước 0 cho thấy được; còn lại chọn B.

**Luồng nghiệm thu mới** `learningFlow` trong `web_acceptance.mjs`, chạy với vai sinh viên ở desktop và điện thoại:
1. chọn lớp;
2. mở buổi;
3. đọc tài liệu, đổi trang, tải lại thì vị trí đọc được nhớ;
4. "Cập nhật học liệu";
5. gửi phản hồi trang (`PageFeedback`);
6. phiếu cuối buổi: mở, nộp, thấy trạng thái đã nộp;
7. sinh viên lớp khác (nếu hướng B có `--second-student`) nhận 403.

Lỗi tìm thấy ghi vào mục 6 của `BUGFIX_PLAN_20261118.md` và sửa trong gói này, mỗi lỗi một test đỏ trước.

### E5 — Phát hành thử một tài liệu

**Điều kiện**: RAM trống ≥ 2,6 GB ngoài model server, và worker nhập liệu bật (khởi động lại không có `--defer-worker`). Launcher từ chối vì RAM thì hỏi chủ dự án, không tự đóng ứng dụng.

**Các bước**, ghi số liệu trước và sau từng bước:
1. Ghi lại release đang chạy: id release, số đơn vị, sha chỉ mục.
2. Tải `QA-20261120 thông báo thử.txt` (tổng hợp, có một câu đặc trưng không có trong kho) ở chế độ **Gửi duyệt** bằng owner.
3. Duyệt bằng tài khoản khác. Theo dõi đến trạng thái dùng được, ghi thời gian từng chặng.
4. Hỏi chatbot câu đặc trưng: phải có trích dẫn tới tài liệu QA.
5. **Thu hồi**. Xác nhận release, số đơn vị và sha trở về giá trị ban đầu, và câu đặc trưng không còn được trả lời bằng tài liệu đó.

**Kết quả**: thêm vào mục 7 của `BUGFIX_PLAN_20261118.md`. Bước nào thất bại thì dừng ở trạng thái an toàn: thu hồi ngay, rồi ghi lỗi.

### E6 — Quét virus thật qua API

**Điều kiện**: ClamAV bật (cần khoảng 4,2 GB RAM), `/health/ready` có `upload-scanner: ready`.

**Vấn đề**: Windows Defender chặn tệp EICAR trên đĩa, nên đường API báo "bộ quét không sẵn sàng" thay vì "bị từ chối". **Không** thêm ngoại lệ Defender, vì đó là đổi thiết lập bảo mật.

**Bước 0**: đọc `services/api/src/campus247/infrastructure/knowledge/multipart.py`, xem byte được ghi ra đĩa trước hay sau `scan_original`.

**Đề xuất**: nếu hiện tại ghi trước rồi mới quét thì đổi sang **quét trước khi lưu**.
- Đẩy luồng byte vào clamd bằng `INSTREAM` trong lúc nhận, giữ trong bộ nhớ tối đa giới hạn tải lên hiện có.
- Chỉ ghi tệp khi clamd trả `OK`.
- Lợi ích: tệp nhiễm không bao giờ chạm đĩa, giảm rủi ro bảo mật, đồng thời tránh được Defender.
- Đây là thay đổi bảo mật theo hướng chặt hơn. Thất bại vẫn fail-closed như cũ.

**Kiểm**:
- pytest với clamd giả: thứ tự quét trước, ghi sau; nhiễm thì không có tệp nào trên đĩa.
- Chạy thật: tệp sạch nhận 202. EICAR sinh trong bộ nhớ của client Python (không ghi ra đĩa), gửi bằng `httpx`, nhận đúng mã từ chối nhiễm độc.
- Đo thời gian tải tệp 10 MB trước và sau.

Nếu `multipart.py` đã quét trước khi ghi thì chỉ cần phần kiểm thật.

### E7 — Nhãn "nguồn quá hạn rà soát" (C3.5)

**API**:
- Khi tuần tự hóa trích dẫn (luồng SSE ở `presentation/chat.py:375-382` và đường đọc lịch sử hội thoại), thêm trường `review_status ∈ {OK, DUE_SOON, OVERDUE}`, tính bằng `source_freshness.py` (C3.1) theo `version_id` của trích dẫn.
- `FreshnessService` có cache trong tiến trình 5 phút theo `version_id`, để không truy vấn DB mỗi trích dẫn.
- Lỗi tính thì bỏ trường, không làm hỏng lượt chat; log `citation_review_status_failed`.
- Trạng thái tính lúc đọc, không lưu vào tin nhắn, nên lịch sử cũ cũng có nhãn đúng hiện tại.

**Web**:
- `app/chat/page.tsx:44` và `UnifiedAssistantWorkspace.tsx:100` ánh xạ `review_status === "OVERDUE"` thành `reviewOverdue: true`.
- `CitationDrawer` hiện nhãn phụ "Nguồn quá hạn rà soát — nên đối chiếu văn bản gốc", đặt cạnh nhãn hiệu lực hiện có, không thay nhãn đó.

**Bất biến**: chữ câu trả lời và danh sách trích dẫn không đổi. Test so byte của nội dung trả lời trước và sau khi bật làm giàu.

**Kiểm**: pytest (OVERDUE/OK/thiếu ngày, lỗi service thì bỏ trường), vitest (hiện nhãn, không hiện khi OK), cổng nghiệm thu không đổi.

### E8 — Sự kiện từ chối và tab "Chất lượng câu trả lời" (C1.1–C1.4, phương án P1)

**Lưu**:
- Mở rộng `AnswerQualityStore` thay vì tạo bảng `gap_events` riêng, để một nơi giữ một loại tín hiệu.
- Thêm bảng SQLite `answer_gaps(id, at, kind, release_id, version_ids_json, gate_reasons_json, cluster_key, expires_at)`, với `kind ∈ {ABSTAINED, GATE_REFUSED}`.
- **Không** có cột chữ câu hỏi, chữ câu trả lời, người dùng hay hội thoại.
- Giữ 180 ngày, cùng chính sách với `answer_ratings`.

**Ghi**:
- Sau khi lượt chat kết thúc với từ chối hoặc chưa đủ căn cứ, ghi lấy `top_versions` (≤ 5) từ kết quả truy hồi và mã lý do gate.
- Ghi bất đồng bộ, lỗi chỉ log.
- Điểm móc: nơi `attach_quality_recording` gắn vào feedback service (`answer_quality.py:59`); thêm `attach_gap_recording` cho đường kết thúc lượt chat của `rag_v2`.
- Bước 0: tìm mọi chỗ kết thúc lượt bằng từ chối, ví dụ `agent/nodes/rag_v2.py:384` (`Outcome("refuse", GUARD_BLOCKED_MESSAGE …)`), và các kết quả `refuse` khác của `rag_v2/service.py`.

**Cụm** `cluster_key = sha1(sorted(version_ids[:3]) + gate_reason)`. Không gọi embedding, không gửi chữ ra ngoài.

**API** (`KNOWLEDGE_ADMIN`):
- `GET /v1/knowledge/answer-quality?days=30` thêm khối `gaps: [{cluster_key, count, last_at, sources:[{version_id,title}], reasons}]`, tối thiểu 3 lượt một cụm (cùng `MIN_VOTES`).
- `POST /v1/knowledge/answer-quality/gaps/{cluster_key}/decision` nhận `{action: NEEDS_SOURCE|SOURCE_OUTDATED|OUT_OF_SCOPE|RESOLVED, note ≤ 500, release_ref?}`. Ghi audit; `RESOLVED` bắt buộc có `release_ref`.

**Web**:
- Tab "Chất lượng câu trả lời" trong `/knowledge` gồm hai bảng:
  - nguồn bị đánh giá chưa hữu ích (đã có API);
  - cụm từ chối.
- Mỗi cụm có nút "Thêm nguồn", mở `KnowledgeIntake` với gợi ý tên nguồn. Badge "mới" khi số đếm tuần này > 1,5 lần tuần trước.

**Kiểm**:
- pytest: một lượt từ chối tạo đúng một sự kiện và cơ sở dữ liệu không chứa chuỗi câu hỏi (quét toàn bộ tệp SQLite tìm chuỗi đó); ghi lỗi không làm hỏng lượt chat; sinh viên nhận 403; hết hạn thì bị xóa.
- vitest cho tab.
- Thêm `answer_gaps` vào danh sách sao lưu giống `answer_ratings`.

### E9 — Kiểm truy hồi khi kích hoạt release (C2.4) và baseline (C2.6)

- **Móc**: khi `KnowledgeReleaseRuntime` kích hoạt release mới, leader đặt một việc `nightly_retrieval.run(trigger="release")`.
  - Gom các lần kích hoạt trong 10 phút thành một lần chạy.
  - Bỏ qua nếu có hơn 3 lượt chat đang chạy (số liệu A2), thử lại sau 15 phút, tối đa 3 lần.
  - Chạy trong tiến trình con, không chặn vòng lặp sự kiện.
- **Baseline** (C2.6, chọn theo đề xuất): lần chạy thành công đầu tiên trên release hiện tại được ghi `evals/results/nightly/baseline.json` **chỉ khi tệp chưa có**, không bao giờ ghi đè. Đổi baseline là thao tác tay có ghi chú.
- **Kiểm**:
  - pytest với hook và đồng hồ giả: gom 3 lần kích hoạt thành 1 lần chạy, bỏ qua khi bận, baseline không bị ghi đè.
  - Chạy thật một lần (cần 18081/18082).

### E10 — Nhắc phiếu ra lớp sắp đóng (B1.5)

**Nguồn**: thêm `exit_ticket_candidates(learning_service, resolve_recipient, *, now, window=25h)` cạnh `exam_candidates` (`reminders.py:91`).
- Danh sách phiếu lấy qua một hàm đọc mới `LearningService.due_exit_tickets(tenant, now, until)`. Hàm dùng đúng kiểm quyền lớp hiện có và trả `(ticket_id, class_id, closes_utc, title)` cho phiếu `OPEN` (cách tính ở `exit_tickets.py:79`).
- Lọc ra sinh viên trong lớp **chưa nộp**.

**Gửi**:
- Dùng chung `deliver()` và bảng idempotency của B1.4, khóa `(subject, "EXIT_TICKET", ticket_id, offset)`, offset T−24h và T−2h.
- Liên kết tới đúng buổi học.

**Tôn trọng cài đặt**: thêm loại `exit_tickets` vào preferences (B1.6). Mặc định bật.

**Chịu lỗi**: học liệu tắt (`learning_service is None`) thì bỏ qua lặng lẽ. Lỗi đọc thì log và không chặn nhắc thi.

**Kiểm**:
- pytest đồng hồ giả: nhắc đúng 2 mốc; đã nộp thì không nhắc; phiếu đã đóng không nhắc; chạy lại không trùng; tắt cài đặt thì không nhắc.
- Trên giao diện thật dùng phiếu mô phỏng của E4.

### E11 — Công tắc nhắc nguồn theo vai trò (phần còn lại của B1.6)

- `ReminderPreferences` đọc vai trò từ `/v1/users/me` có sẵn trong store. Công tắc "Nhắc hạn rà soát nguồn" chỉ hiện với `KNOWLEDGE_ADMIN`/owner. API đã nhận loại này.
- **Kiểm**: vitest cho ba vai (sinh viên ẩn, cán bộ ẩn, owner hiện).

### E12 — PWA: xóa cache khi đăng xuất, kiểm trình duyệt thật

- Gọi `clearPwaCaches()` trong luồng đăng xuất. Bước 0: xác định nơi xử lý đăng xuất thật, ứng viên là `lib/store.tsx` và `components/Navbar.tsx`.
- Gọi trước khi chuyển trang, không chờ kết quả; lỗi bỏ qua.
- **Kiểm**:
  - vitest: đăng xuất gọi `clearPwaCaches` đúng một lần.
  - Kiểm trên trình duyệt thật (Playwright, 8015):
    1. SW đăng ký;
    2. ngắt mạng thì điều hướng ra `/offline`;
    3. `caches` không có mục `/v1/*` nào sau một phiên chat;
    4. đăng xuất xong, cache trang trống.
  - Ghi ảnh và kết quả `caches.keys()`.

### E13 — Ôn tập từ học liệu (B3.3–B3.6)

**Migration 0032** (`services/api/migrations/versions/0032_learning_practice.py`), chỉ thêm, không sửa bảng cũ:

| Bảng | Cột chính | Ràng buộc |
|---|---|---|
| `learning_practice_sets` | `id uuid pk, tenant_id, class_id, version_id, title, status (DRAFT/PUBLISHED/RETIRED), revision int, created_by, created_at, published_at` | FK `version_id`; `status` CHECK; unique `(tenant_id, id)` |
| `learning_practice_items` | `id, set_id, ordinal, kind (single_choice/multi_choice/short_answer), prompt, options jsonb, answer jsonb, explanation, citations jsonb, origin (lecturer), review_state` | `citations` không rỗng khi set PUBLISHED (kiểm ở ứng dụng) |
| `learning_practice_attempts` | `id, tenant_id, subject_id, item_id, correct bool, answered_at, idempotency_key` | unique `(subject_id, idempotency_key)` |
| `learning_practice_schedule` | `tenant_id, subject_id, item_id, ease numeric, interval_days int, due_at` | pk `(tenant_id, subject_id, item_id)` |

**Áp dụng**:
- Áp và kiểm **chỉ trên DB tạm** (runtime diễn tập 8016 hoặc DB `campus_practice_test_<stamp>` do test tạo và xóa).
- Áp vào DB vận hành cần chủ dự án duyệt **hash cụ thể** của tệp migration. Guard migration hiện có đòi điều này, và thiết kế không nới nó. Khi xong sẽ báo hash để duyệt.
- Thêm `0032` vào tập revision chấp nhận ở `knowledge_platform.py:282` chỉ sau khi được duyệt.

**Domain**: dùng lại `practice.py` (B3.1 kiểm trích dẫn, B3.2 lặp lại ngắt quãng, 26 test đã đạt).

**API**:
- Giảng viên:
  - `POST /v1/learning/classes/{c}/practice-sets`;
  - `PUT …/items`;
  - `POST …:publish`, trả 422 kèm danh sách item lỗi nếu trích dẫn không khớp nguyên văn trang của đúng phiên bản;
  - `GET …/stats`.
- Sinh viên:
  - `GET /v1/learning/classes/{c}/practice/session?size=10`, ưu tiên câu đến hạn;
  - `POST …/practice/attempts`, có idempotency key.
- Quyền:
  - kiểm quyền lớp trong cùng transaction (bài học AUD-001);
  - sinh viên lớp khác nhận 403;
  - phiên bị thu hồi giữa transaction bị từ chối.
- Câu trả lời ngắn chấm bằng so khớp sau chuẩn hóa NFC, chữ thường và khoảng trắng; không dùng AI chấm.

**Thống kê**: tỉ lệ đúng theo câu và câu sai nhiều nhất. Lớp dưới 5 người thì chỉ trả số gộp, không trả theo sinh viên.

**Web**:
- Giảng viên: soạn, xem trước như sinh viên, công bố, xem danh sách "trích dẫn không còn khớp" khi có phiên bản mới.
- Sinh viên: phiên ôn tập 10 câu, chấm ngay, nút "Mở trang được trích".

**Kiểm**:
- pytest repository trên DB tạm;
- test quyền;
- vitest;
- mở rộng `apps/web/e2e/learning-features.mjs` trên runtime diễn tập.

Không làm B3.7 (sinh nháp bằng AI), vì cần ngân sách provider.

### E14 — Tiếng Anh: đo trước, rồi nền giao diện (B4.1–B4.3)

**B4.1**:
- Dịch bộ ca dev của `rag_v2_retrieval_probe.py` sang tiếng Anh. Claude dịch trong phiên, không gọi provider. Giữ nguyên unit gold.
- Kiểm bằng code: mỗi ca dịch có cùng `gold_unit_ids` với bản gốc; tệp lưu ở `evals/datasets/rag-v2-en/`.
- Chạy probe và so recall@1/5/10 giữa tiếng Việt và tiếng Anh, lưu kết quả vào `evals/results/b4-1-<stamp>/`.
- **Quy tắc quyết định**:
  - recall@5 tiếng Anh ≥ 90 % của tiếng Việt: B4.5 (câu trả lời tiếng Anh) đáng đề xuất;
  - thấp hơn: dừng ở giao diện tiếng Anh, câu trả lời vẫn tiếng Việt.

**B4.2**:
- `apps/web/src/lib/i18n/`: `vi.ts` là nguồn khóa, `en.ts` có kiểu `Record<keyof typeof vi, string>` nên thiếu khóa thì lỗi biên dịch.
- `t(key, params)` thay `{name}`, escape được.
- Cookie `lang` (`vi` mặc định, `en`). `<html lang>` đặt theo cookie ở `app/layout.tsx`. Không đổi route.

**B4.3**:
- Chuyển chuỗi của shell, đăng nhập, chat và lịch.
- Chữ do API trả về (thông báo lỗi, nội dung nguồn) giữ nguyên tiếng Việt, kèm ghi chú "Nội dung nguồn bằng tiếng Việt".

**Kiểm**: `tsc` báo lỗi khi thiếu khóa (test có chủ đích bằng `// @ts-expect-error`), vitest đổi ngôn ngữ, ảnh chụp hai ngôn ngữ ở 4 màn hình.

B4.4 (các màn hình còn lại) để sau, vì khối lượng lớn.

### E15 — Kiểm trên Postgres thật

- **SQL độ mới nguồn**: chạy `freshness_service.py` với cụm Postgres cục bộ mà runtime đang dùng, **chỉ đọc**, và so kết quả với bản DB giả của test. Lệch thì sửa SQL, thêm test.
- **Diễn tập khôi phục**:
  - `infra/cloud/rehearse_restore.py` khôi phục bản sao lưu mới nhất vào DB **mới** `campus_restore_drill_<stamp>`, không bao giờ vào DB đang chạy.
  - Kiểm số dòng các bảng chính và `alembic_version`. Đo thời gian (RTO).
  - Xong thì xóa đúng DB tạm do lượt này tạo; tên phải khớp tiền tố mới được xóa.
- Ghi kết quả vào `PHASE1_COMPLETION` hoặc một tệp bằng chứng mới. restic thật vẫn chờ duyệt tải (mục 6).

### E16 — Chạy tải có số liệu vận hành (A2.8)

- Runtime thử trên cổng riêng, provider giả (`CAMPUS_LOADTEST_FAKE_PROVIDER=1`), không dừng 8015.
- Chạy kịch bản A với 100 người dùng. So số liệu `/v1/admin/operations/status` (p95, lỗi, 429, hàng đợi admission) với số đo của công cụ tải.
- **Tiêu chí**: chênh p95 ≤ 10 %, đếm lỗi khớp, cảnh báo bắn và tự giải quyết đúng luật A3 khi tạo quá tải có chủ đích.

### E17 — Mở rộng bộ giữ lại RAG

- Viết 3 tài liệu tổng hợp kiểu mới:
  - văn bản nhiều điều khoản và tham chiếu chéo;
  - bảng tiêu đề nhiều tầng;
  - thông báo có hạn và ngoại lệ.
- Mỗi tài liệu 6 câu, gold là đoạn nguồn được code kiểm (`--no-llm-check` kiểm gold trước, không tốn hạn mức).
- **Chạy đúng một lần**, không chỉnh mã theo từng câu. Báo điểm cùng bộ cũ (17/18). Lỗi mới ghi vào tài liệu tiến độ RAG để xử lý bằng cơ chế chung.
- Chi phí khoảng 150 lượt gọi provider.

---

## 5. Tiêu chí xong cho cả kế hoạch

1. Mọi gói E0–E17 có commit trên nhánh riêng (hoặc lý do bị chặn có bằng chứng), test đỏ trước và xanh sau, và bằng chứng trong `evals/results/`.
2. `run_full_regression.py --ci` đạt, `tsc` sạch, vitest đạt.
3. `web_acceptance.mjs` đạt toàn bộ trang và luồng, gồm luồng học liệu (E4) và khẳng định số yêu cầu phòng (E1).
4. `BUGFIX_PLAN_20261118.md` mục 6–7 và `FEATURE_PROGRESS_20261117.md` được cập nhật bằng số đo thật.
5. Còn lại phải ghi "chưa đo": người dùng thật, máy chủ cloud, nhà cung cấp OIDC thật.

---

## 6. Vẫn cần đầu vào riêng (đồng ý chung không thay được)

| Mục | Vì sao | Đầu vào tối thiểu |
|---|---|---|
| A1.10 nối HUCE | Cần dữ liệu từ bên ngoài | Issuer, client, redirect URI, tên claim (`OIDC_SIGN_IN_SETUP_20261117.md`) |
| A3.7 kênh cảnh báo thật | Cần bí mật của chủ dự án | Chọn Telegram hoặc email; tự đặt token vào `.env` |
| A4.5 restic, A1.9 Keycloak, A5.5 container CI | Tải phần mềm/image mới | Duyệt tải từng thứ (tên, nguồn, kích thước, sha256 sẽ báo trước) |
| A4.6 kho sao lưu ngoài | Chi phí và tài khoản | Nơi lưu, tài khoản do chủ dự án tạo |
| B2.4 web push | Dữ liệu đi qua dịch vụ push bên thứ ba và cần dependency mới | Xác nhận rõ |
| C1.5 (P2) sinh viên gửi chữ câu hỏi | Quyền riêng tư: cần nội dung đồng ý và thời hạn lưu | Duyệt văn bản đồng ý |
| C2.5 gate sinh câu trả lời hằng tuần, B3.7 | Chi phí định kỳ | Ngân sách |
| Áp migration 0032 vào DB vận hành | Guard migration đòi duyệt hash | Duyệt hash khi E13 xong |
| Giai đoạn 2 (VPS, tên miền) | Chi phí, hạ tầng thật | Lệnh bắt đầu giai đoạn 2 |
| Xóa thư mục `.pytest-tmp-*` | Xóa dữ liệu | Duyệt danh sách do E0 xuất |
| Push, merge các nhánh của kế hoạch này | Quy tắc git | Duyệt push |

---

## 7. Ghi nhận cho thiết kế sau (không thuộc đợt này)

- **Đồ thị quy chế trên v2**: cần trích quan hệ điều khoản từ đơn vị `rag_v2`, fingerprint theo chỉ mục v2, repository riêng và duyệt của người quản trị. Đáng thiết kế riêng khi có nhu cầu thật.
- **Rerank**: tắt có chủ ý theo số đo. Nếu sau này có GPU hoặc reranker nhanh hơn thì đo lại bằng bộ dev và bộ giữ lại trước khi bật.
- **B4.4 và B4.5**: quyết định sau khi có số đo của E14.

---

## 8. Kết quả thực thi (cập nhật cuối ngày 19/11/2026)

Mỗi gói nằm trên nhánh riêng từ `origin/main`; nhánh `integration/e-all-20261119` gộp tất cả (một xung đột ở `app/knowledge/page.tsx`, đã giải bằng tay: giữ cả hai liên kết mới và điều kiện hiện của đồ thị quy chế). Chưa push, chưa merge vào `main`.

| Gói | Nhánh · commit | Kết quả đo được | Khác với thiết kế |
|---|---|---|---|
| E0 | `chore/e0-repo-hygiene` · 704f795 | `.pytest-tmp*/` được bỏ qua; `scripts/maintenance/list_test_temp.py` liệt kê 118 thư mục (2,1 GB, 42 thư mục không đọc được), chỉ xóa tên đã duyệt; 3 test đạt, 1 bỏ qua (symlink) | Danh sách đã xuất ở `infra/local/pytest-tmp-list-20261119.csv`, **chưa xóa gì** |
| E1 | `fix/e1-rooms-availability-batch` · 1e47291 | `GET /v1/rooms/availability` bằng 2 truy vấn; kết quả từng phòng bằng đúng câu trả lời từng phòng (test trên mọi phòng, mọi ngày có lịch); web gọi 1 lần thay vì 34; 75 test Python, 88 test web đạt | — |
| E2 | `fix/e2-rrf-only-trace` · 3c120d9 | trace ghi `RRF_ONLY` khi rerank tắt có chủ ý; ứng viên và thứ tự không đổi; `tests/rag_v2` 753 đạt | — |
| E3 | `fix/e3-hide-policy-graph-link` · 2a67862 | liên kết đồ thị quy chế chỉ hiện khi API trả lời; 2 test đạt | — |
| E7 | `feat/e7-citation-review-status` · 1802756 | `GET /v1/knowledge/source-review-status` (tối đa 20 nguồn, cache 5 phút, xóa khi có rà soát); nhãn "Nguồn quá hạn rà soát" trong ngăn trích dẫn; 21 test Python, 280 test web đạt | **Tra cứu riêng bên cạnh câu trả lời** thay vì ghi vào luồng chat và lịch sử, nên không byte nào của câu trả lời đổi |
| E10 | `feat/e10b-exit-ticket-reminders` · 3c9a5e9, ccdf4f1 | nhắc phiếu ra lớp T−24h và T−2h, chỉ sinh viên chưa nộp, một lần, tôn trọng công tắc mới `exit_tickets`; đã nối vào vòng việc nền của leader; 28 test Python, 16 test web đạt | xếp trên E11 |
| E11 | `feat/e11-source-reminder-switch` · 99208ff | công tắc nhắc nguồn chỉ hiện cho quản trị tri thức; 4 test mới đạt | — |
| E12 | `fix/e12-pwa-clear-on-signout` · eec9910 | đăng xuất gọi `clearPwaCaches` đúng một lần (test đỏ trước, xanh sau) | **Chưa kiểm trên trình duyệt thật** (cần runtime) |
| E8 | `feat/e8-answer-gaps` · e1c077c | mỗi lần từ chối được đếm theo cụm nguồn và lý do, không lưu người/hội thoại/câu hỏi (test quét các cột của bảng); trang `/knowledge/quality`; quyết định có ghi chú, `RESOLVED` cần mã bản phát hành; 37 + 114 + 204 test Python, 5 test web đạt | một loại sự kiện `REFUSED` theo lý do (không tách ABSTAINED/GATE_REFUSED); trang riêng thay vì tab; cũng thêm liên kết "Hiệu lực nguồn" vào `/knowledge` |
| E9 | `feat/e9-release-retrieval-check` · b918f8b | theo dõi mã release đang chạy, gom đổi trong 10 phút, bỏ qua khi >3 lượt chat đang chạy (hỏi lại 3 lần); lần chạy thành công đầu tiên thành baseline, không bao giờ bị lần chạy ghi đè; 702 test đạt | **Chưa chạy thật** (cần model server) |
| E15 | `chore/e15-postgres-checks` · 18294d0 | SQL độ mới nguồn chạy đúng trên Postgres thật (114 nguồn); sao lưu thật 302 s / 566 MB; diễn tập khôi phục 95,6 s, 63 bảng giống hệt, đã dọn; tìm và sửa 2 lỗi (sao lưu dừng vì tệp bị Defender chặn; `--work-dir` tương đối làm hỏng kiểm tra an toàn); 201 test đạt | chưa thử restic/systemd |
| E14 (nền) | `feat/e14-i18n-foundation` · 443f9b0 | từ điển `vi.ts`/`en.ts` có kiểu (thiếu khóa là lỗi biên dịch), nút chuyển ngôn ngữ, cookie `lang`, `<html lang>`; điều hướng, ô tìm kiếm và khung đăng nhập đã dịch; toàn bộ web 147 tệp / 936 test đạt, `tsc` sạch | chỉ đọc cookie ở trình duyệt (trang vẫn tĩnh); **B4.1 (đo truy hồi tiếng Anh) chưa chạy** |
| E17 | `eval/e17-heldout-2` · 38d17e0 | 18 câu trên 3 tài liệu mới (điều khoản tham chiếu chéo, bảng hai tầng, thông báo có ngoại lệ); gold được code kiểm đạt | **Chưa chạy** (cần model nhúng và gateway); chạy đúng một lần, không chỉnh |

### Chưa làm hoặc bị chặn

| Gói | Tình trạng | Lý do cụ thể | Đầu vào tối thiểu |
|---|---|---|---|
| E4 học liệu theo lớp | chưa | Luồng giao diện học liệu đã được kiểm 8/8 ngày 17/11 trên bản diễn tập biệt lập. Việc còn lại là ghi danh `student-local` vào một lớp của runtime vận hành qua API giảng viên, cần runtime 8015 chạy | RAM trống đủ để khởi động runtime |
| E5 phát hành thử, E6 quét virus thật, E16 chạy tải | chưa | cần runtime 8015 + worker nhập liệu + ClamAV. Máy chỉ còn 1,2–2,4 GB RAM trống trên 15,6 GB; launcher cần khoảng 2,6 GB ngoài model server. Tôi không đóng ứng dụng của bạn để lấy RAM | đóng bớt ứng dụng hoặc cho phép dừng thứ gì đó |
| E13 ôn tập | chưa | xem bản đồ tích hợp bên dưới: nhiều điểm chạm vào bộ máy preview/confirm của học liệu, cần quyết định thiết kế nhỏ, không để mã dở dang | thời gian làm riêng |
| E14.B4.1, E17 chạy thật | chưa | cần model nhúng 18081 và gateway 8025 | như E5 |

**Bản đồ tích hợp E13** (đọc từ mã ngày 19/11, theo mẫu "idea cards"):
1. `LearningService.__init__` nhận thêm `practice_offerings`; cờ theo lớp lấy ở `bootstrap/learning.py:78-98` (mỗi tính năng gắn một revision migration; `config.json` hiện tại dùng lưu trữ SQLite nên không cần migration cho bản cục bộ).
2. Đọc: thêm nhóm `PRACTICE_READS` vào `LearningService.query` (`service.py:202-230`).
3. Ghi: thêm hành động vào cơ chế xem trước/xác nhận (`service.py:380-450`) và vào `presentation/learning.py` (schemas `SCHEMAS`, bảng `write_endpoint`), kèm tái phát theo khóa idempotency.
4. Kiểm trích dẫn: dùng `blobs.extract_page(storage_key, page_no)` như `idea_cards.py:71`, rồi `practice.verify_citation` (đã có, 26 test).
5. Postgres: tên bảng trong `COLLECTIONS` của `infra/learning/repository.py`, migration 0032 (cần duyệt hash trước khi áp vào DB vận hành), `practice_schema=True`.
6. Hợp đồng: `tests/learning_entry/test_openapi_contract.py` sẽ đòi cập nhật; thêm test quyền và phiên bị thu hồi giữa transaction.
7. Web: bộ soạn của giảng viên và phiên ôn tập của sinh viên cạnh `ExitTickets.tsx`.
Cần một quyết định nhỏ: bài ôn tập có dùng cùng bước xác nhận như phiếu ra lớp không (đề xuất: có cho giảng viên, không cho sinh viên nộp bài).

Cổng nghiệm thu `web_acceptance.mjs` chỉ thay đổi ở phần đã sửa (số lần gọi khả dụng phòng, trang `/knowledge/quality`) và **chưa chạy lại** vì chưa có runtime.

---

## 9. Cập nhật 20/11/2026 (làm tiếp sau lần báo cáo đầu)

Phần "chưa làm" của mục 8 đã được làm tiếp; trạng thái mới (đã kiểm trên runtime 8015 chạy bản build `frontend-knowledge-eall-20261120-01`, gồm mã của nhánh tích hợp):

| Gói | Kết quả |
|---|---|
| **E13 ôn tập** `feat/e13-practice` · a805c89 | Làm đủ chiều dọc: dịch vụ (`application/learning/practice_sets.py`), 8 route (`presentation/learning_practice.py`), hợp đồng OpenAPI (7 đường dẫn), bootstrap (`practice_offerings`, từ chối lưu trữ PostgreSQL cho tới khi migration 0032 được duyệt), giao diện giảng viên và sinh viên (`PracticeSets.tsx`). 16 test HTTP thật (quyền, ẩn đáp án, trích dẫn sai chặn công bố, chấm, lặp lại ngắt quãng, trùng khóa idempotency, thống kê ẩn dưới 5 sinh viên), toàn bộ bộ học liệu 166 đạt, web 313 đạt, `tsc` sạch. **Lưu trữ**: trạng thái SQLite cục bộ như các tính năng theo lớp khác; bản Postgres cần migration 0032 và chủ dự án duyệt hash |
| **E4 học liệu theo lớp** | `scripts/learning_enroll_local_student.py` (chạy khô mặc định, idempotent) ghi danh `student-local` vào "Lớp SQL 20261104-03" qua chính API (xem trước + xác nhận); sinh viên thấy lớp; luồng `learning` mới trong cổng nghiệm thu đạt |
| **Cổng nghiệm thu trên runtime thật** | `web_acceptance.mjs` toàn bộ: **479 kiểm tra đạt, 0 lỗi** (gồm trang `/knowledge/quality`, khẳng định phòng học ≤ 2 yêu cầu, ẩn liên kết đồ thị quy chế); riêng các luồng sau khi thêm luồng học liệu: 38 đạt, 0 lỗi |
| **E12/E2-PWA kiểm bằng trình duyệt thật** | `scripts/qa/pwa_check.mjs`: service worker đăng ký; sau một phiên dùng không cache nào chứa địa chỉ API; tắt mạng thì hiện trang ngoại tuyến; vào `/login` không còn trang nào trong cache. **Phát hiện**: bản vận hành không có nút đăng xuất (chỉ bản store cũ gọi `logout`), nên việc xóa cache cũng được gắn vào lúc vào trang đăng nhập; thực tế worker chỉ lưu tệp tĩnh và trang ngoại tuyến |
| **B4.1 truy hồi tiếng Anh** | 60 ca dev dịch sang tiếng Anh, gold giống hệt: top 8 **73%** so với **97%** tiếng Việt, top 12 85% so với 97% → theo quy tắc, **dừng ở giao diện tiếng Anh**, câu trả lời vẫn tiếng Việt (`evals/results/b4-1-20261120/`) |
| **E17 bộ giữ lại 2** | Chạy đúng một lần: **16/18 (89%)**. Một ca (tt-04) là lỗi gold của tôi (cấm "40%" nhưng tài liệu có cả hai tỉ lệ); một ca (tt-06) là thiếu sót thật: quy tắc chung trong văn xuôi áp dụng cho ngành không được nêu tên bị từ chối thay vì trả lời bằng quy tắc chung. Cần cơ chế chung (cùng lớp lỗi với R3 nhưng ở văn xuôi), chưa sửa |
| **E9 chạy thật** | xem mục kết quả nightly bên dưới |

Còn lại thật sự: E5 (phát hành thử, cần worker và ≥ 2 GB RAM trống), E6 (ClamAV thật, cần thêm ~1 GB cho `clamd` và khởi động lại API), E16 (chạy tải 100 người) — xem trạng thái ở cuối mục này; ngoài ra các việc cần đầu vào của bạn ở mục 6 và sửa lỗi tt-06 bằng cơ chế chung.

### Kết quả thêm ngày 20/11 (E5, E6, E9, E16)

| Gói | Kết quả (bằng chứng trong `evals/results/`) |
|---|---|
| **E5 phát hành thử** | `scripts/qa/release_trial.mjs`: 8/8 đạt. Tài liệu QA đăng trực tiếp → ACTIVE sau **70 giây**; chỉ mục 9173 → 9176 đơn vị; chatbot trả lời "06:45 … 19:15" kèm trích dẫn; thu hồi → **9173 đơn vị**, chatbot không còn biết dữ kiện bịa. Lần thử đầu bị `ECONNRESET` khi API đổi chỉ mục, tài liệu QA nằm lại ACTIVE vài phút cho tới khi được thu hồi; script nay thử lại tối đa 8 lần và luôn thu hồi trong `finally` |
| **E6 quét virus thật** | ClamAV bật (`upload-scanner: ready`, chữ ký 12,6 giờ): tệp TXT sạch **202**; chuỗi EICAR (dựng trong bộ nhớ, không ghi đĩa) trước đây **503 sau 75 giây**, nay **422 `FILE_REJECTED` ngay** nhờ sửa `ClamdScanner`: tệp bị chính bảo vệ của máy chủ xóa/khóa (winerror 225) là phát hiện, không phải "bộ quét không sẵn sàng". Giới hạn: trên máy này kết quả từ chối đến từ hành động của Defender cộng quy tắc mới, không phải từ phán quyết `FOUND` của clamd (đường đó đã được chứng minh trước đó và bằng test với daemon thật) |
| **E9 chạy thật** | kiểm truy hồi thật lần đầu (120 ca): any 99,2%, top 8 **96,7%**, qua rerank 87,5%; trở thành baseline (tự động, ghi `"auto": true`); thẻ chất lượng trên trang vận hành hiển thị |
| **E16 chạy tải** | 20 sinh viên 100% (p95 6,4 s); 50 sinh viên 100% (p95 11,6 s); **100 sinh viên 90,5%** (19 lượt bỏ cuộc sau 503 "bận", giới hạn 24 lượt đồng thời; p95 13,1 s). Trang vận hành khớp công cụ tải về số lượt (181 = 181). **Lỗi của tôi**: lần chạy đầu truyền PYTHONPATH kiểu POSIX nên công tắc kiểm tải không nạp và **khoảng 65 đến 100 lời gọi thật** (65 dòng nhật ký gateway; 103 bản ghi mới trong sổ cái thật từ 02:23, gồm cả các kiểm thử dùng nhà cung cấp thật sau đó) tới nhà cung cấp trả phí đã xảy ra (ghi trong sổ cái thật; chế độ tính sổ, không giới hạn ngày); phát hiện qua nhật ký gateway, khởi động lại bằng đường dẫn tương đối theo README rồi chạy lại bằng nhà cung cấp giả |

### Tình trạng cuối của máy

Runtime 8015 **đang chạy bản mới** (snapshot `frontend-knowledge-eall-20261120-01`, thay `frontend-knowledge-qa-20261118-04`) với ClamAV bật, worker nhập liệu bật, model server 18081/18082, gateway 8025, Postgres 55437, đúng cấu hình thường (không còn công tắc kiểm tải). Còn lại do kiểm thử: hai tài liệu "QA-scan-check sạch" ở trạng thái `AWAITING_REVIEW` (không phát hành; chủ sở hữu không thể tự từ chối tài liệu mình gửi, cần quản trị viên thứ hai), học viên local đã ghi danh vào "Lớp SQL 20261104-03".

Chưa làm vì cần quyết định hoặc đầu vào: mục 6 (OIDC, kênh cảnh báo thật, tải restic/Keycloak, push web, văn bản đồng ý P2, ngân sách gate hằng tuần, migration 0032, xóa thư mục `.pytest-tmp-*`, push/merge) và sửa lỗi tt-06 của bộ giữ lại 2 bằng cơ chế chung (đụng RAG).

### E14, tiếp (20/11): màn hình đã chuyển sang tiếng Anh

Đã có tiếng Anh cho: điều hướng và ô tìm kiếm, khung và trang đăng nhập (cả trang đăng nhập vận hành, trước đây thiếu nút đổi ngôn ngữ), **hộp thư thông báo**, **màn hình phòng học** (khoảng 80 chuỗi, gồm chuỗi có tham số), **thời khóa biểu theo tuần**. Mỗi màn có một test tiếng Anh; web 157 tệp / 965 test đạt, `tsc` sạch. Phương pháp và công cụ trích/thay chữ nằm ở `scripts/i18n/` (README) để các màn còn lại làm cơ học: **chat (`ChatPanel`, ~110 dòng), phiếu hỗ trợ/dịch vụ, học liệu, quản trị tri thức, trang chủ**. Câu trả lời của chatbot giữ tiếng Việt (B4.1: truy hồi tiếng Anh kém hơn).

**Cập nhật cuối 20/11:** thêm tiếng Anh cho toàn bộ khu chat (khung chat, phản hồi, lịch sử, trích dẫn), màn dịch vụ học vụ / hồ sơ của tôi (chữ được lưu vào hồ sơ đã gửi vẫn giữ tiếng Việt), phần còn lại của khung ứng dụng (tiêu đề, biển báo vai trò, nhãn trợ năng) và trang quyền riêng tư. Còn tiếng Việt: trang chủ, danh sách hồ sơ cũ, phần sinh viên của học tập, và các màn cho cán bộ, giảng viên, quản trị, tri thức. Câu trả lời của chatbot vẫn là tiếng Việt (xem B4.1).

### Quyết định của chủ dự án ngày 21/11/2026

- **Đăng nhập (mục 1):** dùng cách hiện có (tài khoản thử và đăng nhập chủ dự án) cho đến khi HUCE cung cấp OIDC. Không làm gì thêm.
- **Kênh cảnh báo (mục 2):** đã nối Telegram (bot `@ca247_bot`, chat riêng của chủ dự án). Token nằm trong `data/secrets/alert-telegram-token.key` (git bỏ qua), `.env` chỉ giữ đường dẫn và `chat_id`. Đã gửi một tin thử qua `build_notifier` và chủ dự án xác nhận đã nhận (21/11/2026). Token cần đổi (đã lộ trong chat). Cảnh báo tự động đã bật trong tiến trình API (launcher đọc `CAMPUS247_ALERT_*` từ `.env`); cảnh báo thật `loop_blocked` lúc khởi động ngày 21/11/2026 đã tới Telegram và chủ dự án xác nhận. Watchdog ngoài (systemd, Linux) vẫn chưa chạy vì máy này là Windows.
- **P2 (mục 3):** đã duyệt văn bản (`docs/P2_CONSENT_TEXT_DRAFT_20261121.md`). Đã làm: `application/knowledge/gap_reports.py`, `create_gap_report_router` (gắn trong `scripts/knowledge_platform.py`), hộp thoại "Báo thiếu thông tin" (`apps/web/src/features/chat/GapReport.tsx`), 17 test API và 4 test web. Chưa làm: gom cụm theo nội dung bằng embedding và màn đọc các báo cáo trong `/knowledge/quality` (API `GET /v1/knowledge/gap-reports` đã có). Chưa chạy trên runtime 8015 (cần khởi động lại để nạp router).
- **Ngân sách gate hằng tuần (mục 4):** 1000 lời gọi/tuần. Gate C2.5 vẫn chưa được viết (đợi lên cloud); số này sẽ là trần khi viết.

### Migration 0032 (câu hỏi ôn tập trên PostgreSQL), 21/11/2026

- **Tệp:** `services/api/migrations/versions/0032_learning_practice.py`, nối sau 0031. Chỉ tạo mới bốn bảng `learning.practice_sets`, `practice_items`, `practice_attempts`, `practice_reviews` (cùng dạng `tenant_id, record_key, payload jsonb` với các bảng học tập khác), chỉ mục, một hàm và các trigger. Không sửa, xóa hay cập nhật dữ liệu có sẵn; `downgrade()` từ chối.
- **CSDL tự chặn những gì ứng dụng đã chặn:** bộ câu hỏi chỉ tăng revision, giữ nguyên danh tính và nguồn, công bố rồi thì đóng băng (chỉ cho chuyển sang RETIRED); câu hỏi giữ danh tính, bộ và vị trí, chỉ đổi khi bộ còn là bản nháp; câu trả lời chỉ ghi thêm, không sửa; chỉ ghi câu trả lời cho bộ đã công bố; không xóa bản ghi nào. Khóa ngoại nối bộ với buổi, bản bài giảng và tài liệu của cùng lớp.
- **Mã nối:** `PostgresLearningRepository(practice_schema=...)`, `PRACTICE_COLLECTIONS`, `bootstrap/learning.py` (bỏ lệnh từ chối PostgreSQL; nay đòi revision 0032 đã xác minh), `LEARNING_REVISIONS` và hai tập revision của bản diễn tập học tập có thêm `0032`.
- **Hash đã duyệt** (chủ dự án duyệt trong chat ngày 21/11/2026): `cf9d3a1d8e2d98c8a31165570b7a415ae40d28e99da639eaca880d0574d07a7f`, ghi trong `infra/local/rag-fixture/fixture.py` (`REVIEWED_ADDITIONS`). Sửa tệp này sau đó sẽ làm guard dừng trước khi ghi CSDL.
- **Kiểm chứng:** `tests/unit/learning/test_practice_migration_0032.py` (cấu trúc, không cần CSDL) và `tests/learning_entry/test_practice_postgres.py` (bật bằng `CAMPUS247_LEARNING_PG_TEST=1`): tạo một CSDL tạm `campus_practice_test_*`, áp 0023 đến 0032, chép lớp học tạo qua API vào PostgreSQL rồi chạy cả luồng ôn tập qua HTTP trên đó, thử trực tiếp bằng SQL rằng CSDL từ chối sửa câu trả lời, xóa bản ghi, sửa bộ đã công bố, sửa câu hỏi của bộ đã công bố, đổi vị trí câu hỏi và ghi câu trả lời cho bản nháp; xong thì xóa CSDL tạm.
- **Chưa áp vào CSDL vận hành, và hiện cũng không có chỗ để áp:** CSDL vận hành (cổng 55437) đang ở revision 0022 và chưa có schema `learning`; mô-đun học tập đang chạy trên SQLite, nơi câu hỏi ôn tập đã hoạt động. 0032 chỉ cần khi chuyển mô-đun học tập sang PostgreSQL (giai đoạn cloud), lúc đó áp cả chuỗi 0023 đến 0032.
