// Checks the F-series pieces that sit in the chat on the running app (default http://127.0.0.1:8015).
//
//   node scripts/qa/f_series_check.mjs [--base http://127.0.0.1:8015] [--keep]
//
// The owner turns the F-series flags on for 40 minutes (an override that expires by itself), a student asks real questions in the
// chat, and the flags are removed again at the end (unless --keep). One question reaches the paid provider.
// Credentials are read from the credential files next to the runtime state and never printed.
import { chromium } from "../../apps/web/node_modules/@playwright/test/index.mjs";
import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const arg = (name, fallback) => { const i = process.argv.indexOf(name); return i > 0 ? process.argv[i + 1] : fallback; };
const BASE = arg("--base", "http://127.0.0.1:8015");
const KEEP = process.argv.includes("--keep");
const CREDS = path.join(root, "infra/local/knowledge-platform-20261023");
const FLAGS = ["policy.rules", "policy.simulator", "agent.procedures", "chat.evidence_receipts", "chat.evidence_ui", "output.read_aloud",
  "input.image", "input.voice"];

const results = [];
const check = (ok, message) => { results.push({ ok, message }); console.log(ok ? "ok  " : "FAIL", message); };
const browser = await chromium.launch();

async function session(role) {
  const c = JSON.parse(fs.readFileSync(path.join(CREDS, role + "-credentials.json"), "utf8"));
  const context = await browser.newContext({ viewport: { width: 1360, height: 860 } });
  const page = await context.newPage();
  await page.goto(BASE + "/login", { waitUntil: "domcontentloaded" });
  await page.locator("input[name=username]").fill(c.username);
  await page.locator("input[name=password]").fill(c.password);
  await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
  await page.waitForURL((url) => !url.pathname.startsWith("/login"), { timeout: 20000 });
  return { context, page };
}

async function change(api, key, body) {
  const list = await (await api.get(BASE + "/v1/admin/features")).json();
  const preview = await api.post(`${BASE}/v1/admin/features/${encodeURIComponent(key)}/preview`, { data: { expected_version: list.version, reason: "F-series check", ...body } });
  if (preview.status() !== 200) throw new Error(`preview ${key}: HTTP ${preview.status()} ${(await preview.text()).slice(0, 160)}`);
  const p = await preview.json();
  const confirm = await api.post(BASE + "/v1/admin/features/confirm", {
    data: { preview_id: p.preview_id, confirmation_token: p.confirmation_token }, headers: { "Idempotency-Key": crypto.randomUUID() } });
  if (confirm.status() !== 200) throw new Error(`confirm ${key}: HTTP ${confirm.status()} ${(await confirm.text()).slice(0, 160)}`);
}

async function ask(page, question) {
  await page.goto(BASE + "/chat", { waitUntil: "domcontentloaded" });
  const box = page.getByPlaceholder(/Hỏi Campus/i);
  await box.fill(question);
  await box.press("Enter");
  await page.waitForTimeout(2500);
  for (let i = 0; i < 40; i++) { if (!(await page.getByRole("button", { name: /dừng|stop/i }).count())) break; await page.waitForTimeout(1500); }
  await page.waitForTimeout(2500);
}

const owner = await session("owner");
let enabled = [];
try {
  const expires = new Date(Date.now() + 40 * 60000).toISOString();
  for (const key of FLAGS) { await change(owner.context.request, key, { value: true, expires_at: expires }); enabled.push(key); }
  check(true, `owner: ${FLAGS.length} flags on for 40 minutes`);
  await new Promise((r) => setTimeout(r, 3000));

  const student = await session("student");
  const features = await (await student.context.request.get(BASE + "/v1/features")).json();
  check(["policy.simulator", "agent.procedures", "chat.evidence_ui", "output.read_aloud"].every((k) => features.features?.[k] === true || features.features?.[k]?.enabled === true || features.features?.[k] === "on"),
    "student: /v1/features shows the new flags on");

  const match = await student.context.request.post(BASE + "/v1/policy-simulator/match", { data: { text: "Cảnh báo học tập bao nhiêu lần thì buộc thôi học?" } });
  const matched = match.status() === 200 ? await match.json() : {};
  check(match.status() === 200 && matched.topic === "FORCED_WITHDRAWAL_WARNINGS", `API: policy match finds the topic (HTTP ${match.status()}, topic ${matched.topic})`);

  const procedures = await student.context.request.post(BASE + "/v1/procedures/runs:from-text", { data: { text: "Em muốn xin giấy xác nhận sinh viên để vay vốn ngân hàng" } });
  const proc = procedures.status() === 200 ? await procedures.json() : {};
  check(procedures.status() === 200 && proc.procedure_id === "student-certificate", `API: procedure suggestion (HTTP ${procedures.status()}, ${proc.procedure_id})`);

  const receiptCalls = [];
  student.page.on("response", (r) => { if (/answer-receipts/.test(r.url())) receiptCalls.push(`${r.status()} ${r.url().replace(BASE, "")}`); });
  await ask(student.page, "Cảnh báo học tập bao nhiêu lần thì buộc thôi học?");
  await student.page.waitForTimeout(3000);
  const main = (await student.page.locator("main").innerText()).replace(/\s+/g, " ");
  check(/Kiểm tra điều kiện/.test(main), "chat: the policy card appears under the question");
  check((await student.page.getByRole("button", { name: /Đọc to/ }).count()) + (await student.page.getByText(/chưa có giọng đọc tiếng Việt/).count()) > 0, "chat: read-aloud button or its no-voice note is shown");
  check(/\d+ ý đã kiểm với nguồn/.test(main), `chat: the evidence line shows how many points were checked (receipt requests: ${receiptCalls.join(" | ") || "none"})`);
  if (!/\d+ ý đã kiểm với nguồn/.test(main)) {
    // Diagnostic: what the chat panel was given (read from React's own props; nothing is changed).
    const props = await student.page.evaluate(() => {
      const el = document.querySelector("[role=article][aria-label]");
      const key = el && Object.keys(el).find((k) => k.startsWith("__reactFiber"));
      for (let f = key ? el[key] : null; f; f = f.return) {
        const p = f.memoizedProps;
        if (p && typeof p === "object" && "messages" in p && "onSendMessage" in p) return { conversationId: p.conversationId ?? null, ids: p.messages.map((m) => String(m.id).slice(0, 8)) };
      }
      return null;
    });
    console.log("diagnostic chat panel props:", JSON.stringify(props));
  }
  await student.page.screenshot({ path: path.join(root, "infra/local/qa-acceptance/f-series-chat.png") });

  await student.page.getByRole("link", { name: "Mở trình kiểm tra" }).first().click();
  await student.page.waitForURL(/policy\/simulator/, { timeout: 15000 });
  await student.page.waitForTimeout(1500);
  check((await student.page.locator("h1").count()) > 0 && /Kiểm tra điều kiện theo quy chế/.test(await student.page.locator("h1").innerText()), "simulator page opens from the card");

  await ask(student.page, "Em muốn xin giấy xác nhận sinh viên để vay vốn ngân hàng");
  check((await student.page.getByRole("button", { name: "Bắt đầu cùng trợ lý" }).count()) > 0, "chat: the procedure card appears");
  await student.page.getByRole("button", { name: "Bắt đầu cùng trợ lý" }).first().click();
  await student.page.waitForURL(/services\/procedures\?run=/, { timeout: 15000 });
  await student.page.waitForTimeout(1500);
  check((await student.page.getByRole("button", { name: "Lưu thông tin" }).count()) > 0, "procedure page shows the form (nothing is sent without the confirm button)");
  await student.page.screenshot({ path: path.join(root, "infra/local/qa-acceptance/f-series-procedure.png") });
  const runs = await (await student.context.request.get(BASE + "/v1/procedures/runs")).json();
  for (const run of runs.items ?? []) if (["STARTED", "COLLECTING"].includes(run.state)) await student.context.request.post(`${BASE}/v1/procedures/runs/${run.id}:cancel`);

  // Procedure submit through the API: a real ticket is created (labelled as an automatic check), and a replayed confirm creates no second one.
  const api = student.context.request;
  const started = await (await api.post(BASE + "/v1/procedures/runs", { data: { procedure_id: "student-certificate" } })).json();
  const filled = await api.put(`${BASE}/v1/procedures/runs/${started.id}/fields`, { data: { row_version: started.row_version,
    fields: { purpose: "Vay vốn", copies: 1, note: "Kiểm thử tự động F-series (dữ liệu thử), có thể đóng" } } });
  const filledRun = filled.status() === 200 ? await filled.json() : {};
  const preview = await (await api.post(`${BASE}/v1/procedures/runs/${started.id}:submit-preview`)).json();
  const key = crypto.randomUUID();
  const confirm = () => api.post(BASE + "/v1/procedures/runs:submit-confirm", { data: { preview_id: preview.preview_id, confirmation_token: preview.confirmation_token }, headers: { "Idempotency-Key": key } });
  const first = await confirm();
  const done = first.status() === 200 ? await first.json() : {};
  const again = await confirm();
  const replay = again.status() === 200 ? await again.json() : {};
  const tickets = await (await api.get(BASE + "/v1/tickets")).json();
  const code = done.ticket?.code ?? done.ticket_code;
  const listed = (tickets.items ?? tickets.tickets ?? []).filter((t) => t.code === code).length;
  check(filled.status() === 200 && first.status() === 200 && done.state === "SUBMITTED" && !!code && listed === 1 && (replay.ticket?.code ?? replay.ticket_code) === code,
    `procedure: submit creates one ticket (fields HTTP ${filled.status()} v${filledRun.row_version}, confirm HTTP ${first.status()}, state ${done.state}, ticket ${code}, listed ${listed}, replay HTTP ${again.status()})`);

  // Image and voice input: real engines on this machine (Tesseract in the WSL sandbox, the local recognizer on 18083).
  const png = fs.readFileSync(path.join(root, ".pytest-tmp/ocr-sample.png"));
  const ocr = await api.post(BASE + "/v1/input/image:ocr", { multipart: { image: { name: "image.png", mimeType: "image/png", buffer: png } } });
  const ocrText = ocr.status() === 200 ? (await ocr.json()).text : "";
  check(ocr.status() === 200 && /Học phí/.test(ocrText) && /2026/.test(ocrText), `image input: OCR reads the rendered text (HTTP ${ocr.status()}: ${ocrText.replace(/\s+/g, " ").slice(0, 60)})`);
  const webm = path.join(root, ".pytest-tmp/voice-sample.webm");
  if (fs.existsSync(webm)) {
    const voice = await api.post(BASE + "/v1/input/voice:transcribe", { multipart: { audio: { name: "voice.webm", mimeType: "audio/webm", buffer: fs.readFileSync(webm) } } });
    const heard = voice.status() === 200 ? await voice.json() : {};
    check(voice.status() === 200 && heard.language === "vi" && (heard.text ?? "").length > 40, `voice input: local recognizer answers (HTTP ${voice.status()}, ${heard.duration_s}s, ${(heard.text ?? "").slice(0, 50)})`);
  }
  await student.context.close();

  // The rules authoring page for the owner.
  await owner.page.goto(BASE + "/knowledge/policy-rules", { waitUntil: "domcontentloaded" });
  await owner.page.waitForTimeout(2500);
  const rulesText = (await owner.page.locator("main").innerText()).replace(/\s+/g, " ");
  check(/Luật từ quy chế/.test(rulesText) && /Đang áp dụng|Cần rà lại/.test(rulesText), "rules page: the owner sees the published rules with their status");
} catch (error) {
  check(false, "script error: " + String(error.message).slice(0, 300));
} finally {
  if (!KEEP) for (const key of enabled) { try { await change(owner.context.request, key, { remove: true }); } catch (e) { console.log("could not remove", key, String(e.message).slice(0, 120)); } }
  await browser.close();
}
const failed = results.filter((r) => !r.ok);
console.log(`\n${results.length - failed.length} checks passed, ${failed.length} failed`);
process.exit(failed.length ? 1 : 0);
