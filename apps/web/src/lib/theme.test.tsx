import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { ThemeProvider } from "./theme";
import { ThemeToggle } from "../components/ThemeToggle";

describe("ThemeToggle without the data store (operational build)", () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.classList.remove("dark");
  });

  it("switches to dark, remembers it, and switches back", () => {
    render(<ThemeProvider><ThemeToggle /></ThemeProvider>);
    fireEvent.click(screen.getByRole("button", { name: "Chuyển sang giao diện tối" }));
    expect(document.documentElement.classList.contains("dark")).toBe(true);
    expect(localStorage.getItem("campus247_theme_v2")).toBe("dark");
    fireEvent.click(screen.getByRole("button", { name: "Chuyển sang giao diện sáng" }));
    expect(document.documentElement.classList.contains("dark")).toBe(false);
    expect(localStorage.getItem("campus247_theme_v2")).toBe("light");
  });

  it("starts dark when the person chose dark before", () => {
    localStorage.setItem("campus247_theme_v2", "dark");
    render(<ThemeProvider><ThemeToggle /></ThemeProvider>);
    expect(document.documentElement.classList.contains("dark")).toBe(true);
    expect(screen.getByRole("button", { name: "Chuyển sang giao diện sáng" })).toBeTruthy();
  });
});
