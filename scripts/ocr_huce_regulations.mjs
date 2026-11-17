import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const directory = path.join(root, 'data', 'huce-public-20261013');
const require = createRequire('C:/Users/Duong Vinh/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/package.json');
const { createWorker } = require('tesseract.js');
const output = path.join(directory, 'regulations-ocr.json');
if (fs.existsSync(output)) throw new Error('Retain existing OCR evidence');
const worker = await createWorker('vie', 1, {
  langPath: directory, cachePath: directory, gzip: false, cacheMethod: 'none',
  logger: () => {},
});
const source = JSON.parse(fs.readFileSync(path.join(directory, 'regulations.json'), 'utf8'));
const chunks = [];
try {
  for (let page = 1; page <= 26; page++) {
    const name = `page-${String(page).padStart(2, '0')}.png`;
    const { data } = await worker.recognize(path.join(directory, 'regulation-pages', name));
    const prior = source.chunks.find(chunk => chunk.page === page);
    chunks.push({ ...prior, text: data.text.trim(), ocr_confidence: data.confidence });
    console.log(JSON.stringify({ page, confidence: data.confidence }));
  }
  fs.writeFileSync(output, JSON.stringify({ ...source, chunks, extraction: 'tesseract.js-vietnamese' }, null, 2), { flag: 'wx' });
} finally {
  await worker.terminate();
}
