import { describe, expect, it, vi } from "vitest";
import { LearningApiError, LearningGateway, learningContentPath, learningId } from "./learning-gateway";

const version = "019a0000-0000-7000-8000-000000000001";
const respond = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status, headers: { "Content-Type": "application/json" } });

describe("learning authenticated transport", () => {
  it("keeps credentials on the Campus origin with no-store and no bearer token", async () => {
    const fetcher = vi.fn(async () => respond({ enabled: true }));
    await new LearningGateway(fetcher).capabilities();
    const [path, init] = fetcher.mock.calls[0] as unknown as [string, RequestInit];
    expect(path).toBe("/v1/learning/capabilities");
    expect(init).toMatchObject({ credentials: "include", cache: "no-store", redirect: "error" });
    expect(new Headers(init.headers).has("Authorization")).toBe(false);
  });
  it("does not call the browser fetch with a LearningGateway receiver", async () => {
    const original=globalThis.fetch;
    globalThis.fetch=function(this: unknown) {
      if(this instanceof LearningGateway)throw new TypeError("Illegal invocation");
      return Promise.resolve(respond({available:true}));
    };
    try {await expect(new LearningGateway().capabilities()).resolves.toMatchObject({available:true});}
    finally {globalThis.fetch=original;}
  });
  it("does not expose private server error details", async () => {
    const gateway = new LearningGateway(async () => respond({ code: "MISSING", detail: "C:/private/doc.pdf" }, 404));
    await expect(gateway.capabilities()).rejects.toMatchObject({ status: 404, code: "MISSING" });
    await expect(gateway.capabilities()).rejects.not.toThrow("private");
  });
  it("preserves abort rather than retrying navigation", async () => {
    const gateway = new LearningGateway(async () => { throw new DOMException("aborted", "AbortError"); });
    await expect(gateway.capabilities()).rejects.toMatchObject({ name: "AbortError" });
  });
  it("follows cursor pages and encodes the cursor", async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(respond({ items: [{ id: "first" }], page: { next_cursor: "a&role=admin" } }))
      .mockResolvedValueOnce(respond({ items: [{ id: "second" }], page: { next_cursor: null } }));
    const result = await new LearningGateway(fetcher).list("/offerings");
    expect(result).toEqual([{ id: "first" }, { id: "second" }]);
    expect(fetcher.mock.calls[1][0]).toBe("/v1/learning/offerings?limit=100&cursor=a%26role%3Dadmin");
  });
  it("rejects invalid collection instead of presenting fake empty data", async () => {
    await expect(new LearningGateway(async () => respond({ rows: [] })).list("/offerings")).rejects.toBeInstanceOf(LearningApiError);
  });
  it("uses an explicit idempotency key for a mutation", async () => {
    const fetcher = vi.fn(async () => respond({ id: version }));
    await new LearningGateway(fetcher).write("/courses", { code: "C1", name: "Course" }, "POST", "create:course:1");
    const [, init] = fetcher.mock.calls[0] as unknown as [string, RequestInit];
    expect(new Headers(init.headers).get("Idempotency-Key")).toBe("create:course:1");
    expect(init.body).toBe(JSON.stringify({ code: "C1", name: "Course" }));
  });
  it("rejects a returned reader URL outside the protected endpoint", async () => {
    const gateway = new LearningGateway(async () => respond({ id: version, version_id: version, page_count: 2, content_path: "https://evil.example/pdf" }));
    await expect(gateway.reader(version)).rejects.toThrow("Đường dẫn tài liệu");
  });
  it.each([['lesson.pdf','application/pdf'],['lesson.PPTX','application/vnd.openxmlformats-officedocument.presentationml.presentation']])("sends %s with matching intent and stream media type",async(filename,contentType)=>{
    const fetcher=vi.fn().mockResolvedValueOnce(respond({id:version})).mockResolvedValueOnce(respond({state:'RECEIVED'})).mockResolvedValueOnce(respond({id:version,processing_state:'QUEUED'}));
    const file=new File(['synthetic'],filename,{type:''});
    await new LearningGateway(fetcher).upload(version,file);
    const intent=fetcher.mock.calls[0][1] as RequestInit,stream=fetcher.mock.calls[1][1] as RequestInit;
    expect(JSON.parse(String(intent.body))).toMatchObject({filename,content_type:contentType,byte_size:file.size});
    expect(new Headers(stream.headers).get('Content-Type')).toBe(contentType);
    expect(stream.body).toBe(file);
    expect(stream.credentials).toBe('include');
  });
  it("rejects traversal, uppercase or non-canonical identity paths", () => {
    expect(learningId(version)).toBe(version);
    for (const id of ["../x", "//x", "", version.toUpperCase()]) {
      if (id === version) continue;
      expect(() => learningId(id)).toThrow();
    }
    expect(() => learningContentPath(`/v1/learning/versions/${version}/content?token=secret`, version)).toThrow();
  });
});
