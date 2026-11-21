import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { LanguageProvider } from "../../lib/i18n";
import { RoomFinder } from "./RoomFinder";
import { roomsApi } from "@/lib/campus-ops-api";

vi.mock("@/lib/campus-ops-api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/campus-ops-api")>();
  return { ...actual, roomsApi: { list: vi.fn(), availabilityMany: vi.fn(), preview: vi.fn(), confirm: vi.fn(), mine: vi.fn(), cancel: vi.fn(), newKey: vi.fn(() => "k") } };
});

const limits = { open: "07:00", close: "21:00", min_minutes: 30, max_minutes: 240, step_minutes: 30, horizon_days: 14, max_active_bookings: 3 };
const room = { id: "r1", room_code: "H1-101", display_name: "Phòng học 101", building: "H1", floor: 1, capacity: 40, kind: "lecture", features: ["MAY_CHIEU", "WIFI"], status: "ACTIVE", source: "SYNTHETIC" };

beforeEach(() => { document.cookie = "lang=en; path=/"; });
afterEach(() => { cleanup(); document.cookie = "lang=; path=/; max-age=0"; });

describe("RoomFinder in English", () => {
  it("translates headings, filters, kinds, features and counts; leaves room names from the data alone", async () => {
    vi.mocked(roomsApi.list).mockResolvedValue({ items: [room], buildings: ["H1"], source: "SYNTHETIC", limits } as never);
    vi.mocked(roomsApi.availabilityMany).mockResolvedValue({ date: "d", open: "07:00", close: "21:00", limits, items: [{ room, busy: [] }], missing: [] } as never);
    vi.mocked(roomsApi.mine).mockResolvedValue({ items: [] });
    render(<LanguageProvider><RoomFinder /></LanguageProvider>);
    expect(await screen.findByRole("heading", { name: "Rooms" })).toBeInTheDocument();
    expect(screen.getByText("All buildings")).toBeInTheDocument();
    expect(screen.getByText("Building H1 · Floor 1")).toBeInTheDocument();
    expect(screen.getByText("40 seats")).toBeInTheDocument();
    expect(screen.getByText("Projector")).toBeInTheDocument();
    expect(screen.getByText("Lecture hall", { selector: "span,div,p" })).toBeInTheDocument();
    expect(screen.getByText("Phòng học 101")).toBeInTheDocument();
  });
});
