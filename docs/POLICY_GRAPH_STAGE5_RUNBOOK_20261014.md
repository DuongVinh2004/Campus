# Policy Graph RAG — runbook local

Ngày 14/10/2026. [Kết quả và giới hạn](POLICY_GRAPH_STAGE5_DELIVERY_20261014.md). Workspace: `C:\Users\Duong Vinh\Vinh`. Không xóa report/DB/source/index, không reset ledger hoặc tạo Gateway thứ hai.

## Đọc lại evidence đã có

Namespace `infra/local/policy-graph-stage5-20261014-01/`: `build-01.json`, `policy-graph.sqlite3`, `source-verification-01.json` đến03, `tests-02.xml` đến07, `frontend-tests-02.xml` đến04, `live-preflight-01.json` đến03, 12live-case reports, 2extraction reports, `live-quality-review-02.json`, `runtime-active-01.json`, `browser-verification-01.json`, `verification-manifest-03.json`. Graph phát triển `huce-policy-development-v1`; publication/source/index immutable. Không chạy lại một command có output name đã tồn tại.

Kiểm chứng lại nguồn bằng một report **mới** sau khi kiểm exact canonical path và Git status:

```powershell
$env:PYTHONIOENCODING='utf-8'
$env:PYTHONDONTWRITEBYTECODE='1'
.\.venv\Scripts\python.exe scripts/verify_policy_graph.py --output=source-verification-04.json
```

Build version tiếp theo với graph ID/report mới. Mặc định chỉ tạo candidate; review bởi admin khác tác giả qua API/UI. Chỉ dùng `--development-source-review` nếu chủ động thực hiện development source review và ghi đúng giới hạn, không gắn nhãn independent human review.

```powershell
.\.venv\Scripts\python.exe scripts/build_policy_graph.py --graph-id huce-policy-development-v2 --output=build-02.json
```

Raw LLM response nằm trong `policy_extraction`; proposal có server-bound envelope riêng. Invalid output giữ audit, không publish. `policy_review` giữ mọi verdict và revision; `policy_publication` bất biến. Không edit DB thủ công để vượt review, sửa hash, đổi ngày hoặc merge aliases.

## API/UI

API group `/v1/policy-graph`:

- `GET /versions`, `GET /versions/{id}`: admin và current source scope, không lộ versions không đủ quyền.
- `POST /versions/{id}/reviews`: target, verdict, note, expected_revision; author không tự review.
- `POST /versions/{id}:publish-preview`, `:publish`: revision + confirmation + confirmed; gắn actor/session/scope/proposal/reviews, đọc lại nguồn, không ghi đè version.
- `POST /versions/{id}:extract-candidate`: target_ids (tối đa 4), admin + shared admission + cùng existing Gateway. Output chỉ candidate, tác giả phải có reviewer khác.
- `POST /relations:search`: query và depth/nodes bounded; scope/as-of do server tạo. Graph path không phải citation/rule.

UI [localhost8003/knowledge/policy-graph](http://localhost:8003/knowledge/policy-graph). Trong runtime graph-enabled, KA001/KA002 dùng hai knowledge admins synthetic có sẵn; SV001/SV024 chỉ truy hồi và luồng hồ sơ đã có. Admin không có quyền gửi hồ sơ sinh viên. Sign-in admin vào graph review. API8003 đang phục vụ graph và proxy frontend3004; frontend3003/build02 giữ nguyên. Proxy8000 cũ không có route graph UI, dùng8003 cho chặng5.

Hai candidate LLM `candidate-01a137da-2126-7057-8c55-53abb83f4af4` và `candidate-01a137da-2d29-7e09-9342-ba8700c1b02b` đã được KA002 ghi `conflicting` revision1 qua trình duyệt sau direct approval; không xuất bản. Lỗi nằm trong notes và `live-quality-review-02.json`. Muốn sửa phải tạo candidate/version mới, giữ raw/history cũ và review lại; không edit DB để loại bỏ lỗi hoặc đổi verdict.

## Local checks

Backend reports04–07 có174distinct passed;17UI passed và scoped TypeScript/fresh production build qua. Fixture basetemp phải **chưa tồn tại** và ở namespace chặng5; không dùng lại tên pytest-04/05/06/07 vì pytest có thể làm sạch basetemp cũ. Dùng output/report mới, giữ mọi failed/aborted evidence.

Frontend scoped check:

```powershell
node apps/web/node_modules/typescript/bin/tsc -p apps/web/tsconfig.policy-graph-20261014.json
```

UI tests từ `apps/web`, dùng harness riêng để jsdom Storage không bị global Web Storage của Node26 che:

```powershell
node node_modules/vitest/vitest.mjs run --config vitest.policy-graph.config.ts src/features/knowledge/PolicyGraphReview.test.tsx src/features/knowledge/KnowledgeReview.test.tsx src/features/documents/CertificateWorkspace.test.tsx
```

Harness không thay tests/threshold hay application auth. Full-project TypeScript còn lỗi có sẵn trong AppShell tests; không mở rộng scope để sửa chúng nhằm lấy trạng thái sạch.

## Live campaign đã chạy và runtime hiện tại

`evals/datasets/policy-graph-development-20261014.json` chứa12câu phát triển và2nhóm extraction targets. Campaign đã chạy đúng một lần qua API8003, không Gateway thứ hai:111calls/0.0873051USD bảo thủ. Ledger cuối12105/12192calls,4.4916066/10USD,14unknown giữ nguyên; native8040HTTP/4695inference/805799tokens. Runner mặc định chỉ read-only preflight. Không chạy lại `--execute` hiện có: output attempt đã tồn tại; còn87calls cũng không đủ admission192calls cho full campaign.

Authorization05 đã tạo và kiểm chứng; không tạo lại/ghi đè. Runner không thực hiện cap transition. Handoff đã xong sau direct approval `Cho phép bàn giao đúng API8003`; old-owner helper10336/13108 là bằng chứng lịch sử, **không chạy lại** để restart owner mới. Receipt hiện tại `infra/local/multi-agent-integrated-20261013-01/20261014T003326234065-live-launch.json`, wrapper1888/worker5480 trên8003. `runtime-active-01.json` giữ exact ownership/commands/creation/listeners. Giữ native/proxy/frontend3003, không mở namespace native mới. Mọi restart sau này cần đọc trạng thái hiện tại, quiet/in-flight và chuẩn bị exact targets thay vì tái sử dụng PID cũ.

Launcher hỗ trợ opt-in như command đã dùng; **không chạy khi8003 đang có owner**:

```powershell
.\.venv\Scripts\python.exe scripts/launch_multi_agent_live.py --api-only --policy-graph huce-policy-development-v1 --graph-frontend 3004
```

Chỉ gọi khi API8003 đã được bàn giao đúng thẩm quyền/ownership và có đủ headroom; launcher không dừng process hoặc tạo writer thứ hai. Runtime graph bật phải giữ source/index fingerprint, chỉ public grants từ server, same budgets/guards. Graph service failure phải ghi event unavailable và dùng eligible hybrid; không gọi đó là không có chính sách.

Runner execute cần receipt của graph-enabled API-only exclusive writer. Không dùng launch receipt v15 cũ. Runner lưu attempt trước request và kết quả riêng; không resend outcome unknown, không gọi replay là fresh:

Command đã dùng: `scripts/evaluate_policy_graph_live.py --execute --runtime-receipt infra/local/multi-agent-integrated-20261013-01/20261014T003326234065-live-launch.json`. Giữ nguyên outputs/attempts, không replay thành fresh. Một campaign mới phải có report/attempt namespace mới và admission được kiểm lại trong cap hiện có.

Kiểm correctness/completeness/ALL-ANY/audience/time/source entailment/hash, graph events, history, tokens, conservative cost/invoice unknown và latency cho **từng ca**. Extraction raw/candidate cần review nguồn; không auto approve. Hai repair envelopes là dự phòng tài nguyên, không biến failed/not_verified thành pass. Giữ luồng giấy xác nhận; nghiệp vụ phúc khảo mới thuộc chặng6. Không yêu cầu ablation hay graph database mới.

Kết quả source review:12correctness2,11completeness2/1partial,11citation entailment2,12citations đúng hash/12history khớp; p50=16563ms/p95=24250ms. Đây là authored development set và Codex review, không independent human assessment. Readback sau restart ở `stage5-after-live-readback-01.json` giữ READY5audit/HTML hash, source/history/ownership; zero paid/native delta. Budget có admission cho run tiếp theo nhưng không dùng chỉ để tìm một kết quả đẹp hơn hoặc tự tăng cap.
