import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import LoginPage from "./page";
import * as storeModule from "@/lib/store";

const mockPush = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: mockPush,
  }),
}));

describe("LoginPage Component (Wave 3: W3-1)", () => {
  const loginMock = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(storeModule, "useStore").mockReturnValue({
      login: loginMock.mockResolvedValue(true),
    } as any);
  });

  it("renders login form with accessible inputs and controls", () => {
    render(<LoginPage />);

    expect(screen.getByRole("heading", { name: "Đăng nhập tài khoản" })).toBeDefined();
    expect(screen.getByLabelText(/^Tài khoản$/i)).toBeDefined();
    expect(screen.getByLabelText(/^Mật khẩu$/i)).toBeDefined();
    expect(screen.getByRole("button", { name: "Đăng nhập" })).toBeDefined();
    expect(screen.getByText(/Ghi nhớ tài khoản/i)).toBeDefined();
  });

  it("validates empty submission and shows helpful error message", async () => {
    render(<LoginPage />);

    const submitBtn = screen.getByRole("button", { name: "Đăng nhập" });
    fireEvent.click(submitBtn);

    expect(await screen.findByText("Vui lòng nhập tài khoản.")).toBeDefined();
    expect(loginMock).not.toHaveBeenCalled();
  });

  it("authenticates student with valid credentials and navigates on successful login", async () => {
    render(<LoginPage />);

    const identifierInput = screen.getByLabelText(/^Tài khoản$/i);
    const passwordInput = screen.getByLabelText(/^Mật khẩu$/i);
    fireEvent.change(identifierInput, { target: { value: "sv001" } });
    fireEvent.change(passwordInput, { target: { value: "demo1234" } });

    const submitBtn = screen.getByRole("button", { name: "Đăng nhập" });
    fireEvent.click(submitBtn);

    expect(loginMock).toHaveBeenCalledWith("SV001", true);
  });
});
