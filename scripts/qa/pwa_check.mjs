// Browser check of the offline cache on the running runtime (default http://127.0.0.1:8015):
//   node scripts/qa/pwa_check.mjs [--base URL]
// 1. the service worker registers; 2. after a session of normal use no cache holds an API address or a page that is not static;
// 3. with the network off a page shows the offline page; 4. arriving at /login empties every cache.
// Exit code 1 when a check fails. Reads the student's credentials from the local runtime folder, never prints them.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "../../apps/web/node_modules/@playwright/test/index.mjs";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const arg = (name, fallback) => { const i = process.argv.indexOf(name); return i > 0 ? process.argv[i + 1] : fallback; };
const BASE = arg("--base", "http://127.0.0.1:8015");
const creds = JSON.parse(fs.readFileSync(path.join(root, "infra/local/knowledge-platform-20261023/student-credentials.json"), "utf8"));
const failures = [];
const check = (ok, message) => { console.log(ok ? "ok  " : "FAIL", message); if (!ok) failures.push(message); };

const cacheContents = (page) => page.evaluate(async () => {
  const out = {};
  for (const name of await caches.keys()) out[name] = (await (await caches.open(name)).keys()).map((r) => new URL(r.url).pathname);
  return out;
});

const browser = await chromium.launch();
const context = await browser.newContext();
const page = await context.newPage();
await page.goto(BASE + "/login", { waitUntil: "domcontentloaded" });
const registered = await page.evaluate(async () => {
  if (!("serviceWorker" in navigator)) return "unsupported";
  const registration = await Promise.race([navigator.serviceWorker.ready, new Promise((r) => setTimeout(() => r(null), 15000))]);
  return registration ? "active" : "timeout";
});
check(registered === "active", `the service worker registers (${registered})`);

await page.locator("input[name=username]").fill(creds.username);
await page.locator("input[name=password]").fill(creds.password);
await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
await page.waitForURL((url) => !url.pathname.startsWith("/login"), { timeout: 20000 });
for (const p of ["/chat", "/rooms", "/schedule", "/notifications"]) {
  await page.goto(BASE + p, { waitUntil: "domcontentloaded" });
  await page.waitForLoadState("networkidle", { timeout: 15000 }).catch(() => {});
}
const used = await cacheContents(page);
const everything = Object.values(used).flat();
console.log("cached:", JSON.stringify(used));
check(everything.length > 0, "something is cached (the offline page and static files)");
check(everything.every((p) => !p.startsWith("/v1/") && !p.startsWith("/api/")), "no API address is in any cache");
check(everything.includes("/offline"), "the offline page is cached");

await context.setOffline(true);
await page.goto(BASE + "/rooms", { waitUntil: "domcontentloaded" }).catch(() => {});
const heading = await page.locator("h1").first().innerText().catch(() => "");
check(/ngoại tuyến/i.test(heading), `with the network off the offline page appears (heading: "${heading}")`);
await context.setOffline(false);

await page.goto(BASE + "/login", { waitUntil: "domcontentloaded" });
await page.waitForTimeout(1500);
const after = await cacheContents(page);
const left = Object.values(after).flat().filter((p) => p !== "/offline" && !p.startsWith("/icons/") && !p.startsWith("/_next/static/"));
console.log("after /login:", JSON.stringify(after));
check(left.length === 0, `arriving at /login leaves no page in any cache (left: ${left.join(", ") || "none"})`);

await browser.close();
process.exit(failures.length ? 1 : 0);
