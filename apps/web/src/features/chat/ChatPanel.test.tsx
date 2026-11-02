import React from "react";
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { ChatPanel, type ChatMessage } from "./ChatPanel";

describe("ChatPanel Component (TASK-WEB-CHAT-003)", () => {
  afterEach(() => {
    cleanup();
  });

  it("shows cited public knowledge without fabricating an account, history or procedural links", () => {
    render(<ChatPanel messages={[{ id: "public-answer", role: "assistant", status: "success",
      content: "Xin bảng điểm qua Một cửa. Phòng tự học ở tầng 2 thư viện. [CIT-001]",
      citations: [{ id: "source", index: 1, title: "Sổ tay HUCE" }] }]} />);
    expect(screen.queryByText("HUCE Demo")).toBeNull();
    expect(screen.queryByText("SV240000")).toBeNull();
    expect(screen.queryByText("Hội thoại gần đây")).toBeNull();
    expect(screen.queryByRole("link", { name: /Nộp hồ sơ Một cửa/ })).toBeNull();
    expect(screen.queryByRole("link", { name: /Thông tin thư viện/ })).toBeNull();
    expect(screen.getByRole("button", { name: /Xem nguồn trích dẫn \[1\]: Sổ tay HUCE/ })).toBeDefined();
    expect(screen.getByText(/Xin bảng điểm qua Một cửa/).textContent).toContain("[1]");
    expect(screen.getByText(/Xin bảng điểm qua Một cửa/).textContent).not.toContain("CIT-");
  });

  it("renders assistant workspace with AI disclosure, ordered turns and transcript hierarchy", () => {
    const messages: ChatMessage[] = [
      { id: "msg-1", role: "user", content: "Điều kiện xét học bổng khuyến khích học tập là gì?" },
      {
        id: "msg-2",
        role: "assistant",
        content: "Theo Quy chế Đào tạo [1], sinh viên cần đạt điểm rèn luyện từ loại Khá trở lên.",
        citations: [{ id: "c1", index: 1, title: "Quy chế Đào tạo 2024" }],
      },
    ];

    render(<ChatPanel messages={messages} />);

    // AI Notice header
    expect(screen.getByText(/Trợ lý AI Campus 24\/7/i)).toBeDefined();
    expect(screen.getByText(/Cổng thông tin & Trợ lý học vụ số — Trường Đại học Xây dựng Hà Nội/i)).toBeDefined();

    // Ordered turns
    expect(screen.getByText("Bạn")).toBeDefined();
    expect(screen.getAllByText(/Trợ lý AI/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/Theo Quy chế Đào tạo/i)).toBeDefined();
  });

  it("supports keyboard flow (Enter sends, Shift+Enter keeps newline) without DOM query", () => {
    const handleSend = vi.fn();
    render(<ChatPanel onSendMessage={handleSend} />);

    const textarea = screen.getByLabelText(/Đặt câu hỏi/i);

    // Shift + Enter should NOT send
    fireEvent.change(textarea, { target: { value: "Dòng 1" } });
    fireEvent.keyDown(textarea, { key: "Enter", shiftKey: true });
    expect(handleSend).not.toHaveBeenCalled();

    // Plain Enter should send
    fireEvent.keyDown(textarea, { key: "Enter", shiftKey: false });
    expect(handleSend).toHaveBeenCalledWith("Dòng 1");
  });

  it("handles streaming state with stop button and active live region", () => {
    const handleStop = vi.fn();
    render(<ChatPanel isStreaming={true} onStopStreaming={handleStop} />);

    // Live region announcing generation
    expect(screen.getByText(/Trợ lý đang trả lời/i)).toBeDefined();

    // Stop generation button
    const stopBtn = screen.getByRole("button", { name: /Dừng trả lời/i });
    expect(stopBtn).toBeDefined();
    fireEvent.click(stopBtn);
    expect(handleStop).toHaveBeenCalled();
  });

  it("provides calm recovery with retry button on failed messages", () => {
    const handleRetry = vi.fn();
    const messages: ChatMessage[] = [
      {
        id: "msg-err-1",
        role: "assistant",
        content: "Không thể kết nối đến máy chủ AI để xử lý câu hỏi.",
        status: "failed",
      },
    ];

    render(<ChatPanel messages={messages} onRetry={handleRetry} />);

    expect(screen.getByText(/Không thể kết nối/i)).toBeDefined();
    const retryBtn = screen.getByRole("button", { name: /Thử lại/i });
    expect(retryBtn).toBeDefined();

    fireEvent.click(retryBtn);
    expect(handleRetry).toHaveBeenCalledWith("msg-err-1");
  });

  it("renders abstention state with guidance to human support without fabricating answers", () => {
    const handleHandover = vi.fn();
    const messages: ChatMessage[] = [
      {
        id: "msg-abs-1",
        role: "assistant",
        content: "Hệ thống chưa tìm thấy văn bản quy định chính thức cho trường hợp này.",
        status: "abstained",
      },
    ];

    render(<ChatPanel messages={messages} onHandover={handleHandover} />);

    expect(screen.getByText(/Hệ thống chưa tìm thấy văn bản quy định/i)).toBeDefined();
    const handoverBtn = screen.getByRole("button", { name: /Chuyển cán bộ/i });
    expect(handoverBtn).toBeDefined();

    fireEvent.click(handoverBtn);
    expect(handleHandover).toHaveBeenCalled();
  });

  it("does not infer procedural actions from unstructured AI text", () => {
    const messages: ChatMessage[] = [
      {
        id: "msg-proc-1",
        role: "assistant",
        content: "Sinh viên có thể xin cấp bảng điểm tạm thời tại bộ phận Một cửa số của trường.",
      },
    ];

    render(<ChatPanel messages={messages} />);

    expect(screen.getByText(messages[0].content)).toBeDefined();
    expect(screen.queryByText(/Gợi ý hành động/i)).toBeNull();
    expect(screen.queryByRole("link", { name: /Nộp hồ sơ Một cửa trực tuyến/i })).toBeNull();
  });

  it("does not invent a One-door scholarship application from general eligibility rules", () => {
    render(<ChatPanel messages={[{ id: "scholarship", role: "assistant", status: "success",
      content: "Khoa xét học bổng theo kết quả học tập, rèn luyện và số suất được phân bổ." }]} />);
    expect(screen.queryByRole("link", { name: /Nộp hồ sơ Một cửa/ })).toBeNull();
  });

  it("labels provisional text and keeps citations, actions and feedback unavailable", () => {
    render(<ChatPanel messages={[{
      id: "provisional", role: "assistant", status: "streaming", content: "Thủ tục xin cấp bảng điểm",
      citations: [{ id: "provisional-citation", index: 1, title: "Provisional source" }],
    }]} />);
    expect(screen.getByText(/Nội dung tạm/i)).toBeDefined();
    expect(screen.queryByText("Provisional source")).toBeNull();
    expect(screen.queryByText(/Gợi ý hành động/i)).toBeNull();
    expect(screen.queryByRole("button", { name: /Hữu ích/i })).toBeNull();
  });

  it("shows explicit unknown and stopped states without action suggestions", () => {
    render(<ChatPanel messages={[
      { id: "unknown", role: "assistant", status: "unknown", content: "Chưa xác nhận thủ tục bảng điểm" },
      { id: "stopped", role: "assistant", status: "stopped", content: "Câu trả lời bảng điểm đã dừng" },
    ]} />);
    expect(screen.getByText(/UNKNOWN/i)).toBeDefined();
    expect(screen.getByText(/Đã dừng — chưa xác nhận/i)).toBeDefined();
    expect(screen.queryByText(/Gợi ý hành động/i)).toBeNull();
  });
});

