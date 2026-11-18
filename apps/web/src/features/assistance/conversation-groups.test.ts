import { describe, expect, it } from "vitest";
import type { ConversationSummary } from "@/lib/assistant-state-service";
import { conversationTooltip, groupConversations } from "./conversation-groups";

const now = new Date(2026, 9, 20, 12);
const item = (id: string, days: number, pinned = false) => ({ id, title: "Điều kiện học bổng?", pinned,
  created_at: new Date(2026, 9, 20 - days, 8, 30).toISOString() } as ConversationSummary);

describe("history chronology", () => {
  it("distinguishes repeated questions by date groups while keeping titles intact", () => {
    const values = [item("old", 30), item("today", 0), item("yesterday", 1), item("recent", 4)];
    const groups = groupConversations(values, now);
    expect(groups.slice(0, 3).map(group => group.label)).toEqual(["Hôm nay", "Hôm qua", "7 ngày qua"]);
    expect(groups.flatMap(group => group.items).map(value => value.id)).toEqual(["today", "yesterday", "recent", "old"]);
    expect(values[0].id).toBe("old");
    expect(groups.flatMap(group => group.items).every(value => value.title === "Điều kiện học bổng?")).toBe(true);
  });
  it("keeps pins ahead of chronology", () => {
    const groups = groupConversations([item("new", 0), item("pinned", 30, true)], now);
    expect(groups[0].label).toBe("Đã ghim");
    expect(groups[0].items[0].id).toBe("pinned");
  });
  it("provides the full title and timestamp for a truncated row", () => {
    const value = { ...item("one", 0), title: "Câu hỏi rất dài cần giữ nguyên nội dung" };
    expect(conversationTooltip(value)).toContain(value.title);
    expect(conversationTooltip(value)).toMatch(/Tạo lúc.*8:30|Tạo lúc.*08:30/);
  });
  it("handles missing legacy dates without inventing a timestamp", () => {
    const value = { ...item("legacy", 0), created_at: "invalid" };
    expect(groupConversations([value], now)[0].label).toBe("Trước đây");
    expect(conversationTooltip(value)).toBe(value.title);
  });
});
