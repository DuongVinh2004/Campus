// UI audit of the running app (default http://127.0.0.1:8015): every page of every role at desktop and phone size.
//
//   node scripts/qa/ui_audit.mjs [--base http://127.0.0.1:8015] [--out infra/local/qa-acceptance/ui-audit]
//
// For each page and viewport it records, and the report lists: a page-level horizontal scroll (layout wider than the screen),
// no <h1> or more than one, buttons/links without an accessible name, form fields without a label, images without alt,
// text smaller than 12 px that people must read, tap targets smaller than 24x24 px on the phone, console errors and failed
// requests (HTTP >= 500, or 4xx other than flagged-off features), plus a full-page screenshot. It changes nothing.
// Credentials are read from the credential files next to the runtime state and never printed.
import { chromium } from "../../apps/web/node_modules/@playwright/test/index.mjs";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const arg = (name, fallback) => { const i = process.argv.indexOf(name); return i > 0 ? process.argv[i + 1] : fallback; };
const BASE = arg("--base", "http://127.0.0.1:8015");
const OUT = path.resolve(root, arg("--out", "infra/local/qa-acceptance/ui-audit"));
const CREDS = path.join(root, "infra/local/knowledge-platform-20261023");
const PAGES = {
  student: ["/", "/chat", "/services", "/tickets", "/schedule", "/rooms", "/notifications", "/learning", "/privacy", "/memory", "/announcements"],
  staff: ["/staff", "/tickets", "/chat", "/rooms", "/notifications"],
  owner: ["/admin", "/knowledge", "/knowledge/sources", "/knowledge/documents", "/knowledge/freshness", "/knowledge/quality", "/knowledge/crawl", "/announcements/manage"],
  public: ["/login", "/offline"],
};
const VIEWPORTS = { desktop: { width: 1360, height: 860 }, phone: { width: 390, height: 844 } };
fs.mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch();
const findings = [];

async function context(role, viewport) {
  const ctx = await browser.newContext({ viewport, deviceScaleFactor: 1, isMobile: viewport.width < 600, hasTouch: viewport.width < 600 });
  if (role === "public") return ctx;
  const c = JSON.parse(fs.readFileSync(path.join(CREDS, role + "-credentials.json"), "utf8"));
  const page = await ctx.newPage();
  await page.goto(BASE + "/login", { waitUntil: "domcontentloaded" });
  await page.locator("input[name=username]").fill(c.username);
  await page.locator("input[name=password]").fill(c.password);
  await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
  await page.waitForURL((url) => !url.pathname.startsWith("/login"), { timeout: 20000 });
  await page.close();
  return ctx;
}

const CHECK = () => {
  const visible = (el) => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el); return r.width > 0 && r.height > 0 && s.visibility !== "hidden" && s.display !== "none"; };
  const name = (el) => (el.getAttribute("aria-label") || el.getAttribute("aria-labelledby") && document.getElementById(el.getAttribute("aria-labelledby"))?.textContent || el.textContent || el.getAttribute("title") || el.querySelector("img[alt]")?.getAttribute("alt") || "").trim();
  const describe = (el) => (el.tagName.toLowerCase() + (el.id ? "#" + el.id : "") + (el.className && typeof el.className === "string" ? "." + el.className.trim().split(/\s+/).slice(0, 2).join(".") : "")).slice(0, 80);
  const out = { overflow: document.documentElement.scrollWidth - window.innerWidth, h1: document.querySelectorAll("h1").length, unnamed: [], unlabelled: [], noAlt: [], tiny: [], smallTargets: [] };
  for (const el of document.querySelectorAll("button, a[href], [role=button]")) if (visible(el) && !name(el)) out.unnamed.push(describe(el));
  for (const el of document.querySelectorAll("input:not([type=hidden]), select, textarea")) {
    if (!visible(el)) continue;
    const labelled = el.labels?.length || el.getAttribute("aria-label") || el.getAttribute("aria-labelledby") || el.getAttribute("title") || el.closest("label");
    if (!labelled) out.unlabelled.push(describe(el) + (el.getAttribute("placeholder") ? ` [placeholder="${el.getAttribute("placeholder").slice(0, 30)}"]` : ""));
  }
  for (const el of document.querySelectorAll("img")) if (visible(el) && !el.hasAttribute("alt")) out.noAlt.push(describe(el));
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  const seen = new Set();
  while (walker.nextNode()) {
    const text = walker.currentNode.textContent.trim();
    const el = walker.currentNode.parentElement;
    if (!text || text.length < 3 || !el || seen.has(el) || !visible(el)) continue;
    seen.add(el);
    if (parseFloat(getComputedStyle(el).fontSize) < 12) out.tiny.push(`${describe(el)} "${text.slice(0, 30)}" ${getComputedStyle(el).fontSize}`);
  }
  if (window.innerWidth < 600) for (const el of document.querySelectorAll("button, a[href], input[type=checkbox], input[type=radio], [role=button]")) {
    if (!visible(el)) continue;
    // A checkbox or radio inside its <label> is toggled by the whole label, so the label is the tap target.
    const holder = el.matches("input[type=checkbox], input[type=radio]") ? el.closest("label") : null;
    const r = (holder || el).getBoundingClientRect();
    if ((r.width < 24 || r.height < 24) && !el.closest("p, li")) out.smallTargets.push(`${describe(el)} ${Math.round(r.width)}x${Math.round(r.height)} "${name(el).slice(0, 20)}"`);
  }
  for (const key of ["unnamed", "unlabelled", "noAlt", "tiny", "smallTargets"]) out[key] = [...new Set(out[key])].slice(0, 12);
  return out;
};

for (const [vpName, viewport] of Object.entries(VIEWPORTS)) {
  for (const [role, pages] of Object.entries(PAGES)) {
    const ctx = await context(role, viewport);
    for (const route of pages) {
      const page = await ctx.newPage();
      const errors = [], failed = [];
      page.on("console", (m) => { if (m.type() === "error") errors.push(m.text().slice(0, 160)); });
      page.on("response", (r) => {
        const s = r.status();
        if (s >= 500 || (s >= 400 && s !== 401 && !/FEATURE_DISABLED/.test(r.headers()["x-feature"] ?? "") && !/\/v1\/(features|policy|procedures|answer-receipts|nudges|learning\/(mastery|tutor))/.test(r.url()))) failed.push(`${s} ${r.url().replace(BASE, "").slice(0, 90)}`);
      });
      await page.goto(BASE + route, { waitUntil: "domcontentloaded" });
      await page.waitForLoadState("networkidle", { timeout: 12000 }).catch(() => undefined);
      await page.waitForTimeout(800);
      const result = await page.evaluate(CHECK);
      const file = `${vpName}-${role}${route.replace(/\//g, "_") || "_home"}.png`;
      await page.screenshot({ path: path.join(OUT, file), fullPage: true });
      findings.push({ viewport: vpName, role, route, ...result, console_errors: [...new Set(errors)].slice(0, 6), failed_requests: [...new Set(failed)].slice(0, 6), screenshot: file });
      await page.close();
    }
    await ctx.close();
  }
}
await browser.close();
fs.writeFileSync(path.join(OUT, "report.json"), JSON.stringify(findings, null, 1));
let issues = 0;
for (const f of findings) {
  const problems = [];
  if (f.overflow > 1) problems.push(`horizontal scroll ${f.overflow}px`);
  if (f.h1 !== 1) problems.push(`${f.h1} h1`);
  for (const [key, label] of [["unnamed", "no accessible name"], ["unlabelled", "field without label"], ["noAlt", "img without alt"], ["tiny", "text < 12px"], ["smallTargets", "tap target < 24px"], ["console_errors", "console error"], ["failed_requests", "failed request"]])
    if (f[key].length) problems.push(`${label}: ${f[key].join(" | ")}`);
  if (problems.length) { issues += 1; console.log(`[${f.viewport}] ${f.role} ${f.route}\n  - ${problems.join("\n  - ")}`); }
}
console.log(`\n${findings.length} page views, ${issues} with findings; report and screenshots in ${path.relative(root, OUT)}`);
