/* eslint-disable @typescript-eslint/no-unused-vars */
import {
  ReviewCase,
  ReviewDocument,
  ReviewCriterion,
  ReviewFinding,
  SupplementRequest,
  User,
  EvidenceCitation,
} from "./types";

/**
 * Service AI rà soát hồ sơ học thuật minh bạch và có thể thay thế.
 * Vận hành deterministic quy trình 4 bước:
 * 1. Đọc tài liệu
 * 2. Trích thông tin
 * 3. Đối chiếu tiêu chí
 * 4. Chuẩn bị bản rà soát
 */

export interface AiProgressStep {
  step: number;
  label: string;
  description: string;
  status: "pending" | "processing" | "completed";
}

export const AI_PROGRESS_STEPS: AiProgressStep[] = [
  {
    step: 1,
    label: "Đọc & phân loại tài liệu",
    description: "Nhận diện đơn đề nghị, bảng điểm gốc và các phiên bản đề cương môn học.",
    status: "pending",
  },
  {
    step: 2,
    label: "Trích xuất thông tin cấu trúc",
    description: "Phân tách mã học phần, số tín chỉ, mục tiêu chuẩn đầu ra, đề cương chi tiết.",
    status: "pending",
  },
  {
    step: 3,
    label: "Đối chiếu ngữ nghĩa theo tiêu chí",
    description: "Tìm nội dung tương đương dù khác tên môn; đối soát điều kiện tín chỉ & thực hành.",
    status: "pending",
  },
  {
    step: 4,
    label: "Tổng hợp dẫn chứng & phát hiện",
    description: "Chỉ ra bằng chứng, phát hiện mâu thuẫn dữ liệu hoặc phần tài liệu chưa đủ căn cứ.",
    status: "pending",
  },
];

/**
 * Phân tích đối chiếu học phần giữa tài liệu và bộ tiêu chí
 */
export function compareCourseContent(
  caseItem: ReviewCase,
  documents: ReviewDocument[]
): {
  findings: ReviewFinding[];
  summary: ReviewCase["aiSummary"];
} {
  const syllabusOldDoc = documents.find((d) => d.type === "syllabus_old");
  const transcriptDoc = documents.find((d) => d.type === "transcript");
  const applicationDoc = documents.find((d) => d.type === "application");
  const targetSyllabusDoc = documents.find((d) => d.type === "syllabus_target");

  const latestSyllabusVersion = syllabusOldDoc
    ? syllabusOldDoc.versions.find((v) => v.version === syllabusOldDoc.currentVersion)
    : undefined;

  const isSyllabusV2 = (latestSyllabusVersion?.version || 1) >= 2;
  const isSyllabusBlurry = latestSyllabusVersion?.legibility === "partial_blurry";

  // Check data contradiction in Case B
  const hasCodeContradiction = caseItem.code === "REV-2026-002" || (
    caseItem.priorCourseCode === "TCC-A1-2023" &&
    latestSyllabusVersion?.sections.some((s) => s.content.includes("MAT-102-K45"))
  );

  const updatedFindings: ReviewFinding[] = caseItem.criteria.map((crit) => {
    // Keep existing officer edits if present
    const existing = caseItem.findings.find((f) => f.criterionId === crit.id);
    const officerStatus = existing?.officerStatus || "unverified";
    const officerAdjustedLabel = existing?.officerAdjustedLabel;
    const officerNote = existing?.officerNote;

    let aiLabel: ReviewFinding["aiLabel"] = "has_evidence";
    let aiExplanation = "";
    let extractedEvidence = "";
    let aiSuggestedAction = "";
    const citations: EvidenceCitation[] = [];

    switch (crit.code) {
      case "C1_CREDITS": {
        // Tiêu chí số tín chỉ
        extractedEvidence = `Bảng điểm ghi nhận: ${caseItem.priorCourseCredits} tín chỉ lý thuyết & thực hành (Điểm: ${caseItem.priorGrade}).`;
        if (caseItem.priorCourseCredits >= caseItem.targetCourseCredits) {
          aiLabel = "has_evidence";
          aiExplanation = `Số tín chỉ môn đã học (${caseItem.priorCourseCredits} TC) đạt yêu cầu tối thiểu so với học phần tại trường tiếp nhận (${caseItem.targetCourseCredits} TC).`;
        } else {
          aiLabel = "has_difference";
          aiExplanation = `Số tín chỉ môn đã học (${caseItem.priorCourseCredits} TC) thấp hơn học phần trường tiếp nhận (${caseItem.targetCourseCredits} TC).`;
          aiSuggestedAction = "Chuyển Hội đồng xem xét học bổ sung chuyên đề hoặc từ chối công nhận.";
        }
        if (transcriptDoc) {
          citations.push({
            documentId: transcriptDoc.id,
            documentTitle: transcriptDoc.title,
            version: transcriptDoc.currentVersion,
            pageNumber: 1,
            sectionTitle: "Bảng kết quả học tập",
            snippet: `${caseItem.priorCourseName} - Số tín chỉ: ${caseItem.priorCourseCredits} - Điểm: ${caseItem.priorGrade}`,
          });
        }
        break;
      }

      case "C2_CODE_CONSISTENCY": {
        // Tiêu chí tính nhất quán mã học phần (Hồ sơ B)
        if (hasCodeContradiction) {
          aiLabel = "contradiction";
          extractedEvidence = `Bảng điểm ghi: "${caseItem.priorCourseCode} - ${caseItem.priorCourseName}". Tuy nhiên, Đề cương chi tiết nộp lại ghi: "Mã môn: MAT-102-K45 - Toán giải tích ứng dụng".`;
          aiExplanation = `DỮ LIỆU MÂU THUẪN: Có sự sai lệch giữa mã học phần trên Bảng điểm chính thức (${caseItem.priorCourseCode}) và mã trên Đề cương chi tiết (MAT-102-K45). Không thể tự ý suy luận hai học phần này là một mà cần xác nhận từ trường cấp bảng điểm.`;
          aiSuggestedAction = "Yêu cầu sinh viên xin giấy xác nhận tương đương mã môn của Phòng Đào tạo trường cũ.";
          if (transcriptDoc) {
            citations.push({
              documentId: transcriptDoc.id,
              documentTitle: transcriptDoc.title,
              version: transcriptDoc.currentVersion,
              pageNumber: 1,
              sectionTitle: "Bảng kết quả học tập chính thức",
              snippet: `${caseItem.priorCourseCode} | Toán cao cấp A1 | 3 tín chỉ | Điểm 8.0 (B+)`,
            });
          }
          if (syllabusOldDoc) {
            citations.push({
              documentId: syllabusOldDoc.id,
              documentTitle: syllabusOldDoc.title,
              version: syllabusOldDoc.currentVersion,
              pageNumber: 1,
              sectionTitle: "Thông tin chung học phần",
              snippet: "Mã học phần: MAT-102-K45. Tên học phần: Toán giải tích ứng dụng. Khóa áp dụng: K45 trở đi.",
            });
          }
        } else {
          aiLabel = "has_evidence";
          extractedEvidence = `Mã học phần và tên môn khớp nhất quán giữa Bảng điểm và Đề cương chi tiết (${caseItem.priorCourseCode} - ${caseItem.priorCourseName}).`;
          aiExplanation = "Thông tin định danh học phần đồng nhất trên toàn bộ hồ sơ.";
          if (transcriptDoc) {
            citations.push({
              documentId: transcriptDoc.id,
              documentTitle: transcriptDoc.title,
              version: transcriptDoc.currentVersion,
              pageNumber: 1,
              sectionTitle: "Bảng kết quả học tập",
              snippet: `${caseItem.priorCourseCode} - ${caseItem.priorCourseName}`,
            });
          }
        }
        break;
      }

      case "C3_CORE_DATA_STRUCT": {
        // Tiêu chí cấu trúc dữ liệu cơ bản (Hồ sơ A)
        extractedEvidence = "Đề cương thể hiện các nội dung: Mảng động, Danh sách liên kết đơn/kép, Ngăn xếp (Stack), Hàng đợi (Queue), Cây nhị phân tìm kiếm (BST).";
        aiLabel = "has_evidence";
        aiExplanation = "Nội dung cấu trúc dữ liệu cốt lõi tương ứng 90% với yêu cầu học phần tiếp nhận (IT3011). Dù tên môn là 'Cấu trúc dữ liệu' thay vì 'Cấu trúc dữ liệu và giải thuật', các khối kiến thức nền tảng hoàn toàn tương thích.";
        if (syllabusOldDoc) {
          citations.push({
            documentId: syllabusOldDoc.id,
            documentTitle: syllabusOldDoc.title,
            version: syllabusOldDoc.currentVersion,
            pageNumber: 2,
            sectionTitle: "Chương 2 & Chương 3: Cấu trúc dữ liệu tuyến tính và cây",
            snippet: "Chương 2: Danh sách liên kết đơn, kép. Ngăn xếp và Hàng đợi ứng dụng trong quản lý tiến trình. Chương 3: Cây nhị phân và Cây nhị phân tìm kiếm (BST).",
          });
        }
        break;
      }

      case "C4_GRAPH_ALGORITHMS": {
        // Tiêu chí đồ thị và thuật toán duyệt (Hồ sơ A - mấu chốt v1 vs v2)
        if (isSyllabusV2) {
          aiLabel = "has_evidence";
          extractedEvidence = "Đề cương v2 (bổ sung có dấu Khoa CNTT) bổ sung Chương 5: Đồ thị. Gồm: Biểu diễn đồ thị, Duyệt đồ thị theo chiều rộng (BFS), duyệt theo chiều sâu (DFS), Cây khung nhỏ nhất Prim/Kruskal, Đường đi ngắn nhất Dijkstra (Tổng 12 tiết).";
          aiExplanation = "BẰNG CHỨNG ĐÃ ĐẦY ĐỦ: Bản đề cương chi tiết v2 cập nhật đã thể hiện rõ ràng toàn bộ các thuật toán đồ thị cơ bản và nâng cao, đáp ứng chuẩn đầu ra của IT3011.";
          if (syllabusOldDoc) {
            citations.push({
              documentId: syllabusOldDoc.id,
              documentTitle: syllabusOldDoc.title,
              version: 2,
              pageNumber: 4,
              sectionTitle: "Chương 5: Đồ thị và các thuật toán trên đồ thị (Bổ sung v2)",
              snippet: "Mục 5.2: Thuật toán duyệt đồ thị BFS, DFS và ứng dụng kiểm tra tính liên thông. Mục 5.3: Tìm đường đi ngắn nhất đồ thị có trọng số với thuật toán Dijkstra.",
            });
          }
        } else {
          aiLabel = "insufficient_evidence";
          extractedEvidence = "Đề cương v1 tại Mục 4.3 chỉ ghi khái quát 'Các cấu trúc phi tuyến tính khác (03 tiết)'. Không có đề mục chi tiết về đồ thị, thuật toán duyệt BFS, DFS hay Dijkstra.";
          aiExplanation = "CHƯA ĐỦ CĂN CỨ: Nội dung đồ thị và thuật toán duyệt đồ thị là chuẩn đầu ra bắt buộc của IT3011. Đề cương hiện tại chưa thể hiện đủ thời lượng và nội dung giảng dạy phần này.";
          aiSuggestedAction = "Yêu cầu sinh viên nộp Đề cương chi tiết có đóng dấu xác nhận của Bộ môn/Khoa trường cũ về nội dung Chương Đồ thị.";
          if (syllabusOldDoc) {
            citations.push({
              documentId: syllabusOldDoc.id,
              documentTitle: syllabusOldDoc.title,
              version: 1,
              pageNumber: 3,
              sectionTitle: "Mục 4.3: Giới thiệu cấu trúc nâng cao",
              snippet: "Mục 4.3: Khái quát các dạng cấu trúc dữ liệu nâng cao khác (3 tiết) - không liệt kê chi tiết nội dung đồ thị hoặc giải thuật tìm kiếm trên đồ thị.",
            });
          }
        }
        break;
      }

      case "C5_LAB_PRACTICE": {
        // Tiêu chí thực hành lập trình
        if (isSyllabusBlurry) {
          aiLabel = "insufficient_evidence";
          extractedEvidence = "Tài liệu đề cương scan bị mờ từ trang 2 đến trang 3, không thể đọc được phân bổ số giờ thực hành phòng máy và hình thức kiểm tra lab.";
          aiExplanation = "TÀI LIỆU CHƯA ĐỌC ĐƯỢC: Chất lượng scan độ phân giải thấp (bị bóng mờ & mất nét) tại phần Đề cương thực hành. AI không tự ý suy đoán đủ điều kiện.";
          aiSuggestedAction = "Yêu cầu sinh viên nộp lại bản scan chất lượng cao hoặc bản sao có chứng thực rõ nét.";
          if (syllabusOldDoc) {
            citations.push({
              documentId: syllabusOldDoc.id,
              documentTitle: syllabusOldDoc.title,
              version: syllabusOldDoc.currentVersion,
              pageNumber: 2,
              sectionTitle: "Trang 2: Đề cương thực hành phòng Lab [Chất lượng scan kém]",
              snippet: "[Văn bản bị mờ / Độ phân giải thấp - Không thể trích xuất tự động mục 2.3 và tiêu chí chấm lab]",
            });
          }
        } else {
          extractedEvidence = "Đề cương quy định: 30 tiết lý thuyết + 15 tiết thực hành phòng máy trên ngôn ngữ C++/Java; có 02 bài kiểm tra lab chiếm 30% tổng điểm.";
          aiLabel = "has_evidence";
          aiExplanation = "Học phần có phân bổ thực hành lập trình tương đương với quy chuẩn đào tạo kỹ thuật phần mềm của trường tiếp nhận.";
          if (syllabusOldDoc) {
            citations.push({
              documentId: syllabusOldDoc.id,
              documentTitle: syllabusOldDoc.title,
              version: syllabusOldDoc.currentVersion,
              pageNumber: 1,
              sectionTitle: "Phần 3: Phương pháp giảng dạy và đánh giá",
              snippet: "Thời lượng: 30 tiết lý thuyết, 15 tiết bài tập lớn và thực hành phòng máy lập trình C++. Điểm thực hành chiếm 30% điểm quá trình.",
            });
          }
        }
        break;
      }

      case "C6_LEARNING_OUTCOMES": {
        // Tiêu chí Chuẩn đầu ra (CLO)
        if (isSyllabusBlurry) {
          aiLabel = "insufficient_evidence";
          extractedEvidence = "Không trích xuất được bảng chuẩn đầu ra (CLO) do trang 3 đề cương bị mất trang/mờ scan.";
          aiExplanation = "Chưa thể đối soát chuẩn đầu ra chi tiết với chương trình đào tạo của trường tiếp nhận do thiếu dữ liệu.";
          aiSuggestedAction = "Yêu cầu bổ sung trang 3 của đề cương chi tiết.";
        } else if (hasCodeContradiction) {
          aiLabel = "has_difference";
          extractedEvidence = "Chuẩn đầu ra trên đề cương MAT-102-K45 nhấn mạnh ứng dụng kinh tế lượng, trong khi MATH101 nhấn mạnh giải tích toán học thuần túy và chứng minh định lý.";
          aiExplanation = "Có sự khác biệt về hướng ứng dụng của chuẩn đầu ra giữa khối kinh tế và khối kỹ thuật/toán học.";
          aiSuggestedAction = "Cần ý kiến chuyên môn từ Bộ môn Toán về mức độ tương thích kiến thức nền tảng.";
        } else {
          aiLabel = "has_evidence";
          extractedEvidence = "Sinh viên đạt chuẩn đầu ra: Phân tích được độ phức tạp thời gian/không gian của thuật toán O(n), thiết kế được cấu trúc dữ liệu phù hợp với bài toán thực tế.";
          aiExplanation = "Chuẩn đầu ra tương thích trên 85% so với chuẩn đầu ra CLO1, CLO2, CLO3 của học phần IT3011.";
          if (syllabusOldDoc) {
            citations.push({
              documentId: syllabusOldDoc.id,
              documentTitle: syllabusOldDoc.title,
              version: syllabusOldDoc.currentVersion,
              pageNumber: 1,
              sectionTitle: "Mục 2: Mục tiêu và chuẩn đầu ra học phần",
              snippet: "CĐR 1: Nắm vững và phân tích độ phức tạp O(n), O(log n). CĐR 2: Vận dụng được danh sách, cây để cài đặt các giải thuật tìm kiếm, sắp xếp.",
            });
          }
        }
        break;
      }

      default: {
        extractedEvidence = "Đã đối chiếu thông tin trích xuất với hồ sơ đính kèm.";
        aiLabel = "has_evidence";
        aiExplanation = "Đáp ứng yêu cầu chung theo quy chế công nhận học phần.";
      }
    }

    return {
      id: existing?.id || `find-${crit.id}-${Date.now()}`,
      criterionId: crit.id,
      criterionTitle: crit.title,
      category: crit.category,
      targetRequirement: crit.targetRequirement,
      extractedEvidence,
      citations,
      aiLabel,
      aiExplanation,
      aiSuggestedAction,
      officerStatus,
      officerAdjustedLabel,
      officerNote,
      officerReviewedAt: existing?.officerReviewedAt,
      officerReviewedBy: existing?.officerReviewedBy,
    };
  });

  // Calculate summaries
  const matchCount = updatedFindings.filter((f) => f.aiLabel === "has_evidence").length;
  const differenceCount = updatedFindings.filter((f) => f.aiLabel === "has_difference").length;
  const insufficientCount = updatedFindings.filter((f) => f.aiLabel === "insufficient_evidence").length;
  const contradictionCount = updatedFindings.filter((f) => f.aiLabel === "contradiction").length;

  let overallRecommendation = "";
  if (contradictionCount > 0) {
    overallRecommendation = "Hồ sơ phát hiện mâu thuẫn dữ liệu giữa các chứng từ. Đề xuất cán bộ tạm dừng thẩm định và gửi yêu cầu xác minh mã học phần.";
  } else if (insufficientCount > 0) {
    overallRecommendation = `Hồ sơ có ${insufficientCount} nội dung chưa đủ căn cứ (do tài liệu mờ hoặc thiếu đề cương chi tiết). Đề xuất yêu cầu sinh viên bổ sung chứng từ trước khi trình Hội đồng.`;
  } else if (differenceCount > 0) {
    overallRecommendation = `Hồ sơ có ${differenceCount} điểm khác biệt cần chuyên môn xem xét. Các tiêu chí cốt lõi cơ bản đáp ứng.`;
  } else {
    overallRecommendation = "Toàn bộ các tiêu chí cơ bản có bằng chứng tương ứng rõ ràng trong tài liệu. Cán bộ có thể kiểm tra và hoàn tất phiếu rà soát để trình Hội đồng Học vụ.";
  }

  return {
    findings: updatedFindings,
    summary: {
      overallRecommendation,
      totalCriteria: caseItem.criteria.length,
      matchCount,
      differenceCount,
      insufficientCount,
      contradictionCount,
      isStale: false,
    },
  };
}

/**
 * Tạo dự thảo yêu cầu sinh viên bổ sung tài liệu dựa trên các vấn đề được chọn
 */
export function draftSupplementRequest(
  caseItem: ReviewCase,
  selectedFindingIds: string[]
): SupplementRequest {
  const involvedFindings = caseItem.findings.filter((f) => selectedFindingIds.includes(f.id));

  const requestedDocs: string[] = [];
  const bulletPoints: string[] = [];

  for (const f of involvedFindings) {
    if (f.aiLabel === "contradiction" || f.category === "credit") {
      requestedDocs.push("Văn bản xác nhận của Trường cũ về mã và tên học phần tương đương");
      bulletPoints.push(
        `- Đối với tiêu chí "${f.criterionTitle}": Đề nghị sinh viên cung cấp văn bản xác nhận từ Phòng Đào tạo trường cũ làm rõ sự sai lệch giữa mã học phần trên bảng điểm (${caseItem.priorCourseCode}) và mã trên đề cương.`
      );
    } else if (f.category === "core_content" || f.criterionTitle.includes("Đồ thị")) {
      requestedDocs.push("Đề cương chi tiết học phần (có đóng dấu xác nhận của Khoa/Bộ môn)");
      bulletPoints.push(
        `- Đối với nội dung "${f.criterionTitle}": Bản đề cương hiện tại chưa thể hiện đầy đủ thời lượng giảng dạy và bài tập về thuật toán Đồ thị (BFS, DFS, Dijkstra). Đề nghị bổ sung đề cương chi tiết có xác nhận của Khoa/Bộ môn chuyên ngành.`
      );
    } else if (f.aiLabel === "insufficient_evidence" && f.extractedEvidence.includes("mờ")) {
      requestedDocs.push("Bản scan màu độ phân giải cao hoặc bản sao có chứng thực của Đề cương chi tiết");
      bulletPoints.push(
        `- Đối với tiêu chí "${f.criterionTitle}": Bản scan hiện tại tại trang 2 và trang 3 bị mờ nét, không thể trích xuất nội dung thực hành và chuẩn đầu ra. Đề nghị gửi lại bản scan rõ nét.`
      );
    } else {
      bulletPoints.push(`- Đối với tiêu chí "${f.criterionTitle}": ${f.aiSuggestedAction || "Cần bổ sung minh chứng chi tiết."}`);
    }
  }

  // Deduplicate docs
  const uniqueDocs = Array.from(new Set(requestedDocs));
  if (uniqueDocs.length === 0) {
    uniqueDocs.push("Tài liệu bổ sung theo yêu cầu thẩm định chuyên môn");
  }

  const subject = `[Campus 24/7] Yêu cầu bổ sung hồ sơ đề nghị công nhận học phần: ${caseItem.targetCourseName} (${caseItem.targetCourseCode})`;

  const messageBody = `Chào bạn ${caseItem.studentName} (MSSV: ${caseItem.studentMssv}),

Phòng Đào tạo & CTSV đã thực hiện rà soát sơ bộ hồ sơ đề nghị công nhận học phần "${caseItem.targetCourseName}" (${caseItem.targetCourseCode}) của bạn tương đương với học phần đã học tại ${caseItem.priorInstitution}.

Để có đủ căn cứ trình Hội đồng Chuyên môn và Trưởng Bộ môn phê duyệt, đề nghị bạn bổ sung các chứng từ sau trước hạn chót:

${bulletPoints.join("\n\n")}

Danh mục tài liệu cần tải lên bổ sung:
${uniqueDocs.map((d, i) => `${i + 1}. ${d}`).join("\n")}

Bạn có thể tải tài liệu bổ sung trực tiếp tại mục "Hồ sơ rà soát học phần" trên Cổng Sinh viên (Campus 24/7). Sau khi nhận được bản bổ sung, Phòng Đào tạo sẽ tiếp tục hoàn tất quy trình thẩm định.

Trân trọng,
Bộ phận Tiếp nhận & Rà soát Hồ sơ Học vụ
Phòng Đào tạo & CTSV`;

  return {
    id: `sup-${Date.now()}`,
    createdAt: new Date().toISOString(),
    sentBy: "OF001",
    targetStudentId: caseItem.studentId,
    status: "draft",
    subject,
    messageBody,
    requestedDocuments: uniqueDocs,
    findingsInvolved: selectedFindingIds,
  };
}

/**
 * Tạo bản Phiếu rà soát học thuật chính thức (BM-RS-01) để lưu trữ và trình Hội đồng
 */
export function generateReviewReport(
  caseItem: ReviewCase,
  officer: User,
  recommendation: "propose_recognition" | "propose_conditional" | "propose_rejection",
  conclusionSummary: string
): NonNullable<ReviewCase["finalReport"]> {
  return {
    completedAt: new Date().toISOString(),
    officerId: officer.id,
    officerName: officer.name,
    decisionRecommendation: recommendation,
    conclusionSummary:
      conclusionSummary ||
      (recommendation === "propose_recognition"
        ? "Cán bộ đã kiểm tra toàn bộ các đối chiếu bằng chứng. Hồ sơ cơ bản đáp ứng các tiêu chuẩn cốt lõi về khối lượng tín chỉ, chuẩn đầu ra và đề cương chi tiết. Đề xuất chuyển Bộ môn chuyên môn thẩm định lần cuối."
        : recommendation === "propose_conditional"
        ? "Hồ sơ có một số nội dung khác biệt về cấu trúc học phần. Đề xuất Hội đồng xem xét công nhận có điều kiện (yêu cầu sinh viên học bổ sung bài tập lớn hoặc thi đánh giá năng lực)."
        : "Hồ sơ không đáp ứng điều kiện tiên quyết hoặc có mâu thuẫn chứng từ không thể khắc phục. Đề xuất từ chối công nhận học phần."),
    disclaimer:
      "Lưu ý pháp lý: Bản rà soát này được lập để lưu trữ và chuyển người có thẩm quyền (Hội đồng Học vụ / Trưởng bộ môn) xem xét; chưa phải là quyết định chính thức công nhận học phần hoặc cấp tín chỉ tích lũy.",
  };
}
