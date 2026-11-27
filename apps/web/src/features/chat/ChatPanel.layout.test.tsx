import React from "react";
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen, within } from "@testing-library/react";
import { ChatPanel, type ChatMessage } from "./ChatPanel";

// Exactly what the API's answer layout (application/conversation/answer_layout.py) sends for a two-part question.
const LAID_OUT = [
  "> Nguồn áp dụng cho K69.",
  "",
  "### Phải đăng nhập vào hệ thống nào",
  "",
  "Đăng nhập sinhvien.huce.edu.vn để tự đánh giá. [CIT-001]",
  "",
  "### Được dùng để xét những việc gì",
  "",
  "- Học phí **580.500 đồng/tín chỉ**. [CIT-001]",
  "- Hạn nộp **20/10/2026**. [CIT-002]",
  "",
  "> Chưa đủ căn cứ cho phần còn lại.",
  "",
  "Gợi ý hỏi tiếp:",
  "- Học bổng",
].join("\n");

const messages: ChatMessage[] = [
  { id: "q", role: "user", content: "Câu hỏi hai ý" },
  { id: "a", role: "assistant", status: "success", responseClass: "partial_answer", content: LAID_OUT },
];

describe("ChatPanel shows a laid-out grounded answer as structure, not one paragraph", () => {
  afterEach(() => cleanup());

  it("renders sections, a list, bold values, quoted notes and citation numbers", () => {
    const { container } = render(<ChatPanel messages={messages} />);
    const headings = screen.getAllByRole("heading", { level: 3 }).map(h => h.textContent);
    expect(headings).toEqual(["Phải đăng nhập vào hệ thống nào", "Được dùng để xét những việc gì"]);
    const items = within(container.querySelector("ul")!).getAllByRole("listitem").map(li => li.textContent);
    expect(items).toEqual(["Học phí 580.500 đồng/tín chỉ. [1]", "Hạn nộp 20/10/2026. [2]"]);
    expect([...container.querySelectorAll("strong")].map(s => s.textContent)).toEqual(["580.500 đồng/tín chỉ", "20/10/2026"]);
    expect([...container.querySelectorAll("blockquote")].map(q => q.textContent?.trim()))
      .toEqual(["Nguồn áp dụng cho K69.", "Chưa đủ căn cứ cho phần còn lại."]);
    // The follow-up block still becomes buttons, not a third item of the answer's list.
    expect(screen.getByRole("button", { name: /Học bổng/ })).toBeTruthy();
    expect(container.querySelectorAll("ul li")).toHaveLength(2);
  });
});
