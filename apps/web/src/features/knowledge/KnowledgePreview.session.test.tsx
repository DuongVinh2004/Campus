import React from "react";
import "@testing-library/jest-dom/vitest";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { RenditionCorrection } from "./RenditionCorrection";
import { KnowledgeIntake } from "./KnowledgeIntake";
import { PreservedActivity } from "../learning/learning-session";

const json = (value: unknown) => new Response(JSON.stringify(value));
const page = { page: 1, text: "Complete original source text and its exception.", expected_page_sha256: "a".repeat(64), preview_image_sha256: "b".repeat(64) };
function urls() {
  const active = new Map<string, Blob>();
  let serial = 0;
  vi.stubGlobal("URL", class extends URL {
    static createObjectURL(blob: Blob) { const url = `blob:preview-${++serial}`; active.set(url, blob); return url; }
    static revokeObjectURL(url: string) { active.delete(url); }
  });
  return active;
}
function component(kind: string) {
  return kind === "correction" ? <RenditionCorrection versionId="version" actorId="author" authorId="author" onCreated={vi.fn()} />
    : <KnowledgeIntake onResolved={vi.fn()} />;
}
function response(path: string) {
  if (path.endsWith("correction-preview")) return json({ expected_revision: 1, expected_rendition_sha256: "c".repeat(64), intake_id: "intake", pages: [page] });
  return json({ items: path.endsWith("/intakes") ? [{ id: "intake", filename: "fixture.pdf", state: "NEEDS_INFORMATION", stage: "METADATA_REVIEW",
    progress: 40, job_id: "job", observed_at: "2026-11-09T00:00:00Z", revision: 1, hints: {},
    issues: [{ id: "metadata", code: "SOURCE_METADATA_REQUIRED", fields: [], evidence: { preview_pages: [1] } }] }] : [] });
}
async function open(kind: string) {
  if (kind === "correction") fireEvent.click(screen.getByRole("button", { name: "Sửa chữ/OCR bằng bản mới" }));
  const imageButton = await screen.findByRole("button", { name: kind === "correction" ? "Mở ảnh trang cần sửa" : "Xem ảnh đối chiếu trang 1" });
  fireEvent.click(imageButton);
}
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it.each(["correction", "intake"])("keeps the %s source image usable when session validation resumes", async kind => {
  const active = urls();
  vi.stubGlobal("fetch", vi.fn(async (path: string) => path.endsWith("/preview") ? new Response(new Blob(["image"], { type: "image/png" })) : response(path)));
  const child = component(kind);
  const view = render(<PreservedActivity mode="visible">{child}</PreservedActivity>);
  await open(kind);
  const image = await screen.findByRole("img");
  expect(active.has(image.getAttribute("src")!)).toBe(true);
  if (kind === "correction") fireEvent.change(screen.getByLabelText("Toàn bộ chữ của trang đã đối chiếu"), { target: { value: "Unsent source correction with its exception intact." } });
  await act(async () => view.rerender(<PreservedActivity mode="hidden">{child}</PreservedActivity>));
  await act(async () => view.rerender(<PreservedActivity mode="visible">{child}</PreservedActivity>));
  expect(active.has(screen.getByRole("img").getAttribute("src")!)).toBe(true);
  if (kind === "correction") expect(screen.getByLabelText("Toàn bộ chữ của trang đã đối chiếu")).toHaveValue("Unsent source correction with its exception intact.");
  view.unmount();
  expect(active.size).toBe(0);
});

it("does not allocate an orphaned preview URL when an image response arrives while hidden", async () => {
  const active = urls();
  let finish!: () => void;
  vi.stubGlobal("fetch", vi.fn(async (path: string) => path.endsWith("/preview")
    ? new Promise<Response>(resolve => { finish = () => resolve(new Response(new Blob(["image"]))); }) : response(path)));
  const child = component("correction");
  const view = render(<PreservedActivity mode="visible">{child}</PreservedActivity>);
  await open("correction");
  await act(async () => view.rerender(<PreservedActivity mode="hidden">{child}</PreservedActivity>));
  await act(async () => finish());
  expect(active.size).toBe(0);
  view.unmount();
  expect(active.size).toBe(0);
});
