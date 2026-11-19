import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { SubmittedTickets } from "./SubmittedTickets";
import { ticketsApi, type Ticket, type TicketDetail } from "@/lib/campus-ops-api";

vi.mock("@/lib/campus-ops-api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/campus-ops-api")>(
    "@/lib/campus-ops-api"
  );
  return {
    ...actual,
    ticketsApi: {
      mine: vi.fn(),
      detail: vi.fn(),
      reply: vi.fn(),
      cancel: vi.fn(),
    },
  };
});

const sampleTicket: Ticket = {
  id: "tk-001",
  code: "TK-2025-001",
  service_kind: "STUDENT_CERTIFICATE",
  service_label: "Giấy xác nhận sinh viên đang học",
  title: "Xin giấy xác nhận vay vốn ngân hàng",
  summary: "Cần giấy xác nhận để làm thủ tục vay vốn tại địa phương",
  fields: { "Học kỳ": "Kỳ 2 năm 2024-2025", "Lý do": "Vay vốn chính sách" },
  status: "NEED_INFO",
  priority: "NORMAL",
  owner_display: "Sinh viên A",
  owner_code: "123456",
  assignee_display: "Thầy Hùng",
  created_at: "2025-03-01T08:00:00Z",
  updated_at: "2025-03-02T09:30:00Z",
  due_at: "2025-03-05T17:00:00Z",
  overdue: true,
};

const sampleDetail: TicketDetail = {
  ...sampleTicket,
  events: [
    {
      id: "ev-001",
      kind: "STAFF_REPLY",
      actor_role: "STAFF",
      actor_display: "Thầy Hùng",
      body: "Vui lòng bổ sung mẫu giấy của ngân hàng chính sách.",
      visibility: "PUBLIC",
      created_at: "2025-03-02T09:30:00Z",
    },
    {
      id: "ev-internal",
      kind: "NOTE",
      actor_role: "STAFF",
      actor_display: "Cán bộ nội bộ",
      body: "Ghi chú nội bộ không được hiển thị cho sinh viên.",
      visibility: "INTERNAL",
      created_at: "2025-03-02T09:31:00Z",
    },
  ],
  allowed_actions: ["reply", "cancel"],
};

describe("SubmittedTickets", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("hiển thị danh sách hồ sơ đã gửi và banner thông tin", async () => {
    vi.mocked(ticketsApi.mine).mockResolvedValue({ items: [sampleTicket] });

    render(<SubmittedTickets />);

    expect(screen.getByRole("status")).toHaveTextContent("Đang tải…");

    expect(
      await screen.findByText(
        "Hồ sơ được xử lý trong hệ thống Một cửa nội bộ của Campus 24/7; chưa kết nối hệ thống tiếp nhận của HUCE."
      )
    ).toBeInTheDocument();

    expect(await screen.findByTestId("submitted-tickets")).toBeInTheDocument();
    expect(screen.getByTestId("submitted-ticket-tk-001")).toBeInTheDocument();
    expect(screen.getByText("TK-2025-001")).toBeInTheDocument();
    expect(screen.getByText("Xin giấy xác nhận vay vốn ngân hàng")).toBeInTheDocument();
    expect(screen.getByText("Cần bổ sung thông tin")).toBeInTheDocument();
  });

  it("hiển thị trạng thái rỗng khi chưa gửi hồ sơ nào", async () => {
    vi.mocked(ticketsApi.mine).mockResolvedValue({ items: [] });

    render(<SubmittedTickets />);

    expect(await screen.findByText("Bạn chưa gửi hồ sơ nào")).toBeInTheDocument();
    expect(
      screen.getByText("Soạn nháp ở 'Dịch vụ học vụ' rồi bấm 'Gửi hồ sơ'.")
    ).toBeInTheDocument();
  });

  it("xử lý lỗi tải danh sách và cho phép thử lại", async () => {
    vi.mocked(ticketsApi.mine)
      .mockRejectedValueOnce(new Error("Lỗi kết nối"))
      .mockResolvedValueOnce({ items: [sampleTicket] });

    render(<SubmittedTickets />);

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Không thực hiện được. Vui lòng thử lại.");

    fireEvent.click(screen.getByRole("button", { name: "Thử lại" }));

    expect(await screen.findByTestId("submitted-tickets")).toBeInTheDocument();
  });

  it("mở chi tiết hồ sơ, lọc sự kiện nội bộ và gửi phản hồi thành công", async () => {
    vi.mocked(ticketsApi.mine).mockResolvedValue({ items: [sampleTicket] });
    vi.mocked(ticketsApi.detail).mockResolvedValue(sampleDetail);
    const updatedDetail: TicketDetail = {
      ...sampleDetail,
      status: "IN_REVIEW",
      events: [
        ...sampleDetail.events,
        {
          id: "ev-002",
          kind: "STUDENT_REPLY",
          actor_role: "STUDENT",
          actor_display: "Sinh viên A",
          body: "Em đã tải kèm mẫu ngân hàng theo yêu cầu.",
          visibility: "PUBLIC",
          created_at: "2025-03-02T10:00:00Z",
        },
      ],
    };
    vi.mocked(ticketsApi.reply).mockResolvedValue(updatedDetail);

    const dispatchSpy = vi.spyOn(window, "dispatchEvent");

    render(<SubmittedTickets initialId="tk-001" />);

    const detailPanel = await screen.findByTestId("ticket-detail");
    expect(detailPanel).toBeInTheDocument();

    expect(screen.getByText("Quá hạn")).toBeInTheDocument();
    expect(screen.getByText("Học kỳ")).toBeInTheDocument();
    expect(screen.getByText("Kỳ 2 năm 2024-2025")).toBeInTheDocument();

    // Check public events only
    expect(screen.getByText("Cán bộ")).toBeInTheDocument();
    expect(
      screen.getByText("Vui lòng bổ sung mẫu giấy của ngân hàng chính sách.")
    ).toBeInTheDocument();
    expect(
      screen.queryByText("Ghi chú nội bộ không được hiển thị cho sinh viên.")
    ).not.toBeInTheDocument();

    // NEED_INFO notice
    expect(
      screen.getByText("Cán bộ đang chờ bạn bổ sung thông tin")
    ).toBeInTheDocument();

    // Fill and submit reply
    const replyInput = screen.getByTestId("ticket-reply-input");
    const submitBtn = screen.getByTestId("ticket-reply-submit");

    fireEvent.change(replyInput, {
      target: { value: "Em đã tải kèm mẫu ngân hàng theo yêu cầu." },
    });
    expect(submitBtn).toBeEnabled();

    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(ticketsApi.reply).toHaveBeenCalledWith(
        "tk-001",
        "Em đã tải kèm mẫu ngân hàng theo yêu cầu."
      );
    });

    expect(dispatchSpy).toHaveBeenCalledWith(
      expect.objectContaining({ type: "campus:notifications-changed" })
    );
  });

  it("xác nhận hủy hồ sơ và phát thông báo", async () => {
    vi.mocked(ticketsApi.mine).mockResolvedValue({ items: [sampleTicket] });
    vi.mocked(ticketsApi.detail).mockResolvedValue(sampleDetail);
    vi.mocked(ticketsApi.cancel).mockResolvedValue({
      ...sampleDetail,
      status: "CANCELLED",
      allowed_actions: [],
    });

    const dispatchSpy = vi.spyOn(window, "dispatchEvent");

    render(<SubmittedTickets initialId="tk-001" />);

    await screen.findByTestId("ticket-detail");

    const cancelOpenBtn = screen.getByTestId("ticket-cancel-button");
    fireEvent.click(cancelOpenBtn);

    expect(screen.getByText("Xác nhận hủy hồ sơ?")).toBeInTheDocument();

    const cancelInput = screen.getByPlaceholderText("Lý do hủy (tùy chọn)");
    fireEvent.change(cancelInput, { target: { value: "Không còn nhu cầu vay" } });

    const confirmBtn = screen.getByTestId("ticket-cancel-confirm");
    fireEvent.click(confirmBtn);

    await waitFor(() => {
      expect(ticketsApi.cancel).toHaveBeenCalledWith(
        "tk-001",
        "Không còn nhu cầu vay"
      );
    });

    expect(dispatchSpy).toHaveBeenCalledWith(
      expect.objectContaining({ type: "campus:notifications-changed" })
    );
  });
});
