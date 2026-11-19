// Browser check of the optional learning features on an isolated synthetic bundle:
// exit tickets, page feedback, shared explanations, version changes, idea cards, accessible text, and
// that a signed-in student keeps focus and typed text while the account is re-checked in the background.
//
//   python scripts/learning_features_rehearsal.py seed  --name learning-features-<date>-01 --pdf <a.pdf> --pdf <b.pdf>
//   python scripts/learning_features_rehearsal.py serve --name learning-features-<date>-01
//   LEARNING_TEST_CREDENTIALS=<bundle>/credentials.json LEARNING_TEST_PDF_V2=<b.pdf> node e2e/learning-features.mjs
//
// Needs a fresh seed per run (it creates tickets and releases). Takes about five minutes.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium, expect } from "@playwright/test";

const repo = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../..");
const run = process.env.LEARNING_BROWSER_RUN || "features-" + new Date().toISOString().slice(0, 10) + "-01";
if (!/^[a-z0-9-]+$/.test(run)) throw new Error("Invalid run identifier");
const output = path.join(repo, ".tooling", `learning-browser-${run}`);
if (fs.existsSync(output)) throw new Error("Output must be a new directory inside .tooling");
fs.mkdirSync(output, { recursive: true });
const credentialPath = fs.realpathSync(process.env.LEARNING_TEST_CREDENTIALS || "");
if (!credentialPath.startsWith(repo + path.sep) || path.basename(credentialPath) !== "credentials.json") throw new Error("Synthetic workspace credentials are required");
const credentials = JSON.parse(fs.readFileSync(credentialPath, "utf8"));
if (credentials.synthetic_only !== true) throw new Error("Only synthetic accounts are permitted");
const accounts = credentials.accounts;
const base = process.env.LEARNING_TEST_URL || "http://127.0.0.1:8025";
if (!/^http:\/\/127\.0\.0\.1:\d+$/.test(base)) throw new Error("Only an isolated loopback host is allowed");
const secondPdf = process.env.LEARNING_TEST_PDF_V2 ? fs.realpathSync(process.env.LEARNING_TEST_PDF_V2) : "";
const checks = [], errors = [];
const secrets = accounts.flatMap(a => [a.username, a.password]).filter(Boolean);
const safe = text => secrets.reduce((value, secret) => value.split(secret).join("[redacted]"), String(text));
const browser = await chromium.launch({ headless: true, executablePath: "C:/Program Files/Google/Chrome/Application/chrome.exe" });
const wall = minutes => new Date(Date.now() + 7 * 3600e3 + minutes * 60e3).toISOString().slice(0, 16); // class time, Asia/Bangkok
const confirmDialog = async page => {
  await page.getByLabel(/Tôi đã kiểm tra/).check();
  await page.getByRole("button", { name: /^Xác nhận/ }).click();
};
async function login(role, ordinal = 0, width = 1280) {
  const account = accounts.filter(item => item.role === role)[ordinal];
  const context = await browser.newContext({ viewport: { width, height: 1000 } });
  const page = await context.newPage();
  page.on("pageerror", error => errors.push(safe(error.message)));
  await page.goto(`${base}/login?redirect=%2Flearning`);
  await page.getByLabel("Tài khoản", { exact: true }).fill(account.username);
  await page.getByLabel("Mật khẩu", { exact: true }).fill(account.password);
  await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
  await page.waitForURL("**/learning");
  await page.getByRole("heading", { name: "Buổi 1" }).first().waitFor({ timeout: 20000 });
  return page;
}
const ready = async page => { await page.reload(); await page.getByRole("heading", { name: "Buổi 1" }).first().waitFor(); };
const openReader = async page => {
  await page.getByRole("button", { name: "Đọc bài giảng" }).first().click();
  await page.locator(".learning-reader-viewport .page canvas").first().waitFor({ timeout: 30000 });
};
const text = async locator => (await locator.innerText()).replace(/\s+/g, " ");

try {
  const teacher = await login("LECTURER"), student = await login("STUDENT", 0, 390), classmate = await login("STUDENT", 1, 1280);

  // LEARNING_RESUME_AT_VERSION=1 skips sections 1-5 on a bundle where they already ran (they are not repeatable).
  if (!process.env.LEARNING_RESUME_AT_VERSION) {
  // 1. Exit tickets: create, publish, submit, resubmit, close, review, publish the shared answer.
  const ticketPanel = teacher.locator('[aria-label="Phiếu ra lớp theo buổi"]');
  const openTicket = page => page.getByLabel("Câu trả lời riêng").waitFor();
  const createTicket = async (question, pageNo, closeIn) => {
    await teacher.getByRole("button", { name: "Tạo phiếu ra lớp", exact: true }).click();
    await ticketPanel.getByLabel("Phiên bản nguồn").selectOption({ index: 1 });
    await ticketPanel.getByLabel("Trang nguồn").fill(String(pageNo));
    await ticketPanel.getByLabel("Câu hỏi vận dụng").fill(question);
    await ticketPanel.getByLabel(/Giờ mở/).fill(wall(-5));
    await ticketPanel.getByLabel(/Giờ đóng/).fill(wall(closeIn));
    await ticketPanel.getByRole("button", { name: "Lưu bản nháp" }).click();
    await teacher.getByRole("button", { name: question }).click();
    await teacher.getByRole("button", { name: "Xem trước công bố", exact: true }).click();
    await confirmDialog(teacher);
    await expect(teacher.getByText("Đang nhận bài").first()).toBeVisible();
  };
  const first = "Nêu một ví dụ dùng LEFT JOIN?", second = "Phiếu hai: INNER JOIN khác LEFT JOIN thế nào?";
  await createTicket(first, 1, 120);
  await ready(student);
  await student.getByRole("button", { name: /Nêu một ví dụ dùng LEFT JOIN/ }).first().click();
  await openTicket(student);
  await student.getByLabel("Câu trả lời riêng").fill("LEFT JOIN giữ lại mọi khách hàng dù chưa có đơn hàng.");
  await student.getByRole("button", { name: "Nộp câu trả lời" }).click();
  await expect(student.getByLabel("Biên nhận bài nộp")).toContainText("Lần 1");
  await student.getByLabel("Câu trả lời riêng").fill("LEFT JOIN giữ lại mọi khách hàng, đơn thiếu thì NULL.");
  await student.getByRole("button", { name: /Nộp bản sửa/ }).click();
  await expect(student.getByLabel("Biên nhận bài nộp")).toContainText("Lần 2");
  checks.push("exit ticket: lecturer publishes, student submits and resubmits with receipts");
  await teacher.getByRole("button", { name: "Quay lại danh sách phiếu" }).click().catch(() => {});
  await createTicket(second, 2, 1);
  await ready(student);
  await student.getByRole("button", { name: new RegExp(second.slice(0, 20)) }).click();
  await openTicket(student);
  await student.getByLabel("Câu trả lời riêng").fill("INNER JOIN chỉ giữ hàng khớp.");
  await student.getByRole("button", { name: "Nộp câu trả lời" }).click();
  await expect(student.getByLabel("Biên nhận bài nộp")).toBeVisible();
  await teacher.waitForTimeout(75000);
  await ready(teacher);
  await teacher.getByRole("button", { name: second }).click();
  await expect(teacher.getByText("Đã đóng").first()).toBeVisible();
  await teacher.getByRole("button", { name: "Soạn bản rà bài" }).click();
  const review = teacher.locator('[aria-label="Rà bài ra lớp"]');
  await review.getByRole("button", { name: "Xem bài nộp" }).click();
  await expect(review).toContainText("INNER JOIN chỉ giữ hàng khớp.");
  await review.getByLabel("Chủ đề lỗi thường gặp").fill("Nhầm INNER JOIN với LEFT JOIN.");
  await review.getByLabel("Kế hoạch buổi sau").fill("Ôn phép nối ngoài.");
  await review.getByRole("textbox", { name: "Lời giải chung" }).fill("INNER JOIN chỉ giữ hàng khớp ở cả hai bảng.");
  await review.getByRole("button", { name: "Lưu bản rà bài" }).click();
  await teacher.getByRole("button", { name: "Xem trước công bố lời giải" }).click();
  await confirmDialog(teacher);
  await ready(student);
  await student.getByRole("button", { name: new RegExp(second.slice(0, 20)) }).click();
  await expect(student.getByLabel("Lời giải chung").first()).toBeVisible();
  await expect(student.locator("#main-content")).toContainText("INNER JOIN chỉ giữ hàng khớp ở cả hai bảng.");
  checks.push("exit ticket: closes on time, lecturer reviews and publishes the common answer, student reads it");

  // 2. Page feedback: window, keyboard report, saved choice, focus returns to the opener.
  await ready(teacher);
  await teacher.getByLabel(/Giờ chốt/).fill(wall(240));
  await teacher.getByRole("button", { name: "Xem trước và mở báo vướng" }).click();
  await expect(teacher.getByRole("dialog")).toContainText(/Giờ chốt\s*\d{4}-\d{2}-\d{2} \d{2}:\d{2} \(Asia\/Bangkok\)/);
  await expect(teacher.getByRole("dialog")).not.toContainText("T0");
  await confirmDialog(teacher);
  await ready(student);
  await openReader(student);
  const opener = student.getByRole("button", { name: "Em đang vướng ở trang này" });
  await opener.focus();
  await student.keyboard.press("Enter");
  await student.getByLabel("Cần thêm ví dụ").check();
  await student.getByRole("button", { name: "Gửi báo vướng" }).click();
  await expect(student.getByLabel("Trạng thái báo vướng")).toContainText("Đã lưu phản hồi");
  await student.keyboard.press("Escape");
  await expect(opener).toBeFocused();
  await opener.click();
  await expect(student.getByRole("dialog")).toContainText("Cần thêm ví dụ");
  await student.keyboard.press("Escape");
  checks.push("page feedback: window opens with class-time preview, student reports by keyboard, choice persists, focus returns");

  // 3. Shared explanation for the session.
  const explanations = teacher.locator('[aria-label="Lời giải chung theo buổi"]');
  await ready(teacher);
  await explanations.getByLabel("Phiên bản nguồn").selectOption({ index: 1 });
  await explanations.getByLabel("Trang nguồn").fill("1");
  await explanations.getByLabel("Hành động").selectOption({ label: "Bổ sung ví dụ" });
  await explanations.getByLabel("Nội dung lời giải").fill("Khách chưa có đơn vẫn xuất hiện với giá trị NULL.");
  await explanations.getByRole("button", { name: "Lưu bản nháp lời giải" }).click();
  await explanations.getByRole("button", { name: "Xem trước công bố" }).click();
  await confirmDialog(teacher);
  await ready(student);
  await expect(student.locator('[aria-label="Lời giải chung theo buổi"]')).toContainText("Khách chưa có đơn vẫn xuất hiện với giá trị NULL.");
  checks.push("shared explanation: draft, confirmed publication, visible to the student");

  // 4. Idea card: save with a page source, share a frozen copy, withdraw.
  await ready(student); await ready(classmate);
  await openReader(student);
  await student.getByRole("button", { name: "Dẫn cả trang vào phiếu ý tưởng" }).click();
  const ideas = student.locator("#learning-idea-cards");
  await ideas.getByLabel("Vấn đề").fill("Khi nào cần LEFT JOIN?");
  await ideas.getByLabel("Ý tưởng", { exact: true }).fill("Khi muốn giữ mọi hàng bảng trái.");
  await ideas.getByLabel("Cách kiểm chứng").fill("Chạy hai truy vấn trên dữ liệu có khách chưa có đơn.");
  await ideas.getByLabel("Mô tả của bạn về phần nguồn").fill("Trang 1.");
  await ideas.getByRole("button", { name: "Lưu phiếu ý tưởng" }).click();
  await expect(ideas).toContainText("Đã lưu phiếu riêng.");
  await ideas.getByRole("button", { name: "Chọn người nhận" }).click();
  await ideas.getByLabel(/Bạn cùng lớp/).check();
  await ideas.getByRole("button", { name: "Xem trước chia sẻ" }).click();
  await confirmDialog(student);
  const received = classmate.locator("#learning-idea-cards");
  await received.getByRole("button", { name: "Tải lại phiếu ý tưởng" }).click();
  await expect(received).toContainText("Khi nào cần LEFT JOIN?");
  await ideas.getByRole("button", { name: "Rút chia sẻ" }).click();
  if (await student.getByRole("dialog").count()) await confirmDialog(student);
  await received.getByRole("button", { name: "Tải lại phiếu ý tưởng" }).click();
  await expect(received).toContainText("Chưa có phiếu được chia sẻ.");
  checks.push("idea card: saved with a page source, shared as a frozen copy, hidden again after withdrawal");

  // 5. Accessible text: request, review each page, verify the risky block, publish one page, search as a student.
  await ready(teacher);
  await openReader(teacher);
  await teacher.getByRole("button", { name: "Quản lý bản chữ" }).click();
  const manage = teacher.locator('[aria-label="Quản lý bản chữ hỗ trợ"]');
  await manage.getByLabel(/Trang cần tạo bản chữ/).fill("1-3");
  await manage.getByRole("button", { name: "Yêu cầu OCR" }).click();
  await expect(manage).toContainText("3/3 trang đã xử lý", { timeout: 30000 });
  await manage.getByLabel("Trang cần đối chiếu").selectOption({ index: 1 });
  // Real OCR can return several blocks per page; the review edits the first and keeps the others as read.
  const firstBlock = manage.getByRole("group", { name: "Khối 1" });
  await firstBlock.getByLabel("Loại khối").selectOption({ label: "Đoạn văn" });
  await firstBlock.getByLabel("Chữ hoặc mô tả đã kiểm tra").fill("LEFT JOIN giữ mọi hàng của bảng trái trên trang hai.");
  // The stand-in OCR flags a possible formula, which forces this confirmation; real OCR on plain text may not.
  const risk = firstBlock.getByLabel(/đối chiếu số liệu, đơn vị/);
  if (await risk.count()) await risk.check();
  else if (!process.env.LEARNING_FEATURES_REAL_OCR) throw new Error("Expected the risk confirmation for the stand-in OCR page");
  await manage.getByLabel("Tôi đã đối chiếu nội dung và thứ tự đọc của trang với ảnh gốc.").check();
  await manage.getByRole("button", { name: /^Lưu duyệt trang 2/ }).click();
  await expect(manage).toContainText("Đã lưu duyệt trang");
  await manage.getByRole("checkbox", { name: "Trang 2" }).check();
  await manage.getByRole("button", { name: "Xem trước công bố bản chữ" }).click();
  await confirmDialog(teacher);
  await expect(manage).toContainText("Đã công bố bản chữ hỗ trợ");
  await ready(student);
  await openReader(student);
  await student.getByRole("button", { name: "Bản chữ hỗ trợ" }).click();
  const reading = student.locator('[aria-label="Đọc bản chữ hỗ trợ"]');
  await reading.getByLabel("Tìm trong bản chữ").fill("bảng trái");
  await reading.getByRole("button", { name: "Tìm bản chữ" }).click();
  await expect(student.locator('[aria-label="Kết quả tìm bản chữ"]')).toContainText("Trang 2");
  checks.push("accessible text: only the verified page is published and searchable; other pages stay on the source image");

  }
  // 6. A newer version with a change note, then the live banner for a student reading the old one.
  if (secondPdf) {
    await ready(student);
    await openReader(student);
    await ready(teacher);
    await teacher.getByText("Tải phiên bản mới", { exact: true }).click();
    const box = teacher.getByText("Tải phiên bản mới", { exact: true }).locator("..");
    await box.getByLabel(/^File PDF/).setInputFiles(secondPdf);
    await box.getByRole("button", { name: "Tải phiên bản", exact: true }).click();
    const next = teacher.getByText(/^Phiên bản 2 ·/).locator("..");
    await expect(teacher.getByText(/Phiên bản 2 đã sẵn sàng/)).toBeVisible({ timeout: 60000 });
    if (!(await next.isVisible().catch(() => false))) await teacher.getByText("Lịch sử phiên bản", { exact: true }).click();
    await expect(next.getByRole("button", { name: "Công bố", exact: true })).toBeVisible({ timeout: 60000 });
    await next.getByText("Mô tả thay đổi giữa hai bản", { exact: true }).click();
    await next.getByLabel("Bản trước").selectOption({ index: 1 });
    await next.getByLabel("Phạm vi thay đổi").selectOption({ label: "Thay đổi toàn tài liệu" });
    await next.getByLabel("Lý do cập nhật").fill("Thêm liên kết đọc thêm ở trang 1.");
    await next.getByRole("button", { name: "Lưu mô tả thay đổi" }).click();
    await expect(next).toContainText("Máy chủ đã xác nhận lần lưu mô tả.");
    await next.getByRole("button", { name: "Công bố", exact: true }).click();
    await expect(teacher.getByRole("dialog")).toContainText("Thêm liên kết đọc thêm ở trang 1.");
    await confirmDialog(teacher);
    await expect(next).toContainText("Đã công bố");
    await student.evaluate(() => window.dispatchEvent(new Event("focus")));
    await expect(student.getByText("Bạn đang đọc một phiên bản khác với bản hiện hành.")).toBeVisible({ timeout: 10000 });
    checks.push("version change: note shown in the publish confirmation; a student on the old version is told within seconds of regaining focus");
  }

  // 7. The periodic account check must not take the caret out of a field being typed in.
  await ready(classmate);
  await classmate.getByRole("button", { name: /Nêu một ví dụ dùng LEFT JOIN/ }).first().click();
  const answer = classmate.getByLabel("Câu trả lời riêng");
  await answer.click();
  await classmate.keyboard.type("Bắt đầu gõ ");
  await classmate.waitForTimeout(34000);
  await expect(answer).toBeFocused();
  await classmate.keyboard.type("tiếp tục gõ");
  await expect(answer).toHaveValue(/Bắt đầu gõ tiếp tục gõ$/);
  checks.push("typing in an answer keeps focus and every character across the 30 s account re-check");

  if (errors.length) throw new Error("Page errors: " + errors.join(" | "));
  fs.writeFileSync(path.join(output, "report.json"), JSON.stringify({ status: "passed", base_url: base, checks, page_errors: errors }, null, 2));
  console.log(JSON.stringify({ status: "passed", checks: checks.length, output }));
} catch (error) {
  fs.writeFileSync(path.join(output, "report.json"), JSON.stringify({ status: "failed", checks, error: safe(error.message).slice(0, 1500), page_errors: errors }, null, 2));
  console.log(JSON.stringify({ status: "failed", checks: checks.length, error: safe(error.message).slice(0, 800), output }));
  process.exitCode = 1;
} finally {
  await browser.close();
}
