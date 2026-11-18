import React, { useState } from "react";
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup, within } from "@testing-library/react";
import { AppShell } from "../src/components/AppShell";
import { ChatPanel } from "../src/features/chat/ChatPanel";
import { CitationDrawer, type CitationItem } from "../src/features/chat/CitationDrawer";

function GroundedFaqJourney() {
  const [messages, setMessages] = useState<Array<{ id: string; role: "user" | "assistant"; content: string }>>([
    { id: "1", role: "user", content: "Điều kiện xét tốt nghiệp chính quy HUCE gồm những gì?" },
    { id: "2", role: "assistant", content: "Theo quy chế đào tạo chính quy HUCE, sinh viên cần tích luỹ đủ số tín chỉ, điểm CPA >= 2.0 và chứng chỉ chuẩn đầu ra ngoại ngữ." },
  ]);
  const [showCitations, setShowCitations] = useState(false);

  const mockCitations: CitationItem[] = [
    {
      id: "cite-101",
      title: "Quy chế Đào tạo Đại học Chính quy HUCE 2024",
      documentRef: "QC-2024/HUCE-DT",
      quote: "Điều kiện tốt nghiệp: tích lũy đủ học phần, CPA >= 2.0, chứng chỉ ngoại ngữ và GDQP.",
      authority: "Phòng Quản lý Đào tạo HUCE",
      locator: "Điều 28, Khoản 1",
      validityStatus: "active",
      confidence: 0.98,
    },
  ];

  return React.createElement(
    AppShell,
    null,
    React.createElement(
      "div",
      { className: "p-4" },
      React.createElement(ChatPanel, {
        messages,
        onSendMessage: (msg) => setMessages((prev) => [...prev, { id: "3", role: "user", content: msg }]),
      }),
      React.createElement(
        "button",
        {
          onClick: () => setShowCitations(true),
          "aria-label": "Xem nguồn trích dẫn",
          className: "mt-2 px-3 py-1 bg-blue-100 text-blue-700 rounded",
        },
        "Xem nguồn trích dẫn"
      ),
      React.createElement(CitationDrawer, {
        isOpen: showCitations,
        citations: mockCitations,
        onClose: () => setShowCitations(false),
      })
    )
  );
}

describe("Grounded FAQ Browser Journey E2E (TASK-TEST-E2E-001)", () => {
  afterEach(() => {
    cleanup();
  });

  it("completes grounded FAQ journey from query to verified citations", () => {
    render(React.createElement(GroundedFaqJourney));

    // 1. Verify AppShell banner & official online status
    const banner = screen.getByRole("banner");
    expect(within(banner).getByText(/Campus 24\/7/i)).toBeDefined();
    expect(within(banner).getByRole("search", { name: "Tìm nhanh trong Campus" })).toBeDefined();

    // 2. Verify conversation messages
    expect(screen.getByText(/Điều kiện xét tốt nghiệp chính quy HUCE/i)).toBeDefined();
    expect(screen.getByText(/Theo quy chế đào tạo chính quy HUCE/i)).toBeDefined();

    // 3. Open and verify citation drawer
    const citeBtn = screen.getByRole("button", { name: "Xem nguồn trích dẫn" });
    fireEvent.click(citeBtn);

    const dialog = screen.getByRole("dialog");
    expect(dialog).toBeDefined();
    expect(screen.getByText(/Nguồn trích dẫn & Bằng chứng/i)).toBeDefined();
    expect(screen.getByText(/QC-2024\/HUCE-DT/i)).toBeDefined();
    expect(screen.getByText(/Văn bản đang hiệu lực/i)).toBeDefined();

    // Must NOT contain raw percentage
    expect(screen.queryByText(/Độ tin cậy: 98%/i)).toBeNull();

    // 4. Close citation drawer
    const closeBtn = screen.getByRole("button", { name: "Đóng" });
    fireEvent.click(closeBtn);
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("negative path: rejects empty message input in chat composer", () => {
    const handleSend = vi.fn();
    render(React.createElement(ChatPanel, { onSendMessage: handleSend }));

    const input = screen.getByLabelText(/Đặt câu hỏi/i);
    const sendBtn = screen.getByRole("button", { name: /Gửi/i });

    fireEvent.change(input, { target: { value: "   " } });
    fireEvent.click(sendBtn);

    expect(handleSend).not.toHaveBeenCalled();
  });
});
