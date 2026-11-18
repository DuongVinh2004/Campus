import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ChatStream, type SseFrame } from "./sse";
import { ChatPanel } from "./ChatPanel";

const ID = "01923456-789a-7def-8123-456789abcdef";
let seq = 0;
function event(name: string, data: unknown): SseFrame {
  return { id: `01923456-789a-7def-8123-${(++seq).toString(16).padStart(12, "0")}`, event: name, data: JSON.stringify(data) };
}
function started() {
  const stream = new ChatStream(ID);
  stream.accept(event("message.started", { conversation_id: ID, message_id: ID }));
  return stream;
}
const progress = { version: 1, run_id: ID, phase: "verifying", source_count: 2,
  tasks: [{ id: "T1", role: "research", status: "succeeded" }, { id: "T2", role: "verifier", status: "running" }] };

describe("multi-agent status binding", () => {
  it("shows verified progress without publishing an answer or source citations", () => {
    const stream = started();
    const snapshot = stream.accept(event("agent.status", progress));
    expect(snapshot.text).toBe(""); expect(snapshot.citations).toEqual([]); expect(stream.terminal).toBe(false);
    render(<ChatPanel messages={[{ id: ID, role: "assistant", content: "", status: "streaming", agentProgress: snapshot.agentProgress }]} />);
    expect(screen.getByText("Đang kiểm chứng nguồn và điều kiện")).toBeTruthy();
    expect(screen.getByText("1/2 phần đã tra cứu · 2 nguồn đã đọc")).toBeTruthy();
  });
  it.each([
    { ...progress, raw_prompt: "hidden" },
    { ...progress, tasks: [progress.tasks[0], progress.tasks[0]] },
    { ...progress, source_count: 100 },
    { ...progress, tasks: [{ id: "T1", role: "executor", status: "succeeded" }] },
  ])("rejects invalid/extra status payloads", (data) => {
    expect(() => started().accept(event("agent.status", data))).toThrow();
  });
  it("distinguishes service failure from missing-source refusal and restores it as terminal", () => {
    const stream = started();
    const snapshot = stream.accept(event("message.completed", { conversation_id: ID, message_id: ID,
      status: "abstained", response_class: "system_error", content: "Dịch vụ tra cứu nguồn phản hồi quá chậm.", citations: [] }));
    expect(snapshot.phase).toBe("failed"); expect(snapshot.text).toContain("quá chậm"); expect(stream.finish().responseClass).toBe("system_error");
  });
});
