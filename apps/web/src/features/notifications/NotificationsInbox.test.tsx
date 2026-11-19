import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { NotificationsInbox } from "./NotificationsInbox";
import { notificationsApi, type AppNotification } from "@/lib/campus-ops-api";

vi.mock("next/link", () => ({
  default: ({
    href,
    children,
    onClick,
    ...rest
  }: {
    href: string;
    children: React.ReactNode;
    onClick?: () => void;
    [key: string]: unknown;
  }) => (
    <a href={href} onClick={onClick} {...rest}>
      {children}
    </a>
  ),
}));

vi.mock("@/lib/campus-ops-api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/campus-ops-api")>(
    "@/lib/campus-ops-api"
  );
  return {
    ...actual,
    notificationsApi: {
      list: vi.fn(),
      markRead: vi.fn(),
      markAllRead: vi.fn(),
    },
  };
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const sampleNotifications: AppNotification[] = [
  {
    id: "notif-1",
    kind: "TICKET",
    title: "Cập nhật yêu cầu học vụ",
    body: "Đơn xin cấp giấy xác nhận đã được duyệt.",
    link: "/tickets/ticket-123",
    created_at: new Date(Date.now() - 5 * 60 * 1000).toISOString(),
    read: false,
  },
  {
    id: "notif-2",
    kind: "ROOM_BOOKING",
    title: "Xác nhận đặt phòng H1-301",
    body: "Phòng học nhóm đã được đặt thành công.",
    link: "/rooms/bookings",
    created_at: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
    read: true,
  },
];

describe("NotificationsInbox", () => {
  it("renders notifications list and displays unread count", async () => {
    vi.mocked(notificationsApi.list).mockResolvedValue({
      items: sampleNotifications,
      unread_count: 1,
    });

    render(<NotificationsInbox />);

    expect(screen.getByRole("status")).toHaveTextContent("Đang tải…");

    expect(await screen.findByText("Cập nhật yêu cầu học vụ")).toBeInTheDocument();
    expect(screen.getByText("Xác nhận đặt phòng H1-301")).toBeInTheDocument();
    expect(screen.getByTestId("notifications-filter-unread")).toHaveTextContent("Chưa đọc (1)");
    expect(screen.getByText("Mới")).toBeInTheDocument();
  });

  it("filters by unread notifications when filter tab is clicked", async () => {
    vi.mocked(notificationsApi.list).mockImplementation(async (opts) => {
      if (opts?.unreadOnly) {
        return {
          items: [sampleNotifications[0]],
          unread_count: 1,
        };
      }
      return {
        items: sampleNotifications,
        unread_count: 1,
      };
    });

    render(<NotificationsInbox />);
    await screen.findByText("Cập nhật yêu cầu học vụ");

    const unreadFilter = screen.getByTestId("notifications-filter-unread");
    fireEvent.click(unreadFilter);

    await waitFor(() => {
      expect(notificationsApi.list).toHaveBeenCalledWith({ unreadOnly: true });
    });
    expect(screen.getByText("Cập nhật yêu cầu học vụ")).toBeInTheDocument();
    expect(screen.queryByText("Xác nhận đặt phòng H1-301")).not.toBeInTheDocument();
  });

  it("marks a single notification as read on click", async () => {
    vi.mocked(notificationsApi.list).mockResolvedValue({
      items: [sampleNotifications[0]],
      unread_count: 1,
    });
    // A consistent server: once the item is marked read, the next list call reports it as read.
    vi.mocked(notificationsApi.markRead).mockImplementation(async () => {
      vi.mocked(notificationsApi.list).mockResolvedValue({ items: [{ ...sampleNotifications[0], read: true }], unread_count: 0 });
      return { updated: 1 };
    });

    render(<NotificationsInbox />);
    const item = await screen.findByTestId("notification-item-notif-1");
    expect(screen.getByText("Mới")).toBeInTheDocument();

    fireEvent.click(item);

    await waitFor(() => {
      expect(notificationsApi.markRead).toHaveBeenCalledWith("notif-1");
    });
    await waitFor(() => expect(screen.queryByText("Mới")).not.toBeInTheDocument());
    expect(screen.getByTestId("notifications-filter-unread")).toHaveTextContent("Chưa đọc (0)");
  });

  it("marks all notifications as read when mark all button is clicked", async () => {
    vi.mocked(notificationsApi.list).mockResolvedValue({
      items: sampleNotifications,
      unread_count: 1,
    });
    vi.mocked(notificationsApi.markAllRead).mockImplementation(async () => {
      vi.mocked(notificationsApi.list).mockResolvedValue({ items: sampleNotifications.map(n => ({ ...n, read: true })), unread_count: 0 });
      return { updated: 1 };
    });

    render(<NotificationsInbox />);
    await screen.findByText("Cập nhật yêu cầu học vụ");

    const readAllBtn = screen.getByTestId("notifications-read-all");
    expect(readAllBtn).not.toBeDisabled();

    fireEvent.click(readAllBtn);

    await waitFor(() => {
      expect(notificationsApi.markAllRead).toHaveBeenCalledTimes(1);
    });
    await waitFor(() => expect(readAllBtn).toBeDisabled());
    expect(screen.queryByText("Mới")).not.toBeInTheDocument();
  });

  it("renders error state with retry button on failure", async () => {
    vi.mocked(notificationsApi.list)
      .mockRejectedValueOnce(new Error("Lỗi tải thông báo"))
      .mockResolvedValueOnce({
        items: sampleNotifications,
        unread_count: 1,
      });

    render(<NotificationsInbox />);

    const alert = await screen.findByRole("alert");
    expect(alert).toBeInTheDocument();

    const retryBtn = screen.getByRole("button", { name: "Thử lại" });
    fireEvent.click(retryBtn);

    expect(await screen.findByText("Cập nhật yêu cầu học vụ")).toBeInTheDocument();
  });

  it("renders empty state when there are no notifications", async () => {
    vi.mocked(notificationsApi.list).mockResolvedValue({
      items: [],
      unread_count: 0,
    });

    render(<NotificationsInbox />);

    expect(await screen.findByText("Chưa có thông báo")).toBeInTheDocument();
    expect(screen.getByTestId("notifications-read-all")).toBeDisabled();
  });
});
