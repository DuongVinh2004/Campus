import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { LanguageProvider } from "../../lib/i18n";
import { WeekSchedule } from "./WeekSchedule";
import { scheduleApi } from "@/lib/campus-ops-api";

vi.mock("@/lib/campus-ops-api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/campus-ops-api")>("@/lib/campus-ops-api");
  return { ...actual, scheduleApi: { list: vi.fn(), create: vi.fn(), update: vi.fn(), remove: vi.fn() } };
});

beforeEach(() => { document.cookie = "lang=en; path=/"; vi.mocked(scheduleApi.list).mockResolvedValue({ items: [], page: { next_cursor: null, has_more: false, limit: 100 }, sources: [] } as never); });
afterEach(() => { cleanup(); document.cookie = "lang=; path=/; max-age=0"; });

describe("WeekSchedule in English", () => {
  it("translates headings, week buttons, day names, empty states and the event dialog", async () => {
    render(<LanguageProvider><WeekSchedule /></LanguageProvider>);
    expect(await screen.findByRole("heading", { name: "Timetable" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Previous week" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Next week" })).toBeInTheDocument();
    expect(screen.getByText("Monday")).toBeInTheDocument();
    expect(screen.getByText("Sunday")).toBeInTheDocument();
    expect(await screen.findByText("No classes or events this week.")).toBeInTheDocument();
    expect(screen.getByText(/^Week \d+ ·/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Add event/ }));
    expect(await screen.findByText("Add personal event")).toBeInTheDocument();
    expect(screen.getByText("Event name")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save event" })).toBeInTheDocument();
  });
});
