import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import ChatPage from "./page";
import { FAILED_GUIDANCE } from "../../features/chat/sse";
vi.mock("../../features/chat/ConversationHistory", () => ({ ConversationHistory: () => null }));

const conv = "019a0000-0024-7000-8000-000000000010";
const id = "019a0000-0024-7000-8000-000000000011";
function response(legacy = false) {
  const final_result = { conversation_id: conv, message_id: id, status: "abstained",
    response_class: "safe_refusal", content: "Chưa đủ nguồn synthetic.", citations: [] };
  return { items: [{ id, conversation_id: conv, sequence_no: 2, sender_type: "ASSISTANT",
    content: final_result.content, content_format: "MARKDOWN_SAFE", citations: [],
    created_at: "2026-10-06T00:00:00Z", ...(!legacy ? { final_result } : {}) }],
    page: { next_cursor: null as string | null, has_more: false } };
}
beforeEach(() => {
  vi.restoreAllMocks();
  window.localStorage.clear();
  window.history.replaceState(null, "", `/chat?conversation_id=${conv}`);
});
afterEach(() => { cleanup(); window.history.replaceState(null, "", "/chat"); window.localStorage.removeItem("campus247_token"); vi.restoreAllMocks(); });
describe("chat refresh recovery", () => {
  it("discards an expired local token and restores committed history with cookies", async () => {
    window.localStorage.setItem("campus247_token", btoa(JSON.stringify({ exp: 1 })) + ".signature");
    const fetcher = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => response() } as Response);
    render(<ChatPage />);
    await waitFor(() => expect(screen.getByText("Chưa đủ nguồn synthetic.")).toBeDefined());
    expect(fetcher.mock.calls[0][0]).toContain(`/v1/conversations/${conv}/messages?limit=100`);
    expect(new Headers(fetcher.mock.calls[0][1]?.headers).has("Authorization")).toBe(false);
    expect(window.localStorage.getItem("campus247_token")).toBeNull();
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
  it("restores a committed final via authenticated GET without recreating a conversation", async () => {
    const fetcher = vi.spyOn(globalThis, "fetch").mockResolvedValue({ ok: true, status: 200, json: async () => response() } as Response);
    render(<ChatPage />);
    await waitFor(() => expect(screen.getByText("Chưa đủ nguồn synthetic.")).toBeDefined());
    expect(screen.getByText(/Chưa đủ căn cứ/)).toBeDefined();
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(fetcher).toHaveBeenCalledWith(expect.stringContaining(`/v1/conversations/${conv}/messages?limit=100`),
      expect.objectContaining({ credentials: "include", cache: "no-store" }));
  });
  it("shows legacy content as unknown and never as a successful answer", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({ ok: true, status: 200, json: async () => response(true) } as Response);
    render(<ChatPage />);
    await waitFor(() => expect(screen.getByText(FAILED_GUIDANCE)).toBeDefined());
    expect(screen.queryByText("Chưa đủ nguồn synthetic.")).toBeNull();
    expect(screen.getByText(/UNKNOWN/)).toBeDefined();
  });
  it("blocks send after unauthorized restore without leaking old history", async () => {
    const fetcher = vi.spyOn(globalThis, "fetch").mockResolvedValue({ ok: false, status: 401 } as Response);
    render(<ChatPage />);
    await waitFor(() => expect(screen.getByText(/Phiên đăng nhập đã hết hạn/)).toBeDefined());
    fireEvent.change(screen.getByLabelText(/Đặt câu hỏi/), { target: { value: "Synthetic question" } });
    fireEvent.click(screen.getByRole("button", { name: /Gửi/i }));
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(screen.queryByText("Chưa đủ nguồn synthetic.")).toBeNull();
  });
  it("publishes no partial history when a later page fails", async () => {
    const first = response(); first.page = { next_cursor: id, has_more: true };
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => first } as Response)
      .mockResolvedValueOnce({ ok: false, status: 503 } as Response);
    render(<ChatPage />);
    await waitFor(() => expect(screen.getByText(/Không thể khôi phục lịch sử đã xác nhận/)).toBeDefined());
    expect(screen.queryByText("Chưa đủ nguồn synthetic.")).toBeNull();
  });
  it("starts a new chat without deleting server history", async () => {
    const fetcher = vi.spyOn(globalThis, "fetch").mockResolvedValue({ ok: true, status: 200, json: async () => response() } as Response);
    render(<ChatPage />);
    await waitFor(() => expect(screen.getByText("Chưa đủ nguồn synthetic.")).toBeDefined());
    fireEvent.click(screen.getAllByRole("button", { name: /Đoạn chat mới/ })[0]);
    expect(new URL(window.location.href).searchParams.has("conversation_id")).toBe(false);
    expect(screen.queryByText("Chưa đủ nguồn synthetic.")).toBeNull();
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
});
