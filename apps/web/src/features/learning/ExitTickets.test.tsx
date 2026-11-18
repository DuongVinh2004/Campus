import React from "react";
import "@testing-library/jest-dom/vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { LearningExitSubmission, LearningExitTicket, LearningMaterial, LearningVisibleExitTicket } from "../../lib/data/api/learning-gateway";
import { ExitTicketDetail } from "./ExitTicketDetail";
import { ExitTicketDraftForm, ExitTicketPreviewDetails } from "./ExitTickets";

const ticketId = "00000000-0000-4000-8000-000000000004";
const versionId = "00000000-0000-4000-8000-000000000006";
const sessionId = "00000000-0000-4000-8000-000000000007";
const actorId = "00000000-0000-4000-8000-000000000008";
const path = `/v1/learning/exit-tickets/${ticketId}`;
const receiptPath = `${path}/me/submission`;
const ticket: LearningVisibleExitTicket = {
  id: ticketId, session_id: sessionId, revision: 3, state: "OPEN", version_id: versionId, page_no: 4,
  question: "Giải thích một quan sát.", zone_id: "America/New_York", instruction: null,
  opens: { local: "2026-11-01T01:30", offset_minutes: -300, utc: "2026-11-01T06:30:00.000Z" },
  closes: { local: "2026-11-01T02:30", offset_minutes: -300, utc: "2026-11-01T07:30:00.000Z" },
};
const materials: LearningMaterial[] = [{
  id: "material", offering_id: "offering", title: "Bài giảng", description: "", visibility: "VISIBLE", revision: 1,
  current_published_version_id: versionId, versions: [{
    id: versionId, version_no: 1, processing_state: "READY", publication_state: "PUBLISHED",
    page_count: 8, has_text_layer: true, revision: 1,
  }],
}];

function response(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

function receipt(answer: string, revision = 1): LearningExitSubmission {
  return { ticket_id: ticketId, answer, revision, receipt_id: `bien-nhan-${revision}`, submitted_at: "2026-11-01T06:40:00Z" };
}

function detail(extra: Partial<React.ComponentProps<typeof ExitTicketDetail>> = {}) {
  return render(<ExitTicketDetail actorId={actorId} ticketId={ticketId} staff={false} canManage={false}
    materials={materials} instructions={[]} zoneId="America/New_York" onClose={vi.fn()} onOpen={vi.fn()}
    onChange={vi.fn()} confirmWrite={vi.fn()} {...extra} />);
}

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe("exit ticket time and source", () => {
  it("requires the intended offset for a folded class wall time and disallows nonexistent times", () => {
    const save = vi.fn();
    render(<ExitTicketDraftForm materials={materials} instructions={[]} zoneId="America/New_York"
      source={{ versionId, page: 4 }} busy={false} onSave={save} onCancel={vi.fn()} />);
    fireEvent.change(screen.getByLabelText("Câu hỏi vận dụng"), { target: { value: "Vì sao?" } });
    fireEvent.change(screen.getByLabelText("Giờ mở (America/New_York)"), { target: { value: "2026-03-08T02:30" } });
    expect(screen.getByRole("alert")).toHaveTextContent("Giờ này không tồn tại");
    fireEvent.change(screen.getByLabelText("Giờ mở (America/New_York)"), { target: { value: "2026-11-01T01:30" } });
    fireEvent.change(screen.getByLabelText("Giờ đóng (America/New_York)"), { target: { value: "2026-11-01T02:30" } });
    expect(screen.getByRole("button", { name: "Lưu bản nháp" })).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Độ lệch UTC cho giờ mở"), { target: { value: "-300" } });
    fireEvent.click(screen.getByRole("button", { name: "Lưu bản nháp" }));
    expect(save).toHaveBeenCalledWith({
      version_id: versionId, page_no: 4, question: "Vì sao?",
      opens: { local: "2026-11-01T01:30", offset_minutes: -300 },
      closes: { local: "2026-11-01T02:30" }, instruction: null,
    });
  });

  it("shows the canonical preview window and impact returned by the server", () => {
    render(<ExitTicketPreviewDetails preview={{ ...ticket, students: 12, submissions: 3 }} />);
    expect(screen.getByText("2026-11-01 01:30 (UTC−05:00)")).toHaveAttribute("datetime", ticket.opens.utc);
    expect(screen.getByText("Tại lúc xem trước, thao tác ảnh hưởng 12 sinh viên và 3 bài đã nộp.")).toBeVisible();
  });

  it("opens the exact version and page and uses the pinned instruction revision", async () => {
    const open = vi.fn();
    vi.stubGlobal("fetch", vi.fn(async (url: string) => url === path
      ? response({ ...ticket, instruction: { id: "instruction", revision: 4, purpose: "Đọc bản gốc", page_ranges: [{ start: 2, end: 3 }] } })
      : response({ submission: null })));
    detail({ onOpen: open });
    fireEvent.click(await screen.findByRole("button", { name: "Mở trang nguồn 4" }));
    fireEvent.click(screen.getByRole("button", { name: "Đọc trang 2–3" }));
    expect(screen.getByText("Chỉ dẫn đọc · Lần 4")).toBeVisible();
    expect(open.mock.calls).toEqual([[versionId, 4], [versionId, 2]]);
  });
});

describe("private exit ticket submission", () => {
  it("recovers a committed submission after losing its response without replaying", async () => {
    let saved: LearningExitSubmission | null = null;
    const fetch = vi.fn(async (url: string, init: RequestInit) => {
      if (url === path) return response(ticket);
      if (url === receiptPath && init.method === "PUT") {
        expect(new Headers(init.headers).get("X-Campus-Reader-Actor")).toBe(actorId);
        saved = receipt("Bài do tôi viết.");
        throw new TypeError("ACK lost after commit");
      }
      return response({ submission: saved });
    });
    vi.stubGlobal("fetch", fetch);
    detail();
    fireEvent.change(await screen.findByRole("textbox", { name: "Câu trả lời riêng" }), { target: { value: "Bài do tôi viết." } });
    fireEvent.click(screen.getByRole("button", { name: "Nộp câu trả lời" }));
    const check = await screen.findByRole("button", { name: "Kiểm tra biên nhận" });
    act(() => window.dispatchEvent(new Event("online")));
    fireEvent.click(check);
    expect(await screen.findByText("Đã tìm thấy biên nhận lần 1.")).toBeVisible();
    expect(screen.getByText("Mã bien-nhan-1 · Lần 1")).toBeVisible();
    expect(fetch.mock.calls.filter(([url, init]) => url === receiptPath && init.method === "PUT")).toHaveLength(1);
  });

  it("requires a manual retry with the same idempotency key while the window remains open", async () => {
    const keys: (string | null)[] = [];
    vi.stubGlobal("fetch", vi.fn(async (url: string, init: RequestInit) => {
      if (url === path) return response(ticket);
      if (init.method === "PUT") {
        keys.push(new Headers(init.headers).get("Idempotency-Key"));
        if (keys.length === 1) throw new TypeError("Connection lost");
        return response(receipt("Thử lại."));
      }
      return response({ submission: null });
    }));
    detail();
    fireEvent.change(await screen.findByRole("textbox", { name: "Câu trả lời riêng" }), { target: { value: "Thử lại." } });
    fireEvent.click(screen.getByRole("button", { name: "Nộp câu trả lời" }));
    fireEvent.click(await screen.findByRole("button", { name: "Kiểm tra biên nhận" }));
    const retry = await screen.findByRole("button", { name: "Thử lại lần gửi" });
    expect(keys).toHaveLength(1);
    fireEvent.click(retry);
    expect(await screen.findByText("Đã nhận bài lần 1.")).toBeVisible();
    expect(keys).toEqual([expect.any(String), keys[0]]);
  });

  it("keeps the local answer after the server closes and never retries a late submission", async () => {
    let current: LearningExitTicket = ticket;
    const fetch = vi.fn(async (url: string, init: RequestInit) => {
      if (url === path) return response(current);
      if (init.method === "PUT") {
        current = { ...ticket, state: "CLOSED" };
        throw new TypeError("Disconnected before commit");
      }
      return url === `${path}/review` ? response({ review: null }) : response({ submission: null });
    });
    vi.stubGlobal("fetch", fetch);
    detail();
    fireEvent.change(await screen.findByRole("textbox", { name: "Câu trả lời riêng" }), { target: { value: "Còn trong tab." } });
    fireEvent.click(screen.getByRole("button", { name: "Nộp câu trả lời" }));
    fireEvent.click(await screen.findByRole("button", { name: "Kiểm tra biên nhận" }));
    expect(await screen.findByText(/Không có biên nhận cho lần gửi này/)).toBeVisible();
    expect(screen.getByRole("textbox", { name: "Câu trả lời riêng" })).toHaveValue("Còn trong tab.");
    expect(screen.queryByRole("button", { name: "Thử lại lần gửi" })).toBeNull();
    expect(fetch.mock.calls.filter(([, init]) => init.method === "PUT")).toHaveLength(1);
  });

  it("keeps the competing tab's receipt and waits for an explicit choice on revision conflict", async () => {
    let saved = receipt("Bản đầu.");
    vi.stubGlobal("fetch", vi.fn(async (url: string, init: RequestInit) => {
      if (url === path) return response(ticket);
      if (init.method === "PUT") {
        expect(JSON.parse(String(init.body)).revision).toBe(1);
        saved = receipt("Bản tab khác.", 2);
        return response({ code: "REVISION_CONFLICT" }, 409);
      }
      return response({ submission: saved });
    }));
    detail();
    fireEvent.change(await screen.findByRole("textbox", { name: "Câu trả lời riêng" }), { target: { value: "Bản đang soạn." } });
    fireEvent.click(screen.getByRole("button", { name: "Nộp bản sửa" }));
    expect(await screen.findByText("Bản tab khác.")).toBeVisible();
    expect(await screen.findByRole("button", { name: "Giữ bản đang soạn" })).toBeVisible();
    expect(screen.getByRole("textbox", { name: "Câu trả lời riêng" })).toHaveValue("Bản đang soạn.");
    expect(screen.getByRole("button", { name: "Nộp bản sửa" })).toBeDisabled();
  });

  it("hides the question, source, and review after withdrawal while keeping the owner's receipt", async () => {
    let current: LearningExitTicket | null = { ...ticket, state: "CLOSED" };
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (url === path) return current ? response(current) : response({ code: "RESOURCE_NOT_FOUND" }, 404);
      if (url === `${path}/review`) return response({ review: { published: { explanation: "Lời giải", published_at: ticket.closes.utc } } });
      return response({ submission: receipt("Bài riêng.") });
    }));
    detail();
    expect(await screen.findByText("Lời giải")).toBeVisible();
    current = { id: ticketId, session_id: sessionId, revision: 3, state: "SOURCE_UNAVAILABLE" };
    fireEvent.click(screen.getByRole("button", { name: "Tải lại phiếu" }));
    await waitFor(() => expect(screen.getByText("Nguồn học liệu không còn khả dụng")).toBeVisible());
    expect(screen.getByText("Bài riêng.")).toBeVisible();
    expect(screen.queryByText(ticket.question)).toBeNull();
    expect(screen.queryByText("Lời giải")).toBeNull();
    expect(screen.queryByRole("button", { name: /Mở trang nguồn/ })).toBeNull();
    current = null;
    fireEvent.click(screen.getByRole("button", { name: "Tải lại phiếu" }));
    await waitFor(() => expect(screen.queryByText("Bài riêng.")).toBeNull());
  });
});

describe("exit ticket review workflow", () => {
  it("passes the exact ticket revision into the reviewed extension", async () => {
    const confirm = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal("fetch", vi.fn(async () => response(ticket)));
    detail({ staff: true, canManage: true, confirmWrite: confirm });
    fireEvent.click(await screen.findByRole("button", { name: "Gia hạn nhận bài" }));
    fireEvent.change(screen.getByLabelText("Giờ đóng mới (America/New_York)"), { target: { value: "2026-11-01T03:30" } });
    fireEvent.click(screen.getByRole("button", { name: "Xem trước gia hạn" }));
    await waitFor(()=>expect(confirm).toHaveBeenCalledWith(`/exit-tickets/${ticketId}`,
      { operation: "EXTEND", revision: 3, closes: { local: "2026-11-01T03:30" } }, "exit-ticket-update", "Gia hạn phiếu ra lớp", "PATCH"));
    expect(await screen.findByText("Đã cập nhật phiếu ra lớp.")).toBeVisible();
  });

  it("keeps staff review notes private and passes only the saved revision to the publication preview", async () => {
    let stored = { revision: 0, topics: "", next_plan: "", explanation: "", published: null };
    const confirm = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal("fetch", vi.fn(async (url: string, init: RequestInit) => {
      if (url === path) return response({ ...ticket, state: "CLOSED" });
      if (url === `${path}/submissions?limit=100`) return response({ items: [{ ...receipt("Bài riêng để rà."),
        id: "submission", student_id: "student" }] });
      if (init.method === "PUT") {
        const payload = JSON.parse(String(init.body));
        expect(payload.operation).toBe("SAVE_DRAFT");
        expect(payload.revision).toBe(0);
        stored = { ...stored, ...payload, revision: 1 };
      }
      return response({ review: stored });
    }));
    detail({ staff: true, canManage: true, confirmWrite: confirm });
    fireEvent.click(await screen.findByRole("button", { name: "Xem bài nộp" }));
    expect(await screen.findByText("Bài riêng để rà.")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Soạn bản rà bài" }));
    fireEvent.change(screen.getByLabelText("Chủ đề lỗi thường gặp"), { target: { value: "Ghi chú nội bộ." } });
    fireEvent.change(screen.getByLabelText("Kế hoạch buổi sau"), { target: { value: "Kế hoạch riêng." } });
    fireEvent.change(screen.getByLabelText("Lời giải chung"), { target: { value: "Lời giải được chia sẻ." } });
    fireEvent.click(screen.getByRole("button", { name: "Lưu bản rà bài" }));
    expect(await screen.findByText("Đã lưu bản rà bài riêng.")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Xem trước công bố lời giải" }));
    expect(confirm).toHaveBeenCalledWith(`/exit-tickets/${ticketId}/review`, { operation: "PUBLISH", revision: 1 },
      "exit-review-save", "Công bố lời giải chung của phiếu", "PUT");
    expect(await screen.findByText("Đã công bố lời giải chung.")).toBeVisible();
  });
});
