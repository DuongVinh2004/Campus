import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ThemeToggle } from "./ThemeToggle";
import * as themeModule from "@/lib/theme";

describe("ThemeToggle Component (W0-5)", () => {
  it("renders light mode icon and toggles theme when clicked", () => {
    const toggleThemeMock = vi.fn();
    vi.spyOn(themeModule, "useTheme").mockReturnValue({
      theme: "light",
      toggleTheme: toggleThemeMock,
    } as any);

    render(<ThemeToggle />);

    const button = screen.getByRole("button", { name: /Chuyển sang giao diện tối/i });
    expect(button).toBeDefined();
    expect(button.getAttribute("aria-pressed")).toBe("false");
    fireEvent.click(button);
    expect(toggleThemeMock).toHaveBeenCalledTimes(1);
  });

  it("renders dark mode state with label when requested", () => {
    vi.spyOn(themeModule, "useTheme").mockReturnValue({
      theme: "dark",
      toggleTheme: vi.fn(),
    } as any);

    render(<ThemeToggle showLabel={true} />);

    expect(screen.getByText("Chuyển sang giao diện sáng")).toBeDefined();
    const button = screen.getByRole("button", { name: /Chuyển sang giao diện sáng/i });
    expect(button).toBeDefined();
    expect(button.getAttribute("aria-pressed")).toBe("true");
  });
});
