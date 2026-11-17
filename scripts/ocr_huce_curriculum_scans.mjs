import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const root = fs.realpathSync(path.resolve(path.dirname(fileURLToPath(import.meta.url)), ".."));
const require = createRequire("C:/Users/Duong Vinh/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/package.json");
const { createWorker } = require("tesseract.js");
function checked(candidate) {
  const absolute = path.resolve(candidate);
  const relative = path.relative(root, absolute);
  if (!relative || relative.startsWith("..") || path.isAbsolute(relative)) throw new Error("workspace descendant required");
  let cursor = absolute;
  while (cursor !== root) {
    if (fs.existsSync(cursor) && fs.lstatSync(cursor).isSymbolicLink()) throw new Error("reparse destination denied");
    cursor = path.dirname(cursor);
  }
  return absolute;
}
const input = checked(path.join(root, "data/huce-discovery-20261020/curricula-20261020T150911234144Z/scan-review"));
const output = checked(path.join(root, "data/huce-discovery-20261020", `ocr-${new Date().toISOString().replace(/[:.]/g, "-")}`));
fs.mkdirSync(output);
const language = checked(path.join(root, "data/huce-public-20261013"));
const worker = await createWorker("vie", 1, { langPath: language, cachePath: output, gzip: false,
  cacheMethod: "none", logger: () => {} });
const pages = [];
try {
  for (const page of [1, 2]) {
    const { data } = await worker.recognize(checked(path.join(input, `page-${page}.png`)), {}, { text: true, tsv: true, blocks: true });
    const record = { page, text: data.text, confidence: data.confidence, blocks: data.blocks,
      language: "vie", extractor: "tesseract.js-7.0.0", source: path.relative(root, input),
      visual_review: "title_and_semester_credit_counts_checked; full_OCR_grid_unreviewed",
      rag_status: "not_admitted; 2025_chart_cohort_scope_requires_review" };
    fs.writeFileSync(checked(path.join(output, `page-${page}.json`)), JSON.stringify(record, null, 2), { flag: "wx" });
    if (data.tsv) fs.writeFileSync(checked(path.join(output, `page-${page}.tsv`)), data.tsv, { flag: "wx" });
    pages.push({ page, confidence: data.confidence, characters: data.text.length });
  }
  fs.writeFileSync(checked(path.join(output, "manifest.json")), JSON.stringify({ pages, original_drive_id: "1nPJqjaUqzlYIvT4OR1YMFoBjnP4yysxb",
    source_layout_manifest: "data/huce-discovery-20261020/layout-20261020T153253945901Z/manifest.json", complete_visual_table_review: false }, null, 2), { flag: "wx" });
  console.log(JSON.stringify({ output, pages }));
} finally {
  await worker.terminate();
}
