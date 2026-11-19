import React from "react";
import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
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

it("keeps one feedback and explanation section across session revalidation with both modules enabled", async () => {
  vi.stubGlobal("BroadcastChannel", undefined);
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ user_id: "teacher", roles: ["LECTURER"] }))));
  api.capabilities.mockResolvedValue({ available: true });
  api.offerings.mockResolvedValue([{ id: "offering", title: "Synthetic class", status: "ACTIVE", capabilities: {
    read: true, manage: true, page_feedback: true, page_explanations: true,
  } }]);
  api.sessions.mockResolvedValue([{ id: "session", title: "Synthetic session", sequence_no: 1, starts_at: null }]);
  api.materials.mockResolvedValue([]);
  api.list.mockResolvedValue([]);
  api.request.mockResolvedValue({ state: "WAITING", closes_at: "2099-01-01T00:00:00Z", pages: [] });
  render(<LearningWorkspace />);
  await screen.findByRole("heading", { name: "Synthetic session" });
  for (let index = 0; index < 3; index++) {
    fireEvent(window, new Event("focus"));
    await waitFor(() => expect(screen.getAllByRole("region", { name: "Báo vướng theo buổi" })).toHaveLength(1));
    expect(screen.getAllByRole("region", { name: "Lời giải chung theo buổi" })).toHaveLength(1);
  }
  expect(api.write).not.toHaveBeenCalled();
});
