import { test, expect } from "@playwright/test";
import { randomBytes } from "node:crypto";
import { writeFile } from "node:fs/promises";

test("SV001 explicitly authorized history consent only", async ({ page }) => {
  await page.goto("/login?next=/chat");
  await page.getByLabel("Mã tài khoản", { exact: true }).fill("SV001");
  await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
  await expect(page.getByLabel("Đặt câu hỏi", { exact: true })).toBeVisible();
  const state = async () => {
    const response = await page.request.get("/v1/assistant/consent-state");
    expect(response.status()).toBe(200);
    return (await response.json()).items;
  };
  const before = await state();
  const current = before.find((item: any) => item.purpose === "CONVERSATION_HISTORY");
  const noticeResponse = await page.request.get("/v1/assistant/consent-notice");
  expect(noticeResponse.status()).toBe(200);
  const notice = await noticeResponse.json();
  if (!current.current_notice_consented) {
    const preview = await page.request.post("/v1/assistant/consents:preview", { data: {
      purpose: "CONVERSATION_HISTORY", decision: "GRANTED", notice_version: notice.version,
      expected_version: current.version, client_id: (() => {
        const bytes = randomBytes(16);
        bytes.writeUIntBE(Date.now(), 0, 6);
        bytes[6] = (bytes[6] & 15) | 112;
        bytes[8] = (bytes[8] & 63) | 128;
        const hex = bytes.toString("hex");
        return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
      })(),
    } });
    expect(preview.status()).toBe(200);
    const prepared = await preview.json();
    const confirm = await page.request.post("/v1/assistant/preferences:confirm", { data: {
      normalized_payload: prepared.normalized_payload,
      confirmation_token: prepared.confirmation_token, confirmed: true,
    } });
    expect(confirm.ok()).toBe(true);
  }
  const after = await state();
  expect(after.find((item: any) => item.purpose === "CONVERSATION_HISTORY").current_notice_consented).toBe(true);
  expect(after.filter((item: any) => item.purpose !== "CONVERSATION_HISTORY"))
    .toEqual(before.filter((item: any) => item.purpose !== "CONVERSATION_HISTORY"));
  await writeFile(test.info().outputPath("consent-receipt-redacted.json"), JSON.stringify({
    actor: "SV001", authority: "Direct user request: Bật CONVERSATION_HISTORY cho SV001 để kiểm thử",
    before, after, preview_confirm_used: !current.current_notice_consented,
  }, null, 2), { flag: "wx" });
});
