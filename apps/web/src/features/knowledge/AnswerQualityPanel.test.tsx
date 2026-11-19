import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { AnswerQualityPanel } from "./AnswerQualityPanel";

const fetchMock = vi.fn();
beforeEach(() => { fetchMock.mockReset(); vi.stubGlobal("fetch", fetchMock); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const problem = (status: number, detail: string) => json(status, { type: "x", title: "t", status, detail, code: "X" });

const cluster = (over = {}) => ({
  cluster_key: "a".repeat(40), reason: "no_source", version_ids: ["v1"], count: 5, count_7d: 4, previous_7d: 1, is_new_trend: true, last_at: "2026-11-19T03:00:00Z",
  sources: [{ version_id: "v1", title: "Thông báo học phí", owner_unit: "Phòng Tài chính" }], decision: null, ...over,
});
const report = (over = {}) => ({ days: 30, minimum_votes: 3, ratings: 0, sources: [], gaps: { days: 30, minimum_count: 3, clusters: [cluster()] }, ...over });

describe("AnswerQualityPanel", () => {
  it("lists refusal clusters with their sources, counts and the new-trend mark", async () => {
    fetchMock.mockResolvedValue(json(200, report()));
    render(<AnswerQualityPanel />);
    expect(await screen.findByText("Không tìm thấy nguồn phù hợp")).toBeTruthy();
    expect(screen.getByText("Thông báo học phí")).toBeTruthy();
    expect(screen.getByText("Mới tăng")).toBeTruthy();
    expect(screen.getByText(/5 lần · 4 trong 7 ngày/)).toBeTruthy();
    expect(screen.getByRole("link", { name: "Thêm nguồn" }).getAttribute("href")).toBe("/knowledge/documents");
  });

  it("shows empty states and the rated sources", async () => {
    fetchMock.mockResolvedValue(json(200, report({ gaps: { days: 30, minimum_count: 3, clusters: [] },
      sources: [{ version_id: "v1", title: "Quy chế", owner_unit: "Phòng Đào tạo", in_current_release: true, helpful: 1, not_helpful: 2, share_not_helpful: 0.667 }] })));
    render(<AnswerQualityPanel />);
    expect(await screen.findByTestId("gaps-empty")).toBeTruthy();
    expect(screen.getByText("Quy chế")).toBeTruthy();
    expect(screen.getByText(/2 chưa hữu ích \/ 3 đánh giá \(67%\)/)).toBeTruthy();
  });

  it("refuses people who may not read it", async () => {
    fetchMock.mockResolvedValue(problem(403, "no"));
    render(<AnswerQualityPanel />);
    expect(await screen.findByTestId("quality-forbidden")).toBeTruthy();
  });

  it("offers a retry when loading fails", async () => {
    fetchMock.mockResolvedValueOnce(problem(500, "Máy chủ lỗi"));
    fetchMock.mockResolvedValueOnce(json(200, report()));
    render(<AnswerQualityPanel />);
    fireEvent.click(await screen.findByRole("button", { name: "Thử lại" }));
    expect(await screen.findByText("Không tìm thấy nguồn phù hợp")).toBeTruthy();
  });

  it("records a decision, needs a release for 'resolved', and reloads", async () => {
    fetchMock.mockResolvedValueOnce(json(200, report()));
    fetchMock.mockResolvedValueOnce(json(200, { cluster_key: "a".repeat(40), action: "NEEDS_SOURCE" }));
    fetchMock.mockResolvedValueOnce(json(200, report({ gaps: { days: 30, minimum_count: 3, clusters: [cluster({ decision: { at: "2026-11-19T04:00:00Z", action: "NEEDS_SOURCE", note: "Cần thêm thông báo học phí", release_ref: "", actor: "u" } })] } })));
    render(<AnswerQualityPanel />);
    fireEvent.click(await screen.findByRole("button", { name: "Ghi nhận xử lý" }));
    const save = screen.getByRole("button", { name: "Ghi nhận" }) as HTMLButtonElement;
    expect(save.disabled).toBe(true);
    fireEvent.change(screen.getByLabelText(/Ghi chú/), { target: { value: "Cần thêm thông báo học phí" } });
    expect(save.disabled).toBe(false);
    fireEvent.change(screen.getByLabelText("Quyết định"), { target: { value: "RESOLVED" } });
    expect(save.disabled).toBe(true);
    fireEvent.change(screen.getByLabelText("Quyết định"), { target: { value: "NEEDS_SOURCE" } });
    fireEvent.click(save);
    await waitFor(() => expect(screen.getByText(/Cần thêm nguồn \(.*\): Cần thêm thông báo học phí/)).toBeTruthy());
    const post = fetchMock.mock.calls[1];
    expect(String(post[0])).toContain(`/v1/knowledge/answer-quality/gaps/${"a".repeat(40)}/decision`);
    expect(JSON.parse(post[1].body)).toEqual({ action: "NEEDS_SOURCE", note: "Cần thêm thông báo học phí", release_ref: "" });
  });
});
