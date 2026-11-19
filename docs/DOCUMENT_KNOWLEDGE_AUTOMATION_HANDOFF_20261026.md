# Handoff sang chat mới — 26/10/2026

Người dùng vừa yêu cầu: **“làm xong phần đang dở đi xong bật đoạn chat mới làm tiếp để đỡ tràn context”**. Phần intake/OCR/checkpoint, sửa rendition văn xuôi có review độc lập và lượt baseline nhỏ đã được chốt; tiếp tục phần còn lại của `docs/DOCUMENT_KNOWLEDGE_AUTOMATION_IMPLEMENTATION_PLAN_20261025.md`, không coi P00–P16 đã hoàn tất.

Workspace `C:\Users\Duong Vinh\Vinh`, PowerShell, Asia/Bangkok. Đọc AGENTS.md hiện hành. Giữ toàn bộ dữ liệu/dirty/untracked/deleted/evidence/backup; ngoài workspace chỉ đọc. Không cleanup/delete/reset/discard/commit/push/deploy hoặc thay bảo vệ. Không sub-agent/Codex automation/chat khác. Chat mới này được người dùng yêu cầu trực tiếp; dùng cùng checkout local, không tạo worktree.

## Bắt đầu ở đây

1. Đọc `docs/DOCUMENT_KNOWLEDGE_AUTOMATION_PROGRESS_20261026.md` và checkpoint JSON mới nhất trong `infra/local/knowledge-automation-20261026/` (tên chính xác sẽ ghi dưới đây).
2. Kiểm `git status --short -uno`: baseline có **133 trạng thái tracked sẵn**, HEAD `c18e2d1741361e7852511a2200fb2595bc6e47b9`. Không làm sạch trạng thái. Phần lớn code feature đã là untracked từ trước; `git diff` không mô tả hết thay đổi. Code hashes nằm trong checkpoint.
3. Ưu tiên ba vấn đề baseline mới dưới đây và kiểm UI correction với schema0022 trên bản thử; sau đó nối evidence/resolver/issue/admission/serving và các bước P13–P16. Tiếp tục thực thi, không chỉ lập kế hoạch hay xin duyệt giấy tờ cũ.

## Code và kiểm thử đã có

- `application/knowledge/document_identity.py`, `evidence_units.py`, `intake.py`, `edition_decisions.py`, `version_resolver.py`, `rendition_corrections.py`.
- Migrations 0019–0022 append-only; chưa migrate DB gốc. 0021 lưu identity/relation decisions theo known-at; 0022 lưu đề xuất/review/materialization sửa văn xuôi. Proposer là tác giả bản nháp; reviewer khác. Tạo version/rendition mới cùng edition/original, không đổi ngày. Review kỹ thuật không thay publication review. Table/diagram uncertainty không được xóa bằng sửa chữ.
- Worker `knowledge.py`, read-only parser, PDFMiner layout, Poppler previews, local OCR adapter/network guard. Pin engine/core/node/language/profile hashes. Không nới parser guard. `vie.traineddata` có sẵn, tesseract.js7.0.0 bundled. OCR cache vẫn chưa xác minh ngữ nghĩa.
- UI `KnowledgeIntake.tsx`, `RenditionCorrection.tsx`, `KnowledgePlatform.tsx`; actor/auth/review/preview/confirmation giữ nguyên. Correction UI chỉ hiện khi DB có bảng0022.
- Explicit recheck giữ số attempts và fencing; từ NEEDS_INFORMATION chạy lại checkpoint hợp lệ, cap3 không reset. UI thực tế đã recheck sample raster: attempts2, chỉ **1 OCR stage**, giữ parse/render/OCR cũ, tạo EVIDENCE theo validator mới.
- Latest full verify: **324 passed, 7 skipped**; UI **11 passed**; TypeScript exit0. Receipt `verify-20261026T135251027454/receipt.json`. Two local OCR smoke tests previously ran/pass in `verify-20261026T131424477172/`; latest run intentionally skips them and five main-DB live opt-ins. Do not claim skipped passed or make synthetic tests into real-document acceptance.
- Frontend immutable snapshot **07**, build exit0. Only a visual spacing class was added after last tests; build07 checks TypeScript. Snapshot matches source.

## Active runtimes — bảo toàn runtime gốc

- Main **8015/3015**, DB `campus247_knowledge_local_20261023`, PG55437, schema0018, release `01a172fe-1822-7679-a515-335e063dd1fa`, generation27/policy3,114 serving. Main processes never stopped/restarted. Source120 raw; priority117 =24 CNTT+22 shared+71 deferred unchanged. Main source/schema/review/release unchanged; baseline evaluation added fresh conversations/login/logout records only.
- Prototype **8016/3016**, DB `campus247_automation_20261026_008daf8c925a`, schema0020, frontend07, generation disabled. Manifest `schema-rehearsal-restored-20261026T101117685822.json`. Correction0022 is tested code, not active on this prototype.
- Task-owned current exec sessions: frontend07 **63217** (node19388 at last read), API8016 **81867** (uvicorn21020), worker prototype **21997**. Recheck exact live PID/command identity before any process action; do not guess or stop main processes. Session tools may not carry across chats.
- To run full tests, pause **only this prototype worker** first: duplicate test uses the restored copy's real published bindings and otherwise races its queue. Main worker stays untouched. No lease/cap/reset workaround.
- Worker uses the existing shared BGE18081/reranker18082, not new model services. Keep 2 GiB RAM floor. RESOURCE_WAIT was observed, not bypassed.
- A new paid gateway on8017 **failed the existing single-writer ledger lock**. Do not alter/drop/release/replace that lock. No8017 listener currently remains. Baseline used the existing8015 gateway through normal HTTP and its existing guards.

## Restore bindings

- Initial full PG dump restore verified vectors/artifact metadata/membership.
- Complete scoped bundle `schema-rehearsal-bundle-20261026T125636532306.json`, DB `campus247_automation_20261026_fc5c770d07fc`, schema0021: 649 operational-tenant artifacts,100083724 bytes copied backup→restore,3 SQLite snapshots restored, fingerprints/integrity/FK checks pass. SQLite read transactions span PG exported snapshot; data_version stable for that capture. Other74 test-tenant artifact rows stay in PG dump but their separate stores are outside HUCE artifact backup scope; first cross-tenant root lookup failed and is retained, no deletion.
- `restore-runtime-20261026T130034144065.json`: restored app had new boot/ack, exact original/hash, owned historical citation/hash/locator, anonymous denied, fresh checker session denied after logout. That8017 process was stopped after verification; all restored data retained.
- 0021 empty rehearsal: `schema-rehearsal-20261026T124825291097.json`, DB5e053412ba3c.
- 0022 empty rehearsal: `schema-rehearsal-20261026T133349385686.json`, DB51403b34b00c.
- Old0020 test DB: `schema-rehearsal-20261026T090926324751.json`, DBabce1e052bde. All manifests under `infra/local/knowledge-automation-20261026/`.

## New baseline — actual failures to address, no more blind broad campaigns

Frozen gold `evals/datasets/knowledge-independent-20261026-v2.json`, SHA `6c5bfae6143b029c35f1fe4cca7968758e175db8e399aa238d041e2cececd28f`. Original v1 retained. Coding agent visually checked cached source PNGs PDF4,5,10,18,22,23,24 of QĐ1486; not institutional/human admission or proof of all later amendments. Block10 spans PDF4–5; course definitions are on PDF5, 50-hour credit on PDF4. Witness transcription/image hashes frozen before live answers.

Outputs:

- `independent-text-baseline-01.json`: 12 observations/11 unique questions. One initial missing-final attempt retained, then one explicit successful diagnostic for first question and remaining10 questions; latest observation per question selected by time, not best score. First-attempt dispositions8/11; latest9/11. Existing runtime baseline only, **not candidate-code evaluation**.
- `independent-text-diagnostic-01.json`:7 answered pass material/source checks,1 correct-explanation abstention,3 flags. No claim all prose semantics verified. Prior223/224 verdict unchanged;65 old replay flags are not65 proven wrong answers.
- Segments `live-independent-20261026T140135511601`, `...T140703087919`, `...T141127388101`; all raw per-case receipts retained. First failed attempt did not save raw SSE; later two segments save streams. A preceding no-listener attempt has0 cases and is retained separately.
- Shared paid ledger delta across segments:42 calls,51856 input,1888 output, conservativeUSD0.0178224; counters shared, not exclusive billing/agent quota. Old unsettled attempts/caps/locks preserved. Account snapshot `account-usage-20261026T132337322222.json` is shared-account usage, no task-start quota baseline.

Three concrete issues (diagnose general routing/retrieval/gate causes; **do not hardcode these questions or lower expected facts**):

1. `fresh_transfer_ceiling`: “Em muốn chuyển đổi kết quả đã học sang chương trình mới: phần được công nhận tối đa tính trên khối lượng nào?” Runtime abstained with “tìm được nguồn nhưng chưa xác minh…”. Source PDF18 Điều12(3) explicitly caps recognition/transfer at50% of the programme's minimum workload. Inspect saved stream/final and candidate/gate behavior.
2. `fresh_no_registration_reason`: “Bỏ đăng ký học tập thì có tự động bị cảnh báo trong mọi trường hợp không?” Runtime said no official source. PDF24 Điều19(5) explicitly conditions warning on no legitimate reason. Need preserve negation/condition.
3. `fresh_personal_schedule`: “Ngày mai tài khoản sinh viên HUCE của em phải học ở phòng nào?” Runtime abstains but says missing official document rather than explaining missing personal HUCE API/SSO. Do not fabricate schedule, grades or real student identity.

The new live run is a bounded baseline to reveal defects; don't immediately rerun224 old questions, use a model judge as sole truth, rewrite source/gold to make tests green, or claim benchmark/SLA from local timings.

## Remaining limits

P07 verified semantic dependency graphs, OCR evidence-unit integration, merged tables/arrows; P08 serving integration and decision UI; P09 live correction UI on0022 and structured corrections; P10 incremental units/pages; P11 scoped automation authority (none enabled; no fake reviewer/confirmation bypass); P12 defects above/multiturn/multisource full checks; P13 application sync/effective-date scheduling; P14 load/cancel/long-job; P15 real three-type/novel-source full UI pilot and46-source shadow migration; P16 rollout/acceptance remain.

Novel official PDF fetch at khcn.huce.edu.vn failed strict TLS chain validation. No certificate bypass or trust-store weakening. File/URL/redirect/DNS guards remain. Keep missing business facts UNKNOWN, not ALL/date-of-upload. Preserve71 deferred sources and114 existing members. Don't advertise fully autonomous source-to-answer until those gaps and actual reviewer/authority requirements are met.

Final checkpoint JSON: `infra/local/knowledge-automation-20261026/checkpoint-20261026T142917811865.json`. Capture confirms same133 tracked states/HEAD, prototype snapshot matches source, old source/version/review/release counts retained. Overall goal remains incomplete.

**Continuation 27/10/2026:** Đọc thêm `docs/DOCUMENT_KNOWLEDGE_AUTOMATION_PROGRESS_20261027.md`. Checkpoint mới `infra/local/knowledge-automation-20261026/checkpoint-20261026T175836882985.json`; prototype riêng8018/3018 đã có schema0022/snapshot09 và proposal UI tổng hợp, không có independent review/publication. Main và prototype cũ giữ riêng. Các giới hạn candidate answer/semantic dependency/P00–P16 chưa hoàn tất vẫn áp dụng.
