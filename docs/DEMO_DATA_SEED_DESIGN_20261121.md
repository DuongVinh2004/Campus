# Thiết kế bộ dữ liệu vận hành mô phỏng — 2026-11-21

Trạng thái: **chủ dự án duyệt toàn bộ ngày 2026-11-21 và đã thực hiện** — kết quả ở mục 6.

Mục tiêu: runtime 8015 có đủ dữ liệu như đang dùng thật cho mọi trang (sinh viên, nhân viên, giảng viên, quản trị), để
dùng thử, demo và kiểm thử. Dữ liệu cần có từ hệ thống HUCE thật mà chưa có kết nối thì được tạo mô phỏng.

## 1. Kiểm định hiện trạng (đọc chỉ-đọc, 2026-11-21)

| Khu vực | Nơi lưu | Đang có | Đánh giá |
|---|---|---|---|
| Kho tri thức RAG | Postgres 55437 | 332 nguồn công khai huce.edu.vn, 558 phiên bản, 6 228 chunk, chỉ mục v2 9 173 đơn vị, 28 nguồn crawl | **Dữ liệu thật công khai, đủ dùng.** Không đụng. |
| Tài khoản | `owner-identity.json`, `student-identity.json`, `staff-identity.json`, `learning-materials-…/identity.json` | 1 chủ, 1 sinh viên (`student-local`), 1 nhân viên, 3 tài khoản học tập (admin/GV/SV) | **Thiếu nhất.** Adapter sinh viên/nhân viên chỉ đọc *một* tài khoản mỗi file. |
| Lịch học, lịch thi | `campus-ops.sqlite3` `ops_schedule` | 117 dòng, chỉ cho `student-local` (7 môn × 15 tuần + 5 kỳ thi) | Có nhưng chỉ 1 người. |
| Phòng | `ops_rooms` | 34 phòng, 9 nhà | Dùng được; có thể mở rộng. |
| Đặt phòng | `ops_room_bookings` | 14, tất cả của `student-local`, do test tạo | Rác kiểm thử. |
| Hồ sơ/yêu cầu | `ops_tickets` (+94 sự kiện) | 21: 5 hồ sơ seed "Sinh viên mô phỏng 01–05" (không có tài khoản), 16 hồ sơ test lặp "Giấy xác nhận sinh viên" | Phần lớn là rác kiểm thử. |
| Thông báo | `ops_notifications` | 76, tất cả của `student-local`, sinh từ test | Rác kiểm thử. |
| Học tập | `learning.sqlite3` (một khối JSON, revision 424) | 12 môn "Môn SQL 2026110x-…", 12 học kỳ "Học kỳ 2026110x-…", 12 tài liệu "Bài giảng SQL joins", 7 câu hỏi | Toàn bộ là dấu vết kiểm thử, không giống thật. |
| Hội thoại chat | `conversations.sqlite3` (175 MB) | 45 657 hội thoại / 80 047 tin: 25 609 của `student-local`, 20 043 của chủ | Rác load-test, làm danh sách lịch sử của 2 tài khoản này vô dụng. |
| Đánh giá câu trả lời, khoảng trống | `answer-quality.sqlite3` | 27 đánh giá, 11 khoảng trống | Ít. |
| Bộ nhớ trợ lý, theo dõi, đồng ý | `actor-state.sqlite3` | 44 trạng thái, 23 chuẩn bị hồ sơ | Ít, từ test. |
| Bàn giao, báo lỗi khoảng trống, rà nguồn | Postgres `handover`, `gap-reports`, `source-reviews` | 0 | Trống. |
| Bảng nghiệp vụ Postgres (`ticket`, `room`, `student_profile`, `user_identity`…) | Postgres | 0 | Runtime 8015 không dùng (dùng SQLite ở trên). Không seed. |

Kết luận: phần tri thức đã thật; phần **người dùng và hoạt động** gần như trống hoặc chỉ là dấu vết test của một tài khoản.

## 2. Nguyên tắc

1. **Không xóa, không ghi đè.** Trước khi ghi, sao lưu từng file SQLite/JSON đụng tới vào
   `infra/local/seed-backup-<thời điểm>/` kèm SHA-256. Tài khoản `student-local`, `staff-local`, chủ và khóa giữ nguyên.
2. **Ghi rõ là mô phỏng.** Mọi bản ghi seed mang thẻ `seed_batch = DEMO-2026HK1-01` và nhãn "mô phỏng"
   (quy tắc repo: không đưa fixture ra như dữ liệu trường). Giao diện đã có nhãn `LOCAL_SYNTHETIC`; giữ nguyên.
3. **Đi qua code nghiệp vụ thật.** Seed gọi các service/store mà runtime dùng (`CampusOpsService`, learning service,
   provisioning script…), không chèn SQL tay, để kiểm quyền, audit, quét ClamAV và ràng buộc vẫn chạy.
4. **Lặp lại được, gỡ được.** Một script, RNG cố định, có `--dry-run` (in số lượng sẽ tạo), chạy lại không nhân đôi
   (khóa idempotency theo `seed_batch`), có `--remove-batch` chỉ gỡ đúng bản ghi mang thẻ (chỉ chạy khi chủ bảo).
5. **Không đụng RAG** (splitter, embedding, ngưỡng, prompt, chỉ mục) và không gọi API trả phí trừ mục 5.3 nếu được duyệt.

## 3. Bộ dữ liệu đề xuất: "Học kỳ 1 năm học 2026–2027"

Mốc thời gian: học kỳ bắt đầu 07/09/2026, hôm nay là tuần 12, thi cuối kỳ 04–16/01/2027. Lịch sử hoạt động rải từ
tháng 9 đến hôm nay; lịch tương lai rải đến hết tháng 1/2027.

### 3.1 Tài khoản (cần code: adapter nhiều tài khoản)

| Vai trò | Số lượng | Ví dụ tên đăng nhập |
|---|---|---|
| Sinh viên | 40, thuộc 4 khoa × 2 lớp (CNTT, Xây dựng DD&CN, Kiến trúc, Kinh tế xây dựng), khóa 66–68 | `sv.demo01` … `sv.demo40` |
| Nhân viên hỗ trợ | 4 (Phòng Đào tạo, Phòng CTSV, Quản trị thiết bị, Thư viện) | `nv.demo01` … |
| Giảng viên (học tập) | 6 | `gv.demo01` … |
| Quản trị học tập | 1 | `qt.hoctap.demo` |
| Cộng tác viên tri thức | 1 (dùng `provision_knowledge_contributor.py` sẵn có) | `ctv.demo01` |

Họ tên, mã SV (`SIM66…`), email `@synthetic.huce.edu.vn` đều bịa và qua bộ kiểm `DemoSeedPacker.validate_record`.
Mật khẩu sinh ngẫu nhiên, băm như tài khoản hiện có, ghi vào một file credentials cạnh file identity (không in ra chat).

Thay đổi code cần: `LocalStudentIdentityAdapter` và `LocalStaffIdentityAdapter` đọc thêm file danh sách
`students-directory.json` / `staff-directory.json` (cùng định dạng, cùng cách băm, cùng kiểm UUIDv7 và tenant), file cũ
vẫn chạy như hiện nay. Không nới xác thực; thêm test đăng nhập đúng/sai/nhầm vai trò cho từng adapter.

### 3.2 Lịch và phòng

- Chương trình theo lớp: mỗi lớp 6–7 học phần với mã, tên, giảng viên, phòng, tiết (bảng 4 ca hiện có); mỗi sinh viên
  nhận lịch của lớp mình + 1–2 học phần tự chọn. ~40 × 100 ≈ 4 000 dòng lịch, ~200 dòng lịch thi.
- Phòng: thêm khoảng 30 phòng (nhà H4, H6, phòng thí nghiệm vật liệu, xưởng kiến trúc, sân thể thao) → ~64 phòng; vài
  phòng `MAINTENANCE`.
- Đặt phòng: ~150 lượt (quá khứ: đã dùng/đã hủy kèm lý do; tương lai: đã xác nhận), không trùng giờ, đúng giờ mở cửa.

### 3.3 Hồ sơ, yêu cầu, thông báo

- ~180 hồ sơ, đủ loại dịch vụ có trong code (giấy xác nhận SV, phúc khảo, hỗ trợ thủ tục, …) và đủ trạng thái
  `SUBMITTED / IN_REVIEW / NEED_INFO / RESOLVED / REJECTED`, có người xử lý, hạn xử lý (một phần quá hạn để trang nhân viên
  có việc), chuỗi sự kiện trao đổi `STUDENT_REPLY` / `STAFF_REPLY` hợp lý theo thời gian.
- Thông báo sinh ra từ chính các sự kiện trên (đặt phòng, hồ sơ, nhắc lịch) — không bịa rời.
- Bàn giao ca giữa nhân viên: ~10.

### 3.4 Học tập

- 1 học kỳ "HK1 2026–2027", 8 học phần / 12 lớp học phần, mỗi lớp có giảng viên và 25–40 sinh viên ghi danh.
- Tài liệu: ~40 file PDF/PPTX **do script sinh** (bài giảng, đề cương, bài tập; nội dung học thuật chung, có dòng
  "Tài liệu mô phỏng"), tải lên qua đường quét ClamAV thật, có phiên bản, hướng dẫn đọc.
- Hoạt động: hỏi–đáp trong lớp (~60 câu hỏi, ~90 trả lời), đánh dấu, ghi chú, trạng thái đọc, câu hỏi luyện tập
  (lưu theo cách runtime đang cấu hình).

### 3.5 Trợ lý cá nhân và tri thức

- Bộ nhớ trợ lý, mục theo dõi, lựa chọn đồng ý (privacy) cho mỗi sinh viên, đa dạng (có người từ chối lưu bộ nhớ).
- Chuẩn bị hồ sơ (document request preparation) ở các bước khác nhau.
- Cộng tác viên tri thức gửi 3–5 tài liệu **công khai thật** của HUCE vào hàng chờ duyệt (không tài liệu bịa, vì duyệt xong
  chúng vào chỉ mục RAG).

## 4. Cách làm

1. Nhánh `feat/demo-data-seed` từ HEAD hiện tại (không đổi sang `main` vì runtime chạy từ thư mục làm việc).
2. Code: adapter nhiều tài khoản + test; `scripts/seed_demo_campus.py` + `scripts/demo/campus_2026hk1.yaml` (manifest).
3. Chạy `--dry-run`, rồi dừng API ~5 phút (khối JSON học tập không chịu được ghi song song), sao lưu, seed, khởi động lại.
4. Kiểm: đếm bản ghi theo `seed_batch`; đăng nhập 1 tài khoản mỗi vai trò và đi các trang chính trên trình duyệt;
   `scripts/qa/web_acceptance.mjs`; test API/web liên quan.
5. Commit trên nhánh; push/merge chỉ khi chủ duyệt.

## 5. Các quyết định của chủ dự án

| # | Câu hỏi | Đề xuất |
|---|---|---|
| 5.1 | Tạo ~52 tài khoản mô phỏng và sửa adapter đăng nhập để đọc danh sách tài khoản | **Duyệt** |
| 5.2 | Dấu vết test cũ (45 657 hội thoại load-test, 12 môn "Môn SQL…", 16 hồ sơ lặp, 14 đặt phòng, 76 thông báo của `student-local`) | **Để nguyên**, dùng tài khoản demo mới sạch. Phương án khác: sao lưu rồi chuyển dấu vết test sang file lưu trữ (cần lệnh rõ của chủ) |
| 5.3 | Lịch sử chat cho tài khoản demo: (a) không seed; (b) chạy ~40 câu hỏi thật qua RAG + nhà cung cấp trả phí (ước tính 40–120 lượt gọi; sẽ đo trên 3 câu đầu và báo trước khi chạy hết) | **(b)** — câu trả lời và trích dẫn là thật; không bịa câu trả lời AI |
| 5.4 | Mở rộng kho tri thức bằng crawl thêm trang huce.edu.vn | **Chưa làm** (đụng chỉ mục RAG; kho hiện đủ). Làm riêng nếu chủ muốn |
| 5.5 | Dừng API ~5 phút lúc seed | **Duyệt** |

Ngoài phạm vi (cần kết nối HUCE thật, không thể seed thành "thật"): SSO/OIDC, bảng điểm, lịch cá nhân, tiếp nhận hồ sơ và
đặt phòng thật của trường. Các trang này sẽ chạy bằng dữ liệu mô phỏng và vẫn ghi rõ là mô phỏng.

## 6. Kết quả thực hiện (2026-11-21)

Mọi bản ghi seed thuộc lô `DEMO-2026HK1-01`; receipt từng bước ở `infra/local/seed-demo-2026hk1/`, bản sao lưu trước khi
ghi ở `infra/local/seed-backup-*` (bản dữ liệu gốc trước seed: `seed-backup-20261121T111216Z` và `…T111232Z`).

| Khu vực | Đã tạo | Đường ghi |
|---|---|---|
| Tài khoản | 40 sinh viên (8 lớp, 4 khoa), 4 cán bộ Một cửa (`campus-directory.json`); 6 giảng viên + 1 quản trị học tập (identity học tập); 1 cộng tác viên tri thức `ctv.demo01` | file danh bạ mới + script provisioning có sẵn |
| Phòng, lịch | +28 phòng (tổng 62); 4 657 dòng lịch (lịch học 15 tuần, thi giữa/cuối kỳ, sự kiện cá nhân) | `scripts/seed_demo_campus.py ops` |
| Hồ sơ | 178 hồ sơ, 842 sự kiện (trả lời, ghi chú nội bộ, đổi trạng thái), 14 quá hạn trong hàng chờ | như trên |
| Đặt phòng, thông báo | 160 lượt đặt phòng (đã dùng/đã hủy/sắp tới), 775 thông báo, 793 dòng audit | như trên |
| Học tập | 1 học kỳ, 8 học phần, 13 lớp học phần, 78 ghi danh, 55 tài liệu PDF (quét ClamAV thật, công bố), ~230 lượt đọc/đánh dấu/ghi chú, 19 hỏi–đáp có trả lời của giảng viên | API thật (`scripts/seed_demo_learning.py`) |
| Chat | 27 câu hỏi thật qua RAG + nhà cung cấp (23 trả lời có nguồn, 1 trả lời một phần, 2 từ chối an toàn, 1 lỗi hệ thống); 17 đánh giá câu trả lời; tổng 119 lượt gọi gateway | API thật (`scripts/seed_demo_chat.py`) |
| Dịch vụ học vụ | 33 bản nháp hồ sơ cho 25 sinh viên | API thật (`scripts/seed_demo_preparations.py`) |

Sửa lỗi phát hiện trong lúc làm:

- **Tải học liệu lên runtime 8015 không bao giờ xử lý xong** (có từ khi API chạy 2 worker): uvicorn `--workers` trên Windows dùng
  `SelectorEventLoop`, không hỗ trợ `asyncio.create_subprocess_exec`. `infrastructure/learning/blob.py` giờ chạy tiến trình con
  qua luồng phụ (`run_bounded`), giữ nguyên timeout và mã lỗi; test `tests/learning_entry/test_run_bounded.py`.
  (`infrastructure/knowledge/index_builder.py` vẫn dùng asyncio subprocess, chạy trong tiến trình worker riêng — chưa đụng.)
- Tài khoản danh bạ không gửi mã khoa vào phiên: mọi nguồn công khai của kho mang phạm vi khoa `FIT`, mã khoa mô phỏng làm
  RAG lọc hết nguồn (3 câu đầu bị từ chối vì lý do này; đã hỏi lại).

Chưa làm / bị chặn:

- 13 câu chat còn lại (~52 lượt gọi) vượt mức 120 lượt đã duyệt — chờ chủ dự án quyết.
- Tài liệu tri thức trong hàng chờ duyệt: cần tải tài liệu công khai thật từ huce.edu.vn — chờ chủ dự án cho phép tải.
- Bàn giao ca (`/v1/handovers`): runtime 8015 chặn đường này và kho của nó chỉ nằm trong bộ nhớ, nên không seed được bền vững.
- Đồng ý quyền riêng tư, bộ nhớ/theo dõi của trợ lý: trang vận hành không có thao tác tạo; để trống.
- Một phiên bản tài liệu (`IT3090/66IT1`, đề cương) kẹt ở trạng thái quét do lỗi trên; đã tải lại phiên bản mới, bản kẹt giữ làm lịch sử.
- Dấu vết test cũ để nguyên theo quyết định 5.2.
