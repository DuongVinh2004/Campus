import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, cleanup, within, fireEvent } from "@testing-library/react";
import { afterEach } from "vitest";
import { AppShell } from "./AppShell";

describe("AppShell Component (TASK-WEB-SHELL-001)", () => {
  beforeEach(() => { vi.stubGlobal("ResizeObserver", class { observe() {} disconnect() {} }); });
  afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); vi.unstubAllEnvs(); });
  it("removes the legacy credential on load without reading or writing a token", async () => {
    vi.stubEnv("NEXT_PUBLIC_KNOWLEDGE_PLATFORM", "true");
    const fetcher = vi.spyOn(globalThis, "fetch").mockResolvedValue({ ok: false, status: 401 } as Response);
    window.localStorage.setItem("campus247_token", "legacy-fixture");
    const read = vi.spyOn(window.localStorage, "getItem");
    const write = vi.spyOn(window.localStorage, "setItem");
    render(<AppShell activeNav="chat" />);
    expect(read.mock.calls.some(([key]) => key === "campus247_token")).toBe(false);
    expect(write.mock.calls.some(([key]) => key === "campus247_token")).toBe(false);
    expect(window.localStorage.getItem("campus247_token")).toBeNull();
    expect(fetcher).toHaveBeenCalledWith(expect.stringContaining("/v1/users/me"), expect.objectContaining({ credentials: "include" }));
    expect(new Headers(fetcher.mock.calls[0][1]?.headers).has("Authorization")).toBe(false);
    expect(await screen.findByRole("link", { name: "Đăng nhập lại" })).toBeDefined();
  });
  it("shows the main student services with the signed-in account and no admin navigation", async () => {
    vi.stubEnv("NEXT_PUBLIC_KNOWLEDGE_PLATFORM", "true");
    vi.spyOn(globalThis, "fetch").mockResolvedValue({ ok: true, json: async () => ({ display_name: "Sinh viên local", student_code: "LOCAL-STUDENT-001", roles: ["STUDENT"] }) } as Response);
    render(<AppShell activeNav="chat"><div>Chat</div></AppShell>);
    await screen.findByRole("link", { name: "Đổi tài khoản: Sinh viên local" });
    const navigation = within(screen.getByRole("navigation", { name: "Điều hướng chính" }));
    expect(navigation.getByRole("link", { name: "Dịch vụ học vụ" }).getAttribute("href")).toBe("/services");
    expect(navigation.getByRole("link", { name: "Hồ sơ của tôi" }).getAttribute("href")).toBe("/tickets");
    expect(navigation.queryByRole("link", { name: "Quản trị nguồn" })).toBeNull();
    expect(screen.getByRole("button", { name: "Thu gọn menu" })).toBeDefined();
  });
  it("renders the Stitch institutional toolbar and shared navigation", () => {
    render(
      <AppShell>
        <div>Page Content</div>
      </AppShell>
    );

    // Official institutional portal header
    const banner = screen.getByRole("banner");
    expect(within(banner).getByText(/Campus 24\/7/i)).toBeDefined();
    expect(within(banner).getByText(/HUCE/i)).toBeDefined();
    expect(within(banner).getByRole("search", { name: "Tìm nhanh trong Campus" })).toBeDefined();

    // Semantic landmarks
    expect(banner).toBeDefined();
    expect(screen.getByRole("navigation", { name: "Điều hướng chính" })).toBeDefined();
    expect(screen.getByRole("main")).toBeDefined();

    // Skip to content link
    const skipLink = screen.getByText(/Bỏ qua tới nội dung chính/i);
    expect(skipLink).toBeDefined();
    expect(skipLink.getAttribute("href")).toBe("#main-content");

    // Children rendered in main
    expect(screen.getByText("Page Content")).toBeDefined();
  });


  it("filters navigation items based on userRole", () => {
    const { rerender, queryByRole } = render(
      <AppShell userRole="student">
        <div>Content</div>
      </AppShell>
    );
    expect(within(screen.getByRole("navigation", { name: "Điều hướng chính" })).queryByRole("link", { name: "Trợ lý" })).not.toBeNull();
    expect(within(screen.getByRole("navigation", { name: "Điều hướng chính" })).queryByRole("link", { name: "Cán bộ" })).toBeNull();

    rerender(
      <AppShell userRole="staff">
        <div>Content</div>
      </AppShell>
    );
    expect(within(screen.getByRole("navigation", { name: "Điều hướng chính" })).queryByRole("link", { name: "Cán bộ" })).not.toBeNull();
    expect(within(screen.getByRole("navigation", { name: "Điều hướng chính" })).queryByRole("link", { name: "Trợ lý" })).toBeNull();
  });

  it("negative path: handles empty or null children without crashing", () => {
    const { container } = render(<AppShell>{null}</AppShell>);
    const main = container.querySelector("main");
    expect(main).not.toBeNull();
    expect(main?.children.length).toBe(0);
  });

  it("renders public knowledge mode with external HUCE service links", () => {
    render(
      <AppShell publicKnowledge={true}>
        <div>Public Content</div>
      </AppShell>
    );

    expect(screen.getByText(/CỔNG THÔNG TIN CÔNG KHAI/i)).toBeDefined();
    expect(screen.getByRole("link", { name: "Cổng sinh viên" })).toBeDefined();
    expect(screen.getByRole("link", { name: "Một cửa HUCE" })).toBeDefined();
    expect(screen.getByRole("link", { name: "Thư viện HUCE" })).toBeDefined();
  });

  it("handles guest role without leaking privileged navigation", () => {
    render(
      <AppShell userRole="guest">
        <div>Guest View</div>
      </AppShell>
    );

    expect(within(screen.getByRole("navigation", { name: "Điều hướng chính" })).getByRole("link", { name: "Trợ lý" })).not.toBeNull();
    expect(within(screen.getByRole("navigation", { name: "Điều hướng chính" })).queryByRole("link", { name: "Cán bộ" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Quản trị" })).toBeNull();
  });

  it("opens mobile navigation dialog when menu button is clicked", () => {
    render(
      <AppShell>
        <div>Content</div>
      </AppShell>
    );

    const menuButton = screen.getByRole("button", { name: /Mở điều hướng/i });
    expect(menuButton).toBeDefined();
    expect(menuButton.getAttribute("aria-expanded")).toBe("false");

    fireEvent.click(menuButton);
    expect(menuButton.getAttribute("aria-expanded")).toBe("true");
    expect(screen.getByRole("dialog")).toBeDefined();
    expect(screen.getByRole("heading", { name: "Điều hướng Campus 24/7" })).toBeDefined();
  });
});
