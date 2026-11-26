import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { VerificationPanel } from "./VerificationPanel";
import { answerQualityApi } from "../../lib/answer-quality-api";

vi.mock("../../lib/answer-quality-api", () => ({ answerQualityApi: { verification: vi.fn() } }));
const api = vi.mocked(answerQualityApi);
const report = { days: 30, statements: 8, verbatim: 3, semantic: 5, rejected: { NUMBER_NOT_IN_SOURCE: 2, SEMANTIC_UNSUPPORTED: 0 }, rejected_total: 2, rejected_share: 0.2, verbatim_share: 0.375, daily_rejected: [] };

beforeEach(() => { api.verification.mockReset(); });
afterEach(() => cleanup());

describe("VerificationPanel", () => {
  it("shows kept and dropped counts with a Vietnamese reason per code and reloads for another window", async () => {
    api.verification.mockResolvedValue(report);
    render(<VerificationPanel />);
    expect(await screen.findByText(/8 ý được giữ lại · 2 ý bị loại \(20%/)).toBeTruthy();
    expect(screen.getByText("Số liệu không có trong nguồn")).toBeTruthy();
    expect(screen.getByText(/37,5%|37.5%/)).toBeTruthy();
    fireEvent.change(screen.getByLabelText(/Khoảng thời gian/), { target: { value: "7" } });
    await waitFor(() => expect(api.verification).toHaveBeenLastCalledWith(7));
  });

  it("says so when nothing was dropped and reports a failure", async () => {
    api.verification.mockResolvedValueOnce({ ...report, rejected: {}, rejected_total: 0, rejected_share: 0 });
    render(<VerificationPanel />);
    expect(await screen.findByText(/Chưa có ý nào bị loại/)).toBeTruthy();
    cleanup();
    api.verification.mockImplementation(() => Promise.reject(new Error("Chỉ quản trị tri thức mới xem được.")));
    render(<VerificationPanel />);
    expect((await screen.findByRole("alert")).textContent).toContain("Chỉ quản trị");
  });
});

describe("rejectedSpike", () => {
  const day = (d: string, n: number) => ({ day: d, by_reason: { NUMBER_NOT_IN_SOURCE: n } });
  it("flags a day with more than twice the 7-day average, and at least five drops", async () => {
    const { rejectedSpike } = await import("./VerificationPanel");
    const week = ["2026-11-19", "2026-11-20", "2026-11-21", "2026-11-22", "2026-11-23", "2026-11-24", "2026-11-25"].map(d => day(d, 2));
    expect(rejectedSpike([...week, day("2026-11-26", 5)])).toEqual({ day: "2026-11-26", count: 5, average: 2 });
    expect(rejectedSpike([...week, day("2026-11-26", 4)])).toBeNull();            // 4 <= 2 x 2
    expect(rejectedSpike([day("2026-11-26", 4)])).toBeNull();                       // below the minimum of 5
    expect(rejectedSpike([day("2026-11-26", 6)])).toEqual({ day: "2026-11-26", count: 6, average: 0 });
    expect(rejectedSpike([])).toBeNull();
  });
});
