import React from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import ChatPage from "./page";
import { ChatDraftActor, ChatDraftSessionProvider, chatDraftActorScope } from "../../features/chat/route-drafts";

vi.mock("../../components/AppShell", () => ({ AppShell: ({ children }: { children: React.ReactNode }) =>
  <ChatDraftActor value={chatDraftActorScope({ user_id: "student-a", roles: ["STUDENT"] })}><main>{children}</main></ChatDraftActor> }));

const A = "019a0000-0030-7000-8000-000000000001";
const B = "019a0000-0030-7000-8000-000000000002";
const N = "019a0000-0030-7000-8000-000000000003";
const M = "019a0000-0030-7000-8000-000000000004";
const ok = (body: unknown) => new Response(JSON.stringify(body), { headers: { "Content-Type": "application/json" } });
const page = (id: string, text: string) => ({ items: [{ id: id === A ? "019a0000-0030-7000-8000-000000000011" : "019a0000-0030-7000-8000-000000000012",
  conversation_id: id, sequence_no: 1, sender_type: "USER", content: text, citations: [], created_at: "2026-11-10T00:00:00Z" }],
  page: { has_more: false, next_cursor: null } });
const composer = () => screen.getByRole("textbox", { name: "Đặt câu hỏi" }) as HTMLTextAreaElement;
const edit = (text: string) => fireEvent.change(composer(), { target: { value: text } });
const mount = () => render(<ChatDraftSessionProvider><ChatPage /></ChatDraftSessionProvider>);
async function choose(name: string) {
  const link = await screen.findByRole("link", { name });
  // Avoid jsdom attempting document navigation when testing the unrepaired anchor.
  const native = (event: Event) => event.preventDefault();
  document.addEventListener("click", native);
  try { fireEvent.click(link); } finally { document.removeEventListener("click", native); }
}
function defaults(input: RequestInfo | URL, init?: RequestInit) {
  const path = String(input);
  if (path.startsWith("/v1/assistant/conversations?") && !init?.method) return Promise.resolve(ok({
    items: [{ id: A, title: "History A" }, { id: B, title: "History B" }], page: { has_more: false, next_cursor: null } }));
  if (path.includes(`/${A}/messages?`)) return Promise.resolve(ok(page(A, "Saved question A")));
  if (path.includes(`/${B}/messages?`)) return Promise.resolve(ok(page(B, "Saved question B")));
  throw new Error("Unexpected synthetic request: " + path);
}
beforeEach(() => {
  window.history.replaceState(null, "", "/chat");
  vi.spyOn(globalThis, "fetch").mockImplementation(defaults);
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); window.history.replaceState(null, "", "/chat"); });

it("switches history without a document reload and restores the new-chat draft", async () => {
  mount(); edit("Unsent new-chat question");
  await choose("History A");
  await screen.findByText("Saved question A");
  expect(new URL(window.location.href).searchParams.get("conversation_id")).toBe(A);
  expect(composer().value).toBe("");
  edit("Unsent A follow-up");
  fireEvent.click(screen.getAllByRole("button", { name: "Đoạn chat mới" })[0]);
  expect(composer().value).toBe("Unsent new-chat question");
  await choose("History A");
  await screen.findByText("Saved question A");
  expect(composer().value).toBe("Unsent A follow-up");
  expect(vi.mocked(fetch).mock.calls.every(([, init]) => !init?.method || init.method === "GET")).toBe(true);
});

it("keeps independent follow-up drafts for two saved conversations", async () => {
  mount(); await choose("History A"); await screen.findByText("Saved question A"); edit("Follow-up A");
  await choose("History B"); await screen.findByText("Saved question B");
  expect(composer().value).toBe(""); edit("Follow-up B");
  await choose("History A"); await screen.findByText("Saved question A");
  expect(composer().value).toBe("Follow-up A");
});

it("ignores an old restore result that arrives after another conversation is selected", async () => {
  let finish!: (value: Response) => void;
  vi.mocked(fetch).mockImplementation((input, init) => String(input).includes(`/${A}/messages?`)
    ? new Promise(resolve => { finish = resolve; }) : defaults(input, init));
  mount(); await choose("History A");
  await waitFor(() => expect(finish).toBeTypeOf("function"));
  await choose("History B"); await screen.findByText("Saved question B");
  await act(async () => finish(ok(page(A, "Late private A"))));
  expect(screen.queryByText("Late private A")).toBeNull();
  expect(screen.getByText("Saved question B")).toBeDefined();
});

it("blocks send during history restoration without clearing a typed follow-up", async () => {
  let finish!: (value: Response) => void;
  vi.mocked(fetch).mockImplementation((input, init) => String(input).includes(`/${A}/messages?`)
    ? new Promise(resolve => { finish = resolve; }) : defaults(input, init));
  mount(); await choose("History A");
  await waitFor(() => expect(finish).toBeTypeOf("function"));
  edit("Keep while loading");
  fireEvent.click(screen.getByRole("button", { name: "Gửi" }));
  expect(composer().value).toBe("Keep while loading");
  expect(vi.mocked(fetch).mock.calls.every(([, init]) => !init?.method || init.method === "GET")).toBe(true);
  await act(async () => finish(ok(page(A, "Saved question A"))));
  expect(composer().value).toBe("Keep while loading");
});

it("retries a failed history read in place while retaining its follow-up", async () => {
  let reads = 0;
  vi.mocked(fetch).mockImplementation((input, init) => String(input).includes(`/${A}/messages?`) && ++reads === 1
    ? Promise.resolve(new Response("", { status: 503 })) : defaults(input, init));
  mount(); await choose("History A");
  await screen.findByText(/Không thể khôi phục lịch sử đã xác nhận/);
  edit("Unsent after read failure");
  fireEvent.click(screen.getByRole("button", { name: "Thử lại" }));
  await screen.findByText("Saved question A");
  expect(composer().value).toBe("Unsent after read failure");
});

it("restores the selected history and draft on browser popstate", async () => {
  mount(); await choose("History A"); await screen.findByText("Saved question A"); edit("A before Back");
  await choose("History B"); await screen.findByText("Saved question B"); edit("B before Back");
  window.history.replaceState(window.history.state, "", `/chat?conversation_id=${A}`);
  fireEvent(window, new PopStateEvent("popstate"));
  await screen.findByText("Saved question A");
  expect(composer().value).toBe("A before Back");
});

it("keeps an unacknowledged send when navigation cancels conversation creation", async () => {
  let finish!: (value: Response) => void;
  vi.mocked(fetch).mockImplementation((input, init) => String(input) === "/v1/conversations" && init?.method === "POST"
    ? new Promise(resolve => { finish = resolve; }) : defaults(input, init));
  mount(); edit("Not yet persisted question");
  fireEvent.click(screen.getByRole("button", { name: "Gửi" }));
  await waitFor(() => expect(finish).toBeTypeOf("function"));
  await choose("History B"); await screen.findByText("Saved question B");
  await act(async () => finish(ok({ id: N })));
  fireEvent.click(screen.getAllByRole("button", { name: "Đoạn chat mới" })[0]);
  expect(composer().value).toBe("Not yet persisted question");
  expect(vi.mocked(fetch).mock.calls.some(([input]) => String(input).endsWith("messages:stream"))).toBe(false);
});

it("does not abort its own new conversation and clears a query seed only after the started receipt", async () => {
  window.history.replaceState(null, "", "/chat?q=Seed%20question");
  let stream!: ReadableStreamDefaultController<Uint8Array>;
  let signal: AbortSignal | null | undefined;
  vi.mocked(fetch).mockImplementation((input, init) => {
    if (String(input) === "/v1/conversations" && init?.method === "POST") return Promise.resolve(ok({ id: N }));
    if (String(input).endsWith("messages:stream")) {
      signal = init?.signal;
      return Promise.resolve(new Response(new ReadableStream({ start(controller) { stream = controller; } })));
    }
    return defaults(input, init);
  });
  mount(); await waitFor(() => expect(composer().value).toBe("Seed question"));
  fireEvent.click(screen.getByRole("button", { name: "Gửi" }));
  await waitFor(() => expect(signal).toBeDefined());
  expect(signal?.aborted).toBe(false);
  expect(composer().value).toBe("Seed question");
  await act(async () => stream.enqueue(new TextEncoder().encode(`id: ${M}\nevent: message.started\ndata: ${JSON.stringify({ conversation_id: N, message_id: M })}\n\n`)));
  expect(composer().value).toBe("");
  expect(signal?.aborted).toBe(false);
});

it("rejects an invalid created conversation before opening a stream and retains its question", async () => {
  vi.mocked(fetch).mockImplementation((input, init) => String(input) === "/v1/conversations" && init?.method === "POST"
    ? Promise.resolve(ok({ id: "not-a-uuid" })) : defaults(input, init));
  mount(); edit("Question with no valid receipt");
  fireEvent.click(screen.getByRole("button", { name: "Gửi" }));
  await screen.findByText(/Câu hỏi chưa được xác nhận đã lưu/);
  expect(composer().value).toBe("Question with no valid receipt");
  expect(vi.mocked(fetch).mock.calls.some(([input]) => String(input).endsWith("messages:stream"))).toBe(false);
});

it("conceals a cancelled stream's late events after selecting another history", async () => {
  let stream!: ReadableStreamDefaultController<Uint8Array>;
  let signal: AbortSignal | null | undefined;
  vi.mocked(fetch).mockImplementation((input, init) => {
    if (String(input) === "/v1/conversations" && init?.method === "POST") return Promise.resolve(ok({ id: N }));
    if (String(input).endsWith("messages:stream")) {
      signal = init?.signal;
      return Promise.resolve(new Response(new ReadableStream({ start(controller) { stream = controller; } })));
    }
    return defaults(input, init);
  });
  mount(); edit("Pending in the previous conversation");
  fireEvent.click(screen.getByRole("button", { name: "Gửi" }));
  await waitFor(() => expect(signal).toBeDefined());
  await choose("History B"); await screen.findByText("Saved question B");
  expect(signal?.aborted).toBe(true);
  await act(async () => {
    stream.enqueue(new TextEncoder().encode(`id: ${M}\nevent: message.started\ndata: ${JSON.stringify({ conversation_id: N, message_id: M })}\n\n`));
    stream.close();
  });
  expect(screen.getByText("Saved question B")).toBeDefined();
  expect(screen.queryByText("Pending in the previous conversation")).toBeNull();
  expect(composer().value).toBe("");
});
