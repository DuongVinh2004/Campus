import { afterEach, expect, it, vi } from "vitest";
import { ApiClient } from "./client";
import { ApiCertificateGateway } from "../data/api/certificate-gateway";
import { ApiServiceGateway } from "../data/api/service-gateway";

afterEach(() => vi.restoreAllMocks());
it("uses cookies for API, demo login, logout and downloads without touching browser tokens", async () => {
  const read = vi.spyOn(Storage.prototype, "getItem");
  const write = vi.spyOn(Storage.prototype, "setItem");
  const remove = vi.spyOn(Storage.prototype, "removeItem");
  const fetcher = vi.spyOn(globalThis, "fetch").mockImplementation(async () => new Response(JSON.stringify({ user: { user_id: "fixture-user" } })));
  await new ApiClient().get("/v1/users/me");
  const certificate = new ApiCertificateGateway();
  await expect(certificate.login("SV01")).resolves.toEqual({ user_id: "fixture-user" });
  await certificate.result("fixture"); await new ApiServiceGateway().download("fixture", "result"); await certificate.logout();
  expect(read).not.toHaveBeenCalled(); expect(write).not.toHaveBeenCalled(); expect(remove).not.toHaveBeenCalled();
  for (const [, init] of fetcher.mock.calls) {
    expect(init?.credentials).toBe("include");
    expect(new Headers(init?.headers).has("Authorization")).toBe(false);
  }
});
