import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { ChatPanel, type ChatMessage } from "./ChatPanel";

const SERVER_ID = "01a17d81-7b84-7918-add2-763596212c5f";
const stored: ChatMessage[] = [
  { id: "01a17d81-7b65-7d9b-8c31-81df8580080d", role: "user", content: "Cảnh báo học tập?" },
  { id: SERVER_ID, role: "assistant", status: "success", content: "Có căn cứ." },
];

describe("rating an answer in the chat", () => {
  afterEach(() => cleanup());

  it("shows the rating buttons for an answer the server stored and sends the rating", async () => {
    const onFeedbackSubmit = vi.fn().mockResolvedValue(undefined);
    render(<ChatPanel messages={stored} onFeedbackSubmit={onFeedbackSubmit} />);
    fireEvent.click(screen.getByRole("button", { name: "Chưa hữu ích" }));
    await waitFor(() => expect(onFeedbackSubmit).toHaveBeenCalledWith(SERVER_ID, "not_helpful"));
  });

  it("does not offer a rating for an answer that is still a local placeholder", () => {
    render(<ChatPanel messages={[stored[0], { ...stored[1], id: "assistant-3" }]} onFeedbackSubmit={vi.fn()} />);
    expect(screen.queryByRole("button", { name: "Chưa hữu ích" })).toBeNull();
  });

  it("has no rating buttons when the page gives no handler", () => {
    render(<ChatPanel messages={stored} />);
    expect(screen.queryByRole("button", { name: "Hữu ích" })).toBeNull();
  });
});
