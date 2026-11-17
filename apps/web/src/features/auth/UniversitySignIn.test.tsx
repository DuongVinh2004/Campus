import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { ApiClientError } from "@/lib/api/client";
import { returnPath, SIGN_IN_ERRORS, signInErrorMessage, UniversitySignIn } from "./UniversitySignIn";

const fetchMock = vi.fn();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

describe("UniversitySignIn", () => {
  it("shows a link to the server's start address when the provider is offered", async () => {
    fetchMock.mockResolvedValue(json(200, { providers: [{ id: "oidc", label: "Tài khoản trường" }] }));
    render(<UniversitySignIn search="?next=%2Fknowledge%2Fsources" />);
    const link = await screen.findByRole("link", { name: "Đăng nhập bằng tài khoản trường" });
    expect(link.getAttribute("href")).toBe("/v1/auth/oidc/start?next=%2Fknowledge%2Fsources");
    expect(fetchMock.mock.calls[0][0]).toBe("/v1/auth/providers");
  });

  it("renders nothing when sign-in with the school account is not configured (the endpoint does not exist)", async () => {
    fetchMock.mockResolvedValue(json(404, { status: 404, code: "NOT_FOUND", title: "x", detail: "x", type: "x" }));
    const { container } = render(<UniversitySignIn search="" />);
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(container.innerHTML).toBe("");
  });

  it("renders nothing when the request fails or the server offers another provider", async () => {
    fetchMock.mockRejectedValueOnce(new Error("offline"));
    const first = render(<UniversitySignIn search="" />);
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(first.container.innerHTML).toBe("");
    first.unmount();
    fetchMock.mockResolvedValueOnce(json(200, { providers: [{ id: "saml", label: "SAML" }] }));
    const second = render(<UniversitySignIn search="" />);
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(second.container.innerHTML).toBe("");
  });

  it("explains a failure code in Vietnamese even when the button is not available", async () => {
    fetchMock.mockRejectedValue(new Error("offline"));
    render(<UniversitySignIn search="?error=ACCOUNT_NOT_PROVISIONED" />);
    expect((await screen.findByTestId("university-sign-in-error")).textContent).toBe(SIGN_IN_ERRORS.ACCOUNT_NOT_PROVISIONED);
    expect(screen.getByRole("alert")).toBeDefined();
  });

  it("never prints text from the address bar: an unknown code gets the generic message", async () => {
    fetchMock.mockResolvedValue(json(200, { providers: [{ id: "oidc", label: "x" }] }));
    render(<UniversitySignIn search="?error=%3Cscript%3Ealert(1)%3C%2Fscript%3E" />);
    const message = (await screen.findByTestId("university-sign-in-error")).textContent!;
    expect(message).not.toContain("script");
    expect(message).toContain("không thành công");
  });
});

describe("helpers", () => {
  it("maps every known code and falls back for unknown or missing ones", () => {
    for (const code of Object.keys(SIGN_IN_ERRORS)) expect(signInErrorMessage(code)).toBe(SIGN_IN_ERRORS[code]);
    expect(signInErrorMessage(null)).toBeNull();
    expect(signInErrorMessage("SOMETHING_NEW")).toContain("không thành công");
  });

  it.each([["/chat", "/chat"], ["//evil.example", "/"], ["https://evil.example", "/"], ["/\\evil", "/"], [null, "/"], ["", "/"]])(
    "return path %s becomes %s", (input, expected) => expect(returnPath(input as string | null)).toBe(expected));

  it("treats ApiClientError from a 404 as 'not available'", () => {
    expect(new ApiClientError({ type: "x", title: "t", status: 404, detail: "d", code: "NOT_FOUND" }).problem.status).toBe(404);
  });
});
