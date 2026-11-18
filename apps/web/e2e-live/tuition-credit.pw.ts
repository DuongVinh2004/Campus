import { test, expect } from "@playwright/test";
import { writeFile } from "node:fs/promises";

test("@model tuition-credit: original three questions answer from real public sources", async ({ page }) => {
  test.setTimeout(480_000);
  await page.goto("/login?next=/chat");
  await page.getByLabel("Mã tài khoản", { exact: true }).fill("SV001");
  await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
  await expect(page).toHaveURL(/\/chat$/);
  await expect(page.getByLabel("Đặt câu hỏi", { exact: true })).toBeVisible();
  const history = page.getByRole("complementary", { name: "Lịch sử theo tài khoản", exact: true });
  if (!await history.isVisible()) await page.getByRole("button", { name: "Mở danh sách hội thoại", exact: true }).click();
  await history.getByRole("button", { name: "Tùy chọn danh sách hội thoại", exact: true }).click();
  await history.getByRole("button", { name: "Chat tạm thời mới", exact: true }).click();
  const cases = [
    { kind: "fees", q: "học phí đang là bao nhiêu", expected: /592[., ]?500|547[., ]?000|580[., ]?500/ },
    { kind: "fees", q: "một tín chỉ bao nhiêu tiền", expected: /592[., ]?500|547[., ]?000|580[., ]?500/ },
    { kind: "credits", q: "học kỹ sư cần bao nhiêu tín", expected: /180/ },
  ].filter(item => !process.env.CAMPUS_RAG_TEST_CASE || item.kind === process.env.CAMPUS_RAG_TEST_CASE);
  expect(cases.length).toBeGreaterThan(0);
  const evidence: unknown[] = [];
  for (const [index, item] of cases.entries()) {
    await page.getByLabel("Đặt câu hỏi", { exact: true }).fill(item.q);
    const [stream] = await Promise.all([
      page.waitForResponse(r => r.url().endsWith("/messages:stream")),
      page.getByRole("button", { name: "Gửi", exact: true }).click(),
    ]);
    expect(stream.status()).toBe(200);
    const id = new URL(stream.url()).pathname.split("/")[3];
    // Chromium may retain the proxied SSE connection after the final event.
    // Require the UI to consume that event, then read the persisted result.
    await expect(page.getByLabel("Đặt câu hỏi", { exact: true })).toHaveValue("", { timeout: 150_000 });
    let final: any;
    await expect.poll(async () => {
      const response = await page.request.get(`/v1/conversations/${id}/messages`);
      if (response.status() === 429 || response.status() === 503) return false;
      expect(response.status()).toBe(200);
      const saved = await response.json();
      const answers = saved.items.filter((value: any) => value.sender_type === "ASSISTANT");
      final = answers[index]?.final_result;
      return Boolean(final);
    }, { timeout: 150_000, intervals: [4000] }).toBe(true);
    evidence.push({ question: item.q, final });
    await writeFile(test.info().outputPath(`answer-${index + 1}.json`), JSON.stringify({ question: item.q, final }, null, 2), { flag: "wx" });
    await test.info().attach(`answer-${index + 1}`, { body: JSON.stringify({ question: item.q, final }, null, 2), contentType: "application/json" });
    expect(final.response_class).toBe("grounded_answer");
    expect(final.content).toMatch(item.expected);
    expect(final.citations.length).toBeGreaterThan(0);
    if (item.kind === "fees") expect(final.content).toMatch(/K6[4-9]|khóa|chương trình/i);
    else expect(final.content).toMatch(/CNTT|Công nghệ thông tin/i);
    await expect(page.getByLabel("Đặt câu hỏi", { exact: true })).toHaveValue("");
    await page.screenshot({ path: test.info().outputPath(`answer-${index + 1}.png`), fullPage: true });
  }
});
