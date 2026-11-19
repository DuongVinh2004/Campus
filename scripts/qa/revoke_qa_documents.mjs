// Revokes the synthetic QA documents (owner_unit "QA", title starting "QA-") that a release trial may have left published.
//   node scripts/qa/revoke_qa_documents.mjs [--base URL] [--apply]   (without --apply it only lists them)
import { chromium } from "../../apps/web/node_modules/@playwright/test/index.mjs";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const arg = (name, fallback) => { const i = process.argv.indexOf(name); return i > 0 ? process.argv[i + 1] : fallback; };
const BASE = arg("--base", "http://127.0.0.1:8015");
const apply = process.argv.includes("--apply");
const creds = JSON.parse(fs.readFileSync(path.join(root, "infra/local/knowledge-platform-20261023/owner-credentials.json"), "utf8"));
const browser = await chromium.launch();
const context = await browser.newContext();
const page = await context.newPage();
await page.goto(BASE + "/login", { waitUntil: "domcontentloaded" });
await page.locator("input[name=username]").fill(creds.username);
await page.locator("input[name=password]").fill(creds.password);
await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
await page.waitForURL((url) => !url.pathname.startsWith("/login"), { timeout: 20000 });
const rows = ((await (await context.request.get(BASE + "/v1/knowledge/platform/documents")).json()).items || []).filter((r) => /^QA-/.test(r.title));
for (const row of rows) {
  console.log(JSON.stringify({ version_id: row.version_id, title: row.title, state: row.state, can_revoke: row.can_revoke }));
  if (apply && row.can_revoke) {
    const done = await context.request.post(`${BASE}/v1/knowledge/platform/documents/${row.version_id}/revoke`, { data: { note: "QA release trial finished" } });
    console.log("  revoke ->", done.status());
  }
}
await browser.close();
