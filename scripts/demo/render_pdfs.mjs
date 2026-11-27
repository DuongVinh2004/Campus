// Render simulated lecture PDFs from locally authored HTML with local Chrome (no network).
//   node scripts/demo/render_pdfs.mjs <specs.json> <output-dir>
// specs.json: [{"file": "IT3090-01.pdf", "html": "<!doctype html>..."}]. Existing files are never overwritten.
import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';

const repo = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const require = createRequire(path.join(repo, 'apps/web/package.json'));
const {chromium} = require('@playwright/test');
const [specsPath, output] = process.argv.slice(2);
const specs = JSON.parse(fs.readFileSync(specsPath, 'utf8'));
fs.mkdirSync(output, {recursive: true});
const browser = await chromium.launch({headless: true, executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
let written = 0;
try {
  const page = await browser.newPage();
  for (const spec of specs) {
    const target = path.join(output, spec.file);
    if (fs.existsSync(target)) continue;
    await page.setContent(spec.html, {waitUntil: 'load'});
    const bytes = await page.pdf({format: 'A4', printBackground: true, tagged: true, outline: true,
      margin: {top: '18mm', bottom: '18mm', left: '18mm', right: '18mm'}, displayHeaderFooter: true,
      headerTemplate: '<span></span>',
      footerTemplate: '<div style="font-size:8px;width:100%;text-align:center;color:#666;font-family:Arial">Tài liệu mô phỏng — Campus 24/7 · không phải tài liệu chính thức của HUCE · trang <span class="pageNumber"></span>/<span class="totalPages"></span></div>'});
    fs.writeFileSync(target, bytes, {flag: 'wx'});
    written += 1;
  }
} finally {
  await browser.close();
}
console.log(JSON.stringify({output, written, total: specs.length}));
