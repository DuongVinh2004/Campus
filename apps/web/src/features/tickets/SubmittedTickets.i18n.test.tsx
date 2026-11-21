import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { SubmittedTickets } from "./SubmittedTickets";
import { LanguageProvider } from "../../lib/i18n";
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

describe("SubmittedTickets in English", () => {
  beforeEach(() => { vi.clearAllMocks(); document.cookie = "lang=en; path=/"; });
  afterEach(() => { cleanup(); document.cookie = "lang=; path=/; max-age=0"; });

  it("translates the heading, status and field captions; leaves the request data as written", async () => {
    vi.mocked(ticketsApi.mine).mockResolvedValue({ items: [sampleTicket] });
    render(<LanguageProvider><SubmittedTickets /></LanguageProvider>);
    expect(screen.getByRole("status")).toHaveTextContent("Loading…");
    expect(await screen.findByRole("heading", { name: "Sent requests" })).toBeInTheDocument();
    expect(await screen.findByTestId("submitted-ticket-tk-001")).toBeInTheDocument();
    expect(screen.getByText("More information needed")).toBeInTheDocument();
    expect(screen.getByText("Officer in charge:")).toBeInTheDocument();
    expect(screen.getByText("Xin giấy xác nhận vay vốn ngân hàng")).toBeInTheDocument();
  });

  it("shows the English empty state", async () => {
    vi.mocked(ticketsApi.mine).mockResolvedValue({ items: [] });
    render(<LanguageProvider><SubmittedTickets /></LanguageProvider>);
    expect(await screen.findByText("You have not sent any request")).toBeInTheDocument();
    expect(screen.getByText("Write a draft under 'Academic services', then press 'Send request'.")).toBeInTheDocument();
  });
});
