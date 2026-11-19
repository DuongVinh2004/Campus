import React from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { OperationalServiceWorkspace } from "./OperationalServiceWorkspace";
import { ChatDraftActor, ChatDraftSessionProvider, chatDraftActorScope } from "../chat/route-drafts";

const calls = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn(), actor: "student-a", roles: ["STUDENT"] as string[] }));
vi.mock("@/lib/api/client", () => ({ ApiClient: class { get = calls.get; post = calls.post; }, ApiClientError: class extends Error {} }));
vi.mock("@/components/AppShell", () => ({ AppShell: ({ children }: { children: React.ReactNode }) =>
  <ChatDraftActor value={chatDraftActorScope({ user_id: calls.actor, roles: calls.roles })}><main>{children}</main></ChatDraftActor> }));

const originalScroll = Object.getOwnPropertyDescriptor(HTMLElement.prototype, "scrollIntoView");
beforeEach(() => {
  calls.actor = "student-a";
  calls.roles = ["STUDENT"];
  window.history.replaceState(null, "", "/services");
  Object.defineProperty(HTMLElement.prototype, "scrollIntoView", { configurable: true, value: vi.fn() });
  calls.get.mockImplementation(async (path: string) => path === "/v1/users/me"
    ? { user_id: calls.actor, display_name: calls.actor, roles: calls.roles } : { items: [] });
});
afterEach(() => {
  cleanup(); vi.resetAllMocks(); window.history.replaceState(null, "", "/services");
  if (originalScroll) Object.defineProperty(HTMLElement.prototype, "scrollIntoView", originalScroll);
  else Reflect.deleteProperty(HTMLElement.prototype, "scrollIntoView");
});
function View({ active = true }: { active?: boolean }) {
  return <ChatDraftSessionProvider>{active ? <OperationalServiceWorkspace /> : <p>Other route</p>}</ChatDraftSessionProvider>;
}
async function begin(index = 2) {
  await screen.findByText(/student-a ·/);
  fireEvent.click(screen.getAllByRole("button", { name: "Chuẩn bị nháp" })[index]);
}
const reason = () => screen.getByRole("textbox", { name: "Nội dung / lý do" }) as HTMLTextAreaElement;

it.each([0, 1, 2])("preserves unsaved preparation %s across a route unmount", async index => {
  const view = render(<View />);
  await begin(index);
  fireEvent.change(reason(), { target: { value: "Unsent service draft" } });
  if (index === 0) fireEvent.change(screen.getByRole("textbox", { name: "Mục đích sử dụng" }), { target: { value: "Private purpose" } });
  if (index === 1) fireEvent.change(screen.getByRole("textbox", { name: "Học phần bạn muốn hỏi" }), { target: { value: "Private course" } });
  view.rerender(<View active={false} />);
  window.history.replaceState(null, "", "/services");
  view.rerender(<View />);
  await screen.findByText(/student-a ·/);
  expect(reason().value).toBe("Unsent service draft");
  if (index === 0) expect((screen.getByRole("textbox", { name: "Mục đích sử dụng" }) as HTMLInputElement).value).toBe("Private purpose");
  if (index === 1) expect((screen.getByRole("textbox", { name: "Học phần bạn muốn hỏi" }) as HTMLInputElement).value).toBe("Private course");
  expect(calls.post).not.toHaveBeenCalled();
});

it("retains the exact uncertain save key across navigation and never retries automatically", async () => {
  const view = render(<View />);
  await begin();
  fireEvent.change(reason(), { target: { value: "Uncertain save draft" } });
  const form = { kind: "GENERAL_SUPPORT", purpose: "", recipient: "", course: "", reason: "Uncertain save draft" };
  calls.post.mockResolvedValueOnce({ preview_id: "preview-a", confirmation_token: "synthetic-token", payload: { id: "draft-a", form } });
  fireEvent.click(screen.getByRole("button", { name: "Xem trước nháp" }));
  await screen.findByRole("region", { name: "Xem trước nháp" });
  fireEvent.click(screen.getByRole("checkbox", { name: "Tôi đã xem nội dung nháp" }));
  calls.post.mockRejectedValueOnce(new Error("Connection interrupted"));
  fireEvent.click(screen.getByRole("button", { name: "Lưu nháp đã xem" }));
  await screen.findByRole("button", { name: "Đọc lại kết quả bằng cùng mã lưu" });
  const originalKey = calls.post.mock.calls[1][1];
  view.rerender(<View active={false} />);
  window.history.replaceState(null, "", "/services");
  view.rerender(<View />);
  await screen.findByText(/student-a ·/);
  expect(reason().value).toBe("Uncertain save draft");
  expect(reason().matches(":disabled")).toBe(true);
  expect(calls.post).toHaveBeenCalledTimes(2);
  calls.post.mockResolvedValueOnce({ effect: "draft_saved", receipt_id: "receipt-a", document: {
    id: "draft-a", version: 1, form, status: "DRAFT", sent_to_university: false, updated_at: "2026-11-10T00:00:00Z" } });
  fireEvent.click(screen.getByRole("button", { name: "Đọc lại kết quả bằng cùng mã lưu" }));
  await screen.findByText(/Biên nhận receipt-a/);
  expect(calls.post.mock.calls[2][1]).toEqual(originalKey);
});

it("isolates unsaved forms by account and restores the original owner", async () => {
  const view = render(<View />);
  await begin();
  fireEvent.change(reason(), { target: { value: "Private form A" } });
  view.rerender(<View active={false} />);
  calls.actor = "student-b";
  window.history.replaceState(null, "", "/services");
  view.rerender(<View />);
  await screen.findByText(/student-b ·/);
  expect(screen.queryByRole("textbox", { name: "Nội dung / lý do" })).toBeNull();
  fireEvent.click(screen.getAllByRole("button", { name: "Chuẩn bị nháp" })[2]);
  expect(reason().value).toBe("");
  fireEvent.change(reason(), { target: { value: "Private form B" } });
  view.rerender(<View active={false} />);
  calls.actor = "student-a";
  window.history.replaceState(null, "", "/services");
  view.rerender(<View />);
  await screen.findByText(/student-a ·/);
  expect(reason().value).toBe("Private form A");
});

it("preserves independent unsaved forms when switching preparation kinds", async () => {
  render(<View />);
  await begin();
  fireEvent.change(reason(), { target: { value: "Private support" } });
  fireEvent.click(screen.getByRole("button", { name: "← Danh mục dịch vụ" }));
  fireEvent.click(screen.getAllByRole("button", { name: "Chuẩn bị nháp" })[1]);
  fireEvent.change(reason(), { target: { value: "Private appeal" } });
  fireEvent.click(screen.getByRole("button", { name: "← Danh mục dịch vụ" }));
  fireEvent.click(screen.getAllByRole("button", { name: "Chuẩn bị nháp" })[2]);
  expect(reason().value).toBe("Private support");
  fireEvent.click(screen.getByRole("button", { name: "← Danh mục dịch vụ" }));
  fireEvent.click(screen.getAllByRole("button", { name: "Chuẩn bị nháp" })[1]);
  expect(reason().value).toBe("Private appeal");
});

it("keeps the selected saved record and expected version after navigation", async () => {
  const form = { kind: "GENERAL_SUPPORT", purpose: "", recipient: "", course: "", reason: "Original saved form" };
  const saved = { id: "saved-a", version: 2, form, status: "DRAFT", sent_to_university: false, updated_at: "2026-11-10T00:00:00Z" };
  calls.get.mockImplementation(async (path: string) => path === "/v1/users/me"
    ? { user_id: calls.actor, display_name: calls.actor, roles: ["STUDENT"] }
    : path === "/v1/student-preparations/saved-a" ? saved : { items: [saved] });
  window.history.replaceState(null, "", "/services?request=saved-a");
  const view = render(<View />);
  await screen.findByRole("textbox", { name: "Nội dung / lý do" });
  fireEvent.change(reason(), { target: { value: "Unsent edit of saved form" } });
  view.rerender(<View active={false} />);
  window.history.replaceState(null, "", "/services");
  view.rerender(<View />);
  await screen.findByText(/student-a ·/);
  expect(reason().value).toBe("Unsent edit of saved form");
  calls.post.mockResolvedValueOnce({ preview_id: "preview-saved", confirmation_token: "synthetic", payload: { id: "saved-a", form } });
  fireEvent.click(screen.getByRole("button", { name: "Xem trước nháp" }));
  await screen.findByRole("region", { name: "Xem trước nháp" });
  expect(calls.post.mock.calls[0][1]).toMatchObject({ document_id: "saved-a", expected_version: 2,
    form: { reason: "Unsent edit of saved form" } });
});

it("opens an explicit different record without losing the earlier unsent edit", async () => {
  const form = (reason: string) => ({ kind: "GENERAL_SUPPORT", purpose: "", recipient: "", course: "", reason });
  const row = (id: string) => ({ id, version: 2, form: form("Saved " + id), status: "DRAFT", sent_to_university: false, updated_at: "2026-11-10T00:00:00Z" });
  calls.get.mockImplementation(async (path: string) => path === "/v1/users/me"
    ? { user_id: calls.actor, display_name: calls.actor, roles: ["STUDENT"] }
    : path.endsWith("/saved-a") ? row("saved-a") : path.endsWith("/saved-b") ? row("saved-b") : { items: [row("saved-a"), row("saved-b")] });
  window.history.replaceState(null, "", "/services?request=saved-a");
  const view = render(<View />);
  await screen.findByRole("textbox", { name: "Nội dung / lý do" });
  fireEvent.change(reason(), { target: { value: "Unsent A" } });
  view.rerender(<View active={false} />);
  window.history.replaceState(null, "", "/services?request=saved-b");
  view.rerender(<View />);
  await screen.findByText(/student-a ·/);
  expect(reason().value).toBe("Saved saved-b");
  fireEvent.change(reason(), { target: { value: "Unsent B" } });
  view.rerender(<View active={false} />);
  window.history.replaceState(null, "", "/services?request=saved-a");
  view.rerender(<View />);
  await screen.findByText(/student-a ·/);
  expect(reason().value).toBe("Unsent A");
  expect(calls.post).not.toHaveBeenCalled();
});

it("honors an explicit preparation kind while preserving the previous kind's draft", async () => {
  const view = render(<View />);
  await begin();
  fireEvent.change(reason(), { target: { value: "Unsent support" } });
  view.rerender(<View active={false} />);
  window.history.replaceState(null, "", "/services?kind=GRADE_APPEAL");
  view.rerender(<View />);
  await screen.findByText(/student-a ·/);
  expect(screen.getByRole("textbox", { name: "Học phần bạn muốn hỏi" })).toBeDefined();
  expect(reason().value).toBe("");
  fireEvent.change(reason(), { target: { value: "Unsent appeal" } });
  view.rerender(<View active={false} />);
  window.history.replaceState(null, "", "/services?kind=GENERAL_SUPPORT");
  view.rerender(<View />);
  await screen.findByText(/student-a ·/);
  expect(reason().value).toBe("Unsent support");
});

it.each(["toString", "constructor", "__proto__"])("rejects the inherited URL kind %s without creating a form", async kind => {
  window.history.replaceState(null, "", "/services?kind=" + kind);
  render(<View />);
  await screen.findByText(/student-a ·/);
  expect(screen.queryByRole("textbox", { name: "Nội dung / lý do" })).toBeNull();
  expect(screen.getAllByRole("button", { name: "Chuẩn bị nháp" })).toHaveLength(3);
  expect(calls.post).not.toHaveBeenCalled();
});

it.each([true, false])("retains an in-flight save without changing a different route (remount first: %s)", async remountFirst => {
  const view = render(<View />);
  await begin();
  fireEvent.change(reason(), { target: { value: "In-flight draft" } });
  const form = { kind: "GENERAL_SUPPORT", purpose: "", recipient: "", course: "", reason: "In-flight draft" };
  calls.post.mockResolvedValueOnce({ preview_id: "preview-flight", confirmation_token: "synthetic", payload: { id: "draft-flight", form } });
  fireEvent.click(screen.getByRole("button", { name: "Xem trước nháp" }));
  await screen.findByRole("region", { name: "Xem trước nháp" });
  fireEvent.click(screen.getByRole("checkbox", { name: "Tôi đã xem nội dung nháp" }));
  let complete!: (result: unknown) => void;
  calls.post.mockImplementationOnce(() => new Promise(resolve => { complete = resolve; }));
  fireEvent.click(screen.getByRole("button", { name: "Lưu nháp đã xem" }));
  await waitFor(() => expect(calls.post).toHaveBeenCalledTimes(2));
  view.rerender(<View active={false} />);
  window.history.replaceState(null, "", "/privacy");
  if (remountFirst) {
    window.history.replaceState(null, "", "/services");
    view.rerender(<View />);
    await screen.findByText(/student-a ·/);
    expect(reason().matches(":disabled")).toBe(true);
    expect(calls.post).toHaveBeenCalledTimes(2);
  }
  await act(async () => complete({ effect: "draft_saved", receipt_id: "receipt-flight", document: {
    id: "draft-flight", version: 1, form, status: "DRAFT", sent_to_university: false, updated_at: "2026-11-10T00:00:00Z" } }));
  if (!remountFirst) {
    expect(window.location.pathname + window.location.search).toBe("/privacy");
    window.history.replaceState(null, "", "/services");
    view.rerender(<View />);
    await screen.findByText(/student-a ·/);
  }
  await screen.findByText(/Biên nhận receipt-flight/);
  expect(reason().matches(":disabled")).toBe(false);
  expect(calls.post).toHaveBeenCalledTimes(2);
});

it.each([false, true])("publishes no private data when identity changes during initial reads (specific record: %s)", async specific => {
  let reads = 0;
  if (specific) window.history.replaceState(null, "", "/services?request=private-b");
  calls.get.mockImplementation(async (path: string) => path === "/v1/users/me"
    ? { user_id: ++reads === 1 ? "student-a" : "student-b", display_name: "private", roles: ["STUDENT"] }
    : path.endsWith("/private-b") ? { id: "private-b", version: 1,
      form: { kind: "GENERAL_SUPPORT", purpose: "", recipient: "", course: "", reason: "PRIVATE_B" } } : { items: [] });
  render(<View />);
  await screen.findByRole("alert");
  expect(screen.queryByRole("button", { name: "Chuẩn bị nháp" })).toBeNull();
  expect(screen.queryByRole("textbox", { name: "Nội dung / lý do" })).toBeNull();
  expect(calls.post).not.toHaveBeenCalled();
});

it("keeps earlier-role drafts separate and restores them for the exact original scope", async () => {
  const view = render(<View />);
  await begin();
  fireEvent.change(reason(), { target: { value: "Private original permission scope" } });
  view.rerender(<View active={false} />);
  window.history.replaceState(null, "", "/services");
  calls.roles = ["STUDENT", "LECTURER"];
  view.rerender(<View />);
  await screen.findByText(/student-a ·/);
  expect(screen.queryByRole("textbox", { name: "Nội dung / lý do" })).toBeNull();
  view.rerender(<View active={false} />);
  calls.roles = ["STUDENT"];
  view.rerender(<View />);
  await screen.findByText(/student-a ·/);
  expect(reason().value).toBe("Private original permission scope");
});
