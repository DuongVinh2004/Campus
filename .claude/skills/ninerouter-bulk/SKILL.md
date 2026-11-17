---
name: ninerouter-bulk
description: Giao hàng loạt việc nhỏ cùng mẫu cho nhiều worker Antigravity song song qua 9router — viết test, docstring/comment, đổi chữ UI, sửa lint/kiểu theo mẫu, fixture tổng hợp, bản nháp tài liệu — bằng fanout.py, rồi Claude duyệt theo lô. Chỉ dùng khi người dùng đã bật 9router. Dùng kèm ninerouter-workers.
---

# Bulk: nhiều job nhỏ cùng mẫu

## Cách làm

1. **Liệt kê đơn vị việc.** Mỗi đơn vị là một file; Claude tự liệt kê bằng Glob hoặc Grep, hoặc dùng scout để liệt kê.
2. **Viết một brief mẫu chung** trong `defaults`. Mỗi job chỉ khác `id`, `context`, `allow` và vài dòng riêng.
3. **Làm thử 1–2 job trước.** Duyệt kỹ kết quả, chỉnh brief mẫu, rồi mới chạy cả lô. Như vậy tránh được việc 30 job cùng sai một kiểu.
4. **Chạy cả lô** với `fanout.py jobs.json --parallel 8`. Không cần `--show-output`, vì bản tóm tắt chỉ nêu file, BLOCK và cảnh báo.
5. **Duyệt theo lô.**
   - Job `ok` không có cảnh báo: apply. Lô 10 job thì lấy ngẫu nhiên 2–3 job đọc diff.
   - Job bị chặn hoặc có cảnh báo: xem riêng từng job.
6. **Kiểm cả lô một lần** (tsc, vitest hay pytest trên các file test mới), không kiểm từng file.

## jobs.json mẫu: viết test cho nhiều component

```json
{
  "defaults": {
    "mode": "files",
    "brief_text": "Viết file test vitest + @testing-library/react cho component trong context, theo đúng style của file test mẫu. Kiểm: render mặc định, các trạng thái, tương tác chính, data-testid có sẵn. Không mock thứ không cần. Chỉ ghi file test được phép.",
    "max_total_kb": 400
  },
  "jobs": [
    {"id": "t-toast", "context": ["apps/web/src/components/Toast.tsx", "apps/web/src/components/AsyncState.test.tsx"],
     "allow": ["apps/web/src/components/Toast.test.tsx"]},
    {"id": "t-skeleton", "context": ["apps/web/src/components/Skeleton.tsx", "apps/web/src/components/AsyncState.test.tsx"],
     "allow": ["apps/web/src/components/Skeleton.test.tsx"]}
  ]
}
```

Lưu `jobs.json` vào scratchpad, không để trong repo.

## Hợp với bulk

- Test UI hoặc test đơn vị cho hàm thuần. Test backend vào `services/api/tests/**` được phép khi Claude `--allow` đúng đường dẫn đó, nhưng file nguồn backend thì không.
- Đổi chữ, i18n, sửa lỗi dấu tiếng Việt trên nhiều trang.
- Docstring, comment, README nháp cho từng module (bản nháp; Claude duyệt nội dung kỹ thuật).
- Fixture tổng hợp: dữ liệu giả, ghi rõ là tổng hợp, không bắt chước người thật.

## Không hợp với bulk

- Việc mà các job phụ thuộc kết quả của nhau.
- Đổi API dùng chung trên nhiều file (cần một người làm nhất quán, nên Claude tự làm).
- Bất cứ việc gì thuộc cột "Claude tự làm" trong `ninerouter-workers`.
