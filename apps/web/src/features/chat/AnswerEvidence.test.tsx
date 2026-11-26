import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { AnswerEvidence } from "./AnswerEvidence";
import { markNumbers } from "./markNumbers";
import { answerReceiptsApi, type AnswerReceipt } from "../../lib/answer-receipts-api";

vi.mock("../../lib/answer-receipts-api", () => ({ answerReceiptsApi: { forMessage: vi.fn() } }));
const api = vi.mocked(answerReceiptsApi);

const receipt = (over: Partial<AnswerReceipt> = {}): AnswerReceipt => ({
  receipt_id: "r1", created_at: "2026-11-26T08:00:00Z", release_id: "rel", outcome_kind: "answer", rejected_counts: {},
  now: { release_id: "rel", sources_changed: 0, sources_removed: 0, impact_run_id: null },
  statements: [
    { index: 1, checks: { deterministic: "PASSED", verbatim: true, semantic: "NOT_RUN" }, sources: [{ unit_id: "u1", path: "Điều 10 > Khoản 2", doc_title: "Quy chế", page: 4, status_now: "UNCHANGED" }] },
    { index: 2, checks: { deterministic: "PASSED", verbatim: false, semantic: "PASSED" }, sources: [{ unit_id: "u2", path: null, doc_title: "Sổ tay", page: null, status_now: "CHANGED" }] },
  ], ...over,
});

beforeEach(() => { api.forMessage.mockReset(); });
afterEach(() => cleanup());

describe("AnswerEvidence", () => {
  it("counts the checked points and hides reason codes from a student", async () => {
    api.forMessage.mockResolvedValue(receipt({ rejected_counts: { NUMBER_NOT_IN_SOURCE: 1 } }));
    render(<AnswerEvidence conversationId="c1" messageId="m1" />);
    expect(await screen.findByText(/2 ý đã kiểm với nguồn · 1 ý bị loại vì không đủ nguồn/)).toBeTruthy();
    expect(document.body.textContent).not.toContain("NUMBER_NOT_IN_SOURCE");
    expect(document.body.textContent).not.toContain("số không có trong nguồn");
  });

  it("shows staff the reasons of dropped points in words", async () => {
    api.forMessage.mockResolvedValue(receipt({ rejected_counts: { NUMBER_NOT_IN_SOURCE: 1, SEMANTIC_UNSUPPORTED: 2 }, show_reason_codes: true }));
    render(<AnswerEvidence conversationId="c1" messageId="m1" />);
    expect(await screen.findByText("Ý bị loại: 1 × số không có trong nguồn · 2 × ý không được nguồn đỡ")).toBeTruthy();
  });

  it("opens the receipt with each point's check and the source status now", async () => {
    api.forMessage.mockResolvedValue(receipt());
    render(<AnswerEvidence conversationId="c1" messageId="m1" />);
    fireEvent.click(await screen.findByRole("button", { name: "Xem biên nhận" }));
    const dialog = await screen.findByRole("dialog");
    expect(dialog.textContent).toContain("Biên nhận câu trả lời");
    expect(dialog.textContent).toContain("Nguyên văn");
    expect(dialog.textContent).toContain("Quy chế — Điều 10 > Khoản 2, trang 4 (nguồn còn nguyên)");
    expect(dialog.textContent).toContain("Sổ tay (nguồn đã được sửa)");
    expect(screen.getByLabelText(/Đã đối chiếu: Số liệu/)).toBeTruthy();
  });

  it("warns when a cited source changed since the answer", async () => {
    api.forMessage.mockResolvedValue(receipt({ now: { release_id: "rel2", sources_changed: 1, sources_removed: 0, impact_run_id: null } }));
    render(<AnswerEvidence conversationId="c1" messageId="m1" />);
    expect((await screen.findByRole("status")).textContent).toContain("Nguồn đã được sửa đổi");
  });

  it("renders nothing when there is no receipt", async () => {
    api.forMessage.mockImplementation(() => Promise.reject(new Error("404")));
    const { container } = render(<AnswerEvidence conversationId="c1" messageId="m1" />);
    await waitFor(() => expect(api.forMessage).toHaveBeenCalled());
    expect(container.innerHTML).toBe("");
  });
});

describe("markNumbers", () => {
  it("marks in the source the numbers the answer uses, and nothing else", () => {
    const quote = "Điều 1. Học phí là 580.500 đồng/tín chỉ, nộp trước 15/12/2026; khóa 67 áp dụng.";
    const { nodes, marked } = markNumbers(quote, "Học phí 580500 đồng một tín chỉ, hạn 15/12/2026.");
    render(<p data-testid="q">{nodes}</p>);
    const marks = Array.from(screen.getByTestId("q").querySelectorAll("mark")).map(m => m.textContent);
    expect(marks).toEqual(["580.500", "15/12/2026"]);
    expect(marked).toBe(2);
    expect(screen.getByTestId("q").textContent).toBe(quote);                  // the quote is unchanged, only wrapped
    expect(markNumbers("Điều 1 khoản 2", "1 và 2").marked).toBe(0);            // single digits mean nothing alone
  });
});
