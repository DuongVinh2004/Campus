import React from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, isInaccessible, render, screen } from "@testing-library/react";
import { LearningWorkspace } from "./LearningWorkspace";

const api = vi.hoisted(() => ({ capabilities: vi.fn(), offerings: vi.fn(), sessions: vi.fn(), materials: vi.fn(), reader: vi.fn(), list: vi.fn(), request: vi.fn(), write: vi.fn() }));
vi.mock("../../lib/data/api/learning-gateway", () => ({ LearningGateway: class {
  capabilities = api.capabilities; offerings = api.offerings; sessions = api.sessions; materials = api.materials;
  reader = api.reader; list = api.list; request = api.request; write = api.write;
}, LearningApiError: class extends Error {} }));
vi.mock("../../components/AppShell", () => ({ AppShell: ({ children }: { children: React.ReactNode }) => <div>{children}</div> }));
vi.mock("./reader/LearningPdfReader", () => ({ LearningPdfReader: () => <div>PDF fixture</div> }));
vi.mock("./ReadingInstructions", () => ({ ReadingInstructions: () => null }));
vi.mock("./LearningPresentation", () => ({ LearningPresentation: () => null }));
vi.mock("./LearningNotifications", () => ({ LearningNotifications: () => null }));

const actor = "019a0000-0000-7000-8000-000000000001";
const version = "019a0000-0000-7000-8000-000000000002";
const session = "019a0000-0000-7000-8000-000000000003";
const offering = "019a0000-0000-7000-8000-000000000004";
let currentActor = actor;
beforeEach(() => {
  currentActor = actor;
  vi.stubGlobal("BroadcastChannel", undefined);
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ user_id: currentActor, roles: ["STUDENT"] }))));
  api.capabilities.mockResolvedValue({ available: true });
  api.offerings.mockResolvedValue([{ id: offering, title: "Lớp thử", status: "ACTIVE", capabilities: { read: true, manage: false } }]);
  api.sessions.mockResolvedValue([{ id: session, title: "Buổi thử", sequence_no: 1 }]);
  api.materials.mockResolvedValue([{ id: version, title: "Bài thử", visibility: "VISIBLE", current_published_version_id: version,
    versions: [{ id: version, version_no: 1, processing_state: "READY", publication_state: "PUBLISHED" }] }]);
  api.reader.mockResolvedValue({ id: version, version_id: version, offering_id: offering, title: "Bài thử", version_no: 1,
    publication_state: "PUBLISHED", page_count: 3, capabilities: { download: true, manage: false } });
  api.request.mockResolvedValue({ revision: 0, page_no: 2 });
  api.list.mockImplementation(async (path: string) => path.startsWith("/me/annotations") ? [{
    id: session, version_id: version, page_no: 2, anchor: { kind: "PAGE" }, body: "Saved private note", revision: 1, status: "ACTIVE",
  }] : []);
});
afterEach(() => { cleanup(); vi.resetAllMocks(); vi.unstubAllGlobals(); });

it.each(["new", "edit"])("conceals private notes on account change and preserves the %s note draft", async mode => {
  render(<LearningWorkspace />);
  fireEvent.click(await screen.findByRole("button", { name: "Đọc bài giảng" }));
  await screen.findByText("Saved private note");
  if (mode === "edit") fireEvent.click(screen.getByRole("button", { name: "Sửa ghi chú" }));
  const label = mode === "edit" ? "Sửa ghi chú" : "Nội dung ghi chú";
  fireEvent.change(screen.getByRole("textbox", { name: label }), { target: { value: "Unsent private draft" } });
  currentActor = "019a0000-0000-7000-8000-000000000009";
  fireEvent(window, new Event("focus"));
  await screen.findByText(/Tài khoản đăng nhập đã thay đổi/);
  expect(screen.queryByRole("textbox", { name: label })).toBeNull();
  expect(isInaccessible(screen.getByText("Saved private note", { selector: "p" }))).toBe(true);
  currentActor = actor;
  fireEvent.click(screen.getByRole("button", { name: "Kiểm tra lại tài khoản" }));
  expect((await screen.findByRole("textbox", { name: label }) as HTMLTextAreaElement).value).toBe("Unsent private draft");
  expect(isInaccessible(screen.getByText("Saved private note", { selector: "p" }))).toBe(false);
  expect(api.write).not.toHaveBeenCalled();
});

it("still notices a newer published version when the focus also re-checks the account", async () => {
  const newer = "019a0000-0000-7000-8000-000000000008";
  render(<LearningWorkspace />);
  fireEvent.click(await screen.findByRole("button", { name: "Đọc bài giảng" }));
  await screen.findByText("PDF fixture");
  expect(screen.queryByText("Bạn đang đọc một phiên bản khác với bản hiện hành.")).toBeNull();
  api.reader.mockResolvedValue({ id: version, version_id: version, offering_id: offering, title: "Bài thử", version_no: 1,
    publication_state: "PUBLISHED", current_published_version_id: newer, page_count: 3, capabilities: { download: true, manage: false } });
  fireEvent(window, new Event("focus"));
  expect(await screen.findByText("Bạn đang đọc một phiên bản khác với bản hiện hành.")).toBeTruthy();
  expect(screen.getByRole("button", { name: "Mở bản hiện hành" })).toBeTruthy();
});
