---
document_id: "DOC-PROD-000"
version: "1.2.0"
status: "approved"
owner: "Product Lead"
approvers: ["Product Owner", "Architecture Lead", "Security/Privacy Lead"]
last_updated: "2026-09-22"
---

# Product and requirements package

Kế hoạch hiện tại: [đồ án tốt nghiệp](../GRADUATION_PROJECT_PLAN_20261013.md). Nội dung sản phẩm bên dưới được giữ làm tài liệu tham khảo lịch sử. [Phạm vi và roadmap cũ](../../archive/legacy-plans-20261013/docs/01-product/SCOPE_AND_ROADMAP.md) đã chuyển nguyên vẹn vào khu lưu trữ; các ranh giới bảo vệ dữ liệu và bảo mật vẫn được giữ.

## 1. Mục đích và thẩm quyền

Thư mục này là nguồn sự thật cấp sản phẩm cho **Campus 24/7 — HUCE Demo**. `requirements.yaml` là nguồn chuẩn duy nhất cho 125 requirement (77 functional, 48 non-functional); hai Markdown requirement là bản diễn giải được đồng bộ từ catalog đó. Nó xác định lý do kinh doanh, phạm vi, người dùng, use case, KPI và các yêu cầu mà thiết kế, contract, test và micro-task triển khai phải truy vết tới.

Thứ tự ưu tiên khi có xung đột tuân theo `docs/README.md`. Agent triển khai MUST dừng và phát hành blocker nếu tài liệu cấp thấp hơn trái với requirement đã được phê duyệt; agent MUST NOT tự sửa requirement để làm cho code hiện tại trở nên hợp lệ.

## 2. Ranh giới bất biến của V1

- Sản phẩm là sản phẩm thương mại được thiết kế theo tiêu chuẩn production, nhưng V1 chỉ phục vụ **một trường đại học**.
- Ngữ cảnh tham chiếu là Khoa Công nghệ Thông tin, Trường Đại học Xây dựng Hà Nội; tên hiển thị là `HUCE Demo`.
- `HUCE Demo` là mô phỏng không chính thức. Mọi màn hình đăng nhập và vùng ứng dụng đã xác thực MUST hiển thị disclaimer theo `REQ-F-GOV-001`.
- Development, test và demo MUST chỉ dùng dữ liệu tổng hợp có thể tái tạo; MUST NOT dùng hồ sơ sinh viên thật.
- V1 MUST NOT triển khai SaaS, multi-tenancy, tenant onboarding, subscription billing hoặc thanh toán.
- DeepSeek là LLM provider đầu tiên nhưng không phải dependency của domain; yêu cầu chi tiết được giao cho kiến trúc và AI package.

## 3. Danh mục tài liệu

| Tài liệu | Mục đích |
|---|---|
| `PRODUCT_VISION.md` | Tầm nhìn, nguyên tắc và product outcomes |
| `COMMERCIAL_BUSINESS_CASE.md` | Giả thuyết thương mại, chi phí, lợi ích và điều kiện đầu tư |
| `PRD.md` | Product requirements document tổng thể |
| `PERSONAS_AND_ROLES.md` | Persona, role và boundary trách nhiệm |
| `USE_CASE_CATALOG.md` | Use case ưu tiên và luồng thành công/thất bại |
| `SCOPE_AND_NON_GOALS.md` | In-scope, future scope và non-goals |
| `KPI_CATALOG.md` | Công thức, nguồn dữ liệu và quality gate |
| `FUNCTIONAL_REQUIREMENTS.md` | Requirement chức năng nguyên tử |
| `NON_FUNCTIONAL_REQUIREMENTS.md` | Requirement phi chức năng đo được |
| [CAPABILITY_ROADMAP.md — lưu trữ](../../archive/legacy-plans-20261013/docs/01-product/CAPABILITY_ROADMAP.md) | Các phase và điều kiện thăng hạng của kế hoạch cũ |
| `REQUIREMENT_DEPENDENCY_MAP.md` | DAG requirement và downstream obligations |
| `requirements.yaml` | Bản machine-readable chuẩn cho orchestrator/agent |

## 4. Quy tắc dùng bởi coding agent

1. Agent MUST đọc `requirements.yaml` trước khi lập kế hoạch; Markdown chỉ hỗ trợ review của con người và MUST khớp catalog.
2. Agent MUST chỉ triển khai requirement có `status: approved` hoặc được task đã `ready` tham chiếu hợp lệ. Trạng thái hiện tại `reviewed` yêu cầu Product Owner phê duyệt trước khi tạo task `ready`.
3. Một micro-task MUST xử lý một hành vi kiểm thử được và không được tự mở rộng sang capability khác.
4. Mỗi task MUST ghi lại requirement IDs, acceptance criteria IDs, file thay đổi, lệnh kiểm chứng, exit code và residual risks.
5. Khi một `planned` design/contract/test reference chưa tồn tại, agent MUST dừng nếu task phụ thuộc vào reference đó; agent không được tự sáng tác contract.
6. Từ khóa MUST, MUST NOT, SHOULD và MAY mang nghĩa chuẩn RFC-style như quy định trong `docs/README.md`.

## 5. Quy tắc đồng bộ

- `requirements.yaml` là nguồn chuẩn. Markdown là biểu diễn giải thích được dẫn xuất; hai biểu diễn MUST có cùng 125 ID, statement, acceptance criteria, failure behavior, classification, priority và dependency.
- Thay đổi requirement là `Behavioral change`; MUST cập nhật đồng thời Markdown, YAML, dependency map và traceability downstream.
- Requirement bị loại bỏ MUST chuyển sang `superseded`; ID MUST NOT tái sử dụng.

## 6. Trạng thái phê duyệt

Gói tài liệu và danh mục yêu cầu sản phẩm (`DOC-PROD-012`) đã được Product Owner phê duyệt chính thức (`status: approved`) cho phạm vi triển khai mô phỏng dữ liệu tổng hợp (synthetic implementation) ngày 2026-09-22 theo quyết định của `TASK-DOC-GOV-001`. Ngữ nghĩa của 125 requirement (77 FR, 48 NFR) được bảo toàn nguyên vẹn. Các câu hỏi mở `OQ-001` đến `OQ-008` tiếp tục chặn launch với dữ liệu/người dùng thật và production; chúng không chặn simulated implementation.
