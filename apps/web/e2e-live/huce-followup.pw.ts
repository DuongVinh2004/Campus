import { test, expect } from "@playwright/test";
import { writeFile } from "node:fs/promises";

test("@model HUCE followup: unaccented credits, source drawer, exclusion and topic change", async ({ page }) => {
  test.setTimeout(300_000);
  await page.goto("/login?next=/chat");
  await page.getByLabel("Mã tài khoản", { exact: true }).fill("SV001");
  await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
  await expect(page.getByLabel("Đặt câu hỏi", { exact: true })).toBeVisible();
  const history = page.getByRole("complementary", { name: "Lịch sử theo tài khoản", exact: true });
  if (!await history.isVisible()) await page.getByRole("button", { name: "Mở danh sách hội thoại", exact: true }).click();
  await history.getByRole("button", { name: "Tùy chọn danh sách hội thoại", exact: true }).click();
  await history.getByRole("button", { name: "Chat tạm thời mới", exact: true }).click();
  const cases = [
    { q: "ky su CNTT K71 can bao nhieu tin chi?", expected: /180/ },
    { q: "Vậy số đó tính cả thể chất và quốc phòng chưa?", expected: /không tính|không bao gồm|chưa tính/i },
    { q: "Chuyển sang học phí: K69 chương trình kỹ sư một tín bao nhiêu tiền?", expected: /547[., ]?000/ },
  ];
  for (const [index, item] of cases.entries()) {
    await page.getByLabel("Đặt câu hỏi", { exact: true }).fill(item.q);
    const [stream] = await Promise.all([
      page.waitForResponse(r => r.url().endsWith("/messages:stream")),
      page.getByRole("button", { name: "Gửi", exact: true }).click(),
    ]);
    expect(stream.status()).toBe(200);
    const conversation = new URL(stream.url()).pathname.split("/")[3];
    let final: any;
    await expect.poll(async () => {
      const response = await page.request.get(`/v1/conversations/${conversation}/messages`, { timeout: 10_000 });
      if ([429, 503].includes(response.status())) return false;
      expect(response.status()).toBe(200);
      const saved = await response.json();
      final = saved.items.filter((value: any) => value.sender_type === "ASSISTANT")[index]?.final_result;
      return Boolean(final);
    }, { timeout: 100_000, intervals: [4000] }).toBe(true);
    await writeFile(test.info().outputPath(`answer-${index + 1}.json`), JSON.stringify({ question: item.q, final }, null, 2), { flag: "wx" });
    expect(final.response_class).toBe("grounded_answer");
    expect(final.content).toMatch(item.expected);
    await expect(page.getByLabel("Đặt câu hỏi", { exact: true })).toHaveValue("");
    if (index === 0) {
      await page.getByRole("button", { name: /nguồn/i }).last().click();
      const [source] = await Promise.all([
        page.waitForResponse(r => /\/citations\/[^/]+\/source$/.test(new URL(r.url()).pathname)),
        page.getByRole("button", { name: "Mở đoạn nguồn gốc", exact: true }).first().click(),
      ]);
      expect(source.status()).toBe(200);
      await expect(page.getByTestId("original-source-text")).toBeVisible();
      await writeFile(test.info().outputPath("source-readback.json"), JSON.stringify(await source.json(), null, 2), { flag: "wx" });
      await page.screenshot({ path: test.info().outputPath("source-drawer.png"), fullPage: true });
      await page.getByRole("button", { name: "Đóng", exact: true }).click();
    }
    await page.screenshot({ path: test.info().outputPath(`answer-${index + 1}.png`), fullPage: true });
  }
});
