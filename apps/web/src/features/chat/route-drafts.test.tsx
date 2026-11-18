import React from "react";
import { afterEach, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { ChatDraftActor, ChatDraftSessionProvider, chatDraftActorScope, RouteDraftChatPanel } from "./route-drafts";

afterEach(() => { cleanup(); vi.restoreAllMocks(); });
const actor = (id = "student-a", roles = ["STUDENT"]) => chatDraftActorScope({ user_id: id, roles });
function View({ active = true, scope = actor(), draftId = "new", seed = "", send = vi.fn() }: {
  active?: boolean; scope?: string | null; draftId?: string; seed?: string; send?: (value: string) => void;
}) {
  return <ChatDraftSessionProvider><ChatDraftActor value={scope}>{active
    ? <RouteDraftChatPanel draftId={draftId} initialDraft={seed} onSendMessage={send} />
    : <p>Dịch vụ học vụ</p>}</ChatDraftActor></ChatDraftSessionProvider>;
}
const composer = () => screen.getByRole("textbox", { name: "Đặt câu hỏi" }) as HTMLTextAreaElement;
const edit = (value: string) => fireEvent.change(composer(), { target: { value } });

it("restores an unsent question after the chat route unmounts and remounts", () => {
  const fetcher = vi.spyOn(globalThis, "fetch");
  const storage = vi.spyOn(Storage.prototype, "setItem");
  const view = render(<View seed="Original query" />);
  edit("Edited unsent question");
  view.rerender(<View active={false} />);
  expect(screen.queryByRole("textbox")).toBeNull();
  view.rerender(<View seed="Different query" />);
  expect(composer().value).toBe("Edited unsent question");
  expect(fetcher).not.toHaveBeenCalled();
  expect(storage).not.toHaveBeenCalled();
});

it("isolates drafts by account and restores each when its owner returns", () => {
  const view = render(<View />);
  edit("Private A");
  view.rerender(<View scope={actor("student-b")} />);
  expect(composer().value).toBe("");
  edit("Private B");
  view.rerender(<View scope={actor()} />);
  expect(composer().value).toBe("Private A");
  view.rerender(<View scope={actor("student-b")} />);
  expect(composer().value).toBe("Private B");
});

it("does not expose saved text while the account has not been verified", () => {
  const view = render(<View />);
  edit("Private A");
  view.rerender(<View scope={null} />);
  expect(screen.queryByRole("textbox")).toBeNull();
  expect(screen.getByRole("status").textContent).toContain("Đang kiểm tra tài khoản");
  view.rerender(<View />);
  expect(composer().value).toBe("Private A");
});

it("isolates changed permissions without treating role order as a new owner", () => {
  const view = render(<View scope={actor("a", ["STUDENT", "LECTURER"])} />);
  edit("Private with two roles");
  view.rerender(<View scope={actor("a", ["LECTURER", "STUDENT", "STUDENT"])} />);
  expect(composer().value).toBe("Private with two roles");
  view.rerender(<View scope={actor("a")} />);
  expect(composer().value).toBe("");
});

it("keeps independent questions for each conversation and the new-chat composer", () => {
  const view = render(<View />);
  edit("New chat draft");
  view.rerender(<View draftId="conversation-a" />);
  expect(composer().value).toBe("");
  edit("Follow-up A");
  view.rerender(<View draftId="conversation-b" />);
  expect(composer().value).toBe("");
  edit("Follow-up B");
  view.rerender(<View draftId="conversation-a" />);
  expect(composer().value).toBe("Follow-up A");
  view.rerender(<View />);
  expect(composer().value).toBe("New chat draft");
});

it("retains an explicit clear across routes even when a later query seed exists", () => {
  const view = render(<View seed="Seed" />);
  edit("");
  view.rerender(<View active={false} />);
  view.rerender(<View seed="Later seed" />);
  expect(composer().value).toBe("");
});

it("clears only the submitted composer and never resends it on route return", () => {
  const send = vi.fn();
  const view = render(<View send={send} />);
  edit("Question to send");
  fireEvent.click(screen.getByRole("button", { name: "Gửi" }));
  expect(send).toHaveBeenCalledTimes(1);
  expect(send).toHaveBeenCalledWith("Question to send");
  expect(composer().value).toBe("");
  view.rerender(<View active={false} send={send} />);
  view.rerender(<View seed="Late seed" send={send} />);
  expect(composer().value).toBe("");
  expect(send).toHaveBeenCalledTimes(1);
});

type DraftLifecycle = { created: (id: string) => boolean; accepted: () => void };
function PendingView({ draftId = "new", send }: { draftId?: string; send: (value: string, lifecycle?: DraftLifecycle) => void }) {
  return <ChatDraftSessionProvider><ChatDraftActor value={actor()}><RouteDraftChatPanel
    draftId={draftId} retainUntilAcknowledged onSendMessage={send} /></ChatDraftActor></ChatDraftSessionProvider>;
}

it("keeps an unacknowledged send and binds it to the server-created conversation", () => {
  let lifecycle: DraftLifecycle | undefined;
  const send = (_: string, value?: DraftLifecycle) => { lifecycle = value; };
  const view = render(<PendingView send={send} />);
  edit("Question pending server receipt");
  fireEvent.click(screen.getByRole("button", { name: "Gửi" }));
  expect(composer().value).toBe("Question pending server receipt");
  let bound = false;
  act(() => { bound = lifecycle?.created("created-conversation") ?? false; });
  expect(bound).toBe(true);
  view.rerender(<PendingView send={send} draftId="created-conversation" />);
  expect(composer().value).toBe("Question pending server receipt");
  act(() => lifecycle!.accepted());
  expect(composer().value).toBe("");
});

it("never clears a newer edit when the earlier question is acknowledged", () => {
  let lifecycle: DraftLifecycle | undefined;
  render(<PendingView send={(_, value) => { lifecycle = value; }} />);
  edit("Earlier question");
  fireEvent.click(screen.getByRole("button", { name: "Gửi" }));
  edit("Next unsent question");
  act(() => lifecycle!.accepted());
  expect(composer().value).toBe("Next unsent question");
});

it("preserves an explicit clear followed by retyping the same text before an acknowledgement", () => {
  let lifecycle: DraftLifecycle | undefined;
  render(<PendingView send={(_, value) => { lifecycle = value; }} />);
  edit("Same text");
  fireEvent.click(screen.getByRole("button", { name: "Gửi" }));
  edit(""); edit("Same text");
  act(() => lifecycle!.accepted());
  expect(composer().value).toBe("Same text");
});

it("refuses a conversation binding that would replace another private draft", () => {
  let lifecycle: DraftLifecycle | undefined;
  const send = (_: string, value?: DraftLifecycle) => { lifecycle = value; };
  const view = render(<PendingView send={send} draftId="existing-conversation" />);
  edit("Existing private draft");
  view.rerender(<PendingView send={send} />);
  edit("New pending question");
  fireEvent.click(screen.getByRole("button", { name: "Gửi" }));
  expect(lifecycle?.created("existing-conversation")).toBe(false);
  expect(composer().value).toBe("New pending question");
  view.rerender(<PendingView send={send} draftId="existing-conversation" />);
  expect(composer().value).toBe("Existing private draft");
});

it("keeps the earlier unacknowledged text alongside a newer unsent edit after navigation", () => {
  let lifecycle: DraftLifecycle | undefined;
  const send = (_: string, value?: DraftLifecycle) => { lifecycle = value; };
  const view = render(<PendingView send={send} />);
  edit("Earlier unacknowledged question");
  fireEvent.click(screen.getByRole("button", { name: "Gửi" }));
  edit("Newer unsent edit");
  act(() => { lifecycle!.created("created-conversation"); });
  view.rerender(<PendingView send={send} draftId="other-conversation" />);
  expect(screen.queryByText("Earlier unacknowledged question")).toBeNull();
  view.rerender(<PendingView send={send} draftId="created-conversation" />);
  expect(composer().value).toBe("Newer unsent edit");
  expect(screen.getByText("Earlier unacknowledged question")).toBeDefined();
  act(() => lifecycle!.accepted());
  expect(composer().value).toBe("Newer unsent edit");
  expect(screen.queryByText("Earlier unacknowledged question")).toBeNull();
});
