import { chromium } from "../apps/web/node_modules/@playwright/test/index.mjs";
import fs from "node:fs";

const root = "C:/Users/Duong Vinh/Vinh/infra/local/knowledge-platform-20261023/";
const out = process.argv[2] || "infra/local/ui-shots";
fs.mkdirSync(out, { recursive: true });
const role = process.argv[3] || "student";
const pages = (process.argv[4] || "chat,rooms,schedule,tickets,notifications,").split(",").map((p) => "/" + p.replace(/^\/+/, ""));
const cred = JSON.parse(fs.readFileSync(root + role + "-credentials.json", "utf8"));
const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1360, height: 860 } });
const res = await ctx.request.post("http://127.0.0.1:8015/v1/knowledge/platform/session", {
  data: { username: cred.username, password: cred.password },
});
console.log("login", res.status());
const page = await ctx.newPage();
for (const p of pages) {
  await page.goto("http://127.0.0.1:8015" + p, { waitUntil: "networkidle" }).catch(() => {});
  await page.waitForTimeout(800);
  const name = p.replace(/\//g, "_") || "_home";
  await page.screenshot({ path: `${out}/${role}${name}.png` });
}
await browser.close();
