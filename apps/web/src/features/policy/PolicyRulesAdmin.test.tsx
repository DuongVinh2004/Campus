import React from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
  list: vi.fn(), draft: vi.fn(), rule: vi.fn(), createDraft: vi.fn(), updateDraft: vi.fn(), validate: vi.fn(),
  review: vi.fn(), publishPreview: vi.fn(), retirePreview: vi.fn(), confirm: vi.fn(),
}));
vi.mock("../../lib/policy-rules-api", () => ({ policyRulesApi: api }));

import { PolicyRulesAdmin } from "./PolicyRulesAdmin";

const list = {
  stale: 1,
  rules: [{ rule_id: "attendance-requirement", version: 1, topic: "ATTENDANCE_REQUIREMENT", status: "STALE", label: "Đủ điều kiện dự thi", release_id: "r", published_at: "2026-11-26T00:00:00Z", published_by: "a" }],
  drafts: [{ id: "d1", rule_id: "attendance-requirement", topic: "ATTENDANCE_REQUIREMENT", origin: "MODEL_CANDIDATE", row_version: 1, author: "c", updated_at: "2026-11-26T00:00:00Z" }],
};
const draft = { ...list.drafts[0], body: { rule_id: "attendance-requirement" }, reviews: [], issues: [], vector_count: 24, mismatches: [] };

beforeEach(() => { Object.values(api).forEach((f) => f.mockReset()); api.list.mockResolvedValue(list); api.draft.mockResolvedValue(draft); });
afterEach(cleanup);

describe("PolicyRulesAdmin", () => {
  it("lists rules with a plain status, warns about stale ones and opens a draft with its checks", async () => {
    render(<PolicyRulesAdmin />);
    expect(await screen.findByText("1 luật cần rà lại vì đoạn quy chế được trích đã thay đổi.")).toBeTruthy();
    expect(screen.getByText("Cần rà lại (nguồn đã đổi)")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Mở" }));
    expect(await screen.findByText(/24 ca kiểm tự sinh · không ca nào lệch/)).toBeTruthy();
    expect(screen.getByText("Do AI soạn từ quy chế · cập nhật", { exact: false })).toBeTruthy();
  });

  it("asks for a note of at least 8 characters before a verdict is recorded", async () => {
    api.review.mockResolvedValue({});
    render(<PolicyRulesAdmin />);
    fireEvent.click(await screen.findByRole("button", { name: "Mở" }));
    const record = await screen.findByRole("button", { name: "Ghi phán quyết" });
    expect((record as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(screen.getByLabelText("Ghi chú (ít nhất 8 ký tự)"), { target: { value: "đã đối chiếu khoản 3" } });
    fireEvent.click(screen.getByLabelText("Cần thêm nguồn"));
    fireEvent.click(record);
    await waitFor(() => expect(api.review).toHaveBeenCalledWith("d1", "needs_source", "đã đối chiếu khoản 3"));
  });

  it("publishes only after the change is shown and confirmed", async () => {
    const preview = { preview_id: "p1", confirmation_token: "t", expires_at: "2026-11-26T01:00:00Z", change: { rule_id: "attendance-requirement", version: 2, vectors: 24, supersedes_version: 1 } };
    api.publishPreview.mockResolvedValue(preview);
    api.confirm.mockResolvedValue({ rule_id: "attendance-requirement", version: 2, status: "PUBLISHED" });
    render(<PolicyRulesAdmin />);
    fireEvent.click(await screen.findByRole("button", { name: "Mở" }));
    fireEvent.click(await screen.findByRole("button", { name: "Xem trước khi công bố" }));
    const dialog = await screen.findByRole("dialog", { name: "Xác nhận thay đổi luật" });
    expect(dialog.textContent).toContain("phiên bản 2 (thay phiên bản 1)");
    expect(api.confirm).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Xác nhận" }));
    expect(await screen.findByText("Đã công bố.")).toBeTruthy();
    expect(api.confirm).toHaveBeenCalledWith(preview);
  });

  it("refuses a draft body that is not JSON without calling the API", async () => {
    render(<PolicyRulesAdmin />);
    fireEvent.click(await screen.findByRole("button", { name: "Mở" }));
    fireEvent.change(await screen.findByLabelText("Nội dung luật (JSON)"), { target: { value: "{ không hợp lệ" } });
    fireEvent.click(screen.getByRole("button", { name: "Lưu bản nháp" }));
    expect((await screen.findByRole("alert")).textContent).toBe("Nội dung không phải JSON hợp lệ.");
    expect(api.updateDraft).not.toHaveBeenCalled();
  });
});
