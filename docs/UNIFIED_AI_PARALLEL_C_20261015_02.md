# Chat C — tiếp tục02, batch 20261015-01

**Cập nhật cuối:** [report03](UNIFIED_AI_PARALLEL_C_20261015_03.md) đã đối soát final handoffs, snapshot03, backend854/859 với5 lỗi gốc và TypeScript/build đạt. UNI-040 partial; các đoạn pending bên dưới giữ bối cảnh lịch sử của tiếp tục02.

Ngày15/10/2026, Asia/Bangkok. Người dùng yêu cầu tiếp tục từ checkpoint01. **Chưa có final handoffs A/B; final integrated acceptance/build chưa được xác nhận.** Không UI tests, pilot/human usefulness, paid/provider, serving-runtime transition hoặc production actions. [Checkpoint trước](UNIFIED_AI_PARALLEL_C_20261015_01.md) và mọi artifacts trước được giữ.

## Kết quả C mới

- `independent-09`: **56/56 ca C đạt**, source stable trong lượt kiểm. Thêm10 ca so checkpoint trước rồi thêm3 ca strict quantity, tổng13 ca mới: typed supplement rollback khi response/receipt write fail, stale source/session/recipient, mandatory officer re-review sau correction, internal handover isolation, actual memory/context suppression, missing-store unavailable, actual business outbox/in-app delivery/revoke và bool/float/text quantity rejected.
- `independent-07`:52/53. Lỗi setup trong test mới dùng expected_draft_version0 dù draft yêu cầu bổ sung cũ vẫn tồn tại. C sửa setup đọc current draft và CAS sang revision mới; assertion mandatory review giữ nguyên. `independent-08`:53/53 nhưng source upstream tests đổi trong lúc chạy, không final integration evidence. Giữ tất cả XML/log/preimages.
- Actual A/B composition đã quan sát bằng C fixture: memory declaration sau consent/opt-in đi qua `/context:compose` dưới classification untrusted/action_authority none; forget tạo suppression revision và text biến mất khỏi context; business feedback→durable outbox→bounded worker→đúng1 in-app inbox item; revoke chặn đọc401. Không suy main-model writer hoặc legacy chat memory đã có consumer.
- `matched-comparison-04`:3 matched synthetic conditions có nguồn/thiếu nguồn/claim số sai đều đạt material gates ở single graph và selected multi. Fake dispatch single=3/2/4; multi=8/5/8; multi source reads=5/0/6, durable counts khớp dispatch. Gold fee từ literal synthetic source độc lập với model output, không majority vote/self-judge. Mẫu này không chứng minh lợi ích chất lượng của fan-out. Cost USD=null; expert/human usefulness pending; policy/budgets không đổi.
- `case-measure-01`:3 first commits qua review→preview→confirm→public readback, retry cùng receipt/no duplicate. First confirm→readback32,70–41,79ms, **n=3 nên không báo p95**.24 warm receipt reads trên3 cases có p95=14,9242ms; clustered fixture observations, không24 user sessions hoặc production SLO/throughput.

Evidence thuộc `infra/local/unified-ai-parallel-20261015-01/stream-c/`:

| Command / attempt | Exit / trạng thái | Artifact |
| --- | --- | --- |
| `unified_parallel_c_verify.py independent 07` | 1;52/53, C setup CAS error | `checks/independent-07/`, `checks/independent-07-harness-correction.json` |
| `... independent 08` | 0;53/53, source changed | `checks/independent-08/command.json` |
| `... independent 09` | 0;56/56, stable | `checks/independent-09/command.json` |
| `unified_parallel_c_compare.py 01` | interrupted; sandbox asyncio startup, fixture chưa tạo | `checks/matched-comparison-01-interrupted.json` |
| `... compare 02/03` | 1/1; C harness citation attribute/dataclass serializer errors | `checks/matched-comparison-02-harness-error.json`, `...03-harness-error.json`, partial fixture namespaces giữ nguyên |
| `... compare 04` | 0;3 conditions ×2 actual graph paths; stable | `fixtures/matched-comparison-04/report.json` |
| `unified_parallel_c_case_measure.py 01` | 0;3 valid first outcomes +24 receipt reads; stable | `fixtures/case-measure-01/report.json` |
| `unified_parallel_c_preserve.py snapshot 02` | 1; source notification đổi giữa capture | `snapshots/attempt-02-failure.json`, partial `source-02/` giữ nguyên; không completed manifest |
| `unified_parallel_c_preserve.py audit 03` | 0;4 DB all-table/row/schema, metadata, guard, preimages, Git entries không đổi | `preservation-03.json` |

Broad backend/exact contract run `scoped-01` đang được đối soát riêng. Đây là run trước final handoffs trên working source, không phải final release candidate. Chỉ latest unique `(classname,name)` được tính sau khi phân loại failures; không cộng reruns/history/A+B totals. Lỗi deadline50ms có từ chặng11/12 vẫn phải giữ riêng và không suy đã sửa nếu một rerun pass.

## Source và handoff

Đã đọc A `uni031-02`, `uni033-01`, `uni035-01`; chúng dùng32-case milestone evidence nhưng current contract/service/router đã đổi sau hashes đó. `checks/continuation-preflight-02.json` giữ mismatch list. Đã đọc A `integration-acks/personal-01.json`: actual explicit-store composition/consumer fixture readback, có giới hạn resource-context API, không model writer/legacy chat/distributed atomicity. `checks/personal-composition-review-02.json` ghi4 path đã đổi sau ack; C checks xác minh scoped actual consumers nhưng chưa công nhận final source revision.

Final frontend wrapper vẫn yêu cầu A/B final handoffs + fresh stable snapshot; **chưa chạy final TypeScript/production build** trong C. Snapshot01/02 đều giữ partials và lỗi drift, không được dùng làm final source. Build guard nguyên byte; không build tại `apps/web` hoặc build đang phục vụ. Không thay final-check safeguards để bỏ điều kiện này.

Master backlog chỉ ghi tiến độ có bằng chứng. Source task statuses001–042 và nguyên records11/12 giữ nguyên trong checkpoint trước; việc công nhận milestone/final mới cần exact current hashes/composition/evidence phù hợp. Các acceptance044 UI,047 pilot,045 expert review,048 full rehearsal và institutional/production giữ pending. [Acceptance map](UNIFIED_AI_ACCEPTANCE_C_20261015_01.md), [pilot protocol](UNIFIED_AI_PILOT_C_20261015_01.md), [runbook](UNIFIED_AI_RUNBOOK_C_20261015_01.md).

Next action thực: đối soát broad scoped failures và chuyển owner qua append-only findings nếu là source regression; giữ failure nền riêng. Sau owner final handoffs/hashes ổn định mới chụp snapshot/fixtures lần mới và chạy final combined backend/exact contracts, guarded TypeScript/build; audit giữ lại mọi dữ liệu/lượt thất bại. Không chờ vô hạn hoặc gọi build/synthetic là UI/pilot usefulness.
