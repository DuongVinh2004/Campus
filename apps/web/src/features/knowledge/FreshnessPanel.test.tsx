import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { ApiClientError } from "@/lib/api/client";
import { FreshnessPanel } from "./FreshnessPanel";
import { freshnessApi, type FreshnessItem, type FreshnessReport } from "@/lib/knowledge-freshness-api";

vi.mock("@/lib/knowledge-freshness-api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/knowledge-freshness-api")>("@/lib/knowledge-freshness-api");
  return { ...actual, freshnessApi: { report: vi.fn(), reviewed: vi.fn() } };
});

const item = (over: Partial<FreshnessItem>): FreshnessItem => ({
  source_id: "s1", version_id: "v1", title: "Quy chế đào tạo", owner_unit: "Phòng Đào tạo", version_label: "v1", state: "OK",
  due_at: "2026-12-20T00:00:00Z", reason: "REVIEW_INTERVAL", days_left: 33, applicability_unknown: false, last_review: null, ...over,
});

const report = (items: FreshnessItem[]): FreshnessReport => ({
  generated_at: "2026-11-17T03:00:00Z",
  summary: { EXPIRED: items.filter((i) => i.state === "EXPIRED").length, OVERDUE: items.filter((i) => i.state === "OVERDUE").length,
             DUE_SOON: items.filter((i) => i.state === "DUE_SOON").length, OK: items.filter((i) => i.state === "OK").length,
             applicability_unknown: items.filter((i) => i.applicability_unknown).length },
  items,
});

const api = vi.mocked(freshnessApi);
const ITEMS = [
  item({ source_id: "a", title: "Quy chế A", state: "OVERDUE", days_left: -4, due_at: "2026-11-13T00:00:00Z" }),
  item({ source_id: "b", title: "Học phí B", state: "DUE_SOON", days_left: 12, reason: "EFFECTIVE_UNTIL", applicability_unknown: true }),
  item({ source_id: "c", title: "Lịch C", state: "OK" }),
  item({ source_id: "d", title: "Cũ D", state: "EXPIRED", days_left: -2, reason: "EFFECTIVE_UNTIL" }),
];

// Braces matter: a function returned from beforeEach is run by vitest as cleanup, which would call the mock itself.
beforeEach(() => {
  api.report.mockReset();
  api.reviewed.mockReset();
});
afterEach(cleanup);

describe("FreshnessPanel", () => {
  it("lists sources with their state, due text and counts per filter", async () => {
    api.report.mockResolvedValue(report(ITEMS));
    render(<FreshnessPanel />);
    await screen.findByTestId("freshness-panel");
    expect(screen.getByTestId("freshness-a").textContent).toContain("quá 4 ngày");
    expect(screen.getByTestId("freshness-b").textContent).toContain("Hết hiệu lực");
    expect(screen.getByTestId("freshness-b").textContent).toContain("còn 12 ngày");
    expect(screen.getByText(/1 nguồn chưa rõ phạm vi áp dụng/)).toBeDefined();
    expect(screen.getByRole("button", { name: /Quá hạn rà soát \(1\)/ })).toBeDefined();
    expect(screen.getByRole("button", { name: /Tất cả \(4\)/ }).getAttribute("aria-pressed")).toBe("true");
  });

  it("filters by state and says when a state has no source", async () => {
    api.report.mockResolvedValue(report([ITEMS[0], ITEMS[2]]));
    render(<FreshnessPanel />);
    await screen.findByTestId("freshness-panel");
    fireEvent.click(screen.getByRole("button", { name: /Quá hạn rà soát/ }));
    expect(screen.queryByTestId("freshness-c")).toBeNull();
    expect(screen.getByTestId("freshness-a")).toBeDefined();
    fireEvent.click(screen.getByRole("button", { name: /Đã hết hiệu lực/ }));
    expect(screen.getByTestId("freshness-empty")).toBeDefined();
  });

  it("offers no review button for an expired source", async () => {
    api.report.mockResolvedValue(report(ITEMS));
    render(<FreshnessPanel />);
    await screen.findByTestId("freshness-panel");
    expect(within(screen.getByTestId("freshness-d")).queryByRole("button")).toBeNull();
    expect(within(screen.getByTestId("freshness-a")).getByRole("button", { name: /Đã rà soát/ })).toBeDefined();
  });

  it("needs a note of at least 10 characters, sends it, and reloads the report", async () => {
    api.report.mockResolvedValueOnce(report(ITEMS));
    api.report.mockResolvedValueOnce(report([item({ source_id: "a", title: "Quy chế A", state: "OK", last_review: { reviewed_at: "2026-11-17T03:00:00Z", note: "Đã đối chiếu với bản gốc" } })]));
    api.reviewed.mockResolvedValue({ source_id: "a", reviewed_at: "x" });
    render(<FreshnessPanel />);
    await screen.findByTestId("freshness-panel");
    fireEvent.click(within(screen.getByTestId("freshness-a")).getByRole("button", { name: /Đã rà soát/ }));
    const submit = screen.getByRole("button", { name: "Ghi nhận" }) as HTMLButtonElement;
    expect(submit.disabled).toBe(true);
    fireEvent.change(screen.getByLabelText(/Ghi chú rà soát/), { target: { value: "ngắn" } });
    expect(submit.disabled).toBe(true);
    fireEvent.change(screen.getByLabelText(/Ghi chú rà soát/), { target: { value: "  Đã đối chiếu với bản gốc  " } });
    expect(submit.disabled).toBe(false);
    fireEvent.click(submit);
    await waitFor(() => expect(api.reviewed).toHaveBeenCalledWith("a", "Đã đối chiếu với bản gốc"));
    await waitFor(() => expect(screen.getByTestId("freshness-a").getAttribute("data-state")).toBe("OK"));
    expect(screen.getByTestId("freshness-a").textContent).toContain("Rà soát gần nhất");
  });

  it("shows the server's message when saving fails and keeps the note", async () => {
    api.report.mockResolvedValue(report([ITEMS[0]]));
    api.reviewed.mockRejectedValue(new ApiClientError({ type: "x", title: "t", status: 404, detail: "Nguồn không thuộc bản phát hành hiện hành.", code: "NOT_FOUND" }));
    render(<FreshnessPanel />);
    await screen.findByTestId("freshness-panel");
    fireEvent.click(screen.getByRole("button", { name: /Đã rà soát/ }));
    fireEvent.change(screen.getByLabelText(/Ghi chú rà soát/), { target: { value: "Đã đối chiếu với bản gốc" } });
    fireEvent.click(screen.getByRole("button", { name: "Ghi nhận" }));
    expect((await screen.findByRole("alert")).textContent).toContain("không thuộc bản phát hành");
    expect((screen.getByLabelText(/Ghi chú rà soát/) as HTMLTextAreaElement).value).toBe("Đã đối chiếu với bản gốc");
  });

  it("explains a 403 and offers retry after another error", async () => {
    api.report.mockRejectedValueOnce(new ApiClientError({ type: "x", title: "t", status: 403, detail: "no", code: "FORBIDDEN" }));
    const first = render(<FreshnessPanel />);
    expect((await screen.findByTestId("freshness-forbidden")).textContent).toContain("quản trị tri thức");
    first.unmount();
    api.report.mockRejectedValueOnce(new Error("network"));
    api.report.mockResolvedValueOnce(report(ITEMS));
    render(<FreshnessPanel />);
    fireEvent.click(await screen.findByRole("button", { name: "Thử lại" }));
    await screen.findByTestId("freshness-panel");
  });
});
