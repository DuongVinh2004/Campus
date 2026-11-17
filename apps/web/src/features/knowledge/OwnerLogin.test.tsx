import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { OwnerLogin } from "./OwnerLogin";

afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

describe("cookie session login", () => {
  it.each([
    ["STUDENT", "", "/chat"],
    ["KNOWLEDGE_ADMIN", "", "/knowledge/sources"],
    ["STUDENT", "/tickets?request=fixture", "/tickets?request=fixture"],
    ["STUDENT", "https://outside.invalid/", "/chat"],
    ["STUDENT", "//outside.invalid/", "/chat"],
    ["STUDENT", "/\\outside.invalid/", "/chat"],
    ["STUDENT", "/\noutside.invalid/", "/chat"],
  ])("uses an HttpOnly session and safe redirect (%s, %s)", async (role, redirect, expected) => {
    const assign = vi.fn();
    const realWindow = window;
    vi.stubGlobal("window", new Proxy(realWindow, { get: (target, key) => key === "location"
      ? { search: `?redirect=${encodeURIComponent(redirect)}`, assign } : Reflect.get(target, key) }));
    const write = vi.spyOn(Storage.prototype, "setItem");
    const read = vi.spyOn(Storage.prototype, "getItem");
    const fetcher = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({
      roles: [role], user_id: "019a0000-0000-7000-8000-000000000009",
    }), { headers: { "content-type": "application/json", "set-cookie": "session=fixture; HttpOnly; SameSite=Strict" } }));
    render(<OwnerLogin />);
    fireEvent.change(screen.getByLabelText("Tài khoản"), { target: { value: "fixture-user" } });
    fireEvent.change(screen.getByLabelText("Mật khẩu"), { target: { value: "fixture-password" } });
    fireEvent.submit(screen.getByRole("button", { name: "Đăng nhập" }).closest("form")!);
    await waitFor(() => expect(assign).toHaveBeenCalledWith(expected));
    expect(fetcher).toHaveBeenCalledWith("/v1/knowledge/platform/session", expect.objectContaining({ credentials: "include", method: "POST" }));
    expect(write).not.toHaveBeenCalled();
    expect(read).not.toHaveBeenCalled();
  });

  it("keeps failed login on the form without reporting success", async () => {
    const fetcher = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("{}", { status: 401 }));
    render(<OwnerLogin />);
    fireEvent.submit(screen.getByRole("button", { name: "Đăng nhập" }).closest("form")!);
    await screen.findByRole("alert");
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
});
