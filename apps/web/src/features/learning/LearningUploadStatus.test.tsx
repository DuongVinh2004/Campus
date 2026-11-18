import React from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { LearningWorkspace } from "./LearningWorkspace";

const api = vi.hoisted(() => ({ capabilities: vi.fn(), offerings: vi.fn(), sessions: vi.fn(), materials: vi.fn(), list: vi.fn(), upload: vi.fn() }));
vi.mock("../../lib/data/api/learning-gateway", () => ({ LearningGateway: class {
  capabilities = api.capabilities; offerings = api.offerings; sessions = api.sessions;
  materials = api.materials; list = api.list; upload = api.upload;
}, LearningApiError: class extends Error {} }));
vi.mock("../../components/AppShell", () => ({ AppShell: ({ children }: { children: React.ReactNode }) => <div>{children}</div> }));
vi.mock("./ReadingInstructions", () => ({ ReadingInstructions: () => null }));

const offering = "019a0000-0000-7000-8000-000000000001";
const session = "019a0000-0000-7000-8000-000000000002";
const material = "019a0000-0000-7000-8000-000000000003";
const version = "019a0000-0000-7000-8000-000000000004";
const rows = (state: string) => [{ id: material, title: "PDF kiểm thử", description: "", visibility: "VISIBLE",
  revision: 1, current_published_version_id: null,
  versions: [{ id: version, version_no: 2, processing_state: state, publication_state: "DRAFT" }] }];

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ roles: ["LECTURER"], user_id: offering }))));
  api.capabilities.mockResolvedValue({ available: true });
  api.offerings.mockResolvedValue([{ id: offering, title: "Lớp thử", status: "ACTIVE", capabilities: { read: true, manage: true } }]);
  api.sessions.mockResolvedValue([{ id: session, title: "Buổi thử", sequence_no: 1 }]);
  api.materials.mockResolvedValue(rows("READY"));
  api.list.mockResolvedValue([]);
  api.upload.mockResolvedValue({ id: version, version_no: 2, processing_state: "SCANNING" });
});
afterEach(() => { cleanup(); vi.useRealTimers(); vi.clearAllMocks(); vi.unstubAllGlobals(); });

it.each(["READY", "REJECTED"])("updates the accepted upload notice when polling reaches %s", async terminal => {
  render(<LearningWorkspace />);
  fireEvent.click(await screen.findByText("Tải phiên bản mới"));
  const file = screen.getAllByLabelText("File PDF")[0] as HTMLInputElement;
  const pdf = new File(["%PDF-synthetic"], "audit.pdf", { type: "application/pdf" });
  fireEvent.change(file, { target: { files: [pdf] } });
  // JSDOM's FormData does not read the FileList set by Testing Library.
  const NativeFormData = FormData;
  vi.stubGlobal("FormData", class extends NativeFormData {
    constructor(form?: HTMLFormElement) { super(form); if (form === file.form) this.set("file", pdf); }
  });
  api.materials.mockResolvedValue(rows("SCANNING"));
  vi.useFakeTimers({ toFake: ["setInterval", "clearInterval"] });
  fireEvent.submit(file.form!);
  await screen.findByText(/Đã nhận phiên bản 2/);
  api.materials.mockResolvedValue(rows(terminal));
  await act(async () => { await vi.advanceTimersByTimeAsync(3000); });
  await screen.findByText(terminal === "READY"
    ? "Phiên bản 2 đã sẵn sàng. Hãy xem trước trước khi công bố."
    : "Phiên bản 2 không được chấp nhận. Xem chi tiết trong lịch sử phiên bản.");
  expect(screen.queryByText(/Hệ thống đang kiểm tra tệp/)).toBeNull();
  expect(api.upload).toHaveBeenCalledTimes(1);
});
