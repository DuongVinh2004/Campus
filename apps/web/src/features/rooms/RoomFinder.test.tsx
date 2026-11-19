import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, cleanup } from "@testing-library/react";
import { RoomFinder } from "./RoomFinder";
import { roomsApi, type RoomList, type Availability, type Booking, type BookingPreview } from "@/lib/campus-ops-api";

vi.mock("@/lib/campus-ops-api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/campus-ops-api")>();
  return {
    ...actual,
    roomsApi: {
      list: vi.fn(),
      availability: vi.fn(),
      preview: vi.fn(),
      confirm: vi.fn(),
      mine: vi.fn(),
      cancel: vi.fn(),
      newKey: vi.fn(() => "test-idempotency-key"),
    },
    problemMessage: vi.fn((err: unknown) => (err as { message?: string })?.message || "Lỗi thao tác"),
  };
});

const mockLimits = {
  open: "07:00",
  close: "21:00",
  min_minutes: 30,
  max_minutes: 240,
  step_minutes: 15,
  horizon_days: 14,
  max_active_bookings: 3,
};

const mockRoomList: RoomList = {
  source: "LOCAL_SYNTHETIC",
  buildings: ["H1", "H2"],
  limits: mockLimits,
  items: [
    {
      id: "room-101",
      room_code: "H1-101",
      display_name: "Phòng học 101 H1",
      building: "H1",
      floor: 1,
      capacity: 40,
      kind: "lecture",
      features: ["WIFI", "MAY_CHIEU", "DIEU_HOA"],
      status: "ACTIVE",
      source: "LOCAL_SYNTHETIC",
    },
    {
      id: "room-102",
      room_code: "H1-102",
      display_name: "Phòng máy 102 H1",
      building: "H1",
      floor: 1,
      capacity: 30,
      kind: "lab",
      features: ["MAY_TINH"],
      status: "MAINTENANCE",
      source: "LOCAL_SYNTHETIC",
    },
  ],
};

const mockAvailability: Availability = {
  room: mockRoomList.items[0],
  date: "2025-05-10",
  open: "07:00",
  close: "21:00",
  limits: mockLimits,
  busy: [
    {
      starts_at: "2025-05-10T14:00:00+07:00",
      ends_at: "2025-05-10T16:00:00+07:00",
      type: "CLASS",
      label: "Cơ học kết cấu",
    },
  ],
};

const mockMyBookings: Booking[] = [
  {
    id: "booking-1",
    booking_id: "booking-1",
    code: "BK-12345",
    room_id: "room-101",
    room_code: "H1-101",
    room_name: "Phòng học 101 H1",
    building: "H1",
    starts_at: "2025-05-10T09:00:00+07:00",
    ends_at: "2025-05-10T11:00:00+07:00",
    purpose: "Học nhóm môn Tin học",
    attendees: 5,
    status: "CONFIRMED",
    created_at: "2025-05-09T08:00:00+07:00",
    cancelled_at: null,
    can_cancel: true,
  },
];

describe("RoomFinder", () => {
  beforeEach(() => {
    vi.mocked(roomsApi.list).mockResolvedValue(mockRoomList);
    vi.mocked(roomsApi.availability).mockResolvedValue(mockAvailability);
    vi.mocked(roomsApi.mine).mockResolvedValue({ items: mockMyBookings });
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("hiển thị banner dữ liệu mô phỏng, danh sách phòng và tiện nghi", async () => {
    render(<RoomFinder />);

    expect(
      await screen.findByText(
        "Dữ liệu phòng là dữ liệu mô phỏng nội bộ, chưa kết nối hệ thống quản lý phòng của HUCE."
      )
    ).toBeInTheDocument();

    expect(screen.getByTestId("room-card-H1-101")).toBeInTheDocument();
    expect(screen.getByText("Phòng học 101 H1")).toBeInTheDocument();
    expect(screen.getByText("Wi‑Fi")).toBeInTheDocument();
    expect(screen.getByText("Máy chiếu")).toBeInTheDocument();
    expect(screen.getByText("Trống trong khung giờ này")).toBeInTheDocument();

    expect(screen.getByTestId("room-card-H1-102")).toBeInTheDocument();
    expect(screen.getByText("Đang bảo trì")).toBeInTheDocument();
    expect(screen.getByTestId("room-book-H1-102")).toBeDisabled();
  });

  it("hiển thị lỗi khi tải phòng thất bại và cho phép thử lại", async () => {
    vi.mocked(roomsApi.list).mockRejectedValueOnce(new Error("Không thể kết nối máy chủ"));

    render(<RoomFinder />);

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Không thể kết nối máy chủ");

    const retryBtn = screen.getByRole("button", { name: "Thử lại" });
    fireEvent.click(retryBtn);

    expect(await screen.findByTestId("room-card-H1-101")).toBeInTheDocument();
  });

  it("thực hiện luồng mở dialog, xem trước và xác nhận đặt phòng", async () => {
    const mockPreview: BookingPreview = {
      preview_id: "prev-123",
      can_confirm: true,
      problems: [],
      conflicts: [],
      expires_at: "2025-05-10T09:15:00+07:00",
      notice: "Phòng đủ điều kiện để xác nhận.",
      summary: {
        room_id: "room-101",
        room_code: "H1-101",
        room_name: "Phòng học 101 H1",
        starts_at: "2025-05-10T09:00:00+07:00",
        ends_at: "2025-05-10T11:00:00+07:00",
        purpose: "Họp nhóm đồ án tốt nghiệp",
        attendees: 4,
      },
    };

    const mockConfirmed: Booking = {
      id: "booking-2",
      booking_id: "booking-2",
      code: "BK-67890",
      room_id: "room-101",
      room_code: "H1-101",
      room_name: "Phòng học 101 H1",
      building: "H1",
      starts_at: "2025-05-10T09:00:00+07:00",
      ends_at: "2025-05-10T11:00:00+07:00",
      purpose: "Họp nhóm đồ án tốt nghiệp",
      attendees: 4,
      status: "CONFIRMED",
      created_at: "2025-05-09T08:30:00+07:00",
      cancelled_at: null,
      can_cancel: true,
    };

    vi.mocked(roomsApi.preview).mockResolvedValue(mockPreview);
    vi.mocked(roomsApi.confirm).mockResolvedValue(mockConfirmed);

    const dispatchSpy = vi.spyOn(window, "dispatchEvent");

    render(<RoomFinder />);

    const bookBtn = await screen.findByTestId("room-book-H1-101");
    fireEvent.click(bookBtn);

    const dialog = screen.getByTestId("booking-dialog");
    expect(dialog).toBeInTheDocument();

    const purposeInput = screen.getByLabelText(/Mục đích sử dụng/);
    fireEvent.change(purposeInput, { target: { value: "Họp nhóm đồ án tốt nghiệp" } });

    const previewBtn = screen.getByTestId("booking-preview-button");
    fireEvent.click(previewBtn);

    expect(await screen.findByText("Lịch phòng hợp lệ!")).toBeInTheDocument();

    const confirmBtn = screen.getByTestId("booking-confirm-button");
    expect(confirmBtn).not.toBeDisabled();
    fireEvent.click(confirmBtn);

    expect(await screen.findByText("Đặt phòng thành công!")).toBeInTheDocument();
    expect(screen.getByText("BK-67890")).toBeInTheDocument();

    expect(roomsApi.confirm).toHaveBeenCalledWith("prev-123", "test-idempotency-key");
    expect(dispatchSpy).toHaveBeenCalledWith(expect.objectContaining({ type: "campus:notifications-changed" }));
  });

  it("hiển thị lượt đặt của tôi và cho phép hủy đặt có xác nhận", async () => {
    vi.mocked(roomsApi.cancel).mockResolvedValue({
      ...mockMyBookings[0],
      status: "CANCELLED",
      can_cancel: false,
    });

    const dispatchSpy = vi.spyOn(window, "dispatchEvent");

    render(<RoomFinder />);

    const myBookingsSection = await screen.findByTestId("my-bookings");
    expect(myBookingsSection).toHaveTextContent("BK-12345");
    expect(myBookingsSection).toHaveTextContent("Đã xác nhận");

    const cancelBtn = screen.getByTestId("booking-cancel-BK-12345");
    fireEvent.click(cancelBtn);

    expect(screen.getByText("Hủy lượt đặt này?")).toBeInTheDocument();

    const confirmYesBtn = screen.getByRole("button", { name: "Có" });
    fireEvent.click(confirmYesBtn);

    await waitFor(() => {
      expect(roomsApi.cancel).toHaveBeenCalledWith("booking-1");
    });
    expect(dispatchSpy).toHaveBeenCalledWith(expect.objectContaining({ type: "campus:notifications-changed" }));
  });
});
