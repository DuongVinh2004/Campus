import React from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const calls = vi.hoisted(() => ({ request: vi.fn(), list: vi.fn(), write: vi.fn() }));
vi.mock("../../lib/data/api/learning-gateway", () => ({
  LearningGateway: class { request = calls.request; list = calls.list; write = calls.write; },
}));

import { SessionPracticeSets } from "./PracticeSets";

const materials = [{ id: "m1", title: "Bài 1", visibility: "VISIBLE", current_published_version_id: "v1", versions: [] }] as never;

beforeEach(() => { calls.request.mockReset(); calls.list.mockReset(); calls.write.mockReset(); });
afterEach(cleanup);

describe("student", () => {
  const set = { id: "s1", title: "Ôn chương 1", status: "PUBLISHED", revision: 3, item_count: 2 };

  it("works through a session: answer, see the result with the cited page, and a final score", async () => {
    calls.list.mockResolvedValue([set]);
    calls.request.mockResolvedValue({ ...set, items: [
      { id: "i1", kind: "single_choice", prompt: "Bê tông chịu lực nào tốt?", options: [{ id: "a", text: "Nén" }, { id: "b", text: "Kéo" }] },
      { id: "i2", kind: "short_answer", prompt: "Vật liệu nào chịu kéo?", options: [] }] });
    calls.write.mockResolvedValueOnce({ correct: true, answer: ["a"], accepted: [], explanation: "Xem trang 1.", citations: [{ page_no: 1, quote: "Bê tông chịu nén tốt" }], next_review_at: "x" });
    calls.write.mockResolvedValueOnce({ correct: false, answer: [], accepted: ["thép"], explanation: "", citations: [], next_review_at: "x" });
    render(<SessionPracticeSets sessionId="ses" materials={materials} canManage={false} actorId="u" />);
    fireEvent.click(await screen.findByRole("button", { name: "Ôn tập" }));
    expect(await screen.findByText("Bê tông chịu lực nào tốt?")).toBeTruthy();
    expect((screen.getByRole("button", { name: "Trả lời" }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByLabelText("Nén"));
    fireEvent.click(screen.getByRole("button", { name: "Trả lời" }));
    expect(await screen.findByText("Đúng.")).toBeTruthy();
    expect(screen.getByText(/Trang 1: Bê tông chịu nén tốt/)).toBeTruthy();
    expect(calls.write).toHaveBeenCalledWith("/practice-items/i1/attempts", { choices: ["a"] });
    fireEvent.click(screen.getByRole("button", { name: "Câu tiếp theo" }));
    fireEvent.change(await screen.findByLabelText("Câu trả lời"), { target: { value: "gỗ" } });
    fireEvent.click(screen.getByRole("button", { name: "Trả lời" }));
    expect(await screen.findByText("Chưa đúng.")).toBeTruthy();
    expect(screen.getByText("Đáp án chấp nhận: thép")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Xem kết quả" }));
    expect((await screen.findByTestId("practice-summary")).textContent).toContain("đúng 1 câu");
  });

  it("shows no authoring controls and says so when there is nothing to practise", async () => {
    calls.list.mockResolvedValue([]);
    render(<SessionPracticeSets sessionId="ses" materials={materials} canManage={false} actorId="u" />);
    expect(await screen.findByText("Chưa có bộ câu hỏi nào.")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Tạo bộ câu hỏi" })).toBeNull();
  });

  it("shows the server's message when answering fails", async () => {
    calls.list.mockResolvedValue([set]);
    calls.request.mockResolvedValue({ ...set, items: [{ id: "i1", kind: "short_answer", prompt: "Hỏi?", options: [] }] });
    calls.write.mockRejectedValue(new Error("Mất kết nối."));
    render(<SessionPracticeSets sessionId="ses" materials={materials} canManage={false} actorId="u" />);
    fireEvent.click(await screen.findByRole("button", { name: "Ôn tập" }));
    fireEvent.change(await screen.findByLabelText("Câu trả lời"), { target: { value: "x" } });
    fireEvent.click(screen.getByRole("button", { name: "Trả lời" }));
    expect((await screen.findByRole("alert")).textContent).toBe("Mất kết nối.");
  });
});

describe("lecturer", () => {
  it("creates a set from a published file and the new set appears", async () => {
    calls.list.mockResolvedValueOnce([]).mockResolvedValueOnce([{ id: "s9", title: "Bộ mới", status: "DRAFT", revision: 1 }]);
    calls.request.mockResolvedValue({ id: "s9", title: "Bộ mới", status: "DRAFT", revision: 1, items: [] });
    calls.write.mockResolvedValue({ id: "s9" });
    render(<SessionPracticeSets sessionId="ses" materials={materials} canManage actorId="u" />);
    fireEvent.change(await screen.findByLabelText("Tên bộ câu hỏi"), { target: { value: "Bộ mới" } });
    fireEvent.click(screen.getByRole("button", { name: "Tạo bộ câu hỏi" }));
    await waitFor(() => expect(calls.write).toHaveBeenCalledWith("/sessions/ses/practice-sets", { version_id: "v1", title: "Bộ mới" }));
    expect(await screen.findByTestId("practice-set-s9")).toBeTruthy();
  });

  it("adds a question with its citation, publishes, and surfaces the server's refusal for a quote that is not on the page", async () => {
    const draft = { id: "s9", title: "Bộ mới", status: "DRAFT", revision: 1, item_count: 1 };
    calls.list.mockResolvedValue([draft]);
    calls.request.mockResolvedValue({ ...draft, items: [{ id: "i1", kind: "single_choice", prompt: "Hỏi?", options: [], answer: ["a"], accepted: [], explanation: "", citations: [{ page_no: 1, quote: "q" }], revision: 1 }] });
    calls.write.mockResolvedValueOnce({ set_revision: 2 });
    render(<SessionPracticeSets sessionId="ses" materials={materials} canManage actorId="u" />);
    const form = await screen.findByRole("form", { name: "Thêm câu hỏi" });
    fireEvent.change(screen.getByLabelText("Câu hỏi"), { target: { value: "Bê tông chịu lực nào tốt?" } });
    fireEvent.change(screen.getByLabelText(/Các lựa chọn/), { target: { value: "Nén\nKéo" } });
    fireEvent.change(screen.getByLabelText(/Đáp án đúng/), { target: { value: "a" } });
    fireEvent.change(screen.getByLabelText("Trang trích dẫn"), { target: { value: "2" } });
    fireEvent.change(screen.getByLabelText(/Đoạn trích/), { target: { value: "Bê tông cốt thép chịu nén tốt" } });
    fireEvent.submit(form);
    await waitFor(() => expect(calls.write).toHaveBeenCalledTimes(1));
    expect(calls.write.mock.calls[0][0]).toBe("/practice-sets/s9/items");
    expect(calls.write.mock.calls[0][1]).toMatchObject({ revision: 1, kind: "single_choice", answer: ["a"], options: [{ id: "a", text: "Nén" }, { id: "b", text: "Kéo" }], citations: [{ page_no: 2, quote: "Bê tông cốt thép chịu nén tốt" }] });
    calls.write.mockRejectedValueOnce(new Error("Kiểm tra thông tin và định dạng tệp học liệu."));
    fireEvent.click(await screen.findByRole("button", { name: "Công bố bộ câu hỏi" }));
    expect((await screen.findAllByRole("alert"))[0].textContent).toContain("Kiểm tra thông tin");
  });
});
