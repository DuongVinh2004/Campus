import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, cleanup } from "@testing-library/react";
import ChatPage from "./page";
import * as fs from "fs";
import * as path from "path";
import { FAILED_GUIDANCE } from "../../features/chat/sse";
vi.mock("../../features/chat/ConversationHistory", () => ({ ConversationHistory: () => null }));

beforeEach(() => {
  window.history.replaceState(null, "", "/chat");
  window.localStorage.removeItem("campus247_token");
});
afterEach(() => {
  window.history.replaceState(null, "", "/chat");
  window.localStorage.removeItem("campus247_token");
});

describe("ChatPage Authentication & Session Boundary (TASK-WEB-AUTH-002)", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("AC-TASK-WEB-AUTH-002-01: does not embed demo token or bearer credential in source code", () => {
    const pageSourcePath = path.resolve(__dirname, "page.tsx");
    const sourceContent = fs.readFileSync(pageSourcePath, "utf-8");

    // Must NOT contain hardcoded DEFAULT_DEMO_TOKEN or base64 JWT payload
    expect(sourceContent).not.toContain("DEFAULT_DEMO_TOKEN");
    expect(sourceContent).not.toContain("eyJleHAi");
    expect(sourceContent).not.toContain("Bearer ");
  });

  it("AC-TASK-WEB-AUTH-002-02: fails closed with unauthorized state when session is missing or returns 401", async () => {
    window.localStorage.removeItem("campus247_token");
    // Mock fetch returning 401 Unauthorized for conversation initialization
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({
      ok: false,
      status: 401,
      statusText: "Unauthorized",
      json: async () => ({
        code: "AUTHENTICATION_REQUIRED",
        title: "Authentication Required",
        detail: "A valid Bearer token or signed session is required.",
      }),
    } as unknown as Response);

    render(<ChatPage />);

    // Attempt to send a message
    const input = screen.getByLabelText(/Đặt câu hỏi/i);
    const sendButton = screen.getByRole("button", { name: /Gửi/i });

    fireEvent.change(input, { target: { value: "Học bổng kỳ này điều kiện gì?" } });
    fireEvent.click(sendButton);

    await waitFor(() => {
      // AsyncState unauthorized heading or text should appear
      expect(screen.getByText(/Phiên đăng nhập đã hết hạn/i)).toBeDefined();
    });

    // Verify fetch used credentials: "include" and did not send hardcoded token
    expect(globalThis.fetch).toHaveBeenCalledWith(
      expect.stringContaining("/v1/conversations"),
      expect.objectContaining({
        credentials: "include",
      })
    );
    expect(globalThis.fetch).toHaveBeenCalledTimes(1);
  });

  it("AC-TASK-WEB-AUTH-002-03: handles session expiration on stream failure gracefully", async () => {
    // First conversation init succeeds
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ id: "conv-123" }),
      } as unknown as Response)
      // Stream call fails with 401
      .mockResolvedValueOnce({
        ok: false,
        status: 401,
        statusText: "Unauthorized",
      } as unknown as Response);

    render(<ChatPage />);

    const input = screen.getByLabelText(/Đặt câu hỏi/i);
    const sendButton = screen.getByRole("button", { name: /Gửi/i });

    fireEvent.change(input, { target: { value: "Xin chào" } });
    fireEvent.click(sendButton);

    await waitFor(() => {
      expect(screen.getByText(/Phiên đăng nhập đã hết hạn/i)).toBeDefined();
    });
  });
});

const STREAM_CONVERSATION = "01923456-789a-7def-8123-456789abcdef";
const STREAM_MESSAGE = "01923456-789a-7def-8123-456789abcdea";
let streamEventCounter = 0;
function streamEvent(event: string, data: unknown): string {
  return `id: 01923456-789a-7def-8123-${(++streamEventCounter).toString(16).padStart(12, "0")}\nevent: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
}
function startedEvent() {
  return streamEvent("message.started", { conversation_id: STREAM_CONVERSATION, message_id: STREAM_MESSAGE });
}
function completionEvent(status = "answered") {
  return streamEvent("message.completed", { conversation_id: STREAM_CONVERSATION, message_id: STREAM_MESSAGE,
    status, response_class: status === "abstained" ? "safe_refusal" : "tool_result",
    content: status === "abstained" ? "Chưa đủ căn cứ; vui lòng làm rõ câu hỏi." : "Kết quả đã xác nhận", citations: [] });
}
function mockStream(wire: string) {
  const bytes = new TextEncoder().encode(wire);
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      // Byte-sized fragments include split Vietnamese UTF-8 and SSE boundaries.
      bytes.forEach((byte) => controller.enqueue(new Uint8Array([byte])));
      controller.close();
    },
  });
  vi.spyOn(globalThis, "fetch")
    .mockResolvedValueOnce({ ok: true, status: 201, json: async () => ({ id: STREAM_CONVERSATION }) } as Response)
    .mockResolvedValueOnce({ ok: true, status: 200, headers: new Headers(), body } as Response);
}
function sendQuestion() {
  fireEvent.change(screen.getByLabelText(/Đặt câu hỏi/i), { target: { value: "Synthetic question" } });
  fireEvent.click(screen.getByRole("button", { name: /Gửi/i }));
}

it.each(["missing", "expired"])("uses cookies with a %s legacy token and publishes the committed final", async (sessionState) => {
  if (sessionState === "expired") window.localStorage.setItem("campus247_token", btoa(JSON.stringify({ exp: 1 })) + ".signature");
  else window.localStorage.removeItem("campus247_token");
  const wire = startedEvent() + completionEvent();
  const body = new ReadableStream<Uint8Array>({ start(controller) {
    controller.enqueue(new TextEncoder().encode(wire)); controller.close();
  } });
  const fetcher = vi.spyOn(globalThis, "fetch")
    .mockResolvedValueOnce({ ok: true, status: 201, json: async () => ({ id: STREAM_CONVERSATION }) } as Response)
    .mockResolvedValueOnce({ ok: true, status: 200, headers: new Headers(), body } as Response);
  render(<ChatPage />); sendQuestion();
  await waitFor(() => expect(screen.getByText("Kết quả đã xác nhận")).toBeDefined());
  expect(fetcher.mock.calls.map(([url]) => String(url))).toEqual([
    expect.stringContaining("/v1/conversations"),
    expect.stringContaining("/messages:stream"),
  ]);
  expect(new Headers(fetcher.mock.calls[0][1]?.headers).has("Authorization")).toBe(false);
  expect(window.localStorage.getItem("campus247_token")).toBeNull();
  cleanup(); vi.restoreAllMocks();
});

describe("ChatPage approved streaming lifecycle", () => {
  beforeEach(() => { vi.restoreAllMocks(); });
  afterEach(() => { cleanup(); });

  it("replaces provisional output and ends loading after a fragmented completed event", async () => {
    mockStream(startedEvent() + streamEvent("message.delta", { seq: 1, delta: "PROVISIONAL_SYNTHETIC" }) + completionEvent());
    render(<ChatPage />); sendQuestion();
    await waitFor(() => { expect(screen.getByText("Kết quả đã xác nhận")).toBeDefined(); });
    const submitted = vi.mocked(globalThis.fetch).mock.calls.find(([url]) => String(url).endsWith("/messages:stream"));
    const request = JSON.parse(String(submitted?.[1]?.body));
    expect(request.client_id).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
    expect(screen.queryByText("PROVISIONAL_SYNTHETIC")).toBeNull();
    await waitFor(() => { expect(screen.queryByText(/Trợ lý đang trả lời/i)).toBeNull(); });
  });

  it("withdraws rejected provisional text on abstention", async () => {
    mockStream(startedEvent() + streamEvent("message.delta", { seq: 1, delta: "REJECTED_SYNTHETIC" }) + completionEvent("abstained"));
    render(<ChatPage />); sendQuestion();
    await waitFor(() => { expect(screen.getByText(/Chưa đủ căn cứ; vui lòng/i)).toBeDefined(); });
    expect(screen.queryByText("REJECTED_SYNTHETIC")).toBeNull();
    expect(screen.queryByRole("button", { name: /Nguồn trích dẫn/i })).toBeNull();
  });

  it("replaces provisional output on terminal failure and does not retry", async () => {
    mockStream(startedEvent() + streamEvent("message.delta", { seq: 1, delta: "PROVISIONAL_SYNTHETIC" }) + streamEvent("message.failed", {
      type: "https://campus247.example/problems/internal-error", title: "Safe error", detail: "Safe guidance", status: 500,
      instance: `urn:request:${STREAM_MESSAGE}`, request_id: STREAM_MESSAGE, code: "INTERNAL_ERROR", retryable: false,
    }));
    render(<ChatPage />); sendQuestion();
    await waitFor(() => { expect(screen.getAllByText(FAILED_GUIDANCE).length).toBeGreaterThan(0); });
    expect(screen.queryByText("PROVISIONAL_SYNTHETIC")).toBeNull();
    expect(globalThis.fetch).toHaveBeenCalledTimes(2);
  });

  it.each(["incomplete", "malformed", "unknown-status"])("reports %s stream without empty success", async (scenario) => {
    const tail = scenario === "incomplete" ? "" : scenario === "malformed"
      ? "id: 01923456-789a-7def-8123-456789abcdeb\nevent: message.delta\ndata: {broken\n\n"
      : completionEvent("future-status");
    mockStream(startedEvent() + streamEvent("message.delta", { seq: 1, delta: "PROVISIONAL_SYNTHETIC" }) + tail);
    render(<ChatPage />); sendQuestion();
    await waitFor(() => { expect(screen.queryByText("PROVISIONAL_SYNTHETIC")).toBeNull();
      expect(screen.getAllByText(/Nội dung tạm đã được thu hồi|Không thể xác nhận câu trả lời/i).length).toBeGreaterThan(0); });
    await waitFor(() => { expect(screen.queryByText(/Trợ lý đang trả lời/i)).toBeNull(); });
  });

  it("keeps earlier turns when a later attempt fails", async () => {
    mockStream(startedEvent() + completionEvent());
    render(<ChatPage />); sendQuestion();
    await waitFor(() => { expect(screen.getByText("Kết quả đã xác nhận")).toBeDefined(); });
    await waitFor(() => { expect(screen.queryByText(/Trợ lý đang trả lời/i)).toBeNull(); });
    vi.mocked(globalThis.fetch).mockRejectedValueOnce(new Error("SYNTHETIC_PRIVATE_TRANSPORT_ERROR"));
    sendQuestion();
    await waitFor(() => { expect(screen.getAllByText(FAILED_GUIDANCE).length).toBeGreaterThan(0); });
    expect(screen.getByText("Kết quả đã xác nhận")).toBeDefined();
    expect(screen.queryByText("SYNTHETIC_PRIVATE_TRANSPORT_ERROR")).toBeNull();
  });

  it("withdraws provisional text and ends loading when the user cancels a pending read", async () => {
    let pending: ReadableStreamDefaultController<Uint8Array>;
    const body = new ReadableStream<Uint8Array>({ start(controller) { pending = controller; } });
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce({ ok: true, status: 201, json: async () => ({ id: STREAM_CONVERSATION }) } as Response)
      .mockImplementationOnce(async (_input, options) => {
        options?.signal?.addEventListener("abort", () => pending.error(new DOMException("Aborted", "AbortError")));
        pending.enqueue(new TextEncoder().encode(startedEvent() + streamEvent("message.delta", {
          seq: 1, delta: "CANCELLED_PROVISIONAL_SYNTHETIC",
        })));
        return { ok: true, status: 200, headers: new Headers(), body } as Response;
      });
    render(<ChatPage />); sendQuestion();
    await waitFor(() => { expect(screen.getByText("CANCELLED_PROVISIONAL_SYNTHETIC")).toBeDefined(); });
    fireEvent.click(screen.getByRole("button", { name: /Dừng trả lời/i }));
    await waitFor(() => { expect(screen.getByText(/Đã dừng — câu trả lời chưa được xác nhận/i)).toBeDefined(); });
    expect(screen.queryByText("CANCELLED_PROVISIONAL_SYNTHETIC")).toBeNull();
    await waitFor(() => { expect(screen.queryByText(/Trợ lý đang trả lời/i)).toBeNull(); });
    expect(globalThis.fetch).toHaveBeenCalledTimes(2);
    expect(screen.queryByRole("button", { name: /Nguồn trích dẫn/i })).toBeNull();
  });

  it("withdraws provisional text after a transport fault without exposing the exception", async () => {
    let pending: ReadableStreamDefaultController<Uint8Array>;
    const body = new ReadableStream<Uint8Array>({ start(controller) { pending = controller; } });
    pending!.enqueue(new TextEncoder().encode(startedEvent() + streamEvent("message.delta", {
      seq: 1, delta: "FAULT_PROVISIONAL_SYNTHETIC",
    })));
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce({ ok: true, status: 201, json: async () => ({ id: STREAM_CONVERSATION }) } as Response)
      .mockResolvedValueOnce({ ok: true, status: 200, headers: new Headers(), body } as Response);
    render(<ChatPage />); sendQuestion();
    await waitFor(() => { expect(screen.getByText("FAULT_PROVISIONAL_SYNTHETIC")).toBeDefined(); });
    pending!.error(new Error("SYNTHETIC_PRIVATE_LATE_TRANSPORT_FAULT"));
    await waitFor(() => { expect(screen.getAllByText(FAILED_GUIDANCE).length).toBeGreaterThan(0); });
    expect(screen.queryByText("FAULT_PROVISIONAL_SYNTHETIC")).toBeNull();
    expect(screen.queryByText("SYNTHETIC_PRIVATE_LATE_TRANSPORT_FAULT")).toBeNull();
    await waitFor(() => { expect(screen.queryByText(/Trợ lý đang trả lời/i)).toBeNull(); });
    expect(globalThis.fetch).toHaveBeenCalledTimes(2);
  });

  it("ends loading immediately while stream cancellation cleanup remains pending", async () => {
    const cancel = vi.fn(() => new Promise<void>(() => {}));
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(new TextEncoder().encode(startedEvent() + streamEvent("message.delta", {
          seq: 1, delta: "PENDING_CLEANUP_PROVISIONAL_SYNTHETIC",
        })));
      },
      cancel,
    });
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce({ ok: true, status: 201, json: async () => ({ id: STREAM_CONVERSATION }) } as Response)
      .mockResolvedValueOnce({ ok: true, status: 200, headers: new Headers(), body } as Response);
    render(<ChatPage />); sendQuestion();
    await waitFor(() => { expect(screen.getByText("PENDING_CLEANUP_PROVISIONAL_SYNTHETIC")).toBeDefined(); });
    fireEvent.click(screen.getByRole("button", { name: /Dừng trả lời/i }));
    expect(screen.queryByText("PENDING_CLEANUP_PROVISIONAL_SYNTHETIC")).toBeNull();
    expect(screen.getByText(/Đã dừng — câu trả lời chưa được xác nhận/i)).toBeDefined();
    expect(screen.queryByText(/Trợ lý đang trả lời/i)).toBeNull();
    expect(cancel).toHaveBeenCalledTimes(1);

    const nextBody = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(new TextEncoder().encode(startedEvent() + completionEvent()));
        controller.close();
      },
    });
    vi.mocked(globalThis.fetch).mockResolvedValueOnce({ ok: true, status: 200, headers: new Headers(), body: nextBody } as Response);
    sendQuestion();
    await waitFor(() => { expect(screen.getByText("Kết quả đã xác nhận")).toBeDefined(); });
    expect(screen.getByText(/Đã dừng — câu trả lời chưa được xác nhận/i)).toBeDefined();
    expect(globalThis.fetch).toHaveBeenCalledTimes(3);
  });

  it("ignores a late conversation response after cancellation while a new attempt is active", async () => {
    let resolveOld: (value: Response) => void;
    let resolveNew: (value: Response) => void;
    vi.spyOn(globalThis, "fetch")
      .mockImplementationOnce(() => new Promise<Response>((resolve) => { resolveOld = resolve; }))
      .mockImplementationOnce(() => new Promise<Response>((resolve) => { resolveNew = resolve; }));
    render(<ChatPage />); sendQuestion();
    fireEvent.click(screen.getByRole("button", { name: /Dừng trả lời/i }));
    expect(screen.getByText(/Đã dừng — câu trả lời chưa được xác nhận/i)).toBeDefined();
    expect(screen.queryByText(/Trợ lý đang trả lời/i)).toBeNull();
    sendQuestion();
    const lateJson = vi.fn(async () => ({ id: "01923456-789a-7def-8123-456789abcdeb" }));
    resolveOld!({ ok: true, status: 201, json: lateJson } as unknown as Response);
    await waitFor(() => { expect(screen.getByText(/Trợ lý đang trả lời/i)).toBeDefined(); });
    expect(lateJson).not.toHaveBeenCalled();
    expect(globalThis.fetch).toHaveBeenCalledTimes(2);

    const nextBody = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(new TextEncoder().encode(startedEvent() + completionEvent()));
        controller.close();
      },
    });
    vi.mocked(globalThis.fetch).mockResolvedValueOnce({ ok: true, status: 200, headers: new Headers(), body: nextBody } as Response);
    resolveNew!({ ok: true, status: 201, json: async () => ({ id: STREAM_CONVERSATION }) } as Response);
    await waitFor(() => { expect(screen.getByText("Kết quả đã xác nhận")).toBeDefined(); });
    expect(globalThis.fetch).toHaveBeenLastCalledWith(
      expect.stringContaining(`/v1/conversations/${STREAM_CONVERSATION}/messages:stream`), expect.anything(),
    );
    await waitFor(() => { expect(screen.queryByText(/Trợ lý đang trả lời/i)).toBeNull(); });
    expect(globalThis.fetch).toHaveBeenCalledTimes(3);
  });

  it("fails safely on a foreign final message binding", async () => {
    mockStream(startedEvent() + streamEvent("message.delta", { seq: 1, delta: "FOREIGN_PROVISIONAL_SYNTHETIC" }) +
      streamEvent("message.completed", {
        conversation_id: STREAM_CONVERSATION, message_id: STREAM_CONVERSATION, status: "answered",
        response_class: "tool_result", content: "FOREIGN_FINAL_SYNTHETIC", citations: [],
      }));
    render(<ChatPage />); sendQuestion();
    await waitFor(() => { expect(screen.getAllByText(FAILED_GUIDANCE).length).toBeGreaterThan(0); });
    expect(screen.queryByText("FOREIGN_PROVISIONAL_SYNTHETIC")).toBeNull();
    expect(screen.queryByText("FOREIGN_FINAL_SYNTHETIC")).toBeNull();
    expect(globalThis.fetch).toHaveBeenCalledTimes(2);
  });
});
