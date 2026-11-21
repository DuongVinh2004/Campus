import React from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { LanguageProvider } from "../lib/i18n";
import { ThemeProvider } from "../lib/theme";
import { AuthLayout } from "./AuthLayout";

beforeEach(() => { document.cookie = "lang=; path=/; max-age=0"; });
afterEach(() => { cleanup(); document.cookie = "lang=; path=/; max-age=0"; });

const page = () => render(<LanguageProvider><ThemeProvider><AuthLayout><p>form</p></AuthLayout></ThemeProvider></LanguageProvider>);

describe("AuthLayout in two languages", () => {
  it("is Vietnamese by default", () => {
    page();
    expect(screen.getByText("Hướng dẫn sử dụng")).toBeTruthy();
    expect(screen.getByText("Quay lại trang chủ")).toBeTruthy();
    expect(screen.getByText("Chính sách quyền riêng tư")).toBeTruthy();
  });

  it("switches its header, back link and footer to English and back", () => {
    page();
    fireEvent.click(screen.getByRole("button", { name: "Chuyển sang tiếng Anh" }));
    expect(screen.getByText("User guide")).toBeTruthy();
    expect(screen.getByText("Back to the home page")).toBeTruthy();
    expect(screen.getByText("Privacy policy")).toBeTruthy();
    expect(screen.queryByText("Hướng dẫn sử dụng")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Switch to Vietnamese" }));
    expect(screen.getByText("Hướng dẫn sử dụng")).toBeTruthy();
  });

  it("opens in English when the person chose it before", () => {
    document.cookie = "lang=en; path=/";
    page();
    expect(screen.getByText("User guide")).toBeTruthy();
  });
});
