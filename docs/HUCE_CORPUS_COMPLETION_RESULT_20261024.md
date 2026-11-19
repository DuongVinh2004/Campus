# Kết quả xử lý kho HUCE — 24/10/2026

Kho đã chuyển từ 3 lên **114 tài liệu phục vụ**, thêm **3 nguồn trùng/liên kết
được đối soát**, bao phủ danh tính của cả 117 nguồn đầu vào. Release local
`01a16dad-9939-785d-beba-d7ef2df4d2ea`, generation **15**, được kích hoạt bằng
preview và confirmation của ứng dụng; runtime đã xác nhận. Ba phiên bản cũ
đang phục vụ được giữ nguyên trong membership mới.

Đây là hoàn tất đường nhập, phân loại và phát hành phần nguồn có thể chứng minh,
không phải xác nhận đã hiểu đầy đủ mọi sơ đồ hoặc sẵn sàng production.

## Số liệu được tách rõ

| Số liệu | Kết quả |
|---|---:|
| Nguồn đầu vào được đối soát | 117 |
| Tài liệu trong release và được phục vụ | 114 |
| Nguồn trùng hoặc trang liên kết tới nguồn đã phục vụ | 3 |
| Phiên bản cũ vẫn giữ trạng thái chưa duyệt | 122 |
| Trong đó bản lịch sử của nguồn có phiên bản mới | 119 |
| Trong đó bản của nguồn trùng/liên kết đã đối soát | 3 |
| Phiên bản chờ xử lý ngoài hai nhóm trên | 0 |
| Nguồn có phần chữ sử dụng được trong phạm vi đã ghi | 21 |
| Nguồn chỉ được xác nhận một phần nội dung | 81 |
| Nguồn chưa đủ căn cứ gắn khóa hoặc phân tách hàng của bảng nhiều khóa | 12 |

**93 nguồn còn giới hạn nội dung/phạm vi.** Con số 0 ở hàng chờ không có nghĩa
93 giới hạn này đã biến mất. Giao diện hiển thị cả số nguồn phục vụ, bản lịch sử,
nguồn trùng và các giới hạn; mặc định ẩn bản lịch sử nhưng vẫn có thể mở lại.

## Công việc đã thực hiện

1. Kiểm kê 126 phiên bản ban đầu, 115 bản gốc khác nhau, 377 trang; giữ hash và
   locator. Xác nhận toàn bộ 126 phiên bản còn nguyên bản gốc, trạng thái review
   và thông tin áp dụng cũ. Không xóa hoặc duyệt đè 122 bản đang chờ.
2. Tái dựng đoạn chữ từ bản gốc, dùng bản trích đã đối chiếu khi có thể tái lập.
   Tải bản PDF đính kèm công khai của thông báo 1106, OCR lại trang bị xoay và
   đối chiếu ảnh. Sửa lớp OCR hỏng của thông báo học bổng STEM; giữ giới hạn
   trang/đoạn đã đọc. Hai đoạn chỉ dẫn iframe không được coi là bằng chứng.
3. Phân biệt ngày có thể truy xuất bản lưu với ngày hiệu lực pháp lý. Không lấy
   ngày nhập làm ngày hiệu lực. Quyết định 1486 có đối chiếu ngày ký/Điều 2 ở
   trang 1; các trang quy chế chưa được xác nhận đầy đủ không được tuyên bố đã đọc.
4. Lập chỉ mục bằng BGE thật, giữ input/model/vector/hash và checkpoint. Release
   có 1.720 chunk đã kiểm hash nội dung và input. Không dùng vector giả hoặc
   reset kế toán mô hình để hoàn thành công việc.
5. Lọc khóa/chương trình trước giới hạn tìm kiếm; giữ khóa chưa rõ ở trạng thái
   chưa rõ. Khi nguồn có tổng tín chỉ in sẵn, lấy đúng dòng tổng và phần loại trừ;
   không cộng các ô học kỳ để suy ra tổng. Chặn suy diễn quan hệ mũi tên và gán
   cột học kỳ chưa được xác minh.
6. Thêm phân loại nguồn chỉ ghi bổ sung. Review kỹ thuật ghi rõ danh tính agent
   và chủ hệ thống; không mạo nhận cán bộ HUCE duyệt. Giữ auth, review độc lập,
   preview/confirmation, hash, ngưỡng relevance và semantic verification.
7. Sao lưu PostgreSQL và ba kho SQLite trước kích hoạt. Khi tiến trình local
   dừng, khởi động lại cluster và runtime đã lưu, tiếp tục ledger mô hình ở
   namespace kế tiếp với số liệu tích lũy; không khởi tạo lại dữ liệu hoặc sửa
   chính sách Windows. Frontend phục vụ là bản build v14.
8. Tách K69/K70 theo từng trang có tiêu đề in rõ ở hai sơ đồ môi trường và khoa
   học máy tính; không trộn môn giữa hai trang. Lịch năm học có nhiều khóa trong
   cùng bảng vẫn chưa được dùng để suy ra lịch riêng cho một khóa.
9. Áp dụng ngoại lệ hạn nộp công khai đúng phạm vi người dùng vừa cho phép trong
   `safety_rules.py`: cần số thông báo hoặc năm học rõ ràng. Vẫn chặn hồ sơ cá
   nhân, gia hạn/ngoại lệ, prompt injection và các tín hiệu nguy cấp. Hai thông
   báo 2025–2026 và 2026–2027 trả đúng khoảng thời gian riêng, dẫn đến trang có
   trường hạn nộp thực tế. Không lấy ngày ký hoặc phụ lục làm hạn nộp.
10. Giữ nguyên tên nút trong hướng dẫn Office; loại thanh điều hướng
    Previous/Next Post khỏi bản trích bài viết và sửa một lỗi OCR học bổng sau
    khi đối chiếu ảnh. Kiểm toàn bộ 1.720 chunk không còn ba dấu vết lỗi này.

## Kiểm chứng và bằng chứng

- Mỗi nguồn trong 114 thành viên có ít nhất một truy vấn tìm đúng phiên bản,
  kiểm hash đoạn trả về. Có câu rộng không tìm được nguồn; các lần thất bại
  được giữ lại. Một truy vấn đạt cho mỗi nguồn không chứng minh mọi câu hỏi đều đạt.
- Kiểm integrity: 126 phiên bản/115 bản gốc ban đầu được giữ; sealed membership
  đúng 114 thành viên; 1.720 chunk khớp nội dung/input và binding nguồn.
- Bộ mã cuối: **191 passed, 4 skipped**; bốn ca PostgreSQL được bật riêng và
  **4/4 passed**. Không cộng hai bộ thành số ca độc lập mới. Frontend **14/14**
  passed, bản build v14 qua TypeScript và build production local.
- **8/8 câu trong bốn cặp chạy đồng thời** đúng nội dung/khóa/đơn vị; source
  HTTP 200, truy cập không đăng nhập 401, hash và release generation 15 đúng.
  Mẫu này đo được 6,750–10,595 giây mỗi câu; chưa phải kiểm tải dài hạn/SLO.
- **14 kiểm tra quyền/binding/session** đúng mã HTTP mong đợi. Ba fault cô lập
  đạt: mất embedding/reranker từ chối an toàn, nguồn sai checksum trả 409.
  Fault được tiêm vào adapter/bản sao bộ nhớ, không phá nguồn hoặc DB phục vụ.
- Trình duyệt thật đạt thư viện/số liệu/bản lịch sử, câu Office, mở đoạn nguồn
  và giới hạn áp dụng; màn hình điện thoại không tràn ngang. `browser-02` không
  có page error; các ERR_ABORTED khi điều hướng được giữ trong receipt.
- Bộ **34 câu hồi quy chạy lại trên generation 15 đạt 34/34**, gồm đúng/sai
  khóa, đơn vị, follow-up, thiếu điều kiện, hồ sơ cá nhân và prompt injection.
  Khi ghép các ca kiểm thêm, **47/47 chủ đề đạt ở lần kiểm gần nhất**; đây là
  kết quả ghép nhiều receipt, không phải một lượt chạy duy nhất 47 câu.
  Phán định ngữ nghĩa/hash/quyền ở `final-verdict-01.json`. Các lần trước có từ
  chối USB hoặc lấy nhầm phụ lục hạn nộp vẫn được giữ nguyên.

Các file chính trong `infra/local/huce-corpus-completion-20261024-01/`:

- `inventory-01.json`: baseline của 117 nguồn và 126 phiên bản.
- `candidate-plan-06.json`, `candidate-release-06.json`: 111 bản mới, ba bản cũ
  giữ nguyên và ba nguồn liên kết/trùng; membership đúng phiên bản đang phục vụ.
- `source-dispositions-03.json`, `source-status-final-01.json`: đủ 117 nguồn,
  lý do, phạm vi, liên kết tương đương và phiên bản phục vụ từng nguồn.
- `candidate-integrity-03.json`: đối chiếu original, review, thời gian và chunk.
- `retrieval-coverage-final-02.json`: truy vấn đúng phiên bản cho 114 nguồn;
  giữ 108 cặp nguồn/phiên bản không đổi, kiểm lại sáu nguồn thay đổi cuối.
- `activation-preview-03.json`: preview đã bỏ token xác nhận khỏi evidence file.
- `activation-confirmation-03.json`, `activation-ready-03.json`: receipt và ack.
- `financial-guard-authorization-01.json`: phạm vi cho phép trực tiếp của người dùng.
- `final-tests-27.xml`, `postgres-tests-16.xml`: kết quả kiểm thử mã và DB.
- `final-verdict-01.json`, `browser-02/report.json`: phán định câu trả lời và UI.
- `backups/pre-activation-02/receipt.json`: hash bốn bản sao lưu; thư mục backup
  được bỏ khỏi Git để tránh đưa dữ liệu runtime vào mã nguồn.
- `backups/post-verification-01/receipt.json`: thêm bốn bản sao sau kiểm chứng,
  gồm pg_dump 34.385.212 byte và ba SQLite qua online backup/quick_check.
  Từng kho nhất quán riêng; chưa chạy thử phục hồi hoặc xác nhận tính nguyên tử
  giữa bốn kho. Không ghi đè bản sao trước phát hành.
- `style-only-tests-28.xml`: 52 ca liên quan vẫn đạt sau sửa tên alias regex
  và định dạng import; hành vi ứng dụng không đổi, không cộng vào 191 ca chính.

## Phần cần tiếp tục để đọc đầy đủ nội dung

- Với sơ đồ đào tạo: đối chiếu tọa độ ô, nhánh tự chọn, đơn vị và đường nối trên
  ảnh gốc. Bản chữ phẳng hiện có không chứng minh môn thuộc cột học kỳ nào hoặc
  quan hệ tiên quyết/song hành. Chỉ mở những khả năng đó sau khi có đối chiếu.
- Với 12 nguồn chưa rõ khóa/phạm vi hàng: cần chứng cứ khóa/chương trình ở bản gốc hoặc
  dòng công bố chính thức đủ cụ thể; không suy ra từ nhãn nhập cũ
  `K70_and_earlier_verify_individual_row` hoặc chỉ từ năm 2025.
- Với trang scan, ảnh/bảng ít chữ và quy chế dài: hoàn tất transcript theo trang
  và kiểm lại điều kiện/ngoại lệ. Ví dụ phần quy chế kèm Quyết định 1486 còn cần
  đối chiếu ngoài trang quyết định; tài liệu vật liệu 2025 mới có phần chọn lọc.
- Với vận hành chính thức: SSO HUCE, API học vụ, quyền dữ liệu thật và hạ tầng
  triển khai còn chưa kết nối. Dữ liệu công khai và QA local không thay thế các
  tích hợp này.

Kế hoạch chi tiết: [HUCE_CORPUS_COMPLETION_PLAN_20261024.md](HUCE_CORPUS_COMPLETION_PLAN_20261024.md).
Bảng từng nguồn: [HUCE_SOURCE_STATUS_20261024.md](HUCE_SOURCE_STATUS_20261024.md).

## Lệnh tái hiện chính

Chạy từ repository bằng PowerShell. Mỗi lệnh live ghi receipt mới; model và
database phải đúng danh tính local đã lưu. Không reset DB hoặc xóa output cũ.

```powershell
& 'infra/local/rag-fixture/.venv/Scripts/python.exe' -B scripts/knowledge_platform_runtime.py status
& 'infra/local/rag-fixture/.venv/Scripts/python.exe' -B scripts/audit_huce_rag_20261023.py questions --cases-file infra/local/huce-corpus-completion-20261024-01/live-cases-34-01.json
& 'infra/local/rag-fixture/.venv/Scripts/python.exe' -B scripts/audit_huce_rag_20261023.py questions --cases-file infra/local/huce-corpus-completion-20261024-01/live-cases-expanded-03.json
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
$env:PYTHONPATH='C:/Users/Duong Vinh/Vinh/infra/local/rag-fixture'
& '.venv/Scripts/python.exe' -B -m pytest tests/knowledge_platform tests/api/test_citation_source.py tests/unit/retrieval/test_citations.py tests/unit/retrieval/test_public_source_excerpts.py tests/operations/test_knowledge_platform_runtime.py -q -p pytest_asyncio.plugin
```

`report_huce_corpus_completion.py --baseline <receipt>` chỉ đọc receipt và ghi
bộ đối soát cuối bằng thao tác tạo file mới độc quyền; bộ đã ghi không bị đè.
Các report cũ vẫn phản ánh đúng lần chạy tại thời điểm đó.

## Bổ sung ngày 25/10/2026

Đợt tiếp theo đã phát hành sáu nguồn bổ sung trên generation 17; số nguồn
chưa rõ khóa/hàng giảm từ 12 xuống 7. Vẫn còn 93 nguồn giới hạn nội dung.
Báo cáo và phạm vi hiện tại ở
[HUCE_EVIDENCE_CONTINUATION_RESULT_20261025.md](HUCE_EVIDENCE_CONTINUATION_RESULT_20261025.md).
Số liệu phía trên được giữ nguyên cho lần kiểm ngày 24/10.
