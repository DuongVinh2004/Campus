# HUCE public đã nạp advanced retrieval — 13/10/2026

Chat public tại `http://localhost:8000/chat` đã chạy bản tích hợp BM25 + BGE-M3
→ RRF → BGE-reranker → parent evidence → kiểm chứng claim. API dùng corpus,
lịch sử SQLite và ledger public hiện có. Frontend 3000 được giữ nguyên.

## Phần hoàn tất

- Nạp factory public vào runtime thật; log startup xác nhận mode
  `advanced_hybrid_conversational`, 131 parent nguồn. Index 261 child được đọc
  và xác minh fingerprint, không build/ghi đè corpus hoặc index.
- Thêm khóa độc quyền ledger giữa tiến trình Windows trước khi đọc credential,
  resume budget hoặc gọi paid HTTP. Test tiến trình thứ hai bị từ chối trước
  gateway. API advanced cũ ở 8001 được dừng; lịch sử của nó vẫn còn nguyên.
- Bổ sung guard cho phát biểu biến một phần của danh sách “đủ các điều kiện”
  thành điều kiện đủ. Ca phát hiện qua live QA bị chặn ở regression; ca live
  cuối giữ rõ “khi có đủ các điều kiện, trong đó…”, có nguồn Điều 15.
- Khắc phục model service bị kẹt sau lỗi client ngắt kết nối: HTTP boundary ghi
  mã lỗi hữu hạn, không ghi traceback/input; controller đọc stderr liên tục và
  giữ trong file mới. Worker BGE mới mang counters từ namespace -05 sang -06,
  không reset inference/token hoặc sửa model artifact/guard.
- Sửa import launcher để kiểm thử độc lập không phụ thuộc thứ tự import.
- Fixture citation synthetic cũ được khai báo `source_status=SYNTHETIC` rõ
  ràng; expected True giữ nguyên. Thêm ca nguồn public/không có metadata không
  được tự gán simulation. Không sửa logic citation để ép test pass.

Giữ nguyên auth/ownership, source hash/locator/citation readback, lọc tenant,
campus/hiệu lực, EvidenceGate/OutputGuard, xác nhận action và rate limit.
Model/endpoint/revision, 900 token/cặp, native 3 giây, CPU 4 core và 5 GiB vẫn
giữ nguyên. Retrieval sáu ứng viên tổng, tối đa ba subquery/bốn parent/15.000
byte/12 giây; generation 5 giây và 1.000 output token chia với regeneration và
semantic verifier. Không tăng cap để tránh lỗi.

## Kết quả quan sát

| Kiểm tra | Kết quả | Phạm vi |
|---|---|---|
| Suite regression cuối | **768/768 passed**, 33,03 giây, exit 0 | Retrieval, nguồn, chat/SSE, lịch sử, model limits, budget, lease và các guard; dùng model doubles |
| Nhóm wiring/model recovery chạy độc lập | **58/58 passed**, exit 0 | Không phụ thuộc thứ tự suite khác |
| Hội thoại public qua LLM thật | **10/10 qua** class/terms/source/hash/history | Bộ regression đã dùng trước; đo trước guard điều kiện cần/đủ cuối |
| Ca focused sau model recovery | **2/2 qua review** nội dung, material guard, hash/history | Chuyển ngành năm nhất và thư viện; không gọi thêm paid HTTP khi review lại |
| Hai request đồng thời trên bản cuối | **2/2 qua**, 8.016 và 10.219 ms | Một cặp câu thư viện/tín chỉ; không là phép đo capacity hoặc p95/p99 |
| Browser | Gửi chat thật, nhận citation, mở đoạn nguồn, reload phục hồi; bản cuối mở toàn văn Điều 15 | Screenshot và tab kết quả được giữ |
| Dữ liệu trước restart | 249 message public và 135 message advanced giữ nguyên từng record; không thiếu ID | Metadata một conversation public tăng do có thêm message, không thay nội dung cũ |
| Native controls | 4 physical core, 5 GiB; child tree trong Job; model read-only, outbound denied | Kiểm từ launch receipt của worker mới |

![Bằng chứng browser bản cuối](../infra/local/huce-public-hybrid-activation-20261013-01/browser-proof-final.jpg)

## Ngân sách và trạng thái runtime

Tại snapshot chốt: ledger ghi **8.463/8.500 calls**, **1.7349633/3 USD** tính bảo
thủ, còn **37 calls** và **1.2650367 USD**. Cap calls có thể chạm trước cap USD.
Số liệu thay đổi khi tiếp tục chat; không có tự tăng cap hoặc reset ledger.
Chênh lệch tổng trong khoảng kiểm chứng bao gồm hoạt động chat khác, không quy
toàn bộ cho runner. Ledger giữ tất cả uncertain reservations trước đó.

API public cuối PID 21172, launcher 16684. Model controller mới 21632; exact
worker/control receipt ở `infra/local/rag-advanced-models-20261013-06/launch.json`.
Frontend public 3000 và frontend advanced 3001 không bị dừng; API 8001 không còn
writer. Không khởi chạy lại advanced API song song để dùng chung paid ledger.

## Lỗi được giữ lại trong bằng chứng

- 10/10 kiểm tự động ban đầu không phát hiện câu chuyển ngành biến clause a
  thành điều kiện đủ dù nguồn yêu cầu a–d. Review thủ công phát hiện và guard
  được bổ sung; không dùng kết quả ban đầu để chứng minh correctness phổ quát.
- Hai ca focused sau reload API gặp retrieval dependency timeout, không có
  grounded final; generation không được chạy khi thiếu retrieval. Reranker
  `/info` bị kẹt trong khi embedding còn đáp ứng. Controller cũ sau khi dừng giữ
  3.824 byte stderr, ba traceback, hai marker ngắt kết nối. Sau sửa/drain và
  restart model, hai endpoint /info đúng revision đáp ứng và focused qua.
- Runner focused ban đầu đưa mã citation đã render vào numeric guard, tạo
  false failure cho thư viện vì CIT-001 bị hiểu là số 1. Audit chỉ đọc loại mã
  server đúng như claim input thực tế, giữ original report và nguồn; không
  thay expected fact/threshold hoặc gọi lại provider.
- So sánh history ban đầu đòi metadata conversation bất biến nên báo failure
  khi version/time tăng cùng một message được append. Audit giữ byte-identical
  mọi message cũ và field bất biến; sự khác biệt metadata được ghi riêng.
- Test nhóm nhỏ lần đầu lộ import launcher phụ thuộc sys.path của suite khác;
  đã sửa và nhóm độc lập qua. Các báo cáo thất bại vẫn được giữ nguyên.

## Bằng chứng và giới hạn

Thư mục `infra/local/huce-public-hybrid-activation-20261013-01/` chứa:

- `regression-final.xml`, `model-wiring-final-tests02.xml`;
- `live-dialogue*.json`, `condition-live-recovered*.json`, `concurrent-two-final.json`;
- `history-preservation-reviewed.json`, `history-difference-audit.json`;
- ba snapshot SQLite, các bản `.before`, startup/restart records và runtime logs;
- `browser-proof-final.jpg`, manifest hash và kiểm tra runtime chỉ đọc cuối.

Đây là tích hợp và kiểm chứng local trên snapshot public. Chưa chứng minh
held-out correctness/completeness, mọi trường hợp ngoại lệ, tải lớn dài hạn,
p95/p99 hoặc production readiness. Semantic verifier vẫn có thể sai; guard
điều kiện mới chỉ nhận dạng cấu trúc và ngôn ngữ sufficiency rõ ràng. Chất lượng
OCR và hiệu lực chính sách vẫn cần đối chiếu bản phát hành chính thức. Không
commit, push, triển khai production, xóa nguồn/lịch sử hoặc thay recovery controls.
