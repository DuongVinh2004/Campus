import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";
import { UnifiedAssistantProvider, useUnifiedAssistant } from "./unified-assistant-runtime";

vi.mock("next/navigation", () => ({ usePathname: () => "/chat" }));
vi.mock("./store", () => ({ useStore: () => ({ dataConfig: { mode: "api" }, currentUser: { id: "fixture", role: "STUDENT" } }) }));
let serial = 20;
function Harness() {
  const runtime = useUnifiedAssistant();
  return <><span>{runtime.actor?.display_name || "Chưa xác thực"}</span>
    <input aria-label="Nháp trợ lý" value={runtime.active?.input || ""} onChange={e => runtime.input(e.target.value)} />
    {runtime.authenticationRequired && <p role="alert">Đăng nhập lại</p>}</>;
}
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe("unified assistant cookie identity", () => {
  it.each(["account", "role", "expired"])("revalidates identity on focus and conceals the old draft after %s changes", async change => {
    let user = { user_id: `019a0000-0000-7000-8000-${String(serial++).padStart(12, "0")}`, roles: ["STUDENT"], display_name: "Sinh viên thử" };
    let expired = false;
    const fetcher = vi.spyOn(globalThis, "fetch").mockImplementation(async (url, init) => {
      expect(init?.credentials).toBe("include");
      expect(new Headers(init?.headers).has("Authorization")).toBe(false);
      return new Response(JSON.stringify(String(url).endsWith("/users/me")
        ? expired ? { status: 401, code: "AUTHENTICATION_REQUIRED" } : user
        : { audience: "student", tenant_id: "fixture-tenant", history: false }), { status: expired ? 401 : 200 });
    });
    const read = vi.spyOn(Storage.prototype, "getItem");
    const write = vi.spyOn(Storage.prototype, "setItem");
    render(<UnifiedAssistantProvider><Harness /></UnifiedAssistantProvider>);
    await screen.findByText("Sinh viên thử");
    fireEvent.change(screen.getByLabelText("Nháp trợ lý"), { target: { value: "Nội dung riêng chưa lưu" } });
    expect(screen.getByLabelText("Nháp trợ lý")).toHaveValue("Nội dung riêng chưa lưu");
    if (change === "account") user = { ...user, user_id: "019a0000-0000-7000-8000-000000000099" };
    if (change === "role") user = { ...user, roles: ["SUPPORT_OFFICER"] };
    if (change === "expired") expired = true;
    fireEvent.focus(window);
    await screen.findByText("Chưa xác thực");
    await waitFor(() => expect(screen.getByLabelText("Nháp trợ lý")).toHaveValue(""));
    if (expired) expect(screen.getByRole("alert")).toHaveTextContent("Đăng nhập lại");
    expect(fetcher).toHaveBeenCalledTimes(3);
    expect(read).not.toHaveBeenCalled(); expect(write).not.toHaveBeenCalled();
  });
});
