import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { AnswerEvidence } from "./AnswerEvidence";
import { answerReceiptsApi, type AnswerReceipt } from "../../lib/answer-receipts-api";

vi.mock("../../lib/answer-receipts-api", () => ({ answerReceiptsApi: { forMessage: vi.fn() } }));
const api = vi.mocked(answerReceiptsApi);

const receipt = (over: Partial<AnswerReceipt> = {}): AnswerReceipt => ({
  receipt_id: "r1", created_at: "", release_id: "rel", outcome_kind: "answer", rejected_counts: {},
  now: { release_id: "rel", sources_changed: 0, sources_removed: 0, impact_run_id: null },
  statements: [
    { index: 1, checks: { deterministic: "PASSED", verbatim: true, semantic: "NOT_RUN" }, sources: [{ unit_id: "u1", path: "Điều 10 > Khoản 2", doc_title: "Quy chế", page: 4, status_now: "UNCHANGED" }] },
    { index: 2, checks: { deterministic: "PASSED", verbatim: false, semantic: "PASSED" }, sources: [] },
  ], ...over,
});

beforeEach(() => { api.forMessage.mockReset(); });
afterEach(() => cleanup());

describe("AnswerEvidence", () => {
  it("counts the checked points, shows a word badge for each and hides rejected text and reason codes", async () => {
    api.forMessage.mockResolvedValue(receipt({ rejected_counts: { NUMBER_NOT_IN_SOURCE: 1 } }));
    render(<AnswerEvidence conversationId="c1" messageId="m1" />);
    expect(await screen.findByText(/2 ý đã kiểm với nguồn · 1 ý bị loại vì không đủ nguồn/)).toBeTruthy();
    expect(screen.getByText("Nguyên văn")).toBeTruthy();
    expect(screen.getByText("Đã đối chiếu")).toBeTruthy();
    expect(document.body.textContent).not.toContain("NUMBER_NOT_IN_SOURCE");
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
