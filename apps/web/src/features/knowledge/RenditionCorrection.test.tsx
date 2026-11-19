import React from "react";
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";
import { RenditionCorrection } from "./RenditionCorrection";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
const page = { page: 1, text: "Original complete prose including its exception.", expected_page_sha256: "a".repeat(64), preview_image_sha256: "b".repeat(64) };

it("preserves source revision and page/image hashes and asks for independent review", async () => {
  let body: Record<string, unknown> | null = null;
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === "POST") { body = JSON.parse(String(init.body)); return new Response(JSON.stringify({ correction_id: "proposal" })); }
    return new Response(JSON.stringify(url.endsWith("correction-preview") ? { expected_revision: 3, expected_rendition_sha256: "c".repeat(64), intake_id: "intake", pages: [page] } : { items: [] }));
  }));
  render(<RenditionCorrection versionId="version" actorId="author" authorId="author" onCreated={vi.fn()} />);
  fireEvent.click(screen.getByRole("button", { name: "Sửa chữ/OCR bằng bản mới" }));
  await screen.findByLabelText("Toàn bộ chữ của trang đã đối chiếu");
  const checkbox = screen.getByRole("checkbox", { name: /Tôi đã đối chiếu chữ với đúng ảnh/ });
  expect(checkbox).not.toBeChecked(); expect(checkbox).toBeRequired();
  fireEvent.change(screen.getByLabelText("Toàn bộ chữ của trang đã đối chiếu"), { target: { value: "Corrected complete prose including its exception." } });
  fireEvent.change(screen.getByLabelText("Căn cứ đề xuất sửa"), { target: { value: "Compared the original full page and all exception clauses." } });
  fireEvent.click(checkbox);
  fireEvent.submit(screen.getByRole("button", { name: "Lưu đề xuất để người khác đối chiếu" }).closest("form")!);
  await screen.findByText(/Cần người khác đối chiếu độc lập/);
  expect(body).toMatchObject({ expected_revision: 3, expected_rendition_sha256: "c".repeat(64), confirmed_source_comparison: true,
    pages: [{ ...page, text: "Corrected complete prose including its exception." }] });
});

it("does not offer self approval and lets an independent reviewer reject without asserting prose coverage", async () => {
  let submitted: Record<string, unknown> | null = null;
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === "POST") { submitted = JSON.parse(String(init.body)); return new Response(JSON.stringify({ verdict: "REJECTED" })); }
    if (url.endsWith("correction-preview")) return new Response(JSON.stringify({ expected_revision: 1, expected_rendition_sha256: "c".repeat(64), intake_id: "intake", pages: [page] }));
    if (url.endsWith("/corrections")) return new Response(JSON.stringify({ items: [{ id: "proposal", created_by: "author", revision: 0, proposal_sha256: "d".repeat(64), version_id: null }] }));
    return new Response(JSON.stringify({ correction_id: "proposal", created_by: "author", proposal_sha256: "d".repeat(64), revision: 0, intake_id: "intake", pages: [page], note: "Original proposal note." }));
  }));
  const first = render(<RenditionCorrection versionId="version" actorId="author" authorId="author" onCreated={vi.fn()} />);
  fireEvent.click(screen.getByRole("button", { name: "Sửa chữ/OCR bằng bản mới" }));
  fireEvent.click(await screen.findByRole("button", { name: "Mở đề xuất để đối chiếu" }));
  await screen.findByText(/Người đề xuất không được tự duyệt/);
  expect(screen.queryByRole("button", { name: "Ghi quyết định độc lập" })).toBeNull();
  first.unmount();
  render(<RenditionCorrection versionId="version" actorId="reviewer" authorId="author" onCreated={vi.fn()} />);
  fireEvent.click(screen.getByRole("button", { name: "Sửa chữ/OCR bằng bản mới" }));
  fireEvent.click(await screen.findByRole("button", { name: "Mở đề xuất để đối chiếu" }));
  const confirm = await screen.findByRole("checkbox", { name: /Tôi đã đối chiếu toàn trang/ });
  expect(confirm).not.toBeRequired(); expect(confirm).not.toBeChecked();
  fireEvent.change(screen.getByLabelText("Ghi nhận đối chiếu độc lập"), { target: { value: "Cannot verify the table or its shared exception from prose alone." } });
  fireEvent.submit(screen.getByRole("button", { name: "Ghi quyết định độc lập" }).closest("form")!);
  await waitFor(() => expect(submitted).toMatchObject({ verdict: "REJECTED", coverage: null, confirmed_full_page_and_conditions: false,
    expected_revision: 0, expected_proposal_sha256: "d".repeat(64) }));
});
