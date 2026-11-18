import React from "react";
import "@testing-library/jest-dom/vitest";
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { StudentPageFeedback } from "./PageFeedback";
import { PreservedActivity } from "./learning-session";

const title = "Em đang vướng ở trang này";
const sessionId = "00000000-0000-4000-8000-000000000003";
const versionId = "00000000-0000-4000-8000-000000000002";
const own = { id: "feedback", session_id: sessionId, category: "NEED_EXAMPLE", status: "ACTIVE", revision: 1 };
const json = (value: unknown) => new Response(JSON.stringify(value));
let writes = 0;
let stored = false;
function transport({ initialReadPaused = false, writePaused = false } = {}) {
  let firstRead = initialReadPaused;
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    if (init?.signal?.aborted) throw new DOMException("Cancelled", "AbortError");
    const path = String(input);
    if (init?.method === "PUT") {
      writes++; stored = true;
      if (writePaused) return new Promise<Response>((_resolve, reject) => init.signal?.addEventListener("abort", () => reject(new DOMException("Cancelled", "AbortError")), { once: true }));
      return json(own);
    }
    if (path.includes("session-contexts")) return json({ items: [{ id: sessionId, title: "Synthetic session" }] });
    if (path.includes("page-feedback-window")) return json({ window: { closes_at: "2099-01-01T00:00:00Z" } });
    if (firstRead) {
      firstRead = false;
      return new Promise<Response>((_resolve, reject) => init?.signal?.addEventListener("abort", () => reject(new DOMException("Cancelled", "AbortError")), { once: true }));
    }
    return json({ feedback: stored ? own : null });
  }));
}
function harness() {
  const child = <StudentPageFeedback actorId="student" versionId={versionId} versionNumber={1} pageNo={2}
    sourceSessionId={sessionId} timeZone="Asia/Bangkok" />;
  const view = render(<PreservedActivity mode="visible">{child}</PreservedActivity>);
  fireEvent.click(screen.getByRole("button", { name: title }));
  return async () => {
    await act(async () => view.rerender(<PreservedActivity mode="hidden">{child}</PreservedActivity>));
    await act(async () => view.rerender(<PreservedActivity mode="visible">{child}</PreservedActivity>));
  };
}
async function choose() {
  fireEvent.click(await screen.findByRole("radio", { name: "Cần thêm ví dụ" }));
  const submit = screen.getByRole("button", { name: "Gửi báo vướng" });
  await waitFor(() => expect(submit).toBeEnabled());
  return submit;
}
afterEach(() => { cleanup(); vi.unstubAllGlobals(); writes = 0; stored = false; });

it("can save the preserved reason after an idle feedback dialog resumes", async () => {
  transport(); const resume = harness(); await choose();
  await resume();
  expect(screen.getByRole("radio", { name: "Cần thêm ví dụ" })).toBeChecked();
  fireEvent.click(screen.getByRole("button", { name: "Gửi báo vướng" }));
  await waitFor(() => expect(writes).toBe(1));
  await screen.findByText("Đã lưu phản hồi.");
});

it("resumes a cancelled initial read without getting stuck in context loading", async () => {
  transport({ initialReadPaused: true }); const resume = harness();
  await resume();
  await choose();
  expect(writes).toBe(0);
});

it("checks the receipt after a suspended write and never duplicates the accepted feedback", async () => {
  transport({ writePaused: true }); const resume = harness();
  fireEvent.click(await choose());
  await waitFor(() => expect(writes).toBe(1));
  await resume();
  const modal = within(screen.getByRole("dialog", { name: title }));
  const check = await modal.findByRole("button", { name: "Kiểm tra và thử lại" });
  expect(check).toBeEnabled();
  fireEvent.click(check);
  await modal.findByText("Đã kiểm tra và hiển thị trạng thái hiện tại.");
  expect(writes).toBe(1);
  expect(modal.getByRole("button", { name: "Đóng" })).toBeEnabled();
});
