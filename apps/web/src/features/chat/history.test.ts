import { describe, expect, it } from "vitest";
import { decodeHistoryPage } from "./history";

const conv = "019a0000-0024-7000-8000-000000000010";
const message = "019a0000-0024-7000-8000-000000000011";
function page() {
  return { items: [{ id: message, conversation_id: conv, sequence_no: 2,
    sender_type: "ASSISTANT", content: "Kết quả synthetic", citations: [], created_at: "2026-10-06T00:00:00Z",
    final_result: { conversation_id: conv, message_id: message, status: "completed",
      response_class: "tool_result", content: "Kết quả synthetic", citations: [] } }],
    page: { next_cursor: null as string | null, has_more: false } };
}
describe("durable history decoding", () => {
  it("preserves final IDs, status, class and text across refresh", () => {
    const restored = decodeHistoryPage(page(), conv).messages[0];
    expect(restored.id).toBe(message);
    expect(restored.final).toMatchObject({ messageId: message, finishStatus: "completed", responseClass: "tool_result" });
    expect(restored.content).toBe("Kết quả synthetic");
  });
  it("does not promote legacy assistant text to a verified answer", () => {
    const value = page();
    delete (value.items[0] as { final_result?: unknown }).final_result;
    expect(decodeHistoryPage(value, conv).messages[0]).toMatchObject({ final: null, content: "Kết quả synthetic" });
  });
  it.each(["conversation_id", "message_id", "content"])("rejects mismatched persisted %s", (field) => {
    const value = page();
    (value.items[0].final_result as Record<string, unknown>)[field] = "tampered";
    expect(() => decodeHistoryPage(value, conv)).toThrow();
  });
  it("rejects invalid final status/class and citation-free grounded answers", () => {
    const value = page();
    value.items[0].final_result.status = "answered";
    value.items[0].final_result.response_class = "action_result";
    expect(() => decodeHistoryPage(value, conv)).toThrow();
    value.items[0].final_result.response_class = "grounded_answer";
    expect(() => decodeHistoryPage(value, conv)).toThrow();
  });
  it("rejects cross-conversation rows, duplicates and replayed pages", () => {
    const value = page();
    expect(() => decodeHistoryPage(value, message)).toThrow();
    expect(() => decodeHistoryPage(value, conv, 2)).toThrow();
    value.items.push(value.items[0]);
    expect(() => decodeHistoryPage(value, conv)).toThrow();
  });
  it("binds pagination cursor to the final item and requires progress", () => {
    const value = page(); value.page.has_more = true;
    value.page.next_cursor = conv;
    expect(() => decodeHistoryPage(value, conv)).toThrow();
    value.page.next_cursor = message;
    expect(decodeHistoryPage(value, conv).nextCursor).toBe(message);
    value.items = [];
    expect(() => decodeHistoryPage(value, conv)).toThrow();
  });
});
