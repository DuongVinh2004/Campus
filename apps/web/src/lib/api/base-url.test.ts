import { afterEach, describe, expect, it, vi } from "vitest";
import { CAMPUS_API_BASE_URL } from "./base-url";
import { getDataConfig } from "../data/config";
import { createGateway } from "../data/create-gateway";
import { ApiClient } from "./client";

afterEach(() => { vi.unstubAllEnvs(); vi.unstubAllGlobals(); });

describe("Campus single entry point", () => {
  it("keeps even stale public API settings on the browser origin", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "http://localhost:8000");
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8004");
    vi.stubEnv("NEXT_PUBLIC_DATA_MODE", "api");
    vi.stubEnv("NEXT_PUBLIC_ENABLE_DATA_MODE_SWITCH", "false");
    const config = getDataConfig();
    expect(config.apiBaseUrl).toBe("");
    expect(() => createGateway(config)).not.toThrow();
    const fetcher = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ status: "ok" }) });
    vi.stubGlobal("fetch", fetcher);
    await new ApiClient({ baseUrl: CAMPUS_API_BASE_URL }).get("/v1/users/me");
    expect(fetcher.mock.calls[0][0]).toBe("/v1/users/me");
    expect(fetcher.mock.calls[0][1].credentials).toBe("include");
  });
});
