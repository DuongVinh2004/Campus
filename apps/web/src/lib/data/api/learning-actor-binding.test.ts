import { expect, it, vi } from "vitest";
import { LearningGateway } from "./learning-gateway";

const actor = "019a0000-0000-7000-8000-000000000001";
it("binds both reads and writes to the actor who opened the workspace", async () => {
  const fetcher = vi.fn(async () => new Response("{}"));
  const gateway = new LearningGateway(fetcher, actor);
  await gateway.request("/capabilities"); await gateway.write("/me/annotations", { body: "Synthetic private draft" });
  for (const [, options] of fetcher.mock.calls as unknown as [string, RequestInit][]) {
    expect(new Headers(options.headers).get("X-Campus-Reader-Actor")).toBe(actor);
    expect(options.credentials).toBe("include");
  }
});
it("rejects a mismatched actor header before transmitting a request", async () => {
  const fetcher = vi.fn(async () => new Response("{}"));
  await expect(new LearningGateway(fetcher, actor).request("/capabilities", {
    headers: { "X-Campus-Reader-Actor": "019a0000-0000-7000-8000-000000000002" },
  })).rejects.toMatchObject({ status: 401, code: "READER_SESSION_CHANGED" });
  expect(fetcher).not.toHaveBeenCalled();
});
