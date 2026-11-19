import { chromium } from '@playwright/test';
import fs from 'fs';
import path from 'path';

const screenshotDir = 'C:/Users/Duong Vinh/.gemini/antigravity/brain/02da27b2-7527-47d4-a6a0-b31819578736/screenshots';
if (!fs.existsSync(screenshotDir)) {
  fs.mkdirSync(screenshotDir, { recursive: true });
}

const htmlPath = 'file:///C:/Users/Duong%20Vinh/Vinh/fluent-ai-landing.html';

async function runVerification() {
  console.log('--- Starting Estilo Fluent AI Verification ---');
  const browser = await chromium.launch();
  
  // 1. Desktop Light Mode
  console.log('1. Testing Desktop Light Mode (1440x900)...');
  const desktopContext = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    colorScheme: 'light'
  });
  const page = await desktopContext.newPage();
  await page.goto(htmlPath, { waitUntil: 'load' });
  await page.waitForTimeout(500);

  // Verification checks on page
  const pageText = await page.innerText('body');
  const forbiddenWords = ['Elevate', 'Seamless', 'Unleash', 'Next-Gen'];
  for (const word of forbiddenWords) {
    if (pageText.toLowerCase().includes(word.toLowerCase())) {
      throw new Error(`Forbidden word "${word}" found in page copy!`);
    }
  }
  console.log('✔ Forbidden words check passed: No "Elevate", "Seamless", "Unleash", "Next-Gen" found.');

  // Check required sections
  const requiredSelectors = [
    'header',
    '#hero',
    '#capabilities',
    '#testimonials',
    '#pricing',
    '#cta',
    'footer'
  ];
  for (const sel of requiredSelectors) {
    const el = await page.$(sel);
    if (!el) throw new Error(`Missing required section: ${sel}`);
  }
  console.log('✔ All 7 required sections detected.');

  const lightScreenshotPath = path.join(screenshotDir, 'fluent_ai_desktop_light.png');
  await page.screenshot({ path: lightScreenshotPath, fullPage: true });
  console.log(`✔ Desktop Light screenshot saved: ${lightScreenshotPath}`);

  // 2. Test Pricing Switcher
  console.log('2. Testing Pricing Switcher...');
  const priceBefore = await page.locator('.price-val').first().innerText();
  await page.click('#btnAnnual');
  await page.waitForTimeout(200);
  const priceAfter = await page.locator('.price-val').first().innerText();
  if (priceBefore === priceAfter) {
    throw new Error('Pricing toggle failed to change price!');
  }
  console.log(`✔ Pricing toggle verified ($49/mo -> ${priceAfter}/mo).`);

  // 3. Test Dark Mode Switcher
  console.log('3. Testing Dark Mode Toggle...');
  await page.click('#themeToggleBtn');
  await page.waitForTimeout(300);
  const isDark = await page.evaluate(() => document.documentElement.classList.contains('dark'));
  if (!isDark) throw new Error('Theme toggle failed to set .dark class!');
  console.log('✔ Dark mode class toggled successfully.');

  await page.evaluate(() => window.scrollTo(0, 0));
  await page.waitForTimeout(200);
  const darkScreenshotPath = path.join(screenshotDir, 'fluent_ai_desktop_dark.png');
  await page.screenshot({ path: darkScreenshotPath, fullPage: true });
  console.log(`✔ Desktop Dark screenshot saved: ${darkScreenshotPath}`);

  // 4. Test Mobile Viewport (375x812)
  console.log('4. Testing Mobile Viewport (375x812)...');
  const mobileContext = await browser.newContext({
    viewport: { width: 375, height: 812 },
    colorScheme: 'light'
  });
  const mobilePage = await mobileContext.newPage();
  await mobilePage.goto(htmlPath, { waitUntil: 'load' });
  await mobilePage.waitForTimeout(400);

  // Test mobile menu drawer toggle
  await mobilePage.click('#mobileMenuBtn');
  await mobilePage.waitForTimeout(200);
  const isDrawerOpen = await mobilePage.evaluate(() => !document.getElementById('mobileMenuDrawer').classList.contains('hidden'));
  if (!isDrawerOpen) throw new Error('Mobile drawer failed to open on toggle!');
  console.log('✔ Mobile drawer toggles correctly.');

  const mobileScreenshotPath = path.join(screenshotDir, 'fluent_ai_mobile.png');
  await mobilePage.screenshot({ path: mobileScreenshotPath, fullPage: false });
  console.log(`✔ Mobile screenshot saved: ${mobileScreenshotPath}`);

  await browser.close();
  console.log('--- ALL VERIFICATIONS PASSED WITH EXIT CODE 0 ---');
}

runVerification().catch(err => {
  console.error('VERIFICATION FAILED:', err);
  process.exit(1);
});
