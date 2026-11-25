// Lab Web Vitals on 8015 (no Lighthouse in the repo): TTFB, FCP, LCP, CLS, transferred JS per page, cold and warm load.
//   node infra/local/audit-20261125/web_vitals.mjs
import { chromium } from "../../../apps/web/node_modules/@playwright/test/index.mjs";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, "../../..");
const BASE = "http://127.0.0.1:8015";
const account = JSON.parse(fs.readFileSync(path.join(root, "infra/local/knowledge-platform-20261023/campus-directory-credentials.json"), "utf8")).accounts.find((a) => a.username === "sv.demo04");
const owner = JSON.parse(fs.readFileSync(path.join(root, "infra/local/knowledge-platform-20261023/owner-credentials.json"), "utf8"));
const browser = await chromium.launch({ executablePath: "C:/Program Files/Google/Chrome/Application/chrome.exe" });

const observe = () => {
  window.__v = { lcp: 0, cls: 0 };
  new PerformanceObserver((l) => { for (const e of l.getEntries()) window.__v.lcp = e.startTime; }).observe({ type: "largest-contentful-paint", buffered: true });
  new PerformanceObserver((l) => { for (const e of l.getEntries()) if (!e.hadRecentInput) window.__v.cls += e.value; }).observe({ type: "layout-shift", buffered: true });
};

async function measure(who, creds, pages, mobile) {
  const context = await browser.newContext(mobile ? { viewport: { width: 375, height: 812 }, deviceScaleFactor: 2, isMobile: true } : { viewport: { width: 1360, height: 860 } });
  await context.addInitScript(observe);
  const page = await context.newPage();
  await page.goto(BASE + "/login");
  await page.locator("input[name=username]").fill(creds.username);
  await page.locator("input[name=password]").fill(creds.password);
  await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
  await page.waitForURL((u) => !u.pathname.startsWith("/login"), { timeout: 20000 });
  const rows = [];
  for (const route of pages) {
    for (const pass of ["cold", "warm"]) {
      if (pass === "cold") { const cdp = await context.newCDPSession(page); await cdp.send("Network.clearBrowserCache"); await cdp.detach(); }
      let js = 0;
      const onResponse = async (r) => { if (r.url().includes("/_next/static/") && r.url().endsWith(".js")) { try { js += (await r.body()).length; } catch { /* aborted */ } } };
      page.on("response", onResponse);
      await page.goto(BASE + route, { waitUntil: "load" });
      await page.waitForLoadState("networkidle", { timeout: 15000 }).catch(() => undefined);
      await page.waitForTimeout(800);
      page.off("response", onResponse);
      const m = await page.evaluate(() => {
        const nav = performance.getEntriesByType("navigation")[0];
        const fcp = performance.getEntriesByName("first-contentful-paint")[0];
        return { ttfb: Math.round(nav.responseStart), fcp: Math.round(fcp ? fcp.startTime : -1), lcp: Math.round(window.__v.lcp), cls: +window.__v.cls.toFixed(3), load: Math.round(nav.loadEventEnd) };
      });
      rows.push({ who, mobile, route, pass, ...m, jsKB: Math.round(js / 1024) });
    }
  }
  await context.close();
  return rows;
}

const rows = [
  ...(await measure("student", account, ["/chat", "/schedule", "/tickets", "/rooms", "/learning"], false)),
  ...(await measure("student", account, ["/chat", "/schedule"], true)),
  ...(await measure("owner", owner, ["/admin", "/knowledge/sources"], false)),
];
await browser.close();
fs.writeFileSync(path.join(here, "web_vitals.json"), JSON.stringify(rows, null, 1));
for (const r of rows) console.log([r.who, r.mobile ? "m" : "d", r.route, r.pass, `ttfb=${r.ttfb}`, `fcp=${r.fcp}`, `lcp=${r.lcp}`, `cls=${r.cls}`, `load=${r.load}`, `js=${r.jsKB}KB`].join(" "));
