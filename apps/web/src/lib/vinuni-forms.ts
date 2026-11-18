export type VinUniTask = "certificate" | "complaint";
export type FormValues = Record<string, string>;
export const VINUNI_SOURCES = {
  documents: "https://registrar.vinuni.edu.vn/academics/request-transcripts-certifications/",
  documentForm: "https://forms.office.com/pages/responsepage.aspx?id=iSf4WJVmSk-r2zV2aNVc_0dbBYw8WtJPgbnOOjH80gpUNDRJUExIOEoxQzA0RE9CRE9XWVM1M0QxSS4u&route=shorturl",
  appeal: "https://policy.vinuni.edu.vn/all-policies/student-grade-appeal-procedure/",
  appealForm: "https://policy.vinuni.edu.vn/wp-content/uploads/2026/01/PRC_AQA_002_Grade-Appeal-Form_21.01.2026.pdf",
  fees: "https://policy.vinuni.edu.vn/all-policies/financial-regulations-and-tariff-for-student-2/",
  policies: "https://policy.vinuni.edu.vn/",
};
export const documentTypes = [
  ["ENR", "Xác nhận đang theo học", "Enrollment Certification Letter"],
  ["TNR", "Bảng điểm chính thức", "Official Transcript"],
  ["RCM", "Thư hỗ trợ chương trình/trao đổi/thực tập", "Letter of Recommendation"],
  ["ENG", "Xác nhận chương trình học bằng tiếng Anh", "English Proficiency Confirmation Letter"],
  ["GRD", "Xác nhận tốt nghiệp", "Graduation Confirmation Letter"],
  ["CRS", "Danh sách học phần học kỳ hiện tại", "Current Semester Course List"],
] as const;
export interface FormField {
  name: string; label: string; type?: "select" | "textarea" | "email" | "number" | "date" | "checkbox" | "file";
  options?: readonly (readonly [string, string])[]; required?: boolean; hint?: string;
  when?: (values: FormValues) => boolean;
}
const paperShipping = (v: FormValues) => v.receiveMethod === "paper_stamped" && v.delivery === "shipping";
const otherRecipient = (v: FormValues) => v.receiveMethod === "digital_pdf" && v.recipient === "other";
export function languages(type: string): readonly (readonly [string, string])[] {
  return type === "ENR" ? [["bilingual", "Song ngữ Anh – Việt"]] : type === "TNR" ? [["english", "Tiếng Anh"]] : [["english", "Tiếng Anh"], ["bilingual", "Song ngữ Anh – Việt (theo yêu cầu)"]];
}
export function fieldsFor(task: VinUniTask, stage: number, values: FormValues): FormField[] {
  const identity: FormField[] = [{ name: "email", label: "Email sinh viên", type: "email", required: true, hint: "Dùng email trường cấp (ví dụ: ...@huce.edu.vn) khi nộp hồ sơ chính thức." }];
  if (task === "certificate") return stage === 0 ? [...identity,
    { name: "documentType", label: "Loại tài liệu", type: "select", options: documentTypes.map(([id, label]) => [id, label]), required: true },
    { name: "language", label: "Ngôn ngữ", type: "select", options: languages(values.documentType), required: true },
    { name: "purpose", label: "Mục đích sử dụng", hint: "Ví dụ: hồ sơ visa, học bổng, thực tập. Không bắt buộc." },
    { name: "expectedGraduation", label: "Đề nghị ghi ngày tốt nghiệp dự kiến", type: "checkbox", when: (v) => v.documentType === "ENR" },
    { name: "programDetails", label: "Thông tin chương trình/trao đổi/thực tập", type: "textarea", required: true, when: (v) => v.documentType === "RCM", hint: "Tên chương trình, đơn vị tổ chức, địa chỉ, thời gian và thông tin tài trợ/học bổng nếu có." },
    { name: "extraRequest", label: "Yêu cầu bổ sung", type: "textarea", hint: "Không bắt buộc. Bộ phận chức năng sẽ xác nhận yêu cầu đặc biệt có được hỗ trợ hay không." },
  ] : [
    { name: "receiveMethod", label: "Định dạng tài liệu", type: "select", options: [["digital_pdf", "Bản điện tử (PDF)"], ["paper_stamped", "Bản giấy"]], required: true },
    { name: "copies", label: "Số bản", type: "number", required: true, hint: "Phí tham khảo: 50.000đ/bản. Cán bộ xác nhận phí khi tiếp nhận." },
    { name: "recipient", label: "Gửi PDF tới", type: "select", options: [["self", "Email trường cấp của tôi"], ["other", "Email đơn vị/người nhận khác"]], when: (v) => v.receiveMethod === "digital_pdf", required: true },
    { name: "destinationOrg", label: "Tên đơn vị/người nhận", when: otherRecipient, required: true },
    { name: "recipientEmail", label: "Email người nhận", type: "email", when: otherRecipient, required: true, hint: "Email người nhận cần được bộ phận tiếp nhận xác minh." },
    { name: "delivery", label: "Cách nhận bản giấy", type: "select", options: [["pickup", "Nhận tại Bộ phận Một cửa"], ["shipping", "Yêu cầu chuyển phát"]], when: (v) => v.receiveMethod === "paper_stamped", required: true },
    { name: "recipientName", label: "Họ tên người nhận", when: paperShipping, required: true },
    { name: "recipientPhone", label: "Số điện thoại người nhận", when: paperShipping, required: true },
    { name: "address", label: "Địa chỉ đầy đủ", type: "textarea", when: paperShipping, required: true },
    { name: "country", label: "Quốc gia", when: paperShipping, required: true, hint: "Chuyển phát quốc tế do sinh viên thanh toán theo thông báo của trường." },
  ];
  return stage === 0 ? [...identity,
    { name: "phone", label: "Số điện thoại", required: true },
    { name: "courseCode", label: "Mã học phần — Course Code", required: true },
    { name: "course", label: "Tên học phần — Course Name", required: true },
    { name: "section", label: "Lớp học phần — Course Section", required: true },
    { name: "semester", label: "Học kỳ / Năm học — Semester/Year", required: true },
    { name: "instructor", label: "Giảng viên — Instructor Name", required: true },
    { name: "scope", label: "Điểm bạn muốn xem xét", type: "select", options: [["final", "Điểm tổng kết học phần"], ["component", "Điểm thành phần / bài kiểm tra"]], required: true },
    { name: "grade", label: "Điểm tổng kết hiện tại", hint: "Không bắt buộc; ghi đúng điểm đang hiển thị trên cổng đào tạo." },
    { name: "postedDate", label: "Ngày công bố điểm chính thức", type: "date", required: true, hint: "Hạn nộp theo quy trình: trong 5 ngày làm việc kể từ ngày công bố điểm chính thức." },
    { name: "contactOutcome", label: "Kết quả liên hệ giảng viên", type: "select", options: [["", "Chọn kết quả"], ["unresolved", "Đã trao đổi nhưng chưa giải quyết được"], ["unanswered", "Đã liên hệ nhưng chưa nhận được phản hồi"], ["other", "Trường hợp khác"], ["not_contacted", "Chưa liên hệ giảng viên"]], required: true },
    { name: "contactDates", label: "Ngày/giờ liên hệ hoặc trao đổi", required: true, hint: "Nêu ngày/giờ trong email đã gửi. Quy trình yêu cầu liên hệ bằng email." },
    { name: "contactExplanation", label: "Giải thích trường hợp khác", type: "textarea", when: (v) => v.contactOutcome === "other", required: true },
  ] : [
    { name: "claimError", label: "Sai sót — Error", type: "checkbox" },
    { name: "claimInconsistency", label: "Chấm điểm không nhất quán — Grading Inconsistency", type: "checkbox" },
    { name: "claimOther", label: "Căn cứ khác — Other", type: "checkbox" },
    { name: "description", label: "Tóm tắt căn cứ khiếu nại", type: "textarea", required: true, hint: "Mô tả vấn đề, căn cứ và các nỗ lực giải quyết trước đó." },
    { name: "evidenceFiles", label: "Tài liệu minh chứng và email trao đổi", type: "file", required: true, hint: "PDF, PNG, JPG; tối đa 5 tệp, 10MB/tệp. Sau khi xác nhận, tệp được lưu cùng hồ sơ." },
    { name: "paymentProof", label: "Chứng từ thanh toán lệ phí", type: "file", required: true, hint: "Phí rà soát điểm tham khảo: 1.000.000đ/yêu cầu/học phần. Kiểm tra hướng dẫn thanh toán chính thức trước khi thực hiện." },
    { name: "declaration", label: "Tôi xác nhận thông tin đã khai chính xác và đầy đủ theo hiểu biết của mình", type: "checkbox", required: true, hint: "Xác nhận điện tử này được ghi nhận cùng hồ sơ; cán bộ có thể yêu cầu mẫu ký bổ sung nếu cần." },
  ];
}
export function visibleFields(task: VinUniTask, stage: number, values: FormValues) { return fieldsFor(task, stage, values).filter((f) => !f.when || f.when(values)); }
export function validateForm(task: VinUniTask, values: FormValues, stages = [0, 1], availableFiles: Record<string, File[]> = {}) {
  const errors: Record<string, string> = {};
  if (task === "complaint" && stages.includes(1) && !["claimError", "claimInconsistency", "claimOther"].some((name) => values[name] === "yes")) errors.claimError = "Chọn ít nhất một căn cứ khiếu nại.";
  for (const stage of stages) for (const field of visibleFields(task, stage, values)) {
    const value = values[field.name]?.trim() || "";
    if (field.required && (field.type === "file" ? !availableFiles[field.name]?.length : field.type === "checkbox" ? value !== "yes" : !value)) errors[field.name] = field.type === "file" ? "Chọn lại tệp để hoàn tất hồ sơ." : `Vui lòng điền hoặc xác nhận ${field.label.toLowerCase()}.`;
    if (value.length > 4000) errors[field.name] = "Nội dung tối đa 4.000 ký tự.";
    if (field.type === "email" && value && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) errors[field.name] = "Nhập địa chỉ email hợp lệ.";
    if (field.name === "email" && value && !/^[^\s@]+@(?:[a-z0-9-]+\.)*(?:huce|vinuni)\.edu\.vn$/i.test(value)) errors.email = "Dùng địa chỉ email do trường cấp (ví dụ: ...@huce.edu.vn).";
    if (field.type === "select" && value && !field.options?.some(([id]) => id === value)) errors[field.name] = "Lựa chọn không còn phù hợp. Vui lòng chọn lại.";
    if (field.type === "date" && value) {
      const parsed = new Date(`${value}T00:00:00Z`);
      const today = new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Bangkok", year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date());
      if (!/^\d{4}-\d{2}-\d{2}$/.test(value) || Number.isNaN(parsed.getTime()) || parsed.toISOString().slice(0, 10) !== value || value > today) errors[field.name] = "Chọn ngày công bố hợp lệ, không ở tương lai.";
    }
    if (["phone", "recipientPhone"].includes(field.name) && value && !/^\+?[\d ()-]{7,25}$/.test(value)) errors[field.name] = "Nhập số điện thoại hợp lệ, có thể kèm mã quốc gia.";
  }
  if (task === "certificate" && stages.includes(1) && (!/^\d+$/.test(values.copies) || !Number.isSafeInteger(Number(values.copies)) || Number(values.copies) < 1 || Number(values.copies) > 99)) errors.copies = "Nhập số bản từ 1 đến 99; cán bộ xác nhận số lượng được cấp.";
  if (task === "complaint") {
    if (stages.includes(0) && values.scope !== "final") errors.scope = "Grade Appeal chỉ áp dụng điểm tổng kết học phần. Hãy liên hệ giảng viên về điểm thành phần.";
    if (stages.includes(0) && values.contactOutcome === "not_contacted") errors.contactOutcome = "Cần liên hệ giảng viên bằng email trước. Có thể lưu bản nháp và quay lại sau.";
  }
  return errors;
}
export function defaults(task: VinUniTask, email: string): FormValues {
  return task === "certificate" ? { documentType: "ENR", language: "bilingual", receiveMethod: "digital_pdf", copies: "1", recipient: "self", delivery: "pickup", email, country: "Việt Nam" } : { scope: "final", email, contactOutcome: "" };
}
