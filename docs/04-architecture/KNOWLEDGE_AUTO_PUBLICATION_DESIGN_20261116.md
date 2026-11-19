# Thiết kế: thêm tài liệu tự động đến khi chatbot dùng được

Ngày: 2026-11-16 · Trạng thái: **đề xuất, chờ chủ hệ thống duyệt** · Phạm vi: runtime 8015 (local), dùng nguyên cho cloud giai đoạn 2.

## 1. Mục tiêu

Người có quyền thêm tài liệu chỉ thao tác một lần; mọi bước còn lại hệ thống tự làm cho đến khi chatbot trả lời được bằng tài liệu đó.

| Vai trò | Người dùng làm | Hệ thống tự làm |
|---|---|---|
| **Người đăng trực tiếp** | Tải tệp + điền thông tin nguồn, bấm **Đăng** | xử lý → kiểm tra tự động → phát hành → cập nhật chỉ mục chat → dùng được |
| **Người đóng góp** (cần duyệt) | Tải tệp + điền thông tin nguồn, bấm **Gửi duyệt** | xử lý → kiểm tra tự động → đưa vào hàng chờ duyệt |
| **Người duyệt** | Xem bản trích + kết quả kiểm tra, bấm **Duyệt** | phát hành → cập nhật chỉ mục chat → dùng được |
| **Nguồn tự động** (3.8) | Chủ hệ thống khai báo một lần các trang gốc của trường | dò định kỳ → lấy văn bản mới/đổi → lọc dữ liệu cá nhân → vào hàng chờ duyệt (hoặc đăng thẳng nếu nguồn được chỉ định) |

Thời gian từ lúc bấm đến khi dùng được (ước tính, phần in đậm đã đo trên máy này): xử lý tệp TXT/PDF có chữ vài giây (**đo: ~2 s với TXT**), PDF scan lâu hơn do OCR; phát hành < 1 s; dựng lại chỉ mục **~30 s (đo: 26–29 s)**; nạp chỉ mục mới vào API và làm nóng quyền truy cập ước tính 20–60 s. Tổng ước tính **1–2 phút**.

Thu hồi tài liệu đã **có hiệu lực ngay** hôm nay: mỗi lượt hỏi, chat kiểm lại quyền từng chunk với DB (`rag_v2_sources`, cổng SQL theo release), nên tài liệu bị thu hồi không được dùng nữa mà không cần dựng lại chỉ mục.

## 2. Hiện trạng (đã kiểm 2026-11-16)

- Luồng hiện có: tải lên → worker xử lý/nhúng BGE → **người duyệt khác tác giả** → dựng release → xem trước → **xác nhận** → con trỏ release tăng generation. Mọi bước sau tải lên đều là thao tác tay.
- Không có gì tự phát hành: lịch hẹn (`schedules.py`) chỉ chạy khi có phiên quản trị đang mở và luôn dừng ở `AWAITING_CONFIRMATION` (`publication_authority: False`).
- Chat dùng chỉ mục RAG v2 dạng ảnh chụp gắn với một release (`data/rag_v2_index/embedded2`, generation 27). Sau phát hành, `/health/ready` báo `stale` (HTTP 503 `degraded`) và tài liệu mới **không được chat tìm thấy** cho đến khi dựng lại chỉ mục (`scripts/refresh_rag_v2_index.py`) và **khởi động lại API** (~40 s gián đoạn chat).
- Chỉ có 1 tài khoản `KNOWLEDGE_ADMIN` (owner); `SUPPORT_OFFICER` và `STUDENT` bị chặn (403). Vì người duyệt phải khác tác giả, hiện **không thể phát hành** tài liệu nào owner tự tải lên.
- Đã kiểm chứng: dựng lại chỉ mục bằng công cụ hiện có tái lập chỉ mục đang chạy (9167/9173 vector giống từng bit, phần còn lại lệch ≤ 1,9×10⁻⁹); thêm tài liệu mới không làm đổi top-5 của 80 câu hỏi cũ (vector và từ khóa).

## 3. Thiết kế

### 3.1 Vai trò và chính sách phát hành

Thêm một vai trò, giữ các vai trò cũ:

| Vai trò | Thêm tài liệu | Duyệt tài liệu của người khác | Tự đăng tài liệu của mình | Thu hồi |
|---|---|---|---|---|
| `KNOWLEDGE_CONTRIBUTOR` (**mới**) | có | không | không (luôn qua duyệt) | không |
| `KNOWLEDGE_ADMIN` | có | có | **có** (đăng trực tiếp) | có |
| `SYSTEM_ADMIN` | như `KNOWLEDGE_ADMIN` | | | |

Người đăng trực tiếp phải tick một xác nhận khi bấm Đăng: *"Tôi xác nhận đây là văn bản chính thức, đúng nguồn và đúng phạm vi áp dụng."* Xác nhận này được lưu nguyên văn kèm danh tính, thời điểm, mã băm tệp và metadata.

**Đây là thay đổi chính sách an toàn có chủ đích:** hôm nay hệ thống bắt buộc hai người (tác giả ≠ người duyệt ≠ người phát hành). Với `KNOWLEDGE_ADMIN`, thiết kế chuyển thành *một người + kiểm tra tự động + nhật ký + thu hồi tức thì*. Người đóng góp vẫn theo nguyên tắc hai người.

### 3.2 Bộ điều phối phát hành (chạy trong worker nhập liệu)

Một máy trạng thái bền vững trong Postgres, bảng mới `knowledge_auto_publication` (một dòng/tài liệu), do worker nhập liệu chạy (worker đã chạy nền liên tục, có DB, tách khỏi API):

```
NHẬN → ĐANG XỬ LÝ → KIỂM TRA TỰ ĐỘNG ─┬─(người đóng góp)→ CHỜ DUYỆT ─(Duyệt)─┐
                                      └─(người đăng trực tiếp)──────────────┤
                                                                            ▼
                     ĐÃ DÙNG ĐƯỢC ← ĐANG NẠP CHỈ MỤC ← ĐANG DỰNG CHỈ MỤC ← ĐANG PHÁT HÀNH
       (nhánh lỗi ở mọi bước → CẦN XỬ LÝ, kèm lý do và nút hành động; nhánh ngày hiệu lực tương lai → CHỜ NGÀY HIỆU LỰC)
```

- Mỗi bước dùng khóa idempotency và advisory lock sẵn có; worker chết giữa chừng thì chạy lại đúng bước đó, không phát hành hai lần.
- **Gom lô:** chờ ~30 s sau lần duyệt/đăng gần nhất rồi phát hành chung một release (dùng `build_batch_release` sẵn có), để nhiều tài liệu chỉ cần một lần dựng chỉ mục.
- **Phát hành:** dùng nguyên `build_batch_release` → `preview` → `confirm` hiện có, thực thi bởi một danh tính dịch vụ `system:auto-publisher` (khác tác giả, nên các kiểm tra tách quyền và cổng SQL truy xuất `rv.reviewer_id<>x.created_by` **giữ nguyên, không sửa**). Bản ghi duyệt ghi rõ căn cứ: "xác nhận của người đăng (vai trò KNOWLEDGE_ADMIN) + kiểm tra tự động" hoặc "duyệt bởi <người duyệt>".
- **Ngày hiệu lực tương lai:** giữ ở CHỜ NGÀY HIỆU LỰC và tự phát hành khi tới ngày (thay vì lỗi `RELEASE_NOT_YET_EFFECTIVE`).

### 3.3 Kiểm tra tự động (thay cho phần việc "đối chiếu tay" mà máy làm được)

Chạy sau khi worker xử lý xong; bất kỳ điều kiện nào trượt → CẦN XỬ LÝ, không phát hành:

1. Job xử lý `SUCCEEDED`, có ít nhất một chunk đã nhúng; nội dung trích không rỗng.
2. Metadata đủ: tiêu đề, đơn vị ban hành, URI nguồn `https://` (đã chặn `urn:` ở chế độ vận hành), phạm vi (mặc định HUCE/FIT/PUBLIC/sinh viên).
3. Không trùng: cùng mã băm với văn bản đang phát hành → dừng để người quyết định (dùng lại / phiên bản mới / tách riêng), dùng luồng `link-existing`/`keep-separate` sẵn có.
4. PDF scan: OCR phải đạt một ngưỡng chất lượng tính từ bằng chứng OCR mà worker đã ghi (ngưỡng cụ thể chốt khi triển khai, sau khi đo trên các PDF scan hiện có); không đạt → CẦN XỬ LÝ.
5. Quét prompt-injection (bộ dò sẵn có) trên các đoạn trích; có cảnh báo → CẦN XỬ LÝ.
6. Giới hạn kích thước/số trang như hiện tại.

### 3.4 Duyệt một lần bấm (người đóng góp)

Màn hình duyệt hiện bản trích, metadata, kết quả kiểm tra tự động và *danh sách những gì sẽ thành dữ liệu chatbot*. Nút **Duyệt** = ghi bản duyệt + xác nhận phát hành trong một thao tác (giao diện lấy phiếu xem trước khi mở màn hình, gửi kèm khi bấm; phiếu hết hạn thì xin lại). Nút **Từ chối** kèm lý do. Sau Duyệt, mọi thứ còn lại do bộ điều phối làm.

### 3.5 Tự cập nhật chỉ mục chat — **phần chạm RAG, cần chủ hệ thống duyệt**

Sau mỗi lần con trỏ release đổi:

1. **Dựng** (worker): chạy đúng logic `refresh_rag_v2_index.py` — xuất corpus của release đang phục vụ, `rag_v2_build_index.py --embed --base <chỉ mục đang chạy> --batch-size 1` vào thư mục mới. Không đổi bộ tách đoạn, mô hình nhúng, batch size, ngưỡng, rerank, prompt. Kiểm: manifest khớp release/generation, kiểm kê chunk khớp DB, checksum đúng. Ghi một dòng `READY` vào bảng mới `rag_v2_index_registry`.
2. **Nạp nóng** (mỗi tiến trình API): định kỳ ~5 s đọc registry; thấy chỉ mục mới thì nạp trong luồng nền với đúng các kiểm tra của `load_rag_v2` hiện tại, làm nóng phần kiểm quyền cho generation mới (nếu không, lượt hỏi đầu tiên sau phát hành sẽ chậm hàng chục giây), quét injection cho đơn vị mới, rồi **đổi con trỏ một lần** sang chỉ mục mới. Lượt hỏi đang chạy dùng nốt chỉ mục cũ. Chỉ mục cũ giữ nguyên trên đĩa để quay lại.
3. **Sức khỏe:** trong lúc đang dựng/nạp (tối đa 10 phút), `/health/ready` trả `ready` kèm `snapshot_state: "refreshing"` thay vì 503, để proxy/systemd ở cloud không coi API là chết. Quá 10 phút hoặc dựng lỗi → `degraded` như hiện nay, và chat tiếp tục dùng chỉ mục cũ.

Mã cần sửa cho phần này: `bootstrap/rag_v2.py` (thêm hàm nạp lại), `agent/nodes/rag_v2.py` (thêm một phương thức đổi chỉ mục: thay `index`, `service`, tập chunk được phép, xóa bộ nhớ đệm `_prepared`), `presentation/health.py`. **Không** sửa truy xuất, xếp hạng, ngưỡng, prompt, cổng SQL quyền.

Phương án thay thế không chạm mã RAG: bộ điều phối tự khởi động lại API sau mỗi lần dựng chỉ mục. Đơn giản hơn nhưng mỗi lần phát hành chat gián đoạn ~40–60 s và dồn 503 cho người đang hỏi. **Đề xuất: nạp nóng.**

### 3.6 Giao diện

- Một biểu mẫu thêm tài liệu cho cả hai vai trò (gộp biểu mẫu cũ và luồng tiếp nhận hai bước): tệp, tiêu đề, đơn vị ban hành, URI `https://`, ngày hiệu lực (mặc định: ngay), phạm vi (mặc định). Nút đổi theo vai trò: **Đăng** hoặc **Gửi duyệt**.
- Mỗi tài liệu có dòng trạng thái theo các bước ở 3.2, cập nhật tự động, ghi thời điểm "dùng được từ".
- CẦN XỬ LÝ hiện lý do bằng tiếng Việt và hành động: sửa thông tin, thử lại, chọn cách xử lý trùng, hủy.
- Người đăng trực tiếp có nút **Thu hồi** (có hiệu lực ngay).

### 3.8 Tự cào tài liệu từ trang công khai của trường

**Hiện có:** bộ tải URL (`infrastructure/knowledge/fetch.py`) tải *một* URL do quản trị viên nhập, chỉ `https://` thuộc `huce.edu.vn` và tên miền con, chặn địa chỉ nội bộ (ghim DNS), kiểm TLS, không gửi thông tin đăng nhập, ≤ 50 MB, ≤ 5 lần chuyển hướng, tải lại có điều kiện (ETag/Last-Modified). Bộ tải này **không** dò liên kết, **không** đọc HTML (worker chỉ nhận PDF/TXT làm bản gốc; trang HTML dừng ở `LINKED_ORIGINAL_REQUIRED`), **không** theo tệp đính kèm. Chưa có thư viện phân tích HTML/DOCX nào được cài.

**Mục tiêu:** chủ hệ thống khai báo các trang gốc của trường; hệ thống tự dò định kỳ, lấy văn bản mới hoặc đã thay đổi, đưa vào đúng luồng tự động ở 3.2 (mặc định qua người duyệt).

#### Cấu hình nguồn (bảng `knowledge_crawl_source`)
Mỗi nguồn gốc do `KNOWLEDGE_ADMIN` khai báo: URL gốc (`https://*.huce.edu.vn`), loại (`trang danh sách` | `sitemap` | `một trang`), mẫu URL được phép/loại trừ, độ sâu (mặc định 2), số trang tối đa mỗi lần chạy (mặc định 200), lịch (mặc định mỗi ngày 1 lần, ngoài giờ cao điểm), đơn vị ban hành, phạm vi người đọc, và **chế độ phát hành**: `CẦN DUYỆT` (mặc định) hoặc `ĐĂNG THẲNG` (chỉ cho mục chủ hệ thống chỉ định là văn bản chính thức; cấu hình này là căn cứ xác nhận, được ghi nhật ký).

#### Một lượt chạy (trong worker nhập liệu, có khóa để chỉ một lượt chạy cùng lúc)
1. **robots.txt:** đọc bằng `urllib.robotparser` (thư viện chuẩn), giữ 24 h; tuân `Disallow` và `Crawl-delay`. Không đọc được robots.txt thì chạy ở chế độ thận trọng (chỉ đúng các URL gốc, không dò sâu).
2. **Dò liên kết:** đọc `sitemap.xml` nếu có, trang danh sách; tách liên kết bằng `html.parser` (thư viện chuẩn); chuẩn hóa URL; chỉ giữ URL qua `public_document_url` (quy tắc tên miền hiện có) và khớp mẫu được phép; bỏ trang đăng nhập, tìm kiếm, lịch, URL có tham số phiên.
3. **Tải:** dùng nguyên `PublicDocumentFetcher` (mọi chốt an toàn hiện có), tải có điều kiện; tốc độ **1 yêu cầu / 3 s mỗi tên miền**, 1 kết nối; User-Agent tự giới thiệu là bot của Campus 24/7. Không đổi (304 hoặc cùng mã băm) → bỏ qua.
4. **Chuyển thành văn bản** (bản gốc luôn được lưu nguyên làm bằng chứng bất biến):
   - Trang HTML → bộ tách nội dung chính viết bằng `html.parser`: bỏ `script/style/nav/header/footer/form`, chọn `<article>`/`<main>` hoặc khối chữ dày nhất, giữ tiêu đề, danh sách, bảng (mỗi dòng bảng một dòng chữ). Kết quả là một bản TXT kèm tiêu đề, URL, ngày đăng nếu tìm thấy, thời điểm tải → đi vào worker như tệp TXT, nên **bộ tách đoạn và chỉ mục RAG không đổi**.
   - PDF → luồng PDF hiện có.
   - DOCX → đọc `word/document.xml` bằng `zipfile` + XML (thư viện chuẩn): đoạn văn và bảng.
   - DOC đời cũ (nhị phân) → CẦN XỬ LÝ; muốn đọc tự động phải thêm bộ chuyển đổi (ví dụ LibreOffice), là phụ thuộc mới cần chủ hệ thống duyệt.
5. **Lọc dữ liệu cá nhân (bắt buộc, trước khi vào kho):** bộ dò xác định theo luật: bảng có cột kiểu "Họ và tên / Mã SV / Ngày sinh / Điểm", nhiều mã sinh viên, số CCCD, số điện thoại, email cá nhân. Trang/tệp dính → `LOẠI: DỮ LIỆU CÁ NHÂN`, không bao giờ vào chatbot, chỉ ghi URL và lý do. Định dạng mã sinh viên HUCE và các mẫu cụ thể chốt khi triển khai, kiểm trên các trang thật.
6. **Lọc nội dung:** quá ngắn, trang danh sách thuần, tin sự kiện (theo mẫu URL/mục do chủ hệ thống cấu hình) → bỏ qua, có ghi lý do. Thông báo có vẻ đã hết hạn → không bỏ, gắn cờ cho người duyệt.
7. **Tự điền metadata:** tiêu đề từ `<h1>`/`<title>`, đơn vị ban hành và phạm vi từ cấu hình nguồn, `canonical_uri` = URL trang (https), ngày hiệu lực = ngày đăng tìm thấy, nếu không có thì ngày tải và gắn cờ "ngày hiệu lực chưa xác minh" cho người duyệt.
8. **Đưa vào luồng 3.2** bằng danh tính dịch vụ `system:crawler` với vai trò người đóng góp (`CẦN DUYỆT`), hoặc qua `system:auto-publisher` nếu nguồn ở chế độ `ĐĂNG THẲNG`.

#### Cập nhật và biến mất
- Trang/tệp đổi nội dung → phiên bản mới của cùng nguồn → theo chế độ phát hành của nguồn; bản cũ chỉ được thay sau khi bản mới được duyệt/đăng.
- Trang không còn (404/410) → gắn cờ "nguồn không còn" để quản trị quyết định thu hồi; không tự thu hồi (giữ nguyên nguyên tắc hiện có: lỗi truy cập không phải căn cứ thu hồi).
- Cùng một tệp đính kèm ở nhiều trang → một tài liệu (cùng mã băm), dùng luồng xử lý trùng sẵn có.

#### Giao diện "Nguồn tự động" (chỉ `KNOWLEDGE_ADMIN`)
Thêm/sửa/tạm dừng nguồn, nút "Chạy ngay", và báo cáo mỗi lượt chạy: số trang tìm thấy / mới / đổi / bỏ qua / loại vì dữ liệu cá nhân, kèm lý do từng trang.

#### Phép lịch sự và pháp lý
Chỉ trang công khai của HUCE, không đăng nhập, tuân robots.txt, tải chậm, tự giới thiệu là bot. Nên báo trước hoặc xin phép đơn vị quản trị website của trường; nếu trường có RSS/nguồn tin chính thức thì ưu tiên dùng.

### 3.9 Những gì giữ nguyên

Xác thực, phân quyền theo vai trò, cổng SQL quyền truy cập ở mỗi lượt hỏi, trích dẫn và kiểm chứng câu trả lời, nhật ký kiểm toán, idempotency, quét injection, hiệu lực theo ngày, thu hồi, bất biến của bản đã duyệt.

## 4. Triển khai theo giai đoạn

| GĐ | Nội dung | Chạm RAG? |
|---|---|---|
| 0 | (đã làm, chưa nạp vào runtime) chặn `urn:` khi tải lên ở chế độ vận hành; biểu mẫu cũ chỉ nhận `https://`; worker bật cùng `pnpm start`; lệnh làm mới chỉ mục | không |
| 1 | Vai trò `KNOWLEDGE_CONTRIBUTOR`; tài khoản `system:auto-publisher`; bảng `knowledge_auto_publication`; kiểm tra tự động; bộ điều phối phát hành; duyệt một lần bấm; biểu mẫu + dòng trạng thái | không |
| 2 | Dựng chỉ mục tự động + registry trong worker | không (chỉ chạy công cụ có sẵn) |
| 3 | Nạp nóng chỉ mục trong API + trạng thái `refreshing` | **có**: cần duyệt |
| 4 | Kiểm thử đầu-cuối và nghiệm thu | — |
| 5a | Bộ dò: robots.txt, sitemap/trang danh sách, tách liên kết; **chạy thử chỉ đọc** trên 1–2 nguồn thật (không nạp gì) và báo cáo trang tìm được | không |
| 5b | Chuyển HTML/DOCX thành văn bản; lọc dữ liệu cá nhân; lọc nội dung; tự điền metadata | không |
| 5c | Đưa vào luồng 3.2 (mặc định cần duyệt); phát hiện thay đổi/biến mất; lịch chạy; giao diện "Nguồn tự động" | không |

GĐ5 chỉ cần GĐ1 (luồng tự động + vai trò người đóng góp); không phụ thuộc GĐ3. Không thêm thư viện mới (dùng `html.parser`, `urllib.robotparser`, `zipfile`), trừ khi chủ hệ thống muốn đọc tệp `.doc` đời cũ.

Nếu chưa duyệt GĐ3, GĐ1–2 vẫn chạy: tài liệu tự phát hành và chỉ mục tự dựng sẵn; bước cuối là khởi động lại API (thủ công hoặc phương án tự khởi động lại).

## 5. Kiểm thử và nghiệm thu

- Unit: máy trạng thái (mọi chuyển trạng thái, worker chết giữa chừng, gom lô, ngày hiệu lực tương lai), kiểm tra tự động, phân quyền 3 vai trò (403 đúng chỗ).
- Postgres trong tenant cô lập (như bộ kiểm `knowledge-e2e-*` đã dùng): cả hai luồng vai trò từ tải lên đến truy xuất đúng; thu hồi; trùng lặp; lỗi xử lý.
- Nạp nóng: dựng chỉ mục ứng viên có tài liệu mới, đổi trong tiến trình, kiểm 80 câu hỏi cũ cho top-5 giống hệt và tài liệu mới đứng đầu cho câu hỏi của nó (cách đã làm 2026-11-16); lượt hỏi đang chạy không lỗi khi đổi.
- Trên runtime 8015: một tài liệu thật do chủ hệ thống chọn, đo thời gian từ bấm đến khi chat trả lời có trích dẫn đúng.
- Bộ cào: test chạy trên trang HTML/DOCX mẫu tự viết mô phỏng cấu trúc trang trường (test không gọi mạng); robots.txt, chuẩn hóa/lọc URL ngoài `huce.edu.vn`, tốc độ tải, phát hiện thay đổi (304/mã băm), trang biến mất; bộ lọc dữ liệu cá nhân với các ca có và không có dữ liệu cá nhân (không được lọt ca nào có dữ liệu cá nhân). Trước khi bật nạp thật: một lượt chạy thử chỉ đọc trên trang thật, chủ hệ thống xem báo cáo.
- Cổng hồi quy RAG nhanh (`rag_regression_gate.py run --quick`) cần nhà cung cấp trả phí (~600 lượt gọi): chỉ chạy khi chủ hệ thống đồng ý.

## 6. Rủi ro

| Rủi ro | Giảm thiểu |
|---|---|
| Một quản trị viên đăng nhầm văn bản | xác nhận bắt buộc, kiểm tra tự động, nhật ký, thu hồi tức thì |
| RAM thấp (máy này thường chỉ ~2–3 GB trống) | worker đã chờ khi RAM < 2 GB; nạp nóng giữ hai chỉ mục tạm thời (+~50–150 MB/tiến trình API, ước tính) |
| Dựng chỉ mục lỗi | giữ chỉ mục cũ, báo CẦN XỬ LÝ, thử lại có giãn cách |
| Lượt hỏi đúng lúc đổi chỉ mục | lượt đang chạy dùng chỉ mục cũ; trường hợp hiếm nhận "nguồn đã thay đổi, vui lòng hỏi lại" như hiện nay |
| Nhiều phát hành liên tiếp | gom lô 30 s, một lần dựng cho cả lô |
| Bộ cào đưa dữ liệu cá nhân (danh sách sinh viên, điểm) vào chatbot | lọc bắt buộc trước khi vào kho; mặc định qua người duyệt; ca kiểm có dữ liệu cá nhân phải bị chặn 100 % |
| Thông báo cũ/hết hạn được trả lời như còn hiệu lực | ngày hiệu lực chưa xác minh được gắn cờ cho người duyệt; mặc định không đăng thẳng |
| Trang trường đổi bố cục, bộ tách nội dung lấy sai phần | báo cáo mỗi lượt chạy; trang có chữ quá ít/bất thường → CẦN XỬ LÝ; người duyệt xem bản trích trước khi duyệt |
| Website trường chặn bot hoặc phản đối | tuân robots.txt, tải chậm, tự giới thiệu; báo trước/xin phép đơn vị quản trị website |

## 7. Cần chủ hệ thống quyết định

1. **Mô hình vai trò** ở 3.1 (đề xuất: `KNOWLEDGE_ADMIN` đăng trực tiếp, thêm `KNOWLEDGE_CONTRIBUTOR` cần duyệt).
2. **Duyệt GĐ3** (nạp nóng chỉ mục, chạm mã nạp RAG nhưng không chạm truy xuất/xếp hạng), hoặc chọn phương án tự khởi động lại API.
3. **Tài khoản:** ai giữ vai trò nào. Tạo tài khoản là việc của chủ hệ thống; có thể dùng tài khoản thử để kiểm thử.
4. **Nguồn tự động (3.8):** danh sách trang gốc của trường cần theo dõi; nguồn nào (nếu có) được đăng thẳng — đề xuất ban đầu: **không có**, tất cả qua người duyệt; tần suất chạy (đề xuất: mỗi ngày); có cần đọc tệp `.doc` đời cũ không (cần thêm phụ thuộc); có báo trước/xin phép đơn vị quản trị website của trường không.

## 8. Tình trạng triển khai (2026-11-16)

Chủ hệ thống đã duyệt thiết kế và các đề xuất (vai trò, nạp nóng chỉ mục, nguồn cào qua người duyệt). Đã cài đặt:

| Phần | Mã | Kiểm chứng |
|---|---|---|
| Vai trò `KNOWLEDGE_CONTRIBUTOR`, cổng quyền `contributor()`/`admin()`, cấp tài khoản | `ports/identity.py`, `application/knowledge/platform.py`, `infrastructure/identity/local_owner.py`, `scripts/provision_knowledge_contributor.py` | `test_contributor_identity.py` |
| Bộ điều phối phát hành tự động, kiểm tra tự động, duyệt một lần bấm | `application/knowledge/auto_publication.py`, `infrastructure/knowledge/auto_publication_store.py` | `test_auto_publication_postgres.py` (Postgres thật, BGE thật, truy xuất sau phát hành tự động) |
| API và giao diện "Thêm tài liệu" | `presentation/knowledge_platform.py` (`/documents`), `KnowledgeDocuments.tsx`, trang `/knowledge/documents` | `test_document_routes_postgres.py`, `KnowledgeDocuments.test.tsx` |
| Dựng chỉ mục tự động + sổ đăng ký | `infrastructure/knowledge/index_builder.py`, `scripts/refresh_rag_v2_index.py --tag --json` | chạy thật (xem mục 9) |
| Nạp nóng chỉ mục trong API | `bootstrap/rag_v2.py` (`SwappableRagNode`, `RagV2IndexReloader`), `presentation/health.py` (`refreshing`) | `tests/rag_v2/test_hot_reload_20261116.py` |
| Bộ cào trang HUCE (chạy thử chỉ đọc → nạp qua hàng chờ duyệt) | `application/knowledge/crawl/*`, `infrastructure/knowledge/crawl_fetch.py`, `crawl_store.py`, trang `/knowledge/crawl` | `test_crawl_pure.py`, `test_crawl_postgres.py`, `KnowledgeCrawl.test.tsx` |

Khác biệt so với thiết kế: (1) bảng trạng thái được tạo bằng `CREATE TABLE IF NOT EXISTS` thay vì migration Alembic, vì runtime chỉ chấp nhận một số revision schema cố định và guard băm migration cần người duyệt; (2) lệnh `activate_rag_v2_index.py` không còn cần: API tự nạp nóng; (3) URL đã có trong kho mà bộ cào chưa theo dõi được báo `EXISTS`, không ghi đè hay tạo bản trùng (URL nguồn là duy nhất toàn nền tảng).
