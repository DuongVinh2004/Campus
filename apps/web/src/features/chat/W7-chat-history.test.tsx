import React from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import ChatPage from "../../app/chat/page";
import { OperationalPrivacy } from "../privacy/OperationalPrivacy";

vi.mock("../../components/AppShell", () => ({ AppShell: ({ children }: { children: React.ReactNode }) => <main>{children}</main> }));
const conv = "019a0000-0024-7000-8000-000000000010";
const other = "019a0000-0024-7000-8000-000000000011";
const message = "019a0000-0024-7000-8000-000000000012";
const entry = (id = conv, title = "Học trực tuyến theo Quy chế 1486") => ({ id, title,
  created_at: "2026-11-01T08:00:00Z", updated_at: "2026-11-01T08:01:00Z",
  mode: "persistent", can_continue: true, retention_state: "available" });
const page = (items = [entry(), entry(other, "Thủ tục bảng điểm")]) => ({ items,
  page: { next_cursor: null, has_more: false, limit: 20 } });
const ok = (value: unknown) => ({ ok: true, status: 200, json: async () => value }) as Response;
const emptyHistory = { items: [], page: { next_cursor: null, has_more: false, limit: 100 } };

beforeEach(() => {
  vi.stubEnv("NEXT_PUBLIC_KNOWLEDGE_PLATFORM", "true");
  window.history.replaceState(null, "", "/chat");
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllEnvs(); window.history.replaceState(null, "", "/chat"); });

it("shows server conversation history, native keyboard links and only the current selection", async () => {
  window.history.replaceState(null, "", `/chat?conversation_id=${conv}`);
  vi.spyOn(globalThis, "fetch").mockImplementation(async url => String(url).includes("/assistant/conversations?") ? ok(page()) : ok(emptyHistory));
  render(<ChatPage />);
  const history = await screen.findByRole("navigation", { name: "Lịch sử hội thoại" });
  const active = await within(history).findByRole("link", { name: entry().title });
  expect(active.getAttribute("aria-current")).toBe("page");
  const target = within(history).getByRole("link", { name: "Thủ tục bảng điểm" });
  expect(target.getAttribute("href")).toBe(`/chat?conversation_id=${other}`);
  expect(target.getAttribute("aria-current")).toBeNull();
  target.focus(); expect(document.activeElement).toBe(target);
  const navigate = vi.fn((event: Event) => event.preventDefault());
  target.addEventListener("click", navigate);
  fireEvent.click(target); expect(navigate).toHaveBeenCalledOnce();
  expect(window.getComputedStyle(screen.getByRole("button", { name: /Tôi cần tra học phí/ })).fontWeight).toBe("400");
  fireEvent.click(screen.getAllByRole("button", { name: "Đoạn chat mới" })[0]);
  expect(active.getAttribute("aria-current")).toBeNull();
  expect(new URL(window.location.href).searchParams.has("conversation_id")).toBe(false);
});

it("opens the real chat history destination from the privacy page link", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(ok(page()));
  const privacy = render(<OperationalPrivacy />);
  const target = screen.getByRole("link", { name: "Lịch sử hội thoại" }).getAttribute("href");
  expect(target).toBe("/chat");
  privacy.unmount();
  window.history.replaceState(null, "", target!);
  render(<ChatPage />);
  expect(await screen.findByRole("link", { name: entry().title })).toBeDefined();
});

it.each([401, 404, 503, "network"])("keeps chat usable when the list fails with %s", async status => {
  vi.spyOn(globalThis, "fetch").mockImplementation(async () => {
    if (status === "network") throw new Error("private transport detail");
    return { ok: false, status } as Response;
  });
  render(<ChatPage />);
  await screen.findByText(status === 401 ? /Phiên đăng nhập đã hết hạn/ : /Chưa tải được lịch sử/);
  expect(screen.getByRole("textbox", { name: "Đặt câu hỏi" }).hasAttribute("disabled")).toBe(false);
  expect(screen.queryByRole("link", { name: entry().title })).toBeNull();
  expect(screen.queryByText("private transport detail")).toBeNull();
  if (status === 401) expect(screen.getByRole("link", { name: "Đăng nhập lại" }).getAttribute("href")).toBe("/login?redirect=%2Fchat");
});

it("uses cookies without reading or writing a legacy token and refreshes after the first turn", async () => {
  window.localStorage.setItem("campus247_token", "legacy-fixture");
  const read = vi.spyOn(window.localStorage, "getItem");
  const write = vi.spyOn(window.localStorage, "setItem");
  let lists = 0;
  const fetcher = vi.spyOn(globalThis, "fetch").mockImplementation(async url => {
    const path = String(url);
    if (path.includes("/assistant/conversations?")) return ok(page(lists++ ? [entry()] : []));
    if (path.endsWith("/v1/conversations")) return ok({ id: conv });
    if (path.endsWith("/messages:stream")) {
      const final = { conversation_id: conv, message_id: message, status: "abstained",
        response_class: "safe_refusal", content: "Chưa đủ nguồn để trả lời.", citations: [] };
      const wire = `id: ${conv}\nevent: message.started\ndata: ${JSON.stringify({ conversation_id: conv, message_id: message })}\n\n`
        + `id: ${message}\nevent: message.completed\ndata: ${JSON.stringify(final)}\n\n`;
      return { ok: true, status: 200, headers: new Headers(), body: new ReadableStream({ start(controller) {
        controller.enqueue(new TextEncoder().encode(wire)); controller.close();
      } }) } as Response;
    }
    throw new Error("Unexpected request");
  });
  render(<ChatPage />);
  await screen.findByText("Chưa có hội thoại đã lưu.");
  fireEvent.change(screen.getByLabelText("Đặt câu hỏi"), { target: { value: entry().title } });
  fireEvent.click(screen.getByRole("button", { name: "Gửi" }));
  await screen.findByText("Chưa đủ nguồn để trả lời.");
  const active = await screen.findByRole("link", { name: entry().title });
  expect(active.getAttribute("aria-current")).toBe("page");
  expect(new URL(window.location.href).searchParams.get("conversation_id")).toBe(conv);
  expect(lists).toBe(2);
  expect(read.mock.calls.some(([key]) => key === "campus247_token")).toBe(false);
  expect(write.mock.calls.some(([key]) => key === "campus247_token")).toBe(false);
  expect(window.localStorage.getItem("campus247_token")).toBeNull();
  for (const [url, options] of fetcher.mock.calls) {
    expect(String(url)).not.toContain("/auth/demo-session");
    expect(options?.credentials).toBe("include");
    expect(new Headers(options?.headers).has("Authorization")).toBe(false);
  }
});

it.each(["restore", "send"])("offers login with the current redirect after %s returns 401 without renewal", async action => {
  if (action === "restore") window.history.replaceState(null, "", `/chat?conversation_id=${conv}`);
  const fetcher = vi.spyOn(globalThis, "fetch").mockImplementation(async url => String(url).includes("/assistant/conversations?")
    ? ok(page([])) : { ok: false, status: 401 } as Response);
  render(<ChatPage />);
  if (action === "send") {
    fireEvent.change(screen.getByLabelText("Đặt câu hỏi"), { target: { value: "Học phí" } });
    fireEvent.click(screen.getByRole("button", { name: "Gửi" }));
  }
  await screen.findByText(/Phiên đăng nhập đã hết hạn/);
  const redirect = action === "restore" ? `/chat?conversation_id=${conv}` : "/chat";
  expect(screen.getByRole("link", { name: "Đăng nhập lại" }).getAttribute("href")).toBe(`/login?redirect=${encodeURIComponent(redirect)}`);
  expect(fetcher.mock.calls.some(([url]) => String(url).includes("demo-session"))).toBe(false);
});
