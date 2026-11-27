import React from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({ authored: vi.fn(), approvals: vi.fn(), stats: vi.fn(), approve: vi.fn(), reject: vi.fn(), withdrawPreview: vi.fn(), withdrawConfirm: vi.fn(), revisionPreview: vi.fn(), revisionConfirm: vi.fn() }));
vi.mock("../../lib/announcements-api", () => ({ announcementsApi: api }));
import { AnnouncementManager } from "./AnnouncementManager";

const item = (over = {}) => ({ id: "a1", code: "TB-2026-000001", title: "Lịch thi cuối kỳ", category: "EXAM", priority: "NORMAL", issuer_unit: "Phòng Đào tạo",
  status: "PUBLISHED", revision: 1, expires_at: "2026-12-31T00:00:00Z", requires_ack: false, ack_deadline: null, published_at: "2026-11-26T00:00:00Z", row_version: 3, ...over });

beforeEach(() => {
  Object.values(api).forEach(f => f.mockReset());
  api.approvals.mockRejectedValue(new Error("403"));
  api.stats.mockResolvedValue({ delivered: 120, read: 90, acked: 0, read_rate: 0.75,
    by_faculty: [{ key: "CNTT", delivered: 100, read: 80, acked: 0 }, { key: "khác", delivered: 20, read: 10, acked: 0 }], by_cohort: [], timeline: [] });
});
afterEach(cleanup);

describe("AnnouncementManager", () => {
  it("shows the reach of a sent announcement with small groups merged", async () => {
    api.authored.mockResolvedValue({ items: [item()] });
    render(<AnnouncementManager />);
    fireEvent.click(await screen.findByRole("button", { name: "Số liệu và thao tác" }));
    expect(await screen.findByText("Đã gửi 120 · đã đọc 90 (75%) · đã xác nhận 0")).toBeTruthy();
    expect(screen.getByText("Nhóm nhỏ (gộp)")).toBeTruthy();
    expect(screen.queryByText("Chờ duyệt", { exact: false })).toBeNull();          // the author cannot approve: no queue
  });

  it("withdraws only after the reach is shown and confirmed", async () => {
    api.authored.mockResolvedValue({ items: [item()] });
    api.withdrawPreview.mockResolvedValue({ preview_id: "p", confirmation_token: "t", expires_at: "x", summary: { delivered: 120, knowledge_revoked: true } });
    api.withdrawConfirm.mockResolvedValue({ id: "a1", status: "WITHDRAWN" });
    render(<AnnouncementManager />);
    fireEvent.click(await screen.findByRole("button", { name: "Số liệu và thao tác" }));
    fireEvent.change(await screen.findByLabelText("Lý do thu hồi"), { target: { value: "Sai ngày thi" } });
    fireEvent.click(screen.getByRole("button", { name: "Xem trước khi thu hồi" }));
    const dialog = await screen.findByRole("dialog", { name: "Xác nhận thu hồi thông báo" });
    expect(dialog.textContent).toContain("120 người đã nhận");
    expect(dialog.textContent).toContain("kho tri thức cũng được gỡ");
    expect(api.withdrawConfirm).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Xác nhận thu hồi" }));
    await waitFor(() => expect(api.withdrawConfirm).toHaveBeenCalledWith("p", "t"));
  });

  it("lets an approver approve, and reject only with a note", async () => {
    api.authored.mockResolvedValue({ items: [] });
    api.approvals.mockResolvedValue({ items: [item({ id: "a2", status: "PENDING_APPROVAL", priority: "URGENT", row_version: 5 })] });
    api.approve.mockResolvedValue({});
    render(<AnnouncementManager />);
    expect(await screen.findByText("Chờ duyệt (1)")).toBeTruthy();
    expect((screen.getByRole("button", { name: "Từ chối" }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "Duyệt" }));
    await waitFor(() => expect(api.approve).toHaveBeenCalledWith("a2", "", 5));
  });

  it("revises a sent announcement only with a change note and after the confirm step", async () => {
    api.authored.mockResolvedValue({ items: [item()] });
    api.revisionPreview.mockResolvedValue({ preview_id: "p", confirmation_token: "t", expires_at: "x", summary: { material: true, revision: 2 } });
    api.revisionConfirm.mockResolvedValue({ id: "a1", revision: 2 });
    render(<AnnouncementManager />);
    fireEvent.click(await screen.findByRole("button", { name: "Số liệu và thao tác" }));
    const previewButton = await screen.findByRole("button", { name: "Xem trước bản sửa" });
    expect((previewButton as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(screen.getByLabelText("Ghi chú thay đổi (người nhận sẽ thấy)"), { target: { value: "Đổi phòng thi" } });
    fireEvent.click(screen.getByLabelText(/Thay đổi quan trọng/));
    fireEvent.click(previewButton);
    expect((await screen.findByRole("dialog", { name: "Xác nhận sửa thông báo" })).textContent).toContain("người đã nhận sẽ được báo lại");
    expect(api.revisionPreview).toHaveBeenCalledWith("a1", { change_note: "Đổi phòng thi", material: true });
    fireEvent.click(screen.getByRole("button", { name: "Xác nhận sửa" }));
    await waitFor(() => expect(api.revisionConfirm).toHaveBeenCalledWith("p", "t"));
  });
});
