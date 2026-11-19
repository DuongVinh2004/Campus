# Chặng 6 — runbook local

[Bàn giao và giới hạn](SERVICE_STAGE6_DELIVERY_20261014.md). Mở **http://localhost:8004/login**. API8004 chỉ nghiệp vụ/tri thức demo và proxy hỏi đáp sang writer8003; frontend3005/build02. Không mở paid writer mới hoặc dừng owner8003/native/các frontend cũ.

## Tài khoản và demo

| Tài khoản synthetic | Phạm vi |
|---|---|
| SV001 / SV024 | Chỉ course/request của chính mình |
| OF001 | HUCE_GENERAL, hỗ trợ và certificate queue cũ |
| OF002 | ACADEMIC_SERVICES, phúc khảo demo; không có quyền certificate HUCE_GENERAL |
| KA001 / KA002 | Nguồn demo; tác giả và reviewer/publisher phải khác nhau |

Sinh viên vào `/services`, chọn phúc khảo vàCS101mô phỏng, đọc hướng dẫn, nhập lý do, xem trước rồi xác nhận. OF002 vào cùng trang để nhận queue, yêu cầu bổ sung/trả lời/trả outcome demo. Sinh viên mở lại record và tài liệu. Hỗ trợ chung dùng context do sinh viên chọn vàOF001; không tự gửi transcript/email. Chat `/chat` đưa đề xuất vào form; intent không là confirmation.

Quản trị vào `/knowledge/sources`: giữ snapshot `.txt` mới → tạo rendition/version/mapping/hiệu lực → đăng nhập admin khác để đối chiếu source/checksum → review → build → preview → confirm publish. Bản đã xuất bản muốn sửa phải tạo version mới. Withdraw cũng cần preview/confirmation; không xóa snapshot/history. Graph UI `/knowledge/policy-graph` tiếp tục dùng API8003 và active graph chặng5; không publish candidate graph lỗi đã giữ từ trước.

Các thông báo thiếu source/eligibility/deadline, quyền, stale version, confirmation expired hoặc kết quả gửi chưa rõ đều là tình trạng thật. Nếu mất response sau confirm, đọc lại hồ sơ/thử lại **cùng preview và idempotency**; không tạo draft/confirm mới để tránh unknown effect. Phiên mới không được dùng preview phiên cũ; source/payload đổi cần preview mới.

## Storage và API

DB: `infra/local/certificate-stage1-20261013-01/demo.sqlite3`. Migration additive: `service_request`, `service_request_audit`, `service_operations_record`, schema marker2. Certificate tables và mọi row cũ được giữ; backup trước chặng6 ở namespace mới. Service forms/attachments/results trong transaction, không có filesystem path do input lựa chọn.

API mới: `/v1/service-course-records`, `/v1/service-guidance/{kind}`, `/v1/service-assistant`, `/v1/service-requests/drafts`, `/{id}/preview`, `/{id}/confirm`, `/{id}/result`, `/{id}/attachments/{index}`; staff dưới `/v1/staff/service-requests`. `/v1/service-staff-directory` lấy quyền nhận thực tế từ synthetic directory. `/v1/knowledge-operations` quản lý source/version/review/build/publication, `/v1/service-knowledge/search` chỉ current demo evidence. Không đưa token/actor/role/signature/status do LLM tạo vào executor.

## Build và launch

Receipt hiện tại `infra/local/service-stage6-20261014-01/*-launch.json` và `runtime-active-01.json` gắn command/parent/creation/listener. PID chỉ là observation; kiểm lại trước mọi tác động. Launcher chỉ tạo process khi8004/3005trống và build/guard hợp lệ, không tự dừng process. Không chạy lại khi runtime còn sở hữu cổng.

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONIOENCODING='utf-8'
.\.venv\Scripts\python.exe -B scripts/launch_service_stage6.py --build-ordinal 02
```

Muốn build tiếp, chọn ordinal**03 chưa tồn tại**, giữ toàn bộ build01/02 và guard byte-for-byte; không lặp command vào output đã có:

```powershell
.\.venv\Scripts\python.exe -B scripts/prepare_service_stage6_frontend.py prepare 03
.\.venv\Scripts\python.exe -B scripts/prepare_service_stage6_frontend.py build 03
```

Không sửa preservation guard, không cleanup `.next`, không reset DB để chạy lại. Nếu8004/3005còn occupied, kiểm owner/read-only; chuẩn bị đúng target trước handoff. API8003 vẫn riêng; không tái dùng handoff approval/PID cũ10336/13108.

## Kiểm chứng lại

Mỗi basetemp/report phải mới và canonical trong namespace chặng6. Lượt06/07 đã tồn tại; có thể dùng08 sau khi xác minh chưa tồn tại. TestClient cần loopback socket; sandbox từng chặn socketpair, không coi treo là implementation pass.

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
.\.venv\Scripts\python.exe -B -m pytest tests/api/test_service_stage6.py tests/api/test_certificate_stage1.py tests/api/test_multi_agent_api.py tests/api/test_policy_graph_bootstrap.py tests/unit/agent/test_multi_agent_integrated.py tests/unit/agent/test_multi_agent_admission.py --basetemp=infra/local/service-stage6-20261014-01/pytest-08 --junitxml=infra/local/service-stage6-20261014-01/backend-tests-08.xml -q -p no:cacheprovider -p pytest_asyncio.plugin
```

Scoped TS: `node apps/web/node_modules/typescript/bin/tsc -p apps/web/tsconfig.service-stage6-20261014.json`. UI tests dùng existing `vitest.policy-graph.config.ts` để jsdom Storage không bị Node26 Web Storage che; chọn report02mới và giữ report01. Scope gồm `ServiceWorkspace.test.tsx`, `SourceOperations.test.tsx`, `CertificateWorkspace.test.tsx`.

Restart runner đã dùng exact fixture `process-restart.sqlite3` và cổng8005; **không chạy lại tên này**. Một test restart tiếp cần script/destination mới giữ fixture cũ. Lifecycle shutdown chỉ có trên worker test mới, không có trên sản phẩm8004; nonce nằm trong bộ nhớ, không log.

Readback01vàfinalizer manifest01/02đã tồn tại nên không chạy lại. Đọc manifest02/hash trước, hoặc tạo runner/report namespace mới. Không confirm lại READY certificate để kiểm effect. READY cũ thuộc**SV024**, không phảiSV001.

Paid campaign đã chạy3câu+1browserchat:41calls,0,0257856USD bảo thủ. `evaluate_service_stage6_live.py --execute` hiện có attempt outputs; **không chạy lại** hoặc replay thành fresh. Trước campaign mới phải kiểm admission toàn bộ run envelope, cumulative caps và unknowns.46calls còn lại không tự cấp quyền hạ admission hay mở writer khác; chặng7 cần lập campaign/tài nguyên đúng phạm vi riêng.
