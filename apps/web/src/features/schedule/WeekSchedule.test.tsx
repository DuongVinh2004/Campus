import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { ApiClientError } from "@/lib/api/client";
import { WeekSchedule } from "./WeekSchedule";
import { scheduleApi, ScheduleResponse } from "@/lib/campus-ops-api";

vi.mock("@/lib/campus-ops-api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/campus-ops-api")>("@/lib/campus-ops-api");
  return {
    ...actual,
    scheduleApi: {
      list: vi.fn(),
      create: vi.fn(),
      update: vi.fn(),
      remove: vi.fn(),
    },
  };
});

const mockList = vi.mocked(scheduleApi.list);
const mockCreate = vi.mocked(scheduleApi.create);
const mockUpdate = vi.mocked(scheduleApi.update);
const mockRemove = vi.mocked(scheduleApi.remove);

const mockScheduleData: ScheduleResponse = {
  items: [
    {
      id: "class-1",
      kind: "CLASS",
      course_code: "XD101",
      course_name: "Cơ học kết cấu",
      starts_at: "2025-05-12T07:30:00+07:00",
      ends_at: "2025-05-12T10:00:00+07:00",
      location_label: "P.301-H1",
      instructor_display_name: "TS. Nguyễn Văn A",
      note: "Học lý thuyết",
      source_system: "HUCE_SIS",
      editable: false,
    },
    {
      id: "exam-1",
      kind: "EXAM",
      course_code: "XD102",
      course_name: "Bê tông cốt thép",
      starts_at: "2025-05-14T13:30:00+07:00",
      ends_at: "2025-05-14T15:00:00+07:00",
      location_label: "P.402-A1",
      instructor_display_name: "",
      note: "Đem máy tính cầm tay",
      source_system: "HUCE_SIS",
      editable: false,
    },
    {
      id: "personal-1",
      kind: "PERSONAL",
      course_code: "",
      course_name: "Họp nhóm đồ án",
      starts_at: "2025-05-15T09:00:00+07:00",
      ends_at: "2025-05-15T11:00:00+07:00",
      location_label: "Thư viện H1",
      instructor_display_name: "",
      note: "Chuẩn bị bản vẽ",
      source_system: "CAMPUS_OPS",
      editable: true,
    },
  ],
  page: { next_cursor: null, has_more: false, limit: 50 },
  sources: ["LOCAL_SYNTHETIC"],
};

describe("WeekSchedule", () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date("2025-05-14T05:00:00Z"));
    vi.clearAllMocks();
    mockList.mockResolvedValue(mockScheduleData);
    mockCreate.mockResolvedValue(mockScheduleData.items[2]);
    mockUpdate.mockResolvedValue(mockScheduleData.items[2]);
    mockRemove.mockResolvedValue({ id: "personal-1", deleted: true });
  });

  afterEach(() => {
    vi.useRealTimers();
    cleanup();
  });

  it("hiển thị lịch học, banner mô phỏng, bảng sắp tới và các nút điều hướng", async () => {
    render(<WeekSchedule />);

    expect(screen.getByRole("status")).toHaveTextContent("Đang tải lịch học…");

    await waitFor(() => {
      expect(screen.getByTestId("week-schedule")).toBeInTheDocument();
    });

    expect(
      screen.getByText("Lịch học và lịch thi là dữ liệu mô phỏng nội bộ, chưa kết nối Cổng đào tạo HUCE.")
    ).toBeInTheDocument();

    expect(screen.getByTestId("week-prev")).toBeInTheDocument();
    expect(screen.getByTestId("week-today")).toBeInTheDocument();
    expect(screen.getByTestId("week-next")).toBeInTheDocument();
    expect(screen.getByTestId("upcoming-panel")).toBeInTheDocument();

    expect(screen.getByTestId("schedule-event-class-1")).toHaveTextContent("Cơ học kết cấu");
    expect(screen.getByTestId("schedule-event-class-1")).toHaveTextContent("Lớp học");
    expect(screen.getByTestId("schedule-event-exam-1")).toHaveTextContent("Bê tông cốt thép");
    expect(screen.getByTestId("schedule-event-exam-1")).toHaveTextContent("Lịch thi");
    expect(screen.getByTestId("schedule-event-personal-1")).toHaveTextContent("Họp nhóm đồ án");
    expect(screen.getByTestId("schedule-event-personal-1")).toHaveTextContent("Cá nhân");
  });

  it("hiển thị trạng thái rỗng khi không có lịch học trong tuần", async () => {
    mockList.mockResolvedValue({
      items: [],
      page: { next_cursor: null, has_more: false, limit: 50 },
      sources: [],
    });

    render(<WeekSchedule />);

    await waitFor(() => {
      expect(screen.getByText("Không có lịch học hoặc sự kiện trong tuần này.")).toBeInTheDocument();
    });

    const emptySlots = screen.getAllByText("Không có lịch");
    expect(emptySlots.length).toBeGreaterThanOrEqual(7);
  });

  it("hiển thị trạng thái lỗi và cho phép thử lại", async () => {
    mockList.mockRejectedValueOnce(new ApiClientError({ type: "x", title: "Lỗi", status: 503, detail: "Không thể kết nối máy chủ đào tạo", code: "UNAVAILABLE" }));

    render(<WeekSchedule />);

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Không thể kết nối máy chủ đào tạo");

    const retryBtn = screen.getByRole("button", { name: "Thử lại" });
    mockList.mockResolvedValueOnce(mockScheduleData);
    fireEvent.click(retryBtn);

    await waitFor(() => {
      expect(screen.getByTestId("schedule-event-class-1")).toBeInTheDocument();
    });
  });

  it("mở hộp thoại thêm sự kiện, kiểm tra giờ kết thúc > giờ bắt đầu và tạo thành công", async () => {
    const notifySpy = vi.spyOn(window, "dispatchEvent");
    render(<WeekSchedule />);

    await waitFor(() => {
      expect(screen.getByTestId("add-event-button")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("add-event-button"));

    const dialog = screen.getByTestId("event-dialog");
    expect(dialog).toBeInTheDocument();
    expect(dialog).toHaveAttribute("role", "dialog");
    expect(dialog).toHaveAttribute("aria-modal", "true");

    const titleInput = screen.getByLabelText(/Tên sự kiện/);
    const startInput = screen.getByLabelText(/Giờ bắt đầu/);
    const endInput = screen.getByLabelText(/Giờ kết thúc/);

    fireEvent.change(titleInput, { target: { value: "Ôn tập kết cấu" } });
    fireEvent.change(startInput, { target: { value: "14:00" } });
    fireEvent.change(endInput, { target: { value: "10:00" } });

    expect(screen.getByText("Giờ kết thúc phải sau giờ bắt đầu")).toBeInTheDocument();

    fireEvent.change(endInput, { target: { value: "16:00" } });
    expect(screen.queryByText("Giờ kết thúc phải sau giờ bắt đầu")).not.toBeInTheDocument();

    const saveBtn = screen.getByTestId("event-save-button");
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(mockCreate).toHaveBeenCalledWith(
        expect.objectContaining({
          title: "Ôn tập kết cấu",
          starts_at: expect.stringContaining("T14:00:00+07:00"),
          ends_at: expect.stringContaining("T16:00:00+07:00"),
        })
      );
    });

    expect(notifySpy).toHaveBeenCalledWith(expect.objectContaining({ type: "campus:notifications-changed" }));
  });

  it("cho phép xác nhận xóa sự kiện cá nhân ngay trên thẻ", async () => {
    const notifySpy = vi.spyOn(window, "dispatchEvent");
    render(<WeekSchedule />);

    await waitFor(() => {
      expect(screen.getByTestId("schedule-event-personal-1")).toBeInTheDocument();
    });

    const personalCard = screen.getByTestId("schedule-event-personal-1");
    const deleteBtn = personalCard.querySelector("button:last-child")!;
    expect(deleteBtn).toHaveTextContent("Xóa");

    fireEvent.click(deleteBtn);

    expect(screen.getByText("Xác nhận xóa sự kiện này?")).toBeInTheDocument();
    const confirmDeleteBtn = screen.getByRole("button", { name: "Xác nhận xóa" });
    fireEvent.click(confirmDeleteBtn);

    await waitFor(() => {
      expect(mockRemove).toHaveBeenCalledWith("personal-1");
    });
    expect(notifySpy).toHaveBeenCalledWith(expect.objectContaining({ type: "campus:notifications-changed" }));
  });
});
