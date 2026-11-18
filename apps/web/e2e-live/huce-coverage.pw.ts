import { test, expect } from "@playwright/test";
import { writeFile } from "node:fs/promises";

// Live observations across every student topic. A completed transport with a
// refusal is recorded as a knowledge gap, never counted as a grounded success.
const cases = [
  ["admission", "Sinh viên mới HUCE cần xem hướng dẫn nhập học và hồ sơ chính thức ở đâu?"],
  ["curriculum", "K71 ngành CNTT phần mềm thuộc chương trình cấp bằng gì?"],
  ["credits", "Kỹ sư CNTT K71 cần bao nhiêu tín chỉ, có tính giáo dục thể chất và quốc phòng không?"],
  ["registration", "Em muốn rút bớt học phần sau khi đăng ký thì phải theo quy định nào?"],
  ["tuition", "K69 đóng bao nhiêu tiền một tín nếu học chương trình kỹ sư?"],
  ["financial_support", "Điểm học tập và rèn luyện ảnh hưởng thế nào đến xét học bổng khuyến khích học tập HUCE?"],
  ["calendar_exams", "Muốn xem lịch thi và xin phúc khảo bài thi ở HUCE thì tra cứu thế nào?"],
  ["academic_standing", "Em muốn bảo lưu rồi quay lại học thì cần những điều kiện gì?"],
  ["graduation", "Khi xét tốt nghiệp đại học HUCE, yêu cầu ngoại ngữ được kiểm tra thế nào?"],
  ["one_stop", "Có thể xin bảng điểm qua bộ phận Một cửa HUCE theo quy trình nào?"],
  ["student_affairs", "HUCE đánh giá điểm rèn luyện sinh viên theo những nhóm nội dung nào?"],
  ["facilities", "Muốn mượn sách mang về từ thư viện HUCE thì phải đáp ứng điều kiện nào?"],
  ["it_support", "Em quên mật khẩu tài khoản sinh viên HUCE thì tìm hỗ trợ ở đâu?"],
  ["opportunities", "Sinh viên HUCE muốn tham gia nghiên cứu khoa học cần tìm đầu mối nào?"],
  ["contacts", "Em cần liên hệ phòng công tác sinh viên HUCE, nên đến địa điểm nào?"],
  ["missing_programme", "Kỹ sư xây dựng dân dụng K69 phải tích lũy chính xác bao nhiêu tín chỉ?"],
  ["missing_future", "Cho em ngày bắt đầu và kết thúc lịch nghỉ Tết HUCE năm 2035 đã phê duyệt."],
];

for (const [topic, question] of cases) test(`@model HUCE coverage: ${topic}`, async ({ page }) => {
  test.setTimeout(180_000);
  await page.goto("/login?next=/chat");
  await page.getByLabel("Mã tài khoản", { exact: true }).fill("SV001");
  await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
  await expect(page).toHaveURL(/\/chat$/);
  await expect(page.getByLabel("Đặt câu hỏi", { exact: true })).toBeVisible();
  const history = page.getByRole("complementary", { name: "Lịch sử theo tài khoản", exact: true });
  if (!await history.isVisible()) await page.getByRole("button", { name: "Mở danh sách hội thoại", exact: true }).click();
  await history.getByRole("button", { name: "Tùy chọn danh sách hội thoại", exact: true }).click();
  await history.getByRole("button", { name: "Chat tạm thời mới", exact: true }).click();
  await page.getByLabel("Đặt câu hỏi", { exact: true }).fill(question);
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
    final = saved.items.find((item: any) => item.sender_type === "ASSISTANT")?.final_result;
    return Boolean(final);
  }, { timeout: 100_000, intervals: [4000] }).toBe(true);
  expect(final).toBeTruthy();
  if (final.response_class !== "system_error") {
    await expect(page.getByLabel("Đặt câu hỏi", { exact: true })).toHaveValue("");
  }
  const readbacks: unknown[] = [];
  for (const citation of final.citations ?? []) {
    const id = citation.citation.citation_id;
    const source = await page.request.get(`/v1/conversations/${conversation}/messages/${final.message_id}/citations/${id}/source`, { timeout: 10_000 });
    readbacks.push({ citation_id: id, http_status: source.status(), ...(source.ok() ? { source: await source.json() } : {}) });
  }
  await writeFile(test.info().outputPath("observation.json"), JSON.stringify({
    topic, question, final, readbacks, grounded: final.response_class === "grounded_answer",
    grading: "transport_and_citation_readback_only; requires_content_review",
  }, null, 2), { flag: "wx" });
  await page.screenshot({ path: test.info().outputPath("answer.png"), fullPage: true });
  if (["grounded_answer", "partial_answer"].includes(final.response_class)) {
    expect(final.citations.length).toBeGreaterThan(0);
    expect(readbacks.every((r: any) => r.http_status === 200)).toBe(true);
  }
  if (topic === "missing_programme") expect(final.content).not.toMatch(/(?:cần|gồm|tổng|là)\s*180\s*(?:tín|TC)/i);
  if (topic === "missing_future") expect(final.response_class).not.toBe("grounded_answer");
});
