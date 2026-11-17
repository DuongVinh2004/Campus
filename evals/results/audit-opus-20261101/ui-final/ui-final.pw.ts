// Kiểm giao diện sau sửa trên 8015. Đọc credentials trong Node, không in; không gọi mô hình.
// Chạy từ apps/web: npx playwright test --config ../../evals/results/audit-opus-20261101/ui-final/playwright.config.ts
import { test, expect, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const ROOT = path.resolve(__dirname, "../../../..");
const OUT = __dirname;
const BASE = "http://127.0.0.1:8015";
const results: Record<string, unknown> = {};

function credentials() {
  return JSON.parse(fs.readFileSync(path.join(ROOT, "infra/local/knowledge-platform-20261023/student-credentials.json"), "utf8"));
}

async function login(page: Page, redirect: string) {
  const c = credentials();
  await page.goto(`${BASE}/login?redirect=${encodeURIComponent(redirect)}`);
  await page.getByLabel("Tài khoản").fill(c.username);
  await page.getByLabel("Mật khẩu").fill(c.password);
  await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
  await page.waitForURL(u => !u.pathname.endsWith("/login"), { timeout: 20000 });
}

test.afterAll(() => fs.writeFileSync(path.join(OUT, "ui-final.json"), JSON.stringify(results, null, 1)));

test("UI sau sửa: đăng nhập, lịch sử, nguồn, font, mobile, tối, nháp, phiên hết hạn", async ({ page, context }) => {
  const fontStatus: number[] = [];
  page.on("response", r => { if (r.url().includes("/fonts/")) fontStatus.push(r.status()); });

  await login(page, "/chat");
  results.redirect_after_login = new URL(page.url()).pathname;
  results.localStorage_token = await page.evaluate(() => localStorage.getItem("campus247_token"));

  // Lịch sử hội thoại
  const history = page.getByRole("navigation", { name: /Lịch sử/i }).or(page.getByRole("region", { name: /Lịch sử/i })).first();
  await expect(page.getByText(/Lịch sử/).first()).toBeVisible({ timeout: 15000 });
  const links = page.locator('a[href*="/chat?conversation_id="]');
  await expect(links.first()).toBeVisible({ timeout: 15000 });
  results.history_items = await links.count();
  results.history_has_region = await history.count();
  await page.screenshot({ path: path.join(OUT, "01-history.png") });

  // Mở hội thoại có trích dẫn (tìm mục có câu hỏi về phòng máy)
  const target = links.filter({ hasText: /phòng máy|trực tuyến/i }).first();
  await (await target.count() ? target : links.first()).click();
  await page.waitForURL(/conversation_id=/);
  await expect(page.getByRole("article").first()).toBeVisible({ timeout: 15000 });
  results.restore_error = await page.getByText("Không thể khôi phục lịch sử").count();
  results.restored_articles = await page.getByRole("article").count();
  results.current_marked = await page.locator('a[aria-current="page"][href*="conversation_id="]').count();

  // Mở nguồn + "Mở đoạn nguồn gốc"
  const sourceButton = page.getByRole("button", { name: /Xem nguồn trích dẫn \[1\]/ }).first();
  if (await sourceButton.count()) {
    await sourceButton.click();
    await page.getByRole("button", { name: "Mở đoạn nguồn gốc" }).first().click();
    await page.waitForTimeout(3000);
    const dialog = page.getByRole("dialog");
    results.source_alerts = await dialog.getByRole("alert").allTextContents();
    results.source_has_issuer = (await dialog.textContent())?.includes("Cơ quan ban hành") ?? false;
    results.drawer_horizontal_overflow = await dialog.evaluate(el => {
      const scroller = [el, ...el.querySelectorAll("*")].some(n => (n as HTMLElement).scrollWidth > (n as HTMLElement).clientWidth + 2
        && getComputedStyle(n as HTMLElement).overflowX !== "visible" && getComputedStyle(n as HTMLElement).overflowX !== "hidden");
      return scroller;
    });
    results.drawer_font = await dialog.evaluate(el => getComputedStyle(el.querySelector("h3") || el).fontFamily);
    await page.screenshot({ path: path.join(OUT, "02-source-drawer.png") });
    await page.keyboard.press("Escape");
  } else {
    results.source_button = "not found in restored conversation";
  }
  results.font_responses = fontStatus;

  // Mobile 375 + nút menu
  await page.setViewportSize({ width: 375, height: 812 });
  await page.reload();
  await page.waitForTimeout(2500);
  await page.screenshot({ path: path.join(OUT, "03-mobile-chat.png") });
  results.mobile_horizontal_scroll = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);

  // Chế độ tối: nút "Chuẩn bị thủ tục mới" ở Hồ sơ của tôi
  await page.emulateMedia({ colorScheme: "dark" });
  await page.goto(`${BASE}/tickets`);
  const button = page.getByText("Chuẩn bị thủ tục mới", { exact: true }).first();
  await expect(button).toBeVisible({ timeout: 15000 });
  results.dark_button_contrast = await button.evaluate(el => {
    const parse = (s: string) => (s.match(/[\d.]+/g) || []).slice(0, 3).map(Number);
    const lum = ([r, g, b]: number[]) => { const f = (c: number) => { c /= 255; return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4); }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
    let node: HTMLElement | null = el as HTMLElement; let bg = "rgba(0, 0, 0, 0)";
    while (node && /rgba\(0, 0, 0, 0\)|transparent/.test(bg)) { bg = getComputedStyle(node).backgroundColor; node = node.parentElement; }
    const a = lum(parse(getComputedStyle(el).color)), b = lum(parse(bg));
    return Number(((Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05)).toFixed(2));
  });
  // Danh sách nháp có dòng trích + mở nháp cuộn tới biểu mẫu
  const drafts = page.locator("li button").filter({ hasText: /Nháp · v/ });
  results.draft_items = await drafts.count();
  results.draft_snippets = await drafts.evaluateAll(els => els.slice(0, 3).map(e => (e.querySelector(".truncate")?.textContent || "").slice(0, 60)));
  if (await drafts.count()) {
    await drafts.first().click();
    await page.waitForTimeout(800);
    results.draft_form_in_view = await page.getByLabel("Nội dung / lý do").evaluate(el => {
      const r = el.getBoundingClientRect(); return r.top >= 0 && r.bottom <= window.innerHeight;
    });
  }
  await page.screenshot({ path: path.join(OUT, "04-mobile-dark-tickets.png") });
  await page.emulateMedia({ colorScheme: "light" });
  await page.setViewportSize({ width: 1280, height: 800 });

  // Phiên hết hạn: xóa cookie rồi gửi câu hỏi (máy chủ trả 401, không gọi mô hình)
  await page.goto(`${BASE}/chat`);
  await page.waitForTimeout(1500);
  await context.clearCookies();
  await page.getByRole("textbox", { name: "Đặt câu hỏi" }).fill("Kiểm tra phiên hết hạn");
  await page.keyboard.press("Enter");
  await page.waitForTimeout(3000);
  results.expired_login_links = await page.locator('a[href^="/login?redirect="]').count();
  results.expired_text = (await page.locator("main").textContent())?.match(/[^.]*(hết hạn|đăng nhập lại)[^.]*/i)?.[0] ?? null;
  await page.screenshot({ path: path.join(OUT, "05-session-expired.png") });
});
