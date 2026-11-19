import React from "react";
import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { LearningWorkspace } from "./LearningWorkspace";

const api = vi.hoisted(() => ({ capabilities: vi.fn(), offerings: vi.fn(), sessions: vi.fn(), materials: vi.fn(), list: vi.fn(), request: vi.fn(), write: vi.fn() }));
vi.mock("../../lib/data/api/learning-gateway", () => ({ LearningGateway: class {
  capabilities = api.capabilities; offerings = api.offerings; sessions = api.sessions; materials = api.materials;
  list = api.list; request = api.request; write = api.write;
}, LearningApiError: class extends Error {} }));
vi.mock("../../components/AppShell", () => ({ AppShell: ({ children }: { children: React.ReactNode }) => <div>{children}</div> }));
vi.mock("./reader/LearningPdfReader", () => ({ LearningPdfReader: () => null }));
vi.mock("./ReadingInstructions", () => ({ ReadingInstructions: () => null }));
vi.mock("./LearningNotifications", () => ({ LearningNotifications: () => null }));
afterEach(() => { cleanup(); vi.resetAllMocks(); vi.unstubAllGlobals(); });

it("tells an instructor a version is quarantined and offers neither opening nor publishing it", async () => {
  vi.stubGlobal("BroadcastChannel", undefined);
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ user_id: "teacher", roles: ["LECTURER"] }))));
  api.capabilities.mockResolvedValue({ available: true });
  api.offerings.mockResolvedValue([{ id: "offering", title: "Synthetic class", status: "ACTIVE", capabilities: { read: true, manage: true } }]);
  api.sessions.mockResolvedValue([{ id: "session", title: "Synthetic session", sequence_no: 1, starts_at: null }]);
  api.materials.mockResolvedValue([{ id: "material", title: "Bài thử", visibility: "VISIBLE", current_published_version_id: "v1",
    versions: [
      { id: "v1", version_no: 1, processing_state: "READY", publication_state: "PUBLISHED" },
      { id: "v2", version_no: 2, processing_state: "READY", publication_state: "QUARANTINED" },
    ] }]);
  api.list.mockResolvedValue([]);
  api.request.mockResolvedValue({});
  render(<LearningWorkspace />);
  await screen.findByRole("heading", { name: "Synthetic session" });
  const quarantined = (await screen.findByText(/Phiên bản 2 · Sẵn sàng · Đã cách ly/)).closest("div") as HTMLElement;
  expect(within(quarantined).getByRole("alert")).toHaveTextContent("không vượt qua kiểm tra an toàn");
  expect(within(quarantined).queryByRole("button", { name: "Xem trước" })).toBeNull();
  expect(within(quarantined).queryByRole("button", { name: "Mở" })).toBeNull();
  expect(within(quarantined).queryByRole("button", { name: "Công bố" })).toBeNull();
  const published = screen.getByText(/Phiên bản 1 · Sẵn sàng · Đã công bố/).closest("div") as HTMLElement;
  expect(within(published).getByRole("button", { name: "Mở" })).toBeInTheDocument();
  expect(within(published).getByRole("button", { name: "Thu hồi" })).toBeInTheDocument();
});
