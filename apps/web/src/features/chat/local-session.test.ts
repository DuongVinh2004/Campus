import { afterEach, expect, it, vi } from "vitest";
import { localTokenExpired, renewExpiredLocalToken, SessionRenewalError } from "./local-session";

const expired = btoa(JSON.stringify({ exp: 1 })) + ".signature";
afterEach(() => { vi.restoreAllMocks(); window.localStorage.removeItem("campus247_token"); });
it("recognizes local session expiry without using client claims as authorization", () => {
  expect(localTokenExpired(expired)).toBe(true);
  expect(localTokenExpired(btoa(JSON.stringify({ exp: Date.now() / 1000 + 3600 })) + ".signature")).toBe(false);
  expect(localTokenExpired("malformed")).toBe(false);
});
it("discards an expired legacy token without renewal or storage writes", async () => {
  const fetcher = vi.spyOn(globalThis, "fetch").mockResolvedValue({ ok: true, json: async () => ({ token: "issued-session" }) } as Response);
  expect(await renewExpiredLocalToken(expired, "http://localhost:8000", new AbortController().signal)).toBeNull();
  expect(window.localStorage.getItem("campus247_token")).toBeNull();
  expect(fetcher).not.toHaveBeenCalled();
});
it("never calls a renewal endpoint even when it would deny access", async () => {
  const fetcher = vi.spyOn(globalThis, "fetch").mockResolvedValue({ ok: false, status: 401 } as Response);
  expect(await renewExpiredLocalToken(expired, "http://localhost:8000", new AbortController().signal)).toBeNull();
  expect(fetcher).not.toHaveBeenCalled();
  expect(window.localStorage.getItem("campus247_token")).toBeNull();
});
it("keeps expiry guidance without trying to recover a credential from the server", async () => {
  const fetcher = vi.spyOn(globalThis, "fetch").mockResolvedValue({ ok: false, status: 503 } as Response);
  expect(await renewExpiredLocalToken(expired, "", new AbortController().signal)).toBeNull();
  expect(fetcher).not.toHaveBeenCalled();
  expect(new SessionRenewalError(401).message).toContain("đăng nhập lại");
  expect(window.localStorage.getItem("campus247_token")).toBeNull();
});
it("does not call the session endpoint for a current or cookie-only session", async () => {
  const fetcher = vi.spyOn(globalThis, "fetch");
  expect(await renewExpiredLocalToken(null, "http://localhost:8000", new AbortController().signal)).toBeNull();
  expect(await renewExpiredLocalToken("other-auth-token", "http://localhost:8000", new AbortController().signal)).toBeNull();
  expect(fetcher).not.toHaveBeenCalled();
});
