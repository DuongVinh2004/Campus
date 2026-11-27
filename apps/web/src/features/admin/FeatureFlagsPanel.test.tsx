import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { FeatureFlagsPanel } from "./FeatureFlagsPanel";
import { featuresApi, type FeatureItem } from "../../lib/features-api";

vi.mock("../../lib/features-api", () => ({ featuresApi: { adminList: vi.fn(), audit: vi.fn(), preview: vi.fn(), confirm: vi.fn() } }));
const api = vi.mocked(featuresApi);

const item = (over: Partial<FeatureItem>): FeatureItem => ({
  key: "rooms.booking", title: "Đặt phòng", area: "rooms", kind: "module", locked: false, startup_wired: false, variants: [], depends_on: [], dependents: [],
  configured: { value: true, source: "default" }, effective_for_all: true, off_reasons: [],
  entry_points: { api: [], pages: ["rooms"], jobs: [], tools: [] }, cost: "none", ...over,
});

describe("FeatureFlagsPanel", () => {
  beforeEach(() => { Object.values(api).forEach(m => m.mockReset()); });
  afterEach(() => cleanup());

  it("lists features, hides the change button for locked ones, and filters", async () => {
    api.adminList.mockResolvedValue({ version: 1, profile: "local", store_error: false, items: [item({}), item({ key: "core.auth", title: "Đăng nhập", locked: true }), item({ key: "learning.tutor", title: "Gia sư", effective_for_all: false, off_reasons: ["CONFIGURED_OFF"] })] });
    render(<FeatureFlagsPanel />);
    await screen.findByText("Đặt phòng");
    expect(screen.getAllByText("Đổi")).toHaveLength(2);
    expect(screen.getByText("Luôn bật")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Lọc"), { target: { value: "off" } });
    expect(screen.queryByText("Đặt phòng")).toBeNull();
    expect(screen.getByText("Gia sư")).toBeTruthy();
  });

  it("requires a reason, shows the preview impact, and confirms with an idempotency key", async () => {
    api.adminList.mockResolvedValue({ version: 1, profile: "local", store_error: false, items: [item({})] });
    api.preview.mockResolvedValue({ preview_id: "p1", confirmation_token: "t1", expires_at: "x", change: { key: "rooms.booking", from: true, to: false, remove: false },
      impact: { also_off: ["proactive.nudges"], api_prefixes: [], pages: [], jobs: [], restart_required: false, data_kept: true } });
    api.confirm.mockResolvedValue({ receipt_id: "1", key: "rooms.booking", version: 2 });
    render(<FeatureFlagsPanel />);
    fireEvent.click(await screen.findByText("Đổi"));
    const preview = screen.getByText("Xem trước") as HTMLButtonElement;
    expect(preview.disabled).toBe(true);
    fireEvent.change(screen.getByLabelText(/Lý do/), { target: { value: "Bảo trì phòng tầng 3" } });
    fireEvent.click(screen.getByText("Xem trước"));
    await screen.findByText(/Cũng bị tắt theo: proactive.nudges/);
    fireEvent.click(screen.getByText("Xác nhận"));
    await waitFor(() => expect(api.confirm).toHaveBeenCalledWith("p1", "t1", "ff-p1"));
    expect(api.preview).toHaveBeenCalledWith("rooms.booking", expect.objectContaining({ value: false, expected_version: 1 }));
    await screen.findByText(/Đã lưu thay đổi/);
  });

  it("shows an error state when the list cannot be loaded", async () => {
    api.adminList.mockRejectedValue(new Error("Chỉ quản trị viên"));
    render(<FeatureFlagsPanel />);
    expect(await screen.findByText("Chỉ quản trị viên")).toBeTruthy();
  });
});
