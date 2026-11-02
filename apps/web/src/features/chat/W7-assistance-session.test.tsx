import React from "react";
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { AssistanceContextPanel } from "../assistance/AssistanceContextPanel";

afterEach(() => { cleanup(); vi.restoreAllMocks(); window.localStorage.removeItem("campus247_token"); window.history.replaceState(null, "", "/chat"); });
it("resolves assistance with cookies and returns to the same resource after login", async () => {
  window.history.replaceState(null, "", "/services?id=fixture");
  window.localStorage.setItem("campus247_token", "legacy-fixture");
  const read = vi.spyOn(window.localStorage, "getItem");
  const write = vi.spyOn(window.localStorage, "setItem");
  const fetcher = vi.spyOn(globalThis, "fetch").mockResolvedValue({ ok: false, status: 401 } as Response);
  render(<AssistanceContextPanel id="fixture" version={7} />);
  fireEvent.click(screen.getByRole("button", { name: "Đối chiếu hồ sơ và nguồn" }));
  await screen.findByText(/Phiên đăng nhập đã hết hạn/);
  expect(screen.getByRole("link", { name: "Đăng nhập lại" }).getAttribute("href")).toBe("/login?redirect=%2Fservices%3Fid%3Dfixture");
  expect(fetcher).toHaveBeenCalledTimes(1);
  const options = fetcher.mock.calls[0][1];
  expect(options?.credentials).toBe("include");
  expect(new Headers(options?.headers).has("Authorization")).toBe(false);
  expect(JSON.parse(String(options?.body)).resource).toEqual({ kind: "service_request", id: "fixture", expected_version: 7 });
  expect(read.mock.calls.some(([key]) => key === "campus247_token")).toBe(false);
  expect(write.mock.calls.some(([key]) => key === "campus247_token")).toBe(false);
});
