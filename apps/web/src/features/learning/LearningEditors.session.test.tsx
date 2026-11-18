import React from "react";
import "@testing-library/jest-dom/vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { PageExplanations } from "./PageExplanations";
import { VersionChangeBanner } from "./VersionChanges";
import { PreservedActivity } from "./learning-session";
import type { LearningMaterial } from "../../lib/data/api/learning-gateway";

const versionId = "00000000-0000-4000-8000-000000000002";
const materials: LearningMaterial[] = [{ id: "material", offering_id: "offering", title: "Synthetic source", description: "",
  visibility: "VISIBLE", revision: 1, current_published_version_id: versionId, versions: [{ id: versionId,
    version_no: 1, processing_state: "READY", publication_state: "PUBLISHED", page_count: 3, has_text_layer: true, revision: 1 }] }];
const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });
function retained(child: React.ReactNode) {
  const view = render(<PreservedActivity mode="visible">{child}</PreservedActivity>);
  return async () => {
    await act(async () => view.rerender(<PreservedActivity mode="hidden">{child}</PreservedActivity>));
    await act(async () => view.rerender(<PreservedActivity mode="visible">{child}</PreservedActivity>));
  };
}
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it.each([false, true])("keeps an explanation draft when a suspended write resolves late=%s", async late => {
  let finish: (() => void) | undefined;
  let writes = 0;
  vi.stubGlobal("fetch", vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
    if (!init?.method) return json({ items: [] });
    writes++;
    return new Promise<Response>((resolve, reject) => {
      finish = () => resolve(json({}));
      if (!late) init.signal?.addEventListener("abort", () => reject(new DOMException("Cancelled", "AbortError")), { once: true });
    });
  }));
  const resume = retained(<PageExplanations actorId="teacher" sessionId="session" materials={materials} canManage
    onPublish={vi.fn()} onOpen={vi.fn()} />);
  fireEvent.change(screen.getByLabelText("Phiên bản nguồn"), { target: { value: versionId } });
  fireEvent.change(screen.getByLabelText("Nội dung lời giải"), { target: { value: "Private unfinished explanation" } });
  fireEvent.click(screen.getByRole("button", { name: "Lưu bản nháp lời giải" }));
  await waitFor(() => expect(writes).toBe(1));
  await resume();
  if (late) await act(async () => finish?.());
  expect(screen.getByLabelText("Nội dung lời giải")).toBeEnabled();
  expect(screen.getByLabelText("Nội dung lời giải")).toHaveValue("Private unfinished explanation");
  expect(writes).toBe(1);
});

it("recovers the version-change banner after a transient read failure and session revalidation", async () => {
  let reads = 0;
  vi.stubGlobal("fetch", vi.fn(async () => ++reads === 1 ? json({}, 503) : json({ change_set: {
    base_available: true, base_version_id: "base", base_version_no: 1, target_version_id: versionId,
    target_version_no: 2, mode: "WHOLE_DOCUMENT", reason: "Recovered source description", target_guidance: "", items: [],
  } })));
  const resume = retained(<VersionChangeBanner actorId="student" versionId={versionId} onOpen={vi.fn()} />);
  await screen.findByText("Chưa đọc được mô tả thay đổi.");
  await resume();
  await screen.findByText("Trang thay đổi trong phiên bản này");
  expect(screen.queryByText("Chưa đọc được mô tả thay đổi.")).toBeNull();
});
