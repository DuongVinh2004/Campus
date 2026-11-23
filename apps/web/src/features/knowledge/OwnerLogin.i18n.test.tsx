import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { LanguageProvider } from "../../lib/i18n";
import { OwnerLogin } from "./OwnerLogin";

beforeEach(() => { document.cookie = "lang=; path=/; max-age=0"; });
afterEach(() => { cleanup(); vi.restoreAllMocks(); document.cookie = "lang=; path=/; max-age=0"; });

const page = () => render(<LanguageProvider><OwnerLogin /></LanguageProvider>);

describe("sign-in page in two languages", () => {
  it("is Vietnamese by default and has a language switch", () => {
    page();
    expect(screen.getByRole("heading", { name: "Đăng nhập Campus 24/7" })).toBeTruthy();
    expect(screen.getByLabelText(/^Tài khoản/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Chuyển sang tiếng Anh" })).toBeTruthy();
  });

  it("switches every visible text to English, including the password reveal and the error", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("{}", { status: 401 }));
    page();
    fireEvent.click(screen.getByRole("button", { name: "Chuyển sang tiếng Anh" }));
    expect(screen.getByRole("heading", { name: "Sign in to Campus 24/7" })).toBeTruthy();
    expect(screen.getByLabelText(/^Account/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Sign in" })).toBeTruthy();
    expect(screen.getByRole("button", { name: /Show/ })).toBeTruthy();
    expect(screen.getByText("Open the chatbot and see the knowledge base status")).toBeTruthy();
    fireEvent.submit(screen.getByRole("button", { name: "Sign in" }).closest("form")!);
    expect((await screen.findByRole("alert")).textContent).toContain("Wrong account or password.");
  });
});
