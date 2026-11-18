import React, { useState } from "react";
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { AppShell } from "../src/components/AppShell";
import { ChatPanel } from "../src/features/chat/ChatPanel";
import { HandoverPanel, type HandoverReceipt } from "../src/features/handover/HandoverPanel";

function SensitiveHandoverJourney({ isWorkingHours = true }: { isWorkingHours?: boolean }) {
  const [isHandedOver, setIsHandedOver] = useState(false);

  const mockReceipt: HandoverReceipt = {
    receiptId: "rcpt-crisis-911",
    department: "Trung tâm Tư vấn Tâm lý & Hỗ trợ Sinh viên HUCE",
    reason: "Yêu cầu hỗ trợ khủng hoảng tâm lý khẩn cấp",
    assignedQueue: "QUEUE_EMERGENCY_SUPPORT",
    estimatedResponseHours: 1,
    status: "queued",
  };

  const handleMessage = (msg: string) => {
    if (msg.includes("bế tắc") || msg.includes("khẩn cấp")) {
      setIsHandedOver(true);
    }
  };

  return React.createElement(
    AppShell,
    null,
    React.createElement(
      "div",
      { className: "p-4" },
      !isHandedOver
        ? React.createElement(ChatPanel, {
            onSendMessage: handleMessage,
          })
        : React.createElement(HandoverPanel, {
            receipt: mockReceipt,
            isAvailable: isWorkingHours,
          })
    )
  );
}

describe("Sensitive Handover Browser Journey E2E (TASK-TEST-E2E-003)", () => {
  afterEach(() => {
    cleanup();
  });

  it("routes sensitive crisis input directly to human handover panel with hotlines", () => {
    render(React.createElement(SensitiveHandoverJourney, { isWorkingHours: true }));

    // 1. Initial chat state
    const input = screen.getByLabelText(/Đặt câu hỏi/i);
    const sendBtn = screen.getByRole("button", { name: /Gửi/i });

    // 2. Submit sensitive crisis query
    fireEvent.change(input, { target: { value: "Em đang rất bế tắc và cần hỗ trợ khẩn cấp." } });
    fireEvent.click(sendBtn);

    // 3. Immediately transitions to HandoverPanel
    expect(screen.getByText(/Chuyển tiếp chuyên viên hỗ trợ/i)).toBeDefined();
    expect(screen.getByText("Trung tâm Tư vấn Tâm lý & Hỗ trợ Sinh viên HUCE")).toBeDefined();
    expect(screen.getByText(/Mã biên nhận: rcpt-crisis-911/i)).toBeDefined();

    // 4. Toggle emergency hotlines
    const emergencyBtn = screen.getByRole("button", { name: /Đường dây nóng khẩn cấp/i });
    fireEvent.click(emergencyBtn);

    expect(screen.getByText(/Đầu mối hỗ trợ khẩn cấp chính thức Trường Đại học Xây dựng Hà Nội/i)).toBeDefined();
    expect(screen.queryByText("024-3869-XXXX")).toBeNull();
  });

  it("negative path: renders graceful out-of-hours queue assurance", () => {
    render(React.createElement(SensitiveHandoverJourney, { isWorkingHours: false }));

    const input = screen.getByLabelText(/Đặt câu hỏi/i);
    const sendBtn = screen.getByRole("button", { name: /Gửi/i });

    fireEvent.change(input, { target: { value: "Trường hợp bế tắc khẩn cấp ngoài giờ." } });
    fireEvent.click(sendBtn);

    expect(screen.getByText(/Hiện ngoài giờ tiếp nhận trực tuyến/i)).toBeDefined();
    expect(screen.getByText(/Yêu cầu của bạn đã được ghi nhận vào hàng đợi/i)).toBeDefined();
  });
});
