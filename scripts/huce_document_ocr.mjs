// Local OCR stage for the common document pipeline. OCR never assigns table/arrow semantics.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const root = fs.realpathSync(path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..'));
function checked(value) {
  const absolute = path.resolve(value);
  const relative = path.relative(root, absolute);
  if (!relative || relative.startsWith('..') || path.isAbsolute(relative)) throw new Error('workspace descendant required');
  for (let cursor = absolute; cursor !== root; cursor = path.dirname(cursor)) {
    if (fs.existsSync(cursor) && fs.lstatSync(cursor).isSymbolicLink()) throw new Error('reparse path denied');
  }
  return absolute;
}
const hash = data => crypto.createHash('sha256').update(data).digest('hex');
const manifestPath = checked(process.argv[2]);
const jobs = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
const require = createRequire(jobs.node_package_root);
const { createWorker } = require('tesseract.js');
const version = require('tesseract.js/package.json').version;
const language = checked(jobs.language_directory);
const trainedData = checked(path.join(language, 'vie.traineddata'));
const dependency = { version, language: 'vie', traineddata_sha256: hash(fs.readFileSync(trainedData)),
  geometry: 'tesseract pixel boxes; unreviewed, no inferred cells or relationships' };
if (jobs.parameters) dependency.parameters = jobs.parameters;
const worker = await createWorker('vie', 1, { langPath: language, gzip: false, cacheMethod: 'none',
  cachePath: checked(jobs.output_directory), logger: () => {} });
try {
  if (jobs.parameters) await worker.setParameters(jobs.parameters);
  for (const job of jobs.pages) {
    const original = checked(path.join(root, job.source_file));
    if (hash(fs.readFileSync(original)) !== job.source_sha256) throw new Error('original payload changed');
    const input = checked(path.join(root, job.image));
    if (hash(fs.readFileSync(input)) !== job.image_sha256) throw new Error('render changed');
    const binding = job.cell_id ? { cell_id: job.cell_id, source_bbox_pixels: job.source_bbox_pixels,
      original_page_image_sha256: job.original_page_image_sha256 } : undefined;
    const key = hash(JSON.stringify({ dependency, image_sha256: job.image_sha256, ...(binding ? { binding } : {}) }));
    const destination = checked(path.join(jobs.output_directory, `page-${job.page}-${key}.json`));
    if (fs.existsSync(destination)) {
      const record = JSON.parse(fs.readFileSync(destination, 'utf8'));
      if (record.image_sha256 !== job.image_sha256 || record.source_sha256 !== job.source_sha256
          || (job.cell_id && record.cell_id !== job.cell_id)) throw new Error('OCR cache mismatch');
      console.log(JSON.stringify({ page: job.page, cache_reused: true, destination }));
      continue;
    }
    const { data } = await worker.recognize(input, {}, { text: true, tsv: true, blocks: true });
    const record = { ...job, dependency, text: data.text, confidence: data.confidence,
      blocks: data.blocks, tsv: data.tsv, review_status: 'OCR_unreviewed', index_status: 'not_admitted' };
    const serialized = JSON.stringify(record, null, 2);
    fs.writeFileSync(destination, serialized, { flag: 'wx' });
    console.log(JSON.stringify({ page: job.page, characters: data.text.length, destination }));
  }
} finally { await worker.terminate(); }
