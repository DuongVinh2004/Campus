import React, { useState, type FormEvent, type ChangeEvent } from "react";
import {
  ArrowRight,
  FileText,
  Clock,
  CheckCircle2,
  AlertTriangle,
  X,
  Upload,
  Sparkles,
  Paperclip,
  ShieldCheck,
} from "lucide-react";

export interface DocumentRequestPayload {
  documentType: string;
  deliveryMethod?: string;
  quantity: number;
  reason: string;
  attachedFiles?: string[];
}

export interface DocumentRequestFormProps {
  onSubmit?: (data: DocumentRequestPayload) => void;
  onCancel?: () => void;
  hideTitle?: boolean;
}

const docTypeLabels: Record<string, string> = {
  xac_nhan_sinh_vien: "Giấy xác nhận sinh viên (mục đích chung)",
  bang_diem_tam_thoi: "Bảng điểm tạm thời (xác nhận học phần đã hoàn thành)",
  gioi_thieu_thuc_tap: "Giấy giới thiệu thực tập doanh nghiệp",
  hoan_nghia_vu_quan_su: "Giấy xác nhận tạm hoãn NVQS",
};

const docPreparationGuidance: Record<string, { guide: string; documents: string[] }> = {
  xac_nhan_sinh_vien: {
    guide: "Áp dụng cho thủ tục vay vốn, xin trợ cấp hoặc xác nhận tư cách sinh viên.",
    documents: [
      "Ảnh thẻ 3x4 nếu yêu cầu đóng dấu giáp lai ảnh",
      "Thông tin chính xác về nơi nộp giấy xác nhận",
    ],
  },
  bang_diem_tam_thoi: {
    guide: "Bảng điểm tính đến học kỳ gần nhất đã có điểm tổng kết chính thức.",
    documents: [
      "Mã sinh viên và chương trình đào tạo",
      "Đã hoàn thành đánh giá môn học trên Cổng đào tạo",
    ],
  },
  gioi_thieu_thuc_tap: {
    guide: "Cấp cho sinh viên đủ điều kiện thực tập tốt nghiệp hoặc thực tập chuyên ngành.",
    documents: [
      "Tên cơ quan, doanh nghiệp hoặc đơn vị tiếp nhận thực tập",
      "Thời gian dự kiến bắt đầu và kết thúc",
    ],
  },
  hoan_nghia_vu_quan_su: {
    guide: "Giấy xác nhận gửi Ban chỉ huy Quân sự cấp xã/phường nơi đăng ký thường trú.",
    documents: [
      "Lệnh gọi khám tuyển hoặc giấy báo nhập ngũ của Ban chỉ huy quân sự",
      "Bản sao CCCD của sinh viên",
    ],
  },
};

const deliveryLabels: Record<string, string> = {
  pickup: "Nhận trực tiếp tại bộ phận Một cửa (Phòng 102 - Tòa H1)",
  email: "Bản điện tử (PDF gửi qua email sinh viên)",
};

interface AiSuggestion {
  targetType: string;
  label: string;
  confidence: number;
  reason: string;
}

export function DocumentRequestForm({
  onSubmit,
  onCancel,
  hideTitle = false,
}: DocumentRequestFormProps) {
  const [step, setStep] = useState<"editing" | "preview">("editing");
  const [documentType, setDocumentType] = useState("xac_nhan_sinh_vien");
  const [deliveryMethod, setDeliveryMethod] = useState("pickup");
  const [quantity, setQuantity] = useState(1);
  const [reason, setReason] = useState("");
  const [attachedFiles, setAttachedFiles] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  // AI Assistant suggestion state
  const [aiSuggestion, setAiSuggestion] = useState<AiSuggestion | null>(null);

  const analyzeReasonWithAi = (text: string, currentDocType: string) => {
    const lower = text.toLowerCase();
    if (
      lower.includes("thực tập") ||
      lower.includes("doanh nghiệp") ||
      lower.includes("công ty")
    ) {
      if (currentDocType !== "gioi_thieu_thuc_tap") {
        setAiSuggestion({
          targetType: "gioi_thieu_thuc_tap",
          label: "Giấy giới thiệu thực tập doanh nghiệp",
          confidence: 94,
          reason: "Phát hiện từ khóa thực tập/doanh nghiệp trong lý do xin cấp",
        });
        return;
      }
    } else if (
      lower.includes("bảng điểm") ||
      lower.includes("học phần") ||
      lower.includes("kết quả học tập") ||
      lower.includes("gpa")
    ) {
      if (currentDocType !== "bang_diem_tam_thoi") {
        setAiSuggestion({
          targetType: "bang_diem_tam_thoi",
          label: "Bảng điểm tạm thời (xác nhận học phần đã hoàn thành)",
          confidence: 92,
          reason: "Phát hiện từ khóa bảng điểm/học phần trong lý do xin cấp",
        });
        return;
      }
    } else if (
      lower.includes("nghĩa vụ") ||
      lower.includes("quân sự") ||
      lower.includes("nhập ngũ") ||
      lower.includes("nvqs")
    ) {
      if (currentDocType !== "hoan_nghia_vu_quan_su") {
        setAiSuggestion({
          targetType: "hoan_nghia_vu_quan_su",
          label: "Giấy xác nhận tạm hoãn NVQS",
          confidence: 96,
          reason: "Phát hiện nội dung liên quan đến nghĩa vụ quân sự",
        });
        return;
      }
    }
    setAiSuggestion(null);
  };

  const handleReasonChange = (value: string) => {
    setReason(value);
    if (error) setError(null);
    analyzeReasonWithAi(value, documentType);
  };

  const applyAiSuggestion = (targetType: string) => {
    setDocumentType(targetType);
    setAiSuggestion(null);
  };

  const handleFileUpload = (e: ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const newFiles = Array.from(e.target.files).map((f) => f.name);
      setAttachedFiles((prev) => Array.from(new Set([...prev, ...newFiles])));
    }
  };

  const removeFile = (fileName: string) => {
    setAttachedFiles((prev) => prev.filter((f) => f !== fileName));
  };

  const handleProceedToPreview = (e: FormEvent) => {
    e.preventDefault();
    const finalReason = reason.trim();
    if (!finalReason) {
      setError("Vui lòng nhập mục đích xin cấp giấy tờ.");
      return;
    }
    setError(null);
    setStep("preview");
  };

  const handleConfirmSubmit = () => {
    onSubmit?.({
      documentType,
      deliveryMethod,
      quantity: Number(quantity),
      reason: reason.trim(),
      attachedFiles: attachedFiles.length > 0 ? attachedFiles : undefined,
    });
  };

  const handleCancel = () => {
    if (onCancel) {
      onCancel();
    } else {
      setStep("editing");
      setReason("");
      setAttachedFiles([]);
      setError(null);
    }
  };

  const guidance =
    docPreparationGuidance[documentType] ||
    docPreparationGuidance.xac_nhan_sinh_vien;

  if (step === "preview") {
    return (
      <section
        aria-labelledby="preview-heading"
        className={`flex flex-col gap-6 ${
          hideTitle
            ? "pt-2"
            : "rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900 sm:p-8"
        }`}
      >
        <div className="border-b border-slate-100 pb-4 dark:border-slate-800">
          <div className="mb-1.5 flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-blue-50 text-blue-700 dark:bg-blue-950/60 dark:text-blue-300">
              <CheckCircle2 className="h-5 w-5" />
            </div>
            <h2
              id="preview-heading"
              className="text-lg font-bold tracking-tight text-slate-900 dark:text-slate-100 sm:text-xl"
            >
              Xác nhận thông tin yêu cầu cấp giấy tờ
            </h2>
          </div>
          <p className="text-xs text-slate-600 dark:text-slate-400">
            Vui lòng kiểm tra kỹ các thông tin dưới đây trước khi gửi yêu cầu chính thức.
          </p>
        </div>

        {/* Structured Preview List */}
        <dl className="grid grid-cols-1 gap-4 rounded-xl border border-slate-200 bg-slate-50/70 p-4 text-xs dark:border-slate-800 dark:bg-slate-850/60 sm:p-5">
          <div>
            <dt className="font-semibold text-slate-500 uppercase tracking-wider dark:text-slate-400">
              Loại giấy tờ
            </dt>
            <dd className="mt-1 text-sm font-bold text-slate-900 dark:text-slate-100">
              {docTypeLabels[documentType] || documentType}
            </dd>
          </div>

          <div>
            <dt className="font-semibold text-slate-500 uppercase tracking-wider dark:text-slate-400">
              Phương thức nhận
            </dt>
            <dd className="mt-1 font-medium text-slate-800 dark:text-slate-200">
              {deliveryLabels[deliveryMethod] || deliveryMethod}
            </dd>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div>
              <dt className="font-semibold text-slate-500 uppercase tracking-wider dark:text-slate-400">
                Số lượng
              </dt>
              <dd className="mt-1 font-bold text-slate-900 dark:text-slate-100">
                {quantity} bản
              </dd>
            </div>

            <div>
              <dt className="font-semibold text-slate-500 uppercase tracking-wider dark:text-slate-400">
                Lệ phí
              </dt>
              <dd className="mt-1 font-bold text-emerald-600 dark:text-emerald-400">
                Miễn phí
              </dd>
            </div>

            <div>
              <dt className="font-semibold text-slate-500 uppercase tracking-wider dark:text-slate-400">
                Thời gian xử lý dự kiến
              </dt>
              <dd className="mt-1 font-medium text-slate-800 dark:text-slate-200">
                1 - 2 ngày làm việc
              </dd>
            </div>
          </div>

          <div>
            <dt className="font-semibold text-slate-500 uppercase tracking-wider dark:text-slate-400">
              Mục đích xin cấp
            </dt>
            <dd className="mt-1 leading-relaxed text-slate-800 dark:text-slate-200">
              {reason}
            </dd>
          </div>

          {attachedFiles.length > 0 && (
            <div>
              <dt className="font-semibold text-slate-500 uppercase tracking-wider dark:text-slate-400">
                Tệp đính kèm ({attachedFiles.length})
              </dt>
              <dd className="mt-1 flex flex-wrap gap-2">
                {attachedFiles.map((fn, idx) => (
                  <span
                    key={idx}
                    className="inline-flex items-center gap-1.5 rounded-md border border-slate-300 bg-white px-2.5 py-1 text-xs font-medium text-slate-800 shadow-2xs dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
                  >
                    <Paperclip className="h-3 w-3 text-slate-500" />
                    <span>{fn}</span>
                  </span>
                ))}
              </dd>
            </div>
          )}
        </dl>

        {/* Transparency Intake Checklist Preview */}
        <div className="flex flex-col gap-3 rounded-xl border border-emerald-200 bg-emerald-50/60 p-4 text-xs dark:border-emerald-900/50 dark:bg-emerald-950/20 sm:p-5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-emerald-700 dark:text-emerald-400" />
              <h3 className="font-bold text-emerald-900 dark:text-emerald-200">
                Tiêu chuẩn thẩm định của Cán bộ Một cửa (Bộ 6 Cổng tiếp nhận)
              </h3>
            </div>
            <span className="rounded-full border border-emerald-300 bg-emerald-100 px-2.5 py-0.5 text-[11px] font-bold text-emerald-800 dark:border-emerald-700 dark:bg-emerald-900/60 dark:text-emerald-300">
              ✓ Sẵn sàng 6/6 cổng
            </span>
          </div>

          <p className="leading-relaxed text-emerald-800 dark:text-emerald-300">
            Sau khi bạn gửi, hệ thống Một cửa số và Cán bộ chuyên môn sẽ tự động đối chiếu hồ sơ theo 6 tiêu chuẩn nghiệp vụ:
          </p>

          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {[
              { title: "Xác minh danh tính & MSSV", badge: "VNeID", desc: "Khớp hồ sơ đào tạo chính quy" },
              { title: "Thẩm quyền giải quyết", badge: "Quy chế", desc: "Đúng thẩm quyền Một cửa số HUCE" },
              { title: "Kiểm tra đơn trùng lặp", badge: "30 ngày", desc: "Không có đơn trùng đang thụ lý" },
              { title: "Tính hợp lệ minh chứng", badge: "OCR", desc: attachedFiles.length > 0 ? "Đã đính kèm tệp minh chứng" : "Áp dụng theo thủ tục trực tuyến" },
              { title: "Cam kết SLA tiếp nhận", badge: "24h", desc: "Phản hồi trong vòng 24h làm việc" },
              { title: "Bảo vệ thông tin cá nhân", badge: "NĐ 13", desc: "Bảo mật & mã hóa thông tin nhạy cảm" },
            ].map((gate, idx) => (
              <div
                key={idx}
                className="flex items-center justify-between rounded-lg border border-emerald-100 bg-white p-2 text-xs shadow-2xs dark:border-emerald-900/30 dark:bg-slate-900"
              >
                <div className="flex items-center gap-1.5">
                  <span className="font-bold text-emerald-600">✓</span>
                  <span className="font-medium text-slate-800 dark:text-slate-200">{gate.title}</span>
                </div>
                <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-bold text-slate-600 dark:bg-slate-800 dark:text-slate-400">
                  {gate.badge}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Action Controls */}
        <div className="mt-2 flex flex-wrap items-center justify-between gap-3">
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setStep("editing")}
              className="min-h-11 rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 shadow-xs transition hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700 cursor-pointer"
            >
              Quay lại chỉnh sửa
            </button>
            <button
              type="button"
              onClick={handleCancel}
              className="min-h-11 rounded-lg px-4 py-2 text-sm font-medium text-slate-500 transition hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200 cursor-pointer"
            >
              Hủy
            </button>
          </div>

          <button
            type="button"
            onClick={handleConfirmSubmit}
            className="inline-flex min-h-11 items-center gap-2 rounded-lg bg-blue-600 px-6 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-700 cursor-pointer"
          >
            <span>Gửi yêu cầu</span>
            <ArrowRight className="h-4 w-4" />
          </button>
        </div>
      </section>
    );
  }

  return (
    <form
      onSubmit={handleProceedToPreview}
      className={`flex flex-col gap-6 ${
        hideTitle
          ? "pt-2"
          : "rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900 sm:p-8"
      }`}
    >
      {!hideTitle && (
        <div className="border-b border-slate-100 pb-4 dark:border-slate-800">
          <div className="mb-1.5 flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-blue-50 text-blue-700 dark:bg-blue-950/60 dark:text-blue-300">
              <FileText className="h-5 w-5" />
            </div>
            <h2 className="text-lg font-bold tracking-tight text-slate-900 dark:text-slate-100 sm:text-xl">
              Đăng ký cấp giấy tờ sinh viên
            </h2>
          </div>
          <p className="text-xs text-slate-600 dark:text-slate-400">
            Hệ thống một cửa số tiếp nhận và chuyển tiếp tới Phòng Quản lý Đào tạo HUCE xử lý
          </p>
        </div>
      )}

      {error && (
        <div
          id="reason-error"
          role="alert"
          className="flex items-center gap-2.5 rounded-xl border border-rose-200 bg-rose-50 p-3.5 text-xs font-medium text-rose-800 dark:border-rose-900/60 dark:bg-rose-950/30 dark:text-rose-300"
        >
          <span className="h-2 w-2 shrink-0 rounded-full bg-rose-600" />
          <span>{error}</span>
        </div>
      )}

      {/* Document Type */}
      <div className="flex flex-col gap-2">
        <label
          htmlFor="doc-type"
          className="text-xs font-semibold text-slate-800 dark:text-slate-200"
        >
          Loại giấy tờ <span className="text-rose-500">*</span>
        </label>
        <select
          id="doc-type"
          value={documentType}
          onChange={(e) => {
            setDocumentType(e.target.value);
            setAiSuggestion(null);
          }}
          className="min-h-[42px] cursor-pointer rounded-xl border border-slate-300 bg-white px-3.5 py-2 text-xs text-slate-900 shadow-2xs focus:border-blue-500 focus:outline-none dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
        >
          <option value="xac_nhan_sinh_vien">
            Giấy xác nhận sinh viên (mục đích chung)
          </option>
          <option value="bang_diem_tam_thoi">
            Bảng điểm tạm thời (xác nhận học phần đã hoàn thành)
          </option>
          <option value="gioi_thieu_thuc_tap">
            Giấy giới thiệu thực tập doanh nghiệp
          </option>
          <option value="hoan_nghia_vu_quan_su">
            Giấy xác nhận tạm hoãn NVQS
          </option>
        </select>
      </div>

      {/* Document Preparation Guidance Card */}
      <div className="rounded-xl border border-blue-200 bg-blue-50/70 p-4 text-xs text-blue-900 dark:border-blue-900/50 dark:bg-blue-950/20 dark:text-blue-300">
        <div className="mb-1 flex items-center gap-1.5 font-bold">
          <span>ℹ️</span> Hồ sơ & giấy tờ cần chuẩn bị:
        </div>
        <p className="mb-1 text-slate-700 dark:text-slate-300">{guidance.guide}</p>
        <ul className="list-disc pl-5 text-slate-800 dark:text-slate-200 space-y-0.5">
          {guidance.documents.map((item, idx) => (
            <li key={idx}>{item}</li>
          ))}
        </ul>
      </div>

      {/* Delivery Method */}
      <div className="flex flex-col gap-2">
        <label
          htmlFor="delivery-method"
          className="text-xs font-semibold text-slate-800 dark:text-slate-200"
        >
          Phương thức nhận kết quả <span className="text-rose-500">*</span>
        </label>
        <select
          id="delivery-method"
          value={deliveryMethod}
          onChange={(e) => setDeliveryMethod(e.target.value)}
          className="min-h-[42px] cursor-pointer rounded-xl border border-slate-300 bg-white px-3.5 py-2 text-xs text-slate-900 shadow-2xs focus:border-blue-500 focus:outline-none dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
        >
          <option value="pickup">
            Nhận trực tiếp tại bộ phận Một cửa (Phòng 102 - Tòa H1)
          </option>
          <option value="email">
            Bản điện tử (PDF gửi qua email sinh viên)
          </option>
        </select>
      </div>

      {/* Quantity */}
      <div className="flex flex-col gap-2">
        <label
          htmlFor="quantity"
          className="text-xs font-semibold text-slate-800 dark:text-slate-200"
        >
          Số lượng bản <span className="text-rose-500">*</span>
        </label>
        <div className="flex items-center gap-3">
          <input
            id="quantity"
            type="number"
            min={1}
            max={5}
            value={quantity}
            onChange={(e) =>
              setQuantity(Math.max(1, Math.min(5, Number(e.target.value))))
            }
            className="min-h-[42px] w-24 rounded-xl border border-slate-300 bg-white px-3.5 py-2 text-xs text-slate-900 shadow-2xs focus:border-blue-500 focus:outline-none dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
          />
          <span className="text-xs text-slate-500 dark:text-slate-400">
            (Tối đa 5 bản/lần đăng ký)
          </span>
        </div>
      </div>

      {/* Purpose / Reason */}
      <div className="flex flex-col gap-2">
        <label
          htmlFor="reason"
          className="text-xs font-semibold text-slate-800 dark:text-slate-200"
        >
          Mục đích xin cấp <span className="text-rose-500">*</span>
        </label>
        <textarea
          id="reason"
          rows={3}
          value={reason}
          onChange={(e) => handleReasonChange(e.target.value)}
          aria-invalid={error ? "true" : "false"}
          aria-describedby={error ? "reason-error" : undefined}
          placeholder="Ví dụ: Vay vốn sinh viên chính sách tại địa phương, bổ sung hồ sơ xin thực tập..."
          className={`w-full rounded-xl border p-3 text-xs leading-relaxed transition focus:outline-none ${
            error
              ? "border-rose-400 bg-rose-50/20 text-rose-900 focus:border-rose-500"
              : "border-slate-300 bg-white text-slate-900 focus:border-blue-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
          }`}
        />

        {/* AI Assistant Suggestion Banner */}
        {aiSuggestion && (
          <div
            role="status"
            className="flex flex-wrap items-center justify-between gap-2.5 rounded-xl border border-fuchsia-200 bg-fuchsia-50/70 p-3 text-xs text-fuchsia-900 dark:border-fuchsia-900/60 dark:bg-fuchsia-950/30 dark:text-fuchsia-200"
          >
            <div className="flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-fuchsia-600 dark:text-fuchsia-400" />
              <span>
                <strong>Gợi ý AI phân loại ({aiSuggestion.confidence}%):</strong> Bạn có muốn đổi sang{" "}
                <strong>{aiSuggestion.label}</strong>?
              </span>
            </div>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => applyAiSuggestion(aiSuggestion.targetType)}
                className="rounded-lg bg-fuchsia-700 px-3 py-1 font-semibold text-white shadow-2xs transition hover:bg-fuchsia-800 dark:bg-fuchsia-600 dark:hover:bg-fuchsia-700"
              >
                Áp dụng gợi ý
              </button>
              <button
                type="button"
                onClick={() => setAiSuggestion(null)}
                aria-label="Bỏ qua gợi ý"
                className="cursor-pointer text-xs font-medium text-fuchsia-700 hover:text-fuchsia-900 dark:text-fuchsia-300"
              >
                Bỏ qua
              </button>
            </div>
          </div>
        )}
      </div>

      {/* File Attachment Simulation */}
      <div className="flex flex-col gap-2">
        <label
          htmlFor="file-attachments"
          className="text-xs font-semibold text-slate-800 dark:text-slate-200"
        >
          Tệp minh chứng đính kèm (nếu có)
        </label>
        <p className="text-xs text-slate-500 dark:text-slate-400">
          Đính kèm bản chụp CCCD, giấy gọi NVQS, hoặc văn bản liên quan (PDF, JPG, PNG tối đa 5MB).
        </p>

        <div className="flex flex-wrap items-center gap-3">
          <label
            htmlFor="file-attachments"
            className="inline-flex cursor-pointer items-center gap-2 rounded-xl border border-dashed border-slate-300 bg-slate-50 px-4 py-2 text-xs font-semibold text-slate-700 transition hover:bg-slate-100 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-750"
          >
            <Upload className="h-3.5 w-3.5 text-slate-500" />
            <span>Chọn tệp tải lên</span>
            <input
              id="file-attachments"
              type="file"
              multiple
              onChange={handleFileUpload}
              className="hidden"
            />
          </label>

          {attachedFiles.map((fn, idx) => (
            <span
              key={idx}
              className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-slate-100 px-2.5 py-1 text-xs text-slate-800 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
            >
              <span>{fn}</span>
              <button
                type="button"
                onClick={() => removeFile(fn)}
                aria-label={`Xóa tệp ${fn}`}
                className="font-bold text-rose-500 hover:text-rose-700"
              >
                ×
              </button>
            </span>
          ))}
        </div>
      </div>

      {/* Turnaround expectation & Action Button */}
      <div className="mt-2 flex flex-wrap items-center justify-between gap-4">
        <div className="inline-flex items-center gap-2 text-xs text-slate-600 dark:text-slate-400">
          <Clock className="h-4 w-4 text-slate-400" />
          <span>Thời gian xử lý dự kiến: 1 - 2 ngày làm việc</span>
        </div>

        <button
          type="submit"
          className="inline-flex min-h-11 items-center gap-2 rounded-lg bg-blue-600 px-6 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-700 cursor-pointer"
        >
          <span>Xem trước yêu cầu</span>
          <ArrowRight className="h-4 w-4" />
        </button>
      </div>
    </form>
  );
}
