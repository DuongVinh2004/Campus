import { describe, expect, it, vi } from "vitest";
import { LearningGateway } from "./learning-gateway";

const id = "019a0000-0000-7000-8000-000000000001";
const file = () => new File(["synthetic PDF"], "audit.pdf", { type: "application/pdf" });
const ok = (value: unknown) => new Response(JSON.stringify(value), { status: 200 });

describe("learning upload cancellation across steps", () => {
  it("does not create an intent when the caller already canceled", async () => {
    const controller = new AbortController(); controller.abort();
    const fetcher = vi.fn().mockResolvedValue(ok({ id }));
    await expect(new LearningGateway(fetcher).upload(id, file(), controller.signal)).rejects.toMatchObject({ name: "AbortError" });
    expect(fetcher).not.toHaveBeenCalled();
  });

  it("does not send completion after cancellation at the end of content transfer", async () => {
    const controller = new AbortController();
    const fetcher = vi.fn().mockResolvedValueOnce(ok({ id }))
      .mockImplementationOnce(async () => { controller.abort(); return ok({ state: "RECEIVED" }); })
      .mockResolvedValueOnce(ok({ id, processing_state: "QUEUED" }));
    await expect(new LearningGateway(fetcher).upload(id, file(), controller.signal)).rejects.toMatchObject({ name: "AbortError" });
    expect(fetcher).toHaveBeenCalledTimes(2);
    expect(fetcher.mock.calls.some(([url]) => String(url).endsWith("/complete"))).toBe(false);
  });

  it("passes the same cancellation signal to intent, content and completion", async () => {
    const controller = new AbortController();
    const fetcher = vi.fn().mockResolvedValueOnce(ok({ id }))
      .mockResolvedValueOnce(ok({ state: "RECEIVED" }))
      .mockResolvedValueOnce(ok({ id, processing_state: "QUEUED" }));
    await new LearningGateway(fetcher).upload(id, file(), controller.signal);
    expect(fetcher).toHaveBeenCalledTimes(3);
    for (const [, init] of fetcher.mock.calls) expect((init as RequestInit).signal).toBe(controller.signal);
  });

  it("retains the returned intent ID for explicit cancellation without uploading its body", async () => {
    const controller = new AbortController();
    const onIntent = vi.fn();
    const fetcher = vi.fn().mockImplementationOnce(async () => { controller.abort(); return ok({ id }); });
    await expect(new LearningGateway(fetcher).upload(id, file(), controller.signal, onIntent)).rejects.toMatchObject({ name: "AbortError" });
    expect(onIntent).toHaveBeenCalledWith(id);
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
});
