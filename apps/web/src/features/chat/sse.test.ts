import { describe, expect, it } from "vitest";
import { ChatStream, ChatStreamError, SseParser, FAILED_GUIDANCE, DEPENDENCY_GUIDANCE, type SseFrame } from "./sse";

// Oracle: approved stream-event.schema.json / API_CONVENTIONS 8.1, not the old UI.
const CONVERSATION = "01923456-789a-7def-8123-456789abcdef";
const MESSAGE = "01923456-789a-7def-8123-456789abcdea";
let eventNumber = 0;
function frame(event: string, data: unknown): SseFrame {
  return { id: `01923456-789a-7def-8123-${(++eventNumber).toString(16).padStart(12, "0")}`, event, data: JSON.stringify(data) };
}
const started = () => frame("message.started", { conversation_id: CONVERSATION, message_id: MESSAGE });
const completed = (status = "answered", content = "Final verified read result") => frame("message.completed", {
  conversation_id: CONVERSATION, message_id: MESSAGE, status,
  response_class: status === "abstained" ? "safe_refusal" : "tool_result", content, citations: [],
});
const wire = (value: SseFrame) => `id: ${value.id}\nevent: ${value.event}\ndata: ${value.data}\n\n`;

describe("SSE framing", () => {
  it.each(["\n", "\r\n", "\r"])("parses fragmented boundaries with %j and multiline data", (newline) => {
    const message = started();
    const raw = `\uFEFF: heartbeat${newline}id: ${message.id}${newline}event: ${message.event}${newline}` +
      `unknown-field: ignored${newline}data: {${newline}data: "conversation_id": "${CONVERSATION}",${newline}` +
      `data: "message_id": "${MESSAGE}"}${newline}${newline}`;
    const parser = new SseParser();
    const parsed: SseFrame[] = [];
    for (const character of raw) parsed.push(...parser.push(character));
    parsed.push(...parser.finish());
    expect(parsed).toHaveLength(1);
    const stream = new ChatStream(CONVERSATION);
    expect(stream.accept(parsed[0]).messageId).toBe(MESSAGE);
  });

  it("requires blank lines and discards unfinished EOF records", () => {
    const parser = new SseParser();
    expect(parser.push(wire(started()).slice(0, -1))).toEqual([]);
    expect(parser.finish()).toEqual([]);
  });

  it("joins several complete events in one chunk without merging their payloads", () => {
    const parser = new SseParser();
    expect(parser.push(wire(started()) + wire(completed()))).toHaveLength(2);
  });

  it("handles UTF-8 split inside Vietnamese characters using incremental decoding", () => {
    const bytes = new TextEncoder().encode(wire(completed("answered", "Lịch học tiếng Việt")));
    const decoder = new TextDecoder("utf-8", { fatal: true });
    const parser = new SseParser();
    const parsed: SseFrame[] = [];
    bytes.forEach((byte) => parsed.push(...parser.push(decoder.decode(new Uint8Array([byte]), { stream: true }))));
    parsed.push(...parser.push(decoder.decode()), ...parser.finish());
    expect(JSON.parse(parsed[0].data).content).toBe("Lịch học tiếng Việt");
  });

  it("bounds incomplete event data instead of accumulating unbounded memory", () => {
    expect(() => new SseParser().push("data: " + "x".repeat(128001))).toThrow(ChatStreamError);
  });
});

describe("validated streaming lifecycle", () => {
  it("replaces provisional text with authoritative final content", () => {
    const stream = new ChatStream(CONVERSATION);
    stream.accept(started());
    expect(stream.accept(frame("message.delta", { seq: 1, delta: "Provisional text" })).phase).toBe("streaming");
    expect(stream.accept(completed()).text).toBe("Final verified read result");
    expect(stream.finish().phase).toBe("completed");
  });

  it("withdraws rejected provisional text on abstention", () => {
    const stream = new ChatStream(CONVERSATION);
    stream.accept(started());
    stream.accept(frame("message.delta", { seq: 1, delta: "REJECTED_SYNTHETIC_DRAFT" }));
    const final = stream.accept(completed("abstained", "Chưa đủ căn cứ; vui lòng làm rõ câu hỏi."));
    expect(final.phase).toBe("abstained");
    expect(final.text).not.toContain("REJECTED_SYNTHETIC_DRAFT");
    expect(final.citations).toEqual([]);
  });

  it("uses direct safe problems and clears provisional text after terminal failure", () => {
    const stream = new ChatStream(CONVERSATION, MESSAGE);
    stream.accept(started());
    stream.accept(frame("message.delta", { seq: 1, delta: "Provisional answer" }));
    const failed = stream.accept(frame("message.failed", {
      type: "https://campus247.example/problems/dependency-unavailable", status: 503,
      code: "DEPENDENCY_UNAVAILABLE", title: "Safe title", detail: "Safe guidance",
      instance: `urn:request:${MESSAGE}`, request_id: MESSAGE, retryable: false,
    }));
    expect(failed.phase).toBe("failed"); expect(failed.text).toBe(DEPENDENCY_GUIDANCE);
    expect(failed.citations).toEqual([]); expect(stream.terminal).toBe(true);
  });

  it("ignores duplicate/reordered deltas and events", () => {
    const stream = new ChatStream(CONVERSATION);
    stream.accept(started());
    const delta = frame("message.delta", { seq: 2, delta: "kept" });
    stream.accept(delta); stream.accept(delta);
    stream.accept(frame("message.delta", { seq: 1, delta: "obsolete" }));
    stream.accept(frame("message.delta", { seq: 2, delta: "duplicate-sequence" }));
    expect(stream.snapshot.text).toBe("kept");
  });

  it.each(["message.error", "message.abstained", "future.event"])("maps unknown event %s to explicit UNKNOWN", (event) => {
    const stream = new ChatStream(CONVERSATION);
    stream.accept(started());
    expect(() => stream.accept(frame(event, {}))).toThrow("UNKNOWN");
  });

  it.each(["future-status", "toString", "__proto__"])("fails safely on unknown finish status %s", (status) => {
    const stream = new ChatStream(CONVERSATION); stream.accept(started());
    expect(() => stream.accept(completed(status))).toThrow("UNKNOWN");
  });

  it("does not accept EOF, wrong message ID, malformed JSON or schema-incompatible completion as success", () => {
    const incomplete = new ChatStream(CONVERSATION); incomplete.accept(started());
    expect(() => incomplete.finish()).toThrow(ChatStreamError);
    const foreign = new ChatStream(CONVERSATION); foreign.accept(started());
    expect(() => foreign.accept(frame("message.completed", {
      ...JSON.parse(completed().data), message_id: CONVERSATION,
    }))).toThrow(ChatStreamError);
    const malformed = new ChatStream(CONVERSATION); malformed.accept(started());
    expect(() => malformed.accept({ ...frame("message.delta", {}), data: "{broken" })).toThrow(ChatStreamError);
    const invalid = new ChatStream(CONVERSATION); invalid.accept(started());
    expect(() => invalid.accept(frame("message.completed", {
      ...JSON.parse(completed().data), response_class: "grounded_answer", citations: [],
    }))).toThrow(ChatStreamError);
  });

  it("ignores unknown response fields and trailing events after terminal", () => {
    const stream = new ChatStream(CONVERSATION); stream.accept(started());
    stream.accept(frame("message.completed", { ...JSON.parse(completed().data), future_field: 1 }));
    expect(stream.accept(frame("message.failed", {})).text).toBe("Final verified read result");
  });

  it("validates citation mapping but enables citations only after final completion", () => {
    const mapping = { turn_citation_id: "CIT-001", citation: {
      citation_id: MESSAGE, source_id: CONVERSATION, document_version_id: CONVERSATION,
      source_title: "Synthetic source", canonical_uri: "synthetic://stream/source", version_label: "v1",
      source_status: "SYNTHETIC", locator: { section_path: "Section 1" }, quote: "Synthetic quote",
    } };
    const stream = new ChatStream(CONVERSATION); stream.accept(started());
    stream.accept(frame("citation.added", { message_id: MESSAGE, citation: mapping }));
    expect(stream.snapshot.citations).toEqual([]);
    const final = stream.accept(frame("message.completed", {
      ...JSON.parse(completed().data), content: "Supported answer [CIT-001]", response_class: "grounded_answer", citations: [mapping],
    }));
    expect(final.citations[0].turn_citation_id).toBe("CIT-001");
    expect(final.citations[0].citation.citation_id).toBe(MESSAGE);
  });

  it.each(["future-class", "toString", "__proto__"])("reports unknown response class %s", (responseClass) => {
    const stream = new ChatStream(CONVERSATION); stream.accept(started());
    expect(() => stream.accept(frame("message.completed", {
      ...JSON.parse(completed().data), response_class: responseClass,
    }))).toThrow("UNKNOWN");
  });

  it("rejects a problem correlated to a different request", () => {
    const stream = new ChatStream(CONVERSATION, MESSAGE); stream.accept(started());
    expect(() => stream.accept(frame("message.failed", {
      type: "https://campus247.example/problems/dependency-unavailable", status: 503,
      code: "DEPENDENCY_UNAVAILABLE", title: "Safe title", detail: "Safe guidance",
      instance: `urn:request:${CONVERSATION}`, request_id: CONVERSATION, retryable: false,
    }))).toThrow(ChatStreamError);
  });

  it("explains dependency failures without reflecting exception text or declaring missing sources", () => {
    const stream = new ChatStream(CONVERSATION, MESSAGE); stream.accept(started());
    const result = stream.accept(frame("message.failed", {
      type: "https://campus247.example/problems/dependency-unavailable", status: 503,
      code: "DEPENDENCY_UNAVAILABLE", title: "Safe title", detail: "UNTRUSTED_EXCEPTION_TEXT",
      instance: `urn:request:${MESSAGE}`, request_id: MESSAGE, retryable: false,
    }));
    expect(result.phase).toBe("failed");
    expect(result.problemCode).toBe("DEPENDENCY_UNAVAILABLE");
    expect(result.text).toBe(DEPENDENCY_GUIDANCE);
    expect(result.text).not.toContain("UNTRUSTED_EXCEPTION_TEXT");
    expect(result.citations).toEqual([]);
  });
});
