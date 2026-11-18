import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";
import { KnowledgeSchedules } from "./KnowledgeSchedules";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

function setup(items: unknown[] = [], running = true, failFirstCreate = false) {
  const calls: Array<{ url: string; body: Record<string, unknown> | null; key: string | null }> = [];
  let failed = false;
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    const body = init?.body ? JSON.parse(String(init.body)) : null;
    calls.push({ url: String(url), body, key: new Headers(init?.headers).get("Idempotency-Key") });
    if (body?.kind && failFirstCreate && !failed) {
      failed = true;
      return new Response(JSON.stringify({ detail: "Temporary dependency failure" }), { status: 503 });
    }
    return new Response(JSON.stringify(String(url).endsWith("/intakes")
      ? { items: [{ id: "intake", filename: "public.pdf", can_refresh_url: true, original_sha256: "a".repeat(64) }] }
      : { items, session_expires_at: "2030-01-01T00:00:00Z", background_running: running }));
  }));
  return calls;
}

describe("Session-scoped knowledge schedules", () => {
  it("requires an exact target and explicit scoped confirmation before saving", async () => {
    const calls = setup();
    render(<KnowledgeSchedules releases={[]} generation={2} onPreview={vi.fn()} />);
    await screen.findByText(/Phiên hết hạn/);
    const save = screen.getByRole("button", { name: "Lưu lịch trong phiên" });
    expect(save).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Nguồn hoặc release"), { target: { value: "intake" } });
    expect(save).toBeDisabled();
    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.click(save);
    await waitFor(() => expect(calls.some(call => call.body?.kind === "URL_REFRESH")).toBe(true));
    const created = calls.find(call => call.body?.kind)!;
    expect(created.body).toMatchObject({ target_id: "intake", expected_original_sha256: "a".repeat(64), confirmed: true });
    expect(created.body).not.toHaveProperty("expected_generation");
    expect(calls.some(call => call.url.endsWith("/confirmations"))).toBe(false);
  });

  it("retains the idempotency key after an ambiguous failure", async () => {
    const calls = setup([], true, true);
    render(<KnowledgeSchedules releases={[]} generation={2} onPreview={vi.fn()} />);
    await screen.findByText(/Phiên hết hạn/);
    fireEvent.change(screen.getByLabelText("Nguồn hoặc release"), { target: { value: "intake" } });
    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.click(screen.getByRole("button", { name: "Lưu lịch trong phiên" }));
    await screen.findByRole("alert");
    fireEvent.click(screen.getByRole("button", { name: "Lưu lịch trong phiên" }));
    await waitFor(() => expect(calls.filter(call => call.body?.kind).length).toBe(2));
    const keys = calls.filter(call => call.body?.kind).map(call => call.key);
    expect(keys[0]).toBeTruthy(); expect(keys[0]).toBe(keys[1]);
  });

  it("requests a normal preview for a due release without publishing or claiming serving", async () => {
    const calls = setup([{ id: "schedule", kind: "RELEASE_DUE", target_id: "release", state: "ACTIVE",
      not_before: "2026-10-27T00:00:00Z", expires_at: "2030-01-01T00:00:00Z", interval_seconds: 900,
      last_outcome: { state: "AWAITING_CONFIRMATION" } }]);
    const preview = vi.fn(async () => {});
    render(<KnowledgeSchedules releases={[]} generation={2} onPreview={preview} />);
    fireEvent.click(await screen.findByRole("button", { name: "Xem trước release tới hạn" }));
    await waitFor(() => expect(preview).toHaveBeenCalledWith("release"));
    expect(calls.some(call => call.url.endsWith("/confirmations"))).toBe(false);
    expect(screen.queryByText(/Runtime đã xác nhận/)).toBeNull();
  });

  it("does not offer a different session authority or silently resume schedules", async () => {
    const calls = setup([{ id: "schedule", kind: "URL_REFRESH", target_id: "intake", state: "SESSION_REQUIRED", can_resume: false,
      not_before: "2026-10-27T00:00:00Z", expires_at: "2030-01-01T00:00:00Z", interval_seconds: 900, last_outcome: null }], false);
    render(<KnowledgeSchedules releases={[]} generation={2} onPreview={vi.fn()} />);
    await screen.findByText(/Lịch gắn với phiên cũ/);
    expect(screen.queryByRole("button", { name: "Tiếp tục lịch của phiên" })).toBeNull();
    expect(screen.getByRole("button", { name: "Lưu lịch trong phiên" })).toBeDisabled();
    expect(calls.some(call => call.url.endsWith("/resume"))).toBe(false);
  });
});
