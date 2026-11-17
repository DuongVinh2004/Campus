// Screenshots one static front-end variant (fe-variants/<name>, served by scripts/fe_variant_server.mjs).
//   node scripts/fe_variant_shots.mjs <name> <port> [outRoot]
// Saves PNGs to <outRoot>/<name>/ (default infra/local/ui-shots/variants), desktop 1360x860 and mobile 390x844:
//   login, home, chat-empty, chat-answer, schedule, rooms, notifications, tickets  (+ page errors in errors.txt)
import { chromium } from "../apps/web/node_modules/@playwright/test/index.mjs";
import fs from "node:fs";

const [name, port, outRoot = "infra/local/ui-shots/variants"] = process.argv.slice(2);
if (!name || !port) { console.error("usage: fe_variant_shots.mjs <name> <port> [outRoot]"); process.exit(2); }
const base = `http://127.0.0.1:${port}`;
const out = `${outRoot}/${name}`;
fs.mkdirSync(out, { recursive: true });
const cred = JSON.parse(fs.readFileSync("infra/local/knowledge-platform-20261023/student-credentials.json", "utf8"));
const errors = [];

const browser = await chromium.launch();
for (const [label, viewport] of [["desktop", { width: 1360, height: 860 }], ["mobile", { width: 390, height: 844 }]]) {
  const shot = async (page, file, full = false) => {
    await page.waitForTimeout(900);
    await page.screenshot({ path: `${out}/${label}-${file}.png`, fullPage: full });
  };
  // Signed-out login screen.
  const anon = await browser.newContext({ viewport });
  const ap = await anon.newPage();
  ap.on("pageerror", (e) => errors.push(`${label} login pageerror: ${e.message}`));
  await ap.goto(`${base}/#/home`, { waitUntil: "networkidle" }).catch(() => {});
  await shot(ap, "login");
  await anon.close();
  // Signed in.
  const ctx = await browser.newContext({ viewport });
  const res = await ctx.request.post(`${base}/v1/knowledge/platform/session`, { data: { username: cred.username, password: cred.password } });
  if (res.status() !== 200) errors.push(`${label} login status ${res.status()}`);
  const page = await ctx.newPage();
  page.on("pageerror", (e) => errors.push(`${label} pageerror: ${e.message}`));
  page.on("console", (m) => { if (m.type() === "error") errors.push(`${label} console: ${m.text().slice(0, 200)}`); });
  for (const route of ["home", "chat", "schedule", "rooms", "notifications", "tickets"]) {
    await page.goto(`${base}/#/${route}`, { waitUntil: "networkidle" }).catch(() => {});
    await shot(page, route === "chat" ? "chat-empty" : route);
  }
  // One real question through the chat.
  await page.goto(`${base}/#/chat`, { waitUntil: "networkidle" }).catch(() => {});
  const input = page.locator('[data-testid="chat-input"]').first();
  if (await input.count()) {
    await input.fill("Học phí một tín chỉ của K69 đại trà là bao nhiêu?");
    await input.press("Enter");
    await page.waitForTimeout(16000);
    await shot(page, "chat-answer", true);
  } else errors.push(`${label}: no [data-testid=chat-input]`);
  await ctx.close();
}
await browser.close();
fs.writeFileSync(`${out}/errors.txt`, errors.join("\n") || "none");
console.log(name, "done;", errors.length, "problems");
