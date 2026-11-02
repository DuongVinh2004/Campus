import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import { SourceOperations } from "./SourceOperations";
vi.mock("../../components/AppShell", () => ({ AppShell: ({ children }: { children: React.ReactNode }) => <>{children}</> }));

const v = { id: "version-demo", source_id: "source-demo", procedure: "GRADE_APPEAL", text: "Demo source evidence", mapping: "ORIGINAL_TEXT", candidate_text: "Candidate only",
  created_by: "editor", revision: 3, state: "BUILT", source_sha256: "hash", rendition_sha256: "hash", effective_from: "2026-10-13T00:00:00Z", effective_until: null,
  reviews: [{ reviewer: "reviewer", verdict: "approved", note: "Checked" }], build: { error: null, checksum: "manifest", compatibility: "demo-lexical-v1" } };
function setup(actorId = "reviewer", publicationStatus = 200, denied = false) {
  const requests: string[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    const path = new URL(url, window.location.origin).pathname; requests.push(path);
    let status = 200; let value: unknown;
    if (path.endsWith("/users/me")) value = { user_id: actorId, display_name: "Admin demo", roles: ["KNOWLEDGE_ADMIN"] };
    else if (path.endsWith("/publish/preview")) value = { preview_id: "publication-preview", confirmation_token: "signed", expires_at: "2030-01-01T00:00:00Z", payload: { version_id: v.id, operation: "publish" } };
    else if (path.endsWith("/confirm")) { status = publicationStatus; value = status === 200 ? {} : { detail: "Build/active pointer đã đổi", code: "ACTIVE_VERSION_CHANGED" }; }
    else { status = denied ? 403 : 200; value = denied ? { detail: "Không có quyền admin", code: "ROLE_REQUIRED" } : { versions: [v], sources: [{ id: "source-demo", title: "Demo source", filename: "demo.txt", locator: "Fixture", original_base64: btoa("Demo source evidence"), original_sha256: "hash", created_by: "editor" }], active: [{ id: "GRADE_APPEAL", version_id: "old-version", generation: 1 }], history: [] }; }
    return new Response(JSON.stringify(value), { status, headers: { "Content-Type": "application/json" } });
  })); return requests;
}
beforeEach(() => { localStorage.clear(); window.history.replaceState({}, "", "/knowledge/sources"); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
describe("Stage6 source UI", () => {
  it("requires publication preview and confirmation, preserving old pointer on failure", async () => {
    const requests = setup("reviewer", 409); render(<SourceOperations />);
    fireEvent.click(await screen.findByRole("button", { name: /GRADE_APPEAL/ }));
    fireEvent.click(screen.getByText("Xem trước xuất bản")); await screen.findByText("Preview publish");
    expect(requests.some(p => p.endsWith("/confirm"))).toBe(false);
    fireEvent.click(screen.getByText("Xác nhận xuất bản")); await screen.findByRole("alert");
    expect(screen.getByText(/old-version/)).toBeInTheDocument();
    expect(screen.queryByText("Đã ghi thay đổi active version")).toBeNull();
  });
  it("does not offer editor self review or publication", async () => {
    setup("editor"); render(<SourceOperations />); fireEvent.click(await screen.findByRole("button", { name: /GRADE_APPEAL/ }));
    expect(screen.queryByText("Review đồng ý")).toBeNull(); expect(screen.queryByText("Xem trước xuất bản")).toBeNull();
  });
  it("shows real authorization error and no fake versions", async () => {
    setup("student", 200, true); render(<SourceOperations />); await screen.findByRole("alert");
    expect(screen.queryByText("Active version")).toBeNull();
  });
});
