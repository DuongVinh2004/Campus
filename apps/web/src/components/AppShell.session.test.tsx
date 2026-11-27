import React from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { AppShell } from "./AppShell";
import { ChatPanel } from "../features/chat/ChatPanel";
import { AccessibleDialog } from "./shared/AccessibleDialog";

const actor = "019a0000-0000-7000-8000-000000000001";
let currentActor = actor;
beforeEach(() => {
  currentActor = actor;
  vi.stubEnv("NEXT_PUBLIC_KNOWLEDGE_PLATFORM", "true");
  vi.stubGlobal("BroadcastChannel", undefined);
  vi.stubGlobal("ResizeObserver", class { observe() {} disconnect() {} });
  vi.spyOn(globalThis, "fetch").mockImplementation(async () => new Response(JSON.stringify({
    user_id: currentActor, display_name: "Synthetic owner", roles: ["STUDENT"],
  })));
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); vi.unstubAllEnvs(); });

it.each(["tickets", "privacy", "knowledge"])("conceals %s data and preserves a form draft across account changes", async activeNav => {
  render(<AppShell activeNav={activeNav}><label>Nháp riêng<input defaultValue="" /></label></AppShell>);
  await screen.findByRole("link", { name: "Đổi tài khoản: Synthetic owner" });
  fireEvent.change(screen.getByRole("textbox", { name: "Nháp riêng" }), { target: { value: "Unsent private draft" } });
  currentActor = "019a0000-0000-7000-8000-000000000009";
  fireEvent(window, new Event("focus"));
  await screen.findByText(/Tài khoản đăng nhập đã thay đổi/);
  expect(screen.queryByRole("textbox", { name: "Nháp riêng" })).toBeNull();
  currentActor = actor;
  fireEvent.click(screen.getByRole("button", { name: "Kiểm tra lại tài khoản" }));
  expect((await screen.findByRole("textbox", { name: "Nháp riêng" }) as HTMLInputElement).value).toBe("Unsent private draft");
});

it("preserves edits to a search-seeded chat draft after session validation", async () => {
  render(<AppShell activeNav="chat"><ChatPanel messages={[]} initialDraft="Original search" /></AppShell>);
  await screen.findByRole("link", { name: "Đổi tài khoản: Synthetic owner" });
  fireEvent.change(screen.getByRole("textbox", { name: "Đặt câu hỏi" }), { target: { value: "Edited private chat draft" } });
  currentActor = "019a0000-0000-7000-8000-000000000009";
  fireEvent(window, new Event("focus"));
  await screen.findByText(/Tài khoản đăng nhập đã thay đổi/);
  expect(screen.queryByRole("textbox", { name: "Đặt câu hỏi" })).toBeNull();
  currentActor = actor;
  fireEvent.click(screen.getByRole("button", { name: "Kiểm tra lại tài khoản" }));
  expect((await screen.findByRole("textbox", { name: "Đặt câu hỏi" }) as HTMLTextAreaElement).value).toBe("Edited private chat draft");
});

it("also conceals a private portal dialog while retaining its unsent input", async () => {
  render(<AppShell activeNav="tickets"><AccessibleDialog open onClose={() => {}} labelledBy="private-preview">
    <h2 id="private-preview">Private preview</h2><label>Private modal draft<input defaultValue="Unsent modal text" /></label>
  </AccessibleDialog></AppShell>);
  await screen.findByRole("dialog", { name: "Private preview" });
  await screen.findByRole("link", { name: "Đổi tài khoản: Synthetic owner" });
  currentActor = "019a0000-0000-7000-8000-000000000009";
  fireEvent(window, new Event("focus"));
  await screen.findByText(/Tài khoản đăng nhập đã thay đổi/);
  expect(screen.queryByRole("dialog", { name: "Private preview" })).toBeNull();
  currentActor = actor;
  fireEvent.click(screen.getByRole("button", { name: "Kiểm tra lại tài khoản" }));
  expect((await screen.findByRole("textbox", { name: "Private modal draft" }) as HTMLInputElement).value).toBe("Unsent modal text");
});

it("signs out through the server so the session cookie is revoked, then returns to the login page", async () => {
  const assign = vi.fn();
  vi.stubGlobal("location", { ...window.location, assign });
  render(<AppShell activeNav="tickets"><p>Nội dung</p></AppShell>);
  fireEvent.click(await screen.findByRole("button", { name: "Đăng xuất" }));
  await vi.waitFor(() => expect(assign).toHaveBeenCalledWith("/login"));
  const logout = vi.mocked(fetch).mock.calls.find(([url]) => String(url).endsWith("/v1/auth/logout"));
  expect(logout?.[1]).toMatchObject({ method: "POST", credentials: "include" });
});
