import { createRequire } from "node:module";
import * as fs from "node:fs";
import * as path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const require = createRequire(path.resolve(__dirname, "../../apps/web/package.json"));
const { chromium } = require("@playwright/test");

const SCREENSHOTS_DIR = path.resolve(__dirname, "screenshots");
if (!fs.existsSync(SCREENSHOTS_DIR)) {
  fs.mkdirSync(SCREENSHOTS_DIR, { recursive: true });
}

async function run() {
  console.log("Starting browser verification...");
  const browser = await chromium.launch({ headless: true });
  const results = {
    checks: [],
    screenshots: {},
  };

  try {
    // 1. Desktop 1440x900
    const desktopContext = await browser.newContext({
      viewport: { width: 1440, height: 900 },
      deviceScaleFactor: 2,
    });
    const desktopPage = await desktopContext.newPage();
    await desktopPage.goto("http://localhost:3000/", { waitUntil: "networkidle" });
    await desktopPage.waitForTimeout(1000);

    const desktopPath = path.join(SCREENSHOTS_DIR, "desktop-shell.png");
    await desktopPage.screenshot({ path: desktopPath });
    results.screenshots.desktop = desktopPath;
    console.log("Desktop screenshot saved:", desktopPath);

    // Verify skip link on desktop
    await desktopPage.keyboard.press("Tab");
    const activeElHref = await desktopPage.evaluate(() => document.activeElement?.getAttribute("href"));
    const skipLinkPassed = activeElHref === "#main-content";
    results.checks.push({ name: "Skip link to #main-content on Tab", pass: skipLinkPassed, detail: activeElHref });

    // Verify landmarks
    const bannerCount = await desktopPage.locator("header[role='banner']").count();
    const navCount = await desktopPage.locator("nav[aria-label='Điều hướng chính']").count();
    const mainCount = await desktopPage.locator("main#main-content").count();
    const footerCount = await desktopPage.locator("footer[role='contentinfo']").count();
    results.checks.push({
      name: "Semantic landmarks (banner, nav, main, footer)",
      pass: bannerCount === 1 && navCount === 1 && mainCount === 1 && footerCount === 1,
      detail: `banner: ${bannerCount}, nav: ${navCount}, main: ${mainCount}, footer: ${footerCount}`,
    });

    // Dark mode toggle on desktop
    const themeToggleBtn = desktopPage.locator(".campus-theme-toggle");
    await themeToggleBtn.click();
    await desktopPage.waitForTimeout(500);
    const isDark = await desktopPage.evaluate(() => document.documentElement.classList.contains("dark"));
    const darkPath = path.join(SCREENSHOTS_DIR, "dark-mode-shell.png");
    await desktopPage.screenshot({ path: darkPath });
    results.screenshots.dark = darkPath;
    results.checks.push({ name: "Dark mode toggle activated html.dark", pass: isDark });
    console.log("Dark mode screenshot saved:", darkPath);

    await desktopContext.close();

    // 2. Mobile 390x844 (iPhone 14 / standard modern mobile)
    const mobileContext = await browser.newContext({
      viewport: { width: 390, height: 844 },
      deviceScaleFactor: 2,
    });
    const mobilePage = await mobileContext.newPage();
    await mobilePage.goto("http://localhost:3000/", { waitUntil: "networkidle" });
    await mobilePage.waitForTimeout(1000);

    // Check no horizontal scroll at 390px
    const overflowCheck = await mobilePage.evaluate(() => {
      const docWidth = document.documentElement.scrollWidth;
      const winWidth = window.innerWidth;
      const bodyWidth = document.body.scrollWidth;
      return { docWidth, winWidth, bodyWidth, hasHorizontalScroll: docWidth > winWidth || bodyWidth > winWidth };
    });
    results.checks.push({
      name: "No horizontal scroll at 390px",
      pass: !overflowCheck.hasHorizontalScroll,
      detail: overflowCheck,
    });

    const mobilePath = path.join(SCREENSHOTS_DIR, "mobile-shell.png");
    await mobilePage.screenshot({ path: mobilePath });
    results.screenshots.mobile = mobilePath;
    console.log("Mobile screenshot saved:", mobilePath);

    // 3. Test mobile navigation dialog
    const menuBtn = mobilePage.locator("button[aria-label='Mở điều hướng']");
    const menuBtnVisible = await menuBtn.isVisible();
    results.checks.push({ name: "Mobile menu trigger visible on <960px", pass: menuBtnVisible });

    await menuBtn.click();
    await mobilePage.waitForTimeout(400);

    const dialogVisible = await mobilePage.locator("div[role='dialog']").isVisible();
    const dialogPath = path.join(SCREENSHOTS_DIR, "mobile-menu-dialog.png");
    await mobilePage.screenshot({ path: dialogPath });
    results.screenshots.mobileMenu = dialogPath;
    results.checks.push({ name: "Mobile navigation dialog opens", pass: dialogVisible });
    console.log("Mobile dialog screenshot saved:", dialogPath);

    // Check Escape closes dialog and restores focus
    await mobilePage.keyboard.press("Escape");
    await mobilePage.waitForTimeout(400);
    const dialogClosed = !(await mobilePage.locator("div[role='dialog']").isVisible());
    const focusReturnedToTrigger = await mobilePage.evaluate(() => {
      return document.activeElement?.getAttribute("aria-label") === "Mở điều hướng";
    });
    results.checks.push({
      name: "Escape key closes dialog and restores focus to menu trigger",
      pass: dialogClosed && focusReturnedToTrigger,
      detail: { dialogClosed, focusReturnedToTrigger },
    });

    await mobileContext.close();

    console.log("\n=== VERIFICATION RESULTS ===");
    console.log(JSON.stringify(results, null, 2));
  } finally {
    await browser.close();
  }
}

run().catch((err) => {
  console.error("Verification failed:", err);
  process.exit(1);
});
