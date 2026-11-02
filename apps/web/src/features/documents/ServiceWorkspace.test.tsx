import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";
import { ServiceWorkspace } from "./ServiceWorkspace";

vi.mock("../../components/AppShell", () => ({ AppShell: ({ children }: { children: React.ReactNode }) => <>{children}</> }));
const student = { user_id: "student-1", display_name: "Sinh viên demo", roles: ["STUDENT"] };
const form = { kind: "GRADE_APPEAL", course_record_id: "CS101", reason: "Đối chiếu bài thi", attachments: [], contact_preference: "PORTAL", question: "", unresolved: "", evidence_refs: [] };
const draft = { id: "019a0000-0000-7000-8000-000000000001", student_user_id: student.user_id, document_type: "GRADE_APPEAL", status: "DRAFT", version: 1,
  payload: form, history: [], messages: [], profile: { display_name: "Demo", student_code: "SYN01" }, assigned_user_id: null, result: null,
  snapshot: { guidance: { text: "Demo source" } }, queue: "ACADEMIC_SERVICES" };

function setup(confirmationStatus = 201, staff = false) {
  const requests: Array<{ path: string; body: unknown }> = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    const path = new URL(url, window.location.origin).pathname;
    requests.push({ path, body: init?.body ? JSON.parse(init.body as string) : null });
    let status = 200;
    let value: unknown;
    if (path.endsWith("/users/me")) value = staff ? { user_id: "officer-1", display_name: "Cán bộ demo", roles: ["SUPPORT_OFFICER"] } : student;
    else if (path.endsWith("/service-course-records")) value = { items: [{ id: "CS101", course_code: "CS101", semester: "DEMO", score: "6", eligibility: "ELIGIBLE_DEMO" },
      { id: "CS102", course_code: "CS102", eligibility: "COURSE_INELIGIBLE", eligibility_reason: "Thi vấn đáp" }] };
    else if (path.endsWith("/service-staff-directory")) value = { items: [] };
    else if (path.endsWith("/drafts")) { value = draft; status = 201; }
    else if (path.endsWith("/preview")) value = { document_request: { ...draft, status: "PENDING_CONFIRMATION", version: 2 }, form, operation: "SERVICE_SUBMIT", preview_id: "preview-demo", confirmation_token: "signed",
      expires_at: "2030-01-01T00:00:00Z", disclaimer: "MÔ PHỎNG", note: "" };
    else if (path.endsWith("/confirm")) { status = confirmationStatus; value = status === 201 ? { document_request_id: draft.id, status: "SUBMITTED", queue: "ACADEMIC_SERVICES" }
      : { detail: "Kết quả chưa rõ", code: "DEPENDENCY_UNAVAILABLE" }; }
    else if (path.endsWith("/claim")) { status = 409; value = { detail: "Hồ sơ đã đổi", code: "STALE_VERSION" }; }
    else if (path.endsWith(draft.id)) value = { ...draft, status: "SUBMITTED", version: 3 };
    else value = { items: staff ? [{ ...draft, status: "SUBMITTED", version: 3 }] : [], page: { next_cursor: null } };
    return new Response(JSON.stringify(value), { status, headers: { "Content-Type": "application/json" } });
  }));
  return requests;
}

beforeEach(() => { localStorage.clear(); window.history.replaceState({}, "", "/services"); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
async function openAppeal() {
  await screen.findByRole("heading", { name: "Phúc khảo kết quả học tập" });
  fireEvent.click(screen.getAllByRole("button", { name: "Tạo yêu cầu" })[0]);
}
async function fill() {
  await openAppeal();
  await screen.findByText("Chuẩn bị bản nháp");
  fireEvent.change(screen.getByLabelText("Học phần mô phỏng"), { target: { value: "CS101" } });
  fireEvent.change(screen.getByLabelText("Lý do"), { target: { value: form.reason } });
  fireEvent.click(screen.getByText("Xem trước hồ sơ"));
  await screen.findByText("Xem trước — chưa gửi");
}

describe("Stage6 service UI", () => {
  it("shows eligibility, previews and requires explicit confirmation before receipt", async () => {
    const requests = setup(); render(<ServiceWorkspace />); await fill();
    expect(requests.some(r => r.path.endsWith("/confirm"))).toBe(false);
    fireEvent.click(screen.getByText("Xác nhận gửi"));
    await screen.findByText(`Đã ghi hồ sơ ${draft.id} vào ACADEMIC_SERVICES`);
    expect(requests.filter(r => r.path.endsWith("/confirm"))).toHaveLength(1);
  });
  it("keeps the same confirmation payload/key after unknown network outcome", async () => {
    const requests = setup(503); render(<ServiceWorkspace />); await fill();
    fireEvent.click(screen.getByText("Xác nhận gửi")); await screen.findByRole("alert");
    expect(screen.queryByText(/Đã ghi hồ sơ/)).toBeNull();
    fireEvent.click(screen.getByText("Xác nhận gửi"));
    await waitFor(() => expect(requests.filter(r => r.path.endsWith("/confirm"))).toHaveLength(2));
    const attempts = requests.filter(r => r.path.endsWith("/confirm")); expect(attempts[0].body).toEqual(attempts[1].body);
  });
  it("marks ineligible course unavailable and keeps missing-source errors visible", async () => {
    setup(); render(<ServiceWorkspace />); await openAppeal(); await screen.findByText("Chuẩn bị bản nháp");
    expect(screen.getByRole("option", { name: /CS102/ })).toBeDisabled();
  });
  it("staff sees persisted queue and a stale transition does not report success", async () => {
    setup(201, true); render(<ServiceWorkspace />);
    fireEvent.click(await screen.findByRole("button", { name: /Xem chi tiết Phúc khảo/ }));
    fireEvent.click(await screen.findByRole("button", { name: "Xử lý hồ sơ" }));
    await screen.findByLabelText("Lý do / phản hồi cán bộ");
    fireEvent.change(screen.getByLabelText("Lý do / phản hồi cán bộ"), { target: { value: "Tiếp nhận demo" } });
    fireEvent.click(screen.getByText("Tiếp nhận")); await screen.findByRole("alert");
    expect(screen.queryByText("Đã cập nhật hồ sơ")).toBeNull();
  });
});
