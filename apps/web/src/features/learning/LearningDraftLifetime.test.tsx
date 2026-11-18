import React from "react";
import "@testing-library/jest-dom/vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { IdeaCards } from "./IdeaCards";
import { AccessibleTextReview } from "./AccessibleTextReview";
import { ExitTicketDetail } from "./ExitTicketDetail";
import { PreservedActivity } from "./learning-session";
import type { LearningOcrReviewRelease, LearningVisibleExitTicket } from "../../lib/data/api/learning-gateway";

const actorId = "00000000-0000-4000-8000-000000000001";
const versionId = "00000000-0000-4000-8000-000000000002";
const release: LearningOcrReviewRelease = {
  id: "draft", version_id: versionId, revision: 1, state: "DRAFT", page_count: 1,
  available_pages: [], missing_page_count: 1, current_release_id: null, requested_pages: [1], reviewed_pages: [],
  candidate: { sha256: "same-candidate", blocks: [{ id: "block", order: 0, text: "Original source text",
    anchor: { x: 0, y: 0, width: 1, height: 1 }, confidence: 99, provenance: "NATIVE", review_reasons: [] }] },
};
const ticket: LearningVisibleExitTicket = {
  id: "ticket", session_id: "session", revision: 1, state: "OPEN", version_id: versionId,
  page_no: 1, question: "Synthetic question", zone_id: "Asia/Bangkok", instruction: null,
  opens: { local: "2026-01-01T07:00", offset_minutes: 420, utc: "2026-01-01T00:00:00Z" },
  closes: { local: "2099-01-01T07:00", offset_minutes: 420, utc: "2099-01-01T00:00:00Z" },
};
const sourceRequest = { sequence: 1, selection: { version_id: versionId, page_no: 1, anchor: { kind: "PAGE" as const } } };
const json = (value: unknown) => new Response(JSON.stringify(value));
let readFailure = false;
let writes = 0;
function transport() {
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (init?.method && init.method !== "GET") {
      writes++;
      return new Promise<Response>((_resolve, reject) => init.signal?.addEventListener("abort",
        () => reject(new DOMException("Cancelled", "AbortError")), { once: true }));
    }
    if (url.includes("ocr-releases/")) {
      if (readFailure) throw new Error("Offline");
      return json(release);
    }
    if (url.endsWith("/ocr-jobs")) return json({ jobs: [], releases: [release], daily_pages_remaining: 10,
      max_pages_per_job: 10, storage_available_bytes: 1024 });
    if (url.endsWith("/me/submission")) return json({ submission: null });
    if (url.endsWith("/exit-tickets/ticket")) return json(ticket);
    return json({ items: [] });
  }));
}
function ideas() {
  return <IdeaCards actorId={actorId} canCreate sourceRequest={sourceRequest} onOpen={vi.fn()} onShare={vi.fn()} />;
}
function ocr() {
  return <AccessibleTextReview actorId={actorId} versionId={versionId} pageCount={1} sourcePage={1} enabled published
    onSource={vi.fn()} onReleaseChange={vi.fn()} confirmWrite={vi.fn()} />;
}
function exit() {
  return <ExitTicketDetail actorId={actorId} ticketId="ticket" staff={false} canManage={false} materials={[]}
    instructions={[]} zoneId="Asia/Bangkok" onClose={vi.fn()} onOpen={vi.fn()} onChange={vi.fn()} confirmWrite={vi.fn()} />;
}
function retained(child: React.ReactNode) {
  const view = render(<PreservedActivity mode="visible">{child}</PreservedActivity>);
  return async () => {
    await act(async () => view.rerender(<PreservedActivity mode="hidden">{child}</PreservedActivity>));
    await act(async () => view.rerender(<PreservedActivity mode="visible">{child}</PreservedActivity>));
  };
}
async function openOcr() {
  fireEvent.change(await screen.findByLabelText("Bản chữ cần xem"), { target: { value: release.id } });
  return screen.findByLabelText("Chữ hoặc mô tả đã kiểm tra");
}
afterEach(() => { cleanup(); vi.unstubAllGlobals(); readFailure = false; writes = 0; });

it("keeps unsaved idea prose when the same source request resumes", async () => {
  transport(); const resume = retained(ideas());
  fireEvent.change(screen.getByLabelText("Ý tưởng"), { target: { value: "Unsent idea prose" } });
  await resume();
  expect(screen.getByLabelText("Ý tưởng")).toHaveValue("Unsent idea prose");
  expect(writes).toBe(0);
});

it.each([false, true])("keeps OCR review edits across resume when revalidation fails=%s", async failure => {
  transport(); const resume = retained(ocr());
  fireEvent.change(await openOcr(), { target: { value: "Unsent reviewed text" } });
  readFailure = failure;
  await resume();
  if (failure) await screen.findByRole("alert");
  await waitFor(() => expect(screen.getByLabelText("Chữ hoặc mô tả đã kiểm tra")).toHaveValue("Unsent reviewed text"));
  expect(writes).toBe(0);
});

it("unlocks an idea form after its write was cancelled by suspension", async () => {
  transport(); const resume = retained(ideas());
  for (const name of ["Vấn đề", "Ý tưởng", "Cách kiểm chứng"]) fireEvent.change(screen.getByLabelText(name), { target: { value: "Private draft" } });
  fireEvent.click(screen.getByRole("button", { name: "Lưu phiếu ý tưởng" }));
  await waitFor(() => expect(writes).toBe(1));
  await resume();
  expect(screen.getByLabelText("Ý tưởng")).toBeEnabled();
  expect(screen.getByLabelText("Ý tưởng")).toHaveValue("Private draft");
  expect(writes).toBe(1);
});

it("unlocks OCR controls after a cancelled request without replaying it", async () => {
  transport(); const resume = retained(ocr());
  const start = await screen.findByRole("button", { name: "Yêu cầu OCR" });
  fireEvent.click(start);
  await waitFor(() => expect(writes).toBe(1));
  await resume();
  expect(screen.getByRole("button", { name: "Yêu cầu OCR" })).toBeEnabled();
  expect(writes).toBe(1);
});

it("unlocks a private exit answer after cancellation and preserves the answer", async () => {
  transport(); const resume = retained(exit());
  const answer = await screen.findByLabelText(/Câu trả lời riêng/);
  await waitFor(() => expect(answer).toBeEnabled());
  fireEvent.change(answer, { target: { value: "Unsent answer" } });
  fireEvent.click(screen.getByRole("button", { name: "Nộp câu trả lời" }));
  await waitFor(() => expect(writes).toBe(1));
  await resume();
  expect(screen.getByLabelText(/Câu trả lời riêng/)).toBeEnabled();
  expect(screen.getByLabelText(/Câu trả lời riêng/)).toHaveValue("Unsent answer");
  expect(screen.getByRole("button", { name: "Kiểm tra biên nhận" })).toBeEnabled();
  expect(writes).toBe(1);
});
