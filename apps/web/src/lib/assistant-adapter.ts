import { lookupStudentGuidance, type AssistantReply } from "./student-assistant";
import { VINUNI_SOURCES, type VinUniTask } from "./vinuni-forms";

export interface AssistantRequest {
  question: string;
  context: { label: string; task?: VinUniTask; requestCode?: string; status?: string; supplement?: string; field?: { label: string; hint?: string } };
}
export interface AssistantResult {
  reply: AssistantReply;
  edit?: { field: string; value: string };
}
/** An API adapter can implement this contract without exposing API keys in the browser. */
export interface AssistantAdapter { respond(request: AssistantRequest, signal: AbortSignal): Promise<AssistantResult> }

export function isAssistantResult(value: unknown): value is AssistantResult {
  if (!value || typeof value !== "object") return false;
  const result = value as AssistantResult;
  const reply = result.reply;
  return Boolean(reply && typeof reply.text === "string" && reply.text.length <= 20000 && !reply.proposal &&
    (!reply.action || (typeof reply.action.label === "string" && ["/student/certificate", "/student/complaint", "/my-requests"].includes(reply.action.href))) &&
    (!reply.source || (typeof reply.source.title === "string" && typeof reply.source.section === "string" && typeof reply.source.quote === "string" && (!reply.source.href || Object.values(VINUNI_SOURCES).includes(reply.source.href)))) &&
    (!result.edit || (typeof result.edit.field === "string" && typeof result.edit.value === "string" && result.edit.value.length <= 4000)));
}

export const guidanceAdapter: AssistantAdapter = {
  async respond({ question, context }, signal) {
    if (signal.aborted) throw new DOMException("Aborted", "AbortError");
    if (context.field) return { reply: { text: `Bạn đang hỏi về trường “${context.field.label}”. ${context.field.hint || "Điền đúng thông tin tương ứng với yêu cầu của bạn. Bạn có thể sửa trực tiếp trong biểu mẫu và kiểm tra lại ở bước cuối."}` } };
    if (context.requestCode && /trạng thái|tiến độ|theo dõi|bổ sung|phản hồi/i.test(question)) {
      return { reply: { text: `Bạn đang xem hồ sơ ${context.requestCode}${context.status ? `, trạng thái hiển thị: ${context.status}` : ""}. ${context.supplement || "Xem tiến trình và phản hồi của cán bộ trong chi tiết hồ sơ."} Trợ lý chỉ giải thích thông tin đang hiển thị, không xác nhận thay cán bộ.` } };
    }
    if (context.task && /^(?:hãy\s+|giúp (?:mình|tôi|em)\s+)?(?:đổi|chuyển|sửa|cập nhật)\b/i.test(question.normalize("NFC"))) {
      const purpose = question.match(/(?:đổi|sửa|cập nhật)\s+mục đích\s*(?:(?:thành|sang|là)\s+|:\s*)(.+)/i);
      const destination = question.match(/(?:đổi|sửa|cập nhật)\s+(?:nơi nhận|nơi gửi)\s*(?:(?:thành|sang|là)\s+|:\s*)(.+)/i);
      const description = question.match(/(?:đổi|sửa|cập nhật)\s+(?:căn cứ|mô tả)\s*(?:(?:thành|sang|là)\s+|:\s*)(.+)/i);
      const edit = context.task === "certificate"
        ? purpose ? { field: "purpose", value: purpose[1].trim() } : destination ? { field: "destinationOrg", value: destination[1].trim() } : /bản giấy/i.test(question) ? { field: "receiveMethod", value: "paper_stamped" } : /điện tử|pdf/i.test(question) ? { field: "receiveMethod", value: "digital_pdf" } : undefined
        : description ? { field: "description", value: description[1].trim() } : undefined;
      if (edit) return { reply: { text: "Đây là đề xuất cập nhật bản nháp. Bạn kiểm tra thay đổi rồi chọn Áp dụng; hồ sơ chỉ được gửi khi bạn xác nhận nộp trong biểu mẫu." }, edit };
    }
    return { reply: lookupStudentGuidance(question) };
  },
};
