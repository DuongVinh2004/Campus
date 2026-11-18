import { chromium } from '@playwright/test';
import { spawn } from 'child_process';
import path from 'path';
import fs from 'fs';

const screenshotDir = 'C:/Users/Duong Vinh/.gemini/antigravity/brain/02da27b2-7527-47d4-a6a0-b31819578736/screenshots';
if (!fs.existsSync(screenshotDir)) {
  fs.mkdirSync(screenshotDir, { recursive: true });
}

async function waitPort(url, maxRetries = 30) {
  for (let i = 0; i < maxRetries; i++) {
    try {
      const res = await fetch(url);
      if (res.ok || res.status < 500) return true;
    } catch (e) {
      // wait
    }
    await new Promise(r => setTimeout(r, 500));
  }
  return false;
}

async function main() {
  console.log('Starting Next.js production server for QA capture...');
  const server = spawn('npx', ['next', 'start', '-p', '3000'], {
    cwd: path.resolve('C:/Users/Duong Vinh/Vinh/apps/web'),
    shell: true,
    stdio: 'inherit'
  });

  const ready = await waitPort('http://localhost:3000');
  if (!ready) {
    server.kill();
    throw new Error('Server failed to start on port 3000');
  }
  console.log('Server is ready on port 3000.');

  const browser = await chromium.launch();

  const pagesToCapture = [
    { name: 'app_home_light', path: '/', dark: false },
    { name: 'app_home_dark', path: '/', dark: true },
    { name: 'app_login_light', path: '/login', dark: false },
    { name: 'app_login_dark', path: '/login', dark: true },
    { name: 'app_chat_light', path: '/chat', dark: false },
    { name: 'app_chat_dark', path: '/chat', dark: true },
  ];

  for (const item of pagesToCapture) {
    const context = await browser.newContext({
      viewport: { width: 1440, height: 900 },
      colorScheme: item.dark ? 'dark' : 'light'
    });
    const page = await context.newPage();
    await page.goto(`http://localhost:3000${item.path}`, { waitUntil: 'networkidle' });
    if (item.dark) {
      await page.evaluate(() => document.documentElement.classList.add('dark'));
    } else {
      await page.evaluate(() => document.documentElement.classList.remove('dark'));
    }
    await page.waitForTimeout(300);

    const outPath = path.join(screenshotDir, `${item.name}.png`);
    await page.screenshot({ path: outPath, fullPage: false });
    console.log(`Captured: ${item.name} -> ${outPath}`);
    await context.close();
  }

  await browser.close();
  server.kill('SIGTERM');
  console.log('QA captures completed and server stopped.');
}

main().catch(err => {
  console.error('QA Capture error:', err);
  process.exit(1);
});
