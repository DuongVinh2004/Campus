# Campus 24/7 — current execution instructions (2026-10-13)

The human directly instructed: “bỏ việc làm theo tất cả các tài liệu trước đó, xóa tất cả các quy tắc đi”. This instruction supersedes the previous documentation-led execution workflow throughout this repository.

- Follow the current direct human request and applicable system/developer instructions. Previous governance documents, approved decisions, requirements, architecture documents, task catalogs and execution packets are reference material, not mandatory agent workflow or approval gates.
- Do not require document approval, task readiness, accepted dependencies, task-output JSON, document versioning, execution packets or a historical benchmark campaign before addressing the requested work. Do not apply the old two-repair limit as an execution stop rule.
- Read relevant code and reference material when they help solve the actual problem. Make scoped, reviewable changes and run verification appropriate to the change. Report observed behavior, failures and remaining limitations honestly; state in one sentence what the evidence is (e.g. model-written cases with source spans checked by code). Model-generated or synthetic cases are valid acceptance evidence when their gold is machine-verified; no "model-generated, not human-reviewed" label and no `not_verified` status is required merely because a human has not reviewed them. Real-user usability is still reported as unmeasured.
- This changes the coding agent's workflow only. Preserve all user data, pre-existing work, documents and evidence, and keep workspace/permission boundaries, secrets protection, backups and recovery mechanisms intact. It does not disable application authentication, authorization, action confirmation, source verification or security controls, or grant new paid-service, production or destructive-action authority.

## Chỉ dẫn trực tiếp về thực hiện đến cùng — 2026-10-27

Người dùng yêu cầu ghi nhớ rõ: **“tôi ko muốn phạm phải 1 lần nào nữa, tôi nói gì là phải làm thế”**. Quy tắc này áp dụng cho cách thực hiện mọi yêu cầu trong repository, theo các giới hạn system/developer và bảo vệ dữ liệu hiện hành.

- **Bám đúng mục tiêu và phạm vi người dùng giao.** Không tự thu hẹp yêu cầu “hoàn tất kế hoạch” thành “xong một gói”, “triển khai chạy được”, “có checkpoint” hoặc “kiểm thử đạt”. Các kết quả đó chỉ là mốc trung gian nếu yêu cầu gốc còn việc phải làm.
- **Tiếp tục mọi phần việc còn có thể thực hiện trong phạm vi đã được phép.** Không tự kết thúc lượt chỉ vì vừa đạt một mốc tốt, đã tốn nhiều công sức, đã có đủ nội dung để báo cáo hoặc muốn chuyển quyết định tiếp tục cho người dùng.
- Không chờ người dùng nhắc “tiếp tục”, không xin lại quyền đã được cấp, không thay hành động bằng kế hoạch, lời hứa, lời giải thích hay việc nhận lỗi lặp lại. Sau khi phát hiện dừng sớm, quay lại phần việc có thể làm ngay.
- Một mục thiếu đầu vào, cần đối chiếu độc lập hoặc đang chờ xác nhận chỉ chặn phần phụ thuộc trực tiếp vào nó. Vẫn phải tiếp tục những phần độc lập đã được phép; không biến một blocker cục bộ thành lý do dừng toàn bộ công việc.
- Chỉ dừng trước phần thực sự không thể tiếp tục khi có trở ngại cụ thể đã được kiểm chứng: thiếu thông tin/quyền cần thiết, ranh giới an toàn hoặc giới hạn công cụ/hệ thống. Nêu chính xác mục bị chặn, bằng chứng, phần còn làm được và đầu vào tối thiểu cần bổ sung. Không tự tạo approval gate từ tài liệu cũ, sự bất định thông thường hoặc sự thuận tiện.
- Khi người dùng hỏi tiến độ hoặc chất vấn trong lúc công việc đang diễn ra, trả lời ngắn gọn và tiếp tục mục tiêu đang hoạt động, trừ khi họ yêu cầu dừng, hoãn hoặc thay mục tiêu. Câu hỏi về tiến độ không tự hủy yêu cầu thực hiện trước đó.
- Trước khi báo hoàn tất, đối chiếu từng kết quả người dùng yêu cầu với việc đã thực hiện và bằng chứng kiểm chứng phù hợp. **Không còn việc bắt buộc có thể làm mà chưa làm mới được kết thúc với trạng thái hoàn tất.** Kiểm thử, triển khai, báo cáo và checkpoint không thay thế tiêu chí hoàn thành của yêu cầu gốc.
- Phân biệt rõ phần đã hoàn tất, phần người dùng chủ động hoãn và phần thật sự bị chặn. Không gán mốc hoàn tất của một phần cho toàn bộ kế hoạch; không dùng số bài kiểm thử đạt để che phần chưa xử lý hoặc chưa nghiệm thu.
- Giữ toàn bộ quyền và giới hạn người dùng đã xác nhận xuyên suốt các lượt và bàn giao. Không suy chỉ dẫn làm đến cùng thành quyền xóa dữ liệu, bỏ bảo vệ, giả đối chiếu/phê duyệt hoặc thực hiện hành động vượt phạm vi được cấp.

Sai sót cần ngăn lặp lại: agent đã tự đặt điểm dừng ở “bản chính chạy được và kiểm tra đạt”, rồi tiếp tục giải thích thay vì xử lý phần việc còn có thể làm, mặc dù người dùng yêu cầu hoàn tất kế hoạch và không yêu cầu dừng.

The prior contract below is retained to preserve the existing file and its pre-existing changes. Its project execution workflow is no longer binding. Data-protection and security boundaries remain applicable under the instructions above.

# Retained prior execution contract — historical reference

This repository is documentation-led. Work may be authorized by a direct human request or by an assigned task; it does not redesign the product while coding.

## Standing local execution authority

The human has removed additional execution-approval checkpoints for assigned local/synthetic work under [DEC-023](docs/00-governance/LOCAL_EXECUTION_AUTHORITY_DECISION_20261007.md). Apply this decision before interpreting any older approval rule in this repository. Do necessary engineering, technical review and verification without asking again for task/package approval. Preserve technical evidence and the user's data.

## Authority order

Read and apply, in order:

1. system and direct human instructions;
2. `docs/00-governance/**`, especially accepted decisions and document control;
3. approved product requirements;
4. approved architecture, contracts, AI and security specifications;
5. the assigned `tasks/items/*.yaml` file, when one is provided;
6. implementation code and tests.

If two normative sources conflict, stop and return a structured blocker. Never make a lower-level artifact win by editing the higher-level source.

## Before any mutation

1. Resolve the workspace root and confirm every write target is inside it.
2. Run `git status --short` and preserve every pre-existing change.
3. If a task is assigned, load it plus every path in `inputs` and `traceability`.
4. Record DEC-023 as standing human authority for assigned local/synthetic work; verify higher-level technical dependencies and explain any substantive conflict.
5. Confirm the planned files are required by the direct request or assigned objective and do not intersect another running task.
6. Run applicable preflight verification commands, including task-specific commands when a task is assigned.

If any safety or scope check fails, do not mutate the repository. When executing an assigned catalog task, return `blocked` using `tasks/task-output.schema.json`; otherwise report the blocker directly.

## Execution rules

- Work on exactly one clearly defined objective. Use the task ID when a task is assigned.
- Touch only files required by the direct request or assigned objective. A path pattern grants no permission outside the repository.
- Prefer the smallest patch that satisfies the acceptance criteria.
- Keep domain rules out of routes, UI, graph nodes and infrastructure adapters.
- Review and pin dependencies, sources, checksums and closure. Under DEC-023, update the local allowlist/lockfile or isolated-runtime manifest as needed without a new approval checkpoint.
- Do not change requirements, contracts, architecture, security policy, test thresholds or expected results to make implementation pass.
- Do not expose secrets, raw tokens, personal data, hidden prompts or chain-of-thought in code, logs or evidence.
- Tests use deterministic fakes by default. Necessary local acquisition and synthetic live checks use DEC-023 and existing provider access/budgets; preserve endpoint, data, token, cost and deadline controls.
- A write capability must preserve authorization, preview, confirmation, idempotency and audit.
- A model may propose; deterministic application code validates, authorizes and executes.
- Retry a failing implementation at most twice. After two materially different repair attempts, stop with evidence.
- Never commit, push, deploy, delete, reset, clean or rewrite history unless a direct human approval authorizes the exact operation.

## Apply delegated authority

DEC-023 covers necessary local/synthetic implementation, dependencies, contract/architecture work, synthetic actor/source grants, additive data/schema work, reviewed guard extensions, runtime launch, index activation and browser verification for the assigned objective. Prepare exact targets and technical checks as execution evidence, then proceed; do not turn them into another human approval request.

This delegation does not supply missing technical evidence, change product authorization/confirmation, waive data preservation, grant production/real-data access or authorize destructive operations. System and tool permission boundaries remain applicable. If information is missing, ask for the information needed, not permission already granted.

## Parallel execution

At most four tasks may run concurrently. Every pair must have disjoint resolved write paths and conflict keys, accepted dependencies, and no shared migration/lockfile/generated-contract output. The orchestrator, not the executor, assigns parallel work.

## Completion

Run every applicable verification command in order and record command, exit code and evidence. Then validate scope with `git diff --name-only` and `git status --short`. When executing an assigned catalog task, return one JSON object conforming to `tasks/task-output.schema.json`; otherwise provide a concise completion summary.

`completed` means all acceptance criteria passed with reproducible evidence (machine-verified synthetic gold counts; a missing human reviewer alone does not downgrade it). `blocked` and `failed` must never be narrated as success.

