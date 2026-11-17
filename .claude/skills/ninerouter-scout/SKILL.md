---
name: ninerouter-scout
description: Giao worker Antigravity (9router) đọc và tóm tắt thay Claude để tiết kiệm quota — file dài, nhiều file, log, output test hoặc build, diff lớn, tài liệu — và trả về phát hiện có trích dẫn path:line đã kiểm bằng code. Chỉ dùng khi người dùng đã bật 9router. Dùng kèm ninerouter-workers.
---

# Scout: worker đọc, Claude chỉ đọc chỗ cần

Đây là cách tiết kiệm quota Claude nhiều nhất. Thay vì Claude tự đọc 3.000 dòng, worker đọc rồi trả về khoảng 20 dòng phát hiện. Code kiểm từng trích dẫn với file thật; Claude chỉ mở đúng những dòng được trích.

## Khi nào dùng

- Cần hiểu một vùng code lạ trải trên hơn 3 file, hoặc file trên 400 dòng.
- Log, output pytest, vitest, playwright hay build dài: cần tìm lỗi gốc.
- Dò pattern trên nhiều file, ví dụ "component nào thiếu loading state" hay "chỗ nào hard-code chữ tiếng Anh".
- Tóm tắt tài liệu trong `docs/` để lấy ý chính.

**Không dùng** để quyết định logic cốt lõi. Phát hiện của scout là manh mối; Claude vẫn xác minh trước khi hành động.

## Lệnh

Hỏi đáp có trích dẫn đã kiểm:

```bash
python -I .claude/skills/ninerouter-workers/scripts/worker.py --id scout-xyz --mode json --verify-quotes --context "apps/web/src/features/chat/**/*.tsx" --brief-text "Tìm ... Schema: [{\"path\": str, \"line\": int, \"quote\": str, \"finding\": str}]. Tối đa 15 mục, xếp theo mức quan trọng."
```

Log hoặc output dài: ghi ra scratchpad (thư mục temp) trước, rồi đưa đường dẫn tuyệt đối vào `--context`. Ngoài repo, script chỉ nhận file nằm trong thư mục temp:

```bash
python -I .claude/skills/ninerouter-workers/scripts/worker.py --id scout-log --mode text --words 200 --context "<scratchpad>/run.log" --brief-text "Tìm lỗi gốc (không phải lỗi dây chuyền). Trả: test hỏng, thông báo lỗi, file:line nguồn, giả thuyết nguyên nhân."
```

## Đọc kết quả

- Xem `quote_check.failed` trong tóm tắt: mục `_verified: false` trong `result.json` là bịa hoặc lệch dòng, bỏ qua.
- Chỉ mở file ở các dòng được trích bằng `Read` với `offset`/`limit`. Không đọc cả file.
- Nhiều vùng khác nhau thì fan-out nhiều scout song song, mỗi scout một vùng (dùng `fanout.py`).
- Scout trả ít hoặc mơ hồ: hỏi lại với câu hỏi hẹp hơn. Đừng chuyển sang tự đọc toàn bộ ngay.
