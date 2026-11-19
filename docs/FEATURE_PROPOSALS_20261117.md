# Đề xuất tính năng chuyên nghiệp — Campus 24/7 (17/11/2026)

Trạng thái: đề xuất, chưa triển khai. Căn cứ: README, các báo cáo `PROJECT_AUDIT_20261111`,
`HUCE_INTEGRATION_READINESS_20261025`, `LEARNING_MATERIALS_AUDIT_20261117`, kế hoạch
`04-architecture/ROLLOUT_PLAN_LOCAL_THEN_CLOUD_20261115` và cấu trúc mã trong `services/api`,
`apps/web`, `infra/cloud`. Không lặp lại các đề xuất trong `ASSISTANT_ADVANCED_PROPOSAL_20261014`
và `ASSISTANT_PERSONALIZATION_PROPOSAL_20261014`.

Thiết kế chi tiết: [nhóm A](GROUP_A_IMPLEMENTATION_PLAN_20261117.md) · [nhóm B](GROUP_B_DESIGN_20261117.md) ·
[nhóm C](GROUP_C_DESIGN_20261117.md). Task làm được ngay: [FEATURE_READY_TASKS_20261117.md](FEATURE_READY_TASKS_20261117.md).

## Nhóm A — Nền tảng để dùng thật (ưu tiên cao)

| # | Tính năng | Vì sao cần |
|---|---|---|
| A1 | Đăng nhập SSO (OIDC; SAML nếu HUCE chỉ hỗ trợ SAML) qua `IdentityProviderPort` | Runtime chỉ có tài khoản local; chưa có thông tin SSO/API học vụ từ HUCE. |
| A2 | Bảng điều khiển vận hành cho quản trị | `/v1/admin/overview` chỉ có ticket, đặt phòng, audit; chưa có độ trễ, 503, vector, chi phí, sức khỏe model. |
| A3 | Giám sát và cảnh báo chủ động | Các tín hiệu (`chat_admission_rejected`, `rag_v2_vector_stats`, `loop_blocked`, bộ đếm gateway) chỉ nằm trong log. |
| A4 | Sao lưu ngoài máy và diễn tập khôi phục tự động | Kit `infra/cloud/backup.py` đã có backup/verify/restore hằng ngày trên cùng ổ đĩa; còn thiếu bản ngoài server có mã hóa và diễn tập định kỳ. |
| A5 | CI và môi trường kiểm thử tái lập | AUD-003 (môi trường `testing` vs `test`) còn; CI không cấp `LEARNING_TEST_ROOT`, đường import worker, và chỉ chạy trên `main`. |

## Nhóm B — Giá trị cho sinh viên

| # | Tính năng | Mô tả |
|---|---|---|
| B1 | Lịch và nhắc hạn | Lịch học/thi/hạn hồ sơ, xuất `.ics`, nhắc trước hạn. Dữ liệu lịch hiện là tổng hợp; cần dữ liệu thật sau A1. |
| B2 | PWA và web push | Cài lên điện thoại, nhận nhắc việc. |
| B3 | Ôn tập từ học liệu | Câu hỏi ôn tập sinh từ tài liệu đã duyệt, gắn nguồn theo trang, giảng viên duyệt trước; lặp lại ngắt quãng. Gọi AI theo cổng trả phí hiện hành. |
| B4 | Anh/Việt | Dịch giao diện và câu trả lời, giữ trích dẫn gốc tiếng Việt; đo truy hồi chéo ngôn ngữ trước khi bật. |

## Nhóm C — Chất lượng AI và vòng phản hồi

| # | Tính năng | Mô tả |
|---|---|---|
| C1 | Hàng đợi "lỗ hổng tri thức" | Gom câu bị từ chối/đánh giá kém (`AnswerFeedback`) theo chủ đề, gợi ý nguồn thiếu, đưa vào luồng duyệt kho. |
| C2 | Hồi quy chất lượng định kỳ | Bản rút gọn của `rag_regression_gate.py` chạy theo lịch, lưu xu hướng, cảnh báo khi tụt; trong trần chi phí hiện hành. |
| C3 | Cảnh báo nguồn lỗi thời | Hạn rà soát cho từng nguồn (12 nguồn chưa rõ khóa áp dụng), nhắc người phụ trách, câu trả lời ghi "nguồn có thể đã cũ". |

## Ràng buộc chung

- Không đổi RAG, model, index hoặc giới hạn 5 s của provider khi chưa hỏi chủ dự án (B4, C1, C2, C3 chạm vào phần này).
- Giai đoạn 2 (VPS) chỉ bắt đầu khi chủ dự án ra lệnh; không tự thuê dịch vụ hoặc chi tiền.
- Tích hợp HUCE thật cần tài liệu và quyền do trường cấp; phần chuẩn bị không được báo là đã tích hợp.
