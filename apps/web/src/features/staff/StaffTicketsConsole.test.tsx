import { ApiClientError } from "@/lib/api/client";
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { StaffTicketsConsole } from "./StaffTicketsConsole";
import { staffApi, type StaffQueue, type Ticket, type TicketDetail } from "@/lib/campus-ops-api";

vi.mock("@/lib/campus-ops-api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/campus-ops-api")>("@/lib/campus-ops-api");
  return {
    ...actual,
    staffApi: {
      queue: vi.fn(),
      detail: vi.fn(),
      claim: vi.fn(),
      reply: vi.fn(),
      setStatus: vi.fn(),
      note: vi.fn(),
    },
  };
});

const sampleTicket1: Ticket = {
  id: "t-1",
  code: "TK-001",
  service_kind: "GENERAL_SUPPORT",
  service_label: "Hỗ trợ thủ tục học vụ",
  title: "Yêu cầu cấp bảng điểm tạm thời",
  summary: "Cần bảng điểm học kỳ 1 để làm hồ sơ học bổng.",
  fields: { "Học kỳ": "Kỳ 1", "Số lượng": "2 bản" },
  status: "SUBMITTED",
  priority: "NORMAL",
  owner_display: "Nguyễn Văn A",
  owner_code: "123456",
  assignee_display: null,
  created_at: "2025-02-15T08:30:00Z",
  updated_at: "2025-02-15T08:30:00Z",
  due_at: "2025-02-20T17:00:00Z",
  overdue: false,
};

const sampleTicket2: Ticket = {
  id: "t-2",
  code: "TK-002",
  service_kind: "GRADE_APPEAL",
  service_label: "Phúc khảo kết quả học tập",
  title: "Phúc khảo điểm thi Toán cao cấp",
  summary: "Điểm thi có sự chênh lệch lớn.",
  fields: { "Mã môn": "MATH101" },
  status: "IN_REVIEW",
  priority: "HIGH",
  owner_display: "Trần Thị B",
  owner_code: "654321",
  assignee_display: "Cán bộ Hỗ trợ",
  created_at: "2025-02-10T08:30:00Z",
  updated_at: "2025-02-11T09:00:00Z",
  due_at: "2025-02-12T17:00:00Z",
  overdue: true,
};

const sampleQueue: StaffQueue = {
  items: [sampleTicket1, sampleTicket2],
  counts: {
    SUBMITTED: 1,
    IN_REVIEW: 1,
    NEED_INFO: 0,
    RESOLVED: 0,
    REJECTED: 0,
    CANCELLED: 0,
  },
  overdue: 1,
};

const sampleDetail1: TicketDetail = {
  ...sampleTicket1,
  events: [
    {
      id: "ev-1",
      kind: "CREATED",
      actor_role: "STUDENT",
      actor_display: "Nguyễn Văn A",
      body: "Đã tạo yêu cầu hỗ trợ",
      visibility: "PUBLIC",
      created_at: "2025-02-15T08:30:00Z",
    },
    {
      id: "ev-2",
      kind: "NOTE",
      actor_role: "STAFF",
      actor_display: "Cán bộ Lưu",
      body: "Đã kiểm tra sơ bộ hồ sơ.",
      visibility: "INTERNAL",
      created_at: "2025-02-15T09:00:00Z",
    },
  ],
  allowed_actions: ["claim", "reply", "note"],
};

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

beforeEach(() => {
  vi.mocked(staffApi.queue).mockResolvedValue(sampleQueue);
  vi.mocked(staffApi.detail).mockResolvedValue(sampleDetail1);
});

describe("StaffTicketsConsole", () => {
  it("renders queue list with filter chips and ticket cards", async () => {
    render(<StaffTicketsConsole />);

    expect(screen.getByTestId("staff-console")).toBeDefined();
    await waitFor(() => {
      expect(screen.getByTestId("staff-ticket-t-1")).toBeDefined();
      expect(screen.getByTestId("staff-ticket-t-2")).toBeDefined();
    });

    expect(screen.getByTestId("staff-filter-open")).toBeDefined();
    expect(screen.getByTestId("staff-filter-SUBMITTED")).toBeDefined();
    expect(screen.getByTestId("staff-filter-IN_REVIEW")).toBeDefined();
    expect(screen.getByTestId("staff-filter-closed")).toBeDefined();

    expect(screen.getByText("Yêu cầu cấp bảng điểm tạm thời")).toBeDefined();
    expect(screen.getByText("Phúc khảo điểm thi Toán cao cấp")).toBeDefined();
    expect(screen.getByText("Quá hạn")).toBeDefined();
  });

  it("loads ticket detail when initialId is provided", async () => {
    render(<StaffTicketsConsole initialId="t-1" />);

    await waitFor(() => {
      expect(staffApi.detail).toHaveBeenCalledWith("t-1");
    });

    const detailPanel = screen.getByTestId("staff-detail");
    expect(detailPanel).toBeDefined();

    expect(await screen.findByText("Cần bảng điểm học kỳ 1 để làm hồ sơ học bổng.")).toBeDefined();
    expect(screen.getByText("Kỳ 1")).toBeDefined();
    expect(screen.getByText("Ghi chú nội bộ — sinh viên không thấy")).toBeDefined();
    expect(screen.getByText("Đã kiểm tra sơ bộ hồ sơ.")).toBeDefined();
  });

  it("handles queue error and allows retry", async () => {
    vi.mocked(staffApi.queue).mockRejectedValueOnce(new ApiClientError({ type: "x", title: "Lỗi", status: 503, detail: "Lỗi kết nối máy chủ", code: "UNAVAILABLE" }));
    render(<StaffTicketsConsole />);

    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("Lỗi kết nối máy chủ");

    vi.mocked(staffApi.queue).mockResolvedValueOnce(sampleQueue);
    fireEvent.click(screen.getByRole("button", { name: "Thử lại" }));

    await waitFor(() => {
      expect(screen.getByTestId("staff-ticket-t-1")).toBeDefined();
    });
  });

  it("claims ticket on button click and fires notification event", async () => {
    const dispatchSpy = vi.spyOn(window, "dispatchEvent");
    vi.mocked(staffApi.claim).mockResolvedValueOnce({
      ...sampleDetail1,
      assignee_display: "Cán bộ Hiện Tại",
      allowed_actions: ["reply", "note"],
    });

    render(<StaffTicketsConsole initialId="t-1" />);

    const claimBtn = await screen.findByTestId("staff-claim-button");
    fireEvent.click(claimBtn);

    await waitFor(() => {
      expect(staffApi.claim).toHaveBeenCalledWith("t-1");
      expect(dispatchSpy).toHaveBeenCalledWith(expect.objectContaining({ type: "campus:notifications-changed" }));
    });
  });

  it("requires confirmation when reply status is RESOLVED and submits on confirm", async () => {
    vi.mocked(staffApi.reply).mockResolvedValueOnce({
      ...sampleDetail1,
      status: "RESOLVED",
      allowed_actions: ["note"],
    });

    render(<StaffTicketsConsole initialId="t-1" />);

    const textarea = await screen.findByTestId("staff-reply-input");
    fireEvent.change(textarea, { target: { value: "Đã xử lý xong và cấp bảng điểm." } });

    const statusSelect = screen.getByLabelText("Chuyển trạng thái:");
    fireEvent.change(statusSelect, { target: { value: "RESOLVED" } });

    const submitBtn = screen.getByTestId("staff-reply-submit");
    fireEvent.click(submitBtn);

    expect(screen.getByText("Đóng hồ sơ? Sinh viên sẽ được thông báo.")).toBeDefined();

    const confirmBtn = screen.getByRole("button", { name: "Xác nhận" });
    fireEvent.click(confirmBtn);

    await waitFor(() => {
      expect(staffApi.reply).toHaveBeenCalledWith("t-1", "Đã xử lý xong và cấp bảng điểm.", "RESOLVED");
    });
  });
});
