import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { OperationalServiceWorkspace } from "./OperationalServiceWorkspace";
const calls = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }));
vi.mock("@/lib/api/client", () => ({ ApiClient: class { get = calls.get; post = calls.post; }, ApiClientError: class extends Error {} }));
vi.mock("@/components/AppShell", () => ({ AppShell: ({ children }: { children: React.ReactNode }) => <main>{children}</main> }));
afterEach(() => { cleanup(); vi.resetAllMocks(); window.history.replaceState(null, "", "/services"); });
const actor = { display_name: "Sinh viên local", roles: ["STUDENT"] };
function ready() { calls.get.mockImplementation((path: string) => Promise.resolve(path === "/v1/users/me" ? actor : { items: [] })); }

describe("one main student service workspace", () => {
  it("shows all three preparations and the actual university connection limit", async () => {
    ready(); render(<OperationalServiceWorkspace />);
    await screen.findByText(/Sinh viên local/);
    expect(screen.getAllByRole("button", { name: "Chuẩn bị nháp" })).toHaveLength(3);
    expect(screen.getByText(/Chưa kết nối hệ thống tiếp nhận của HUCE/)).toBeDefined();
    fireEvent.click(screen.getAllByRole("button", { name: "Chuẩn bị nháp" })[0]);
    expect(screen.getByLabelText("Mục đích sử dụng")).toBeDefined();
    expect(screen.queryByRole("button", { name: "Xác nhận gửi" })).toBeNull();
  });

  it("requires review, keeps an uncertain write key and reads the same receipt on retry", async () => {
    ready(); render(<OperationalServiceWorkspace />);
    await screen.findByText(/Sinh viên local/);
    fireEvent.click(screen.getAllByRole("button", { name: "Chuẩn bị nháp" })[2]);
    fireEvent.change(screen.getByLabelText("Nội dung / lý do"), { target: { value: "Cần hỏi thủ tục" } });
    const form = { kind: "GENERAL_SUPPORT", purpose: "", recipient: "", course: "", reason: "Cần hỏi thủ tục" };
    calls.post.mockResolvedValueOnce({ preview_id: "preview-test", confirmation_token: "test-only", payload: { id: "draft-test", form } });
    fireEvent.click(screen.getByRole("button", { name: "Xem trước nháp" }));
    await screen.findByRole("region", { name: "Xem trước nháp" });
    expect((screen.getByRole("button", { name: "Lưu nháp đã xem" }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole("checkbox", { name: "Tôi đã xem nội dung nháp" }));
    calls.post.mockRejectedValueOnce(new Error("Mất kết nối"));
    fireEvent.click(screen.getByRole("button", { name: "Lưu nháp đã xem" }));
    await screen.findByRole("button", { name: "Đọc lại kết quả bằng cùng mã lưu" });
    expect(screen.getByLabelText("Nội dung / lý do").matches(":disabled")).toBe(true);
    calls.post.mockResolvedValueOnce({ effect: "draft_saved", receipt_id: "receipt-test", document: { id: "draft-test", version: 1, form, status: "DRAFT", sent_to_university: false, updated_at: new Date().toISOString() } });
    fireEvent.click(screen.getByRole("button", { name: "Đọc lại kết quả bằng cùng mã lưu" }));
    await screen.findByText(/Đã lưu nháp · Biên nhận receipt-test/);
    expect(calls.post.mock.calls[1][1]).toEqual(calls.post.mock.calls[2][1]);
    await waitFor(() => expect(screen.getByRole("button", { name: /Hỗ trợ thủ tục học vụ Nháp/ })).toBeDefined());
  });
});
