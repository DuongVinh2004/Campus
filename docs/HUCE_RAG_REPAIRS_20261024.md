# HUCE RAG — kết quả sửa lỗi ngày 24/10/2026

Mã đã được sửa và kiểm thử. Chưa xác nhận hoàn tất toàn tuyến: Windows Device Guard chặn PostgreSQL đã lưu, nên API chưa khởi động lại được. Kiểm thử đồng thời còn ghi nhận một lần hết thời gian 5 giây; hệ thống từ chối an toàn.

## Các thay đổi

- Chọn đoạn con theo nội dung thực sự trước BGE, tránh việc phần mở đầu cùng trang che mất điều khoản USB. Vẫn phải vượt kiểm tra BGE, quyền, release và hash.
- Khôi phục dấu cho truy vấn không dấu chỉ khi toàn bộ chuỗi từ và số giữ nguyên sau chuẩn hóa. Chỉ dùng cho tìm kiếm.
- Bổ sung xác minh chuỗi công bố chính thức cho đúng tệp nội quy được HUCE liên kết. Ràng buộc publisher, attachment, original, rendition, đoạn trích, source, version và release; không chấp nhận một tên miền Drive nói chung.
- Sửa đúng nhánh `bị đình chỉ` theo yêu cầu đích danh của người dùng: phân biệt câu hỏi nội quy chung với hồ sơ cá nhân. Các tín hiệu HIGH/CRITICAL khác vẫn ưu tiên; câu trả lời tiếp tục qua kiểm chứng và chặn phán quyết cá nhân.
- Dùng cùng câu hỏi đã nối ngữ cảnh cho sinh và xác minh câu trả lời follow-up. Lịch sử trợ lý không trở thành bằng chứng.
- Đối chiếu học phí với đúng nhóm hệ đào tạo, chương trình, khoảng khóa và đơn vị của cùng dòng. Bộ xác minh ngữ nghĩa vẫn nhận toàn bộ bảng cùng các lát nguyên văn có vị trí.
- Trình bày rõ phạm vi cho một mức phí đã được mô hình đề xuất và kiểm chứng. Không sửa giá/đơn vị sai để cho qua; giữ kiểm tra `OutputGuardNode`, nguồn, điều kiện áp dụng và xác minh ngữ nghĩa.
- Sửa phản hồi tái tạo để không kết luận nhầm rằng dòng nguồn không áp dụng khi lỗi thực tế là phủ định sai điều kiện. Yêu cầu mô hình nêu mức/đơn vị đúng, tránh lặp lại giá trị gài sai.
- Một kết quả kiểm chứng ngữ nghĩa âm hợp lệ được dùng lần tái tạo còn trống, rồi phải kiểm chứng lại. Không tái tạo khi verdict lỗi định dạng. Giữ tối đa hai lần sinh, một lần tái tạo, tổng 1.000 output tokens và 5.000 ms cho pha sinh/xác minh; dùng đồng hồ `perf_counter` để tính thời gian trên Windows.

## Bằng chứng trên mã cuối

| Kiểm tra | Kết quả | Bằng chứng trong `infra/local/knowledge-platform-20261023/` |
|---|---|---|
| Hồi quy rộng, gồm API cô lập/SSE, nguồn, trích dẫn, identity, safety và hội thoại | **274 passed**, 106,06 giây | `repair-api-regression-15.xml` |
| Hồi quy tập trung sau sửa tái tạo | **119 passed** | `repair-regression-14.xml` |
| Mô hình thật, sáu ca học phí khó lặp ba lần | **18/18 trả lời đúng** | `generation-component-20261024T054527865526.json` |
| Hai câu hỏi đồng thời, ba cặp đầu | **5/6 trả lời**, một timeout | `generation-component-20261024T054708526468.json` |
| Kiểm tra lại hai câu hỏi đồng thời, ba cặp tiếp | **6/6 trả lời đúng** | `generation-component-20261024T054750102468.json` |
| Hash bản gốc, rendition và 51 đoạn bằng chứng đã xuất của ba tài liệu | Khớp toàn bộ bản lưu | `repair-retained-integrity-20261024-01.json` |
| Tiếp nối kế toán native | Không reset: kế thừa 10.981 inference, 17.212 HTTP, 2.350.568 tokens trước các lượt `/info` mới | `restart-accounting-20261024-02.json` |

Các số kiểm thử hồi quy có phần giao nhau, không cộng thành tổng ca riêng biệt. Kiểm thử mô hình thật là kiểm thử thành phần sinh/xác minh với bằng chứng công khai đã lưu và kiểm hash, qua gateway và sổ kế toán hiện có. Chúng không xác nhận truy xuất PostgreSQL, API đang phục vụ, quyền đọc citation qua HTTP hoặc giao diện trên bản cuối.

Sáu ca học phí gồm kỹ sư chính quy K71, bẫy giá kỹ sư K64, bẫy ĐVHT cử nhân K71, follow-up bổ sung điều kiện cử nhân K71, cử nhân K70 và chất lượng cao K67. Kết quả đúng lần lượt là 547.000, 580.500, 592.500, 592.500, 592.500 và 533.000 đồng/tín chỉ, có trích dẫn. Các kết quả lỗi trước bản cuối vẫn được giữ, gồm hai đợt 17/18; không dùng các lần đạt để xóa bằng chứng lỗi.

Trong 12 lượt đồng thời trên cùng mã sản phẩm, 11 lượt trả lời đúng. Một lượt kỹ sư K71 cần tái tạo sau kiểm chứng âm và hết hạn 5 giây khi chia sẻ gateway; trả `safe_failure/AI_GENERATION_TIMEOUT`. Không tăng thời hạn hay bỏ kiểm chứng để làm ca này đạt. Đây vẫn là giới hạn vận hành cần đo lại khi toàn tuyến hoạt động.

## Trạng thái dịch vụ và việc còn thiếu

PostgreSQL đang dừng. Lệnh khởi động bình thường của `pg_ctl` báo:

> `postgres.exe` was blocked by your organization's Device Guard policy.

Đúng executable bị chặn là `C:/Users/Duong Vinh/Vinh/.tooling/knowledge-postgres-20261023/pgsql/bin/postgres.exe`. Cụm dữ liệu được giữ ở `C:/Users/Duong Vinh/Vinh/.tooling/knowledge-postgres-20261023/cluster`. Không khởi tạo lại database, chạy migration, thay executable để né chính sách hoặc sửa chính sách bảo vệ của Windows.

Hai dịch vụ mô hình native đã khởi động trong namespace mới `infra/local/rag-advanced-models-20261024-accounting-02`, tiếp nối đầy đủ namespace trước. Model/revision đúng BGE-M3 và BGE-reranker-v2-M3 đã xác minh. Binding kế toán đã trỏ sang namespace mới, giữ giới hạn từng yêu cầu và bảo vệ CPU/RAM. API 8015 và frontend 3015 chưa khởi động lại vì database chưa chạy.

Sau khi quản trị viên khôi phục khả năng chạy đúng PostgreSQL theo chính sách máy, cần khởi động lại cluster hiện có, frontend snapshot `frontend-knowledge-v11` và API với generation. Sau đó chạy lại bộ 17 câu chính, 17 biến thể, các follow-up và cặp đồng thời qua API; kiểm lại citation/auth, fault và integrity từ database đang chạy. Script có sẵn: `scripts/audit_huce_rag_20261023.py`. Kiểm thử thành phần có thể tái hiện bằng `scripts/verify_huce_generation_repairs_20261024.py --repetitions 3`, hoặc thêm `--concurrent` cho hai câu đồng thời.

Phạm vi dữ liệu vẫn là ba tài liệu phục vụ của release `01a168c6-dce3-7b72-bcbd-b5797b9452b8`. Chưa xác nhận cả danh mục tài liệu, dữ liệu học vụ cá nhân, SSO hay môi trường production. Mọi thay đổi có sẵn, tài liệu, bản ghi thất bại và dữ liệu người dùng được giữ.

Manifest cuối và kết luận máy đọc: `infra/local/knowledge-platform-20261023/repair-final-verification-20261024-01.json`. Trạng thái toàn tuyến là **NOT_VERIFIED — OS_DEVICE_GUARD_BLOCKED**, không phải hoàn tất.
