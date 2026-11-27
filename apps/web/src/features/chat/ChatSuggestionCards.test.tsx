import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { ChatSuggestionCards } from "./ChatSuggestionCards";
import { policyApi, POLICY_PREFILL_KEY } from "../../lib/policy-api";
import { proceduresApi } from "../../lib/procedures-api";

vi.mock("../../lib/features", () => ({ FeatureGate: ({ children }: { children: React.ReactNode }) => <>{children}</> }));
vi.mock("next/link", () => ({ default: ({ href, children, onClick }: { href: string; children: React.ReactNode; onClick?: () => void }) => <a href={href} onClick={onClick}>{children}</a> }));
vi.mock("../../lib/policy-api", () => ({ POLICY_PREFILL_KEY: "policy-simulator-prefill", policyApi: { match: vi.fn() } }));
vi.mock("../../lib/procedures-api", () => ({ proceduresApi: { fromText: vi.fn(), start: vi.fn() } }));

const policy = vi.mocked(policyApi);
const procedures = vi.mocked(proceduresApi);

beforeEach(() => { policy.match.mockReset(); procedures.fromText.mockReset(); procedures.start.mockReset(); window.sessionStorage.clear(); });
afterEach(() => cleanup());

describe("chat suggestion cards", () => {
  it("shows the policy card with values found in the sentence and hands them over without a URL", async () => {
    policy.match.mockResolvedValue({ matches: [], topic: "COURSE_PASS", label: "Đạt học phần", values: { "grade.process_score": 6 }, evidence: [{ var: "grade.process_score", snippet: "6 điểm" }] });
    procedures.fromText.mockResolvedValue({ suggestions: [], procedure_id: null, extracted: [], dropped: [] });
    render(<ChatSuggestionCards text="điểm quá trình 6 điểm thi 4 điểm có đạt không" />);
    const link = await screen.findByRole("link", { name: "Mở trình kiểm tra" });
    expect(link.getAttribute("href")).toBe("/policy/simulator");
    expect(screen.getByText(/“6 điểm”/)).toBeTruthy();
    fireEvent.click(link);
    expect(JSON.parse(window.sessionStorage.getItem(POLICY_PREFILL_KEY) ?? "{}")).toEqual({ topic: "COURSE_PASS", values: { "grade.process_score": 6 } });
  });

  it("renders nothing when neither a policy topic nor a procedure matches, and for very short text", async () => {
    policy.match.mockResolvedValue({ matches: [], topic: null, values: {}, evidence: [] });
    procedures.fromText.mockResolvedValue({ suggestions: [], procedure_id: null, extracted: [], dropped: [] });
    const { container } = render(<ChatSuggestionCards text="Thư viện mở cửa lúc mấy giờ?" />);
    await waitFor(() => expect(policy.match).toHaveBeenCalled());
    expect(container.querySelector("aside")).toBeNull();
    cleanup();
    const short = render(<ChatSuggestionCards text="chào" />);
    expect(short.container.innerHTML).toBe("");
    expect(policy.match).toHaveBeenCalledTimes(1);
  });

  it("starts a procedure only on the button and keeps extracted values in session storage", async () => {
    policy.match.mockResolvedValue({ matches: [], topic: null, values: {}, evidence: [] });
    procedures.fromText.mockResolvedValue({ suggestions: [{ procedure_id: "student-certificate", title: "Giấy xác nhận sinh viên" }], procedure_id: "student-certificate", extracted: [{ field: "purpose", value: "vay vốn" }], dropped: [] });
    procedures.start.mockResolvedValue({ id: "run-1" } as never);
    const assign = vi.fn();
    Object.defineProperty(window, "location", { value: { assign }, configurable: true });
    render(<ChatSuggestionCards text="em muốn xin giấy xác nhận sinh viên để vay vốn" />);
    expect(await screen.findByText(/Giấy xác nhận sinh viên/)).toBeTruthy();
    expect(procedures.start).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Bắt đầu cùng trợ lý" }));
    await waitFor(() => expect(assign).toHaveBeenCalledWith("/services/procedures?run=run-1"));
    expect(JSON.parse(window.sessionStorage.getItem("procedure-extracted:run-1") ?? "{}")).toEqual({ purpose: "vay vốn" });
  });
});
