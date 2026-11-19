---
name: ninerouter-workers
description: Điều phối các worker Antigravity qua 9router (gateway local 127.0.0.1:20128, model ag/gemini-3.8-flash-high). Claude là đầu não, worker là công nhân. Chỉ dùng khi người dùng yêu cầu dùng 9router/antigravity/worker, hoặc đã bật nó cho phiên hiện tại. Gồm: giao việc gì, không giao việc gì, quy trình giao → guard → duyệt → áp dụng → kiểm, và các script worker.py, guard.py, fanout.py.
---

# 9router workers: Claude chỉ huy, Antigravity làm

**Mục tiêu:** tiết kiệm quota Claude và làm nhanh hơn. Việc tốn token, lặt vặt hay làm hàng loạt thì giao worker. Quota Antigravity không phải lo, cứ giao rộng tay và chạy song song. Claude giữ phần phán đoán, logic cốt lõi, dữ liệu và bước duyệt cuối.

**Bật/tắt:** chỉ dùng khi người dùng yêu cầu. Nếu không, Claude làm việc bình thường như trước.

## Vì sao worker không thể gây sai lầm lớn

Có ba lớp kiểm soát, và chúng nằm trong code, không dựa vào việc worker tự giác:

1. **Worker chỉ trả về chữ.** Nó không có tool, không có filesystem, shell hay git. Mọi thay đổi đều phải đi qua `guard.py` và Claude.
2. **`guard.py` chặn cứng theo chính sách** (`scripts/common.py`):
   - **Đường dẫn:** ghi ngoài `--allow` hoặc vào `HARD_DENY` (toàn bộ `services/api/src/**`, migrations, `contracts/`, `data/`, evidence, backup, `.env`, `apps/web/src/lib/**`, `apps/web/src/app/api/**`, manifest và lockfile, `.claude/`, `AGENTS.md`). `HARD_DENY` không có cờ vượt qua. Các mẹo trên Windows cũng bị chặn: đổi hoa thường, dấu chấm hoặc khoảng trắng ở cuối tên, `a:b`, tên ngắn `~1`, symlink trỏ vào vùng cấm.
   - **Code thêm vào:** lệnh xóa (file, SQL, rm, Remove-Item), git, subprocess, `eval`, `dangerouslySetInnerHTML`, xóa dữ liệu client, giá trị giống bí mật, chữ `<REDACTED>` (sẽ đè lên khóa thật), tiền tố số dòng chép từ context.
   - **File hỏng:** file co mạnh, file rỗng, chỗ viết tắt "...", mất `export`, SEARCH không khớp đúng một chỗ, ghi đè cả file mà worker chưa được xem trọn file đó. Mất `data-testid` hay `aria-`, hoặc có `fetch`/URL ngoài thì chỉ cảnh báo, Claude tự xem.
   - **Áp dụng:** `apply` từ chối nếu file đích đã đổi kể từ lúc giao việc. Nó luôn sao lưu bản gốc, và `revert` chỉ hoàn tác những file chưa ai sửa thêm.
3. **Claude duyệt và tự kiểm** (tsc, test, trình duyệt) trước khi coi việc là xong.

**Dữ liệu rời máy:** context gửi cho worker đi qua Google/Antigravity. `worker.py` tự loại `.env`, DB, `data/`, backup, evidence và che các chuỗi giống khóa. Claude không đưa dữ liệu thật của người dùng hay sinh viên vào brief.

## Phân việc

| Giao worker | Claude tự làm |
|---|---|
| Giao diện: component, style Tailwind, responsive, trạng thái loading/empty/error, a11y, chữ tiếng Việt trên UI | Logic nghiệp vụ, `services/api/src/**`, RAG, agent, LangGraph, quyền, xác thực, xác nhận hành động |
| Đọc nhiều: tóm tắt file, log hay output test dài, dò pattern trên nhiều file (scout) | Thiết kế kiến trúc, chọn giải pháp, quyết định giữ hoặc bỏ |
| Viết test UI (vitest, playwright), fixture **tổng hợp**, docstring, comment, tài liệu nháp | Schema, migration, dữ liệu DB, eval gold, hợp đồng API |
| Việc hàng loạt: đổi chữ, i18n, sửa lint, đổi tên theo mẫu trên nhiều file, bản nháp đầu | `apps/web/src/lib/**` (API client, auth), route server, cấu hình, dependency |
| Ý kiến thứ hai: review một diff, gợi ý ca biên | Git (commit, push), xóa, chạy runtime, đụng tài khoản, bí mật |

Khi phân vân, coi việc đó là cốt lõi và Claude tự làm.

**Không bó buộc quá mức:**
- Ngoài `HARD_DENY`, Claude tự quyết `--allow` rộng hay hẹp theo việc. Ví dụ: thêm `services/api/tests/**` để worker viết test backend, hoặc `docs/**` để viết tài liệu nháp.
- Việc nhỏ hơn 5 phút mà Claude tự làm rẻ hơn viết brief (sửa 1–3 dòng đã biết rõ) thì cứ tự làm.
- 9router không chạy (`--ping` báo DOWN) thì Claude làm bình thường, không chờ.

## Quy trình

1. **Chia việc.** Mỗi job là một việc nhỏ, có danh sách file được ghi rõ ràng. Các job song song không được ghi trùng file.
2. **Viết brief ngắn** theo [references/brief-template.md](references/brief-template.md). `worker.py` tự nối danh sách [lỗi worker hay mắc](references/worker-pitfalls.md) vào system prompt của mọi job và bắt worker rà từng điểm trước khi trả lời; không cần dán lại vào brief. Đưa file qua `--context`, không dán nội dung vào brief. Nêu tiêu chí nghiệm thu đo được.
3. **Giao việc** bằng `worker.py` (một job) hoặc `fanout.py` (nhiều job). Chỉ in bản tóm tắt; output đầy đủ nằm trong thư mục run.
4. **Đọc kết quả guard.**
   - `guard_blocked`: đọc lý do, không sửa chính sách. Gửi lời sửa bằng `--followup RUN --brief-text "sửa đúng lỗi X"`: worker nhận lại cả cuộc hội thoại cùng các phát hiện của guard, nên brief sửa chỉ cần 1 câu.
   - `question`/`blocked`: trả lời qua `--followup`, hoặc Claude tự làm.
   - Một job ghi nhiều file mà chỉ vài file đạt: áp dụng riêng file đạt bằng `apply RUN --only path`.
   - **Lỗi mà guard không bắt** (tsc, vitest hay mắt thường mới thấy): thêm một mục vào [references/worker-pitfalls.md](references/worker-pitfalls.md) ngay sau khi sửa, để các lần giao sau không lặp lại.
5. **Duyệt theo mức rủi ro** ([references/review.md](references/review.md)). Chỉ đọc diff cần đọc (`guard.py diff RUN --path P`), không đọc lại cả file.
6. **Áp dụng** bằng `guard.py apply RUN`. Không chép tay output của worker vào repo.
7. **Kiểm tra** theo skill `campus247` (tsc, vitest file liên quan, trình duyệt nếu là UI). Lỗi nhỏ thì Claude sửa thẳng; lỗi lớn thì `guard.py revert RUN` rồi giao lại hoặc tự làm.
8. **Giới hạn:** tối đa 2 lần giao lại cho một việc. Sau đó Claude tự làm, không lặp mãi.

## Lệnh

Chạy từ gốc repo, luôn dùng `python -I`. Mở đầu phiên bằng `--ping`; lệnh này mất khoảng 1 giây và không gọi model.

```bash
python -I .claude/skills/ninerouter-workers/scripts/worker.py --ping
```

```bash
python -I .claude/skills/ninerouter-workers/scripts/worker.py --id ten-viec --brief-text "..." --context "apps/web/src/components/X.tsx" --mode edit --allow "apps/web/src/components/X.tsx"
```

```bash
python -I .claude/skills/ninerouter-workers/scripts/worker.py --followup RUN_DIR --brief-text "Sửa đúng lỗi tsc: ... Không đổi gì khác."
```

```bash
python -I .claude/skills/ninerouter-workers/scripts/fanout.py jobs.json --parallel 8
```

```bash
python -I .claude/skills/ninerouter-workers/scripts/guard.py diff RUN_DIR --path apps/web/src/components/X.tsx
```

```bash
python -I .claude/skills/ninerouter-workers/scripts/guard.py apply RUN_DIR
```

```bash
python -I .claude/skills/ninerouter-workers/scripts/guard.py revert RUN_DIR
```

- **Chế độ `--mode`:**
  - `text`: trả lời Markdown.
  - `json`: JSON theo schema trong brief. Thêm `--verify-quotes` thì mỗi phát hiện phải có `path`, `line`, `quote`, và code đối chiếu với file thật.
  - `edit` (**mặc định khi sửa file có sẵn**): worker trả các khối SEARCH/REPLACE; script ghép vào file thật, chấp nhận lệch khoảng trắng hoặc thụt lề. Nhanh hơn và ít token hơn hẳn: sửa 1 dòng trong file 120 dòng chỉ ra khoảng 600 token. Không có nguy cơ worker viết lại cả file rồi làm rơi code.
  - `files`: worker trả nội dung đầy đủ của từng file. Dùng cho file mới, hoặc viết lại file nhỏ dưới khoảng 150 dòng. File có sẵn phải có trọn trong `--context`, nếu không guard chặn.
- **`--context`:** nhận đường dẫn, glob, hoặc `path:START-END`. Mặc định giới hạn 120 KB mỗi file và 900 KB tổng.
- **Thư mục run:** `~/.claude/ninerouter-runs/<thời-điểm>-<id>/`, chứa `prompt.md`, `response.md`, `meta.json`, `changes.patch`, `check.json`, `backup/`.
- **Cấu hình:** các biến `NINEROUTER_*` trong `.env` (file này đã gitignore). Không in key.
- **Sửa chính sách:** chính sách nằm ở `scripts/common.py`. Mỗi lần sửa xong phải chạy `python -I .claude/skills/ninerouter-workers/scripts/selftest.py` (offline, không gọi model). Chỉ nới chính sách khi người dùng yêu cầu.
- **Thời gian:** model high thường mất 1,5–2 phút mỗi job. Luôn dùng stream vì gọi không stream sẽ bị treo; script đã xử lý việc này.
  - Gom việc rồi fan-out song song (6–8 job) thay vì chạy lần lượt.
  - Trong lúc chờ, Claude làm phần cốt lõi của mình: chạy `fanout.py` ở chế độ nền (`run_in_background`), không ngồi chờ.
  - Bash có timeout mặc định 2 phút, nên luôn đặt `timeout` khoảng 600000 hoặc chạy nền.

## Công thức theo loại việc

- `ninerouter-scout`: đọc và tóm tắt nhiều file thay Claude, kèm trích dẫn đã kiểm. Đây là cách tiết kiệm quota nhất.
- `ninerouter-ui`: giao việc giao diện trong `apps/web`.
- `ninerouter-bulk`: giao hàng loạt việc nhỏ cùng mẫu (test, chữ, fixture, docstring).
