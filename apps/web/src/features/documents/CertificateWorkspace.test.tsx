import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";
import { CertificateWorkspace } from "./CertificateWorkspace";
vi.mock("../../components/AppShell", () => ({ AppShell: ({ children }: { children: React.ReactNode }) => <>{children}</> }));
vi.mock("../../components/AuthLayout", () => ({ AuthLayout: ({ children }: { children: React.ReactNode }) => <>{children}</> }));

const actor = { user_id: "student-1", display_name: "Sinh viên giả lập", roles: ["STUDENT"], profile: { display_name: "Sinh viên giả lập", student_code: "SYN01", program_code: "IT_STANDARD" } };
const form = { purpose: "Mục đích demo", recipient: "Đơn vị demo", quantity: 1, delivery_method: "DIGITAL", attachments: [] };
const r = { id: "019a0000-0000-7000-8000-000000000001", student_user_id: actor.user_id, status: "DRAFT", version: 1, payload: form, profile: actor.profile,
  disclaimer: "Mô phỏng", history: [], assigned_user_id: null, supplement_request: null, result: null };

function setup(confirmStatus = 201) {
  const requests: Array<{ path: string; body: unknown }> = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    const path = new URL(url, window.location.origin).pathname;
    const body = init?.body ? JSON.parse(init.body as string) : null;
    requests.push({ path, body });
    let value: unknown = {};
    let status = 200;
    if (path.endsWith("/users/me")) value = actor;
    else if (path.endsWith("/certificate-guidance")) value = { summary: "Hướng dẫn", demo_configuration: "Demo", sources: [] };
    else if (path.endsWith("/drafts")) { value = r; status = 201; }
    else if (path.endsWith("/preview")) value = { document_request: { ...r, status: "PENDING_CONFIRMATION", version: 2 }, preview_id: "preview-1", confirmation_token: "signed-demo", expires_at: "2030-01-01T00:00:00Z" };
    else if (path.endsWith("/confirm")) { status = confirmStatus; value = status === 201 ? { document_request_id: r.id, status: "SUBMITTED", tracking_url: "/tickets?request=" + r.id, is_replay: false } : { title: "Lỗi backend", detail: "Chưa xác định kết quả gửi", code: "DEPENDENCY_UNAVAILABLE" }; }
    else if (path.endsWith(r.id)) value = { ...r, status: "SUBMITTED", version: 3 };
    else value = { items: [], page: { next_cursor: null } };
    return new Response(JSON.stringify(value), { status, headers: { "Content-Type": "application/json" } });
  }));
  return requests;
}
beforeEach(() => { localStorage.clear(); window.history.replaceState({}, "", "/tickets"); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe("Certificate backend UI", () => {
  it("requires an explicit preview and confirm before reporting submission", async () => {
    const requests = setup(); render(<CertificateWorkspace embedded />);
    await screen.findByText("Chuẩn bị bản nháp");
    fireEvent.change(screen.getByLabelText("Mục đích xin giấy xác nhận"), { target: { value: form.purpose } });
    fireEvent.change(screen.getByLabelText("Nơi nộp giấy xác nhận"), { target: { value: form.recipient } });
    fireEvent.click(screen.getByText("Xem trước hồ sơ"));
    await screen.findByText("Xem trước — chưa gửi");
    expect(requests.some(r => r.path.endsWith("/confirm"))).toBe(false);
    fireEvent.click(screen.getByText("Xác nhận gửi hồ sơ"));
    await screen.findByText(`Đã gửi hồ sơ ${r.id}`);
    expect(requests.filter(r => r.path.endsWith("/confirm"))).toHaveLength(1);
  });
  it("keeps the preview and the same replay key when a backend result is unknown", async () => {
    const requests = setup(503); render(<CertificateWorkspace embedded />);
    await screen.findByText("Chuẩn bị bản nháp");
    fireEvent.change(screen.getByLabelText("Mục đích xin giấy xác nhận"), { target: { value: form.purpose } });
    fireEvent.change(screen.getByLabelText("Nơi nộp giấy xác nhận"), { target: { value: form.recipient } });
    fireEvent.click(screen.getByText("Xem trước hồ sơ"));
    await screen.findByText("Xác nhận gửi hồ sơ");
    fireEvent.click(screen.getByText("Xác nhận gửi hồ sơ"));
    await screen.findByRole("alert");
    expect(screen.queryByText(/Đã gửi hồ sơ/)).toBeNull();
    fireEvent.click(screen.getByText("Xác nhận gửi hồ sơ"));
    await waitFor(() => expect(requests.filter(r => r.path.endsWith("/confirm"))).toHaveLength(2));
    const attempts = requests.filter(r => r.path.endsWith("/confirm"));
    expect(attempts[0].body).toEqual(attempts[1].body);
  });
});
