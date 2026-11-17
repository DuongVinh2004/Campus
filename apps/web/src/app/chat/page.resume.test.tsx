import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
vi.mock("../../features/chat/ConversationHistory", () => ({ ConversationHistory: () => null }));

const CONV = "019a0000-0024-7000-8000-000000000010";
const RUN = "019a0000-0024-7000-8000-000000000011";
const ASSISTANT = "019a0000-0024-7000-8000-000000000012";
const RESUMED = "019a0000-0024-7000-8000-000000000013";
beforeEach(() => { vi.restoreAllMocks(); window.localStorage.clear(); window.history.replaceState(null, "", "/chat"); });
afterEach(() => { cleanup(); vi.unstubAllEnvs(); vi.restoreAllMocks(); vi.resetModules(); window.localStorage.clear(); window.history.replaceState(null, "", "/chat"); });

describe("durable multi-agent clarification", () => {
  it("reloads the stable run binding and sends facts to resume with current CAS version", async () => {
    vi.stubEnv("NEXT_PUBLIC_MULTI_AGENT", "true");
    vi.resetModules();
    const { default: ChatPage } = await import("./page");
    window.history.replaceState(null, "", `/chat?conversation_id=${CONV}`);
    const clarification = { conversation_id: CONV, message_id: ASSISTANT, run_id: RUN, status: "abstained",
      response_class: "clarification_request", content: "Bạn hỏi loại học bổng nào?", citations: [] };
    const result = { conversation_id: CONV, message_id: RESUMED, run_id: RUN, status: "abstained",
      response_class: "safe_refusal", content: "Chưa có đủ nguồn cho phần bạn bổ sung.", citations: [] };
    const fetcher = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => ({ items: [{ id: ASSISTANT, conversation_id: CONV,
        sequence_no: 2, sender_type: "ASSISTANT", content: clarification.content, citations: [], created_at: "2026-10-13T00:00:00Z", final_result: clarification }],
        page: { next_cursor: null, has_more: false } }) } as Response)
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => ({ id: RUN, status: "waiting_user", version: 24 }) } as Response)
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => ({ run: { id: RUN, status: "partial" }, message: result }) } as Response);
    render(<ChatPage />);
    await waitFor(() => expect(screen.getByText("Thông tin bạn gửi tiếp sẽ dùng để làm rõ yêu cầu đang chờ.")).toBeTruthy());
    fireEvent.change(screen.getByLabelText("Đặt câu hỏi"), { target: { value: "Học bổng khuyến khích học tập" } });
    fireEvent.click(screen.getByRole("button", { name: "Gửi" }));
    await waitFor(() => expect(screen.getByText(result.content)).toBeTruthy());
    expect(fetcher.mock.calls[2][0]).toContain(`/agent-runs/${RUN}:resume`);
    expect(JSON.parse(String(fetcher.mock.calls[2][1]?.body))).toEqual({ expected_version: 24, content: "Học bổng khuyến khích học tập" });
    expect(fetcher.mock.calls.some(([url]) => String(url).endsWith("messages:stream"))).toBe(false);
  });
});
