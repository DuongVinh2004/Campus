import React from "react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { LanguageProvider } from "../../lib/i18n";
import { ChatPanel, type ChatMessage } from "./ChatPanel";

beforeEach(() => { document.cookie = "lang=en; path=/"; });
afterEach(() => { cleanup(); document.cookie = "lang=; path=/; max-age=0"; });

const messages: ChatMessage[] = [
  { id: "m1", role: "user", content: "Điều kiện xét học bổng là gì?" },
  { id: "m2", role: "assistant", content: "Theo Quy chế [1], cần điểm rèn luyện từ loại Khá.", citations: [{ id: "c1", index: 1, title: "Quy chế Đào tạo 2024" }] },
];

describe("ChatPanel chrome in English", () => {
  it("translates the header, the sender labels, the composer and the citation controls; the conversation itself stays as written", () => {
    render(<LanguageProvider><ChatPanel messages={messages} /></LanguageProvider>);
    expect(screen.getByText("Campus 24/7 AI assistant")).toBeInTheDocument();
    expect(screen.getByText("You")).toBeInTheDocument();
    expect(screen.getByText("AI assistant")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Ask Campus 24/7")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Send" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "See cited source [1]: Quy chế Đào tạo 2024" })).toBeInTheDocument();
    expect(screen.getByText("Campus 24/7 AI can make mistakes. Please check important information.")).toBeInTheDocument();
    expect(screen.getByText(/Điều kiện xét học bổng là gì\?/)).toBeInTheDocument();
  });
});
