import type { ConversationSummary } from "@/lib/assistant-state-service";

export function conversationDate(value: ConversationSummary) {
  const parsed = new Date(value.created_at);
  return Number.isFinite(parsed.getTime()) ? parsed : null;
}

export function conversationTooltip(value: ConversationSummary) {
  const date = conversationDate(value);
  return `${value.title}${date ? `\nTạo lúc ${date.toLocaleString("vi-VN", { dateStyle: "short", timeStyle: "short" })}` : ""}`;
}

export function groupConversations(values: ConversationSummary[], now = new Date()) {
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const groups = new Map<string, ConversationSummary[]>();
  for (const value of [...values].sort((a, b) => Number(b.pinned) - Number(a.pinned)
    || (conversationDate(b)?.getTime() ?? 0) - (conversationDate(a)?.getTime() ?? 0) || b.id.localeCompare(a.id))) {
    const date = conversationDate(value);
    const day = date ? new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime() : null;
    const age = day === null ? null : Math.round((today - day) / 86_400_000);
    const label = value.pinned ? "Đã ghim" : age === 0 ? "Hôm nay" : age === 1 ? "Hôm qua"
      : age !== null && age > 1 && age < 7 ? "7 ngày qua" : date ? date.toLocaleDateString("vi-VN", { month: "long", year: "numeric" }) : "Trước đây";
    if (!groups.has(label)) groups.set(label, []);
    groups.get(label)!.push(value);
  }
  return [...groups].map(([label, items]) => ({ label, items }));
}
