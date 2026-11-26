import React from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const calls = vi.hoisted(() => ({ request: vi.fn(), list: vi.fn(), write: vi.fn() }));
vi.mock("../../lib/data/api/learning-gateway", () => ({
  LearningGateway: class { request = calls.request; list = calls.list; write = calls.write; },
}));

import { SessionPracticeSets } from "./PracticeSets";
import { ClassMastery, MyMastery, TutorBox } from "./TutorPanels";

const materials = [{ id: "m1", title: "Bài 1", visibility: "VISIBLE", current_published_version_id: "v1", versions: [] }] as never;

beforeEach(() => { calls.request.mockReset(); calls.list.mockReset(); calls.write.mockReset(); });
afterEach(cleanup);

describe("TutorBox", () => {
  it("gives a hint with its page quote, keeps the solution locked before the threshold, and lets the student retry", async () => {
    const retry = vi.fn();
    calls.write.mockResolvedValueOnce({ level: 1, hint: "Xem lại trang 1: lực nào?", quote: "Vật liệu được chọn theo loại lực", page: 1, origin: "TEMPLATE", remaining_today: 30, turns_left: 5, solution_after: 2 });
    render(<TutorBox itemId="i1" tutor={{ hint_available: true, wrong_attempts: 1, solution_after: 2 }} onRetry={retry} />);
    expect((screen.getByRole("button", { name: "Xem lời giải" }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByText("Lời giải mở sau 2 lần trả lời sai.")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Gợi ý" }));
    expect(await screen.findByText("Xem lại trang 1: lực nào?")).toBeTruthy();
    expect(screen.getByText(/Trang 1: «Vật liệu được chọn theo loại lực»/)).toBeTruthy();
    expect(screen.getByText("Gợi ý mẫu")).toBeTruthy();
    expect(calls.write).toHaveBeenCalledWith("/tutor/practice-items/i1/hints", {});
    fireEvent.click(screen.getByRole("button", { name: "Thử lại câu này" }));
    expect(retry).toHaveBeenCalled();
  });

  it("sends a reply, asks for more and explains a refused request in plain words", async () => {
    calls.write.mockResolvedValueOnce({ level: 1, hint: "Gợi ý một", quote: "", page: 1, origin: "MODEL", remaining_today: 29, turns_left: 5, solution_after: 2 });
    calls.write.mockRejectedValueOnce(Object.assign(new Error("x"), { code: "HINT_TURNS_EXHAUSTED" }));
    render(<TutorBox itemId="i1" tutor={{ hint_available: true, wrong_attempts: 2, solution_after: 2 }} onRetry={() => undefined} />);
    fireEvent.click(screen.getByRole("button", { name: "Gợi ý" }));
    expect(await screen.findByText("Gợi ý tự động từ tài liệu lớp")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Trả lời câu hỏi gợi mở (không bắt buộc)"), { target: { value: "Em nghĩ là nén" } });
    fireEvent.click(screen.getByRole("button", { name: "Gửi câu trả lời gợi mở" }));
    expect((await screen.findByRole("alert")).textContent).toBe("Câu này đã dùng hết lượt gợi ý.");
    expect(calls.write).toHaveBeenLastCalledWith("/tutor/practice-items/i1/hints", { reply: "Em nghĩ là nén" });
    expect((screen.getByRole("button", { name: "Xem lời giải" }) as HTMLButtonElement).disabled).toBe(false);
  });
});

describe("the practice session with the tutor on", () => {
  it("shows the tutor instead of the answer after a wrong attempt, then the same question again", async () => {
    const set = { id: "s1", title: "Ôn chương 1", status: "PUBLISHED", revision: 3, item_count: 1 };
    calls.list.mockResolvedValue([set]);
    calls.request.mockImplementation((path: string) => path.endsWith("/session")
      ? Promise.resolve({ ...set, items: [{ id: "i1", kind: "single_choice", prompt: "Bê tông chịu lực nào tốt?", options: [{ id: "a", text: "Nén" }, { id: "b", text: "Kéo" }] }] })
      : Promise.reject(new Error("404")));
    calls.write.mockResolvedValueOnce({ correct: false, next_review_at: "x", tutor: { hint_available: true, wrong_attempts: 1, solution_after: 2 } });
    render(<SessionPracticeSets sessionId="ses" materials={materials} canManage={false} actorId="u" offeringId="o1" />);
    fireEvent.click(await screen.findByRole("button", { name: "Ôn tập" }));
    fireEvent.click(await screen.findByLabelText("Kéo"));
    fireEvent.click(screen.getByRole("button", { name: "Trả lời" }));
    expect(await screen.findByTestId("tutor-box")).toBeTruthy();
    expect(screen.queryByText(/Đáp án đúng/)).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Thử lại câu này" }));
    expect((screen.getByRole("button", { name: "Trả lời" }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByText("Bê tông chịu lực nào tốt?")).toBeTruthy();
  });
});

describe("mastery views", () => {
  it("shows a student's own concepts with words, and what to review first", async () => {
    calls.request.mockResolvedValue({ concepts: [{ concept_id: "c1", label: "Bê tông chịu nén", p_known: 0.12, attempts: 3, band: "NEEDS_REVIEW" }], review_first: { concept_id: "c1", label: "Bê tông chịu nén" } });
    render(<MyMastery offeringId="o1" />);
    expect(await screen.findByText("Nên ôn trước: Bê tông chịu nén")).toBeTruthy();
    expect(screen.getByText(/Bê tông chịu nén: Cần ôn/)).toBeTruthy();
    expect(screen.getByText("Đây là ước lượng theo các câu đã làm, không phải điểm.")).toBeTruthy();
  });

  it("renders nothing when the feature is off", async () => {
    calls.request.mockRejectedValue(new Error("404"));
    const { container } = render(<MyMastery offeringId="o1" />);
    await waitFor(() => expect(calls.request).toHaveBeenCalled());
    expect(container.innerHTML).toBe("");
  });

  it("gives the lecturer the map with hidden small cells and a note for a small class", async () => {
    calls.request.mockImplementation((path: string) => {
      if (path.endsWith("/map")) return Promise.resolve({ suppressed: false, students: 7, concepts: [{ concept_id: "c1", label: "Nén", students: 7, bands: { MASTERED: 5, PROGRESSING: "<5", NEEDS_REVIEW: "<5", NOT_ENOUGH_DATA: "<5" }, needs_review_rate: 0.286 }], items: [] });
      if (path.endsWith("/settings")) return Promise.resolve({ tutor_enabled: false, reveal_after_attempts: 2, model_hints_enabled: false, revision: 0 });
      return Promise.resolve({ concepts: [{ id: "c1", label: "Nén", description: "", status: "PROPOSED", revision: 1 }] });
    });
    render(<ClassMastery offeringId="o1" />);
    const table = await screen.findByRole("table", { name: "Bản đồ nắm vững của lớp" });
    expect(table.textContent).toContain("< 5");
    expect(table.textContent).toContain("29%");
    expect(await screen.findByRole("button", { name: "Duyệt" })).toBeTruthy();
    calls.write.mockResolvedValueOnce({ tutor_enabled: true, reveal_after_attempts: 2, model_hints_enabled: false, revision: 1 });
    fireEvent.click(screen.getByLabelText("Bật gia sư cho lớp"));
    fireEvent.click(screen.getByRole("button", { name: "Lưu cài đặt" }));
    expect(await screen.findByText("Đã lưu.")).toBeTruthy();
    expect(calls.write).toHaveBeenCalledWith("/tutor/offerings/o1/settings", { tutor_enabled: true, reveal_after_attempts: 2, model_hints_enabled: false, revision: 0 }, "PUT");
  });

  it("says why the map is empty for a class under five students", async () => {
    calls.request.mockImplementation((path: string) => path.endsWith("/map")
      ? Promise.resolve({ suppressed: true, students: "<5", concepts: [], items: [] }) : Promise.reject(new Error("404")));
    render(<ClassMastery offeringId="o1" />);
    expect(await screen.findByText("Lớp có dưới 5 sinh viên nên bản đồ không hiển thị số liệu.")).toBeTruthy();
  });
});

describe("concept proposals", () => {
  it("asks the model for proposals and lists them for approval", async () => {
    let proposed = false;
    calls.request.mockImplementation((path: string) => {
      if (path.endsWith("/map")) return Promise.resolve({ suppressed: true, students: "<5", concepts: [], items: [] });
      if (path.endsWith("/concepts")) return Promise.resolve({ concepts: proposed ? [{ id: "c9", label: "Khả năng chịu nén", description: "", status: "PROPOSED", revision: 1 }] : [] });
      return Promise.reject(new Error("404"));
    });
    calls.write.mockImplementation(() => { proposed = true; return Promise.resolve({ proposed: [{ id: "c9" }] }); });
    render(<ClassMastery offeringId="o1" />);
    fireEvent.click(await screen.findByRole("button", { name: "Đề xuất khái niệm bằng AI" }));
    expect(await screen.findByText("Đã thêm 1 đề xuất chờ duyệt.")).toBeTruthy();
    expect(await screen.findByText("Khả năng chịu nén")).toBeTruthy();
    expect(calls.write).toHaveBeenCalledWith("/mastery/offerings/o1/concept-suggestions", {});
  });
});
