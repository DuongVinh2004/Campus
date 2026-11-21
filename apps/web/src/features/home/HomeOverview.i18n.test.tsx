import React from "react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { LanguageProvider } from "../../lib/i18n";
import HomeOverview from "./HomeOverview";

beforeEach(() => { document.cookie = "lang=en; path=/"; });
afterEach(() => { cleanup(); document.cookie = "lang=; path=/; max-age=0"; });

describe("home page in English", () => {
  it("translates the greeting, services and empty states", () => {
    render(<LanguageProvider><HomeOverview /></LanguageProvider>);
    expect(screen.getByRole("heading", { level: 1, name: "Hello, what do you need help with today?" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Essential services" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Find a room/ })).toBeInTheDocument();
    expect(screen.getByText("Timetable is not connected yet")).toBeInTheDocument();
  });
});
