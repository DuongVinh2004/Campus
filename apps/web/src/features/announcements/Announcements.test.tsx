import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { AnnouncementInbox } from "./AnnouncementInbox";
import { AnnouncementCompose } from "./AnnouncementCompose";
import { announcementsApi, type AnnouncementDetail, type AnnouncementSummary } from "../../lib/announcements-api";

vi.mock("../../lib/announcements-api", () => ({
  announcementsApi: { mine: vi.fn(), publicList: vi.fn(), get: vi.fn(), ack: vi.fn(), authored: vi.fn(), createDraft: vi.fn(), audienceCount: vi.fn(), publishPreview: vi.fn(), publishConfirm: vi.fn() },
}));
const api = vi.mocked(announcementsApi);

const summary = (over: Partial<AnnouncementSummary> = {}): AnnouncementSummary => ({
  id: "a1", code: "TB-2026-000001", title: "Lịch thi cuối kỳ", category: "EXAM", priority: "NORMAL", issuer_unit: "Phòng Đào tạo", status: "PUBLISHED", revision: 1,
  expires_at: "2026-12-30T00:00:00Z", requires_ack: false, ack_deadline: null, published_at: "2026-11-26T00:00:00Z", row_version: 1, read: false, ...over,
});
const detail = (over: Partial<AnnouncementDetail> = {}): AnnouncementDetail => ({
  ...summary(), body: "Nội dung thông báo", links: [{ label: "Quy chế", url: "https://huce.edu.vn/quy-che" }], source_ref: {}, viewer: "recipient", needs_ack: false, ...over,
});

describe("announcements", () => {
  beforeEach(() => { Object.values(api).forEach(m => m.mockReset()); });
  afterEach(() => cleanup());

  it("lists notices with an urgent word label, filters, and shows the empty state", async () => {
    api.mine.mockResolvedValueOnce({ items: [summary({ priority: "URGENT", title: "Đóng cổng ký túc xá" }), summary({ id: "a2", title: "Hội thảo" })], next_offset: null });
    render(<AnnouncementInbox />);
    expect(await screen.findByText(/Đóng cổng ký túc xá/)).toBeTruthy();
    expect(screen.getByText("Khẩn")).toBeTruthy();
    api.mine.mockResolvedValueOnce({ items: [], next_offset: null });
    fireEvent.click(screen.getByRole("tab", { name: "Chưa đọc" }));
    expect(await screen.findByText("Chưa có thông báo nào.")).toBeTruthy();
    expect(api.mine).toHaveBeenLastCalledWith("unread");
  });

  it("opens a notice, shows link domains and requires the acknowledge click", async () => {
    api.mine.mockResolvedValue({ items: [summary({ requires_ack: true })], next_offset: null });
    api.get.mockResolvedValue(detail({ requires_ack: true, needs_ack: true, ack_deadline: "2026-12-01T00:00:00Z" }));
    api.ack.mockResolvedValue({ acked: true });
    render(<AnnouncementInbox />);
    fireEvent.click(await screen.findByRole("button", { name: "Lịch thi cuối kỳ" }));
    expect(await screen.findByText(/huce.edu.vn\)/)).toBeTruthy();
    fireEvent.click(screen.getByText("Tôi đã đọc và hiểu"));
    await waitFor(() => expect(api.ack).toHaveBeenCalledWith("a1"));
    expect(await screen.findByText(/đã xác nhận/)).toBeTruthy();
  });

  it("shows a 404-style error for a notice that is not the reader's", async () => {
    api.mine.mockResolvedValue({ items: [], next_offset: null });
    api.get.mockRejectedValue(new Error("Không tìm thấy thông báo."));
    render(<AnnouncementInbox initialId="zzz" />);
    expect(await screen.findByText("Không tìm thấy thông báo.")).toBeTruthy();
  });

  it("composer shows the live recipient count, previews, then sends only after confirm", async () => {
    api.authored.mockResolvedValue({ items: [] });
    api.audienceCount.mockResolvedValue({ total: 5, by_role: [], by_faculty: [], by_cohort: [], warnings: [] });
    api.createDraft.mockResolvedValue({ id: "d1", row_version: 1 });
    api.publishPreview.mockResolvedValue({ preview_id: "p1", confirmation_token: "t1", warnings: [], summary: { total: 5, needs_approval: false, knowledge_sync: false, publish_at: null } });
    api.publishConfirm.mockResolvedValue({ id: "d1", status: "PUBLISHED" });
    render(<AnnouncementCompose />);
    fireEvent.change(screen.getByLabelText("Tiêu đề"), { target: { value: "Thông báo mới của khoa" } });
    fireEvent.change(screen.getByLabelText("Nội dung"), { target: { value: "Nội dung đầy đủ" } });
    fireEvent.change(screen.getByLabelText(/Hết hạn/), { target: { value: "2026-12-30T10:00" } });
    fireEvent.change(screen.getByLabelText(/Lớp/), { target: { value: "66IT1" } });
    expect(await screen.findByText(/Sẽ gửi cho 5 người/)).toBeTruthy();
    fireEvent.click(screen.getByText("Xem trước khi gửi"));
    await screen.findByText(/Gửi cho 5 người/);
    expect(api.publishConfirm).not.toHaveBeenCalled();
    fireEvent.click(screen.getByText("Xác nhận gửi"));
    expect(await screen.findByText("Đã gửi thông báo.")).toBeTruthy();
    expect(api.publishConfirm).toHaveBeenCalledWith("p1", "t1");
  });
});
