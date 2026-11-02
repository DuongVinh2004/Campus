import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";
import { OperationalServiceWorkspace } from "./OperationalServiceWorkspace";

vi.mock("@/components/AppShell", () => ({ AppShell: ({ children }: { children: React.ReactNode }) => <main>{children}</main> }));
const form = { kind: "GENERAL_SUPPORT", reason: "Hỏi cách xin nghỉ học", purpose: "", course: "", recipient: "" };
const draft = { id: "fixture-draft", version: 1, form, status: "DRAFT", sent_to_university: false, updated_at: "2026-11-01T00:00:00Z" };
const originalScroll = Object.getOwnPropertyDescriptor(HTMLElement.prototype, "scrollIntoView");
beforeEach(() => Object.defineProperty(HTMLElement.prototype, "scrollIntoView", { configurable: true, value: vi.fn() }));
afterEach(() => {
  cleanup(); vi.restoreAllMocks(); window.history.replaceState(null, "", "/");
  if (originalScroll) Object.defineProperty(HTMLElement.prototype, "scrollIntoView", originalScroll);
  else Reflect.deleteProperty(HTMLElement.prototype, "scrollIntoView");
});
function mockApi(items = [draft]) {
  return vi.spyOn(globalThis, "fetch").mockImplementation(async (url, init) => {
    const path = String(url);
    const value = path.endsWith("/users/me") ? { display_name: "Sinh viên thử", roles: ["STUDENT"] }
      : path.endsWith("/preview") ? { preview_id: "fixture-preview", confirmation_token: "fixture-confirmation", expires_at: "2099-01-01T00:00:00Z", payload: { id: draft.id, form } }
      : path.endsWith("/save") ? { effect: "draft_saved", document: draft, receipt_id: "fixture-receipt" }
      : { items };
    expect(init?.credentials).toBe("include");
    return new Response(JSON.stringify(value), { headers: { "content-type": "application/json" } });
  });
}
describe("saved preparation drafts", () => {
  it("distinguishes same-title drafts with a single excerpt of at most 80 characters", async () => {
    mockApi([draft, { ...draft, id: "other", form: { ...form, reason: "", purpose: "  Xin giấy xác nhận\nđể " + "học ".repeat(30) } }]);
    render(<OperationalServiceWorkspace history />);
    const reason = await screen.findByText(form.reason);
    const purpose = screen.getByText(/^Xin giấy xác nhận để/);
    expect(reason.closest("button")).not.toBe(purpose.closest("button"));
    expect(purpose.textContent!.length).toBeLessThanOrEqual(80);
    expect(purpose.textContent).not.toMatch(/\n/);
  });
  it("scrolls and focuses the form on every draft open, including switching while editing", async () => {
    const scroll = vi.mocked(HTMLElement.prototype.scrollIntoView);
    mockApi([draft, { ...draft, id: "other", form: { ...form, reason: "Hỏi thủ tục thứ hai" } }]);
    render(<OperationalServiceWorkspace history />);
    const buttons = await screen.findAllByRole("button", { name: /Hỗ trợ thủ tục học vụ/ });
    fireEvent.click(buttons[0]);
    await waitFor(() => expect(document.activeElement).toBe(screen.getByRole("region", { name: "Biểu mẫu nháp" })));
    expect(scroll).toHaveBeenCalledTimes(1);
    fireEvent.click(buttons[1]);
    await waitFor(() => expect(scroll).toHaveBeenCalledTimes(2));
    expect(screen.getByLabelText("Nội dung / lý do")).toHaveValue("Hỏi thủ tục thứ hai");
    fireEvent.click(buttons[1]);
    await waitFor(() => expect(scroll).toHaveBeenCalledTimes(3));
  });
  it("requires preview and explicit confirmation and reports only draft_saved", async () => {
    const fetcher = mockApi();
    render(<OperationalServiceWorkspace history />);
    fireEvent.click(await screen.findByRole("button", { name: /Hỗ trợ thủ tục học vụ/ }));
    fireEvent.click(screen.getByRole("button", { name: "Xem trước nháp" }));
    const save = await screen.findByRole("button", { name: "Lưu nháp đã xem" });
    expect(save).toBeDisabled();
    expect(fetcher.mock.calls.some(([url]) => String(url).endsWith("/save"))).toBe(false);
    fireEvent.click(screen.getByLabelText("Tôi đã xem nội dung nháp")); fireEvent.click(save);
    expect(await screen.findByText(/Đã lưu nháp · Biên nhận/)).toHaveTextContent("Chưa gửi đến trường.");
    const request = fetcher.mock.calls.find(([url]) => String(url).endsWith("/save"))!;
    expect(JSON.parse(String(request[1]?.body))).toMatchObject({ confirmed: true, confirmation_token: "fixture-confirmation", preview_id: "fixture-preview" });
  });
});
