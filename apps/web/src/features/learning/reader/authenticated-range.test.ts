import { describe, expect, it, vi } from "vitest";
import { authenticatedPdfRange } from "./authenticated-range";

class Transport {
  onDataRange = vi.fn();
  constructor(readonly length: number) {}
}
const api = { PDFDataRangeTransport: Transport } as unknown as Pick<typeof import("pdfjs-dist"), "PDFDataRangeTransport">;
const head = () => new Response(null, { headers: { "Content-Length": "10", "Content-Type": "application/pdf", "Accept-Ranges": "bytes", ETag: '"fixed"' } });
const rangeResponse = (body: string, overrides: Record<string, string> = {}, status = 206) => new Response(body, {
  status, headers: { "Content-Length": "3", "Content-Range": "bytes 2-4/10", ETag: '"fixed"', ...overrides },
});

describe("authenticated PDF ranges", () => {
  it("uses HEAD and bounded ranges with session and immutable If-Range, never a full GET", async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(head()).mockResolvedValueOnce(rangeResponse("abc"));
    const onError = vi.fn();
    const transport = await authenticatedPdfRange(api, "/content", { signal: new AbortController().signal, fetcher, onError });
    transport.requestDataRange(2, 5);
    await vi.waitFor(() => expect(transport.onDataRange).toHaveBeenCalledWith(2, new Uint8Array([97, 98, 99])));
    expect(fetcher.mock.calls[0][1].method).toBe("HEAD");
    expect(fetcher.mock.calls[1][1]).toMatchObject({ headers: { Range: "bytes=2-4", "If-Range": '"fixed"' }, credentials: "same-origin", redirect: "error" });
    expect(onError).not.toHaveBeenCalled();
  });
  it.each([
    ["different version", () => rangeResponse("abc", { ETag: '"changed"' })],
    ["wrong offset", () => rangeResponse("abc", { "Content-Range": "bytes 3-5/10" })],
    ["whole file fallback", () => rangeResponse("abc", {}, 200)],
    ["revoked access", () => rangeResponse("abc", {}, 403)],
    ["truncated body", () => rangeResponse("a")],
    ["oversized body", () => rangeResponse("abcd")],
  ])("rejects %s before passing bytes to PDF.js", async (_, response) => {
    const onError = vi.fn();
    const transport = await authenticatedPdfRange(api, "/content", { signal: new AbortController().signal,
      fetcher: vi.fn().mockResolvedValueOnce(head()).mockResolvedValueOnce(response()), onError });
    transport.requestDataRange(2, 5);
    await vi.waitFor(() => expect(onError).toHaveBeenCalledOnce());
    expect(transport.onDataRange).not.toHaveBeenCalled();
  });
  it("does not grant access after an unauthorized HEAD", async () => {
    await expect(authenticatedPdfRange(api, "/content", { signal: new AbortController().signal,
      fetcher: vi.fn().mockResolvedValue(new Response(null, { status: 401 })), onError: vi.fn() })).rejects.toThrow();
  });
  it("stops new range requests after reader disposal", async () => {
    const controller = new AbortController(), fetcher = vi.fn().mockResolvedValue(head());
    const transport = await authenticatedPdfRange(api, "/content", { signal: controller.signal, fetcher, onError: vi.fn() });
    controller.abort(); transport.requestDataRange(2, 5);
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
  it("resumes a failed range with the same immutable validator and rejects revoked access", async () => {
    const onError = vi.fn();
    const onPause = vi.fn<((retry: (() => void) | null) => void)>();
    const fetcher = vi.fn()
      .mockResolvedValueOnce(head())
      .mockRejectedValueOnce(new TypeError("Offline"))
      .mockResolvedValueOnce(rangeResponse("abc"))
      .mockResolvedValueOnce(rangeResponse("abc", {}, 403));
    const transport = await authenticatedPdfRange(api, "/content", {
      signal: new AbortController().signal, fetcher, onPause, onError,
    });
    transport.requestDataRange(2, 5);
    await vi.waitFor(() => expect(onPause).toHaveBeenCalledOnce());
    expect(onError).not.toHaveBeenCalled();
    onPause.mock.calls[0][0]?.();
    await vi.waitFor(() => expect(transport.onDataRange).toHaveBeenCalledTimes(1));
    expect(onPause).toHaveBeenLastCalledWith(null);
    expect(fetcher.mock.calls[2][1].headers).toEqual({ Range: "bytes=2-4", "If-Range": '"fixed"' });
    transport.requestDataRange(2, 5);
    await vi.waitFor(() => expect(onError).toHaveBeenCalledOnce());
    expect(transport.onDataRange).toHaveBeenCalledTimes(1);
  });
});
