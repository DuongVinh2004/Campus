// One-time release trial on the running runtime: publish a synthetic document, see the chatbot cite it, revoke it, and check the
// index is back to where it started.   node scripts/qa/release_trial.mjs [--base URL]
// Needs the ingest worker running (start the runtime without --defer-worker) and about 2 GB of free RAM while it works.
// Signs in as the owner (credentials read from the runtime folder, never printed). The document is marked QA, carries a made-up fact
// that exists nowhere else, and is revoked at the end, also when a step failed. Exit code 1 when a check fails.
import { chromium } from "../../apps/web/node_modules/@playwright/test/index.mjs";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import crypto from "node:crypto";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const arg = (name, fallback) => { const i = process.argv.indexOf(name); return i > 0 ? process.argv[i + 1] : fallback; };
const BASE = arg("--base", "http://127.0.0.1:8015");
const creds = JSON.parse(fs.readFileSync(path.join(root, "infra/local/knowledge-platform-20261023/owner-credentials.json"), "utf8"));
const STAMP = new Date().toISOString().slice(0, 10);
const FACT = "Phòng Thí nghiệm Hư Cấu QA mở cửa lúc 06:45 và đóng cửa lúc 19:15 các ngày làm việc";
const QUESTION = "Phòng Thí nghiệm Hư Cấu QA mở cửa lúc mấy giờ?";
const TEXT = `QA-${STAMP} Thông báo giờ làm việc của Phòng Thí nghiệm Hư Cấu (tài liệu tổng hợp để kiểm thử, không phải văn bản chính thức)\n\n1. Giờ làm việc\n${FACT}.\n\n2. Liên hệ\nPhòng Thí nghiệm Hư Cấu QA, điện thoại nội bộ 0987 654 321.\n`;
const results = [];
const check = (ok, message) => { console.log(ok ? "ok  " : "FAIL", message); results.push([ok, message]); };

const browser = await chromium.launch();
const context = await browser.newContext();
const page = await context.newPage();
await page.goto(BASE + "/login", { waitUntil: "domcontentloaded" });
await page.locator("input[name=username]").fill(creds.username);
await page.locator("input[name=password]").fill(creds.password);
await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
await page.waitForURL((url) => !url.pathname.startsWith("/login"), { timeout: 20000 });
const api = context.request;
const snapshot = async () => (await (await api.get(BASE + "/health/ready")).json()).rag_v2;
const listing = async () => (await (await api.get(BASE + "/v1/knowledge/platform/documents")).json());

const before = await snapshot();
console.log("before:", JSON.stringify({ units: before.unit_count, release: before.release_id, generation: before.generation }));
const uri = `https://qa.huce.edu.vn/release-trial-${STAMP}-${crypto.randomBytes(4).toString("hex")}`;
let versionId = null;
try {
  const metadata = { title: `QA-${STAMP} Giờ làm việc Phòng Thí nghiệm Hư Cấu`, owner_unit: "QA", canonical_uri: uri, programs: ["PUBLIC"],
    audiences: ["STUDENT", "KNOWLEDGE_ADMIN", "SYSTEM_ADMIN"], effective_from: null, publish_directly: true, attested: true };
  const sent = await api.post(BASE + "/v1/knowledge/platform/documents", {
    headers: { "Idempotency-Key": crypto.randomUUID() },
    multipart: { metadata: JSON.stringify(metadata), file: { name: "qa-release-trial.txt", mimeType: "text/plain", buffer: Buffer.from(TEXT, "utf8") } } });
  check(sent.status() === 202, `the document is accepted (HTTP ${sent.status()})`);
  versionId = (await sent.json()).version_id ?? null;
  const started = Date.now();
  let item = null, last = "";
  while (Date.now() - started < 15 * 60 * 1000) {
    const rows = (await listing()).items || [];
    item = rows.find((r) => r.canonical_uri === uri) || null;
    versionId = item?.version_id ?? versionId;
    if (item && item.state !== last) { last = item.state; console.log(`  state ${item.state} after ${Math.round((Date.now() - started) / 1000)} s`); }
    if (item && ["ACTIVE", "NEEDS_ATTENTION"].includes(item.state)) break;
    await new Promise((r) => setTimeout(r, 5000));
  }
  check(item?.state === "ACTIVE", `the document becomes usable (state ${item?.state}; ${Math.round((Date.now() - started) / 1000)} s)`);
  if (item?.state === "ACTIVE") {
    const during = await snapshot();
    console.log("during:", JSON.stringify({ units: during.unit_count, release: during.release_id, generation: during.generation }));
    check(during.unit_count > before.unit_count, `the index grew (${before.unit_count} to ${during.unit_count} units)`);
    await page.goto(BASE + "/chat", { waitUntil: "domcontentloaded" });
    const box = page.getByPlaceholder(/Hỏi Campus/i);
    await box.fill(QUESTION);
    await box.press("Enter");
    await page.waitForTimeout(3000);
    for (let i = 0; i < 40; i++) { if (!(await page.getByRole("button", { name: /dừng|stop/i }).count())) break; await page.waitForTimeout(1500); }
    const text = (await page.locator("main").innerText()).replace(/\s+/g, " ");
    const answer = text.slice(text.lastIndexOf("Trợ lý AI"));
    check(/06:45|6:45|6h45|6 giờ 45/.test(answer), `the chatbot answers from the new document: "${answer.slice(0, 160)}"`);
    check(/QA/.test(answer) || /Nguồn|\[1\]/.test(answer), "the answer carries a citation to it");
  }
} finally {
  if (versionId) {
    const revoked = await api.post(`${BASE}/v1/knowledge/platform/documents/${versionId}/revoke`, { data: { note: "QA release trial finished" } });
    check(revoked.status() === 200, `the document is revoked (HTTP ${revoked.status()})`);
    const started = Date.now();
    let after = await snapshot();
    while (Date.now() - started < 10 * 60 * 1000 && (after.unit_count !== before.unit_count || after.stale)) {
      await new Promise((r) => setTimeout(r, 5000));
      after = await snapshot();
    }
    console.log("after:", JSON.stringify({ units: after.unit_count, release: after.release_id, generation: after.generation }));
    check(after.unit_count === before.unit_count, `the index is back to ${before.unit_count} units (now ${after.unit_count})`);
    const asked = (await (async () => {
      await page.goto(BASE + "/chat", { waitUntil: "domcontentloaded" });
      const box = page.getByPlaceholder(/Hỏi Campus/i);
      await box.fill(QUESTION);
      await box.press("Enter");
      await page.waitForTimeout(3000);
      for (let i = 0; i < 40; i++) { if (!(await page.getByRole("button", { name: /dừng|stop/i }).count())) break; await page.waitForTimeout(1500); }
      const t = (await page.locator("main").innerText()).replace(/\s+/g, " ");
      return t.slice(t.lastIndexOf("Trợ lý AI"));
    })());
    check(!/06:45|6:45/.test(asked), "after the revocation the chatbot no longer knows the made-up fact");
  }
  await browser.close();
}
const failed = results.filter(([ok]) => !ok);
console.log(`${results.length - failed.length} checks passed, ${failed.length} failed`);
process.exit(failed.length ? 1 : 0);
