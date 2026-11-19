import { ChatStream, normalizeCitation, type StreamSnapshot } from "./sse";

export interface RestoredMessage {
  id: string;
  sequence: number;
  role: "user" | "assistant";
  content: string;
  createdAt: string;
  final: StreamSnapshot | null;
  clientId?: string;
}
export interface HistoryPage {
  messages: RestoredMessage[];
  nextCursor: string | null;
}
const UUID7 = /^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
function object(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("Invalid history");
  return value as Record<string, unknown>;
}
function invalid(): never { throw new Error("Invalid history"); }

/** Decode an authenticated page atomically. Never infer final status from text. */
export function decodeHistoryPage(value: unknown, conversationId: string, afterSequence = 0): HistoryPage {
  if (!UUID7.test(conversationId)) return invalid();
  const raw = object(value), page = object(raw.page);
  if (!Array.isArray(raw.items) || raw.items.length > 100 || typeof page.has_more !== "boolean") return invalid();
  const cursor = page.next_cursor;
  if ((page.has_more && (typeof cursor !== "string" || !UUID7.test(cursor))) ||
      (!page.has_more && cursor !== null)) return invalid();
  const ids = new Set<string>();
  let lastSequence = afterSequence;
  const messages = raw.items.map((value): RestoredMessage => {
    const item = object(value);
    if (typeof item.id !== "string" || !UUID7.test(item.id) || ids.has(item.id) ||
        item.conversation_id !== conversationId || typeof item.sequence_no !== "number" ||
        !Number.isSafeInteger(item.sequence_no) || item.sequence_no <= lastSequence ||
        typeof item.content !== "string" || item.content.length > 20000 ||
        typeof item.created_at !== "string" || !Number.isFinite(Date.parse(item.created_at)) ||
        !Array.isArray(item.citations) || item.citations.length > 20) return invalid();
    ids.add(item.id); lastSequence = item.sequence_no;
    let final: StreamSnapshot | null = null;
    let content = item.content;
    if (item.sender_type === "USER") {
      if (item.final_result !== undefined || item.citations.length) return invalid();
    } else if (item.sender_type === "ASSISTANT") {
      if (item.final_result !== undefined) {
        const result = object(item.final_result);
        if (result.message_id !== item.id || result.conversation_id !== conversationId ||
            result.content !== item.content || !Array.isArray(result.citations)) return invalid();
        const stream = new ChatStream(conversationId);
        stream.accept({ id: "019a0000-0024-7000-8000-000000000001", event: "message.started",
          data: JSON.stringify({ conversation_id: conversationId, message_id: item.id }) });
        final = stream.accept({ id: "019a0000-0024-7000-8000-000000000002", event: "message.completed",
          data: JSON.stringify(result) });
        stream.finish();
        // Message.citations and final_result must refer to the same immutable map.
        const citations = item.citations.map(normalizeCitation);
        if (JSON.stringify(final.citations.map((entry) => entry.citation)) !== JSON.stringify(citations)) return invalid();
      } else {
        // Legacy or interrupted messages have no verified final metadata.
        // Preserve legacy text while displaying an unverified state separately.
        content = item.content;
      }
    } else return invalid();
    return { id: item.id, sequence: item.sequence_no, role: item.sender_type === "USER" ? "user" : "assistant",
      content, createdAt: item.created_at, final,
      ...(typeof item.client_id === "string" && UUID7.test(item.client_id) ? { clientId: item.client_id } : {}) };
  });
  if (page.has_more && (!messages.length || cursor !== messages[messages.length - 1].id)) return invalid();
  return { messages, nextCursor: page.has_more ? cursor as string : null };
}
