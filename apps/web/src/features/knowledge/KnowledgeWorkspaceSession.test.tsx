import React from "react";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { KnowledgeWorkspaceSession } from "./KnowledgeWorkspaceSession";
import { ChatDraftSessionProvider } from "../chat/route-drafts";

const route = vi.hoisted(() => ({ path: "/knowledge/sources" }));
vi.mock("next/navigation", () => ({ usePathname: () => route.path }));
const originalActor = { user_id: "knowledge-owner", display_name: "Synthetic knowledge owner", roles: ["KNOWLEDGE_ADMIN"] };
let actor = originalActor;
let expired = false;
let holdIdentity = false;
let identityReplies: Array<() => void>;
let finishPreview: (() => void) | undefined;
let holdPreview = false;
const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });
const preview = { preview_id: "synthetic-preview", confirmation_token: "synthetic-confirmation", expires_at: "2030-01-01T00:00:00Z",
  payload: { operation: "activate", target_id: "release", generation: 27, members: [] } };
const state = { mode: "postgres_bge", session_schedules_available: true,
  sources: [{ id: "A", title: "Source A", canonical_uri: "urn:synthetic:A" }],
  versions: [{ version_id: "A", source_id: "A", filename: "A.pdf", created_by: "other-author", revision: 1,
    review_state: "DRAFT", publication_state: "DRAFT", original_sha256: "a", rendition_sha256: "b", revoked_at: null, index_version: "fixture" }],
  jobs: [], desired: { release_id: "release", generation: 27, policy_generation: 3 }, is_serving: true,
  serving: [], runtime: [], releases: [{ id: "release", document_count: 1, membership_sha256: "hash" }] };
const view = () => <ChatDraftSessionProvider><KnowledgeWorkspaceSession><p>Another route</p></KnowledgeWorkspaceSession></ChatDraftSessionProvider>;
const input = (name: string) => screen.getByLabelText(name) as HTMLInputElement;
const edit = (name: string, value: string) => fireEvent.change(input(name), { target: { value } });
async function open() { await screen.findByText("Upload tài liệu"); await screen.findByRole("link", { name: "Đổi tài khoản: Synthetic knowledge owner" }); }
async function navigate(instance: ReturnType<typeof render>, path: string) {
  route.path = path; await act(async () => instance.rerender(view()));
}
beforeEach(() => {
  route.path = "/knowledge/sources"; actor = originalActor; expired = false; holdIdentity = false;
  identityReplies = []; finishPreview = undefined; holdPreview = false;
  vi.stubEnv("NEXT_PUBLIC_KNOWLEDGE_PLATFORM", "true");
  vi.stubGlobal("BroadcastChannel", undefined);
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const path = String(input);
    if (path.endsWith("/users/me")) {
      const respond = () => expired ? json({}, 401) : json(actor);
      return holdIdentity ? new Promise(resolve => { identityReplies.push(() => resolve(respond())); }) : respond();
    }
    if (path.endsWith("/state")) return json(state);
    if (path.endsWith("/intakes")) return json({ items: [] });
    if (path.endsWith("/schedules")) return json({ session_expires_at: "2030-01-01T00:00:00Z", background_running: true, items: [] });
    if (path.endsWith("/rendition")) return json({ pages: [{ page: 1, text: "Original A" }], issues: [] });
    if (path.endsWith("/previews") && init?.method === "POST") return holdPreview
      ? new Promise(resolve => { finishPreview = () => resolve(json(preview)); }) : json(preview);
    throw new Error("Unexpected synthetic request: " + path);
  });
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); vi.unstubAllEnvs(); });

it("does not load knowledge administration before the route is visited", async () => {
  route.path = "/chat"; const instance = render(view());
  expect(screen.getByText("Another route")).toBeVisible(); expect(fetch).not.toHaveBeenCalled();
  await navigate(instance, "/knowledge/sources"); await open();
  expect(screen.queryByText("Another route")).toBeNull();
});

it("retains upload, intake and verification fields without posting during route changes", async () => {
  const instance = render(view()); await open();
  edit("Tên tài liệu", "Unsent source title"); edit("Đơn vị ban hành", "Unsent publisher"); edit("URI gốc / xuất xứ", "https://unsent.example");
  edit("URL xuất xứ nếu biết", "https://huce.edu.vn/unsent-origin");
  edit("Hoặc URL tài liệu công khai HUCE", "https://huce.edu.vn/unsent-fetch"); edit("Câu hỏi kiểm chứng", "Unsent verification");
  await navigate(instance, "/chat"); expect(screen.queryByRole("heading", { name: "Kho tri thức RAG" })).toBeNull();
  await navigate(instance, "/knowledge/sources"); await open();
  expect(input("Tên tài liệu")).toHaveValue("Unsent source title"); expect(input("Đơn vị ban hành")).toHaveValue("Unsent publisher");
  expect(input("URI gốc / xuất xứ")).toHaveValue("https://unsent.example");
  expect(input("URL xuất xứ nếu biết")).toHaveValue("https://huce.edu.vn/unsent-origin");
  expect(input("Hoặc URL tài liệu công khai HUCE")).toHaveValue("https://huce.edu.vn/unsent-fetch");
  expect(input("Câu hỏi kiểm chứng")).toHaveValue("Unsent verification");
  expect(vi.mocked(fetch).mock.calls.some(([, init]) => init?.method === "POST")).toBe(false);
});

it("preserves the real file input and selected File reference in tab memory", async () => {
  const instance = render(view()); await open();
  const file = new File(["Synthetic document"], "unsent-fixture.txt", { type: "text/plain" });
  const fileInput = input("File PDF/TXT UTF-8"); fireEvent.change(fileInput, { target: { files: [file] } });
  await navigate(instance, "/privacy"); await navigate(instance, "/knowledge/sources"); await open();
  expect(input("File PDF/TXT UTF-8")).toBe(fileInput); expect(input("File PDF/TXT UTF-8").files?.[0]).toBe(file);
});

it("retains document selection, review notes, applicability and schedule inputs together", async () => {
  const instance = render(view()); await open();
  fireEvent.click(screen.getByRole("button", { name: /^Source A A.pdf/ })); await screen.findByText("Original A");
  edit("Ghi chú đối chiếu original và rendition", "Private review note A");
  fireEvent.click(screen.getByText("Bổ sung hiệu lực bằng phiên bản mới"));
  edit("Ngày bắt đầu đã xác minh", "2026-11-11T09:00"); edit("Căn cứ trong văn bản", "Private verified applicability basis A");
  edit("Bắt đầu theo dõi", "2026-11-12T10:00");
  await navigate(instance, "/chat"); await navigate(instance, "/knowledge/sources"); await open();
  expect(input("Ghi chú đối chiếu original và rendition")).toHaveValue("Private review note A");
  expect(input("Ngày bắt đầu đã xác minh")).toHaveValue("2026-11-11T09:00");
  expect(input("Căn cứ trong văn bản")).toHaveValue("Private verified applicability basis A");
  expect(input("Bắt đầu theo dõi")).toHaveValue("2026-11-12T10:00");
});

it.each(["account", "roles", "expired"])("conceals retained forms before revalidating a resumed %s session", async change => {
  const instance = render(view()); await open(); edit("Tên tài liệu", "Original private source draft");
  await navigate(instance, "/chat");
  if (change === "account") actor = { ...originalActor, user_id: "different-user" };
  if (change === "roles") actor = { ...originalActor, roles: ["STUDENT"] };
  if (change === "expired") expired = true;
  holdIdentity = true; await navigate(instance, "/knowledge/sources");
  expect(screen.queryByRole("textbox", { name: "Tên tài liệu" })).toBeNull();
  await waitFor(() => expect(identityReplies.length).toBeGreaterThan(0));
  await act(async () => { holdIdentity = false; identityReplies.splice(0).forEach(reply => reply()); });
  await screen.findByText(change === "account" ? /Tài khoản đăng nhập đã thay đổi/
    : change === "roles" ? /Quyền truy cập của tài khoản đã thay đổi/ : /Phiên đăng nhập đã hết hạn. Nội dung riêng/);
  expect(screen.queryByRole("textbox", { name: "Tên tài liệu" })).toBeNull();
  actor = originalActor; expired = false;
  fireEvent.click(screen.getByRole("button", { name: "Kiểm tra lại tài khoản" }));
  expect(await screen.findByRole("textbox", { name: "Tên tài liệu" })).toHaveValue("Original private source draft");
});

it("retains an in-flight preview and never confirms or repeats it when the route resumes", async () => {
  holdPreview = true; const instance = render(view()); await open();
  fireEvent.change(screen.getByLabelText("Release"), { target: { value: "release" } });
  fireEvent.click(screen.getByRole("button", { name: "Xem trước xuất bản" }));
  await waitFor(() => expect(finishPreview).toBeTypeOf("function"));
  await navigate(instance, "/chat"); await navigate(instance, "/knowledge/sources"); await open();
  expect(screen.getByRole("button", { name: "Xem trước xuất bản" })).toBeDisabled();
  await act(async () => finishPreview!()); await screen.findByText("Xác nhận activate");
  expect(vi.mocked(fetch).mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(1);
  expect(vi.mocked(fetch).mock.calls.some(([path]) => String(path).endsWith("/confirmations"))).toBe(false);
});
