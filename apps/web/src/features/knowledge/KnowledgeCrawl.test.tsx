import React from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { KnowledgeCrawl, type CrawlSource } from "./KnowledgeCrawl";

const source = (over: Partial<CrawlSource> = {}): CrawlSource => ({ id: "s1", name: "Thông báo đào tạo", seed_urls: ["https://huce.edu.vn/thong-bao"], kind: "LIST", include: [], exclude: [],
  max_depth: 2, max_pages: 200, interval_hours: 24, owner_unit: "Phòng Đào tạo", mode: "REVIEW", active: true, ingest_enabled: false, next_run_at: null,
  last_run_at: "2026-11-16T10:00:00Z", last_status: "DRY_RUN", pending_run: null,
  last_run: { id: "r1", dry_run: true, state: "DONE", counts: { WOULD_CREATE: 3, BLOCKED_PII: 1 }, error: null, started_at: "2026-11-16T10:00:00Z", finished_at: "2026-11-16T10:02:00Z" }, ...over });

let sources: CrawlSource[]; let calls: Array<{ url: string; body?: string }>;
beforeEach(() => {
  calls = []; sources = [source()];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (url, init) => {
    calls.push({ url: String(url), body: init?.body as string | undefined });
    if (String(url).endsWith("/runs")) return new Response(JSON.stringify({ items: [{ ...sources[0].last_run, decisions: [
      { url: "https://huce.edu.vn/thong-bao/a", kind: "page", decision: "WOULD_CREATE", reason: "chạy thử: chưa nạp gì", title: "Học phí" },
      { url: "https://huce.edu.vn/thong-bao/ds", kind: "page", decision: "BLOCKED_PII", reason: "danh sách người kèm mã định danh (8)" }] }] }));
    if (init?.method === "POST") return new Response(JSON.stringify({ id: "s1" }), { status: 202 });
    return new Response(JSON.stringify({ items: sources }));
  });
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

it("a new source is shown as dry-run only, with the warning, and ingestion is off", async () => {
  render(<KnowledgeCrawl />);
  expect(await screen.findByText("Chỉ chạy thử")).toBeTruthy();
  expect(screen.getByText(/Xem báo cáo chạy thử trước khi bật nạp/)).toBeTruthy();
  expect(screen.queryByRole("button", { name: "Chạy ngay" })).toBeNull();          // no real run before ingestion is switched on
  expect(screen.getByText(/Sẽ tạo mới: 3/)).toBeTruthy();
});

it("the report lists each decision with its reason, including pages kept out for personal data", async () => {
  render(<KnowledgeCrawl />);
  fireEvent.click(await screen.findByRole("button", { name: "Xem báo cáo" }));
  expect(await screen.findByText(/Loại: dữ liệu cá nhân/)).toBeTruthy();
  expect(screen.getByText(/danh sách người kèm mã định danh/)).toBeTruthy();
});

it("switching ingestion on and requesting a dry run send the right commands", async () => {
  render(<KnowledgeCrawl />);
  fireEvent.click(await screen.findByRole("button", { name: "Bật nạp" }));
  await waitFor(() => expect(calls.some(c => c.url.endsWith("/s1/settings"))).toBe(true));
  expect(JSON.parse(calls.find(c => c.url.endsWith("/s1/settings"))!.body!)).toEqual({ ingest_enabled: true });
  fireEvent.click(screen.getByRole("button", { name: /Chạy thử/ }));
  await waitFor(() => expect(calls.some(c => c.url.endsWith("/s1/run"))).toBe(true));
  expect(JSON.parse(calls.find(c => c.url.endsWith("/s1/run"))!.body!)).toEqual({ dry_run: true });
});

it("an ingesting source offers a real run and can be switched back to dry run", async () => {
  sources = [source({ ingest_enabled: true, last_status: "OK" })];
  render(<KnowledgeCrawl />);
  expect(await screen.findByText("Đang nạp tài liệu")).toBeTruthy();
  expect(screen.getByRole("button", { name: "Chạy ngay" })).toBeTruthy();
  expect(screen.getByRole("button", { name: "Tắt nạp" })).toBeTruthy();
});

it("creating a source posts the seed addresses, one per line, always as approval-first", async () => {
  const { container } = render(<KnowledgeCrawl />);
  await screen.findByText("Thông báo đào tạo");
  fireEvent.change(container.querySelector('input[name="name"]')!, { target: { value: "Tin phòng Công tác sinh viên" } });
  fireEvent.change(container.querySelector('input[name="owner_unit"]')!, { target: { value: "Phòng CTSV" } });
  fireEvent.change(container.querySelector('textarea[name="seed_urls"]')!, { target: { value: "https://huce.edu.vn/a\nhttps://huce.edu.vn/b" } });
  fireEvent.submit(container.querySelectorAll("form")[0]);
  await waitFor(() => expect(calls.some(c => c.url === "/v1/knowledge/platform/crawl-sources" && c.body)).toBe(true));
  const body = JSON.parse(calls.find(c => c.url === "/v1/knowledge/platform/crawl-sources" && c.body)!.body!);
  expect(body.seed_urls).toEqual(["https://huce.edu.vn/a", "https://huce.edu.vn/b"]); expect(body.mode).toBe("REVIEW");
});
