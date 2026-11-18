import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import { KnowledgePlatform } from "./KnowledgePlatform";

vi.mock("../../components/AppShell", () => ({ AppShell: ({ children }: { children: React.ReactNode }) => <>{children}</> }));

function setup({ serving = false, denied = false, author = false } = {}) {
  const calls: Array<{ url: string; body: unknown }> = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    const path = String(url); const body = init?.body ? JSON.parse(String(init.body)) : null;
    calls.push({ url: path, body });
    let value: unknown = {};
    if (path.endsWith("/users/me")) value = { user_id: author ? "editor" : "reviewer", roles: ["KNOWLEDGE_ADMIN"] };
    else if (path.endsWith("/state")) value = { mode: "postgres_bge", sources: [{ id: "source", title: "Văn bản", canonical_uri: "urn:test" }],
      versions: [{ version_id: "version", source_id: "source", filename: "document.txt", created_by: "editor", revision: 2,
        review_state: "APPROVED", publication_state: "DRAFT", original_sha256: "hash", rendition_sha256: "rendition", revoked_at: null, index_version: "bge-index" }],
      jobs: [{ id: "job", version_id: "version", state: "SUCCEEDED", stage: "REVIEW", progress: 100 }],
      desired: { release_id: "release", generation: 2, policy_generation: 0 }, is_serving: serving,
      serving: [], runtime: [], releases: [{ id: "release", document_count: 1, membership_sha256: "hash" }] };
    else if (path.endsWith("/rendition")) value = { pages: [{ page: null, text: "Evidence nguyên văn." }], issues: [] };
    else if (path.endsWith("/previews")) value = { preview_id: "preview", confirmation_token: "signed", expires_at: "2030-01-01T00:00:00Z",
      payload: { operation: "activate", target_id: "release", generation: 2, members: [{ version_id: "version" }] } };
    else if (path.endsWith("/confirmations")) value = { serving_confirmed: false };
    return new Response(JSON.stringify(denied ? { detail: "Không có quyền quản trị", code: "KNOWLEDGE_FORBIDDEN" } : value),
      { status: denied ? 403 : 200, headers: { "Content-Type": "application/json" } });
  }));
  return calls;
}
beforeEach(() => { localStorage.clear(); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe("Real knowledge administration", () => {
  it("waits for runtime acknowledgement after explicit preview and confirmation", async () => {
    const calls = setup(); render(<KnowledgePlatform />);
    await screen.findByText("Chưa có xác nhận phục vụ còn hiệu lực");
    fireEvent.change(screen.getByLabelText("Release"), { target: { value: "release" } });
    fireEvent.click(screen.getByText("Xem trước xuất bản"));
    await screen.findByText("Xác nhận activate");
    expect(calls.some(c => c.url.endsWith("/confirmations"))).toBe(false);
    fireEvent.click(screen.getByText("Tôi xác nhận thao tác này"));
    await screen.findByText("Đã ghi thay đổi; đang chờ xác nhận runtime.");
    expect(screen.queryByText("Runtime đã xác nhận phục vụ release hiện tại")).toBeNull();
  });
  it("does not offer authors independent review", async () => {
    setup({ author: true }); render(<KnowledgePlatform />);
    fireEvent.click(await screen.findByRole("button", { name: /document.txt/ }));
    await screen.findByText("Evidence nguyên văn.");
    expect(screen.queryByText("Duyệt nội dung")).toBeNull();
  });
  it("shows authorization failure without mock sources", async () => {
    setup({ denied: true }); render(<KnowledgePlatform />);
    await screen.findByRole("alert");
    expect(screen.queryByText("Upload tài liệu")).toBeNull();
    expect(screen.queryByText("document.txt")).toBeNull();
  });

  it("opens the actual rendition when returning from a resolved intake", async () => {
    const calls = setup({ author: true });
    const originalFetch = global.fetch;
    vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
      if (String(url).endsWith("/intakes")) return new Response(JSON.stringify({ items: [{
        id: "intake", filename: "received.pdf", version_id: "version", state: "SUCCEEDED", stage: "METADATA_RESOLVED",
        progress: 100, revision: 2, job_id: "intake-job", observed_at: "2026-10-26T00:00:00Z", hints: {}, issues: [] }] }));
      return originalFetch(url, init);
    }));
    render(<KnowledgePlatform />);
    fireEvent.click(await screen.findByRole("button", { name: "Mở phiên bản để đối chiếu" }));
    await screen.findByText("Evidence nguyên văn.");
    expect(calls.some(call => call.url.endsWith("/versions/version/rendition"))).toBe(true);
  });
});
