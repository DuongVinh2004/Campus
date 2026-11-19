import { test, expect, type Page } from "@playwright/test";

async function login(page: Page) {
  await page.goto("/login?next=/chat");
  await page.getByLabel("Mã tài khoản", { exact: true }).fill("SV001");
  await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
  await expect(page).toHaveURL(/\/chat$/);
  await expect(page.getByLabel("Đặt câu hỏi", { exact: true })).toBeVisible();
}

for (const width of [1440, 960, 390]) test(`unified UX: welcome and preserved drafts ${width}px`, async ({ page }) => {
  await page.setViewportSize({ width, height: 900 });
  let modelRequests = 0;
  await page.route("**/messages:stream", async route => { modelRequests++; await route.abort(); });
  await login(page);
  const input = page.getByLabel("Đặt câu hỏi", { exact: true });
  await expect(page.getByRole("heading", { name: "Bạn cần hỗ trợ gì?", exact: true })).toBeVisible();
  await expect(page.locator(".campus-conversation-context")).toContainText("Chat mới");
  expect(await page.locator(".campus-chat-welcome").innerText()).not.toContain("Mọi thông tin đều đối soát");
  expect((await page.locator(".campus-chat-welcome").boundingBox())!.height).toBeLessThan(250);
  for (const chip of await page.locator(".campus-prompt-chip").all()) expect((await chip.boundingBox())!.height).toBeLessThanOrEqual(46);
  const composer = page.locator(".campus-composer > div");
  const body = page.locator(".campus-chat-log > div");
  expect((await composer.boundingBox())!.width).toBeLessThanOrEqual(760);
  expect(Math.abs((await composer.boundingBox())!.x - (await body.boundingBox())!.x)).toBeLessThanOrEqual(2);
  await page.screenshot({ path: test.info().outputPath(`welcome-${width}.png`), fullPage: true });
  await input.fill("Bản soạn vẫn được giữ");
  if (width < 960) await page.getByRole("button", { name: "Mở danh sách hội thoại", exact: true }).click();
  const history = page.getByRole("complementary", { name: "Lịch sử theo tài khoản", exact: true });
  await expect(history.getByRole("heading", { name: "Hôm nay", exact: true })).toBeVisible();
  const title = history.locator("[data-conversation-title]").first();
  const id = await history.locator("[data-conversation-row]").first().getAttribute("data-conversation-row");
  await title.click();
  await expect(page.locator(`[data-conversation-row="${id}"] [aria-current=true]`)).toHaveCount(width < 960 ? 0 : 1);
  await expect(page).toHaveURL(new RegExp(`conversation_id=${id}`));
  if (width < 960) await page.getByRole("button", { name: "Mở danh sách hội thoại", exact: true }).click();
  await history.getByRole("button", { name: "Đoạn chat mới", exact: true }).click();
  await expect(page).toHaveURL(/\/chat$/);
  await expect(input).toHaveValue("");
  await expect(page.locator(".campus-conversation-context")).toContainText("Chat mới");
  await input.fill("Bản soạn vẫn được giữ");
  if (width >= 960) await history.getByRole("button", { name: "Đóng lịch sử", exact: true }).click();
  await expect(input).toHaveValue("Bản soạn vẫn được giữ");
  await page.getByRole("button", { name: "Mở danh sách hội thoại", exact: true }).click();
  if (width < 960) {
    expect((await history.boundingBox())!.width).toBeLessThanOrEqual(300);
    await expect(history.getByRole("button", { name: "Đóng lịch sử", exact: true })).toBeFocused();
  }
  await history.getByRole("button", { name: "Đóng lịch sử", exact: true }).click();
  await expect(input).toHaveValue("Bản soạn vẫn được giữ");
  await input.press("Shift+Enter");
  await expect(input).toHaveValue("Bản soạn vẫn được giữ\n");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
  expect(modelRequests).toBe(0);
});

test("unified UX: Enter sends and Stop cancels a simulated stream without losing the next draft", async ({ page }) => {
  const conversationId = "01a1585e-0001-7000-8000-000000000001";
  await page.route("**/v1/conversations", async route => {
    if (route.request().method() === "POST") await route.fulfill({ json: { id: conversationId, mode: "persistent" } });
    else await route.continue();
  });
  let realModelRequests = 0;
  await page.route("**/messages:stream", async route => { realModelRequests++; await route.abort(); });
  await page.addInitScript(() => {
    const original = window.fetch.bind(window);
    (window as unknown as { simulatedTurns: number }).simulatedTurns = 0;
    window.fetch = async (request, init) => {
      const url = typeof request === "string" ? request : request instanceof URL ? request.href : request.url;
      if (!url.endsWith("/messages:stream")) return original(request, init);
      (window as unknown as { simulatedTurns: number }).simulatedTurns++;
      const id = url.split("/").at(-2)!;
      const body = new ReadableStream<Uint8Array>({ start(controller) {
        const encode = new TextEncoder();
        controller.enqueue(encode.encode(`id: 01a1585e-0002-7000-8000-000000000001\nevent: message.started\ndata: ${JSON.stringify({ conversation_id: id, message_id: "01a1585e-0003-7000-8000-000000000001" })}\n\n`));
        controller.enqueue(encode.encode('id: 01a1585e-0004-7000-8000-000000000001\nevent: message.delta\ndata: {"seq":1,"delta":"Nội dung kiểm thử đang truyền"}\n\n'));
        init?.signal?.addEventListener("abort", () => controller.error(new DOMException("Aborted", "AbortError")), { once: true });
      } });
      return new Response(body, { status: 200, headers: { "Content-Type": "text/event-stream" } });
    };
  });
  await login(page);
  const input = page.getByLabel("Đặt câu hỏi", { exact: true });
  await input.press("Enter");
  expect(await page.evaluate(() => (window as unknown as { simulatedTurns: number }).simulatedTurns)).toBe(0);
  await input.fill("Câu hỏi kiểm thử giao diện"); await input.press("Enter");
  await expect(page.getByRole("button", { name: "Dừng trả lời", exact: true })).toBeVisible();
  await input.fill("Bản soạn tiếp theo");
  await page.getByRole("button", { name: "Dừng trả lời", exact: true }).click();
  await expect(page.getByRole("button", { name: "Dừng trả lời", exact: true })).toHaveCount(0);
  await expect(input).toHaveValue("Bản soạn tiếp theo");
  expect(await page.evaluate(() => (window as unknown as { simulatedTurns: number }).simulatedTurns)).toBe(1);
  expect(realModelRequests).toBe(0);
});

test("unified UX: constrained columns, keyboard focus and metadata preview without commit", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  let commits = 0, modelRequests = 0;
  page.on("request", request => { if (request.method() === "POST" && request.url().endsWith("/conversations:confirm")) commits++; });
  await page.route("**/messages:stream", async route => { modelRequests++; await route.abort(); });
  await login(page);
  const history = page.getByRole("complementary", { name: "Lịch sử theo tài khoản", exact: true });
  const row = history.locator("[data-conversation-row]").first();
  const originalTitle = await row.locator("[data-conversation-title]").textContent();
  await row.getByRole("button", { name: /^Thao tác hội thoại:/ }).click();
  await row.getByRole("button", { name: "Đổi tên", exact: true }).click();
  await row.getByRole("textbox", { name: "Tên hội thoại", exact: true }).fill("Bản xem trước kiểm thử, không lưu");
  const [preview] = await Promise.all([
    page.waitForResponse(response => response.url().endsWith(":preview") && response.request().method() === "POST"),
    row.getByRole("button", { name: "Lưu", exact: true }).click(),
  ]);
  expect(preview.status()).toBe(200);
  await expect(history.getByRole("button", { name: "Xác nhận", exact: true })).toBeDisabled();
  await history.getByRole("checkbox", { name: "Xác nhận metadata trên" }).check();
  await expect(history.getByRole("button", { name: "Xác nhận", exact: true })).toBeEnabled();
  await history.getByRole("button", { name: "Giữ tiêu đề đang soạn", exact: true }).click();
  await expect(row.locator("[data-conversation-title]")).toHaveText(originalTitle!);
  const input = page.getByLabel("Đặt câu hỏi", { exact: true });
  await input.fill("Bản soạn kiểm tra bố cục");
  await page.getByRole("button", { name: "Mở rộng menu", exact: true }).click();
  await page.getByRole("separator", { name: "Đổi độ rộng menu", exact: true }).press("End");
  await page.getByRole("separator", { name: "Đổi độ rộng lịch sử", exact: true }).press("End");
  await page.setViewportSize({ width: 1024, height: 720 });
  await expect.poll(async () => (await page.locator(".campus-chat-main").boundingBox())!.width).toBeGreaterThanOrEqual(320);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
  await expect(input).toHaveValue("Bản soạn kiểm tra bố cục");
  await page.screenshot({ path: test.info().outputPath("expanded-1024.png"), fullPage: true });
  await page.getByRole("button", { name: "Thu gọn menu", exact: true }).click();
  await history.getByRole("button", { name: "Đóng lịch sử", exact: true }).click();
  await page.screenshot({ path: test.info().outputPath("collapsed-1024.png"), fullPage: true });
  await expect(input).toHaveValue("Bản soạn kiểm tra bố cục");
  await input.focus();
  for (let index = 0; index < 14; index++) {
    await page.keyboard.press("Tab");
    expect(await page.evaluate(() => {
      const focused = document.activeElement as HTMLElement | null;
      return focused === document.body || !!focused && focused.getClientRects().length > 0 && !focused.closest("[inert]");
    })).toBe(true);
  }
  expect(commits).toBe(0);
  expect(modelRequests).toBe(0);
});
