import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { TodayTasks } from "./TodayTasks";
import { nudgesApi } from "../../lib/nudges-api";

vi.mock("../../lib/nudges-api", () => ({ nudgesApi: { today: vi.fn(), done: vi.fn(), snooze: vi.fn(), preferences: vi.fn(), setPreferences: vi.fn() } }));
vi.mock("next/link", () => ({ default: ({ href, children }: { href: string; children: React.ReactNode }) => <a href={href}>{children}</a> }));
const api = vi.mocked(nudgesApi);

const item = { key: "ann:1", kind: "ANNOUNCEMENT_ACK", title: "Lịch thi cuối kỳ", reason: "Hạn xác nhận ngày mai", due_at: null, urgency: "HIGH", link: "/announcements?id=1" };

describe("TodayTasks", () => {
  beforeEach(() => { Object.values(api).forEach(m => m.mockReset()); });
  afterEach(() => cleanup());

  it("lists tasks with a word for urgency and reloads after Done", async () => {
    api.today.mockResolvedValueOnce({ items: [item] }).mockResolvedValueOnce({ items: [] });
    api.done.mockResolvedValue({ key: "ann:1", state: "DONE" });
    render(<TodayTasks />);
    expect(await screen.findByText("Gấp")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Lịch thi cuối kỳ" }).getAttribute("href")).toBe("/announcements?id=1");
    fireEvent.click(screen.getByRole("button", { name: "Đã xong: Lịch thi cuối kỳ" }));
    await waitFor(() => expect(api.done).toHaveBeenCalledWith("ann:1"));
    expect(await screen.findByText(/không có việc nào/)).toBeTruthy();
  });

  it("snoozes for a day and shows a failure instead of crashing", async () => {
    api.today.mockResolvedValueOnce({ items: [item] });
    api.snooze.mockRejectedValue(new Error("Không hoãn được."));
    render(<TodayTasks />);
    fireEvent.click(await screen.findByRole("button", { name: /Hoãn 1 ngày/ }));
    await waitFor(() => expect(api.snooze).toHaveBeenCalledWith("ann:1", 24));
    expect((await screen.findByRole("alert")).textContent).toContain("Không hoãn được");
  });
});
