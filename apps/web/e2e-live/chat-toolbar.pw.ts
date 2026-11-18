import { test, expect } from "@playwright/test";

for (const width of [1440, 960, 390]) test(`compact chat toolbar: ${width}px, dialogs and source remain accessible`, async ({ page }) => {
  await page.setViewportSize({ width, height: 960 });
  let generations = 0;
  page.on("request", r => { if (r.method() === "POST" && r.url().endsWith("/messages:stream")) generations++; });
  await page.goto("/login?next=/chat");
  await page.getByLabel("Mã tài khoản", { exact: true }).fill("SV001");
  await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
  await expect(page).toHaveURL(/\/chat$/);
  await expect(page.getByLabel("Đặt câu hỏi", { exact: true })).toBeVisible();
  await page.goto("/chat?conversation_id=01a1582d-b1b2-7b88-ab0c-69efb3687115");
  await expect(page.getByRole("article", { name: /^Tin nhắn của trợ lý:/ })).toBeVisible();
  await expect(page.locator(".campus-chat-controls")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Đọc trạng thái công việc", exact: true })).toHaveCount(0);
  const header = page.locator(".campus-chat-log");
  await expect(page.locator(".campus-chat-header, .campus-toolbar")).toHaveCount(0);
  if (width >= 960) {
    const mainMenu = page.getByRole("navigation", { name: "Điều hướng chính", exact: true });
    await expect(mainMenu.getByRole("button", { name: "Cài đặt", exact: true })).toBeVisible();
    for (const name of ["Tiện ích", "Thông tin hội thoại", "Nguồn trích dẫn"]) {
      await expect(mainMenu.getByRole("button", { name, exact: true })).toHaveCount(0);
    }
    await expect(mainMenu.getByRole("link", { name: "Thông báo", exact: true })).toHaveCount(0);
    await expect(mainMenu.getByRole("link", { name: "Quyền riêng tư", exact: true })).toHaveCount(0);
  }
  const composer = page.locator(".campus-composer form");
  expect((await composer.boundingBox())!.height).toBeLessThanOrEqual(66);
  expect(await composer.evaluate(el => getComputedStyle(el).flexDirection)).toBe("row");
  expect(parseFloat(await composer.evaluate(el => getComputedStyle(el).borderRadius))).toBeGreaterThanOrEqual(30);
  const input = page.getByLabel("Đặt câu hỏi", { exact: true });
  await expect(input).toHaveAttribute("placeholder", "Hỏi Campus 24/7");
  await expect(composer.getByRole("button", { name: "Gửi", exact: true })).toBeDisabled();
  await composer.getByRole("button", { name: "Tiện ích học vụ", exact: true }).click();
  const composerTools = page.getByRole("dialog", { name: "Tiện ích học vụ", exact: true });
  await expect(composerTools).toBeVisible();
  await composerTools.getByRole("button", { name: "Đóng", exact: true }).click();
  await expect(composer.getByRole("button", { name: "Tùy chọn trả lời", exact: true })).toHaveCount(0);
  await menuAction("Cài đặt");
  const composerSettings = page.getByRole("dialog", { name: /^Cài đặt và quyền/ });
  await expect(composerSettings).toBeVisible();
  await expect(composerSettings.getByRole("link", { name: "Thông báo", exact: true })).toBeVisible();
  await expect(composerSettings.getByRole("link", { name: "Phòng học", exact: true })).toHaveCount(0);
  await expect(composerSettings.getByRole("button", { name: "Thông tin hội thoại", exact: true })).toHaveCount(0);
  await expect(composerSettings.getByRole("button", { name: /Chuyển sang giao diện/ })).toBeVisible();
  await composerSettings.getByRole("button", { name: "Đóng", exact: true }).click();
  await input.fill("Bản soạn kiểm thử");
  await expect(composer.getByRole("button", { name: "Gửi", exact: true })).toBeEnabled();
  await input.press("Shift+Enter");
  await expect(input).toHaveValue("Bản soạn kiểm thử\n");
  await input.fill("");
  expect((await composer.boundingBox())!.height).toBeLessThanOrEqual(66);
  async function menuAction(name: string) {
    if (["Tiện ích", "Thông tin hội thoại", "Nguồn trích dẫn"].includes(name)) {
      await page.getByRole("button", { name: "Thao tác cuộc trò chuyện", exact: true }).click();
      await page.locator(".campus-conversation-context").getByRole("button", { name: name === "Tiện ích" ? "Tiện ích học vụ" : name, exact: true }).click();
    } else {
      if (width < 960) await page.getByRole("button", { name: "Mở điều hướng", exact: true }).click();
      await page.getByRole("button", { name, exact: true }).click();
    }
  }
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 2)).toBe(true);
  const temporaryNotice = page.locator('[aria-label="Thông báo hội thoại"] [data-compact-notice]').filter({ hasText: "Chat tạm thời" });
  await expect(temporaryNotice).toBeVisible();
  expect((await temporaryNotice.boundingBox())!.height).toBeLessThanOrEqual(36);
  const headerBeforeDismiss = await header.boundingBox();
  const composerBeforeDismiss = await page.getByLabel("Đặt câu hỏi", { exact: true }).boundingBox();
  await temporaryNotice.getByRole("button", { name: "Đóng thông báo: Chat tạm thời", exact: true }).click();
  await expect(temporaryNotice).toHaveCount(0);
  expect(await header.boundingBox()).toEqual(headerBeforeDismiss);
  expect(await page.getByLabel("Đặt câu hỏi", { exact: true }).boundingBox()).toEqual(composerBeforeDismiss);
  await page.screenshot({ path: test.info().outputPath(`chat-${width}.png`), fullPage: true });
  const history = page.getByRole("complementary", { name: "Lịch sử theo tài khoản", exact: true });
  if (width >= 960) {
    await expect(history).toBeVisible();
    await expect(page.getByRole("dialog")).toHaveCount(0);
    expect((await history.boundingBox())!.width).toBe(244);
    const navigation = page.getByRole("complementary", { name: "Thanh bên ứng dụng", exact: true });
    expect((await navigation.boundingBox())!.width).toBe(64);
    await expect(navigation.getByRole("link", { name: /^Đổi tài khoản:/ })).toBeVisible();
    await expect(navigation.getByRole("link", { name: "Phòng học", exact: true })).toBeVisible();
    await expect(navigation.getByRole("button", { name: "Lịch sử", exact: true })).toHaveCount(0);
    await page.getByRole("button", { name: "Mở rộng menu", exact: true }).click();
    const navEdge = page.getByRole("separator", { name: "Đổi độ rộng menu", exact: true });
    const navBounds = (await navEdge.boundingBox())!;
    await page.mouse.move(navBounds.x + 3, navBounds.y + 120);
    await page.mouse.down(); await page.mouse.move(navBounds.x + 63, navBounds.y + 120); await page.mouse.up();
    expect((await navigation.boundingBox())!.width).toBe(284);
    await navEdge.press("ArrowLeft");
    expect((await navigation.boundingBox())!.width).toBe(274);
    await navEdge.dblclick();
    expect((await navigation.boundingBox())!.width).toBe(224);
    await page.getByRole("button", { name: "Thu gọn menu", exact: true }).click();
    expect((await navigation.boundingBox())!.width).toBe(64);
    await expect(navigation.getByRole("button", { name: "Cài đặt", exact: true })).toBeVisible();
    await page.screenshot({ path: test.info().outputPath(`rail-${width}.png`), fullPage: true });
    await page.getByRole("button", { name: "Mở rộng menu", exact: true }).click();
    expect((await navigation.boundingBox())!.width).toBe(224);
    const historyEdge = page.getByRole("separator", { name: "Đổi độ rộng lịch sử", exact: true });
    const historyBounds = (await historyEdge.boundingBox())!;
    await page.mouse.move(historyBounds.x + 3, historyBounds.y + 120);
    await page.mouse.down(); await page.mouse.move(historyBounds.x + 83, historyBounds.y + 120); await page.mouse.up();
    expect((await history.boundingBox())!.width).toBe(324);
    await historyEdge.press("ArrowLeft");
    expect((await history.boundingBox())!.width).toBe(314);
    await historyEdge.dblclick();
    expect((await history.boundingBox())!.width).toBe(244);
    const mainWidth = (await page.locator(".campus-chat-main").boundingBox())!.width;
    await history.getByRole("button", { name: "Đóng lịch sử", exact: true }).click();
    expect((await page.locator(".campus-chat-main").boundingBox())!.width).toBeGreaterThan(mainWidth);
  }
  await page.getByRole("button", { name: "Mở danh sách hội thoại", exact: true }).click();
  await expect(history).toBeVisible();
  expect((await history.boundingBox())!.width).toBeLessThanOrEqual(320);
  if (width >= 960) {
    await expect(page.getByRole("dialog")).toHaveCount(0);
    expect((await page.locator(".campus-chat-main").boundingBox())!.x).toBeGreaterThanOrEqual((await history.boundingBox())!.x + 244);
    await expect(page.getByLabel("Đặt câu hỏi", { exact: true })).toBeEnabled();
  }
  await expect(history.getByRole("button", { name: "Hội thoại mới", exact: true })).toHaveCount(0);
  await expect(history.getByRole("button", { name: "Chat tạm thời mới", exact: true })).not.toBeVisible();
  await expect(history.getByRole("textbox")).toHaveCount(0);
  await expect(history.getByRole("checkbox")).toHaveCount(0);
  const row = history.locator("[data-conversation-row]").first();
  await expect(row).toBeVisible();
  const rowId = await row.getAttribute("data-conversation-row");
  const savedHistory = await page.request.get(`/v1/conversations/${rowId}/messages?limit=50`);
  expect(savedHistory.status()).toBe(200);
  const firstQuestion = (await savedHistory.json()).items.find((item: { sender_type: string }) => item.sender_type === "USER");
  expect(firstQuestion).toBeTruthy();
  const expectedTitle = firstQuestion.content.trim().replace(/\s+/g, " ").slice(0, 120);
  expect(await row.locator("button[title]").first().getAttribute("title")).toContain(expectedTitle);
  expect(await row.locator("button[title]").first().getAttribute("title")).toContain("Tạo lúc");
  await expect(row.locator("button[title]").first()).toHaveText(expectedTitle);
  expect((await row.boundingBox())!.height).toBeLessThanOrEqual(45);
  const title = row.locator("button[title]").first();
  expect(await title.evaluate(el => getComputedStyle(el).whiteSpace)).toBe("nowrap");
  const actions = row.getByRole("button", { name: /^Thao tác hội thoại:/ });
  await actions.click();
  await expect(row.getByRole("button", { name: "Đổi tên", exact: true })).toBeVisible();
  await expect(row.getByRole("button", { name: /^(Bỏ )?ghim$/i })).toBeVisible();
  await expect(row.getByRole("button", { name: "Lưu trữ", exact: true })).toBeVisible();
  await page.screenshot({ path: test.info().outputPath(`history-${width}.png`), fullPage: true });
  await row.getByRole("button", { name: "Đổi tên", exact: true }).click();
  await expect(row.getByRole("textbox", { name: "Tên hội thoại" })).toBeFocused();
  await row.getByRole("button", { name: "Hủy", exact: true }).click();
  await expect(history.getByRole("textbox")).toHaveCount(0);
  await actions.click();
  await row.getByRole("button", { name: "Đổi tên", exact: true }).focus();
  await page.keyboard.press("Escape");
  await expect(history).toBeVisible();
  await expect(row.getByRole("button", { name: "Đổi tên", exact: true })).not.toBeVisible();
  await history.getByRole("button", { name: "Tùy chọn danh sách hội thoại", exact: true }).click();
  const [archived] = await Promise.all([
    page.waitForResponse(r => r.url().includes("/assistant/conversations?") && r.url().includes("archived=true")),
    history.getByRole("button", { name: "Hội thoại đã lưu trữ", exact: true }).click(),
  ]);
  expect(archived.status()).toBe(200);
  await history.getByRole("button", { name: "Tùy chọn danh sách hội thoại", exact: true }).click();
  await history.getByRole("button", { name: "Hội thoại đang mở", exact: true }).click();
  await page.getByRole("button", { name: "Đóng lịch sử", exact: true }).click();
  await menuAction("Cài đặt");
  const settings = page.getByRole("dialog", { name: /^Cài đặt và quyền/ });
  await expect(settings).toBeVisible();
  await settings.getByRole("button", { name: "Đóng", exact: true }).click();
  await menuAction("Tiện ích");
  const tools = page.getByRole("dialog", { name: "Tiện ích học vụ", exact: true });
  await expect(tools).toBeVisible();
  await tools.getByRole("button", { name: "Đóng", exact: true }).click();
  await menuAction("Thông tin hội thoại");
  const details = page.getByRole("dialog", { name: "Thông tin hội thoại", exact: true });
  await expect(details).toContainText("Đã lưu");
  await expect(details).toContainText("Chat tạm thời không đọc/ghi personal memory");
  const [run] = await Promise.all([
    page.waitForResponse(r => /\/agent-runs\/[^/]+$/.test(new URL(r.url()).pathname)),
    details.getByRole("button", { name: "Đọc trạng thái công việc", exact: true }).click(),
  ]);
  // This retained run belongs to an earlier login session. Moving the control
  // must preserve the server's current-session check and surface its denial.
  expect(run.status()).toBe(403);
  await expect(details.getByRole("alert")).toBeVisible();
  await details.getByRole("alert").getByRole("button", { name: /^Đóng thông báo:/ }).click();
  await expect(details.getByRole("alert")).toHaveCount(0);
  await details.getByRole("button", { name: "Đóng thông tin", exact: true }).click();
  const floatingError = page.locator('[aria-label="Thông báo hội thoại"]').getByRole("alert");
  await expect(floatingError).toBeVisible();
  expect((await floatingError.boundingBox())!.height).toBeLessThanOrEqual(36);
  await floatingError.getByRole("button", { name: /^Đóng thông báo:/ }).click();
  await expect(floatingError).toHaveCount(0);
  await menuAction("Nguồn trích dẫn");
  await expect(page.getByRole("dialog", { name: "Nguồn trích dẫn & Bằng chứng", exact: true })).toBeVisible();
  expect(generations).toBe(0);
});
