// Serves one static front-end variant from fe-variants/<name>/ and proxies /v1/* to the real API (default 8015),
// so the variant is same-origin and the login cookie just works.
//   node scripts/fe_variant_server.mjs <name> <port> [apiBase]
// /shared/* is served from fe-variants/_shared/. Unknown paths fall back to index.html (single-page apps).
import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "fe-variants");
const [name, portArg, apiArg] = process.argv.slice(2);
if (!name || !portArg) { console.error("usage: fe_variant_server.mjs <name> <port> [apiBase]"); process.exit(2); }
const api = new URL(apiArg || "http://127.0.0.1:8015");
const dir = path.join(root, name);
const TYPES = { ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".mjs": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8", ".svg": "image/svg+xml", ".json": "application/json", ".png": "image/png", ".jpg": "image/jpeg", ".webp": "image/webp", ".woff2": "font/woff2", ".ico": "image/x-icon" };

// The API accepts state-changing requests only from its own origin, so the proxy presents itself as the API's origin.
function sameOriginHeaders(headers) {
  const out = { ...headers, host: api.host };
  if (out.origin) out.origin = api.origin;
  if (out.referer) out.referer = api.origin + "/";
  return out;
}

function serveFile(res, file) {
  fs.readFile(file, (err, data) => {
    if (err) { res.writeHead(404); res.end("not found"); return; }
    res.writeHead(200, { "Content-Type": TYPES[path.extname(file)] || "application/octet-stream", "Cache-Control": "no-store" });
    res.end(data);
  });
}

http.createServer((req, res) => {
  const url = new URL(req.url, "http://x");
  if (url.pathname.startsWith("/v1/") || url.pathname === "/health/ready") {
    const proxied = http.request({ hostname: api.hostname, port: api.port, path: req.url, method: req.method, agent: false, headers: { ...sameOriginHeaders(req.headers), connection: "close" } }, (up) => {
      res.writeHead(up.statusCode || 502, up.headers);
      up.pipe(res);
    });
    proxied.on("error", (e) => { console.error("proxy error:", e.code, e.message); res.writeHead(502); res.end("api unreachable"); });
    req.pipe(proxied);
    return;
  }
  const base = url.pathname.startsWith("/shared/") ? path.join(root, "_shared") : dir;
  const rel = url.pathname.startsWith("/shared/") ? url.pathname.slice(8) : url.pathname.slice(1);
  const file = path.normalize(path.join(base, rel || "index.html"));
  if (!file.startsWith(base)) { res.writeHead(403); res.end(); return; }
  if (fs.existsSync(file) && fs.statSync(file).isFile()) return serveFile(res, file);
  return serveFile(res, path.join(dir, "index.html"));
}).listen(Number(portArg), "127.0.0.1", () => console.log(`variant ${name} on http://127.0.0.1:${portArg}`));
