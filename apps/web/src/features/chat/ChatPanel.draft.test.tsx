import React from "react";
import { renderToString } from "react-dom/server";
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { ChatPanel } from "./ChatPanel";
import { PreservedActivity as Activity } from "../learning/learning-session";

afterEach(cleanup);
const composer = () => screen.getByRole("textbox", { name: "Đặt câu hỏi" }) as HTMLTextAreaElement;

it("preserves an edit when a search seed arrives after typing", () => {
  const view = render(<ChatPanel initialDraft="" />);
  fireEvent.change(composer(), { target: { value: "Unsent manual question" } });
  view.rerender(<ChatPanel initialDraft="Late search question" />);
  expect(composer().value).toBe("Unsent manual question");
});

it("preserves an explicitly cleared composer when a different seed arrives", () => {
  const view = render(<ChatPanel initialDraft="First search" />);
  fireEvent.change(composer(), { target: { value: "" } });
  view.rerender(<ChatPanel initialDraft="Late search question" />);
  expect(composer().value).toBe("");
});

it("applies a late search seed to an untouched composer", () => {
  const view = render(<ChatPanel initialDraft="" />);
  view.rerender(<ChatPanel initialDraft="Late search question" />);
  expect(composer().value).toBe("Late search question");
});

it("does not resurrect a submitted question when a seed arrives later", () => {
  const send = vi.fn();
  const view = render(<ChatPanel initialDraft="First search" onSendMessage={send} />);
  fireEvent.click(screen.getByRole("button", { name: "Gửi" }));
  expect(send).toHaveBeenCalledWith("First search");
  view.rerender(<ChatPanel initialDraft="Late search question" onSendMessage={send} />);
  expect(composer().value).toBe("");
  expect(send).toHaveBeenCalledTimes(1);
});

it("retains a manual draft when a seed changes while the session is concealed", () => {
  const view = render(<Activity mode="visible"><ChatPanel initialDraft="First search" /></Activity>);
  fireEvent.change(composer(), { target: { value: "Private unsent edit" } });
  view.rerender(<Activity mode="hidden"><ChatPanel initialDraft="Late search question" /></Activity>);
  view.rerender(<Activity mode="visible"><ChatPanel initialDraft="Late search question" /></Activity>);
  expect(composer().value).toBe("Private unsent edit");
});

it("leaves a parent-controlled composer authoritative", () => {
  const change = vi.fn();
  const view = render(<ChatPanel composerValue="Parent draft" onComposerChange={change} />);
  view.rerender(<ChatPanel composerValue="Parent draft" onComposerChange={change} initialDraft="Late search" />);
  expect(composer().value).toBe("Parent draft");
  expect(change).not.toHaveBeenCalled();
});

it("blocks typing in server HTML until the input handlers are ready", () => {
  const html = document.createElement("div");
  html.innerHTML = renderToString(<ChatPanel initialDraft="Search" />);
  expect(html.querySelector("textarea")?.disabled).toBe(true);
  render(<ChatPanel initialDraft="Search" />);
  expect(composer().disabled).toBe(false);
  expect(composer().value).toBe("Search");
});
