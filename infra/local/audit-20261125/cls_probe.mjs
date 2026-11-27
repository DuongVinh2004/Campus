import { chromium } from "../../../apps/web/node_modules/@playwright/test/index.mjs";
import fs from "node:fs";
const a = JSON.parse(fs.readFileSync("infra/local/knowledge-platform-20261023/campus-directory-credentials.json", "utf8")).accounts.find(x => x.username === "sv.demo04");
const b = await chromium.launch({ executablePath: "C:/Program Files/Google/Chrome/Application/chrome.exe" });
const c = await b.newContext({ viewport: { width: 375, height: 812 }, isMobile: true });
await c.addInitScript(() => { window.__s = []; new PerformanceObserver(l => { for (const e of l.getEntries()) if (!e.hadRecentInput) window.__s.push({ v: +e.value.toFixed(3), t: Math.round(e.startTime), src: e.sources.map(s => { const n = s.node; return n && n.nodeType === 1 ? (n.tagName + "." + String(n.className).split(" ").slice(0, 3).join(".") + " «" + (n.innerText || "").slice(0, 40).replace(/\s+/g, " ") + "»") : String(n && n.nodeName); }).slice(0, 3) }); }).observe({ type: "layout-shift", buffered: true }); });
const p = await c.newPage();
await p.goto("http://127.0.0.1:8015/login"); await p.locator("input[name=username]").fill(a.username); await p.locator("input[name=password]").fill(a.password);
await p.getByRole("button", { name: "Đăng nhập", exact: true }).click(); await p.waitForURL(u => !u.pathname.startsWith("/login"));
for (const r of ["/schedule", "/rooms"]) { await p.goto("http://127.0.0.1:8015" + r); await p.waitForLoadState("networkidle").catch(() => {}); await p.waitForTimeout(1000); console.log(r, JSON.stringify(await p.evaluate(() => window.__s.sort((x, y) => y.v - x.v).slice(0, 4)))); }
await b.close();
