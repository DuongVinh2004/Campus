// Automated acceptance check for one static front-end variant. Prints one JSON object {ok, problems:[...]} to stdout.
//   node scripts/fe_variant_check.mjs <name> <port>
// The variant server must already be running. Problems are plain Vietnamese/English sentences meant to be pasted
// back to the worker that wrote the variant, so each says what is wrong and where.
import { chromium } from "../apps/web/node_modules/@playwright/test/index.mjs";
import fs from "node:fs";

const [name, port] = process.argv.slice(2);
const base = `http://127.0.0.1:${port}`;
const problems = [];
const cred = JSON.parse(fs.readFileSync("infra/local/knowledge-platform-20261023/student-credentials.json", "utf8"));
const NAV = ["home", "chat", "schedule", "rooms", "notifications", "tickets"];

function note(msg) { if (!problems.includes(msg) && problems.length < 25) problems.push(msg); }

const browser = await chromium.launch();
try {
  for (const [label, viewport] of [["desktop 1360px", { width: 1360, height: 860 }], ["mobile 390px", { width: 390, height: 844 }]]) {
    const ctxAnon = await browser.newContext({ viewport });
    const ap = await ctxAnon.newPage();
    ap.on("pageerror", (e) => note(`[${label}] JS error on the login screen: ${e.message}`));
    await ap.goto(`${base}/#/home`, { waitUntil: "networkidle" }).catch(() => {});
    await ap.waitForTimeout(500);
    for (const id of ["login-username", "login-password", "login-submit"]) {
      if (!(await ap.locator(`[data-testid="${id}"]`).count())) note(`[${label}] signed-out page has no element [data-testid="${id}"] (the login screen must show when CampusAPI.session.isSignedIn() is false)`);
    }
    // Real login through the form.
    if (await ap.locator('[data-testid="login-username"]').count()) {
      await ap.fill('[data-testid="login-username"]', cred.username);
      await ap.fill('[data-testid="login-password"]', cred.password);
      await ap.click('[data-testid="login-submit"]');
      await ap.waitForTimeout(2500);
      if (await ap.locator('[data-testid="login-submit"]').isVisible().catch(() => false)) note(`[${label}] after a correct login the login screen is still visible (should go to #/home)`);
    }
    await ctxAnon.close();

    const ctx = await browser.newContext({ viewport });
    const res = await ctx.request.post(`${base}/v1/knowledge/platform/session`, { data: { username: cred.username, password: cred.password } });
    if (res.status() !== 200) note(`[${label}] API login via proxy returned ${res.status()}`);
    const page = await ctx.newPage();
    const external = new Set();
    page.on("pageerror", (e) => note(`[${label}] uncaught JS error: ${e.message}`));
    page.on("console", (m) => { if (m.type() === "error" && !/429/.test(m.text())) note(`[${label}] console.error: ${m.text().slice(0, 220)}`); });
    page.on("requestfailed", (r) => { if (r.url().startsWith(base) && !/ERR_ABORTED/.test(r.failure()?.errorText || "")) note(`[${label}] request failed: ${r.url().replace(base, "")}`); });
    page.on("response", (r) => { if (r.url().startsWith(base) && r.status() >= 500) note(`[${label}] HTTP ${r.status()} from ${r.url().replace(base, "")}`); });
    page.on("request", (r) => { const u = r.url(); if (!u.startsWith(base) && !u.startsWith("data:") && !u.startsWith("blob:")) external.add(u.slice(0, 80)); });

    for (const route of NAV) {
      await page.goto(`${base}/#/${route}`, { waitUntil: "networkidle" }).catch(() => {});
      await page.waitForTimeout(900);
      const text = (await page.evaluate(() => document.body.innerText)).trim();
      if (text.length < 120) note(`[${label}] #/${route} renders almost nothing (${text.length} characters of visible text)`);
      if (/undefined|NaN|\[object Object\]/.test(text)) note(`[${label}] #/${route} shows a raw "undefined"/"NaN"/"[object Object]" in the visible text`);
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
      if (overflow > 2) note(`[${label}] #/${route} scrolls horizontally by ${overflow}px (layout wider than the viewport)`);
      if (!(await page.locator(`[data-testid="nav-${route}"]`).count())) note(`[${label}] navigation is missing [data-testid="nav-${route}"]`);
    }

    // Chat: a real question must stream an answer with text.
    await page.goto(`${base}/#/chat`, { waitUntil: "networkidle" }).catch(() => {});
    const input = page.locator('[data-testid="chat-input"]').first();
    if (!(await input.count())) note(`[${label}] #/chat has no [data-testid="chat-input"]`);
    else {
      await input.fill("Học phí một tín chỉ của K69 đại trà là bao nhiêu?");
      await input.press("Enter");
      let shown = false;
      for (let i = 0; i < 24 && !shown; i++) {  // poll up to ~48 s for the streamed answer
        await page.waitForTimeout(2000);
        shown = (await page.evaluate(() => document.body.innerText)).includes("592.500");
      }
      if (!shown) {  // the API rate-limits a student that just ran many requests: wait out the window and ask once more
        await page.waitForTimeout(30000);
        await input.fill("Học phí một tín chỉ của K69 đại trà là bao nhiêu?");
        await input.press("Enter");
        for (let i = 0; i < 24 && !shown; i++) {
          await page.waitForTimeout(2000);
          shown = (await page.evaluate(() => document.body.innerText)).includes("592.500");
        }
      }
      if (!shown) note(`[${label}] after asking the K69 tuition question the page never shows the answer text (expected "592.500" from the API reply within 48 s)`);
    }

    // Rooms: cards, then the two-step booking controls.
    await page.goto(`${base}/#/rooms`, { waitUntil: "networkidle" }).catch(() => {});
    await page.waitForTimeout(1200);
    if (!(await page.locator('[data-testid^="room-card-"]').count())) note(`[${label}] #/rooms shows no [data-testid^="room-card-"] elements (rooms.list returns 30+ rooms)`);
    if (!(await page.locator('[data-testid="rooms-search"]').count())) note(`[${label}] #/rooms has no [data-testid="rooms-search"]`);
    await page.goto(`${base}/#/tickets`, { waitUntil: "networkidle" }).catch(() => {});
    await page.waitForTimeout(800);
    if (!(await page.locator('[data-testid="tickets-new"]').count())) note(`[${label}] #/tickets has no [data-testid="tickets-new"]`);
    await page.goto(`${base}/#/schedule`, { waitUntil: "networkidle" }).catch(() => {});
    await page.waitForTimeout(800);
    if (!(await page.locator('[data-testid="schedule-add"]').count())) note(`[${label}] #/schedule has no [data-testid="schedule-add"]`);
    if (external.size) note(`[${label}] requests to outside origins are not allowed: ${[...external].slice(0, 3).join(", ")}`);
    await ctx.close();
  }
} catch (e) {
  note(`check crashed: ${String(e).slice(0, 200)}`);
}
await browser.close();
console.log(JSON.stringify({ ok: problems.length === 0, problems }));
