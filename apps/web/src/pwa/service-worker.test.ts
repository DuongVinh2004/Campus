// @vitest-environment node
import { readFileSync } from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { beforeEach, describe, expect, it } from "vitest";

const SOURCE = readFileSync(path.resolve(__dirname, "../../public/sw.js"), "utf8");
const ORIGIN = "https://chat.example.edu.vn";

class FakeResponse {
  status: number;
  type = "basic";
  headers: Map<string, string>;
  constructor(public body: string, init: { status?: number; headers?: Record<string, string> } = {}) {
    this.status = init.status ?? 200;
    this.headers = new Map(Object.entries(init.headers ?? {}).map(([k, v]) => [k.toLowerCase(), v]));
  }
  clone() {
    return new FakeResponse(this.body, { status: this.status, headers: Object.fromEntries(this.headers) });
  }
}
Object.assign(FakeResponse.prototype, { headers: undefined });

/** Loads sw.js into an isolated context with a fake Cache Storage and a fake network, then returns the listeners it registered. */
function load(network: (url: string, request: FakeRequest) => FakeResponse | Promise<FakeResponse>) {
  const stores = new Map<string, Map<string, FakeResponse>>();
  const listeners: Record<string, (event: any) => void> = {};
  const fetched: string[] = [];
  const caches = {
    open: async (name: string) => {
      if (!stores.has(name)) stores.set(name, new Map());
      const store = stores.get(name)!;
      return {
        addAll: async (urls: string[]) => urls.forEach((u) => store.set(ORIGIN + u, new FakeResponse("precached " + u))),
        put: async (request: FakeRequest | string, response: FakeResponse) => store.set(typeof request === "string" ? request : request.url, response),
      };
    },
    match: async (request: FakeRequest | string) => {
      const key = typeof request === "string" ? (request.startsWith("http") ? request : ORIGIN + request) : request.url;
      for (const store of stores.values()) if (store.has(key)) return store.get(key);
      return undefined;
    },
    keys: async () => [...stores.keys()],
    delete: async (name: string) => stores.delete(name),
  };
  const context = {
    self: { location: { origin: ORIGIN }, addEventListener: (type: string, fn: (e: any) => void) => (listeners[type] = fn), skipWaiting: async () => undefined, clients: { claim: async () => undefined } },
    caches,
    fetch: async (request: FakeRequest) => {
      fetched.push(request.url);
      return network(request.url, request);
    },
    Response: Object.assign(FakeResponse, { error: () => new FakeResponse("network error", { status: 0 }) }),
    URL,
  };
  vm.runInNewContext(SOURCE, context);
  return { listeners, stores, fetched };
}

interface FakeRequest {
  url: string;
  method: string;
  mode: string;
  headers: { has: (name: string) => boolean };
}
const request = (pathname: string, over: Partial<FakeRequest> & { range?: boolean } = {}): FakeRequest => ({
  url: ORIGIN + pathname, method: "GET", mode: "no-cors", headers: { has: (name) => name === "range" && !!over.range }, ...over,
});

/** Fires a fetch event; returns the response if the worker answered, or "passthrough" if it left the request to the browser. */
async function dispatch(listeners: Record<string, (e: any) => void>, req: FakeRequest) {
  let answer: Promise<FakeResponse> | undefined;
  listeners.fetch({ request: req, respondWith: (promise: Promise<FakeResponse>) => (answer = promise) });
  return answer ? await answer : "passthrough";
}

async function lifecycle(listeners: Record<string, (e: any) => void>, type: "install" | "activate") {
  let work: Promise<unknown> = Promise.resolve();
  listeners[type]({ waitUntil: (promise: Promise<unknown>) => (work = promise) });
  await work;
}

describe("service worker", () => {
  let sw: ReturnType<typeof load>;
  beforeEach(() => {
    sw = load((url) => new FakeResponse("network " + url));
  });

  it("precaches the offline page and the icons on install", async () => {
    await lifecycle(sw.listeners, "install");
    expect([...sw.stores.get("campus247-sw-v1-static")!.keys()].sort()).toEqual([ORIGIN + "/icons/icon-192.png", ORIGIN + "/icons/icon-512.png", ORIGIN + "/offline"]);
  });

  it("on activate deletes caches of older versions and keeps its own", async () => {
    await lifecycle(sw.listeners, "install");
    sw.stores.set("campus247-sw-v0-static", new Map());
    sw.stores.set("something-else", new Map());
    await lifecycle(sw.listeners, "activate");
    expect([...sw.stores.keys()]).toEqual(["campus247-sw-v1-static"]);
  });

  it.each(["/v1/conversations", "/v1/auth/oidc/start", "/api/anything", "/health/live", "/metrics"])("never touches %s", async (pathname) => {
    expect(await dispatch(sw.listeners, request(pathname))).toBe("passthrough");
    expect(sw.fetched).toEqual([]);
  });

  it("never touches non-GET requests, downloads with Range, or other origins", async () => {
    expect(await dispatch(sw.listeners, request("/_next/static/a.js", { method: "POST" }))).toBe("passthrough");
    expect(await dispatch(sw.listeners, request("/_next/static/a.js", { range: true }))).toBe("passthrough");
    expect(await dispatch(sw.listeners, { ...request("/x"), url: "https://evil.example/_next/static/a.js" })).toBe("passthrough");
  });

  it("shows the offline page when a navigation fails, and never stores a page it did load", async () => {
    await lifecycle(sw.listeners, "install");
    const online = await dispatch(sw.listeners, request("/chat", { mode: "navigate" }));
    expect((online as FakeResponse).body).toBe("network " + ORIGIN + "/chat");
    expect([...sw.stores.keys()]).toEqual(["campus247-sw-v1-static"]);
    expect([...sw.stores.get("campus247-sw-v1-static")!.keys()]).not.toContain(ORIGIN + "/chat");
    const offline = load(() => { throw new Error("offline"); });
    await lifecycle(offline.listeners, "install");
    expect(((await dispatch(offline.listeners, request("/chat", { mode: "navigate" }))) as FakeResponse).body).toBe("precached /offline");
  });

  it("caches hashed static files and serves them from the cache next time", async () => {
    const first = await dispatch(sw.listeners, request("/_next/static/chunks/app-123.js"));
    expect((first as FakeResponse).body).toContain("network");
    await new Promise((resolve) => setTimeout(resolve, 0));
    await dispatch(sw.listeners, request("/_next/static/chunks/app-123.js"));
    expect(sw.fetched.filter((url) => url.endsWith("app-123.js"))).toHaveLength(1);
  });

  it.each([
    [{ headers: { "Cache-Control": "no-store" } }, "no-store"],
    [{ headers: { "Cache-Control": "private, max-age=60" } }, "private"],
    [{ headers: { "Set-Cookie": "auth_token=x" } }, "a cookie"],
    [{ status: 500 }, "an error"],
  ])("does not keep a static response with %j (%s)", async (init: { headers?: Record<string, string>; status?: number }, _label: string) => {
    const worker = load(() => new FakeResponse("body", init));
    await dispatch(worker.listeners, request("/_next/static/x.js"));
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(worker.stores.size === 0 || ![...worker.stores.values()].some((store) => store.has(ORIGIN + "/_next/static/x.js"))).toBe(true);
  });

  it("forgets every cache when the page asks, for example after signing out", async () => {
    await lifecycle(sw.listeners, "install");
    let work: Promise<unknown> = Promise.resolve();
    sw.listeners.message({ data: { type: "campus247:clear-caches" }, waitUntil: (p: Promise<unknown>) => (work = p) });
    await work;
    expect(sw.stores.size).toBe(0);
    sw.listeners.message({ data: { type: "other" }, waitUntil: () => { throw new Error("must not run"); } });
  });
});
