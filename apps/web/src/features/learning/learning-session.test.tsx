import React from "react";
import { afterEach, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { announceSessionChange, LearningSessionNotice, PreservedActivity, useLearningSession } from "./learning-session";

const actor = "019a0000-0000-7000-8000-000000000001";
const other = "019a0000-0000-7000-8000-000000000002";
const identity = (user_id = actor) => new Response(JSON.stringify({ user_id }));
function Harness() {
  const session = useLearningSession(actor);
  return <><LearningSessionNotice state={session.state} onCheck={() => void session.check()} />
    <PreservedActivity mode={session.state === "ready" ? "visible" : "hidden"}>
      <label>Private draft<input defaultValue="" /></label>
    </PreservedActivity></>;
}
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

it("hides the prior actor's content and restores an unsent draft only for that actor", async () => {
  vi.stubGlobal("BroadcastChannel", undefined);
  const fetcher = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(identity(other)).mockResolvedValueOnce(identity());
  render(<Harness />);
  fireEvent.change(screen.getByRole("textbox", { name: "Private draft" }), { target: { value: "Unsent private text" } });
  fireEvent(window, new Event("focus"));
  await screen.findByText(/Tài khoản đăng nhập đã thay đổi/);
  expect(screen.queryByRole("textbox", { name: "Private draft" })).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Kiểm tra lại tài khoản" }));
  expect((await screen.findByRole("textbox", { name: "Private draft" }) as HTMLInputElement).value).toBe("Unsent private text");
  expect(fetcher).toHaveBeenCalledTimes(2);
  expect(fetcher.mock.calls.every(([, init]) => init?.credentials === "include" && init?.cache === "no-store")).toBe(true);
});

it.each([401, 503, "network"] as const)("conceals private content when session validation returns %s", async status => {
  vi.stubGlobal("BroadcastChannel", undefined);
  const fetcher = vi.spyOn(globalThis, "fetch");
  if (status === "network") fetcher.mockRejectedValueOnce(new Error("private transport detail"));
  else fetcher.mockResolvedValueOnce(new Response("{}", { status }));
  render(<Harness />);
  fireEvent(window, new Event("focus"));
  await screen.findByRole("alert");
  expect(screen.queryByRole("textbox", { name: "Private draft" })).toBeNull();
  expect(screen.queryByText("private transport detail")).toBeNull();
  expect(fetcher).toHaveBeenCalledTimes(1);
});

it("ignores a stale identity response after a newer account check", async () => {
  vi.stubGlobal("BroadcastChannel", undefined);
  let finishOld!: (response: Response) => void;
  vi.spyOn(globalThis, "fetch").mockImplementationOnce(() => new Promise(resolve => { finishOld = resolve; }))
    .mockResolvedValueOnce(identity(other));
  render(<Harness />);
  fireEvent(window, new Event("focus")); fireEvent(window, new Event("focus"));
  await screen.findByText(/Tài khoản đăng nhập đã thay đổi/);
  await act(async () => { finishOld(identity()); });
  expect(screen.queryByRole("textbox", { name: "Private draft" })).toBeNull();
});

it("broadcasts a credential-free hint and always leaves identity checks to the server", () => {
  const channel = { postMessage: vi.fn(), close: vi.fn() };
  vi.stubGlobal("BroadcastChannel", vi.fn(function () { return channel; }));
  announceSessionChange();
  expect(channel.postMessage).toHaveBeenCalledWith("changed");
  expect(channel.close).toHaveBeenCalledTimes(1);
});

it("keeps the view during the periodic check while it is pending, but hides it once the account changed", async () => {
  vi.useFakeTimers();
  try {
    vi.stubGlobal("BroadcastChannel", undefined);
    let finish!: (response: Response) => void;
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(() => new Promise(resolve => { finish = resolve; }));
    render(<Harness />);
    const field = screen.getByRole("textbox", { name: "Private draft" });
    field.focus();
    await act(async () => { await vi.advanceTimersByTimeAsync(30000); });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(screen.queryByText("Đang kiểm tra lại tài khoản…")).toBeNull();
    expect(document.activeElement).toBe(field);
    await act(async () => { finish(identity()); });
    expect(screen.getByRole("textbox", { name: "Private draft" })).toBe(field);
    await act(async () => { await vi.advanceTimersByTimeAsync(30000); });
    await act(async () => { finish(identity(other)); });
    expect(screen.getByText(/Tài khoản đăng nhập đã thay đổi/)).toBeTruthy();
    expect(screen.queryByRole("textbox", { name: "Private draft" })).toBeNull();
  } finally { vi.useRealTimers(); }
});
