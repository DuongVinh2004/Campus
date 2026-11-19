import type { PDFDataRangeTransport } from "pdfjs-dist";

type PdfRangeApi = Pick<typeof import("pdfjs-dist"), "PDFDataRangeTransport">;
type Fetcher = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>;
const MAX_PDF_BYTES = 50 * 1024 * 1024;
class RangeTemporarilyUnavailable extends Error {}

/** Fetch only authenticated byte ranges; never start a competing whole-file stream. */
export async function authenticatedPdfRange(pdfjs: PdfRangeApi, source: string, options: {
  signal: AbortSignal;
  onError: (error: Error) => void;
  onPause?: (retry: (() => void) | null) => void;
  fetcher?: Fetcher;
}): Promise<PDFDataRangeTransport> {
  const fetcher = options.fetcher ?? ((input, init) => fetch(input, init));
  const head = await fetcher(source, { method: "HEAD", credentials: "same-origin", cache: "no-store", redirect: "error", signal: options.signal });
  const length = Number(head.headers.get("Content-Length"));
  const etag = head.headers.get("ETag");
  if (!head.ok || !Number.isSafeInteger(length) || length <= 0 || length > MAX_PDF_BYTES
    || head.headers.get("Accept-Ranges")?.toLowerCase() !== "bytes"
    || head.headers.get("Content-Type")?.split(";")[0].trim() !== "application/pdf"
    || !etag || !/^"[^"\r\n]+"$/.test(etag)) {
    throw new Error("Không xác minh được thông tin hoặc quyền đọc PDF.");
  }
  const controller = new AbortController();
  const stop = () => controller.abort();
  if (options.signal.aborted) controller.abort();
  else options.signal.addEventListener("abort", stop, { once: true });
  const transport = new pdfjs.PDFDataRangeTransport(length, null, true);
  const deferred = new Map<string, [number, number]>();
  const active = new Set<string>();
  transport.abort = () => {
    controller.abort();
    deferred.clear();
    options.signal.removeEventListener("abort", stop);
  };
  const fetchRange = async (begin: number, end: number) => {
    if (!Number.isInteger(begin) || !Number.isInteger(end) || begin < 0 || end <= begin || end > length) {
      throw new Error("Khoảng byte PDF không hợp lệ.");
    }
    const response = await fetcher(source, {
      headers: { Range: `bytes=${begin}-${end - 1}`, "If-Range": etag },
      credentials: "same-origin", cache: "no-store", redirect: "error", signal: controller.signal,
    });
    if (response.status === 408 || response.status === 429 || response.status >= 500) {
      await response.body?.cancel();
      throw new RangeTemporarilyUnavailable();
    }
    if (response.status !== 206 || response.headers.get("ETag") !== etag
      || response.headers.get("Content-Range") !== `bytes ${begin}-${end - 1}/${length}`
      || Number(response.headers.get("Content-Length")) !== end - begin) {
      await response.body?.cancel();
      throw new Error("Nội dung PDF đã thay đổi hoặc quyền đọc không còn hiệu lực.");
    }
    const reader = response.body?.getReader();
    if (!reader) throw new Error("Chưa nhận được nội dung PDF.");
    const bytes = new Uint8Array(end - begin);
    let received = 0;
    try {
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        if (received + value.length > bytes.length) {
          await reader.cancel();
          throw new Error("PDF trả nhiều dữ liệu hơn khoảng được yêu cầu.");
        }
        bytes.set(value, received); received += value.length;
      }
    } finally { reader.releaseLock(); }
    if (received !== bytes.length) throw new Error("Khoảng byte PDF chưa đầy đủ.");
    if (!controller.signal.aborted) transport.onDataRange(begin, bytes);
  };
  const resume = () => {
    for (const [begin, end] of deferred.values()) transport.requestDataRange(begin, end);
  };
  transport.requestDataRange = (begin, end) => {
    const key = `${begin}:${end}`;
    if (controller.signal.aborted || active.has(key)) return;
    active.add(key);
    void fetchRange(begin, end).then(() => {
      active.delete(key);
      if (deferred.delete(key) && !deferred.size) options.onPause?.(null);
    }).catch(error => {
      active.delete(key);
      if (controller.signal.aborted) return;
      if (options.onPause && (error instanceof TypeError || error instanceof RangeTemporarilyUnavailable)) {
        deferred.set(key, [begin, end]);
        options.onPause(resume);
        return;
      }
      transport.abort();
      options.onPause?.(null);
      options.onError(error instanceof Error ? error : new Error("Chưa đọc được PDF."));
    });
  };
  return transport;
}
