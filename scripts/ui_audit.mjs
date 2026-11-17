import pkg from '../apps/web/node_modules/@playwright/test/index.js';
const { chromium } = pkg;
import fs from 'fs';
import path from 'path';

const SCREENSHOT_DIR = 'C:/Users/Duong Vinh/.gemini/antigravity/brain/8819df69-d894-4ee3-a2d0-e7f7bfa09a41/screenshots';
fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });

const BASE_URL = 'http://127.0.0.1:3115';

const VIEWPORTS = {
  desktop: { width: 1440, height: 900 },
  mobile: { width: 375, height: 667 }
};

const ROUTES = [
  { name: 'home', path: '/', role: 'public' },
  { name: 'login', path: '/login', role: 'public' },
  { name: 'chat', path: '/chat', role: 'student' },
  { name: 'tickets', path: '/tickets', role: 'student' },
  { name: 'schedule', path: '/schedule', role: 'student' },
  { name: 'rooms', path: '/rooms', role: 'student' },
  { name: 'privacy', path: '/privacy', role: 'student' },
  { name: 'knowledge', path: '/knowledge', role: 'staff' },
  { name: 'staff', path: '/staff', role: 'staff' },
  { name: 'admin', path: '/admin', role: 'staff' },
];

async function runAudit() {
  const browser = await chromium.launch({
    executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe',
    headless: true
  });

  const auditResults = {
    timestamp: new Date().toISOString(),
    pages: [],
    summary: {
      totalRoutes: ROUTES.length,
      passedRoutes: 0,
      failedRoutes: 0,
      consoleErrorsTotal: 0,
      a11yIssuesTotal: 0
    }
  };

  for (const route of ROUTES) {
    console.log(`Checking route: ${route.name} (${route.path})`);
    const pageResult = {
      name: route.name,
      path: route.path,
      role: route.role,
      status: 200,
      consoleErrors: [],
      networkFailures: [],
      a11y: {},
      screenshots: {}
    };

    // Test Desktop Light
    const context = await browser.newContext({
      baseURL: BASE_URL,
      viewport: VIEWPORTS.desktop,
      colorScheme: 'light'
    });
    const page = await context.newPage();

    page.on('console', msg => {
      if (msg.type() === 'error') {
        pageResult.consoleErrors.push(msg.text());
      }
    });

    page.on('response', resp => {
      if (resp.status() >= 400 && !resp.url().includes('/favicon.ico')) {
        pageResult.networkFailures.push({ url: resp.url(), status: resp.status() });
      }
    });

    try {
      // If student/staff role needed, simulate login first
      if (route.role === 'student') {
        await page.goto(`${BASE_URL}/login`, { waitUntil: 'domcontentloaded' });
        try {
          await page.getByLabel(/tài khoản/i).fill('SV001');
          await page.getByRole('button', { name: /đăng nhập/i }).click();
          await page.waitForTimeout(500);
        } catch (e) {
          // continue
        }
      } else if (route.role === 'staff') {
        await page.goto(`${BASE_URL}/login`, { waitUntil: 'domcontentloaded' });
        try {
          await page.getByLabel(/tài khoản/i).fill('OF001');
          await page.getByRole('button', { name: /đăng nhập/i }).click();
          await page.waitForTimeout(500);
        } catch (e) {
          // continue
        }
      }

      const res = await page.goto(`${BASE_URL}${route.path}`, { waitUntil: 'networkidle', timeout: 15000 });
      pageResult.status = res ? res.status() : 0;
      await page.waitForTimeout(600);

      // Accessibility audit
      const a11y = await page.evaluate(() => {
        const issues = [];
        // Check main landmarks
        const main = document.querySelector('main');
        if (!main) issues.push('Missing <main> landmark');

        // Check headings
        const h1 = document.querySelector('h1');
        if (!h1) issues.push('Missing <h1> primary heading');

        // Check images alt
        const images = Array.from(document.querySelectorAll('img'));
        const imagesWithoutAlt = images.filter(img => !img.hasAttribute('alt'));
        if (imagesWithoutAlt.length > 0) {
          issues.push(`${imagesWithoutAlt.length} images missing alt text`);
        }

        // Check form controls without accessible label
        const formControls = Array.from(document.querySelectorAll('input:not([type="hidden"]), select, textarea'));
        const unlabelledControls = formControls.filter(ctrl => {
          const id = ctrl.id;
          const hasLabel = id ? !!document.querySelector(`label[for="${id}"]`) : false;
          const hasAriaLabel = !!ctrl.getAttribute('aria-label') || !!ctrl.getAttribute('aria-labelledby');
          const hasTitle = !!ctrl.getAttribute('title');
          return !hasLabel && !hasAriaLabel && !hasTitle;
        });
        if (unlabelledControls.length > 0) {
          issues.push(`${unlabelledControls.length} form controls missing accessible labels`);
        }

        // Check buttons without name
        const buttons = Array.from(document.querySelectorAll('button'));
        const emptyButtons = buttons.filter(btn => {
          const text = btn.innerText.trim();
          const ariaLabel = btn.getAttribute('aria-label');
          const title = btn.getAttribute('title');
          return !text && !ariaLabel && !title;
        });
        if (emptyButtons.length > 0) {
          issues.push(`${emptyButtons.length} buttons missing accessible names`);
        }

        return {
          title: document.title,
          hasMain: !!main,
          hasH1: !!h1,
          issues
        };
      });
      pageResult.a11y = a11y;
      auditResults.summary.a11yIssuesTotal += a11y.issues.length;

      // Capture Desktop Light Screenshot
      const shotDesktopLight = path.join(SCREENSHOT_DIR, `${route.name}_desktop_light.png`);
      await page.screenshot({ path: shotDesktopLight, fullPage: true });
      pageResult.screenshots.desktop_light = shotDesktopLight;

      // Toggle Dark Mode
      await page.evaluate(() => document.documentElement.classList.add('dark'));
      await page.waitForTimeout(300);
      const shotDesktopDark = path.join(SCREENSHOT_DIR, `${route.name}_desktop_dark.png`);
      await page.screenshot({ path: shotDesktopDark, fullPage: true });
      pageResult.screenshots.desktop_dark = shotDesktopDark;

      // Test Mobile Viewport
      await page.setViewportSize(VIEWPORTS.mobile);
      await page.evaluate(() => document.documentElement.classList.remove('dark'));
      await page.waitForTimeout(300);
      const shotMobileLight = path.join(SCREENSHOT_DIR, `${route.name}_mobile_light.png`);
      await page.screenshot({ path: shotMobileLight, fullPage: true });
      pageResult.screenshots.mobile_light = shotMobileLight;

      // Check horizontal overflow in mobile
      const hasOverflow = await page.evaluate(() => {
        return document.documentElement.scrollWidth > window.innerWidth;
      });
      if (hasOverflow) {
        pageResult.a11y.issues.push('Horizontal overflow detected on mobile viewport (375px)');
      }

      auditResults.summary.passedRoutes++;
    } catch (err) {
      console.error(`Error on route ${route.name}:`, err.message);
      pageResult.error = err.message;
      auditResults.summary.failedRoutes++;
    } finally {
      auditResults.summary.consoleErrorsTotal += pageResult.consoleErrors.length;
      auditResults.pages.push(pageResult);
      await context.close();
    }
  }

  await browser.close();

  const reportPath = path.join(SCREENSHOT_DIR, 'audit_report.json');
  fs.writeFileSync(reportPath, JSON.stringify(auditResults, null, 2), 'utf-8');
  console.log(`UI audit complete. Report written to ${reportPath}`);
}

runAudit().catch(err => {
  console.error('Audit failed:', err);
  process.exit(1);
});
