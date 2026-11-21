import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { StudentGapReports } from "./StudentGapReports";

const fetchMock = vi.fn();
beforeEach(() => { fetchMock.mockReset(); vi.stubGlobal("fetch", fetchMock); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

describe("StudentGapReports", () => {
  it("lists the kept questions and says how many had their text dropped", async () => {
    fetchMock.mockResolvedValue(json(200, { total: 3, samples: [
      { id: 2, at: "2026-11-21T03:00:00Z", expires_at: "2027-02-19T03:00:00Z", question: "Học phí nộp ở đâu?" },
      { id: 1, at: "2026-11-20T03:00:00Z", expires_at: "2027-02-18T03:00:00Z", question: "Lịch thi cuối kỳ?" }] }));
    render(<StudentGapReports />);
    expect(await screen.findByText("Học phí nộp ở đâu?")).toBeTruthy();
    expect(screen.getByText(/1 báo cáo không giữ chữ/)).toBeTruthy();
    expect(String(fetchMock.mock.calls[0][0])).toContain("/v1/knowledge/gap-reports");
  });

  it("shows an empty state", async () => {
    fetchMock.mockResolvedValue(json(200, { total: 0, samples: [] }));
    render(<StudentGapReports />);
    expect(await screen.findByTestId("student-reports-empty")).toBeTruthy();
  });

  it("shows nothing for someone who may not read the reports", async () => {
    fetchMock.mockResolvedValue(json(403, { type: "x", title: "t", status: 403, detail: "no", code: "FORBIDDEN" }));
    const { container } = render(<StudentGapReports />);
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(container.textContent).toBe("");
  });

  it("says so when the reports cannot be loaded", async () => {
    fetchMock.mockResolvedValue(json(500, { type: "x", title: "t", status: 500, detail: "boom", code: "X" }));
    render(<StudentGapReports />);
    expect(await screen.findByTestId("student-reports-error")).toBeTruthy();
  });
});
