---
name: ninerouter-ui
description: Giao việc giao diện trong apps/web (Next.js 16, React 19, Tailwind 4, tiếng Việt) cho worker Antigravity qua 9router — component, style, responsive, trạng thái loading/empty/error, a11y, chữ UI, test vitest/playwright cho UI — rồi Claude duyệt, áp dụng và kiểm. Chỉ dùng khi người dùng đã bật 9router. Dùng kèm ninerouter-workers.
---

# UI qua worker

## Phạm vi được giao

- **Được giao:** `apps/web/src/components/**`, `apps/web/src/features/**/*.tsx` (phần hiển thị), `apps/web/src/app/**/page.tsx` và `layout.tsx` (phần JSX/style), `apps/web/src/styles/**`, test `*.test.tsx`, `apps/web/e2e/**`.
- **Không giao** (guard chặn cứng): `apps/web/src/lib/**` (API client, auth, session), `apps/web/src/app/api/**`, middleware, `next.config.*`, `package.json`.
- **Một file vừa có hiển thị vừa có logic** (fetch, xác nhận hành động, phân quyền): chỉ giao phần hiển thị, và ghi trong brief "GIỮ NGUYÊN mọi hook, handler, lời gọi API, điều kiện quyền". Claude đọc toàn bộ diff (mức Vừa).

## Chế độ

- Sửa component có sẵn: `--mode edit`.
- Component mới hoặc file test mới: `--mode files`.

## Brief UI nên có

- Kết quả nhìn thấy được: bố cục, kích thước, màu theo token đang dùng, các breakpoint (375px, 768px, desktop).
- Trạng thái cần có: loading, empty, error, disabled; hỗ trợ bàn phím và focus.
- Bắt buộc giữ: `data-testid` hiện có. Thêm `data-testid` cho phần tử mới theo kiểu đặt tên của file.
- Chữ UI tiếng Việt có dấu, giọng giống các màn khác.
- Context: file cần sửa, một component mẫu cùng kiểu, test của file đó nếu có.

## Kiểm sau khi apply

Chạy trong `apps/web`:

```bash
npx tsc --noEmit
```

```bash
npx vitest run src/path/to/Component.test.tsx
```

- Có thay đổi hiển thị: xem trên runtime theo skill `campus247` (build snapshot, cổng 8015) ở cả 375px và desktop.
- tsc báo lỗi kiểu nhỏ: Claude sửa thẳng, rẻ hơn giao lại. Sai bố cục hay thiếu trạng thái: giao lại một lần, kèm mô tả hoặc ảnh chụp lỗi.

## Song song

Mỗi job một component hoặc một trang, không ghi trùng file. Muốn thêm test cho component đang sửa thì tách job test ra, và cho nó chạy sau khi component đã apply để context là bản mới.
