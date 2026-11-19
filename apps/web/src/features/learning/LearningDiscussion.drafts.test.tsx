import React from "react";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { LearningDiscussion } from "./LearningDiscussion";
import { LearningExplanation } from "./LearningExplanation";
import { ChatDraftActor, ChatDraftSessionProvider, chatDraftActorScope } from "../chat/route-drafts";
const api = vi.hoisted(() => ({ list: vi.fn(), write: vi.fn() }));
vi.mock("../../lib/data/api/learning-gateway", () => ({ LearningGateway: class { list = api.list; write = api.write; } }));
const V = "019a0000-0000-7000-8000-000000000001";
const W = "019a0000-0000-7000-8000-000000000002";
const originalRoles = ["STUDENT"];
const select = (version: string) => ({ version_id: version, page_no: 2, anchor: { kind: "PAGE" as const } });
function View({ open = true, version = V, actor = "student-a", roles = originalRoles, selected = true }:
  { open?: boolean; version?: string; actor?: string; roles?: string[]; selected?: boolean }) {
  return <ChatDraftSessionProvider><ChatDraftActor value={chatDraftActorScope({ user_id: actor, roles })}>
    {open && <><LearningDiscussion key={version+actor} versionId={version} actorId={actor} selection={selected ? select(version) : null}
      canManage={false} onAnnotationsChange={() => {}} />
      <LearningExplanation actorId={actor} versionId={version} selection={select(version)} available onSource={() => {}} /></>}
  </ChatDraftActor></ChatDraftSessionProvider>;
}
const edit = (name: string, value: string) => fireEvent.change(screen.getByLabelText(name), { target: { value } });
const note = () => screen.getByLabelText("Nội dung ghi chú");
beforeEach(() => {
  api.list.mockImplementation(async (path: string) => path.includes("/questions") ? [{ id: "q1", body: "Stored question", page_no: 2,
    author_id: "other", visibility: "CLASS", revision: 1, author_name: "Synthetic class member", replies: [] }] : []);
  api.write.mockResolvedValue({});
});
afterEach(() => { cleanup(); vi.resetAllMocks(); });

it("retains separate note, question, visibility, reply and explanation drafts after closing the reader", async () => {
  const view = render(<View />); await screen.findByText("Stored question");
  edit("Nội dung ghi chú", "Unsent private note"); edit("Câu hỏi", "Unsent source question");
  edit("Ai được xem", "CLASS"); edit("Trả lời", "Unsent reply"); edit("Bạn cần hiểu điều gì", "Unsent explanation question");
  view.rerender(<View open={false} />); view.rerender(<View />); await screen.findByText("Stored question");
  expect(note()).toHaveValue("Unsent private note"); expect(screen.getByLabelText("Câu hỏi")).toHaveValue("Unsent source question");
  expect(screen.getByLabelText("Ai được xem")).toHaveValue("CLASS"); expect(screen.getByLabelText("Trả lời")).toHaveValue("Unsent reply");
  expect(screen.getByLabelText("Bạn cần hiểu điều gì")).toHaveValue("Unsent explanation question"); expect(api.write).not.toHaveBeenCalled();
});

it.each(["version", "actor", "roles"])("keeps drafts independent for a different %s and restores the original scope", async change => {
  const view = render(<View />); edit("Nội dung ghi chú", "Original private note");
  const next = change === "version" ? { version: W } : change === "actor" ? { actor: "student-b" } : { roles: ["LECTURER"] };
  view.rerender(<View {...next} />); expect(note()).toHaveValue(""); edit("Nội dung ghi chú", "Other scoped note");
  view.rerender(<View />); expect(note()).toHaveValue("Original private note");
});

it("retains a recovered draft without binding it to a source the user has not selected", () => {
  const view = render(<View />); edit("Nội dung ghi chú", "Unsent original page note");
  view.rerender(<View open={false} />); view.rerender(<View selected={false} />);
  expect(note()).toHaveValue("Unsent original page note"); expect(screen.getByRole("button", { name: "Lưu ghi chú riêng" })).toBeDisabled();
  expect(api.write).not.toHaveBeenCalled();
});

it.each(["note", "question", "reply"])("does not erase a newer %s edit when an earlier save finishes after reader remount", async kind => {
  let finish!: () => void;
  api.write.mockImplementation(() => new Promise(resolve => { finish = () => resolve({}); }));
  const view = render(<View />); await screen.findByText("Stored question");
  const label = kind === "note" ? "Nội dung ghi chú" : kind === "question" ? "Câu hỏi" : "Trả lời";
  const button = kind === "note" ? "Lưu ghi chú riêng" : kind === "question" ? "Gửi câu hỏi" : "Gửi trả lời";
  edit(label, "Earlier submitted body"); fireEvent.click(screen.getByRole("button", { name: button }));
  await waitFor(() => expect(finish).toBeTypeOf("function"));
  view.rerender(<View open={false} />); view.rerender(<View />); await screen.findByText("Stored question");
  expect(screen.getByRole("button", { name: button })).toBeDisabled(); edit(label, "Newer unsent body");
  await act(async () => finish());
  await waitFor(() => expect(screen.getByRole("button", { name: button })).toBeEnabled());
  expect(screen.getByLabelText(label)).toHaveValue("Newer unsent body"); expect(api.write).toHaveBeenCalledTimes(1);
  view.rerender(<View open={false} />); view.rerender(<View />); await screen.findByText("Stored question");
  expect(screen.getByLabelText(label)).toHaveValue("Newer unsent body");
});

it("keeps the expected revision and separate new-note draft when an existing note is edited", async () => {
  api.list.mockImplementation(async (path: string) => path.includes("/annotations?") ? [{ id: "saved-note", body: "Stored note", page_no: 2,
    status: "ACTIVE", revision: 7, anchor: { kind: "PAGE" } }] : []);
  const view = render(<View />); await screen.findByText("Stored note"); edit("Nội dung ghi chú", "Separate new-note draft");
  fireEvent.click(screen.getByRole("button", { name: "Sửa ghi chú" })); edit("Sửa ghi chú", "Unsent edit of saved note");
  view.rerender(<View open={false} />); view.rerender(<View />); await screen.findByText("Stored note");
  expect(screen.getByLabelText("Sửa ghi chú")).toHaveValue("Unsent edit of saved note");
  fireEvent.click(screen.getByRole("button", { name: "Lưu ghi chú riêng" }));
  await waitFor(() => expect(api.write).toHaveBeenCalledWith("/me/annotations/saved-note", { body: "Unsent edit of saved note", revision: 7 }, "PATCH", expect.any(String)));
  expect(await screen.findByLabelText("Nội dung ghi chú")).toHaveValue("Separate new-note draft");
});

it.each(["note", "question", "reply"])("reuses the exact %s request key after an uncertain result and reader remount", async kind => {
  api.write.mockRejectedValueOnce(new Error("Synthetic response unavailable")).mockResolvedValue({});
  const view = render(<View />); await screen.findByText("Stored question");
  const label = kind === "note" ? "Nội dung ghi chú" : kind === "question" ? "Câu hỏi" : "Trả lời";
  const button = kind === "note" ? "Lưu ghi chú riêng" : kind === "question" ? "Gửi câu hỏi" : "Gửi trả lời";
  edit(label, "Body with an uncertain result"); fireEvent.click(screen.getByRole("button", { name: button }));
  await screen.findByText("Synthetic response unavailable");
  view.rerender(<View open={false} />); view.rerender(<View />); await screen.findByText("Stored question");
  expect(screen.getByLabelText(label)).toHaveValue("Body with an uncertain result");
  fireEvent.click(screen.getByRole("button", { name: button }));
  await waitFor(() => expect(api.write).toHaveBeenCalledTimes(2));
  expect(api.write.mock.calls[1]).toEqual(api.write.mock.calls[0]);
  expect(api.write.mock.calls[0][3]).toEqual(expect.any(String));
  await waitFor(() => expect(screen.getByLabelText(label)).toHaveValue(""));
});
