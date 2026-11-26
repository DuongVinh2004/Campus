import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { ChatPanel, type ChatMessage } from "./ChatPanel";

const flags = vi.hoisted(() => ({ on: false }));
vi.mock("../../lib/features", () => ({ FeatureGate: ({ children }: { children: React.ReactNode }) => (flags.on ? <>{children}</> : null) }));
vi.mock("./ChatSuggestionCards", () => ({ ChatSuggestionCards: ({ text }: { text: string }) => (flags.on ? <div data-testid="cards">{text}</div> : null) }));
vi.mock("./AnswerEvidence", () => ({ AnswerEvidence: ({ messageId }: { messageId: string }) => <div data-testid="evidence">{messageId}</div> }));
vi.mock("../input/ImageInput", () => ({ ImageInput: () => <div data-testid="image-input" /> }));
vi.mock("../input/ReadAloud", () => ({ ReadAloud: ({ text }: { text: string }) => <button type="button">Đọc to: {text}</button> }));

const messages: ChatMessage[] = [
  { id: "u1", role: "user", content: "Câu hỏi cũ về học phí" },
  { id: "a1", role: "assistant", status: "success", content: "Trả lời cũ." },
  { id: "u2", role: "user", content: "Em nghỉ 25 tiết có sao không?" },
  { id: "a2", role: "assistant", status: "success", content: "Trả lời mới." },
];

afterEach(() => cleanup());

describe("F-series pieces mounted in the chat", () => {
  it("shows nothing extra while the feature flags are off", () => {
    flags.on = false;
    render(<ChatPanel messages={messages} />);
    expect(screen.queryByTestId("cards")).toBeNull();
    expect(screen.queryByTestId("image-input")).toBeNull();
    expect(screen.queryByRole("button", { name: /Đọc to/ })).toBeNull();
  });

  it("puts cards only under the latest question, read-aloud on each answer and the image input in the composer", () => {
    flags.on = true;
    render(<ChatPanel messages={messages} />);
    const cards = screen.getAllByTestId("cards");
    expect(cards).toHaveLength(1);
    expect(cards[0].textContent).toBe("Em nghỉ 25 tiết có sao không?");
    expect(screen.getAllByRole("button", { name: /Đọc to/ })).toHaveLength(2);
    expect(screen.getByTestId("image-input")).toBeTruthy();
  });

  it("hides the image input while the composer is disabled", () => {
    flags.on = true;
    render(<ChatPanel messages={messages} disabled />);
    expect(screen.queryByTestId("image-input")).toBeNull();
  });

  it("shows the evidence line only for answers the server stored, in a known conversation, with the flag on", () => {
    const stored: ChatMessage[] = [{ id: "01a17d81-7b84-7918-add2-763596212c5f", role: "assistant", status: "success", content: "Có căn cứ." }, { id: "assistant-2", role: "assistant", status: "success", content: "Cục bộ." }];
    flags.on = true;
    render(<ChatPanel messages={stored} conversationId="c1" />);
    expect(screen.getAllByTestId("evidence").map(n => n.textContent)).toEqual(["01a17d81-7b84-7918-add2-763596212c5f"]);
    cleanup();
    render(<ChatPanel messages={stored} />);
    expect(screen.queryByTestId("evidence")).toBeNull();
    cleanup();
    flags.on = false;
    render(<ChatPanel messages={stored} conversationId="c1" />);
    expect(screen.queryByTestId("evidence")).toBeNull();
  });
});
