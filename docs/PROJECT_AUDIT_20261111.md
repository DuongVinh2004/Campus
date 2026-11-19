# Campus 24/7 — kiểm định dự án ngày 11/11/2026

## Phạm vi và kết luận

Yêu cầu trực tiếp: áp dụng prompt kiểm định toàn diện, giữ nguyên mã nguồn, cấu hình và dữ liệu; sau đó ghi lại và tiếp tục tìm vấn đề khác. Báo cáo này ghi nhận phát hiện, không phải bản sửa hoặc phê duyệt phát hành. Tài liệu lịch sử được dùng làm tham khảo, không tạo thêm approval gate.

Runtime local8015 đang chạy, nhưng chưa đủ bằng chứng nghiệm thu toàn dự án. Có lỗi P1 ở ranh giới thu hồi phiên học liệu. Bằng chứng gồm mã nguồn, kiểm thử tổng hợp có kết quả kiểm chứng bằng code, ca tái hiện trong bộ nhớ và GET tới runtime thật. Chưa đo trải nghiệm người dùng thật.

Baseline: HEAD `c52b007976aa2ebae3198807c62cdec0f8243647`; working tree có nhiều thay đổi, file untracked và file đã xóa từ trước. Git status của lượt kiểm định đầu có 1.452 mục và giống nhau trước/sau. Không sửa ứng dụng hoặc dữ liệu. Các đường dẫn bên dưới tương đối với repository; dòng chỉ vị trí quan sát, có thể thay đổi khi mã được sửa về sau.

## Phát hiện lượt 1

### AUD-001 · P1 · Ghi học liệu sau khi phiên bị thu hồi

- Trạng thái: đã tái hiện trong bộ nhớ; chưa sửa.
- Vị trí: `services/api/src/campus247/presentation/learning.py:379,399`; `services/api/src/campus247/application/learning/service.py:388,397`.
- Điều kiện: request xác thực thành công, sau đó phiên bị thu hồi trong lúc chờ transaction.
- Bằng chứng: PATCH tên học liệu trả200 và lưu thay đổi trong repository tổng hợp; request tiếp theo trả401. Router không truyền callback kiểm tra phiên vào command để kiểm lại dưới khóa.
- Tác động: thao tác đang chờ có thể thực thi sau logout/thu hồi phiên.
- Hướng sửa: xác minh lại principal/session/roles trong transaction trước mutation; từ chối và rollback khi không còn quyền. Kiểm cả replay và các lệnh quản trị quan trọng.

### AUD-002 · P2 · Trả byte PDF sau khi phiên bị thu hồi lúc kiểm checksum

- Trạng thái: đã tái hiện với blob tổng hợp trong bộ nhớ; chưa sửa.
- Vị trí: `services/api/src/campus247/presentation/learning.py:468,473,483`.
- Bằng chứng: thu hồi phiên trong `blobs.verify()` vẫn nhận200 và đầy đủ byte tổng hợp riêng; chỉ một lần revalidate trước await.
- Tác động: cửa sổ thu hồi quyền trước khi bắt đầu trả nội dung chưa được đóng.
- Hướng sửa: kiểm lại phiên và quyền phiên bản sau các await, trước response/stream. Ca kiểm chứng không được trả byte sau khi thu hồi ở bước verify.

### AUD-003 · P2 · Cấu hình testing hợp lệ nhưng không khởi tạo được backend

- Trạng thái: đã tái hiện; chưa sửa.
- Vị trí: `services/api/src/campus247/bootstrap/settings.py:25`; `services/api/src/campus247/infrastructure/identity/mock.py:13,18`.
- Bằng chứng: `Settings(_env_file=None, ENVIRONMENT="testing", ...)` hợp lệ, nhưng `create_app` ném `ValueError: Synthetic identity adapter forbidden in environment: testing` trước khi mở ledger.
- Nguyên nhân: Settings dùng `testing`, adapter cho phép `test`.
- Hướng sửa: thống nhất tên và có integration test khởi tạo ứng dụng ở từng môi trường hỗ trợ.

### AUD-004 · P2 · CI chưa cấp điều kiện cho suite học liệu

- Trạng thái: đã tái hiện lỗi setup; chưa sửa.
- Vị trí: `.github/workflows/ci.yml:54`; `tests/unit/learning/test_learning_backend.py:31,33`; `pyproject.toml:60`.
- Bằng chứng: workflow chạy `tests/unit` nhưng không cấp `LEARNING_TEST_ROOT`; ca `LearningTests::test_upload_draft_publication_and_restart` dừng tại setup với yêu cầu thư mục bằng chứng đã tồn tại. Chạy riêng suite accessible-text cũng gặp thiếu đường import `campus247_worker`; thêm đường dẫn cho riêng tiến trình kiểm định mới thu thập được.
- Hướng sửa: chuẩn bị namespace bằng chứng mới, giữ lại output, cấp biến và đường import worker trong CI. Không dùng việc xóa dữ liệu để đạt test.

### AUD-005 · P2 · Verifier dependency không đồng bộ với lock hiện tại

- Trạng thái: verifier và hai test thất bại; chưa sửa.
- Vị trí: `scripts/verify_dependencies.py:23,249`; `pyproject.toml:72`; `tests/unit/dependency_resolution/test_verifier.py:157,209`.
- Hash verifier/pyproject đang neo: `251e0a8fbd1f5910abd30105a3a0e6b63f6ab9a51244d209cfc29848b2dbce46`.
- SHA256 uv.lock quan sát được: `edd5ac6ca92357cc9938e219a108cca24858aa7e3d4fc86e47adcf3265dad452`.
- Đối chiếu TOML độc lập: dependency trực tiếp, root dependency references và requires-dist metadata khớp giữa pyproject và lock. Các thông báo lock drift của verifier không được mặc nhiên xem là drift thực tế: verifier loại pin prerelease khi điều kiện hash không đạt.
- Đây là bất nhất kỹ thuật của verifier với trạng thái hiện tại, không phải kết luận dependency chưa được phép theo quy trình cũ.
- Hướng sửa: đối soát closure/hash/version hiện tại rồi cập nhật evidence và kiểm chứng verifier; không tắt bảo vệ hoặc bỏ kiểm tra để đạt test.

### AUD-006 · P2 · Nhánh privacy legacy báo trạng thái thiếu biên nhận

- Trạng thái: chứng minh từ mã; không đi nhánh này ở frontend knowledge-platform8015; chưa sửa.
- Vị trí: `apps/web/src/app/privacy/page.tsx:33,98,116`; `services/api/src/campus247/application/privacy/requests.py:11`.
- Điều kiện: không bật knowledge-platform/unified UI; API consent/request lỗi.
- Bằng chứng: catch giữ optimistic consent; request xóa dùng `DELETE_DATA` trong khi API nhận `DELETION`, sau lỗi vẫn thêm request local ở trạng thái processing.
- Hướng sửa: dùng enum đúng, trạng thái pending/error rõ ràng, chỉ báo đã tiếp nhận sau receipt máy chủ. Không tạo lịch sử giả khi API lỗi.

### AUD-007 · P2 · Một số security test không kiểm implementation ứng dụng

- Trạng thái: chứng minh từ mã; chưa sửa.
- Vị trí: `tests/security/test_ssrf_and_links.py:17`; `test_no_sensitive_egress.py:16`; `test_knowledge_poisoning.py:15`; `test_web_boundaries.py:44,48`.
- Bằng chứng: ba nhóm đầu dùng hàm bảo vệ viết ngay trong file test; bài cookie dựng FastAPI endpoint mẫu riêng. Test có thể đạt dù implementation sản phẩm bị hỏng.
- Hướng sửa: chạy cùng payload qua adapter/endpoint thật và kiểm phủ định; giữ test fixture như bằng chứng bổ sung thay vì suy ra mức an toàn của runtime từ nó.

### AUD-008 · P2 · Ba vi phạm ranh giới kiến trúc

- Trạng thái: test kiến trúc thất bại; AST xác định ba import; chưa sửa.
- Vị trí: `services/api/src/campus247/application/learning/service.py:39,40` import infrastructure blob/metrics; `services/api/src/campus247/presentation/learning.py:32` import infrastructure metrics.
- Hướng sửa: port/callback cho scanner/metrics, cấp implementation ở bootstrap. Tiêu chí: test boundary đạt với cùng quy tắc hiện tại.

### AUD-009 · P3 · Interpreter Windows thiếu dữ liệu múi giờ

- Trạng thái: đã tái hiện trong interpreter kiểm thử và interpreter launcher, có thêm vendor path của knowledge runtime; chưa sửa.
- Vị trí: `pyproject.toml:22`; `services/api/src/campus247/application/learning/exit_tickets.py:22,28`.
- Bằng chứng: ZoneInfo không tìm được Asia/Bangkok, Asia/Ho_Chi_Minh hoặc UTC; `class_wall_time({"local":"2026-11-12T08:30"}, "Asia/Bangkok")` trả lỗi422 INVALID_CLASS_TIME.
- Hướng sửa: cấp tzdata đúng lock cho interpreter phục vụ và test; kiểm giờ bình thường, giờ lặp và giờ không tồn tại trước khi bật chức năng giờ lớp.

## Kiểm chứng lượt 1

| Nhóm | Kết quả lượt cuối | Cách chạy / giới hạn |
|---|---|---|
| Frontend | 120 file, 761 test đạt; exit0 | Vitest API, config trong bộ nhớ tương đương vitest.config.ts; tắt cache/config bundling, đóng context sau lượt chạy |
| TypeScript | exit0 | `apps/web/node_modules/.bin/tsc.cmd --noEmit --incremental false --project apps/web/tsconfig.json` |
| Python nhóm đầu | 83 đạt; exit0 | Safety, intent, authorization, action tokens/preview, identity, AI policy, evidence gate/citations, learning privacy |
| RAG v2/architecture/learning thuần | 545 đạt, 1 thất bại; exit1 | Chặn file write/delete, subprocess và mạng ngoài socketpair nội bộ của asyncio; thêm worker source path cho tiến trình; không chạy các ca cần index ghi đĩa |
| Contract/Postgres protocol/CI setup | 61 đạt, 2 failed, 2 errors; exit1 | 1 failed do LEARNING_TEST_ROOT; 3 ca inventory cần ledger đĩa bị harness chặn, không tính là lỗi ứng dụng |
| Dependency tests | 32 đạt, 2 thất bại, 14 subtest đạt; exit1 | `pytest --capture=sys -p no:cacheprovider tests/unit/dependency_resolution/test_verifier.py` với plugin autoload tắt |
| Local preparation | 9 kiểm tra độc lập đạt | SQLite trong bộ nhớ, SQL/service thật; chưa chứng minh restart/durability trên file |
| OpenAPI | VALIDATION_OK; exit0 | `python -B contracts/tools/validate_openapi.py`; 35 operations, 592 refs |
| Contracts/eval structure | VALIDATION_OK; exit0 | `python -B evals/validate_contracts.py`; 920 file, 562 JSONL case; không phải đo chất lượng model |
| Dependency verifier | exit1 | `python -B scripts/verify_dependencies.py` |
| Python syntax | 845 file, 0 lỗi | ast.parse các source API/worker/synthetic/scripts; không ghi pyc |

Tổng các nhóm pytest lượt cuối đã chọn: 721 đạt, 4 lỗi thực tế nêu ở AUD-004/AUD-005/AUD-008, 3 ca bị chặn vì cần ghi ledger. Không cộng các lượt dựng harness lỗi hoặc lượt chạy trùng vào số này; đây không phải full backend suite.

Các ca độc lập local-preparation đạt: lưu/đọc nháp sở hữu; sent_to_university=false; replay không ghi trùng; từ chối đọc chéo; chặn stale version; bắt xác nhận; chặn phiên thu hồi dưới lock; chặn token sai; list không lộ nháp người khác.

## Quan sát runtime và mức hoàn thiện

- GET8015 `/health/live`, `/health/ready`, `/health/entry`: 200; database ready; redis disabled; worker learning ready. RAG v2: 9.173 units, release generation27/policy_generation3, inventory_checked=true, missing/extra/changed đều0, stale=false, warm=ready.
- API riêng `/v1/users/me`, `/v1/learning/capabilities`, `/v1/student-preparations` trả401 khi không có phiên. `/staff`, `/admin` trả404. `/chat`, `/learning` trả HTML200. Không đăng nhập, không tạo hội thoại hoặc gọi paid model trên runtime chính.
- Main entry hỗ trợ chuẩn bị/lưu nháp; chưa kết nối tiếp nhận hồ sơ HUCE. Chưa chứng minh hành trình gửi hồ sơ → cán bộ xử lý → trả kết quả ở cùng entry. Mã multi-agent/checkpoint/graph riêng không tự chứng minh năng lực đã tích hợp vào main entry.
- Cấu hình học liệu mặc định đọc được dùng SQLite; năm nhóm extension theo lớp có danh sách rỗng, AI source allowlist rỗng. Không suy ra cấu hình tiến trình đang chạy nếu tiến trình có environment override chưa quan sát.
- Chưa chạy lại upload/conversion/OCR, E2E có ghi, load, restore hoặc suy luận trả phí. Để kiểm những phần này cần phạm vi kiểm thử có ghi và môi trường tổng hợp riêng; không sử dụng dữ liệu đang phục vụ làm dữ liệu disposable.

## Ưu tiên khắc phục

1. AUD-001/AUD-002: đóng ranh giới thu hồi phiên, kiểm cả commit và trước byte đầu.
2. AUD-003/AUD-004/AUD-005/AUD-009: khôi phục môi trường và kiểm thử tái lập mà không bỏ bảo vệ.
3. AUD-007/AUD-008: nối security gate vào sản phẩm và sửa phụ thuộc sai lớp.
4. AUD-006: chỉ thông báo tác động khi có biên nhận hợp lệ.
5. Đối chiếu từng luồng đồ án với E2E trên môi trường tổng hợp riêng; đo người dùng thật riêng với bằng chứng kỹ thuật.

## Lượt 2

Lượt này bổ sung sáu phát hiện đã tái hiện bằng chương trình [PROJECT_AUDIT_20261111_REPRO.py](PROJECT_AUDIT_20261111_REPRO.py). Không sửa ứng dụng. Chương trình chặn ghi/xóa tệp, kết nối database trên đĩa, mạng dịch vụ và subprocess; chỉ dùng SQLite `:memory:`, actor tổng hợp và ASGI transport. Socketpair nội bộ của asyncio trên Windows được phép. Không đọc credentials hoặc gọi runtime đang phục vụ.

Chạy từ root bằng interpreter sẵn có:

```powershell
& .venv/Scripts/python.exe -B -X utf8 docs/PROJECT_AUDIT_20261111_REPRO.py
& .venv/Scripts/python.exe -B -X utf8 docs/PROJECT_AUDIT_20261111_REPRO.py --existing-tests
```

Exit0 của chương trình có nghĩa là **đã tái hiện các lỗi với ca đối chứng đạt**, không phải trạng thái ứng dụng đạt. Chương trình dùng fixture tổng hợp hiện có ở `tests/learning_review/test_privacy_boundaries.py` và `tests/api/test_citation_source.py`; không suy rộng bằng chứng trong bộ nhớ thành kiểm chứng persistence/restart tiến trình thật.

### AUD-010 · P2 · Null trong cập nhật chỉ dẫn gây lỗi500

- Trạng thái: đã tái hiện ở HTTP transport thật với service/repository tổng hợp; chưa sửa.
- Vị trí: `services/api/src/campus247/presentation/learning.py:180,232`; `services/api/src/campus247/application/learning/extensions.py:328`.
- Bằng chứng: PATCH chỉ dẫn hợp lệ với `questions: []` trả200. Cùng tài nguyên/revision tiếp theo, `questions: null` trả500 do `len(None)` trong parse; `page_ranges: null` cũng trả500 trong service. Failed transaction không thay đổi revision.
- Nguyên nhân: schema cho phép null, nhưng code dùng giá trị như list. LearningRoute không xử lý TypeError; đây không phải một lỗi nghiệp vụ được trả có kiểm soát.
- Tác động: đầu vào thuộc shape nullable của schema làm API lỗi nội bộ thay vì validation422; client không nhận được hướng dẫn sửa trường.
- Hướng sửa: định nghĩa rõ bỏ trường/clear/null; từ chối null không hợp lệ tại schema hoặc chuẩn hóa trước domain. Tiêu chí: ca hợp lệ vẫn200, hai ca null trả lỗi4xx có cấu trúc, không mutation.

### AUD-011 · P2 · Không mở được citation của message thứ2.001 trở đi

- Trạng thái: đã tái hiện với service thật và lịch sử tổng hợp; chưa sửa.
- Vị trí: `services/api/src/campus247/application/conversation/citation_source.py:46`; `services/api/src/campus247/application/conversation/messages.py:278`.
- Bằng chứng: citation đọc được ở message thứ2.000. Chèn thêm một message hợp lệ trước nó: message đích vẫn xuất hiện trong trang lịch sử sở hữu, retention và source vẫn hợp lệ, nhưng đọc citation ném ResourceNotFoundError. Source reader không được gọi cho lần đọc này.
- Nguyên nhân: citation service chỉ quét20 trang, mỗi trang100 message, từ đầu hội thoại; API tạo/đọc lịch sử không có giới hạn tương ứng2.000 message.
- Tác động: câu trả lời mới trong hội thoại dài mất khả năng mở/đối chiếu nguồn dù nguồn còn quyền.
- Hướng sửa: lookup message trực tiếp theo conversation/message/owner qua repository có kiểm scope, hoặc cơ chế bounded seek; không bỏ kiểm ownership, retention, final_result và source eligibility. Tiêu chí: message2.001 và sâu hơn mở đúng nguồn, ID người khác vẫn bị che.

### AUD-012 · P2 · Ticket confirm201 nhưng đọc lại404

- Trạng thái: đã tái hiện qua `bootstrap.create_app` thật, chỉ thay ledger đĩa bằng SQL trong bộ nhớ; chưa sửa.
- Vị trí: `services/api/src/campus247/application/ticket/confirm.py:41,122`; `services/api/src/campus247/bootstrap/app.py:327,580,583`.
- Bằng chứng: preview201 → confirm201 có ticket_id và Location → GET chính ticket đó404, GET list200 không có ticket mới.
- Nguyên nhân: confirmation service ghi dict `_tickets` riêng; query router dùng `RepositoryComposition.ticket_store` khác. Hai luồng không chia sẻ repository.
- Tác động: endpoint báo tạo thành công nhưng người tạo không thể mở/theo dõi ticket vừa tạo.
- Phạm vi: backend ticket legacy trong factory gốc. Runtime8015 hiện chặn `/v1/tickets`; không gán lỗi này cho local-preparation hay service/certificate workflow độc lập.
- Hướng sửa: dùng cùng repository cho command/query và receipt, commit dữ liệu + biên nhận nguyên tử. Tiêu chí: Location đọc được ngay, list thấy đúng ticket của chính actor; không lộ chéo người.

### AUD-013 · P2 · Replay ticket tạo bản mới khi service instance đổi

- Trạng thái: đã tái hiện; chưa sửa.
- Vị trí: `services/api/src/campus247/application/ticket/confirm.py:98-105,122`.
- Bằng chứng: cùng instance + cùng key trả lại đúng ID với is_replay=true. Instance mới dùng nguyên ledger đã COMPLETED, cùng actor/payload/token/key, lại tạo ID mới và trả is_replay=false. Các reserve/complete dùng implementation SQL thật trên cùng SQLite trong bộ nhớ.
- Nguyên nhân: khi ledger trả REPLAY nhưng dict ticket của instance không có record, code rơi xuống nhánh create thay vì phục hồi kết quả hoặc fail closed. Ledger response reference sau đó bị cập nhật sang ticket mới.
- Tác động: đổi worker/instance hoặc khởi động lại service có thể biến retry thành thao tác mới. Ca tái hiện mô phỏng đổi instance, không khẳng định đã restart tiến trình thật.
- Phạm vi: ticket legacy; không phải cơ chế receipt local-preparation đã kiểm ở lượt1.
- Hướng sửa: replay đọc từ durable store/result đã commit; missing semantic result phải fail closed/reconcile, tuyệt đối không tạo lại. Tiêu chí: replay qua hai instance luôn giữ cùng ticket_id.

### AUD-014 · P2 · Cùng preview/token ticket thực thi nhiều lần với key khác

- Trạng thái: đã tái hiện; chưa sửa.
- Vị trí: `services/api/src/campus247/application/ticket/confirm.py:75-106`; đối chiếu ý nghĩa token một lần tại `docs/06-security/07_CRYPTOGRAPHY_AND_SECRETS.md:83` và `docs/04-architecture/contracts/ENTITY_LIFECYCLES.md:82`.
- Bằng chứng: giữ nguyên actor, preview_id, confirmation_token và payload, chỉ đổi idempotency_key, cùng service tạo ticket thứhai khác ID.
- Nguyên nhân: xác minh chữ ký/binding/expiry nhưng không tiêu thụ preview/token nguyên tử; ledger chỉ chống lặp theo key do client cung cấp.
- Tác động: một lần preview/xác nhận không giới hạn được số lần tác động; client đổi key vượt qua chống replay.
- Phạm vi: ticket legacy; runtime8015 hiện chặn API này. Các tài liệu bảo mật được dùng để đối chiếu ý nghĩa confirmation, không tạo workflow phê duyệt mới.
- Hướng sửa: unique execution binding theo preview/nonce trong cùng transaction với ticket/result/receipt. Tiêu chí: key khác với cùng preview chỉ nhận kết quả cũ hoặc bị từ chối, không có ticket thứhai.

### AUD-015 · P2 · Room availability lỗi500 với datetime thiếu múi giờ

- Trạng thái: đã tái hiện qua HTTP với booking tổng hợp; chưa sửa.
- Vị trí: `services/api/src/campus247/presentation/rooms.py:76-92`.
- Bằng chứng: cặp thời gian có `Z` trả200 và đúng một khoảng xung đột. Cặp thiếu offset trả500 khi so với booking timezone-aware; cặp trộn có/không offset cũng500 tại kiểm starts_at >= ends_at.
- Nguyên nhân: fromisoformat chấp nhận datetime naive; phép so sánh nằm ngoài khối xử lý lỗi parse và không có kiểm timezone.
- Tác động: đầu vào thiếu offset gây lỗi nội bộ trên endpoint đọc, không phải phản hồi validation có kiểm soát.
- Phạm vi: room API legacy; điểm vào8015 hiện chưa kết nối nghiệp vụ phòng học.
- Hướng sửa: dùng typed datetime và bắt buộc offset trước so sánh hoặc truy vấn, chuẩn hóa UTC. Tiêu chí: hai ca thiếu/trộn offset trả422; cặp có offset tương đương trả cùng kết quả.

### Bằng chứng thực thi lượt 2

Lệnh repro trên đã chạy exit0, phát ra:

| Mã | Đối chứng và kết quả quan sát |
|---|---|
| AUD-010 | valid_update_status200; null_questions_status500; null_page_ranges_status500; failed_writes_rolled_back=true |
| AUD-011 | source_at_2000=allowed; source_at_2001=not_found; message_at_2001_visible_in_owned_page=true; deep_read_source_calls0 |
| AUD-012 | preview201; confirm201; get_created_ticket404; list_contains_created_ticket=false |
| AUD-013 | same_instance_replay_preserves_id=true; new_instance_same_ledger_creates_new_ticket=true; new_instance_is_replay=false |
| AUD-014 | same_preview_and_token=true; different_client_key=true; second_ticket_created=true |
| AUD-015 | valid_timezone200; naive_datetime500; mixed_timezone500 |

Các kiểm tra hiện có cho citation, room, ticket và Postgres adapter protocol được chạy thêm với harness chặn ghi/mạng: **32 đạt, exit0**. Dùng tùy chọn `--existing-tests` ở lệnh trên để chạy lại. Adapter SQL tổng hợp giữ database hoàn toàn trong bộ nhớ và khóa toàn transaction để phục vụ thread TestClient. Lượt dựng harness trước đó có một lỗi thread của chính fixture; đã khắc phục trong chương trình evidence, không sửa mã ứng dụng và không tính đó là lỗi ứng dụng mới. Sáu ca tái hiện độc lập được chạy lại sau thay đổi fixture và vẫn tái hiện đủ sáu lỗi.

### Phần đã rà thêm nhưng chưa kết luận thành lỗi mới

- PublicDocumentFetcher có kiểm HTTPS/domain HUCE, kiểm địa chỉ global và pin IP tại socket, kiểm lại redirect, TLS, giới hạn byte và deadline. Không thực hiện fetch tới trường trong lượt này; không kết luận SSRF runtime chỉ từ test helper cũ.
- Rà quyền đọc câu hỏi/reply riêng, DTO chỉ dẫn, nguồn đã thu hồi và read_view PostgreSQL. Không phát hiện bypass mới được chứng minh trong các đường vừa đọc; không suy ra toàn bộ module an toàn.
- SSE hiện kiểm nguồn trước các delta và sau toàn bộ delta, không kiểm nguồn ở từng delta. Test hiện có chủ động xác nhận cadence này. Đây là giới hạn cần cân nhắc cho nguồn riêng khi thu hồi trong lúc stream; không gán thêm mã lỗi mới hoặc coi kiểm cuối là bằng chứng không byte nào đã truyền trước đó.

### Tổng trạng thái sau lượt 2

- 15 phát hiện được ghi nhận: AUD-001…AUD-015; tất cả chưa sửa ứng dụng.
- Sáu phát hiện mới có ca tái hiện chạy lại được và ca đối chứng; ba lỗi ticket và room API được ghi rõ là legacy, không mặc định đang mở ở8015.
- Ưu tiên cho main runtime: AUD-001/AUD-002 trước; tiếp theo AUD-010/AUD-011 và lỗi môi trường/CI của lượt1. Các luồng legacy cần sửa AUD-012…AUD-015 trước khi tái sử dụng hoặc mở API.
- Chỉ tạo báo cáo và chương trình tái hiện trong docs. Không commit/push/deploy, không xóa hay thay đổi dữ liệu đang phục vụ.

## Kiểm định sâu lượt 3 — 12/11/2026

Tiếp tục theo yêu cầu “kiểm định sâu hơn” và “tiep”. Tập trung vào giới hạn lịch sử dữ liệu, phục hồi worker sau lỗi và thu hồi nguồn giữa các điểm await trước khi gửi AI. Không sửa ứng dụng. Bằng chứng là các ca tổng hợp có assert đối chứng, chạy qua service/SQL thật với repository bộ nhớ, scanner và gateway giả; hook chặn ghi file, kết nối database trên đĩa, kết nối dịch vụ và subprocess. Không đo trải nghiệm người dùng thật.

### AUD-016 · P2 · Giao dịch không liên quan làm lịch sử consent không đọc được

- Trạng thái: đã tái hiện bằng SQLite trong bộ nhớ; chưa sửa.
- Vị trí: `services/api/src/campus247/infrastructure/repositories/sqlite_consents.py:51-70`; nối store dùng chung tại `services/api/src/campus247/bootstrap/unified_demo.py:153-163`; endpoint đọc tại `services/api/src/campus247/presentation/privacy_notice.py:56`.
- Đối chứng: một consent và 999 biên nhận conversation_metadata vẫn đọc đúng một consent. Thêm đúng một biên nhận conversation_metadata khiến list_user_consents ném CONSENT_STORAGE_UNAVAILABLE. Database vẫn chỉ có một revision consent và has_active_consent vẫn trả true.
- Nguyên nhân: SELECT lấy tối đa 1001 receipt của toàn bộ namespace theo actor, từ chối khi vượt 1000, sau đó mới lọc namespace consent. Ngưỡng lịch sử consent phụ thuộc cả lưu metadata hội thoại và các nghiệp vụ khác trên store dùng chung.
- Tác động: lịch sử lựa chọn quyền riêng tư bị mất khả năng truy cập ở actor có nhiều giao dịch; trang OperationalPrivacy gọi notice/consents bằng Promise.all nên lỗi danh sách làm bước tải trang thất bại. Không phải dữ liệu consent bị xóa hoặc consent tự đổi trạng thái.
- Phạm vi: đường consent dùng SQLite actor state; đã thấy wiring dùng chung trong unified bootstrap. Không khẳng định tài khoản thật hiện đã chạm ngưỡng.
- Hướng sửa: truy vấn đúng namespace trước khi áp dụng giới hạn và cung cấp phân trang lịch sử. Tiêu chí: hơn 1000 receipt ngoài consent không ảnh hưởng danh sách consent; giữ kiểm tenant/owner và tính toàn vẹn receipt/revision.

### AUD-017 · P2 · Worker mắc kẹt SCANNING sau lỗi không được bắt ở lần thử cuối

- Trạng thái: đã tái hiện qua process_version/tick thật với scanner giả; chưa sửa.
- Vị trí: `services/api/src/campus247/application/learning/service.py:791-824,913-926`; nguồn lỗi hệ điều hành có thể thoát từ `services/api/src/campus247/infrastructure/learning/blob.py:51-57`.
- Đối chứng: TimeoutError được chuyển thành FAILED/PROCESSING_TIMEOUT sau ba lần. Với OSError lúc khởi chạy scanner, cả ba lần lỗi thoát ra ngoài; job còn PROCESSING, version còn SCANNING, không có error_code. Sau khi đặt lease hết hạn và chạy thêm hai tick, attempt vẫn là 3, không phục hồi hay chuyển trạng thái cuối.
- Nguyên nhân: bộ xử lý chỉ bắt LearningError/TimeoutError; attempt được commit trước khi gọi scanner. Scheduler bỏ qua mọi job attempt >= 3 kể cả PROCESSING đã hết lease. Lỗi khởi chạy process của ClamAV không được chuyển thành LearningError.
- Tác động: học liệu không xuất bản được, trạng thái giao diện vẫn như đang xử lý; lần khởi động lại hoặc tick tiếp theo không tự giải quyết job này. Không kết luận toàn bộ worker dừng vĩnh viễn vì còn tùy vòng lặp gọi bên ngoài.
- Hướng sửa: chuyển lỗi adapter thành lỗi nghiệp vụ có kiểm soát và bổ sung xử lý lease cuối đã hết hạn thành trạng thái cuối có chẩn đoán. Tiêu chí: lỗi khởi chạy scanner và crash ở attempt cuối đều thoát PROCESSING sau lease, không vượt giới hạn retry và không bỏ qua quét an toàn.

### AUD-018 · P2 · Thu hồi học liệu chưa chặn các lần gửi AI tiếp theo

- Trạng thái: đã tái hiện với gateway giả ghi lại trạng thái nguồn tại mỗi lần gọi; chưa sửa.
- Vị trí: `services/api/src/campus247/application/learning/explanation.py:33-68`.
- Đối chứng: nguồn còn hiển thị gọi generation và verifier thành công. Ẩn nguồn trước khi bắt đầu khiến từ chối và không gọi gateway. Nếu nguồn bị ẩn trong extract_page, cả generation lẫn verifier vẫn được gọi khi nguồn đã HIDDEN. Nếu ẩn trong generation, verifier vẫn nhận nguồn sau khi ẩn. Cả hai ca race chỉ bị từ chối ở lần query cuối, không trả answer cho client.
- Nguyên nhân: kiểm quyền nguồn trước verify/extract và sau inference; thiếu kiểm lại ngay trước từng lần gửi generation/verifier qua các khoảng await. Kiểm cuối chỉ bảo vệ phản hồi, không thu hồi được nội dung đã gửi tới gateway.
- Tác động: khi bật AI học liệu, nguồn bị ẩn trong lúc chuẩn bị hoặc tạo câu trả lời vẫn tiếp tục được chuyển cho bước AI tiếp theo. Đây là ranh giới outbound khác AUD-002 (trả PDF cho client).
- Giới hạn: implementation yêu cầu actor synthetic và hash nguồn được cho phép; AI học liệu mặc định chưa bật. Ca kiểm định sử dụng đúng hai điều kiện này, gateway giả và dữ liệu tổng hợp, không có cuộc gọi nhà cung cấp thật; không suy ra rò rỉ dữ liệu production đang xảy ra.
- Hướng sửa: revalidate phiên và quyền nguồn sát từng dispatch, gắn nguồn/phiên bản đã cấp quyền vào guard của gateway; kiểm lại sau await và trước verifier. Tiêu chí: thu hồi ở extract phải tạo 0 dispatch; thu hồi trong generation phải chặn verifier; giữ kiểm quyền cuối trước trả kết quả.

### Bằng chứng thực thi lượt 3

Chạy từ repository root:

```powershell
& .venv/Scripts/python.exe -B -X utf8 docs/PROJECT_AUDIT_20261111_DEEP_REPRO.py
& .venv/Scripts/python.exe -B -X utf8 docs/PROJECT_AUDIT_20261111_DEEP_REPRO.py --existing-tests
```

Lệnh đầu **exit0**, xác nhận đủ ba lỗi và đối chứng. Exit0 của chương trình tái hiện nghĩa là lỗi tái hiện đúng như mô tả, không phải ứng dụng đạt nghiệm thu.

| Mã | Kết quả kiểm chứng bằng assert |
|---|---|
| AUD-016 | total_receipts_1000_history_ok=true; total_receipts_1001_history_unavailable=true; consent_revisions=1; active_consent_still_readable=true |
| AUD-017 | handled_timeout_final_state=FAILED; os_errors_escaped=3; attempt=3; expired_lease=true; two_more_ticks_no_recovery=true; job_state=PROCESSING; version_state=SCANNING; error_code_absent=true |
| AUD-018 | visible_source_calls=2; hidden_before_start_calls=0; hidden_during_extract gọi cả generation/verifier với source_hidden=true; hidden_during_generation_verifier_called=true; final_response_denied=true; real_provider_calls=0 |

Lệnh thứ hai chạy hai module hiện có về ranh giới quyền học liệu và API privacy notice/consent: **11 đạt, exit0** với cùng guard chặn ghi/mạng. Đây là kiểm tra đối chứng phạm vi hẹp, không thay thế kiểm toàn bộ hệ thống. Không chạy các integration test cần tạo database/file trên đĩa.

Tổng cộng báo cáo có **18 phát hiện AUD-001…AUD-018**, chưa sửa ứng dụng. Ưu tiên P1 thu hồi phiên đã ghi ở lượt 1 giữ nguyên; ba phát hiện lượt này bổ sung rủi ro độ bền trạng thái và thu hồi nguồn khi bật AI. Chỉ bổ sung báo cáo này và file DEEP_REPRO trong lượt 3; giữ file REPRO lượt 2 và toàn bộ thay đổi có sẵn. Các mục đọc thêm nhưng chưa có bằng chứng tái hiện độc lập không được cộng vào số phát hiện.
