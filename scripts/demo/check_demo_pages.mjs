// Sign in through the real form as one simulated student, officer and lecturer; open their main pages; save screenshots and
// a short text summary of each page. Passwords are read from the credential files and never printed.
//   node scripts/demo/check_demo_pages.mjs
import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';

const repo = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const require = createRequire(path.join(repo, 'apps/web/package.json'));
const {chromium} = require('@playwright/test');
const BASE = 'http://127.0.0.1:8015';
const out = path.join(repo, 'infra/local/seed-demo-2026hk1/page-check');
fs.mkdirSync(out, {recursive: true});
const directory = JSON.parse(fs.readFileSync(path.join(repo, 'infra/local/knowledge-platform-20261023/campus-directory-credentials.json'), 'utf8')).accounts;
const learning = JSON.parse(fs.readFileSync(path.join(repo, 'infra/local/learning-materials-20261104-01/credentials.json'), 'utf8')).accounts;
const people = [
  {who: 'student', account: directory.find(a => a.username === 'sv.demo01'), pages: ['/', '/schedule', '/tickets', '/rooms', '/notifications', '/services', '/chat', '/learning']},
  {who: 'officer', account: directory.find(a => a.username === 'nv.demo01'), pages: ['/', '/staff', '/rooms', '/notifications']},
  {who: 'lecturer', account: learning.find(a => a.username === 'gv.demo01'), pages: ['/learning']},
];
const browser = await chromium.launch({headless: true, executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
const summary = [];
try {
  for (const person of people) {
    const context = await browser.newContext({viewport: {width: 1366, height: 900}, locale: 'vi-VN'});
    const page = await context.newPage();
    await page.goto(BASE + '/login', {waitUntil: 'domcontentloaded'});
    await page.locator('input[name=username]').fill(person.account.username);
    await page.locator('input[name=password]').fill(person.account.password);
    await page.getByRole('button', {name: 'Đăng nhập', exact: true}).click();
    await page.waitForURL(url => !url.pathname.startsWith('/login'), {timeout: 20000});
    for (const route of person.pages) {
      await page.goto(BASE + route, {waitUntil: 'networkidle'}).catch(() => {});
      await page.waitForTimeout(1500);
      const text = (await page.locator('main').innerText().catch(() => '')).replace(/\s+/g, ' ').trim();
      const file = `${person.who}${route.replace(/\//g, '_') || '_home'}.png`;
      await page.screenshot({path: path.join(out, file), fullPage: false});
      summary.push({who: person.who, user: person.account.username, route, status: page.url().includes('/login') ? 'REDIRECTED_TO_LOGIN' : 'ok',
                    chars: text.length, excerpt: text.slice(0, 220)});
    }
    await context.close();
  }
} finally {
  await browser.close();
}
fs.writeFileSync(path.join(out, 'summary.json'), JSON.stringify(summary, null, 1));
for (const row of summary) console.log(`${row.who} ${row.route} ${row.status} ${row.chars} | ${row.excerpt}`);
