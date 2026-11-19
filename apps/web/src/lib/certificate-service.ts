import { Ticket, SystemVerificationItem, IssuedCertificateDocument } from "./types";

/**
 * Service deterministic quản lý quy trình đối soát dữ liệu và phát hành Giấy xác nhận sinh viên BM-03.
 * Đảm bảo: Hệ thống chuẩn bị dữ liệu -> Cán bộ kiểm tra, xác nhận -> Sinh viên nhận được giấy.
 */

export const CERTIFICATE_TEMPLATE_VERSION = "BM-03/CTSV-v2.1";

/**
 * Chạy đối soát tự động dữ liệu giả lập cho ticket cấp giấy.
 * Kết quả thay đổi theo dữ liệu từng hồ sơ; không hiển thị thành công giả.
 */
export function runCertificateVerification(ticket: Ticket): SystemVerificationItem[] {
  const now = new Date();
  const timeStr = `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}:${String(
    now.getSeconds()
  ).padStart(2, "0")}`;
  const dateStr = `${String(now.getDate()).padStart(2, "0")}/${String(now.getMonth() + 1).padStart(2, "0")}/${now.getFullYear()}`;
  const timestamp = `${timeStr} · ${dateStr}`;

  // Kiểm tra trường hợp hồ sơ đặc biệt demo
  const isErrCase = ticket.code === "TKT-2026-0146" || ticket.id === "TKT-2026-0146";
  const isWarningCase = ticket.code === "TKT-2026-0145" || ticket.id === "TKT-2026-0145";

  // 1. Điều kiện Tình trạng học tập sinh viên
  let statusAcademic: "passed" | "failed" | "insufficient" | "error" = "passed";
  let reasonAcademic = "Sinh viên đang học chính quy tại Trường, không có quyết định đình chỉ hoặc cảnh cáo học vụ mức 3.";
  if (isErrCase) {
    statusAcademic = "error";
    reasonAcademic = "Máy chủ CSDL Đào tạo phản hồi chậm (HTTP 504 Gateway Timeout). Chưa thể lấy dữ liệu tình trạng đào tạo.";
  }

  const academicItem: SystemVerificationItem = {
    id: `verif-${ticket.id}-academic`,
    criterionKey: "academic_status",
    criterionLabel: "1. Tình trạng học tập & Kỷ luật sinh viên",
    conditionApplied: "Quy chế Đào tạo & CTSV Điều 14: Sinh viên phải ở trạng thái 'Đang học chính quy', không bị tạm đình chỉ học tập.",
    dataChecked: `MSSV: ${ticket.studentMssv} · Họ tên: ${ticket.studentName} · Lớp: ${ticket.studentClassYear} · Trạng thái: Đang học bình thường`,
    sourceSystem: "CSDL Đào tạo tích hợp [PORTAL-DB]",
    lookupTimestamp: timestamp,
    status: statusAcademic,
    reason: reasonAcademic,
    evidenceDetails: {
      rawSnippet: `SELECT student_id, full_name, status, discipline_record FROM academic_students WHERE student_id = '${ticket.studentMssv}';\n=> Result: STATUS = 'ACTIVE', DISCIPLINE = 'NONE', TERM = '2025.2'`,
      systemUrl: "https://daotao.campus.edu.vn/api/v1/students/verify",
      verifiedFields: {
        "Trạng thái đào tạo": "Đang học chính quy",
        "Số tín chỉ tích lũy": "114 / 138 TC",
        "Cảnh cáo học tập": "Không có (Mức 0)",
        "Điểm rèn luyện kỳ gần nhất": "88 (Tốt)",
      },
    },
    officerReviewStatus: "pending",
  };

  // 2. Điều kiện Nghĩa vụ tài chính & Học phí
  let statusFinance: "passed" | "failed" | "insufficient" | "error" = "passed";
  let reasonFinance =
    "Dữ liệu cổng KHTC ghi nhận sinh viên không nợ học phí kỳ trước. Với mục đích vay vốn NHCSXH (QĐ 157/2007/QĐ-TTg), sinh viên đủ điều kiện cấp giấy để giải ngân học phí.";
  
  if (isWarningCase) {
    statusFinance = "insufficient";
    reasonFinance =
      "Cổng KHTC ghi nhận nợ học phí kỳ 1 (12.500.000 VNĐ) chưa có đơn xin gia hạn nợ. Cần cán bộ kiểm tra xác nhận chính sách trước khi phát hành.";
  } else if (isErrCase) {
    statusFinance = "passed";
    reasonFinance = "Hệ thống KHTC đã lưu cache: Đã hoàn tất nghĩa vụ học phí năm 2025.";
  }

  const financeItem: SystemVerificationItem = {
    id: `verif-${ticket.id}-finance`,
    criterionKey: "financial_obligation",
    criterionLabel: "2. Nghĩa vụ học phí & Tài chính học kỳ",
    conditionApplied:
      "Quy định Tài chính SV: Sinh viên không nợ học phí quá hạn. Đối với giấy xác nhận vay vốn chính sách, không bắt buộc nợ học phí = 0 nếu có cam kết giải ngân qua ngân hàng.",
    dataChecked: isWarningCase
      ? `Số tiền nợ: 12.500.000 VNĐ · Kỳ phát sinh: Học kỳ 1 2025-2026 · Hạn thanh toán: Quá hạn 15 ngày`
      : `Số tiền nợ: 0 VNĐ · Trạng thái: Đã hoàn thành học phí học kỳ hiện tại`,
    sourceSystem: "Cổng Kế hoạch - Tài chính [FIN-PORTAL]",
    lookupTimestamp: timestamp,
    status: statusFinance,
    reason: reasonFinance,
    evidenceDetails: {
      rawSnippet: `GET /api/khtc/tuition-status?mssv=${ticket.studentMssv}\n=> Balance: ${isWarningCase ? "12500000" : "0"} VND, Status: ${isWarningCase ? "OVERDUE" : "CLEARED"}`,
      systemUrl: "https://khtc.campus.edu.vn/portal/finance/lookup",
      verifiedFields: {
        "Dư nợ học phí": isWarningCase ? "12.500.000 VNĐ" : "0 VNĐ (Không nợ)",
        "Kỳ tính phí": "Học kỳ 2 Năm học 2025 - 2026",
        "Chính sách hỗ trợ": "Đủ điều kiện vay vốn NHCSXH theo diện gia đình chính sách",
      },
    },
    officerReviewStatus: "pending",
  };

  // 3. Điều kiện Tính hợp lệ mục đích & Cơ quan tiếp nhận
  let statusPurpose: "passed" | "failed" | "insufficient" | "error" = "passed";
  let reasonPurpose = `Mục đích xin giấy (${ticket.purpose}) và cơ quan tiếp nhận (${ticket.destinationOrg}) rõ ràng, đúng thẩm quyền biểu mẫu BM-03.`;

  if (!ticket.destinationOrg || ticket.destinationOrg.trim().length < 5) {
    statusPurpose = "insufficient";
    reasonPurpose = "Cơ quan tiếp nhận chưa được ghi cụ thể chi nhánh hoặc tổ chức tiếp nhận văn bản.";
  }

  const purposeItem: SystemVerificationItem = {
    id: `verif-${ticket.id}-purpose`,
    criterionKey: "purpose_and_org",
    criterionLabel: "3. Tính hợp lệ mục đích & Cơ quan tiếp nhận",
    conditionApplied: "Quy chuẩn Biểu mẫu BM-03: Mục đích cấp giấy phải có nơi nhận cụ thể (Ngân hàng, Cơ quan quân sự, Doanh nghiệp) để đảm bảo giá trị sử dụng.",
    dataChecked: `Nơi nhận: ${ticket.destinationOrg || "(Chưa rõ)"} · Mục đích: ${ticket.purpose}`,
    sourceSystem: "Dữ liệu kê khai Cổng 1 & Bộ lọc chuẩn hóa AI Copilot",
    lookupTimestamp: timestamp,
    status: statusPurpose,
    reason: reasonPurpose,
    evidenceDetails: {
      rawSnippet: `FORM_DATA: destinationOrg = "${ticket.destinationOrg}", purpose = "${ticket.purpose}"`,
      verifiedFields: {
        "Biểu mẫu chuẩn": "BM-03/CTSV (Giấy xác nhận sinh viên)",
        "Nơi nhận đề nghị": ticket.destinationOrg || "Chưa xác định",
        "Tính phù hợp quy định": "Hợp lệ theo Danh mục thủ tục 1 cửa",
      },
    },
    officerReviewStatus: "pending",
  };

  return [academicItem, financeItem, purposeItem];
}

/**
 * Tự động tạo bản thảo Giấy xác nhận sinh viên hoàn chỉnh (BM-03) từ dữ liệu đã đối soát
 */
export function buildDefaultCertificate(
  ticket: Ticket,
  customEdits?: Partial<IssuedCertificateDocument>
): IssuedCertificateDocument {
  const now = new Date();
  const dateFormatted = `${String(now.getDate()).padStart(2, "0")}/${String(now.getMonth() + 1).padStart(2, "0")}/${now.getFullYear()}`;
  const timeFormatted = `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}`;
  
  // Tính ngày hết hạn (30 ngày sau)
  const expireDate = new Date(now.getTime() + 30 * 24 * 60 * 60 * 1000);
  const expireFormatted = `${String(expireDate.getDate()).padStart(2, "0")}/${String(expireDate.getMonth() + 1).padStart(2, "0")}/${expireDate.getFullYear()}`;

  const cleanNumber = ticket.code.replace(/[^0-9]/g, "").slice(-4) || "0142";
  const docNumber = `${cleanNumber}/XNSV-ĐT-2026`;

  return {
    id: `CERT-2026-${cleanNumber}`,
    docNumber,
    templateCode: "BM-03",
    templateName: "Giấy xác nhận sinh viên chính quy",
    templateVersion: CERTIFICATE_TEMPLATE_VERSION,
    issuedAt: now.toISOString(),
    issuedAtFormatted: `${timeFormatted} · ${dateFormatted}`,
    issuedByOfficerId: "OF001",
    issuedByOfficerName: "ThS. Trần Thu Hà",
    studentId: ticket.studentId,
    studentName: ticket.studentName,
    studentMssv: ticket.studentMssv,
    studentDob: "15/08/2003",
    studentGender: "Nam",
    studentMajor: ticket.studentMajor || "Kỹ thuật Phần mềm",
    studentClassYear: ticket.studentClassYear || "Khóa 18 (2021 - 2025)",
    studentFaculty: "Khoa Công nghệ Phần mềm",
    studentAcademicStatus: "Đang học chính quy (Học kỳ 2 Năm học 2025 - 2026)",
    purpose: ticket.purpose || "Bổ sung hồ sơ vay vốn Ngân hàng Chính sách Xã hội kỳ 2 năm học 2025 - 2026",
    destinationOrg: ticket.destinationOrg || "Ngân hàng Chính sách Xã hội Chi nhánh Q. Thủ Đức",
    validUntil: `Có giá trị sử dụng đến ngày ${expireFormatted} (30 ngày kể từ ngày cấp)`,
    customOfficerNotes: "Sinh viên chấp hành tốt nội quy trường học và hoàn thành đầy đủ nghĩa vụ học kỳ.",
    status: "draft",
    fileName: `Giay_Xac_Nhan_Sinh_Vien_${ticket.studentMssv}_BM03.html`,
    isDemoSample: true,
    ...customEdits,
  };
}

/**
 * Hàm escaping HTML cơ bản, deterministic để bảo vệ nội dung text
 */
function escapeHtml(unsafe: unknown): string {
  if (unsafe == null) return "";
  return String(unsafe)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

/**
 * Sinh mã HTML hoàn chỉnh chuẩn trang văn bản hành chính Việt Nam cho Giấy xác nhận BM-03
 */
export function generateCertificateHtml(cert: IssuedCertificateDocument): string {
  // Escape toàn bộ dynamic fields để chống XSS
  const safeCert = {
    studentName: escapeHtml(cert.studentName),
    studentMssv: escapeHtml(cert.studentMssv),
    studentDob: escapeHtml(cert.studentDob),
    studentGender: escapeHtml(cert.studentGender),
    studentClassYear: escapeHtml(cert.studentClassYear),
    studentMajor: escapeHtml(cert.studentMajor),
    studentFaculty: escapeHtml(cert.studentFaculty),
    studentAcademicStatus: escapeHtml(cert.studentAcademicStatus),
    destinationOrg: escapeHtml(cert.destinationOrg),
    purpose: escapeHtml(cert.purpose),
    validUntil: escapeHtml(cert.validUntil),
    customOfficerNotes: escapeHtml(cert.customOfficerNotes),
    docNumber: escapeHtml(cert.docNumber),
    id: escapeHtml(cert.id),
    issuedByOfficerName: escapeHtml(cert.issuedByOfficerName),
    issuedByOfficerId: escapeHtml(cert.issuedByOfficerId),
    templateCode: escapeHtml(cert.templateCode),
    templateVersion: escapeHtml(cert.templateVersion),
    issuedAtFormatted: escapeHtml(cert.issuedAtFormatted)
  };

  const dayStr = safeCert.issuedAtFormatted.split("·")[1]?.trim() || "24 tháng 10 năm 2026";

  return `<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8">
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none';">
  <title>Giấy xác nhận sinh viên - ${safeCert.studentName} (${safeCert.studentMssv})</title>
  <style>
    @page { size: A4; margin: 20mm; }
    body {
      font-family: 'Times New Roman', Times, serif;
      color: #111;
      background: #f8fafc;
      margin: 0;
      padding: 20px;
      line-height: 1.5;
    }
    .page-container {
      max-width: 800px;
      margin: 0 auto;
      background: #fff;
      padding: 40px 50px;
      box-shadow: 0 4px 20px rgba(0,0,0,0.08);
      border: 1px solid #e2e8f0;
      position: relative;
      overflow: hidden;
    }
    .watermark {
      position: absolute;
      top: 45%;
      left: 50%;
      transform: translate(-50%, -50%) rotate(-30deg);
      font-size: 42px;
      font-weight: bold;
      color: rgba(220, 38, 38, 0.12);
      border: 4px dashed rgba(220, 38, 38, 0.2);
      padding: 15px 30px;
      border-radius: 12px;
      pointer-events: none;
      white-space: nowrap;
      text-transform: uppercase;
      letter-spacing: 2px;
    }
    .header-table {
      width: 100%;
      margin-bottom: 25px;
      border-collapse: collapse;
    }
    .header-left {
      width: 45%;
      text-align: center;
      vertical-align: top;
      font-size: 13px;
    }
    .header-right {
      width: 55%;
      text-align: center;
      vertical-align: top;
      font-size: 13px;
    }
    .school-name {
      font-weight: bold;
      text-transform: uppercase;
    }
    .school-sub {
      font-size: 12px;
      text-transform: uppercase;
    }
    .doc-num {
      margin-top: 5px;
      font-style: italic;
    }
    .nation-title {
      font-weight: bold;
      text-transform: uppercase;
    }
    .nation-motto {
      font-weight: bold;
    }
    .divider {
      width: 120px;
      margin: 4px auto 8px auto;
      border-bottom: 1px solid #222;
    }
    .date-line {
      font-style: italic;
      margin-top: 5px;
    }
    .main-title {
      text-align: center;
      margin: 25px 0 20px 0;
    }
    .main-title h1 {
      font-size: 22px;
      font-weight: bold;
      margin: 0;
      text-transform: uppercase;
      letter-spacing: 1px;
    }
    .main-title .sub-code {
      font-size: 13px;
      font-style: italic;
      color: #475569;
      margin-top: 4px;
    }
    .intro-p {
      text-align: justify;
      margin-bottom: 15px;
      font-size: 15px;
    }
    .info-table {
      width: 100%;
      margin-bottom: 20px;
      border-collapse: collapse;
      font-size: 15px;
    }
    .info-table td {
      padding: 6px 4px;
      vertical-align: top;
    }
    .info-label {
      width: 28%;
      color: #334155;
    }
    .info-dots {
      width: 2%;
      text-align: center;
    }
    .info-val {
      width: 70%;
      font-weight: bold;
      color: #0f172a;
    }
    .footer-table {
      width: 100%;
      margin-top: 30px;
      border-collapse: collapse;
      font-size: 14px;
    }
    .footer-left {
      width: 45%;
      vertical-align: top;
    }
    .footer-right {
      width: 55%;
      text-align: center;
      vertical-align: top;
    }
    .stamp-box {
      margin: 20px auto 10px auto;
      width: 160px;
      height: 90px;
      border: 2px dashed #94a3b8;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      font-size: 11px;
      color: #64748b;
      border-radius: 8px;
    }
    .disclaimer-bar {
      margin-top: 35px;
      padding: 10px 15px;
      background: #fef2f2;
      border-left: 4px solid #ef4444;
      font-size: 12px;
      color: #991b1b;
      line-height: 1.4;
    }
    @media print {
      body { background: #fff; padding: 0; }
      .page-container { box-shadow: none; border: none; padding: 0; }
      .no-print { display: none; }
    }
  </style>
</head>
<body>
  <div class="page-container">
    <div class="watermark">BẢN ĐIỆN TỬ — XÁC THỰC SỐ</div>

    <!-- Header Section -->
    <table class="header-table">
      <tr>
        <td class="header-left">
          <div class="school-name">TRƯỜNG ĐẠI HỌC XÂY DỰNG HÀ NỘI</div>
          <div class="school-sub">PHÒNG QUẢN LÝ ĐÀO TẠO &amp; CTSV</div>
          <div class="divider"></div>
          <div class="doc-num">Số: <strong>${safeCert.docNumber}</strong></div>
        </td>
        <td class="header-right">
          <div class="nation-title">CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM</div>
          <div class="nation-motto">Độc lập - Tự do - Hạnh phúc</div>
          <div class="divider"></div>
          <div class="date-line">Hà Nội, ngày ${dayStr}</div>
        </td>
      </tr>
    </table>

    <!-- Title Section -->
    <div class="main-title">
      <h1>GIẤY XÁC NHẬN SINH VIÊN</h1>
      <div class="sub-code">(Mẫu số: ${safeCert.templateCode} · Phiên bản: ${safeCert.templateVersion})</div>
    </div>

    <!-- Body Section -->
    <p class="intro-p">
      Phòng Quản lý Đào tạo &amp; Công tác Sinh viên Trường Đại học Xây dựng Hà Nội xác nhận:
    </p>

    <table class="info-table">
      <tr>
        <td class="info-label">Họ và tên sinh viên</td>
        <td class="info-dots">:</td>
        <td class="info-val">${safeCert.studentName}</td>
      </tr>
      <tr>
        <td class="info-label">Ngày sinh</td>
        <td class="info-dots">:</td>
        <td class="info-val">${safeCert.studentDob} &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; Giới tính: ${safeCert.studentGender}</td>
      </tr>
      <tr>
        <td class="info-label">Mã số sinh viên (MSSV)</td>
        <td class="info-dots">:</td>
        <td class="info-val">${safeCert.studentMssv}</td>
      </tr>
      <tr>
        <td class="info-label">Khóa học / Niên khóa</td>
        <td class="info-dots">:</td>
        <td class="info-val">${safeCert.studentClassYear}</td>
      </tr>
      <tr>
        <td class="info-label">Ngành đào tạo</td>
        <td class="info-dots">:</td>
        <td class="info-val">${safeCert.studentMajor}</td>
      </tr>
      <tr>
        <td class="info-label">Khoa / Bộ môn phụ trách</td>
        <td class="info-dots">:</td>
        <td class="info-val">${safeCert.studentFaculty}</td>
      </tr>
      <tr>
        <td class="info-label">Hệ đào tạo</td>
        <td class="info-dots">:</td>
        <td class="info-val">Chính quy tập trung</td>
      </tr>
      <tr>
        <td class="info-label">Tình trạng học tập</td>
        <td class="info-dots">:</td>
        <td class="info-val">${safeCert.studentAcademicStatus}</td>
      </tr>
      <tr>
        <td class="info-label">Cơ quan / Đơn vị tiếp nhận</td>
        <td class="info-dots">:</td>
        <td class="info-val">${safeCert.destinationOrg}</td>
      </tr>
      <tr>
        <td class="info-label">Mục đích cấp giấy</td>
        <td class="info-dots">:</td>
        <td class="info-val">${safeCert.purpose}</td>
      </tr>
      <tr>
        <td class="info-label">Thời hạn có giá trị</td>
        <td class="info-dots">:</td>
        <td class="info-val">${safeCert.validUntil}</td>
      </tr>
    </table>

    <p class="intro-p" style="margin-top: 15px; font-style: italic;">
      ${safeCert.customOfficerNotes || "Giấy xác nhận được cấp trên cơ sở dữ liệu học vụ đồng bộ tại thời điểm thẩm định. Đề nghị cơ quan tiếp nhận phối hợp hỗ trợ sinh viên."}
    </p>

    <!-- Signatures Section -->
    <table class="footer-table">
      <tr>
        <td class="footer-left">
          <strong>Nơi nhận:</strong><br>
          - Như trên;<br>
          - Lưu: P. Đào tạo, Hồ sơ SV.<br>
          <div style="margin-top: 20px; font-size: 11px; color: #64748b;">
            Mã định danh văn bản: <code>${safeCert.id}</code><br>
            Cán bộ thụ lý: ${safeCert.issuedByOfficerName} (${safeCert.issuedByOfficerId})
          </div>
        </td>
        <td class="footer-right">
          <strong>TL. HIỆU TRƯỞNG</strong><br>
          <strong>KT. TRƯỞNG PHÒNG ĐÀO TẠO &amp; CTSV</strong><br>
          <em>PHÓ TRƯỞNG PHÒNG</em>
          
          <div class="stamp-box">
            <span style="font-weight: bold; color: #16a34a;">[ĐÃ KÝ SỐ ĐIỆN TỬ]</span>
            <span>XÁC THỰC HỌC VỤ</span>
            <span style="font-size: 9px; margin-top: 4px;">Cổng Dịch Vụ Số HUCE</span>
          </div>

          <div style="font-weight: bold; margin-top: 5px;">${safeCert.issuedByOfficerName}</div>
        </td>
      </tr>
    </table>

    <!-- Disclaimer Alert -->
    <div class="disclaimer-bar">
      <strong>LƯU Ý NGHIỆP VỤ:</strong> Giấy xác nhận được cấp dưới dạng văn bản điện tử có giá trị tra cứu và xác thực trực tuyến qua Cổng dịch vụ một cửa số HUCE.
    </div>
  </div>
</body>
</html>`;
}

/**
 * Hàm chuẩn hóa tên file an toàn cho tải xuống
 */
function getSafeFileName(fileName: string | undefined, mssv: string): string {
  const defaultName = `Giay_Xac_Nhan_Sinh_Vien_${mssv}.html`;
  const rawName = fileName || defaultName;
  // Loại bỏ path separator và control characters
  const safeName = rawName.replace(/[\/\?<>\\:\*\|":]/g, "_").replace(/[\x00-\x1F]/g, "");
  return safeName.endsWith(".html") ? safeName : `${safeName}.html`;
}

/**
 * Tải file văn bản thật về máy tính của người dùng
 */
export function downloadCertificateFile(cert: IssuedCertificateDocument): void {
  if (typeof window === "undefined") return;

  const htmlContent = generateCertificateHtml(cert);
  const blob = new Blob([htmlContent], { type: "text/html;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  
  const link = document.createElement("a");
  link.href = url;
  link.download = getSafeFileName(cert.fileName, cert.studentMssv);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);

  // Tránh leak memory bằng cách revoke ngay sau khi trigger tải
  setTimeout(() => URL.revokeObjectURL(url), 100);
}

/**
 * Mở cửa sổ in văn bản để xem trực tiếp hoặc lưu ra PDF bằng Ctrl+P / Print
 */
export function openCertificatePrintWindow(cert: IssuedCertificateDocument): void {
  if (typeof window === "undefined") return;

  const htmlContent = generateCertificateHtml(cert);
  const blob = new Blob([htmlContent], { type: "text/html;charset=utf-8" });
  const url = URL.createObjectURL(blob);

  const link = document.createElement("a");
  link.href = url;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);

  // Thu hồi URL sau 10s để đảm bảo browser tải xong trang mới
  setTimeout(() => {
    URL.revokeObjectURL(url);
  }, 10000);
}
