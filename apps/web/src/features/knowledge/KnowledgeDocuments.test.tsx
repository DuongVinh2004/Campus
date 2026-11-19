import React from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { KnowledgeDocuments, type PipelineItem } from "./KnowledgeDocuments";

const item = (over: Partial<PipelineItem>): PipelineItem => ({
  version_id: "v1", title: "Quy định thử", filename: "a.txt", canonical_uri: "https://huce.edu.vn/a", mode: "REVIEW", origin: "UPLOAD", state: "AWAITING_REVIEW",
  label: "Chờ người duyệt", flags: [], checks: [{ name: "text", label: "Có nội dung chữ", ok: true, detail: "300 ký tự" }], error_code: null, error_detail: null,
  created_at: "2026-11-16T10:00:00Z", state_changed_at: "2026-11-16T10:00:00Z", usable_at: null, effective_from: null, review_note: null,
  can_approve: false, can_retry: false, can_reject: false, ...over });

let listing: { items: PipelineItem[]; generation: number; can_publish_directly: boolean };
let calls: Array<{ url: string; init?: RequestInit }>;
beforeEach(() => {
  calls = [];
  listing = { items: [], generation: 1, can_publish_directly: false };
  vi.spyOn(globalThis, "fetch").mockImplementation(async (url, init) => {
    calls.push({ url: String(url), init });
    if (init?.method === "POST") return new Response(JSON.stringify({ mode: listing.can_publish_directly ? "DIRECT" : "REVIEW", version_id: "v9" }), { status: 202 });
    return new Response(JSON.stringify(listing));
  });
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

it("a contributor can only send for approval: no direct publish option, button says Gửi duyệt", async () => {
  render(<KnowledgeDocuments />);
  expect(await screen.findByRole("button", { name: "Gửi duyệt" })).toBeTruthy();
  expect(screen.queryByText(/Đăng trực tiếp/)).toBeNull();
  expect(screen.queryByRole("checkbox")).toBeNull();
});

it("a direct publisher must tick the attestation before Đăng is possible", async () => {
  listing.can_publish_directly = true;
  render(<KnowledgeDocuments />);
  const button = await screen.findByRole("button", { name: "Đăng" });
  expect((button as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByRole("checkbox"));
  expect((button as HTMLButtonElement).disabled).toBe(false);
});

it("sends publish_directly only after attestation and carries an idempotency key", async () => {
  listing.can_publish_directly = true;
  const { container } = render(<KnowledgeDocuments />);
  await screen.findByRole("button", { name: "Đăng" });
  fireEvent.click(screen.getByRole("checkbox"));
  const file = new File(["nội dung"], "a.txt", { type: "text/plain" });
  fireEvent.change(container.querySelector('input[name="title"]')!, { target: { value: "Quy định thử" } });
  fireEvent.change(container.querySelector('input[name="owner_unit"]')!, { target: { value: "Phòng thử" } });
  fireEvent.change(container.querySelector('input[name="canonical_uri"]')!, { target: { value: "https://huce.edu.vn/a" } });
  fireEvent.change(container.querySelector('input[name="file"]')!, { target: { files: [file] } });
  fireEvent.submit(container.querySelector("form")!);
  await waitFor(() => expect(calls.some(c => c.init?.method === "POST")).toBe(true));
  const post = calls.find(c => c.init?.method === "POST")!;
  expect((post.init!.headers as Record<string, string>)["Idempotency-Key"]).toBeTruthy();
  const meta = JSON.parse(String((post.init!.body as FormData).get("metadata")));
  expect(meta.publish_directly).toBe(true); expect(meta.attested).toBe(true); expect(meta.canonical_uri.startsWith("https://")).toBe(true);
});

it("shows approve only where the API allows it and sends the note", async () => {
  listing = { items: [item({ can_approve: true, can_reject: true })], generation: 1, can_publish_directly: true };
  render(<KnowledgeDocuments />);
  fireEvent.change(await screen.findByLabelText("Ghi chú cho Quy định thử"), { target: { value: "Đã đối chiếu." } });
  fireEvent.click(screen.getByRole("button", { name: "Duyệt" }));
  await waitFor(() => expect(calls.some(c => c.url.endsWith("/v1/knowledge/platform/documents/v1/approve"))).toBe(true));
  expect(JSON.parse(String(calls.find(c => c.url.endsWith("/approve"))!.init!.body))).toEqual({ note: "Đã đối chiếu." });
});

it("does not offer approve to the author or a contributor", async () => {
  listing = { items: [item({ can_approve: false })], generation: 1, can_publish_directly: false };
  render(<KnowledgeDocuments />);
  expect(await screen.findByText("Quy định thử")).toBeTruthy();
  expect(screen.queryByRole("button", { name: "Duyệt" })).toBeNull();
});

it("shows the failing check and a retry for a document that needs attention, and the usable time when active", async () => {
  listing = { items: [item({ state: "NEEDS_ATTENTION", label: "Cần xử lý", error_code: "CHECK_FAILED", error_detail: "Không trùng văn bản đang phát hành: trùng nội dung với «A»", can_retry: true, can_reject: true,
    checks: [{ name: "duplicate", label: "Không trùng văn bản đang phát hành", ok: false, detail: "trùng nội dung với «A»" }] }),
    item({ version_id: "v2", title: "Đã xong", state: "ACTIVE", label: "Chatbot đã dùng được", usable_at: "2026-11-16T10:05:00Z" })], generation: 2, can_publish_directly: true };
  render(<KnowledgeDocuments />);
  expect((await screen.findByRole("alert")).textContent).toContain("trùng nội dung");
  expect(screen.getByRole("button", { name: "Thử lại" })).toBeTruthy();
  expect(screen.getByText(/Chatbot dùng được từ/)).toBeTruthy();
});

it("an administrator can revoke a published document, but only with a reason", async () => {
  listing = { items: [item({ state: "ACTIVE", label: "Chatbot đã dùng được", usable_at: "2026-11-16T10:05:00Z", can_revoke: true })], generation: 2, can_publish_directly: true };
  render(<KnowledgeDocuments />);
  fireEvent.click(await screen.findByRole("button", { name: "Thu hồi" }));
  expect((await screen.findByRole("alert")).textContent).toContain("lý do thu hồi");
  expect(calls.some(c => c.url.endsWith("/revoke"))).toBe(false);
  fireEvent.change(screen.getByLabelText("Ghi chú cho Quy định thử"), { target: { value: "Đăng nhầm văn bản." } });
  fireEvent.click(screen.getByRole("button", { name: "Thu hồi" }));
  await waitFor(() => expect(calls.some(c => c.url.endsWith("/v1/knowledge/platform/documents/v1/revoke"))).toBe(true));
});

it("submitting an empty form shows what is missing instead of doing nothing, and sends nothing", async () => {
  render(<KnowledgeDocuments />);
  fireEvent.click(await screen.findByRole("button", { name: "Gửi duyệt" }));
  const alert = await screen.findByRole("alert");
  expect(alert.textContent).toContain("Tên tài liệu");
  expect(alert.textContent).toContain("Chọn tệp PDF hoặc TXT");
  expect(calls.some((call) => call.init?.method === "POST")).toBe(false);
});
