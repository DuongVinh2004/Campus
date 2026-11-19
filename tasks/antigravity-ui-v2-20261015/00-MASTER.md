# Chỉ đạo chung — Campus 24/7 UX/UI V2

Bạn là Antigravity 3.8 Flash, vai trò triển khai. Người dùng giao xây lại toàn bộ giao diện ngay trong code FE hiện tại. Cuộc chat chỉ đạo giữ vai trò đánh giá thiết kế và review kết quả; bạn tự hoàn thành các chi tiết kỹ thuật trong mỗi đợt.

## Mục tiêu và cách làm
Tạo trải nghiệm đại học hiện đại, chỉn chu, dễ hiểu và nhất quán từ trang chủ tới thao tác nghiệp vụ. Làm mới kiến trúc bố cục, phân cấp thông tin, điều hướng và component; không chỉ đổi màu/CSS trên layout cũ. Đọc code cũ để hiểu chức năng, contracts và edge cases.
Ứng dụng chính vẫn là apps/web. Không làm landing page/demo độc lập, bản HTML mẫu, dự án khác hay bản build nằm ở snapshot rồi gọi đó là kết quả.
Đích thẩm mỹ là chất lượng cao; không tự chấm “10/10”, tuyên bố toàn WCAG hoặc usability đã đạt nếu chưa kiểm chứng.

## Quyền thực thi và an toàn
- Thực hiện các sửa đổi UX/UI cần thiết, reversible và có diff. Không xin lại quyền cho từng tệp hoặc component.
- Tuân thủ AGENTS.md hiện hành và chính sách bảo vệ dữ liệu của người dùng. Hướng dẫn execution lịch sử không phải approval gates. Không dùng tasks/ANTIGRAVITY_REDESIGN_ORCHESTRATOR_PROMPT.md hay catalog cũ làm workflow bắt buộc.
- Canonical-check đường dẫn và symlink/junction, kiểm trạng thái Git trước/sau; giữ toàn bộ dirty/staged/untracked/ignored/deleted state có trước. Đọc tệp trước khi sửa; chỉ thay phần liên quan.
- Người dùng đã cho phép ngoại lệ tin cậy riêng repo cho việc đọc trạng thái/diff: git -c safe.directory="C:/Users/Duong Vinh/Vinh" --no-optional-locks status --short. Không sửa Git global config.
- Không xóa, reset, clean, restore, truncate, move/quarantine hoặc loại bỏ work có trước. Để thay UI, sửa code có chọn lọc và ngừng dùng phần cũ khi phù hợp; không cần xóa vật lý. Mọi thao tác phá hủy vẫn theo protocol bảo vệ dữ liệu.
- Không commit, push, deploy hoặc gửi dữ liệu/mã riêng ra dịch vụ ngoài. Không thay backend, contracts, database, auth/authorization, confirmation/idempotency, privacy consent, evidence/source verification hoặc safety controls.
- Không hiển thị success, receipt, lịch học/phòng/hồ sơ giả khi API lỗi. Không chạy write flow trên dữ liệu không xác định là fixture dùng cho kiểm thử. Giữ nội dung nháp khi lỗi.
- Giữ nguyên feature flags và cách chạy hiện tại. Chỉ dùng giá trị NEXT_PUBLIC_* cần thiết; không in secret/env toàn bộ. Không đổi port/kill runtime không rõ nguồn.

## Tình trạng dự án
Stack đã kiểm: Next.js + React + TypeScript + Tailwind v4 + Lucide; có Vitest, Testing Library và Playwright. Không cần đổi framework hoặc thêm dependency UI để hoàn thành.
Đọc apps/web/AGENTS.md. Với Next.js, đọc guide liên quan trong apps/web/node_modules/next/dist/docs, không áp API cũ từ trí nhớ.
Nguồn thiết kế mới: apps/web/DESIGN.md — tên Campus Studio; nền sáng #F6F7F9, ink #182C3A, teal #155E63, accent ochre nhỏ #D6A34A; Inter có tiếng Việt; dark mode đầy đủ. Được tinh chỉnh có lý do trong file này, không thay hướng thiết kế ở từng đợt.
UI UX Pro Max đã được xem xét từ repo nextlevelbuilder/ui-ux-pro-max-skill, nhưng chưa được cài/chạy trong workspace. Nếu dùng bản có sẵn, đọc SKILL.md và tra cứu ít, đúng mục tiêu; không tuyên bố đã dùng database nếu chưa chạy. Nếu chưa có, tiếp tục từ DESIGN.md, không mất một đợt chỉ để cài skill.
Không cần cấu hình hoặc upload lên Stitch. DESIGN.md dùng ngay cho implementation.

Snapshot trước khi thay shell:
.tooling/campus-ui-v2-20261015-01/frontend-before.zip
.tooling/campus-ui-v2-20261015-01/frontend-before.json
.tooling/campus-ui-v2-20261015-01/git-status-before.txt
Có thể đọc nội dung đúng tệp trong zip để đối chiếu bằng zipfile.read; không bung toàn bộ đè workspace.
Bản nháp hiện tại: AppShell đã đổi markup nhưng thiếu CSS campus-*, truyền initialFocusRef không tồn tại trong AccessibleDialog, publicKnowledge chưa xử lý. Sửa các vấn đề này ở đợt 01; không xóa hành vi cũ chỉ để build qua.

Kiểm tra sơ bộ đã chạy: tsc --noEmit --incremental false có lỗi kiểu trong một số test; Vitest báo 43/55 tệp pass, 251/302 test pass, có lỗi localStorage môi trường test và lỗi assertions khác. Việc chạy kiểm tra có thời gian giao nhau với lúc bắt đầu thay shell; không coi đây là baseline sạch trước mọi sửa đổi. Cần chạy/đối chiếu có scope, phân biệt lỗi mới, lỗi tồn tại và lỗi môi trường bằng bằng chứng. Không sửa test bằng cách bỏ assertion hoặc tắt kiểm tra.

## Bản đồ frontend để tìm đúng implementation
- /: src/app/page.tsx, AppShell.
- /login: src/app/login/page.tsx, AuthLayout; CERTIFICATE_DEMO dùng CertificateLogin trong CertificateWorkspace.
- /chat: src/app/chat/page.tsx; NEXT_PUBLIC_UNIFIED_AI chọn UnifiedAssistantWorkspace; ChatPanel và CitationDrawer là phần dùng chung.
- /tickets: app/tickets/page.tsx; CERTIFICATE_DEMO chọn CertificateWorkspace.
- /staff: app/staff/page.tsx; CERTIFICATE_DEMO chọn CertificateWorkspace staff.
- /services: app/services/page.tsx → features/documents/ServiceWorkspace.
- /schedule, /rooms: page adapters; Unified AI có thể dùng UnavailableStudentSurface.
- /knowledge: KnowledgeReview; /knowledge/sources → SourceOperations; /knowledge/policy-graph → PolicyGraphReview.
- /admin: admin/layout.tsx, page.tsx.
- /privacy: PrivacyCenter hoặc nhánh Unified AI có settings; /memory → MemoryCenter; /notifications → NotificationCenter.
- Có components/student, components/staff, Navbar cho workspace khác; xác minh chỗ gọi và route thật trước khi sửa. Không tạo /student, /dashboard, /reviews chỉ vì component cũ nhắc tới.
- src/lib, gateways, store, runtime và API client là hợp đồng/hành vi để giữ, không phải nơi tái thiết kế UI.
Các đường dẫn trên tính từ apps/web. Kiểm tra lại source hiện tại; không mặc định mọi variant đang được serve.

## Chất lượng bắt buộc
- Màn hình có mục đích và primary action rõ; hỗ trợ loading/empty/error/unauthorized/stale khi luồng có các trạng thái đó.
- Header/sidebar/component nhất quán; không “shell mới, nội dung cũ” ở bản hoàn tất.
- Responsive 390/768/1024/1440px, reflow 320 CSS px tương đương zoom, focus bàn phím, dialog đóng/khôi phục focus, reduced motion; touch target thao tác chính >=44px.
- Không dùng overflow-x:hidden để che lỗi layout; bảng/code chỉ scroll trong container.
- Nội dung tiếng Việt tự nhiên; badge trạng thái có chữ; nội dung dài không cắt mất thông tin thiết yếu.
- Có dark mode thực tế cho tất cả surface, controls, dialogs và feedback; không chỉ đổi canvas.
- Giữ preview/xác nhận/readback/receipt và phân quyền; không tự gửi khi chọn prompt hoặc mở trang.
- Không biến chỗ cấu hình chưa sẵn sàng thành chức năng giả; dùng empty/unavailable state được thiết kế hoàn chỉnh.

## Quy tắc tiết kiệm quota
Thực hiện tuần tự một đợt theo prompt được giao. Không tạo subagent hoặc orchestrator khác. Không đọc toàn bộ docs/catalog/evidence/infra/local. Không lặp dài kế hoạch hoặc giải thích code. Không chạy mọi test sau mỗi sửa CSS; kiểm phần bị tác động rồi kiểm rộng ở cuối.
Không đổi framework, cài thêm cả bộ UI, tạo nhiều biến thể hoặc ảnh trang trí nếu không cần.
Khi xong đợt: code + checks + ảnh browser thật + báo cáo ngắn theo REPORT-TEMPLATE.md, rồi dừng ở ranh giới đợt để nhận review. Đây là cách chia việc để điều phối, không phải approval gate cho từng sửa đổi.
