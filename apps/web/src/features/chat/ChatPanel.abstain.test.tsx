import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { ChatPanel, type ChatMessage } from "./ChatPanel";

const abstained: ChatMessage[] = [
  { id: "q", role: "user", content: "Học phí K67?" },
  { id: "a", role: "assistant", status: "abstained", responseClass: "insufficient_evidence", content: "Mình chưa tìm thấy nguồn phù hợp để trả lời câu hỏi này." },
];

describe("ChatPanel without a grounded answer", () => {
  afterEach(() => cleanup());

  it("offers concrete next steps instead of a dead end", () => {
    render(<ChatPanel messages={abstained} />);
    const help = screen.getByRole("note");
    expect(help.textContent).toContain("Hỏi cụ thể hơn");
    expect(help.textContent).toContain("Phòng Đào tạo");
  });

  it("does not show the help for a clarification request or a grounded answer", () => {
    render(<ChatPanel messages={[abstained[0], { ...abstained[1], responseClass: "clarification_request" }]} />);
    expect(screen.queryByRole("note")).toBeNull();
    cleanup();
    render(<ChatPanel messages={[abstained[0], { id: "ok", role: "assistant", status: "success", content: "Có căn cứ." }]} />);
    expect(screen.queryByRole("note")).toBeNull();
  });
});
