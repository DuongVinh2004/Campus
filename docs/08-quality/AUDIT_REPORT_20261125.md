# Báo cáo kiểm định Campus 24/7 — 2026-11-25

Nhánh `chore/audit-20261125`, tạo từ HEAD của `feat/ui-audit-upgrade-20261125` (nhánh đó còn 5 commit chưa merge và runtime 8015 chạy thẳng từ thư mục làm việc). Hàng nghìn thay đổi dở của người dùng trong `apps/web/**`, `docs/04-architecture/*` được giữ nguyên, không commit lẫn. Không push, không merge.

Bằng chứng nằm ở `infra/local/audit-20261125/` (log, JSON, ảnh chụp); các script probe đã commit cùng thư mục. Mọi ca RAG ở đây là ca do mô hình viết có gold kiểm bằng mã; mức hài lòng của người dùng thật: **chưa đo**.

Ràng buộc đã giữ: không gọi provider trả phí (nên phần chất lượng câu trả lời bị chặn, xem mục "Chưa đo"), không đổi RAG, không tăng giới hạn provider 5 s, không ghi vào DB thật (migration và restore chạy trên cụm Postgres tạm 55498/55499 rồi xóa), không in bí mật.

## Bảng 16 tiêu chí

| # | Tiêu chí | Kết luận | Bằng chứng | Ghi chú |
|---|---|---|---|---|
| 1 | Build & kiểu | Đạt có lưu ý | `tsc --noEmit` exit 0 (`tsc.log`); `next build` exit 0, 41 s; cảnh báo CSS duy nhất đã sửa (`next-build2.log`: 0 warning); `compileall services/api/src` exit 0 | Không có ESLint web; ruff không có config/CI: 1722 cảnh báo (727 thứ tự import, 144 F401, 80 BLE001, 15 F841). F821 ở `presentation/identity.py:73` chỉ là annotation (vô hại). S608 đã đọc: tên bảng từ hằng số, không phải injection. B023 đã đọc: closure gọi ngay trong vòng lặp, dương tính giả. File sinh bị track: `apps/web/tsconfig.tsbuildinfo`, 42 file `.log` trong `evals/results/` |
| 2 | Kiểm thử tự động | Đạt có lưu ý | vitest 169 file / **992 đạt**, 0 skip (200 s). pytest toàn bộ (`run_full_regression.py`): main **5669 đạt, 2 lỗi, 65 skip, 5 xfail**; nhóm stream-a/b/c, staff-12: 42+57+109+38 đạt. Native OCR + ClamAV thật: **7/7 đạt**. QA gate trang: **444 kiểm đạt, 2 lỗi**. `evals/validate_contracts.py`: 562 ca, 36 kịch bản red-team hợp lệ | 2 lỗi pytest: `tests/architecture` (vi phạm lớp L6) và `tests/rag_v2/test_l22_event_loop.py` (lỗi khi máy đang build/vitest song song, chạy riêng 9/9 đạt → nhạy tải, L7). `e2e-live/*.pw.ts` 5/5 lỗi trên 8015 (L14). Skip chủ yếu: chỉ chạy Linux/POSIX, cần ClamAV bundle, Postgres 5433 |
| 3 | Chức năng theo vai trò | Đạt có lưu ý | Đăng nhập thật 8 tài khoản (sinh viên ×2, cán bộ ×2, giảng viên, quản trị học liệu, chủ tri thức, cộng tác viên): 200, đúng vai trò. QA gate quét 56 trang × desktop/mobile/dark. Đặt phòng: preview → xác nhận 2 lần cùng khóa trả **cùng** booking (BK-261127-ED0B), thiếu khóa 422, có trong audit, đã hủy lại | Chat có câu trả lời mô hình, tải tệp lên (PDF giảng viên, tài liệu tri thức) **chưa chạy** lượt này (xem "Chưa đo"). Lúc bắt đầu runtime báo "Kho HUCE chưa sẵn sàng" (M6) |
| 4 | Phân quyền & xác thực | Đạt có lưu ý | `authz_probe.json`: ma trận 9 vai trò × 14 endpoint đúng (sinh viên/giảng viên 403 ở staff/admin/knowledge; cán bộ 200 staff, 403 admin; cộng tác viên chỉ thấy documents; ẩn danh 401). IDOR: sinh viên khác đọc hồ sơ → 404, qua route staff → 403. Token giả 401; đăng xuất rồi dùng lại token 401; đăng nhập khác origin 403. Cookie `HttpOnly; SameSite=Strict`, 1 giờ. Khóa đăng nhập 5 lần sai/phút/tài khoản, so sánh hằng thời gian, scrypt | Không có `Secure` trên cookie và đăng nhập mật khẩu sẽ 403 sau Caddy (H1). GET không giới hạn tốc độ (40 GET /v1/notifications → 40×200, theo thiết kế); `GET /v1/students/me/schedule` ẩn danh trả 422 trước 401 (L12) |
| 5 | Bảo mật ứng dụng | Đạt có lưu ý | Header bảo mật thiếu → **đã sửa** (M1). SSRF bộ cào: chỉ https `huce.edu.vn`, cổng 443, IP đã phân giải phải `is_global` và được ghim, ≤5 redirect kiểm lại, giới hạn 5/50 MB (`infrastructure/knowledge/fetch.py:24-41`). Quét bí mật bằng regex trên file track + lịch sử thêm file: không có khóa thật (chỉ token giả trong test); bundle web không chứa bí mật. GitHub Actions ghim SHA | `pnpm audit`: 19 (3 critical, 4 high) — tất cả ở công cụ dev (vitest 2.1.9, tinypool, happy-dom, vite) trừ `source-map-js` (high, build-time qua postcss). OSV cho `uv.lock` (149 gói): 1 gói — `opentelemetry-api 1.45.0` (2 GHSA, sửa ở 1.45.1/1.45.2). Chủ dự án đã hoãn cả hai nhóm (M5). `next` cài trong node_modules 16.3.8 ≠ lockfile 16.4.5 (M4) |
| 6 | An toàn AI/RAG | Chưa đo một phần | Đo được (không tốn phí): recall truy hồi trên hold-out 188 ca: đúng chunk @5 92,6 %, **@12 97,3 %**, @40 100 %; trích dẫn nguyên văn @12 76,6 % (từ khóa 63,8 %) — trùng baseline 14/11, không hồi quy. Test an toàn offline trong regression đạt (poisoning, egress, output guard, tool safety). Giới hạn provider 5 s giữ nguyên (`scripts/run_public_rag.py:150`). Hành động ghi: mô hình chỉ tạo nháp, ghi thật qua preview/xác nhận/idempotency/audit (đã thử đặt phòng) | Chất lượng câu trả lời, từ chối, trích dẫn khớp nguồn trên runtime, hội thoại dài/đồng thời: **bị chặn** vì cần gọi provider trả phí |
| 7 | Dữ liệu | Đạt có lưu ý | `alembic upgrade head` 0→0032 trên cụm tạm: 97 bảng. Downgrade dừng ở 0032 theo thiết kế (21/32 migration forward-only). DB trống thiếu extension `vector` → upgrade lỗi ở 0009 (M2). Backup thật bằng `infra/cloud/backup.py` (555 MB, 340 s, chỉ đọc DB sống) → verify checksum ok → `pg_restore` vào cụm tạm: 63 bảng, `knowledge_chunk` 6228 dòng; 7 SQLite khôi phục `integrity_check ok`; bản sao đã xóa. SQLite sống: `quick_check ok`, 0 vi phạm FK. Dữ liệu demo DEMO-2026HK1-01 khớp đủ lô (44 tài khoản, 178 hồ sơ, 160 booking…) | Log API không chứa tên đăng nhập/mật khẩu/token (grep 0 trùng) |
| 8 | Giao diện & trải nghiệm | Đạt có lưu ý | 4 vai trò × 1360/768/375 px + dark: không tràn ngang (overflow 0), không khóa i18n thô, `lang="vi"`; ảnh chụp `a11y/*.png`, `qa-pages/*.png` | Tiêu đề thanh trên cắt "…" ở 375 px (h1 bên dưới vẫn đủ chữ — chấp nhận). CLS kém ở /schedule, /rooms, /admin (M3) |
| 9 | Truy cập (a11y) | Đạt có lưu ý | Script trong trang (repo không có axe): 0 nút/link/ô nhập không tên thật (các mục báo đều nằm trong `<details>` đóng), 0 ảnh thiếu alt, 0 id trùng, có `aria-live`/`role=status` mỗi trang; dialog lịch: Esc đóng, giữ focus trong dialog, **focus không vào dialog khi mở → đã sửa** (M7) | Mục tiêu < 24 px: link "Mở chatbot…" ở /login, "Của tôi" ở /staff, checkbox trang tri thức (L2, L3). < 44 px (AAA) còn nhiều trên desktop. Tương phản dark: /learning 29 đoạn chữ < 4.5:1 (L5) |
| 10 | Hiệu năng & tải | Chưa đo một phần | Web vitals lab (`web_vitals.log`): LCP ≤ 2,5 s mọi trang (chat lạnh 2,47 s, còn lại < 1,1 s), TTFB ≤ 0,5 s; JS lạnh /chat 1,5 MB, chunk lớn nhất 514 KB (146 KB gzip). RAM runtime: model server 2,9 GB, API 0,87 GB, frontend 0,19 GB, Postgres 0,1 GB; máy còn ~1 GB trống | CLS (M3). Một mẫu /rooms TTFB 6,7 s khi máy đang chạy regression. Tải 100 người, khởi động lạnh: **chưa đo** lượt này |
| 11 | Độ tin cậy & vận hành | Không đạt (lúc bắt đầu) → đã khôi phục | `/health/ready` lúc đầu: `degraded`, `rag_v2.warm=failed`, model server 18081 không chạy, `campus.py status` → ConnectError. Sau khi khởi động model server với thư mục trạng thái mới: `ready`, `warm=ready` | Không có giám sát tự khởi động lại model server trên Windows (M6). Một số SQLite ở journal `delete` trong khi API chạy nhiều worker (L11). Cấu hình mẫu thiếu nhiều biến (L10) |
| 12 | Chất lượng mã | Đạt có lưu ý | 0 TODO/FIXME; file lớn nhất: `StaffTicketQueue.tsx` 1411 dòng, `agent/nodes/definitions.py` 1101, `ChatPanel.tsx` 1059, `scripts/knowledge_platform.py` 939 (route + nghiệp vụ trong script). 1 vi phạm lớp | Xem ruff ở mục 1. Không refactor trong lượt này |
| 13 | Tài liệu & truy vết | Đạt có lưu ý | Mọi đường dẫn trong README tồn tại. Skill `campus247` nêu sai vi phạm lớp, thiếu điều kiện `vector` và `PYTHONPATH` worker → **đã sửa** (53655e2) | `e2e-live` và `campus.py` (nhánh lịch sử) còn nói cổng 3115; CI tên "Web Unit & A11y Gates" nhưng không có axe |
| 14 | CI/CD & phát hành | Đạt có lưu ý | `ci.yml`: catalog, regression portable, tsc + vitest, AI gate, release manifest, kiểm closure phụ thuộc; `security.yaml`: 4 test bảo mật; actions ghim SHA; `main` bảo vệ (PR + 6 check). Rollback: `infra/cloud/restore.sh`, `backup.py restore` (đã thử khôi phục ở mục 7) | Thiếu: `next build`, `pnpm audit`/`pip-audit`, lint Python, e2e. Bước "Validate Lockfiles Integrity" chỉ in sha256, không so (L13) |
| 15 | Quyền riêng tư & tuân thủ | Đạt có lưu ý | Hội thoại giữ 30 ngày (`conversation/messages.py:145`), đánh giá câu trả lời 180 ngày, có API đồng ý/yêu cầu quyền riêng tư (`presentation/privacy_*.py`), log không chứa dữ liệu đăng nhập, file credentials bị gitignore và chưa từng vào lịch sử | Nguồn tri thức là tài liệu công khai HUCE; chính sách `RESEARCH_AND_DATASET_POLICY.md` yêu cầu ghi giấy phép — chưa kiểm từng tài liệu. Lịch sử git còn email/đường dẫn cá nhân (đã biết, chủ dự án hoãn) |
| 16 | Chi phí & giới hạn | Đạt có lưu ý | Giới hạn mỗi lời gọi 5 s, 28.000 byte vào, 1000 token ra; cloud: 5 USD / 2000 lời gọi mỗi ngày, gateway trả 429 khi chạm trần (`scripts/gateway_sidecar.py:140`); chat 30 yêu cầu/phút/tài khoản | Profile local không có trần chi tiêu ngày (`infra/profiles/local.toml:23`, M8). Tiêu thụ token thực tế lượt này: 0 (không gọi provider) |

## Phát hiện theo mức độ

### Nghiêm trọng
Không có.

### Cao
- **H1 — Đăng nhập mật khẩu sẽ hỏng sau Caddy (giai đoạn cloud).** Tái hiện bằng đọc mã: `scripts/knowledge_platform.py:691` từ chối mọi `request.client.host` không phải loopback; uvicorn 0.52.1 mặc định `proxy_headers=True`, tin `X-Forwarded-For` từ 127.0.0.1 (`uvicorn/config.py:220,357`); `infra/cloud/Caddyfile.example` proxy từ chính 127.0.0.1 → `client.host` thành IP người dùng → 403. Cookie `auth_token` không có `Secure`. Nguyên nhân: kiểm "local" dựa vào IP sau khi proxy đã viết lại. Trạng thái: **chưa sửa** — cần chủ dự án quyết định cloud dùng đăng nhập nào (mật khẩu local hay OIDC) và thử thật sau Caddy. Không ảnh hưởng chạy local.

### Trung bình
- **M1 — Thiếu header bảo mật trên 8015** (clickjacking app đã đăng nhập). `curl -D - http://127.0.0.1:8015/login` không có X-Frame-Options/CSP frame-ancestors/nosniff/Referrer-Policy. **Đã sửa** ở `1a3ff3d` (`scripts/runtime_routes.py` `apply_security_headers`, gọi trong middleware; giữ CSP `sandbox` sẵn có), test `tests/test_runtime_routes.py` 9/9. **Chưa có hiệu lực trên tiến trình đang chạy** cho tới khi API được khởi động lại.
- **M2 — Chuỗi migration không chạy trên DB trống nếu chưa có extension `vector`.** `bash infra/local/audit-20261125/migration_roundtrip.sh` → `type "vector" does not exist` ở 0009. Chưa sửa: sửa migration làm đổi hash nguồn mà guard yêu cầu chủ dự án duyệt; đã ghi điều kiện vào hướng dẫn kiểm.
- **M3 — CLS kém.** `node infra/local/audit-20261125/web_vitals.mjs`: /schedule 0,27 (desktop) / 0,58–0,94 (mobile), /rooms 0,52, /admin 0,41. `cls_probe.mjs`: nguồn chính là lưới tuần hiện ra sau khi tải dữ liệu (0,50), banner kho nguồn thêm ~0,05. Chưa sửa: đổi bố cục trạng thái tải ở màn hình đang có việc UI dở.
- **M4 — node_modules lệch lockfile:** `apps/web/node_modules/next` 16.3.8, `pnpm-lock.yaml` 16.4.5 (bản vá #29). Snapshot frontend đang chạy dùng Next cũ. Chưa sửa: `pnpm install --frozen-lockfile` thay thư viện mà tiến trình frontend 3015 đang nạp; cần dừng frontend rồi build lại snapshot.
- **M5 — Phụ thuộc có CVE:** dev tools (vitest/tinypool critical, happy-dom/vite high), `source-map-js` high (build-time), `opentelemetry-api` 1.45.0. Chủ dự án đã hoãn; báo lại để quyết định.
- **M6 — Runtime 8015 suy giảm khi không ai để ý:** model server 18081 không chạy (stderr trống), chatbot báo "Kho HUCE chưa sẵn sàng" trên mọi trang. Đã khôi phục bằng cách khởi động model server (thư mục `infra/local/campus-run-20261125-02/models`). Nguyên nhân gốc tắt chưa rõ; không có supervisor.
- **M7 — Dialog thêm sự kiện lịch không nhận focus khi mở** (WCAG 2.4.3). **Đã sửa** ở `49722da`, test `WeekSchedule.test.tsx` kiểm `toHaveFocus`.
- **M8 — Profile local không có trần chi tiêu ngày** (`daily_usd_cap = "0"`). Quyết định của chủ dự án.

### Thấp
- **L1** Tailwind quét cache `.next-stitch-redesign` → cảnh báo CSS và một rule hỏng mỗi lần build. **Đã sửa** `410e8f7` (.gitignore), build lại 0 cảnh báo.
- **L2** Link "Mở chatbot và xem trạng thái kho" ở /login < 24 px (QA gate). Không sửa: `OwnerLogin.tsx` đang có thay đổi dở của người dùng.
- **L3** "Của tôi" ở /staff, checkbox xác nhận ở /knowledge/documents, /knowledge/sources < 24 px.
- **L4** Nhiều điều khiển < 44 px trên desktop (AAA), ví dụ /chat 11/27.
- **L5** Tương phản chế độ tối: /learning 29 (sinh viên) / 20 (giảng viên) đoạn chữ < 4,5:1; /schedule 1.
- **L6** Vi phạm lớp: `presentation/oidc.py` import `infrastructure.identity.oidc*`; `tests/architecture` đỏ.
- **L7** `tests/rag_v2/test_l22_event_loop.py` lỗi khi máy bận, đạt khi chạy riêng → nhạy tải.
- **L8** Ruff 1722 cảnh báo, không có config/CI lint Python; không có cấu hình mypy.
- **L9** File sinh bị track: `apps/web/tsconfig.tsbuildinfo`, 42 `.log` trong `evals/results/`.
- **L10** `.env.example` chỉ có 8/29 trường settings; 20 biến `CAMPUS247_*` đọc trong mã không có trong file mẫu nào.
- **L11** SQLite `actor-state`, `conversations`, `answer-quality`, `gap-reports`, `source-reviews` ở journal `delete` trong khi API chạy nhiều worker (nguy cơ `database is locked`; chưa đo).
- **L12** `GET /v1/students/me/schedule` ẩn danh trả 422 thay vì 401.
- **L13** CI thiếu `next build`, audit phụ thuộc, lint Python, e2e; bước "lockfile integrity" chỉ in hash.
- **L14** `e2e-live/*.pw.ts` dùng đăng nhập demo cũ (`Mã tài khoản`/SV001): 5/5 lỗi trên 8015. `playwright.live.config.ts` trỏ 3115 → **đã sửa** `c3b2d15` (mặc định 8015); chính các spec chưa viết lại.

## Commit trong lượt này (chưa push)

| Commit | Nội dung |
|---|---|
| `1a3ff3d` | Header bảo mật từ origin 8015 (M1) |
| `410e8f7` | Bỏ qua `.next-stitch-*` (L1) |
| `49722da` | Focus vào dialog lịch (M7) |
| `c3b2d15` | Playwright live trỏ 8015 (L14) |
| `53655e2` | Script probe kiểm định + cập nhật hướng dẫn kiểm (tiêu chí 13) |

Kiểm lại sau sửa (`infra/local/audit-20261125/final-web.log`): `tsc` exit 0; vitest 169 file / 992 đạt; `tests/test_runtime_routes.py` + `tests/architecture`: 11 đạt, 1 lỗi (chính là L6, có từ trước). `next build` sau sửa: exit 0, 0 cảnh báo. Pytest toàn bộ không chạy lại sau sửa: các thay đổi Python chỉ ở `scripts/runtime_routes.py` và một dòng middleware, đã có test riêng.

## Chưa đo / bị chặn

| Mục | Bằng chứng chặn | Đầu vào tối thiểu để làm tiếp |
|---|---|---|
| Chất lượng câu trả lời RAG (eval `rag_natural_eval`, gate `--quick`), chat thật trên trình duyệt, từ chối/trích dẫn trên runtime, hội thoại dài/đồng thời | Mọi lượt chat gọi provider trả phí; yêu cầu kiểm định cấm chi tiền | Chủ dự án duyệt số lời gọi: 3 (luồng chat của QA gate) hoặc ~600 (gate `--quick`) |
| Thử tải 100 người, thời gian khởi động lạnh | Cần khởi động lại runtime với fake provider và tắt limiter; runtime 8015 hiện do một phiên khác khởi động lúc 21:43 | Một khung giờ được phép dừng runtime |
| `KNOWLEDGE_PLATFORM_LIVE_TESTS` | Ghi tenant test vào Postgres sống 55437 | Đồng ý ghi tenant test vào DB sống, hoặc dựng cụm riêng có dữ liệu |
| Tải tệp lên qua trình duyệt (PDF giảng viên, tài liệu tri thức), duyệt tài liệu | Duyệt sẽ công bố vào kho chatbot; lượt này không làm | Tài liệu test được phép công bố, hoặc chỉ thử tới bước "chờ duyệt" |
| Lighthouse | Không có trong repo (đã đo lab vitals bằng Playwright thay) | Cho phép cài Lighthouse |
| HSTS/TLS, Caddy thật, đăng nhập sau proxy (H1) | Chưa có VPS/tên miền | Giai đoạn 2 |
| Mức hài lòng người dùng thật | Chưa có người dùng thật | Thử nghiệm với sinh viên |

## Rủi ro còn lại

- Header bảo mật mới chưa chạy trên tiến trình API hiện tại; Next trong snapshot đang chạy là bản cũ hơn lockfile.
- Runtime 8015 có thể lại mất model server mà không ai biết; chatbot khi đó từ chối mọi câu hỏi.
- Đăng nhập trên cloud chưa chạy được (H1), cần quyết định trước giai đoạn 2.
- Rollback schema chỉ bằng khôi phục backup (migration forward-only); backup/restore đã chạy được nhưng mất ~6 phút cho 555 MB.

## 5 việc nên làm tiếp

1. Quyết định cơ chế đăng nhập cho cloud và sửa H1 (bỏ phụ thuộc vào IP sau proxy, thêm `Secure` khi qua HTTPS), thử thật sau Caddy.
2. Dừng frontend, `pnpm install --frozen-lockfile`, build snapshot mới và khởi động lại API để áp dụng M1/M4; thêm giám sát model server (M6).
3. Duyệt một ngân sách gọi provider nhỏ để chạy lại gate RAG `--quick` và luồng chat của QA gate.
4. Thêm vào CI: `next build`, `pnpm audit --prod`, OSV/pip-audit, ruff với tập luật tối thiểu (F, E9); viết lại `e2e-live` theo đăng nhập thật hoặc bỏ.
5. Giữ chỗ cho lưới lịch/phòng khi tải (M3) và sửa tương phản dark ở /learning (L5), vùng chạm nhỏ (L2, L3).
