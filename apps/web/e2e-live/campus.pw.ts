import { test, expect, type Browser, type Page, type BrowserContext } from "@playwright/test";

const mark = () => `E2E-${Date.now()}`;
// All browser actors share the loopback peer and the real limiter. Pace the
// campaign instead of resetting counters or relaxing production protections.
test.afterEach(async () => { await new Promise(resolve => setTimeout(resolve, 15_000)); });
async function login(browser: Browser, account: string, width = 1440) {
  console.log(`Login UI: ${account}`);
  const context = await browser.newContext({ baseURL: "http://127.0.0.1:3115", viewport: { width, height: 960 } });
  const page = await context.newPage();
  await page.goto("http://127.0.0.1:3115/login");
  await page.getByLabel("Mã tài khoản").fill(account);
  await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
  await page.waitForURL(url => !url.pathname.endsWith("/login"));
  console.log(`Login completed: ${account}`);
  return { context, page };
}
async function state(page: Page, path: string) {
  console.log(`Readback: ${path}`);
  const response = await page.request.get(path);
  expect(response.status()).toBe(200);
  return response.json();
}
async function action(page: Page, label: string, suffix: string) {
  console.log(`UI action: ${label} -> ${suffix}`);
  const button = page.getByRole("button", { name: label, exact: true });
  if (!await button.isVisible() && ["Tiếp nhận", "Yêu cầu bổ sung", "Duyệt và cấp giấy xác nhận", "Trả lời", "Trả kết quả demo"].includes(label)) {
    await page.getByRole("button", { name: "Xử lý hồ sơ", exact: true }).click();
  }
  const [response] = await Promise.all([
    page.waitForResponse(r => r.url().split("?")[0].endsWith(suffix) && r.request().method() === "POST", { timeout: 20_000 }),
    page.getByRole("button", { name: label, exact: true }).click(),
  ]);
  expect(response.status()).toBeLessThan(300);
  const result = await response.json();
  await expect(page.getByText("Đang tải hoặc xử lý…", { exact: true })).toHaveCount(0);
  await expect(page.getByText("Đang xử lý…", { exact: true })).toHaveCount(0);
  return result;
}
async function staffNote(page: Page, label: string, text: string) {
  if (!await page.getByLabel(label, { exact: true }).isVisible()) {
    await page.getByRole("button", { name: "Xử lý hồ sơ", exact: true }).click();
  }
  await page.getByLabel(label, { exact: true }).fill(text);
}
async function certificate(page: Page, name: string) {
  await page.goto("http://127.0.0.1:3115/tickets?new=1");
  await page.getByLabel("Mục đích xin giấy xác nhận", { exact: true }).fill(name);
  await page.getByLabel("Nơi nộp giấy xác nhận", { exact: true }).fill("Đơn vị kiểm thử tổng hợp");
  const draft = await action(page, "Lưu bản nháp", "/v1/document-requests/drafts");
  expect((await state(page, `/v1/document-requests/${draft.id}`)).status).toBe("DRAFT");
  await action(page, "Xem trước hồ sơ", `/${draft.id}/preview`);
  expect((await state(page, `/v1/document-requests/${draft.id}`)).status).toBe("PENDING_CONFIRMATION");
  await expect(page.getByRole("heading", { name: "Xem trước — chưa gửi" })).toBeVisible();
  await action(page, "Xác nhận gửi hồ sơ", `/${draft.id}/confirm`);
  await expect(page.getByText(`Đã gửi hồ sơ ${draft.id}`, { exact: true })).toBeVisible();
  expect((await state(page, `/v1/document-requests/${draft.id}`)).status).toBe("SUBMITTED");
  return draft.id as string;
}

test("certificate: draft, preview, confirm, staff supplement, student reply, issue and download", async ({ browser }) => {
  const student = await login(browser, "SV001");
  const id = await certificate(student.page, mark());
  await student.page.reload();
  await expect(student.page.getByText(id, { exact: false }).first()).toBeVisible();
  const officer = await login(browser, "OF001");
  await officer.page.goto(`http://127.0.0.1:3115/staff?request=${id}`);
  await action(officer.page, "Tiếp nhận", `/${id}/accept`);
  await staffNote(officer.page, "Lý do / yêu cầu bổ sung", "MÔ PHỎNG: cần bổ sung mục đích sử dụng");
  await action(officer.page, "Yêu cầu bổ sung", `/${id}/request_supplement`);
  await student.page.reload();
  await student.page.getByLabel("Nội dung bổ sung", { exact: true }).fill("MÔ PHỎNG: đã đối chiếu và bổ sung thông tin kiểm thử");
  await action(student.page, "Xác nhận gửi bổ sung", `/${id}/supplement`);
  expect((await state(student.page, `/v1/document-requests/${id}`)).status).toBe("SUBMITTED");
  await officer.page.reload();
  await action(officer.page, "Tiếp nhận", `/${id}/accept`);
  await staffNote(officer.page, "Lý do / yêu cầu bổ sung", "MÔ PHỎNG: đã kiểm tra hồ sơ tổng hợp, chấp thuận cấp bản demo");
  await action(officer.page, "Duyệt và cấp giấy xác nhận", `/${id}/approve`);
  await student.page.reload();
  expect((await state(student.page, `/v1/document-requests/${id}`)).status).toBe("READY");
  await student.page.getByRole("button", { name: "Xem kết quả", exact: true }).click();
  await expect(student.page.locator("iframe")).toBeVisible();
  const other = await login(browser, "SV024");
  expect((await other.page.request.get(`/v1/document-requests/${id}`)).status()).toBe(404);
  await Promise.all([student.context.close(), officer.context.close(), other.context.close()]);
});

for (const kind of ["GENERAL_SUPPORT", "GRADE_APPEAL"] as const) {
  test(`${kind}: student submits, correct queue claims, responds, resolves and student downloads`, async ({ browser }) => {
    const student = await login(browser, "SV024");
    await student.page.goto(`http://127.0.0.1:3115/services?kind=${kind}`);
    await student.page.getByLabel("Lý do", { exact: true }).fill(`${mark()} — hồ sơ nghiệp vụ tổng hợp, không gửi tới trường`);
    if (kind === "GRADE_APPEAL") {
      const values = await student.page.getByLabel("Học phần mô phỏng", { exact: true }).locator("option:not([disabled])").evaluateAll(nodes => nodes.map(node => (node as HTMLOptionElement).value).filter(Boolean));
      expect(values.length).toBeGreaterThan(0);
      await student.page.getByLabel("Học phần mô phỏng", { exact: true }).selectOption(values[0]);
    }
    const draft = await action(student.page, "Lưu bản nháp", "/v1/service-requests/drafts");
    await action(student.page, "Xem trước hồ sơ", `/${draft.id}/preview`);
    await action(student.page, "Xác nhận gửi", `/${draft.id}/confirm`);
    await expect(student.page.getByText(`Đã ghi hồ sơ ${draft.id}`, { exact: false }).first()).toBeVisible();
    const id = draft.id;
    const submitted = await state(student.page, `/v1/service-requests/${id}`);
    expect(submitted.status).toBe("SUBMITTED");
    const officer = await login(browser, kind === "GRADE_APPEAL" ? "OF002" : "OF001");
    await officer.page.goto(`http://127.0.0.1:3115/services?request=${id}`);
    await staffNote(officer.page, "Lý do / phản hồi cán bộ", "MÔ PHỎNG: tiếp nhận đúng queue được phân quyền");
    await action(officer.page, "Tiếp nhận", `/${id}/claim`);
    await staffNote(officer.page, "Lý do / phản hồi cán bộ", "MÔ PHỎNG: cán bộ phản hồi dữ liệu tổng hợp");
    await action(officer.page, "Trả lời", `/${id}/respond`);
    await staffNote(officer.page, "Lý do / phản hồi cán bộ", "MÔ PHỎNG: hoàn tất kiểm tra, trả kết quả demo");
    await action(officer.page, "Trả kết quả demo", `/${id}/resolve`);
    await student.page.reload();
    expect((await state(student.page, `/v1/service-requests/${id}`)).status).toBe("READY");
    await student.page.getByRole("button", { name: "Mở kết quả", exact: true }).click();
    await expect(student.page.locator("iframe")).toBeVisible();
    const wrongQueue = await login(browser, kind === "GRADE_APPEAL" ? "OF001" : "OF002");
    expect([403, 404]).toContain((await wrongQueue.page.request.get(`/v1/staff/service-requests/${id}`)).status());
    await Promise.all([student.context.close(), officer.context.close(), wrongQueue.context.close()]);
  });
}

test("authentication: unauthenticated API denied and invalid login stays on login", async ({ page }) => {
  expect((await page.request.get("/v1/assistant/consumer-capabilities")).status()).toBe(401);
  await page.goto("/login");
  await page.getByLabel("Mã tài khoản").fill("NO_SUCH_E2E_ACCOUNT");
  const [denied] = await Promise.all([
    page.waitForResponse(r => r.url().includes("/v1/auth/") && r.request().method() === "POST"),
    page.getByRole("button", { name: "Đăng nhập", exact: true }).click(),
  ]);
  expect(denied.status()).toBe(401);
  await expect(page.getByRole("alert").filter({ hasText: "Phiên đăng nhập đã hết hạn hoặc chưa hợp lệ" })).toBeVisible();
  await expect(page).toHaveURL(/\/login$/);
});

test("desktop/mobile: student surfaces use real same-origin APIs without JS errors", async ({ browser }) => {
  test.setTimeout(180_000);
  for (const width of [1440, 390]) {
    const session = await login(browser, "SV001", width);
    const errors: string[] = [];
    const origins = new Set<string>();
    session.page.on("pageerror", error => errors.push(error.message));
    session.page.on("request", request => { const url = new URL(request.url()); if (url.pathname.startsWith("/v1/")) origins.add(url.origin); });
    for (const route of ["/", "/chat", "/services", "/tickets", "/privacy", "/memory", "/notifications"]) {
      await session.page.goto(`http://127.0.0.1:3115${route}`, { waitUntil: "networkidle" });
      await expect(session.page.locator("main").first()).toBeVisible();
      await expect(session.page.getByText("Không thể kết nối đến máy chủ.", { exact: true })).toHaveCount(0);
      expect(await session.page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 2)).toBe(true);
    }
    expect([...origins]).toEqual(["http://127.0.0.1:3115"]);
    expect(errors).toEqual([]);
    await session.context.close();
  }
});

test("student role cannot read staff queue or knowledge administration", async ({ browser }) => {
  const session = await login(browser, "SV001");
  expect((await session.page.request.get("/v1/staff/service-requests")).status()).toBe(403);
  expect((await session.page.request.get("/v1/knowledge-operations")).status()).toBe(403);
  await session.context.close();
});

test("settings and personal memory: preview, explicit confirmation, reload and non-destructive forgetting", async ({ browser }) => {
  test.setTimeout(120_000);
  const session = await login(browser, "SV024");
  const page = session.page;
  await page.goto("http://127.0.0.1:3115/privacy");
  const before = await state(page, "/v1/assistant/preferences");
  const name = mark();
  await page.getByLabel("Tên hiển thị", { exact: true }).fill(name);
  await action(page, "Xem trước settings", "/v1/assistant/preferences:preview");
  expect((await state(page, "/v1/assistant/preferences")).version).toBe(before.version);
  await expect(page.getByRole("button", { name: "Xác nhận và đọc lại", exact: true })).toBeDisabled();
  await page.getByLabel("Tôi xác nhận đúng nội dung và phạm vi trên", { exact: true }).check();
  await action(page, "Xác nhận và đọc lại", "/v1/assistant/preferences:confirm");
  await expect(page.getByRole("region", { name: "Xem trước thay đổi", exact: true })).toHaveCount(0);
  await page.reload();
  await expect(page.getByLabel("Tên hiển thị", { exact: true })).toHaveValue(name);
  const consent = page.getByText(/^Cá nhân hóa cách trả lời ·/).locator("..");
  if ((await consent.innerText()).includes("Chưa có consent hiện hành")) {
    await consent.getByRole("button", { name: "Xem trước cho phép", exact: true }).click();
    await page.getByLabel("Tôi xác nhận đúng nội dung và phạm vi trên", { exact: true }).check();
    await action(page, "Xác nhận và đọc lại", "/v1/assistant/preferences:confirm");
  }
  await page.goto("http://127.0.0.1:3115/memory");
  await expect(page.getByRole("button", { name: /^Xem trước (bật|tắt) memory$/ })).toBeVisible();
  if (await page.getByRole("button", { name: "Xem trước bật memory", exact: true }).isVisible()) {
    await page.getByRole("button", { name: "Xem trước bật memory", exact: true }).click();
    await page.getByLabel("Tôi xác nhận nội dung, thời hạn và phạm vi trên", { exact: true }).check();
    await page.getByRole("button", { name: "Xác nhận và đọc lại", exact: true }).click();
    await expect(page.getByRole("button", { name: "Xem trước tắt memory", exact: true })).toBeVisible();
  }
  const topic = `e2e-${Date.now()}`;
  await page.getByLabel("Topic", { exact: true }).fill(topic);
  await page.getByLabel("Nội dung", { exact: true }).fill("Tôi muốn câu trả lời có các bước ngắn gọn.");
  await page.getByRole("button", { name: "Xem trước lưu", exact: true }).click();
  await page.getByLabel("Tôi xác nhận nội dung, thời hạn và phạm vi trên", { exact: true }).check();
  await page.getByRole("button", { name: "Xác nhận và đọc lại", exact: true }).click();
  const item = page.locator("article").filter({ hasText: topic });
  await expect(item).toContainText("Tôi muốn câu trả lời có các bước ngắn gọn.");
  await page.reload();
  await expect(page.locator("article").filter({ hasText: topic })).toBeVisible();
  await page.locator("article").filter({ hasText: topic }).getByRole("button", { name: "Xem trước quên", exact: true }).click();
  await page.getByLabel("Tôi xác nhận nội dung, thời hạn và phạm vi trên", { exact: true }).check();
  await page.getByRole("button", { name: "Xác nhận và đọc lại", exact: true }).click();
  await expect(page.getByText(/Topic đã quên — ngăn tái tạo/)).toBeVisible();
  await session.context.close();
});

test("knowledge: immutable source, separate reviewer, build, publication preview and confirm", async ({ browser }) => {
  test.setTimeout(120_000);
  const author = await login(browser, "KA001");
  await author.page.goto("http://127.0.0.1:3115/knowledge/sources");
  const title = mark();
  await author.page.getByLabel("Tên nguồn", { exact: true }).fill(title);
  await author.page.getByLabel("Tên tệp .txt", { exact: true }).fill("e2e-source.txt");
  await author.page.getByLabel("Locator / xuất xứ", { exact: true }).fill("Local synthetic E2E, no institutional publication");
  await author.page.getByLabel("Original UTF-8 (tối đa 16 KB)", { exact: true }).fill("MÔ PHỎNG E2E: nguồn tổng hợp hỗ trợ thủ tục, không thay thế quy định nhà trường.");
  await action(author.page, "Giữ snapshot mới", "/v1/knowledge-operations/sources");
  await author.page.getByRole("combobox", { name: "Nghiệp vụ", exact: true }).selectOption("GENERAL_SUPPORT");
  const version = await action(author.page, "Tạo version mới", "/v1/knowledge-operations/versions");
  await expect(author.page.getByRole("button", { name: "Review đồng ý", exact: true })).toHaveCount(0);
  const reviewer = await login(browser, "KA002");
  await reviewer.page.goto("http://127.0.0.1:3115/knowledge/sources");
  await reviewer.page.getByRole("button").filter({ hasText: version.id.slice(-8) }).click();
  await reviewer.page.getByLabel("Ghi chú đối chiếu nguồn", { exact: true }).fill("MÔ PHỎNG E2E: admin khác đối chiếu original snapshot và rendition tổng hợp.");
  await action(reviewer.page, "Review đồng ý", `/${version.id}/review`);
  await action(reviewer.page, "Build candidate local", `/${version.id}/build`);
  await action(reviewer.page, "Xem trước xuất bản", `/${version.id}/publish/preview`);
  const previewState = await state(reviewer.page, "/v1/knowledge-operations");
  expect(previewState.versions.find((value: any) => value.id === version.id).state).toBe("BUILT");
  await action(reviewer.page, "Xác nhận xuất bản", `/${version.id}/confirm`);
  const published = await state(reviewer.page, "/v1/knowledge-operations");
  expect(published.versions.find((value: any) => value.id === version.id).state).toBe("PUBLISHED");
  await Promise.all([author.context.close(), reviewer.context.close()]);
});

test("assistant preparation: review required, durable draft only and explicit submission", async ({ browser }) => {
  const session = await login(browser, "SV024");
  const page = session.page;
  await page.goto("/chat");
  await page.getByRole("button", { name: "Tiện ích", exact: true }).click();
  const tools = page.getByRole("dialog", { name: "Tiện ích học vụ", exact: true });
  await tools.getByText("Chuẩn bị thủ tục sinh viên", { exact: true }).click();
  await tools.getByLabel("Kết quả mong muốn", { exact: true }).fill("MÔ PHỎNG E2E: chuẩn bị giấy xác nhận để đối chiếu quy trình");
  await tools.getByRole("combobox", { name: "Thủ tục", exact: true }).selectOption("STUDENT_CERTIFICATE");
  await tools.getByLabel("Mục đích", { exact: true }).fill(mark());
  await tools.getByLabel("Đơn vị nhận", { exact: true }).fill("Đơn vị kiểm thử tổng hợp");
  await tools.getByRole("button", { name: "Chuẩn bị đề xuất", exact: true }).click();
  await expect(tools.getByRole("button", { name: "Lưu nháp đã xem", exact: true })).toBeDisabled();
  await tools.getByLabel("Tôi đã xem các thay đổi nháp trên", { exact: true }).check();
  await tools.getByRole("button", { name: "Lưu nháp đã xem", exact: true }).click();
  const openDraft = tools.getByRole("link", { name: "Mở nháp để xem trước và xác nhận gửi", exact: true });
  await expect(openDraft).toBeVisible();
  const id = new URL(await openDraft.getAttribute("href") || "", "http://127.0.0.1:3115").searchParams.get("request");
  expect((await state(page, `/v1/document-requests/${id}`)).status).toBe("DRAFT");
  await openDraft.click();
  await action(page, "Xem trước hồ sơ", `/${id}/preview`);
  expect((await state(page, `/v1/document-requests/${id}`)).status).toBe("PENDING_CONFIRMATION");
  await action(page, "Xác nhận gửi hồ sơ", `/${id}/confirm`);
  await expect(page.getByText(`Đã gửi hồ sơ ${id}`, { exact: true })).toBeVisible();
  expect((await state(page, `/v1/document-requests/${id}`)).status).toBe("SUBMITTED");
  await session.context.close();
});

test("capability gaps: calendar and room actions remain unavailable on the new UI", async ({ browser }) => {
  const session = await login(browser, "SV001");
  for (const [route, message] of [["/schedule", "Chưa có nguồn lịch học cá nhân được kết nối"], ["/rooms", "Chưa có kết nối đặt phòng"]]) {
    await session.page.goto(route);
    await expect(session.page.getByText(message, { exact: false }).first()).toBeVisible();
  }
  await session.context.close();
});

test("@model real RAG: temporary chat, grounded answer, original citation reader and run checkpoint", async ({ browser }) => {
  test.setTimeout(180_000);
  const session = await login(browser, "SV001");
  const entry = await state(session.page, "/health/entry");
  expect(entry.generation).toBe("retained_live");
  await session.page.goto("http://127.0.0.1:3115/chat");
  const historyDialog = session.page.getByRole("complementary", { name: "Lịch sử theo tài khoản", exact: true });
  if (!await historyDialog.isVisible()) await session.page.getByRole("button", { name: "Mở danh sách hội thoại", exact: true }).click();
  await historyDialog.getByRole("button", { name: "Tùy chọn danh sách hội thoại", exact: true }).click();
  await historyDialog.getByRole("button", { name: "Chat tạm thời mới", exact: true }).click();
  await session.page.getByRole("button", { name: "Thao tác cuộc trò chuyện", exact: true }).click();
  await session.page.getByRole("button", { name: "Thông tin hội thoại", exact: true }).click();
  await session.page.getByText("Về chat tạm thời", { exact: true }).click();
  await expect(session.page.getByText(/^Chat tạm thời không đọc\/ghi personal memory\./)).toBeVisible();
  await session.page.getByRole("button", { name: "Đóng thông tin", exact: true }).click();
  const question = "Theo Sổ tay sinh viên HUCE 2026–2027, những điều kiện cơ bản để xét tốt nghiệp là gì? Trích dẫn nguồn.";
  await session.page.getByLabel("Đặt câu hỏi", { exact: true }).fill(question);
  const [stream] = await Promise.all([
    session.page.waitForResponse(r => r.url().endsWith("/messages:stream")),
    session.page.getByRole("button", { name: "Gửi", exact: true }).click(),
  ]);
  expect(stream.status()).toBe(200);
  await expect(session.page.getByLabel("Đặt câu hỏi", { exact: true })).toHaveValue("", { timeout: 100_000 });
  await session.page.getByRole("button", { name: "Thao tác cuộc trò chuyện", exact: true }).click();
  await session.page.getByRole("button", { name: "Thông tin hội thoại", exact: true }).click();
  await expect(session.page.getByRole("button", { name: "Đọc trạng thái công việc", exact: true })).toBeVisible();
  const [checkpoint] = await Promise.all([
    session.page.waitForResponse(r => /\/agent-runs\/[^/]+$/.test(new URL(r.url()).pathname)),
    session.page.getByRole("button", { name: "Đọc trạng thái công việc", exact: true }).click(),
  ]);
  expect(checkpoint.status()).toBe(200);
  const run = await checkpoint.json();
  expect(["completed", "partial"]).toContain(run.status);
  await session.page.getByRole("button", { name: "Đóng thông tin", exact: true }).click();
  await session.page.getByRole("button", { name: /nguồn/i }).last().click();
  await expect(session.page.getByRole("dialog")).toBeVisible();
  const [original] = await Promise.all([
    session.page.waitForResponse(r => /\/citations\/[^/]+\/source$/.test(new URL(r.url()).pathname)),
    session.page.getByRole("button", { name: "Mở đoạn nguồn gốc", exact: true }).first().click(),
  ]);
  expect(original.status()).toBe(200);
  await expect(session.page.getByTestId("original-source-text")).toBeVisible();
  await expect(session.page.getByText("Không thể kết nối đến máy chủ.", { exact: true })).toHaveCount(0);
  const conversation = new URL(stream.url()).pathname.split("/")[3];
  const history = await state(session.page, `/v1/conversations/${conversation}/messages`);
  const final = history.items.find((item: any) => item.sender_type === "ASSISTANT" || item.role === "assistant");
  expect(final).toBeTruthy();
  expect(["grounded_answer", "partial_answer"]).toContain(final.final_result.response_class);
  expect(final.final_result.citations.length).toBeGreaterThan(0);
  console.log(`Verified persisted answer: ${conversation}; ${final.final_result.response_class}; ${final.final_result.citations.length} citations`);
  await session.context.close();
});

if (process.env.CAMPUS_READBACK_CONVERSATION) test("restart readback: saved real answer and original citation survive reload without generation", async ({ browser }) => {
  const id = process.env.CAMPUS_READBACK_CONVERSATION!;
  const session = await login(browser, "SV001");
  const page = session.page;
  let dispatches = 0;
  page.on("request", request => { if (request.method() === "POST" && request.url().endsWith("/messages:stream")) dispatches++; });
  const stored = await state(page, `/v1/conversations/${id}/messages`);
  const final = stored.items.find((item: any) => item.sender_type === "ASSISTANT").final_result;
  expect(final.response_class).toBe("grounded_answer");
  await page.goto(`/chat?conversation_id=${id}`);
  const answer = page.getByRole("article", { name: /^Tin nhắn của trợ lý:/ });
  await expect(answer).toBeVisible();
  const text = await answer.innerText();
  await page.reload();
  await expect(answer).toHaveText(text, { useInnerText: true });
  await page.getByRole("button", { name: /nguồn/i }).last().click();
  const [original] = await Promise.all([
    page.waitForResponse(r => /\/citations\/[^/]+\/source$/.test(new URL(r.url()).pathname)),
    page.getByRole("button", { name: "Mở đoạn nguồn gốc", exact: true }).first().click(),
  ]);
  expect(original.status()).toBe(200);
  await expect(page.getByTestId("original-source-text")).toBeVisible();
  expect(dispatches).toBe(0);
  expect((await state(page, `/v1/conversations/${id}/messages`)).items).toEqual(stored.items);
  await page.screenshot({ path: test.info().outputPath("retained-real-rag.png"), fullPage: true });
  await session.context.close();
});
