import React from "react";
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { ConversationHistory } from "./ConversationHistory";

const first = "019a0000-0000-7000-8000-000000000001";
const second = "019a0000-0000-7000-8000-000000000002";
const cursor = `${first}:synthetic&cursor=keep+literal`;
const page = (id: string, title: string, next: string | null = null) => ({
  items: [{ id, title }], page: { has_more: next !== null, next_cursor: next, limit: 20 },
});
const ok = (body: unknown) => ({ ok: true, status: 200, json: async () => body }) as Response;
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

it("loads another server page on request while retaining the first page and active selection", async () => {
  const fetcher = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(ok(page(first, "Trang đầu", cursor)))
    .mockResolvedValueOnce(ok(page(second, "Hội thoại tiếp theo")));
  render(<ConversationHistory activeId={second} revision={0} />);
  await screen.findByRole("link", { name: "Trang đầu" });
  expect(fetcher).toHaveBeenCalledTimes(1);
  fireEvent.click(screen.getByRole("button", { name: "Tải thêm hội thoại" }));
  const selected = await screen.findByRole("link", { name: "Hội thoại tiếp theo" });
  expect(selected.getAttribute("aria-current")).toBe("page");
  expect(screen.getByRole("link", { name: "Trang đầu" })).toBeDefined();
  expect(fetcher.mock.calls[1][0]).toContain(`&cursor=${encodeURIComponent(cursor)}`);
  expect(fetcher.mock.calls[1][1]?.credentials).toBe("include");
  expect(screen.queryByRole("button", { name: "Tải thêm hội thoại" })).toBeNull();
});

it("retains loaded links and retries the same cursor after a later page fails", async () => {
  const fetcher = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(ok(page(first, "Giữ hội thoại này", cursor)))
    .mockRejectedValueOnce(new Error("private transport detail"))
    .mockResolvedValueOnce(ok(page(second, "Đã thử lại")));
  render(<ConversationHistory activeId={first} revision={0} />);
  fireEvent.click(await screen.findByRole("button", { name: "Tải thêm hội thoại" }));
  await screen.findByText("Chưa tải được phần lịch sử tiếp theo. Bạn có thể thử lại.");
  expect(screen.getByRole("link", { name: "Giữ hội thoại này" })).toBeDefined();
  expect(screen.queryByText("private transport detail")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Tải thêm hội thoại" }));
  await screen.findByRole("link", { name: "Đã thử lại" });
  expect(fetcher.mock.calls[1][0]).toBe(fetcher.mock.calls[2][0]);
});

it("distinguishes forbidden history from a network failure", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue({ ok: false, status: 403 } as Response);
  render(<ConversationHistory activeId={null} revision={0} />);
  await screen.findByText("Tài khoản này không có quyền xem danh sách hội thoại.");
  expect(screen.queryByText(/Chưa tải được lịch sử/)).toBeNull();
});

it("does not show stale page results after the history revision changes", async () => {
  let finishOld!: (value: Response) => void;
  const fetcher = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(ok(page(first, "Lượt cũ", cursor)))
    .mockImplementationOnce(() => new Promise(resolve => { finishOld = resolve; }))
    .mockResolvedValueOnce(ok(page(second, "Lượt mới")));
  const view = render(<ConversationHistory activeId={null} revision={0} />);
  fireEvent.click(await screen.findByRole("button", { name: "Tải thêm hội thoại" }));
  await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(2));
  view.rerender(<ConversationHistory activeId={null} revision={1} />);
  await screen.findByRole("link", { name: "Lượt mới" });
  finishOld(ok(page(first, "Kết quả đã cũ")));
  await waitFor(() => expect(screen.queryByRole("link", { name: "Kết quả đã cũ" })).toBeNull());
  expect(screen.queryByRole("link", { name: "Lượt cũ" })).toBeNull();
});

it.each(["repeated-cursor", "duplicate-item"])("keeps existing history when another page has %s", async fault => {
  vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(ok(page(first, "Dữ liệu đã đọc", cursor)))
    .mockResolvedValueOnce(ok(page(fault === "duplicate-item" ? first : second, "Trang lỗi", fault === "repeated-cursor" ? cursor : null)));
  render(<ConversationHistory activeId={null} revision={0} />);
  fireEvent.click(await screen.findByRole("button", { name: "Tải thêm hội thoại" }));
  await screen.findByText("Chưa tải được phần lịch sử tiếp theo. Bạn có thể thử lại.");
  expect(screen.getByRole("link", { name: "Dữ liệu đã đọc" })).toBeDefined();
  expect(screen.queryByRole("link", { name: "Trang lỗi" })).toBeNull();
});

it("delegates an ordinary history click without document navigation", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(ok(page(first, "Select in place")));
  const select = vi.fn();
  render(<ConversationHistory activeId={null} revision={0} onSelect={select} />);
  const link = await screen.findByRole("link", { name: "Select in place" });
  expect(link.getAttribute("href")).toBe(`/chat?conversation_id=${first}`);
  expect(fireEvent.click(link)).toBe(false);
  expect(select).toHaveBeenCalledWith(first);
});

it.each([{ ctrlKey: true }, { metaKey: true }, { shiftKey: true }, { altKey: true }, { button: 1 }])("preserves native modified-link behavior for %j", async modifiers => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(ok(page(first, "Open separately")));
  const select = vi.fn();
  render(<ConversationHistory activeId={null} revision={0} onSelect={select} />);
  const link = await screen.findByRole("link", { name: "Open separately" });
  let cancelledByComponent: boolean | undefined;
  const observe = (event: Event) => { cancelledByComponent = event.defaultPrevented; event.preventDefault(); };
  document.addEventListener("click", observe);
  try { fireEvent.click(link, modifiers); } finally { document.removeEventListener("click", observe); }
  expect(cancelledByComponent).toBe(false);
  expect(select).not.toHaveBeenCalled();
});
