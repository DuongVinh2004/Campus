const { chromium } = require('@playwright/test');
const fs = require('fs');
const path = require('path');

const outputDir = path.resolve('C:/Users/Duong Vinh/.gemini/antigravity/brain/541a547e-29d2-4ac3-9823-b7b23dcfc12e/screenshots');
if (!fs.existsSync(outputDir)) {
  fs.mkdirSync(outputDir, { recursive: true });
}

const routes = [
  { name: 'home_desktop_light', url: 'http://localhost:3000/', viewport: { width: 1440, height: 900 }, dark: false },
  { name: 'home_desktop_dark', url: 'http://localhost:3000/', viewport: { width: 1440, height: 900 }, dark: true },
  { name: 'home_mobile', url: 'http://localhost:3000/', viewport: { width: 375, height: 812 }, dark: false },
  
  { name: 'login_desktop_light', url: 'http://localhost:3000/login', viewport: { width: 1440, height: 900 }, dark: false },
  { name: 'login_desktop_dark', url: 'http://localhost:3000/login', viewport: { width: 1440, height: 900 }, dark: true },
  
  { name: 'chat_desktop_light', url: 'http://localhost:3000/chat', viewport: { width: 1440, height: 900 }, dark: false },
  { name: 'chat_desktop_dark', url: 'http://localhost:3000/chat', viewport: { width: 1440, height: 900 }, dark: true },
  { name: 'chat_mobile', url: 'http://localhost:3000/chat', viewport: { width: 375, height: 812 }, dark: false },
  
  { name: 'schedule_desktop', url: 'http://localhost:3000/schedule', viewport: { width: 1440, height: 900 }, dark: false },
  { name: 'tickets_desktop', url: 'http://localhost:3000/tickets', viewport: { width: 1440, height: 900 }, dark: false },
  { name: 'rooms_desktop', url: 'http://localhost:3000/rooms', viewport: { width: 1440, height: 900 }, dark: false },
  { name: 'staff_desktop', url: 'http://localhost:3000/staff', viewport: { width: 1440, height: 900 }, dark: false },
  { name: 'knowledge_desktop', url: 'http://localhost:3000/knowledge', viewport: { width: 1440, height: 900 }, dark: false },
  { name: 'admin_desktop', url: 'http://localhost:3000/admin', viewport: { width: 1440, height: 900 }, dark: false },
  { name: 'privacy_desktop', url: 'http://localhost:3000/privacy', viewport: { width: 1440, height: 900 }, dark: false },
];

async function capture() {
  const browser = await chromium.launch();
  console.log('Browser launched. Starting screenshot capture...');

  for (const r of routes) {
    const context = await browser.newContext({
      viewport: r.viewport,
      colorScheme: r.dark ? 'dark' : 'light',
    });
    const page = await context.newPage();
    try {
      await page.goto(r.url, { waitUntil: 'networkidle', timeout: 15000 });
      if (r.dark) {
        await page.evaluate(() => document.documentElement.classList.add('dark'));
      }
      await page.waitForTimeout(600);
      const filePath = path.join(outputDir, `${r.name}.png`);
      await page.screenshot({ path: filePath, fullPage: false });
      console.log(`Captured: ${r.name} -> ${filePath}`);
    } catch (err) {
      console.error(`Failed ${r.name}:`, err.message);
    } finally {
      await context.close();
    }
  }

  await browser.close();
  console.log('Capture complete!');
}

capture().catch((err) => {
  console.error(err);
  process.exit(1);
});
