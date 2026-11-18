import React from "react";
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { HandoverPanel, type HandoverReceipt } from "./HandoverPanel";

describe("HandoverPanel Component (TASK-WEB-SAFE-001)", () => {
  afterEach(() => {
    cleanup();
  });

  const mockReceipt: HandoverReceipt = {
    receiptId: "rcpt-hitl-001",
    department: "Phòng Đào tạo & Quản lý Sinh viên",
    reason: "Vấn đề khiếu nại điểm thi vượt thẩm quyền AI",
    assignedQueue: "QUEUE_EXAM_REVIEW",
    estimatedResponseHours: 4,
    status: "queued",
  };

  it("renders handover receipt with department and estimated response time", () => {
    render(<HandoverPanel receipt={mockReceipt} isAvailable={true} />);

    expect(screen.getByText(/Chuyển tiếp chuyên viên hỗ trợ/i)).toBeDefined();
    expect(screen.getByText("Phòng Đào tạo & Quản lý Sinh viên")).toBeDefined();
    expect(screen.getByText(/Thời gian phản hồi dự kiến: 4 giờ/i)).toBeDefined();
    expect(screen.getByText(/Mã biên nhận: rcpt-hitl-001/i)).toBeDefined();
  });

  it("AC-TASK-WEB-SAFE-001-01: renders approved emergency fallback copy and forbids fabricated contacts", () => {
    render(<HandoverPanel receipt={mockReceipt} isAvailable={true} />);

    const emergencyBtn = screen.getByRole("button", { name: /Đường dây nóng khẩn cấp/i });
    fireEvent.click(emergencyBtn);

    // Must NOT display fabricated phone numbers
    expect(screen.queryByText(/024-3869-XXXX/i)).toBeNull();
    expect(screen.queryByText(/024-3869-YYYY/i)).toBeNull();

    // Must render the official institutional emergency contacts
    expect(
      screen.getByText(/Đầu mối hỗ trợ khẩn cấp chính thức Trường Đại học Xây dựng Hà Nội/i)
    ).toBeDefined();
    expect(screen.getByText(/Phòng Y tế/i)).toBeDefined();
  });

  it("AC-TASK-WEB-SAFE-001-02: provides honest handover status without claiming human has received or will answer", () => {
    render(<HandoverPanel receipt={mockReceipt} isAvailable={true} />);

    // Must NOT claim human has already received and is reviewing
    expect(screen.queryByText(/Chuyên viên tiếp nhận đã được thông báo và đang xem xét yêu cầu của bạn/i)).toBeNull();

    // Must state honest queue status
    expect(screen.getByText(/Yêu cầu của bạn đã được tiếp nhận vào hàng chờ xử lý của đơn vị/i)).toBeDefined();
  });

  it("renders non-color indicators on emergency action", () => {
    render(<HandoverPanel receipt={mockReceipt} isAvailable={true} />);

    const emergencyBtn = screen.getByRole("button", { name: /Đường dây nóng khẩn cấp/i });
    // Emergency button contains accessible icon with label/title or non-color hint
    expect(emergencyBtn.querySelector("svg")).not.toBeNull();
  });

  it("renders unavailable state outside working hours", () => {
    render(<HandoverPanel receipt={mockReceipt} isAvailable={false} />);

    expect(screen.getByText(/Hiện ngoài giờ tiếp nhận trực tuyến/i)).toBeDefined();
    expect(screen.getByText(/Yêu cầu của bạn đã được ghi nhận vào hàng đợi/i)).toBeDefined();
  });
});
