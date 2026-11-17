import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const directory = path.join(root, 'data', 'huce-public-20261013');
const require = createRequire('C:/Users/Duong Vinh/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/package.json');
const { createWorker } = require('tesseract.js');
const output = path.join(directory, 'handbook-reviewed.json');
if (fs.existsSync(output)) throw new Error('Retain existing OCR evidence');
const worker = await createWorker('vie', 1, {langPath: directory, cachePath: directory, gzip: false, cacheMethod:'none',logger:()=>{}});
const source = JSON.parse(fs.readFileSync(path.join(directory, 'handbook-visible.json'), 'utf8'));
const pages = [15,27,28,29,34,35,70,71,...Array.from({length:10},(_,i)=>106+i)];
try {
  for (const page of pages) {
    const name = `page-${String(page).padStart(3,'0')}.png`;
    const {data} = await worker.recognize(path.join(directory,'handbook-pages',name));
    let chunk = source.chunks.find(c=>c.page===page);
    if (data.confidence < 75) {
      console.log(JSON.stringify({page,confidence:data.confidence,retained_visible_text:true}));
      continue;
    }
    if (!chunk) {
      chunk = {...source.chunks[0],page,section:`Trang ${page}`,text:''};
      source.chunks.push(chunk);
    }
    chunk.text = data.text.trim();
    chunk.ocr_confidence = data.confidence;
    console.log(JSON.stringify({page,confidence:data.confidence}));
  }
  fs.writeFileSync(output,JSON.stringify({...source,extraction:'visible-box-and-vietnamese-OCR',ocr_pages:pages},null,2),{flag:'wx'});
} finally { await worker.terminate(); }
