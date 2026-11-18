import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { StudentPageFeedback } from "./PageFeedback";

const actorId = "00000000-0000-4000-8000-000000000001";
const versionId = "00000000-0000-4000-8000-000000000002";
const sessionId = "00000000-0000-4000-8000-000000000003";
const feedbackId = "00000000-0000-4000-8000-000000000004";
const versionPath = `/v1/learning/versions/${versionId}`;
const pagePath = `${versionPath}/pages/2/me/feedback`;
const title = "Em đang vướng ở trang này";

function reader(pageNo = 2) {
  return <StudentPageFeedback actorId={actorId} versionId={versionId} versionNumber={3}
    pageNo={pageNo} sourceSessionId={sessionId} timeZone="Asia/Bangkok" />;
}

function json(value: unknown) {
  return new Response(JSON.stringify(value), { headers: { "Content-Type": "application/json" } });
}

beforeEach(() => {
  // jsdom has no layout, so report the fixture's visible dialog controls as laid out.
  vi.spyOn(HTMLElement.prototype, "getClientRects").mockReturnValue({ length: 1 } as DOMRectList);
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

it("puts focus on the dialog heading during context loading and restores the opener on Escape", () => {
  const requests: AbortSignal[] = [];
  vi.stubGlobal("fetch", vi.fn((_path: string, init: RequestInit) => {
    if (init.signal) requests.push(init.signal);
    return new Promise<Response>(() => {});
  }));
  render(reader());
  const opener = screen.getByRole("button", { name: title });
  fireEvent.click(opener);
  const modal = screen.getByRole("dialog", { name: title });
  const dialog = within(modal);
  const heading = dialog.getByRole("heading", { name: title });
  const close = dialog.getByRole("button", { name: "Đóng" });
  expect(opener).toHaveAttribute("aria-haspopup", "dialog");
  expect(modal).toHaveAccessibleDescription("Phiên bản 3 · Trang 2");
  expect(heading).toHaveFocus();
  expect(dialog.getByRole("status")).toHaveTextContent("Đang kiểm tra ngữ cảnh buổi học…");

  fireEvent.keyDown(heading, { key: "Tab", shiftKey: true });
  expect(close).toHaveFocus();
  fireEvent.keyDown(close, { key: "Tab" });
  expect(heading).toHaveFocus();

  fireEvent.keyDown(heading, { key: "Escape" });
  expect(screen.queryByRole("dialog")).toBeNull();
  expect(opener).toHaveFocus();
  expect(requests).toHaveLength(2);
  expect(requests.every(signal => signal.aborted)).toBe(true);
});

it("keeps focus and the page fixed through a lost response, retry and withdrawal", async () => {
  const writes: { method: string; key: string | null; body: unknown }[] = [];
  let failFirstWrite: (() => void) | undefined;
  let pageReads = 0;
  vi.stubGlobal("fetch", vi.fn(async (path: string, init: RequestInit) => {
    const headers = new Headers(init.headers);
    expect(headers.get("X-Campus-Reader-Actor")).toBe(actorId);
    if (path === `${versionPath}/session-contexts?limit=100`) {
      return json({ items: [{ id: sessionId, title: "Buổi diễn tập" }] });
    }
    if (path === `/v1/learning/sessions/${sessionId}/page-feedback-window`) {
      return json({ window: { closes_at: "2099-01-01T00:00:00Z" } });
    }
    if (path === pagePath && !init.method) {
      pageReads++;
      return json({ feedback: null });
    }
    if ((path === pagePath && init.method === "PUT") ||
      (path === `/v1/learning/me/page-feedback/${feedbackId}` && init.method === "PATCH")) {
      writes.push({ method: init.method, key: headers.get("Idempotency-Key"), body: JSON.parse(String(init.body)) });
      if (writes.length === 1) {
        return new Promise<Response>((_resolve, reject) => { failFirstWrite = () => reject(new Error("Lost response")); });
      }
      const withdrawn = init.method === "PATCH";
      return json({ id: feedbackId, session_id: sessionId, category: "NEED_EXAMPLE",
        status: withdrawn ? "WITHDRAWN" : "ACTIVE", revision: withdrawn ? 2 : 1 });
    }
    throw new Error(`Unexpected feedback request: ${init.method ?? "GET"} ${path}`);
  }));
  const view = render(reader());
  const opener = screen.getByRole("button", { name: title });
  fireEvent.click(opener);
  const dialog = within(screen.getByRole("dialog", { name: title }));
  const status = dialog.getByRole("status");
  const alert = dialog.getByRole("alert");
  view.rerender(reader(4));
  expect(screen.getByRole("dialog", { name: title })).toHaveAccessibleDescription("Phiên bản 3 · Trang 2");
  const reason = await dialog.findByRole("radio", { name: "Cần thêm ví dụ" });
  expect(dialog.getByRole("group", { name: "Lý do" })).toContainElement(reason);
  fireEvent.click(reason);
  expect(reason).toBeChecked();
  const submit = dialog.getByRole("button", { name: "Gửi báo vướng" });
  await waitFor(() => expect(submit).toBeEnabled());
  submit.focus();
  fireEvent.click(submit);
  expect(status).toHaveFocus();
  expect(status).toHaveTextContent("Đang kiểm tra hoặc lưu phản hồi…");
  const heading = dialog.getByRole("heading", { name: title });
  fireEvent.keyDown(status, { key: "Tab" });
  expect(heading).toHaveFocus();
  fireEvent.keyDown(heading, { key: "Tab", shiftKey: true });
  expect(status).toHaveFocus();
  fireEvent.keyDown(status, { key: "Escape" });
  expect(screen.getByRole("dialog", { name: title })).toBeVisible();
  failFirstWrite?.();
  const retry = await dialog.findByRole("button", { name: "Kiểm tra và thử lại" });
  expect(alert).toHaveTextContent("Mất kết nối. Hãy kiểm tra kết quả trước khi gửi lại.");
  expect(status).toHaveFocus();
  expect(submit).toBeDisabled();

  retry.focus();
  fireEvent.click(retry);
  await waitFor(() => expect(status).toHaveTextContent("Đã lưu phản hồi."));
  expect(status).toHaveFocus();
  expect(alert).toBeEmptyDOMElement();
  expect(pageReads).toBe(2);
  expect(writes[0]).toMatchObject({ method: "PUT", key: expect.any(String),
    body: { category: "NEED_EXAMPLE", session_id: sessionId, revision: 0 } });
  expect(writes[1]).toEqual(writes[0]);

  const withdraw = dialog.getByRole("button", { name: "Rút phản hồi" });
  withdraw.focus();
  fireEvent.click(withdraw);
  await waitFor(() => expect(status).toHaveTextContent("Đã rút phản hồi."));
  expect(status).toHaveFocus();
  expect(writes[2]).toMatchObject({ method: "PATCH", body: { revision: 1 } });
  fireEvent.click(dialog.getByRole("button", { name: "Đóng" }));
  expect(screen.queryByRole("dialog")).toBeNull();
  expect(opener).toHaveFocus();
});
