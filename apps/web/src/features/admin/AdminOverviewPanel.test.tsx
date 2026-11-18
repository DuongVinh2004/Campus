import { ApiClientError } from "@/lib/api/client";
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { AdminOverviewPanel } from "./AdminOverviewPanel";
import { adminApi, AdminOverview } from "@/lib/campus-ops-api";

vi.mock("@/lib/campus-ops-api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/campus-ops-api")>("@/lib/campus-ops-api");
  return {
    ...actual,
    adminApi: {
      overview: vi.fn(),
    },
  };
});

const mockOverviewData: AdminOverview = {
  tickets: {
    by_status: {
      SUBMITTED: 3,
      IN_REVIEW: 2,
      NEED_INFO: 1,
      RESOLVED: 4,
      REJECTED: 0,
      CANCELLED: 0,
    },
    overdue: 2,
    total: 10,
  },
  bookings: {
    by_status: {
      CONFIRMED: 5,
      CANCELLED: 1,
    },
    upcoming: 4,
  },
  rooms: {
    by_status: {
      ACTIVE: 8,
      MAINTENANCE: 2,
    },
    total: 10,
  },
  schedule_entries: 15,
  recent_audit: [
    {
      at: "2025-05-15T02:30:00Z",
      actor: "usr_01948392847293",
      action: "room.book",
      resource: "room_h1_101",
    },
    {
      at: "2025-05-15T03:00:00Z",
      actor: "usr_01948392847294",
      action: "ticket.submit",
      resource: "tkt_01948392847294",
    },
    {
      at: "2025-05-15T04:15:00Z",
      actor: "usr_01948392847295",
      action: "schedule.create",
      resource: "evt_01948392847295",
    },
  ],
  data_sources: {
    rooms: "mock",
    timetable: "mock",
    note: "Dữ liệu vận hành được mô phỏng phục vụ kiểm thử.",
  },
};

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(() => {
  cleanup();
});

describe("AdminOverviewPanel", () => {
  it("renders loading state initially", () => {
    vi.mocked(adminApi.overview).mockReturnValue(new Promise(() => {}));
    render(<AdminOverviewPanel />);

    const statusEl = screen.getByRole("status");
    expect(statusEl.textContent).toContain("Đang tải…");
  });

  it("renders overview metrics, progress bars and audit logs successfully", async () => {
    vi.mocked(adminApi.overview).mockResolvedValue(mockOverviewData);
    render(<AdminOverviewPanel />);

    await waitFor(() => {
      expect(screen.getByTestId("admin-overview")).toBeInTheDocument();
    });

    expect(screen.getByTestId("admin-stat-tickets")).toHaveTextContent("10");
    expect(screen.getByTestId("admin-stat-tickets")).toHaveTextContent("2 hồ sơ quá hạn");

    expect(screen.getByTestId("admin-stat-bookings")).toHaveTextContent("4");
    expect(screen.getByTestId("admin-stat-rooms")).toHaveTextContent("10");
    expect(screen.getByTestId("admin-stat-rooms")).toHaveTextContent("Đang bảo trì: 2");

    expect(screen.getByText("Dữ liệu vận hành được mô phỏng phục vụ kiểm thử.")).toBeInTheDocument();

    const progressBar = screen.getByRole("img", { name: /Đã gửi, chờ tiếp nhận: 3 \(30%\)/ });
    expect(progressBar).toBeInTheDocument();

    const auditTable = screen.getByTestId("admin-audit-table");
    expect(auditTable).toBeInTheDocument();
    expect(screen.getByText("Đặt phòng")).toBeInTheDocument();
    expect(screen.getByText("Gửi hồ sơ")).toBeInTheDocument();
    expect(screen.getByText("Lịch cá nhân")).toBeInTheDocument();
    expect(screen.getAllByText("usr_01948392847293").length).toBeGreaterThan(0);
  });

  it("handles error state and retries on button click", async () => {
    vi.mocked(adminApi.overview).mockRejectedValueOnce(new ApiClientError({ type: "x", title: "Lỗi", status: 500, detail: "Lỗi kết nối máy chủ", code: "INTERNAL_ERROR" }));
    render(<AdminOverviewPanel />);

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Lỗi kết nối máy chủ");

    const retryBtn = screen.getByRole("button", { name: "Thử lại" });
    vi.mocked(adminApi.overview).mockResolvedValueOnce(mockOverviewData);
    fireEvent.click(retryBtn);

    await waitFor(() => {
      expect(screen.getByTestId("admin-overview")).toBeInTheDocument();
      expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    });
    expect(adminApi.overview).toHaveBeenCalledTimes(2);
  });

  it("handles 403 forbidden state with required message", async () => {
    const error403 = Object.assign(new Error("Forbidden"), { status: 403 });
    vi.mocked(adminApi.overview).mockRejectedValueOnce(error403);
    render(<AdminOverviewPanel />);

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Chỉ quản trị viên mới xem được trang này.");
  });

  it("renders empty audit table state when recent_audit is empty", async () => {
    vi.mocked(adminApi.overview).mockResolvedValueOnce({
      ...mockOverviewData,
      recent_audit: [],
    });
    render(<AdminOverviewPanel />);

    await waitFor(() => {
      expect(screen.getByTestId("admin-audit-table")).toBeInTheDocument();
    });
    expect(screen.getByText("Chưa có thao tác nào gần đây")).toBeInTheDocument();
  });

  it("triggers data refresh when clicking Làm mới button", async () => {
    vi.mocked(adminApi.overview).mockResolvedValue(mockOverviewData);
    render(<AdminOverviewPanel />);

    const refreshBtn = await screen.findByTestId("admin-refresh");
    fireEvent.click(refreshBtn);

    expect(adminApi.overview).toHaveBeenCalledTimes(2);
  });
});
