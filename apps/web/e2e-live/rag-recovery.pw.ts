import { test, expect, type Page } from "@playwright/test";

const expired = Buffer.from(JSON.stringify({ exp: 1 })).toString("base64url") + ".expired-test-fixture";
async function login(page: Page) {
  await page.goto("/login?next=/chat");
  await page.getByLabel("Mã tài khoản", { exact: true }).fill("SV001");
  await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
  await expect(page).toHaveURL(/\/chat$/);
  await expect(page.getByLabel("Đặt câu hỏi", { exact: true })).toBeVisible();
}
async function expireLocal(page: Page) {
  await page.evaluate(value => localStorage.setItem("campus247_token", value), expired);
}
async function expireBoth(page: Page) {
  await expireLocal(page);
  await page.context().addCookies([{ name: "auth_token", value: expired, url: "http://127.0.0.1:3115", httpOnly: true, sameSite: "Lax" }]);
}
async function recover(page: Page) {
  await page.goto("/chat");
  const recovery = page.getByRole("region", { name: "Kết nối trợ lý", exact: true });
  await expect(recovery.getByRole("link", { name: "Đăng nhập lại", exact: true })).toBeVisible();
  await expect(page.getByText("Session renewal unavailable", { exact: true })).toHaveCount(0);
  await recovery.getByRole("link", { name: "Đăng nhập lại", exact: true }).click();
  await page.getByLabel("Mã tài khoản", { exact: true }).fill("SV001");
  await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
  await expect(page).toHaveURL(/\/chat$/);
  await expect(page.getByLabel("Đặt câu hỏi", { exact: true })).toBeVisible();
}

test("RAG recovery: unauthenticated chat has a working login return path", async ({ page }) => {
  await recover(page);
});

test("RAG recovery: stale browser token recovers using the valid signed cookie", async ({ page }) => {
  await login(page);
  const previous = await (await page.request.get("/v1/users/me")).json();
  await expireLocal(page);
  const [session] = await Promise.all([
    page.waitForResponse(r => r.url().endsWith("/v1/auth/demo-session")),
    page.goto("/chat"),
  ]);
  expect(session.status()).toBe(200);
  await expect(page.getByLabel("Đặt câu hỏi", { exact: true })).toBeVisible();
  expect((await (await page.request.get("/v1/users/me")).json()).user_id).toBe(previous.user_id);
  expect(await page.evaluate(value => localStorage.getItem("campus247_token") !== value, expired)).toBe(true);
});

test("RAG recovery: expired cookie cannot authorize; explicit login restores chat", async ({ page }) => {
  await login(page);
  await expireBoth(page);
  let automaticLogins = 0;
  page.on("request", r => { if (r.method() === "POST" && r.url().endsWith("/v1/auth/demo-login")) automaticLogins++; });
  await page.goto("/chat");
  await expect(page.getByRole("link", { name: "Đăng nhập lại", exact: true })).toBeVisible();
  expect((await page.request.get("/v1/users/me")).status()).toBe(401);
  expect(automaticLogins).toBe(0);
  await recover(page);
});

test("RAG recovery: transient session failure retries without switching account", async ({ page }) => {
  await login(page);
  const previous = await (await page.request.get("/v1/users/me")).json();
  await expireLocal(page);
  await page.route("**/v1/auth/demo-session", route => route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "Synthetic session outage" }) }));
  await page.goto("/chat");
  await expect(page.getByRole("alert").filter({ hasText: "Chưa thể kiểm tra phiên đăng nhập" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Đăng nhập lại", exact: true })).toHaveCount(0);
  await page.unroute("**/v1/auth/demo-session");
  await page.getByRole("button", { name: "Thử kết nối lại", exact: true }).click();
  await expect(page.getByLabel("Đặt câu hỏi", { exact: true })).toBeVisible();
  expect((await (await page.request.get("/v1/users/me")).json()).user_id).toBe(previous.user_id);
});

test("@model RAG recovery: expired session to real grounded answer with original source", async ({ page }) => {
  test.setTimeout(180_000);
  await login(page);
  await expireBoth(page);
  await recover(page);
  const entry = await (await page.request.get("/health/entry")).json();
  expect(entry.generation).toBe("retained_live");
  expect(entry.test_ceiling_reached).toBe(false);
  const history = page.getByRole("complementary", { name: "Lịch sử theo tài khoản", exact: true });
  if (!await history.isVisible()) await page.getByRole("button", { name: "Mở danh sách hội thoại", exact: true }).click();
  await history.getByRole("button", { name: "Tùy chọn danh sách hội thoại", exact: true }).click();
  await history.getByRole("button", { name: "Chat tạm thời mới", exact: true }).click();
  await page.getByRole("button", { name: "Thao tác cuộc trò chuyện", exact: true }).click();
  await page.getByRole("button", { name: "Thông tin hội thoại", exact: true }).click();
  await page.getByText("Về chat tạm thời", { exact: true }).click();
  await expect(page.getByText(/^Chat tạm thời không đọc\/ghi personal memory\./)).toBeVisible();
  await page.getByRole("button", { name: "Đóng thông tin", exact: true }).click();
  const question = "Theo Sổ tay sinh viên HUCE 2026–2027, những điều kiện cơ bản để xét tốt nghiệp là gì? Trích dẫn nguồn.";
  await page.getByLabel("Đặt câu hỏi", { exact: true }).fill(question);
  const [stream] = await Promise.all([
    page.waitForResponse(r => r.url().endsWith("/messages:stream")),
    page.getByRole("button", { name: "Gửi", exact: true }).click(),
  ]);
  expect(stream.status()).toBe(200);
  await expect(page.getByLabel("Đặt câu hỏi", { exact: true })).toHaveValue("", { timeout: 100_000 });
  const id = new URL(stream.url()).pathname.split("/")[3];
  const saved = await (await page.request.get(`/v1/conversations/${id}/messages`)).json();
  const final = saved.items.find((value: any) => value.sender_type === "ASSISTANT").final_result;
  expect(final.response_class).toBe("grounded_answer");
  expect(final.citations.length).toBeGreaterThan(0);
  await page.screenshot({ path: test.info().outputPath("real-rag-answer.png"), fullPage: true });
  await page.getByRole("button", { name: "Thao tác cuộc trò chuyện", exact: true }).click();
  await page.getByRole("button", { name: "Thông tin hội thoại", exact: true }).click();
  const [checkpoint] = await Promise.all([
    page.waitForResponse(r => /\/agent-runs\/[^/]+$/.test(new URL(r.url()).pathname)),
    page.getByRole("button", { name: "Đọc trạng thái công việc", exact: true }).click(),
  ]);
  expect(checkpoint.status()).toBe(200);
  const run = await checkpoint.json();
  expect(run.status).toBe("completed");
  expect(run.usage.model_calls).toBeLessThanOrEqual(12);
  await page.getByRole("button", { name: "Đóng thông tin", exact: true }).click();
  await page.getByRole("button", { name: /nguồn/i }).last().click();
  const [original] = await Promise.all([
    page.waitForResponse(r => /\/citations\/[^/]+\/source$/.test(new URL(r.url()).pathname)),
    page.getByRole("button", { name: "Mở đoạn nguồn gốc", exact: true }).first().click(),
  ]);
  expect(original.status()).toBe(200);
  await expect(page.getByTestId("original-source-text")).toBeVisible();
  console.log(`Verified real RAG after session recovery: ${id}; ${run.usage.model_calls} model operations; ${final.citations.length} original citations`);
});
