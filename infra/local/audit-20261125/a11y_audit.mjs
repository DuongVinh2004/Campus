// Lightweight in-page accessibility + UI audit (no axe-core in the repo). Read-only: it only visits pages.
//   node infra/local/audit-20261125/a11y_audit.mjs
// Per page: unnamed buttons/links/inputs, images without alt, missing lang, duplicate ids, text contrast < 4.5:1 (normal) / 3:1 (large),
// targets < 44 px (WCAG 2.5.5 AAA, reported) and < 24 px (2.5.8 AA), raw i18n keys, aria-live regions, keyboard focus visibility,
// dialogs closing on Escape. Viewports: 1360, 768, 375. Passwords are read from the credential files and never printed.
import { chromium } from "../../../apps/web/node_modules/@playwright/test/index.mjs";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, "../../..");
const BASE = "http://127.0.0.1:8015";
const OUT = path.join(here, "a11y");
fs.mkdirSync(OUT, { recursive: true });
const KP = path.join(root, "infra/local/knowledge-platform-20261023");
const read = (p) => JSON.parse(fs.readFileSync(p, "utf8"));
const learning = read(path.join(root, "infra/local/learning-materials-20261104-01/credentials.json")).accounts;
const directory = read(path.join(KP, "campus-directory-credentials.json")).accounts;
const ROLES = {
  student: { account: directory.find((a) => a.username === "sv.demo03"), pages: ["/chat", "/services", "/tickets", "/schedule", "/rooms", "/notifications", "/learning", "/privacy", "/memory"] },
  officer: { account: directory.find((a) => a.username === "nv.demo02"), pages: ["/staff", "/tickets", "/rooms", "/notifications"] },
  lecturer: { account: learning.find((a) => a.username === "gv.demo02"), pages: ["/learning"] },
  owner: { account: read(path.join(KP, "owner-credentials.json")), pages: ["/admin", "/knowledge/sources", "/knowledge/documents", "/knowledge/freshness", "/knowledge/quality", "/knowledge/crawl"] },
};
const VIEWPORTS = { desktop: { width: 1360, height: 860 }, tablet: { width: 768, height: 1024 }, phone: { width: 375, height: 812 } };

const browser = await chromium.launch({ executablePath: "C:/Program Files/Google/Chrome/Application/chrome.exe" });
const results = [];

async function signIn(context, account) {
  const page = await context.newPage();
  await page.goto(BASE + "/login", { waitUntil: "domcontentloaded" });
  await page.locator("input[name=username]").fill(account.username);
  await page.locator("input[name=password]").fill(account.password);
  await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
  await page.waitForURL((url) => !url.pathname.startsWith("/login"), { timeout: 20000 });
  return page;
}

function inPageAudit() {
  const visible = (e) => { const b = e.getBoundingClientRect(); const s = getComputedStyle(e); return b.width > 1 && b.height > 1 && s.visibility !== "hidden" && s.display !== "none"; };
  const name = (e) => {
    const by = e.getAttribute("aria-labelledby");
    const labelled = by ? by.split(/\s+/).map((id) => document.getElementById(id)?.textContent || "").join(" ") : "";
    const label = e.id ? [...document.querySelectorAll(`label[for="${CSS.escape(e.id)}"]`)].map((l) => l.textContent).join(" ") : "";
    const wrap = e.closest("label")?.textContent || "";
    const img = [...e.querySelectorAll("img[alt],svg[aria-label]")].map((i) => i.getAttribute("alt") || i.getAttribute("aria-label")).join(" ");
    return (e.getAttribute("aria-label") || labelled || label || wrap || e.getAttribute("title") || e.innerText || e.value || img || e.getAttribute("placeholder") || "").trim();
  };
  const describe = (e) => `${e.tagName.toLowerCase()}${e.id ? "#" + e.id : ""}${e.className && typeof e.className === "string" ? "." + e.className.split(/\s+/).slice(0, 2).join(".") : ""}`.slice(0, 70);
  const unnamed = [...document.querySelectorAll("button,[role=button],a[href],input:not([type=hidden]),select,textarea,[role=tab],[role=switch],[role=checkbox]")]
    .filter(visible).filter((e) => !name(e)).map(describe);
  const imgNoAlt = [...document.querySelectorAll("img")].filter((i) => !i.hasAttribute("alt")).map(describe);
  const ids = {}; for (const e of document.querySelectorAll("[id]")) ids[e.id] = (ids[e.id] || 0) + 1;
  const dupIds = Object.entries(ids).filter(([, n]) => n > 1).map(([id]) => id);
  const parse = (c) => { const m = c.match(/rgba?\(([^)]+)\)/); if (!m) return null; const p = m[1].split(/[ ,/]+/).filter(Boolean).map(Number); return { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 }; };
  const lum = ({ r, g, b }) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
  const bgOf = (e) => { for (let n = e; n; n = n.parentElement) { const s = getComputedStyle(n); if (s.backgroundImage && s.backgroundImage !== "none") return null; const c = parse(s.backgroundColor); if (c && c.a > 0.95) return c; } return { r: 255, g: 255, b: 255, a: 1 }; };
  const lowContrast = [];
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  const seen = new Set();
  while (walker.nextNode()) {
    const t = walker.currentNode; const e = t.parentElement;
    if (!e || seen.has(e) || !t.textContent.trim() || !visible(e)) continue;
    seen.add(e);
    const s = getComputedStyle(e); const fg = parse(s.color); const bg = bgOf(e);
    if (!fg || !bg || fg.a < 0.95 || Number(s.opacity) < 0.95 || e.closest("[disabled],[aria-disabled=true]")) continue;
    const [l1, l2] = [lum(fg), lum(bg)].sort((a, b) => b - a); const ratio = (l1 + 0.05) / (l2 + 0.05);
    const size = parseFloat(s.fontSize); const bold = Number(s.fontWeight) >= 700;
    const need = size >= 24 || (bold && size >= 18.66) ? 3 : 4.5;
    if (ratio < need) lowContrast.push(`${ratio.toFixed(2)}<${need} "${t.textContent.trim().slice(0, 28)}" ${describe(e)}`);
  }
  const targets = [...document.querySelectorAll("button,[role=button],a[href],input[type=checkbox],input[type=radio],select")].filter(visible)
    .filter((e) => !(e.tagName === "A" && getComputedStyle(e).display === "inline"));
  const under44 = targets.filter((e) => { const b = e.getBoundingClientRect(); return b.width < 44 || b.height < 44; });
  const under24 = targets.filter((e) => { const b = e.getBoundingClientRect(); return b.width < 24 || b.height < 24; }).map((e) => `${name(e).slice(0, 24) || describe(e)}`);
  const text = document.body.innerText;
  const rawKeys = [...new Set(text.match(/\b[a-z][a-zA-Z]+(?:\.[a-z][a-zA-Z0-9]+){2,}\b/g) || [])].filter((k) => !/\.(vn|com|edu|pdf|docx?|json|png|jpg)$/i.test(k) && !/^\d/.test(k)).slice(0, 8);
  const english = [...new Set(text.match(/\b(Loading|Error|Submit|Cancel|Save|Delete|Undefined|null|NaN|undefined)\b/g) || [])];
  const overflow = document.documentElement.scrollWidth - window.innerWidth;
  const clipped = [...document.querySelectorAll("h1,h2,h3,button,a,label,th,td,p,span")].filter(visible).filter((e) => {
    const s = getComputedStyle(e); return (s.overflow === "hidden" || s.textOverflow === "ellipsis") && e.scrollWidth > e.clientWidth + 2 && s.whiteSpace === "nowrap" && !e.title && !e.getAttribute("aria-label");
  }).map((e) => `"${e.innerText.trim().slice(0, 30)}"`).slice(0, 6);
  return {
    lang: document.documentElement.lang, title: document.title, h1: document.querySelectorAll("h1").length,
    unnamed, imgNoAlt, dupIds, lowContrast: lowContrast.slice(0, 12), lowContrastCount: lowContrast.length,
    targets: targets.length, under44: under44.length, under24, live: document.querySelectorAll("[aria-live],[role=status],[role=alert]").length,
    rawKeys, english, overflow, clipped,
  };
}

async function keyboard(page) {
  // Tab through the first 12 stops: each focused element must show a visible focus indicator (outline or box-shadow change).
  await page.locator("body").click({ position: { x: 2, y: 2 } }).catch(() => undefined);
  const misses = [];
  for (let i = 0; i < 12; i++) {
    await page.keyboard.press("Tab");
    const r = await page.evaluate(() => {
      const e = document.activeElement; if (!e || e === document.body) return null;
      const s = getComputedStyle(e);
      const shown = (s.outlineStyle !== "none" && parseFloat(s.outlineWidth) > 0) || (s.boxShadow && s.boxShadow !== "none");
      return { shown, what: (e.getAttribute("aria-label") || e.innerText || e.tagName).trim().slice(0, 24) };
    });
    if (r && !r.shown) misses.push(r.what);
  }
  return [...new Set(misses)];
}

for (const [role, { account, pages }] of Object.entries(ROLES)) {
  for (const [vp, viewport] of Object.entries(VIEWPORTS)) {
    const context = await browser.newContext({ viewport, locale: "vi-VN" });
    let page;
    try { page = await signIn(context, account); } catch (e) { results.push({ role, vp, error: "sign-in " + String(e.message).slice(0, 80) }); await context.close(); continue; }
    for (const route of pages) {
      try {
        const res = await page.goto(BASE + route, { waitUntil: "domcontentloaded", timeout: 30000 });
        await page.waitForLoadState("networkidle", { timeout: 10000 }).catch(() => undefined);
        await page.waitForTimeout(500);
        const audit = await page.evaluate(inPageAudit);
        const focusMisses = vp === "desktop" ? await keyboard(page) : [];
        let dark = null;
        if (vp === "desktop") {
          await page.evaluate(() => document.documentElement.classList.add("dark"));
          await page.waitForTimeout(250);
          const d = await page.evaluate(inPageAudit);
          dark = { lowContrastCount: d.lowContrastCount, lowContrast: d.lowContrast.slice(0, 6) };
          await page.screenshot({ path: path.join(OUT, `${role}${route.replace(/\//g, "_")}_dark.png`) }).catch(() => undefined);
          await page.evaluate(() => document.documentElement.classList.remove("dark"));
        }
        await page.screenshot({ path: path.join(OUT, `${role}${route.replace(/\//g, "_")}_${vp}.png`) }).catch(() => undefined);
        results.push({ role, vp, route, status: res && res.status(), ...audit, focusMisses, dark });
      } catch (e) { results.push({ role, vp, route, error: String(e.message).slice(0, 120) }); }
    }
    await context.close();
  }
}

// Dialog check on the student's ticket page: open the first dialog-opening control and press Escape.
{
  const context = await browser.newContext({ viewport: VIEWPORTS.desktop });
  const page = await signIn(context, ROLES.student.account);
  const out = { checked: [] };
  for (const route of ["/tickets", "/schedule", "/rooms"]) {
    await page.goto(BASE + route, { waitUntil: "domcontentloaded" });
    await page.waitForLoadState("networkidle", { timeout: 10000 }).catch(() => undefined);
    const opener = page.locator("button[aria-haspopup=dialog], button:has-text('Thêm'), button:has-text('Tạo')").first();
    if (!(await opener.count())) { out.checked.push({ route, opener: false }); continue; }
    await opener.click().catch(() => undefined);
    await page.waitForTimeout(400);
    const dialog = page.locator("[role=dialog],dialog[open]").first();
    const opened = (await dialog.count()) > 0 && (await dialog.isVisible().catch(() => false));
    let focusInside = null, closedOnEsc = null, trapped = null;
    if (opened) {
      focusInside = await page.evaluate(() => !!document.activeElement?.closest("[role=dialog],dialog"));
      for (let i = 0; i < 15; i++) await page.keyboard.press("Tab");
      trapped = await page.evaluate(() => !!document.activeElement?.closest("[role=dialog],dialog"));
      await page.keyboard.press("Escape");
      await page.waitForTimeout(300);
      closedOnEsc = !(await dialog.isVisible().catch(() => false));
    }
    out.checked.push({ route, opener: true, opened, focusInside, trapped, closedOnEsc });
  }
  results.push({ role: "student", dialogs: out.checked });
  await context.close();
}

await browser.close();
fs.writeFileSync(path.join(OUT, "result.json"), JSON.stringify(results, null, 1));
const agg = { pages: 0, unnamed: 0, imgNoAlt: 0, dupIds: 0, lowContrast: 0, darkLowContrast: 0, under24: 0, under44: 0, targets: 0, rawKeys: 0, overflow: 0, errors: 0 };
for (const r of results) {
  if (r.error) { agg.errors++; continue; }
  if (!r.route) continue;
  agg.pages++; agg.unnamed += r.unnamed.length; agg.imgNoAlt += r.imgNoAlt.length; agg.dupIds += r.dupIds.length; agg.lowContrast += r.lowContrastCount;
  agg.darkLowContrast += r.dark ? r.dark.lowContrastCount : 0; agg.under24 += r.under24.length; agg.under44 += r.under44; agg.targets += r.targets;
  agg.rawKeys += r.rawKeys.length; agg.overflow += r.overflow > 1 ? 1 : 0;
}
console.log(JSON.stringify(agg));
