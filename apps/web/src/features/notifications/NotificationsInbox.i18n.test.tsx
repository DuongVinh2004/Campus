import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, fireEvent } from "@testing-library/react";
import { LanguageProvider } from "../../lib/i18n";
import { NotificationsInbox } from "./NotificationsInbox";
import { notificationsApi } from "@/lib/campus-ops-api";

vi.mock("next/link", () => ({ default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => <a href={href} {...rest}>{children}</a> }));
vi.mock("@/lib/campus-ops-api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/campus-ops-api")>("@/lib/campus-ops-api");
  return { ...actual, notificationsApi: { list: vi.fn(), markRead: vi.fn(), markAllRead: vi.fn() } };
});

beforeEach(() => { document.cookie = "lang=en; path=/"; });
afterEach(() => { cleanup(); vi.restoreAllMocks(); document.cookie = "lang=; path=/; max-age=0"; });

const item = (minutes: number) => ({ id: "n", kind: "TICKET", title: "Cập nhật", body: "Nội dung", link: "/tickets/1", created_at: new Date(Date.now() - minutes * 60000).toISOString(), read: false });

describe("notification inbox in English", () => {
  it("translates the heading, filters, relative time and the empty state; leaves the notification text alone", async () => {
    vi.mocked(notificationsApi.list).mockResolvedValue({ items: [item(5)], unread_count: 1 });
    render(<LanguageProvider><NotificationsInbox /></LanguageProvider>);
    expect(await screen.findByRole("heading", { name: "Notifications" })).toBeInTheDocument();
    expect(screen.getByText("All")).toBeInTheDocument();
    expect(screen.getByText("Unread (1)")).toBeInTheDocument();
    expect(screen.getByText("Mark all as read")).toBeInTheDocument();
    expect(screen.getByText("5 min ago")).toBeInTheDocument();
    expect(screen.getByText("Cập nhật")).toBeInTheDocument(); // text from the server stays as written
  });

  it("shows the English empty state", async () => {
    vi.mocked(notificationsApi.list).mockResolvedValue({ items: [], unread_count: 0 });
    render(<LanguageProvider><NotificationsInbox /></LanguageProvider>);
    expect(await screen.findByText("No notifications yet")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Unread (0)"));
    expect(await screen.findByText("No unread notifications")).toBeInTheDocument();
  });
});
