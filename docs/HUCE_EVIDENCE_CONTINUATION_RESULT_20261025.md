# HUCE — đợt bổ sung bằng chứng ngày 25/10/2026

Đã hoàn tất nhập, duyệt kỹ thuật, phát hành và kiểm chứng phần bổ sung của sáu
nguồn bị dở ở lượt trước. Runtime local đang phục vụ release
`01a16f03-62a4-7fa1-ade2-c848a2b16ad7`, generation **17**, policy generation **3**,
với 114 tài liệu và 3 alias. Đây không phải hoàn tất nội dung của toàn bộ 93
nguồn còn giới hạn.

## Phần đã bổ sung

- Bốn tài liệu Kiến trúc, Xây dựng DD&CN, Kinh tế xây dựng và Công nghệ kỹ thuật
  vật liệu xây dựng: khôi phục căn cứ K71 từ đúng hàng của bảng công bố chính
  thức. Manifest cũ có đủ `rows` nhưng bước chuẩn bị chỉ dùng `files` đã loại
  trùng, nên mất lần xuất hiện trong bảng K71. Đã đối chiếu cả bản lưu và bảng
  công bố tải lại. Không gán riêng K70 hoặc các khóa trước từ mục chung.
- Lịch CNTT: kiểm lại bản gốc, hình học bảng, ảnh và 208 ô tuần của bốn hàng
  K68–K71; ràng buộc đoạn trích với từng hàng, năm học 2026–2027, nhãn K71
  **DỰ KIẾN**, ngày bắt đầu tuần, ký hiệu và chú giải màu. Ô trống vẫn là ô
  không ghi ký hiệu; ngày bắt đầu tuần không được gọi là ngày thi cụ thể.
- Quy chế 1486: giữ trang quyết định và bổ sung các điều khoản hoàn chỉnh đã
  đối chiếu ảnh ở trang PDF 2–5: Điều 1(1–3), Điều 2(2–5), Điều 3(1,2a), các
  định nghĩa đã chọn trong 3(2b), và 3(2c,d). Giữ riêng quy định tiên quyết,
  học trước, song hành và điều kiện hủy học phần ở lần học đầu. Chưa đưa các
  phần nối trang bị bỏ qua hoặc trang PDF 6–26 vào bản trích mới.
- Chú giải vật liệu được tách khỏi dãy tổng học kỳ bằng các span liên tiếp,
  giữ nguyên toàn bộ chữ của bản đã đối chiếu. Không thêm/bớt nội dung để
  làm tăng số lượng nguồn hoặc suy ra tổng tín chỉ.

Trang công bố: [Khung chương trình đào tạo hệ chính quy HUCE](https://huce.edu.vn/khung-chuong-trinh-dao-tao-chinh-quy).
Ngày đối chiếu bản lưu không được dùng làm ngày hiệu lực pháp lý hoặc cam kết
rằng bản PDF trên mạng chưa thay đổi sau lần thu thập.

## Sửa đường xử lý và giữ kiểm soát

- Câu hỏi tín chỉ một môn không còn bị đổi thành câu hỏi tổng tín chỉ chương trình.
- Khi người dùng nêu rõ sơ đồ/chương trình, chọn đúng chủ thể trước giới hạn
  tìm kiếm; bỏ hậu tố năm và bản dịch tiếng Anh khỏi phép so khớp tên ngành.
  Chỉ tập trung phần câu hỏi chú giải sau khi đã chọn đúng chương trình.
- Tiêu đề xuống dòng như `Năm 2` không còn trở thành đơn vị của số tín chỉ
  ở ô trước. Đơn vị thời gian thật, kể cả xuống dòng, vẫn bị kiểm tra.
- Nhãn số `TC` trong nguồn được nhận diện tương đương từ vựng với “tín chỉ”.
  Ngưỡng 0,78 giữ nguyên; kiểm số, đơn vị và xác minh ngữ nghĩa vẫn chạy trên
  nguồn không thay đổi. Ca thiếu nhãn TC và ca sai số vẫn bị từ chối.
- Thêm kiểm tra việc gọi nhầm cả chuỗi `mã-số tín chỉ` là mã học phần; chỉ
  cho phép một lần tái tạo trong ngân sách/thời hạn cũ và kiểm lại đầu ra.
- Giữ chữ viết tắt của chú giải và nhãn hàng khi trình bày. Không bỏ auth,
  hash, kiểm scope, review, preview/confirmation hoặc semantic verification.

Các lần API khởi động lại chỉ dừng listener local đã kiểm đúng danh tính;
PostgreSQL, BGE, worker, frontend, release pointer và ledger được giữ.
Không reset dữ liệu, không commit/push/deploy hoặc xóa bằng chứng.

## Kiểm chứng đã chốt

- Kiểm mã: **212 passed, 4 skipped**. Bốn kiểm thử PostgreSQL opt-in chạy riêng
  đạt **4/4**; không coi hai lượt là các tập ca độc lập để cộng số.
- Bộ 12 câu mới chạy liền một lượt trên generation 17 đã trả đúng nội dung
  và phạm vi khi đọc câu trả lời cuối. Các nguồn trích trả HTTP 200, truy cập
  không đăng nhập 401, hash và membership được đối soát trong receipt.
- Bộ 34 câu cũ chạy lại liền một lượt trên generation 17 đạt **34/34**,
  gồm điều kiện học phí, đơn vị, follow-up, sai năm, hồ sơ cá nhân và injection.
  Đây là hai bộ 12 và 34 riêng, không phải một lượt chạy 46 câu.
- Integrity toàn release: **1.717 chunk** khớp hash nội dung/input; giữ nguyên
  **126 phiên bản và 115 original** ban đầu, cùng ba phiên bản phục vụ gốc.
  Giảm số chunk không đồng nghĩa mất bản gốc: lịch chỉ phục vụ các hàng đã
  đối chiếu; mọi bản nguồn và phiên bản cũ vẫn được giữ.
- Các lần tìm không ra nguồn, từ chối vì định dạng/đơn vị/cách diễn đạt và
  một component runner bị ledger từ chối quyền ghi đều được giữ nguyên.
  Không lấy tổng hợp các lần chạy làm một lượt kiểm duy nhất.
- Chưa kiểm lại trình duyệt hoặc tải dài hạn trong đợt này. Frontend và API
  hiện hoạt động; kiểm nguồn/citation ở đợt này thực hiện qua API thật.

## Phần chưa hoàn tất

Phân loại hiện tại là **21 SOURCE_TEXT_AVAILABLE, 86 PARTIAL_SOURCE_TEXT,
7 SOURCE_SCOPE_UNRESOLVED, 3 alias**. Vẫn có **93 nguồn còn giới hạn**; việc
12 giảm xuống 7 là giải quyết phạm vi cho năm nguồn, không biến năm nguồn
đó thành đã hiểu toàn bộ sơ đồ.

Bảy nguồn chưa có căn cứ khóa cụ thể:

1. CNTT — Mạng và hệ thống thông tin — B7.
2. Khoa học máy tính tiếng Anh, hợp tác Mississippi.
3. CNTT — An toàn thông tin — B7.
4. CNTT — Công nghệ đa phương tiện, cử nhân.
5. CNTT — Công nghệ phần mềm — B7.
6. Khoa học dữ liệu, cử nhân.
7. Kỹ thuật xây dựng CEQT.

Bản gốc đã kiểm của các nguồn này không in khóa; đúng liên kết chỉ nằm trong
mục “K70 về trước”. Tìm bổ sung theo các ID công khai đã thực hiện không cho
thêm căn cứ cụ thể. Cần bản công bố hoặc xác nhận có thẩm quyền chỉ rõ khóa;
không suy từ năm, bằng cấp hoặc tên liên kết.

Các việc đọc ô học kỳ, nhánh tự chọn, đường nối tiên quyết/song hành và phần
scan/quy chế còn thiếu vẫn nằm trong danh sách từng nguồn. Giới hạn trả lời
theo học kỳ/mũi tên chưa xác minh được giữ nguyên. SSO HUCE và API học vụ cá
nhân **chưa kết nối**; chưa có quyền dữ liệu thật hoặc dữ liệu cá nhân thay thế.

## Hồ sơ và tái hiện

Namespace bằng chứng: `infra/local/huce-evidence-20261025-01/`.

- `inspection-material-01.json`, ảnh từng trang: 13 nguồn/48 trang làm vật liệu
  đối chiếu; số trang này không phải tuyên bố tất cả đã được duyệt nội dung.
- `publisher-20261025-01.html`, `publisher-rows-01.json`: bản công bố và các hàng.
- `calendar-revalidated-01.json`, `regulation-selected-pages-01.json`: căn cứ bảng
  và transcript điều khoản có phạm vi rõ ràng.
- `activation-*.json`, `legend-activation-*.json`: preview đã bỏ token xác nhận,
  confirmation và acknowledgement của ứng dụng.
- `regression-tests-07.xml`, `postgres-tests-01.xml`: kiểm mã và DB.
- `final-verdict-02.json`: phán định 12/12 và 34/34 từ hai receipt cụ thể;
  `final-verdict-01.json` giữ lỗi bộ đối soát so ngày có dấu `/` với chuỗi đã
  chuẩn hóa mất dấu `/`. Lần 02 chuẩn hóa hai vế giống nhau, không đổi câu hỏi,
  kỳ vọng ngày hoặc câu trả lời đã lưu.
- `source-status-final-01.json`, `remaining-evidence-worklist-01.json`: trạng thái
  117 nguồn và việc còn thiếu của 93 nguồn.
- `final-scope-check-02.json`: trạng thái Git và năm đường dẫn bị xóa từ trước.

Plan/release cuối ở namespace cũ để tiếp tục cơ chế checkpoint:
`candidate-plan-08.json`, `candidate-release-08.json`, `candidate-integrity-05.json`.
Các file 01–07 và backup cũ vẫn giữ nguyên.

Backup bổ sung nằm trong namespace cũ `backups/pre-stage-20261025-01/` và
`backups/post-verification-20261025-01/`. Mỗi bộ gồm pg_dump và ba bản SQLite
online backup/quick_check. Chưa chạy phục hồi; không khẳng định tính nguyên tử
giữa bốn kho.

```powershell
& 'infra/local/rag-fixture/.venv/Scripts/python.exe' -B scripts/knowledge_platform_runtime.py status
& 'infra/local/rag-fixture/.venv/Scripts/python.exe' -B scripts/audit_huce_rag_20261023.py questions --cases-file infra/local/huce-evidence-20261025-01/live-cases-01.json
& 'infra/local/rag-fixture/.venv/Scripts/python.exe' -B scripts/audit_huce_rag_20261023.py questions --cases-file infra/local/huce-corpus-completion-20261024-01/live-cases-34-01.json
```

Các lệnh audit ghi receipt mới. Không chạy lại prepare/activation/backup vào
đường dẫn đã tồn tại; các bước ghi dùng tạo mới độc quyền để bảo toàn lịch sử.
