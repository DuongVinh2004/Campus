import React from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { AppShell } from "./AppShell";

let roles: unknown;
beforeEach(() => {
  roles = ["KNOWLEDGE_ADMIN", "STUDENT"];
  vi.stubEnv("NEXT_PUBLIC_KNOWLEDGE_PLATFORM", "true");
  vi.stubGlobal("BroadcastChannel", undefined);
  vi.stubGlobal("ResizeObserver", class { observe() {} disconnect() {} });
  vi.spyOn(globalThis, "fetch").mockImplementation(async () => new Response(JSON.stringify({
    user_id: "019a0000-0000-7000-8000-000000000001", display_name: "Synthetic owner", roles,
  })));
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); vi.unstubAllEnvs(); });

it("conceals cached source administration when the same account loses a role, retaining its draft", async () => {
  render(<AppShell activeNav="knowledge"><label>Private source draft<input defaultValue="" /></label></AppShell>);
  await screen.findByRole("link", { name: "Đổi tài khoản: Synthetic owner" });
  fireEvent.change(screen.getByRole("textbox", { name: "Private source draft" }), { target: { value: "Unsent source edit" } });
  roles = ["STUDENT"];
  fireEvent(window, new Event("focus"));
  await screen.findByText(/Quyền truy cập của tài khoản đã thay đổi/);
  expect(screen.queryByRole("textbox", { name: "Private source draft" })).toBeNull();
  roles = ["STUDENT", "KNOWLEDGE_ADMIN"];
  fireEvent.click(screen.getByRole("button", { name: "Kiểm tra lại tài khoản" }));
  expect((await screen.findByRole("textbox", { name: "Private source draft" }) as HTMLInputElement).value).toBe("Unsent source edit");
});

it("accepts the same roles in a different order without hiding cached content", async () => {
  render(<AppShell activeNav="knowledge"><label>Private source draft<input defaultValue="Unsent source edit" /></label></AppShell>);
  await screen.findByRole("link", { name: "Đổi tài khoản: Synthetic owner" });
  roles = ["STUDENT", "KNOWLEDGE_ADMIN", "STUDENT"];
  fireEvent(window, new Event("focus"));
  expect((await screen.findByRole("textbox", { name: "Private source draft" }) as HTMLInputElement).value).toBe("Unsent source edit");
  expect(screen.queryByRole("alert")).toBeNull();
});

it.each([null, ["KNOWLEDGE_ADMIN", 7]])("conceals cached content when role verification is malformed: %j", async value => {
  render(<AppShell activeNav="knowledge"><label>Private source draft<input defaultValue="Unsent source edit" /></label></AppShell>);
  await screen.findByRole("link", { name: "Đổi tài khoản: Synthetic owner" });
  roles = value;
  fireEvent(window, new Event("focus"));
  await screen.findByText(/Quyền truy cập của tài khoản đã thay đổi/);
  expect(screen.queryByRole("textbox", { name: "Private source draft" })).toBeNull();
});
