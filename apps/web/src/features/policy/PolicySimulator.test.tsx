import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { PolicySimulator } from "./PolicySimulator";
import { policyApi, type PolicyResult } from "../../lib/policy-api";

vi.mock("../../lib/policy-api", () => ({ policyApi: { topics: vi.fn(), form: vi.fn(), evaluate: vi.fn() } }));
const api = vi.mocked(policyApi);

const result = (over: Partial<PolicyResult> = {}): PolicyResult => ({
  topic: "ATTENDANCE_REQUIREMENT", outcome: "NOT_SATISFIED", reason: null, as_of: "2026-11-26", conclusion: { code: "X", label: "Không bị điểm F do nghỉ học" },
  proof: { id: "g", kind: "all", value: "F", children: [{ id: "c1", kind: "pred", value: "F", text: "Tỉ lệ nghỉ: 23,3 % — yêu cầu không vượt quá 20 %", source: { unit_id: "u", path: "Điều 9 > Khoản 3", quote: "vượt quá 20%" } }] },
  missing: [], thresholds: [{ var: "attendance.absent_periods", flip_at: 6, direction: "<=", text: "Số tiết nghỉ cần không vượt quá 6 tiết" }], exceptions: [], refer_to: null,
  rule: { rule_id: "r", version: 1 }, disclaimer_code: "SIMULATION_NOT_DECISION", ...over,
});

describe("PolicySimulator", () => {
  beforeEach(() => { Object.values(api).forEach(m => m.mockReset()); });
  afterEach(() => cleanup());

  it("walks topic -> form -> verdict with proof, threshold and the fixed disclaimer", async () => {
    api.topics.mockResolvedValue({ topics: [{ topic: "ATTENDANCE_REQUIREMENT", label: "Điều kiện nghỉ học", description: "", rule_count: 1, effective_from: null }] });
    api.form.mockResolvedValue({ topic: "ATTENDANCE_REQUIREMENT", conclusion: "Không bị điểm F do nghỉ học", needs_cohort: false, fields: [
      { var: "attendance.absent_periods", label: "Số tiết nghỉ", type: "integer", unit: "period", min: 0, max: 300, step: 1, values: [], input: "USER", help: "", source: { path: "Điều 9 > Khoản 3" } }] });
    api.evaluate.mockResolvedValue(result());
    render(<PolicySimulator />);
    fireEvent.click(await screen.findByRole("button", { name: /Điều kiện nghỉ học/ }));
    const input = await screen.findByLabelText(/Số tiết nghỉ/);
    fireEvent.change(input, { target: { value: "7" } });
    fireEvent.click(screen.getByRole("button", { name: "Kiểm tra" }));
    await waitFor(() => expect(screen.getByTestId("policy-outcome").textContent).toBe("Chưa đạt điều kiện"));
    expect(api.evaluate).toHaveBeenCalledWith("ATTENDANCE_REQUIREMENT", { "attendance.absent_periods": 7 });
    expect(screen.getByRole("tree")).toBeTruthy();
    expect(screen.getByText(/Xem điều khoản: Điều 9 > Khoản 3/)).toBeTruthy();
    expect(screen.getByText("Số tiết nghỉ cần không vượt quá 6 tiết")).toBeTruthy();
    expect(screen.getByText(/không thay quyết định của nhà trường/)).toBeTruthy();
  });

  it("says what is missing instead of guessing, and shows the empty state", async () => {
    api.topics.mockResolvedValueOnce({ topics: [] });
    render(<PolicySimulator />);
    expect(await screen.findByText(/Chưa có quy định nào/)).toBeTruthy();
    cleanup();
    api.topics.mockResolvedValue({ topics: [{ topic: "T", label: "Chủ đề", description: "", rule_count: 1, effective_from: null }] });
    api.form.mockResolvedValue({ topic: "T", conclusion: "KQ", needs_cohort: false, fields: [
      { var: "a", label: "Giá trị A", type: "number", unit: null, min: 0, max: 10, step: 0.1, values: [], input: "USER", help: "", source: { path: null } }] });
    api.evaluate.mockResolvedValue(result({ outcome: "UNDETERMINED", reason: "MISSING_INPUT", missing: ["a"], proof: null, thresholds: [], refer_to: { refer_to: "ACADEMIC_SERVICES" } }));
    render(<PolicySimulator />);
    fireEvent.click(await screen.findByRole("button", { name: /Chủ đề/ }));
    await screen.findByLabelText(/Giá trị A/);
    fireEvent.click(screen.getByRole("button", { name: "Kiểm tra" }));
    await waitFor(() => expect(screen.getByTestId("policy-outcome").textContent).toBe("Chưa đủ thông tin để kết luận"));
    expect(screen.getByText(/Còn thiếu: Giá trị A/)).toBeTruthy();
    expect(screen.getByText(/hỏi phòng chức năng/)).toBeTruthy();
  });
});
