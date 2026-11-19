import React from "react";
import { afterEach, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { LearningNotifications, type LearningUpdate } from "./LearningNotifications";

const api = vi.hoisted(() => ({ list: vi.fn(), write: vi.fn() }));
vi.mock("../../lib/data/api/learning-gateway", () => ({ LearningGateway: class { list = api.list; write = api.write; } }));
const notice = (title = "Bài giảng mới", read_at: string | null = null): LearningUpdate => ({
  id: "019a0000-0000-7000-8000-000000000001", title,
  version_id: "019a0000-0000-7000-8000-000000000002",
  material_id: "019a0000-0000-7000-8000-000000000003",
  read_at, revision: 1, created_at: "2026-11-09T02:00:00Z", event_type: "MATERIAL_PUBLISHED",
});
afterEach(() => { cleanup(); vi.resetAllMocks(); });

it("clears a failed refresh message when a later refresh succeeds", async () => {
  api.list.mockRejectedValueOnce(new Error("Mất kết nối kiểm thử")).mockResolvedValue([notice()]);
  render(<LearningNotifications onOpen={() => {}} />);
  fireEvent.click(screen.getByText(/Cập nhật học liệu/));
  await screen.findByRole("alert");
  fireEvent.click(screen.getByRole("button", { name: "Tải lại thông báo" }));
  await screen.findByText("Bài giảng mới");
  expect(screen.queryByRole("alert")).toBeNull();
});

it("prevents duplicate read writes while opening a notification", async () => {
  let finish!: () => void;
  const onOpen = vi.fn();
  api.list.mockResolvedValue([notice()]);
  api.write.mockImplementation(() => new Promise<void>(resolve => { finish = resolve; }));
  render(<LearningNotifications onOpen={onOpen} />);
  fireEvent.click(screen.getByText(/Cập nhật học liệu/));
  const open = await screen.findByRole("button", { name: "Mở bản được công bố" });
  fireEvent.click(open);
  expect((open as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(open);
  expect(api.write).toHaveBeenCalledTimes(1);
  api.list.mockResolvedValue([notice("Bài giảng mới", "2026-11-09T02:01:00Z")]);
  await act(async () => { finish(); });
  await waitFor(() => expect(onOpen).toHaveBeenCalledTimes(1));
});

it("opens an already read notification without changing its receipt again", async () => {
  const item = notice("Đã xem từ trước", "2026-11-09T02:01:00Z");
  const onOpen = vi.fn();
  api.list.mockResolvedValue([item]);
  render(<LearningNotifications onOpen={onOpen} />);
  fireEvent.click(screen.getByText(/Cập nhật học liệu/));
  fireEvent.click(await screen.findByRole("button", { name: "Mở bản được công bố" }));
  await waitFor(() => expect(onOpen).toHaveBeenCalledWith(item));
  expect(api.write).not.toHaveBeenCalled();
});

it("keeps the newest refresh when an older request resolves last", async () => {
  let finishOld!: (rows: LearningUpdate[]) => void;
  api.list.mockImplementationOnce(() => new Promise(resolve => { finishOld = resolve; }))
    .mockResolvedValueOnce([notice("Kết quả mới")]);
  render(<LearningNotifications onOpen={() => {}} />);
  fireEvent.click(screen.getByText(/Cập nhật học liệu/));
  fireEvent.click(screen.getByRole("button", { name: "Tải lại thông báo" }));
  await screen.findByText("Kết quả mới");
  await act(async () => { finishOld([notice("Kết quả cũ")]); });
  expect(screen.getByText("Kết quả mới")).toBeDefined();
  expect(screen.queryByText("Kết quả cũ")).toBeNull();
});

it("does not navigate after an in-flight open finishes on an unmounted panel", async () => {
  let finish!: () => void;
  const onOpen = vi.fn();
  api.list.mockResolvedValue([notice()]);
  api.write.mockImplementationOnce(() => new Promise<void>(resolve => { finish = resolve; }));
  const view = render(<LearningNotifications onOpen={onOpen} />);
  fireEvent.click(screen.getByText(/Cập nhật học liệu/));
  fireEvent.click(await screen.findByRole("button", { name: "Mở bản được công bố" }));
  view.unmount();
  await act(async () => { finish(); });
  expect(onOpen).not.toHaveBeenCalled();
});

it("does not report an empty list while the first request is pending", async () => {
  api.list.mockImplementationOnce(() => new Promise(() => {}));
  render(<LearningNotifications onOpen={() => {}} />);
  fireEvent.click(screen.getByText(/Cập nhật học liệu/));
  expect(screen.queryByText("Chưa có cập nhật học liệu được phép xem.")).toBeNull();
  expect(screen.getByRole("status").textContent).toBe("Đang tải thông báo…");
});
