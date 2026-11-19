# Học liệu theo buổi học — triển khai và bằng chứng ngày 05/11/2026

Học liệu đã chạy trong ứng dụng Campus tại cổng 8027 với cơ sở PostgreSQL mới, bốn tài khoản tổng hợp, ClamAV và trình đọc PDF.js thật. Tại cùng điểm vào đã kiểm được đăng nhập, chat, lịch sử và lưu nháp dịch vụ. **Chưa nghiệm thu với thiết bị và người dùng thật; chưa triển khai vào kho Campus đang dùng ở cổng 8015 hoặc production.**

Người dùng đã yêu cầu dừng sử dụng subagent; công việc tiếp tục do agent chính thực hiện. Các thay đổi có sẵn của repository, dữ liệu và bằng chứng cũ được giữ nguyên. Không commit/push, không xóa file, không reset DB, không đổi firewall/ACL/cổng của kho đang dùng.

## Phần đã xây

- Quản trị học kỳ, môn, lớp, phân công giảng viên và sinh viên; thao tác quản trị quan trọng dùng preview và xác nhận trên server.
- Buổi học, đổi thứ tự, nhiều bài trong một buổi, dùng lại bài trong cùng lớp; cập nhật và ẩn có kiểm tra revision.
- Upload stream PDF và PPTX ≤50 MiB, ≤500 trang, 2 GiB/lớp gồm bản gốc và bản xem; mặc định 10 GiB/kho local. Hệ thống giữ trước dung lượng khi nhận tệp và không tự xóa file hoặc phiên bản.
- Intent có hạn, hủy an toàn khi stream và xác nhận hoàn tất có khóa chống trùng. Lượt chưa nhận byte có thể nhả chỗ dự trữ, còn byte đã ghi vẫn được giữ. Pipeline checksum, scan và parse dùng job bền vững, thời hạn xử lý tổng 120 giây, lease 3 phút và tối đa 3 lượt. Attempt cũ không ghi kết quả lên attempt mới.
- Nháp, xem trước, công bố, hẹn giờ và thu hồi. Giao diện dùng múi giờ của lớp khi nhập và xem thời điểm. Máy chủ lưu UTC và kiểm lại phân công khi đến lịch. Giảng viên có thể chọn bản đã công bố trước đó của cùng học liệu làm bản hiện hành khi thu hồi. Lựa chọn được ràng buộc với lần xác nhận mới. Bản gốc, lịch sử và thông báo được lưu bền vững.
- Xem dọc, ngang hoặc từng trang, zoom 50–300%, vừa trang hoặc vừa rộng, xoay, tìm chữ, ảnh thu nhỏ, mục lục, tập trung và tải bản gốc theo quyền. Thanh công cụ điện thoại có phần mở rộng. Liên kết web trong PDF hiện địa chỉ đích và chờ người đọc chọn mở.
- Range có xác thực, HEAD, ETag/If-Range, transport yêu cầu byte giới hạn; không có URL public cho blob. Bản xem tối ưu có page tree cân bằng, kiểm chữ và drawing operators từng trang; tải gốc giữ nguyên byte. PDF có chữ ký được bỏ qua bước tối ưu.
- Đọc tiếp riêng theo người và phiên bản, đặt nhãn bookmark và giải quyết xung đột. Hàng chờ giữ vị trí mới nhất khi lần lưu trước lỗi hoặc chậm. Khi kết nối lại, trình đọc thử lưu vị trí và tải tiếp khoảng byte đang chờ. Liên kết mở đúng trang và ghi chú riêng trên phiên bản cũ còn quyền.
- Ghi chú PAGE/TEXT/REGION gắn vào phiên bản và rendition. Chủ ghi chú có thể xem trước và xác nhận gửi một bản sao trong mục hỏi đáp cho giảng viên hiện hành. Bản gốc vẫn riêng tư. Hỏi đáp có xác nhận của giảng viên và thông báo kiểm lại quyền. Chỉ người hỏi được xác nhận đổi phạm vi, các phản hồi vốn riêng vẫn riêng.
- Chỉ dẫn đọc mở từng khoảng trang ở đúng phiên bản, lưu lịch sử chỉnh sửa và dấu đã xem riêng theo sinh viên và revision. Phiên trình bày dùng SSE và kiểm tra định kỳ. Mất kết nối trả người theo dõi về vị trí cá nhân và yêu cầu chọn theo dõi lại.
- AI giải thích và đề xuất câu tự kiểm tra theo một trang. Bước kiểm chứng kiểm cả lời giải thích lẫn câu tự kiểm tra. Chỉ tài khoản tổng hợp và nguồn có mã băm được duyệt mới được gửi qua gateway; mặc định tắt. Đã xác minh trên nhà cung cấp thật với PDF tổng hợp không chứa dữ liệu cá nhân.
- Tải PPTX, quét, chuyển thành PDF tĩnh bằng LibreOffice trong WSL/bubblewrap, kiểm số slide, quét lại bản xem, xem trước rồi công bố. Bản gốc và rendition bất biến, có mã băm riêng. Tệp có macro, OLE, liên kết ngoài hoặc công thức trong workbook nhúng bị từ chối; biểu đồ có dữ liệu tĩnh trong workbook nội bộ được kiểm hỗ trợ.
- Hợp đồng OpenAPI riêng 65 operations và 36 schemas, nối vào OpenAPI chính. Mã identity, menu và runtime đã tích hợp. Health điểm vào có trạng thái worker và lần tick thành công gần nhất, giới hạn ở dữ liệu vận hành.
- Snapshot/verify/restore SQLite tổng hợp vào đường dẫn mới, bảo toàn metadata, blob và identity. Đã khôi phục riêng schema học liệu PostgreSQL cùng blob vào cơ sở mới; đối chiếu nguyên vẹn metadata và từng mã băm. Bản thử PostgreSQL này không sao chép kho chat hoặc tài khoản.

## Ma trận thực hiện so với kế hoạch

| Hạng mục | Trạng thái và phạm vi bằng chứng |
|---|---|
| T01 viewer/proxy/mobile/corpus | Viewer thật qua proxy Campus diễn tập; chữ Việt, trang ngang, vector, raster; chưa kiểm thiết bị cảm ứng thật |
| T02 identity/phân quyền | Đã kiểm vai trò toàn hệ thống + membership, người ngoài lớp, quyền bị rút, bản nháp/thu hồi, riêng tư và phiên hết hạn |
| T03 metadata/repository/migration | SQLite lifecycle/restart; toàn bộ Alembic đến 0025 chạy trên PostgreSQL riêng; đã kiểm asyncpg, Range, idempotency, ràng buộc rendition và 30 người đọc đồng thời |
| T04–T08 quản trị/buổi/upload/worker/publication | Đã xây và kiểm local; scanner thật cho PDF, job/retry/lease/quota và xác nhận có test |
| T09 content/Range/download | Đã kiểm qua proxy Campus diễn tập ở 8027; bản tải giữ nguyên MIME và byte gốc; viewer luôn nhận PDF |
| T10 reader | Mã VIEW01–VIEW12; kiểm browser desktop/mobile mô phỏng; cảm ứng thật/iOS và các PDF đại diện của trường chưa đo |
| T11 trạng thái/bookmark/thông báo | Đã kiểm lưu bền vững, revision conflict, tính riêng tư và mở lại trong browser |
| T12 tích hợp/recovery/E2E | Cùng một điểm vào Campus diễn tập đã kiểm chat, dịch vụ, đăng nhập và học liệu. Restore SQLite và PostgreSQL đạt. Log kỹ thuật ghi mã lỗi, thời gian xử lý, kết quả công bố và dung lượng không chứa nội dung riêng. |
| T13 dùng thử R1 | Đã chuẩn bị hai lớp và 12 tài khoản người tham gia tổng hợp trên 8029. Còn cần nhóm thật, thiết bị thật và điểm vào truy cập từ thiết bị. [Kịch bản và phiếu đo](LEARNING_MATERIALS_UAT_20261105.md) |
| T14–T15 ghi chú/hỏi đáp | Đã kiểm với hai sinh viên: hỏi riêng, trả lời, xem trước và chia sẻ có xác nhận, giữ phản hồi riêng, thông báo mở đúng trang; kiểm phiên cũ, revision, idempotency và rút quyền |
| T16 PPTX | Converter và sandbox thật đạt trên corpus tổng hợp ba slide, có chữ Việt, bảng, biểu đồ và công thức; chưa suy rộng fidelity sang mọi bản PowerPoint |
| T17 chỉ dẫn đọc | API và UI gắn phạm vi trang với phiên bản cố định. Dấu đã xem tách theo sinh viên và revision. Giảng viên đọc được lịch sử nội dung đã giao. |
| T18 trình bày | Hai sinh viên theo dõi cùng lúc, tạm rời và quay lại độc lập. Khi mất kết nối, người theo dõi trở về vị trí riêng. Sau kết nối lại, họ tự chọn theo dõi. |
| T19 AI | Hai ca trả lời có dẫn đúng trang, một ca thiếu nguồn bị từ chối, hai ca sai quyền/sai đoạn chọn không gọi provider. Năm lượt HTTP thật qua gateway có accounting. Chưa đánh giá chất lượng diện rộng. |
| T20 kiểm liên phần và dùng thử R2–R4 | E2E với PPTX và hỏi đáp qua Campus diễn tập đã đạt. Chưa có thiết bị và người dùng thật. |

FR01–FR07, FR09–FR14 có bằng chứng local theo phạm vi trên; FR14 chạy qua composition Campus thật với kho mới, chưa đo lại ở cổng 8015. FR08 còn phần thiết bị thật. Kết quả kỹ thuật local chưa thay thế nghiệm thu R1–R4 với giảng viên và sinh viên.

## Bằng chứng kỹ thuật

Các ca tổng hợp dùng source spans, metadata và hash được mã kiểm tra. Luồng browser dùng UI và session thật trên các kho SQLite và PostgreSQL tách riêng. Khả dụng và hiệu quả học tập còn chờ phép đo với người dùng thật.

| Kiểm tra | Kết quả | Vị trí tái hiện/bằng chứng |
|---|---|---|
| Backend, identity, learning HTTP/privacy/PPTX, runtime regression | 135 ca và 2 ca con đạt, gồm hủy khi stream, hết hạn, chống trùng, quyền chia sẻ ghi chú, chỉ dẫn, múi giờ theo lớp và thu hồi có bản thay thế | `tests/unit/identity`, `tests/learning_entry`, `tests/unit/learning`, `tests/learning_review`, `tests/unit/learning_pptx`, `tests/operations/test_knowledge_platform_runtime.py`; basetemp `.tooling/learning-technical-suite-20261105-04` |
| Backend, API và ranh giới tài khoản đọc tiếp | 61 passed và 2 subtests sau thay đổi đồng bộ | `tests/learning_entry`, `tests/unit/learning`, `tests/learning_review`; basetemp `.tooling/learning-resume-tests-20261105-01` |
| Frontend | 50 ca đạt trên 9 tệp, gồm đổi múi giờ và kiểm giờ bị trùng hoặc bị bỏ qua khi đổi giờ mùa hè | `pnpm --filter web exec vitest run src/features/learning src/lib/data/api/learning-gateway.test.ts` |
| TypeScript | exit 0 | `pnpm --filter web exec tsc --noEmit --incremental false` |
| Bản build frontend | Build, TypeScript và sinh trang tĩnh đạt | `infra/local/knowledge-platform-20261023/frontend-knowledge-learning-20261105-14` |
| Browser qua UI và auth thật của harness | 18 bước đạt, 0 page errors; tiếng Việt chọn được, mục lục dẫn đúng trang ngang, touch mô phỏng, thumbnail/search/xoay/focus; vừa rộng trang ngang tại 360px | [report.json](../.tooling/learning-browser-20261105-09/report.json); 3 trang/89,420 bytes, trang đầu 1,012 ms, không phải benchmark NFR01 |
| Ruff phần learning/recovery/contracts | All checks passed | Lệnh ở dưới; không khẳng định lint toàn repository vốn có thay đổi khác |
| OpenAPI | 65 operations của learning khớp router, schema refs, security, HEAD và binary hợp lệ | `tests/learning_entry/test_openapi_contract.py`, `contracts/openapi/v1/learning.openapi.pptx.json` |
| Validator OpenAPI chính | VALIDATION_OK, 455 local refs. Bộ đếm legacy 35 đếm phần hợp đồng chính | `contracts/tools/validate_openapi.py` |
| PostgreSQL 0023 | 19/19 checks pass | [continued-report.json](../.tooling/learning-pg-single-20261105-02/continued-report.json) |
| PostgreSQL 0024/view source binding | 8/8 checks pass | [views-report.json](../.tooling/learning-pg-single-20261105-02/views-report.json) |
| Campus diễn tập và PostgreSQL đến 0025 | 21 bước browser PPTX trên build 09, 0 lỗi trang; 6 nhóm kiểm tra cùng điểm vào gồm chat và dịch vụ | [Browser PPTX](../.tooling/learning-browser-campus-pptx-20261105-01/report.json), [hồi quy điểm vào](../.tooling/learning-campus-rehearsal-20261105-01/entry-regression-01.json) |
| Campus PowerPoint trên build 14 | 24 bước qua browser, 0 lỗi trang. Kiểm chuyển đổi, tải nguyên bản, Range, neo ghi chú, chia sẻ riêng, lịch sử chỉ dẫn, mất mạng giữa phiên trình bày và giao diện mobile mô phỏng | [Báo cáo browser](../.tooling/learning-browser-campus-technical-pptx-20261105-02/report.json) |
| Campus PDF trên build 14 | 30 bước qua browser, 0 lỗi trang. Kiểm hẹn giờ theo lớp từ trình duyệt UTC, truy cập trước khi công bố, cảnh báo và cách ly tab liên kết ngoài, chọn bản thay thế khi thu hồi, vị trí đọc và ghi chú của bản cũ | [Báo cáo browser](../.tooling/learning-browser-campus-technical-20261105-05/report.json) |
| Campus PDF, hai sinh viên theo dõi và lịch sử phiên bản | 21 bước browser, 0 lỗi trang; mở liên kết cũ và ghi chú bằng phiên đăng nhập thứ hai, không nhảy sang bản mới, từ chối Range sau thu hồi | [Browser PDF](../.tooling/learning-browser-campus-20261105-05/report.json) |
| Campus PDF, mất mạng và xung đột đọc tiếp | 22 bước browser trên build 10. Trang đã tải vẫn hiển thị khi ngắt mạng, kết nối lại lưu vị trí, revision cũ chờ lựa chọn của người đọc và bookmark có nhãn mở đúng trang | [Browser reader sync](../.tooling/learning-browser-campus-reader-sync-20261105-02/report.json) |
| Nháp và lịch sử PPTX trên build 10 | Kiểm riêng trên hai bài đã tạo. Giảng viên mở được nháp sau chuyển đổi. Sinh viên mở đúng slide và ghi chú bản cũ, giữ nguyên hash PPTX và bị chặn Range sau thu hồi. Lượt tự động trước dừng ở mốc chờ 60 giây | [Kiểm tra tiếp](../.tooling/learning-pptx-history-resumed-20261105-02/report.json), [lượt hết thời gian chờ](../.tooling/learning-browser-campus-pptx-reader-20261105-02/report.json) |
| Chuẩn bị nhóm dùng thử | Hai lớp có bài đã công bố. 26 ca Range xác nhận quyền riêng từng lớp, học viên hai lớp và ngưng ghi danh | [Pilot seed report](../.tooling/learning-campus-rehearsal-20261105-02/pilot-seed-report.json) |
| Tắt học liệu để phục hồi | Worker tắt, khả năng đọc tắt, byte trả 503; chat/dịch vụ vẫn hoạt động, bản công bố đang có không đổi | [Flag report](../.tooling/learning-campus-rehearsal-20261105-01/flag-disabled-report.json) |
| Sandbox WSL/bubblewrap | 11 phép thử thật đạt, gồm cách ly network và không còn tiến trình con khi hủy | [Sandbox report](../.tooling/learning-sandbox-proof-20261105-01/run-02/report.json) |
| PPTX thật | 3 slide, bao gồm slide ẩn; chữ, bảng, giá trị biểu đồ và công thức khớp bộ kiểm; chuyển đổi khoảng 13,6 giây trong lần đo riêng | [Conversion report](../.tooling/learning-pptx-live-20261105-02/report.json), [ảnh browser](../.tooling/learning-browser-campus-20261105-01/pptx-chart.png) |
| AI giới hạn ở trang đã chọn | 5/5 ca đạt; hai lượt hỏi có nguồn mất 2,06 và 2,31 giây; năm HTTP ghi sổ, không có nguồn thật hoặc định danh cá nhân | [AI report](../.tooling/learning-ai-live-20261105-01/report.json) |
| Scanner thật | Clean PDF pass; EICAR stdin bị từ chối exit 1 | [scanner verification](../.tooling/learning-clamav-20261104-01/scanner-verification-1793811435034182900.json); không lưu EICAR thành file |
| Snapshot/restore đang dùng trong harness | 4 blobs/7 files verified ở cả hai bản sao | `.tooling/learning-recovery-evidence-20261105-02`, `.tooling/learning-recovered-evidence-20261105-02`; nguồn không bị ghi đè |
| Restore PostgreSQL và blob | Schema học liệu từ snapshot nhất quán; khớp chính xác dữ liệu lớp, phiên bản, reader state, ghi chú, hỏi đáp, thông báo và ba blob | [Recovery report](../.tooling/learning-pg-recovery-20261105-01/report.json) |

### Hiệu năng có giới hạn môi trường

[Browser performance report](../.tooling/learning-performance-balanced-20261105-01/browser-performance.json) dùng component React đã build, desktop Chromium, CPU i7-10850H, RAM 16 GiB, viewport 1280×1000, CDP 20 Mbps/RTT 50 ms; HTTP cache tắt.

- NFR01: p95 **1.337 giây**, 20 mẫu, PDF 100 trang ~10.22 MiB; tính từ request PDF đầu tới trang đầu render. Mốc ≤3 giây đạt trong harness này.
- NFR02: chuyển trang đã nạp p95 **33.5 ms**, 20 mẫu desktop. Điện thoại thật chưa đo.
- NFR04: PDF 500 trang tối đa 10 canvas khi khảo sát; JS heap tối đa ~11.6 MB, canvas backing ~14.9 MB. Không phải toàn bộ RAM renderer/GPU.
- NFR03: 30 sinh viên tổng hợp, 300 request metadata. SQLite ASGI p95 **82,5 ms**; [PostgreSQL TCP loopback](../.tooling/learning-pg-live-20261105-01/metadata-performance-01.json) pool tối đa 5 kết nối p95 **259,3 ms** (đạt 500 ms). Pool tối đa 36 kết nối không đạt, p95 **1.287,8 ms** trong phép thử mở rộng kết nối lạnh. Không đo tải byte hoặc đăng nhập trong số này.
- NFR05: browser mô phỏng 360px/390px; NFR06 có restart/restore; NFR07 fail closed khi auth/storage/scanner thiếu. Không suy rộng thành thiết bị thật hoặc production.

Các phép đo chậm trước khi cân bằng page tree được giữ ở `.tooling/learning-performance-20261104-01`; không xóa hoặc thay kết quả fail bằng kết quả mới.

Khi chạy hai luồng browser PDF và PPTX cùng lúc, PDF vẫn ở bước quét sau 60 giây và lượt kiểm kết thúc theo timeout của browser test. Lượt PDF chạy riêng đạt đủ 30 bước. Hai lượt này chưa tạo số liệu thời gian xử lý khi tải hỗn hợp. [Lượt đồng thời](../.tooling/learning-browser-campus-technical-20261105-04/report.json)

## Mở bản kiểm thử local

Điểm vào kiểm thử kỹ thuật là [Campus 8027](http://127.0.0.1:8027/learning). Nhóm thử dùng [Campus 8029](http://127.0.0.1:8029/learning) với tài khoản và cơ sở riêng. Hai điểm vào dùng cùng bản frontend 3028. PostgreSQL 56457 lắng nghe trên loopback. Có thể dùng harness 8026 để đối chiếu SQLite.

Bốn tài khoản thử học liệu nằm trong `.tooling/learning-campus-rehearsal-20261105-01/learning/credentials.json`. Tài khoản hồi quy chat/dịch vụ nằm trong `student/credentials.json` cùng bundle. Đây là tài khoản thử cục bộ; không đưa nội dung credentials, identity hay snapshot vào log, chat hoặc commit.

Lệnh chạy lại từ repository, sau khi kiểm cổng không thuộc tiến trình khác:

```powershell
.venv/Scripts/python.exe -B scripts/knowledge_platform_frontend.py serve --name frontend-knowledge-learning-20261105-14 --port 3028
$env:CAMPUS_LEARNING_AI_ENABLED='false'
$env:CAMPUS247_RAG_ENGINE='v1'
.venv/Scripts/python.exe -B scripts/knowledge_platform.py serve --learning-rehearsal .tooling/learning-campus-rehearsal-20261105-01/rehearsal.json --port 8027 --frontend-port 3028
```

Không chạy song song thêm tiến trình trên các cổng đang dùng. Trình chạy chỉ nhận bundle tổng hợp tường minh, kiểm host, cổng, tên DB, tên user, data directory và revision 0025 cho từng kết nối. Không nạp kho tri thức đang dùng hoặc gọi provider từ điểm vào này. [Biên bản chuẩn bị DB](../.tooling/learning-campus-rehearsal-20261105-01/rehearsal.json) ghi đúng đích.

Config PostgreSQL của diễn tập dùng ClamAV 1.5.4 pin SHA256, `pdf_web_view=true`, sandbox PPTX và quota 10 GiB. Các đường dẫn scanner/database/certs/temp phải còn ở workspace. CVD có phiên bản tại thời điểm thử; trước dùng file thật cần quy trình cập nhật và giám sát phù hợp.

`CAMPUS_LEARNING_CONFIG` chọn cấu hình cho composition Campus thông thường. Đặt `CAMPUS_LEARNING_ENABLED=false` và khởi động lại tiến trình đã xác minh để tắt module mà không đổi kho. PostgreSQL + PDF view yêu cầu schema 0024 hoặc 0025; PPTX yêu cầu 0025 và runtime được pin. `CAMPUS_LEARNING_AI_ENABLED` mặc định `false`; nhánh bật yêu cầu gateway có egress/accounting và `ai_synthetic_source_sha256` là tập con của nguồn tổng hợp đã xác minh. Kiểm tra lại quyền và mã băm trước gửi nội dung. Không tự đổi provider, DB hoặc chạy migration lúc khởi động.

## Kiểm tra và khôi phục

```powershell
$env:LEARNING_TEST_ROOT='C:\Users\Duong Vinh\Vinh\.tooling'
.venv/Scripts/python.exe -B -m pytest tests/unit/identity tests/learning_entry tests/unit/learning tests/learning_review tests/unit/learning_pptx tests/operations/test_knowledge_platform_runtime.py --basetemp=.tooling/learning-repeat-NEW-RUN-ID -p no:cacheprovider -q
pnpm --filter web exec vitest run src/features/learning src/lib/data/api/learning-gateway.test.ts
pnpm --filter web exec tsc --noEmit --incremental false
.venv/Scripts/python.exe -B contracts/tools/validate_openapi.py
.venv/Scripts/python.exe -B -m ruff check services/api/src/campus247/application/learning services/api/src/campus247/infrastructure/learning services/api/src/campus247/presentation/learning.py scripts/learning_snapshot.py scripts/export_learning_openapi.py tests/learning_entry
```

Thay `NEW-RUN-ID` bằng tên mới chưa tồn tại trong workspace. Đặt `LEARNING_BROWSER_RUN` mới trước khi chạy `node apps/web/e2e/learning-integrated.mjs`. Với Campus diễn tập, đặt `LEARNING_TEST_URL=http://127.0.0.1:8027` và `LEARNING_TEST_CREDENTIALS` đến file tài khoản tổng hợp trong bundle. Chọn corpus đã khai báo gold qua `LEARNING_TEST_PDF` hoặc `LEARNING_TEST_PPTX`. Dùng `LEARNING_TEST_VERSION_HISTORY=1` để kiểm bản cũ, ghi chú và thu hồi. Dùng `LEARNING_TEST_READER_SYNC=1` để kiểm mất mạng, xung đột vị trí và nhãn bookmark. Profile phiên được giữ trong phạm vi local và loại khỏi Git.

Snapshot hiện có kiểm lại được bằng lệnh đọc:

```powershell
.venv/Scripts/python.exe -B scripts/learning_snapshot.py verify --source .tooling/learning-recovery-evidence-20261105-02
.venv/Scripts/python.exe -B scripts/learning_snapshot.py verify --source .tooling/learning-recovered-evidence-20261105-02
```

`snapshot --source <config.json> --destination <thư mục mới>` và `restore --source <snapshot> --destination <thư mục mới>` luôn từ chối đích có sẵn. Utility giới hạn ở SQLite tổng hợp. Online SQLite backup lấy metadata nhất quán; blob đã commit là bất biến và được đối chiếu hash. Nếu snapshot có upload RECEIVING thì từ chối và giữ bằng chứng để chạy lại sau khi upload kết thúc. Artifact mồ côi/partial không được sao lưu như blob đã commit; chúng vẫn được giữ ở nguồn, không cleanup. Bản phục hồi giữ trạng thái processing để lease có thể được worker xử lý sau hạn.

Khi lỗi: xem mã upload/job và trạng thái worker. Logger `campus247.learning.metrics` ghi dòng JSON cho kết quả xử lý, thời gian, dung lượng còn lại, công bố và lỗi yêu cầu; không chứa tài liệu hoặc định danh người đọc. Khi tắt feature, giữ toàn bộ kho. Migration chỉ tiến. Utility `learning_snapshot.py` chỉ dành cho SQLite; phép khôi phục PostgreSQL riêng dùng `pg_dump --schema=learning` trên snapshot đã xuất, đối chiếu blob bất biến, rồi `pg_restore` vào DB mới đã xác minh và so sánh lại metadata cùng mã băm. Không dùng đích đã có dữ liệu.

## Phần thực sự còn bị chặn

1. **Campus đang dùng ở 8015**: [log cũ](../.tooling/learning-postgres-20261104T130227664533/postgres.log) báo không bind được PostgreSQL ở 55437. Cổng này thuộc dải Windows dành riêng lúc kiểm. Đã kiểm đầy đủ thành phần Campus qua bản diễn tập 8027 và PostgreSQL mới ở 56457. Kho cũ, wrapper gốc và cấu hình hệ điều hành vẫn được giữ. Triển khai vào kho thật cần môi trường được chỉ định, sao lưu và kiểm riêng.
2. **Thiết bị và người dùng thật**. Người dùng ưu tiên hoàn chỉnh kỹ thuật trước. T13/T20 hiện dừng ở bước chuẩn bị, với hai lớp ở 8029 và kịch bản đo dành cho giảng viên, sinh viên và thiết bị thật. [Kịch bản UAT](LEARNING_MATERIALS_UAT_20261105.md)
3. **Mở rộng từ mẫu tổng hợp**: PPTX mới kiểm trên corpus đại diện nhỏ; fidelity trên bài giảng thật còn phải nghiệm thu. AI mới kiểm trên trang tổng hợp cho phép, chưa đánh giá rộng và chưa có phạm vi egress cho học liệu thật.

Bản kỹ thuật R1–R4 đã build và kiểm trong môi trường diễn tập. T13/T20 còn phần đo khả dụng với giảng viên, sinh viên và thiết bị thật. Điểm vào Campus đang dùng và production là phạm vi triển khai riêng.
