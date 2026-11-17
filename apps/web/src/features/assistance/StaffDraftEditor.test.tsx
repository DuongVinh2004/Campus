import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";
import { StaffDraftEditor } from "./StaffDraftEditor";

const actor = "019a0000-0000-7000-8000-000000000009";
let counter = 100;
function resource() { return { kind: "service_request" as const, id: `019a0000-0000-7000-8000-${String(counter++).padStart(12, "0")}`, expected_version: 3 }; }
function response(value: unknown, status = 200) { return new Response(JSON.stringify(value), { status, headers: { "content-type": "application/json" } }); }
function view(text = "", version = 0) { return { draft_version: version, business_version: 3, text, saved: version > 0, binding_stale: false, actor_id: actor, tenant: "huce-local-public" }; }
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe("durable private staff draft", () => {
  it("restores committed text and only copies after an explicit reauthorized click", async () => {
    const onUse = vi.fn(); const requests: string[] = [];
    vi.stubGlobal("fetch", vi.fn(async (url: string) => { requests.push(new URL(url, window.location.origin).pathname); return response(view("Committed private text", 2)); }));
    render(<StaffDraftEditor actorId={actor} resource={resource()} onUse={onUse} />);
    await waitFor(() => expect(screen.getByLabelText("Nội dung nháp riêng")).toHaveValue("Committed private text"));
    expect(screen.getByRole("status")).toHaveTextContent("Đã lưu nháp · phiên bản 2"); expect(onUse).not.toHaveBeenCalled();
    fireEvent.click(screen.getByText("Đưa vào ô phản hồi để kiểm tra"));
    await waitFor(() => expect(onUse).toHaveBeenCalledWith("Committed private text"));
    expect(requests).toEqual(["/v1/assistant/staff-drafts/read", "/v1/assistant/staff-drafts/read"]);
  });

  it("keeps manual text after failure and retries the identical payload/client ID", async () => {
    const writes: Record<string, unknown>[] = []; let saved = view();
    vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
      if (new URL(url, window.location.origin).pathname.endsWith("/read")) return response(saved);
      const body = JSON.parse(init?.body as string); writes.push(body);
      if (writes.length === 1) return response({ status: 503, code: "DEPENDENCY_UNAVAILABLE", detail: "Fixture database unavailable" }, 503);
      saved = view(body.text, 1); return response({ saved: true, draft_version: 1, business_version: 3, receipt_id: "fixture-receipt" }, 201);
    }));
    render(<StaffDraftEditor actorId={actor} resource={resource()} onUse={vi.fn()} />);
    await waitFor(() => expect(screen.getByLabelText("Nội dung nháp riêng")).toBeEnabled());
    fireEvent.change(screen.getByLabelText("Nội dung nháp riêng"), { target: { value: "Unsent manual text survives" } });
    fireEvent.click(screen.getByText("Lưu nháp"));
    await screen.findByRole("alert"); expect(screen.getByLabelText("Nội dung nháp riêng")).toHaveValue("Unsent manual text survives");
    expect(screen.getByRole("status")).not.toHaveTextContent("Đã lưu");
    fireEvent.click(screen.getByText("Thử lại cùng nội dung lưu"));
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("Đã lưu nháp"));
    expect(writes[1]).toEqual(writes[0]);
    expect(writes[0].client_id).toMatch(/^[0-9a-f-]{14}7[0-9a-f-]{21}$/);
  });

  it("preserves manual input on CAS conflict and displays the server text separately", async () => {
    let reads = 0;
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (new URL(url, window.location.origin).pathname.endsWith("/read")) return response(view(reads++ ? "Another tab committed" : "Old text", reads > 1 ? 2 : 1));
      return response({ status: 409, code: "STATE_CONFLICT", detail: "Changed by another tab" }, 409);
    }));
    render(<StaffDraftEditor actorId={actor} resource={resource()} onUse={vi.fn()} />);
    await waitFor(() => expect(screen.getByLabelText("Nội dung nháp riêng")).toHaveValue("Old text"));
    fireEvent.change(screen.getByLabelText("Nội dung nháp riêng"), { target: { value: "My unsent manual words" } });
    fireEvent.click(screen.getByText("Lưu nháp")); await screen.findByRole("alert");
    expect(screen.getByLabelText("Nội dung nháp riêng")).toHaveValue("My unsent manual words");
    fireEvent.click(screen.getByText("Đối chiếu bản server, giữ nội dung đang soạn"));
    await waitFor(() => expect(screen.queryByRole("alert")).toBeNull());
    expect(screen.getByLabelText("Nội dung nháp riêng")).toHaveValue("My unsent manual words");
  });

  it("serializes edits arriving while a save is in flight", async () => {
    let release: ((value: Response) => void) | undefined; let saved = view(); const writes: Record<string, unknown>[] = [];
    vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
      if (new URL(url, window.location.origin).pathname.endsWith("/read")) return response(saved);
      const body = JSON.parse(init?.body as string); writes.push(body);
      if (writes.length === 1) return new Promise<Response>(resolve => { release = resolve; });
      saved = view(body.text, 2); return response({ saved: true, draft_version: 2, business_version: 3, receipt_id: "fixture-receipt2" });
    }));
    render(<StaffDraftEditor actorId={actor} resource={resource()} onUse={vi.fn()} />);
    const field = screen.getByLabelText("Nội dung nháp riêng"); await waitFor(() => expect(field).toBeEnabled());
    fireEvent.change(field, { target: { value: "First words" } }); fireEvent.click(screen.getByText("Lưu nháp"));
    await waitFor(() => expect(release).toBeDefined()); fireEvent.change(field, { target: { value: "Second manual words" } });
    saved = view("First words", 1); release?.(response({ saved: true, draft_version: 1, business_version: 3, receipt_id: "fixture-receipt1" }));
    await waitFor(() => expect(writes).toHaveLength(2), { timeout: 3000 });
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("phiên bản 2"));
    expect(writes[1].text).toBe("Second manual words"); expect(writes[1].expected_draft_version).toBe(1);
  });

  it("does not project draft data from a different server actor", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => response({ ...view("Private other actor text", 1), actor_id: "019a0000-0000-7000-8000-000000000099" })));
    render(<StaffDraftEditor actorId={actor} resource={resource()} onUse={vi.fn()} />);
    await screen.findByRole("alert"); expect(screen.getByLabelText("Nội dung nháp riêng")).toHaveValue("");
    expect(screen.getByLabelText("Nội dung nháp riêng")).toBeDisabled();
    expect(screen.queryByText("Private other actor text")).toBeNull();
  });

  it("refuses copying a stale binding without invoking the public response callback", async () => {
    let reads = 0; const onUse = vi.fn();
    vi.stubGlobal("fetch", vi.fn(async () => response({ ...view("Manual candidate", 1), binding_stale: reads++ > 0 })));
    render(<StaffDraftEditor actorId={actor} resource={resource()} onUse={onUse} />);
    await waitFor(() => expect(screen.getByLabelText("Nội dung nháp riêng")).toBeEnabled());
    fireEvent.click(screen.getByText("Đưa vào ô phản hồi để kiểm tra")); await screen.findByRole("alert");
    expect(onUse).not.toHaveBeenCalled();
  });
});
