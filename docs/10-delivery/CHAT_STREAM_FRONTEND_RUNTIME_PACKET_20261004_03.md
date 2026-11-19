---
document_id: "DOC-DELIVERY-CHAT-FRONTEND-PACKET-20261004-03"
version: "0.1.1"
status: "proposed"
owner: "Campus 24/7 Engineering"
approvers: []
last_updated: "2026-10-04"
---

# P-FE-VERIFY-003 — exact offline frontend verification packet

**Chưa được phép chạy Node/package code.** Packet này xin approval cho một run
TypeScript và ba frontend test files trong objective streaming đang dở. Không
xin engineering authorization chung, install, thay pins hay live RAG permission.
Không tuyên bố signature/tree hashes là independent security review.

## 1. Lý do cần scoped approval

Direct human request yêu cầu chỉ chạy frontend/browser khi runtime được xác
minh và có approval phù hợp. Execution plan 0.2.0 G0 yêu cầu runtime frontend
được xác minh/duyệt. Root AGENTS bắt buộc approval cho dependencies ngoài
allowlist; DEPENDENCY_ALLOWLIST section 3 chưa liệt kê Vitest, jsdom,
happy-dom, Testing Library hoặc các transitive test packages. Dependency verifier
hiện chỉ kiểm Python; exit 0 không cấp frontend clearance.

Human có thể phê duyệt **đúng P-FE-VERIFY-003** cho việc dùng bytes hiện có trong
inventory để kiểm thử offline. Approval không sửa approved allowlist, không cho
phép package/version mới hoặc miễn security/independent review nếu có gate áp
dụng. Nếu reviewer yêu cầu provenance/security evidence bổ sung, run vẫn pending;
không giả lập chữ ký reviewer. Không suy ra approval từ installation hay access.

## 2. Runtime và dependency bytes đã discovery read-only

Runtime được chọn: bundled Node trong desktop dependencies bundle `26.930.11008`.

```text
C:\Users\Duong Vinh\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe
Windows ProductVersion/FileVersion: 24.19.0
SHA-256: 3602f2bb1a10f2cbab4c36886218a33c1ab3db87290e73b033c46c77147d0237
Authenticode: Valid
Signer: OpenJS Foundation
```

Version là Windows executable metadata; `node --version` chưa chạy. Launcher
sẽ ghi version thực trước compiler/tests. PATH Node 26.5.1 (`Program Files`)
chỉ được inventory, không chọn hoặc chạy. Không dùng bundled Python khác;
launcher dùng fixture Python 3.12.14 `-B` đã được human duyệt.

Dependency set chính xác: toàn bộ **157 installed package records / 14.633 file
hashes** trong `infra/local/rag-fixture/chat-stream-20261004-03-frontend-inventory.json`.
SHA-256 inventory:
`68afe547f7c643856b912e179f03d4154571b7980a6dfa1138acc37e03ee0f54`.

Repository `pnpm-lock.yaml` và installed `.pnpm/lock.yaml` cùng SHA-256
`312ff19fc589d57b241982bb6249fe6e674efa1c311d2f2e66afda9c09bf3092`.
Không có package record ngoài lock, importer mismatch hoặc inspected link ra
ngoài workspace. Lock còn các optional platform packages không cài trên Windows;
inventory ghi từng tên, không install bổ sung.

| Direct package | Installed exact version |
|---|---|
| next | 14.2.35 |
| react / react-dom | 18.3.1 / 18.3.1 |
| typescript | 5.6.3 |
| vitest | 2.1.9 |
| jsdom / happy-dom | 25.0.1 / 20.14.5 |
| @testing-library/react / jest-dom | 16.3.3 / 6.10.0 |
| @types/node | 20.19.43 |
| @types/react / react-dom | 18.3.31 / 18.3.7 |

Native/transitive bytes, licenses, engines, entry hashes và full per-file hashes
nằm trong inventory, bao gồm esbuild 0.21.5, Rollup 4.63.4, Vite 5.4.21 và
Next SWC 14.2.33. Typecheck dùng TypeScript; tests dùng Vitest + jsdom và React
Testing Library; happy-dom không được chọn làm test environment. Next build/SWC
không được chạy trong packet này. Chỉ native **esbuild.exe** được phép spawn
với service protocol 0.21.5; các package records không tự cấp quyền child process.

Tree hashes bind current unpacked bytes, **không chứng minh** bytes khớp tarball
registry integrity trong lock. Không gọi registry, không install để tự lấp gap
provenance, không gọi candidate inventory là runtime clearance đã accepted.

## 3. Concrete prepared launch và output scope

Files đã chuẩn bị để review, chưa thực thi bằng Node:

- `infra/local/rag-fixture/chat-stream-20261004-03-frontend-launch.py`:
  SHA `b0ebfa2cd08d5ff5dce2e61daf294527af3183ace696de7ca857eb141c7a810a`.
- `infra/local/rag-fixture/chat-stream-20261004-03-frontend-guard.mjs`:
  SHA `4e4837c821560a733f1fb0d353fe312d1c2f2455d5e0be18ca6cd512d0b5e6d0`.
- `infra/local/rag-fixture/chat-stream-20261004-03-frontend-verify.mjs`:
  SHA `d970bc5ba89addff1819705696b4e6b2979b3e6ed90ed5cb42886aae934bc234`.

Sau direct human approval, ghi **fresh** receipt
`infra/local/rag-fixture/chat-stream-20261004-03-frontend-approval.json` có
packet ID/status, SHA của packet/guard/runner/inventory và reference tới actual
human message. Không tạo approved receipt khi human chưa trả lời.

Lệnh launcher exact, cwd `C:\Users\Duong Vinh\Vinh`:

```powershell
& 'C:\Users\Duong Vinh\Vinh\infra\local\rag-fixture\.venv\Scripts\python.exe' -B 'infra/local/rag-fixture/chat-stream-20261004-03-frontend-launch.py'
```

Launcher rehash runtime, dependency files, lock và tooling, require receipt,
exclusive-create fresh output root rồi chạy tuần tự (absolute paths trong script):

```text
<Node exact above> --version
<Node exact above> --import <frontend-guard.mjs> <frontend-verify.mjs> typecheck
<Node exact above> --import <frontend-guard.mjs> <frontend-verify.mjs> tests
```

`typecheck` đọc existing `apps/web/tsconfig.json`, dùng TypeScript API tương
đương `--noEmit --incremental false`; không ghi đè tsbuildinfo. Không sửa config
hoặc bỏ diagnostics để pass. `tests` gọi programmatic Vitest API hiện có với
existing config semantics: jsdom/globals, `@` alias và automatic JSX. `configFile`
false tránh temp config bundle/delete; `envFile:false` tắt automatic dotenv
loading trước credential guard (đã kiểm option trong installed Vite 5.4.21
source/types, chưa chạy Vite). Single thread, no watch/no cache/no HMR.
Test filters exact:

```text
apps/web/src/features/chat/sse.test.ts
apps/web/src/features/chat/ChatPanel.test.tsx
apps/web/src/app/chat/page.test.tsx
```

Canonical write/output root duy nhất của Node run:

```text
C:\Users\Duong Vinh\Vinh\infra\local\rag-fixture\chat-stream-20261004-03-frontend-run-01
```

Đầu ra: `version.log`, `typecheck.log`, `typecheck.json`, `tests.log`, `tests.json`,
`commands.json`, retained `temp/` và `vite-cache/` descendants. Child profile/temp
refs trỏ vào output root. Environment được tạo mới từ literal non-secret values,
không đọc/in inherited credentials. NODE_ENV=test chặn existing AppShell automatic
demo-session call trong test path; production AppShell không sửa.

Preload guard deny DNS/socket/network, credential/config paths, filesystem
deletion/rename/permission changes, write ngoài output root và subprocess ngoài
esbuild service exact. OS sandbox vẫn bắt buộc; JS guard không phải isolation
chống malicious native code và chưa được runtime-verified. Nếu tool thực hiện
write/delete/bind ngoài scope, dừng với evidence; không bypass guard cho tests pass.
Giữ log/artifacts cả khi fail, không rerun label đã tồn tại. Sửa implementation
tối đa hai materially different repairs theo AGENTS, với fresh baselines/labels.
Revision 0.1.1 hoàn tất static launcher review trước execution: tắt Vite dotenv,
không gán HOME và ghi explicit exit124 khi timeout. Các baseline trước chỉnh
tooling được giữ; đây chưa phải runtime/test failure hoặc approved execution.

## 4. Acceptance và giới hạn permission

Typecheck phải exit 0; cả ba test files phải pass, không unhandled errors hoặc
skip/drop tests để hợp thức hóa. Cases: success/final replacement, abstention,
safe terminal/transport failure, unknown/malformed/EOF, request/message binding,
fragmented UTF-8/newlines, provisional isolation, cancellation/loading và citation
mapping. Tests auth/ownership hiện có được giữ; backend ownership regression có
guarded offline evidence riêng.

Packet này **không** nghiệm thu browser, Next build, live API, durable DB,
real RAG/model quality hoặc M1. Production build dùng next/font/google; plain
Next build có thể load environment/config và fetch fonts. Không chạy build/dev
server trong packet này hoặc tự cấp egress vì font.

Browser candidate chỉ inventory read-only:
`C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`, metadata
version `154.0.4258.53`, Authenticode Valid/Microsoft Corporation, SHA
`39966f2799d3503e74871c945ba1c4877f38426d1c28756ab1545ad7c3de8907`.
Không launch browser, đọc profile/localStorage hoặc truy cập port8000. Port13003
chưa có listener tại lúc discovery; không reservation/launch. Packet browser
riêng cần concrete source-only synthetic fixture, isolated workspace profile,
exact browser/tool dependency hashes, loopback server/commands/output scope và
fault matrix sau kết quả frontend. Candidate Edge không thay approval đó.

Không install, chỉnh package manifests/lock/pins/allowlist/governance, đọc .env
hay Docker config/container environment, dùng default DATABASE_URL, DB/container,
live providers, model inference, commit/push/deploy, delete/reset/cleanup, agent
hoặc chat khác. Approval gói này chỉ áp dụng run/output scope trên.
