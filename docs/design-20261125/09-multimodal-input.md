# F8 — Hỏi bằng ảnh và giọng nói

Cờ: `input.image`, `input.voice`, `output.read_aloud`. Không đổi lõi RAG: ảnh và giọng nói chỉ được chuyển thành **văn bản do người dùng xác nhận**, rồi đi vào chat như một câu hỏi gõ tay.

## 1. Mục tiêu và giá trị

- **Ảnh**: sinh viên chụp thông báo dán bảng, biểu mẫu hay trang sổ tay rồi hỏi luôn. Hệ thống đọc chữ bằng OCR tiếng Việt chạy local (đã có), cho người dùng xem và sửa chữ đọc được, rồi gửi câu hỏi kèm nội dung đó.
- **Giọng nói**: bấm micro để nói câu hỏi tiếng Việt; chữ hiện ra để sửa trước khi gửi. Hữu ích khi đang di chuyển, và cho người khó gõ phím.
- **Đọc to câu trả lời**: nút "Đọc" dùng giọng đọc sẵn trên thiết bị, hữu ích cho người khiếm thị hoặc khi không tiện nhìn màn hình.

## 2. Hiện trạng liên quan

- OCR tiếng Việt chạy local: `services/worker/src/campus247_worker/knowledge_ocr.py`.
  - Nhận ảnh PNG (kiểm chữ ký PNG và kích thước), dùng `vie.traineddata` đã ghim hash, chạy qua gói node có ghim.
  - Học liệu có thêm `learning/ocr_sandbox.py` và `ocr_supervisor.py` (sandbox, giám sát tiến trình).
  - Runtime OCR native (Tesseract/Poppler) có tài liệu ở memory `learning-ocr-native-runtime`.
- Bộ nhớ máy local chật (khoảng 3 GB trống khi mọi thứ chạy, memory `runtime-8015-startup-gotchas`).
- Hồ sơ cloud 4 vCPU / 8 GB đã có bảng ngân sách RAM chặt (`infra/profiles/cloud.toml`, mục `[memory]`).
- Chưa có nhận dạng giọng nói.
- Kiểm an toàn đầu vào chat (phân loại an toàn, `EgressPolicy`, `PromptInjectionDetector`) đã áp cho mọi văn bản người dùng gửi.

## 3. Tiêu chí xong (kiểm được)

1. **OCR ảnh.** Có 120 ảnh tổng hợp dựng từ văn bản tiếng Việt đã biết (kiểu thông báo, biểu mẫu, bảng ngắn), chia 3 nhóm:
   - sạch: CER ≤ 5 %;
   - nghiêng ±7°, nhiễu, độ sáng lệch: CER ≤ 12 %;
   - chụp nghiêng phối cảnh: chỉ báo số đo, chưa đặt ngưỡng.

   Gold là văn bản dựng, nên đúng theo cách tạo. Ảnh được dựng bằng Playwright (đã có trong repo) chụp trang HTML, rồi biến dạng bằng script có seed.
2. **Không lưu ảnh.** Sau mỗi yêu cầu, thư mục tạm rỗng và không có đối tượng nào trong storage. Test kiểm hệ thống tệp.
3. **Người dùng kiểm soát.** Chữ từ ảnh hay giọng nói **không bao giờ** tự gửi vào chat. Luôn có bước xem, sửa và bấm "Gửi". Test giao diện kiểm điều này.
4. **Giọng nói** (khi D6 chọn model local): WER ≤ 20 % trên bộ kiểm tiếng Việt được chọn ở D6b; p95 thời gian ≤ 1,5 × độ dài đoạn nói trên CPU máy local. Cổng RAM từ chối khởi động model khi RAM trống < nhu cầu model + 500 MB, và trả `503 VOICE_UNAVAILABLE` rõ ràng.
5. **Đọc to** chỉ dùng giọng có `localService === true` trên thiết bị, nên văn bản không rời máy. Không có giọng tiếng Việt local thì nút ẩn kèm chú thích.
6. Tắt từng cờ thì nút tương ứng biến mất và route 404.

## 4. Phạm vi

**Trong phạm vi:**
- OCR ảnh một trang cho câu hỏi chat;
- nhận dạng giọng nói tiếng Việt ≤ 60 giây;
- đọc to câu trả lời bằng giọng của thiết bị.

**Ngoài phạm vi:**
- hiểu ảnh bằng model thị giác (ảnh sẽ rời máy, tốn phí; để quyết định sau);
- ảnh nhiều trang hay PDF (đã có ở luồng tài liệu tri thức);
- hội thoại giọng nói hai chiều thời gian thực;
- tự điền trình mô phỏng F2 từ ảnh bảng điểm. Có thể làm sau, ghi ở §11.

## 5. Ảnh (`input.image`)

### 5.1 Luồng

```
[Trình duyệt] chọn hoặc chụp ảnh (input accept="image/*" capture="environment")
  → xoay/cắt (tùy chọn) → vẽ lại lên canvas, thu nhỏ cạnh dài ≤ 2000 px, xuất PNG (bỏ EXIF, bỏ vị trí GPS)
  → POST /v1/input/image:ocr (PNG ≤ 4 MB)
[API] kiểm chữ ký PNG, IHDR, kích thước ≤ 2000×2000, dung lượng; rate limit 20 ảnh/ngày/người
  → ghi tệp tạm trong thư mục riêng của yêu cầu (quyền chỉ của tiến trình)
  → OCR qua adapter local (sandbox + timeout 15 s), ngôn ngữ vie
  → xóa tệp tạm (finally) → trả {text, lines[{text, confidence, bbox}], mean_confidence, warnings}
[Trình duyệt] hiện chữ đọc được (dòng tin cậy thấp được gạch chân) trong ô sửa được
  → người dùng thêm câu hỏi ("Hạn nộp là khi nào?") → bấm Gửi
  → tin nhắn chat = câu hỏi + "\n\nNội dung từ ảnh (đã xác nhận):\n" + chữ đã sửa (cắt ≤ 2 000 ký tự)
```

### 5.2 Quyết định thiết kế

- **Chuyển sang PNG ở trình duyệt.** Lý do: máy chủ khỏi phải phân tích JPEG/HEIC (thêm thư viện, thêm bề mặt tấn công), EXIF và GPS bị loại trước khi rời máy, và adapter OCR hiện chỉ nhận PNG. Máy chủ vẫn kiểm lại PNG theo cách `knowledge_ocr.py` đang kiểm.
- **Không lưu ảnh, không lưu chữ OCR.** Chữ chỉ tồn tại trong phản hồi. Nếu người dùng gửi vào chat, nó trở thành nội dung tin nhắn và theo quy tắc lưu hội thoại hiện có.
- **Quét mã độc**: không áp cho v1, vì ảnh được vẽ lại thành PNG mới ở trình duyệt, kiểm cấu trúc ở máy chủ, không bao giờ được phục vụ lại cho ai, và bị xóa ngay. Khi có `clamd` (`CAMPUS247_SCANNER_*`), quét thêm một lớp, không bắt buộc.
- **Chữ từ ảnh là dữ liệu của người dùng.** Nó đi qua đúng các kiểm an toàn của tin nhắn chat. Ảnh chứa câu "bỏ qua chỉ dẫn" thì bị xử lý như người dùng gõ câu đó.

### 5.3 API

`POST /v1/input/image:ocr`, `multipart/form-data` với trường `image` (PNG):
- `200`: `{"text": "...", "lines": [{"text": "...", "confidence": 0.93, "bbox": [x, y, w, h]}], "mean_confidence": 0.88, "warnings": ["LOW_CONFIDENCE", "TEXT_TRUNCATED"]}`.
- Lỗi:
  - `413 IMAGE_TOO_LARGE`;
  - `415 IMAGE_NOT_PNG`;
  - `422 IMAGE_DIMENSIONS`;
  - `429 IMAGE_RATE`;
  - `503 OCR_UNAVAILABLE` (adapter hay gói ngôn ngữ thiếu hoặc lệch hash);
  - `504 OCR_TIMEOUT`.
- Chỉ người đã đăng nhập. Header `Cache-Control: no-store`.

Thêm tiền tố `/v1/input/` vào `ALLOWED_API_PREFIXES`.

## 6. Giọng nói (`input.voice`)

### 6.1 Các phương án (quyết định D6)

| Phương án | Ưu | Nhược | Đề xuất |
|---|---|---|---|
| A. Model local trên máy chủ (faster-whisper hoặc whisper.cpp, model cỡ nhỏ, int8, CPU) | Âm thanh không rời hệ thống; không phí | Tốn RAM khoảng 0,5–1,5 GB tùy cỡ; tải model cần đồng ý tải xuống (hash-pinned như onnxruntime); độ chính xác tiếng Việt cần đo | **Chọn**, chỉ bật khi đủ RAM |
| B. Web Speech API của trình duyệt | Không tốn máy chủ | Với Chrome, âm thanh được gửi tới máy chủ của hãng trình duyệt: dữ liệu rời hệ thống, ngoài kiểm soát | Không chọn mặc định; chỉ khi chủ dự án chấp nhận và có màn hình đồng ý riêng |
| C. Dịch vụ nhận dạng có phí | Chính xác cao | Phí; âm thanh rời hệ thống; cần hợp đồng xử lý dữ liệu | Không chọn |

### 6.2 Thiết kế phương án A

- Tiến trình riêng `scripts/serve_asr.py`, cổng local 18083, theo nếp model server 18081/18082.
  - Model nạp lười ở yêu cầu đầu tiên; gỡ sau 10 phút rảnh.
  - Cổng RAM: trước khi nạp, kiểm RAM trống ≥ `model_mb + 500`. Không đủ thì từ chối.
  - Model và thư viện được ghim phiên bản và SHA-256 (cùng quy trình đã làm với onnxruntime), tải bằng script có danh sách cho phép. Việc tải cần chủ dự án đồng ý (tên tệp, nguồn, dung lượng).
- Hồ sơ chạy thêm `asr_mb` vào ngân sách bộ nhớ của `runtime_profile.py`. Bảng `[memory]` có schema chặt, nên phải thêm khóa vào **cả** `local.toml` và `cloud.toml`. Hồ sơ cloud mặc định tắt `input.voice`.
- Trình duyệt ghi âm bằng `MediaRecorder` (`audio/webm;codecs=opus`), tối đa 60 s, có đồng hồ đếm và nút dừng. Quyền micro do trình duyệt hỏi, và chỉ hỏi khi người dùng bấm nút lần đầu.
- `POST /v1/input/voice:transcribe` (multipart `audio`, ≤ 2 MB, ≤ 60 s): API chuyển tới 18083 với timeout `max(10 s, 2 × độ dài)` và trả `{text, segments[{start, end, text}], language: "vi", duration_s}`.
  - Lỗi: `413 AUDIO_TOO_LARGE`, `415 AUDIO_FORMAT`, `422 AUDIO_TOO_LONG`, `429 VOICE_RATE` (30 lượt/ngày/người), `503 VOICE_UNAVAILABLE` (model tắt hoặc thiếu RAM), `504 VOICE_TIMEOUT`.
- Âm thanh không lưu: tệp tạm bị xóa trong `finally`. Log không có văn bản.
- Chữ nhận được hiện vào ô soạn, sửa được, và chỉ gửi khi bấm "Gửi" (tiêu chí 3).

### 6.3 Bộ kiểm giọng nói (D6b)

Cần một bộ âm thanh tiếng Việt có văn bản chuẩn. Các lựa chọn, đều cần chủ dự án quyết:
- (a) tập con công khai của một bộ dữ liệu tiếng Việt: kiểm giấy phép trước khi tải;
- (b) chủ dự án tự ghi khoảng 50 câu hỏi học vụ, văn bản chuẩn là câu đọc.

Chưa có bộ này thì tiêu chí 4 ghi **chưa đo**, và cờ không bật mặc định ở đâu cả.

## 7. Đọc to (`output.read_aloud`)

- Chạy hoàn toàn ở trình duyệt bằng `speechSynthesis`. Chọn giọng có `lang` bắt đầu `vi` **và** `localService === true`. Không có giọng như vậy thì ẩn nút, kèm chú thích "Thiết bị chưa có giọng đọc tiếng Việt".
- Đọc phần câu trả lời đã dựng (đoạn, danh sách), bỏ số trích dẫn `[CIT-001]`. Có nút dừng và tốc độ 0,8×, 1×, 1,25×.
- Không gọi máy chủ, không cần API.

## 8. Giao diện

- Ô soạn chat (`ChatPanel.tsx`) thêm hai nút biểu tượng có nhãn: "Hỏi bằng ảnh" (`Camera`) và "Nói câu hỏi" (`Mic`). Mỗi nút hiện theo cờ của nó.
- Hộp thoại ảnh có 4 bước: chọn hoặc chụp; xoay/cắt; "Đang đọc chữ…"; ô sửa chữ đọc được (dòng tin cậy thấp có gạch chân chấm) và ô câu hỏi, cùng nút Gửi.
- Ghi âm: nút chuyển trạng thái (bấm để nói, bấm để dừng), đồng hồ 0:00/1:00, sóng âm đơn giản; xong thì chữ vào ô soạn và con trỏ đặt ở cuối.
- Mỗi câu trả lời có nút "Đọc".
- Khả năng tiếp cận: mọi nút có `aria-label`; trạng thái ghi âm báo qua `aria-live`; ảnh không có văn bản thay thế vì nó không được hiển thị lại sau khi OCR.

## 9. Bảo mật và quyền riêng tư

- Ảnh và âm thanh không lưu, không log, không gửi ra ngoài (phương án A).
- Trình duyệt loại EXIF và GPS trước khi gửi.
- Rate limit theo người. Kích thước và thời lượng có trần.
- OCR và ASR chạy trong tiến trình hay sandbox riêng, có timeout. Không có đường thực thi tệp người dùng gửi.
- Văn bản chuyển đổi được kiểm an toàn như mọi tin nhắn.

## 10. Quan sát

`input_image_requests_total{result}`, `input_image_ocr_ms`, `input_image_mean_confidence` (histogram), `input_voice_requests_total{result}`, `input_voice_rtf` (thời gian xử lý chia độ dài), `asr_model_loaded` (gauge), `asr_ram_refusals_total`.

## 11. Kiểm thử

| Loại | Nội dung |
|---|---|
| Gold OCR | `scripts/eval/make_ocr_images.mjs`: 120 ảnh từ văn bản đã biết (Playwright + biến dạng có seed); đo CER theo nhóm; ghi `evals/results/input-ocr-<date>/` |
| Kiểm đầu vào | PNG giả (sai chữ ký, IHDR lớn, tệp nén bom), ảnh 0 byte, đúng ngưỡng ± 1 |
| Không lưu | Sau 50 yêu cầu (có cả lỗi giữa chừng), thư mục tạm rỗng |
| ASR | Khi có bộ D6b: WER, RTF; cổng RAM với RAM giả lập thấp thì 503 |
| Web | Vitest: chữ không tự gửi; nút theo cờ; đọc to chỉ chọn giọng local |
| Cờ | Ma trận F0 |

Ghi cho sau: tự điền biến F2 từ ảnh bảng điểm (OCR bảng + người dùng xác nhận từng ô) là gói riêng khi F2 có chủ đề cần điểm số.

## 12. Rủi ro

| Rủi ro | Giảm |
|---|---|
| OCR sai làm câu hỏi sai | Người dùng xem và sửa trước khi gửi; dòng tin cậy thấp được đánh dấu |
| Hết RAM do model giọng nói | Cổng RAM, nạp lười, gỡ khi rảnh, mặc định tắt trên cloud |
| Dữ liệu giọng nói rời hệ thống | Chỉ phương án A; B và C cần quyết định riêng |
| Tải model ngoài | Ghim hash, xin đồng ý tải, không tự tải |

## 13. Kế hoạch gói con

| Gói | Nội dung | Cỡ | Ghi chú |
|---|---|---|---|
| F8.1 | API OCR ảnh (kiểm PNG, tạm, sandbox, xóa) + gold 120 ảnh | M | |
| F8.2 | Giao diện ảnh (chụp, cắt, canvas sang PNG, sửa, gửi) | M | |
| F8.3 | Đọc to bằng giọng local của thiết bị | S | |
| F8.4 | Máy chủ ASR local + cổng RAM + hồ sơ bộ nhớ | M | **cần D6 và đồng ý tải model** |
| F8.5 | API và giao diện giọng nói | M | sau F8.4 |
| F8.6 | Bộ kiểm giọng nói và số đo | S | **cần D6b** |
