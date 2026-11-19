# Hoàn thiện toàn bộ kho HUCE — kế hoạch thực thi 24/10/2026

## Mục tiêu và phạm vi

Xử lý rõ toàn bộ 117 nguồn công khai đã nhập: mỗi nguồn có đúng trạng thái
phục vụ hoặc lý do chưa phục vụ có dẫn chứng và bước xử lý cụ thể. Tăng phần
tri thức được phục vụ bằng đối chiếu bản gốc, không biến số lượng nhập/test
thành độ bao phủ. Giữ ba tài liệu đang phục vụ trong các release kế tiếp.
Không yêu cầu thêm phê duyệt local mà người dùng đã cấp trong chat.

## Chặng 1 — kiểm kê và phân loại toàn bộ

- Chụp trạng thái Git và release; giữ hash original/rendition/index và thống kê
  đầy đủ từ database, không dùng danh sách UI bị cắt trang làm tổng số.
- Tách nguồn/phiên bản, bản đã phục vụ, tiền nhiệm và các bản cùng nguồn.
- Đọc bản gốc theo hash; kiểm kê loại tệp, số trang, lượng text, bảng, OCR và
  điều khoản/ngày/phạm vi có trong nội dung thật.
- Đầu ra: inventory JSON, text extraction giữ locator và bảng công việc từng
  nguồn. Không tạo ngày hiệu lực hoặc phê duyệt ở bước kiểm kê.

## Chặng 2 — phân loại tính áp dụng

- Văn bản quy phạm/quy chế: chứng minh ngày và điều khoản có hiệu lực từ nguồn;
  giữ khóa/chương trình/năm và văn bản thay thế khi nguồn nêu.
- Chương trình đào tạo/bảng: giữ đúng tên ngành, hệ, khóa và từng hàng/cột; kiểm
  ảnh trang mẫu với text, không gộp các khóa có số liệu khác nhau.
- Thông tin giới thiệu/hướng dẫn/sự kiện: phân biệt ngày công bố, thời gian sự
  kiện và hiệu lực pháp lý. Nếu cần, bổ sung mô hình snapshot có provenance và
  giới hạn câu trả lời rõ ràng; không gán ngày nhập làm ngày hiệu lực pháp lý.
- Tài liệu scan: ưu tiên OCR/transcript đã có và kiểm hash ảnh/bản gốc; phần
  không đọc được phải có lý do cụ thể, không được coi mặc nhiên là đã đạt.

## Chặng 3 — hoàn thiện đường xử lý chung

- Tái dựng evidence từ nguyên văn bản gốc, loại prefix/suffix biên tập khỏi
  bằng chứng; tái dùng vector chỉ khi chứng minh input/profile không đổi.
- Trường hợp phải dựng lại: chunk giữ char/page locator và bảng, embedding bằng
  BGE thật, có checkpoint, giới hạn từng request và tài nguyên hiện hữu.
- Sửa các thiếu sót chung được phát hiện: phân trang, trạng thái bản tiền nhiệm,
  khả năng phân biệt lý do chờ và nội dung có/không có ngày hiệu lực pháp lý.
- Kiểm thử domain/contract/quyền/hash/date/scope trước khi dùng candidate.

## Chặng 4 — xử lý và phát hành theo nhóm

- Mỗi nhóm có manifest nguồn/version/hash, căn cứ áp dụng, vùng text giữ/loại,
  số vector tái dùng/tạo mới và kết quả kiểm tự động/kiểm ảnh cần thiết.
- Review kỹ thuật bằng danh tính agent/tài khoản chủ hệ thống đã chỉ định,
  tách tác giả và reviewer; không mạo nhận cán bộ HUCE duyệt.
- Build release giữ thành viên cũ, đọc preview, kiểm chính xác membership và
  generation, xác nhận qua ứng dụng, đợi ack. Giữ lịch sử và bản thất bại.
- Mỗi nhóm kiểm truy xuất, câu trả lời và source HTTP/hash; giữ ngoài release
  thành viên không qua kiểm chứng thay vì nới tiêu chí.

## Chặng 5 — kiểm toàn kho và hồi quy

- Mỗi nguồn mới có ít nhất truy xuất kiểm đúng nguồn và locator; nguồn có số,
  điều kiện hoặc bảng có ca đúng/sai khóa/đơn vị/phạm vi tương ứng.
- Chạy lại 34 ca HUCE hiện có trên release mở rộng; ca ngoài corpus phải đánh
  giá theo membership mới, không giữ kỳ vọng thiếu nguồn nếu đã có nguồn thật.
- Kiểm citation/auth/thu hồi/Origin, fault, đồng thời, hash và integrity.
- Kiểm trình duyệt thư viện/chat/nguồn và thống kê không lẫn bản cũ với việc
  thực sự phải làm. Đo tốc độ theo nhóm thực tế, không cam kết giờ chưa đo.

## Chặng 6 — đối soát và bàn giao

- Đối soát đủ 117 nguồn đầu vào; mỗi nguồn có trạng thái và evidence.
- Công bố số nguồn phục vụ, số tiền nhiệm, số ngoài phạm vi và số thiếu bằng
  chứng; không dùng nhãn chung để che phần chưa làm.
- Lưu lệnh tái hiện, manifest/hash, receipt release và giới hạn thực tế.
- Không tuyên bố toàn kho đã phục vụ khi còn nguồn chưa qua kiểm chứng.

## Bảo toàn

Giữ mọi thay đổi có sẵn, bản gốc, lịch sử, bằng chứng lỗi và backup. Mọi phiên
bản mới là bổ sung. Không xóa/reset/cleanup, không sửa chính sách Windows,
không bỏ auth/review/confirmation/hash/semantic verification, không reset kế
toán, không commit/push/deploy. Dùng nguồn công khai và runtime local hiện có.

Tiến độ và đầu ra chi tiết được ghi bổ sung trong namespace
`infra/local/huce-corpus-completion-20261024-01/`; các lần chạy ghi file mới.

## Tiến độ thực tế sau phát hành generation 15

| Chặng | Kết quả đã thực hiện | Phần chưa được khẳng định |
|---|---|---|
| 1. Kiểm kê | Đủ 117 nguồn, 126 phiên bản ban đầu, 115 original khác nhau | Không suy ra độ bao phủ từ số trang |
| 2. Tính áp dụng | Có phạm vi theo nguồn/trang, tách hai sơ đồ K69/K70, snapshot khác ngày hiệu lực | 12 nguồn còn thiếu chứng cứ khóa hoặc ánh xạ hàng nhiều khóa |
| 3. Đường xử lý | Bản trích ràng buộc hash, BGE thật, scope trước LIMIT, dẫn nguồn có ghi giới hạn | Chưa có trình hiểu mọi sơ đồ/hàng/cột/mũi tên |
| 4. Phát hành | 114 tài liệu, ba alias có đối soát, giữ ba phiên bản cũ, preview/confirmation/ack | Chỉ phần chữ/trang có bằng chứng được sử dụng |
| 5. Hồi quy | Kiểm mã, DB, quyền, fault, đồng thời và browser; receipt lỗi giữ nguyên | Chưa kiểm tải dài hạn hoặc production |
| 6. Bàn giao | Bảng đủ 117 nguồn, release/hash/receipt và giới hạn rõ ràng | 93 nguồn còn giới hạn nội dung/phạm vi |

Ưu tiên tiếp theo để tăng độ đọc đầy đủ, không chỉ tăng số nguồn:

1. Nhóm 12 nguồn: tìm dòng công bố/bản gốc chứng minh khóa; với bảng nhiều khóa,
   đối chiếu tọa độ và từng hàng. Chỉ cập nhật scope khi có chứng cứ cụ thể.
2. Nhóm sơ đồ còn lại: lưu ô môn, đơn vị, học kỳ, tự chọn và đường nối theo trang;
   đối chiếu ảnh trước khi cho trả lời quan hệ tiên quyết/song hành.
3. Nhóm scan/quy chế: bổ sung transcript các trang còn thiếu, điều kiện và ngoại lệ;
   giữ bản cũ và phát hành phiên bản bổ sung sau kiểm hash/locator.
4. Vận hành HUCE thật: nối SSO/API theo quyền dữ liệu thật, kiểm bảo mật/tải/phục hồi
   trên môi trường được xác định. Runtime local không tự cấp các quyền này.

Mỗi nguồn và lý do cụ thể ở [bảng đối soát](HUCE_SOURCE_STATUS_20261024.md).
Kết quả kiểm chứng ở [báo cáo thực hiện](HUCE_CORPUS_COMPLETION_RESULT_20261024.md).

Đợt 25/10 đã hoàn tất phát hành phần bổ sung sáu nguồn, gồm bốn căn cứ K71,
bốn hàng lịch CNTT và các điều khoản chọn lọc của Quy chế 1486. Kết quả và
danh sách phần chưa hoàn tất nằm trong
[báo cáo tiếp nối](HUCE_EVIDENCE_CONTINUATION_RESULT_20261025.md).
93 nguồn vẫn còn giới hạn; bảy nguồn trong đó chưa rõ khóa cụ thể.
