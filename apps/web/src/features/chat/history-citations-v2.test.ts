import { describe, expect, it } from "vitest";
import { decodeHistoryPage } from "./history";
import { ChatStream, type SseFrame } from "./sse";

const conv = "019a0000-0024-7000-8000-000000000010";
const message = "019a0000-0024-7000-8000-000000000011";
function serverCitation() {
  return {
    citation_id: "01a1973a-6cca-7089-82ae-21eabfd24c67", source_id: "253eb450-c57a-79a7-84a4-b0d85e12de1c",
    document_version_id: "01a17057-0cbd-7504-a63c-b4c0ca345694", chunk_id: "01a17057-0d62-76af-8733-fb90d72a2762",
    source_title: "Quy chế đào tạo HUCE — Quyết định 1486 ngày 06/11/2023",
    canonical_uri: "https://drive.google.com/file/d/fixture/preview?",
    version_label: "verified-effective-01a17057-0cbd-7504-a63c-b4c0ca345694", source_status: "CURRENT",
    locator: { section_path: "Quy chế 1486 — Điều 8, khoản 2 — PDF 10", page_start: 10, page_end: 10 },
    quote: "tổ chức các lớp học phương thức trực tuyến khi đáp ứng …",
    release_id: "01a172fe-1822-7679-a515-335e063dd1fa", release_generation: 27,
    evidence_sha256: "a".repeat(64), unit_id: "0123456789abcdef".repeat(4),
  };
}
function historyPage() {
  const content = "Câu trả lời có căn cứ [CIT-001]";
  return { items: [{ id: message, conversation_id: conv, sequence_no: 2, sender_type: "ASSISTANT",
    content, citations: [serverCitation()], created_at: "2026-11-01T00:00:00Z",
    final_result: { conversation_id: conv, message_id: message, status: "answered", response_class: "grounded_answer",
      content, citations: [{ turn_citation_id: "CIT-001", citation: serverCitation() }] } }],
    page: { next_cursor: null, has_more: false } };
}
function frame(event: string, data: unknown, sequence: number): SseFrame {
  return { id: `019a0000-0024-7000-8000-${sequence.toString().padStart(12, "0")}`, event, data: JSON.stringify(data) };
}
function stream() {
  const result = new ChatStream(conv);
  result.accept(frame("message.started", { conversation_id: conv, message_id: message }, 1));
  return result;
}

describe("v2 history citation normalization", () => {
  it("restores server-ordered citations and preserves unit_id in final citations", () => {
    const restored = decodeHistoryPage(historyPage(), conv).messages[0];
    expect(restored.final?.phase).toBe("completed");
    expect(restored.final?.citations).toEqual([{ turn_citation_id: "CIT-001", citation: serverCitation() }]);
  });

  it("ignores key order and additive server fields on both sides", () => {
    const page = historyPage(), item = page.items[0];
    const citation = serverCitation();
    item.citations = [Object.assign(Object.fromEntries(Object.entries(citation).reverse()) as typeof citation, {
      locator: { page_end: 10, page_start: 10, section_path: citation.locator.section_path },
      future_metadata: { revision: 2 } })];
    Object.assign(item.final_result.citations[0].citation, { future_metadata: { revision: 3 } });
    expect(decodeHistoryPage(page, conv).messages[0].final?.citations[0].citation).toEqual(citation);
  });

  it("normalizes legacy citation key order without requiring unit_id", () => {
    const page = historyPage(), item = page.items[0];
    delete (item.citations[0] as { unit_id?: string }).unit_id;
    delete (item.final_result.citations[0].citation as { unit_id?: string }).unit_id;
    item.citations = [Object.fromEntries(Object.entries(item.citations[0]).reverse()) as ReturnType<typeof serverCitation>];
    expect(decodeHistoryPage(page, conv).messages[0].final?.citations[0].citation).not.toHaveProperty("unit_id");
  });

  it.each([
    ["citation_id", message], ["source_id", conv], ["document_version_id", conv], ["chunk_id", message],
    ["source_title", "Nguồn khác"], ["canonical_uri", "https://example.invalid/other"], ["version_label", "other"],
    ["source_status", "SUPERSEDED"], ["quote", "Đoạn khác"], ["release_id", conv], ["release_generation", 28],
    ["evidence_sha256", "b".repeat(64)], ["unit_id", "fedcba9876543210".repeat(4)],
  ])("rejects a stored %s that differs from the final result", (field, value) => {
    const page = historyPage();
    (page.items[0].citations[0] as Record<string, unknown>)[field] = value;
    expect(() => decodeHistoryPage(page, conv)).toThrow();
  });

  it.each([
    ["section_path", "Mục khác"], ["paragraph_id", "paragraph-2"], ["page_start", 9], ["page_end", 11],
  ])("rejects a stored locator %s that differs from the final result", (field, value) => {
    const page = historyPage();
    (page.items[0].citations[0].locator as Record<string, unknown>)[field] = value;
    expect(() => decodeHistoryPage(page, conv)).toThrow();
  });

  it.each(["quote", "chunk_id", "release_id", "release_generation", "evidence_sha256", "unit_id"])(
    "rejects a missing stored %s present in the final result", (field) => {
      const page = historyPage();
      delete (page.items[0].citations[0] as Record<string, unknown>)[field];
      expect(() => decodeHistoryPage(page, conv)).toThrow();
    },
  );

  it.each(["stored", "final"])("rejects invalid known fields on the %s side", (side) => {
    const page = historyPage(), item = page.items[0];
    const citation = side === "stored" ? item.citations[0] : item.final_result.citations[0].citation;
    citation.evidence_sha256 = "invalid";
    expect(() => decodeHistoryPage(page, conv)).toThrow();
  });

  it.each(["", " \t", null, 17, "x".repeat(257)])("rejects invalid unit_id %j on both sides", (unitId) => {
    const page = historyPage(), item = page.items[0];
    (item.citations[0] as Record<string, unknown>).unit_id = unitId;
    (item.final_result.citations[0].citation as Record<string, unknown>).unit_id = unitId;
    expect(() => decodeHistoryPage(page, conv)).toThrow();
  });
});

describe("v2 live SSE citations", () => {
  it("completes with server-shaped citations and preserves unit_id", () => {
    const result = stream(), final = historyPage().items[0].final_result;
    result.accept(frame("citation.added", { message_id: message, citation: final.citations[0] }, 2));
    expect(result.snapshot.citations).toEqual([]);
    result.accept(frame("message.completed", final, 3));
    expect(result.finish()).toMatchObject({ phase: "completed", citations: final.citations });
  });

  it.each(["", " \t", null, 17, "x".repeat(257)])("rejects malformed unit_id %j in citation events and completion", (unitId) => {
    const final = historyPage().items[0].final_result;
    (final.citations[0].citation as Record<string, unknown>).unit_id = unitId;
    expect(() => stream().accept(frame("citation.added", { message_id: message, citation: final.citations[0] }, 2))).toThrow();
    expect(() => stream().accept(frame("message.completed", final, 2))).toThrow();
  });
});
