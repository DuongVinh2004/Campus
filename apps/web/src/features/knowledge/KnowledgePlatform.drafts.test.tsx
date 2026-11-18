import React from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { KnowledgePlatform } from "./KnowledgePlatform";

vi.mock("../../components/AppShell", () => ({ AppShell: ({ children }: { children: React.ReactNode }) => <>{children}</> }));
vi.mock("./KnowledgeIntake", () => ({ KnowledgeIntake: ({ onResolved }: { onResolved: (id: string) => void }) => <>
  <button onClick={() => onResolved("A")}>Open intake A</button><button onClick={() => onResolved("B")}>Open intake B</button>
</> }));

const original = (id: string) => `Original ${id} complete prose including its exception.`;
let holdA = false;
let finishA: (() => void) | undefined;
let holdReview = false;
let finishReview: (() => void) | undefined;
let requested: string[];
let currentActor = "author";
let switchDuringState = false;
const json = (value: unknown) => new Response(JSON.stringify(value));
beforeEach(() => {
  holdA = false; finishA = undefined; holdReview = false; finishReview = undefined; requested = [];
  currentActor = "author";
  switchDuringState = false;
  vi.stubGlobal("fetch", vi.fn(async (input: string, init?: RequestInit) => {
    const url = String(input);
    requested.push(url);
    if (url.endsWith("/corrections/proposal-A/reviews") && init?.method === "POST") {
      return new Promise<Response>(resolve => { finishReview = () => resolve(json({ version_id: "C" })); });
    }
    if (url.endsWith("/corrections/proposal-A")) return json({ correction_id: "proposal-A", created_by: "another-author", proposal_sha256: "d".repeat(64), revision: 0, intake_id: "intake-A",
      pages: [{ page: 1, text: original("A"), expected_page_sha256: "a".repeat(64), preview_image_sha256: "b".repeat(64) }], note: "Full source comparison proposal." });
    if (url.endsWith("/users/me")) return json({ user_id: currentActor, roles: ["KNOWLEDGE_ADMIN"] });
    if (url.endsWith("/state")) {
      if (switchDuringState) currentActor = "another-account";
      return json({ correction_history_available: true, mode: "postgres_bge",
      sources: ["A", "B"].map(id => ({ id, title: `Source ${id}`, canonical_uri: `urn:${id}` })),
      versions: ["A", "B"].map(id => ({ version_id: id, source_id: id, filename: `${id}.pdf`, created_by: "author", revision: 1,
        review_state: "DRAFT", publication_state: "DRAFT", original_sha256: id, rendition_sha256: id, revoked_at: null, index_version: "fixture-index", effective_from: null })),
      jobs: [], desired: { release_id: null, generation: 0, policy_generation: 0 }, is_serving: false, serving: [], runtime: [], releases: [] });
    }
    const id = url.includes("/versions/B/") ? "B" : "A";
    if (url.endsWith("/rendition")) {
      const value = () => json({ pages: [{ page: 1, text: original(id) }], issues: [] });
      if (holdA && id === "A") return new Promise<Response>(resolve => { finishA = () => resolve(value()); });
      return value();
    }
    if (url.endsWith("/correction-preview")) return json({ expected_revision: 1, expected_rendition_sha256: "c".repeat(64), intake_id: `intake-${id}`,
      pages: [{ page: 1, text: original(id), expected_page_sha256: "a".repeat(64), preview_image_sha256: "b".repeat(64) }] });
    if (url.endsWith("/corrections")) return json({ items: holdReview && id === "A" ? [{ id: "proposal-A", created_by: "another-author", revision: 0, proposal_sha256: "d".repeat(64), version_id: null }] : [] });
    return json({});
  }));
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
async function choose(id: string) {
  fireEvent.click(await screen.findByRole("button", { name: new RegExp(`^Source ${id} ${id}\\.pdf`) }));
  await screen.findByRole("heading", { name: `Source ${id}` });
  await waitFor(() => expect(screen.getByRole("button", { name: new RegExp(`^Source ${id} ${id}\\.pdf`) })).not.toBeDisabled());
}

it("keeps independent correction text, reason and comparison confirmation for each document", async () => {
  render(<KnowledgePlatform />); await choose("A");
  fireEvent.click(screen.getByRole("button", { name: "Sửa chữ/OCR bằng bản mới" }));
  fireEvent.change(await screen.findByRole("textbox", { name: "Toàn bộ chữ của trang đã đối chiếu" }), { target: { value: "Unsent correction A with exception retained." } });
  fireEvent.change(screen.getByRole("textbox", { name: "Căn cứ đề xuất sửa" }), { target: { value: "Private source A comparison reason." } });
  fireEvent.click(screen.getByRole("checkbox", { name: /Tôi đã đối chiếu chữ với đúng ảnh/ }));
  await choose("B");
  fireEvent.click(screen.getByRole("button", { name: "Sửa chữ/OCR bằng bản mới" }));
  expect(await screen.findByRole("textbox", { name: "Toàn bộ chữ của trang đã đối chiếu" })).toHaveValue(original("B"));
  fireEvent.change(screen.getByRole("textbox", { name: "Toàn bộ chữ của trang đã đối chiếu" }), { target: { value: "Unsent correction B with exception retained." } });
  await choose("A");
  expect(screen.getByRole("textbox", { name: "Toàn bộ chữ của trang đã đối chiếu" })).toHaveValue("Unsent correction A with exception retained.");
  expect(screen.getByRole("textbox", { name: "Căn cứ đề xuất sửa" })).toHaveValue("Private source A comparison reason.");
  expect(screen.getByRole("checkbox", { name: /Tôi đã đối chiếu chữ với đúng ảnh/ })).toBeChecked();
  await choose("B");
  expect(screen.getByRole("textbox", { name: "Toàn bộ chữ của trang đã đối chiếu" })).toHaveValue("Unsent correction B with exception retained.");
});

it("retains review and applicability drafts separately instead of clearing them on navigation", async () => {
  render(<KnowledgePlatform />); await choose("A");
  fireEvent.change(screen.getByLabelText("Ghi chú đối chiếu original và rendition"), { target: { value: "Unsent review A" } });
  fireEvent.click(screen.getByText("Bổ sung hiệu lực bằng phiên bản mới"));
  fireEvent.change(screen.getByLabelText("Ngày bắt đầu đã xác minh"), { target: { value: "2026-11-11T09:00" } });
  fireEvent.change(screen.getByLabelText("Căn cứ trong văn bản"), { target: { value: "Unsent applicability basis A" } });
  await choose("B");
  expect(screen.getByLabelText("Ghi chú đối chiếu original và rendition")).toHaveValue("");
  fireEvent.change(screen.getByLabelText("Ghi chú đối chiếu original và rendition"), { target: { value: "Unsent review B" } });
  await choose("A");
  expect(screen.getByLabelText("Ghi chú đối chiếu original và rendition")).toHaveValue("Unsent review A");
  expect(screen.getByLabelText("Ngày bắt đầu đã xác minh")).toHaveValue("2026-11-11T09:00");
  expect(screen.getByLabelText("Căn cứ trong văn bản")).toHaveValue("Unsent applicability basis A");
});

it("ignores a late rendition from an earlier intake selection", async () => {
  holdA = true;
  render(<KnowledgePlatform />);
  await screen.findByText("Upload tài liệu");
  fireEvent.click(screen.getByRole("button", { name: "Open intake A" }));
  await waitFor(() => expect(finishA).toBeDefined());
  fireEvent.click(screen.getByRole("button", { name: "Open intake B" }));
  await screen.findByText(original("B"));
  await act(async () => { finishA!(); });
  expect(screen.getByRole("heading", { name: "Source B" })).toBeVisible();
  expect(screen.getByText(original("B"))).toBeVisible();
  expect(screen.queryByText(original("A"))).toBeNull();
});

it("keeps the selected document when an earlier document's review finishes in the background", async () => {
  holdReview = true;
  render(<KnowledgePlatform />); await choose("A");
  fireEvent.click(screen.getByRole("button", { name: "Sửa chữ/OCR bằng bản mới" }));
  fireEvent.click(await screen.findByRole("button", { name: "Mở đề xuất để đối chiếu" }));
  fireEvent.change(await screen.findByRole("textbox", { name: "Ghi nhận đối chiếu độc lập" }), { target: { value: "Checked the original page including every exception." } });
  fireEvent.change(screen.getByRole("combobox", { name: "Kết luận" }), { target: { value: "APPROVED" } });
  fireEvent.click(screen.getByRole("checkbox", { name: /Tôi đã đối chiếu toàn trang/ }));
  fireEvent.submit(screen.getByRole("button", { name: "Ghi quyết định độc lập" }).closest("form")!);
  await waitFor(() => expect(finishReview).toBeDefined());
  await choose("B");
  await act(async () => { finishReview!(); });
  expect(screen.getByRole("heading", { name: "Source B" })).toBeVisible();
  expect(requested.some(url => url.includes("/versions/C/rendition"))).toBe(false);
});

it("does not replace the tab's actor and unmount private form fields during background refresh under another account", async () => {
  render(<KnowledgePlatform />); await choose("A");
  fireEvent.click(screen.getByRole("button", { name: "Sửa chữ/OCR bằng bản mới" }));
  await screen.findByRole("textbox", { name: "Căn cứ đề xuất sửa" });
  fireEvent.change(screen.getByRole("textbox", { name: "Căn cứ đề xuất sửa" }), { target: { value: "Unsent source comparison reason A" } });
  fireEvent.click(screen.getByRole("checkbox", { name: /Tôi đã đối chiếu chữ với đúng ảnh/ }));
  currentActor = "another-account";
  await choose("B");
  currentActor = "author";
  await choose("A");
  expect(screen.getByRole("textbox", { name: "Căn cứ đề xuất sửa" })).toHaveValue("Unsent source comparison reason A");
  expect(screen.getByRole("checkbox", { name: /Tôi đã đối chiếu chữ với đúng ảnh/ })).toBeChecked();
});

it("does not publish the source snapshot if the account changes while it is loading", async () => {
  switchDuringState = true;
  render(<KnowledgePlatform />);
  await waitFor(() => expect(requested.filter(url => url.endsWith("/users/me")).length).toBeGreaterThanOrEqual(2));
  expect(screen.queryByRole("button", { name: /^Source A A\.pdf/ })).toBeNull();
  expect(screen.queryByText("Upload tài liệu")).toBeNull();
});
