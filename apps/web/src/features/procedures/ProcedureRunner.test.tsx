import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { ProcedureRunner, EXTRACTED_KEY } from "./ProcedureRunner";
import { proceduresApi, type ProcedureRun } from "../../lib/procedures-api";

vi.mock("../../lib/procedures-api", () => ({ proceduresApi: { catalog: vi.fn(), get: vi.fn(), start: vi.fn(), putFields: vi.fn(), preview: vi.fn(), confirm: vi.fn(), cancel: vi.fn() } }));
const api = vi.mocked(proceduresApi);

const info = { id: "student-certificate", title: "Giấy xác nhận", description: "", sources: [], fields: [{ key: "purpose", label: "Mục đích", type: "text", required: true, values: [], min: null, max: null }] };
const run = (over: Partial<ProcedureRun> = {}): ProcedureRun => ({ id: "r1", procedure_id: "student-certificate", title: "Giấy xác nhận", state: "COLLECTING", fields: {}, field_origin: {}, blocked: [], missing: ["purpose"], row_version: 1, next_step: "fill", ticket: null, expires_at: "", ...over });

beforeEach(() => { Object.values(api).forEach(m => m.mockReset()); window.sessionStorage.clear(); api.catalog.mockResolvedValue({ items: [info] }); });
afterEach(() => cleanup());

describe("ProcedureRunner", () => {
  it("marks assistant-filled values, confirms them on save and submits only after preview and the explicit button", async () => {
    window.sessionStorage.setItem(EXTRACTED_KEY("r1"), JSON.stringify({ purpose: "vay vốn" }));
    api.get.mockResolvedValue(run());
    api.putFields.mockResolvedValue(run({ state: "READY_FOR_PREVIEW", fields: { purpose: "vay vốn" }, missing: [], row_version: 2, next_step: "preview" }));
    api.preview.mockResolvedValue({ preview_id: "p1", confirmation_token: "tok", expires_at: "", ticket_preview: { title: "Xin giấy xác nhận", summary: "Mục đích: vay vốn", fields: {} } });
    api.confirm.mockResolvedValue(run({ state: "SUBMITTED", next_step: "track", ticket: { id: "t1", code: "TK-1" } }));
    render(<ProcedureRunner runId="r1" />);
    expect(await screen.findByText(/Trợ lý điền từ câu của bạn/)).toBeTruthy();
    expect((screen.getByLabelText(/Mục đích/) as HTMLInputElement).value).toBe("vay vốn");
    fireEvent.click(screen.getByRole("button", { name: "Lưu thông tin" }));
    await waitFor(() => expect(api.putFields).toHaveBeenCalledWith("r1", { purpose: "vay vốn" }, 1, ["purpose"]));
    fireEvent.click(await screen.findByRole("button", { name: "Xem trước hồ sơ" }));
    expect(api.confirm).not.toHaveBeenCalled();
    fireEvent.click(await screen.findByRole("button", { name: "Gửi hồ sơ" }));
    await waitFor(() => expect(api.confirm).toHaveBeenCalledTimes(1));
    expect(api.confirm.mock.calls[0].slice(0, 2)).toEqual(["p1", "tok"]);
    expect(api.confirm.mock.calls[0][2]).toMatch(/.+/);
    expect(await screen.findByText(/Đã gửi hồ sơ \(mã TK-1\)/)).toBeTruthy();
  });

  it("shows why a blocked run cannot continue and surfaces API failures", async () => {
    api.get.mockResolvedValue(run({ state: "BLOCKED", next_step: "fix_or_ask", blocked: [{ text: "Chưa học đủ 2 học kỳ", quote: "đã học ít nhất hai học kỳ" }] }));
    render(<ProcedureRunner runId="r1" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Chưa học đủ 2 học kỳ");
    expect(screen.getByText("đã học ít nhất hai học kỳ")).toBeTruthy();
    api.cancel.mockRejectedValue(new Error("Phiên đã gửi, không hủy được."));
    fireEvent.click(screen.getByRole("button", { name: "Hủy thủ tục" }));
    await waitFor(() => expect(screen.getAllByRole("alert").some(a => a.textContent?.includes("không hủy được"))).toBe(true));
  });
});
